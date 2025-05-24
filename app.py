# -*- coding: utf-8 -*-
import os
import pandas as pd
import io
import csv
import hashlib
import math
import re
from sqlalchemy import func
import traceback
import uuid
import json
from functools import wraps
import time
from datetime import date, timedelta, datetime # Asegúrate que datetime está importado
import glob
import requests # Para tipos de cambio
import yfinance as yf # Para precios acciones
from flask import (
    Flask, request, render_template, send_file, flash, redirect, url_for, session, get_flashed_messages, jsonify
)
from flask_wtf.file import FileField, FileRequired, FileAllowed
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
# MODIFICACIÓN AQUÍ: Añadir IntegerField y NumberRange
from wtforms import StringField, PasswordField, SubmitField, BooleanField, RadioField, FileField, MultipleFileField, HiddenField, SelectField, TextAreaField, IntegerField, DateField, FloatField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange # Asegúrate que NumberRange está importado
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

# --- Configuración para Flask-Mail (NECESITARÁS AJUSTAR ESTO) ---
# Ejemplo de configuración esencial en app.py
print("DEBUG: Configurando Flask-Mail...")
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587 # o 465
app.config['MAIL_USE_TLS'] = True # o MAIL_USE_SSL = True
app.config['MAIL_USE_SSL'] = False # Si usas TLS en puerto 587, SSL es False
app.config['MAIL_USERNAME'] = 'followup.fit@gmail.com' # el que te da tu proveedor de envío
app.config['MAIL_PASSWORD'] = 'gbbzbvuvidosrgwy' # la que te da tu proveedor de envío
app.config['MAIL_DEFAULT_SENDER'] = 'followup.fit@gmail.com' # O un email 'no-reply@tuapp.com'

# --- Depuración de la Configuración de Mail ---
print(f"DEBUG: MAIL_SERVER = {app.config.get('MAIL_SERVER')}")
print(f"DEBUG: MAIL_PORT = {app.config.get('MAIL_PORT')}")
print(f"DEBUG: MAIL_USE_TLS = {app.config.get('MAIL_USE_TLS')}")
print(f"DEBUG: MAIL_USERNAME = {app.config.get('MAIL_USERNAME')}")
print(f"DEBUG: MAIL_PASSWORD EXISTE = {'Sí' if app.config.get('MAIL_PASSWORD') else 'No'}") # No imprimas la contraseña real
print(f"DEBUG: MAIL_DEFAULT_SENDER = {app.config.get('MAIL_DEFAULT_SENDER')}")
# --- Fin Depuración ---

mail = Mail(app)
print("DEBUG: Flask-Mail inicializado.")



# Constantes de categorización
BUY_TRANSACTION_KINDS = [
    'viban_purchase', 'recurring_buy_order', 'dust_conversion_credited', 
    'crypto_wallet_swap_credited', 'finance.dpos.staking_conversion.credit'
]

SELL_TRANSACTION_KINDS = [
    'crypto_viban_exchange', 'dust_conversion_debited', 
    'crypto_wallet_swap_debited', 'finance.dpos.staking_conversion.terminate'
]

REWARD_TRANSACTION_KINDS = [
    'campaign_reward', 'referral_bonus', 'referral_card_cashback', 
    'admin_wallet_credited', 'crypto_earn_interest_paid', 'card_cashback_reverted'
]




db = SQLAlchemy(app)

from flask_migrate import Migrate
migrate = Migrate(app, db)

# Inicializar Flask-Login DESPUÉS de configurar la app
login_manager = LoginManager(app)
login_manager.login_view = 'login' # Endpoint de la vista de login
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'info'

# --- Crear Carpetas ---
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)




class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Quién realizó la acción (puede ser NULL para acciones del sistema)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    username = db.Column(db.String(80), nullable=True) # Guardar por si se borra el usuario
    
    # A quién afecta la acción (puede ser NULL)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    target_username = db.Column(db.String(80), nullable=True)

    action_type = db.Column(db.String(100), nullable=False, index=True) # Ej: 'LOGIN', 'LOGOUT', 'REGISTER', 'PASSWORD_RESET_REQUEST', 'ADMIN_TOGGLE_ACTIVE'
    message = db.Column(db.String(500), nullable=False) # Descripción breve
    details = db.Column(db.Text, nullable=True) # Detalles adicionales, ej. JSON con datos cambiados
    ip_address = db.Column(db.String(45), nullable=True)

    # Relaciones para acceder fácilmente a los usuarios si aún existen
    actor = db.relationship('User', foreign_keys=[user_id], backref='actions_performed')
    target = db.relationship('User', foreign_keys=[target_user_id], backref='actions_received')

    def __repr__(self):
        return f'<ActivityLog {self.timestamp} - {self.username or "System"} - {self.action_type}>'


# Modelo User (Verifica que todas las relaciones estén definidas aquí con backref y cascade)
class SetEmailForm(FlaskForm): # NUEVO FORMULARIO
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email(message="Correo electrónico no válido.")])
    confirm_email = StringField('Confirmar Correo Electrónico', validators=[DataRequired(), EqualTo('email', message='Los correos electrónicos deben coincidir.')])
    submit = SubmitField('Guardar Correo Electrónico')

    def validate_email(self, email):
        # Comprobar si el email ya está en uso por OTRO usuario
        user = User.query.filter(User.email == email.data, User.id != current_user.id).first()
        if user:
            raise ValidationError('Ese correo electrónico ya está registrado por otro usuario. Por favor, elige otro.')


# --- Modelos para Plan de Pensiones ---
class PensionPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    entity_name = db.Column(db.String(100), nullable=False)
    plan_name = db.Column(db.String(150), nullable=True)
    current_balance = db.Column(db.Float, nullable=False, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('pension_plans', lazy='dynamic'))

    def __repr__(self):
        return f'<PensionPlan {self.entity_name} - {self.plan_name} ({self.current_balance}€)>'

class PensionPlanHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('pension_history', lazy='dynamic'))

    def __repr__(self):
        return f'<PensionPlanHistory {self.date.strftime("%m/%Y")} - {self.total_amount}€>'

# --- Modelos para Cryptos ---
class CryptoExchange(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    exchange_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('crypto_exchanges', lazy='dynamic'))
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

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('crypto_transactions', lazy='dynamic'))

    def __repr__(self):
        return f'<CryptoTransaction {self.transaction_type} {self.crypto_name} ({self.quantity})>'

class CryptoCategoryMapping(db.Model):
    __tablename__ = 'crypto_category_mappings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mapping_type = db.Column(db.String(20), nullable=False)  # 'Tipo' o 'Descripción'
    source_value = db.Column(db.String(255), nullable=False)  # transaction_kind o transaction_description
    target_category = db.Column(db.String(50), nullable=False)  # Categoría destino
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con usuario
    user = db.relationship('User', backref=db.backref('crypto_category_mappings', lazy=True, cascade='all, delete-orphan'))
    
    # Constraint único por usuario, tipo y valor fuente
    __table_args__ = (db.UniqueConstraint('user_id', 'mapping_type', 'source_value'),)
    
    def __repr__(self):
        return f'<CryptoCategoryMapping {self.id}: {self.mapping_type} - {self.source_value} -> {self.target_category}>'

class CryptoHolding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey('crypto_exchange.id', ondelete='CASCADE'), nullable=False, index=True) # Mantener si es útil
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    crypto_name = db.Column(db.String(100), nullable=False)
    ticker_symbol = db.Column(db.String(20), nullable=False)  # BTC-EUR, ETH-EUR, etc.
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    current_price = db.Column(db.Float, nullable=True)
    price_updated_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('crypto_holdings', lazy='dynamic'))

    def __repr__(self):
        return f'<CryptoHolding {self.crypto_name} ({self.quantity})>'

class CryptoHistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total_value_eur = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('crypto_history', lazy='dynamic'))

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

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('metal_transactions', lazy='dynamic'))

    def __repr__(self):
        return f'<PreciousMetalTransaction {self.metal_type} {self.transaction_type} {self.quantity}{self.unit_type}>'

# --- Models for Debt Management ---
class DebtCeiling(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    percentage = db.Column(db.Float, nullable=False, default=5.0)  # Default 5% of salary
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('debt_ceiling', uselist=False))

    def __repr__(self):
        return f'<DebtCeiling {self.percentage}%>'

# En app.py

# En app.py

# ... other imports and model definitions ...

class DebtInstallmentPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True) 
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    expense_category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id', ondelete='SET NULL'), nullable=True)
    description = db.Column(db.String(200), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    monthly_payment = db.Column(db.Float, nullable=False)    
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    is_mortgage = db.Column(db.Boolean, default=False, nullable=False)
    linked_asset_id_for_mortgage = db.Column(db.Integer, db.ForeignKey('real_estate_asset.id'), nullable=True)

    category = db.relationship('ExpenseCategory', backref=db.backref('debt_plans_associated', lazy='select'))
    # user relationship is via backref in User.debt_plans

    # ADD THIS RELATIONSHIP:
    # This defines that a DebtInstallmentPlan can be the source ID for one RealEstateMortgage record.
    # If this DebtInstallmentPlan is deleted, the associated RealEstateMortgage record (which uses this plan's ID)
    # will also be deleted due to cascade="all, delete-orphan".
    mortgage_record_it_is_linked_to = db.relationship(
        "RealEstateMortgage",
        foreign_keys="RealEstateMortgage.debt_installment_plan_id", # Links via RealEstateMortgage.debt_installment_plan_id
        backref=db.backref("debt_installment_plan_source", uselist=False), # Allows RealEstateMortgage to access its DebtInstallmentPlan
        uselist=False, # One-to-one: one DebtInstallmentPlan ID is used by at most one RealEstateMortgage
        cascade="all, delete-orphan" # Crucial for cleanup
    )

    @property
    def end_date(self):
        if self.start_date and self.duration_months:
            month = self.start_date.month - 1 + self.duration_months
            year = self.start_date.year + month // 12
            month = month % 12 + 1
            try:
                return date(year, month, 1)
            except ValueError:
                app.logger.error(f"Fecha inválida calculada para DebtInstallmentPlan {self.id}: Año {year}, Mes {month}")
                return None
        return None

    @property
    def remaining_installments(self):
        if not self.is_active: return 0
        today = date.today()
        
        if not isinstance(self.start_date, date):
            try:
                start_date_obj = datetime.strptime(str(self.start_date), '%Y-%m-%d').date()
            except ValueError:
                return self.duration_months
        else:
            start_date_obj = self.start_date

        if today < start_date_obj: return self.duration_months
        
        months_since_start = (today.year - start_date_obj.year) * 12 + (today.month - start_date_obj.month)
        
        if today.day > 1 and start_date_obj <= today: # Consider current month as passed if not the 1st
            months_since_start += 1
            
        remaining = self.duration_months - months_since_start
        return max(0, remaining)

    @property
    def remaining_amount(self):
        monthly_payment_val = self.monthly_payment if isinstance(self.monthly_payment, (int, float)) else 0.0
        return monthly_payment_val * self.remaining_installments

    @property
    def progress_percentage(self):
        if self.duration_months == 0: return 100
        completed_installments = self.duration_months - self.remaining_installments
        # Ensure completed_installments does not exceed duration_months due to rounding or future start_dates
        completed_installments = min(completed_installments, self.duration_months)
        completed_installments = max(0, completed_installments) # Ensure not negative
        return (completed_installments / self.duration_months) * 100 if self.duration_months > 0 else 100

    def __repr__(self):
        return f'<DebtInstallmentPlan {self.description} - {self.total_amount}€ CategoryID: {self.expense_category_id}>'

# ... rest of your app.py ...

class DebtHistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    debt_amount = db.Column(db.Float, nullable=False)
    ceiling_percentage = db.Column(db.Float, nullable=False)  # Store the ceiling % at the time of record
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('debt_history', lazy='dynamic'))

    def __repr__(self):
        return f'<DebtHistoryRecord {self.date.strftime("%m/%Y")} - {self.debt_amount}€>'


# --- Modelos para Gastos ---
class ExpenseCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('expense_category.id', ondelete='SET NULL'), nullable=True)
    is_default = db.Column(db.Boolean, default=False)  # Para categorías predefinidas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('expense_categories', lazy='dynamic'))

    # Relación para subcategorías (esta está bien porque es dentro de la misma tabla)
    subcategories = db.relationship('ExpenseCategory',
                                 backref=db.backref('parent', remote_side=[id]),
                                 cascade="all, delete-orphan")

    # Relación con gastos (esta está bien, el backref está en Expense)
    expenses = db.relationship('Expense', backref='category', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id', ondelete='SET NULL'), nullable=True) # ondelete SET NULL está bien aquí
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

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('expenses', lazy='dynamic'))

    def __repr__(self):
        return f'<Expense {self.description} ({self.amount}€)>'

# --- Modelo para guardar la configuración del Resumen Financiero ---

# Modelo UserPortfolio
class UserPortfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    portfolio_data = db.Column(db.Text, nullable=True)  # JSON en formato texto
    csv_data = db.Column(db.Text, nullable=True)  # JSON en formato texto para el CSV procesado
    csv_filename = db.Column(db.String(100), nullable=True)  # Nombre del archivo CSV temporal
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('portfolio', uselist=False))


# Modelo FixedIncome
class FixedIncome(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    annual_net_salary = db.Column(db.Float, nullable=True)  # Salario neto anual
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('fixed_income', uselist=False))


# Modelo BrokerOperation
class BrokerOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    operation_type = db.Column(db.String(20), nullable=False)  # 'Ingreso', 'Retirada', 'Comisión'
    concept = db.Column(db.String(50), nullable=False)  # 'Inversión', 'Dividendos', 'Desinversión', etc.
    amount = db.Column(db.Float, nullable=False)  # Cantidad (positiva para ingresos, negativa para retiradas/comisiones)
    description = db.Column(db.Text, nullable=True)  # Descripción opcional
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('broker_operations', lazy='dynamic'))


# Modelo SalaryHistory
class SalaryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    annual_net_salary = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('salary_history', lazy='dynamic'))


# Modelo BankAccount
class BankAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    bank_name = db.Column(db.String(100), nullable=False)
    account_name = db.Column(db.String(100), nullable=True)  # Nombre optativo (ej: "Cuenta Nómina")
    current_balance = db.Column(db.Float, nullable=False, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('bank_accounts', lazy='dynamic'))

    def __repr__(self):
        return f'<BankAccount {self.bank_name} - {self.account_name} ({self.current_balance}€)>'

# Modelo CashHistoryRecord
class CashHistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    total_cash = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('cash_history', lazy='dynamic'))

    def __repr__(self):
        return f'<CashHistoryRecord {self.date.strftime("%m/%Y")} - {self.total_cash}€>'


