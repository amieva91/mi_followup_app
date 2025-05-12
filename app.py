# -*- coding: utf-8 -*-
import os
import pandas as pd
import io
import re
import traceback
import uuid
import json
import time
from datetime import date, timedelta, datetime
import glob
import requests # Para tipos de cambio
import yfinance as yf # Para precios acciones
from flask import (
    Flask, request, render_template, send_file, flash, redirect, url_for, session, get_flashed_messages
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, RadioField, FileField, MultipleFileField, HiddenField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import numpy as np

# --- Configuración Global ---
UPLOAD_FOLDER = 'uploads'           # Carpeta para archivos subidos (temporalmente por Flask)
OUTPUT_FOLDER = 'output'            # Carpeta para archivos CSV/JSON temporales generados
MAPPING_FILE = 'mapping_db.json'    # Archivo para guardar el mapeo ISIN -> Ticker/GoogleEx/Nombre
ALLOWED_EXTENSIONS = {'csv'}        # Extensiones permitidas para subir
OUTPUT_FILENAME = 'degiro_unificado.csv' # Nombre por defecto para descarga final

# !!! IMPORTANTE: DEFINE AQUÍ LA RUTA BASE SEGURA !!!
# Solo se permitirán cargar CSVs desde esta carpeta o sus subdirectorios.
# AJUSTA ESTA RUTA a una carpeta real y segura en tu sistema.
# Ejemplo Linux: SAFE_BASE_DIRECTORY = '/home/ssoo/safe_csv_imports'
# Ejemplo Windows: SAFE_BASE_DIRECTORY = 'C:/Users/ssoo/Documents/SafeCSVImports'
# Asegúrate de que esta carpeta exista.
SAFE_BASE_DIRECTORY = '/ruta/absoluta/a/tu/carpeta/segura/para/csvs' # <-- ¡¡¡AJUSTA ESTO!!!

# Nombres FINALES deseados y su orden para el CSV descargado
FINAL_COLS_ORDERED = [
    "Fecha", "Hora", "Producto", "ISIN", "Ticker", "Bolsa", "Exchange Yahoo",
    "Exchange Google", "Cantidad", "Precio", "Precio Divisa", "Valor Local",
    "Valor Local Divisa", "Valor", "Valor Divisa", "Tipo de cambio",
    "Costes Transacción", "Costes Transacción Divisa", "Total", "Total Divisa"
]

# Mapeo de columnas leídas del CSV a nombres finales del CSV unificado
COLS_MAP = { "Fecha": "Fecha", "Hora": "Hora", "Producto": "Producto", "ISIN": "ISIN", "Bolsa de": "Bolsa", "Número": "Cantidad", "Precio": "Precio", "Unnamed: 8": "Precio Divisa", "Valor local": "Valor Local", "Unnamed: 10": "Valor Local Divisa", "Valor": "Valor", "Unnamed: 12": "Valor Divisa", "Tipo de cambio": "Tipo de cambio", "Costes de transacción": "Costes Transacción", "Unnamed: 15": "Costes Transacción Divisa", "Total": "Total", "Unnamed: 17": "Total Divisa" }

# Mapeo de códigos de Bolsa (leídos de DeGiro) a sufijos de Yahoo Finance
BOLSA_TO_YAHOO_MAP = { 'NDQ': '', 'MAD': '.MC', 'OMX': '.ST', 'NSY': '', 'HKS': '.HK', 'EPA': '.PA', 'XET': '.DE', 'MIL': '.MI', 'DEG': '.DE', 'EAM': '.AS', 'TOR': '.TO', 'LSE': '.L', 'TSV': '.V', 'ASE': '.AT', 'TDG': '.TG', 'WSE': '.WA', 'OMK': '.CO', 'OSL': '.OL', 'FRA': '.F', 'ASX': '.AX' }

# Columnas que deben ser numéricas en el CSV final (usando NOMBRES FINALES)
NUMERIC_COLS = [ "Cantidad", "Precio", "Valor Local", "Valor", "Tipo de cambio", "Costes Transacción", "Total" ]

# --- Inicialización de Flask y Extensiones ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24) # Usar una clave más segura en producción
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

# Inicializar SQLAlchemy DESPUÉS de configurar la app
db = SQLAlchemy(app)

# Inicializar Flask-Login DESPUÉS de configurar la app
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Endpoint de la vista de login
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'

# --- Crear Carpetas ---
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# En app.py

# ... (Imports y Configuración de app, db, login_manager ANTES de esto) ...

# --- Modelos de Base de Datos ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Relación con items de watchlist, con borrado en cascada y carga dinámica
    watchlist_items = db.relationship('WatchlistItem', backref='owner', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class WatchlistItem(db.Model):
    # --- Campos Básicos ---
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    isin = db.Column(db.String(12), nullable=True, index=True)

    # --- Datos de Identificación/Mapeo (Editables en /manage_mapping) ---
    ticker = db.Column(db.String(20), nullable=False) # Obligatorio tener al menos el ticker base
    item_name = db.Column(db.String(150), nullable=True) # Nombre (puede venir de mapeo o manual)
    yahoo_suffix = db.Column(db.String(10), nullable=False, default='')
    google_ex = db.Column(db.String(10), nullable=True)

    # --- Estado (Gestionado por la App) ---
    is_in_portfolio = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_in_followup = db.Column(db.Boolean, nullable=False, default=True, index=True) # Renombrado de is_manual

    # --- NUEVOS CAMPOS MANUALES (Opcionales) ---
    # Fecha Resultados
    fecha_resultados = db.Column(db.Date, nullable=True)

    # Perfil empresa
    pais = db.Column(db.String(100), nullable=True)
    sector = db.Column(db.String(100), nullable=True)
    industria = db.Column(db.String(100), nullable=True)
    market_cap = db.Column(db.Float, nullable=True)  # Nuevo campo para Market Cap en millones

    # Gobierno
    ceo_salary = db.Column(db.String(10), nullable=True) # OK, NA, NoOK
    dilucion_shares = db.Column(db.Float, nullable=True) # %

    # Valuation
    ntm_ps = db.Column(db.Float, nullable=True)
    ntm_tev_ebitda = db.Column(db.Float, nullable=True)
    ntm_pe = db.Column(db.Float, nullable=True)
    ntm_div_yield = db.Column(db.Float, nullable=True) # %
    ltm_pbv = db.Column(db.Float, nullable=True)

    # Métricas
    revenue_cagr = db.Column(db.Float, nullable=True) # %
    ebitda_margins = db.Column(db.Float, nullable=True) # %
    eps_normalized = db.Column(db.Float, nullable=True) # Para cálculo EPS Yield
    fcf_margins = db.Column(db.Float, nullable=True) # %
    cfo = db.Column(db.Float, nullable=True) # Cash From Operations
    net_debt_ebitda = db.Column(db.Float, nullable=True)
    roe = db.Column(db.Float, nullable=True) # % Return on Equity

    # Estimates
    pe_objetivo = db.Column(db.Float, nullable=True)
    eps_5y = db.Column(db.Float, nullable=True) # EPS estimado a 5 años (para cálculo EPS Yield)
    price_5y = db.Column(db.Float, nullable=True) # Precio estimado a 5 años

    # Campos sin categoría asignada explícita
    riesgo = db.Column(db.Float, nullable=True) # Valor 0-10
    stake = db.Column(db.Float, nullable=True) # Desplegable 1-10 (0.5)
    movimiento = db.Column(db.String(10), nullable=True) # Buy, Hold, Sell
    comentario = db.Column(db.Text, nullable=True) # Texto largo

    # --- NUEVOS CAMPOS PARA CONTROL DE ACTUALIZACIÓN AUTOMÁTICA ---
    # Estas banderas controlan qué campos se actualizan automáticamente con datos de Yahoo
    auto_update_date = db.Column(db.Boolean, nullable=False, default=True)  # Fecha resultados
    auto_update_pais = db.Column(db.Boolean, nullable=False, default=True)  # País
    auto_update_sector = db.Column(db.Boolean, nullable=False, default=True)  # Sector
    auto_update_industria = db.Column(db.Boolean, nullable=False, default=True)  # Industria
    auto_update_market_cap = db.Column(db.Boolean, nullable=False, default=True)  # Market Cap
    auto_update_pe = db.Column(db.Boolean, nullable=False, default=True)  # P/E Ratio
    auto_update_div_yield = db.Column(db.Boolean, nullable=False, default=True)  # Dividend Yield
    auto_update_pbv = db.Column(db.Boolean, nullable=False, default=True)  # Price/Book Value
    auto_update_roe = db.Column(db.Boolean, nullable=False, default=True)  # Return on Equity

    # --- Timestamp de última actualización de datos Yahoo ---
    yahoo_last_updated = db.Column(db.DateTime, nullable=True)  # Última actualización de datos
    
    # --- NUEVOS CAMPOS PARA PRECIOS CACHEADOS ---
    cached_price = db.Column(db.Float, nullable=True)  # Último precio conocido
    cached_price_date = db.Column(db.DateTime, nullable=True)  # Fecha de ese precio

    # --- __repr__ para debugging ---
    def __repr__(self):
        status = f"Portfolio={'T' if self.is_in_portfolio else 'F'}, Followup={'T' if self.is_in_followup else 'F'}"
        return f'<WatchlistItem ISIN:{self.isin} Ticker:{self.ticker}{self.yahoo_suffix} User:{self.user_id} ({status})>'

# --- Modelos para Plan de Pensiones ---
class PensionPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    entity_name = db.Column(db.String(100), nullable=False)
    plan_name = db.Column(db.String(150), nullable=True)
    current_balance = db.Column(db.Float, nullable=False, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('pension_plans', lazy='dynamic'))

    def __repr__(self):
        return f'<PensionPlan {self.entity_name} - {self.plan_name} ({self.current_balance}€)>'

class PensionPlanHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('pension_history', lazy='dynamic'))

    def __repr__(self):
        return f'<PensionPlanHistory {self.date.strftime("%m/%Y")} - {self.total_amount}€>'

# --- Modelos para Cryptos ---
class CryptoExchange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    exchange_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario y transacciones
    user = db.relationship('User', backref=db.backref('crypto_exchanges', lazy='dynamic'))
    transactions = db.relationship('CryptoTransaction', backref='exchange', lazy='dynamic', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<CryptoExchange {self.exchange_name}>'

class CryptoTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('crypto_exchange.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'buy' o 'sell'
    crypto_name = db.Column(db.String(100), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False)  # BTC-EUR, ETH-EUR, etc.
    date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)
    fees = db.Column(db.Float, nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    price_updated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('crypto_transactions', lazy='dynamic'))
    
    def __repr__(self):
        return f'<CryptoTransaction {self.transaction_type} {self.crypto_name} ({self.quantity})>'

class CryptoHolding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('crypto_exchange.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    crypto_name = db.Column(db.String(100), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False)  # BTC-EUR, ETH-EUR, etc.
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    current_price = db.Column(db.Float, nullable=True)
    price_updated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('crypto_holdings', lazy='dynamic'))

    def __repr__(self):
        return f'<CryptoHolding {self.crypto_name} ({self.quantity})>'

class CryptoHistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total_value_eur = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('crypto_history', lazy='dynamic'))

    def __repr__(self):
        return f'<CryptoHistoryRecord {self.date.strftime("%m/%Y")} - {self.total_value_eur}€>'

# --- Modelos para Silver/Gold ---
class PreciousMetalTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    metal_type = db.Column(db.String(10), nullable=False)  # 'gold' o 'silver'
    transaction_type = db.Column(db.String(10), nullable=False)  # 'buy' o 'sell'
    date = db.Column(db.Date, nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)  # Precio por unidad
    quantity = db.Column(db.Float, nullable=False)  # Cantidad en gramos u onzas
    unit_type = db.Column(db.String(10), nullable=False)  # 'g' o 'oz'
    taxes_fees = db.Column(db.Float, nullable=True)  # Impuestos y comisiones
    description = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('metal_transactions', lazy='dynamic'))

    def __repr__(self):
        return f'<PreciousMetalTransaction {self.metal_type} {self.transaction_type} {self.quantity}{self.unit_type}>'

class PreciousMetalPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metal_type = db.Column(db.String(10), nullable=False)  # 'gold' o 'silver'
    price_eur_per_oz = db.Column(db.Float, nullable=False)  # Precio por onza en EUR
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PreciousMetalPrice {self.metal_type} {self.price_eur_per_oz}€/oz>'


# --- Formularios para Plan de Pensiones ---
class PensionPlanForm(FlaskForm):
    entity_name = StringField('Entidad', validators=[DataRequired()],
                          render_kw={"placeholder": "Ej: BBVA, ING..."})
    plan_name = StringField('Nombre del Plan',
                       render_kw={"placeholder": "Ej: Plan Individual, Plan Empresa..."})
    current_balance = StringField('Saldo Actual (€)', validators=[DataRequired()],
                              render_kw={"placeholder": "Ej: 15000.75"})
    submit = SubmitField('Guardar Plan')

class PensionHistoryForm(FlaskForm):
    month_year = StringField('Mes y Año', validators=[DataRequired()],
                          render_kw={"type": "month", "placeholder": "YYYY-MM"})
    submit = SubmitField('Guardar Estado Actual')

# --- Formularios para Cryptos ---
# --- Formularios para Crypto ---
class CryptoExchangeForm(FlaskForm):
    exchange_name = StringField('Nombre del Exchange', validators=[DataRequired()],
                             render_kw={"placeholder": "Ej: Binance, Coinbase..."})
    submit = SubmitField('Añadir Exchange')

class CryptoTransactionForm(FlaskForm):
    exchange_id = SelectField('Exchange', coerce=int, validators=[DataRequired()])
    transaction_type = SelectField('Tipo de Operación', choices=[('buy', 'Compra'), ('sell', 'Venta')],
                               validators=[DataRequired()])
    crypto_name = StringField('Nombre de la Criptomoneda', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: Bitcoin, Ethereum..."})
    ticker_symbol = StringField('Símbolo Ticker', validators=[DataRequired()],
                             render_kw={"placeholder": "Ej: BTC-EUR, ETH-EUR..."})
    date = StringField('Fecha', validators=[DataRequired()],
                     render_kw={"type": "date"})
    quantity = StringField('Cantidad', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 0.25"})
    price_per_unit = StringField('Precio por Unidad (€)', validators=[DataRequired()],
                              render_kw={"placeholder": "Ej: 32500"})
    fees = StringField('Comisiones (€)',
                    render_kw={"placeholder": "Ej: 1.25"})
    submit = SubmitField('Registrar Operación')

class CryptoHoldingForm(FlaskForm):
    exchange_id = SelectField('Exchange', coerce=int, validators=[DataRequired()])
    crypto_name = StringField('Nombre de la Criptomoneda', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: Bitcoin, Ethereum..."})
    ticker_symbol = StringField('Símbolo Ticker', validators=[DataRequired()],
                             render_kw={"placeholder": "Ej: BTC-EUR, ETH-EUR..."})
    quantity = StringField('Cantidad', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 0.25"})
    submit = SubmitField('Añadir Criptomoneda')

class CryptoHistoryForm(FlaskForm):
    month_year = StringField('Mes y Año', validators=[DataRequired()],
                          render_kw={"type": "month", "placeholder": "YYYY-MM"})
    submit = SubmitField('Guardar Estado Actual')

# --- Formularios para Silver/Gold ---
class PreciousMetalTransactionForm(FlaskForm):
    metal_type = SelectField('Tipo de Metal', choices=[('gold', 'Oro'), ('silver', 'Plata')],
                          validators=[DataRequired()])
    transaction_type = SelectField('Tipo de Operación', choices=[('buy', 'Compra'), ('sell', 'Venta')],
                                validators=[DataRequired()])
    date = StringField('Fecha', validators=[DataRequired()],
                     render_kw={"type": "date"})
    price_per_unit = StringField('Precio por Unidad (€)', validators=[DataRequired()],
                              render_kw={"placeholder": "Ej: 56.75"})
    quantity = StringField('Cantidad', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 10"})
    unit_type = SelectField('Unidad', choices=[('g', 'Gramos'), ('oz', 'Onzas Troy')],
                         validators=[DataRequired()])
    taxes_fees = StringField('Impuestos/Comisiones (€)',
                          render_kw={"placeholder": "Ej: 5.50"})
    description = StringField('Descripción',
                           render_kw={"placeholder": "Ej: Compra de monedas de plata"})
    submit = SubmitField('Registrar Operación')


# --- Models for Debt Management ---
class DebtCeiling(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    percentage = db.Column(db.Float, nullable=False, default=5.0)  # Default 5% of salary
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('debt_ceiling', uselist=False))
    
    def __repr__(self):
        return f'<DebtCeiling {self.percentage}%>'


class DebtInstallmentPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Debt description
    description = db.Column(db.String(200), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    
    # Payment plan
    start_date = db.Column(db.Date, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)  # Number of installments
    monthly_payment = db.Column(db.Float, nullable=False)    # Calculated field
    
    # Status tracking
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('debt_plans', lazy='dynamic'))
    
    def __repr__(self):
        return f'<DebtInstallmentPlan {self.description} - {self.total_amount}€>'
    
    @property
    def end_date(self):
        """Calculate the end date of the installment plan."""
        if self.start_date and self.duration_months:
            # Add months to start date
            month = self.start_date.month - 1 + self.duration_months
            year = self.start_date.year + month // 12
            month = month % 12 + 1
            return date(year, month, 1)
        return None
    
    @property
    def remaining_installments(self):
        """Calculate the number of remaining installments assuming payments on the 1st of each month."""
        if not self.is_active:
            return 0
        
        today = date.today()
    
        # Si estamos antes del inicio, todas las cuotas están pendientes
        if today < self.start_date:
            return self.duration_months
    
        # Calcular el número total de meses entre la fecha de inicio y hoy
        # Incluyendo el mes actual solo si hoy es día 1 o anterior
        months_since_start = (today.year - self.start_date.year) * 12 + (today.month - self.start_date.month)
    
        # Si ya pasó el día 1 del mes actual, ese pago ya está hecho
        if today.day > 1:
            months_since_start += 1
    
        # Calcular cuotas restantes
        remaining = self.duration_months - months_since_start
        return max(0, remaining) 
   
    @property
    def remaining_amount(self):
        """Calculate the remaining amount to be paid."""
        return self.monthly_payment * self.remaining_installments
    
    @property
    def progress_percentage(self):
        """Calculate the percentage of debt paid off."""
        if self.duration_months == 0:
            return 100
        
        completed = self.duration_months - self.remaining_installments
        return (completed / self.duration_months) * 100


class DebtHistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    debt_amount = db.Column(db.Float, nullable=False)
    ceiling_percentage = db.Column(db.Float, nullable=False)  # Store the ceiling % at the time of record
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship with user
    user = db.relationship('User', backref=db.backref('debt_history', lazy='dynamic'))
    
    def __repr__(self):
        return f'<DebtHistoryRecord {self.date.strftime("%m/%Y")} - {self.debt_amount}€>'


# --- Forms for Debt Management ---
class DebtCeilingForm(FlaskForm):
    percentage = StringField('Techo de Deuda (% del Salario Neto)', validators=[DataRequired()],
                          render_kw={"placeholder": "Ej: 5.0"})
    submit = SubmitField('Guardar Techo de Deuda')

class DebtInstallmentPlanForm(FlaskForm):
    description = StringField('Descripción de la Deuda', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: Préstamo coche, Tarjeta crédito..."})
    total_amount = StringField('Cantidad Total a Pagar (€)', validators=[DataRequired()],
                            render_kw={"placeholder": "Ej: 5000.00"})
    start_date = StringField('Fecha de Inicio (Mes/Año)', validators=[DataRequired()],
                          render_kw={"type": "month", "placeholder": "YYYY-MM"})
    duration_months = StringField('Duración (Meses)', validators=[DataRequired()],
                               render_kw={"placeholder": "Ej: 12", "type": "number", "min": "1"})
    submit = SubmitField('Añadir Plan de Pago')

class DebtHistoryForm(FlaskForm):
    month_year = StringField('Mes y Año', validators=[DataRequired()],
                          render_kw={"type": "month", "placeholder": "YYYY-MM"})
    debt_amount = StringField('Cantidad de Deuda Actual (€)', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: 500.00"})
    submit = SubmitField('Guardar Registro de Deuda')


# --- Modelos para Gastos ---
class ExpenseCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('expense_category.id', ondelete='SET NULL'), nullable=True)
    is_default = db.Column(db.Boolean, default=False)  # Para categorías predefinidas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('expense_categories', lazy='dynamic'))
    
    # Relación para subcategorías
    subcategories = db.relationship('ExpenseCategory', 
                                 backref=db.backref('parent', remote_side=[id]),
                                 cascade="all, delete-orphan")
    
    # Relación con gastos
    expenses = db.relationship('Expense', backref='category', lazy='dynamic', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    expense_type = db.Column(db.String(20), nullable=False)  # "fixed", "punctual"
    is_recurring = db.Column(db.Boolean, default=False)  # Para gastos periódicos/fijos
    recurrence_months = db.Column(db.Integer, nullable=True)  # Cada cuántos meses se repite (1=mensual, 12=anual)
    start_date = db.Column(db.Date, nullable=True)  # Para gastos recurrentes
    end_date = db.Column(db.Date, nullable=True)  # Fecha opcional de finalización
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('expenses', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Expense {self.description} ({self.amount}€)>'

# --- Formularios para la gestión de gastos ---
# --- Formularios para la gestión de gastos (MODIFICADO) ---
class ExpenseCategoryForm(FlaskForm):
    name = StringField('Nombre de la Categoría', validators=[DataRequired()],
                    render_kw={"placeholder": "Ej: Alquiler, Alimentación, Transporte..."})
    description = TextAreaField('Descripción (Opcional)',
                             render_kw={"placeholder": "Descripción opcional", "rows": 2})
    parent_id = SelectField('Categoría Padre (Opcional)', coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField('Guardar Categoría')

class ExpenseForm(FlaskForm):
    description = StringField('Descripción', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: Alquiler Mayo, Compra Supermercado..."})
    amount = StringField('Importe (€)', validators=[DataRequired()],
                       render_kw={"placeholder": "Ej: 500.50"})
    date = StringField('Fecha', validators=[DataRequired()],
                     render_kw={"type": "date"})
    category_id = SelectField('Categoría', coerce=int, validators=[Optional()])
    # Modificar las opciones para que sean solo Gasto Puntual y Gasto Recurrente
    expense_type = SelectField('Tipo de Gasto',
                            choices=[
                                ('punctual', 'Gasto Puntual'),
                                ('fixed', 'Gasto Recurrente')
                            ],
                            validators=[DataRequired()])
    # Se mantiene este campo, pero se controlará por JavaScript
    is_recurring = BooleanField('Es Recurrente')
    recurrence_months = SelectField('Recurrencia',
                                 choices=[
                                     (1, 'Mensual'),
                                     (2, 'Bimestral'),
                                     (3, 'Trimestral'),
                                     (6, 'Semestral'),
                                     (12, 'Anual')
                                 ], coerce=int, validators=[Optional()])
    # El campo start_date se mantiene, pero no se mostrará en el formulario
    start_date = StringField('Fecha Inicio (Para recurrentes)',
                          render_kw={"type": "date"}, validators=[Optional()])
    end_date = StringField('Fecha Fin (Opcional)',
                        render_kw={"type": "date"}, validators=[Optional()])
    submit = SubmitField('Registrar Gasto')



@app.route('/edit_expense/<int:expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    """Edita un gasto existente."""
    # Buscar el gasto por ID y verificar que pertenece al usuario
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    
    # Crear formulario y prellenarlo con los datos del gasto
    form = ExpenseForm()
    
    # Cargar categorías para el dropdown
    all_categories = ExpenseCategory.query.filter_by(user_id=current_user.id).all()
    
    # Crear lista de opciones con indentación para mostrar jerarquía
    category_choices = []
    for cat in all_categories:
        if cat.parent_id is None:
            category_choices.append((cat.id, cat.name))
            # Añadir subcategorías con indentación
            subcats = ExpenseCategory.query.filter_by(parent_id=cat.id).all()
            for subcat in subcats:
                category_choices.append((subcat.id, f"-- {subcat.name}"))
    
    form.category_id.choices = [(0, 'Sin categoría')] + category_choices
    
    if request.method == 'GET':
        # Precargar datos del gasto en el formulario
        form.description.data = expense.description
        form.amount.data = str(expense.amount)
        form.date.data = expense.date.strftime('%Y-%m-%d')
        form.category_id.data = expense.category_id if expense.category_id else 0
        form.expense_type.data = expense.expense_type
        form.is_recurring.data = expense.is_recurring
        
        if expense.is_recurring:
            form.recurrence_months.data = expense.recurrence_months if expense.recurrence_months else 1
            if expense.start_date:
                form.start_date.data = expense.start_date.strftime('%Y-%m-%d')
            if expense.end_date:
                form.end_date.data = expense.end_date.strftime('%Y-%m-%d')
    
    if form.validate_on_submit():
        try:
            # Convertir valores
            amount = float(form.amount.data.replace(',', '.'))
            date_obj = datetime.strptime(form.date.data, '%Y-%m-%d').date()
            
            # Determinar categoría
            category_id = form.category_id.data
            if category_id == 0:
                category_id = None  # Sin categoría
                
            # Verificar campos para gastos recurrentes
            is_recurring = form.is_recurring.data
            recurrence_months = None
            start_date = None
            end_date = None
            
            if is_recurring:
                recurrence_months = form.recurrence_months.data
                
                # CAMBIO: Para edición también usamos la fecha del gasto como inicio
                start_date = date_obj
                    
                if form.end_date.data:
                    end_date = datetime.strptime(form.end_date.data, '%Y-%m-%d').date()
            
            # Actualizar el gasto
            expense.description = form.description.data
            expense.amount = amount
            expense.date = date_obj
            expense.category_id = category_id
            expense.expense_type = form.expense_type.data
            expense.is_recurring = is_recurring
            expense.recurrence_months = recurrence_months
            expense.start_date = start_date
            expense.end_date = end_date
            expense.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Gasto actualizado correctamente.', 'success')
            return redirect(url_for('expenses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar gasto: {e}', 'danger')
    
    return render_template('edit_expense.html', form=form, expense=expense)


# --- Modelo para guardar la configuración del Resumen Financiero ---
class FinancialSummaryConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    include_income = db.Column(db.Boolean, default=True)
    include_expenses = db.Column(db.Boolean, default=True)
    include_debts = db.Column(db.Boolean, default=True)
    include_investments = db.Column(db.Boolean, default=True)
    include_crypto = db.Column(db.Boolean, default=True)
    include_metals = db.Column(db.Boolean, default=True)
    include_bank_accounts = db.Column(db.Boolean, default=True)
    include_pension_plans = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('fin_summary_config', uselist=False))

# --- Formulario para configurar el Resumen Financiero ---
class FinancialSummaryConfigForm(FlaskForm):
    include_income = BooleanField('Incluir Ingresos', default=True)
    include_expenses = BooleanField('Incluir Gastos', default=True)
    include_debts = BooleanField('Incluir Deudas', default=True)
    include_investments = BooleanField('Incluir Inversiones', default=True)
    include_crypto = BooleanField('Incluir Criptomonedas', default=True)
    include_metals = BooleanField('Incluir Metales Preciosos', default=True)
    include_bank_accounts = BooleanField('Incluir Cuentas Bancarias', default=True)
    include_pension_plans = BooleanField('Incluir Planes de Pensiones', default=True)
    submit = SubmitField('Guardar Configuración')


# Función correcta para calcular la fecha de fin de un plan

def calculate_end_date(start_date, duration_months):
    """
    Calcula la fecha de finalización correcta basada en la fecha de inicio y la duración.
    Esta fecha representa el último mes en que se realiza un pago.
    
    Args:
        start_date: date, fecha de inicio (siempre día 1)
        duration_months: int, número de meses de duración
    
    Returns:
        date: fecha de finalización (último mes de pago)
    """
    # Para 4 meses iniciando en abril (4/2025), el último pago debe ser en julio (7/2025)
    # Por tanto, mes final = mes inicial + duración - 1
    end_month = start_date.month + duration_months - 1
    end_year = start_date.year
    
    # Ajustar el año si el mes sobrepasa 12
    if end_month > 12:
        end_year += (end_month - 1) // 12
        end_month = ((end_month - 1) % 12) + 1
    
    # Crear fecha de finalización (siempre día 1)
    return date(end_year, end_month, 1)

def get_crypto_price(ticker_symbol):
    """
    Obtiene el precio actual de una criptomoneda usando yfinance.
    
    Args:
        ticker_symbol: Símbolo del ticker (ej: 'BTC-EUR', 'ETH-EUR')
    
    Returns:
        Precio actual o 0 si no se puede obtener
    """
    try:
        # Reutilizar función existente para precios
        return get_current_price(ticker_symbol, force_update=True)
    except Exception as e:
        print(f"Error obteniendo precio para {ticker_symbol}: {e}")
        return 0  # Devolver 0 en lugar de None

def get_precious_metal_price(metal_type):
    """
    Obtiene el precio actual del oro o la plata usando yfinance.
    
    Args:
        metal_type: 'gold' o 'silver'
    
    Returns:
        Precio actual por onza en EUR o 0 si no se puede obtener
    """
    # Mapeo de tipo de metal a símbolo de Yahoo Finance
    metal_symbols = {
        'gold': 'GC=F',   # Oro en USD por onza
        'silver': 'SI=F'  # Plata en USD por onza
    }
    
    symbol = metal_symbols.get(metal_type)
    if not symbol:
        return 0
    
    try:
        # Obtener precio en USD
        ticker_obj = yf.Ticker(symbol)
        hist = ticker_obj.history(period="2d")
        
        if not hist.empty:
            # Obtener último precio en USD
            price_usd = hist['Close'].iloc[-1]
            
            # Si el precio es nan, devolver 0
            if pd.isna(price_usd):
                print(f"  -> Precio nan para {symbol}, devolviendo 0")
                return 0
                
            # Convertir de USD a EUR
            usd_eur_rate = get_exchange_rate('USD', 'EUR')
            
            # Si no podemos obtener la tasa de cambio, usar el precio en USD como aproximación
            if usd_eur_rate is None:
                print(f"  -> No se pudo obtener tasa USD/EUR, usando precio USD: {price_usd}")
                return price_usd
                
            # Calcular precio en EUR
            price_eur = price_usd * usd_eur_rate
            print(f"  -> Precio {metal_type} obtenido: {price_usd} USD ({price_eur} EUR)")
            return price_eur
        else:
            print(f"  -> No historial reciente para {symbol}")
            return 0
    except Exception as e:
        print(f"  -> Error obteniendo precio para {metal_type} ({symbol}): {e}")
        return 0


def update_precious_metal_prices():
    """Actualiza los precios del oro y la plata en la base de datos."""
    try:
        # Actualizar precio del oro
        gold_price = get_precious_metal_price('gold')
        if gold_price:
            gold_record = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
            if gold_record:
                gold_record.price_eur_per_oz = gold_price
                gold_record.updated_at = datetime.utcnow()
            else:
                gold_record = PreciousMetalPrice(metal_type='gold', price_eur_per_oz=gold_price)
                db.session.add(gold_record)
        
        # Actualizar precio de la plata
        silver_price = get_precious_metal_price('silver')
        if silver_price:
            silver_record = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
            if silver_record:
                silver_record.price_eur_per_oz = silver_price
                silver_record.updated_at = datetime.utcnow()
            else:
                silver_record = PreciousMetalPrice(metal_type='silver', price_eur_per_oz=silver_price)
                db.session.add(silver_record)
        
        # Guardar cambios
        db.session.commit()
        return True, "Precios actualizados correctamente"
    except Exception as e:
        db.session.rollback()
        return False, f"Error al actualizar precios: {e}"


# Funciones para obtener y actualizar datos de Yahoo Finance

def get_yahoo_data_for_ticker(ticker_with_suffix, force_update=False):
    """
    Obtiene datos fundamentales y técnicos de Yahoo Finance para un ticker.
    
    Args:
        ticker_with_suffix: Ticker completo con sufijo Yahoo (ej: 'TEF.MC')
        force_update: Si es True, fuerza la actualización desde Yahoo ignorando cualquier caché
    """
    if not ticker_with_suffix:
        return None

    # Implementar un caché para datos fundamentales similar al de precios
    # Podríamos usar una variable global o una tabla en la BD
    global yahoo_data_cache  # Declarar si se usa como variable global

    # Si no existe la variable de caché, inicializarla
    if not 'yahoo_data_cache' in globals():
        yahoo_data_cache = {}

    now = time.time()
    
    # Comprobar si los datos están en caché y son recientes (24 horas)
    if not force_update and ticker_with_suffix in yahoo_data_cache:
        timestamp, data = yahoo_data_cache[ticker_with_suffix]
        # Para datos fundamentales, podemos usar un tiempo mayor (24h)
        if now - timestamp < 24 * 60 * 60:
            print(f"Usando datos fundamentales cacheados para {ticker_with_suffix}")
            return data

    try:
        # Inicializar diccionario de resultados
        result = {
            'market_cap': None,
            'pe_ratio': None,
            'div_yield': None,
            'pb_ratio': None,
            'roe': None,
            'earnings_date': None,
            'country': None,
            'sector': None,
            'industry': None,
            'timestamp': datetime.utcnow()
        }

        # Obtener datos básicos
        ticker_obj = yf.Ticker(ticker_with_suffix)

        # Obtener información básica
        info = ticker_obj.info

        # Market Cap (convertir a millones para mejor visualización)
        if 'marketCap' in info and info['marketCap']:
            result['market_cap'] = info['marketCap'] / 1000000

        # Forward P/E
        if 'forwardPE' in info and info['forwardPE']:
            result['pe_ratio'] = info['forwardPE']
        elif 'trailingPE' in info and info['trailingPE']:
            result['pe_ratio'] = info['trailingPE']

        # Price/Book
        if 'priceToBook' in info and info['priceToBook']:
            result['pb_ratio'] = info['priceToBook']

        # Dividend Yield (RESTAURADO: multiplicar por 100 para almacenar como porcentaje)
        if 'dividendYield' in info and info['dividendYield']:
             # Si yfinance devuelve 0.0168, almacenamos 1.68
            result['div_yield'] = info['dividendYield']  

        # Return on Equity (mantener como porcentaje)
        if 'returnOnEquity' in info and info['returnOnEquity']:
            result['roe'] = info['returnOnEquity'] * 100

        # País, Sector e Industria
        if 'country' in info and info['country']:
            result['country'] = info['country']

        if 'sector' in info and info['sector']:
            result['sector'] = info['sector']

        if 'industry' in info and info['industry']:
            result['industry'] = info['industry']

        # Earnings Date
        try:
            calendar = ticker_obj.calendar
            if calendar is not None and hasattr(calendar, 'iloc') and not calendar.empty:
                next_earnings_date = calendar.iloc[0, 0]
                if isinstance(next_earnings_date, pd.Timestamp):
                    result['earnings_date'] = next_earnings_date.date()
        except Exception as e_cal:
            print(f"Error obteniendo calendario para {ticker_with_suffix}: {e_cal}")

        # Guardar en caché
        yahoo_data_cache[ticker_with_suffix] = (now, result)
        
        return result

    except Exception as e:
        print(f"Error obteniendo datos Yahoo para {ticker_with_suffix}: {e}")
        return None



def update_watchlist_item_from_yahoo(item_id, force_update=False):
    """
    Actualiza los datos de Yahoo Finance para un ítem específico de la watchlist.
    
    Args:
        item_id: ID del item a actualizar
        force_update: Si es True, fuerza la actualización desde Yahoo ignorando el caché
    """
    try:
        # Obtener el item de la base de datos
        item = WatchlistItem.query.get(item_id)
        if not item:
            return False, "Item no encontrado"

        # Comprobar si tiene ticker y sufijo Yahoo
        ticker = item.ticker
        yahoo_suffix = item.yahoo_suffix or ''

        if not ticker:
            return False, "Item sin ticker definido"

        # Formar el ticker completo para Yahoo
        yahoo_ticker = f"{ticker}{yahoo_suffix}"

        # Obtener datos de Yahoo (FORZANDO ACTUALIZACIÓN SI SE SOLICITA)
        yahoo_data = get_yahoo_data_for_ticker(yahoo_ticker, force_update=force_update)

        if not yahoo_data:
            return False, f"No se pudieron obtener datos para {yahoo_ticker}"

        # NUEVO: Obtener y guardar el precio actual si se fuerza actualización
        if force_update:
            current_price = get_current_price(yahoo_ticker, force_update=True)
            if current_price is not None:
                item.cached_price = current_price
                item.cached_price_date = datetime.utcnow()
                print(f"Precio cacheado actualizado para {yahoo_ticker}: {current_price}")

        # Actualizar campos según las banderas de auto-actualización
        # País
        if item.auto_update_pais and yahoo_data.get('country'):
            item.pais = yahoo_data.get('country')

        # Sector
        if item.auto_update_sector and yahoo_data.get('sector'):
            item.sector = yahoo_data.get('sector')

        # Industria
        if item.auto_update_industria and yahoo_data.get('industry'):
            item.industria = yahoo_data.get('industry')

        # Market Cap
        if item.auto_update_market_cap and yahoo_data.get('market_cap'):
            item.market_cap = yahoo_data.get('market_cap')

        # P/E Ratio
        if item.auto_update_pe and yahoo_data.get('pe_ratio'):
            item.ntm_pe = yahoo_data.get('pe_ratio')

        # Dividend Yield
        if item.auto_update_div_yield and yahoo_data.get('div_yield'):
            item.ntm_div_yield = yahoo_data.get('div_yield')

        # Price/Book Value
        if item.auto_update_pbv and yahoo_data.get('pb_ratio'):
            item.ltm_pbv = yahoo_data.get('pb_ratio')

        # Return on Equity
        if item.auto_update_roe and yahoo_data.get('roe'):
            item.roe = yahoo_data.get('roe')

        # Actualizar timestamp de última actualización
        item.yahoo_last_updated = yahoo_data.get('timestamp')

        # Guardar cambios
        db.session.commit()

        return True, f"Datos de {yahoo_ticker} actualizados correctamente"

    except Exception as e:
        db.session.rollback()
        print(f"Error actualizando item {item_id} desde Yahoo: {e}")
        return False, f"Error: {str(e)}"


def create_default_expense_categories(user_id):
    """Crea categorías de gastos predeterminadas para un nuevo usuario."""
    default_categories = [
        {
            'name': 'Vivienda', 
            'description': 'Gastos relacionados con la vivienda',
            'subcategories': [
                'Alquiler', 
                'Hipoteca', 
                'Electricidad', 
                'Agua', 
                'Gas', 
                'Internet', 
                'Mantenimiento'
            ]
        },
        {
            'name': 'Alimentación', 
            'description': 'Gastos de alimentación',
            'subcategories': [
                'Supermercado', 
                'Restaurantes', 
                'Comida a domicilio'
            ]
        },
        {
            'name': 'Transporte', 
            'description': 'Gastos de transporte',
            'subcategories': [
                'Gasolina', 
                'Transporte público', 
                'Mantenimiento vehículo', 
                'Seguro vehículo', 
                'Impuestos vehículo'
            ]
        },
        {
            'name': 'Salud', 
            'description': 'Gastos médicos y de salud',
            'subcategories': [
                'Seguro médico', 
                'Medicamentos', 
                'Consultas médicas'
            ]
        },
        {
            'name': 'Ocio', 
            'description': 'Gastos de ocio y entretenimiento',
            'subcategories': [
                'Cine/Teatro', 
                'Suscripciones', 
                'Vacaciones', 
                'Hobbies'
            ]
        },
        {
            'name': 'Educación', 
            'description': 'Gastos de formación y educación',
            'subcategories': [
                'Cursos', 
                'Material de estudio', 
                'Libros'
            ]
        },
        {
            'name': 'Varios', 
            'description': 'Otros gastos no categorizados',
            'subcategories': []
        }
    ]
    
    try:
        for category in default_categories:
            # Crear categoría principal
            main_cat = ExpenseCategory(
                user_id=user_id,
                name=category['name'],
                description=category['description'],
                is_default=True
            )
            db.session.add(main_cat)
            db.session.flush()  # Para obtener el ID asignado
            
            # Crear subcategorías
            for subcat_name in category['subcategories']:
                subcategory = ExpenseCategory(
                    user_id=user_id,
                    name=subcat_name,
                    parent_id=main_cat.id,
                    is_default=True
                )
                db.session.add(subcategory)
        
        db.session.commit()
        print(f"Categorías predeterminadas creadas para el usuario {user_id}")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear categorías predeterminadas: {e}")
        return False



@app.route('/financial_summary', methods=['GET', 'POST'])
@login_required
def financial_summary():
    """Muestra un resumen financiero global con datos de todas las secciones."""
    # Obtener o crear configuración
    config = FinancialSummaryConfig.query.filter_by(user_id=current_user.id).first()
    if not config:
        config = FinancialSummaryConfig(user_id=current_user.id)
        db.session.add(config)
        db.session.commit()

    # Crear formulario de configuración
    config_form = FinancialSummaryConfigForm()

    # Precargar datos si es GET
    if request.method == 'GET':
        config_form.include_income.data = config.include_income
        config_form.include_expenses.data = config.include_expenses
        config_form.include_debts.data = config.include_debts
        config_form.include_investments.data = config.include_investments
        config_form.include_crypto.data = config.include_crypto
        config_form.include_metals.data = config.include_metals
        config_form.include_bank_accounts.data = config.include_bank_accounts
        config_form.include_pension_plans.data = config.include_pension_plans

    # Procesar formulario
    if config_form.validate_on_submit():
        try:
            config.include_income = config_form.include_income.data
            config.include_expenses = config_form.include_expenses.data
            config.include_debts = config_form.include_debts.data
            config.include_investments = config_form.include_investments.data
            config.include_crypto = config_form.include_crypto.data
            config.include_metals = config_form.include_metals.data
            config.include_bank_accounts = config_form.include_bank_accounts.data
            config.include_pension_plans = config_form.include_pension_plans.data

            db.session.commit()
            flash('Configuración del resumen guardada correctamente.', 'success')
            return redirect(url_for('financial_summary'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar configuración: {e}', 'danger')

    # Inicializar datos del resumen
    summary_data = {
        'income': {'available': False, 'data': {}},
        'variable_income': {'available': False, 'data': {}},  # Nueva sección para ingresos variables
        'expenses': {'available': False, 'data': {}},
        'debts': {'available': False, 'data': {}},
        'investments': {'available': False, 'data': {}},
        'crypto': {'available': False, 'data': {}},
        'metals': {'available': False, 'data': {}},
        'bank_accounts': {'available': False, 'data': {}},
        'pension_plans': {'available': False, 'data': {}},
        'net_worth': {'available': False, 'data': {}},
        'kpis': {'available': False, 'data': {}}  # Nueva sección para KPIs financieros
    }

    # Recopilar datos según la configuración
    try:
        # 1. Ingresos Fijos
        if config.include_income:
            income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
            if income_data:
                summary_data['income']['available'] = True
                summary_data['income']['data'] = {
                    'annual_net_salary': income_data.annual_net_salary,
                    'monthly_salary_12': income_data.annual_net_salary / 12 if income_data.annual_net_salary else 0,
                    'monthly_salary_14': income_data.annual_net_salary / 14 if income_data.annual_net_salary else 0,
                    'last_updated': income_data.last_updated
                }

                # Historial de salarios
                salary_history = SalaryHistory.query.filter_by(user_id=current_user.id).order_by(SalaryHistory.year.desc()).all()
                if salary_history:
                    summary_data['income']['data']['history'] = []
                    prev_salary = None

                    for entry in salary_history:
                        variation = None
                        if prev_salary and prev_salary > 0:
                            variation = ((entry.annual_net_salary - prev_salary) / prev_salary) * 100

                        summary_data['income']['data']['history'].append({
                            'year': entry.year,
                            'salary': entry.annual_net_salary,
                            'variation': variation
                        })

                        prev_salary = entry.annual_net_salary
        
        # 1.1 Ingresos Variables (NUEVO)
        if config.include_income:
            # Obtener ingresos variables para el período actual (últimos 3 meses)
            three_months_ago = date.today() - timedelta(days=90)
            
            # Ingresos variables puntuales
            punctual_incomes = VariableIncome.query.filter_by(
                user_id=current_user.id,
                income_type='punctual'
            ).filter(VariableIncome.date >= three_months_ago).all()
            
            # Ingresos fijos recurrentes (expandidos para incluir todos los pagos en el período)
            fixed_incomes = VariableIncome.query.filter_by(
                user_id=current_user.id,
                income_type='fixed',
                is_recurring=True
            ).all()
            
            # Procesar ingresos recurrentes para el período
            recurring_income_entries = []
            for income in fixed_incomes:
                # Determinar fecha de inicio y fin para el período a considerar
                start_date = max(income.start_date or income.date, three_months_ago)
                end_date = income.end_date or date.today()
                
                if end_date < three_months_ago:
                    continue  # Omitir ingresos que terminaron antes del período
                
                # Ajustar fin al período actual
                end_date = min(end_date, date.today())
                
                # Generar entradas para cada mes según recurrencia
                current_date = start_date
                recurrence = income.recurrence_months or 1
                
                while current_date <= end_date:
                    recurring_income_entries.append({
                        'date': current_date,
                        'amount': income.amount,
                        'description': income.description
                    })
                    
                    # Avanzar al siguiente período
                    month = current_date.month + recurrence
                    year = current_date.year + (month - 1) // 12
                    month = ((month - 1) % 12) + 1
                    current_date = date(year, month, 1)
            
            # Calcular totales
            total_punctual = sum(income.amount for income in punctual_incomes)
            total_recurring = sum(entry['amount'] for entry in recurring_income_entries)
            total_variable_income = total_punctual + total_recurring
            
            # Agregar a summary_data
            if punctual_incomes or recurring_income_entries:
                summary_data['variable_income']['available'] = True
                summary_data['variable_income']['data'] = {
                    'total_punctual': total_punctual,
                    'total_recurring': total_recurring,
                    'total': total_variable_income,
                    'monthly_avg': total_variable_income / 3  # Promedio mensual (3 meses)
                }

        # 2. Gastos
        if config.include_expenses:
            # Obtener gastos
            expenses = Expense.query.filter_by(user_id=current_user.id).all()

            if expenses:
                summary_data['expenses']['available'] = True

                # Gastos fijos mensuales
                fixed_expenses = [e for e in expenses if e.expense_type == 'fixed' and e.is_recurring]
                fixed_sum = sum(e.amount for e in fixed_expenses)

                # Gastos puntuales último mes
                one_month_ago = date.today() - timedelta(days=30)
                punctual_expenses = [e for e in expenses if e.expense_type == 'punctual' and e.date >= one_month_ago]
                punctual_sum = sum(e.amount for e in punctual_expenses)
                
                # Gastos totales últimos 3 meses (para cálculos comparativos)
                three_months_ago = date.today() - timedelta(days=90)
                expenses_last_3_months = []
                
                # 1. Añadir gastos puntuales de los últimos 3 meses
                punctual_3m = [e for e in expenses if e.expense_type == 'punctual' and e.date >= three_months_ago]
                expenses_last_3_months.extend([{'date': e.date, 'amount': e.amount} for e in punctual_3m])
                
                # 2. Añadir gastos recurrentes expandidos
                for expense in fixed_expenses:
                    start_date = max(expense.start_date or expense.date, three_months_ago)
                    end_date = expense.end_date or date.today()
                    
                    if end_date < three_months_ago:
                        continue  # Omitir gastos que terminaron antes del período
                    
                    # Ajustar fin al período actual
                    end_date = min(end_date, date.today())
                    
                    # Generar entradas para cada mes según recurrencia
                    current_date = start_date
                    recurrence = expense.recurrence_months or 1
                    
                    while current_date <= end_date:
                        expenses_last_3_months.append({
                            'date': current_date,
                            'amount': expense.amount
                        })
                        
                        # Avanzar al siguiente período
                        month = current_date.month + recurrence
                        year = current_date.year + (month - 1) // 12
                        month = ((month - 1) % 12) + 1
                        current_date = date(year, month, 1)
                
                total_expenses_3m = sum(entry['amount'] for entry in expenses_last_3_months)
                monthly_avg_expenses = total_expenses_3m / 3  # Promedio mensual

                # Análisis por categoría
                expenses_by_category = {}
                six_months_ago = date.today() - timedelta(days=180)
                recent_expenses = [e for e in expenses if e.date >= six_months_ago]

                for expense in recent_expenses:
                    category_name = "Sin categoría"
                    if expense.category_id:
                        category = ExpenseCategory.query.get(expense.category_id)
                        if category:
                            category_name = category.name

                    if category_name not in expenses_by_category:
                        expenses_by_category[category_name] = 0

                    expenses_by_category[category_name] += expense.amount

                # Ordenar categorías por gasto
                sorted_categories = sorted(
                    expenses_by_category.items(),
                    key=lambda x: x[1],
                    reverse=True
                )

                summary_data['expenses']['data'] = {
                    'fixed_monthly': fixed_sum,
                    'punctual_last_month': punctual_sum,
                    'monthly_avg_expenses': monthly_avg_expenses,
                    'by_category': sorted_categories
                }

        # 3. Deudas
        if config.include_debts:
            debt_plans = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()

            if debt_plans:
                summary_data['debts']['available'] = True

                # Total deuda pendiente
                total_debt = sum(plan.remaining_amount for plan in debt_plans)

                # Pago mensual actual
                today = date.today()
                current_month = date(today.year, today.month, 1)
                current_payment = sum(
                    plan.monthly_payment for plan in debt_plans
                    if plan.start_date <= current_month and
                    (plan.end_date is None or plan.end_date > current_month)
                )

                # Deudas individuales
                debt_list = []
                for plan in debt_plans:
                    debt_list.append({
                        'description': plan.description,
                        'total_amount': plan.total_amount,
                        'remaining': plan.remaining_amount,
                        'monthly_payment': plan.monthly_payment,
                        'progress_pct': plan.progress_percentage,
                        'remaining_months': plan.remaining_installments
                    })

                summary_data['debts']['data'] = {
                    'total_debt': total_debt,
                    'monthly_payment': current_payment,
                    'debt_list': debt_list
                }

        # 4. Cuentas Bancarias
        if config.include_bank_accounts:
            bank_accounts = BankAccount.query.filter_by(user_id=current_user.id).all()

            if bank_accounts:
                summary_data['bank_accounts']['available'] = True

                # Total en cuentas
                total_cash = sum(account.current_balance for account in bank_accounts)

                # Lista de cuentas
                account_list = []
                for account in bank_accounts:
                    account_list.append({
                        'bank_name': account.bank_name,
                        'account_name': account.account_name,
                        'balance': account.current_balance,
                        'last_updated': account.last_updated
                    })

                # Historial de efectivo
                cash_history = CashHistoryRecord.query.filter_by(user_id=current_user.id).order_by(CashHistoryRecord.date.desc()).all()
                history_data = []
                
                # Listas para el gráfico
                dates_list = []
                values_list = []

                if cash_history:
                    prev_amount = None
                    for record in cash_history:
                        variation = None
                        if prev_amount and prev_amount > 0:
                            variation = ((record.total_cash - prev_amount) / prev_amount) * 100

                        # Añadir a la lista de historial
                        history_data.append({
                            'date': record.date,
                            'amount': record.total_cash,
                            'variation': variation
                        })
                        
                        # Añadir a las listas para el gráfico
                        dates_list.append(record.date.strftime('%Y-%m-%d'))
                        values_list.append(record.total_cash)

                        prev_amount = record.total_cash

                summary_data['bank_accounts']['data'] = {
                    'total_cash': total_cash,
                    'accounts': account_list,
                    'history': history_data
                }
                
                # Añadir datos para el gráfico si tenemos historial
                if cash_history:
                    if 'charts' not in summary_data:
                        summary_data['charts'] = {'available': True, 'data': {}}
                    
                    summary_data['charts']['data']['cash_history'] = {
                        'dates': dates_list,
                        'values_list': values_list  # Usar values_list en lugar de values
                    }

        # 5. Planes de Pensiones
        if config.include_pension_plans:
            pension_plans = PensionPlan.query.filter_by(user_id=current_user.id).all()

            if pension_plans:
                summary_data['pension_plans']['available'] = True

                # Total en planes
                total_pension = sum(plan.current_balance for plan in pension_plans)

                # Lista de planes
                plan_list = []
                for plan in pension_plans:
                    plan_list.append({
                        'entity_name': plan.entity_name,
                        'plan_name': plan.plan_name,
                        'balance': plan.current_balance,
                        'last_updated': plan.last_updated
                    })

                # Historial de pensiones
                pension_history = PensionPlanHistory.query.filter_by(user_id=current_user.id).order_by(PensionPlanHistory.date.desc()).all()
                history_data = []

                if pension_history:
                    prev_amount = None
                    for record in pension_history:
                        variation = None
                        if prev_amount and prev_amount > 0:
                            variation = ((record.total_amount - prev_amount) / prev_amount) * 100

                        history_data.append({
                            'date': record.date,
                            'amount': record.total_amount,
                            'variation': variation
                        })

                        prev_amount = record.total_amount

                summary_data['pension_plans']['data'] = {
                    'total_pension': total_pension,
                    'plans': plan_list,
                    'history': history_data
                }
        
        # 6. Inversiones (Portfolio)
        if config.include_investments:
            # Intentar obtener datos del portfolio desde la base de datos
            portfolio_record = UserPortfolio.query.filter_by(user_id=current_user.id).first()
            
            if portfolio_record and portfolio_record.portfolio_data:
                summary_data['investments']['available'] = True
                
                # Convertir JSON a dict
                portfolio_data = json.loads(portfolio_record.portfolio_data)
                
                # Calcular valor total del portfolio
                total_market_value = 0
                total_cost_basis = 0
                
                for item in portfolio_data:
                    if 'market_value_eur' in item and item['market_value_eur'] is not None:
                        total_market_value += float(item['market_value_eur'])
                    
                    if 'cost_basis_eur_est' in item and item['cost_basis_eur_est'] is not None:
                        total_cost_basis += float(item['cost_basis_eur_est'])
                
                # Calcular ganancia/pérdida
                total_pl = total_market_value - total_cost_basis
                
                summary_data['investments']['data'] = {
                    'total_market_value': total_market_value,
                    'total_cost_basis': total_cost_basis,
                    'total_pl': total_pl,
                    'last_updated': portfolio_record.last_updated,
                    'top_positions': []
                }
                
                # Añadir top posiciones (las 5 mayores)
                sorted_items = sorted(
                    [item for item in portfolio_data if 'market_value_eur' in item and item['market_value_eur'] is not None], 
                    key=lambda x: float(x['market_value_eur']), 
                    reverse=True
                )
                
                for i, item in enumerate(sorted_items[:5]):
                    position = {
                        'name': item.get('item_name') or item.get('Producto', 'Desconocido'),
                        'ticker': item.get('ticker', ''),
                        'market_value': item.get('market_value_eur', 0),
                        'pl': item.get('pl_eur_est', 0)
                    }
                    summary_data['investments']['data']['top_positions'].append(position)
        
        # 7. Criptomonedas
        if config.include_crypto:
            # Obtener exchanges y transacciones
            crypto_exchanges = CryptoExchange.query.filter_by(user_id=current_user.id).all()
            crypto_transactions = CryptoTransaction.query.filter_by(user_id=current_user.id).all()
            
            if crypto_transactions:
                summary_data['crypto']['available'] = True
                
                # Calcular valor total actual
                total_investment = 0
                total_value = 0
                crypto_holdings = {}
                
                for transaction in crypto_transactions:
                    crypto_key = transaction.ticker_symbol
                    
                    if crypto_key not in crypto_holdings:
                        crypto_holdings[crypto_key] = {
                            'name': transaction.crypto_name,
                            'ticker': transaction.ticker_symbol,
                            'quantity': 0,
                            'investment': 0,
                            'current_price': transaction.current_price,
                            'current_value': 0
                        }
                    
                    # Actualizar cantidades
                    if transaction.transaction_type == 'buy':
                        crypto_holdings[crypto_key]['quantity'] += transaction.quantity
                        crypto_holdings[crypto_key]['investment'] += (transaction.quantity * transaction.price_per_unit)
                    else:  # 'sell'
                        crypto_holdings[crypto_key]['quantity'] -= transaction.quantity
                        crypto_holdings[crypto_key]['investment'] -= (transaction.quantity * transaction.price_per_unit)
                    
                    # Usar precio más actualizado
                    if transaction.current_price is not None and (
                        crypto_holdings[crypto_key]['current_price'] is None or 
                        (transaction.price_updated_at and 
                         (crypto_holdings[crypto_key].get('price_updated_at') is None or 
                          transaction.price_updated_at > crypto_holdings[crypto_key]['price_updated_at'])
                        )
                    ):
                        crypto_holdings[crypto_key]['current_price'] = transaction.current_price
                        crypto_holdings[crypto_key]['price_updated_at'] = transaction.price_updated_at
                
                # Calcular valores actuales y filtrar solo posiciones con cantidad > 0
                active_holdings = []
                for key, crypto in crypto_holdings.items():
                    if crypto['quantity'] > 0 and crypto['current_price'] is not None:
                        current_value = crypto['quantity'] * crypto['current_price']
                        crypto['current_value'] = current_value
                        
                        total_investment += crypto['investment']
                        total_value += current_value
                        
                        active_holdings.append(crypto)
                
                # Ordenar por valor actual
                active_holdings.sort(key=lambda x: x['current_value'], reverse=True)
                
                # Calcular ganancia/pérdida
                total_pl = total_value - total_investment
                
                summary_data['crypto']['data'] = {
                    'total_investment': total_investment,
                    'total_value': total_value,
                    'total_pl': total_pl,
                    'top_holdings': active_holdings[:5]  # Top 5 posiciones
                }
        
        # 8. Metales Preciosos
        if config.include_metals:
            metal_transactions = PreciousMetalTransaction.query.filter_by(user_id=current_user.id).all()
            
            if metal_transactions:
                summary_data['metals']['available'] = True
                
                # Obtener precios actuales
                gold_price = None
                silver_price = None
                
                gold_record = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
                if gold_record:
                    gold_price = gold_record.price_eur_per_oz
                
                silver_record = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
                if silver_record:
                    silver_price = silver_record.price_eur_per_oz
                
                # Calcular resumen por tipo de metal
                gold_summary = {
                    'total_g': 0,
                    'total_oz': 0,
                    'total_investment': 0,
                    'total_taxes_fees': 0,
                    'current_value': 0,
                    'profit_loss': 0
                }
                
                silver_summary = {
                    'total_g': 0,
                    'total_oz': 0,
                    'total_investment': 0,
                    'total_taxes_fees': 0,
                    'current_value': 0,
                    'profit_loss': 0
                }
                
                # Factor de conversión gramos a onzas troy
                g_to_oz = 0.0321507466
                
                for t in metal_transactions:
                    # Determinar el resumen a actualizar
                    summary = gold_summary if t.metal_type == 'gold' else silver_summary
                    
                    # Conversión a onzas troy si es necesario
                    quantity_oz = t.quantity if t.unit_type == 'oz' else t.quantity * g_to_oz
                    
                    # Actualizar totales en función del tipo de transacción
                    if t.transaction_type == 'buy':
                        summary['total_investment'] += (t.price_per_unit * quantity_oz)
                        if t.taxes_fees:
                            summary['total_taxes_fees'] += t.taxes_fees
                            
                        # Actualizar cantidad total
                        if t.unit_type == 'g':
                            summary['total_g'] += t.quantity
                        else:
                            summary['total_oz'] += t.quantity
                            summary['total_g'] += t.quantity / g_to_oz
                            
                    elif t.transaction_type == 'sell':
                        summary['total_investment'] -= (t.price_per_unit * quantity_oz)
                        if t.taxes_fees:
                            summary['total_taxes_fees'] += t.taxes_fees
                            
                        # Actualizar cantidad total
                        if t.unit_type == 'g':
                            summary['total_g'] -= t.quantity
                        else:
                            summary['total_oz'] -= t.quantity
                            summary['total_g'] -= t.quantity / g_to_oz
                
                # Calcular valores actuales y rentabilidad
                if gold_price:
                    gold_summary['total_oz'] = gold_summary['total_g'] * g_to_oz
                    gold_summary['current_value'] = gold_summary['total_oz'] * gold_price
                    gold_summary['profit_loss'] = gold_summary['current_value'] - gold_summary['total_investment'] - gold_summary['total_taxes_fees']
                    
                if silver_price:
                    silver_summary['total_oz'] = silver_summary['total_g'] * g_to_oz
                    silver_summary['current_value'] = silver_summary['total_oz'] * silver_price
                    silver_summary['profit_loss'] = silver_summary['current_value'] - silver_summary['total_investment'] - silver_summary['total_taxes_fees']
                
                # Calcular totales
                total_investment = gold_summary['total_investment'] + silver_summary['total_investment']
                total_value = gold_summary['current_value'] + silver_summary['current_value']
                total_pl = total_value - total_investment
                
                summary_data['metals']['data'] = {
                    'gold': gold_summary,
                    'silver': silver_summary,
                    'total_investment': total_investment,
                    'total_value': total_value,
                    'total_pl': total_pl
                }
        
        # 9. Cálculo del Patrimonio Neto
        assets = 0
        liabilities = 0
        
        # Activos
        if summary_data['bank_accounts']['available']:
            assets += summary_data['bank_accounts']['data']['total_cash']
        
        if summary_data['investments']['available']:
            assets += summary_data['investments']['data']['total_market_value']
        
        if summary_data['crypto']['available']:
            assets += summary_data['crypto']['data']['total_value']
        
        if summary_data['metals']['available']:
            assets += summary_data['metals']['data']['total_value']
        
        if summary_data['pension_plans']['available']:
            assets += summary_data['pension_plans']['data']['total_pension']
        
        # Pasivos
        if summary_data['debts']['available']:
            liabilities += summary_data['debts']['data']['total_debt']
        
        # Patrimonio Neto
        net_worth = assets - liabilities
        
        summary_data['net_worth']['available'] = True
        summary_data['net_worth']['data'] = {
            'total_assets': assets,
            'total_liabilities': liabilities,
            'net_worth': net_worth
        }
        
        # 10. Cálculo de KPIs financieros (NUEVO)
        # Calcular KPIs solo si tenemos datos suficientes
        total_monthly_income = 0
        if summary_data['income']['available']:
            total_monthly_income += summary_data['income']['data']['monthly_salary_12']
        
        if summary_data['variable_income']['available']:
            total_monthly_income += summary_data['variable_income']['data']['monthly_avg']
        
        total_monthly_expenses = 0
        if summary_data['expenses']['available']:
            total_monthly_expenses += summary_data['expenses']['data']['monthly_avg_expenses']
        
        if summary_data['debts']['available']:
            total_monthly_expenses += summary_data['debts']['data']['monthly_payment']
        
        # Calcular KPIs si tenemos ingresos y gastos
        if total_monthly_income > 0:
            summary_data['kpis']['available'] = True
            
            # Tasa de ahorro mensual
            monthly_savings = total_monthly_income - total_monthly_expenses
            savings_rate = (monthly_savings / total_monthly_income) * 100 if total_monthly_income > 0 else 0
            
            # Ratio deuda/ingresos
            debt_to_income = 0
            if summary_data['debts']['available'] and summary_data['debts']['data']['monthly_payment'] > 0:
                debt_to_income = (summary_data['debts']['data']['monthly_payment'] / total_monthly_income) * 100
            
            # Ratio deuda/patrimonio
            debt_to_assets = 0
            if assets > 0 and summary_data['debts']['available']:
                debt_to_assets = (summary_data['debts']['data']['total_debt'] / assets) * 100
            
            # Meses para independencia financiera (estimación)
            months_to_fi = 0
            if monthly_savings > 0:
                # Suponiendo que la independencia financiera se logra con 25 veces los gastos anuales
                annual_expenses = total_monthly_expenses * 12
                fi_target = annual_expenses * 25
                
                # Estimación sencilla sin considerar rendimientos de inversiones
                if net_worth < fi_target:
                    months_to_fi = (fi_target - net_worth) / monthly_savings
            
            summary_data['kpis']['data'] = {
                'monthly_income': total_monthly_income,
                'monthly_expenses': total_monthly_expenses,
                'monthly_savings': monthly_savings,
                'savings_rate': savings_rate,
                'debt_to_income': debt_to_income,
                'debt_to_assets': debt_to_assets,
                'months_to_fi': months_to_fi
            }
        
        # 11. Calcular datos históricos para gráficos
        # Obtener los registros históricos de patrimonio neto
        if summary_data['bank_accounts']['available'] and 'history' in summary_data['bank_accounts']['data']:
            cash_history = summary_data['bank_accounts']['data']['history']
            
            # Crear una estructura de fechas para el gráfico
            chart_dates = [record['date'].strftime('%Y-%m-%d') for record in cash_history[:12]]
            chart_values = [record['amount'] for record in cash_history[:12]]
            
            # Añadir datos de gráfico al summary_data
            if 'charts' not in summary_data:
                summary_data['charts'] = {'available': True, 'data': {}}
            
            # No es necesario esto si ya añadimos los datos del gráfico de cash_history antes
            # summary_data['charts']['data']['cash_history'] = {
            #    'dates': chart_dates,
            #    'values_list': chart_values
            # }
        
        # Calcular histórico de patrimonio neto si tenemos datos suficientes
        if summary_data['net_worth']['available']:
            # Intentar construir un gráfico de evolución del patrimonio
            # basado en registros históricos disponibles
            
            # Primero obtener todos los registros históricos
            all_history_records = []
            
            # Añadir histórico de efectivo
            if summary_data['bank_accounts']['available'] and 'history' in summary_data['bank_accounts']['data']:
                for record in summary_data['bank_accounts']['data']['history']:
                    all_history_records.append({
                        'date': record['date'],
                        'type': 'cash',
                        'amount': record['amount']
                    })
            
            # Añadir histórico de planes de pensiones
            if summary_data['pension_plans']['available'] and 'history' in summary_data['pension_plans']['data']:
                for record in summary_data['pension_plans']['data']['history']:
                    all_history_records.append({
                        'date': record['date'],
                        'type': 'pension',
                        'amount': record['amount']
                    })
            
            # Ordenar por fecha (más reciente primero)
            all_history_records.sort(key=lambda x: x['date'], reverse=True)
            
            # Si tenemos registros históricos, crear datos para gráfico
            if all_history_records:
                # Agrupar por fecha para crear un chart de patrimonio neto
                net_worth_by_date = {}
                
                for record in all_history_records:
                    date_str = record['date'].strftime('%Y-%m')
                    if date_str not in net_worth_by_date:
                        net_worth_by_date[date_str] = {
                            'cash': 0,
                            'pension': 0,
                            'date': record['date']
                        }
                    
                    net_worth_by_date[date_str][record['type']] = record['amount']
                
                # Convertir a lista y calcular patrimonio neto para cada fecha
                net_worth_chart = []
                
                for date_str, values in net_worth_by_date.items():
                    net_worth_chart.append({
                        'date': date_str,
                        'net_worth': values['cash'] + values['pension'],
                        'cash': values['cash'],
                        'pension': values['pension']
                    })
                
                # Ordenar por fecha (más antigua primero para el gráfico)
                net_worth_chart.sort(key=lambda x: x['date'])
                
                # Limitar a los últimos 12 meses
                net_worth_chart = net_worth_chart[-12:]
                
                # Añadir datos para el gráfico
                if 'charts' not in summary_data:
                    summary_data['charts'] = {'available': True, 'data': {}}
                
                # Crear listas para el gráfico
                dates_list = [entry['date'] for entry in net_worth_chart]
                values_list = [entry['net_worth'] for entry in net_worth_chart]
                
                summary_data['charts']['data']['net_worth_history'] = {
                    'dates': dates_list,
                    'values_list': values_list
                }
        
        # 12. Calcular flujo de caja (cash flow)
        if summary_data['income']['available'] or summary_data['variable_income']['available'] or summary_data['expenses']['available']:
            total_income = 0
            if summary_data['income']['available']:
                total_income += summary_data['income']['data']['monthly_salary_12']
            
            if summary_data['variable_income']['available']:
                total_income += summary_data['variable_income']['data']['monthly_avg']
            
            total_expenses = 0
            if summary_data['expenses']['available']:
                total_expenses += summary_data['expenses']['data']['monthly_avg_expenses']
            
            cash_flow = total_income - total_expenses
            
            # Añadir a los datos del resumen
            if 'cash_flow' not in summary_data:
                summary_data['cash_flow'] = {'available': True, 'data': {}}
            
            summary_data['cash_flow']['data'] = {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'net_cash_flow': cash_flow
            }
    
    except Exception as e:
        print(f"Error calculando resumen financiero: {e}")
        flash(f"Se produjo un error al calcular algunos datos del resumen: {e}", "warning")
        import traceback
        traceback.print_exc()
    
    return render_template('financial_summary.html',
                          config_form=config_form,
                          summary=summary_data,
                          config=config)


@app.route('/export_financial_summary', methods=['GET'])
@login_required
def export_financial_summary():
    """Exporta el resumen financiero a un archivo CSV o XLSX."""
    try:
        # Obtener el formato solicitado (por defecto CSV)
        export_format = request.args.get('format', 'csv').lower()
        if export_format not in ['csv', 'xlsx']:
            export_format = 'csv'  # Formato por defecto si no es válido
        
        # Obtener configuración
        config = FinancialSummaryConfig.query.filter_by(user_id=current_user.id).first()
        if not config:
            flash("No se encontró configuración para el resumen financiero.", "warning")
            return redirect(url_for('financial_summary'))
        
        # Crear estructura para los datos a exportar
        export_data = []
        
        # 1. Información general
        export_data.append(["RESUMEN FINANCIERO", "", ""])
        export_data.append([f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", "", ""])
        export_data.append(["", "", ""])
        
        # 2. Patrimonio Neto
        export_data.append(["PATRIMONIO NETO", "", ""])
        
        # Calcular las mismas cifras que en financial_summary
        assets = 0
        liabilities = 0
        
        # Activos
        if config.include_bank_accounts:
            bank_accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
            cash_total = sum(account.current_balance for account in bank_accounts) if bank_accounts else 0
            assets += cash_total
            export_data.append(["Efectivo en cuentas", f"{cash_total:.2f} €", ""])
        
        if config.include_investments:
            portfolio_record = UserPortfolio.query.filter_by(user_id=current_user.id).first()
            if portfolio_record and portfolio_record.portfolio_data:
                portfolio_data = json.loads(portfolio_record.portfolio_data)
                total_market_value = sum(float(item.get('market_value_eur', 0)) for item in portfolio_data if 'market_value_eur' in item and item['market_value_eur'] is not None)
                assets += total_market_value
                export_data.append(["Inversiones", f"{total_market_value:.2f} €", ""])
                
                # Añadir detalle de las top inversiones
                sorted_items = sorted(
                    [item for item in portfolio_data if 'market_value_eur' in item and item['market_value_eur'] is not None], 
                    key=lambda x: float(x['market_value_eur']), 
                    reverse=True
                )
                
                for i, item in enumerate(sorted_items[:5]):
                    name = item.get('item_name') or item.get('Producto', 'Desconocido')
                    value = item.get('market_value_eur', 0)
                    export_data.append([f"  - {name}", f"{value:.2f} €", ""])
        
        if config.include_crypto:
            crypto_transactions = CryptoTransaction.query.filter_by(user_id=current_user.id).all()
            if crypto_transactions:
                crypto_holdings = {}
                for transaction in crypto_transactions:
                    crypto_key = transaction.ticker_symbol
                    if crypto_key not in crypto_holdings:
                        crypto_holdings[crypto_key] = {
                            'name': transaction.crypto_name,
                            'quantity': 0,
                            'current_price': transaction.current_price
                        }
                    
                    if transaction.transaction_type == 'buy':
                        crypto_holdings[crypto_key]['quantity'] += transaction.quantity
                    else:
                        crypto_holdings[crypto_key]['quantity'] -= transaction.quantity
                    
                    if transaction.current_price is not None:
                        crypto_holdings[crypto_key]['current_price'] = transaction.current_price
                
                crypto_value = sum(crypto['quantity'] * crypto['current_price'] for crypto in crypto_holdings.values() 
                                 if crypto['quantity'] > 0 and crypto['current_price'] is not None)
                assets += crypto_value
                export_data.append(["Criptomonedas", f"{crypto_value:.2f} €", ""])
                
                # Añadir detalle de criptomonedas
                active_holdings = []
                for key, crypto in crypto_holdings.items():
                    if crypto['quantity'] > 0 and crypto['current_price'] is not None:
                        current_value = crypto['quantity'] * crypto['current_price']
                        crypto['current_value'] = current_value
                        active_holdings.append(crypto)
                
                # Ordenar por valor
                active_holdings.sort(key=lambda x: x['current_value'], reverse=True)
                
                for crypto in active_holdings[:5]:
                    export_data.append([f"  - {crypto['name']}", f"{crypto['current_value']:.2f} €", f"{crypto['quantity']:.6f} {crypto.get('ticker', '')}"])
        
        if config.include_metals:
            gold_record = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
            silver_record = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
            gold_price = gold_record.price_eur_per_oz if gold_record else 0
            silver_price = silver_record.price_eur_per_oz if silver_record else 0
            
            metal_transactions = PreciousMetalTransaction.query.filter_by(user_id=current_user.id).all()
            if metal_transactions:
                g_to_oz = 0.0321507466
                gold_oz = 0
                silver_oz = 0
                
                for transaction in metal_transactions:
                    quantity_oz = transaction.quantity if transaction.unit_type == 'oz' else transaction.quantity * g_to_oz
                    
                    if transaction.metal_type == 'gold':
                        if transaction.transaction_type == 'buy':
                            gold_oz += quantity_oz
                        else:
                            gold_oz -= quantity_oz
                    else:
                        if transaction.transaction_type == 'buy':
                            silver_oz += quantity_oz
                        else:
                            silver_oz -= quantity_oz
                
                gold_value = gold_oz * gold_price
                silver_value = silver_oz * silver_price
                metals_value = gold_value + silver_value
                assets += metals_value
                export_data.append(["Metales preciosos", f"{metals_value:.2f} €", ""])
                export_data.append(["  - Oro", f"{gold_value:.2f} €", f"{gold_oz:.2f} oz"])
                export_data.append(["  - Plata", f"{silver_value:.2f} €", f"{silver_oz:.2f} oz"])
        
        if config.include_pension_plans:
            pension_plans = PensionPlan.query.filter_by(user_id=current_user.id).all()
            pension_total = sum(plan.current_balance for plan in pension_plans) if pension_plans else 0
            assets += pension_total
            export_data.append(["Planes de pensiones", f"{pension_total:.2f} €", ""])
            
            # Añadir detalle de planes de pensiones
            if pension_plans:
                for plan in pension_plans:
                    export_data.append([f"  - {plan.entity_name} ({plan.plan_name})", f"{plan.current_balance:.2f} €", ""])
        
        export_data.append(["Total Activos", f"{assets:.2f} €", ""])
        export_data.append(["", "", ""])
        
        # Pasivos
        if config.include_debts:
            debt_plans = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()
            debt_total = sum(plan.remaining_amount for plan in debt_plans) if debt_plans else 0
            liabilities += debt_total
            export_data.append(["Total Deudas", f"{debt_total:.2f} €", ""])
            
            # Añadir detalle de deudas
            if debt_plans:
                for plan in debt_plans:
                    export_data.append([f"  - {plan.description}", f"{plan.remaining_amount:.2f} €", f"{plan.progress_percentage:.1f}% completado"])
        
        export_data.append(["Total Pasivos", f"{liabilities:.2f} €", ""])
        export_data.append(["", "", ""])
        
        # Patrimonio Neto
        net_worth = assets - liabilities
        export_data.append(["PATRIMONIO NETO", f"{net_worth:.2f} €", ""])
        export_data.append(["", "", ""])
        
        # 3. KPIs Financieros (NUEVO)
        # Calcular KPIs
        total_monthly_income = 0
        income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
        if income_data and income_data.annual_net_salary:
            monthly_salary = income_data.annual_net_salary / 12
            total_monthly_income += monthly_salary
        
        # Obtener ingresos variables promedio (últimos 3 meses)
        three_months_ago = date.today() - timedelta(days=90)
        variable_incomes = VariableIncome.query.filter_by(user_id=current_user.id).filter(VariableIncome.date >= three_months_ago).all()
        variable_income_total = sum(income.amount for income in variable_incomes)
        monthly_variable_income = variable_income_total / 3 if variable_incomes else 0
        total_monthly_income += monthly_variable_income
        
        # Calcular gastos mensuales (fijos + promedio variables)
        total_monthly_expenses = 0
        fixed_expenses = Expense.query.filter_by(user_id=current_user.id, expense_type='fixed', is_recurring=True).all()
        fixed_expenses_sum = sum(expense.amount for expense in fixed_expenses)
        
        # Gastos variables (promedio últimos 3 meses)
        variable_expenses = Expense.query.filter_by(user_id=current_user.id, expense_type='punctual').filter(Expense.date >= three_months_ago).all()
        variable_expenses_sum = sum(expense.amount for expense in variable_expenses)
        monthly_variable_expenses = variable_expenses_sum / 3 if variable_expenses else 0
        
        # Pagos mensuales de deuda
        monthly_debt_payment = 0
        if debt_plans:
            today = date.today()
            current_month = date(today.year, today.month, 1)
            monthly_debt_payment = sum(
                plan.monthly_payment for plan in debt_plans
                if plan.start_date <= current_month and
                (plan.end_date is None or plan.end_date > current_month)
            )
        
        total_monthly_expenses = fixed_expenses_sum + monthly_variable_expenses + monthly_debt_payment
        
        # Calcular KPIs
        monthly_savings = total_monthly_income - total_monthly_expenses
        savings_rate = (monthly_savings / total_monthly_income * 100) if total_monthly_income > 0 else 0
        debt_to_income_ratio = (monthly_debt_payment / total_monthly_income * 100) if total_monthly_income > 0 else 0
        debt_to_assets_ratio = (liabilities / assets * 100) if assets > 0 else 0
        
        # Añadir KPIs al reporte
        export_data.append(["INDICADORES FINANCIEROS", "", ""])
        export_data.append(["Ingresos mensuales", f"{total_monthly_income:.2f} €", ""])
        export_data.append(["  - Salario", f"{monthly_salary:.2f} €", ""])
        export_data.append(["  - Ingresos variables", f"{monthly_variable_income:.2f} €", ""])
        export_data.append(["Gastos mensuales", f"{total_monthly_expenses:.2f} €", ""])
        export_data.append(["  - Gastos fijos", f"{fixed_expenses_sum:.2f} €", ""])
        export_data.append(["  - Gastos variables", f"{monthly_variable_expenses:.2f} €", ""])
        export_data.append(["  - Pago de deudas", f"{monthly_debt_payment:.2f} €", ""])
        export_data.append(["Ahorro mensual", f"{monthly_savings:.2f} €", ""])
        export_data.append(["Tasa de ahorro", f"{savings_rate:.1f}%", ""])
        export_data.append(["Ratio deuda/ingresos", f"{debt_to_income_ratio:.1f}%", ""])
        export_data.append(["Ratio deuda/activos", f"{debt_to_assets_ratio:.1f}%", ""])
        export_data.append(["", "", ""])
        
        # 4. Ingresos y Gastos detallados
        if config.include_income:
            export_data.append(["INGRESOS DETALLADOS", "", ""])
            
            # Salario
            if income_data:
                export_data.append(["Salario Anual Neto", f"{income_data.annual_net_salary:.2f} €", ""])
                export_data.append(["Salario Mensual (12 pagas)", f"{income_data.annual_net_salary / 12:.2f} €", ""])
                export_data.append(["Salario Mensual (14 pagas)", f"{income_data.annual_net_salary / 14:.2f} €", ""])
                
                # Historial de salarios
                salary_history = SalaryHistory.query.filter_by(user_id=current_user.id).order_by(SalaryHistory.year.desc()).all()
                if salary_history:
                    export_data.append(["", "", ""])
                    export_data.append(["Evolución Salarial", "", ""])
                    
                    prev_salary = None
                    for entry in salary_history:
                        variation = None
                        if prev_salary and prev_salary > 0:
                            variation = ((entry.annual_net_salary - prev_salary) / prev_salary) * 100
                            variation_str = f"{variation:.1f}%"
                        else:
                            variation_str = ""
                        
                        export_data.append([str(entry.year), f"{entry.annual_net_salary:.2f} €", variation_str])
                        prev_salary = entry.annual_net_salary
            
            # Ingresos variables
            if variable_incomes:
                export_data.append(["", "", ""])
                export_data.append(["Ingresos Variables (últimos 3 meses)", "", ""])
                export_data.append(["Fecha", "Descripción", "Importe"])
                
                # Ordenar por fecha descendente
                variable_incomes.sort(key=lambda x: x.date, reverse=True)
                
                for income in variable_incomes:
                    category_name = "Sin categoría"
                    if income.category_id:
                        category = VariableIncomeCategory.query.get(income.category_id)
                        if category:
                            category_name = category.name
                    
                    export_data.append([
                        income.date.strftime("%d/%m/%Y"),
                        f"{income.description} ({category_name})",
                        f"{income.amount:.2f} €"
                    ])
                    
                export_data.append(["Total", "", f"{variable_income_total:.2f} €"])
                export_data.append(["Promedio Mensual", "", f"{monthly_variable_income:.2f} €"])
            
            export_data.append(["", "", ""])
        
        if config.include_expenses:
            export_data.append(["GASTOS DETALLADOS", "", ""])
            
            # Gastos por categoría
            expenses_by_category = {}
            six_months_ago = date.today() - timedelta(days=180)
            recent_expenses = Expense.query.filter_by(user_id=current_user.id).filter(Expense.date >= six_months_ago).all()
            
            for expense in recent_expenses:
                category_name = "Sin categoría"
                if expense.category_id:
                    category = ExpenseCategory.query.get(expense.category_id)
                    if category:
                        category_name = category.name
                
                if category_name not in expenses_by_category:
                    expenses_by_category[category_name] = 0
                
                expenses_by_category[category_name] += expense.amount
            
            # Ordenar categorías por gasto (mayor a menor)
            sorted_categories = sorted(
                expenses_by_category.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            export_data.append(["Gastos por Categoría (últimos 6 meses)", "", ""])
            total_expenses_6m = sum(amount for _, amount in sorted_categories)
            
            for category, amount in sorted_categories:
                percentage = (amount / total_expenses_6m * 100) if total_expenses_6m > 0 else 0
                export_data.append([category, f"{amount:.2f} €", f"{percentage:.1f}%"])
            
            export_data.append(["Total", f"{total_expenses_6m:.2f} €", "100%"])
            export_data.append(["Promedio Mensual", f"{total_expenses_6m / 6:.2f} €", ""])
            export_data.append(["", "", ""])
        
        # Preparar respuesta según formato solicitado
        today_str = datetime.now().strftime('%Y%m%d')
        
        if export_format == 'csv':
            # Crear buffer para el CSV
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')
            
            # Escribir datos
            for row in export_data:
                writer.writerow(row)
            
            # Preparar respuesta
            output.seek(0)
            filename = f"resumen_financiero_{today_str}.csv"
            
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
        
        elif export_format == 'xlsx':
            # Usar pandas para crear un Excel
            import pandas as pd
            from io import BytesIO
            
            # Crear un DataFrame con los datos
            df = pd.DataFrame(export_data)
            
            # Crear un BytesIO para guardar el Excel
            output = BytesIO()
            
            # Crear un writer de Excel
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Escribir el DataFrame sin encabezados
                df.to_excel(writer, sheet_name='Resumen Financiero', header=False, index=False)
                
                # Obtener el objeto workbook y la hoja
                workbook = writer.book
                worksheet = writer.sheets['Resumen Financiero']
                
                # Definir formato para encabezados
                header_format = workbook.add_format({
                    'bold': True,
                    'font_size': 12,
                    'bg_color': '#4F81BD',
                    'font_color': 'white'
                })
                
                # Definir formato para subtítulos
                subtitle_format = workbook.add_format({
                    'bold': True,
                    'font_size': 11,
                    'bg_color': '#DCE6F1'
                })
                
                # Aplicar formato a encabezados y celdas específicas
                for i, row_data in enumerate(export_data):
                    if row_data[0].strip() and row_data[0].isupper() and not row_data[0].startswith('  -'):
                        # Es un encabezado
                        worksheet.set_row(i, None, header_format)
                    elif row_data[0].strip() and not row_data[0].startswith('  -'):
                        # Es un subtítulo
                        worksheet.set_row(i, None, subtitle_format)
                
                # Ajustar anchos de columna
                worksheet.set_column('A:A', 40)
                worksheet.set_column('B:B', 20)
                worksheet.set_column('C:C', 20)
            
            # Preparar respuesta
            output.seek(0)
            filename = f"resumen_financiero_{today_str}.xlsx"
            
            return Response(
                output.getvalue(),
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error al exportar resumen financiero: {e}", "danger")
        return redirect(url_for('financial_summary'))


@app.route('/generate_financial_report', methods=['GET'])
@login_required
def generate_financial_report():
    """
    Genera un informe financiero detallado con recomendaciones 
    personalizadas basadas en los datos del usuario.
    """
    try:
        # Obtener configuración
        config = FinancialSummaryConfig.query.filter_by(user_id=current_user.id).first()
        if not config:
            flash("No se encontró configuración para el resumen financiero.", "warning")
            return redirect(url_for('financial_summary'))

        # Recopilar todos los datos necesarios (similar a financial_summary)
        report_data = {
            'general': {
                'date': datetime.now().strftime('%d/%m/%Y'),
                'user': current_user.username
            },
            'income': {},
            'expenses': {},
            'assets': {},
            'liabilities': {},
            'metrics': {},
            'recommendations': []
        }

        # --- INGRESOS ---
        total_monthly_income = 0
        
        # Salario fijo
        income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
        if income_data and income_data.annual_net_salary:
            monthly_salary = income_data.annual_net_salary / 12
            total_monthly_income += monthly_salary
            report_data['income']['salary'] = {
                'annual': income_data.annual_net_salary,
                'monthly': monthly_salary
            }
            
            # Evaluar tendencia salarial
            salary_history = SalaryHistory.query.filter_by(user_id=current_user.id).order_by(SalaryHistory.year.desc()).all()
            if len(salary_history) >= 2:
                # Calcular crecimiento promedio anual
                salary_growth = []
                for i in range(len(salary_history) - 1):
                    current = salary_history[i].annual_net_salary
                    previous = salary_history[i + 1].annual_net_salary
                    if previous > 0:
                        growth = ((current - previous) / previous) * 100
                        salary_growth.append(growth)
                
                if salary_growth:
                    avg_growth = sum(salary_growth) / len(salary_growth)
                    report_data['income']['salary_trend'] = {
                        'avg_growth': avg_growth,
                        'history': [(h.year, h.annual_net_salary) for h in salary_history]
                    }
        
        # Ingresos variables
        three_months_ago = date.today() - timedelta(days=90)
        variable_incomes = VariableIncome.query.filter_by(user_id=current_user.id).filter(VariableIncome.date >= three_months_ago).all()
        
        if variable_incomes:
            variable_income_total = sum(income.amount for income in variable_incomes)
            monthly_variable_income = variable_income_total / 3
            total_monthly_income += monthly_variable_income
            
            # Categorizar ingresos variables
            income_by_category = {}
            for income in variable_incomes:
                category_name = "Sin categoría"
                if income.category_id:
                    category = VariableIncomeCategory.query.get(income.category_id)
                    if category:
                        category_name = category.name
                
                if category_name not in income_by_category:
                    income_by_category[category_name] = 0
                
                income_by_category[category_name] += income.amount
            
            report_data['income']['variable'] = {
                'monthly_avg': monthly_variable_income,
                'total_3m': variable_income_total,
                'by_category': income_by_category
            }
        
        report_data['income']['total_monthly'] = total_monthly_income

        # --- GASTOS ---
        total_monthly_expenses = 0
        
        # Gastos fijos
        fixed_expenses = Expense.query.filter_by(user_id=current_user.id, expense_type='fixed', is_recurring=True).all()
        fixed_expenses_sum = sum(expense.amount for expense in fixed_expenses)
        total_monthly_expenses += fixed_expenses_sum
        
        # Gastos variables (promedio últimos 3 meses)
        variable_expenses = Expense.query.filter_by(user_id=current_user.id, expense_type='punctual').filter(Expense.date >= three_months_ago).all()
        variable_expenses_sum = sum(expense.amount for expense in variable_expenses)
        monthly_variable_expenses = variable_expenses_sum / 3 if variable_expenses else 0
        total_monthly_expenses += monthly_variable_expenses
        
        # Gastos por categoría (últimos 6 meses)
        six_months_ago = date.today() - timedelta(days=180)
        recent_expenses = Expense.query.filter_by(user_id=current_user.id).filter(Expense.date >= six_months_ago).all()
        
        expenses_by_category = {}
        for expense in recent_expenses:
            category_name = "Sin categoría"
            if expense.category_id:
                category = ExpenseCategory.query.get(expense.category_id)
                if category:
                    category_name = category.name
            
            if category_name not in expenses_by_category:
                expenses_by_category[category_name] = 0
            
            expenses_by_category[category_name] += expense.amount
        
        # Ordenar categorías por gasto (mayor a menor)
        sorted_categories = sorted(
            expenses_by_category.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        report_data['expenses'] = {
            'fixed_monthly': fixed_expenses_sum,
            'variable_monthly_avg': monthly_variable_expenses,
            'total_monthly': total_monthly_expenses,
            'by_category': dict(sorted_categories),
            'total_6m': sum(amount for _, amount in sorted_categories)
        }

        # --- ACTIVOS ---
        total_assets = 0
        assets_composition = {}
        
        # Efectivo
        bank_accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
        if bank_accounts:
            cash_total = sum(account.current_balance for account in bank_accounts)
            total_assets += cash_total
            assets_composition['Efectivo'] = cash_total
        
        # Inversiones
        portfolio_record = UserPortfolio.query.filter_by(user_id=current_user.id).first()
        if portfolio_record and portfolio_record.portfolio_data:
            portfolio_data = json.loads(portfolio_record.portfolio_data)
            total_market_value = sum(float(item.get('market_value_eur', 0)) for item in portfolio_data if 'market_value_eur' in item and item['market_value_eur'] is not None)
            total_assets += total_market_value
            assets_composition['Inversiones'] = total_market_value
        
        # Criptomonedas
        crypto_transactions = CryptoTransaction.query.filter_by(user_id=current_user.id).all()
        if crypto_transactions:
            crypto_holdings = {}
            for transaction in crypto_transactions:
                crypto_key = transaction.ticker_symbol
                if crypto_key not in crypto_holdings:
                    crypto_holdings[crypto_key] = {
                        'quantity': 0,
                        'current_price': transaction.current_price
                    }
                
                if transaction.transaction_type == 'buy':
                    crypto_holdings[crypto_key]['quantity'] += transaction.quantity
                else:
                    crypto_holdings[crypto_key]['quantity'] -= transaction.quantity
                
                if transaction.current_price is not None:
                    crypto_holdings[crypto_key]['current_price'] = transaction.current_price
            
            crypto_value = sum(crypto['quantity'] * crypto['current_price'] for crypto in crypto_holdings.values() 
                             if crypto['quantity'] > 0 and crypto['current_price'] is not None)
            total_assets += crypto_value
            assets_composition['Criptomonedas'] = crypto_value
        
        # Metales preciosos
        gold_record = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
        silver_record = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
        gold_price = gold_record.price_eur_per_oz if gold_record else 0
        silver_price = silver_record.price_eur_per_oz if silver_record else 0
        
        metal_transactions = PreciousMetalTransaction.query.filter_by(user_id=current_user.id).all()
        if metal_transactions:
            g_to_oz = 0.0321507466
            gold_oz = 0
            silver_oz = 0
            
            for transaction in metal_transactions:
                quantity_oz = transaction.quantity if transaction.unit_type == 'oz' else transaction.quantity * g_to_oz
                
                if transaction.metal_type == 'gold':
                    if transaction.transaction_type == 'buy':
                        gold_oz += quantity_oz
                    else:
                        gold_oz -= quantity_oz
                else:
                    if transaction.transaction_type == 'buy':
                        silver_oz += quantity_oz
                    else:
                        silver_oz -= quantity_oz
            
            gold_value = gold_oz * gold_price
            silver_value = silver_oz * silver_price
            metals_value = gold_value + silver_value
            total_assets += metals_value
            assets_composition['Metales'] = metals_value
        
        # Planes de pensiones
        pension_plans = PensionPlan.query.filter_by(user_id=current_user.id).all()
        if pension_plans:
            pension_total = sum(plan.current_balance for plan in pension_plans)
            total_assets += pension_total
            assets_composition['Pensiones'] = pension_total
        
        report_data['assets'] = {
            'total': total_assets,
            'composition': assets_composition
        }

        # --- PASIVOS ---
        total_liabilities = 0
        monthly_debt_payment = 0
        
        # Deudas
        debt_plans = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()
        if debt_plans:
            total_liabilities = sum(plan.remaining_amount for plan in debt_plans)
            
            # Pago mensual de deudas
            today = date.today()
            current_month = date(today.year, today.month, 1)
            monthly_debt_payment = sum(
                plan.monthly_payment for plan in debt_plans
                if plan.start_date <= current_month and
                (plan.end_date is None or plan.end_date > current_month)
            )
            
            # Añadir detalle de deudas
            debt_details = []
            for plan in debt_plans:
                debt_details.append({
                    'description': plan.description,
                    'total_amount': plan.total_amount,
                    'remaining': plan.remaining_amount,
                    'monthly_payment': plan.monthly_payment,
                    'progress_pct': plan.progress_percentage,
                    'remaining_months': plan.remaining_installments
                })
            
            report_data['liabilities'] = {
                'total': total_liabilities,
                'monthly_payment': monthly_debt_payment,
                'details': debt_details
            }
        
        # --- MÉTRICAS FINANCIERAS ---
        # Total gastos mensuales incluyendo deuda
        total_monthly_expenses += monthly_debt_payment
        
        # Ahorro mensual
        monthly_savings = total_monthly_income - total_monthly_expenses
        savings_rate = (monthly_savings / total_monthly_income * 100) if total_monthly_income > 0 else 0
        
        # Ratio deuda/ingresos
        debt_to_income_ratio = (monthly_debt_payment / total_monthly_income * 100) if total_monthly_income > 0 else 0
        
        # Ratio deuda/activos
        debt_to_assets_ratio = (total_liabilities / total_assets * 100) if total_assets > 0 else 0
        
        # Patrimonio neto
        net_worth = total_assets - total_liabilities
        
        # Meses para independencia financiera (estimación)
        months_to_fi = 0
        fi_target = 0
        if monthly_savings > 0:
            # Suponiendo que la independencia financiera se logra con 25 veces los gastos anuales
            annual_expenses = total_monthly_expenses * 12
            fi_target = annual_expenses * 25
            
            # Estimación sin considerar rendimientos de inversiones
            if net_worth < fi_target:
                months_to_fi = (fi_target - net_worth) / monthly_savings
        
        report_data['metrics'] = {
            'net_worth': net_worth,
            'monthly_savings': monthly_savings,
            'savings_rate': savings_rate,
            'debt_to_income_ratio': debt_to_income_ratio,
            'debt_to_assets_ratio': debt_to_assets_ratio,
            'months_to_fi': months_to_fi,
            'fi_target': fi_target
        }
        
        # --- RECOMENDACIONES PERSONALIZADAS ---
        recommendations = []
        
        # 1. Tasa de ahorro
        if savings_rate < 0:
            recommendations.append({
                'category': 'savings',
                'severity': 'high',
                'title': 'Balance mensual negativo',
                'description': 'Estás gastando más de lo que ingresas. Considera reducir gastos o aumentar ingresos para evitar endeudamiento.',
                'actions': [
                    'Revisa tus gastos fijos para identificar posibles reducciones',
                    'Considera fuentes adicionales de ingresos'
                ]
            })
        elif savings_rate < 10:
            recommendations.append({
                'category': 'savings',
                'severity': 'medium',
                'title': 'Baja tasa de ahorro',
                'description': f'Tu tasa de ahorro es del {savings_rate:.1f}%. Se recomienda ahorrar al menos el 15-20% de los ingresos.',
                'actions': [
                    'Establece un presupuesto mensual',
                    'Automatiza tus ahorros'
                ]
            })
        elif savings_rate > 50:
            recommendations.append({
                'category': 'savings',
                'severity': 'low',
                'title': 'Excelente tasa de ahorro',
                'description': f'Tu tasa de ahorro del {savings_rate:.1f}% es extraordinaria. Considera optimizar la inversión de estos ahorros.',
                'actions': [
                    'Revisa tu estrategia de inversión para maximizar retornos',
                    'Considera diversificar en diferentes clases de activos'
                ]
            })
        
        # 2. Deuda
        if debt_to_income_ratio > 40:
            recommendations.append({
                'category': 'debt',
                'severity': 'high',
                'title': 'Ratio deuda/ingresos elevado',
                'description': f'Tu ratio de pago de deuda mensual respecto a ingresos es del {debt_to_income_ratio:.1f}%. Se recomienda mantenerlo por debajo del 35%.',
                'actions': [
                    'Prioriza el pago de deudas con mayor interés',
                    'Considera opciones de refinanciación',
                    'Evita asumir nuevas deudas hasta reducir las actuales'
                ]
            })
        elif debt_to_income_ratio > 0 and debt_to_income_ratio < 20:
            recommendations.append({
                'category': 'debt',
                'severity': 'low',
                'title': 'Buen manejo de deuda',
                'description': f'Tu ratio de deuda/ingresos es del {debt_to_income_ratio:.1f}%, lo cual es saludable.',
                'actions': [
                    'Mantén este nivel de endeudamiento',
                    'Considera realizar pagos adicionales para reducir el plazo'
                ]
            })
        
        # 3. Diversificación de activos
        if total_assets > 0:
            # Calcular porcentajes de diversificación
            asset_percentages = {k: (v / total_assets * 100) for k, v in assets_composition.items()}
            
            # Verificar si hay alguna categoría que represente más del 50%
            concentrated_assets = [(k, v) for k, v in asset_percentages.items() if v > 50]
            
            if concentrated_assets:
                asset_name, percentage = concentrated_assets[0]
                recommendations.append({
                    'category': 'diversification',
                    'severity': 'medium',
                    'title': 'Concentración de activos',
                    'description': f'El {percentage:.1f}% de tus activos está en {asset_name}. Considera diversificar para reducir riesgos.',
                    'actions': [
                        'Diversifica gradualmente hacia otras clases de activos',
                        'Establece objetivos de asignación de activos'
                    ]
                })
            
            # Verificar si tiene efectivo suficiente para emergencias
            if 'Efectivo' in asset_percentages:
                cash_percentage = asset_percentages.get('Efectivo', 0)
                monthly_expenses_x3 = total_monthly_expenses * 3
                cash_total = assets_composition.get('Efectivo', 0)
                
                if cash_total < monthly_expenses_x3:
                    recommendations.append({
                        'category': 'emergency_fund',
                        'severity': 'medium',
                        'title': 'Fondo de emergencia insuficiente',
                        'description': f'Tu efectivo ({cash_total:.2f} €) es menor que 3 meses de gastos ({monthly_expenses_x3:.2f} €).',
                        'actions': [
                            'Prioriza acumular un fondo de emergencia de 3-6 meses de gastos',
                            'Considera una cuenta de ahorro de alta rentabilidad para este fondo'
                        ]
                    })
                elif cash_percentage > 30 and cash_total > monthly_expenses_x6:
                    # Si tiene más de 6 meses de gastos en efectivo
                    monthly_expenses_x6 = total_monthly_expenses * 6
                    excess_cash = cash_total - monthly_expenses_x6
                    
                    recommendations.append({
                        'category': 'cash_optimization',
                        'severity': 'low',
                        'title': 'Exceso de efectivo',
                        'description': f'Tienes {excess_cash:.2f} € por encima de un fondo de emergencia de 6 meses.',
                        'actions': [
                            'Considera invertir el exceso de efectivo para obtener mejores rendimientos',
                            'Mantén 3-6 meses de gastos como fondo de emergencia'
                        ]
                    })
        
        # 4. Ingresos y Gastos
        if 'income' in report_data and 'salary_trend' in report_data['income']:
            avg_growth = report_data['income']['salary_trend']['avg_growth']
            
            if avg_growth < 2:
                recommendations.append({
                    'category': 'income',
                    'severity': 'medium',
                    'title': 'Bajo crecimiento salarial',
                    'description': f'Tu salario ha crecido un promedio de {avg_growth:.1f}% anual, por debajo de la inflación.',
                    'actions': [
                        'Considera negociar un aumento salarial',
                        'Evalúa oportunidades para desarrollo profesional',
                        'Explora fuentes de ingresos adicionales'
                    ]
                })
        
        if 'variable' in report_data.get('income', {}):
            variable_income_pct = (report_data['income']['variable']['monthly_avg'] / report_data['income']['total_monthly'] * 100)
            
            if variable_income_pct > 30:
                recommendations.append({
                    'category': 'income_stability',
                    'severity': 'medium',
                    'title': 'Alta dependencia de ingresos variables',
                    'description': f'El {variable_income_pct:.1f}% de tus ingresos son variables, lo que puede generar inestabilidad financiera.',
                    'actions': [
                        'Mantén un fondo de emergencia más amplio',
                        'Busca formas de estabilizar tus fuentes de ingresos',
                        'Adapta tus gastos fijos a tu ingreso fijo'
                    ]
                })
        
        # 5. Categorías de gasto
        if 'expenses' in report_data and 'by_category' in report_data['expenses']:
            # Calcular porcentajes de categorías
            total_6m = report_data['expenses']['total_6m']
            expense_percentages = {k: (v / total_6m * 100) for k, v in report_data['expenses']['by_category'].items()}
            
            # Identificar categorías con gasto elevado
            high_expense_categories = []
            for category, percentage in expense_percentages.items():
                # Umbrales por categoría
                threshold = 30  # Umbral genérico por defecto
                
                if category.lower() in ['vivienda', 'hipoteca', 'alquiler']:
                    threshold = 35  # Máximo recomendado para vivienda
                elif category.lower() in ['alimentación', 'comida', 'supermercado']:
                    threshold = 15  # Máximo para alimentación
                elif category.lower() in ['transporte', 'coche', 'vehículo']:
                    threshold = 15  # Máximo para transporte
                elif category.lower() in ['ocio', 'entretenimiento', 'restaurantes']:
                    threshold = 10  # Máximo para ocio
                
                if percentage > threshold:
                    high_expense_categories.append({
                        'category': category,
                        'percentage': percentage,
                        'threshold': threshold
                    })
            
            # Generar recomendaciones para categorías de gasto elevado
            for category_info in high_expense_categories:
                recommendations.append({
                    'category': 'expenses',
                    'severity': 'medium',
                    'title': f'Gasto elevado en {category_info["category"]}',
                    'description': f'Gastas el {category_info["percentage"]:.1f}% en {category_info["category"]}, por encima del {category_info["threshold"]}% recomendado.',
                    'actions': [
                        f'Revisa detalladamente tus gastos en {category_info["category"]}',
                        'Identifica áreas específicas de reducción',
                        'Establece un presupuesto máximo mensual para esta categoría'
                    ]
                })
        
        # Añadir recomendaciones al informe
        report_data['recommendations'] = recommendations
        
        # Renderizar la plantilla con los datos del informe
        return render_template(
            'financial_report.html',
            report=report_data
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"Error al generar el informe financiero: {e}", "danger")
        return redirect(url_for('financial_summary'))


@app.route('/manage_expense_categories')
@login_required
def manage_expense_categories():
    """Muestra y gestiona las categorías de gastos."""
    # Obtener todas las categorías principales
    main_categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None
    ).order_by(ExpenseCategory.name).all()
    
    # Preparar datos para mostrar
    categories_data = []
    
    for category in main_categories:
        # Contar gastos en esta categoría
        expenses_count = Expense.query.filter_by(category_id=category.id).count()
        
        # Buscar subcategorías
        subcategories = ExpenseCategory.query.filter_by(
            user_id=current_user.id,
            parent_id=category.id
        ).order_by(ExpenseCategory.name).all()
        
        subcategories_data = []
        for subcat in subcategories:
            # Contar gastos en la subcategoría
            subcat_expenses_count = Expense.query.filter_by(category_id=subcat.id).count()
            
            subcategories_data.append({
                'id': subcat.id,
                'name': subcat.name,
                'description': subcat.description,
                'expenses_count': subcat_expenses_count
            })
        
        categories_data.append({
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'expenses_count': expenses_count,
            'subcategories': subcategories_data
        })
    
    # Crear formulario para nueva categoría
    form = ExpenseCategoryForm()
    
    # Cargar categorías para el dropdown
    form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [
        (cat.id, cat.name) for cat in main_categories
    ]
    
    return render_template(
        'manage_expense_categories.html',
        categories=categories_data,
        form=form
    )


# --- Formularios para la gestión de gastos (MODIFICADO) ---
class ExpenseCategoryForm(FlaskForm):
    name = StringField('Nombre de la Categoría', validators=[DataRequired()],
                    render_kw={"placeholder": "Ej: Alquiler, Alimentación, Transporte..."})
    description = TextAreaField('Descripción (Opcional)',
                             render_kw={"placeholder": "Descripción opcional", "rows": 2})
    parent_id = SelectField('Categoría Padre (Opcional)', coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField('Guardar Categoría')

class ExpenseForm(FlaskForm):
    description = StringField('Descripción', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: Alquiler Mayo, Compra Supermercado..."})
    amount = StringField('Importe (€)', validators=[DataRequired()],
                       render_kw={"placeholder": "Ej: 500.50"})
    date = StringField('Fecha', validators=[DataRequired()],
                     render_kw={"type": "date"})
    category_id = SelectField('Categoría', coerce=int, validators=[Optional()])
    # Modificar las opciones para que sean solo Gasto Puntual y Gasto Recurrente
    expense_type = SelectField('Tipo de Gasto',
                            choices=[
                                ('punctual', 'Gasto Puntual'),
                                ('fixed', 'Gasto Recurrente')
                            ],
                            validators=[DataRequired()])
    # Se mantiene este campo, pero se controlará por JavaScript
    is_recurring = BooleanField('Es Recurrente')
    recurrence_months = SelectField('Recurrencia',
                                 choices=[
                                     (1, 'Mensual'),
                                     (2, 'Bimestral'),
                                     (3, 'Trimestral'),
                                     (6, 'Semestral'),
                                     (12, 'Anual')
                                 ], coerce=int, validators=[Optional()])
    # El campo start_date se mantiene, pero no se mostrará en el formulario
    start_date = StringField('Fecha Inicio (Para recurrentes)',
                          render_kw={"type": "date"}, validators=[Optional()])
    end_date = StringField('Fecha Fin (Opcional)',
                        render_kw={"type": "date"}, validators=[Optional()])
    submit = SubmitField('Registrar Gasto')



@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    """Muestra y gestiona la página de gastos."""
    # Formulario para categorías
    category_form = ExpenseCategoryForm()

    # Cargar categorías para el dropdown del formulario
    user_categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None  # Solo categorías principales
    ).all()

    category_form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [
        (cat.id, cat.name) for cat in user_categories
    ]

    # Formulario para gastos
    expense_form = ExpenseForm()

    # Cargar todas las categorías para el dropdown (incluyendo subcategorías)
    all_categories = ExpenseCategory.query.filter_by(user_id=current_user.id).all()

    # Crear una lista de opciones con indentación para mostrar jerarquía
    category_choices = []
    for cat in all_categories:
        if cat.parent_id is None:
            category_choices.append((cat.id, cat.name))
            # Añadir subcategorías con indentación
            subcats = ExpenseCategory.query.filter_by(parent_id=cat.id).all()
            for subcat in subcats:
                category_choices.append((subcat.id, f"-- {subcat.name}"))

    expense_form.category_id.choices = [(0, 'Sin categoría')] + category_choices

    # Procesar formulario de categoría
    if category_form.validate_on_submit() and 'add_category' in request.form:
        try:
            parent_id = category_form.parent_id.data
            if parent_id == 0:
                parent_id = None  # Si se seleccionó "Ninguna"

            # Crear nueva categoría
            new_category = ExpenseCategory(
                user_id=current_user.id,
                name=category_form.name.data,
                description=category_form.description.data,
                parent_id=parent_id
            )

            db.session.add(new_category)
            db.session.commit()

            flash('Categoría añadida correctamente.', 'success')
            return redirect(url_for('expenses'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear categoría: {e}', 'danger')

    # Procesar formulario de gasto
    if expense_form.validate_on_submit() and 'add_expense' in request.form:
        try:
            # Convertir valores
            amount = float(expense_form.amount.data.replace(',', '.'))
            date_obj = datetime.strptime(expense_form.date.data, '%Y-%m-%d').date()

            # Determinar categoría
            category_id = expense_form.category_id.data
            if category_id == 0:
                category_id = None  # Sin categoría

            # Verificar campos para gastos recurrentes
            is_recurring = expense_form.is_recurring.data
            recurrence_months = None
            start_date = None
            end_date = None

            if is_recurring:
                recurrence_months = expense_form.recurrence_months.data

                # CAMBIO: Para gastos recurrentes, la fecha de inicio siempre es igual a la fecha del gasto
                start_date = date_obj

                if expense_form.end_date.data:
                    end_date = datetime.strptime(expense_form.end_date.data, '%Y-%m-%d').date()

            # Crear nuevo gasto
            new_expense = Expense(
                user_id=current_user.id,
                category_id=category_id,
                description=expense_form.description.data,
                amount=amount,
                date=date_obj,
                expense_type=expense_form.expense_type.data,
                is_recurring=is_recurring,
                recurrence_months=recurrence_months,
                start_date=start_date,
                end_date=end_date
            )

            db.session.add(new_expense)
            db.session.commit()

            flash('Gasto registrado correctamente.', 'success')
            return redirect(url_for('expenses'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar gasto: {e}', 'danger')

    # Obtener todos los gastos del usuario (ordenados por fecha, más recientes primero)
    user_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()

    # Obtener gastos de deuda desde DebtInstallmentPlan
    debt_plans = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()

    # Convertir planes de deuda a "gastos" para mostrarlos en el historial unificado
    debt_expenses = []
    for plan in debt_plans:
        # Calcular meses ya pagados
        today = date.today()
        if today < plan.start_date:
            # Si aún no ha empezado, no hay pagos
            continue

        # Calcular número de pagos ya realizados
        months_passed = (today.year - plan.start_date.year) * 12 + today.month - plan.start_date.month
        months_passed = min(months_passed, plan.duration_months)

        # Clonar la fecha de inicio para manipulación
        current_date = date(plan.start_date.year, plan.start_date.month, 1)

        # Para cada mes que ya ha pasado, crear un "gasto"
        for i in range(months_passed):
            # Avanzar al siguiente mes
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)

            # Crear un objeto tipo diccionario para simular un gasto
            debt_expense = {
                'id': f"debt_{plan.id}_{i}",  # ID único para identificar
                'description': f"Deuda: {plan.description}",
                'amount': plan.monthly_payment,
                'date': current_date,
                'expense_type': 'debt',  # Tipo especial para deudas
                'is_recurring': True,
                'category_name': 'Deudas',  # Categoría virtual
                'from_debt': True  # Flag para identificar que viene de deudas
            }

            debt_expenses.append(debt_expense)

    # Calcular estadísticas y resúmenes

    # 1. Gastos fijos mensuales (actuales)
    fixed_expenses_sum = sum(expense.amount for expense in user_expenses
                           if expense.expense_type == 'fixed' and expense.is_recurring)

    # 2. Gastos puntuales (último mes)
    one_month_ago = date.today() - timedelta(days=30)
    punctual_expenses_sum = sum(expense.amount for expense in user_expenses
                              if expense.expense_type == 'punctual' and expense.date >= one_month_ago)

    # 3. Gastos de deuda mensuales (actuales)
    debt_monthly_sum = sum(plan.monthly_payment for plan in debt_plans
                         if plan.is_active and plan.remaining_installments > 0)

    # 4. Total gastos mensuales
    total_monthly_expenses = fixed_expenses_sum + debt_monthly_sum

    # 5. Gastos por categoría (últimos 6 meses) - ACTUALIZADO
    six_months_ago = date.today() - timedelta(days=180)
    end_date = date.today()
    expenses_by_category = {}

    # Lista para almacenar todos los gastos procesados (incluyendo recurrentes expandidos)
    expenses_in_range = []

    # Procesar cada gasto
    for expense in user_expenses:
        # Para gastos recurrentes, generar entradas para cada mes
        if expense.is_recurring and expense.expense_type == 'fixed':
            # Determinar fecha de inicio y fin
            expense_start = expense.start_date or expense.date
            expense_end = expense.end_date or end_date

            # Ajustar si está fuera del rango de análisis
            if expense_end < six_months_ago:
                # El gasto terminó antes del período de análisis
                continue

            if expense_start > end_date:
                # El gasto comienza después del período de análisis
                continue

            # Ajustar inicio al período de análisis si es necesario
            actual_start = max(expense_start, six_months_ago)
            # Ajustar fin al período de análisis si es necesario
            actual_end = min(expense_end, end_date)

            # Calcular meses entre start_date y end_date
            current_date = actual_start
            recurrence = expense.recurrence_months or 1  # Por defecto mensual

            while current_date <= actual_end:
                # Crear una copia del gasto para este mes
                expenses_in_range.append({
                    'description': expense.description,
                    'amount': expense.amount,
                    'date': current_date,
                    'category_id': expense.category_id,
                    'expense_type': expense.expense_type,
                    'is_recurring': expense.is_recurring
                })

                # Avanzar al siguiente período según la recurrencia
                year = current_date.year
                month = current_date.month + recurrence

                # Ajustar si nos pasamos de diciembre
                while month > 12:
                    month -= 12
                    year += 1

                # Crear nueva fecha
                try:
                    current_date = date(year, month, 1)
                except ValueError:
                    # Por si hay algún problema con la fecha
                    break

        else:
            # Para gastos puntuales, solo incluir si están en el rango
            if six_months_ago <= expense.date <= end_date:
                expenses_in_range.append({
                    'description': expense.description,
                    'amount': expense.amount,
                    'date': expense.date,
                    'category_id': expense.category_id,
                    'expense_type': expense.expense_type,
                    'is_recurring': expense.is_recurring
                })

    for expense in expenses_in_range:
        category_name = "Sin categoría"
        if expense['category_id']:
            category = ExpenseCategory.query.get(expense['category_id'])
            if category:
                category_name = category.name

        if category_name not in expenses_by_category:
            expenses_by_category[category_name] = {
                'total': 0,
                'count': 0,
                'monthly_avg': 0
            }

        expenses_by_category[category_name]['total'] += expense['amount']
        expenses_by_category[category_name]['count'] += 1

    # Calcular promedio mensual por categoría (dividir entre 6 meses)
    for category_name, data in expenses_by_category.items():
        # Dividir entre 6 (meses) o el número de gastos si es menor
        months = 6
        data['monthly_avg'] = data['total'] / months

    # Ordenar categorías por gasto total (de mayor a menor)
    sorted_categories = sorted(
        expenses_by_category.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )

    # 6. Comparar gastos actuales con la media
    current_month = date.today().replace(day=1)
    current_month_expenses = sum(expense.amount for expense in user_expenses
                               if expense.date.year == current_month.year
                               and expense.date.month == current_month.month)

    # Calcular promedio mensual (últimos 6 meses excluyendo mes actual)
    last_6_months = []
    for i in range(1, 7):
        month = current_month.month - i
        year = current_month.year

        if month <= 0:
            month += 12
            year -= 1

        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        month_expenses = sum(expense.amount for expense in user_expenses
                           if expense.date >= month_start and expense.date <= month_end)

        last_6_months.append(month_expenses)

    # Calcular promedio de los últimos 6 meses
    avg_monthly_expenses = sum(last_6_months) / len(last_6_months) if last_6_months else 0

    # Calcular porcentaje de variación
    if avg_monthly_expenses > 0:
        current_vs_avg_pct = ((current_month_expenses - avg_monthly_expenses) / avg_monthly_expenses) * 100
    else:
        current_vs_avg_pct = 0

    # ===== NUEVO: PREPARACIÓN DE HISTORIAL UNIFICADO MEJORADO =====
    # Combinar gastos regulares y de deuda para historial unificado
    unified_expenses = []

    # Convertir gastos normales a formato común
    for expense in user_expenses:
        category_name = "Sin categoría"
        if expense.category_id:
            category = ExpenseCategory.query.get(expense.category_id)
            if category:
                category_name = category.name

        # Si es un gasto recurrente, generar entradas para cada mes
        if expense.is_recurring and expense.expense_type == 'fixed':
            # Determinar fecha de inicio y fin
            start_date = expense.start_date or expense.date
            end_date = expense.end_date or date.today()

            # Si la fecha de fin es futura, usar la fecha actual como límite
            if end_date > date.today():
                end_date = date.today()

            # Calcular meses entre start_date y end_date
            current_date = start_date
            recurrence = expense.recurrence_months or 1  # Por defecto mensual

            while current_date <= end_date:
                # Crear entrada para este mes
                monthly_entry = {
                    'id': expense.id,
                    'description': f"{expense.description} ({current_date.strftime('%b %Y')})",
                    'amount': expense.amount,
                    'date': current_date,
                    'expense_type': expense.expense_type,
                    'is_recurring': expense.is_recurring,
                    'category_name': category_name,
                    'from_debt': False
                }
                unified_expenses.append(monthly_entry)

                # Avanzar al siguiente período según la recurrencia
                # Calcular el siguiente mes
                year = current_date.year
                month = current_date.month + recurrence

                # Ajustar si nos pasamos de diciembre
                while month > 12:
                    month -= 12
                    year += 1

                # Crear nueva fecha
                try:
                    current_date = date(year, month, 1)
                except ValueError:
                    # Por si hay algún problema con la fecha
                    break
        else:
            # Para gastos puntuales, solo añadir una entrada
            unified_expenses.append({
                'id': expense.id,
                'description': expense.description,
                'amount': expense.amount,
                'date': expense.date,
                'expense_type': expense.expense_type,
                'is_recurring': expense.is_recurring,
                'category_name': category_name,
                'from_debt': False
            })

    # Añadir gastos de deuda
    unified_expenses.extend(debt_expenses)

    # ==== NUEVO: PROCESAR ESTADO DE FINALIZACIÓN DE GASTOS RECURRENTES ====
    # Para cada gasto recurrente, verificar si está finalizado y marcar las entradas correspondientes
    for expense_entry in unified_expenses:
        # Solo procesar los gastos recurrentes regulares (no de deuda)
        if expense_entry.get('is_recurring') and expense_entry.get('expense_type') == 'fixed' and not expense_entry.get('from_debt'):
            # Obtener el gasto original para conocer su fecha de fin
            original_expense = Expense.query.get(expense_entry.get('id'))
            if original_expense:
                # Determinar si el gasto está finalizado (tiene end_date)
                if original_expense.end_date:
                    entry_date = expense_entry.get('date')

                    # Si la entrada es del mes de finalización o anterior, marcar como "finalizado"
                    # (Comparamos por año y mes, ignorando el día)
                    if (entry_date.year < original_expense.end_date.year or
                        (entry_date.year == original_expense.end_date.year and
                         entry_date.month <= original_expense.end_date.month)):
                        expense_entry['is_ended'] = True
                        expense_entry['end_date'] = original_expense.end_date
                    else:
                        # Si es posterior a la fecha de fin, marcar para ocultar
                        expense_entry['is_ended'] = True
                        expense_entry['should_hide'] = True
                else:
                    expense_entry['is_ended'] = False

    # Filtrar para eliminar entradas que no deben mostrarse (posteriores a finalización)
    unified_expenses = [e for e in unified_expenses if not e.get('should_hide', False)]

    # Ordenar por fecha (más recientes primero)
    unified_expenses.sort(key=lambda x: x['date'], reverse=True)

    return render_template('expenses.html',
                         category_form=category_form,
                         expense_form=expense_form,
                         expenses=user_expenses,
                         unified_expenses=unified_expenses,
                         fixed_expenses_sum=fixed_expenses_sum,
                         punctual_expenses_sum=punctual_expenses_sum,
                         debt_monthly_sum=debt_monthly_sum,
                         total_monthly_expenses=total_monthly_expenses,
                         sorted_categories=sorted_categories,
                         current_month_expenses=current_month_expenses,
                         avg_monthly_expenses=avg_monthly_expenses,
                         current_vs_avg_pct=current_vs_avg_pct)


# --- Nuevas rutas a añadir en app.py para las funcionalidades solicitadas ---

# 1. Ruta para finalizar un gasto recurrente
@app.route('/end_recurring_expense/<int:expense_id>/<string:action_date>', methods=['POST'])
@login_required
def end_recurring_expense(expense_id, action_date):
    """
    Finaliza un gasto recurrente estableciendo su fecha de fin a la fecha especificada.
    Si ya está finalizado (tiene end_date), revierte la finalización.
    
    Args:
        expense_id: ID del gasto recurrente
        action_date: Fecha desde la que finalizar (formato YYYY-MM-DD)
    """
    # Buscar el gasto por ID y verificar que pertenece al usuario
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    
    # Verificar que es un gasto recurrente
    if not expense.is_recurring or expense.expense_type != 'fixed':
        flash('Solo se pueden finalizar gastos recurrentes.', 'warning')
        return redirect(url_for('expenses'))
    
    try:
        # Convertir la fecha de acción a objeto date
        fin_date = datetime.strptime(action_date, '%Y-%m-%d').date()
        
        # Si el gasto ya tiene fecha de fin (está finalizado), revertir la finalización
        if expense.end_date:
            expense.end_date = None
            db.session.commit()
            flash(f'El gasto recurrente "{expense.description}" ha sido reactivado. Se generarán pagos desde la fecha actual.', 'success')
        else:
            # Finalizar el gasto en la fecha especificada
            # Ajustamos al primer día del mes para mantener consistencia
            fin_month_date = date(fin_date.year, fin_date.month, 1)
            
            expense.end_date = fin_month_date
            db.session.commit()
            flash(f'El gasto recurrente "{expense.description}" ha sido finalizado en {fin_month_date.strftime("%m/%Y")}. No se generarán más pagos a partir de esta fecha.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el gasto recurrente: {e}', 'danger')
    
    return redirect(url_for('expenses'))

@app.route('/delete_expense_with_options/<int:expense_id>/<string:delete_type>', methods=['POST'])
@login_required
def delete_expense_with_options(expense_id, delete_type):
    """
    Elimina un gasto recurrente según la opción seleccionada:
    - 'single': Elimina solo la entrada específica
    - 'series': Elimina toda la serie recurrente
    
    Args:
        expense_id: ID del gasto recurrente
        delete_type: Tipo de eliminación ('single' o 'series')
    """
    # Buscar el gasto por ID y verificar que pertenece al usuario
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    
    if not expense:
        flash('Gasto no encontrado.', 'danger')
        return redirect(url_for('expenses'))
    
    try:
        if delete_type == 'series':
            # Eliminar toda la serie recurrente
            db.session.delete(expense)
            db.session.commit()
            flash(f'La serie completa del gasto recurrente "{expense.description}" ha sido eliminada.', 'success')
        
        elif delete_type == 'single':
            # Para eliminar solo una entrada de una serie, necesitamos:
            # 1. Marcar la fecha como un hueco en la serie (realmente no podemos eliminar solo una instancia real)
            # 2. O crear un nuevo registro negativo para ese mes específico
            
            # Vamos a optar por la segunda opción: crear un registro negativo (compensación)
            # Primero, determinar la fecha exacta a partir de los parámetros de URL si se proporciona
            entry_date_str = request.args.get('entry_date')
            
            if entry_date_str:
                entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date()
                
                # Crear un gasto de compensación (mismo importe pero negativo)
                compensation = Expense(
                    user_id=current_user.id,
                    category_id=expense.category_id,
                    description=f"Excepción: {expense.description}",
                    amount=-expense.amount,  # Importe negativo para cancelar
                    date=entry_date,
                    expense_type='punctual',  # Puntual para que no se repita
                    is_recurring=False
                )
                
                db.session.add(compensation)
                db.session.commit()
                flash(f'El pago específico de "{expense.description}" para {entry_date.strftime("%m/%Y")} ha sido cancelado.', 'success')
            else:
                flash('No se pudo determinar la fecha del pago a eliminar.', 'warning')
        
        else:
            flash('Opción de eliminación no válida.', 'warning')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar gasto: {e}', 'danger')
    
    return redirect(url_for('expenses'))

# 2. Ruta para obtener análisis por categoría según rango temporal
@app.route('/get_category_analysis')
@login_required
def get_category_analysis():
    """
    Endpoint AJAX para obtener el análisis por categoría según un rango temporal.
    
    Parámetros Query:
    - months: número de meses hacia atrás (1, 3, 6, 12, 36, 60, 120)
    - start_date: fecha de inicio para rango personalizado (formato YYYY-MM-DD)
    - end_date: fecha de fin para rango personalizado (formato YYYY-MM-DD)
    """
    # Obtener parámetros
    months = request.args.get('months', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # Calcular fechas de inicio y fin
    end_date = date.today()
    
    if start_date_str and end_date_str:
        # Usar rango personalizado
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # Validar fechas
            if start_date > end_date:
                return '<div class="alert alert-danger">La fecha de inicio no puede ser posterior a la fecha de fin.</div>'
            
            range_description = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
        except ValueError:
            return '<div class="alert alert-danger">Formato de fecha inválido.</div>'
    else:
        # Usar número de meses
        if not months:
            months = 6  # Por defecto, 6 meses
        
        start_date = end_date - timedelta(days=30 * months)
        
        # Determinar descripción del rango según meses
        if months == 1:
            range_description = "Último mes"
        elif months == 3:
            range_description = "Últimos 3 meses"
        elif months == 6:
            range_description = "Últimos 6 meses"
        elif months == 12:
            range_description = "Último año"
        elif months == 36:
            range_description = "Últimos 3 años"
        elif months == 60:
            range_description = "Últimos 5 años"
        elif months == 120:
            range_description = "Últimos 10 años"
        else:
            range_description = f"Últimos {months} meses"
    
    # Obtener todos los gastos
    all_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    
    # Lista para almacenar todos los gastos procesados (incluyendo recurrentes expandidos)
    expenses_in_range = []
    
    # Procesar cada gasto
    for expense in all_expenses:
        # Para gastos recurrentes, generar entradas para cada mes
        if expense.is_recurring and expense.expense_type == 'fixed':
            # Determinar fecha de inicio y fin
            expense_start = expense.start_date or expense.date
            expense_end = expense.end_date or end_date
            
            # Ajustar si está fuera del rango de análisis
            if expense_end < start_date:
                # El gasto terminó antes del período de análisis
                continue
                
            if expense_start > end_date:
                # El gasto comienza después del período de análisis
                continue
                
            # Ajustar inicio al período de análisis si es necesario
            actual_start = max(expense_start, start_date)
            # Ajustar fin al período de análisis si es necesario
            actual_end = min(expense_end, end_date)
            
            # Calcular meses entre start_date y end_date
            current_date = actual_start
            recurrence = expense.recurrence_months or 1  # Por defecto mensual
            
            while current_date <= actual_end:
                # Crear una copia del gasto para este mes
                expenses_in_range.append({
                    'description': expense.description,
                    'amount': expense.amount,
                    'date': current_date,
                    'category_id': expense.category_id,
                    'expense_type': expense.expense_type,
                    'is_recurring': expense.is_recurring
                })
                
                # Avanzar al siguiente período según la recurrencia
                year = current_date.year
                month = current_date.month + recurrence
                
                # Ajustar si nos pasamos de diciembre
                while month > 12:
                    month -= 12
                    year += 1
                
                # Crear nueva fecha
                try:
                    current_date = date(year, month, 1)
                except ValueError:
                    # Por si hay algún problema con la fecha
                    break
                    
        else:
            # Para gastos puntuales, solo incluir si están en el rango
            if start_date <= expense.date <= end_date:
                expenses_in_range.append({
                    'description': expense.description,
                    'amount': expense.amount,
                    'date': expense.date,
                    'category_id': expense.category_id,
                    'expense_type': expense.expense_type,
                    'is_recurring': expense.is_recurring
                })
    
    # Calcular gastos por categoría
    expenses_by_category = {}
    
    for expense in expenses_in_range:
        category_name = "Sin categoría"
        if expense['category_id']:
            category = ExpenseCategory.query.get(expense['category_id'])
            if category:
                category_name = category.name
                
        if category_name not in expenses_by_category:
            expenses_by_category[category_name] = {
                'total': 0,
                'count': 0,
                'monthly_avg': 0
            }
        
        expenses_by_category[category_name]['total'] += expense['amount']
        expenses_by_category[category_name]['count'] += 1
    
    # Calcular promedio mensual por categoría
    # Calcular número de meses en el rango
    if start_date_str and end_date_str:
        # Para rangos personalizados, calcular número de meses
        months_diff = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
    else:
        # Para rangos predefinidos, usar el valor de meses
        months_diff = months
    
    for category_name, data in expenses_by_category.items():
        if months_diff > 0:
            data['monthly_avg'] = data['total'] / months_diff
        else:
            data['monthly_avg'] = 0
    
    # Ordenar categorías por gasto total (de mayor a menor)
    sorted_categories = sorted(
        expenses_by_category.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )
    
    # Calcular el total de todos los gastos para los porcentajes
    total_sum = sum(data['total'] for _, data in sorted_categories)
    
    # Renderizar solo la parte de la tabla de análisis
    return render_template(
        'category_analysis_table.html',
        sorted_categories=sorted_categories,
        total_sum=total_sum,
        range_description=range_description
    )

@app.route('/delete_expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    """Elimina un gasto existente."""
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Gasto eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar gasto: {e}', 'danger')
    
    return redirect(url_for('expenses'))

@app.route('/edit_expense_category/<int:category_id>', methods=['GET', 'POST'])
@login_required
def edit_expense_category(category_id):
    """Edita una categoría de gasto existente."""
    # Buscar la categoría por ID y verificar que pertenece al usuario
    category = ExpenseCategory.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    
    # Crear formulario
    form = ExpenseCategoryForm()
    
    # Cargar categorías para el dropdown (excluyendo la actual y sus subcategorías)
    user_categories = ExpenseCategory.query.filter_by(
        user_id=current_user.id, 
        parent_id=None  # Solo categorías principales
    ).filter(ExpenseCategory.id != category_id).all()
    
    # Filtrar subcategorías que pertenecen a esta categoría
    subcategory_ids = [subcat.id for subcat in category.subcategories]
    user_categories = [cat for cat in user_categories if cat.id not in subcategory_ids]
    
    form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [
        (cat.id, cat.name) for cat in user_categories
    ]
    
    if request.method == 'GET':
        # Precargar datos de la categoría en el formulario
        form.name.data = category.name
        form.description.data = category.description
        form.parent_id.data = category.parent_id if category.parent_id else 0
    
    if form.validate_on_submit():
        try:
            parent_id = form.parent_id.data
            if parent_id == 0:
                parent_id = None  # Si se seleccionó "Ninguna"
                
            # Actualizar la categoría
            category.name = form.name.data
            category.description = form.description.data
            category.parent_id = parent_id
            
            db.session.commit()
            
            flash('Categoría actualizada correctamente.', 'success')
            return redirect(url_for('expenses'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar categoría: {e}', 'danger')
    
    return render_template('edit_expense_category.html', form=form, category=category)

@app.route('/delete_expense_category/<int:category_id>', methods=['POST'])
@login_required
def delete_expense_category(category_id):
    """Elimina una categoría de gasto existente."""
    category = ExpenseCategory.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()
    
    try:
        # Verificar si hay gastos o subcategorías asociadas
        has_expenses = Expense.query.filter_by(category_id=category_id).first() is not None
        has_subcategories = ExpenseCategory.query.filter_by(parent_id=category_id).first() is not None
        
        if has_expenses:
            flash('No se puede eliminar la categoría porque tiene gastos asociados.', 'warning')
            return redirect(url_for('expenses'))
            
        if has_subcategories:
            flash('No se puede eliminar la categoría porque tiene subcategorías.', 'warning')
            return redirect(url_for('expenses'))
        
        db.session.delete(category)
        db.session.commit()
        flash('Categoría eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar categoría: {e}', 'danger')
    
    return redirect(url_for('expenses'))



@app.route('/debt_management', methods=['GET', 'POST'])
@login_required
def debt_management():
    """Displays and manages the debt management page."""
    # Get current user's salary if available
    income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
    annual_salary = income_data.annual_net_salary if income_data else None
    monthly_salary = annual_salary / 12 if annual_salary else None
    
    # Get or create debt ceiling
    debt_ceiling = DebtCeiling.query.filter_by(user_id=current_user.id).first()
    if not debt_ceiling:
        debt_ceiling = DebtCeiling(user_id=current_user.id)
        db.session.add(debt_ceiling)
        db.session.commit()
    
    # Calculate debt ceiling amount
    ceiling_amount = None
    if monthly_salary and debt_ceiling:
        ceiling_amount = monthly_salary * (debt_ceiling.percentage / 100)
    
    # Form for updating debt ceiling
    ceiling_form = DebtCeilingForm()
    if ceiling_form.is_submitted() and ceiling_form.validate() and 'update_ceiling' in request.form:
        try:
            # Convert to float (replacing comma with period if necessary)
            percentage = ceiling_form.percentage.data.replace(',', '.')
            percentage = float(percentage)
            
            # Update debt ceiling
            debt_ceiling.percentage = percentage
            debt_ceiling.last_updated = datetime.utcnow()
            db.session.commit()
            
            flash('Techo de deuda actualizado correctamente.', 'success')
            return redirect(url_for('debt_management'))
        
        except (ValueError, Exception) as e:
            db.session.rollback()
            flash(f'Error al procesar los datos: {e}', 'danger')
    
    # Pre-fill form with current value
    if debt_ceiling and not ceiling_form.is_submitted():
        ceiling_form.percentage.data = debt_ceiling.percentage
    
    # Form for adding debt installment plan
    plan_form = DebtInstallmentPlanForm()
    
    # Process debt plan form
    if plan_form.validate_on_submit() and ('add_plan' in request.form):
        try:
            # Parse the start date
            start_month_year = plan_form.start_date.data  # Format: "YYYY-MM"
            date_parts = start_month_year.split('-')
            
            if len(date_parts) != 2:
                flash('Formato de fecha incorrecto. Use YYYY-MM.', 'warning')
                return redirect(url_for('debt_management'))
            
            year = int(date_parts[0])
            month = int(date_parts[1])
            
            # Create date with the first day of the month (siempre día 1)
            start_date = date(year, month, 1)
            
            # Verificar si la fecha de inicio es posterior a hoy (si está en el pasado, mostrar advertencia)
            today = date.today()
            if start_date < today and (today.year != start_date.year or today.month != start_date.month):
                flash(f'Advertencia: La fecha de inicio {start_date.strftime("%m/%Y")} está en el pasado.', 'warning')
                
            # Si estamos en el mismo mes pero después del día 1, advertir que el primer pago será el próximo mes
            elif start_date.year == today.year and start_date.month == today.month and today.day > 1:
                flash(f'Advertencia: Ya ha pasado el día 1 de este mes. El primer pago contará a partir del {start_date.strftime("%d/%m/%Y")}.', 'warning')
            
            # Convert numeric values
            total_amount = float(plan_form.total_amount.data.replace(',', '.'))
            duration_months = int(plan_form.duration_months.data)
            
            # Calculate monthly payment
            monthly_payment = total_amount / duration_months if duration_months > 0 else total_amount
            
            # Calcular fecha de fin correctamente
            end_date = calculate_end_date(start_date, duration_months)
            
            # Calculate end date manually (don't try to set it as an attribute)
            month_end = month + duration_months
            year_end = year + (month_end - 1) // 12
            month_end = ((month_end - 1) % 12) + 1
            end_date = date(year_end, month_end, 1)
            
            # Check if the plan is already expired
            today = date.today()
            is_active = end_date >= today
            
            # Create new debt plan
            new_plan = DebtInstallmentPlan(
                user_id=current_user.id,
                description=plan_form.description.data,
                total_amount=total_amount,
                start_date=start_date,
                duration_months=duration_months,
                monthly_payment=monthly_payment,
                is_active=is_active  # Set active status based on end date
            )
            
            db.session.add(new_plan)
            db.session.commit()
            
            if is_active:
                flash('Plan de pago añadido correctamente.', 'success')
            else:
                flash('Plan de pago añadido como Inactivo porque la fecha de finalización ya pasó.', 'info')
            return redirect(url_for('debt_management'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear plan de pago: {e}', 'danger')
            print(f"Error al crear plan de pago: {e}")
            import traceback
            traceback.print_exc()
    
    # Get all debt plans for current user
    all_debt_plans = DebtInstallmentPlan.query.filter_by(user_id=current_user.id).order_by(
        DebtInstallmentPlan.is_active.desc(),  # Active plans first
        DebtInstallmentPlan.start_date.desc()   # Most recent first
    ).all()
    
    # Calculate today's date for filtering
    today = date.today()
    
    # Create a dictionary to store calculated end dates for use in the template
    plan_end_dates = {}
    
    # Get only active debt plans
    active_debt_plans = []
    for plan in all_debt_plans:
        if plan.is_active:
            # Calculate end_date manually
            month_end = plan.start_date.month + plan.duration_months
            year_end = plan.start_date.year + (month_end - 1) // 12
            month_end = ((month_end - 1) % 12) + 1
            plan_end_date = date(year_end, month_end, 1)
            
            # Store in dictionary instead of trying to set as attribute
            plan_end_dates[plan.id] = plan_end_date
            
            # Include only if not expired
            if plan_end_date >= today:
                active_debt_plans.append(plan)
    
    # Calculate end dates for all plans and store in the dictionary
    for plan in all_debt_plans:
        if plan.id not in plan_end_dates:
            month_end = plan.start_date.month + plan.duration_months
            year_end = plan.start_date.year + (month_end - 1) // 12
            month_end = ((month_end - 1) % 12) + 1
            plan_end_dates[plan.id] = date(year_end, month_end, 1)
    
    # Sort active debt plans by end_date (ascending - soonest to expire first)
    active_debt_plans.sort(key=lambda x: plan_end_dates[x.id])
    
    # Sort all_debt_plans by end_date for the history view
    all_debt_plans.sort(key=lambda x: plan_end_dates[x.id], reverse=True)
    
    # Calculate current month and next month for payment summaries
    current_month = date(today.year, today.month, 1)
    
    # Calculate next month
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)
    
    # Calculate summary data
    total_debt_remaining = sum(plan.remaining_amount for plan in active_debt_plans)
    
    # Calculate current month payment
    current_month_payment = sum(
        plan.monthly_payment for plan in active_debt_plans 
        if plan.start_date <= current_month and plan_end_dates[plan.id] > current_month
    )
    
    # Calculate next month payment
    next_month_payment = sum(
        plan.monthly_payment for plan in active_debt_plans 
        if plan.start_date <= next_month and plan_end_dates[plan.id] > next_month
    )
    
    # Calculate debt percentage of ceiling
    debt_percentage = None
    debt_margin = None
    if ceiling_amount and ceiling_amount > 0:
        debt_percentage = (current_month_payment / ceiling_amount) * 100
        debt_margin = ceiling_amount - current_month_payment
    
    return render_template(
        'debt_management.html',
        ceiling_form=ceiling_form,
        plan_form=plan_form,
        debt_ceiling=debt_ceiling,
        ceiling_amount=ceiling_amount,
        all_debt_plans=all_debt_plans,
        active_debt_plans=active_debt_plans,
        total_debt_remaining=total_debt_remaining,
        current_month_payment=current_month_payment,
        next_month_payment=next_month_payment,
        debt_percentage=debt_percentage,
        debt_margin=debt_margin,
        current_month=current_month,
        next_month=next_month,
        monthly_salary=monthly_salary,
        now=datetime.now(),  # Added to provide current date for template
        plan_end_dates=plan_end_dates  # Pass the end dates dictionary to the template
    )

@app.route('/toggle_debt_plan/<int:plan_id>', methods=['POST'])
@login_required
def toggle_debt_plan(plan_id):
    """Marca un plan de deuda como liquidado (inactivo) y actualiza la fecha de fin al mes actual."""
    plan = DebtInstallmentPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    try:
        # Si el plan está activo, marcarlo como inactivo (liquidado)
        if plan.is_active:
            # Obtener la fecha actual para usarla como fecha de fin
            today = date.today()
            
            # Calcular la nueva duración en meses desde la fecha de inicio hasta el mes actual
            start_month = plan.start_date.month + (plan.start_date.year * 12)
            end_month = today.month + (today.year * 12)
            new_duration = end_month - start_month
            
            # Asegurar que la duración es de al menos 1 mes
            if new_duration < 1:
                new_duration = 1
            
            # Calcular la nueva cuota mensual basada en la cantidad total y la duración real
            # Esto asegura que en el historial, la cuota mensual refleje el valor correcto
            new_monthly_payment = plan.total_amount / new_duration
            
            # Actualizar la duración y la cuota mensual del plan
            plan.duration_months = new_duration
            plan.monthly_payment = new_monthly_payment
            
            # Actualizar el estado a inactivo
            plan.is_active = False
            
            db.session.commit()
            flash(f'Plan de pago "{plan.description}" marcado como liquidado en {today.strftime("%m/%Y")}.', 'success')
        # No incluimos la opción de reactivar planes desde el historial
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar estado del plan: {e}', 'danger')
        print(f"Error al cambiar estado del plan: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('debt_management'))



@app.route('/debug_form', methods=['POST'])
@login_required
def debug_form():
    """Ruta de debugging para ver por qué el formulario no se está validando."""
    print("=== DEBUG INFORMACIÓN DEL FORMULARIO ===")
    print(f"Método de solicitud: {request.method}")
    print(f"Contenido del formulario: {request.form}")

    # Crear el formulario
    plan_form = DebtInstallmentPlanForm()

    # Verificar si el token CSRF está presente y es válido
    print(f"Token CSRF presente: {'csrf_token' in request.form}")
    if hasattr(plan_form, 'csrf_token'):
        print(f"Validación CSRF: {plan_form.csrf_token.validate(plan_form)}")

    # Intentar validar el formulario
    is_valid = plan_form.validate_on_submit()
    print(f"Formulario válido: {is_valid}")

    # Verificar cada campo individual
    print("Errores de validación por campo:")
    for field_name, field in plan_form._fields.items():
        if field.errors:
            print(f"  Campo '{field_name}': {field.errors}")

    # Verificar si 'add_plan' está en el formulario
    print(f"'add_plan' presente en el formulario: {'add_plan' in request.form}")

    # Devolver esta información como JSON
    return {
        "method": request.method,
        "form_data": {k: v for k, v in request.form.items()},
        "is_valid": is_valid,
        "errors": {name: field.errors for name, field in plan_form._fields.items() if field.errors}
    }

# Luego modifica el formulario en la plantilla para incluir un botón adicional de debugging
# <button type="button" onclick="debugForm()" class="btn btn-info">Debug Form</button>

# Y añade este JavaScript a la plantilla:
# <script>
# function debugForm() {
#     // Crear una copia del formulario
#     var form = document.querySelector('form:has(input[name="add_plan"])');
#     var formData = new FormData(form);
#
#     // Enviar a la ruta de debugging
#     fetch('/debug_form', {
#         method: 'POST',
#         body: formData
#     })
#     .then(response => response.json())
#     .then(data => {
#         console.log('DEBUG INFO:', data);
#         alert('Información de debugging en la consola');
#     })
#     .catch(error => console.error('Error:', error));
# }
# </script>


@app.route('/delete_debt_plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_debt_plan(plan_id):
    """Deletes a debt plan."""
    plan = DebtInstallmentPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(plan)
        db.session.commit()
        flash(f'Plan de pago "{plan.description}" eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar plan: {e}', 'danger')
    
    return redirect(url_for('debt_management'))

@app.route('/delete_debt_history/<int:record_id>', methods=['POST'])
@login_required
def delete_debt_history(record_id):
    """Deletes a debt history record."""
    record = DebtHistoryRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(record)
        db.session.commit()
        flash('Registro de deuda eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar registro: {e}', 'danger')

    return redirect(url_for('debt_management'))


@app.route('/pension_plans', methods=['GET', 'POST'])
@login_required
def pension_plans():
    """Muestra y gestiona la página de planes de pensiones."""
    # Formulario para añadir nuevo plan
    plan_form = PensionPlanForm()
    
    # Formulario para guardar historial
    history_form = PensionHistoryForm()
    
    # Procesar formulario de nuevo plan
    if plan_form.validate_on_submit() and 'add_plan' in request.form:
        try:
            # Convertir saldo a float
            balance = float(plan_form.current_balance.data.replace(',', '.'))
            
            # Crear nuevo plan
            new_plan = PensionPlan(
                user_id=current_user.id,
                entity_name=plan_form.entity_name.data,
                plan_name=plan_form.plan_name.data,
                current_balance=balance
            )
            
            db.session.add(new_plan)
            db.session.commit()
            
            flash('Plan de pensiones añadido correctamente.', 'success')
            return redirect(url_for('pension_plans'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al añadir plan: {e}', 'danger')
    
    # Obtener todos los planes del usuario
    user_plans = PensionPlan.query.filter_by(user_id=current_user.id).all()
    
    # Calcular el total de pensiones
    total_pension = sum(plan.current_balance for plan in user_plans)
    
    # Obtener historial de pensiones
    pension_history = PensionPlanHistory.query.filter_by(user_id=current_user.id).order_by(PensionPlanHistory.date.desc()).all()
    
    # Calcular variaciones
    for i, record in enumerate(pension_history):
        if i < len(pension_history) - 1:
            next_record = pension_history[i + 1]
            if next_record.total_amount > 0:
                variation = ((record.total_amount - next_record.total_amount) / next_record.total_amount) * 100
                record.variation = variation
            else:
                record.variation = None
        else:
            record.variation = None
    
    return render_template(
        'pension_plans.html',
        plan_form=plan_form,
        history_form=history_form,
        plans=user_plans,
        total_pension=total_pension,
        pension_history=pension_history
    )

@app.route('/update_pension_plan/<int:plan_id>', methods=['POST'])
@login_required
def update_pension_plan(plan_id):
    """Actualiza un plan de pensiones existente."""
    plan = PensionPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    try:
        # Obtener datos del formulario
        entity_name = request.form.get('entity_name')
        plan_name = request.form.get('plan_name')
        current_balance = request.form.get('current_balance').replace(',', '.')
        
        # Validar datos
        if not entity_name or not current_balance:
            flash('Todos los campos obligatorios deben estar completos.', 'warning')
            return redirect(url_for('pension_plans'))
        
        # Actualizar plan
        plan.entity_name = entity_name
        plan.plan_name = plan_name
        plan.current_balance = float(current_balance)
        plan.last_updated = datetime.utcnow()
        
        db.session.commit()
        flash('Plan actualizado correctamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar plan: {e}', 'danger')
    
    return redirect(url_for('pension_plans'))

@app.route('/delete_pension_plan/<int:plan_id>', methods=['POST'])
@login_required
def delete_pension_plan(plan_id):
    """Elimina un plan de pensiones."""
    plan = PensionPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(plan)
        db.session.commit()
        flash('Plan eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar plan: {e}', 'danger')
    
    return redirect(url_for('pension_plans'))

@app.route('/save_pension_history', methods=['POST'])
@login_required
def save_pension_history():
    """Guarda un registro del historial de planes de pensiones."""
    form = PensionHistoryForm()
    
    if form.validate_on_submit():
        try:
            # Obtener la fecha del formulario
            month_year = form.month_year.data  # Formato: "YYYY-MM"
            date_parts = month_year.split('-')
            
            if len(date_parts) != 2:
                flash('Formato de fecha incorrecto. Use YYYY-MM.', 'warning')
                return redirect(url_for('pension_plans'))
            
            year = int(date_parts[0])
            month = int(date_parts[1])
            
            # Crear fecha con el primer día del mes
            record_date = date(year, month, 1)
            
            # Comprobar si ya existe un registro para este mes/año
            existing = PensionPlanHistory.query.filter_by(
                user_id=current_user.id, 
                date=record_date
            ).first()
            
            if existing:
                flash(f'Ya existe un registro para {month}/{year}. Elimínelo antes de crear uno nuevo.', 'warning')
                return redirect(url_for('pension_plans'))
            
            # Calcular el total actual
            plans = PensionPlan.query.filter_by(user_id=current_user.id).all()
            total_amount = sum(plan.current_balance for plan in plans)
            
            # Crear nuevo registro
            new_record = PensionPlanHistory(
                user_id=current_user.id,
                date=record_date,
                total_amount=total_amount
            )
            
            db.session.add(new_record)
            db.session.commit()
            
            flash(f'Registro de planes de pensiones para {month}/{year} guardado correctamente.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar registro: {e}', 'danger')
    
    return redirect(url_for('pension_plans'))

@app.route('/delete_pension_history/<int:record_id>', methods=['POST'])
@login_required
def delete_pension_history(record_id):
    """Elimina un registro del historial de planes de pensiones."""
    record = PensionPlanHistory.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(record)
        db.session.commit()
        flash('Registro histórico eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar registro: {e}', 'danger')
    
    return redirect(url_for('pension_plans'))


@app.route('/crypto', methods=['GET', 'POST'])
@login_required
def crypto():
    """Muestra y gestiona la página de criptomonedas."""
    # Formulario para añadir nuevo exchange
    exchange_form = CryptoExchangeForm()
    
    # Formulario para añadir nueva transacción
    transaction_form = CryptoTransactionForm()
    
    # Cargar exchanges para el dropdown del formulario
    user_exchanges = CryptoExchange.query.filter_by(user_id=current_user.id).all()
    transaction_form.exchange_id.choices = [(e.id, e.exchange_name) for e in user_exchanges]
    
    # Procesar formulario de añadir exchange
    if exchange_form.validate_on_submit() and 'add_exchange' in request.form:
        try:
            new_exchange = CryptoExchange(
                user_id=current_user.id,
                exchange_name=exchange_form.exchange_name.data
            )
            
            db.session.add(new_exchange)
            db.session.commit()
            
            flash('Exchange añadido correctamente.', 'success')
            return redirect(url_for('crypto'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al añadir exchange: {e}', 'danger')
    
    # Procesar formulario de añadir transacción
    if transaction_form.validate_on_submit() and 'add_transaction' in request.form:
        try:
            # Comprobar si el exchange pertenece al usuario
            exchange = CryptoExchange.query.filter_by(
                id=transaction_form.exchange_id.data, 
                user_id=current_user.id
            ).first()
            
            if not exchange:
                flash('Exchange no válido.', 'danger')
                return redirect(url_for('crypto'))
            
            # Convertir valores numéricos
            quantity = float(transaction_form.quantity.data.replace(',', '.'))
            price_per_unit = float(transaction_form.price_per_unit.data.replace(',', '.'))
            fees = None
            if transaction_form.fees.data and transaction_form.fees.data.strip():
                fees = float(transaction_form.fees.data.replace(',', '.'))
            
            # Convertir fecha
            transaction_date = datetime.strptime(transaction_form.date.data, '%Y-%m-%d').date()
            
            # Crear nueva transacción
            new_transaction = CryptoTransaction(
                exchange_id=exchange.id,
                user_id=current_user.id,
                transaction_type=transaction_form.transaction_type.data,
                crypto_name=transaction_form.crypto_name.data,
                ticker_symbol=transaction_form.ticker_symbol.data.upper(),
                date=transaction_date,
                quantity=quantity,
                price_per_unit=price_per_unit,
                fees=fees
            )
            
            # Intentar obtener precio actual
            current_price = get_crypto_price(new_transaction.ticker_symbol)
            if current_price is not None:
                new_transaction.current_price = current_price
                new_transaction.price_updated_at = datetime.utcnow()
            
            db.session.add(new_transaction)
            db.session.commit()
            
            flash('Operación registrada correctamente.', 'success')
            return redirect(url_for('crypto'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar la operación: {e}', 'danger')
    
    # Obtener todas las transacciones ordenadas por fecha (más recientes primero)
    all_transactions = CryptoTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(CryptoTransaction.date.desc()).all()
    
    # Mapa de exchange_id a nombre para mostrar en la lista
    exchange_map = {ex.id: ex.exchange_name for ex in user_exchanges}
    
    # Preparar resumen del portfolio por exchange
    exchange_portfolios = {}
    for exchange in user_exchanges:
        exchange_portfolios[exchange.id] = {
            'exchange': exchange,
            'cryptos': {}
        }
    
    # Calcular resumen del portfolio por criptomoneda
    portfolio_summary = {}
    total_investment = 0
    total_current_value = 0
    total_profit_loss = 0
    
    for transaction in all_transactions:
        crypto_key = transaction.ticker_symbol
        
        # Inicializar datos de la criptomoneda si no existe
        if crypto_key not in portfolio_summary:
            portfolio_summary[crypto_key] = {
                'name': transaction.crypto_name,
                'ticker': transaction.ticker_symbol,
                'total_quantity': 0,
                'total_investment': 0,
                'total_fees': 0,
                'current_price': transaction.current_price,
                'price_updated_at': transaction.price_updated_at,
            }
        
        # Actualizar cantidades basadas en el tipo de transacción
        if transaction.transaction_type == 'buy':
            portfolio_summary[crypto_key]['total_quantity'] += transaction.quantity
            portfolio_summary[crypto_key]['total_investment'] += (transaction.quantity * transaction.price_per_unit)
            if transaction.fees:
                portfolio_summary[crypto_key]['total_fees'] += transaction.fees
        else:  # 'sell'
            portfolio_summary[crypto_key]['total_quantity'] -= transaction.quantity
            portfolio_summary[crypto_key]['total_investment'] -= (transaction.quantity * transaction.price_per_unit)
            if transaction.fees:
                portfolio_summary[crypto_key]['total_fees'] += transaction.fees
        
        # Usar precio más reciente
        if transaction.current_price is not None and (
            portfolio_summary[crypto_key]['current_price'] is None or 
            (transaction.price_updated_at and portfolio_summary[crypto_key]['price_updated_at'] and 
             transaction.price_updated_at > portfolio_summary[crypto_key]['price_updated_at'])
        ):
            portfolio_summary[crypto_key]['current_price'] = transaction.current_price
            portfolio_summary[crypto_key]['price_updated_at'] = transaction.price_updated_at
        
        # Agregar datos al resumen por exchange
        ex_id = transaction.exchange_id
        if ex_id in exchange_portfolios:
            if crypto_key not in exchange_portfolios[ex_id]['cryptos']:
                exchange_portfolios[ex_id]['cryptos'][crypto_key] = {
                    'name': transaction.crypto_name,
                    'ticker': transaction.ticker_symbol,
                    'total_quantity': 0,
                    'total_investment': 0,
                    'total_fees': 0,
                    'current_price': transaction.current_price,
                }
            
            # Actualizar cantidades en el resumen por exchange
            if transaction.transaction_type == 'buy':
                exchange_portfolios[ex_id]['cryptos'][crypto_key]['total_quantity'] += transaction.quantity
                exchange_portfolios[ex_id]['cryptos'][crypto_key]['total_investment'] += (transaction.quantity * transaction.price_per_unit)
                if transaction.fees:
                    exchange_portfolios[ex_id]['cryptos'][crypto_key]['total_fees'] += transaction.fees
            else:  # 'sell'
                exchange_portfolios[ex_id]['cryptos'][crypto_key]['total_quantity'] -= transaction.quantity
                exchange_portfolios[ex_id]['cryptos'][crypto_key]['total_investment'] -= (transaction.quantity * transaction.price_per_unit)
                if transaction.fees:
                    exchange_portfolios[ex_id]['cryptos'][crypto_key]['total_fees'] += transaction.fees
            
            # Actualizar precio actual
            exchange_portfolios[ex_id]['cryptos'][crypto_key]['current_price'] = portfolio_summary[crypto_key]['current_price']
    
    # Calcular valores actuales y rentabilidad
    portfolio_list = []
    for key, crypto in portfolio_summary.items():
        if crypto['total_quantity'] > 0 and crypto['current_price'] is not None:
            current_value = crypto['total_quantity'] * crypto['current_price']
            profit_loss = current_value - crypto['total_investment'] - crypto['total_fees']
            profit_loss_pct = 0
            
            if crypto['total_investment'] > 0:
                profit_loss_pct = (profit_loss / crypto['total_investment']) * 100
            
            crypto['current_value'] = current_value
            crypto['profit_loss'] = profit_loss
            crypto['profit_loss_pct'] = profit_loss_pct
            
            total_investment += crypto['total_investment'] + crypto['total_fees']
            total_current_value += current_value
            total_profit_loss += profit_loss
        
        # Solo incluir en el resumen si la cantidad es mayor que cero
        if crypto['total_quantity'] > 0:
            portfolio_list.append(crypto)
    
    # Calcular porcentaje total de rentabilidad
    total_profit_loss_pct = 0
    if total_investment > 0:
        total_profit_loss_pct = (total_profit_loss / total_investment) * 100
    
    # Calcular el valor actual para cada crypto en cada exchange
    for ex_id, exchange_data in exchange_portfolios.items():
        exchange_total_value = 0
        exchange_total_investment = 0
        exchange_total_profit_loss = 0
        
        for crypto_key, crypto in exchange_data['cryptos'].items():
            if crypto['total_quantity'] > 0 and crypto['current_price'] is not None:
                current_value = crypto['total_quantity'] * crypto['current_price']
                profit_loss = current_value - crypto['total_investment'] - crypto['total_fees']
                profit_loss_pct = 0
                
                if crypto['total_investment'] > 0:
                    profit_loss_pct = (profit_loss / crypto['total_investment']) * 100
                
                crypto['current_value'] = current_value
                crypto['profit_loss'] = profit_loss
                crypto['profit_loss_pct'] = profit_loss_pct
                
                exchange_total_investment += crypto['total_investment'] + crypto['total_fees']
                exchange_total_value += current_value
                exchange_total_profit_loss += profit_loss
        
        exchange_data['total_investment'] = exchange_total_investment
        exchange_data['total_current_value'] = exchange_total_value
        exchange_data['total_profit_loss'] = exchange_total_profit_loss
        
        if exchange_total_investment > 0:
            exchange_data['total_profit_loss_pct'] = (exchange_total_profit_loss / exchange_total_investment) * 100
        else:
            exchange_data['total_profit_loss_pct'] = 0
    
    return render_template(
        'crypto.html',
        exchange_form=exchange_form,
        transaction_form=transaction_form,
        all_transactions=all_transactions,
        exchange_map=exchange_map,
        portfolio_summary=portfolio_list,
        exchange_portfolios=exchange_portfolios,
        total_investment=total_investment,
        total_current_value=total_current_value,
        total_profit_loss=total_profit_loss,
        total_profit_loss_pct=total_profit_loss_pct
    )


@app.route('/update_crypto_prices', methods=['GET'])
@login_required
def update_crypto_prices():
    """Actualiza los precios de todas las criptomonedas del usuario."""
    try:
        # Obtener todos los tickers únicos de las transacciones
        crypto_tickers = db.session.query(CryptoTransaction.ticker_symbol).filter_by(
            user_id=current_user.id
        ).distinct().all()
        
        updated = 0
        failed = 0
        
        for ticker_tuple in crypto_tickers:
            ticker = ticker_tuple[0]
            price = get_crypto_price(ticker)
            
            if price:
                # Actualizar el precio en todas las transacciones con este ticker
                transactions = CryptoTransaction.query.filter_by(
                    user_id=current_user.id,
                    ticker_symbol=ticker
                ).all()
                
                for transaction in transactions:
                    transaction.current_price = price
                    transaction.price_updated_at = datetime.utcnow()
                
                updated += 1
            else:
                failed += 1
        
        db.session.commit()
        
        if updated > 0:
            flash(f'Precios actualizados para {updated} criptomonedas. Fallos: {failed}', 'success')
        else:
            flash(f'No se pudo actualizar ningún precio. Fallos: {failed}', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar precios: {e}', 'danger')
    
    return redirect(url_for('crypto'))

@app.route('/delete_crypto_exchange/<int:exchange_id>', methods=['POST'])
@login_required
def delete_crypto_exchange(exchange_id):
    """Elimina un exchange y todas sus transacciones asociadas."""
    exchange = CryptoExchange.query.filter_by(id=exchange_id, user_id=current_user.id).first_or_404()
    
    try:
        # Las transacciones se eliminan automáticamente por la relación cascade
        db.session.delete(exchange)
        db.session.commit()
        flash('Exchange y sus operaciones eliminados correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar exchange: {e}', 'danger')
    
    return redirect(url_for('crypto'))

@app.route('/delete_crypto_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def delete_crypto_transaction(transaction_id):
    """Elimina una operación específica."""
    transaction = CryptoTransaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(transaction)
        db.session.commit()
        flash('Operación eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar operación: {e}', 'danger')
    
    return redirect(url_for('crypto'))

@app.route('/edit_crypto_transaction/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_crypto_transaction(transaction_id):
    """Edita una operación existente."""
    # Buscar la transacción por ID y verificar que pertenece al usuario
    transaction = CryptoTransaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            transaction_type = request.form.get('transaction_type')
            crypto_name = request.form.get('crypto_name')
            ticker_symbol = request.form.get('ticker_symbol').upper()
            date_str = request.form.get('date')
            quantity = float(request.form.get('quantity').replace(',', '.'))
            price_per_unit = float(request.form.get('price_per_unit').replace(',', '.'))
            fees_str = request.form.get('fees')
            
            # Convertir fecha
            transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Procesar fees
            fees = None
            if fees_str and fees_str.strip():
                fees = float(fees_str.replace(',', '.'))
            
            # Actualizar la transacción
            transaction.transaction_type = transaction_type
            transaction.crypto_name = crypto_name
            transaction.ticker_symbol = ticker_symbol
            transaction.date = transaction_date
            transaction.quantity = quantity
            transaction.price_per_unit = price_per_unit
            transaction.fees = fees
            
            # Intentar actualizar el precio actual
            current_price = get_crypto_price(ticker_symbol)
            if current_price is not None:
                transaction.current_price = current_price
                transaction.price_updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Operación actualizada correctamente.', 'success')
            return redirect(url_for('crypto'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la operación: {e}', 'danger')
    
    # Para GET, mostrar formulario de edición
    # Obtener exchanges para el dropdown
    exchanges = CryptoExchange.query.filter_by(user_id=current_user.id).all()
    
    return render_template(
        'edit_crypto_transaction.html',
        transaction=transaction,
        exchanges=exchanges
    )

@app.route('/delete_crypto_holding/<int:holding_id>', methods=['POST'])
@login_required
def delete_crypto_holding(holding_id):
    """Elimina una criptomoneda específica."""
    holding = CryptoHolding.query.filter_by(id=holding_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(holding)
        db.session.commit()
        flash('Criptomoneda eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar criptomoneda: {e}', 'danger')

    return redirect(url_for('cryptos'))

@app.route('/update_crypto_holding/<int:holding_id>', methods=['POST'])
@login_required
def update_crypto_holding(holding_id):
    """Actualiza la cantidad de una criptomoneda."""
    holding = CryptoHolding.query.filter_by(id=holding_id, user_id=current_user.id).first_or_404()

    try:
        quantity = request.form.get('quantity')
        if not quantity:
            flash('La cantidad es obligatoria.', 'warning')
            return redirect(url_for('cryptos'))

        holding.quantity = float(quantity.replace(',', '.'))
        db.session.commit()
        flash('Cantidad actualizada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar cantidad: {e}', 'danger')

    return redirect(url_for('cryptos'))


@app.route('/save_crypto_history', methods=['POST'])
@login_required
def save_crypto_history():
    """Guarda un registro del historial de criptomonedas."""
    form = CryptoHistoryForm()
    
    if form.validate_on_submit():
        try:
            # Obtener la fecha del formulario
            month_year = form.month_year.data  # Formato: "YYYY-MM"
            date_parts = month_year.split('-')
            
            if len(date_parts) != 2:
                flash('Formato de fecha incorrecto. Use YYYY-MM.', 'warning')
                return redirect(url_for('cryptos'))
            
            year = int(date_parts[0])
            month = int(date_parts[1])
            
            # Crear fecha con el primer día del mes
            record_date = date(year, month, 1)
            
            # Comprobar si ya existe un registro para este mes/año
            existing = CryptoHistoryRecord.query.filter_by(
                user_id=current_user.id, 
                date=record_date
            ).first()
            
            if existing:
                flash(f'Ya existe un registro para {month}/{year}. Elimínelo antes de crear uno nuevo.', 'warning')
                return redirect(url_for('cryptos'))
            
            # Calcular el valor total actual
            holdings = CryptoHolding.query.filter_by(user_id=current_user.id).all()
            total_value_eur = 0
            
            for holding in holdings:
                if holding.quantity and holding.current_price:
                    total_value_eur += holding.quantity * holding.current_price
            
            # Crear nuevo registro
            new_record = CryptoHistoryRecord(
                user_id=current_user.id,
                date=record_date,
                total_value_eur=total_value_eur
            )
            
            db.session.add(new_record)
            db.session.commit()
            
            flash(f'Registro de criptomonedas para {month}/{year} guardado correctamente.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar registro: {e}', 'danger')
    
    return redirect(url_for('cryptos'))

@app.route('/delete_crypto_history/<int:record_id>', methods=['POST'])
@login_required
def delete_crypto_history(record_id):
    """Elimina un registro del historial de criptomonedas."""
    record = CryptoHistoryRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(record)
        db.session.commit()
        flash('Registro histórico eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar registro: {e}', 'danger')
    
    return redirect(url_for('cryptos'))

@app.route('/silver_gold', methods=['GET', 'POST'])
@login_required
def silver_gold():
    """Muestra y gestiona la página de metales preciosos (oro y plata)."""
    # Formulario para añadir transacción
    transaction_form = PreciousMetalTransactionForm()

    # Procesar formulario de nueva transacción
    if transaction_form.validate_on_submit():
        try:
            # Convertir valores numéricos
            price = float(transaction_form.price_per_unit.data.replace(',', '.'))
            quantity = float(transaction_form.quantity.data.replace(',', '.'))
            taxes_fees = None
            if transaction_form.taxes_fees.data:
                taxes_fees = float(transaction_form.taxes_fees.data.replace(',', '.'))

            # Convertir fecha
            transaction_date = datetime.strptime(transaction_form.date.data, '%Y-%m-%d').date()

            # Crear nueva transacción
            new_transaction = PreciousMetalTransaction(
                user_id=current_user.id,
                metal_type=transaction_form.metal_type.data,
                transaction_type=transaction_form.transaction_type.data,
                date=transaction_date,
                price_per_unit=price,
                quantity=quantity,
                unit_type=transaction_form.unit_type.data,
                taxes_fees=taxes_fees,
                description=transaction_form.description.data
            )

            db.session.add(new_transaction)
            db.session.commit()

            flash('Transacción registrada correctamente.', 'success')
            return redirect(url_for('silver_gold'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar transacción: {e}', 'danger')

    # Obtener precios actuales
    gold_price = None
    silver_price = None

    gold_record = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
    if gold_record:
        gold_price = gold_record.price_eur_per_oz
        gold_last_updated = gold_record.updated_at

    silver_record = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
    if silver_record:
        silver_price = silver_record.price_eur_per_oz
        silver_last_updated = silver_record.updated_at

    # Obtener transacciones ordenadas por fecha (más recientes primero)
    transactions = PreciousMetalTransaction.query.filter_by(user_id=current_user.id).order_by(PreciousMetalTransaction.date.desc()).all()

    # Calcular resumen por tipo de metal
    gold_summary = {
        'total_g': 0,
        'total_oz': 0,
        'total_investment': 0,
        'total_taxes_fees': 0,
        'current_value': 0,
        'profit_loss': 0
    }

    silver_summary = {
        'total_g': 0,
        'total_oz': 0,
        'total_investment': 0,
        'total_taxes_fees': 0,
        'current_value': 0,
        'profit_loss': 0
    }

    # Factor de conversión gramos a onzas troy
    g_to_oz = 0.0321507466

    for t in transactions:
        # Determinar el resumen a actualizar
        summary = gold_summary if t.metal_type == 'gold' else silver_summary

        # Conversión a onzas troy si es necesario
        quantity_oz = t.quantity if t.unit_type == 'oz' else t.quantity * g_to_oz

        # Actualizar totales en función del tipo de transacción
        if t.transaction_type == 'buy':
            summary['total_investment'] += (t.price_per_unit * quantity_oz)
            if t.taxes_fees:
                summary['total_taxes_fees'] += t.taxes_fees

            # Actualizar cantidad total
            if t.unit_type == 'g':
                summary['total_g'] += t.quantity
            else:
                summary['total_oz'] += t.quantity
                summary['total_g'] += t.quantity / g_to_oz

        elif t.transaction_type == 'sell':
            summary['total_investment'] -= (t.price_per_unit * quantity_oz)
            if t.taxes_fees:
                summary['total_taxes_fees'] += t.taxes_fees

            # Actualizar cantidad total
            if t.unit_type == 'g':
                summary['total_g'] -= t.quantity
            else:
                summary['total_oz'] -= t.quantity
                summary['total_g'] -= t.quantity / g_to_oz

    # Calcular valores actuales y rentabilidad
    if gold_price:
        gold_summary['total_oz'] = gold_summary['total_g'] * g_to_oz
        gold_summary['current_value'] = gold_summary['total_oz'] * gold_price
        gold_summary['profit_loss'] = gold_summary['current_value'] - gold_summary['total_investment'] - gold_summary['total_taxes_fees']

    if silver_price:
        silver_summary['total_oz'] = silver_summary['total_g'] * g_to_oz
        silver_summary['current_value'] = silver_summary['total_oz'] * silver_price
        silver_summary['profit_loss'] = silver_summary['current_value'] - silver_summary['total_investment'] - silver_summary['total_taxes_fees']

    return render_template(
        'silver_gold.html',
        transaction_form=transaction_form,
        transactions=transactions,
        gold_price=gold_price,
        silver_price=silver_price,
        gold_last_updated=gold_last_updated if 'gold_last_updated' in locals() else None,
        silver_last_updated=silver_last_updated if 'silver_last_updated' in locals() else None,
        gold_summary=gold_summary,
        silver_summary=silver_summary,
        g_to_oz=g_to_oz
    )

@app.route('/update_metal_prices', methods=['GET'])
@login_required
def update_metal_prices():
    """Actualiza los precios del oro y la plata."""
    success, message = update_precious_metal_prices()

    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    return redirect(url_for('silver_gold'))

@app.route('/edit_metal_transaction/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_metal_transaction(transaction_id):
    """Edita una transacción de metal precioso existente."""
    # Buscar la transacción por ID y verificar que pertenece al usuario
    transaction = PreciousMetalTransaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            metal_type = request.form.get('metal_type')
            transaction_type = request.form.get('transaction_type')
            date_str = request.form.get('date')
            price_per_unit = float(request.form.get('price_per_unit').replace(',', '.'))
            quantity = float(request.form.get('quantity').replace(',', '.'))
            unit_type = request.form.get('unit_type')
            taxes_fees = request.form.get('taxes_fees')
            description = request.form.get('description', '')

            # Convertir fecha
            transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            # Procesar taxes_fees
            if taxes_fees and taxes_fees.strip():
                taxes_fees = float(taxes_fees.replace(',', '.'))
            else:
                taxes_fees = None

            # Actualizar la transacción
            transaction.metal_type = metal_type
            transaction.transaction_type = transaction_type
            transaction.date = transaction_date
            transaction.price_per_unit = price_per_unit
            transaction.quantity = quantity
            transaction.unit_type = unit_type
            transaction.taxes_fees = taxes_fees
            transaction.description = description

            db.session.commit()
            flash('Transacción actualizada correctamente.', 'success')
            return redirect(url_for('silver_gold'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la transacción: {e}', 'danger')

    # Para GET, mostrar formulario de edición
    return render_template(
        'edit_metal_transaction.html',
        transaction=transaction
    )

@app.route('/delete_metal_transaction/<int:transaction_id>', methods=['POST'])
@login_required
def delete_metal_transaction(transaction_id):
    """Elimina una transacción de metal precioso."""
    transaction = PreciousMetalTransaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(transaction)
        db.session.commit()
        flash('Transacción eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la transacción: {e}', 'danger')
    
    return redirect(url_for('silver_gold'))


@app.route('/toggle_all_auto_updates/<int:item_id>', methods=['POST'])
@login_required
def toggle_all_auto_updates(item_id):
    """
    Activa o desactiva todos los checkboxes de auto-actualización para un item.
    Recibe el estado deseado (enabled=True/False) como parámetro GET.
    Devuelve una respuesta JSON.
    """
    try:
        # Obtener el item de la base de datos (verificando que pertenece al usuario)
        item = WatchlistItem.query.filter_by(id=item_id, user_id=current_user.id).first()

        if not item:
            # Si no se encuentra el item o no pertenece al usuario
            return jsonify({"success": False, "message": "Item no encontrado"}), 404

        # Obtener el estado deseado desde los parámetros de la URL
        enable_all = request.args.get('enabled', 'true').lower() == 'true'

        # Actualizar todos los flags de auto-actualización
        # Nota: no incluimos auto_update_date porque ahora la fecha es siempre manual
        item.auto_update_pais = enable_all
        item.auto_update_sector = enable_all
        item.auto_update_industria = enable_all
        item.auto_update_market_cap = enable_all
        item.auto_update_pe = enable_all
        item.auto_update_div_yield = enable_all
        item.auto_update_pbv = enable_all
        item.auto_update_roe = enable_all

        # Guardar cambios en la base de datos
        db.session.commit()

        return jsonify({"success": True, "message": f"Auto-updates {'activados' if enable_all else 'desactivados'} exitosamente"})

    except Exception as e:
        db.session.rollback()
        print(f"Error en toggle_all_auto_updates: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


def update_all_watchlist_items_from_yahoo(user_id, force_update=False):
    """
    Actualiza todos los items de la watchlist de un usuario desde Yahoo Finance.
    
    Args:
        user_id: ID del usuario
        force_update: Si es True, fuerza la actualización desde Yahoo ignorando el caché
    """
    items = WatchlistItem.query.filter_by(user_id=user_id).all()
    results = {
        'total': len(items),
        'success': 0,
        'failed': 0,
        'messages': []
    }
    
    for item in items:
        success, message = update_watchlist_item_from_yahoo(item.id, force_update=force_update)
        if success:
            results['success'] += 1
        else:
            results['failed'] += 1
        
        # Guardar mensaje con nombre del item
        item_name = item.item_name or item.ticker
        results['messages'].append(f"{item_name}: {message}")
    
    return results


# --- User Loader (DEBE IR DESPUÉS de definir User y login_manager) ---
@login_manager.user_loader
def load_user(user_id):
    # ... (código como antes) ...
    return db.session.get(User, int(user_id))

# --- Formularios (DESPUÉS de modelos) ---
# ... (RegistrationForm, LoginForm) ...


# --- Formularios WTForms ---
class RegistrationForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir.')])
    submit = SubmitField('Registrarse')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ese nombre de usuario ya está en uso. Por favor, elige otro.')

class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recuérdame')
    submit = SubmitField('Iniciar Sesión')

class UserPortfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    portfolio_data = db.Column(db.Text, nullable=True)  # JSON en formato texto
    csv_data = db.Column(db.Text, nullable=True)  # JSON en formato texto para el CSV procesado
    csv_filename = db.Column(db.String(100), nullable=True)  # Nombre del archivo CSV temporal
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('portfolio', uselist=False))

# Funciones auxiliares para guardar y cargar el portfolio
def save_user_portfolio(user_id, portfolio_data, csv_data=None, csv_filename=None):
    """Guarda o actualiza los datos del portfolio del usuario en la base de datos."""
    try:
        # Buscar registro existente
        portfolio_record = UserPortfolio.query.filter_by(user_id=user_id).first()

        # Convertir datos a JSON si no son strings
        # Primero convertimos objetos no serializables (como fechas) a strings
        def json_serializable(obj):
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, (np.int64, np.int32, np.float64, np.float32)):
                return int(obj) if np.issubdtype(obj, np.integer) else float(obj)
            return obj

        # Intentar serializar a JSON con manejador personalizado
        try:
            portfolio_json = json.dumps(portfolio_data, default=json_serializable) if not isinstance(portfolio_data, str) else portfolio_data
            csv_json = json.dumps(csv_data, default=json_serializable) if csv_data and not isinstance(csv_data, str) else csv_data
        except Exception as e_json:
            print(f"Error al serializar JSON: {e_json}")
            # Intentar solución alternativa si falla
            import pandas as pd
            if isinstance(portfolio_data, list):
                for item in portfolio_data:
                    for key, value in list(item.items()):
                        if isinstance(value, (datetime, date, pd.Timestamp)):
                            item[key] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                        elif isinstance(value, (np.int64, np.int32)):
                            item[key] = int(value)
                        elif isinstance(value, (np.float64, np.float32)):
                            item[key] = float(value)
                        elif not isinstance(value, (str, int, float, bool, type(None))):
                            item[key] = str(value)
            
            # Intentar nuevamente la serialización
            portfolio_json = json.dumps(portfolio_data) if not isinstance(portfolio_data, str) else portfolio_data
            csv_json = json.dumps(csv_data) if csv_data and not isinstance(csv_data, str) else csv_data

        if portfolio_record:
            # Actualizar registro existente
            portfolio_record.portfolio_data = portfolio_json
            if csv_data is not None:
                portfolio_record.csv_data = csv_json
            if csv_filename is not None:
                portfolio_record.csv_filename = csv_filename
            portfolio_record.last_updated = datetime.utcnow()
        else:
            # Crear nuevo registro
            portfolio_record = UserPortfolio(
                user_id=user_id,
                portfolio_data=portfolio_json,
                csv_data=csv_json,
                csv_filename=csv_filename,
                last_updated=datetime.utcnow()
            )
            db.session.add(portfolio_record)

        db.session.commit()
        print(f"Portfolio del usuario {user_id} guardado exitosamente.")
        return True
    except Exception as e:
        print(f"Error al guardar portfolio del usuario {user_id}: {e}")
        import traceback
        traceback.print_exc()  # Imprime traza completa del error
        db.session.rollback()
        return False


def load_user_portfolio(user_id):
    """Carga los datos del portfolio del usuario desde la base de datos."""
    try:
        portfolio_record = UserPortfolio.query.filter_by(user_id=user_id).first()
        if not portfolio_record:
            return None, None, None

        # Convertir de JSON a dict si hay datos
        portfolio_data = json.loads(portfolio_record.portfolio_data) if portfolio_record.portfolio_data else None
        csv_data = json.loads(portfolio_record.csv_data) if portfolio_record.csv_data else None

        return portfolio_data, csv_data, portfolio_record.csv_filename
    except Exception as e:
        print(f"Error al cargar portfolio del usuario {user_id}: {e}")
        return None, None, None


# --- Funciones Auxiliares (Mapeo, Validación Archivos) ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_filename_format(filename):
    return re.match(r"^\d{4}\.csv$", filename) is not None

def load_mapping():
    if os.path.exists(MAPPING_FILE):
        try:
            with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content: return {}
                return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error al cargar {MAPPING_FILE}: {e}. Usando mapeo vacío.")
            return {}
    return {}

def save_mapping(mapping_dict):
    print(f"Intentando guardar mapeo en {MAPPING_FILE}...")
    try:
        with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(mapping_dict, f, ensure_ascii=False, indent=2)
        print(f"Mapeo guardado correctamente en {MAPPING_FILE} con {len(mapping_dict)} entradas.")
    except IOError as e:
        print(f"Error CRÍTICO de I/O al guardar mapeo en {MAPPING_FILE}: {e}")
        flash(f"¡Error Crítico! No se pudo guardar el mapeo actualizado ({MAPPING_FILE}). Error: {e}", "danger")
    except Exception as e_gen:
        print(f"Error inesperado al guardar mapeo en {MAPPING_FILE}: {e_gen}")
        flash(f"¡Error Crítico Inesperado! No se pudo guardar el mapeo. Error: {e_gen}", "danger")

# --- Funciones de Caché y Obtención de Datos Externos ---
price_cache = {}
CACHE_DURATION_SECONDS = 15 * 60
fx_cache = {}
FX_CACHE_DURATION_SECONDS = 60 * 60


def get_current_price(yahoo_ticker, force_update=False):
    """
    Obtiene el precio de una acción, priorizando el caché a menos que se fuerce actualización.

    Args:
        yahoo_ticker: Ticker completo con sufijo Yahoo (ej: 'TEF.MC')
        force_update: Si es True, ignora el caché y actualiza desde Yahoo

    Returns:
        Precio actual o 0 si no se puede obtener (para evitar NaN)
    """
    if not yahoo_ticker: return 0  # Cambiado de None a 0
    now = time.time()

    # Usar caché si está disponible y no se fuerza actualización
    if not force_update and yahoo_ticker in price_cache:
        timestamp, price = price_cache[yahoo_ticker]
        # Siempre devolver el precio cacheado, sin importar su antigüedad
        print(f"Precio {yahoo_ticker} (caché): {price}")
        # Si el precio es nan, devolver 0
        if pd.isna(price):
            return 0
        return price

    # Si llegamos aquí, es porque debemos actualizar desde Yahoo (force_update=True)
    print(f"Obteniendo precio {yahoo_ticker} (yfinance)...")
    try:
        ticker_obj = yf.Ticker(yahoo_ticker)
        hist = ticker_obj.history(period="2d")
        if not hist.empty:
            last_price = hist['Close'].iloc[-1]
            # Si el precio es nan, guardar 0 en el caché
            if pd.isna(last_price):
                last_price = 0
            price_cache[yahoo_ticker] = (now, last_price)
            print(f"  -> Obtenido y cacheado: {last_price}")
            return last_price
        else:
            print(f"  -> No historial reciente {yahoo_ticker}.")
            # Guardar 0 en el caché en caso de fallo
            price_cache[yahoo_ticker] = (now, 0)
            return 0
    except Exception as e:
        print(f"  -> Error yfinance {yahoo_ticker}: {e}")
        # Guardar 0 en el caché en caso de error
        price_cache[yahoo_ticker] = (now, 0)
        return 0


def get_exchange_rate(from_currency, to_currency='EUR'):
    # ... (Código completo de get_exchange_rate con requests/Frankfurter como lo teníamos antes) ...
    from_currency = from_currency.upper(); to_currency = to_currency.upper()
    if from_currency == to_currency: return 1.0
    cache_key = (from_currency, to_currency); now = time.time()
    if cache_key in fx_cache:
        timestamp, rate = fx_cache[cache_key]
        if now - timestamp < FX_CACHE_DURATION_SECONDS: print(f"FX {from_currency}->{to_currency} (caché): {rate}"); return rate if rate is not None else None
    print(f"Obteniendo FX {from_currency}->{to_currency} (API)..."); rate = None
    try:
        api_url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"; response = requests.get(api_url, timeout=10); response.raise_for_status()
        data = response.json()
        if 'rates' in data and to_currency in data['rates']: rate = data['rates'][to_currency]
        else:
             print(f"  -> Tasa directa no encontrada, intentando vía EUR...")
             api_url_base = f"https://api.frankfurter.app/latest?base=EUR&symbols={from_currency},{to_currency}"; response_base = requests.get(api_url_base, timeout=10); response_base.raise_for_status(); data_base = response_base.json()
             if 'rates' in data_base and from_currency in data_base['rates'] and to_currency in data_base['rates']:
                 rate_from_eur = data_base['rates'][from_currency]; rate_to_eur = data_base['rates'][to_currency]
                 if rate_from_eur != 0: rate = rate_to_eur / rate_from_eur
                 else: print(f"  -> Error: Tasa base EUR para {from_currency} es cero.")
             else: print(f"  -> No se encontraron tasas vía EUR.")
    except requests.exceptions.RequestException as e_req: print(f"  -> Error red/HTTP FX: {e_req}")
    except json.JSONDecodeError as e_json: print(f"  -> Error JSON FX: {e_json}")
    except Exception as e: print(f"  -> Error inesperado FX: {e}")
    if rate is not None: print(f"  -> Obtenido: {rate}")
    else: print(f"  -> Falló obtención.")
    fx_cache[cache_key] = (now, rate)
    return rate

# --- Funciones de Procesamiento de CSVs ---
# (Asegúrate de incluir aquí las versiones completas y funcionales de estas)
def process_uploaded_csvs(files):
    # ... (Código completo de la función como la teníamos antes) ...
    all_dfs = []; filenames_processed = []; errors = []
    if not files or all(f.filename == '' for f in files): errors.append("Error: No archivos seleccionados."); return None, None, errors
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not validate_filename_format(filename): errors.append(f"Advertencia: Archivo '{filename}' ignorado (formato AAAA.csv)."); continue
            df = None
            try: file.seek(0); df = pd.read_csv(io.BytesIO(file.read()), encoding='utf-8', sep=',', decimal='.', skiprows=0, header=0); print(f"Archivo '{filename}' leído UTF-8. Columnas: {df.columns.tolist()}")
            except UnicodeDecodeError:
                 try: file.seek(0); df = pd.read_csv(io.BytesIO(file.read()), encoding='latin-1', sep=',', decimal='.', skiprows=0, header=0); print(f"Archivo '{filename}' leído latin-1. Columnas: {df.columns.tolist()}")
                 except Exception as e: errors.append(f"Error leyendo '{filename}' (UTF8/Latin1): {e}"); continue
            except Exception as e: errors.append(f"Error leyendo '{filename}': {e}"); continue
            if df is not None:
                 missing = [col for col in COLS_MAP.keys() if col not in df.columns];
                 if missing: errors.append(f"Advertencia: Columnas faltantes en '{filename}': {missing}.")
                 df['source_file'] = filename; all_dfs.append(df); filenames_processed.append(filename)
        elif file.filename != '': errors.append(f"Advertencia: Archivo '{file.filename}' ignorado (no .csv).")
    if not all_dfs:
        if not any("Error:" in e for e in errors): errors.append("Error: No CSVs válidos procesados."); return None, None, errors
    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True); print(f"DF raw creado ({len(combined_df_raw)} filas).")
        if 'Fecha' in combined_df_raw.columns: combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
        if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
              try: temp_f = combined_df_raw['Fecha'].dt.strftime('%Y-%m-%d'); temp_h = combined_df_raw['Hora'].astype(str).str.strip(); combined_df_raw['FechaHora'] = pd.to_datetime(temp_f + ' ' + temp_h, errors='coerce')
              except Exception as e: print(f"Warn: No FechaHora: {e}"); combined_df_raw['FechaHora'] = combined_df_raw['Fecha']
        elif 'Fecha' in combined_df_raw.columns: combined_df_raw['FechaHora'] = combined_df_raw['Fecha']
        sort_col = 'FechaHora' if 'FechaHora' in combined_df_raw.columns else 'Fecha'
        if sort_col in combined_df_raw.columns: combined_df_raw = combined_df_raw.sort_values(by=sort_col, ascending=True, na_position='first')
    except Exception as e: errors.append(f"Error combinando/parseando fecha: {e}"); return None, None, errors
    df_for_portfolio_calc = combined_df_raw.copy()
    processed_df_for_csv = pd.DataFrame()
    try:
        cols_k = list(COLS_MAP.keys()); actual_c = combined_df_raw.columns.tolist(); cols_k = [c for c in cols_k if c in actual_c]
        if not cols_k: errors.append("Error: Ninguna columna original encontrada."); return None, df_for_portfolio_calc, errors
        filtered = combined_df_raw[cols_k].copy(); renamed = filtered.rename(columns=COLS_MAP); print(f"Cols renombradas CSV: {renamed.columns.tolist()}")
        if 'Bolsa' in renamed.columns: renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna(''); print("Col 'Exchange Yahoo' añadida.")
        else: renamed['Exchange Yahoo'] = ''; errors.append("Warn: No 'Bolsa' para 'Exchange Yahoo'.")
        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    cleaned = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False); renamed[col] = pd.to_numeric(cleaned, errors='coerce')
                if col == 'Cantidad':
                     if pd.api.types.is_numeric_dtype(renamed[col]): renamed[col] = renamed[col].abs()
                if pd.api.types.is_numeric_dtype(renamed[col]): renamed[col] = renamed[col].astype(float)
            else: errors.append(f"Warn: Col numérica '{col}' no existe.")
        processed_df_for_csv = renamed
    except KeyError as e: errors.append(f"Error proc CSV (KeyError): '{e}'."); return None, df_for_portfolio_calc, errors
    except Exception as e: errors.append(f"Error proc CSV: {e}"); return None, df_for_portfolio_calc, errors
    print(f"Proc base completado. DF CSV ({len(processed_df_for_csv)}), DF raw ({len(df_for_portfolio_calc)}).")
    return processed_df_for_csv, df_for_portfolio_calc, errors

def process_csvs_from_paths(list_of_file_paths):
    # ... (Código completo de la función como la teníamos antes) ...
    all_dfs = []; errors = []
    if not list_of_file_paths: errors.append("Error: No rutas."); return None, None, errors
    for filepath in list_of_file_paths:
        filename = os.path.basename(filepath); df = None
        try: df = pd.read_csv(filepath, encoding='utf-8', sep=',', decimal='.', skiprows=0, header=0); print(f"Archivo ruta '{filename}' UTF-8. Cols: {df.columns.tolist()}")
        except UnicodeDecodeError:
             try: df = pd.read_csv(filepath, encoding='latin-1', sep=',', decimal='.', skiprows=0, header=0); print(f"Archivo ruta '{filename}' latin-1. Cols: {df.columns.tolist()}")
             except Exception as e: errors.append(f"Error leyendo ruta '{filename}' (UTF8/Latin1): {e}"); continue
        except FileNotFoundError: errors.append(f"Error: Archivo no encontrado: {filepath}"); continue
        except Exception as e: errors.append(f"Error leyendo ruta '{filename}': {e}"); continue
        if df is not None:
             missing = [col for col in COLS_MAP.keys() if col not in df.columns];
             if missing: errors.append(f"Warn: Columnas faltantes ruta '{filename}': {missing}.")
             df['source_file'] = filename; all_dfs.append(df)
    if not all_dfs:
        if not any("Error:" in e for e in errors): errors.append("Error: No CSVs válidos desde ruta."); return None, None, errors
    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True); print(f"DF raw (ruta) creado ({len(combined_df_raw)} filas).")
        if 'Fecha' in combined_df_raw.columns: combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
        if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
              try: temp_f = combined_df_raw['Fecha'].dt.strftime('%Y-%m-%d'); temp_h = combined_df_raw['Hora'].astype(str).str.strip(); combined_df_raw['FechaHora'] = pd.to_datetime(temp_f + ' ' + temp_h, errors='coerce')
              except Exception as e: print(f"Warn: No FechaHora: {e}"); combined_df_raw['FechaHora'] = combined_df_raw['Fecha']
        elif 'Fecha' in combined_df_raw.columns: combined_df_raw['FechaHora'] = combined_df_raw['Fecha']
        sort_col = 'FechaHora' if 'FechaHora' in combined_df_raw.columns else 'Fecha'
        if sort_col in combined_df_raw.columns: combined_df_raw = combined_df_raw.sort_values(by=sort_col, ascending=True, na_position='first')
    except Exception as e: errors.append(f"Error combinando (ruta): {e}"); return None, None, errors
    df_for_portfolio_calc = combined_df_raw.copy()
    processed_df_for_csv = pd.DataFrame()
    try:
        cols_k = list(COLS_MAP.keys()); actual_c = combined_df_raw.columns.tolist(); cols_k = [c for c in cols_k if c in actual_c]
        if not cols_k: errors.append("Error: Ninguna col original (ruta)."); return None, df_for_portfolio_calc, errors
        filtered = combined_df_raw[cols_k].copy(); renamed = filtered.rename(columns=COLS_MAP); print(f"Cols renombradas CSV (ruta): {renamed.columns.tolist()}")
        if 'Bolsa' in renamed.columns: renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna(''); print("Col 'Exchange Yahoo' (ruta) añadida.")
        else: renamed['Exchange Yahoo'] = ''; errors.append("Warn: No 'Bolsa' para 'Exchange Yahoo' (ruta).")
        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    cleaned = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False); renamed[col] = pd.to_numeric(cleaned, errors='coerce')
                if col == 'Cantidad':
                     if pd.api.types.is_numeric_dtype(renamed[col]): renamed[col] = renamed[col].abs()
                if pd.api.types.is_numeric_dtype(renamed[col]): renamed[col] = renamed[col].astype(float)
            else: errors.append(f"Warn: Col numérica '{col}' no existe (ruta).")
        processed_df_for_csv = renamed
    except KeyError as e: errors.append(f"Error proc CSV (KeyError ruta): '{e}'."); return None, df_for_portfolio_calc, errors
    except Exception as e: errors.append(f"Error proc CSV (ruta): {e}"); return None, df_for_portfolio_calc, errors
    print(f"Proc base (ruta) completado. DF CSV, DF raw.")
    return processed_df_for_csv, df_for_portfolio_calc, errors


def calculate_portfolio(df_transacciones):
    # ... (Código completo de la función como la teníamos antes) ...
    print("Iniciando cálculo portfolio..."); required_cols = ["ISIN", "Producto", "Número", "Precio", "Valor local", "Bolsa de", "Unnamed: 8"]; sort_col = None
    if 'FechaHora' in df_transacciones.columns: required_cols.append('FechaHora'); sort_col = 'FechaHora'
    elif 'Fecha' in df_transacciones.columns: required_cols.append('Fecha'); sort_col = 'Fecha'
    missing = [c for c in required_cols if c not in df_transacciones.columns];
    if missing: print(f"Error: Faltan cols portfolio: {missing}"); return pd.DataFrame()
    existing_cols = [c for c in required_cols if c in df_transacciones.columns]; df = df_transacciones[existing_cols].copy()
    num_cols = ['Número', 'Precio', 'Valor local']
    for col in num_cols:
         if col in df.columns:
              if df[col].dtype == 'object': df[col] = df[col].astype(str).str.replace(',', '.', regex=False).str.strip()
              df[col] = pd.to_numeric(df[col], errors='coerce')
         else: print(f"Error: Falta col numérica {col}."); return pd.DataFrame()
    ess_cols = ['ISIN', 'Número', 'Precio', 'Valor local', 'Bolsa de', 'Unnamed: 8']
    existing_ess = [c for c in ess_cols if c in df.columns]; df = df.dropna(subset=existing_ess)
    if df.empty: print("No transacciones válidas tras limpiar NaNs."); return pd.DataFrame()
    portfolio = {}; print(f"Calculando portfolio sobre {len(df)} transacciones...")
    for isin, group in df.groupby('ISIN'):
        if sort_col and sort_col in group.columns: group = group.sort_values(by=sort_col, ascending=True, na_position='last')
        producto = group['Producto'].iloc[-1]; bolsa_de = group['Bolsa de'].iloc[-1]; price_currency = group['Unnamed: 8'].iloc[-1]
        col_qty = "Número"; compras = group[group[col_qty] > 0]; ventas = group[group[col_qty] < 0]
        qty_bought = compras[col_qty].sum(); qty_sold = ventas[col_qty].abs().sum(); qty_actual = qty_bought - qty_sold
        cost_pxq = 0
        if 'Precio' in compras.columns:
             if pd.api.types.is_numeric_dtype(compras[col_qty]) and pd.api.types.is_numeric_dtype(compras['Precio']): cost_pxq = (compras[col_qty] * compras['Precio'].abs()).sum()
        avg_buy_p = 0.0
        if qty_bought > 1e-9: avg_buy_p = cost_pxq / qty_bought
        if qty_actual > 1e-6:
            portfolio[isin] = {'ISIN': isin, 'Producto': producto, 'Bolsa de': bolsa_de, 'currency': price_currency, 'Cantidad Actual': round(qty_actual, 4), 'Precio Medio Compra': round(avg_buy_p, 4)}
    if not portfolio: print("Portfolio vacío.")
    else: print(f"Portfolio con {len(portfolio)} activos.")
    df_portfolio = pd.DataFrame.from_dict(portfolio, orient='index')
    if df_portfolio.empty: return df_portfolio
    if df_portfolio.index.name == 'ISIN': df_portfolio = df_portfolio.reset_index(drop=False)
    if 'index' in df_portfolio.columns and 'ISIN' in df_portfolio.columns and df_portfolio['ISIN'].equals(df_portfolio['index']): df_portfolio = df_portfolio.drop(columns=['index'])
    elif 'index' in df_portfolio.columns and 'ISIN' not in df_portfolio.columns: df_portfolio = df_portfolio.rename(columns={'index': 'ISIN'})
    if 'ISIN' not in df_portfolio.columns: print("Warn: ISIN no es columna."); # Podría intentar recuperarlo del índice si fuera necesario
    return df_portfolio

# --- Rutas Flask ---

# --- Rutas de Autenticación ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(username=form.username.data, password_hash=hashed_password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Crear categorías predeterminadas para el nuevo usuario
            create_default_expense_categories(user.id)
            
            flash('¡Cuenta creada correctamente! Ahora puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar usuario: {e}', 'danger')
            print(f"Error DB al registrar usuario: {e}")
            
    return render_template('register.html', title='Registro', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el inicio de sesión de usuarios."""
    if current_user.is_authenticated:
        # Limpiar sesión anterior por si ha habido cambio de usuario
        session.pop('portfolio_data', None)
        session.pop('csv_temp_file', None)
        
        # Si ya está logueado, redirigir a watchlist en lugar de index
        return redirect(url_for('show_watchlist'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            # Limpiar datos de sesión antiguos
            session.pop('portfolio_data', None)
            session.pop('csv_temp_file', None)
            
            # Iniciar sesión de usuario
            login_user(user, remember=form.remember_me.data)
            
            # CARGAR PORTFOLIO CACHEADO DEL USUARIO CORRECTO
            portfolio_data, csv_data, csv_filename = load_user_portfolio(user.id)
            if portfolio_data:
                # Guardar en sesión para mostrar directamente
                session['portfolio_data'] = portfolio_data
                if csv_filename:
                    session['csv_temp_file'] = csv_filename
                flash('Datos de portfolio cargados de la sesión anterior.', 'success')
            
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/login') and not next_page.startswith('/register'):
                return redirect(next_page)
            else:
                return redirect(url_for('financial_summary'))
        else:
            flash('Inicio de sesión fallido. Verifica usuario y contraseña.', 'danger')
    
    return render_template('login.html', title='Iniciar Sesión', form=form)


# 2. AÑADIR NUEVA RUTA PARA ACTUALIZAR SOLO PRECIOS
@app.route('/update_portfolio_prices')
@login_required
def update_portfolio_prices():
    """Actualiza solo los precios del portfolio existente sin subir nuevos CSVs."""
    # Primero, comprobar si hay portfolio en la sesión o en la BD
    portfolio_data = session.get('portfolio_data')
    if not portfolio_data:
        portfolio_data, _, _ = load_user_portfolio(current_user.id)
        if not portfolio_data:
            flash("No hay datos de portfolio para actualizar. Por favor, carga tus CSVs primero.", "warning")
            return redirect(url_for('index'))
    
    # Convertir a DataFrame si es una lista de diccionarios
    if isinstance(portfolio_data, list):
        import pandas as pd
        portfolio_df = pd.DataFrame(portfolio_data)
    else:
        flash("Error al procesar datos de portfolio. Formato incorrecto.", "danger")
        return redirect(url_for('show_portfolio'))
    
    # Cargar mapeo de ISIN a tickers
    mapping_data = load_mapping()
    
    # Buscar watchlist items para este usuario
    watchlist_items = WatchlistItem.query.filter_by(user_id=current_user.id, is_in_portfolio=True).all()
    watchlist_isin_map = {item.isin: item for item in watchlist_items if item.isin}
    
    # Crear portfolio enriquecido
    enriched_portfolio_data = []
    total_market_value_eur = 0.0
    total_cost_basis_eur_est = 0.0
    total_pl_eur_est = 0.0
    
    # Variables para contar actualizaciones
    precios_actualizados = 0
    precios_fallidos = 0
    
    print(f"Actualizando precios para {len(portfolio_df)} items del portfolio...")
    for _, row in portfolio_df.iterrows():
        new_item = row.to_dict()
        isin = new_item.get('ISIN')
        
        # Obtener datos desde el mapeo y la watchlist
        ticker_base = None
        yahoo_suffix = None
        
        # Primero intentar obtener desde watchlist
        if isin in watchlist_isin_map:
            ticker_base = watchlist_isin_map[isin].ticker
            yahoo_suffix = watchlist_isin_map[isin].yahoo_suffix
            
        # Si no está en watchlist, intentar desde el mapeo global
        if (not ticker_base or not yahoo_suffix) and isin in mapping_data:
            ticker_base = mapping_data[isin].get('ticker')
            yahoo_suffix = mapping_data[isin].get('yahoo_suffix', '')
        
        # Si no tenemos ticker, mantener el precio anterior si existe
        if not ticker_base:
            precios_fallidos += 1
            if 'current_price_local' in new_item:
                print(f"  No se encontró ticker para {isin}, manteniendo precio anterior: {new_item['current_price_local']}")
            else:
                print(f"  No se encontró ticker para {isin}, no se puede obtener precio")
            enriched_portfolio_data.append(new_item)
            continue
        
        # Obtener precio actualizado - FORZANDO ACTUALIZACIÓN DESDE YAHOO
        yahoo_ticker = f"{ticker_base}{yahoo_suffix}"
        current_price = get_current_price(yahoo_ticker, force_update=True)
        
        if current_price is not None:
            precios_actualizados += 1
            new_item['current_price_local'] = current_price
            print(f"  Precio actualizado para {isin} ({yahoo_ticker}): {current_price}")
            
            # Calcular resto de valores (copiado de show_portfolio)
            qty = new_item.get('Cantidad Actual')
            avg_buy_price = new_item.get('Precio Medio Compra')
            original_currency = new_item.get('currency')
            
            if original_currency and qty is not None and pd.notna(qty) and avg_buy_price is not None and pd.notna(avg_buy_price):
                price_to_convert = current_price
                avg_buy_price_for_calc = float(avg_buy_price)
                currency_to_convert = original_currency.upper()

                if original_currency == 'GBX':
                    price_to_convert = price_to_convert / 100.0
                    avg_buy_price_for_calc = avg_buy_price_for_calc / 100.0
                    currency_to_convert = 'GBP'

                exchange_rate = get_exchange_rate(currency_to_convert, 'EUR')
                new_item['exchange_rate_to_eur'] = exchange_rate

                if exchange_rate is not None and pd.notna(exchange_rate):
                    # Calcular Coste Estimado EUR
                    try:
                        cost_basis_eur_est = float(qty) * avg_buy_price_for_calc * float(exchange_rate)
                        if pd.notna(cost_basis_eur_est):
                            total_cost_basis_eur_est += cost_basis_eur_est
                            new_item['cost_basis_eur_est'] = cost_basis_eur_est
                    except Exception as e:
                        print(f"Error cálculo coste EUR para {isin}: {e}")
                        new_item['cost_basis_eur_est'] = None

                    # Calcular Valor Mercado EUR
                    if price_to_convert is not None and pd.notna(price_to_convert):
                        try:
                            market_value_local_adjusted = float(qty) * float(price_to_convert)
                            new_item['market_value_local_adj'] = market_value_local_adjusted
                            if exchange_rate is not None and pd.notna(exchange_rate) and pd.notna(market_value_local_adjusted):
                                market_value_eur = market_value_local_adjusted * float(exchange_rate)
                                if pd.notna(market_value_eur):
                                    total_market_value_eur += market_value_eur
                                    new_item['market_value_eur'] = market_value_eur
                        except Exception as e:
                            print(f"Error cálculo valor mercado {isin}: {e}")
                            new_item['market_value_eur'] = None

                    # Calcular G/P Estimada EUR
                    if new_item.get('market_value_eur') is not None and new_item.get('cost_basis_eur_est') is not None:
                        pl_eur_est = new_item['market_value_eur'] - new_item['cost_basis_eur_est']
                        if pd.notna(pl_eur_est):
                            total_pl_eur_est += pl_eur_est
                            new_item['pl_eur_est'] = pl_eur_est
        else:
            precios_fallidos += 1
            print(f"  No se pudo obtener precio para {isin} ({yahoo_ticker})")
        
        enriched_portfolio_data.append(new_item)
    
    # Actualizar portfolio en sesión y en la BD
    session['portfolio_data'] = enriched_portfolio_data
    save_user_portfolio(
        user_id=current_user.id,
        portfolio_data=enriched_portfolio_data,
        csv_data=None,  # No modificamos CSV data
        csv_filename=session.get('csv_temp_file')  # Mantener filename si existe
    )
    
    # Mensaje de confirmación
    if precios_actualizados > 0:
        flash(f"Precios actualizados: {precios_actualizados} acciones. Fallos: {precios_fallidos}", "success")
    else:
        flash(f"No se pudo actualizar ningún precio. Revisa tu portfolio.", "warning")
    
    return redirect(url_for('show_portfolio'))

@app.route('/logout')
@login_required
def logout():
    # Limpiar los datos de la sesión antes de cerrar sesión
    session.pop('portfolio_data', None)
    session.pop('csv_temp_file', None)
    session.pop('missing_isins_for_mapping', None)
    session.pop('temp_csv_pending_filename', None)
    session.pop('temp_portfolio_pending_filename', None)
    
    # Cerrar sesión
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

# --- Rutas Principales de la Aplicación ---
# En app.py
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    """
    Maneja la subida de archivos (POST) o carga desde ruta, procesa,
    calcula portfolio, comprueba mapeo global, sincroniza watchlist DB
    (con logging de error mejorado), y redirige. Muestra form (GET).
    """
    if request.method == 'POST':
        input_method = request.form.get('input_method')
        processed_data = None
        errors_pre_process = []

        # --- Determinar método y procesar archivos ---
        if input_method == 'upload':
            print("Procesando método: upload")
            if 'csv_files[]' not in request.files:
                flash('Error: No parte archivo.', 'danger')
                return redirect(request.url)
            
            files = request.files.getlist('csv_files[]')
            if not files or all(f.filename == '' for f in files):
                flash('Error: No archivos.', 'danger')
                return redirect(request.url)
            
            processed_data = process_uploaded_csvs(files)
            
        elif input_method == 'path':
            # ... [Código para método path sin cambios] ...
            pass
        else:
            flash('Error: Método entrada no válido.', 'danger')
            return redirect(request.url)

        # --- Procesamiento Común Post-Carga/Lectura ---
        if errors_pre_process:
            for msg in errors_pre_process:
                flash(msg, 'danger' if 'Error:' in msg else 'warning')
            if any("Error:" in e for e in errors_pre_process) or processed_data is None:
                return redirect(url_for('index'))

        # Desempaquetado y checks básicos
        try:
            processed_df_for_csv, combined_df_raw, errors_process = processed_data
        except (TypeError, ValueError) as e_unpack:
            print(f"ERROR FATAL: No se pudo desempaquetar processed_data. Error: {e_unpack}")
            flash("Error interno inesperado (Ref: UNPACK_FAIL).", "danger")
            session.clear()
            return redirect(url_for('index'))

        if errors_process:
            for msg in errors_process:
                flash(msg, 'danger' if "Error:" in msg else ('warning' if "Advertencia:" in msg else 'info'))

        if combined_df_raw is None or combined_df_raw.empty:
            flash('No se pudieron procesar los datos base necesarios.', 'warning')
            return redirect(url_for('index'))

        # Calcular Portfolio
        portfolio_df = calculate_portfolio(combined_df_raw)

        # --- SINCRONIZAR PORTFOLIO CALCULADO CON WATCHLIST EN DB --- ### BLOQUE CON ERROR LOGGING MEJORADO ###
        if portfolio_df is not None:
            print(f"Sincronizando portfolio ({len(portfolio_df)} items) con watchlist DB para usuario {current_user.id}...")
            mapping_data_sync = load_mapping() # Cargar mapeo para obtener Ticker/Nombre/etc.
            try:
                # 1. Obtener watchlist actual de la DB
                current_db_watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
                db_isin_map = {item.isin: item for item in current_db_watchlist if item.isin}
                print(f" Encontrados {len(current_db_watchlist)} items en watchlist DB.")

                # 2. Obtener ISINs del nuevo portfolio
                new_portfolio_isins = set(portfolio_df['ISIN'].dropna().unique())
                print(f" ISINs en nuevo portfolio: {len(new_portfolio_isins)}")

                # 3. Actualizar items existentes en DB
                items_to_commit = [] # Lista para guardar objetos modificados
                for item_db in current_db_watchlist:
                    isin = item_db.isin
                    is_now_in_portfolio = isin in new_portfolio_isins
                    needs_update = False

                    if is_now_in_portfolio:
                        if not item_db.is_in_portfolio: # Si antes no estaba y ahora sí
                            print(f"  -> Marcar {isin} EN portfolio (in_portfolio=True, in_followup=False)")
                            item_db.is_in_portfolio = True
                            item_db.is_in_followup = False
                            needs_update = True
                        # Si ya estaba, no cambiamos flags (a menos que fuera manual?) -> Podríamos resetear is_in_followup aquí? Por ahora no.
                        new_portfolio_isins.discard(isin) # Quitar de pendientes a añadir
                    else: # No está en el portfolio actual
                        if item_db.is_in_portfolio: # Pero sí estaba antes
                            print(f"  -> Marcar {isin} FUERA portfolio (in_portfolio=False, in_followup=True)")
                            item_db.is_in_portfolio = False
                            item_db.is_in_followup = True # Pasa a seguimiento manual/histórico
                            needs_update = True

                    if needs_update:
                        items_to_commit.append(item_db) # Añadir a sesión si cambió

                # 4. Añadir items nuevos del portfolio que no estaban en la DB
                print(f" ISINs nuevos a añadir a watchlist DB: {len(new_portfolio_isins)}")
                for isin_to_add in new_portfolio_isins:
                    portfolio_row = portfolio_df[portfolio_df['ISIN'] == isin_to_add].iloc[0]
                    map_info = mapping_data_sync.get(isin_to_add, {})
                    ticker = map_info.get('ticker', 'N/A')
                    google_ex = map_info.get('google_ex', None)
                    name = map_info.get('name', portfolio_row.get('Producto', 'Desconocido')).strip()
                    if not name: name = portfolio_row.get('Producto', 'Desconocido')
                    # Derivar sufijo Yahoo usando el mapa global y la bolsa original
                    degiro_bolsa_code = portfolio_row.get('Bolsa de')
                    yahoo_suffix = BOLSA_TO_YAHOO_MAP.get(degiro_bolsa_code, '') if degiro_bolsa_code else ''

                    print(f"  -> Añadiendo nuevo item {isin_to_add} ({ticker}{yahoo_suffix}) a DB (portfolio=True, followup=False)")
                    new_watch_item = WatchlistItem(
                        item_name=name, isin=isin_to_add, ticker=ticker,
                        yahoo_suffix=yahoo_suffix, google_ex=google_ex,
                        user_id=current_user.id,
                        is_in_portfolio=True, # Está en el portfolio actual
                        is_in_followup=False   # No está (aún) en seguimiento manual
                    )
                    db.session.add(new_watch_item) # Añadir nuevo a sesión

                # 5. Guardar todos los cambios en la base de datos
                if items_to_commit or new_portfolio_isins: # Solo hacer commit si hubo cambios o añadidos
                     db.session.commit()
                     print("Sincronización watchlist DB completada.")
                else:
                     print("No hubo cambios necesarios en la sincronización de watchlist DB.")

            except Exception as e_sync: # Capturar cualquier error durante la sincronización
                db.session.rollback() # MUY IMPORTANTE: Deshacer cambios parciales
                # --- LOGGING DE ERROR MEJORADO ---
                print(f"!!!!!!!! ERROR DURANTE SINCRONIZACIÓN WATCHLIST DB !!!!!!!!")
                print(f"Error específico: {e_sync}")
                print("--- Traceback Completo del Error de Sincronización ---")
                traceback.print_exc() # Imprime el traceback completo a la consola
                print("-----------------------------------------------------")
                flash("Error Interno al actualizar la watchlist con el portfolio. Revisa logs.", "danger")
                # Considerar si continuar o no. Por ahora continuamos.
            # --- FIN BLOQUE TRY/EXCEPT SYNC ---
        else:
            print("Portfolio vacío o no calculado, no se sincroniza watchlist.")
        # --- FIN BLOQUE SINCRONIZACIÓN ---


        # --- Cargar Mapeo GLOBAL y Comprobar ISINs Faltantes (sin cambios aquí) ---
        mapping_data = load_mapping()
        missing_isins_details = []
        if portfolio_df is not None and not portfolio_df.empty:
             all_isins_in_portfolio = portfolio_df['ISIN'].unique()
             for isin in all_isins_in_portfolio:
                map_entry = mapping_data.get(isin);
                if not map_entry or not map_entry.get('ticker') or map_entry.get('yahoo_suffix') is None or not map_entry.get('google_ex'):
                     p_row = portfolio_df.loc[portfolio_df['ISIN'] == isin].iloc[0]
                     p_name = p_row.get('Producto', 'Desconocido'); bolsa_c = p_row.get('Bolsa de', None)
                     missing_isins_details.append({'isin': isin, 'name': p_name, 'bolsa_de': bolsa_c})

        # --- Decisión: Continuar o Pedir Mapeo GLOBAL ---
        if not missing_isins_details:
            # --- CASO 1: No faltan mapeos GLOBALES ---
            print("No faltan mapeos globales. Preparando CSV final y redirect a portfolio...")
            temp_csv_filename = None
            # ... (Enriquecer CSV, guardar CSV temporal final, guardar nombre en session['csv_temp_file']) ...
            if processed_df_for_csv is not None and not processed_df_for_csv.empty:
                try:
                    processed_df_for_csv['Ticker'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('ticker', ''))
                    processed_df_for_csv['Exchange Google'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('google_ex', ''))
                    cols_final = [c for c in FINAL_COLS_ORDERED if c in processed_df_for_csv.columns];
                    if 'Ticker' not in cols_final and 'Ticker' in processed_df_for_csv.columns: cols_final.insert(FINAL_COLS_ORDERED.index('Ticker'), 'Ticker')
                    if 'Exchange Google' not in cols_final and 'Exchange Google' in processed_df_for_csv.columns: cols_final.insert(FINAL_COLS_ORDERED.index('Exchange Google'), 'Exchange Google')
                    cols_final = [c for c in cols_final if c in processed_df_for_csv.columns]; processed_df_for_csv = processed_df_for_csv.reindex(columns=cols_final, fill_value='')
                    uid = uuid.uuid4(); temp_csv_filename = f"processed_{uid}.csv"; path = os.path.join(OUTPUT_FOLDER, temp_csv_filename); processed_df_for_csv.to_csv(path, index=False, sep=';', decimal='.', encoding='utf-8-sig'); session['csv_temp_file'] = temp_csv_filename; print(f"CSV final guardado: {path}")
                except Exception as e: flash(f"Error guardando CSV final: {e}", "danger"); session.pop('csv_temp_file', None)
            else: session.pop('csv_temp_file', None)
        # Guardar portfolio_df en sesión para mostrar en /portfolio
        if portfolio_df is not None and not portfolio_df.empty:
            # Convertir DataFrame a lista de diccionarios para JSON
            portfolio_list = []
            for _, row in portfolio_df.iterrows():
                # Crear un diccionario con valores serializables
                row_dict = {}
                for col, value in row.items():
                    if pd.isna(value):
                        row_dict[col] = None
                    elif isinstance(value, (np.int64, np.int32)):
                        row_dict[col] = int(value)
                    elif isinstance(value, (np.float64, np.float32)):
                        row_dict[col] = float(value)
                    elif isinstance(value, (datetime, date, pd.Timestamp)):
                        row_dict[col] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                    else:
                        row_dict[col] = value
                portfolio_list.append(row_dict)
            
            # Verificar que se puede serializar
            try:
                json.dumps(portfolio_list)
                print("✓ Portfolio válido para JSON")
            except Exception as e_json:
                print(f"⚠️ ERROR: Portfolio no válido para JSON: {e_json}")
                # Intento de corrección básica
                for item in portfolio_list:
                    for key, value in list(item.items()):
                        if not isinstance(value, (str, int, float, bool, type(None))):
                            item[key] = str(value)
            
            # Guardar en sesión y BD
            session['portfolio_data'] = portfolio_list
            
            # También guardar CSV si existe
            temp_csv_filename = None
            csv_data_list = None
            if processed_df_for_csv is not None and not processed_df_for_csv.empty:
                try:
                    # Convertir DF a lista para guardar
                    csv_data_list = []
                    for _, row in processed_df_for_csv.iterrows():
                        row_dict = {}
                        for col, value in row.items():
                            if pd.isna(value):
                                row_dict[col] = None
                            elif isinstance(value, (np.int64, np.int32)):
                                row_dict[col] = int(value)
                            elif isinstance(value, (np.float64, np.float32)):
                                row_dict[col] = float(value)
                            elif isinstance(value, (datetime, date, pd.Timestamp)):
                                row_dict[col] = value.isoformat() if hasattr(value, 'isoformat') else str(value)
                            else:
                                row_dict[col] = value
                        csv_data_list.append(row_dict)
                    
                    # Guardar archivo CSV temporal
                    uid = uuid.uuid4()
                    temp_csv_filename = f"processed_{uid}.csv"
                    path = os.path.join(OUTPUT_FOLDER, temp_csv_filename)
                    processed_df_for_csv.to_csv(path, index=False, sep=';', decimal='.', encoding='utf-8-sig')
                    session['csv_temp_file'] = temp_csv_filename
                    print(f"CSV final guardado: {path}")
                except Exception as e:
                    flash(f"Error guardando CSV final: {e}", "danger")
                    session.pop('csv_temp_file', None)
                    temp_csv_filename = None
            else:
                session.pop('csv_temp_file', None)
            
            # Guardar en BD
            save_success = save_user_portfolio(
                user_id=current_user.id,
                portfolio_data=portfolio_list,
                csv_data=csv_data_list,
                csv_filename=temp_csv_filename
            )
            
            if save_success:
                print("Datos de portfolio guardados en BD")
                flash('Archivos procesados y watchlist sincronizada.', 'success')
            else:
                print("⚠️ ERROR: No se pudo guardar el portfolio en BD")
                flash('Archivos procesados, pero hubo un error al guardar en la base de datos.', 'warning')
        else:
            session.pop('portfolio_data', None)
            print("Warn: Portfolio vacío, no guardado.")
            flash('Archivos procesados. Portfolio vacío.', 'info')

        # Redirigir a show_portfolio
        return redirect(url_for('show_portfolio'))

    # --- Manejo GET ---
    return render_template('index.html')

# --- NUEVA RUTA: Gestionar Mapeo Global ---
@app.route('/manage_mapping')
@login_required # Proteger para que solo usuarios logueados accedan
def manage_mapping():
    """Muestra el contenido del mapeo global y prepara la interfaz de gestión."""
    print("--- Dentro de manage_mapping ---")
    # Cargar los datos actuales del archivo JSON
    mapping_data = load_mapping() # Devuelve un diccionario {ISIN: {detalles}}

    # Convertir el diccionario a una lista de diccionarios para la plantilla
    # Cada item de la lista representará una fila de la tabla
    mapping_list = []
    for isin, details in mapping_data.items():
        item_dict = {'isin': isin} # Añadir el ISIN como un campo más
        item_dict.update(details)  # Copiar el resto de detalles (ticker, name, etc.)
        mapping_list.append(item_dict)

    # Ordenar la lista por defecto (ej: por ISIN o Ticker) para una vista consistente
    # Ordenamos por ticker (insensible a mayúsculas/minúsculas), luego por ISIN
    mapping_list.sort(key=lambda x: (x.get('ticker', '').lower(), x.get('isin', '')))
    print(f" Mapeo global cargado con {len(mapping_list)} entradas.")

    # Renderizar la nueva plantilla, pasando la lista de mapeos
    return render_template(
        'manage_mapping.html',
        mappings=mapping_list,
        title="Gestionar Mapeo Global" # Título para la pestaña del navegador
    )


# En app.py
# Asegúrate de tener imports: request, flash, redirect, url_for, login_required
# Y las funciones: load_mapping, save_mapping

@app.route('/update_mapping_entry', methods=['POST'])
@login_required
def update_mapping_entry():
    """Actualiza una entrada existente en el mapeo global."""
    try:
        isin_to_update = request.form.get('isin')
        if not isin_to_update:
            flash("Error: No se recibió el ISIN para actualizar.", "danger")
            return redirect(url_for('manage_mapping'))

        print(f"Recibida petición para actualizar mapeo de ISIN: {isin_to_update}")

        # Cargar mapeo actual
        mapping_data = load_mapping()

        # Verificar que el ISIN existe en el mapeo
        if isin_to_update not in mapping_data:
            flash(f"Error: El ISIN '{isin_to_update}' no se encontró en el mapeo global.", "danger")
            return redirect(url_for('manage_mapping'))

        # Obtener los nuevos valores del formulario (usando el ISIN en el name)
        # Usar .get() por si algún campo no se envía, aunque los inputs existen
        new_ticker = request.form.get(f'ticker_{isin_to_update}', '').strip().upper()
        new_name = request.form.get(f'name_{isin_to_update}', '').strip()
        new_yahoo_suffix = request.form.get(f'yahoo_suffix_{isin_to_update}', '').strip()
        new_google_ex = request.form.get(f'google_ex_{isin_to_update}', '').strip().upper()

        # Validar datos mínimos (ej: ticker y google exchange no pueden quedar vacíos)
        if not new_ticker or not new_google_ex:
             flash(f"Error: El Ticker Base y el Google Exchange no pueden estar vacíos para {isin_to_update}.", "danger")
             return redirect(url_for('manage_mapping'))

        # Actualizar el diccionario en memoria
        mapping_data[isin_to_update] = {
            "ticker": new_ticker,
            "name": new_name,
            "yahoo_suffix": new_yahoo_suffix,
            "google_ex": new_google_ex
        }
        print(f" Mapeo para {isin_to_update} actualizado en memoria: {mapping_data[isin_to_update]}")

        # Guardar el diccionario completo de vuelta al archivo JSON
        save_mapping(mapping_data) # Esta función ya tiene manejo de errores y flash

        flash(f"Mapeo para ISIN {isin_to_update} actualizado correctamente.", "success")

    except Exception as e:
        flash(f"Error inesperado al actualizar el mapeo: {e}", "danger")
        print(f"Error inesperado en update_mapping_entry: {e}")

    # Redirigir siempre de vuelta a la página de gestión
    return redirect(url_for('manage_mapping'))


@app.route('/update_watchlist_comment', methods=['POST'])
@login_required
def update_watchlist_comment():
    """Actualiza el campo comentario de un item específico de la watchlist."""
    item_id = request.form.get('item_id')
    new_comment = request.form.get('comentario', '').strip() # Obtener y limpiar comentario

    if not item_id:
        flash("Error: No se recibió el ID del item para actualizar comentario.", "danger")
        return redirect(url_for('show_watchlist'))

    print(f"Recibida petición para actualizar comentario de item ID: {item_id}")
    try:
        # Buscar el item por ID Y asegurarse que pertenece al usuario logueado
        item = WatchlistItem.query.filter_by(id=item_id, user_id=current_user.id).first()

        if item:
            # Límite de texto razonable para evitar problemas de almacenamiento
            if len(new_comment) > 10000:
                new_comment = new_comment[:10000]  # Límite de 10,000 caracteres
                
            item.comentario = new_comment # Actualizar el campo comentario
            db.session.commit() # Guardar el cambio en la base de datos
            flash(f"Comentario para '{item.item_name}' actualizado.", "success")
            print(f" Comentario para item {item_id} actualizado.")
        else:
            # Item no encontrado o no pertenece al usuario
            flash("Error: No se encontró el item a actualizar o no tienes permiso.", "warning")
            print(f" Intento de actualizar comentario fallido, item {item_id} no encontrado / no pertenece a user {current_user.id}")

    except Exception as e:
        db.session.rollback()
        flash(f"Error al actualizar comentario: {e}", "danger")
        print(f"Error DB al actualizar comentario watchlist item {item_id}: {e}")

    # Redirigir siempre de vuelta a la watchlist
    return redirect(url_for('show_watchlist'))


# En app.py
# Imports necesarios: jsonify (de flask), login_required, current_user, WatchlistItem

from flask import jsonify # Asegúrate de tener esta importación

# ... resto de imports, app, db, modelos, otras rutas ...



@app.route('/delete_mapping_entry', methods=['POST'])
@login_required
def delete_mapping_entry():
    """Elimina una entrada del mapeo global (mapping_db.json)."""
    isin_to_delete = request.form.get('isin_to_delete')
    print(f"Recibida petición para BORRAR mapeo de ISIN: {isin_to_delete}")

    if not isin_to_delete:
        flash("Error: No se recibió el ISIN para borrar.", "danger")
        return redirect(url_for('manage_mapping'))

    # Cargar mapeo actual
    mapping_data = load_mapping()

    # Verificar que el ISIN existe y eliminarlo
    if isin_to_delete in mapping_data:
        try:
            del mapping_data[isin_to_delete] # Eliminar la entrada del diccionario
            print(f" Mapeo para {isin_to_delete} eliminado de memoria.")
            # Guardar el diccionario modificado de vuelta al archivo JSON
            save_mapping(mapping_data) # Esta función ya tiene manejo de errores y flash
            flash(f"Mapeo para ISIN {isin_to_delete} eliminado correctamente.", "success")
        except Exception as e:
             flash(f"Error al intentar guardar el mapeo después de borrar {isin_to_delete}: {e}", "danger")
             print(f"Error al guardar mapeo tras borrado: {e}")
    else:
        # Si el ISIN no estaba en el diccionario
        flash(f"Error: El ISIN '{isin_to_delete}' no se encontró en el mapeo global para borrar.", "warning")
        print(f" Intento de borrado fallido, ISIN no encontrado: {isin_to_delete}")


    # Redirigir siempre de vuelta a la página de gestión
    return redirect(url_for('manage_mapping'))

# En app.py

# En app.py
# Asegúrate de tener imports: request, flash, redirect, url_for, login_required
# Y las funciones: load_mapping, save_mapping

@app.route('/add_mapping_entry', methods=['POST'])
@login_required
def add_mapping_entry():
    """Añade una nueva entrada al mapeo global (mapping_db.json)."""
    try:
        # Obtener datos del nuevo formulario
        new_isin = request.form.get('new_isin', '').strip().upper()
        new_ticker = request.form.get('new_ticker', '').strip().upper()
        new_name = request.form.get('new_name', '').strip()
        new_yahoo_suffix = request.form.get('new_yahoo_suffix', '').strip()
        new_google_ex = request.form.get('new_google_ex', '').strip().upper()

        # Validar campos obligatorios
        if not new_isin or not new_ticker or not new_google_ex:
            flash("Error: ISIN, Ticker Base y Google Exchange son obligatorios para añadir un nuevo mapeo.", "danger")
            return redirect(url_for('manage_mapping'))

        # Cargar mapeo actual
        mapping_data = load_mapping()

        # Comprobar si el ISIN ya existe
        if new_isin in mapping_data:
            flash(f"Error: El ISIN '{new_isin}' ya existe en el mapeo. Edita la entrada existente si es necesario.", "warning")
            return redirect(url_for('manage_mapping'))

        # Añadir la nueva entrada al diccionario
        mapping_data[new_isin] = {
            "ticker": new_ticker,
            "name": new_name,
            "yahoo_suffix": new_yahoo_suffix,
            "google_ex": new_google_ex
        }
        print(f"Añadiendo nuevo mapeo para ISIN: {new_isin} -> {mapping_data[new_isin]}")

        # Guardar el diccionario completo de vuelta al archivo JSON
        save_mapping(mapping_data) # Maneja errores internos y flash

        flash(f"Nuevo mapeo para ISIN {new_isin} añadido correctamente.", "success")

    except Exception as e:
        flash(f"Error inesperado al añadir la nueva entrada al mapeo: {e}", "danger")
        print(f"Error inesperado en add_mapping_entry: {e}")

    # Redirigir siempre de vuelta a la página de gestión
    return redirect(url_for('manage_mapping'))


@app.route('/complete_mapping', methods=['GET'])
@login_required
def complete_mapping():
    """
    Muestra el formulario para completar mapeos globales de ISIN faltantes.
    Pasa sugerencias de sufijo Yahoo a la plantilla.
    """
    # Recuperar lista de diccionarios con ISIN, Name, Bolsa de
    missing_isins_details = session.get('missing_isins_for_mapping')

    if not missing_isins_details:
        flash("No hay mapeos pendientes para completar.", "warning")
        return redirect(url_for('index')) # O a show_portfolio si es más apropiado

    # Añadir sugerencia de sufijo Yahoo a cada item
    for item in missing_isins_details:
        degiro_bolsa_code = item.get('bolsa_de')
        suggested_suffix = BOLSA_TO_YAHOO_MAP.get(degiro_bolsa_code, '') if degiro_bolsa_code else ''
        item['suggested_yahoo_suffix'] = suggested_suffix

    # Pasar la lista de diccionarios (ahora con sugerencia) a la plantilla
    return render_template(
        'complete_mapping.html',
        missing_items=missing_isins_details
        # Ya no es necesario pasar bolsa_to_yahoo_map si precalculamos la sugerencia
    )


@app.route('/save_mapping', methods=['POST'])
@login_required
def save_mapping_route():
    """
    Guarda los mapeos globales introducidos, carga DFs temporales,
    SINCRONIZA watchlist DB, enriquece CSV, guarda resultados finales y redirige.
    """
    print("--- Dentro de save_mapping_route ---")
    # --- Recuperar datos pendientes de sesión ---
    missing_isins_details = session.get('missing_isins_for_mapping', [])
    temp_csv_filename = session.get('temp_csv_pending_filename')
    temp_portfolio_filename = session.get('temp_portfolio_pending_filename') # Nombre archivo portfolio pendiente

    # Limpiar sesión
    session.pop('missing_isins_for_mapping', None)
    session.pop('temp_csv_pending_filename', None)
    session.pop('temp_portfolio_pending_filename', None)
    print(f"Recuperado: {len(missing_isins_details)} ISINs, CSV: {temp_csv_filename}, Portfolio: {temp_portfolio_filename}")

    # --- Cargar DFs desde archivos temporales ---
    processed_df_for_csv = pd.DataFrame()
    portfolio_df = pd.DataFrame() # <<< DataFrame del portfolio calculado previamente
    load_error = False
    # ... (Código para cargar processed_df_for_csv desde temp_csv_filename como antes) ...
    if temp_csv_filename:
        path = os.path.join(OUTPUT_FOLDER, temp_csv_filename)
        try:
            if os.path.exists(path): df_csv = pd.read_json(path, orient='records', lines=True); print(f"CSV cargado: {path}"); os.remove(path); print(f"CSV temp elim."); processed_df_for_csv = df_csv
            else: print(f"Error: Temp CSV no: {path}"); error = True
        except Exception as e: print(f"Error cargando CSV: {e}"); error = True
    else: print("Warn: No temp CSV.")
    # --- Cargar portfolio_df desde temp_portfolio_filename --- ### NUEVO / RE-AÑADIDO ###
    if temp_portfolio_filename:
        temp_portfolio_path = os.path.join(OUTPUT_FOLDER, temp_portfolio_filename)
        try:
            if os.path.exists(temp_portfolio_path):
                portfolio_df = pd.read_json(temp_portfolio_path, orient='records', lines=True) # Cargar aquí
                print(f"DF de Portfolio cargado desde: {temp_portfolio_path} ({len(portfolio_df)} filas)")
                os.remove(temp_portfolio_path) # Eliminar archivo temporal
                print(f"Archivo temporal Portfolio pendiente eliminado.")
            else:
                 print(f"Error: Archivo temporal de Portfolio no encontrado: {temp_portfolio_path}")
                 load_error = True
        except Exception as e_load_port:
            print(f"Error CRÍTICO al cargar DF de Portfolio desde {temp_portfolio_path}: {e_load_port}")
            load_error = True
    else:
         print("Advertencia: No había nombre de archivo temporal de Portfolio en sesión.")
         # Si no había portfolio pendiente, ¿qué hacemos? Podríamos continuar sin él,
         # pero la sincronización y la vista de portfolio no funcionarán bien.
         # Mejor considerar esto un error si esperábamos un portfolio.
         if missing_isins_details: # Si estábamos completando mapeo, deberíamos tener portfolio
             load_error = True


    if load_error:
         flash("Error al recuperar datos temporales pendientes. Vuelve a subir.", "danger")
         return redirect(url_for('index'))

    # --- Procesar formulario y actualizar mapping_db.json (como antes) ---
    mapping_data = load_mapping()
    updated_count = 0
    if missing_isins_details:
         print(f"Procesando form para {len(missing_isins_details)} ISINs...")
         # ... (lógica para actualizar mapping_data como antes, rellenando huecos) ...
         for item in missing_isins_details:
            isin = item['isin']; ticker = request.form.get(f'ticker_{isin}'); google_ex = request.form.get(f'google_ex_{isin}'); yahoo_s = request.form.get(f'yahoo_suffix_{isin}', ''); name = request.form.get(f'name_{isin}', item.get('name', ''))
            if ticker and google_ex: # Ticker y GoogleEx son mínimos para un mapeo útil
               if isin in mapping_data: # Actualizar existente si faltan campos
                   upd = False; current = mapping_data[isin]; t_clean = ticker.strip().upper(); g_clean = google_ex.strip().upper(); y_clean = yahoo_s.strip(); n_clean = name.strip()
                   if not current.get('ticker') and t_clean: mapping_data[isin]['ticker'] = t_clean; upd = True
                   if not current.get('google_ex') and g_clean: mapping_data[isin]['google_ex'] = g_clean; upd = True
                   if current.get('yahoo_suffix') is None or (not current.get('yahoo_suffix') and y_clean): mapping_data[isin]['yahoo_suffix'] = y_clean; upd = True
                   if not current.get('name') and n_clean: mapping_data[isin]['name'] = n_clean; upd = True
                   if upd: updated_count += 1; print(f"  Mapeo existente ACTUALIZADO {isin}")
                   else: print(f"  Mapeo {isin} ya completo.")
               else: # Añadir nuevo
                   mapping_data[isin] = {"ticker": ticker.strip().upper(), "google_ex": google_ex.strip().upper(), "yahoo_suffix": yahoo_s.strip(), "name": name.strip()}; updated_count += 1; print(f"  Mapeo NUEVO añadido {isin}")
            else: print(f"Warn: Datos incompletos form {isin}"); flash(f"Datos incompletos {isin} ({item.get('name', isin)}).", "warning")

    # Guardar mapeo actualizado si hubo cambios
    if updated_count > 0:
        save_mapping(mapping_data)
        flash(f"Guardados {updated_count} mapeos globales.", "success")
        mapping_data = load_mapping() # Recargar por si acaso
    elif missing_isins_details:
         flash("No se guardó ningún mapeo global nuevo.", "info")


    # --- SINCRONIZAR WATCHLIST DB (AHORA que mapping_data está actualizado) --- ### NUEVO BLOQUE ###
    if portfolio_df is not None and not portfolio_df.empty: # Sincronizar solo si tenemos portfolio cargado
        print(f"Sincronizando portfolio ({len(portfolio_df)} items) con watchlist DB TRAS GUARDAR MAPEO...")
        try:
            # La lógica es idéntica a la del bloque de sincronización en la ruta index (POST)
            current_db_watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
            db_isin_map = {item.isin: item for item in current_db_watchlist if item.isin}
            new_portfolio_isins = set(portfolio_df['ISIN'].dropna().unique())

            # 1. Actualizar existentes
            for item_db in current_db_watchlist:
                isin = item_db.isin; is_now = isin in new_portfolio_isins
                if is_now:
                    if not item_db.is_in_portfolio: print(f"  -> Marcar {isin} EN portfolio"); item_db.is_in_portfolio = True; item_db.is_in_followup = False
                    new_portfolio_isins.discard(isin)
                else:
                    if item_db.is_in_portfolio: print(f"  -> Marcar {isin} FUERA portfolio (manual=True)"); item_db.is_in_portfolio = False; item_db.is_manual = True # Corrección: debería ser is_in_followup = True

            # 2. Añadir nuevos
            print(f" ISINs nuevos a añadir: {len(new_portfolio_isins)}")
            for isin_to_add in new_portfolio_isins:
                portfolio_row = portfolio_df[portfolio_df['ISIN'] == isin_to_add].iloc[0]
                map_info = mapping_data.get(isin_to_add, {}) # Usar mapping_data actualizado
                ticker = map_info.get('ticker', 'N/A'); yahoo_suffix = map_info.get('yahoo_suffix', ''); google_ex = map_info.get('google_ex', None); name = map_info.get('name', portfolio_row.get('Producto', '???')).strip();
                if not name: name = portfolio_row.get('Producto', '???')
                print(f"  -> Añadiendo {isin_to_add} ({ticker}{yahoo_suffix}) a DB (portfolio=True, followup=False)")
                new_watch_item = WatchlistItem(item_name=name, isin=isin_to_add, ticker=ticker, yahoo_suffix=yahoo_suffix, google_ex=google_ex, user_id=current_user.id, is_manual=False, is_in_portfolio=True) # Corrección: usar is_in_followup=False
                db.session.add(new_watch_item)

            # 3. Guardar cambios DB
            db.session.commit()
            print("Sincronización watchlist DB (tras mapeo) completada.")

        except Exception as e_sync:
            db.session.rollback()
            print(f"Error durante sincronización watchlist DB (tras mapeo): {e_sync}")
            flash("Error al actualizar la watchlist tras guardar mapeo.", "danger")
    else:
        print("Advertencia: No hay datos de portfolio cargados para sincronizar watchlist después de guardar mapeo.")
    # --- FIN BLOQUE SINCRONIZACIÓN ---


    # --- Preparar y guardar CSV FINAL (como antes) ---
    temp_csv_filename_final = None
    if processed_df_for_csv is not None and not processed_df_for_csv.empty:
        # ... (Enriquecer y guardar CSV final en session['csv_temp_file']) ...
        print("Enriqueciendo y guardando CSV final...")
        try:
            processed_df_for_csv['Ticker'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('ticker', ''))
            processed_df_for_csv['Exchange Google'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('google_ex', ''))
            cols_final = [c for c in FINAL_COLS_ORDERED if c in processed_df_for_csv.columns];
            if 'Ticker' not in cols_final and 'Ticker' in processed_df_for_csv.columns: cols_final.insert(FINAL_COLS_ORDERED.index('Ticker'), 'Ticker')
            if 'Exchange Google' not in cols_final and 'Exchange Google' in processed_df_for_csv.columns: cols_final.insert(FINAL_COLS_ORDERED.index('Exchange Google'), 'Exchange Google')
            cols_final = [c for c in cols_final if c in processed_df_for_csv.columns]; processed_df_for_csv = processed_df_for_csv.reindex(columns=cols_final, fill_value='')
            uid_f = uuid.uuid4(); temp_csv_filename_final = f"processed_{uid_f}.csv"; path_f = os.path.join(OUTPUT_FOLDER, temp_csv_filename_final); processed_df_for_csv.to_csv(path_f, index=False, sep=';', decimal='.', encoding='utf-8-sig'); session['csv_temp_file'] = temp_csv_filename_final; print(f"CSV final guardado: {path_f}")
        except Exception as e: flash(f"Error guardando CSV final: {e}", "danger"); session.pop('csv_temp_file', None)
    else: print("Warn: No datos CSV final."); session.pop('csv_temp_file', None)


    # --- Guardar portfolio (cargado de temp) en sesión para mostrar ---
    if portfolio_df is not None and not portfolio_df.empty:
         session['portfolio_data'] = portfolio_df.to_dict('records')
         # Guardar en base de datos para persistencia entre sesiones
         save_user_portfolio(
            user_id=current_user.id,
            portfolio_data=portfolio_df.to_dict('records'),
            csv_data=processed_df_for_csv.to_dict('records') if processed_df_for_csv is not None else None,
            csv_filename=temp_csv_filename_final)
         print("Datos de portfolio puestos en sesión para visualización.")
    else:
         session.pop('portfolio_data', None)
         print("Advertencia: No hay datos de portfolio (o error carga) para poner en sesión.")

    # Redirigir finalmente a la vista del portfolio
    print("Redirigiendo a show_portfolio...")
    return redirect(url_for('show_portfolio'))


@app.route('/portfolio')
@login_required
def show_portfolio():
    """
    Muestra la página con el resumen de la cartera, usando precios cacheados.
    """
    print(f"Iniciando show_portfolio para usuario: {current_user.id}")
    
    # Inicializar variables
    portfolio_data_list = None
    temp_filename = None
    csv_existe = False
    last_updated = None
    enriched_portfolio_data = []
    total_market_value_eur = 0.0
    total_cost_basis_eur_est = 0.0
    total_pl_eur_est = 0.0

    # PASO 1: Intentar obtener datos de la sesión
    if 'portfolio_data' in session:
        portfolio_data_list = session.get('portfolio_data')
        temp_filename = session.get('csv_temp_file')
        csv_existe = bool(temp_filename)
        print(f"Datos encontrados en sesión: {len(portfolio_data_list) if portfolio_data_list else 0} items")

    # PASO 2: Si no hay datos en sesión, intentar cargar desde la BD
    if not portfolio_data_list:
        print(f"Cargando datos de la base de datos para usuario: {current_user.id}")
        try:
            # Obtener registro completo para tener la fecha de actualización
            portfolio_record = UserPortfolio.query.filter_by(user_id=current_user.id).first()
            if portfolio_record:
                if portfolio_record.portfolio_data:
                    try:
                        # Cargar datos JSON
                        portfolio_data_list = json.loads(portfolio_record.portfolio_data)
                        print(f"Datos cargados de BD: {len(portfolio_data_list) if portfolio_data_list else 0} items")
                        
                        # Verificar que es una lista de diccionarios
                        if not isinstance(portfolio_data_list, list):
                            portfolio_data_list = []
                        
                        # Actualizar sesión
                        session['portfolio_data'] = portfolio_data_list
                        
                        # Obtener nombre de archivo CSV si existe
                        if portfolio_record.csv_filename:
                            temp_filename = portfolio_record.csv_filename
                            session['csv_temp_file'] = temp_filename
                            csv_existe = True
                        
                        # Obtener fecha de actualización
                        if portfolio_record.last_updated:
                            last_updated = portfolio_record.last_updated.strftime("%d/%m/%Y %H:%M")
                            
                    except json.JSONDecodeError as e:
                        print(f"Error al decodificar JSON del portfolio: {e}")
                        portfolio_data_list = []
                else:
                    print("No hay datos de portfolio en la BD")
            else:
                print("No se encontró registro de portfolio para el usuario")
        except Exception as e:
            print(f"Error general al cargar portfolio de la BD: {e}")
            import traceback
            traceback.print_exc()

    # PASO 3: Procesar datos del portfolio si existen
    if portfolio_data_list:
        print(f"Procesando {len(portfolio_data_list)} items del portfolio")
        mapping_data = load_mapping()
        
        for item in portfolio_data_list:
            # Crear copia para evitar modificar el original en sesión
            try:
                new_item = item.copy() if isinstance(item, dict) else dict(item)
                
                # Acumular totales con datos existentes (sin recalcular)
                if 'market_value_eur' in new_item and new_item.get('market_value_eur') is not None:
                    try:
                        total_market_value_eur += float(new_item['market_value_eur'])
                    except (ValueError, TypeError):
                        pass
                
                if 'cost_basis_eur_est' in new_item and new_item.get('cost_basis_eur_est') is not None:
                    try:
                        total_cost_basis_eur_est += float(new_item['cost_basis_eur_est'])
                    except (ValueError, TypeError):
                        pass
                
                if 'pl_eur_est' in new_item and new_item.get('pl_eur_est') is not None:
                    try:
                        total_pl_eur_est += float(new_item['pl_eur_est'])
                    except (ValueError, TypeError):
                        pass
                
                enriched_portfolio_data.append(new_item)
            except Exception as e:
                print(f"Error procesando item del portfolio: {e}")
                continue
            
        print(f"Portfolio procesado: {len(enriched_portfolio_data)} items válidos")
    else:
        print("No hay datos de portfolio para mostrar")
        # Si no hay datos, crear un array vacío para la plantilla
        enriched_portfolio_data = []

    # Renderizar plantilla
    return render_template(
        'portfolio.html',
        portfolio=enriched_portfolio_data,
        temp_csv_file_exists=csv_existe,
        total_value_eur=total_market_value_eur,
        total_pl_eur=total_pl_eur_est,
        last_updated=last_updated
    )


@app.route('/download_csv')
@login_required
def download_csv():
    """Permite descargar el CSV unificado procesado."""
    temp_fn = session.get('csv_temp_file')
    
    if not temp_fn:
        # Si no está en sesión, intentar cargar de la base de datos
        _, csv_data, temp_fn = load_user_portfolio(current_user.id)
        if not temp_fn or not csv_data:
            flash("Error: No hay referencia a archivo CSV para descargar.", "danger")
            return redirect(url_for('show_portfolio'))
    
    # Comprobar si existe en disco
    fpath = os.path.join(OUTPUT_FOLDER, temp_fn)
    if os.path.exists(fpath):
        # Si existe en disco, enviarlo como antes
        try:
            return send_file(fpath, mimetype='text/csv', as_attachment=True, download_name=OUTPUT_FILENAME)
        except Exception as e:
            flash(f"Error enviando CSV: {e}", "danger")
            return redirect(url_for('show_portfolio'))
    else:
        # Si no existe en disco pero tenemos los datos en DB, generar archivo al vuelo
        _, csv_data, _ = load_user_portfolio(current_user.id)
        if csv_data:
            # Crear un archivo temporal con los datos
            temp_path = os.path.join(OUTPUT_FOLDER, f"temp_{uuid.uuid4()}.csv")
            try:
                # Convertir dict a DataFrame
                df = pd.DataFrame(csv_data)
                # Guardar como CSV
                df.to_csv(temp_path, index=False, sep=';', decimal='.', encoding='utf-8-sig')
                # Enviar el archivo
                return send_file(temp_path, mimetype='text/csv', as_attachment=True, download_name=OUTPUT_FILENAME)
            except Exception as e:
                flash(f"Error generando CSV desde datos guardados: {e}", "danger")
                return redirect(url_for('show_portfolio'))
            finally:
                # Intentar eliminar el archivo temporal después de enviarlo
                # (esto puede no ejecutarse si hay errores en send_file)
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass
        else:
            flash("Error: No se encontraron datos para generar el CSV.", "danger")
            return redirect(url_for('show_portfolio'))


@app.route('/watchlist')
@login_required
def show_watchlist():
    """
    Muestra la watchlist de DB, usando precios cacheados sin actualización automática.
    """
    print("--- Dentro de show_watchlist ---")
    enriched_watchlist = []

    # 1. Obtener TODOS los items de la watchlist desde la DB (ordenados)
    try:
        all_items_db = WatchlistItem.query.filter_by(user_id=current_user.id)\
                        .order_by(WatchlistItem.is_in_portfolio.desc(), WatchlistItem.item_name.asc())\
                        .all()
        print(f"Items cargados de watchlist DB para user {current_user.id}: {len(all_items_db)}")
    except Exception as e_db:
        print(f"Error al consultar watchlist en DB: {e_db}")
        flash("Error al cargar la watchlist desde la base de datos.", "danger")
        all_items_db = []

    # 2. Enriquecer la lista (pero SIN obtener nuevos precios)
    if all_items_db:
        print(f"Enriqueciendo {len(all_items_db)} items de watchlist DB con precios cacheados...")
        today = date.today()

        for item_db in all_items_db:
            # Convertir objeto DB a diccionario base
            new_item = {
                'id': item_db.id, 'item_name': item_db.item_name, 'isin': item_db.isin,
                'ticker': item_db.ticker, 'yahoo_suffix': item_db.yahoo_suffix,
                'google_ex': item_db.google_ex, 'is_in_portfolio': item_db.is_in_portfolio,
                'is_in_followup': item_db.is_in_followup,
                'fecha_resultados_obj': item_db.fecha_resultados,
                'fecha_resultados': item_db.fecha_resultados.strftime('%Y-%m-%d') if item_db.fecha_resultados else None,
                'pais': item_db.pais, 'sector': item_db.sector, 'industria': item_db.industria,
                'market_cap': item_db.market_cap,
                'ceo_salary': item_db.ceo_salary, 'dilucion_shares': item_db.dilucion_shares,
                'ntm_ps': item_db.ntm_ps, 'ntm_tev_ebitda': item_db.ntm_tev_ebitda,
                'ntm_pe': item_db.ntm_pe, 'ntm_div_yield': item_db.ntm_div_yield,
                'ltm_pbv': item_db.ltm_pbv, 'revenue_cagr': item_db.revenue_cagr,
                'ebitda_margins': item_db.ebitda_margins, 'eps_normalized': item_db.eps_normalized,
                'fcf_margins': item_db.fcf_margins, 'cfo': item_db.cfo,
                'net_debt_ebitda': item_db.net_debt_ebitda, 'roe': item_db.roe,
                'pe_objetivo': item_db.pe_objetivo, 'eps_5y': item_db.eps_5y,
                'price_5y': item_db.price_5y, 'riesgo': item_db.riesgo,
                'stake': item_db.stake, 'movimiento': item_db.movimiento,
                'comentario': item_db.comentario,
                'auto_update_pais': item_db.auto_update_pais,
                'auto_update_sector': item_db.auto_update_sector,
                'auto_update_industria': item_db.auto_update_industria,
                'auto_update_market_cap': item_db.auto_update_market_cap,
                'auto_update_pe': item_db.auto_update_pe,
                'auto_update_div_yield': item_db.auto_update_div_yield,
                'auto_update_pbv': item_db.auto_update_pbv,
                'auto_update_roe': item_db.auto_update_roe,
                'yahoo_last_updated': item_db.yahoo_last_updated,
                # NUEVO: Añadir info sobre precio cacheado y su fecha
                'cached_price_date': item_db.cached_price_date
            }

            # --- Calcular Estado Agregado de 'Yahoo Synch' ---
            auto_update_flags = [
                item_db.auto_update_pais, item_db.auto_update_sector, item_db.auto_update_industria,
                item_db.auto_update_market_cap, item_db.auto_update_pe, item_db.auto_update_div_yield,
                item_db.auto_update_pbv, item_db.auto_update_roe
            ]
            all_auto_updates_enabled = all(flag for flag in auto_update_flags)
            new_item['all_auto_updates_enabled'] = all_auto_updates_enabled

            # --- USAR PRECIO CACHEADO en lugar de consultar Yahoo ---
            current_price = None
            
            # Primero intentar usar el precio almacenado en la BD
            if hasattr(item_db, 'cached_price') and item_db.cached_price is not None:
                current_price = item_db.cached_price
                print(f"  Usando precio cacheado en BD para {item_db.ticker}: {current_price}")
            else:
                # Si no hay precio en la BD, intentar usar el caché global
                ticker_base = new_item.get('ticker', 'N/A')
                yahoo_suffix = new_item.get('yahoo_suffix', '')
                
                if ticker_base != 'N/A' and ticker_base:
                    yahoo_ticker = f"{ticker_base}{yahoo_suffix}"
                    if yahoo_ticker in price_cache:
                        timestamp, price = price_cache[yahoo_ticker]
                        current_price = price
                        print(f"  Usando precio del caché global para {yahoo_ticker}: {price}")
                        
                        # Guardar en la BD para futuras consultas
                        if hasattr(item_db, 'cached_price'):
                            item_db.cached_price = price
                            item_db.cached_price_date = datetime.fromtimestamp(timestamp)
                            try:
                                db.session.commit()
                                print(f"  Guardado precio en BD para {yahoo_ticker}")
                            except Exception as e_save:
                                db.session.rollback()
                                print(f"  Error guardando precio en BD: {e_save}")
            
            new_item['current_price'] = current_price

            # --- Calcular Campos Derivados como antes ---
            # Esta lógica no cambia, ya que no depende de actualizar precios
            eps_yield_calc = None
            profitability_calc = None
            eps_norm = new_item.get('eps_normalized')
            eps_5y = new_item.get('eps_5y')
            
            if eps_norm is not None and eps_5y is not None and pd.notna(eps_norm) and pd.notna(eps_5y):
                try:
                    if eps_norm > 0 and eps_5y > 0: 
                        eps_yield_calc = (((float(eps_5y) / float(eps_norm)) ** (1/5)) - 1) * 100
                    elif eps_norm == 0 and eps_5y > 0: 
                        eps_yield_calc = float('inf')
                    else: 
                        eps_yield_calc = 0.0 if eps_norm == 0 and eps_5y == 0 else None
                except Exception as e: 
                    eps_yield_calc = None
            
            new_item['eps_yield_calc'] = eps_yield_calc

            div_yield = new_item.get('ntm_div_yield')
            if eps_yield_calc is not None and eps_yield_calc != float('inf') and div_yield is not None and pd.notna(div_yield):
                try: 
                    profitability_calc = float(eps_yield_calc) + float(div_yield)
                except Exception: 
                    profitability_calc = None
                    
            new_item['profitability_calc'] = profitability_calc

            # --- Determinar Clases CSS de BACKGROUND ---
            # Igual que antes...
            profit_bg_class = ''
            if profitability_calc is not None and pd.notna(profitability_calc):
                if profitability_calc >= 15: 
                    profit_bg_class = 'bg-success'
                elif profitability_calc >= 10: 
                    profit_bg_class = 'bg-warning'
                elif profitability_calc >= 7.5: 
                    profit_bg_class = 'bg-warning'
                else: 
                    profit_bg_class = 'bg-danger'
                    
            new_item['profit_bg_class'] = profit_bg_class

            # Para Fecha Resultados
            fecha_res_obj = new_item.get('fecha_resultados_obj')
            fecha_res_bg_class = ''
            
            if fecha_res_obj:
                try:
                    delta_days = (fecha_res_obj - today).days
                    if delta_days > 7: 
                        fecha_res_bg_class = 'bg-success'
                    elif delta_days >= 0: 
                        fecha_res_bg_class = 'bg-warning'
                    elif delta_days >= -15: 
                        fecha_res_bg_class = 'bg-warning'
                    else: 
                        fecha_res_bg_class = 'bg-danger'
                except Exception as e_date: 
                    print(f"Error procesando fecha {fecha_res_obj}: {e_date}")
                    fecha_res_bg_class = ''
                    
            new_item['fecha_res_bg_class'] = fecha_res_bg_class

            enriched_watchlist.append(new_item)
    else:
        print("Watchlist de DB está vacía para este usuario.")

    # 3. Renderizar Plantilla
    print(f"--- Fin show_watchlist: Renderizando plantilla con {len(enriched_watchlist)} items ---")
    return render_template('watchlist.html', watchlist_items=enriched_watchlist)


@app.route('/edit_watchlist_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_watchlist_item(item_id):
    """
    Muestra el formulario para editar un item específico de la watchlist (GET)
    o procesa los datos enviados para actualizarlo (POST).
    """
    # Buscar el item específico por ID y asegurarse que pertenece al usuario actual
    item_to_edit = WatchlistItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()

    # Si es POST (se envió el formulario de edición)
    if request.method == 'POST':
        print(f"Procesando POST para editar item ID: {item_id}")
        try:
            # Actualizar todos los campos manuales/opcionales desde el formulario
            # Procesar flags de actualización automática primero (excepto fecha)
            # Eliminamos auto_update_date ya que ahora la fecha siempre es manual
            item_to_edit.auto_update_pais = 'auto_update_pais' in request.form
            item_to_edit.auto_update_sector = 'auto_update_sector' in request.form
            item_to_edit.auto_update_industria = 'auto_update_industria' in request.form
            item_to_edit.auto_update_market_cap = 'auto_update_market_cap' in request.form
            item_to_edit.auto_update_pe = 'auto_update_pe' in request.form
            item_to_edit.auto_update_div_yield = 'auto_update_div_yield' in request.form
            item_to_edit.auto_update_pbv = 'auto_update_pbv' in request.form
            item_to_edit.auto_update_roe = 'auto_update_roe' in request.form

            # Convertir fechas y números donde sea necesario
            fecha_str = request.form.get('fecha_resultados')
            if fecha_str:
                # Fecha siempre manual ahora
                try:
                    item_to_edit.fecha_resultados = pd.to_datetime(fecha_str).date()
                except:
                    print(f"Error al convertir fecha: {fecha_str}")
                    # Mantener fecha anterior en caso de error

            # Solo actualizar campos si no están en modo auto
            if not item_to_edit.auto_update_pais:
                item_to_edit.pais = request.form.get('pais', '').strip()

            if not item_to_edit.auto_update_sector:
                item_to_edit.sector = request.form.get('sector', '').strip()

            if not item_to_edit.auto_update_industria:
                item_to_edit.industria = request.form.get('industria', '').strip()

            # Campos normales (no afectados por auto-actualización)
            item_to_edit.ceo_salary = request.form.get('ceo_salary')

            # Convertir números Float, manejar errores
            def get_float_or_none(form_field_name):
                val_str = request.form.get(form_field_name)
                if val_str is None or val_str.strip() == '': return None
                try: return float(val_str.replace(',', '.')) # Reemplazar coma por punto
                except ValueError: return None # Devolver None si no es un número válido

            # Campos con auto-actualización
            if not item_to_edit.auto_update_market_cap:
                item_to_edit.market_cap = get_float_or_none('market_cap')

            if not item_to_edit.auto_update_pe:
                item_to_edit.ntm_pe = get_float_or_none('ntm_pe')

            if not item_to_edit.auto_update_div_yield:
                item_to_edit.ntm_div_yield = get_float_or_none('ntm_div_yield')

            if not item_to_edit.auto_update_pbv:
                item_to_edit.ltm_pbv = get_float_or_none('ltm_pbv')

            if not item_to_edit.auto_update_roe:
                item_to_edit.roe = get_float_or_none('roe')

            # Campos normales (no afectados por auto-actualización)
            item_to_edit.dilucion_shares = get_float_or_none('dilucion_shares')
            item_to_edit.ntm_ps = get_float_or_none('ntm_ps')
            item_to_edit.ntm_tev_ebitda = get_float_or_none('ntm_tev_ebitda')
            item_to_edit.revenue_cagr = get_float_or_none('revenue_cagr')
            item_to_edit.ebitda_margins = get_float_or_none('ebitda_margins')
            item_to_edit.eps_normalized = get_float_or_none('eps_normalized')
            item_to_edit.fcf_margins = get_float_or_none('fcf_margins')

            # Actualizar el campo CFO que ahora es un select con opciones Positivo(1)/Neutral(0)/Negativo(-1)
            cfo_value = request.form.get('cfo')
            if cfo_value in ['1', '0', '-1']:
                item_to_edit.cfo = int(cfo_value)
            else:
                item_to_edit.cfo = None  # Si no se seleccionó ninguna opción

            item_to_edit.net_debt_ebitda = get_float_or_none('net_debt_ebitda')
            item_to_edit.pe_objetivo = get_float_or_none('pe_objetivo')
            item_to_edit.eps_5y = get_float_or_none('eps_5y')

            # Obtener price_5y desde el formulario (ahora es un campo oculto)
            item_to_edit.price_5y = get_float_or_none('price_5y')

            # Calcular price_5y automáticamente si tenemos los valores necesarios
            # y no hay un valor explícito en el formulario
            pe_objetivo = item_to_edit.pe_objetivo
            eps_5y = item_to_edit.eps_5y

            if pe_objetivo is not None and eps_5y is not None and item_to_edit.price_5y is None:
                item_to_edit.price_5y = pe_objetivo * eps_5y
                print(f"Price 5Y calculado automáticamente: {item_to_edit.price_5y} (PE:{pe_objetivo} * EPS:{eps_5y})")

            # El campo riesgo ahora almacena el valor de upside calculado por JavaScript
            item_to_edit.riesgo = get_float_or_none('riesgo')
            item_to_edit.stake = get_float_or_none('stake') # Viene del select numérico

            item_to_edit.movimiento = request.form.get('movimiento') # Viene del select
            item_to_edit.comentario = request.form.get('comentario', '').strip()

            # Guardar cambios en la DB
            db.session.commit()
            flash(f"Datos para '{item_to_edit.item_name}' actualizados correctamente.", "success")
            print(f"Item watchlist ID {item_id} actualizado en DB.")
            # Redirigir de vuelta a la watchlist
            return redirect(url_for('show_watchlist'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar los datos: {e}", "danger")
            print(f"Error DB al actualizar watchlist item {item_id}: {e}")
            # Volver a mostrar el formulario de edición con los datos actuales (no los fallidos)
            return render_template('edit_watchlist_item.html', item=item_to_edit, title=f"Editar {item_to_edit.item_name}")

    # Si es GET: Mostrar el formulario con los datos actuales del item
    print(f"Mostrando formulario de edición para item ID: {item_id}")
    return render_template('edit_watchlist_item.html', item=item_to_edit, title=f"Editar {item_to_edit.item_name}")


@app.route('/update_watchlist_yahoo_data', methods=['GET'])
@login_required
def update_watchlist_yahoo_data():
    """Actualiza los datos de la watchlist desde Yahoo Finance."""
    start_time = time.time()
    
    # Obtener el ID de ítem específico si existe en la URL
    item_id = request.args.get('item_id')
    
    try:
        if item_id:
            # Actualizar solo un ítem específico
            success, message = update_watchlist_item_from_yahoo(item_id, force_update=True)
            if success:
                flash(f"Datos de Yahoo Finance actualizados correctamente: {message}", "success")
            else:
                flash(f"Error al actualizar datos de Yahoo Finance: {message}", "warning")
            
            # Si venimos de la edición, volver a ella
            return redirect(url_for('edit_watchlist_item', item_id=item_id))
        else:
            # Actualizar todos los items
            results = update_all_watchlist_items_from_yahoo(current_user.id, force_update=True)
            
            # Mostrar mensaje de éxito/fallo
            if results['success'] > 0:
                flash(f"Actualizados {results['success']} de {results['total']} items con datos de Yahoo Finance.", "success")
            
            if results['failed'] > 0:
                flash(f"No se pudieron actualizar {results['failed']} items. Revise la consola para detalles.", "warning")
                
            # Log detallado
            for msg in results['messages']:
                print(msg)
                
            # Tiempo total que tomó la actualización
            elapsed_time = time.time() - start_time
            print(f"Actualización completada en {elapsed_time:.2f} segundos")
                
    except Exception as e:
        flash(f"Error durante la actualización de datos: {e}", "danger")
        print(f"Error en update_watchlist_yahoo_data: {e}")
    
    # Redireccionar a la watchlist
    return redirect(url_for('show_watchlist'))


@app.route('/add_watchlist_item', methods=['POST'])
@login_required
def add_watchlist_item():
    """
    Añade un nuevo item manual a la watchlist del usuario (tabla WatchlistItem)
    Y TAMBIÉN intenta añadir/actualizar la entrada en el mapeo global (mapping_db.json).
    """
    item_added_to_db = False # Flag para saber si se añadió a la watchlist personal
    new_item_name_for_flash = "Elemento" # Nombre por defecto para mensaje flash

    try:
        # --- 1. Recuperar y Validar Datos del Formulario ---
        name = request.form.get('item_name')
        isin = request.form.get('isin')
        ticker = request.form.get('ticker')
        yahoo_suffix = request.form.get('yahoo_suffix', '')
        google_ex = request.form.get('google_ex')

        # Limpiar y normalizar datos
        name_clean = name.strip() if name else ''
        isin_clean = isin.strip().upper() if isin else None
        ticker_clean = ticker.strip().upper() if ticker else None
        yahoo_s_clean = yahoo_suffix.strip() # Puede ser vacío
        google_ex_clean = google_ex.strip().upper() if google_ex else None

        # Validación básica (nombre y ticker son obligatorios en el form)
        if not name_clean or not ticker_clean:
            flash("El Nombre y el Ticker Base son obligatorios.", "warning")
            return redirect(url_for('show_watchlist'))
        # Guardar nombre para mensaje flash
        new_item_name_for_flash = name_clean

        # --- 2. Guardar en la Watchlist Personal del Usuario (DB) ---
        # Comprobar si ya existe por ISIN para este usuario (si ISIN fue proporcionado)
        existing_item_in_db = None
        if isin_clean:
            existing_item_in_db = WatchlistItem.query.filter_by(user_id=current_user.id, isin=isin_clean).first()

        if existing_item_in_db:
            flash(f"Ya existe un item con ISIN {isin_clean} en tu watchlist personal.", "info")
            print(f"Intento de añadir duplicado manual por ISIN: {isin_clean} para user {current_user.id}")
        else:
            # Crear nuevo objeto WatchlistItem con flags manuales
            print(f"Añadiendo item manual a DB: Ticker={ticker_clean}, Suffix={yahoo_s_clean}, GoogleEx={google_ex_clean}")
            new_db_item = WatchlistItem(
                item_name=name_clean,
                isin=isin_clean,
                ticker=ticker_clean,
                yahoo_suffix=yahoo_s_clean,
                google_ex=google_ex_clean,
                user_id=current_user.id,
                is_in_portfolio=False, # Estado inicial manual
                is_in_followup=True    # Estado inicial manual
            )
            db.session.add(new_db_item)
            db.session.commit() # Guardar en la DB del usuario
            item_added_to_db = True # Marcar que se añadió a la DB
            print(f"Añadido item manual a watchlist DB: {new_db_item}")
            # No poner flash aquí todavía, esperar a ver si se actualiza el global

    except Exception as e_db:
        db.session.rollback()
        flash(f"Error al añadir item a tu watchlist personal: {e_db}", "danger")
        print(f"Error DB al añadir watchlist item: {e_db}")
        # Si falla aquí, no intentamos actualizar el global y redirigimos
        return redirect(url_for('show_watchlist'))


    # --- 3. Intentar Añadir/Actualizar Mapeo Global (mapping_db.json) ---
    # Hacer esto SOLO si se añadió bien a la DB personal Y si tenemos los datos clave
    mapping_updated = False
    if item_added_to_db and isin_clean and ticker_clean and google_ex_clean:
        print(f"Intentando actualizar mapeo global para ISIN: {isin_clean}")
        try:
            mapping_data = load_mapping()
            needs_saving = False

            if isin_clean not in mapping_data:
                # ISIN es nuevo globalmente -> Añadir entrada completa
                mapping_data[isin_clean] = {
                    "ticker": ticker_clean,
                    "name": name_clean, # Usar nombre proporcionado
                    "yahoo_suffix": yahoo_s_clean,
                    "google_ex": google_ex_clean
                }
                needs_saving = True
                mapping_updated = True # Indicar que se añadió
                print(f" -> ISIN nuevo, añadiendo a mapping_db.json")
            else:
                # ISIN ya existe -> Actualizar SOLO campos vacíos/faltantes
                current_entry = mapping_data[isin_clean]
                updated_entry = False
                print(f" -> ISIN existente, comprobando campos faltantes...")
                # Usar .get() para seguridad
                if not current_entry.get('ticker') and ticker_clean:
                    mapping_data[isin_clean]['ticker'] = ticker_clean; updated_entry = True; print("    -> Actualizando ticker global")
                if not current_entry.get('google_ex') and google_ex_clean:
                    mapping_data[isin_clean]['google_ex'] = google_ex_clean; updated_entry = True; print("    -> Actualizando google_ex global")
                # Actualizar sufijo si estaba ausente o vacío y el nuevo no lo es
                if current_entry.get('yahoo_suffix') is None or (not current_entry.get('yahoo_suffix') and yahoo_s_clean):
                    mapping_data[isin_clean]['yahoo_suffix'] = yahoo_s_clean; updated_entry = True; print("    -> Actualizando yahoo_suffix global")
                 # Actualizar nombre solo si estaba vacío y el nuevo no lo está
                if not current_entry.get('name') and name_clean:
                    mapping_data[isin_clean]['name'] = name_clean; updated_entry = True; print("    -> Actualizando name global")

                if updated_entry:
                    needs_saving = True
                    mapping_updated = True # Indicar que se actualizó
                    print(f" -> Mapeo global existente ACTUALIZADO para {isin_clean}")
                else:
                     print(f" -> Mapeo global para {isin_clean} ya estaba completo.")

            # Guardar si hubo cambios
            if needs_saving:
                save_mapping(mapping_data) # save_mapping ya maneja errores y flash

        except Exception as e_map:
             # Si falla la actualización del global, al menos el item se guardó en la watchlist personal
             print(f"Error al intentar actualizar mapping_db.json: {e_map}")
             flash("Se añadió el item a tu watchlist, pero hubo un error al actualizar el mapeo global.", "warning")

    # --- 4. Mensaje Flash Final y Redirección ---
    if item_added_to_db:
        if mapping_updated:
             flash(f"'{new_item_name_for_flash}' añadido a watchlist. Mapeo global también actualizado/añadido.", "success")
        else:
             flash(f"'{new_item_name_for_flash}' añadido a watchlist.", "success") # Solo mensaje de watchlist

    return redirect(url_for('show_watchlist'))

# --- Nuevos Modelos para las Funcionalidades Adicionales ---

class FixedIncome(db.Model):
    """Modelo para almacenar los ingresos fijos (salario) del usuario."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    annual_net_salary = db.Column(db.Float, nullable=True)  # Salario neto anual
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('fixed_income', uselist=False))

class BrokerOperation(db.Model):
    """Modelo para almacenar operaciones de ingreso/retirada del broker."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    operation_type = db.Column(db.String(20), nullable=False)  # 'Ingreso', 'Retirada', 'Comisión'
    concept = db.Column(db.String(50), nullable=False)  # 'Inversión', 'Dividendos', 'Desinversión', etc.
    amount = db.Column(db.Float, nullable=False)  # Cantidad (positiva para ingresos, negativa para retiradas/comisiones)
    description = db.Column(db.Text, nullable=True)  # Descripción opcional
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('broker_operations', lazy='dynamic'))

# --- Formularios para las Nuevas Funcionalidades ---
class FixedIncomeForm(FlaskForm):
    annual_net_salary = StringField('Salario Neto Anual (€)', validators=[DataRequired()], 
                                  render_kw={"placeholder": "Ej: 35000"})
    submit = SubmitField('Guardar')

class BrokerOperationForm(FlaskForm):
    date = StringField('Fecha', validators=[DataRequired()], 
                      render_kw={"placeholder": "DD/MM/YYYY", "type": "date"})
    operation_type = SelectField('Tipo de Operación', 
                               choices=[
                                   ('Ingreso', 'Ingreso'), 
                                   ('Retirada', 'Retirada'), 
                                   ('Comisión', 'Comisión')
                               ],
                               validators=[DataRequired()])
    # IMPORTANTE: Cambiamos para aceptar cualquier valor en el concepto
    concept = SelectField('Concepto', validators=[DataRequired()]) 
    amount = StringField('Cantidad (€)', validators=[DataRequired()], 
                        render_kw={"placeholder": "Ej: 1500.50"})
    description = TextAreaField('Descripción (Opcional)', 
                             render_kw={"placeholder": "Detalles adicionales (opcional)", "rows": 3})
    submit = SubmitField('Registrar Operación')

# Nuevo modelo para el historial de salarios
class SalaryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    annual_net_salary = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('salary_history', lazy='dynamic'))


# Formulario para añadir historial de salarios
class SalaryHistoryForm(FlaskForm):
    year = StringField('Año', validators=[DataRequired()], 
                      render_kw={"placeholder": "Ej: 2023", "type": "number", "min": "1900", "max": "2100"})
    annual_net_salary = StringField('Salario Neto Anual (€)', validators=[DataRequired()], 
                                  render_kw={"placeholder": "Ej: 35000"})
    submit = SubmitField('Añadir Salario Histórico')


# Modelos para la gestión de cuentas bancarias
class BankAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    bank_name = db.Column(db.String(100), nullable=False)
    account_name = db.Column(db.String(100), nullable=True)  # Nombre optativo (ej: "Cuenta Nómina")
    current_balance = db.Column(db.Float, nullable=False, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('bank_accounts', lazy='dynamic'))
    
    def __repr__(self):
        return f'<BankAccount {self.bank_name} - {self.account_name} ({self.current_balance}€)>'

class CashHistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total_cash = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('cash_history', lazy='dynamic'))
    
    def __repr__(self):
        return f'<CashHistoryRecord {self.date.strftime("%m/%Y")} - {self.total_cash}€>'

# Formularios para cuentas bancarias
class BankAccountForm(FlaskForm):
    bank_name = StringField('Entidad Bancaria', validators=[DataRequired()],
                          render_kw={"placeholder": "Ej: BBVA, Santander..."})
    account_name = StringField('Nombre de la Cuenta (Opcional)',
                             render_kw={"placeholder": "Ej: Cuenta Nómina, Ahorro..."})
    current_balance = StringField('Saldo Actual (€)', validators=[DataRequired()],
                              render_kw={"placeholder": "Ej: 1500.75"})
    submit = SubmitField('Guardar Cuenta')

class CashHistoryForm(FlaskForm):
    month_year = StringField('Mes y Año', validators=[DataRequired()],
                           render_kw={"type": "month", "placeholder": "YYYY-MM"})
    submit = SubmitField('Guardar Estado Actual')

# --- Modelos para Ingresos Variables ---
class VariableIncomeCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('variable_income_category.id', ondelete='SET NULL'), nullable=True)
    is_default = db.Column(db.Boolean, default=False)  # Para categorías predefinidas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('variable_income_categories', lazy='dynamic'))
    
    # Relación para subcategorías
    subcategories = db.relationship('VariableIncomeCategory', 
                                 backref=db.backref('parent', remote_side=[id]),
                                 cascade="all, delete-orphan")
    
    # Relación con ingresos
    incomes = db.relationship('VariableIncome', backref='category', lazy='dynamic', cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<VariableIncomeCategory {self.name}>'

class VariableIncome(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('variable_income_category.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    income_type = db.Column(db.String(20), nullable=False, default="punctual")  # "punctual", "recurring"
    is_recurring = db.Column(db.Boolean, default=False)  # Para ingresos periódicos
    recurrence_months = db.Column(db.Integer, nullable=True)  # Cada cuántos meses se repite (1=mensual, 12=anual)
    start_date = db.Column(db.Date, nullable=True)  # Para ingresos recurrentes
    end_date = db.Column(db.Date, nullable=True)  # Fecha opcional de finalización
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con el usuario
    user = db.relationship('User', backref=db.backref('variable_incomes', lazy='dynamic'))
    
    def __repr__(self):
        return f'<VariableIncome {self.description} ({self.amount}€)>'

# --- Formularios para la gestión de ingresos variables ---
# --- Formularios para la gestión de ingresos ---
class VariableIncomeCategoryForm(FlaskForm):
    name = StringField('Nombre de la Categoría', validators=[DataRequired()],
                    render_kw={"placeholder": "Ej: Freelance, Dividendos, Bonificaciones..."})
    description = TextAreaField('Descripción (Opcional)',
                             render_kw={"placeholder": "Descripción opcional", "rows": 2})
    parent_id = SelectField('Categoría Padre (Opcional)', coerce=int, choices=[], validators=[Optional()])
    submit = SubmitField('Guardar Categoría')

class VariableIncomeForm(FlaskForm):
    description = StringField('Descripción', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: Salario empresa, Proyecto freelance, Dividendo acción..."})
    amount = StringField('Importe (€)', validators=[DataRequired()],
                       render_kw={"placeholder": "Ej: 1500.50"})
    date = StringField('Fecha', validators=[DataRequired()],
                     render_kw={"type": "date"})
    category_id = SelectField('Categoría', coerce=int, validators=[Optional()])
    income_type = SelectField('Tipo de Ingreso',
                            choices=[
                                ('fixed', 'Ingreso Fijo'),
                                ('punctual', 'Ingreso Variable / Puntual')
                            ],
                            validators=[DataRequired()])
    is_recurring = BooleanField('Es Recurrente')
    recurrence_months = SelectField('Recurrencia',
                                 choices=[
                                     (1, 'Mensual'),
                                     (2, 'Bimestral'),
                                     (3, 'Trimestral'),
                                     (6, 'Semestral'),
                                     (12, 'Anual')
                                 ], coerce=int, validators=[Optional()])
    start_date = StringField('Fecha Inicio (Para recurrentes)',
                          render_kw={"type": "date"}, validators=[Optional()])
    end_date = StringField('Fecha Fin (Opcional)',
                        render_kw={"type": "date"}, validators=[Optional()])
    submit = SubmitField('Registrar Ingreso')

@app.route('/end_variable_income/<int:income_id>/<string:action_date>', methods=['POST'])
@login_required
def end_variable_income(income_id, action_date):
    """
    Finaliza un ingreso fijo estableciendo su fecha de fin a la fecha especificada.
    Si ya está finalizado (tiene end_date), revierte la finalización.
    
    Args:
        income_id: ID del ingreso fijo
        action_date: Fecha desde la que finalizar (formato YYYY-MM-DD)
    """
    # Buscar el ingreso por ID y verificar que pertenece al usuario
    income = VariableIncome.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()
    
    # Verificar que es un ingreso fijo (recurrente)
    if not income.is_recurring or income.income_type != 'fixed':
        flash('Solo se pueden finalizar ingresos fijos.', 'warning')
        return redirect(url_for('variable_income'))
    
    try:
        # Convertir la fecha de acción a objeto date
        fin_date = datetime.strptime(action_date, '%Y-%m-%d').date()
        
        # Si el ingreso ya tiene fecha de fin (está finalizado), revertir la finalización
        if income.end_date:
            income.end_date = None
            db.session.commit()
            flash(f'El ingreso fijo "{income.description}" ha sido reactivado. Se generarán pagos desde la fecha actual.', 'success')
        else:
            # Finalizar el ingreso en la fecha especificada
            # Ajustamos al primer día del mes para mantener consistencia
            fin_month_date = date(fin_date.year, fin_date.month, 1)
            
            income.end_date = fin_month_date
            db.session.commit()
            flash(f'El ingreso fijo "{income.description}" ha sido finalizado en {fin_month_date.strftime("%m/%Y")}. No se generarán más pagos a partir de esta fecha.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el ingreso fijo: {e}', 'danger')
    
    return redirect(url_for('variable_income'))



@app.route('/variable_income', methods=['GET', 'POST'])
@login_required
def variable_income():
    """Muestra y gestiona la página de ingresos (fijos y variables)."""
    # Formulario para categorías
    category_form = VariableIncomeCategoryForm()

    # Cargar categorías para el dropdown del formulario
    user_categories = VariableIncomeCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None  # Solo categorías principales
    ).all()

    category_form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [
        (cat.id, cat.name) for cat in user_categories
    ]

    # Formulario para ingresos
    income_form = VariableIncomeForm()

    # Cargar todas las categorías para el dropdown (incluyendo subcategorías)
    all_categories = VariableIncomeCategory.query.filter_by(user_id=current_user.id).all()

    # Crear una lista de opciones con indentación para mostrar jerarquía
    category_choices = []
    for cat in all_categories:
        if cat.parent_id is None:
            category_choices.append((cat.id, cat.name))
            # Añadir subcategorías con indentación
            subcats = VariableIncomeCategory.query.filter_by(parent_id=cat.id).all()
            for subcat in subcats:
                category_choices.append((subcat.id, f"-- {subcat.name}"))

    income_form.category_id.choices = [(0, 'Sin categoría')] + category_choices

    # Procesar formulario de categoría
    if category_form.validate_on_submit() and 'add_category' in request.form:
        try:
            parent_id = category_form.parent_id.data
            if parent_id == 0:
                parent_id = None  # Si se seleccionó "Ninguna"

            # Crear nueva categoría
            new_category = VariableIncomeCategory(
                user_id=current_user.id,
                name=category_form.name.data,
                description=category_form.description.data,
                parent_id=parent_id
            )

            db.session.add(new_category)
            db.session.commit()

            flash('Categoría añadida correctamente.', 'success')
            return redirect(url_for('variable_income'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear categoría: {e}', 'danger')

    # Procesar formulario de ingreso
    if income_form.validate_on_submit() and 'add_income' in request.form:
        try:
            # Convertir valores
            amount = float(income_form.amount.data.replace(',', '.'))
            date_obj = datetime.strptime(income_form.date.data, '%Y-%m-%d').date()

            # Determinar categoría
            category_id = income_form.category_id.data
            if category_id == 0:
                category_id = None  # Sin categoría

            # Verificar campos para ingresos recurrentes/fijos
            is_recurring = income_form.income_type.data == 'fixed'  # Solo ingresos fijos son recurrentes
            recurrence_months = None
            start_date = None
            end_date = None

            if is_recurring:
                recurrence_months = income_form.recurrence_months.data

                # Para ingresos fijos, la fecha de inicio siempre es igual a la fecha del ingreso
                start_date = date_obj

                if income_form.end_date.data:
                    end_date = datetime.strptime(income_form.end_date.data, '%Y-%m-%d').date()

            # Crear nuevo ingreso
            new_income = VariableIncome(
                user_id=current_user.id,
                category_id=category_id,
                description=income_form.description.data,
                amount=amount,
                date=date_obj,
                income_type=income_form.income_type.data,
                is_recurring=is_recurring,
                recurrence_months=recurrence_months if is_recurring else None,
                start_date=start_date,
                end_date=end_date
            )

            db.session.add(new_income)
            db.session.commit()

            flash('Ingreso registrado correctamente.', 'success')
            return redirect(url_for('variable_income'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar ingreso: {e}', 'danger')

    # Obtener todos los ingresos del usuario (ordenados por fecha, más recientes primero)
    user_incomes = VariableIncome.query.filter_by(user_id=current_user.id).order_by(VariableIncome.date.desc()).all()

    # Preparar historial unificado de ingresos incluyendo recurrentes expandidos
    unified_incomes = []
    
    # Procesar cada ingreso
    for income in user_incomes:
        # Si es un ingreso fijo (recurrente), generar entradas para cada mes
        if income.is_recurring and income.income_type == 'fixed':
            # Determinar fecha de inicio y fin
            start_date = income.start_date or income.date
            end_date = income.end_date or date.today()

            # Si la fecha de fin es futura, usar la fecha actual como límite
            if end_date > date.today():
                end_date = date.today()

            # Calcular meses entre start_date y end_date
            current_date = start_date
            recurrence = income.recurrence_months or 1  # Por defecto mensual

            while current_date <= end_date:
                # Determinar nombre de categoría
                category_name = "Sin categoría"
                if income.category_id:
                    category = VariableIncomeCategory.query.get(income.category_id)
                    if category:
                        category_name = category.name
                
                # Crear entrada para este mes
                monthly_entry = {
                    'id': income.id,
                    'description': f"{income.description} ({current_date.strftime('%b %Y')})",
                    'amount': income.amount,
                    'date': current_date,
                    'income_type': income.income_type,
                    'is_recurring': income.is_recurring,
                    'category_name': category_name,
                    'from_debt': False
                }
                
                # Verificar si el ingreso tiene fecha de fin para marcarlo
                if income.end_date:
                    monthly_entry['is_ended'] = True
                    monthly_entry['end_date'] = income.end_date
                else:
                    monthly_entry['is_ended'] = False
                
                unified_incomes.append(monthly_entry)

                # Avanzar al siguiente período según la recurrencia
                year = current_date.year
                month = current_date.month + recurrence

                # Ajustar si nos pasamos de diciembre
                while month > 12:
                    month -= 12
                    year += 1

                # Crear nueva fecha
                try:
                    current_date = date(year, month, 1)
                except ValueError:
                    # Por si hay algún problema con la fecha
                    break
        else:
            # Para ingresos variables/puntuales, solo añadir una entrada directamente
            category_name = "Sin categoría"
            if income.category_id:
                category = VariableIncomeCategory.query.get(income.category_id)
                if category:
                    category_name = category.name
            
            unified_incomes.append({
                'id': income.id,
                'description': income.description,
                'amount': income.amount,
                'date': income.date,
                'income_type': income.income_type,
                'is_recurring': income.is_recurring,
                'category_name': category_name,
                'from_debt': False
            })

    # Ordenar por fecha (más recientes primero)
    unified_incomes.sort(key=lambda x: x['date'], reverse=True)

    # Calcular resumen por categoría (últimos 6 meses)
    six_months_ago = date.today() - timedelta(days=180)
    incomes_by_category = {}
    
    for income in user_incomes:
        # Determinar todas las fechas para ingresos recurrentes dentro del periodo
        dates_to_consider = []
        if income.is_recurring and income.income_type == 'fixed' and income.recurrence_months:
            start_date = max(income.start_date or income.date, six_months_ago)
            end_date = min(income.end_date or date.today(), date.today())
            
            current_date = start_date
            recurrence = income.recurrence_months
            
            while current_date <= end_date:
                dates_to_consider.append(current_date)
                
                # Avanzar al siguiente período
                year = current_date.year
                month = current_date.month + recurrence
                
                # Ajustar si nos pasamos de diciembre
                while month > 12:
                    month -= 12
                    year += 1
                    
                # Crear nueva fecha
                try:
                    current_date = date(year, month, 1)
                except ValueError:
                    break
        else:
            if income.date >= six_months_ago:
                dates_to_consider.append(income.date)
        
        # Sumar el ingreso en cada fecha correspondiente
        for income_date in dates_to_consider:
            # Obtener nombre de categoría
            category_name = "Sin categoría"
            if income.category_id:
                category = VariableIncomeCategory.query.get(income.category_id)
                if category:
                    category_name = category.name
                    
            # Inicializar categoría si es la primera vez
            if category_name not in incomes_by_category:
                incomes_by_category[category_name] = 0
                
            # Sumar ingreso
            incomes_by_category[category_name] += income.amount
    
    # Ordenar categorías por ingreso (de mayor a menor)
    sorted_categories = sorted(
        incomes_by_category.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Calcular total acumulado en distintos períodos
    total_last_month = 0
    total_last_3_months = 0
    total_last_6_months = 0
    
    one_month_ago = date.today() - timedelta(days=30)
    three_months_ago = date.today() - timedelta(days=90)
    
    for income in unified_incomes:
        if income['date'] >= one_month_ago:
            total_last_month += income['amount']
        if income['date'] >= three_months_ago:
            total_last_3_months += income['amount']
        if income['date'] >= six_months_ago:
            total_last_6_months += income['amount']

    return render_template('variable_income.html',
                         category_form=category_form,
                         income_form=income_form,
                         incomes=user_incomes,
                         unified_incomes=unified_incomes,
                         sorted_categories=sorted_categories,
                         total_last_month=total_last_month,
                         total_last_3_months=total_last_3_months,
                         total_last_6_months=total_last_6_months)


@app.route('/edit_variable_income/<int:income_id>', methods=['GET', 'POST'])
@login_required
def edit_variable_income(income_id):
    """Edita un ingreso existente."""
    # Buscar el ingreso por ID y verificar que pertenece al usuario
    income = VariableIncome.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()
    
    # Crear formulario y prellenarlo con los datos del ingreso
    form = VariableIncomeForm()
    
    # Cargar categorías para el dropdown
    all_categories = VariableIncomeCategory.query.filter_by(user_id=current_user.id).all()
    
    # Crear lista de opciones con indentación para mostrar jerarquía
    category_choices = []
    for cat in all_categories:
        if cat.parent_id is None:
            category_choices.append((cat.id, cat.name))
            # Añadir subcategorías con indentación
            subcats = VariableIncomeCategory.query.filter_by(parent_id=cat.id).all()
            for subcat in subcats:
                category_choices.append((subcat.id, f"-- {subcat.name}"))
    
    form.category_id.choices = [(0, 'Sin categoría')] + category_choices
    
    if request.method == 'GET':
        # Precargar datos del ingreso en el formulario
        form.description.data = income.description
        form.amount.data = str(income.amount)
        form.date.data = income.date.strftime('%Y-%m-%d')
        form.category_id.data = income.category_id if income.category_id else 0
        form.income_type.data = income.income_type
        form.is_recurring.data = income.is_recurring
        
        if income.is_recurring:
            form.recurrence_months.data = income.recurrence_months if income.recurrence_months else 1
            if income.start_date:
                form.start_date.data = income.start_date.strftime('%Y-%m-%d')
            if income.end_date:
                form.end_date.data = income.end_date.strftime('%Y-%m-%d')
    
    if form.validate_on_submit():
        try:
            # Convertir valores
            amount = float(form.amount.data.replace(',', '.'))
            date_obj = datetime.strptime(form.date.data, '%Y-%m-%d').date()
            
            # Determinar categoría
            category_id = form.category_id.data
            if category_id == 0:
                category_id = None  # Sin categoría
                
            # Verificar campos para ingresos recurrentes/fijos
            is_recurring = form.income_type.data == 'fixed'  # Solo ingresos fijos son recurrentes
            recurrence_months = None
            start_date = None
            end_date = None
            
            if is_recurring:
                recurrence_months = form.recurrence_months.data
                
                # Para ingresos fijos, la fecha de inicio es igual a la fecha del ingreso
                start_date = date_obj
                    
                if form.end_date.data:
                    end_date = datetime.strptime(form.end_date.data, '%Y-%m-%d').date()
            
            # Actualizar el ingreso
            income.description = form.description.data
            income.amount = amount
            income.date = date_obj
            income.category_id = category_id
            income.income_type = form.income_type.data
            income.is_recurring = is_recurring
            income.recurrence_months = recurrence_months if is_recurring else None
            income.start_date = start_date
            income.end_date = end_date
            income.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            flash('Ingreso actualizado correctamente.', 'success')
            return redirect(url_for('variable_income'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar ingreso: {e}', 'danger')
    
    return render_template('edit_variable_income.html', form=form, income=income)

@app.route('/delete_variable_income_with_options/<int:income_id>/<string:delete_type>', methods=['POST'])
@login_required
def delete_variable_income_with_options(income_id, delete_type):
    """
    Elimina un ingreso fijo recurrente según la opción seleccionada:
    - 'single': Elimina solo la entrada específica
    - 'series': Elimina toda la serie recurrente

    Args:
        income_id: ID del ingreso recurrente
        delete_type: Tipo de eliminación ('single' o 'series')
    """
    # Buscar el ingreso por ID y verificar que pertenece al usuario
    income = VariableIncome.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()

    if not income:
        flash('Ingreso no encontrado.', 'danger')
        return redirect(url_for('variable_income'))

    try:
        if delete_type == 'series':
            # Eliminar toda la serie recurrente
            db.session.delete(income)
            db.session.commit()
            flash(f'La serie completa del ingreso recurrente "{income.description}" ha sido eliminada.', 'success')

        elif delete_type == 'single':
            # Para eliminar solo una entrada de una serie, creamos un registro negativo para ese mes específico
            entry_date_str = request.args.get('entry_date')

            if entry_date_str:
                entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date()

                # Crear un ingreso de compensación (mismo importe pero negativo)
                compensation = VariableIncome(
                    user_id=current_user.id,
                    category_id=income.category_id,
                    description=f"Excepción: {income.description}",
                    amount=-income.amount,  # Importe negativo para cancelar
                    date=entry_date,
                    income_type='punctual',  # Puntual para que no se repita
                    is_recurring=False
                )

                db.session.add(compensation)
                db.session.commit()
                flash(f'El pago específico de "{income.description}" para {entry_date.strftime("%m/%Y")} ha sido cancelado.', 'success')
            else:
                flash('No se pudo determinar la fecha del pago a eliminar.', 'warning')

        else:
            flash('Opción de eliminación no válida.', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar ingreso: {e}', 'danger')

    return redirect(url_for('variable_income'))

@app.route('/delete_variable_income/<int:income_id>', methods=['POST'])
@login_required
def delete_variable_income(income_id):
    """Elimina un ingreso variable."""
    income = VariableIncome.query.filter_by(id=income_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(income)
        db.session.commit()
        flash('Ingreso eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar ingreso: {e}', 'danger')

    return redirect(url_for('variable_income'))

@app.route('/edit_variable_income_category/<int:category_id>', methods=['GET', 'POST'])
@login_required
def edit_variable_income_category(category_id):
    """Edita una categoría de ingreso variable existente."""
    # Buscar la categoría por ID y verificar que pertenece al usuario
    category = VariableIncomeCategory.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()

    # Crear formulario
    form = VariableIncomeCategoryForm()

    # Cargar categorías para el dropdown (excluyendo la actual y sus subcategorías)
    user_categories = VariableIncomeCategory.query.filter_by(
        user_id=current_user.id,
        parent_id=None  # Solo categorías principales
    ).filter(VariableIncomeCategory.id != category_id).all()

    # Filtrar subcategorías que pertenecen a esta categoría
    subcategory_ids = [subcat.id for subcat in category.subcategories]
    user_categories = [cat for cat in user_categories if cat.id not in subcategory_ids]

    form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [
        (cat.id, cat.name) for cat in user_categories
    ]

    if request.method == 'GET':
        # Precargar datos de la categoría en el formulario
        form.name.data = category.name
        form.description.data = category.description
        form.parent_id.data = category.parent_id if category.parent_id else 0

    if form.validate_on_submit():
        try:
            parent_id = form.parent_id.data
            if parent_id == 0:
                parent_id = None  # Si se seleccionó "Ninguna"

            # Actualizar la categoría
            category.name = form.name.data
            category.description = form.description.data
            category.parent_id = parent_id

            db.session.commit()

            flash('Categoría actualizada correctamente.', 'success')
            return redirect(url_for('variable_income'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar categoría: {e}', 'danger')

    return render_template('edit_variable_income_category.html', form=form, category=category)

@app.route('/delete_variable_income_category/<int:category_id>', methods=['POST'])
@login_required
def delete_variable_income_category(category_id):
    """Elimina una categoría de ingreso variable."""
    category = VariableIncomeCategory.query.filter_by(id=category_id, user_id=current_user.id).first_or_404()

    try:
        # Verificar si hay ingresos o subcategorías asociadas
        has_incomes = VariableIncome.query.filter_by(category_id=category_id).first() is not None
        has_subcategories = VariableIncomeCategory.query.filter_by(parent_id=category_id).first() is not None

        if has_incomes:
            flash('No se puede eliminar la categoría porque tiene ingresos asociados.', 'warning')
            return redirect(url_for('variable_income'))

        if has_subcategories:
            flash('No se puede eliminar la categoría porque tiene subcategorías.', 'warning')
            return redirect(url_for('variable_income'))

        db.session.delete(category)
        db.session.commit()
        flash('Categoría eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar categoría: {e}', 'danger')

    return redirect(url_for('variable_income'))


# Ruta para ayudar a crear categorías predeterminadas
@app.route('/create_default_income_categories', methods=['GET'])
@login_required
def create_default_income_categories():
    """Crea categorías de ingresos variables predeterminadas para el usuario."""
    default_categories = [
        {
            'name': 'Trabajo Freelance', 
            'description': 'Ingresos por proyectos independientes',
            'subcategories': [
                'Desarrollo web', 
                'Diseño gráfico', 
                'Consultoría', 
                'Traducción', 
                'Fotografía'
            ]
        },
        {
            'name': 'Inversiones', 
            'description': 'Rendimiento de inversiones',
            'subcategories': [
                'Dividendos', 
                'Intereses', 
                'Alquileres', 
                'Ganancias de capital'
            ]
        },
        {
            'name': 'Premios y Regalos', 
            'description': 'Ingresos no regulares recibidos',
            'subcategories': [
                'Premios', 
                'Regalos', 
                'Herencias',
                'Loterías'
            ]
        },
        {
            'name': 'Reembolsos', 
            'description': 'Devoluciones de dinero',
            'subcategories': [
                'Impuestos', 
                'Gastos médicos', 
                'Seguros',
                'Reclamaciones'
            ]
        },
        {
            'name': 'Bonificaciones', 
            'description': 'Pagos extra del trabajo principal',
            'subcategories': [
                'Bonos', 
                'Comisiones', 
                'Horas extras',
                'Incentivos'
            ]
        },
        {
            'name': 'Varios', 
            'description': 'Otros ingresos no categorizados',
            'subcategories': []
        }
    ]
    
    try:
        categories_added = 0
        subcategories_added = 0
        
        for category in default_categories:
            # Verificar si la categoría ya existe
            existing_cat = VariableIncomeCategory.query.filter_by(
                user_id=current_user.id,
                name=category['name']
            ).first()
            
            if existing_cat:
                # Categoría principal ya existe, solo añadir subcategorías faltantes
                for subcat_name in category['subcategories']:
                    # Verificar si la subcategoría ya existe
                    existing_subcat = VariableIncomeCategory.query.filter_by(
                        user_id=current_user.id,
                        parent_id=existing_cat.id,
                        name=subcat_name
                    ).first()
                    
                    if not existing_subcat:
                        # Crear nueva subcategoría
                        new_subcat = VariableIncomeCategory(
                            user_id=current_user.id,
                            name=subcat_name,
                            parent_id=existing_cat.id,
                            is_default=True
                        )
                        db.session.add(new_subcat)
                        subcategories_added += 1
            else:
                # Crear categoría principal
                main_cat = VariableIncomeCategory(
                    user_id=current_user.id,
                    name=category['name'],
                    description=category['description'],
                    is_default=True
                )
                db.session.add(main_cat)
                db.session.flush()  # Para obtener el ID asignado
                categories_added += 1
                
                # Crear subcategorías
                for subcat_name in category['subcategories']:
                    subcategory = VariableIncomeCategory(
                        user_id=current_user.id,
                        name=subcat_name,
                        parent_id=main_cat.id,
                        is_default=True
                    )
                    db.session.add(subcategory)
                    subcategories_added += 1
        
        db.session.commit()
        
        if categories_added > 0 or subcategories_added > 0:
            flash(f'Se han creado {categories_added} categorías y {subcategories_added} subcategorías predeterminadas.', 'success')
        else:
            flash('Ya existen todas las categorías predeterminadas.', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al crear categorías predeterminadas: {e}', 'danger')
    
    return redirect(url_for('variable_income'))


@app.route('/bank_accounts', methods=['GET', 'POST'])
@login_required
def bank_accounts():
    """Muestra y gestiona la página de cuentas bancarias."""
    # Formulario para añadir nueva cuenta
    account_form = BankAccountForm()
    
    # Formulario para guardar historial
    history_form = CashHistoryForm()
    
    # Procesar formulario de nueva cuenta
    if account_form.validate_on_submit() and 'add_account' in request.form:
        try:
            # Convertir saldo a float
            balance = float(account_form.current_balance.data.replace(',', '.'))
            
            # Crear nueva cuenta
            new_account = BankAccount(
                user_id=current_user.id,
                bank_name=account_form.bank_name.data,
                account_name=account_form.account_name.data,
                current_balance=balance
            )
            
            db.session.add(new_account)
            db.session.commit()
            
            flash('Cuenta bancaria añadida correctamente.', 'success')
            return redirect(url_for('bank_accounts'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al añadir cuenta: {e}', 'danger')
    
    # Obtener todas las cuentas del usuario
    user_accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
    
    # Calcular el total de efectivo
    total_cash = sum(account.current_balance for account in user_accounts)
    
    # Obtener historial de efectivo
    cash_history = CashHistoryRecord.query.filter_by(user_id=current_user.id).order_by(CashHistoryRecord.date.desc()).all()
    
    # Calcular variaciones
    for i, record in enumerate(cash_history):
        if i < len(cash_history) - 1:
            next_record = cash_history[i + 1]
            if next_record.total_cash > 0:
                variation = ((record.total_cash - next_record.total_cash) / next_record.total_cash) * 100
                record.variation = variation
            else:
                record.variation = None
        else:
            record.variation = None
    
    return render_template(
        'bank_accounts.html',
        account_form=account_form,
        history_form=history_form,
        accounts=user_accounts,
        total_cash=total_cash,
        cash_history=cash_history
    )

@app.route('/update_bank_account/<int:account_id>', methods=['POST'])
@login_required
def update_bank_account(account_id):
    """Actualiza una cuenta bancaria existente."""
    account = BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    try:
        # Obtener datos del formulario
        bank_name = request.form.get('bank_name')
        account_name = request.form.get('account_name')
        current_balance = request.form.get('current_balance').replace(',', '.')
        
        # Validar datos
        if not bank_name or not current_balance:
            flash('Todos los campos obligatorios deben estar completos.', 'warning')
            return redirect(url_for('bank_accounts'))
        
        # Actualizar cuenta
        account.bank_name = bank_name
        account.account_name = account_name
        account.current_balance = float(current_balance)
        account.last_updated = datetime.utcnow()
        
        db.session.commit()
        flash('Cuenta actualizada correctamente.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar cuenta: {e}', 'danger')
    
    return redirect(url_for('bank_accounts'))

@app.route('/delete_bank_account/<int:account_id>', methods=['POST'])
@login_required
def delete_bank_account(account_id):
    """Elimina una cuenta bancaria."""
    account = BankAccount.query.filter_by(id=account_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(account)
        db.session.commit()
        flash('Cuenta eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar cuenta: {e}', 'danger')
    
    return redirect(url_for('bank_accounts'))

@app.route('/save_cash_history', methods=['POST'])
@login_required
def save_cash_history():
    """Guarda un registro del historial de efectivo total."""
    form = CashHistoryForm()
    
    if form.validate_on_submit():
        try:
            # Obtener la fecha del formulario
            month_year = form.month_year.data  # Formato: "YYYY-MM"
            date_parts = month_year.split('-')
            
            if len(date_parts) != 2:
                flash('Formato de fecha incorrecto. Use YYYY-MM.', 'warning')
                return redirect(url_for('bank_accounts'))
            
            year = int(date_parts[0])
            month = int(date_parts[1])
            
            # Crear fecha con el primer día del mes
            record_date = date(year, month, 1)
            
            # Comprobar si ya existe un registro para este mes/año
            existing = CashHistoryRecord.query.filter_by(
                user_id=current_user.id, 
                date=record_date
            ).first()
            
            if existing:
                flash(f'Ya existe un registro para {month}/{year}. Elimínelo antes de crear uno nuevo.', 'warning')
                return redirect(url_for('bank_accounts'))
            
            # Calcular el efectivo total actual
            accounts = BankAccount.query.filter_by(user_id=current_user.id).all()
            total_cash = sum(account.current_balance for account in accounts)
            
            # Crear nuevo registro
            new_record = CashHistoryRecord(
                user_id=current_user.id,
                date=record_date,
                total_cash=total_cash
            )
            
            db.session.add(new_record)
            db.session.commit()
            
            flash(f'Registro de efectivo para {month}/{year} guardado correctamente.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar registro: {e}', 'danger')
    
    return redirect(url_for('bank_accounts'))

@app.route('/delete_cash_history/<int:record_id>', methods=['POST'])
@login_required
def delete_cash_history(record_id):
    """Elimina un registro del historial de efectivo."""
    record = CashHistoryRecord.query.filter_by(id=record_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(record)
        db.session.commit()
        flash('Registro de efectivo eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar registro: {e}', 'danger')
    
    return redirect(url_for('bank_accounts'))


@app.route('/fixed_income', methods=['GET', 'POST'])
@login_required
def fixed_income():
    """Muestra y gestiona la página de ingresos fijos (salario)."""
    # Buscar datos existentes del usuario
    income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
    
    # Crear formulario y prellenarlo si hay datos
    form = FixedIncomeForm()
    if income_data and not form.is_submitted():
        form.annual_net_salary.data = income_data.annual_net_salary
    
    # Formulario para añadir historial
    history_form = SalaryHistoryForm()
    
    # Procesar formulario principal si se envió
    if form.validate_on_submit():
        try:
            # Convertir el valor a float (reemplazando coma por punto si es necesario)
            annual_salary_str = form.annual_net_salary.data
            if isinstance(annual_salary_str, str):
                annual_salary = float(annual_salary_str.replace(',', '.'))
            else:
                annual_salary = float(annual_salary_str)
            
            if income_data:
                # Actualizar datos existentes
                income_data.annual_net_salary = annual_salary
                income_data.last_updated = datetime.utcnow()
            else:
                # Crear nuevo registro
                income_data = FixedIncome(
                    user_id=current_user.id,
                    annual_net_salary=annual_salary
                )
                db.session.add(income_data)
            
            db.session.commit()
            flash('Datos de ingresos fijos actualizados correctamente.', 'success')
            return redirect(url_for('fixed_income'))
        
        except (ValueError, Exception) as e:
            db.session.rollback()
            flash(f'Error al procesar los datos: {e}', 'danger')
    
    # Calcular valores para mostrar
    salary_12 = None
    salary_14 = None
    
    if income_data and income_data.annual_net_salary:
        # Cálculo para 12 y 14 pagas
        salary_12 = income_data.annual_net_salary / 12
        salary_14 = income_data.annual_net_salary / 14
    
    # Obtener historial de salarios ordenado por año (descendente)
    salary_history = SalaryHistory.query.filter_by(user_id=current_user.id).order_by(SalaryHistory.year.desc()).all()
    
    # Calcular porcentajes de variación
    for i, entry in enumerate(salary_history):
        if i < len(salary_history) - 1:  # Si no es el último (más antiguo)
            next_entry = salary_history[i + 1]
            if next_entry.annual_net_salary > 0:
                variation = ((entry.annual_net_salary - next_entry.annual_net_salary) / next_entry.annual_net_salary) * 100
                entry.variation = variation
            else:
                entry.variation = None
        else:
            entry.variation = None  # El más antiguo no tiene variación
    
    return render_template(
        'fixed_income.html',
        form=form,
        history_form=history_form,
        income_data=income_data,
        salary_12=salary_12,
        salary_14=salary_14,
        salary_history=salary_history
    )

@app.route('/add_salary_history', methods=['POST'])
@login_required
def add_salary_history():
    """Añade un nuevo registro al historial de salarios."""
    form = SalaryHistoryForm()
    
    if form.validate_on_submit():
        try:
            # Convertir valores
            year = int(form.year.data)
            annual_salary = float(form.annual_net_salary.data.replace(',', '.'))
            
            # Verificar que el año no exista ya
            existing = SalaryHistory.query.filter_by(user_id=current_user.id, year=year).first()
            if existing:
                flash(f'Ya existe un registro para el año {year}. Edítelo en lugar de añadir uno nuevo.', 'warning')
                return redirect(url_for('fixed_income'))
            
            # Crear nuevo registro
            new_entry = SalaryHistory(
                user_id=current_user.id,
                year=year,
                annual_net_salary=annual_salary
            )
            
            db.session.add(new_entry)
            db.session.commit()
            
            flash(f'Salario del año {year} añadido correctamente.', 'success')
        
        except (ValueError, Exception) as e:
            db.session.rollback()
            flash(f'Error al añadir el historial de salario: {e}', 'danger')
    
    return redirect(url_for('fixed_income'))

@app.route('/delete_salary_history/<int:entry_id>', methods=['POST'])
@login_required
def delete_salary_history(entry_id):
    """Elimina un registro del historial de salarios."""
    entry = SalaryHistory.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(entry)
        db.session.commit()
        flash(f'Registro del año {entry.year} eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el registro: {e}', 'danger')
    
    return redirect(url_for('fixed_income'))


@app.route('/update_broker_operation_concepts', methods=['POST'])
@login_required
def update_broker_operation_concepts():
    """Actualiza dinámicamente las opciones del campo 'concept' según el tipo de operación seleccionado."""
    operation_type = request.form.get('operation_type')
    concepts = []
    
    print(f"Actualizando conceptos para tipo: {operation_type}")
    
    if operation_type == 'Ingreso':
        concepts = [('Inversión', 'Inversión')]
    elif operation_type == 'Retirada':
        concepts = [('Dividendos', 'Dividendos'), ('Desinversión', 'Desinversión')]
    elif operation_type == 'Comisión':
        concepts = [
            ('Compra/Venta', 'Comisión de Compra/Venta'), 
            ('Apalancamiento', 'Comisión de Apalancamiento'), 
            ('Otras', 'Otras Comisiones')
        ]
    
    return jsonify(concepts)


@app.route('/broker_operations', methods=['GET', 'POST'])
@login_required
def broker_operations():
    """Muestra y gestiona la página de operaciones del broker (ingresos/retiradas/comisiones)."""
    # Crear formulario
    form = BrokerOperationForm()

    # Configurar opciones iniciales para el campo 'concept'
    form.concept.choices = [
        ('Inversión', 'Inversión'),
        ('Dividendos', 'Dividendos'),
        ('Desinversión', 'Desinversión'),
        ('Compra/Venta', 'Comisión de Compra/Venta'),
        ('Apalancamiento', 'Comisión de Apalancamiento'),
        ('Otras', 'Otras Comisiones')
    ]

    # Procesar formulario si se envió
    if form.validate_on_submit():
        try:
            # Convertir la fecha
            operation_date = datetime.strptime(form.date.data, '%Y-%m-%d').date()

            # Obtener cantidad y manejar automáticamente el signo según el tipo de operación
            amount = form.amount.data.replace(',', '.')
            amount = float(amount)

            # MODIFICADO: Ahora las inversiones son negativas y las retiradas positivas
            if form.operation_type.data == 'Ingreso':
                amount = -abs(amount)  # Inversiones como negativo
            elif form.operation_type.data == 'Retirada':
                amount = abs(amount)   # Retiradas como positivo
            elif form.operation_type.data == 'Comisión':
                amount = -abs(amount)  # Comisiones como negativo

            # Crear nuevo registro
            new_operation = BrokerOperation(
                user_id=current_user.id,
                date=operation_date,
                operation_type=form.operation_type.data,
                concept=form.concept.data,
                amount=amount,
                description=form.description.data
            )

            db.session.add(new_operation)
            db.session.commit()

            flash('Operación registrada correctamente.', 'success')
            return redirect(url_for('broker_operations'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar la operación: {e}', 'danger')
            print(f"Error en broker_operations: {e}")

    # Obtener operaciones del usuario ordenadas por fecha (más recientes primero)
    operations = BrokerOperation.query.filter_by(user_id=current_user.id).order_by(BrokerOperation.date.desc()).all()

    # Calcular totales por concepto
    totals = {
        'Inversión': 0,
        'Dividendos': 0,
        'Desinversión': 0,
        'Compra/Venta': 0,
        'Apalancamiento': 0,
        'Otras': 0,
        'Total': 0
    }

    for op in operations:
        if op.concept in totals:
            totals[op.concept] += op.amount
        totals['Total'] += op.amount

    return render_template(
        'broker_operations.html',
        form=form,
        operations=operations,
        totals=totals,
        now=datetime.now()
    )


@app.route('/renegociate_debt_plan/<int:plan_id>', methods=['POST'])
@login_required
def renegociate_debt_plan(plan_id):
    """Renegocia un plan de deuda, modificando la duración y la cuota mensual."""
    plan = DebtInstallmentPlan.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    try:
        # Obtener nueva duración del formulario
        new_duration = int(request.form.get('new_duration_months', 1))
        
        # Validar datos
        if new_duration < 1:
            flash('La duración debe ser de al menos 1 mes.', 'warning')
            return redirect(url_for('debt_management'))
        
        # Calcular el monto pendiente basado en cuotas restantes
        remaining_amount = plan.remaining_amount
        
        # Obtener fecha actual para el reinicio del plazo
        today = date.today()
        
        # Determinar la nueva fecha de inicio (primer día del próximo mes)
        if today.month == 12:
            new_start_year = today.year + 1
            new_start_month = 1
        else:
            new_start_year = today.year
            new_start_month = today.month + 1
        
        new_start_date = date(new_start_year, new_start_month, 1)
        
        # Calcular fecha de fin correctamente
        end_date = calculate_end_date(new_start_date, new_duration)
        
        # Actualizar plan con nuevos valores
        plan.start_date = new_start_date
        plan.duration_months = new_duration
        plan.monthly_payment = remaining_amount / new_duration
        
        # Asegurar que el plan siga activo
        plan.is_active = True
        
        db.session.commit()
        
        flash(f'Plan de pago "{plan.description}" renegociado correctamente. Próximos pagos: del {new_start_date.strftime("%d/%m/%Y")} al {end_date.strftime("%d/%m/%Y")}', 'success')
    except ValueError:
        flash('Por favor, introduce un número válido de meses.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al renegociar plan: {e}', 'danger')
        print(f"Error al renegociar plan: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('debt_management'))

@app.route('/edit_broker_operation/<int:operation_id>', methods=['GET', 'POST'])
@login_required
def edit_broker_operation(operation_id):
    """Edita una operación de broker existente."""
    # Buscar la operación por ID y verificar que pertenece al usuario
    operation = BrokerOperation.query.filter_by(id=operation_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Obtener los datos del formulario
            operation_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            operation_type = request.form.get('operation_type')
            concept = request.form.get('concept')
            amount = float(request.form.get('amount').replace(',', '.'))
            description = request.form.get('description', '')
            
            # MODIFICADO: Aplicar signo según tipo de operación (inversión de signos)
            if operation_type == 'Ingreso':
                amount = -abs(amount)  # Inversiones como negativo
            elif operation_type == 'Retirada':
                amount = abs(amount)   # Retiradas como positivo
            elif operation_type == 'Comisión':
                amount = -abs(amount)  # Comisiones como negativo
            
            # Actualizar la operación
            operation.date = operation_date
            operation.operation_type = operation_type
            operation.concept = concept
            operation.amount = amount
            operation.description = description
            
            db.session.commit()
            flash('Operación actualizada correctamente.', 'success')
            return redirect(url_for('broker_operations'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la operación: {e}', 'danger')
    
    # Para GET, mostrar formulario de edición
    return render_template(
        'edit_broker_operation.html',
        operation=operation
    )


@app.route('/delete_broker_operation/<int:operation_id>', methods=['POST'])
@login_required
def delete_broker_operation(operation_id):
    """Elimina una operación de broker."""
    operation = BrokerOperation.query.filter_by(id=operation_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(operation)
        db.session.commit()
        flash('Operación eliminada correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la operación: {e}', 'danger')
    
    return redirect(url_for('broker_operations'))

@app.route('/delete_watchlist_item', methods=['POST'])
@login_required
def delete_watchlist_item():
    """
    Borra un item de la watchlist del usuario SOLO SI está en seguimiento manual
    (is_in_followup es True).
    """
    item_id_to_delete = request.form.get('item_id')
    print(f"Intento de borrado watchlist item ID: {item_id_to_delete} por usuario {current_user.id}")

    if not item_id_to_delete:
        flash("Error: No se especificó el ID del item a borrar.", "danger")
        return redirect(url_for('show_watchlist'))

    try:
        # Buscar el item por ID Y asegurándose que pertenece al usuario logueado
        item = WatchlistItem.query.filter_by(id=item_id_to_delete, user_id=current_user.id).first()

        if item:
            # --- COMPROBACIÓN ACTUALIZADA ---
            if item.is_in_followup: # Solo borrar si está en seguimiento manual
                item_name = item.item_name
                db.session.delete(item)
                db.session.commit()
                flash(f"'{item_name}' eliminado de la watchlist.", "success")
                print(f" Item {item_id_to_delete} ('{item_name}') borrado por usuario {current_user.id}")
            else:
                # Si existe pero no está en seguimiento (está en portfolio)
                flash("Error: Solo se pueden borrar items que están en seguimiento manual.", "warning")
                print(f" Intento de borrado denegado para item {item_id_to_delete} (en portfolio) por usuario {current_user.id}")
        else:
            # Item no encontrado o no pertenece al usuario
            flash("Error: No se encontró el item a borrar o no tienes permiso.", "warning")
            print(f" Intento de borrado fallido para item {item_id_to_delete} (no encontrado / no pertenece a user {current_user.id})")

    except Exception as e:
        db.session.rollback()
        flash(f"Error al borrar item de la watchlist: {e}", "danger")
        print(f"Error DB al borrar watchlist item: {e}")

    return redirect(url_for('show_watchlist'))


# --- Ejecución Principal ---
if __name__ == '__main__':
    # Crear tablas si no existen al iniciar la app
    with app.app_context():
        print("Verificando/Creando tablas de la base de datos...")
        db.create_all()
        print("Tablas verificadas/creadas.")
    app.run(debug=True, host='0.0.0.0', port=5000)