# Modelo VariableIncomeCategory
class VariableIncomeCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('variable_income_category.id', ondelete='SET NULL'), nullable=True)
    is_default = db.Column(db.Boolean, default=False)  # Para categorías predefinidas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('variable_income_categories', lazy='dynamic'))

    # Relación para subcategorías (esta está bien)
    subcategories = db.relationship('VariableIncomeCategory',
                                 backref=db.backref('parent', remote_side=[id]),
                                 cascade="all, delete-orphan")

    # Relación con ingresos (esta está bien)
    incomes = db.relationship('VariableIncome', backref='category', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<VariableIncomeCategory {self.name}>'

# Modelo VariableIncome
class VariableIncome(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('variable_income_category.id', ondelete='SET NULL'), nullable=True) # ondelete SET NULL ok
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

    # --- ELIMINA O COMENTA ESTA LÍNEA ---
    # user = db.relationship('User', backref=db.backref('variable_incomes', lazy='dynamic'))

    def __repr__(self):
        return f'<VariableIncome {self.description} ({self.amount}€)>'


# Modelo WatchlistItem (ya tiene backref='owner', así que no necesita cambios aquí)

# ... (otros imports y modelos) ...

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

class CsvUploadForm(FlaskForm):
    exchange = SelectField(
        'Exchange', 
        choices=[('Crypto.com', 'Crypto.com')], 
        validators=[DataRequired()],
        default='Crypto.com'
    )
    csv_file = FileField(
        'Archivo CSV', 
        validators=[
            FileRequired(message='Debe seleccionar un archivo'),
            FileAllowed(['csv'], message='Solo se permiten archivos CSV')
        ]
    )
    submit = SubmitField('Cargar CSV')

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

class CryptoMovementEditForm(FlaskForm):
    category = SelectField(
        'Categoría',
        choices=[
            ('Rewards', 'Rewards'),
            ('Staking Lock', 'Staking Lock'),
            ('Staking Reward', 'Staking Reward'),
            ('Staking UnLock', 'Staking UnLock'),
            ('Compra', 'Compra'),
            ('Venta', 'Venta'),
            ('Deposito', 'Deposito'),
            ('Retiro', 'Retiro'),
            ('Sin Categoría', 'Sin Categoría')
        ],
        validators=[DataRequired()]
    )
    process_status = SelectField(
        'Procesar',
        choices=[
            ('OK', 'OK'),
            ('SKIP', 'SKIP'),
            ('Huérfano', 'Huérfano')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Guardar Cambios')

class CryptoCategoryMappingForm(FlaskForm):
    mapping_type = SelectField(
        'Mapear por',
        choices=[('Tipo', 'Tipo'), ('Descripción', 'Descripción')],
        validators=[DataRequired()]
    )
    source_value = StringField('Valor', validators=[DataRequired()],
                             render_kw={"placeholder": "Ej: viban_purchase o texto descripción"})
    target_category = SelectField(
        'Categoría',
        choices=[
            ('Rewards', 'Rewards'),
            ('Staking Lock', 'Staking Lock'),
            ('Staking Reward', 'Staking Reward'),
            ('Staking UnLock', 'Staking UnLock'),
            ('Compra', 'Compra'),
            ('Venta', 'Venta'),
            ('Deposito', 'Deposito'),
            ('Retiro', 'Retiro'),
            ('Sin Categoría', 'Sin Categoría')
        ],
        validators=[DataRequired()]
    )
    submit = SubmitField('Crear Mapeo')

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



# --- Forms for Debt Management ---
class DebtCeilingForm(FlaskForm):
    percentage = StringField('Techo de Deuda (% del Salario Neto)', validators=[DataRequired()],
                          render_kw={"placeholder": "Ej: 5.0"})
    submit = SubmitField('Guardar Techo de Deuda')

# En app.py, dentro de la definición de formularios

class DebtInstallmentPlanForm(FlaskForm):
    category_id = SelectField('Categoría del Gasto (Deuda)*', coerce=int, validators=[DataRequired(message="Debes seleccionar una categoría.")])
    
    # NUEVOS CAMPOS PARA HIPOTECA
    is_mortgage = BooleanField('Es una Hipoteca')
    linked_asset_id = SelectField('Seleccionar Inmueble Hipotecado', coerce=int, validators=[Optional()]) # Se valida en la vista si is_mortgage=True

    description = StringField('Descripción de la Deuda*', 
                              validators=[DataRequired()],
                              render_kw={"placeholder": "Ej: Préstamo coche, Tarjeta..."})
    total_amount = FloatField('Cantidad Total a Pagar (€)*', 
                               validators=[DataRequired(), NumberRange(min=0.01)], 
                               render_kw={"placeholder": "Ej: 5000.00"}) # Cambiado a FloatField
    start_date = StringField('Fecha de Inicio (Mes/Año)*', 
                             validators=[DataRequired()],
                             render_kw={"type": "month"}) # HTML5 se encargará del formato

    # NUEVO: Elección entre duración o mensualidad
    payment_input_type = RadioField('Definir por:', choices=[('duration', 'Duración'), ('monthly_amount', 'Mensualidad')], default='duration', validators=[DataRequired()])
    duration_months_input = IntegerField('Duración (Meses)*', 
                                    validators=[Optional(), NumberRange(min=1)], # Opcional, dependerá del RadioField
                                    render_kw={"placeholder": "Ej: 12", "type": "number", "min": "1"})
    monthly_payment_input = FloatField('Mensualidad (€)*', 
                                     validators=[Optional(), NumberRange(min=0.01)], # Opcional
                                     render_kw={"placeholder": "Ej: 250.50"})
    
    submit = SubmitField('Añadir Plan de Pago')

    # Validadores personalizados si es necesario para duration/monthly_payment según payment_input_type
    def validate_duration_months_input(self, field):
        if self.payment_input_type.data == 'duration' and not field.data:
            raise ValidationError('La duración es obligatoria si se define por duración.')
        if field.data is not None and field.data <= 0:
            raise ValidationError('La duración debe ser mayor que cero.')

    def validate_monthly_payment_input(self, field):
        if self.payment_input_type.data == 'monthly_amount' and not field.data:
            raise ValidationError('La mensualidad es obligatoria si se define por mensualidad.')
        if field.data is not None and field.data <= 0:
            raise ValidationError('La mensualidad debe ser mayor que cero.')
        if self.payment_input_type.data == 'monthly_amount' and self.total_amount.data and field.data > self.total_amount.data:
            raise ValidationError('La mensualidad no puede ser mayor que la cantidad total.')


class DebtHistoryForm(FlaskForm):
    month_year = StringField('Mes y Año', validators=[DataRequired()],
                          render_kw={"type": "month", "placeholder": "YYYY-MM"})
    debt_amount = StringField('Cantidad de Deuda Actual (€)', validators=[DataRequired()],
                           render_kw={"placeholder": "Ej: 500.00"})
    submit = SubmitField('Guardar Registro de Deuda')


# --- Modelos para Gastos ---
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


# In app.py

class RealEstateAssetFormPopup(FlaskForm): # Formulario simplificado para el pop-up
    property_name = StringField('Nombre del Inmueble*', validators=[DataRequired(), Length(max=150)], render_kw={"placeholder": "Ej: Apartamento Sol"})
    property_type = SelectField('Tipo de Inmueble', choices=[
        ('', '- Seleccionar Tipo -'), ('Apartamento', 'Apartamento'), ('Casa', 'Casa'), 
        ('Local Comercial', 'Local Comercial'), ('Terreno', 'Terreno'), 
        ('Garaje', 'Garaje'), ('Trastero', 'Trastero'), ('Otro', 'Otro')
    ], validators=[Optional()])
    purchase_year = IntegerField('Año de Compra', validators=[Optional(), NumberRange(min=1900, max=datetime.now().year)], render_kw={"placeholder": f"Ej: {datetime.now().year - 5}", "type":"number"})
    purchase_price = FloatField('Precio de Compra (€)', validators=[Optional(), NumberRange(min=0)], render_kw={"placeholder": "Ej: 150000"})
    submit_popup_asset = SubmitField('Guardar Inmueble y Seleccionar')


class RealEstateAssetForm(FlaskForm):
    property_name = StringField('Nombre del Inmueble*', validators=[DataRequired(), Length(max=150)], render_kw={"placeholder": "Ej: Apartamento Sol"})
    property_type = SelectField('Tipo de Inmueble', choices=[
        ('', '- Seleccionar Tipo -'),
        ('Apartamento', 'Apartamento'), 
        ('Casa', 'Casa'), 
        ('Local Comercial', 'Local Comercial'), 
        ('Terreno', 'Terreno'), 
        ('Garaje', 'Garaje'), 
        ('Trastero', 'Trastero'), 
        ('Otro', 'Otro')
    ], validators=[Optional()])
    purchase_year = IntegerField('Año de Compra', 
                                validators=[Optional(), NumberRange(min=1900, max=datetime.now().year)], 
                                render_kw={"placeholder": f"Ej: {datetime.now().year - 5}", "type": "number"})
    purchase_price = FloatField('Precio de Compra (€)', 
                                validators=[Optional(), NumberRange(min=0)], 
                                render_kw={"placeholder": "Ej: 150000"})
    
    # इंश्योर These are REMOVED or commented out:
    # is_rental = BooleanField('Es un Inmueble de Alquiler')
    # rental_income_monthly = FloatField('Ingreso Bruto Mensual por Alquiler (€)', 
    #                                    validators=[Optional(), NumberRange(min=0)], 
    #                                    render_kw={"placeholder": "Ej: 600"})
    
    submit_asset = SubmitField('Guardar Inmueble')

class ValuationEntryForm(FlaskForm):
    asset_id = SelectField('Inmueble a tasar*', coerce=int, validators=[DataRequired(message="Debe seleccionar un inmueble.")])
    valuation_year = IntegerField('Año de Tasación*', 
                                validators=[DataRequired(message="El año es obligatorio."), 
                                            NumberRange(min=1900, max=datetime.now().year + 5, message="Año inválido.")], 
                                render_kw={"placeholder": f"Ej: {datetime.now().year}", "type": "number"})
    market_value = FloatField('Valor Estimado de Mercado (€)*', 
                            validators=[DataRequired(message="El valor es obligatorio."), NumberRange(min=0)], 
                            render_kw={"placeholder": "Ej: 200000"})
    submit_valuation = SubmitField('Guardar Tasación')


class RealEstateMortgageForm(FlaskForm):
    lender_name = StringField('Entidad Prestamista', validators=[Optional(), Length(max=100)])
    original_loan_amount = FloatField('Importe Original del Préstamo (€)', validators=[Optional(), NumberRange(min=0)])
    current_principal_balance = FloatField('Saldo Principal Pendiente (€)', validators=[DataRequired(), NumberRange(min=0)])
    interest_rate_annual = FloatField('Tasa de Interés Anual (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    monthly_payment = FloatField('Cuota Mensual (€)', validators=[Optional(), NumberRange(min=0)])
    loan_term_years = IntegerField('Plazo del Préstamo (Años)', validators=[Optional(), NumberRange(min=1)])
    loan_start_date = DateField('Fecha de Inicio del Préstamo', format='%Y-%m-%d', validators=[Optional()])
    submit_mortgage = SubmitField('Guardar Hipoteca')

class RealEstateExpenseForm(FlaskForm):
    expense_category = SelectField('Categoría del Gasto', choices=[
        ('IBI', 'IBI (Impuesto sobre Bienes Inmuebles)'),
        ('Comunidad', 'Gastos de Comunidad'),
        ('Seguro Hogar', 'Seguro del Hogar'),
        ('Mantenimiento', 'Mantenimiento y Reparaciones'),
        ('Suministros', 'Suministros (si no los paga el inquilino)'),
        ('Tasa Basuras', 'Tasa de Basuras'),
        ('Gestoría Alquiler', 'Gestoría/Administración Alquiler'),
        ('Otros', 'Otros Gastos Específicos')
    ], validators=[DataRequired()])
    description = StringField('Descripción', validators=[Optional(), Length(max=200)])
    amount = FloatField('Importe (€)', validators=[DataRequired(), NumberRange(min=0)])
    date = DateField('Fecha del Gasto', format='%Y-%m-%d', validators=[DataRequired()], default=datetime.today)
    is_recurring = BooleanField('Es un Gasto Recurrente')
    recurrence_frequency = SelectField('Frecuencia', choices=[
        ('monthly', 'Mensual'), ('quarterly', 'Trimestral'), ('semiannual', 'Semestral'), ('annual', 'Anual')
    ], validators=[Optional()])
    submit_expense = SubmitField('Guardar Gasto')

class RealEstateValueHistoryForm(FlaskForm):
    date = DateField('Fecha de Valoración', format='%Y-%m-%d', validators=[DataRequired()], default=datetime.today)
    market_value = FloatField('Valor de Mercado (€)', validators=[DataRequired(), NumberRange(min=0)])
    submit_value = SubmitField('Guardar Valoración')

# --- IMPORTANTE: Revisa el resto de tus modelos (PensionPlan, CryptoExchange, etc.) ---
# Debes ELIMINAR la línea `user = db.relationship(...)` de esos otros modelos
# si la relación ya está definida con `backref` en el modelo User anterior.
# Ejemplo para FinancialSummaryConfig (y aplica un patrón similar a los demás):
class FinancialSummaryConfig(db.Model): # MOSTRANDO COMPLETA COMO EJEMPLO
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
    include_real_estate = db.Column(db.Boolean, default=True) # NUEVO CAMPO
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # La línea: user = db.relationship('User', backref=db.backref('fin_summary_config', uselist=False))
    # DEBE SER ELIMINADA O COMENTADA de aquí.

# --- Formularios WTForms ---
# RegistrationForm (sin cambios, pero la ruta /register sí cambia)


class RegistrationForm(FlaskForm): # MOSTRANDO COMPLETA CON CAMBIOS
    username = StringField('Usuario', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email(message="Correo electrónico no válido.")])
    birth_year = IntegerField('Año de Nacimiento',
                             validators=[Optional(), NumberRange(min=1900, max=datetime.now().year, message="Año inválido.")],
                             render_kw={"placeholder": "Ej: 1990"}) # NUEVO CAMPO
    password = PasswordField('Contraseña', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Contraseña', validators=[DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir.')])
    submit = SubmitField('Registrarse')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Ese nombre de usuario ya está en uso. Por favor, elige otro.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Ese correo electrónico ya está registrado. Por favor, elige otro.')


# LoginForm (sin cambios en la definición del formulario)
class LoginForm(FlaskForm): # MOSTRANDO COMPLETA
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    remember_me = BooleanField('Recuérdame')
    submit = SubmitField('Iniciar Sesión')

class RequestResetForm(FlaskForm): # MOSTRANDO COMPLETA
    email = StringField('Tu Correo Electrónico Registrado', validators=[DataRequired(), Email()])
    submit = SubmitField('Solicitar Reseteo de Contraseña')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is None:
            raise ValidationError('No hay cuenta registrada con ese correo electrónico. Debes registrarte primero.')

# NUEVO FORMULARIO para ingresar la nueva contraseña tras el reseteo
class ResetPasswordForm(FlaskForm): # MOSTRANDO COMPLETA
    password = PasswordField('Nueva Contraseña', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators=[DataRequired(), EqualTo('password', message='Las contraseñas deben coincidir.')])
    submit = SubmitField('Establecer Nueva Contraseña')

# NUEVO FORMULARIO
class ChangePasswordForm(FlaskForm): # MOSTRANDO COMPLETA CON CAMBIOS
    current_password = PasswordField('Contraseña Actual', validators=[Optional()])
    new_password = PasswordField('Nueva Contraseña', validators=[DataRequired(), Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")])
    confirm_new_password = PasswordField('Confirmar Nueva Contraseña', validators=[DataRequired(), EqualTo('new_password', message='Las contraseñas deben coincidir.')])
    submit = SubmitField('Cambiar Contraseña')

# CloseAccountForm (sin cambios en la definición del formulario)
class CloseAccountForm(FlaskForm): # MOSTRANDO COMPLETA
    password = PasswordField('Confirma tu contraseña', validators=[DataRequired()])
    confirm = BooleanField('Entiendo que esta acción es irreversible y se borrarán todos mis datos.', validators=[DataRequired()])
    submit = SubmitField('Cerrar mi cuenta permanentemente')


@app.route('/crypto_movements', methods=['GET', 'POST'])
@login_required
def crypto_movements():
    """Muestra y gestiona los movimientos de CSV de exchanges automatizados."""
    csv_form = CsvUploadForm()
    mapping_form = CryptoCategoryMappingForm()
    
    # Procesar creación de mapeo de categorías
    if mapping_form.validate_on_submit() and 'create_mapping' in request.form:
        try:
            # Verificar si ya existe el mapeo
            existing_mapping = CryptoCategoryMapping.query.filter_by(
                user_id=current_user.id,
                mapping_type=mapping_form.mapping_type.data,
                source_value=mapping_form.source_value.data
            ).first()
            
            if existing_mapping:
                existing_mapping.target_category = mapping_form.target_category.data
                flash(f'Mapeo actualizado: {mapping_form.source_value.data} → {mapping_form.target_category.data}', 'success')
            else:
                new_mapping = CryptoCategoryMapping(
                    user_id=current_user.id,
                    mapping_type=mapping_form.mapping_type.data,
                    source_value=mapping_form.source_value.data,
                    target_category=mapping_form.target_category.data
                )
                db.session.add(new_mapping)
                flash(f'Mapeo creado: {mapping_form.source_value.data} → {mapping_form.target_category.data}', 'success')
            
            db.session.commit()
            
            # Aplicar el nuevo mapeo a movimientos existentes
            apply_category_mapping_to_existing(current_user.id, mapping_form.mapping_type.data, 
                                             mapping_form.source_value.data, mapping_form.target_category.data)
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creando mapeo: {str(e)}', 'danger')
    
    # Procesar carga de CSV
    if csv_form.validate_on_submit() and 'upload_csv' in request.form:
        try:
            uploaded_file = csv_form.csv_file.data
            exchange_name = csv_form.exchange.data
            filename = secure_filename(uploaded_file.filename)
            
            # Leer el contenido del CSV
            stream = io.StringIO(uploaded_file.stream.read().decode("utf-8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            movements_added = 0
            duplicates_found = 0
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    # Parsear la fecha
                    timestamp_str = row.get('Timestamp (UTC)', '').strip()
                    timestamp_utc = None
                    if timestamp_str:
                        try:
                            timestamp_utc = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                timestamp_utc = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                            except ValueError:
                                errors.append(f"Fila {row_num}: Formato de fecha inválido: {timestamp_str}")
                                continue
                    
                    # Convertir valores numéricos
                    amount = None
                    to_amount = None
                    native_amount = None
                    native_amount_in_usd = None
                    
                    try:
                        amount_str = row.get('Amount', '').strip()
                        if amount_str and amount_str != '':
                            amount = float(amount_str)
                    except (ValueError, TypeError):
                        pass
                    
                    try:
                        to_amount_str = row.get('To Amount', '').strip()
                        if to_amount_str and to_amount_str != '':
                            to_amount = float(to_amount_str)
                    except (ValueError, TypeError):
                        pass
                    
                    try:
                        native_amount_str = row.get('Native Amount', '').strip()
                        if native_amount_str and native_amount_str != '':
                            native_amount = float(native_amount_str)
                    except (ValueError, TypeError):
                        pass
                    
                    try:
                        native_amount_usd_str = row.get('Native Amount (in USD)', '').strip()
                        if native_amount_usd_str and native_amount_usd_str != '':
                            native_amount_in_usd = float(native_amount_usd_str)
                    except (ValueError, TypeError):
                        pass
                    
                    # Crear movimiento temporal para generar hash
                    transaction_description = row.get('Transaction Description', '').strip()
                    transaction_kind = row.get('Transaction Kind', '').strip()
                    native_currency = row.get('Native Currency', '').strip()
                    
                    temp_movement = CryptoCsvMovement(
                        user_id=current_user.id,
                        exchange_name=exchange_name,
                        timestamp_utc=timestamp_utc,
                        transaction_description=transaction_description,
                        currency=row.get('Currency', '').strip(),
                        amount=amount,
                        to_currency=row.get('To Currency', '').strip(),
                        to_amount=to_amount,
                        native_currency=native_currency,
                        native_amount=native_amount,
                        native_amount_in_usd=native_amount_in_usd,
                        transaction_kind=transaction_kind,
                        transaction_hash=row.get('Transaction Hash', '').strip(),
                        csv_filename=filename
                    )
                    
                    # Generar hash único
                    transaction_hash_unique = temp_movement.generate_hash()
                    
                    # Verificar si ya existe este hash
                    existing_movement = CryptoCsvMovement.query.filter_by(
                        user_id=current_user.id,
                        transaction_hash_unique=transaction_hash_unique
                    ).first()
                    
                    if existing_movement:
                        duplicates_found += 1
                        continue
                    
                    # Añadir hash al movimiento
                    temp_movement.transaction_hash_unique = transaction_hash_unique
                    
                    # Categorizar automáticamente
                    category = categorize_transaction(transaction_kind, transaction_description, current_user.id)
                    temp_movement.category = category
                    
                    # Establecer estado de procesamiento
                    if category == 'Sin Categoría':
                        temp_movement.process_status = 'SKIP'
                    else:
                        temp_movement.process_status = 'OK'
                    
                    # Convertir USD a EUR si es necesario
                    if native_currency == 'USD' and native_amount is not None and timestamp_utc is not None:
                        exchange_rate = get_usd_to_eur_rate(timestamp_utc)
                        temp_movement.native_amount = native_amount * exchange_rate
                        temp_movement.native_currency = 'EUR'
                    
                    db.session.add(temp_movement)
                    movements_added += 1
                    
                except Exception as e:
                    errors.append(f"Fila {row_num}: Error procesando datos - {str(e)}")
                    continue
            
            # Guardar en la base de datos
            db.session.commit()
            
            # Detectar huérfanos después de añadir los nuevos movimientos
            all_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id).all()
            orphan_ids = detect_orphans(all_movements)
            
            # Actualizar estado de huérfanos
            if orphan_ids:
                CryptoCsvMovement.query.filter(
                    CryptoCsvMovement.id.in_(orphan_ids),
                    CryptoCsvMovement.user_id == current_user.id
                ).update({'process_status': 'Huérfano'}, synchronize_session=False)
                db.session.commit()
            
            # Mostrar resultado
            if movements_added > 0:
                flash(f'CSV procesado correctamente. {movements_added} movimientos añadidos.', 'success')
                if duplicates_found > 0:
                    flash(f'{duplicates_found} movimientos duplicados omitidos.', 'info')
                if len(orphan_ids) > 0:
                    flash(f'{len(orphan_ids)} movimientos marcados como huérfanos.', 'warning')
                if errors:
                    flash(f'Se encontraron {len(errors)} errores en algunas filas.', 'warning')
            elif duplicates_found > 0:
                flash(f'No se añadieron movimientos nuevos. {duplicates_found} duplicados encontrados.', 'warning')
            else:
                flash('No se pudieron procesar movimientos del CSV.', 'warning')
                
            if errors:
                for error in errors[:5]:
                    flash(error, 'danger')
                if len(errors) > 5:
                    flash(f'... y {len(errors) - 5} errores más.', 'danger')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error procesando el archivo CSV: {str(e)}', 'danger')
    
    # Obtener parámetros de búsqueda
    search_query = request.args.get('search', '').strip()
    
    # Construir query base
    movements_query = CryptoCsvMovement.query.filter_by(user_id=current_user.id)
    
    # Aplicar filtro de búsqueda si existe
    if search_query:
        movements_query = movements_query.filter(
            db.or_(
                CryptoCsvMovement.currency.ilike(f'%{search_query}%'),
                CryptoCsvMovement.transaction_description.ilike(f'%{search_query}%'),
                CryptoCsvMovement.transaction_kind.ilike(f'%{search_query}%'),
                CryptoCsvMovement.category.ilike(f'%{search_query}%')
            )
        )
    
    # Obtener movimientos ordenados por fecha
    movements = movements_query.order_by(CryptoCsvMovement.timestamp_utc.desc()).all()
    
    # Estadísticas
    total_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id).count()
    exchanges_count = len(set(m.exchange_name for m in CryptoCsvMovement.query.filter_by(user_id=current_user.id).all())) if total_movements > 0 else 0
    orphans_count = CryptoCsvMovement.query.filter_by(user_id=current_user.id, process_status='Huérfano').count()
    uncategorized_count = CryptoCsvMovement.query.filter_by(user_id=current_user.id, category='Sin Categoría').count()
    
    # Calcular P&L por criptomoneda
    crypto_pnl_data = calculate_crypto_pnl(CryptoCsvMovement.query.filter_by(user_id=current_user.id).all())
    
    # Obtener mapeos existentes
    existing_mappings = CryptoCategoryMapping.query.filter_by(user_id=current_user.id).order_by(
        CryptoCategoryMapping.mapping_type, CryptoCategoryMapping.source_value
    ).all()
    
    return render_template(
        'crypto_movements.html',
        csv_form=csv_form,
        mapping_form=mapping_form,
        movements=movements,
        total_movements=total_movements,
        exchanges_count=exchanges_count,
        orphans_count=orphans_count,
        uncategorized_count=uncategorized_count,
        crypto_pnl_data=crypto_pnl_data,
        existing_mappings=existing_mappings,
        search_query=search_query
    )


def apply_category_mapping_to_existing(user_id, mapping_type, source_value, target_category):
    """Aplica un mapeo de categoría a movimientos existentes"""
    try:
        if mapping_type == 'Tipo':
            movements_to_update = CryptoCsvMovement.query.filter_by(
                user_id=user_id,
                transaction_kind=source_value
            ).all()
        else:  # Descripción
            movements_to_update = CryptoCsvMovement.query.filter_by(
                user_id=user_id,
                transaction_description=source_value
            ).all()
        
        updated_count = 0
        for movement in movements_to_update:
            movement.category = target_category
            # Actualizar process_status según la nueva categoría
            if target_category == 'Sin Categoría':
                movement.process_status = 'SKIP'
            elif movement.process_status == 'SKIP' and target_category != 'Sin Categoría':
                movement.process_status = 'OK'
            updated_count += 1
        
        db.session.commit()
        
        # Recalcular huérfanos después del cambio de categorías
        all_movements = CryptoCsvMovement.query.filter_by(user_id=user_id).all()
        orphan_ids = detect_orphans(all_movements)
        
        # Actualizar estado de huérfanos
        if orphan_ids:
            CryptoCsvMovement.query.filter(
                CryptoCsvMovement.id.in_(orphan_ids),
                CryptoCsvMovement.user_id == user_id
            ).update({'process_status': 'Huérfano'}, synchronize_session=False)
            db.session.commit()
        
        if updated_count > 0:
            flash(f'{updated_count} movimientos actualizados con la nueva categoría.', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error aplicando mapeo: {str(e)}', 'danger')

def log_activity(action_type, message, actor_user=None, target_user=None, details=None):
    try:
        log = ActivityLog(
            action_type=action_type,
            message=message,
            details=json.dumps(details) if details is not None else None, # Guardar detalles como JSON
            ip_address=request.remote_addr
        )
        if actor_user and actor_user.is_authenticated:
            log.user_id = actor_user.id
            log.username = actor_user.username
        
        if target_user:
            log.target_user_id = target_user.id
            log.target_username = target_user.username
            
        db.session.add(log)
        db.session.commit() # Commit individual para logs o agruparlos
    except Exception as e:
        app.logger.error(f"Error al registrar actividad: {action_type} - {e}", exc_info=True)
        db.session.rollback() # Asegurar rollback si el commit del log falla

def get_usd_to_eur_rate(date):
    """Obtiene el tipo de cambio USD->EUR para una fecha específica"""
    try:
        date_str = date.strftime('%Y-%m-%d')
        url = f"https://api.frankfurter.app/{date_str}?from=USD&to=EUR"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('rates', {}).get('EUR', 1.0)
        else:
            # Si falla, usar tipo de cambio actual como fallback
            current_rate = get_exchange_rate('USD', 'EUR')
            return current_rate if current_rate else 1.0
    except Exception as e:
        print(f"Error obteniendo tipo de cambio para {date_str}: {e}")
        return 1.0

def categorize_transaction(transaction_kind, transaction_description, user_id):
    """Categoriza una transacción basada en transaction_kind, descripción y mapeos del usuario"""

    # Primero verificar mapeos personalizados del usuario por tipo
    user_mapping_type = CryptoCategoryMapping.query.filter_by(
        user_id=user_id,
        mapping_type='Tipo',
        source_value=transaction_kind
    ).first()

    if user_mapping_type:
        return user_mapping_type.target_category

    # Luego verificar mapeos personalizados por descripción
    user_mapping_desc = CryptoCategoryMapping.query.filter_by(
        user_id=user_id,
        mapping_type='Descripción',
        source_value=transaction_description
    ).first()

    if user_mapping_desc:
        return user_mapping_desc.target_category

    # Categorización automática por defecto
    if transaction_kind in BUY_TRANSACTION_KINDS:
        return 'Compra'
    elif transaction_kind in SELL_TRANSACTION_KINDS:
        return 'Venta'
    elif transaction_kind in REWARD_TRANSACTION_KINDS:
        return 'Rewards'
    else:
        return 'Sin Categoría'

def detect_orphans(movements):
    """Detecta movimientos huérfanos basado en acumulados por criptomoneda"""
    
    # Agrupar por moneda y ordenar por fecha
    currency_movements = {}
    for movement in movements:
        if movement.currency and movement.category in ['Compra', 'Venta', 'Staking Lock', 'Staking UnLock']:
            if movement.currency not in currency_movements:
                currency_movements[movement.currency] = []
            currency_movements[movement.currency].append(movement)
    
    # Ordenar cada grupo por fecha
    for currency in currency_movements:
        currency_movements[currency].sort(key=lambda x: x.timestamp_utc or datetime.min)
    
    orphans = []
    
    for currency, movements_list in currency_movements.items():
        balance = 0.0
        staking_balance = 0.0
        
        for movement in movements_list:
            if movement.category == 'Compra' and movement.amount:
                balance += movement.amount
            elif movement.category == 'Venta' and movement.amount:
                if balance < movement.amount:
                    orphans.append(movement.id)
                else:
                    balance -= movement.amount
            elif movement.category == 'Staking Lock' and movement.amount:
                staking_balance += movement.amount
            elif movement.category == 'Staking UnLock' and movement.amount:
                if staking_balance < movement.amount:
                    orphans.append(movement.id)
                else:
                    staking_balance -= movement.amount
    
    return orphans

def calculate_crypto_pnl(movements):
    """Calcula P&L por criptomoneda basado en movimientos de compra/venta no huérfanos"""
    
    # Filtrar solo movimientos válidos para P&L
    valid_movements = [
        m for m in movements 
        if m.category in ['Compra', 'Venta'] 
        and m.process_status != 'Huérfano'
        and m.currency
        and m.native_amount
    ]
    
    # Agrupar por moneda
    currency_data = {}
    
    for movement in valid_movements:
        if movement.currency not in currency_data:
            currency_data[movement.currency] = {
                'compras': [],
                'ventas': [],
                'total_invested': 0.0,
                'total_sold': 0.0,
                'realized_pnl': 0.0
            }
        
        if movement.category == 'Compra':
            currency_data[movement.currency]['compras'].append(movement)
            currency_data[movement.currency]['total_invested'] += abs(movement.native_amount)
        elif movement.category == 'Venta':
            currency_data[movement.currency]['ventas'].append(movement)
            currency_data[movement.currency]['total_sold'] += abs(movement.native_amount)
    
    # Calcular P&L realizado
    pnl_data = []
    for currency, data in currency_data.items():
        if data['ventas']:  # Solo incluir si hay ventas registradas
            realized_pnl = data['total_sold'] - data['total_invested']
            pnl_percentage = (realized_pnl / data['total_invested'] * 100) if data['total_invested'] > 0 else 0
            
            pnl_data.append({
                'currency': currency,
                'total_invested': data['total_invested'],
                'total_sold': data['total_sold'],
                'realized_pnl': realized_pnl,
                'pnl_percentage': pnl_percentage,
                'num_compras': len(data['compras']),
                'num_ventas': len(data['ventas'])
            })
    
    return sorted(pnl_data, key=lambda x: abs(x['realized_pnl']), reverse=True)

def convert_usd_to_eur(movements):
    """Convierte cantidades nativas de USD a EUR usando tipos de cambio históricos"""
    for movement in movements:
        if (movement.native_currency == 'USD' and 
            movement.native_amount is not None and 
            movement.timestamp_utc is not None):
            
            # Obtener tipo de cambio para la fecha de la transacción
            exchange_rate = get_usd_to_eur_rate(movement.timestamp_utc)
            
            # Convertir la cantidad
            movement.native_amount = movement.native_amount * exchange_rate
            movement.native_currency = 'EUR'
    
    return movements

def group_top_n_for_pie(data_dict, top_n=7):
    if not data_dict: return {"labels": [], "data": []}
    sorted_items = sorted(data_dict.items(), key=lambda item: item[1], reverse=True)
    labels, data = [], []
    other_sum = 0.0
    for i, (key, value) in enumerate(sorted_items):
        if value <= 0: continue
        if i < top_n:
            labels.append(key)
            data.append(round(value, 2))
        else:
            other_sum += value
    if other_sum > 0:
        labels.append('Otros')
        data.append(round(other_sum, 2))
    return {"labels": labels, "data": data}


def get_current_financial_crosstime_metrics(user_id):
    broker_ops = BrokerOperation.query.filter_by(user_id=user_id).order_by(BrokerOperation.date.asc()).all()
    _, csv_data_list, _ = load_user_portfolio(user_id)
    asset_movements_raw = csv_data_list if csv_data_list and isinstance(csv_data_list, list) else []

    all_events = []
    for op in broker_ops:
        is_external_cf = op.operation_type in ['Ingreso', 'Retirada', 'Comisión']
        cf_value = 0.0
        if op.operation_type == 'Ingreso': cf_value = -op.amount
        elif op.operation_type == 'Retirada': cf_value = -op.amount 
        elif op.operation_type == 'Comisión': cf_value = op.amount 

        all_events.append({
            'date': op.date, 'type': 'broker_op', 'value': op.amount,
            'is_external_ewc_cf': is_external_cf, 'ewc_cf_value': cf_value
        })

    for movement in asset_movements_raw:
        fecha_str, total_val, isin, cantidad_abs = movement.get('Fecha'), movement.get('Total'), movement.get('ISIN'), movement.get('Cantidad')
        if fecha_str and isinstance(fecha_str, str) and total_val is not None and isin and cantidad_abs is not None:
            try:
                event_date = datetime.strptime(fecha_str[:10], '%Y-%m-%d').date()
                all_events.append({
                    'date': event_date, 'type': 'asset_trade',
                    'value': float(total_val), 'isin': isin, 'cantidad': float(cantidad_abs),
                    'is_external_ewc_cf': False, 'ewc_cf_value': 0.0
                })
            except Exception as e: app.logger.warning(f"Metrics: Error procesando movimiento: {movement}, Error: {e}")
        else: app.logger.warning(f"Metrics: Movimiento omitido por datos faltantes: {movement}")
            
    if not all_events:
        return {
            'current_capital_propio': 0.0, 'current_trading_cash_flow': 0.0,
            'current_realized_specific_pnl': 0.0, 'current_apalancamiento': 0.0,
            'first_event_date': None, 'last_event_date': None,
            'total_cost_of_all_buys_ever': 0.0,
            'twr_ewc_percentage': 0.0, 'twr_ewc_annualized_percentage': 0.0,
            'daily_chart_labels': [], 'daily_capital_propio_series': [], 
            'daily_apalancamiento_series': [], 'daily_realized_specific_pnl_series': [],
            'daily_twr_ewc_index_series': [], # Se mantiene para la lógica interna
            'daily_twr_percentage_series': [] # Se añade la nueva serie
        }

    all_events.sort(key=lambda x: (x['date'], 0 if x['is_external_ewc_cf'] else 1))

    first_event_date_overall = all_events[0]['date']
    
    daily_chart_labels = []
    daily_capital_propio_series = []
    daily_apalancamiento_series = []
    daily_realized_specific_pnl_series = []
    daily_twr_ewc_index_series = [] # Esta es la serie base 100 original

    cp_acc = 0.0; tcf_acc = 0.0; rsp_acc = 0.0
    holdings = {}; total_buy_cost_acc = 0.0
    
    twr_factors = []
    cte_after_prev_cf = 0.0 
    current_twr_idx = 100.0   
    twr_started = False       
    first_cf_date_for_annualization = None
    
    final_apalancamiento_calculated = 0.0 

    unique_dates = sorted(list(set(e['date'] for e in all_events)))
    event_pointer = 0

    for current_day in unique_dates:
        temp_event_pointer_for_cf = event_pointer
        ewc_before_any_cf_today = (-cp_acc) + rsp_acc 

        while temp_event_pointer_for_cf < len(all_events) and all_events[temp_event_pointer_for_cf]['date'] == current_day:
            event = all_events[temp_event_pointer_for_cf]
            if event['is_external_ewc_cf']:
                ewc_val_for_factor_calc = (-cp_acc) + rsp_acc 
                if twr_started:
                    if abs(cte_after_prev_cf) > 1e-9:
                        period_factor = ewc_val_for_factor_calc / cte_after_prev_cf
                        twr_factors.append(period_factor)
                        current_twr_idx *= period_factor
                    elif ewc_val_for_factor_calc == 0 and cte_after_prev_cf == 0:
                        twr_factors.append(1.0)
                
                cp_acc_before_cf_event = cp_acc 
                cp_acc += event['value'] 
                
                cte_after_prev_cf = (-cp_acc) + rsp_acc 

                if not twr_started and abs(cte_after_prev_cf) > 1e-9:
                    twr_started = True
                    current_twr_idx = 100.0 
                    if first_cf_date_for_annualization is None:
                         first_cf_date_for_annualization = current_day
            temp_event_pointer_for_cf +=1
        
        temp_rsp_day_change = 0.0
        temp_tcf_day_change = 0.0

        while event_pointer < len(all_events) and all_events[event_pointer]['date'] == current_day:
            event = all_events[event_pointer]
            if event['type'] == 'broker_op': 
                if not event['is_external_ewc_cf']:
                     pass
            elif event['type'] == 'asset_trade':
                temp_tcf_day_change += event['value']
                isin, qty, val = event['isin'], event['cantidad'], event['value']
                if val < 0: 
                    total_buy_cost_acc += abs(val)
                    if isin not in holdings: holdings[isin] = {'qty': 0.0, 'total_cost_basis': 0.0}
                    holdings[isin]['qty'] += qty
                    holdings[isin]['total_cost_basis'] += abs(val)
                elif val > 0: 
                    if isin in holdings and holdings[isin]['qty'] > 1e-6:
                        p = holdings[isin]; avg_c = p['total_cost_basis']/p['qty'] if p['qty'] > 0 else 0
                        q_sold = min(qty, p['qty']); cost_sold = q_sold * avg_c
                        proceeds = (val/qty)*q_sold if qty > 0 else 0
                        pnl_sale = proceeds - cost_sold
                        temp_rsp_day_change += pnl_sale 
                        p['qty'] -= q_sold; p['total_cost_basis'] -= cost_sold
                        if p['qty'] < 1e-6: p['qty'] = 0.0; p['total_cost_basis'] = 0.0
            event_pointer += 1
        
        rsp_acc += temp_rsp_day_change
        tcf_acc += temp_tcf_day_change

        val_inv_bruto = max(0, -tcf_acc); aport_netas_usr = max(0, -cp_acc)
        gnc_netas_tr_cf = max(0, tcf_acc); fondos_disp_s_d = aport_netas_usr + gnc_netas_tr_cf
        apalancamiento_eod = max(0, val_inv_bruto - fondos_disp_s_d)
        final_apalancamiento_calculated = apalancamiento_eod 

        daily_chart_labels.append(current_day.strftime('%Y-%m-%d'))
        daily_capital_propio_series.append(round(cp_acc, 2))
        daily_apalancamiento_series.append(round(apalancamiento_eod, 2))
        daily_realized_specific_pnl_series.append(round(rsp_acc, 2))
        
        if twr_started:
            ewc_eod = (-cp_acc) + rsp_acc 
            if abs(cte_after_prev_cf) > 1e-9:
                factor_interno_periodo = ewc_eod / cte_after_prev_cf 
                daily_twr_ewc_index_series.append(round(current_twr_idx * factor_interno_periodo, 2))
            else:
                 daily_twr_ewc_index_series.append(round(current_twr_idx, 2))
        else:
            daily_twr_ewc_index_series.append(100.0)

    last_event_date_overall = all_events[-1]['date'] if all_events else date.today()

    final_overall_twr_factor = 1.0
    if twr_factors:
        for factor in twr_factors: final_overall_twr_factor *= factor
    
    final_ewc_val_for_last_factor = (-cp_acc) + rsp_acc 
    if twr_started and abs(cte_after_prev_cf) > 1e-9: 
         last_stretch_factor = final_ewc_val_for_last_factor / cte_after_prev_cf
         final_overall_twr_factor *= last_stretch_factor
    elif twr_started and final_ewc_val_for_last_factor == 0 and cte_after_prev_cf == 0:
         final_overall_twr_factor *= 1.0

    twr_ewc_percentage = (final_overall_twr_factor - 1) * 100 if twr_started else 0.0
    
    twr_ewc_annualized_percentage = 0.0
    if twr_started and first_cf_date_for_annualization and last_event_date_overall:
        if final_overall_twr_factor > 0:
            dias_periodo_twr = (last_event_date_overall - first_cf_date_for_annualization).days
            if dias_periodo_twr >= 1:
                anios_periodo_twr = max(dias_periodo_twr / 365.25, 1/365.25)
                twr_ewc_annualized_percentage = (math.pow(final_overall_twr_factor, 1.0 / anios_periodo_twr) - 1) * 100
            elif dias_periodo_twr == 0 :
                 twr_ewc_annualized_percentage = twr_ewc_percentage
        elif final_overall_twr_factor <= 0 and abs(cte_after_prev_cf if cte_after_prev_cf is not None else 0.0) > 1e-9 :
            twr_ewc_annualized_percentage = -100.0

    current_apalancamiento_final = final_apalancamiento_calculated 

    # --- MODIFICACIÓN AQUÍ: Transformar la serie de índice a porcentaje ---
    daily_twr_percentage_series = [round(val - 100, 2) if isinstance(val, (int, float)) else 0 for val in daily_twr_ewc_index_series]
    # --- FIN DE LA MODIFICACIÓN ---

    return {
        'current_capital_propio': round(cp_acc, 2),
        'current_trading_cash_flow': round(tcf_acc, 2),
        'current_realized_specific_pnl': round(rsp_acc, 2),
        'current_apalancamiento': round(current_apalancamiento_final, 2),
        'first_event_date': first_event_date_overall,
        'last_event_date': last_event_date_overall,
        'total_cost_of_all_buys_ever': round(total_buy_cost_acc, 2),
        'twr_ewc_percentage': round(twr_ewc_percentage, 2) if isinstance(twr_ewc_percentage, float) and math.isfinite(twr_ewc_percentage) else "N/A",
        'twr_ewc_annualized_percentage': round(twr_ewc_annualized_percentage, 2) if isinstance(twr_ewc_annualized_percentage, float) and math.isfinite(twr_ewc_annualized_percentage) else "N/A",
        'daily_chart_labels': daily_chart_labels,
        'daily_capital_propio_series': daily_capital_propio_series,
        'daily_apalancamiento_series': daily_apalancamiento_series,
        'daily_realized_specific_pnl_series': daily_realized_specific_pnl_series,
        'daily_twr_ewc_index_series': daily_twr_ewc_index_series, # Se mantiene por si se usa en otro lado o para referencia
        'daily_twr_percentage_series': daily_twr_percentage_series # Se añade la nueva serie para el gráfico
    }


@app.route('/edit_crypto_movement/<int:movement_id>', methods=['GET', 'POST'])
@login_required
def edit_crypto_movement(movement_id):
    """Edita un movimiento de criptomoneda específico"""
    movement = CryptoCsvMovement.query.filter_by(
        id=movement_id,
        user_id=current_user.id
    ).first_or_404()
    
    form = CryptoMovementEditForm()
    
    if form.validate_on_submit():
        try:
            movement.category = form.category.data
            movement.process_status = form.process_status.data
            
            # Si se marca como "Sin Categoría", automáticamente debe ser "SKIP"
            if movement.category == 'Sin Categoría':
                movement.process_status = 'SKIP'
            
            db.session.commit()
            
            # Recalcular huérfanos después del cambio
            all_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id).all()
            orphan_ids = detect_orphans(all_movements)
            
            # Actualizar estado de huérfanos
            if orphan_ids:
                CryptoCsvMovement.query.filter(
                    CryptoCsvMovement.id.in_(orphan_ids),
                    CryptoCsvMovement.user_id == current_user.id
                ).update({'process_status': 'Huérfano'}, synchronize_session=False)
                db.session.commit()
            
            flash('Movimiento actualizado correctamente.', 'success')
            return redirect(url_for('crypto_movements'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error actualizando movimiento: {str(e)}', 'danger')
    
    # Pre-llenar el formulario con los datos actuales
    if request.method == 'GET':
        form.category.data = movement.category
        form.process_status.data = movement.process_status
    
    return render_template('edit_crypto_movement.html', form=form, movement=movement)

@app.route('/delete_crypto_mapping/<int:mapping_id>', methods=['POST'])
@login_required
def delete_crypto_mapping(mapping_id):
    """Elimina un mapeo de categoría"""
    mapping = CryptoCategoryMapping.query.filter_by(
        id=mapping_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        db.session.delete(mapping)
        db.session.commit()
        flash('Mapeo eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error eliminando mapeo: {str(e)}', 'danger')
    
    return redirect(url_for('crypto_movements'))

@app.route('/recalculate_crypto_orphans', methods=['POST'])
@login_required
def recalculate_crypto_orphans():
    """Recalcula todos los movimientos huérfanos"""
    try:
        # Resetear todos los estados que no sean 'SKIP'
        CryptoCsvMovement.query.filter(
            CryptoCsvMovement.user_id == current_user.id,
            CryptoCsvMovement.process_status != 'SKIP'
        ).update({'process_status': 'OK'}, synchronize_session=False)
        
        # Recalcular huérfanos
        all_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id).all()
        orphan_ids = detect_orphans(all_movements)
        
        # Actualizar estado de huérfanos
        if orphan_ids:
            CryptoCsvMovement.query.filter(
                CryptoCsvMovement.id.in_(orphan_ids),
                CryptoCsvMovement.user_id == current_user.id
            ).update({'process_status': 'Huérfano'}, synchronize_session=False)
        
        db.session.commit()
        flash(f'Recálculo completado. {len(orphan_ids)} movimientos marcados como huérfanos.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error recalculando huérfanos: {str(e)}', 'danger')
    
    return redirect(url_for('crypto_movements'))

@app.route('/capital_evolution')
@login_required
def capital_evolution():
    all_metrics_and_series = get_current_financial_crosstime_metrics(current_user.id)

    # >>> INICIO DE LA MODIFICACIÓN <<<
    chart_data = {
        'labels': all_metrics_and_series['daily_chart_labels'],
        'capitalPropio': all_metrics_and_series['daily_capital_propio_series'],
        'apalancamiento': all_metrics_and_series['daily_apalancamiento_series'],
        'tradingPnL': all_metrics_and_series['daily_realized_specific_pnl_series'],
        # Cambiamos twrIndex por twrPercentage y usamos la nueva serie
        'twrPercentage': all_metrics_and_series.get('daily_twr_percentage_series', [])
    }
    # >>> FIN DE LA MODIFICACIÓN <<<

    return render_template('capital_evolution.html',
                           chart_data=chart_data,
                           title="Evolución de Capital")


# En app.py

# ... (otros imports y código) ...

@app.route('/portfolio_dashboard_data')
@login_required
def portfolio_dashboard_data():
    user_id = current_user.id
    portfolio_summary_from_db, _, _ = load_user_portfolio(user_id) # Esto carga las posiciones del portfolio

    # Lógica para calcular datos de distribución por sector y país (basado en tu código)
    watchlist_items_db = WatchlistItem.query.filter_by(user_id=user_id).all()
    watchlist_map = {
        item.isin: {'sector': item.sector, 'pais': item.pais}
        for item in watchlist_items_db if item.isin
    }
    sector_values = {}
    country_values = {}
    total_market_value_eur = 0.0 # Para la suma del valor de mercado de las posiciones
    total_cost_basis_eur_open_positions = 0.0 # Para la suma del coste base de posiciones abiertas
    total_unrealized_pl_eur = 0.0 # Para la suma de P/L no realizada de posiciones abiertas

    if portfolio_summary_from_db: # portfolio_summary_from_db es la lista de items/posiciones
        for item in portfolio_summary_from_db:
            try:
                market_value = float(item.get('market_value_eur', 0.0) or 0.0) # or 0.0 para manejar None
                item_cost_basis = float(item.get('cost_basis_eur_est', 0.0) or 0.0)
                item_pl_eur = float(item.get('pl_eur_est', 0.0) or 0.0)
                isin = item.get('ISIN')

                total_market_value_eur += market_value
                total_cost_basis_eur_open_positions += item_cost_basis
                total_unrealized_pl_eur += item_pl_eur

                sector = 'Desconocido/Otros'
                if isin and isin in watchlist_map and watchlist_map[isin].get('sector'):
                    sector_item = watchlist_map[isin]['sector']
                    if sector_item and sector_item.strip(): sector = sector_item
                sector_values[sector] = sector_values.get(sector, 0.0) + market_value

                pais = 'Desconocido/Otros'
                if isin and isin in watchlist_map and watchlist_map[isin].get('pais'):
                    pais_item = watchlist_map[isin]['pais']
                    if pais_item and pais_item.strip(): pais = pais_item
                country_values[pais] = country_values.get(pais, 0.0) + market_value
            except (ValueError, TypeError) as e:
                app.logger.error(f"Dashboard: Error procesando item del portfolio {item.get('ISIN')} para gráficos de tarta: {e}")
                continue

    # Obtener métricas cruzadas en el tiempo (incluyendo Capital Propio y Apalancamiento)
    crosstime_metrics = get_current_financial_crosstime_metrics(user_id)

    # >>> INICIO DE LA MODIFICACIÓN: Aplicar abs() a current_capital_propio <<<
    current_capital_propio_abs = abs(crosstime_metrics.get('current_capital_propio', 0))
    # >>> FIN DE LA MODIFICACIÓN <<<
    
    current_apalancamiento = crosstime_metrics.get('current_apalancamiento', 0)
    current_realized_specific_pnl = crosstime_metrics.get('current_realized_specific_pnl', 0)
    rentabilidad_acumulada_percentage = crosstime_metrics.get('twr_ewc_percentage', "N/A")
    rentabilidad_media_anual_percentage = crosstime_metrics.get('twr_ewc_annualized_percentage', "N/A")

    beneficio_perdida_global = total_unrealized_pl_eur + current_realized_specific_pnl
    overall_return_percentage_open_positions = (total_unrealized_pl_eur / total_cost_basis_eur_open_positions * 100) if total_cost_basis_eur_open_positions != 0 else 0

    sector_chart_data = group_top_n_for_pie(sector_values)
    country_chart_data = group_top_n_for_pie(country_values)

    data_to_return = {
        "summary_metrics": {
            "total_market_value_eur": round(total_market_value_eur, 2),
            "total_cost_basis_eur_open_positions": round(total_cost_basis_eur_open_positions, 2),
            "total_unrealized_pl_eur": round(total_unrealized_pl_eur, 2),
            "overall_return_percentage_open_positions": round(overall_return_percentage_open_positions, 2),
            "current_capital_propio": current_capital_propio_abs, # Usar el valor absoluto
            "current_apalancamiento": current_apalancamiento, # Ya es >= 0
            "beneficio_perdida_global": round(beneficio_perdida_global, 2),
            "rentabilidad_acumulada_percentage": rentabilidad_acumulada_percentage,
            "rentabilidad_media_anual_percentage": rentabilidad_media_anual_percentage
        },
        "sector_distribution": sector_chart_data,
        "country_distribution": country_chart_data
    }
    return jsonify(data_to_return)

# ... (resto de tu código app.py) ...

# --- User Loader ---
@login_manager.user_loader
def load_user(user_id): # MOSTRANDO COMPLETA
    return db.session.get(User, int(user_id))

# En app.py
def calculate_portfolio_cost_basis(user_id):
    """
    Calcula el coste base total del portfolio actual del usuario.
    Similar a la lógica en capital_evolution, pero solo para posiciones abiertas.
    """
    # Cargar movimientos de activos para recalcular coste base de posiciones actuales
    # Esta es la parte más compleja: necesitaríamos recrear el estado de 'holdings_avg_cost'
    # basado en todos los movimientos históricos para llegar al portfolio actual.
    # O, si el UserPortfolio ya almacena el coste base por posición, usar eso.

    # Alternativa más simple si UserPortfolio.portfolio_data tiene 'coste_medio_compra_eur' y 'cantidad_actual':
    user_portfolio_record = UserPortfolio.query.filter_by(user_id=user_id).first()
    total_cost_basis = 0.0
    if user_portfolio_record and user_portfolio_record.portfolio_data:
        try:
            portfolio_items = json.loads(user_portfolio_record.portfolio_data)
            if isinstance(portfolio_items, list):
                for item in portfolio_items:
                    try:
                        # Asumimos que 'coste_medio_compra_eur' ya está calculado y guardado en el objeto UserPortfolio
                        # O 'valor_compra_total_eur_ajustado' que es el coste total de la posición
                        cost_basis_item = float(item.get('valor_compra_total_eur_ajustado', 0.0)) # Usar el valor total de compra ajustado
                        total_cost_basis += cost_basis_item
                    except (ValueError, TypeError):
                        app.logger.warning(f"Valor de coste inválido para el item {item.get('ISIN')} en calculate_portfolio_cost_basis")
        except json.JSONDecodeError:
            app.logger.error(f"Error decodificando portfolio_data para cálculo de coste base, user {user_id}")
    return total_cost_basis






# En app.py
@app.route('/add_real_estate_asset_ajax', methods=['POST'])
@login_required
def add_real_estate_asset_ajax():
    form = RealEstateAssetFormPopup(request.form) # Usar el formulario específico del popup
    if form.validate():
        try:
            purchase_price_val = form.purchase_price.data
            purchase_year_val = form.purchase_year.data
            new_asset = RealEstateAsset(
                user_id=current_user.id,
                property_name=form.property_name.data,
                property_type=form.property_type.data,
                purchase_year=purchase_year_val,
                purchase_price=purchase_price_val,
                current_market_value=purchase_price_val if purchase_price_val is not None else 0.0,
                value_last_updated_year=purchase_year_val if purchase_year_val is not None else None
            )
            db.session.add(new_asset)
            db.session.commit()

            if purchase_price_val is not None and purchase_year_val is not None:
                initial_valuation = RealEstateValueHistory(
                    asset_id=new_asset.id, user_id=current_user.id,
                    valuation_year=purchase_year_val, market_value=purchase_price_val
                )
                db.session.add(initial_valuation)
                db.session.commit()
            
            # Devolver lista actualizada de inmuebles que NO tienen hipoteca activa
            assets_without_mortgage = RealEstateAsset.query\
                .outerjoin(RealEstateMortgage, RealEstateAsset.id == RealEstateMortgage.asset_id)\
                .filter(RealEstateAsset.user_id == current_user.id)\
                .filter(db.or_(RealEstateMortgage.id == None, RealEstateMortgage.current_principal_balance <= 0))\
                .order_by(RealEstateAsset.property_name).all()

            asset_choices = [{'id': asset.id, 'name': f"{asset.property_type + ' - ' if asset.property_type else ''}{asset.property_name}"} 
                             for asset in assets_without_mortgage]
            
            return jsonify({
                'success': True, 
                'message': 'Inmueble añadido y seleccionado.',
                'new_asset_id': new_asset.id,
                'assets': asset_choices
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error AJAX añadiendo inmueble: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error al crear inmueble: {str(e)}'})
    else:
        errors = {field: error[0] for field, error in form.errors.items()}
        return jsonify({'success': False, 'message': 'Errores de validación al añadir inmueble.', 'errors': errors})



@app.route('/add_expense_category_ajax', methods=['POST'])
@login_required
def add_expense_category_ajax():
    form = ExpenseCategoryForm(request.form) 
    
    # Poblar opciones de parent_id para el formulario que se está validando
    user_categories_main_for_validation = ExpenseCategory.query.filter_by(user_id=current_user.id, parent_id=None).order_by(ExpenseCategory.name).all()
    form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [(cat.id, cat.name) for cat in user_categories_main_for_validation]

    if form.validate():
        try:
            parent_id_val = form.parent_id.data
            if parent_id_val == 0: 
                parent_id_val = None

            new_category = ExpenseCategory(
                user_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                parent_id=parent_id_val
            )
            db.session.add(new_category)
            db.session.commit()

            # Preparar la lista de categorías para el dropdown del formulario principal de Deudas
            all_expense_categories = ExpenseCategory.query.filter_by(user_id=current_user.id).order_by(ExpenseCategory.name).all()
            debt_form_category_choices = []
            # Primero las principales
            main_cats_for_debt_form = [c for c in all_expense_categories if c.parent_id is None]
            for cat_df in main_cats_for_debt_form:
                debt_form_category_choices.append({'id': cat_df.id, 'name': cat_df.name})
                # Luego sus subcategorías
                subcats_df = [s for s in all_expense_categories if s.parent_id == cat_df.id]
                for sub_df in subcats_df:
                     debt_form_category_choices.append({'id': sub_df.id, 'name': f"↳ {sub_df.name}"})
            
            # Preparar la lista de categorías principales para el dropdown de "Categoría Padre" DEL MODAL
            modal_parent_category_choices = [{'id': cat.id, 'name': cat.name} 
                                             for cat in main_cats_for_debt_form] # Reutilizamos main_cats_for_debt_form
            
            return jsonify({
                'success': True, 
                'message': 'Categoría añadida correctamente.', 
                'new_category_id': new_category.id,
                'debt_form_categories': debt_form_category_choices,       # Para el select del plan de deuda
                'modal_parent_categories': modal_parent_category_choices # Para el select de parent_id en el modal
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error AJAX creando categoría: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error al crear categoría: {str(e)}'})
    else:
        errors = {field: error[0] for field, error in form.errors.items()}
        return jsonify({'success': False, 'message': 'Errores de validación.', 'errors': errors})


# --- Decorador para rutas de Administrador (NUEVO) ---
def admin_required(f): # MOSTRANDO COMPLETA
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acceso no autorizado. Se requieren privilegios de administrador.", "danger")
            # Redirige a login o a una página de 'no autorizado' más genérica si la tienes
            return redirect(url_for('login', next=request.url if request.method == 'GET' else None))
        return f(*args, **kwargs)
    return decorated_function

# --- Hook @app.before_request para forzar cambio de contraseña (NUEVO) ---
@app.before_request
@app.before_request
def check_force_password_change(): # MOSTRANDO COMPLETA CON CAMBIOS
    # Primero, manejar usuarios no autenticados o endpoints públicos
    if not current_user.is_authenticated or \
       not request.endpoint or \
       request.endpoint in ['static', 'logout', 'request_reset_password', 'reset_with_token']:
        return

    # Forzar cambio de contraseña si es necesario
    if hasattr(current_user, 'must_change_password') and current_user.must_change_password \
       and request.endpoint != 'change_password': # Evitar bucle si ya está en change_password
        flash('Debes cambiar tu contraseña antes de continuar.', 'warning')
        return redirect(url_for('change_password'))

    # NUEVO: Forzar establecimiento de email si no lo tiene (y no es el admin principal)
    # Asumimos que el admin principal (username 'admin') puede no tener email
    if current_user.username != 'admin' and \
       (not current_user.email or current_user.email == app.config.get('ADMIN_PLACEHOLDER_EMAIL')) and \
       request.endpoint != 'set_email': # Evitar bucle si ya está en set_email
        flash('Por favor, establece tu dirección de correo electrónico para continuar.', 'info')
        return redirect(url_for('set_email'))


# En app.py

# ... (otros imports, modelos, formularios, rutas) ...

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user_to_delete = db.session.get(User, user_id)

    if not user_to_delete:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for('admin_dashboard'))

    if user_to_delete.username == 'admin' and user_to_delete.is_admin:
        flash("No se puede eliminar la cuenta del administrador principal 'admin'.", "warning")
        return redirect(url_for('admin_dashboard'))

    if user_to_delete == current_user:
        flash("No puedes eliminar tu propia cuenta desde el panel de administración.", "warning")
        return redirect(url_for('admin_dashboard'))

    try:
        username_deleted = user_to_delete.username
        # La cascada definida en el modelo User (cascade="all, delete-orphan")
        # debería encargarse de borrar todos los datos relacionados.
        db.session.delete(user_to_delete)
        db.session.commit()
        # log_activity(action_type="ADMIN_DELETE_USER",
        #              message=f"Admin {current_user.username} eliminó al usuario '{username_deleted}'.",
        #              actor_user=current_user,
        #              target_user_id=user_id, # Guardar el ID por si acaso
        #              target_username=username_deleted)
        flash(f"El usuario '{username_deleted}' y todos sus datos asociados han sido eliminados permanentemente.", "success")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error al eliminar usuario {user_to_delete.username}: {e}", exc_info=True)
        flash(f"Error al eliminar el usuario: {e}", "danger")

    return redirect(url_for('admin_dashboard'))


@app.route('/set_email', methods=['GET', 'POST']) # NUEVA RUTA
@login_required
def set_email(): # MOSTRANDO COMPLETA
    # Si el usuario ya tiene un email (y no es el admin placeholder), no debería estar aquí
    # a menos que queramos permitir cambiarlo, pero por ahora es para establecerlo si falta.
    if current_user.email and current_user.email != app.config.get('ADMIN_PLACEHOLDER_EMAIL') and current_user.username != 'admin':
        return redirect(url_for('financial_summary')) # O la página principal

    form = SetEmailForm()
    if form.validate_on_submit():
        # Verificar si el email ya está en uso por OTRO usuario (el validador del form ya lo hace)
        # user_with_email = User.query.filter(User.email == form.email.data, User.id != current_user.id).first()
        # if user_with_email:
        #     flash('Ese correo electrónico ya está en uso por otro usuario.', 'danger')
        # else:
        current_user.email = form.email.data
        db.session.commit()
        flash('Tu correo electrónico ha sido guardado correctamente.', 'success')
        # log_activity(action="email_set", user=current_user) # Ejemplo de log
        return redirect(url_for('financial_summary')) # O a donde deba ir después

    return render_template('set_email.html', title='Establecer Correo Electrónico', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register(): # MOSTRANDO COMPLETA CON CAMBIOS
    if current_user.is_authenticated:
        return redirect(url_for('financial_summary')) 

    form = RegistrationForm()
    if form.validate_on_submit(): 
        hashed_password = generate_password_hash(form.password.data)
        
        new_user = User(username=form.username.data,
                        email=form.email.data,
                        birth_year=form.birth_year.data if form.birth_year.data else None, # Guardar año de nacimiento
                        password_hash=hashed_password,
                        is_admin=False,
                        must_change_password=False,
                        is_active=True,
                        created_at=datetime.utcnow())
        try:
            db.session.add(new_user) 
            db.session.commit()
            
            # Opcional: Crear categorías de gastos por defecto para el nuevo usuario
            # if callable(create_default_expense_categories):
            #     create_default_expense_categories(new_user.id) # Asumiendo que tienes esta función
            
            flash('¡Cuenta creada correctamente! Ahora puedes iniciar sesión.', 'success')
            log_activity(action_type="REGISTER", 
                         message=f"Nuevo usuario registrado: '{new_user.username}'.",
                         actor_user=None, # O el propio new_user si ya tiene ID y se maneja así
                         target_user=new_user) # Log de la acción
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error al registrar usuario {form.username.data}: {e}", exc_info=True)
            flash(f'Error al registrar usuario. Por favor, inténtalo de nuevo.', 'danger')
            
    return render_template('register.html', title='Registro', form=form)



@app.route('/logout') # MOSTRANDO COMPLETA CON CAMBIOS
@login_required
def logout():
    # Limpiar datos de sesión sensibles específicos de la app si los hubiera
    # session.pop('portfolio_data', None)
    # session.pop('csv_temp_file', None)
    # ... cualquier otro dato de sesión ...
    # O limpiar toda la sesión:
    session.clear()
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password(): # MOSTRANDO COMPLETA CON CAMBIOS
    form = ChangePasswordForm()
    
    # Lógica para saber si el campo 'current_password' es necesario
    needs_current_password = True
    if current_user.must_change_password:
        # Si es el admin con la contraseña por defecto "admin"
        if current_user.username == 'admin' and current_user.check_password('admin'):
            needs_current_password = False
        # Si es otro caso donde no hay hash (aunque esto es menos probable ahora)
        elif current_user.password_hash is None:
            needs_current_password = False

    if not needs_current_password:
        form.current_password.validators = [] # Quitar validador
        # Si quieres ocultarlo del formulario, puedes pasar una variable al template
        # o manejarlo en el template con una condición.
    else:
        # Asegurarse de que el validador DataRequired esté presente
        # (Puede que necesites ajustar cómo se añaden/quitan validadores dinámicamente si es complejo,
        # pero para este caso, simplemente no validar current_password si no es necesario)
        pass


    if form.validate_on_submit():
        password_ok = False
        if needs_current_password:
            if current_user.check_password(form.current_password.data):
                password_ok = True
            else:
                flash('La contraseña actual es incorrecta.', 'danger')
        else: # No se necesita contraseña actual (ej. primer login admin con pass por defecto)
            password_ok = True

        if password_ok:
            current_user.set_password(form.new_password.data)
            current_user.must_change_password = False
            db.session.commit()
            flash('Tu contraseña ha sido actualizada correctamente.', 'success')
            if current_user.is_admin: # Después de cambiar la contraseña, el admin va a su dashboard
                 return redirect(url_for('admin_dashboard'))
            return redirect(url_for('financial_summary')) 
            
    return render_template('change_password.html', 
                           title='Cambiar Contraseña', 
                           form=form,
                           needs_current_password=needs_current_password)


# Añadir este modelo después del modelo CryptoCsvMovement en models.py:

class CryptoPriceVerification(db.Model):
    __tablename__ = 'crypto_price_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    currency_symbol = db.Column(db.String(20), nullable=False)
    price_available = db.Column(db.Boolean, nullable=False, default=False)
    last_check = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relación con usuario
    user = db.relationship('User', backref=db.backref('crypto_price_verifications', lazy=True))
    
    # Índice único para evitar duplicados por usuario y moneda
    __table_args__ = (db.UniqueConstraint('user_id', 'currency_symbol', name='unique_user_currency'),)
    
    def __repr__(self):
        return f'<CryptoPriceVerification {self.currency_symbol}: {"✓" if self.price_available else "✗"}>'

class CryptoCsvMovement(db.Model):
    __tablename__ = 'crypto_csv_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exchange_name = db.Column(db.String(100), nullable=False, default='Crypto.com')
    
    # Campos del CSV de Crypto.com
    timestamp_utc = db.Column(db.DateTime, nullable=True)
    transaction_description = db.Column(db.Text, nullable=True)
    currency = db.Column(db.String(20), nullable=True)
    amount = db.Column(db.Float, nullable=True)
    to_currency = db.Column(db.String(20), nullable=True)
    to_amount = db.Column(db.Float, nullable=True)
    native_currency = db.Column(db.String(20), nullable=True)
    native_amount = db.Column(db.Float, nullable=True)
    native_amount_in_usd = db.Column(db.Float, nullable=True)
    transaction_kind = db.Column(db.String(100), nullable=True)
    transaction_hash = db.Column(db.String(255), nullable=True)
    
    # Nuevos campos para categorización y procesamiento
    category = db.Column(db.String(50), nullable=True, default='Sin Categoría')
    process_status = db.Column(db.String(20), nullable=True, default='SKIP')
    
    # Campos de control
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    csv_filename = db.Column(db.String(255), nullable=True)
    transaction_hash_unique = db.Column(db.String(64), nullable=True, index=True)
    
    # Relación con usuario
    user = db.relationship('User', backref=db.backref('crypto_csv_movements', lazy=True, cascade='all, delete-orphan'))
    
    def generate_hash(self):
        """Genera un hash único basado en los datos principales de la transacción."""
        hash_data = f"{self.user_id}_{self.exchange_name}_{self.timestamp_utc}_{self.transaction_description}_{self.currency}_{self.amount}_{self.to_currency}_{self.to_amount}_{self.transaction_kind}_{self.transaction_hash}"
        return hashlib.sha256(hash_data.encode('utf-8')).hexdigest()
    
    def __repr__(self):
        return f'<CryptoCsvMovement {self.id}: {self.exchange_name} - {self.transaction_description}>'

class RealEstateAsset(db.Model):
    # ... (como lo tenías, asegurándote de que 'mortgage' es la relación a RealEstateMortgage)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    property_name = db.Column(db.String(150), nullable=False)
    property_type = db.Column(db.String(50), nullable=True) 
    purchase_year = db.Column(db.Integer, nullable=True)
    purchase_price = db.Column(db.Float, nullable=True)
    current_market_value = db.Column(db.Float, nullable=True, default=0.0) 
    value_last_updated_year = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('real_estate_assets', lazy='dynamic', cascade="all, delete-orphan"))
    # Esta relación es clave: un inmueble puede tener UNA hipoteca principal activa
    mortgage = db.relationship('RealEstateMortgage', backref='real_estate_asset_linked', uselist=False, cascade="all, delete-orphan") 
    value_history = db.relationship('RealEstateValueHistory', 
                                    backref='asset', 
                                    lazy='dynamic', 
                                    cascade="all, delete-orphan", 
                                    order_by="desc(RealEstateValueHistory.valuation_year)")
    
    # Relación para saber si este activo está vinculado a un plan de deuda (que actúa como hipoteca)
    # Esto es para facilitar encontrar el DebtInstallmentPlan que ES la hipoteca de este RealEstateAsset.
    debt_plan_as_mortgage = db.relationship('DebtInstallmentPlan', 
                                            foreign_keys='DebtInstallmentPlan.linked_asset_id_for_mortgage', 
                                            backref='mortgaged_asset', 
                                            uselist=False)


class RealEstateMortgage(db.Model): # Este modelo almacenará los detalles de la hipoteca
    id = db.Column(db.Integer, primary_key=True)
    # Enlace uno-a-uno con RealEstateAsset (un inmueble tiene una hipoteca)
    asset_id = db.Column(db.Integer, db.ForeignKey('real_estate_asset.id', ondelete='CASCADE'), nullable=False, unique=True) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    lender_name = db.Column(db.String(100), nullable=True)
    original_loan_amount = db.Column(db.Float, nullable=False) # Cantidad original de la hipoteca
    current_principal_balance = db.Column(db.Float, nullable=False) # Saldo pendiente (se actualiza)
    interest_rate_annual = db.Column(db.Float, nullable=True)
    monthly_payment = db.Column(db.Float, nullable=False) # Cuota mensual de la hipoteca
    loan_term_years = db.Column(db.Integer, nullable=True) # Duración original en años
    loan_start_date = db.Column(db.Date, nullable=False)
    
    # Enlace al DebtInstallmentPlan que representa esta hipoteca en la sección de deudas
    # Esto ayuda a mantener la coherencia si se edita/liquida el plan de deuda.
    # Hacemos que sea nullable por si se quiere registrar una hipoteca sin un plan de deuda detallado (menos probable con el flujo actual)
    debt_installment_plan_id = db.Column(db.Integer, db.ForeignKey('debt_installment_plan.id'), nullable=True, unique=True)
    
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User') # Ya existe backref en User.real_estate_mortgages

class RealEstateExpense(db.Model): # Gastos específicos del inmueble
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('real_estate_asset.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    expense_category = db.Column(db.String(100), nullable=False) # Ej: IBI, Comunidad, Seguro Hogar, Mantenimiento
    description = db.Column(db.String(200), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_frequency = db.Column(db.String(20), nullable=True) # Ej: 'monthly', 'quarterly', 'annual'
    next_due_date = db.Column(db.Date, nullable=True) # Para gastos recurrentes
    
    user = db.relationship('User', backref=db.backref('real_estate_expenses', lazy='dynamic'))

    def __repr__(self):
        return f'<RealEstateExpense {self.expense_category} - {self.amount}>'

class RealEstateValueHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('real_estate_asset.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    valuation_year = db.Column(db.Integer, nullable=False)
    market_value = db.Column(db.Float, nullable=False)
    entry_created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # user = db.relationship('User', backref=...) # Ya definido en RealEstateAsset con backref
    __table_args__ = (db.UniqueConstraint('asset_id', 'valuation_year', 'user_id', name='uq_asset_year_user_valuation'),)

    def __repr__(self):
        return f'<RealEstateValueHistory AssetID:{self.asset_id} Year:{self.valuation_year} Value:{self.market_value}>'


class User(db.Model, UserMixin): # MOSTRAR COMPLETA SI SE MODIFICA
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False) 
    password_hash = db.Column(db.String(128), nullable=True)
    birth_year = db.Column(db.Integer, nullable=True) # NUEVO CAMPO AÑADIDO
    
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    current_login_at = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ... (resto de relaciones existentes en el modelo User) ...
    watchlist_items = db.relationship('WatchlistItem', backref='owner', lazy='dynamic', cascade="all, delete-orphan")
    fin_summary_config = db.relationship('FinancialSummaryConfig', backref='user', uselist=False, cascade="all, delete-orphan")
    pension_plans = db.relationship('PensionPlan', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    pension_history = db.relationship('PensionPlanHistory', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    crypto_exchanges = db.relationship('CryptoExchange', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    crypto_transactions = db.relationship('CryptoTransaction', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    crypto_holdings = db.relationship('CryptoHolding', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    crypto_history = db.relationship('CryptoHistoryRecord', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    metal_transactions = db.relationship('PreciousMetalTransaction', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    debt_ceiling = db.relationship('DebtCeiling', backref='user', uselist=False, cascade="all, delete-orphan")
    debt_plans = db.relationship('DebtInstallmentPlan', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    debt_history = db.relationship('DebtHistoryRecord', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    expense_categories = db.relationship('ExpenseCategory', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    expenses = db.relationship('Expense', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    portfolio = db.relationship('UserPortfolio', backref='user', uselist=False, cascade="all, delete-orphan")
    fixed_income = db.relationship('FixedIncome', backref='user', uselist=False, cascade="all, delete-orphan")
    broker_operations = db.relationship('BrokerOperation', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    salary_history = db.relationship('SalaryHistory', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    bank_accounts = db.relationship('BankAccount', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    cash_history = db.relationship('CashHistoryRecord', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    variable_income_categories = db.relationship('VariableIncomeCategory', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    variable_incomes = db.relationship('VariableIncome', backref='user', lazy='dynamic', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if self.password_hash is None:
            return False
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self, expires_sec=1800):
        admin_placeholder_email = app.config.get('ADMIN_PLACEHOLDER_EMAIL', 'admin@internal.local')
        if self.username == 'admin' and self.email == admin_placeholder_email:
            app.logger.info(f"Se intentó generar token de reseteo para admin principal ({self.username}) con email placeholder.")
            return None
        if not self.email:
            return None
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            data = s.loads(token, max_age=expires_sec)
            user_id = data.get('user_id')
        except Exception:
            return None
        return db.session.get(User, user_id)

    def __repr__(self):
        return f'<User {self.username} Admin:{self.is_admin} Email:{self.email}>'
class AccountManagementForm(FlaskForm):
    username = StringField('Nombre de Usuario', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Correo Electrónico', validators=[DataRequired(), Email(message="Correo electrónico no válido.")])
    birth_year = IntegerField('Año de Nacimiento', validators=[Optional(), NumberRange(min=1900, max=datetime.now().year)])
    current_password = PasswordField('Contraseña Actual')
    new_password = PasswordField('Nueva Contraseña', validators=[Optional(), Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")])
    confirm_new_password = PasswordField('Confirmar Nueva Contraseña', validators=[EqualTo('new_password', message='Las contraseñas deben coincidir.')])
    submit = SubmitField('Guardar Cambios')

    def validate_username(self, username):
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Ese nombre de usuario ya está en uso. Por favor, elige otro.')

    def validate_email(self, email):
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Ese correo electrónico ya está registrado. Por favor, elige otro.')

@app.route('/manage_account', methods=['GET', 'POST'])
@login_required
def manage_account():
    form = AccountManagementForm(obj=current_user) # Pre-popula el formulario con datos del usuario

    if form.validate_on_submit():
        try:
            # Actualizar nombre de usuario
            if current_user.username != form.username.data:
                current_user.username = form.username.data
                flash('Nombre de usuario actualizado.', 'success')

            # Actualizar email
            if current_user.email != form.email.data:
                current_user.email = form.email.data
                flash('Correo electrónico actualizado.', 'success')

            # Actualizar año de nacimiento
            if form.birth_year.data:
                 current_user.birth_year = form.birth_year.data
                 flash('Año de nacimiento actualizado.', 'success')
            else: # Si se borra el año
                current_user.birth_year = None


            # Actualizar contraseña si se proporcionó la nueva
            if form.new_password.data:
                if form.current_password.data and current_user.check_password(form.current_password.data):
                    current_user.set_password(form.new_password.data)
                    flash('Contraseña actualizada correctamente.', 'success')
                elif not form.current_password.data:
                     flash('Debes ingresar tu contraseña actual para cambiarla.', 'warning')
                else:
                    flash('La contraseña actual es incorrecta.', 'danger')
                    return render_template('manage_account_modal_content.html', form=form) # Para recargar el modal con error

            db.session.commit()

            # Si es una petición AJAX (desde el modal), devolvemos un JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=True, messages=get_flashed_messages(with_categories=True))

            return redirect(url_for('financial_summary')) # O a donde sea apropiado

        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la cuenta: {e}', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, messages=get_flashed_messages(with_categories=True), error=str(e))

    # Si es una petición AJAX (GET inicial para el modal) o falló la validación en POST AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('manage_account_modal_content.html', form=form)

    # Para una ruta GET normal (si se accediera directamente, aunque el modal es lo principal)
    return render_template('manage_account_page.html', title='Gestionar Mi Cuenta', form=form)



def send_reset_email(user): # MOSTRANDO COMPLETA
    # Primero, verificar si el usuario tiene un email válido para enviar.
    # Esto es crucial si tu admin no tiene email o si usas un placeholder.
    admin_placeholder_email = app.config.get('ADMIN_PLACEHOLDER_EMAIL') # Obtener el placeholder desde config

    if not user.email:
        app.logger.warning(f"Intento de enviar email de reseteo a usuario '{user.username}' que no tiene email registrado.")
        return False
    
    if user.username == 'admin' and admin_placeholder_email and user.email == admin_placeholder_email:
        app.logger.warning(f"Intento de enviar email de reseteo al admin principal '{user.username}' que usa un email placeholder.")
        # Decidir si quieres enviar un flash message aquí o manejarlo en la ruta que llama a esta función.
        # Por ahora, solo evitamos el envío y devolvemos False.
        return False

    token = user.get_reset_token() # Este método ya debería estar en tu modelo User

    if not token:
        # Esto podría pasar si get_reset_token tiene alguna lógica interna que previene la creación
        # (aunque ya hemos cubierto el caso de 'no email' arriba).
        app.logger.warning(f"No se pudo generar un token de reseteo para el usuario '{user.username}'.")
        return False
        
    # El remitente por defecto se toma de app.config['MAIL_DEFAULT_SENDER']
    # Asegúrate de que MAIL_DEFAULT_SENDER esté configurado en app.config
    msg = Message(
        subject='Solicitud de Reseteo de Contraseña - Mi Portfolio App',
        recipients=[user.email] # El email del usuario al que se le enviará
        # sender=app.config['MAIL_DEFAULT_SENDER'] # No es necesario si MAIL_DEFAULT_SENDER está configurado globalmente
    )

    # _external=True es importante para generar una URL absoluta que funcione fuera de la app
    link_reseteo = url_for('reset_with_token', token=token, _external=True)
    
    msg.body = f'''Hola {user.username},

Para resetear tu contraseña, por favor visita el siguiente enlace:
{link_reseteo}

Si no solicitaste este cambio, puedes ignorar este correo electrónico de forma segura.
Este enlace expirará en 30 minutos.

Saludos,
El equipo de Mi Portfolio App
'''
    # Opcionalmente, puedes usar plantillas HTML para correos más elaborados:
    # msg.html = render_template('email/reset_password_email.html', user=user, token=token)

    try:
        mail.send(msg)
        app.logger.info(f"Email de reseteo de contraseña enviado exitosamente a {user.email}")
        return True
    except Exception as e:
        # Loguear el error detallado es crucial para diagnosticar problemas de envío
        app.logger.error(f"FALLO al enviar email de reseteo de contraseña a {user.email}. Error: {e}", exc_info=True)
        # Podrías añadir un reintento aquí o una notificación más específica si falla
        return False


@app.route("/request_reset_password", methods=['GET', 'POST']) # NUEVA RUTA
def request_reset_password(): # MOSTRANDO COMPLETA
    if current_user.is_authenticated:
        return redirect(url_for('financial_summary'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if send_reset_email(user):
                flash('Se ha enviado un email con instrucciones para resetear tu contraseña a tu correo electrónico.', 'info')
            else:
                flash('Error al enviar el email de reseteo. Por favor, inténtalo más tarde o contacta al administrador.', 'danger')
        else:
            # No revelamos si el email existe o no por seguridad, pero el validador del form ya lo hace.
             flash('Si ese correo está registrado, recibirás un email para resetear tu contraseña.', 'info')
        return redirect(url_for('login'))
    return render_template('request_reset_password.html', title='Resetear Contraseña', form=form)

@app.route("/reset_password/<token>", methods=['GET', 'POST']) # NUEVA RUTA
def reset_with_token(token): # MOSTRANDO COMPLETA
    if current_user.is_authenticated:
        return redirect(url_for('financial_summary'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('El token de reseteo es inválido o ha expirado.', 'warning')
        return redirect(url_for('request_reset_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.must_change_password = False # El reseteo cuenta como cambio
        db.session.commit()
        flash('Tu contraseña ha sido actualizada. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_with_token.html', title='Establecer Nueva Contraseña', form=form, token=token)

# En app.py

@app.route('/admin/user/<int:user_id>/trigger_reset_password', methods=['POST'])
@login_required
@admin_required
def admin_trigger_reset_password(user_id):
    user_to_reset = db.session.get(User, user_id)
    if not user_to_reset:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for('admin_dashboard'))

    # Evitar que el admin principal se auto-envíe un reset si no tiene email funcional
    # o si su email es el placeholder. La función send_reset_email ya lo maneja.
    if user_to_reset.username == 'admin' and \
       (not user_to_reset.email or user_to_reset.email == app.config.get('ADMIN_PLACEHOLDER_EMAIL')):
        flash(f"El administrador principal '{user_to_reset.username}' no tiene un email configurado para reseteo.", "warning")
        return redirect(url_for('admin_dashboard'))
    
    # La función send_reset_email ya verifica si el usuario tiene un email válido
    if send_reset_email(user_to_reset):
        flash(f"Se ha enviado un email de reseteo de contraseña al usuario '{user_to_reset.username}' ({user_to_reset.email}).", 'success')
    else:
        flash(f"Error al enviar el email de reseteo para '{user_to_reset.username}'. Verifica la configuración de email o si el usuario tiene un email válido.", 'danger')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/close_account', methods=['GET', 'POST']) # MOSTRANDO COMPLETA (sin cambios internos)
@login_required
def close_account():
    form = CloseAccountForm()
    if form.validate_on_submit():
        if current_user.check_password(form.password.data):
            try:
                user_id_to_delete = current_user.id
                username_deleted = current_user.username
                
                db.session.delete(current_user) # Asume cascadas configuradas en User Model
                db.session.commit()
                logout_user() # Importante desloguear al usuario
                flash(f'La cuenta de {username_deleted} ha sido cerrada permanentemente.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al cerrar la cuenta: {e}', 'danger')
                app.logger.error(f"Error al cerrar la cuenta de {current_user.username}: {e}", exc_info=True)
        else:
            flash('Contraseña incorrecta. No se pudo cerrar la cuenta.', 'warning')
    return render_template('close_account.html', title='Cerrar Cuenta', form=form)



@app.route('/admin') # Redirige a dashboard
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard(): # MOSTRANDO COMPLETA CON CAMBIOS PARA LOGS
    users = User.query.order_by(User.username).all()
    user_count = User.query.count()
    active_user_count = User.query.filter_by(is_active=True).count()
    admin_user_count = User.query.filter_by(is_admin=True).count()
    
    # Obtener los últimos N logs de actividad, ordenados por más reciente primero
    # Puedes ajustar el .limit() al número de logs que quieras mostrar
    recent_activity_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(50).all()
    
    # Para la plantilla, es útil procesar los detalles si son JSON
    # Esto es opcional, podrías simplemente mostrar el string details directamente
    processed_logs = []
    for log_entry in recent_activity_logs:
        details_parsed = log_entry.details
        if log_entry.details:
            try:
                # Intenta cargar como JSON si se guardó así
                parsed = json.loads(log_entry.details)
                # Formatear el JSON para mejor visualización (opcional)
                details_parsed = json.dumps(parsed, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                # Si no es JSON válido, se muestra como texto plano
                details_parsed = log_entry.details
        
        processed_logs.append({
            'timestamp': log_entry.timestamp,
            'username': log_entry.username or "Sistema",
            'action_type': log_entry.action_type,
            'message': log_entry.message,
            'target_username': log_entry.target_username,
            'details': details_parsed, # Detalles procesados o en crudo
            'ip_address': log_entry.ip_address
        })

    # Placeholder para los logs "simplificados" que tenías antes, por si aún los quieres
    # admin_simple_logs = [
    #     f"({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) Acceso al panel de administración por {current_user.username}.",
    # ]
    
    admin_placeholder_email = app.config.get('ADMIN_PLACEHOLDER_EMAIL')

    return render_template('admin/dashboard.html', 
                           title="Panel de Administración", 
                           users=users,
                           user_count=user_count,
                           active_user_count=active_user_count,
                           admin_user_count=admin_user_count,
                           admin_placeholder_email=admin_placeholder_email,
                           activity_logs=processed_logs) # Pasar los logs procesados

@app.route('/admin/user/<int:user_id>/toggle_active', methods=['POST']) # NUEVA RUTA
@login_required
@admin_required
def admin_toggle_user_active(user_id): # MOSTRANDO COMPLETA
    user = db.session.get(User, user_id)
    if user:
        if user.username == 'admin' and user.is_admin: # No permitir desactivar al admin principal
            flash("No se puede desactivar la cuenta del administrador principal 'admin'.", "warning")
        else:
            user.is_active = not user.is_active
            db.session.commit()
            status = "activado" if user.is_active else "desactivado"
            flash(f"El estado de actividad del usuario '{user.username}' ha sido cambiado a {status}.", "success")
    else:
        flash("Usuario no encontrado.", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST']) # NUEVA RUTA
@login_required
@admin_required
def admin_toggle_user_admin(user_id): # MOSTRANDO COMPLETA
    user = db.session.get(User, user_id)
    if user:
        if user.username == 'admin' and not user.is_admin == False : # No permitir quitar admin al admin principal
             flash("No se pueden revocar los privilegios de administrador al usuario 'admin'.", "warning")
        else:
            user.is_admin = not user.is_admin
            db.session.commit()
            status = "administrador" if user.is_admin else "usuario normal"
            flash(f"El usuario '{user.username}' ahora es {status}.", "success")
    else:
        flash("Usuario no encontrado.", "danger")
    return redirect(url_for('admin_dashboard'))


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
    include_real_estate = BooleanField('Incluir Inmuebles', default=True)
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

import json # Asegúrate de que json está importado al principio de app.py


# Dentro de app.py

# ... (otros imports)
# import json # Asegúrate que está importado

# ...

@app.route('/movements')
@login_required
def view_movements():
    _, csv_data_list, _ = load_user_portfolio(current_user.id) 
    movements_list = []
    if csv_data_list:
        if isinstance(csv_data_list, list):
            movements_list = csv_data_list
        else:
            flash('Error al cargar los datos de movimientos. Formato de datos inesperado.', 'danger')
            app.logger.error(f"Error cargando movimientos para usuario {current_user.id}: csv_data_list no es una lista, es {type(csv_data_list)}")

    # ---- INICIO DE LÓGICA PARA RESUMEN P/L POR PRODUCTO (CORREGIDA) ----
    portfolio_data_from_db, _, _ = load_user_portfolio(current_user.id)
    current_portfolio_items = portfolio_data_from_db if portfolio_data_from_db else []
    
    portfolio_isin_to_details = {
        item.get('ISIN'): {
            # --- CORRECCIÓN AQUÍ: 'none' a 'None' ---
            'market_value_eur': float(item.get('market_value_eur', 0.0)) if item.get('market_value_eur') is not None else 0.0,
            'producto_name': item.get('Producto') 
        }
        for item in current_portfolio_items if item.get('ISIN')
    }

    raw_product_totals = {} 
    product_movement_isins = {} 

    if movements_list:
        for movement in movements_list:
            producto_mov = movement.get('Producto')
            isin_mov = movement.get('ISIN')
            total_value_mov = movement.get('Total')

            if producto_mov and total_value_mov is not None:
                try:
                    current_total_for_product = float(total_value_mov)
                    raw_product_totals[producto_mov] = raw_product_totals.get(producto_mov, 0.0) + current_total_for_product
                    
                    if isin_mov:
                        if producto_mov not in product_movement_isins:
                            product_movement_isins[producto_mov] = set()
                        product_movement_isins[producto_mov].add(isin_mov)
                except (ValueError, TypeError) as e:
                    app.logger.warning(f"No se pudo convertir 'Total' ({total_value_mov}) a float para el producto '{producto_mov}'. Error: {e}")

    final_product_summary_list = []
    for producto_mov_name, base_net_result in raw_product_totals.items():
        adjusted_net_result = base_net_result
        is_in_portfolio_flag = False
        market_value_of_held_product = 0.0
        
        isins_for_this_product_name = product_movement_isins.get(producto_mov_name, set())
        found_in_portfolio_by_isin = False
        for isin_m in isins_for_this_product_name:
            if isin_m in portfolio_isin_to_details:
                found_in_portfolio_by_isin = True
                market_value_of_held_product += portfolio_isin_to_details[isin_m]['market_value_eur']
        
        if found_in_portfolio_by_isin:
            is_in_portfolio_flag = True
            adjusted_net_result += market_value_of_held_product # Sumar el valor de mercado
            
        final_product_summary_list.append({
            'name': producto_mov_name,
            'net_result': adjusted_net_result, 
            'is_in_portfolio': is_in_portfolio_flag,
            'original_total_sum': base_net_result, 
            'market_value_added': market_value_of_held_product if is_in_portfolio_flag else None,
        })

    sorted_product_summary_for_template = sorted(final_product_summary_list, key=lambda item: item['net_result'], reverse=True)
    # ---- FIN DE LÓGICA ----

    return render_template('movements.html', 
                           movements=movements_list, 
                           product_summary=sorted_product_summary_for_template, 
                           title="Movimientos de Cartera")





# En app.py
@app.route('/real_estate', methods=['GET', 'POST'])
@login_required
def real_estate():
    asset_form = RealEstateAssetForm() # Formulario para añadir nuevo inmueble
    valuation_form = ValuationEntryForm() # Formulario para añadir nueva tasación

    # Mapa de iconos para los tipos de inmueble
    icon_map = {
        'Apartamento': 'bi-building',
        'Casa': 'bi-house-door-fill',
        'Local Comercial': 'bi-shop',
        'Terreno': 'bi-map-fill',
        'Garaje': 'bi-p-circle-fill',
        'Trastero': 'bi-archive-fill',
        'Otro': 'bi-bricks'
    }

    # Poblar dinámicamente las opciones del SelectField de inmuebles para el formulario de tasación
    user_assets_for_select = [
        (asset.id, f"{asset.property_type + ' - ' if asset.property_type else ''}{asset.property_name}")
        for asset in RealEstateAsset.query.filter_by(user_id=current_user.id).order_by(RealEstateAsset.property_name).all()
    ]
    if user_assets_for_select:
        valuation_form.asset_id.choices = [(0, '- Selecciona un Inmueble -')] + user_assets_for_select
        valuation_form.asset_id.render_kw = {}
        valuation_form.submit_valuation.render_kw = {}
    else:
        valuation_form.asset_id.choices = [(0, 'No hay inmuebles registrados para tasar')]
        valuation_form.asset_id.render_kw = {'disabled': True}
        valuation_form.submit_valuation.render_kw = {'disabled': True}

    # Manejar el envío del formulario para añadir un nuevo inmueble
    if asset_form.validate_on_submit() and asset_form.submit_asset.data:
        try:
            purchase_price_val = asset_form.purchase_price.data
            purchase_year_val = asset_form.purchase_year.data

            new_asset = RealEstateAsset(
                user_id=current_user.id,
                property_name=asset_form.property_name.data,
                property_type=asset_form.property_type.data,
                purchase_year=purchase_year_val,
                purchase_price=purchase_price_val,
                current_market_value=purchase_price_val if purchase_price_val is not None else 0.0,
                value_last_updated_year=purchase_year_val if purchase_year_val is not None else None
            )
            db.session.add(new_asset)
            db.session.commit()

            if purchase_price_val is not None and purchase_year_val is not None:
                initial_valuation = RealEstateValueHistory(
                    asset_id=new_asset.id,
                    user_id=current_user.id,
                    valuation_year=purchase_year_val,
                    market_value=purchase_price_val
                )
                db.session.add(initial_valuation)
                db.session.commit()

            flash('Inmueble añadido correctamente. Su valor de mercado inicial se ha establecido al precio de compra.', 'success')
            return redirect(url_for('real_estate'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al añadir inmueble: {str(e)}', 'danger')
            app.logger.error(f"Error añadiendo inmueble: {e}", exc_info=True)

    # --- Preparar datos para mostrar en la página (para solicitudes GET o si un POST falla) ---
    all_user_assets_details = []
    db_assets = RealEstateAsset.query.filter_by(user_id=current_user.id).order_by(RealEstateAsset.property_name).all()

    summary_total_market_value = 0
    summary_total_mortgage = 0 # Suma de los saldos pendientes de las hipotecas activas

    for asset in db_assets:
        current_value_for_table = asset.current_market_value or 0
        summary_total_market_value += current_value_for_table

        # Initialize mortgage details with defaults (assuming paid if no active mortgage)
        mortgage_status = "Pagado"
        mortgage_balance_for_display = 0
        mortgage_progress_percent = 100  # Default to 100% if paid or no mortgage

        # Check if this asset has an active DebtInstallmentPlan that is marked as its mortgage
        active_mortgage_debt_plan = None
        if asset.debt_plan_as_mortgage and asset.debt_plan_as_mortgage.is_active: #
            active_mortgage_debt_plan = asset.debt_plan_as_mortgage #
        
        if active_mortgage_debt_plan:
            # If there's an active linked mortgage plan, use its details
            mortgage_status = "Hipoteca" #
            
            # Use the DebtInstallmentPlan's 'remaining_amount' for the current balance
            mortgage_balance_for_display = active_mortgage_debt_plan.remaining_amount #
            
            # Add this active mortgage's balance to the summary total
            summary_total_mortgage += mortgage_balance_for_display #
            
            # Use the DebtInstallmentPlan's 'progress_percentage'
            mortgage_progress_percent = active_mortgage_debt_plan.progress_percentage #
            
            # Clamp the percentage value between 0 and 100 to be safe for display
            mortgage_progress_percent = max(0, min(mortgage_progress_percent, 100)) #
        
        # If no active_mortgage_debt_plan is found, the defaults "Pagado" and 100% progress remain.

        revalorization_percentage = None
        if asset.purchase_price and asset.purchase_price > 0 and current_value_for_table > 0:
            try:
                revalorization_percentage = ((current_value_for_table - asset.purchase_price) / asset.purchase_price) * 100
            except ZeroDivisionError:
                revalorization_percentage = None

        valuations_for_asset = sorted(asset.value_history.all(), key=lambda v_hist: v_hist.valuation_year)
        valuations_display_list = []
        for i, current_val_hist_item in enumerate(valuations_for_asset):
            change_from_previous_year_pct = None
            if i > 0:
                previous_val_hist_item = valuations_for_asset[i-1]
                if previous_val_hist_item.market_value > 0:
                    try:
                        change_from_previous_year_pct = ((current_val_hist_item.market_value - previous_val_hist_item.market_value) / previous_val_hist_item.market_value) * 100
                    except ZeroDivisionError:
                        change_from_previous_year_pct = None
            valuations_display_list.append({
                'id': current_val_hist_item.id,
                'year': current_val_hist_item.valuation_year,
                'value': current_val_hist_item.market_value,
                'change_pct': change_from_previous_year_pct
            })
        valuations_display_list.sort(key=lambda x: x['year'], reverse=True)

        display_name_text = f"{asset.property_type} - {asset.property_name}" if asset.property_type else asset.property_name
        
        purchase_price_display_text = 'N/A'
        if asset.purchase_price is not None:
            try:
                purchase_price_display_text = f"{round(asset.purchase_price, 0):.0f}"
            except TypeError:
                purchase_price_display_text = 'Error'
        purchase_info_text = f"Compra: {asset.purchase_year if asset.purchase_year else 'N/A'} por {purchase_price_display_text}€"

        all_user_assets_details.append({
            'id': asset.id,
            'display_name': display_name_text,
            'property_type': asset.property_type,
            'purchase_info': purchase_info_text,
            'current_market_value_display': current_value_for_table,
            'value_last_updated_year_display': asset.value_last_updated_year,
            'mortgage_status': mortgage_status,
            'mortgage_balance_for_display': mortgage_balance_for_display,
            'mortgage_progress_percent': mortgage_progress_percent,
            'revalorization_percentage': revalorization_percentage,
            'valuations': valuations_display_list
        })

    summary_net_equity = summary_total_market_value - summary_total_mortgage

    return render_template('real_estate.html',
                           title="Gestión de Inmuebles",
                           asset_form=asset_form,
                           valuation_form=valuation_form,
                           assets_details=all_user_assets_details,
                           total_market_value=summary_total_market_value,
                           total_mortgage_balance=summary_total_mortgage,
                           net_equity=summary_net_equity,
                           icon_class_map=icon_map)


@app.route('/add_valuation', methods=['POST'])
@login_required
def add_valuation():
    valuation_form = ValuationEntryForm()
    user_assets_for_select = [(asset.id, f"{asset.property_type + ' - ' if asset.property_type else ''}{asset.property_name}") 
                              for asset in RealEstateAsset.query.filter_by(user_id=current_user.id).order_by(RealEstateAsset.property_name).all()]
    valuation_form.asset_id.choices = [(0, '- Selecciona un Inmueble -')] + user_assets_for_select

    if valuation_form.validate_on_submit():
        asset_id = valuation_form.asset_id.data
        valuation_year_submitted = valuation_form.valuation_year.data
        market_value_submitted = valuation_form.market_value.data

        if asset_id == 0:
            flash("Por favor, selecciona un inmueble válido para la tasación.", "warning")
            return redirect(url_for('real_estate'))

        asset = RealEstateAsset.query.filter_by(id=asset_id, user_id=current_user.id).first()
        if not asset:
            flash("Inmueble no encontrado o no te pertenece.", "danger")
            return redirect(url_for('real_estate'))

        existing_valuation = RealEstateValueHistory.query.filter_by(
            asset_id=asset.id, 
            valuation_year=valuation_year_submitted
        ).first()

        if existing_valuation:
            existing_valuation.market_value = market_value_submitted
            existing_valuation.entry_created_at = datetime.utcnow()
            flash(f'Tasación para "{asset.property_name}" del año {valuation_year_submitted} actualizada correctamente.', 'success')
        else:
            new_valuation = RealEstateValueHistory(
                asset_id=asset.id,
                user_id=current_user.id,
                valuation_year=valuation_year_submitted,
                market_value=market_value_submitted
            )
            db.session.add(new_valuation)
            flash(f'Nueva tasación para "{asset.property_name}" del año {valuation_year_submitted} guardada correctamente.', 'success')
        
        try:
            db.session.commit() # Guarda la tasación nueva o actualizada

            # Ahora, actualiza el RealEstateAsset con la información de la tasación MÁS RECIENTE
            latest_valuation_for_asset = RealEstateValueHistory.query.filter_by(asset_id=asset.id, user_id=current_user.id)\
                                         .order_by(RealEstateValueHistory.valuation_year.desc())\
                                         .first()
            
            if latest_valuation_for_asset:
                asset.current_market_value = latest_valuation_for_asset.market_value
                asset.value_last_updated_year = latest_valuation_for_asset.valuation_year
            else: 
                # Si no hay ninguna tasación (ej. se borraron todas),
                # poner valor de mercado a precio de compra o None
                asset.current_market_value = asset.purchase_price if asset.purchase_price is not None else None
                asset.value_last_updated_year = asset.purchase_year if asset.purchase_price is not None else None
            
            db.session.commit() # Guarda la actualización en RealEstateAsset
        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar la tasación: {str(e)}', 'danger')
            app.logger.error(f"Error procesando tasación: {e}", exc_info=True)
    else:
        for fieldName, errorMessages in valuation_form.errors.items():
            for err in errorMessages:
                flash(f"Error en '{getattr(valuation_form, fieldName).label.text}': {err}", 'danger')
                
    return redirect(url_for('real_estate'))

@app.route('/delete_valuation/<int:valuation_id>', methods=['POST'])
@login_required
def delete_valuation(valuation_id):
    valuation = RealEstateValueHistory.query.filter_by(id=valuation_id, user_id=current_user.id).first_or_404()
    asset_id_redirect = valuation.asset_id # Guardar para actualizar el activo después
    asset_property_name = valuation.asset.property_name # Para el mensaje flash
    valuation_year_deleted = valuation.valuation_year

    try:
        db.session.delete(valuation)
        db.session.commit() # Commit la eliminación de la valoración

        # Después de eliminar, recalcular y actualizar el current_market_value del activo
        asset = RealEstateAsset.query.get(asset_id_redirect)
        if asset:
            latest_valuation_for_asset = asset.value_history.order_by(db.desc(RealEstateValueHistory.valuation_year)).first()
            if latest_valuation_for_asset:
                asset.current_market_value = latest_valuation_for_asset.market_value
                asset.value_last_updated_year = latest_valuation_for_asset.valuation_year
            else:
                # Si no quedan valoraciones, poner a None o a precio de compra si se prefiere
                asset.current_market_value = None
                asset.value_last_updated_year = None
            db.session.commit() # Commit la actualización del activo

        flash(f'Tasación del año {valuation_year_deleted} para "{asset_property_name}" eliminada.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la tasación: {str(e)}', 'danger')
        app.logger.error(f"Error eliminando tasación: {e}", exc_info=True)
    return redirect(url_for('real_estate'))


# In app.py

@app.route('/edit_real_estate_asset/<int:asset_id>', methods=['GET', 'POST'])
@login_required
def edit_real_estate_asset(asset_id):
    asset_to_edit = RealEstateAsset.query.filter_by(id=asset_id, user_id=current_user.id).first_or_404()
    form = RealEstateAssetForm(obj=asset_to_edit) 

    if form.validate_on_submit():
        try:
            asset_to_edit.property_name = form.property_name.data
            asset_to_edit.property_type = form.property_type.data
            asset_to_edit.purchase_year = form.purchase_year.data
            asset_to_edit.purchase_price = form.purchase_price.data
            
            # REMOVED: Logic for is_rental and rental_income_monthly
            # if hasattr(form, 'is_rental'): 
            #     asset_to_edit.is_rental = form.is_rental.data
            #     asset_to_edit.rental_income_monthly = form.rental_income_monthly.data if form.is_rental.data else None
            
            db.session.commit()
            flash(f'Inmueble "{asset_to_edit.property_name}" actualizado correctamente.', 'success')
            return redirect(url_for('real_estate'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar inmueble: {str(e)}', 'danger')
            app.logger.error(f"Error actualizando inmueble {asset_id}: {e}", exc_info=True)
    
    return render_template('edit_real_estate_asset.html', 
                           form=form, 
                           asset=asset_to_edit,
                           title=f"Editar Inmueble: {asset_to_edit.property_name}")

@app.route('/delete_real_estate_asset/<int:asset_id>', methods=['POST'])
@login_required
def delete_real_estate_asset(asset_id):
    asset_to_delete = RealEstateAsset.query.filter_by(id=asset_id, user_id=current_user.id).first_or_404()
    try:
        # Antes de borrar, podrías querer borrar datos relacionados si no tienes cascade delete configurado
        # Por ejemplo, hipotecas, gastos asociados, historial de valoraciones.
        # if asset_to_delete.mortgage:
        #     db.session.delete(asset_to_delete.mortgage)
        # RealEstateExpense.query.filter_by(asset_id=asset_id).delete()
        # RealEstateValueHistory.query.filter_by(asset_id=asset_id).delete()
        # (Asegúrate de que las cascadas estén bien definidas en tus modelos para simplificar esto)

        db.session.delete(asset_to_delete)
        db.session.commit()
        flash(f'El inmueble "{asset_to_delete.property_name}" ha sido eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el inmueble: {str(e)}', 'danger')
        app.logger.error(f"Error eliminando inmueble {asset_id}: {e}", exc_info=True)
    return redirect(url_for('real_estate'))


# En app.py
# En app.py

# Asegúrate de tener todos estos imports al principio de tu app.py, por ejemplo:
# from flask import render_template, redirect, url_for, flash, request, jsonify
# from flask_login import login_required, current_user
# from .models import (db, User, FinancialSummaryConfig, FixedIncome, SalaryHistory, 
#                      VariableIncome, VariableIncomeCategory, Expense, ExpenseCategory, 
#                      DebtInstallmentPlan, DebtCeiling, DebtHistoryRecord,
#                      BankAccount, CashHistoryRecord, 
#                      PensionPlan, PensionPlanHistory, UserPortfolio, CryptoTransaction, 
#                      CryptoHolding, CryptoHistoryRecord,
#                      PreciousMetalTransaction, PreciousMetalPrice,
#                      RealEstateAsset, RealEstateMortgage, RealEstateExpense, RealEstateValueHistory)
# from .forms import FinancialSummaryConfigForm # Y otros formularios que uses
# from datetime import datetime, date, timedelta
# import json


@app.route('/financial_summary', methods=['GET', 'POST'])
@login_required
def financial_summary():
    """Muestra un resumen financiero global con datos de todas las secciones."""
    config = FinancialSummaryConfig.query.filter_by(user_id=current_user.id).first()
    if not config:
        config = FinancialSummaryConfig(
            user_id=current_user.id,
            include_income=True, include_expenses=True, include_debts=True,
            include_investments=True, include_crypto=True, include_metals=True,
            include_bank_accounts=True, include_pension_plans=True, include_real_estate=True
        )
        db.session.add(config)
        db.session.commit()

    config_form = FinancialSummaryConfigForm(obj=config)

    if config_form.validate_on_submit():
        try:
            config_form.populate_obj(config)
            config.last_updated = datetime.utcnow()
            db.session.commit()
            flash('Configuración del resumen guardada correctamente.', 'success')
            return redirect(url_for('financial_summary'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al guardar configuración: {str(e)}', 'danger')
            app.logger.error(f"Error guardando config resumen: {e}", exc_info=True)

    summary_data = {
        'income': {'available': False, 'data': {}},
        'variable_income': {'available': False, 'data': {}},
        'expenses': {'available': False, 'data': { # Inicializar el diccionario de datos para gastos
            'fixed_monthly': 0,
            'punctual_last_month': 0,
            'monthly_avg_expenses': 0, 
            'by_category': [] 
        }},
        'debts': {'available': False, 'data': {}},
        'investments': {'available': False, 'data': {}},
        'crypto': {'available': False, 'data': {}},
        'metals': {'available': False, 'data': {}},
        'bank_accounts': {'available': False, 'data': {}},
        'pension_plans': {'available': False, 'data': {}},
        'real_estate': {'available': False, 'data': {}},
        'net_worth': {'available': False, 'data': {}},
        'kpis': {'available': False, 'data': {}},
        'charts': {'available': False, 'data': {}}
    }

    try:
        # --- INGRESOS (Fijos y Variables) ---
        current_total_monthly_income_for_kpi = 0 # Para KPIs
        if config.include_income:
            fixed_income_db = FixedIncome.query.filter_by(user_id=current_user.id).first()
            if fixed_income_db and fixed_income_db.annual_net_salary is not None:
                summary_data['income']['available'] = True
                monthly_salary_val = fixed_income_db.annual_net_salary / 12
                current_total_monthly_income_for_kpi += monthly_salary_val
                summary_data['income']['data'] = {
                    'annual_net_salary': fixed_income_db.annual_net_salary,
                    'monthly_salary_12': monthly_salary_val,
                    'monthly_salary_14': fixed_income_db.annual_net_salary / 14,
                    'last_updated': fixed_income_db.last_updated, 'history': []
                }
                salary_history_db = SalaryHistory.query.filter_by(user_id=current_user.id).order_by(SalaryHistory.year.desc()).all()
                prev_salary = None
                for entry in salary_history_db:
                    variation = None
                    if prev_salary is not None and prev_salary > 0:
                        variation = ((entry.annual_net_salary - prev_salary) / prev_salary) * 100
                    summary_data['income']['data']['history'].append({
                        'year': entry.year, 'salary': entry.annual_net_salary, 'variation': variation
                    })
                    prev_salary = entry.annual_net_salary
            
            three_months_ago_inc = date.today() - timedelta(days=90)
            variable_incomes_total_3m = 0
            # (Lógica de expansión de ingresos variables recurrentes en los últimos 3 meses)
            all_var_incomes_expanded_for_summary = []
            for vi_sum in VariableIncome.query.filter_by(user_id=current_user.id).all():
                if hasattr(vi_sum, 'is_recurring') and vi_sum.is_recurring and vi_sum.income_type == 'fixed': # Asumiendo que 'fixed' indica recurrente
                    start_calc_vi_sum = max(vi_sum.start_date or vi_sum.date, three_months_ago_inc)
                    end_calc_vi_sum = min(vi_sum.end_date or date.today(), date.today())
                    current_calc_date_vi_sum = start_calc_vi_sum
                    while current_calc_date_vi_sum <= end_calc_vi_sum:
                        all_var_incomes_expanded_for_summary.append(vi_sum.amount)
                        month_vi_sum = current_calc_date_vi_sum.month + (vi_sum.recurrence_months or 1)
                        year_vi_sum = current_calc_date_vi_sum.year + (month_vi_sum -1) // 12
                        month_vi_sum = ((month_vi_sum - 1) % 12) + 1
                        try: current_calc_date_vi_sum = date(year_vi_sum, month_vi_sum, 1)
                        except ValueError: break
                elif vi_sum.date >= three_months_ago_inc: # Puntuales en rango
                     all_var_incomes_expanded_for_summary.append(vi_sum.amount)
            variable_incomes_total_3m = sum(all_var_incomes_expanded_for_summary)

            if variable_incomes_total_3m > 0:
                avg_monthly_variable_income = variable_incomes_total_3m / 3
                current_total_monthly_income_for_kpi += avg_monthly_variable_income
                summary_data['variable_income']['available'] = True
                summary_data['variable_income']['data'] = {'total': variable_incomes_total_3m, 'monthly_avg': avg_monthly_variable_income}

        # --- GASTOS ---
        current_total_monthly_expenses_for_kpi = 0 # Para KPIs y Flujo de Caja
        if config.include_expenses:
            all_user_expenses = Expense.query.filter_by(user_id=current_user.id).all()
            if all_user_expenses: # Solo si hay gastos, marcamos como disponible
                summary_data['expenses']['available'] = True

                # 1. Gastos Fijos Mensuales (activos)
                fixed_monthly_sum_val = sum(
                    e.amount for e in all_user_expenses 
                    if e.expense_type == 'fixed' and e.is_recurring and (not e.end_date or e.end_date >= date.today())
                )
                summary_data['expenses']['data']['fixed_monthly'] = fixed_monthly_sum_val
                current_total_monthly_expenses_for_kpi += fixed_monthly_sum_val

                # 2. Gastos Puntuales del Último Mes
                one_month_ago = date.today() - timedelta(days=30)
                summary_data['expenses']['data']['punctual_last_month'] = sum(
                    e.amount for e in all_user_expenses
                    if e.expense_type == 'punctual' and e.date >= one_month_ago
                )

                # 3. Promedio Mensual de Gastos (Generales directos, últimos 3 meses)
                three_months_ago_exp = date.today() - timedelta(days=90)
                punctual_expenses_3m_sum = sum(
                    e.amount for e in all_user_expenses
                    if e.expense_type == 'punctual' and e.date >= three_months_ago_exp and e.date <= date.today()
                )
                # Incluir gastos fijos expandidos en el periodo de 3 meses para el promedio
                fixed_expenses_3m_sum = 0
                for exp_fixed_3m in all_user_expenses:
                    if exp_fixed_3m.expense_type == 'fixed' and exp_fixed_3m.is_recurring:
                        start_loop_3m = max(exp_fixed_3m.start_date or exp_fixed_3m.date, three_months_ago_exp)
                        end_loop_3m = min(exp_fixed_3m.end_date or date.today(), date.today())
                        current_loop_3m = start_loop_3m
                        rec_3m = exp_fixed_3m.recurrence_months or 1
                        while current_loop_3m <= end_loop_3m:
                            if current_loop_3m >= three_months_ago_exp:
                                fixed_expenses_3m_sum += exp_fixed_3m.amount
                            year_next_3m = current_loop_3m.year
                            month_next_3m = current_loop_3m.month + rec_3m
                            while month_next_3m > 12: month_next_3m -= 12; year_next_3m += 1
                            try: current_loop_3m = date(year_next_3m, month_next_3m, 1)
                            except ValueError: break
                
                total_direct_expenses_3m = fixed_expenses_3m_sum + punctual_expenses_3m_sum
                avg_monthly_direct_expenses = total_direct_expenses_3m / 3 if total_direct_expenses_3m > 0 else 0
                summary_data['expenses']['data']['monthly_avg_expenses'] = avg_monthly_direct_expenses
                # Para KPIs, usamos un promedio de gastos variables y los fijos actuales
                current_total_monthly_expenses_for_kpi += (punctual_expenses_3m_sum / 3)


                # 4. Gastos por Categoría (para el gráfico, últimos 6 meses)
                six_months_ago_exp_cat = date.today() - timedelta(days=180)
                expenses_in_range_for_cat_chart = []
                for exp_cat in all_user_expenses: # Iterar sobre todos los gastos del usuario
                    if exp_cat.expense_type == 'fixed' and exp_cat.is_recurring:
                        start_loop_date_cat = exp_cat.start_date or exp_cat.date
                        end_loop_date_cat = exp_cat.end_date or date.today()
                        start_loop_date_cat = max(start_loop_date_cat, six_months_ago_exp_cat) # Ajustar al inicio del rango de 6 meses
                        end_loop_date_cat = min(end_loop_date_cat, date.today()) # Ajustar al fin del rango (hoy)

                        current_loop_date_cat = start_loop_date_cat
                        recurrence_loop_cat = exp_cat.recurrence_months or 1
                        while current_loop_date_cat <= end_loop_date_cat:
                            # Solo añadir si la fecha del gasto está dentro del periodo de 6 meses
                            if current_loop_date_cat >= six_months_ago_exp_cat: 
                                 expenses_in_range_for_cat_chart.append({'amount': exp_cat.amount, 'category_id': exp_cat.category_id})
                            
                            year_next_cat = current_loop_date_cat.year
                            month_next_cat = current_loop_date_cat.month + recurrence_loop_cat
                            while month_next_cat > 12: month_next_cat -= 12; year_next_cat +=1
                            try: current_loop_date_cat = date(year_next_cat, month_next_cat, 1)
                            except ValueError: break
                    elif exp_cat.date >= six_months_ago_exp_cat and exp_cat.date <= date.today(): # Puntuales en rango de 6 meses
                         expenses_in_range_for_cat_chart.append({'amount': exp_cat.amount, 'category_id': exp_cat.category_id})
                
                expenses_by_cat_dict = {}
                for exp_item_cat in expenses_in_range_for_cat_chart:
                    cat_obj = ExpenseCategory.query.get(exp_item_cat['category_id']) if exp_item_cat['category_id'] else None
                    cat_name = cat_obj.name if cat_obj else "Sin categoría"
                    expenses_by_cat_dict[cat_name] = expenses_by_cat_dict.get(cat_name, 0) + exp_item_cat['amount']
                
                summary_data['expenses']['data']['by_category'] = sorted(expenses_by_cat_dict.items(), key=lambda x: x[1], reverse=True)

        # --- DEUDAS (No Hipotecarias) ---
        monthly_debt_payment_val = 0
        total_general_debt_val = 0
        if config.include_debts:
            debt_plans_db = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()
            if debt_plans_db:
                summary_data['debts']['available'] = True
                total_general_debt_val = sum(p.remaining_amount for p in debt_plans_db)
                current_month_date = date(date.today().year, date.today().month, 1)
                monthly_debt_payment_val = sum(p.monthly_payment for p in debt_plans_db if p.start_date <= current_month_date and (p.end_date is None or p.end_date > current_month_date))
                summary_data['debts']['data'] = {
                    'total_debt': total_general_debt_val,
                    'monthly_payment': monthly_debt_payment_val,
                    'debt_list': [{'description': p.description, 'remaining': p.remaining_amount, 'progress_pct': p.progress_percentage} for p in debt_plans_db[:3]]
                }
        current_total_monthly_expenses_for_kpi += monthly_debt_payment_val

        # --- ACTIVOS ---
        # Cuentas Bancarias
        total_cash_val = 0
        if config.include_bank_accounts:
            bank_accounts_db = BankAccount.query.filter_by(user_id=current_user.id).all()
            if bank_accounts_db:
                summary_data['bank_accounts']['available'] = True
                total_cash_val = sum(acc.current_balance for acc in bank_accounts_db)
                summary_data['bank_accounts']['data'] = {
                    'total_cash': total_cash_val,
                    'accounts': [{'bank_name': acc.bank_name, 'balance': acc.current_balance} for acc in bank_accounts_db]
                }
        # Inversiones
        total_market_value_inv = 0
        total_cost_basis_inv = 0
        if config.include_investments:
            portfolio_record_db = UserPortfolio.query.filter_by(user_id=current_user.id).first()
            if portfolio_record_db and portfolio_record_db.portfolio_data:
                portfolio_data_json = json.loads(portfolio_record_db.portfolio_data)
                if portfolio_data_json:
                    summary_data['investments']['available'] = True
                    total_market_value_inv = sum(float(item.get('market_value_eur', 0) or 0) for item in portfolio_data_json)
                    total_cost_basis_inv = sum(float(item.get('cost_basis_eur_est', 0) or 0) for item in portfolio_data_json)
                    summary_data['investments']['data'] = {
                        'total_market_value': total_market_value_inv,
                        'total_pl': total_market_value_inv - total_cost_basis_inv,
                        'total_cost_basis': total_cost_basis_inv,
                        'top_positions': [{'name': item.get('item_name', item.get('Producto')), 'market_value': float(item.get('market_value_eur',0) or 0)} for item in sorted(portfolio_data_json, key=lambda x: float(x.get('market_value_eur', 0) or 0), reverse=True)[:3]]
                    }
        # Crypto
        current_crypto_value = 0
        invested_crypto_value = 0
        if config.include_crypto:
            # (Lógica de cálculo de valor de crypto como la tenías) ...
             holdings_summary = {} 
             for ct in CryptoTransaction.query.filter_by(user_id=current_user.id).all():
                if ct.ticker_symbol not in holdings_summary:
                    holdings_summary[ct.ticker_symbol] = {'quantity': 0, 'name': ct.crypto_name, 'current_price': ct.current_price or 0, 'investment':0}
                if ct.transaction_type == 'buy':
                    holdings_summary[ct.ticker_symbol]['quantity'] += ct.quantity
                    holdings_summary[ct.ticker_symbol]['investment'] += ct.quantity * ct.price_per_unit
                elif ct.transaction_type == 'sell':
                    holdings_summary[ct.ticker_symbol]['quantity'] -= ct.quantity
             for ticker, data_crypto in holdings_summary.items():
                current_crypto_value += data_crypto['quantity'] * data_crypto['current_price']
                invested_crypto_value += data_crypto['investment']
             if current_crypto_value > 0 or invested_crypto_value > 0 :
                summary_data['crypto']['available'] = True
                summary_data['crypto']['data'] = {
                    'total_value': current_crypto_value,
                    'total_pl': current_crypto_value - invested_crypto_value,
                    'total_investment': invested_crypto_value,
                    'top_holdings': sorted([{'name': d['name'], 'quantity': d['quantity'], 'current_value': d['quantity'] * d['current_price']} for t, d in holdings_summary.items() if d['quantity'] > 0], key=lambda x: x['current_value'], reverse=True)[:3]
                }
        # Metales
        total_metal_value = 0
        total_invested_metal = 0
        if config.include_metals:
            # (Lógica de cálculo de valor de metales como la tenías) ...
            gold_price_oz = PreciousMetalPrice.query.filter_by(metal_type='gold').first().price_eur_per_oz if PreciousMetalPrice.query.filter_by(metal_type='gold').first() else 0
            silver_price_oz = PreciousMetalPrice.query.filter_by(metal_type='silver').first().price_eur_per_oz if PreciousMetalPrice.query.filter_by(metal_type='silver').first() else 0
            g_to_oz = 0.0321507
            current_gold_oz = 0; invested_gold = 0
            current_silver_oz = 0; invested_silver = 0
            for mt in PreciousMetalTransaction.query.filter_by(user_id=current_user.id).all():
                qty_oz = mt.quantity if mt.unit_type == 'oz' else mt.quantity * g_to_oz
                cost = qty_oz * mt.price_per_unit
                if mt.metal_type == 'gold':
                    if mt.transaction_type == 'buy': current_gold_oz += qty_oz; invested_gold += cost
                    else: current_gold_oz -= qty_oz;
                elif mt.metal_type == 'silver':
                    if mt.transaction_type == 'buy': current_silver_oz += qty_oz; invested_silver += cost
                    else: current_silver_oz -= qty_oz;
            gold_value = current_gold_oz * gold_price_oz
            silver_value = current_silver_oz * silver_price_oz
            total_metal_value = gold_value + silver_value
            total_invested_metal = invested_gold + invested_silver
            if total_metal_value > 0 or total_invested_metal > 0:
                summary_data['metals']['available'] = True
                summary_data['metals']['data'] = {
                    'total_value': total_metal_value, 'total_pl': total_metal_value - total_invested_metal,
                    'gold': {'current_value': gold_value, 'total_oz': current_gold_oz},
                    'silver': {'current_value': silver_value, 'total_oz': current_silver_oz}
                }
        # Pensiones
        total_pension_val = 0
        if config.include_pension_plans:
            pension_plans_db = PensionPlan.query.filter_by(user_id=current_user.id).all()
            if pension_plans_db:
                summary_data['pension_plans']['available'] = True
                total_pension_val = sum(p.current_balance for p in pension_plans_db)
                summary_data['pension_plans']['data'] = {
                    'total_pension': total_pension_val,
                    'plans': [{'entity_name': p.entity_name, 'balance': p.current_balance} for p in pension_plans_db]
                }
        # Inmuebles
        total_re_market_value_val = 0
        total_re_mortgage_balance_val = 0
        if config.include_real_estate:
            real_estate_assets_db = RealEstateAsset.query.filter_by(user_id=current_user.id).all()
            if real_estate_assets_db:
                summary_data['real_estate']['available'] = True
                total_re_market_value_val = sum(asset.current_market_value or 0 for asset in real_estate_assets_db)
                total_re_mortgage_balance_val = sum(asset.mortgage.current_principal_balance or 0 for asset in real_estate_assets_db if asset.mortgage)
                summary_data['real_estate']['data'] = {
                    'count': len(real_estate_assets_db),
                    'total_market_value': total_re_market_value_val,
                    'total_mortgage_balance': total_re_mortgage_balance_val,
                    'net_equity': total_re_market_value_val - total_re_mortgage_balance_val,
                    'assets': [{'name': asset.property_name, 'value': asset.current_market_value or 0} for asset in real_estate_assets_db[:3]]
                }
                # Sumar gastos de hipoteca a los gastos totales para KPIs
                current_total_monthly_expenses_for_kpi += sum(asset_re.mortgage.monthly_payment or 0 for asset_re in real_estate_assets_db if asset_re.mortgage)
                # Sumar gastos recurrentes de RE para KPIs
                # (Asumiendo que tienes el modelo RealEstateExpense y la lógica para promediarlos)
                # monthly_re_expenses_avg = calculate_average_monthly_re_expenses(current_user.id) # Necesitarías esta función
                # current_total_monthly_expenses_for_kpi += monthly_re_expenses_avg


        # --- PATRIMONIO NETO (Cálculo final) ---
        assets_final = (total_cash_val + total_market_value_inv + current_crypto_value + 
                        total_metal_value + total_pension_val + total_re_market_value_val)
        liabilities_final = total_general_debt_val + total_re_mortgage_balance_val
        
        net_worth_val = assets_final - liabilities_final
        summary_data['net_worth']['available'] = True
        summary_data['net_worth']['data'] = {
            'total_assets': assets_final, 'total_liabilities': liabilities_final, 'net_worth': net_worth_val
        }

        # --- KPIs Financieros ---
        if current_total_monthly_income_for_kpi > 0 or current_total_monthly_expenses_for_kpi > 0 :
            summary_data['kpis']['available'] = True
            monthly_savings_val = current_total_monthly_income_for_kpi - current_total_monthly_expenses_for_kpi
            savings_rate_val = (monthly_savings_val / current_total_monthly_income_for_kpi * 100) if current_total_monthly_income_for_kpi > 0 else (-100 if current_total_monthly_expenses_for_kpi > 0 else 0)
            
            total_debt_payments_for_ratio = monthly_debt_payment_val # Deudas generales
            total_debt_payments_for_ratio += sum(asset_re_kpi.mortgage.monthly_payment or 0 for asset_re_kpi in RealEstateAsset.query.filter_by(user_id=current_user.id).all() if asset_re_kpi.mortgage) # Hipotecas

            debt_to_income_val = (total_debt_payments_for_ratio / current_total_monthly_income_for_kpi * 100) if current_total_monthly_income_for_kpi > 0 else 0
            debt_to_assets_val = (liabilities_final / assets_final * 100) if assets_final > 0 else 0
            
            summary_data['kpis']['data'] = {
                'monthly_income': current_total_monthly_income_for_kpi,
                'monthly_expenses': current_total_monthly_expenses_for_kpi,
                'monthly_savings': monthly_savings_val,
                'savings_rate': savings_rate_val,
                'debt_to_income': debt_to_income_val,
                'debt_to_assets': debt_to_assets_val
            }

        # --- Flujo de Caja Mensual ---
        if summary_data['kpis'].get('available'):
            summary_data['cash_flow'] = {'available': True, 'data': {
                'total_income': summary_data['kpis']['data']['monthly_income'],
                'total_expenses': summary_data['kpis']['data']['monthly_expenses'],
                'net_cash_flow': summary_data['kpis']['data']['monthly_savings']
            }}
        
        # --- DATOS PARA GRÁFICOS ---
        if 'charts' not in summary_data: summary_data['charts'] = {'available': True, 'data': {}}

        cash_history_db = CashHistoryRecord.query.filter_by(user_id=current_user.id).order_by(CashHistoryRecord.date.asc()).limit(12).all()
        if cash_history_db:
            summary_data['charts']['data']['cash_history'] = {
                'dates': [rec.date.strftime('%Y-%m') for rec in cash_history_db],
                'values_list': [rec.total_cash for rec in cash_history_db]
            }

        # Historial de Patrimonio Neto
        historical_net_worth_points = {}
        # (Lógica para poblar historical_net_worth_points como te mostré antes, usando historiales de Cash, Pension, Crypto, REValue, Debt)
        # ...
        # Ejemplo simplificado, debes completar esta parte con la lógica de la respuesta anterior
        for rec in CashHistoryRecord.query.filter_by(user_id=current_user.id).all():
            month_year = rec.date.strftime('%Y-%m')
            if month_year not in historical_net_worth_points: historical_net_worth_points[month_year] = {'assets': 0, 'liabilities': 0, 'date_obj': rec.date}
            historical_net_worth_points[month_year]['assets'] += rec.total_cash
        # (Añadir pension, crypto, RE value history a assets; debt history a liabilities)

        net_worth_chart_list = []
        for month_year_str, data_point in historical_net_worth_points.items():
            net_worth_chart_list.append({
                'date_str': month_year_str, 'date_obj': data_point['date_obj'],
                'net_worth': data_point['assets'] - data_point['liabilities']
            })
        net_worth_chart_list.sort(key=lambda x: x['date_obj'])
        net_worth_chart_list = net_worth_chart_list[-12:]

        if net_worth_chart_list:
            summary_data['charts']['data']['net_worth_history'] = {
                'dates': [item['date_str'] for item in net_worth_chart_list],
                'values_list': [item['net_worth'] for item in net_worth_chart_list]
            }

    except Exception as e:
        app.logger.error(f"Error calculando resumen financiero: {e}", exc_info=True)
        flash(f"Se produjo un error al calcular algunos datos del resumen: {str(e)}", "warning")

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
        # Initialize report_data structure
        report_data = {
            'general': {'date': datetime.now().strftime('%d/%m/%Y'), 'user': current_user.username},
            'income': {'salary': None, 'variable': None, 'salary_trend': None, 'total_monthly': 0},
            'expenses': {'fixed_monthly': 0, 'variable_monthly_avg': 0, 'total_monthly': 0, 'by_category': {}, 'total_6m': 0},
            'assets': {'total': 0, 'composition': {}},
            'liabilities': {'total': 0, 'monthly_payment': 0, 'details': [], 'total_debt_general': 0},
            'real_estate': {'total_market_value': 0, 'total_mortgage_balance': 0, 'net_equity': 0, 'details': [], 'monthly_re_expenses':0}, # monthly_rental_income removed
            'metrics': {'net_worth': 0, 'monthly_savings': 0, 'savings_rate': 0, 'debt_to_income_ratio': 0, 'debt_to_assets_ratio': 0, 'months_to_fi': 0, 'fi_target':0},
            'recommendations': []
        }

        # --- INGRESOS ---
        total_monthly_income_report = 0
        fixed_income_db = FixedIncome.query.filter_by(user_id=current_user.id).first()
        if fixed_income_db and fixed_income_db.annual_net_salary:
            monthly_salary_report = fixed_income_db.annual_net_salary / 12
            total_monthly_income_report += monthly_salary_report
            report_data['income']['salary'] = {'annual': fixed_income_db.annual_net_salary, 'monthly': monthly_salary_report}
            
            salary_history_db = SalaryHistory.query.filter_by(user_id=current_user.id).order_by(SalaryHistory.year.desc()).all()
            if len(salary_history_db) >= 2:
                growths = [((salary_history_db[i].annual_net_salary - salary_history_db[i+1].annual_net_salary) / salary_history_db[i+1].annual_net_salary) * 100 
                           for i in range(len(salary_history_db)-1) if salary_history_db[i+1].annual_net_salary > 0]
                avg_growth_report = sum(growths) / len(growths) if growths else 0
                report_data['income']['salary_trend'] = {'avg_growth': avg_growth_report, 'history': [(h.year, h.annual_net_salary) for h in salary_history_db]}

        three_months_ago_rep = date.today() - timedelta(days=90)
        variable_income_total_3m = 0
        income_by_cat_rep = {}
        all_var_incomes_expanded = []

        # Expand recurring/fixed variable incomes
        for vi_rep in VariableIncome.query.filter_by(user_id=current_user.id).all():
            if vi_rep.income_type == 'fixed' and vi_rep.is_recurring: # Assuming 'fixed' income type implies recurring for VariableIncome
                start_calc_vi = max(vi_rep.start_date or vi_rep.date, three_months_ago_rep)
                end_calc_vi = min(vi_rep.end_date or date.today(), date.today())
                current_calc_date_vi = start_calc_vi
                while current_calc_date_vi <= end_calc_vi:
                    all_var_incomes_expanded.append({'amount': vi_rep.amount, 'category_id': vi_rep.category_id})
                    # Advance month logic for recurrence
                    month_vi = current_calc_date_vi.month + (vi_rep.recurrence_months or 1)
                    year_vi = current_calc_date_vi.year + (month_vi -1) // 12
                    month_vi = ((month_vi - 1) % 12) + 1
                    try: current_calc_date_vi = date(year_vi, month_vi, 1)
                    except ValueError: break
            elif vi_rep.date >= three_months_ago_rep: # Punctual incomes in range
                 all_var_incomes_expanded.append({'amount': vi_rep.amount, 'category_id': vi_rep.category_id})
        
        for inc_item_rep in all_var_incomes_expanded:
            variable_income_total_3m += inc_item_rep['amount']
            cat_obj_vi = VariableIncomeCategory.query.get(inc_item_rep['category_id']) if inc_item_rep['category_id'] else None
            cat_name_vi = cat_obj_vi.name if cat_obj_vi else "Sin categoría"
            income_by_cat_rep[cat_name_vi] = income_by_cat_rep.get(cat_name_vi, 0) + inc_item_rep['amount']

        if variable_income_total_3m > 0:
            monthly_variable_income_rep = variable_income_total_3m / 3
            total_monthly_income_report += monthly_variable_income_rep
            report_data['income']['variable'] = {'monthly_avg': monthly_variable_income_rep, 'total_3m': variable_income_total_3m, 'by_category': income_by_cat_rep}
        
        report_data['income']['total_monthly'] = total_monthly_income_report
        # Rental income part removed

        # --- GASTOS ---
        total_monthly_expenses_report = 0
        fixed_expenses_db_rep = Expense.query.filter(Expense.user_id == current_user.id, Expense.expense_type == 'fixed', Expense.is_recurring == True).all() # Explicitly True
        fixed_expenses_sum_rep = sum(exp.amount for exp in fixed_expenses_db_rep if not exp.end_date or exp.end_date >= date.today()) # Only active recurring
        total_monthly_expenses_report += fixed_expenses_sum_rep
        
        variable_expenses_sum_3m_rep = sum(exp.amount for exp in Expense.query.filter(Expense.user_id == current_user.id, Expense.expense_type == 'punctual', Expense.date >= three_months_ago_rep).all())
        monthly_variable_expenses_rep = variable_expenses_sum_3m_rep / 3 if variable_expenses_sum_3m_rep > 0 else 0
        total_monthly_expenses_report += monthly_variable_expenses_rep
        
        six_months_ago_rep = date.today() - timedelta(days=180)
        expenses_by_cat_rep = {}
        all_expenses_expanded_6m = []
        # Expand recurring fixed expenses for category analysis
        for exp_rep_6m in Expense.query.filter_by(user_id=current_user.id).all():
            if exp_rep_6m.expense_type == 'fixed' and exp_rep_6m.is_recurring:
                start_calc_exp = max(exp_rep_6m.start_date or exp_rep_6m.date, six_months_ago_rep)
                end_calc_exp = min(exp_rep_6m.end_date or date.today(), date.today())
                current_calc_date_exp = start_calc_exp
                while current_calc_date_exp <= end_calc_exp:
                    all_expenses_expanded_6m.append({'amount': exp_rep_6m.amount, 'category_id': exp_rep_6m.category_id})
                    # Advance month logic
                    month_exp = current_calc_date_exp.month + (exp_rep_6m.recurrence_months or 1)
                    year_exp = current_calc_date_exp.year + (month_exp -1) // 12
                    month_exp = ((month_exp - 1) % 12) + 1
                    try: current_calc_date_exp = date(year_exp, month_exp, 1)
                    except ValueError: break
            elif exp_rep_6m.date >= six_months_ago_rep and exp_rep_6m.date <= date.today(): # Punctual expenses in range
                 all_expenses_expanded_6m.append({'amount': exp_rep_6m.amount, 'category_id': exp_rep_6m.category_id})

        total_expenses_6m_val = 0
        for exp_item_rep in all_expenses_expanded_6m:
            total_expenses_6m_val += exp_item_rep['amount']
            cat_obj_exp = ExpenseCategory.query.get(exp_item_rep['category_id']) if exp_item_rep['category_id'] else None
            cat_name_exp = cat_obj_exp.name if cat_obj_exp else "Sin categoría"
            expenses_by_cat_rep[cat_name_exp] = expenses_by_cat_rep.get(cat_name_exp, 0) + exp_item_rep['amount']
        
        report_data['expenses']['fixed_monthly'] = fixed_expenses_sum_rep
        report_data['expenses']['variable_monthly_avg'] = monthly_variable_expenses_rep
        report_data['expenses']['by_category'] = dict(sorted(expenses_by_cat_rep.items(), key=lambda item: item[1], reverse=True))
        report_data['expenses']['total_6m'] = total_expenses_6m_val
        # total_monthly will be updated after debts

        # Gastos recurrentes de inmuebles
        monthly_re_expenses_total_rep = 0
        # (Assuming RealEstateExpense model exists and is populated)
        re_expenses_db_rep = RealEstateExpense.query.filter_by(user_id=current_user.id).all()
        for re_exp_item in re_expenses_db_rep:
            if re_exp_item.is_recurring: # Only consider recurring for monthly average
                if re_exp_item.recurrence_frequency == 'monthly': monthly_re_expenses_total_rep += re_exp_item.amount
                elif re_exp_item.recurrence_frequency == 'quarterly': monthly_re_expenses_total_rep += re_exp_item.amount / 3
                elif re_exp_item.recurrence_frequency == 'semiannual': monthly_re_expenses_total_rep += re_exp_item.amount / 6
                elif re_exp_item.recurrence_frequency == 'annual': monthly_re_expenses_total_rep += re_exp_item.amount / 12
        total_monthly_expenses_report += monthly_re_expenses_total_rep
        report_data['real_estate']['monthly_re_expenses'] = monthly_re_expenses_total_rep

        # --- ACTIVOS ---
        assets_total_report = 0
        assets_composition_report = {}
        
        bank_accounts_db_rep = BankAccount.query.filter_by(user_id=current_user.id).all()
        cash_total_rep = sum(acc.current_balance for acc in bank_accounts_db_rep)
        assets_total_report += cash_total_rep; assets_composition_report['Efectivo'] = cash_total_rep
        
        portfolio_record_db_rep = UserPortfolio.query.filter_by(user_id=current_user.id).first()
        if portfolio_record_db_rep and portfolio_record_db_rep.portfolio_data:
            portfolio_data_json_rep = json.loads(portfolio_record_db_rep.portfolio_data)
            total_market_value_inv_rep = sum(float(item.get('market_value_eur', 0) or 0) for item in portfolio_data_json_rep)
            assets_total_report += total_market_value_inv_rep; assets_composition_report['Inversiones'] = total_market_value_inv_rep
        
        crypto_holdings_db = CryptoHolding.query.filter_by(user_id=current_user.id).all()
        crypto_value_rep = sum(h.quantity * (h.current_price or 0) for h in crypto_holdings_db if h.quantity > 0)
        assets_total_report += crypto_value_rep; assets_composition_report['Criptomonedas'] = crypto_value_rep

        g_to_oz_rep = 0.0321507466
        gold_price_rep_obj = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
        silver_price_rep_obj = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
        gold_price_rep = gold_price_rep_obj.price_eur_per_oz if gold_price_rep_obj else 0
        silver_price_rep = silver_price_rep_obj.price_eur_per_oz if silver_price_rep_obj else 0
        
        gold_oz_rep = sum(((t.quantity if t.unit_type == 'oz' else t.quantity * g_to_oz_rep) if t.transaction_type == 'buy' else -(t.quantity if t.unit_type == 'oz' else t.quantity * g_to_oz_rep)) for t in PreciousMetalTransaction.query.filter_by(user_id=current_user.id, metal_type='gold').all())
        silver_oz_rep = sum(((t.quantity if t.unit_type == 'oz' else t.quantity * g_to_oz_rep) if t.transaction_type == 'buy' else -(t.quantity if t.unit_type == 'oz' else t.quantity * g_to_oz_rep)) for t in PreciousMetalTransaction.query.filter_by(user_id=current_user.id, metal_type='silver').all())
        metals_value_rep = (gold_oz_rep * gold_price_rep) + (silver_oz_rep * silver_price_rep)
        assets_total_report += metals_value_rep; assets_composition_report['Metales'] = metals_value_rep
        
        pension_total_rep = sum(p.current_balance for p in PensionPlan.query.filter_by(user_id=current_user.id).all())
        assets_total_report += pension_total_rep; assets_composition_report['Pensiones'] = pension_total_rep

        real_estate_assets_db_rep = RealEstateAsset.query.filter_by(user_id=current_user.id).all()
        total_re_value_rep = sum(asset.current_market_value or 0 for asset in real_estate_assets_db_rep) # Use asset.current_market_value
        assets_total_report += total_re_value_rep; assets_composition_report['Inmuebles'] = total_re_value_rep
        
        report_data['assets']['total'] = assets_total_report
        report_data['assets']['composition'] = assets_composition_report
        
        report_data['real_estate']['total_market_value'] = total_re_value_rep
        report_data['real_estate']['details'] = []
        for asset_re_det in real_estate_assets_db_rep:
            current_val_re_det = asset_re_det.current_market_value or 0
            mortgage_bal_re_det = asset_re_det.mortgage.current_principal_balance if asset_re_det.mortgage and asset_re_det.mortgage.current_principal_balance is not None else 0
            report_data['real_estate']['details'].append({
                'name': asset_re_det.property_name,
                'type': asset_re_det.property_type,
                'value': current_val_re_det,
                'mortgage': mortgage_bal_re_det,
                'equity': current_val_re_det - mortgage_bal_re_det
                # Removed 'is_rental' and 'rental_income'
            })

        # --- PASIVOS ---
        liabilities_total_report = 0
        monthly_debt_payment_report = 0
        
        debt_plans_db_rep = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()
        general_debt_total_rep = sum(p.remaining_amount for p in debt_plans_db_rep)
        liabilities_total_report += general_debt_total_rep
        report_data['liabilities']['total_debt_general'] = general_debt_total_rep
        
        today_rep = date.today()
        current_month_rep = date(today_rep.year, today_rep.month, 1)
        monthly_general_debt_payment_rep = sum(p.monthly_payment for p in debt_plans_db_rep if p.start_date <= current_month_rep and (p.end_date is None or p.end_date > current_month_rep))
        monthly_debt_payment_report += monthly_general_debt_payment_rep
        report_data['liabilities']['details'] = [{'description': p.description, 'remaining': p.remaining_amount, 'monthly_payment': p.monthly_payment, 'progress_pct': p.progress_percentage, 'remaining_months': p.remaining_installments} for p in debt_plans_db_rep]

        total_re_mortgage_rep = sum(asset_re_m.mortgage.current_principal_balance for asset_re_m in real_estate_assets_db_rep if asset_re_m.mortgage and asset_re_m.mortgage.current_principal_balance is not None)
        liabilities_total_report += total_re_mortgage_rep
        report_data['real_estate']['total_mortgage_balance'] = total_re_mortgage_rep
        report_data['real_estate']['net_equity'] = total_re_value_rep - total_re_mortgage_rep

        monthly_mortgage_payment_rep = sum(asset_re_m.mortgage.monthly_payment for asset_re_m in real_estate_assets_db_rep if asset_re_m.mortgage and asset_re_m.mortgage.monthly_payment is not None)
        monthly_debt_payment_report += monthly_mortgage_payment_rep
        
        report_data['liabilities']['total'] = liabilities_total_report
        report_data['liabilities']['monthly_payment'] = monthly_debt_payment_report
        
        total_monthly_expenses_report += monthly_debt_payment_report # Add debt payments to total expenses
        report_data['expenses']['total_monthly'] = total_monthly_expenses_report

        # --- MÉTRICAS FINANCIERAS ---
        net_worth_report = assets_total_report - liabilities_total_report
        monthly_savings_report = total_monthly_income_report - total_monthly_expenses_report
        savings_rate_report = (monthly_savings_report / total_monthly_income_report * 100) if total_monthly_income_report > 0 else 0
        debt_to_income_ratio_report = (monthly_debt_payment_report / total_monthly_income_report * 100) if total_monthly_income_report > 0 else 0
        debt_to_assets_ratio_report = (liabilities_total_report / assets_total_report * 100) if assets_total_report > 0 else 0
        
        fi_target_report = 0
        months_to_fi_report = 0
        if monthly_savings_report > 0 and total_monthly_expenses_report > 0:
            annual_expenses_rep = total_monthly_expenses_report * 12
            fi_target_report = annual_expenses_rep * 25
            if net_worth_report < fi_target_report:
                months_to_fi_report = (fi_target_report - net_worth_report) / monthly_savings_report
        
        report_data['metrics'] = {
            'net_worth': net_worth_report,
            'monthly_savings': monthly_savings_report,
            'savings_rate': savings_rate_report,
            'debt_to_income_ratio': debt_to_income_ratio_report,
            'debt_to_assets_ratio': debt_to_assets_ratio_report,
            'months_to_fi': months_to_fi_report,
            'fi_target': fi_target_report
        }
        
        # --- RECOMENDACIONES PERSONALIZADAS (Ejemplo, expandir según sea necesario) ---
        if savings_rate_report < 10 and savings_rate_report >= 0:
            report_data['recommendations'].append({
                'severity': 'medium', 'title': 'Tasa de ahorro baja', 
                'description': f'Tu tasa de ahorro es del {savings_rate_report:.1f}%. Intenta aumentarla al 15-20%.',
                'actions': ['Revisa gastos no esenciales.', 'Busca formas de incrementar ingresos.']
            })
        elif savings_rate_report < 0:
             report_data['recommendations'].append({
                'severity': 'high', 'title': 'Gastas más de lo que ingresas', 
                'description': 'Tu balance mensual es negativo. Es crucial ajustar tus finanzas.',
                'actions': ['Crea un presupuesto estricto.', 'Identifica y reduce gastos grandes.', 'Considera refinanciar deudas.']
            })

        if debt_to_income_ratio_report > 36: # Umbral común para DTI
            report_data['recommendations'].append({
                'severity': 'high' if debt_to_income_ratio_report > 43 else 'medium', 
                'title': 'Ratio Deuda/Ingresos elevado',
                'description': f'Un {debt_to_income_ratio_report:.1f}% de tus ingresos se destina a deudas. Intenta reducirlo.',
                'actions': ['Prioriza deudas con interés alto.', 'Evita nuevas deudas.']
            })
        
        # (Añadir más recomendaciones...)

        return render_template('financial_report.html', report=report_data)
        
    except Exception as e:
        app.logger.error(f"Error generando informe financiero: {e}", exc_info=True)
        flash(f"Error al generar el informe financiero: {str(e)}", "danger")
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




# Ensure these are imported at the top of app.py if not already:
# from .models import db, Expense, ExpenseCategory, DebtInstallmentPlan, FixedIncome 
# from .forms import ExpenseForm, ExpenseCategoryForm
# from flask_login import current_user, login_required
# from flask import render_template, redirect, url_for, flash, request
# from datetime import date, timedelta, datetime

@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    """Muestra y gestiona la página de gastos."""
    category_form = ExpenseCategoryForm()
    expense_form = ExpenseForm()
    today = date.today() # Define today here for use throughout

    # Populate category dropdown for category_form
    user_expense_categories_main = ExpenseCategory.query.filter_by(user_id=current_user.id, parent_id=None).order_by(ExpenseCategory.name).all()
    category_form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [(cat.id, cat.name) for cat in user_expense_categories_main]

    # Populate category dropdown for expense_form
    all_categories_for_expense_form = ExpenseCategory.query.filter_by(user_id=current_user.id).order_by(ExpenseCategory.name).all()
    expense_category_choices = []
    main_categories_for_expense = [c for c in all_categories_for_expense_form if c.parent_id is None]
    for cat_exp in main_categories_for_expense:
        expense_category_choices.append((cat_exp.id, cat_exp.name))
        subcats_exp = [s for s in all_categories_for_expense_form if s.parent_id == cat_exp.id]
        for subcat_exp in subcats_exp:
            expense_category_choices.append((subcat_exp.id, f"↳ {subcat_exp.name}"))
    expense_form.category_id.choices = [(0, 'Sin categoría')] + expense_category_choices

    if request.method == 'POST':
        if 'add_category' in request.form and category_form.validate_on_submit():
            try:
                parent_id_val = category_form.parent_id.data
                if parent_id_val == 0: parent_id_val = None
                new_category = ExpenseCategory(
                    user_id=current_user.id,
                    name=category_form.name.data,
                    description=category_form.description.data,
                    parent_id=parent_id_val
                )
                db.session.add(new_category)
                db.session.commit()
                flash('Categoría añadida correctamente.', 'success')
                return redirect(url_for('expenses'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al crear categoría: {str(e)}', 'danger')
                app.logger.error(f"Error creando categoría de gasto: {e}", exc_info=True)

        elif 'add_expense' in request.form and expense_form.validate_on_submit():
            try:
                amount_val = float(expense_form.amount.data.replace(',', '.'))
                date_obj_val = datetime.strptime(expense_form.date.data, '%Y-%m-%d').date()
                category_id_val = expense_form.category_id.data
                if category_id_val == 0: category_id_val = None

                is_recurring_val = expense_form.expense_type.data == 'fixed'
                recurrence_months_val = None
                start_date_val = None # Will be set to date_obj_val if recurring
                end_date_val = None

                if is_recurring_val:
                    recurrence_months_val = expense_form.recurrence_months.data
                    start_date_val = date_obj_val 
                    if expense_form.end_date.data:
                        end_date_val = datetime.strptime(expense_form.end_date.data, '%Y-%m-%d').date()
                
                new_expense = Expense(
                    user_id=current_user.id,
                    category_id=category_id_val,
                    description=expense_form.description.data,
                    amount=amount_val,
                    date=date_obj_val, # For punctual, this is the date; for recurring, it's the first occurrence/reference
                    expense_type=expense_form.expense_type.data,
                    is_recurring=is_recurring_val,
                    recurrence_months=recurrence_months_val if is_recurring_val else None,
                    start_date=start_date_val if is_recurring_val else date_obj_val, # Ensure start_date is set
                    end_date=end_date_val
                )
                db.session.add(new_expense)
                db.session.commit()
                flash('Gasto registrado correctamente.', 'success')
                return redirect(url_for('expenses'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al registrar gasto: {str(e)}', 'danger')
                app.logger.error(f"Error registrando gasto: {e}", exc_info=True)
        
        # If POST but forms didn't validate correctly, it will fall through to render_template
        # and WTForms will handle displaying errors on the forms.

    # --- Data for GET request or if POST failed validation ---
    user_expenses_db = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    
    fixed_expenses_sum = 0
    for e in user_expenses_db:
        if e.expense_type == 'fixed' and e.is_recurring:
            is_currently_active = True
            if e.end_date and e.end_date < today.replace(day=1): # If end_date is before the start of current month
                is_currently_active = False
            if e.start_date and e.start_date > today: # If start_date is in the future
                is_currently_active = False
            if is_currently_active:
                fixed_expenses_sum += e.amount
    
    one_month_ago = today - timedelta(days=30)
    punctual_expenses_sum = sum(e.amount for e in user_expenses_db if e.expense_type == 'punctual' and e.date >= one_month_ago and e.date <= today)
    
    debt_plans_active = DebtInstallmentPlan.query.filter_by(user_id=current_user.id, is_active=True).all()
    current_month_date_obj = date(today.year, today.month, 1)
    debt_monthly_sum = 0
    for plan in debt_plans_active:
        plan_end_date_prop = plan.end_date # Access the property
        if plan.start_date <= current_month_date_obj and (plan_end_date_prop is None or current_month_date_obj < plan_end_date_prop):
            debt_monthly_sum += plan.monthly_payment
            
    total_monthly_expenses_summary = fixed_expenses_sum + debt_monthly_sum # Note: punctual_expenses_sum is last 30 days, not strictly "monthly average" for this summary card

    # --- Comparativa vs Media ---
    current_month_start_date = today.replace(day=1)
    current_month_expenses_val = 0
    # Gastos fijos del mes actual
    for exp_fixed_comp in user_expenses_db:
        if exp_fixed_comp.expense_type == 'fixed' and exp_fixed_comp.is_recurring:
            # Check if this fixed expense occurs in the current month
            start_d_comp = exp_fixed_comp.start_date or exp_fixed_comp.date
            end_d_comp = exp_fixed_comp.end_date
            
            # Normalize to first of month for comparison
            start_d_comp_month = start_d_comp.replace(day=1)
            end_d_comp_month = end_d_comp.replace(day=1) if end_d_comp else date.max

            if start_d_comp_month <= current_month_start_date <= end_d_comp_month:
                 current_month_expenses_val += exp_fixed_comp.amount
    # Gastos puntuales del mes actual
    current_month_expenses_val += sum(e.amount for e in user_expenses_db if e.expense_type == 'punctual' and e.date >= current_month_start_date and e.date <= today)
    current_month_expenses_val += debt_monthly_sum # Gastos de deuda del mes actual (calculated above)
    
    # Media 6 meses (usando la lógica de get_category_analysis para consistencia)
    six_months_ago_start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1) # Start of 1st month, 6 months ago
    for _ in range(5): # Go back 5 more full months
        six_months_ago_start_date = (six_months_ago_start_date - timedelta(days=1)).replace(day=1)
    
    # For average, we use end of *previous* month as the period for averaging past data, or end of current month if it's partial.
    # Let's use the total expenses from get_category_analysis for 6 months for better consistency.
    # This means the JS call to fetchCategoryAnalysis(6) will provide the basis for this average eventually.
    # For now, an approximation for display:
    # A more accurate average would involve expanding all expenses over the last 6 months.
    # For a quick display, this can be simplified or fetched.
    # Let's use a placeholder for now, assuming JS will fill the precise table that drives this.
    # avg_monthly_expenses_summary = ... (this would require full expansion logic like in get_category_analysis)
    # Placeholder:
    expenses_for_avg_calc = []
    temp_iter_date = six_months_ago_start_date
    end_avg_period = today.replace(day=1) # Average up to the start of the current month

    while temp_iter_date < end_avg_period: # Iterate through the last 6 full past months
        # Direct fixed expenses
        for exp_avg in user_expenses_db:
            if exp_avg.is_recurring and exp_avg.expense_type == 'fixed':
                s_avg = exp_avg.start_date or exp_avg.date
                e_avg = exp_avg.end_date
                if s_avg.replace(day=1) <= temp_iter_date and (not e_avg or temp_iter_date < e_avg.replace(day=1)):
                    if (temp_iter_date.year - s_avg.year) * 12 + (temp_iter_date.month - s_avg.month) % (exp_avg.recurrence_months or 1) == 0:
                        expenses_for_avg_calc.append(exp_avg.amount)
        # Direct punctual expenses
        expenses_for_avg_calc.extend(e.amount for e in user_expenses_db if not e.is_recurring and e.date.year == temp_iter_date.year and e.date.month == temp_iter_date.month)
        # Debt payments
        for plan_avg in debt_plans_active: # only active plans contribute to ongoing average
            plan_end_date_prop_avg = plan_avg.end_date
            if plan_avg.start_date <= temp_iter_date and (plan_end_date_prop_avg is None or temp_iter_date < plan_end_date_prop_avg):
                expenses_for_avg_calc.append(plan_avg.monthly_payment)
        
        next_m_avg = temp_iter_date.month + 1
        next_y_avg = temp_iter_date.year
        if next_m_avg > 12: next_m_avg = 1; next_y_avg += 1
        try: temp_iter_date = date(next_y_avg, next_m_avg, 1)
        except ValueError: break
        
    avg_monthly_expenses_summary = sum(expenses_for_avg_calc) / 6 if expenses_for_avg_calc else 0
    current_vs_avg_pct_val = ((current_month_expenses_val - avg_monthly_expenses_summary) / avg_monthly_expenses_summary * 100) if avg_monthly_expenses_summary > 0 else 0

    # --- Historial Unificado de Gastos ---
    unified_expenses_list = []
    for expense_item in user_expenses_db:
        category_name_exp = expense_item.category.name if expense_item.category else "Sin categoría"
        if expense_item.is_recurring and expense_item.expense_type == 'fixed':
            start_loop_date = expense_item.start_date or expense_item.date
            # Limit loop to today to not show future occurrences in history
            effective_end_loop_date = expense_item.end_date if expense_item.end_date and expense_item.end_date <= today else today
            
            current_loop_date = start_loop_date
            recurrence_loop = expense_item.recurrence_months or 1
            while current_loop_date <= effective_end_loop_date:
                unified_expenses_list.append({
                    'id': expense_item.id, # Base ID of the recurring expense
                    'unique_id': f"exp_{expense_item.id}_{current_loop_date.strftime('%Y%m%d')}", # For modal uniqueness
                    'description': f"{expense_item.description}", # Base description
                    'occurrence_date_display': f"({current_loop_date.strftime('%b %Y')})", # Display specific occurrence
                    'amount': expense_item.amount,
                    'date': current_loop_date, # Actual date of this occurrence
                    'expense_type': expense_item.expense_type,
                    'is_recurring': expense_item.is_recurring,
                    'category_name': category_name_exp,
                    'from_debt': False,
                    'is_mortgage_payment': False,
                    'is_ended': expense_item.end_date is not None and current_loop_date.replace(day=1) >= expense_item.end_date.replace(day=1),
                    'end_date_obj': expense_item.end_date # Pass actual end_date object
                })
                year_next = current_loop_date.year
                month_next = current_loop_date.month + recurrence_loop
                while month_next > 12: month_next -= 12; year_next +=1
                try: current_loop_date = date(year_next, month_next, 1)
                except ValueError: break
        else: # Punctual expenses
            unified_expenses_list.append({
                'id': expense_item.id,
                'unique_id': f"exp_{expense_item.id}_{expense_item.date.strftime('%Y%m%d')}",
                'description': expense_item.description,
                'occurrence_date_display': "", # No extra date for punctual
                'amount': expense_item.amount,
                'date': expense_item.date,
                'expense_type': expense_item.expense_type,
                'is_recurring': expense_item.is_recurring,
                'category_name': category_name_exp,
                'from_debt': False,
                'is_mortgage_payment': False,
                'is_ended': False,
                'end_date_obj': None
            })

    debt_plans_for_history = DebtInstallmentPlan.query.options(
        db.joinedload(DebtInstallmentPlan.category)
    ).filter_by(user_id=current_user.id).all()

    for plan in debt_plans_for_history:
        num_payments_occurred = plan.duration_months - plan.remaining_installments
        if not plan.is_active and plan.remaining_installments == 0:
            num_payments_occurred = plan.duration_months

        current_payment_date_for_plan = date(plan.start_date.year, plan.start_date.month, 1)
        
        for i in range(num_payments_occurred):
            category_name_for_debt_payment = plan.category.name if plan.category else "Deuda (Sin Categoría)"
            description_prefix = "Pago Hipoteca" if plan.is_mortgage else "Pago Deuda"

            unified_expenses_list.append({
                'id': f"debt_{plan.id}", # Base ID for debt plan related actions
                'unique_id': f"debt_{plan.id}_{current_payment_date_for_plan.strftime('%Y%m%d')}",
                'description': f"{description_prefix}: {plan.description}",
                'occurrence_date_display': f"({current_payment_date_for_plan.strftime('%b %Y')})",
                'amount': plan.monthly_payment,
                'date': current_payment_date_for_plan,
                'expense_type': 'debt_payment', 
                'is_recurring': True, 
                'category_name': category_name_for_debt_payment,
                'from_debt': True,
                'is_mortgage_payment': plan.is_mortgage, # **** MODIFIED: ADDED THIS FLAG ****
                'is_ended': (not plan.is_active and i == (num_payments_occurred -1)),
                'end_date_obj': plan.end_date # Property access
            })

            month_next_debt = current_payment_date_for_plan.month + 1
            year_next_debt = current_payment_date_for_plan.year
            if month_next_debt > 12:
                month_next_debt = 1; year_next_debt += 1
            try: current_payment_date_for_plan = date(year_next_debt, month_next_debt, 1)
            except ValueError: break 
            
    unified_expenses_list.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('expenses.html',
                         title="Gestión de Gastos",
                         category_form=category_form,
                         expense_form=expense_form,
                         unified_expenses=unified_expenses_list,
                         fixed_expenses_sum=fixed_expenses_sum,
                         punctual_expenses_sum=punctual_expenses_sum,
                         debt_monthly_sum=debt_monthly_sum,
                         total_monthly_expenses=total_monthly_expenses_summary,
                         current_month_expenses=current_month_expenses_val,
                         avg_monthly_expenses=avg_monthly_expenses_summary,
                         current_vs_avg_pct=current_vs_avg_pct_val,
                         now=datetime.now()) # For setting default date in JS


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


# Ensure these are imported at the top of app.py if not already:
# from flask import request, jsonify # jsonify is not used here, render_template is
# from .models import db, Expense, ExpenseCategory, DebtInstallmentPlan # Adjust as per your model locations
# from flask_login import current_user, login_required
# from datetime import date, timedelta, datetime

@app.route('/get_category_analysis')
@login_required
def get_category_analysis():
    months_param = request.args.get('months', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    today = date.today()
    # analysis_end_date is the last day of the current month, or today if custom range ends earlier.
    # For month-based ranges, we want to include the entirety of the end month.
    
    range_description = ""
    months_in_range = 0

    if start_date_str and end_date_str:
        try:
            analysis_start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date().replace(day=1)
            # For custom range, end_date is the last day of the selected month
            temp_end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            next_month = temp_end_date.replace(day=28) + timedelta(days=4) # Go to next month
            analysis_end_date = next_month - timedelta(days=next_month.day) # Last day of temp_end_date's month

            if analysis_start_date > analysis_end_date:
                return '<div class="alert alert-danger">La fecha de inicio no puede ser posterior a la fecha de fin.</div>', 400
            range_description = f"{analysis_start_date.strftime('%d/%m/%Y')} - {analysis_end_date.strftime('%d/%m/%Y')}"
            months_in_range = (analysis_end_date.year - analysis_start_date.year) * 12 + (analysis_end_date.month - analysis_start_date.month) + 1
        except ValueError:
            return '<div class="alert alert-danger">Formato de fecha inválido.</div>', 400
    else:
        months_param = months_param if months_param else 6 # Default to 6 months
        months_in_range = months_param
        
        # Calculate end_date as the last day of the current month
        next_month_today = today.replace(day=28) + timedelta(days=4)
        analysis_end_date = next_month_today - timedelta(days=next_month_today.day)

        # Calculate start_date as the first day of the month, 'months_param' months ago
        analysis_start_date = today.replace(day=1)
        for _ in range(months_param -1):
            prev_month_end = analysis_start_date - timedelta(days=1)
            analysis_start_date = prev_month_end.replace(day=1)
        
        if months_param == 1: range_description = "Último mes"
        elif months_param == 3: range_description = "Últimos 3 meses"
        elif months_param == 6: range_description = "Últimos 6 meses"
        elif months_param == 12: range_description = "Último año"
        elif months_param == 36: range_description = "Últimos 3 años"
        elif months_param == 60: range_description = "Últimos 5 años"
        elif months_param == 120: range_description = "Últimos 10 años"
        else: range_description = f"Últimos {months_param} meses"

    all_expense_occurrences = []

    # 1. Process Direct Expenses (from Expense model)
    direct_expenses_query = Expense.query.filter(Expense.user_id == current_user.id).all()
    for expense in direct_expenses_query:
        category_name = expense.category.name if expense.category else "Sin categoría"
        if expense.is_recurring and expense.expense_type == 'fixed':
            expense_loop_start_date = expense.start_date or expense.date
            # For recurring, iterate through months it's active within the analysis window
            current_occurrence_month_start = expense_loop_start_date.replace(day=1)
            
            while current_occurrence_month_start <= analysis_end_date:
                if current_occurrence_month_start < analysis_start_date: # Fast-forward if before analysis window
                    year_next = current_occurrence_month_start.year
                    month_next = current_occurrence_month_start.month + (expense.recurrence_months or 1)
                    while month_next > 12: month_next -= 12; year_next += 1
                    try: current_occurrence_month_start = date(year_next, month_next, 1)
                    except ValueError: break
                    continue

                # Check if this occurrence is within the expense's own active period
                is_within_expense_period = True
                if expense.end_date and current_occurrence_month_start > expense.end_date:
                    is_within_expense_period = False
                
                if is_within_expense_period:
                    all_expense_occurrences.append({
                        'amount': expense.amount,
                        'category_name': category_name
                    })

                # Advance to next recurrence for this expense
                year_next = current_occurrence_month_start.year
                month_next = current_occurrence_month_start.month + (expense.recurrence_months or 1)
                while month_next > 12: month_next -= 12; year_next += 1
                try: current_occurrence_month_start = date(year_next, month_next, 1)
                except ValueError: break # Invalid date, stop processing this expense
        else: # Punctual expenses
            if analysis_start_date <= expense.date <= analysis_end_date:
                all_expense_occurrences.append({
                    'amount': expense.amount,
                    'category_name': category_name
                })

    # 2. Process Debt Payments
    active_debt_plans = DebtInstallmentPlan.query.options(
        db.joinedload(DebtInstallmentPlan.category)
    ).filter(
        DebtInstallmentPlan.user_id == current_user.id,
        DebtInstallmentPlan.is_active == True 
    ).all()

    current_month_iterator = analysis_start_date.replace(day=1)
    while current_month_iterator <= analysis_end_date:
        for plan in active_debt_plans:
            # plan.end_date is the property calculating the month *after* the last payment
            plan_is_payable_this_month = False
            if plan.start_date <= current_month_iterator:
                if plan.end_date: # plan.end_date is already first day of month AFTER last payment
                    if current_month_iterator < plan.end_date:
                        plan_is_payable_this_month = True
                else: # Should not happen if plan has duration, but as fallback
                    plan_is_payable_this_month = True 
            
            if plan_is_payable_this_month:
                debt_category_name = plan.category.name if plan.category else "Deuda (Sin Categoría)"
                all_expense_occurrences.append({
                    'amount': plan.monthly_payment,
                    'category_name': debt_category_name
                })
        
        next_iter_month = current_month_iterator.month + 1
        next_iter_year = current_month_iterator.year
        if next_iter_month > 12:
            next_iter_month = 1
            next_iter_year += 1
        try:
            current_month_iterator = date(next_iter_year, next_iter_month, 1)
        except ValueError: # Should not happen with y/m logic
            break 

    # 3. Aggregate by category
    expenses_by_category_agg = {}
    for occ in all_expense_occurrences:
        cat_name = occ['category_name']
        expenses_by_category_agg.setdefault(cat_name, {'total': 0, 'monthly_avg': 0})
        expenses_by_category_agg[cat_name]['total'] += occ['amount']

    total_sum_for_period = sum(data['total'] for data in expenses_by_category_agg.values())

    if months_in_range > 0:
        for cat_name, data in expenses_by_category_agg.items():
            data['monthly_avg'] = data['total'] / months_in_range
    else: # Avoid division by zero if range is somehow zero months
         for cat_name, data in expenses_by_category_agg.items():
            data['monthly_avg'] = data['total'] 


    sorted_categories_final = sorted(
        expenses_by_category_agg.items(),
        key=lambda x: x[1]['total'],
        reverse=True
    )
    
    return render_template(
        'category_analysis_table.html', 
        sorted_categories=sorted_categories_final,
        total_sum=total_sum_for_period,
        range_description=range_description,
        months_in_range=months_in_range 
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


# En app.py


# Ensure 'math' is imported at the top of your app.py
import math
# Ensure RealEstateAsset, RealEstateMortgage, DebtInstallmentPlan, etc. are imported

@app.route('/debt_management', methods=['GET', 'POST'])
@login_required
def debt_management():
    income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
    monthly_salary = (income_data.annual_net_salary / 12) if income_data and income_data.annual_net_salary else None
    debt_ceiling = DebtCeiling.query.filter_by(user_id=current_user.id).first()
    if not debt_ceiling: 
        debt_ceiling = DebtCeiling(user_id=current_user.id)
        db.session.add(debt_ceiling)
        # Commit immediately or ensure it's part of a transaction that commits soon
        # For simplicity if this is rare, an immediate commit is fine.
        try:
            db.session.commit()
        except Exception as e_dc_commit:
            db.session.rollback()
            app.logger.error(f"Error committing initial debt ceiling: {e_dc_commit}")


    ceiling_amount = (monthly_salary * (debt_ceiling.percentage / 100)) if monthly_salary and debt_ceiling and debt_ceiling.percentage is not None else None
    
    ceiling_form = DebtCeilingForm(request.form if request.method == 'POST' and 'update_ceiling' in request.form else None, obj=debt_ceiling if request.method == 'GET' else None)
    plan_form = DebtInstallmentPlanForm(request.form if request.method == 'POST' and 'add_plan' in request.form else None)
    modal_category_form = ExpenseCategoryForm()
    modal_asset_form = RealEstateAssetFormPopup()

    plan_form.category_id.render_kw = {}
    plan_form.linked_asset_id.render_kw = {} 
    if hasattr(plan_form, 'duration_months_input') and plan_form.duration_months_input:
        plan_form.duration_months_input.render_kw = {}
    if hasattr(plan_form, 'monthly_payment_input') and plan_form.monthly_payment_input:
        plan_form.monthly_payment_input.render_kw = {}
    
    all_expense_categories = ExpenseCategory.query.filter_by(user_id=current_user.id).order_by(ExpenseCategory.name).all()
    category_choices = []
    main_cats_for_modal = []
    main_cats_for_plan_form = [c for c in all_expense_categories if c.parent_id is None]

    for cat_main in main_cats_for_plan_form:
        category_choices.append((cat_main.id, cat_main.name))
        main_cats_for_modal.append({'id': cat_main.id, 'name': cat_main.name})
        for sub_cat in [s for s in all_expense_categories if s.parent_id == cat_main.id]:
            category_choices.append((sub_cat.id, f"↳ {sub_cat.name}"))
    
    plan_form.category_id.choices = [(0, '- Selecciona una Categoría -')] + category_choices
    modal_category_form.parent_id.choices = [(0, 'Ninguna (Categoría Principal)')] + [(c['id'], c['name']) for c in main_cats_for_modal]

    assets_without_active_mortgage = RealEstateAsset.query\
        .outerjoin(DebtInstallmentPlan, RealEstateAsset.id == DebtInstallmentPlan.linked_asset_id_for_mortgage)\
        .filter(RealEstateAsset.user_id == current_user.id)\
        .filter(db.or_(DebtInstallmentPlan.id == None, DebtInstallmentPlan.is_active == False))\
        .order_by(RealEstateAsset.property_name).all()

    asset_choices = [(asset.id, f"{asset.property_type + ' - ' if asset.property_type else ''}{asset.property_name}") 
                     for asset in assets_without_active_mortgage]
    
    if asset_choices:
        plan_form.linked_asset_id.choices = [(0, '- Selecciona Inmueble (si es hipoteca) -')] + asset_choices
    else: 
        plan_form.linked_asset_id.choices = [(0, 'No hay inmuebles elegibles')]
        plan_form.linked_asset_id.render_kw['disabled'] = True
        
    if request.method == 'POST':
        if 'update_ceiling' in request.form:
            if ceiling_form.validate():
                try:
                    percentage_str = str(ceiling_form.percentage.data).replace(',', '.') 
                    debt_ceiling.percentage = float(percentage_str)
                    debt_ceiling.last_updated = datetime.utcnow()
                    db.session.commit()
                    flash('Techo de deuda actualizado correctamente.', 'success')
                    return redirect(url_for('debt_management'))
                except (ValueError, TypeError, Exception) as e: 
                    db.session.rollback()
                    flash(f'Error al procesar los datos del techo de deuda: {str(e)}', 'danger')
                    app.logger.error(f"Error actualizando techo de deuda: {e}", exc_info=True)
        
        elif 'add_plan' in request.form:
            is_mortgage_checked = plan_form.is_mortgage.data # Use plan_form.is_mortgage.data
            linked_asset_id_val = plan_form.linked_asset_id.data if is_mortgage_checked else None

            if is_mortgage_checked and (not linked_asset_id_val or linked_asset_id_val == 0):
                plan_form.linked_asset_id.errors.append("Debe seleccionar un inmueble si es una hipoteca.")
            
            if plan_form.validate() and not plan_form.linked_asset_id.errors:
                try:
                    start_month_year_str = plan_form.start_date.data
                    year_val, month_val = map(int, start_month_year_str.split('-'))
                    start_date_obj_val = date(year_val, month_val, 1)
                    total_amount_val = plan_form.total_amount.data 
                    
                    duration_months_final = None
                    monthly_payment_final = None

                    if plan_form.payment_input_type.data == 'duration':
                        duration_months_final = plan_form.duration_months_input.data
                        if duration_months_final and total_amount_val and duration_months_final > 0:
                            monthly_payment_final = total_amount_val / duration_months_final
                        else:
                            flash("Se requiere Cantidad Total y Duración (mayor que cero) para calcular la mensualidad.", "danger")
                            raise ValueError("Datos insuficientes para cálculo de mensualidad.")
                    elif plan_form.payment_input_type.data == 'monthly_amount':
                        monthly_payment_final = plan_form.monthly_payment_input.data
                        if monthly_payment_final and total_amount_val and monthly_payment_final > 0:
                            duration_months_final = math.ceil(total_amount_val / monthly_payment_final)
                        else:
                            flash("Se requiere Cantidad Total y Mensualidad (mayor que cero) para calcular la duración.", "danger")
                            raise ValueError("Datos insuficientes o inválidos para cálculo de duración.")
                    
                    # end_date_obj_val = calculate_end_date(start_date_obj_val, duration_months_final) 
                    # is_active_val = end_date_obj_val >= date.today() if end_date_obj_val else True
                    # is_active_val will be determined by DebtInstallmentPlan properties later

                    description_val = plan_form.description.data

                    if is_mortgage_checked and linked_asset_id_val and linked_asset_id_val !=0:
                        selected_asset = db.session.get(RealEstateAsset, linked_asset_id_val)
                        if selected_asset and selected_asset.user_id == current_user.id:
                            description_val = f"{selected_asset.property_type + ' - ' if selected_asset.property_type else ''}{selected_asset.property_name}"
                            # Check if asset already has an *active* mortgage debt plan
                            if selected_asset.debt_plan_as_mortgage and selected_asset.debt_plan_as_mortgage.is_active:
                                flash(f"El inmueble '{selected_asset.property_name}' ya tiene una hipoteca (plan de deuda) activa asociada.", "warning")
                                raise ValueError("Inmueble ya hipotecado con plan de deuda activo.")
                        else:
                            flash("Inmueble seleccionado para hipoteca no válido.", "danger")
                            raise ValueError("Inmueble no válido para hipoteca.")
                    else: # If not mortgage or no asset selected, ensure linked_asset_id_val is None
                        linked_asset_id_val = None


                    new_debt_plan = DebtInstallmentPlan(
                        user_id=current_user.id, expense_category_id=plan_form.category_id.data,
                        description=description_val, total_amount=total_amount_val,
                        start_date=start_date_obj_val, duration_months=duration_months_final,
                        monthly_payment=monthly_payment_final, # is_active will be determined by its property
                        is_mortgage=is_mortgage_checked, 
                        linked_asset_id_for_mortgage=linked_asset_id_val if is_mortgage_checked else None
                    )
                    db.session.add(new_debt_plan)
                    db.session.flush() # new_debt_plan gets an ID
                    
                    if is_mortgage_checked and linked_asset_id_val and new_debt_plan.id is not None :
                        asset_to_mortgage = db.session.get(RealEstateAsset, linked_asset_id_val)
                        if asset_to_mortgage:
                            # 1. Delete any existing RealEstateMortgage record directly linked to THIS ASSET
                            #    This is if the asset had an old RealEstateMortgage entry not tied to a still-active debt plan.
                            if asset_to_mortgage.mortgage:
                                app.logger.info(f"Asset (ID: {asset_to_mortgage.id}) has an existing RealEstateMortgage record (ID: {asset_to_mortgage.mortgage.id}). Deleting it before creating new one.")
                                db.session.delete(asset_to_mortgage.mortgage)
                                db.session.flush()

                            # 2. DEFENSIVE CHECK & CLEANUP:
                            #    Check if any RealEstateMortgage record (for any asset, by any user - though should be scoped to user)
                            #    is ALREADY using the new_debt_plan.id. This handles orphaned RealEstateMortgage records
                            #    if the cascade on DebtInstallmentPlan deletion wasn't in place or didn't cover an old case.
                            existing_rem_with_colliding_dip_id = RealEstateMortgage.query.filter_by(
                                debt_installment_plan_id=new_debt_plan.id
                            ).first()
                            
                            if existing_rem_with_colliding_dip_id:
                                app.logger.warning(
                                    f"DEFENSIVE CLEANUP: Found RealEstateMortgage (ID: {existing_rem_with_colliding_dip_id.id}, on asset ID: {existing_rem_with_colliding_dip_id.asset_id}, by user: {existing_rem_with_colliding_dip_id.user_id}) "
                                    f"already linked to the NEW DebtInstallmentPlan ID: {new_debt_plan.id}. Deleting this conflicting record."
                                )
                                db.session.delete(existing_rem_with_colliding_dip_id)
                                db.session.flush() 

                            # 3. Create and link the new mortgage record
                            new_mortgage_record = RealEstateMortgage(
                                asset_id=asset_to_mortgage.id,
                                user_id=current_user.id,
                                original_loan_amount=total_amount_val,
                                current_principal_balance=total_amount_val, # Initial balance is total amount
                                monthly_payment=monthly_payment_final,
                                loan_start_date=start_date_obj_val,
                                loan_term_years=math.ceil(duration_months_final / 12) if duration_months_final else None,
                                debt_installment_plan_id=new_debt_plan.id # Link to the new debt plan
                            )
                            db.session.add(new_mortgage_record)
                            asset_to_mortgage.mortgage = new_mortgage_record # Establish relationship for the asset
                    
                    db.session.commit()
                    flash('Plan de pago añadido correctamente.', 'success')
                    return redirect(url_for('debt_management'))
                except ValueError as ve:
                    db.session.rollback() # Rollback on known ValueErrors too
                    app.logger.warning(f"ValueError al crear plan de pago: {ve}")
                    # flash(str(ve), 'danger') # Flash message is already set by the raising code
                except Exception as e:
                    db.session.rollback()
                    flash(f'Error al crear plan de pago: {str(e)}', 'danger')
                    app.logger.error(f"Error creando plan de pago: {e}", exc_info=True)

    if request.method == "GET" and not ceiling_form.is_submitted():
        ceiling_form = DebtCeilingForm(obj=debt_ceiling)

    all_debt_plans_query = DebtInstallmentPlan.query.options(
        db.joinedload(DebtInstallmentPlan.category)
    ).filter_by(user_id=current_user.id).all()
    
    today = date.today()
    plan_end_dates = {plan.id: plan.end_date for plan in all_debt_plans_query if plan.end_date}
    
    # Populate is_active based on current date and end_date for all plans before filtering
    for plan_dp in all_debt_plans_query:
        if plan_dp.end_date:
            plan_dp.is_active = plan_dp.end_date >= date(today.year, today.month, 1) # Active if end date is this month or later
        else: # No end date means it's ongoing, depends on remaining installments
            plan_dp.is_active = plan_dp.remaining_installments > 0


    all_debt_plans_sorted = sorted(
        all_debt_plans_query, 
        key=lambda p: (not p.is_active, plan_end_dates.get(p.id, date.max), p.start_date),
        reverse=False # Active first, then by end_date ascending, then by start_date ascending
    )
    
    active_debt_plans_list = [plan for plan in all_debt_plans_sorted if plan.is_active]
    
    current_month_date_display = date(today.year, today.month, 1)
    nm_year_display, nm_month_display = (today.year, today.month + 1) if today.month < 12 else (today.year + 1, 1)
    next_month_date_display = date(nm_year_display, nm_month_display, 1)

    total_debt_remaining_display = sum(plan.remaining_amount for plan in active_debt_plans_list)
    current_month_payment_display = sum(plan.monthly_payment for plan in active_debt_plans_list if plan.start_date <= current_month_date_display and (not plan.end_date or plan.end_date >= current_month_date_display))
    next_month_payment_display = sum(plan.monthly_payment for plan in active_debt_plans_list if plan.start_date <= next_month_date_display and (not plan.end_date or plan.end_date >= next_month_date_display))
    
    debt_percentage_display = (current_month_payment_display / ceiling_amount * 100) if ceiling_amount and ceiling_amount > 0 else None
    debt_margin_display = (ceiling_amount - current_month_payment_display) if ceiling_amount is not None else None
        
    return render_template(
        'debt_management.html',
        ceiling_form=ceiling_form,
        plan_form=plan_form,
        modal_category_form=modal_category_form,
        modal_asset_form=modal_asset_form,
        debt_ceiling=debt_ceiling, 
        ceiling_amount=ceiling_amount,
        all_debt_plans=all_debt_plans_sorted, # Pass the fully sorted list for historical view
        active_debt_plans=active_debt_plans_list,
        total_debt_remaining=total_debt_remaining_display,
        current_month_payment=current_month_payment_display,
        next_month_payment=next_month_payment_display,
        debt_percentage=debt_percentage_display,
        debt_margin=debt_margin_display,
        current_month=current_month_date_display,
        next_month=next_month_date_display,
        monthly_salary=monthly_salary,
        now=datetime.now(), # Used in template for {% set today = now.date() %}
        plan_end_dates=plan_end_dates
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


@app.route('/crypto_portfolio', methods=['GET', 'POST'])
@login_required
def crypto_portfolio():
    """Muestra y gestiona la página de portfolio de criptomonedas (funcionalidad manual)."""
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
            return redirect(url_for('crypto_portfolio'))
            
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
                return redirect(url_for('crypto_portfolio'))
            
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
            return redirect(url_for('crypto_portfolio'))
            
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
        'crypto_portfolio.html',  # Cambiar el nombre del template
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


@app.route('/delete_crypto_movement/<int:movement_id>', methods=['POST'])
@login_required
def delete_crypto_movement(movement_id):
    """Elimina un movimiento específico."""
    movement = CryptoCsvMovement.query.filter_by(id=movement_id, user_id=current_user.id).first_or_404()
    
    try:
        db.session.delete(movement)
        db.session.commit()
        flash('Movimiento eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar movimiento: {e}', 'danger')
    
    return redirect(url_for('crypto_movements'))


@app.route('/clear_all_crypto_movements', methods=['POST'])
@login_required
def clear_all_crypto_movements():
    """Elimina todos los movimientos CSV y mapeos del usuario"""
    try:
        # Eliminar todos los movimientos CSV del usuario
        CryptoCsvMovement.query.filter_by(user_id=current_user.id).delete()
        
        # Eliminar todos los mapeos de categorías del usuario
        CryptoCategoryMapping.query.filter_by(user_id=current_user.id).delete()
        
        # Eliminar verificaciones de precios del usuario
        CryptoPriceVerification.query.filter_by(user_id=current_user.id).delete()
        
        db.session.commit()
        flash('Todos los movimientos, mapeos y verificaciones han sido eliminados.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error eliminando datos: {str(e)}', 'danger')
    
    return redirect(url_for('crypto_movements'))

@app.route('/verify_crypto_prices', methods=['POST'])
@login_required
def verify_crypto_prices():
    """Verifica manualmente si yfinance puede obtener precios para las criptomonedas identificadas."""
    try:
        # Obtener todas las criptomonedas únicas del usuario
        unique_currencies = db.session.query(CryptoCsvMovement.currency).filter_by(
            user_id=current_user.id
        ).filter(
            CryptoCsvMovement.currency.isnot(None),
            CryptoCsvMovement.currency != ''
        ).distinct().all()
        
        verified_count = 0
        failed_count = 0
        
        for currency_tuple in unique_currencies:
            currency = currency_tuple[0]
            if not currency or not currency.strip():
                continue
                
            currency = currency.strip()
            
            # Intentar obtener precio con yfinance
            price_available = False
            try:
                # Intentar diferentes formatos de ticker para yfinance
                possible_tickers = [
                    f"{currency}-USD",  # BTC-USD
                    f"{currency}USD",   # BTCUSD  
                    currency,           # BTC
                    f"{currency}-EUR",  # BTC-EUR
                    f"{currency}EUR"    # BTCEUR
                ]
                
                for ticker in possible_tickers:
                    try:
                        crypto_ticker = yf.Ticker(ticker)
                        # Intentar obtener información básica
                        info = crypto_ticker.info
                        if info and 'regularMarketPrice' in info and info['regularMarketPrice'] is not None:
                            price_available = True
                            break
                        
                        # También intentar obtener datos históricos como respaldo
                        hist = crypto_ticker.history(period="1d")
                        if not hist.empty and len(hist) > 0:
                            price_available = True
                            break
                            
                    except Exception:
                        continue
                        
            except Exception as e:
                app.logger.warning(f"Error verificando precio para {currency}: {e}")
            
            # Guardar o actualizar el resultado de verificación
            existing_verification = CryptoPriceVerification.query.filter_by(
                user_id=current_user.id,
                currency_symbol=currency
            ).first()
            
            if existing_verification:
                existing_verification.price_available = price_available
                existing_verification.last_check = datetime.utcnow()
            else:
                new_verification = CryptoPriceVerification(
                    user_id=current_user.id,
                    currency_symbol=currency,
                    price_available=price_available,
                    last_check=datetime.utcnow()
                )
                db.session.add(new_verification)
            
            if price_available:
                verified_count += 1
            else:
                failed_count += 1
        
        db.session.commit()
        
        if verified_count > 0 or failed_count > 0:
            flash(f'Verificación completada: {verified_count} criptomonedas disponibles en yfinance, {failed_count} no disponibles.', 'success')
        else:
            flash('No se encontraron criptomonedas para verificar.', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error durante la verificación: {e}', 'danger')
        app.logger.error(f"Error en verify_crypto_prices: {e}", exc_info=True)
    
    return redirect(url_for('crypto_movements'))


# Añadir este campo al modelo CryptoCsvMovement en models.py:

# Dentro de la clase CryptoCsvMovement, añadir esta línea después de csv_filename:
transaction_hash_unique = db.Column(db.String(64), nullable=True, index=True)  # Hash para detectar duplicados

# Y añadir este método a la clase:
def generate_hash(self):
    """Genera un hash único basado en los datos principales de la transacción."""
    
    # Crear string con datos únicos de la transacción
    hash_data = f"{self.user_id}_{self.exchange_name}_{self.timestamp_utc}_{self.transaction_description}_{self.currency}_{self.amount}_{self.to_currency}_{self.to_amount}_{self.transaction_kind}_{self.transaction_hash}"
    
    # Generar hash SHA-256
    return hashlib.sha256(hash_data.encode('utf-8')).hexdigest()

# Función auxiliar para asegurar que Crypto.com existe como exchange
def ensure_crypto_com_exchange():
    """Asegura que el exchange Crypto.com existe para el usuario actual."""
    crypto_com = CryptoExchange.query.filter_by(
        user_id=current_user.id,
        exchange_name='Crypto.com'
    ).first()
    
    if not crypto_com:
        crypto_com = CryptoExchange(
            user_id=current_user.id,
            exchange_name='Crypto.com'
        )
        db.session.add(crypto_com)
        db.session.commit()
    
    return crypto_com

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


# REEMPLAZA tu función update_crypto_prices incompleta por esta versión completa:

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
    
    return redirect(url_for('crypto_portfolio'))



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
    
    return redirect(url_for('crypto_portfolio'))  # Actualizado

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
    
    return redirect(url_for('crypto_portfolio'))


@app.route('/edit_crypto_transaction/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_crypto_transaction(transaction_id):
    """Edita una operación existente."""
    transaction = CryptoTransaction.query.filter_by(id=transaction_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            transaction_type = request.form.get('transaction_type')
            crypto_name = request.form.get('crypto_name')
            ticker_symbol = request.form.get('ticker_symbol').upper()
            date_str = request.form.get('date')
            quantity = float(request.form.get('quantity').replace(',', '.'))
            price_per_unit = float(request.form.get('price_per_unit').replace(',', '.'))
            fees_str = request.form.get('fees')
            
            transaction_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            fees = None
            if fees_str and fees_str.strip():
                fees = float(fees_str.replace(',', '.'))
            
            transaction.transaction_type = transaction_type
            transaction.crypto_name = crypto_name
            transaction.ticker_symbol = ticker_symbol
            transaction.date = transaction_date
            transaction.quantity = quantity
            transaction.price_per_unit = price_per_unit
            transaction.fees = fees
            
            current_price = get_crypto_price(ticker_symbol)
            if current_price is not None:
                transaction.current_price = current_price
                transaction.price_updated_at = datetime.utcnow()
            
            db.session.commit()
            flash('Operación actualizada correctamente.', 'success')
            return redirect(url_for('crypto_portfolio'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la operación: {e}', 'danger')
    
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




def process_uploaded_csvs(files):
    all_dfs = []
    filenames_processed = []
    errors = []

    if not files or all(f.filename == '' for f in files):
        errors.append("Error: No archivos seleccionados.")
        return None, None, errors

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            if not validate_filename_format(filename):
                errors.append(f"Advertencia: Archivo '{filename}' ignorado (formato debe ser AAAA.csv).")
                continue
            
            df = None
            try:
                file.seek(0)
                df = pd.read_csv(io.BytesIO(file.read()), encoding='utf-8', sep=',', decimal='.', skiprows=0, header=0)
                print(f"Archivo '{filename}' leído con UTF-8. Columnas: {df.columns.tolist()}")
            except UnicodeDecodeError:
                try:
                    file.seek(0)
                    df = pd.read_csv(io.BytesIO(file.read()), encoding='latin-1', sep=',', decimal='.', skiprows=0, header=0)
                    print(f"Archivo '{filename}' leído con latin-1. Columnas: {df.columns.tolist()}")
                except Exception as e:
                    errors.append(f"Error leyendo '{filename}' (probado con UTF-8 y latin-1): {e}")
                    continue
            except Exception as e:
                errors.append(f"Error general leyendo '{filename}': {e}")
                continue

            if df is not None:
                missing_original_cols = [col for col in COLS_MAP.keys() if col not in df.columns]
                if missing_original_cols:
                    errors.append(f"Advertencia: Columnas originales faltantes en '{filename}': {', '.join(missing_original_cols)}.")
                
                df['source_file'] = filename
                all_dfs.append(df)
                filenames_processed.append(filename)
        elif file.filename != '':
            errors.append(f"Advertencia: Archivo '{file.filename}' ignorado (extensión no permitida o nombre vacío).")

    if not all_dfs:
        if not any("Error:" in e for e in errors): # Si no hay errores fatales previos
            errors.append("Error: No se procesaron archivos CSV válidos.")
        return None, None, errors

    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True)
        print(f"DataFrame raw combinado creado ({len(combined_df_raw)} filas).")

        if 'Fecha' in combined_df_raw.columns:
            combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
        
        if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
            try:
                # Asegurar que 'Fecha' sea string para concatenar, y 'Hora' también
                temp_f = combined_df_raw['Fecha'].dt.strftime('%Y-%m-%d')
                temp_h = combined_df_raw['Hora'].astype(str).str.strip()
                combined_df_raw['FechaHora'] = pd.to_datetime(temp_f + ' ' + temp_h, errors='coerce')
            except Exception as e_fh:
                print(f"Advertencia: No se pudo crear 'FechaHora' compuesta: {e_fh}. Usando solo 'Fecha' para ordenar.")
                combined_df_raw['FechaHora'] = combined_df_raw['Fecha'] # Fallback
        elif 'Fecha' in combined_df_raw.columns:
            combined_df_raw['FechaHora'] = combined_df_raw['Fecha']
        
        sort_col_name = 'FechaHora' if 'FechaHora' in combined_df_raw.columns else 'Fecha'
        if sort_col_name in combined_df_raw.columns:
            combined_df_raw = combined_df_raw.sort_values(by=sort_col_name, ascending=True, na_position='first')
        
    except Exception as e_concat:
        errors.append(f"Error al combinar archivos CSV o parsear fechas: {e_concat}")
        return None, None, errors # Devuelve None para df_for_portfolio_calc si falla aquí

    df_for_portfolio_calc = combined_df_raw.copy() # Para cálculo de portfolio con datos más crudos
    processed_df_for_csv = pd.DataFrame()

    try:
        # Filtrar solo columnas que existen en el DF y están en COLS_MAP
        cols_to_rename_present = [col for col in COLS_MAP.keys() if col in combined_df_raw.columns]
        if not cols_to_rename_present:
            errors.append("Error: Ninguna de las columnas esperadas (COLS_MAP) se encontró en los archivos CSV.")
            return None, df_for_portfolio_calc, errors # df_for_portfolio_calc podría tener datos, pero no para el CSV final

        filtered_df = combined_df_raw[cols_to_rename_present].copy()
        renamed = filtered_df.rename(columns=COLS_MAP)
        print(f"Columnas renombradas para CSV: {renamed.columns.tolist()}")

        if 'Bolsa' in renamed.columns:
            renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna('')
            print("Columna 'Exchange Yahoo' añadida.")
        else:
            renamed['Exchange Yahoo'] = '' # Asegurar que la columna exista
            errors.append("Advertencia: No se encontró la columna 'Bolsa' para generar 'Exchange Yahoo'.")

        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    cleaned_series = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False)
                    renamed[col] = pd.to_numeric(cleaned_series, errors='coerce')

                # ---- INICIO DEL CAMBIO ----
                # Reemplazar NaN con 0 después de la coerción
                if pd.api.types.is_numeric_dtype(renamed[col]) or renamed[col].isnull().any():
                    renamed[col] = renamed[col].fillna(0)
                # ---- FIN DEL CAMBIO ----

                if col == 'Cantidad':
                     if pd.api.types.is_numeric_dtype(renamed[col]): # Verificar de nuevo
                         renamed[col] = renamed[col].abs()
                
                if pd.api.types.is_numeric_dtype(renamed[col]): # Asegurar tipo float
                    renamed[col] = renamed[col].astype(float)
            else:
                errors.append(f"Advertencia: Columna numérica '{col}' no encontrada tras renombrar.")
                renamed[col] = 0.0 # Añadir columna con ceros si falta una numérica esencial

        processed_df_for_csv = renamed

    except KeyError as e_key:
        errors.append(f"Error de procesamiento (KeyError): Columna '{e_key}' no encontrada. Verifica COLS_MAP y tus CSVs.")
        return None, df_for_portfolio_calc, errors
    except Exception as e_proc:
        errors.append(f"Error general durante el procesamiento de datos para CSV: {e_proc}")
        return None, df_for_portfolio_calc, errors
        
    print(f"Procesamiento base completado. DF para CSV ({len(processed_df_for_csv)} filas), DF raw para portfolio ({len(df_for_portfolio_calc)} filas).")
    return processed_df_for_csv, df_for_portfolio_calc, errors


def process_csvs_from_paths(list_of_file_paths):
    all_dfs = []
    errors = []

    if not list_of_file_paths:
        errors.append("Error: No se proporcionaron rutas de archivo.")
        return None, None, errors

    for filepath in list_of_file_paths:
        filename = os.path.basename(filepath)
        df = None
        try:
            df = pd.read_csv(filepath, encoding='utf-8', sep=',', decimal='.', skiprows=0, header=0)
            print(f"Archivo de ruta '{filename}' leído con UTF-8. Columnas: {df.columns.tolist()}")
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(filepath, encoding='latin-1', sep=',', decimal='.', skiprows=0, header=0)
                print(f"Archivo de ruta '{filename}' leído con latin-1. Columnas: {df.columns.tolist()}")
            except Exception as e:
                errors.append(f"Error leyendo archivo de ruta '{filename}' (probado con UTF-8 y latin-1): {e}")
                continue
        except FileNotFoundError:
            errors.append(f"Error: Archivo no encontrado en la ruta: {filepath}")
            continue
        except Exception as e:
            errors.append(f"Error general leyendo archivo de ruta '{filename}': {e}")
            continue
        
        if df is not None:
            missing_original_cols = [col for col in COLS_MAP.keys() if col not in df.columns]
            if missing_original_cols:
                errors.append(f"Advertencia: Columnas originales faltantes en archivo de ruta '{filename}': {', '.join(missing_original_cols)}.")
            
            df['source_file'] = filename
            all_dfs.append(df)

    if not all_dfs:
        if not any("Error:" in e for e in errors):
             errors.append("Error: No se procesaron archivos CSV válidos desde las rutas especificadas.")
        return None, None, errors

    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True)
        print(f"DataFrame raw combinado (desde rutas) creado ({len(combined_df_raw)} filas).")

        if 'Fecha' in combined_df_raw.columns:
            combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)

        if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
            try:
                temp_f = combined_df_raw['Fecha'].dt.strftime('%Y-%m-%d')
                temp_h = combined_df_raw['Hora'].astype(str).str.strip()
                combined_df_raw['FechaHora'] = pd.to_datetime(temp_f + ' ' + temp_h, errors='coerce')
            except Exception as e_fh:
                print(f"Advertencia (rutas): No se pudo crear 'FechaHora' compuesta: {e_fh}. Usando solo 'Fecha' para ordenar.")
                combined_df_raw['FechaHora'] = combined_df_raw['Fecha']
        elif 'Fecha' in combined_df_raw.columns:
            combined_df_raw['FechaHora'] = combined_df_raw['Fecha']

        sort_col_name = 'FechaHora' if 'FechaHora' in combined_df_raw.columns else 'Fecha'
        if sort_col_name in combined_df_raw.columns:
            combined_df_raw = combined_df_raw.sort_values(by=sort_col_name, ascending=True, na_position='first')

    except Exception as e_concat:
        errors.append(f"Error al combinar archivos CSV (desde rutas) o parsear fechas: {e_concat}")
        return None, None, errors

    df_for_portfolio_calc = combined_df_raw.copy()
    processed_df_for_csv = pd.DataFrame()

    try:
        cols_to_rename_present = [col for col in COLS_MAP.keys() if col in combined_df_raw.columns]
        if not cols_to_rename_present:
            errors.append("Error (rutas): Ninguna de las columnas esperadas (COLS_MAP) se encontró en los archivos CSV.")
            return None, df_for_portfolio_calc, errors

        filtered_df = combined_df_raw[cols_to_rename_present].copy()
        renamed = filtered_df.rename(columns=COLS_MAP)
        print(f"Columnas renombradas para CSV (desde rutas): {renamed.columns.tolist()}")

        if 'Bolsa' in renamed.columns:
            renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna('')
            print("Columna 'Exchange Yahoo' (desde rutas) añadida.")
        else:
            renamed['Exchange Yahoo'] = ''
            errors.append("Advertencia (rutas): No se encontró la columna 'Bolsa' para generar 'Exchange Yahoo'.")

        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    cleaned_series = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False)
                    renamed[col] = pd.to_numeric(cleaned_series, errors='coerce')

                # ---- INICIO DEL CAMBIO ----
                # Reemplazar NaN con 0 después de la coerción
                if pd.api.types.is_numeric_dtype(renamed[col]) or renamed[col].isnull().any():
                    renamed[col] = renamed[col].fillna(0)
                # ---- FIN DEL CAMBIO ----
                
                if col == 'Cantidad':
                     if pd.api.types.is_numeric_dtype(renamed[col]): # Verificar de nuevo
                         renamed[col] = renamed[col].abs()

                if pd.api.types.is_numeric_dtype(renamed[col]): # Asegurar tipo float
                    renamed[col] = renamed[col].astype(float)
            else:
                errors.append(f"Advertencia: Columna numérica '{col}' no encontrada tras renombrar (rutas).")
                renamed[col] = 0.0 # Añadir columna con ceros

        processed_df_for_csv = renamed

    except KeyError as e_key:
        errors.append(f"Error de procesamiento (KeyError rutas): Columna '{e_key}' no encontrada. Verifica COLS_MAP y tus CSVs.")
        return None, df_for_portfolio_calc, errors
    except Exception as e_proc:
        errors.append(f"Error general durante el procesamiento de datos para CSV (rutas): {e_proc}")
        return None, df_for_portfolio_calc, errors
        
    print(f"Procesamiento base (desde rutas) completado. DF para CSV ({len(processed_df_for_csv)} filas), DF raw para portfolio ({len(df_for_portfolio_calc)} filas).")
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


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated and hasattr(current_user, 'must_change_password') and not current_user.must_change_password:
        # Usuario ya autenticado y sin necesidad de cambiar contraseña, redirigir según rol
        if current_user.is_admin:  # Asumiendo que el usuario 'admin' tiene is_admin = True
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('financial_summary'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.is_active:
            # Manejo especial para el primer inicio de sesión del admin con contraseña por defecto
            if user.username == 'admin' and user.check_password('admin') and user.must_change_password:
                login_user(user, remember=form.remember_me.data)
                # Actualizar datos de login (copiado de tu lógica original)
                if user.current_login_at: user.last_login_at = user.current_login_at
                user.current_login_at = datetime.utcnow()
                user.login_count = (user.login_count or 0) + 1
                # El commit se hará después del cambio de contraseña o en un login normal
                flash('Bienvenido administrador. Por seguridad, por favor cambia tu contraseña por defecto "admin".', 'info')
                return redirect(url_for('change_password'))
            
            elif user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                # Actualizar datos de login (copiado de tu lógica original)
                if user.current_login_at: user.last_login_at = user.current_login_at
                user.current_login_at = datetime.utcnow()
                user.login_count = (user.login_count or 0) + 1
                db.session.commit() # Guardar datos de login

                if hasattr(user, 'must_change_password') and user.must_change_password:
                    # Para cualquier usuario que deba cambiar contraseña (ej. admin después de reseteo por otro admin)
                    return redirect(url_for('change_password'))
                
                next_page = request.args.get('next')
                if next_page and not next_page.startswith(('/login', '/register', '/change_password')):
                    return redirect(next_page)
                
                # --- LÓGICA DE REDIRECCIÓN PRINCIPAL MODIFICADA ---
                if user.is_admin:  # Verificar si el usuario es administrador
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('financial_summary'))
            else:
                flash('Inicio de sesión fallido. Verifica usuario y contraseña.', 'danger')
        elif user and not user.is_active:
            flash('Esta cuenta ha sido desactivada.', 'warning')
        else:
            flash('Inicio de sesión fallido. Usuario no encontrado.', 'danger')
            
    return render_template('login.html', title='Iniciar Sesión', form=form)


# ... (tus importaciones y otras definiciones de app.py) ...
# Recuerda tener definidas tus funciones auxiliares como:
# process_uploaded_csvs, process_csvs_from_paths, calculate_portfolio,
# load_mapping, save_mapping, save_user_portfolio, etc.
# y tus modelos User, WatchlistItem, UserPortfolio.
# y variables globales como OUTPUT_FOLDER, FINAL_COLS_ORDERED, BOLSA_TO_YAHOO_MAP.

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    # Para solicitudes GET de usuarios autenticados, redirigir según el rol.
    if request.method == 'GET':
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('financial_summary'))

    # Para solicitudes POST, se maneja la lógica de subida de archivos.
    if request.method == 'POST':
        input_method = request.form.get('input_method')
        processed_data = None
        errors_pre_process = []

        if input_method == 'upload':
            print("Procesando método: upload")
            if 'csv_files[]' not in request.files:
                flash('Error: No se encontró la parte del archivo en la solicitud.', 'danger')
                return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario
            
            files = request.files.getlist('csv_files[]')
            if not files or all(f.filename == '' for f in files):
                flash('Error: No se seleccionaron archivos.', 'danger')
                return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario
            
            processed_data = process_uploaded_csvs(files) 
            
        elif input_method == 'path':
            print("Procesando método: path")
            server_path_input = request.form.get('server_path', '').strip()
            if not server_path_input:
                flash('Error: No se especificó la ruta del servidor.', 'danger')
                return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario

            try:
                if not os.path.isdir(server_path_input):
                    errors_pre_process.append(f"Error: La ruta '{server_path_input}' no es un directorio válido.")
                else:
                    csv_pattern = re.compile(r"^\d{4}\.csv$")
                    paths_to_process = []
                    for entry in os.listdir(server_path_input):
                        if csv_pattern.match(entry) and os.path.isfile(os.path.join(server_path_input, entry)):
                            paths_to_process.append(os.path.join(server_path_input, entry))
                    
                    if not paths_to_process:
                        errors_pre_process.append(f"Advertencia: No se encontraron archivos AAAA.csv en '{server_path_input}'.")
                    else:
                        print(f"Archivos encontrados en ruta: {paths_to_process}")
                        processed_data = process_csvs_from_paths(paths_to_process)
            except Exception as e_path:
                errors_pre_process.append(f"Error al acceder o listar la ruta del servidor '{server_path_input}': {e_path}")
        else:
            flash('Error: Método de entrada no válido.', 'danger')
            return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario

        if errors_pre_process:
            for msg in errors_pre_process:
                flash(msg, 'danger' if 'Error:' in msg else 'warning')
            if any("Error:" in e for e in errors_pre_process) or processed_data is None:
                return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario

        try:
            processed_df_for_csv, combined_df_raw, errors_process = processed_data
        except (TypeError, ValueError) as e_unpack:
            print(f"ERROR FATAL: No se pudo desempaquetar processed_data. Error: {e_unpack}")
            flash("Error interno inesperado (Ref: UNPACK_FAIL). Por favor, revisa los logs del servidor.", "danger")
            session.clear()
            return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario

        if errors_process:
            for msg in errors_process:
                flash(msg, 'danger' if "Error:" in msg else ('warning' if "Advertencia:" in msg else 'info'))

        if combined_df_raw is None or combined_df_raw.empty:
            flash('No se pudieron procesar los datos base necesarios de los archivos CSV. Verifica el formato y contenido de los archivos.', 'warning')
            return redirect(url_for('upload_page_form')) # MODIFICADO: Redirigir al formulario

        portfolio_df = calculate_portfolio(combined_df_raw)

        if portfolio_df is not None and not portfolio_df.empty:
            print(f"Sincronizando portfolio ({len(portfolio_df)} items) con watchlist DB para usuario {current_user.id}...")
            mapping_data_sync = load_mapping()
            try:
                current_db_watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
                db_isin_map = {item.isin: item for item in current_db_watchlist if item.isin}
                new_portfolio_isins = set(portfolio_df['ISIN'].dropna().unique())
                items_to_commit_or_add = []

                for item_db in current_db_watchlist:
                    isin = item_db.isin
                    is_now_in_portfolio = isin in new_portfolio_isins
                    needs_update = False
                    if is_now_in_portfolio:
                        if not item_db.is_in_portfolio:
                            item_db.is_in_portfolio = True
                            if hasattr(item_db, 'is_in_followup'): item_db.is_in_followup = False
                            elif hasattr(item_db, 'is_manual'): item_db.is_manual = False
                            needs_update = True
                        new_portfolio_isins.discard(isin) 
                    else: 
                        if item_db.is_in_portfolio:
                            item_db.is_in_portfolio = False
                            if hasattr(item_db, 'is_in_followup'): item_db.is_in_followup = True
                            elif hasattr(item_db, 'is_manual'): item_db.is_manual = True
                            needs_update = True
                    if needs_update: items_to_commit_or_add.append(item_db)

                for isin_to_add in new_portfolio_isins:
                    portfolio_row = portfolio_df[portfolio_df['ISIN'] == isin_to_add].iloc[0]
                    map_info = mapping_data_sync.get(isin_to_add, {})
                    ticker = map_info.get('ticker', 'N/A')
                    google_ex = map_info.get('google_ex', None)
                    name = map_info.get('name', portfolio_row.get('Producto', 'Desconocido')).strip()
                    if not name: name = portfolio_row.get('Producto', 'Desconocido')
                    degiro_bolsa_code = portfolio_row.get('Bolsa de')
                    yahoo_suffix = BOLSA_TO_YAHOO_MAP.get(degiro_bolsa_code, '') if degiro_bolsa_code else ''
                    new_watch_item_data = {
                        'item_name': name, 'isin': isin_to_add, 'ticker': ticker,
                        'yahoo_suffix': yahoo_suffix, 'google_ex': google_ex,
                        'user_id': current_user.id, 'is_in_portfolio': True
                    }
                    if hasattr(WatchlistItem, 'is_in_followup'): new_watch_item_data['is_in_followup'] = False
                    elif hasattr(WatchlistItem, 'is_manual'): new_watch_item_data['is_manual'] = False
                    new_watch_item = WatchlistItem(**new_watch_item_data)
                    items_to_commit_or_add.append(new_watch_item)
                
                if items_to_commit_or_add:
                     db.session.add_all(items_to_commit_or_add)
                     db.session.commit()
                     print("Sincronización watchlist DB completada.")
            except Exception as e_sync: 
                db.session.rollback(); traceback.print_exc()
                flash("Error Interno al actualizar la watchlist. Revisa logs.", "danger")
        else:
            print("Portfolio vacío, no se sincroniza watchlist.")
        
        mapping_data = load_mapping()
        missing_isins_details = []
        if portfolio_df is not None and not portfolio_df.empty:
             all_isins_in_portfolio = portfolio_df['ISIN'].unique()
             for isin in all_isins_in_portfolio:
                map_entry = mapping_data.get(isin)
                if not map_entry or not map_entry.get('ticker') or not map_entry.get('google_ex'):
                     p_row = portfolio_df[portfolio_df['ISIN'] == isin].iloc[0]
                     missing_isins_details.append({'isin': isin, 'name': p_row.get('Producto', 'Desconocido'), 'bolsa_de': p_row.get('Bolsa de', None)})
        
        if missing_isins_details:
            session['missing_isins_for_mapping'] = missing_isins_details
            if processed_df_for_csv is not None and not processed_df_for_csv.empty:
                uid_csv = uuid.uuid4(); temp_csv_fn = f"pending_csv_{uid_csv}.json"
                try:
                    processed_df_for_csv.to_json(os.path.join(OUTPUT_FOLDER, temp_csv_fn), orient='records', lines=True)
                    session['temp_csv_pending_filename'] = temp_csv_fn
                except Exception as e: print(f"Error guardando DF CSV pendiente: {e}")
            if portfolio_df is not None and not portfolio_df.empty:
                uid_port = uuid.uuid4(); temp_port_fn = f"pending_portfolio_{uid_port}.json"
                try:
                    portfolio_df.to_json(os.path.join(OUTPUT_FOLDER, temp_port_fn), orient='records', lines=True)
                    session['temp_portfolio_pending_filename'] = temp_port_fn
                except Exception as e: print(f"Error guardando DF Portfolio pendiente: {e}")
            return redirect(url_for('complete_mapping'))
        else:
            final_csv_filename_to_save_in_db = None
            csv_data_list_for_db = None
            if processed_df_for_csv is not None and not processed_df_for_csv.empty:
                try:
                    processed_df_for_csv['Ticker'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('ticker', ''))
                    processed_df_for_csv['Exchange Google'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('google_ex', ''))
                    cols_final_ordered = [c for c in FINAL_COLS_ORDERED if c in processed_df_for_csv.columns] # FINAL_COLS_ORDERED debe estar definido
                    # ... (lógica para añadir Ticker y Exchange Google a cols_final_ordered si no están) ...
                    processed_df_for_csv = processed_df_for_csv.reindex(columns=cols_final_ordered, fill_value='')
                    uid_final = uuid.uuid4(); final_temp_csv_filename_for_session = f"processed_{uid_final}.csv"
                    path_final = os.path.join(OUTPUT_FOLDER, final_temp_csv_filename_for_session) # OUTPUT_FOLDER debe estar definido
                    processed_df_for_csv.to_csv(path_final, index=False, sep=';', decimal='.', encoding='utf-8-sig')
                    session['csv_temp_file'] = final_temp_csv_filename_for_session
                    final_csv_filename_to_save_in_db = final_temp_csv_filename_for_session
                    csv_data_list_for_db = processed_df_for_csv.to_dict('records')
                except Exception as e_final_csv:
                    flash(f"Error al generar CSV final: {e_final_csv}", "danger"); session.pop('csv_temp_file', None)
            else:
                session.pop('csv_temp_file', None)
        
            if portfolio_df is not None and not portfolio_df.empty:
                portfolio_list_for_session_and_db = portfolio_df.to_dict('records')
                session['portfolio_data'] = portfolio_list_for_session_and_db
                save_success = save_user_portfolio(
                    user_id=current_user.id,
                    portfolio_data=portfolio_list_for_session_and_db,
                    csv_data=csv_data_list_for_db,
                    csv_filename=final_csv_filename_to_save_in_db
                ) # Tu función save_user_portfolio
                if save_success: flash('Archivos procesados y portfolio listo.', 'success')
                else: flash('Error al guardar datos del portfolio en BD.', 'warning')
            else:
                session.pop('portfolio_data', None)
                if csv_data_list_for_db:
                     save_user_portfolio(user_id=current_user.id, portfolio_data=None, csv_data=csv_data_list_for_db, csv_filename=final_csv_filename_to_save_in_db)
                flash('Archivos procesados. Portfolio vacío.', 'info')
            return redirect(url_for('show_portfolio'))

    return redirect(url_for('login')) # Fallback improbable

@app.route('/upload_page', methods=['GET'])
@login_required
def upload_page_form():
    """
    Esta ruta se dedica a mostrar la página con el formulario para cargar CSVs.
    El formulario en sí (en index.html) enviará los datos (POST) a la ruta '/' (index).
    """
    return render_template('index.html', title="Cargar CSVs Anuales")


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
    Añade un botón para ir a la página de carga de CSVs.
    """
    print(f"Iniciando show_portfolio para usuario: {current_user.id}")
    
    portfolio_data_list = None
    temp_filename = None
    csv_existe = False
    last_updated = None
    enriched_portfolio_data = []
    total_market_value_eur = 0.0
    total_cost_basis_eur_est = 0.0
    total_pl_eur_est = 0.0

    if 'portfolio_data' in session:
        portfolio_data_list = session.get('portfolio_data')
        temp_filename = session.get('csv_temp_file')
        csv_existe = bool(temp_filename)
        print(f"Datos encontrados en sesión: {len(portfolio_data_list) if portfolio_data_list else 0} items")

    if not portfolio_data_list:
        print(f"Cargando datos de la base de datos para usuario: {current_user.id}")
        try:
            portfolio_record = UserPortfolio.query.filter_by(user_id=current_user.id).first()
            if portfolio_record:
                if portfolio_record.portfolio_data:
                    try:
                        portfolio_data_list = json.loads(portfolio_record.portfolio_data)
                        print(f"Datos cargados de BD: {len(portfolio_data_list) if portfolio_data_list else 0} items")
                        
                        if not isinstance(portfolio_data_list, list):
                            portfolio_data_list = []
                        
                        session['portfolio_data'] = portfolio_data_list
                        
                        if portfolio_record.csv_filename:
                            temp_filename = portfolio_record.csv_filename
                            session['csv_temp_file'] = temp_filename
                            csv_existe = True
                        
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

    if portfolio_data_list:
        print(f"Procesando {len(portfolio_data_list)} items del portfolio")
        # mapping_data = load_mapping() # No es necesario aquí si solo mostramos
        
        for item in portfolio_data_list:
            try:
                new_item = item.copy() if isinstance(item, dict) else dict(item)
                
                if 'market_value_eur' in new_item and new_item.get('market_value_eur') is not None:
                    try: total_market_value_eur += float(new_item['market_value_eur'])
                    except (ValueError, TypeError): pass
                
                if 'cost_basis_eur_est' in new_item and new_item.get('cost_basis_eur_est') is not None:
                    try: total_cost_basis_eur_est += float(new_item['cost_basis_eur_est'])
                    except (ValueError, TypeError): pass
                
                if 'pl_eur_est' in new_item and new_item.get('pl_eur_est') is not None:
                    try: total_pl_eur_est += float(new_item['pl_eur_est'])
                    except (ValueError, TypeError): pass
                
                enriched_portfolio_data.append(new_item)
            except Exception as e:
                print(f"Error procesando item del portfolio: {e}")
                continue
            
        print(f"Portfolio procesado: {len(enriched_portfolio_data)} items válidos")
    else:
        print("No hay datos de portfolio para mostrar")
        enriched_portfolio_data = []

    return render_template(
        'portfolio.html', # Asumo que tienes un portfolio.html
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
# Formulario para añadir historial de salarios
class SalaryHistoryForm(FlaskForm):
    year = StringField('Año', validators=[DataRequired()], 
                      render_kw={"placeholder": "Ej: 2023", "type": "number", "min": "1900", "max": "2100"})
    annual_net_salary = StringField('Salario Neto Anual (€)', validators=[DataRequired()], 
                                  render_kw={"placeholder": "Ej: 35000"})
    submit = SubmitField('Añadir Salario Histórico')


# Modelos para la gestión de cuentas bancarias


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
if __name__ == '__main__': # MOSTRANDO COMPLETA CON CAMBIOS
    # Define el email placeholder para el admin en la config para fácil acceso
    app.config['ADMIN_PLACEHOLDER_EMAIL'] = 'admin@no-reply.internal'


    with app.app_context():
        print("Verificando/Creando tablas de la base de datos...")
        db.create_all()
        print("Tablas verificadas/creadas.")

        admin_user = User.query.filter_by(username='admin').first()
        admin_email_placeholder = app.config['ADMIN_PLACEHOLDER_EMAIL']

        if not admin_user:
            print(f"Creando usuario administrador por defecto ('admin') con email placeholder: {admin_email_placeholder}...")
            admin_password_hash = generate_password_hash("admin")
            admin = User(username='admin',
                         email=admin_email_placeholder,  # <--- CAMBIO: Admin con email placeholder
                         password_hash=admin_password_hash,
                         is_admin=True,
                         must_change_password=True,
                         is_active=True)
            db.session.add(admin)
            try:
                db.session.commit()
                print(f"Usuario 'admin' creado con email '{admin_email_placeholder}' y contraseña 'admin'. Deberá cambiarla en el primer inicio de sesión.")
            except Exception as e:
                db.session.rollback()
                print(f"Error al crear el usuario admin: {e}")
                app.logger.error(f"Error al crear el usuario admin: {e}", exc_info=True)

        elif admin_user.is_admin: # Si el usuario admin ya existe
            # Asegurar que el admin tenga el email placeholder si no tiene uno válido o tiene uno antiguo
            if not admin_user.email or admin_user.email != admin_email_placeholder:
                print(f"Actualizando email del usuario admin a placeholder: {admin_email_placeholder}")
                admin_user.email = admin_email_placeholder

            if not admin_user.is_active:
                admin_user.is_active = True
            if admin_user.check_password('admin'):
               admin_user.must_change_password = True

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al asegurar estado del admin: {e}", exc_info=True)

    # ... (app.run) ...
    app.run(debug=True, host='0.0.0.0', port=5000)
