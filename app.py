# -*- coding: utf-8 -*-
import os
import pandas as pd
import io
import csv
import hashlib
import math
from calendar import monthrange
import re
from sqlalchemy import func
import traceback
from typing import Union 
import uuid
import json
from functools import wraps
import time
from datetime import date, timedelta, datetime # Asegúrate que datetime está importado
import glob
import requests # Para tipos de cambio
import yfinance as yf # Para precios acciones
from flask import (
    Flask, request, render_template, send_file, flash, redirect, url_for, session, get_flashed_messages, jsonify, Response
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
from flask_apscheduler import APScheduler
from apscheduler.schedulers.background import BackgroundScheduler
import atexit


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

# Mapeo de códigos de Mercado IBKR a sufijos de Yahoo Finance
IBKR_MARKET_TO_YAHOO_MAP = {
    'NASDAQ': '',      # NASDAQ (US) - sin sufijo
    'NYSE': '',        # NYSE (US) - sin sufijo  
    'SEHK': '.HK',     # Hong Kong Stock Exchange
    'TSE': '.TO',      # Toronto Stock Exchange
    'LSE': '.L',       # London Stock Exchange
    'SGX': '.SI',      # Singapore Exchange
    'OMXNO': '.OL',    # Oslo Stock Exchange
    'GETTEX2': '.DE',  # German Exchange
    'BATS': '',        # BATS (US) - sin sufijo
    'ARCA': '',        # NYSE Arca (US) - sin sufijo
    'ISLAND': '',      # ISLAND (US) - sin sufijo
    'IBIS2': '.DE',    # German Exchange (IBIS)
    'LSEIOB1': '.L',   # London Stock Exchange IOB
    'DRCTEDGE': '',    # Direct Edge (US) - sin sufijo
    'IBKR': '',        # IBKR internal - sin sufijo
    'IBKRATS': '',     # IBKR ATS - sin sufijo
    'TSXDARK': '.TO',  # TSX Dark Pool
    'TRIACT': '.TO',   # TriAct Canada
    'ALPHA': '.TO',    # Alpha Exchange
    'CAIBFRSH': '.TO', # Canadian exchange
    'IDEALFX': '',     # IBKR FX - no aplicable para acciones
}

# Mapeo de códigos de Mercado IBKR a códigos de Google Exchange  
IBKR_MARKET_TO_GOOGLE_MAP = {
    'NASDAQ': 'NASDAQ',
    'NYSE': 'NYSE', 
    'SEHK': 'HKG',
    'TSE': 'TSE',
    'LSE': 'LON',
    'SGX': 'SGX',
    'OMXNO': 'OSL',
    'GETTEX2': 'FRA',
    'BATS': 'BATS',
    'ARCA': 'ARCA',
    'ISLAND': 'NASDAQ',  # Island es parte de NASDAQ
    'IBIS2': 'FRA',
    'LSEIOB1': 'LON',
    'DRCTEDGE': 'NYSE',  # Direct Edge parte de NYSE
    'IBKR': 'NASDAQ',    # Default para IBKR interno
    'IBKRATS': 'NASDAQ', # Default para IBKR ATS
    'TSXDARK': 'TSE',
    'TRIACT': 'TSE',
    'ALPHA': 'TSE',
    'CAIBFRSH': 'TSE',
}

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
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

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
app.config['SERVER_NAME'] = '127.0.0.1:5000'
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



# Categorización automática inicial
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

DEPOSIT_TRANSACTION_KINDS = [
    'viban_purchase'  # Solo este tipo puede generar depósitos adicionales
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



# ===== TAREAS PREDEFINIDAS PARA INICIALIZAR =====
DEFAULT_SCHEDULER_TASKS = [
    {
        'task_key': 'all_tasks',
        'task_name': 'Procesamiento Completo (Todo en Uno)',
        'task_function': 'process_daily_alerts_global',
        'description': 'Ejecuta actualización de precios, generación de alertas y envío de correos secuencialmente',
        'frequency_type': 'days',
        'frequency_value': 1,
        'start_hour': 0,
        'start_minute': 0,
        'is_active': True
    },
    {
        'task_key': 'update_prices',
        'task_name': 'Actualización Global de Precios',
        'task_function': 'update_all_prices_global',
        'description': 'Actualiza precios de acciones, criptomonedas y metales preciosos para todos los usuarios',
        'frequency_type': 'days',
        'frequency_value': 1,
        'start_hour': 0,
        'start_minute': 5,
        'is_active': False  # Inactiva por defecto si está activa la tarea completa
    },
    {
        'task_key': 'check_alerts', 
        'task_name': 'Comprobación de Alertas',
        'task_function': 'generate_alert_messages_global',
        'description': 'Verifica y genera mensajes de alertas según configuraciones activas',
        'frequency_type': 'minutes',
        'frequency_value': 5,
        'start_hour': 0,
        'start_minute': 0,
        'is_active': False
    },
    {
        'task_key': 'send_emails',
        'task_name': 'Envío de Correos',
        'task_function': 'send_email_notifications_global', 
        'description': 'Envía correos electrónicos para alertas pendientes',
        'frequency_type': 'minutes',
        'frequency_value': 1,
        'start_hour': 0,
        'start_minute': 0,
        'is_active': False
    }
]



class SchedulerTask(db.Model):
    """Configuración de tareas programadas del sistema."""
    __tablename__ = 'scheduler_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    task_key = db.Column(db.String(50), unique=True, nullable=False)  # 'update_prices', 'check_alerts', etc.
    task_name = db.Column(db.String(100), nullable=False)  # Nombre para mostrar
    task_function = db.Column(db.String(100), nullable=False)  # Nombre de la función
    description = db.Column(db.Text)  # Descripción
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Configuración de frecuencia
    frequency_type = db.Column(db.String(20), nullable=False)  # 'minutes', 'hours', 'days', 'weeks'
    frequency_value = db.Column(db.Integer, nullable=False)    # Cada X unidades
    start_hour = db.Column(db.Integer, default=0, nullable=False)     # Hora de inicio (0-23)
    start_minute = db.Column(db.Integer, default=0, nullable=False)   # Minuto de inicio (0-59)
    
    # Metadatos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_executed = db.Column(db.DateTime)  # Última ejecución registrada
    execution_count = db.Column(db.Integer, default=0)  # Contador de ejecuciones
    
    def __repr__(self):
        return f'<SchedulerTask {self.task_key}: {self.task_name}>'
    
    @property
    def next_run_time(self):
        """Calcula la próxima ejecución basada en la configuración."""
        if not self.is_active:
            return None
            
        # Buscar el job activo en el scheduler
        try:
            job = scheduler.get_job(f'task_{self.task_key}')
            return job.next_run_time if job else None
        except:
            return None
    
    @property
    def frequency_display(self):
        """Texto legible de la frecuencia."""
        if self.frequency_value == 1:
            unit_map = {
                'minutes': 'minuto',
                'hours': 'hora', 
                'days': 'día',
                'weeks': 'semana'
            }
            return f"Cada {unit_map.get(self.frequency_type, self.frequency_type)}"
        else:
            unit_map = {
                'minutes': 'minutos',
                'hours': 'horas',
                'days': 'días', 
                'weeks': 'semanas'
            }
            return f"Cada {self.frequency_value} {unit_map.get(self.frequency_type, self.frequency_type)}"

# Configurar APScheduler
class SchedulerConfig:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Europe/Madrid'

app.config.from_object(SchedulerConfig())

# Inicializar el scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

print(f"DEBUG: APScheduler inicializado - Jobs: {scheduler.get_jobs()}")

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

    # Configuración de Alertas y Correo
    alert_configurations = db.relationship('AlertConfiguration', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    mailbox_messages = db.relationship('MailboxMessage', backref='user', lazy='dynamic', cascade="all, delete-orphan")

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

class HistoricalCryptoPrice(db.Model):
    __tablename__ = 'historical_crypto_price'
    id = db.Column(db.Integer, primary_key=True)
    # Esta es la línea crucial:
    crypto_symbol_yf = db.Column(db.String(20), nullable=False) # Debe llamarse exactamente 'crypto_symbol_yf'
    date = db.Column(db.Date, nullable=False)
    price_eur = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), default='yfinance')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('crypto_symbol_yf', 'date', name='uq_crypto_date_price'),)

    def __repr__(self):
        # Asegúrate que aquí también usas self.crypto_symbol_yf
        return f'<HistoricalCryptoPrice {self.crypto_symbol_yf} {self.date} {self.price_eur}€>'

class HistoricalMetalPrice(db.Model):
    __tablename__ = 'historical_metal_price'
    id = db.Column(db.Integer, primary_key=True)
    # Asumiendo que tienes una tabla PreciousMetal con los símbolos, o usas directamente el símbolo de yfinance
    metal_symbol = db.Column(db.String(20), nullable=False) # Ej: "GC=F" para Oro, "SI=F" para Plata
    date = db.Column(db.Date, nullable=False)
    price_eur = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(50), default='yfinance') # Para saber de dónde vino el dato
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('metal_symbol', 'date', name='uq_metal_date'),)

    def __repr__(self):
        return f'<HistoricalMetalPrice {self.metal_symbol} {self.date} {self.price_eur}>'

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


class BrokerOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    operation_type = db.Column(db.String(20), nullable=False)
    concept = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    linked_product_name = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # YA NO NECESITAS: user = db.relationship('User', backref=db.backref('broker_operations', lazy='dynamic'))
    # La relación se establece desde el modelo User

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


class Goal(db.Model):
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    goal_name = db.Column(db.String(200), nullable=False)
    goal_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    
    # Campos para diferentes tipos de objetivos
    goal_asset_type = db.Column(db.String(50))
    target_amount = db.Column(db.Float)
    target_timeframe_months = db.Column(db.Integer)
    monthly_savings_target = db.Column(db.Float)
    debt_ceiling_percentage = db.Column(db.Float)  # IMPORTANTE: Este campo debe existir
    asset_distribution = db.Column(db.Text)  # JSON para distribución de activos
    
    # Campos para predicción automática
    prediction_type = db.Column(db.String(50))
    
    # Metadatos
    start_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
     

# 2. MODELO GoalProgress para historial (agregar en app.py)
class GoalProgress(db.Model):
    """Historial de progreso de objetivos."""
    
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, nullable=False)
    
    # Datos del progreso
    calculation_date = db.Column(db.Date, nullable=False, index=True)
    current_value = db.Column(db.Float, nullable=False)
    target_value = db.Column(db.Float, nullable=False)
    progress_percentage = db.Column(db.Float, nullable=False)
    
    # Predicciones (para objetivos automáticos)
    estimated_completion_date = db.Column(db.Date, nullable=True)
    estimated_final_amount = db.Column(db.Float, nullable=True)
    monthly_growth_rate = db.Column(db.Float, nullable=True)
    
    # Metadatos
    is_on_track = db.Column(db.Boolean, nullable=False, default=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<GoalProgress {self.goal_id}: {self.progress_percentage}% on {self.calculation_date}>'


class PensionHistoryForm(FlaskForm):
    month_year = StringField('Mes y Año', validators=[DataRequired()],
                          render_kw={"type": "month", "placeholder": "YYYY-MM"})
    submit = SubmitField('Guardar Estado Actual')

class EmailQueue(db.Model):
    """Cola de correos electrónicos pendientes de envío."""
    __tablename__ = 'email_queue'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Referencia al mensaje original
    mailbox_message_id = db.Column(db.Integer, db.ForeignKey('mailbox_message.id', ondelete='CASCADE'), nullable=False)
    alert_config_id = db.Column(db.Integer, db.ForeignKey('alert_configuration.id', ondelete='SET NULL'), nullable=True)
    
    # Datos del email
    recipient_email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    # Estado de la cola
    status = db.Column(db.String(20), default='pending', nullable=False)  # 'pending', 'sent', 'failed', 'cancelled'
    priority = db.Column(db.Integer, default=5, nullable=False)  # 1=alta, 5=normal, 10=baja
    
    # Control de envío
    attempts = db.Column(db.Integer, default=0, nullable=False)
    max_attempts = db.Column(db.Integer, default=3, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    scheduled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Cuándo enviar
    sent_at = db.Column(db.DateTime, nullable=True)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    
    # Logs de error
    error_message = db.Column(db.Text, nullable=True)
    
    # Relaciones
    mailbox_message = db.relationship('MailboxMessage', backref='email_queue_entries')
    alert_config = db.relationship('AlertConfiguration', backref='email_queue_entries')
    
    def __repr__(self):
        return f'<EmailQueue {self.id} to {self.recipient_email} status:{self.status}>'
    
    @property
    def can_retry(self):
        """Determina si se puede reintentar el envío."""
        return self.status == 'failed' and self.attempts < self.max_attempts
    
    @property
    def is_ready_to_send(self):
        """Determina si está listo para enviar."""
        return (self.status == 'pending' and 
                self.scheduled_at <= datetime.utcnow() and 
                self.attempts < self.max_attempts)

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

class SystemLog(db.Model):
    """Registro de actividades del sistema."""
    __tablename__ = 'system_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    log_type = db.Column(db.String(50), nullable=False)  # 'daily_alerts', 'price_update', etc.
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='success')  # 'success', 'error', 'partial'
    details = db.Column(db.Text)
    
    def __repr__(self):
        return f'<SystemLog {self.log_type} at {self.executed_at}>'

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

class GoalHistory(db.Model):
    """Historial de progreso de objetivos."""
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    alert_configuration_id = db.Column(db.Integer, nullable=False)
    
    # Datos del progreso
    calculation_date = db.Column(db.Date, nullable=False, index=True)
    current_value = db.Column(db.Float, nullable=False)  # Valor actual del activo/patrimonio
    target_value = db.Column(db.Float, nullable=False)  # Valor objetivo
    progress_percentage = db.Column(db.Float, nullable=False)  # Progreso en %
    
    # Para objetivos de ahorro mensual
    monthly_target = db.Column(db.Float, nullable=True)  # Objetivo mensual
    monthly_actual = db.Column(db.Float, nullable=True)  # Valor real del mes
    cumulative_target = db.Column(db.Float, nullable=True)  # Objetivo acumulado
    cumulative_actual = db.Column(db.Float, nullable=True)  # Valor acumulado real
    
    # Metadatos
    is_on_track = db.Column(db.Boolean, nullable=False, default=True)  # Si va por buen camino
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    #alert_config = db.relationship('AlertConfiguration', backref='goal_history_records')
    
    def __repr__(self):
        return f'<GoalHistory {self.id} User:{self.user_id} Progress:{self.progress_percentage}%>'

# 3. FORMULARIO GoalConfigurationForm MEJORADO (reemplazar en app.py)
class GoalConfigurationForm(FlaskForm):
    """Formulario simplificado para configurar objetivos financieros."""
    
    # Tipo de objetivo
    goal_type = SelectField('Tipo de Objetivo',
                           choices=[
                               ('portfolio_percentage', 'Distribución de Activos'),
                               ('target_amount', 'Cantidad Objetivo Fija'),
                               ('auto_prediction', 'Predicción Automática'),
                               ('savings_monthly', 'Ahorro Mensual'),
                               ('debt_threshold', 'Techo de Deuda')
                           ],
                           validators=[DataRequired()])
    
    # Campos para distribución de activos
    percentage_bolsa = FloatField('% Bolsa', validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    percentage_cash = FloatField('% Cash', validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    percentage_crypto = FloatField('% Criptomonedas', validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    percentage_real_estate = FloatField('% Inmuebles', validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    percentage_metales = FloatField('% Metales', validators=[Optional(), NumberRange(min=0, max=100)], default=0)
    
    # Campos para objetivos de cantidad/predicción
    goal_asset_type = SelectField('Tipo de Activo',
                                 choices=[
                                     ('bolsa', 'Bolsa (Trading + Dividendos)'),
                                     ('cash', 'Cash (Cuentas Bancarias)'),
                                     ('crypto', 'Criptomonedas'),
                                     ('real_estate', 'Inmuebles'),
                                     ('metales', 'Metales Preciosos'),
                                     ('total_patrimonio', 'Patrimonio Total')
                                 ],
                                 validators=[Optional()])
    
    # Solo dos tipos de predicción
    prediction_type = SelectField('Tipo de Predicción',
                                 choices=[
                                     ('amount_to_time', 'Dime la cantidad → Te digo el tiempo'),
                                     ('time_to_amount', 'Dime el tiempo → Te digo la cantidad')
                                 ],
                                 validators=[Optional()])
    
    target_amount = FloatField('Cantidad Objetivo (€)', validators=[Optional(), NumberRange(min=0.01)])
    target_timeframe_months = IntegerField('Plazo (meses)', validators=[Optional(), NumberRange(min=1, max=600)])
    
    # Campos para ahorro mensual
    monthly_savings_target = FloatField('Objetivo de Ahorro Mensual (€)', validators=[Optional(), NumberRange(min=0.01)])
    
    # Campos para techo de deuda
    debt_ceiling_percentage = FloatField('Techo de Deuda (%)', validators=[Optional(), NumberRange(min=0, max=100)])
    
    # Configuración
    start_date = DateField('Fecha de Inicio', validators=[Optional()])
    
    # Configuración de alerta (opcional) - SIN alert_day_of_month
    create_alert = BooleanField('Crear alerta automática para este objetivo', default=False)
    notify_by_email = BooleanField('Recibir alertas por email', default=False)
    
    submit = SubmitField('Crear Objetivo')
    
    def validate(self, **kwargs):
        """Validación personalizada ESPECÍFICA para GoalConfigurationForm."""
        if not super().validate():
            return False
        
        print(f"DEBUG: Validando goal_type: {self.goal_type.data}")
        
        if self.goal_type.data == 'portfolio_percentage':
            # Validar distribución de activos
            percentages = [
                self.percentage_bolsa.data or 0,
                self.percentage_cash.data or 0,
                self.percentage_crypto.data or 0,
                self.percentage_real_estate.data or 0,
                self.percentage_metales.data or 0
            ]
            
            total_percentage = sum(percentages)
            if total_percentage == 0:
                self.percentage_bolsa.errors.append('Debe definir al menos un porcentaje.')
                return False
            
            if total_percentage > 100:
                self.percentage_bolsa.errors.append(f'La suma ({total_percentage}%) no puede exceder 100%.')
                return False
        
        elif self.goal_type.data in ['target_amount', 'auto_prediction']:
            if not self.goal_asset_type.data:
                self.goal_asset_type.errors.append('Debe seleccionar el tipo de activo.')
                return False
            
            if self.goal_type.data == 'auto_prediction':
                if not self.prediction_type.data:
                    self.prediction_type.errors.append('Debe seleccionar el tipo de predicción.')
                    return False
                
                if self.prediction_type.data == 'amount_to_time':
                    if not self.target_amount.data:
                        self.target_amount.errors.append('Debe especificar la cantidad objetivo.')
                        return False
                elif self.prediction_type.data == 'time_to_amount':
                    if not self.target_timeframe_months.data:
                        self.target_timeframe_months.errors.append('Debe especificar el tiempo.')
                        return False
            else:
                # target_amount normal
                if not self.target_amount.data or not self.target_timeframe_months.data:
                    self.target_amount.errors.append('Debe especificar cantidad y tiempo.')
                    return False
        
        elif self.goal_type.data == 'savings_monthly':
            if not self.monthly_savings_target.data:
                self.monthly_savings_target.errors.append('Debe especificar el objetivo mensual.')
                return False
        
        elif self.goal_type.data == 'debt_threshold':
            print(f"DEBUG: Validando debt_threshold - valor: {self.debt_ceiling_percentage.data}")
            if not self.debt_ceiling_percentage.data:
                self.debt_ceiling_percentage.errors.append('Debe especificar el porcentaje.')
                return False
            
            # NUEVA: Validación adicional para debt_threshold
            if self.debt_ceiling_percentage.data <= 0 or self.debt_ceiling_percentage.data > 100:
                self.debt_ceiling_percentage.errors.append('El porcentaje debe estar entre 0.1 y 100.')
                return False
        
        # Validar alerta si se solicita
        if self.create_alert.data:
            pass
        
        print(f"DEBUG: Validación exitosa para {self.goal_type.data}")
        return True

class ReportExportForm(FlaskForm):
    """Formulario para exportar informes desde el buzón."""
    
    report_type = SelectField('Tipo de Informe',
                             choices=[
                                 ('complete', 'Informe Completo de Patrimonio'),
                                 ('bolsa', 'Solo Inversiones (Bolsa)'),
                                 ('cash', 'Solo Efectivo (Cuentas Bancarias)'),
                                 ('crypto', 'Solo Criptomonedas'),
                                 ('real_estate', 'Solo Inmuebles'),
                                 ('metales', 'Solo Metales Preciosos'),
                                 ('debts', 'Solo Deudas'),
                                 ('income_expenses', 'Solo Ingresos y Gastos')
                             ],
                             validators=[DataRequired()])
    
    export_format = SelectField('Formato',
                               choices=[
                                   ('csv', 'CSV'),
                                   ('xlsx', 'Excel (XLSX)')
                               ],
                               validators=[DataRequired()])
    
    submit = SubmitField('Exportar')

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

def admin_required(f): # MOSTRANDO COMPLETA
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acceso no autorizado. Se requieren privilegios de administrador.", "danger")
            # Redirige a login o a una página de 'no autorizado' más genérica si la tienes
            return redirect(url_for('login', next=request.url if request.method == 'GET' else None))
        return f(*args, **kwargs)
    return decorated_function

def check_and_resolve_warnings():
    """Verifica y resuelve mensajes de warning automáticamente."""
    warnings = MailboxMessage.query.filter_by(message_type='config_warning').all()
    
    for warning in warnings:
        if warning.related_watchlist_item_id and warning.related_alert_config_id:
            item = WatchlistItem.query.get(warning.related_watchlist_item_id)
            config = AlertConfiguration.query.get(warning.related_alert_config_id)
            
            # Si la fecha ahora existe y es futura, resolver el warning
            if item and item.fecha_resultados and item.fecha_resultados >= date.today():
                # Crear mensaje de resolución
                resolved_msg = MailboxMessage(
                    user_id=warning.user_id,
                    message_type='config_resolved',
                    title=f'✅ Fecha actualizada: {item.item_name or item.ticker}',
                    content=f'La fecha de resultados para {item.item_name or item.ticker} ha sido actualizada correctamente a {item.fecha_resultados.strftime("%d/%m/%Y")}.',
                    related_watchlist_item_id=item.id,
                    related_alert_config_id=config.id if config else None
                )
                db.session.add(resolved_msg)
                
                # Eliminar el mensaje de warning
                db.session.delete(warning)
    
    db.session.commit()


@app.route('/admin/email-queue/<int:email_id>/details')
@login_required
@admin_required
def admin_email_details(email_id):
    """Obtener detalles completos de un email."""
    try:
        email = EmailQueue.query.get_or_404(email_id)
        
        # Obtener información del mensaje relacionado
        mailbox_message = None
        alert_config = None
        user = None
        
        if email.mailbox_message_id:
            mailbox_message = MailboxMessage.query.get(email.mailbox_message_id)
            
        if email.alert_config_id:
            alert_config = AlertConfiguration.query.get(email.alert_config_id)
            
        # Obtener usuario
        user = User.query.filter_by(email=email.recipient_email).first()
        
        details = {
            'email': {
                'id': email.id,
                'recipient': email.recipient_email,
                'subject': email.subject,
                'status': email.status,
                'priority': email.priority,
                'attempts': email.attempts,
                'max_attempts': email.max_attempts,
                'created_at': email.created_at.strftime('%d/%m/%Y %H:%M:%S'),
                'scheduled_at': email.scheduled_at.strftime('%d/%m/%Y %H:%M:%S'),
                'sent_at': email.sent_at.strftime('%d/%m/%Y %H:%M:%S') if email.sent_at else None,
                'last_attempt_at': email.last_attempt_at.strftime('%d/%m/%Y %H:%M:%S') if email.last_attempt_at else None,
                'error_message': email.error_message,
                'content': email.content[:500] + '...' if len(email.content) > 500 else email.content
            },
            'user': {
                'id': user.id if user else None,
                'username': user.username if user else 'Usuario no encontrado',
                'is_active': user.is_active if user else False
            } if user else None,
            'mailbox_message': {
                'id': mailbox_message.id if mailbox_message else None,
                'title': mailbox_message.title if mailbox_message else None,
                'message_type': mailbox_message.message_type if mailbox_message else None,
                'created_at': mailbox_message.created_at.strftime('%d/%m/%Y %H:%M:%S') if mailbox_message else None
            } if mailbox_message else None,
            'alert_config': {
                'id': alert_config.id if alert_config else None,
                'alert_reason': alert_config.alert_reason if alert_config else None,
                'is_active': alert_config.is_active if alert_config else None,
                'notify_by_email': alert_config.notify_by_email if alert_config else None
            } if alert_config else None
        }
        
        return jsonify({'success': True, 'details': details})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== RUTAS DE ADMINISTRACIÓN DEL SCHEDULER =====
# Agregar estas rutas a app.py junto con las otras rutas /admin/*

@app.route('/admin/scheduler')
@login_required
def admin_scheduler():
    """Panel de gestión del scheduler."""
    if not current_user.is_admin:
        flash('Acceso denegado. Se requieren privilegios de administrador.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        # Obtener todas las tareas configuradas
        tasks = SchedulerTask.query.order_by(SchedulerTask.id).all()
        
        # Obtener jobs activos del scheduler
        active_jobs = {}
        try:
            for job in scheduler.get_jobs():
                task_key = job.id.replace('task_', '') if job.id.startswith('task_') else job.id
                active_jobs[task_key] = {
                    'next_run': job.next_run_time,
                    'job_id': job.id
                }
        except Exception as e:
            print(f"Error obteniendo jobs activos: {e}")
        
        # Obtener logs recientes del scheduler (últimos 50)
        scheduler_logs = SystemLog.query.filter(
            SystemLog.log_type.like('scheduler_%')
        ).order_by(SystemLog.executed_at.desc()).limit(50).all()
        
        return render_template('admin/scheduler.html',
                             title='Gestión del Scheduler',
                             tasks=tasks,
                             active_jobs=active_jobs,
                             scheduler_logs=scheduler_logs)
                             
    except Exception as e:
        flash(f'Error cargando panel del scheduler: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/scheduler/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def admin_toggle_scheduler_task(task_id):
    """Activa o desactiva una tarea del scheduler."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    try:
        task = SchedulerTask.query.get_or_404(task_id)
        old_status = task.is_active
        task.is_active = not task.is_active
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Recargar el scheduler
        reload_scheduler_tasks()
        
        # Registrar actividad
        action = 'activó' if task.is_active else 'desactivó'
        log_entry = ActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action_type='ADMIN_TOGGLE_SCHEDULER_TASK',
            message=f'{action} la tarea del scheduler: {task.task_name}',
            details=f'Cambio de estado: {old_status} → {task.is_active}',
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tarea {action} correctamente',
            'new_status': task.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/scheduler/task/<int:task_id>/execute', methods=['POST'])
@login_required
def admin_execute_scheduler_task(task_id):
    """Ejecuta una tarea del scheduler manualmente."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    try:
        task = SchedulerTask.query.get_or_404(task_id)
        
        # Obtener la función correspondiente
        task_function = get_task_function(task.task_function)
        if not task_function:
            return jsonify({'success': False, 'message': f'Función {task.task_function} no encontrada'}), 400
        
        # Ejecutar la tarea en un hilo separado para no bloquear la respuesta
        import threading
        def execute_task():
            try:
                task_function()
            except Exception as e:
                print(f"Error ejecutando tarea {task.task_key} manualmente: {e}")
        
        thread = threading.Thread(target=execute_task)
        thread.daemon = True
        thread.start()
        
        # Registrar actividad
        log_entry = ActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action_type='ADMIN_EXECUTE_SCHEDULER_TASK',
            message=f'Ejecutó manualmente la tarea: {task.task_name}',
            details=f'Función ejecutada: {task.task_function}',
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Tarea "{task.task_name}" ejecutada. Revisa los logs del sistema para ver el resultado.'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/scheduler/task/<int:task_id>/update', methods=['POST'])
@login_required
def admin_update_scheduler_task(task_id):
    """Actualiza la configuración de una tarea del scheduler."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    try:
        task = SchedulerTask.query.get_or_404(task_id)
        
        # Obtener datos del formulario
        frequency_type = request.form.get('frequency_type')
        frequency_value = int(request.form.get('frequency_value'))
        start_hour = int(request.form.get('start_hour'))
        start_minute = int(request.form.get('start_minute'))
        
        # Validaciones
        if frequency_type not in ['minutes', 'hours', 'days', 'weeks']:
            return jsonify({'success': False, 'message': 'Tipo de frecuencia inválido'}), 400
        
        if frequency_value < 1:
            return jsonify({'success': False, 'message': 'El valor de frecuencia debe ser mayor a 0'}), 400
            
        if not (0 <= start_hour <= 23):
            return jsonify({'success': False, 'message': 'La hora debe estar entre 0 y 23'}), 400
            
        if not (0 <= start_minute <= 59):
            return jsonify({'success': False, 'message': 'Los minutos deben estar entre 0 y 59'}), 400
        
        # Guardar configuración anterior para el log
        old_config = f"{task.frequency_display} a las {task.start_hour:02d}:{task.start_minute:02d}"
        
        # Actualizar tarea
        task.frequency_type = frequency_type
        task.frequency_value = frequency_value
        task.start_hour = start_hour
        task.start_minute = start_minute
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Recargar el scheduler si la tarea está activa
        if task.is_active:
            reload_scheduler_tasks()
        
        # Registrar actividad
        new_config = f"{task.frequency_display} a las {task.start_hour:02d}:{task.start_minute:02d}"
        log_entry = ActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action_type='ADMIN_UPDATE_SCHEDULER_TASK',
            message=f'Actualizó configuración de tarea: {task.task_name}',
            details=f'Cambio: {old_config} → {new_config}',
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Configuración actualizada correctamente',
            'new_frequency': task.frequency_display
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'message': 'Valores numéricos inválidos'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/scheduler/reload', methods=['POST'])
@login_required
def admin_reload_scheduler():
    """Recarga todas las tareas del scheduler."""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Acceso denegado'}), 403
    
    try:
        reload_scheduler_tasks()
        
        # Registrar actividad
        log_entry = ActivityLog(
            user_id=current_user.id,
            username=current_user.username,
            action_type='ADMIN_RELOAD_SCHEDULER',
            message='Recargó todas las tareas del scheduler',
            ip_address=request.remote_addr
        )
        db.session.add(log_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Scheduler recargado correctamente'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/office/goals', methods=['GET', 'POST'])
@login_required
def office_goals():
    """Pestaña de objetivos financieros con modelo Goal."""
    form = GoalConfigurationForm()
    
    # NUEVO: Función auxiliar para obtener objetivos con estado
    def get_goals_with_status():
        user_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True)\
            .order_by(Goal.created_at.desc()).all()
        
        goals_with_status = []
        for goal in user_goals:
            try:
                goal_status = calculate_goal_status_with_model(goal)
                goals_with_status.append({
                    'config': goal,
                    'status': goal_status
                })
            except Exception as e:
                print(f"Error calculando estado de objetivo {goal.id}: {e}")
                goals_with_status.append({
                    'config': goal,
                    'status': {'error': f'Error calculando progreso: {str(e)}'}
                })
        return goals_with_status
    
    if form.validate_on_submit():
        try:
            print(f"DEBUG: Formulario validado exitosamente - goal_type: {form.goal_type.data}")
            
            # Validación de unicidad
            uniqueness_check = validate_goal_uniqueness(form, current_user.id)
            if uniqueness_check['error']:
                flash(uniqueness_check['message'], 'warning')
                # CORREGIDO: Mantener datos existentes en caso de error
                goals_with_status = get_goals_with_status()
                return render_template('office/goals.html', form=form, goals=goals_with_status)
            
            # Validaciones previas según tipo de objetivo
            validation_error = validate_goal_prerequisites_updated(form)
            if validation_error:
                if validation_error.get('type') == 'info':
                    flash(validation_error['message'], 'info')
                else:
                    flash(validation_error['message'], 'warning')
                    # CORREGIDO: Mantener datos existentes en caso de error
                    goals_with_status = get_goals_with_status()
                    return render_template('office/goals.html', form=form, goals=goals_with_status)
            
            # Crear objetivo principal con NOMBRE AUTOMÁTICO
            new_goal = Goal(
                user_id=current_user.id,
                goal_name=generate_automatic_goal_name(form),
                goal_type=form.goal_type.data,
                description=None,
                start_date=form.start_date.data or date.today()
            )
            
            print(f"DEBUG: Creando objetivo - tipo: {new_goal.goal_type}")
            
            # Configurar campos específicos según tipo
            if form.goal_type.data == 'portfolio_percentage':
                distribution = {
                    'bolsa': form.percentage_bolsa.data or 0,
                    'cash': form.percentage_cash.data or 0,
                    'crypto': form.percentage_crypto.data or 0,
                    'real_estate': form.percentage_real_estate.data or 0,
                    'metales': form.percentage_metales.data or 0
                }
                new_goal.asset_distribution = json.dumps(distribution)
                
            elif form.goal_type.data == 'target_amount':
                new_goal.goal_asset_type = form.goal_asset_type.data
                new_goal.target_amount = form.target_amount.data
                new_goal.target_timeframe_months = form.target_timeframe_months.data
                
            elif form.goal_type.data == 'auto_prediction':
                new_goal.goal_asset_type = form.goal_asset_type.data
                new_goal.prediction_type = form.prediction_type.data
                new_goal.target_amount = form.target_amount.data
                new_goal.target_timeframe_months = form.target_timeframe_months.data
                
            elif form.goal_type.data == 'savings_monthly':
                new_goal.goal_asset_type = 'cash'
                new_goal.monthly_savings_target = form.monthly_savings_target.data
                
            elif form.goal_type.data == 'debt_threshold':
                print(f"DEBUG: Configurando debt_threshold - valor: {form.debt_ceiling_percentage.data}")
                new_goal.debt_ceiling_percentage = form.debt_ceiling_percentage.data
                new_goal.goal_asset_type = None
            
            print(f"DEBUG: Objetivo configurado: {new_goal.__dict__}")
            
            db.session.add(new_goal)
            
            # Crear alerta asociada SI el usuario lo solicita
            if form.create_alert.data:
                alert_config = AlertConfiguration(
                    user_id=current_user.id,
                    alert_reason='objetivo',
                    notify_by_email=form.notify_by_email.data,
                    goal_name=new_goal.goal_name,
                    goal_type=new_goal.goal_type,
                    goal_start_date=new_goal.start_date,
                    custom_frequency_type='monthly',
                    custom_start_date=new_goal.start_date
                )
                db.session.add(alert_config)
                print(f"DEBUG: Alerta creada para objetivo")
            
            db.session.commit()
            print(f"DEBUG: Objetivo guardado exitosamente en BD")
            
            success_msg = f'Objetivo "{new_goal.goal_name}" creado correctamente.'
            if form.create_alert.data:
                success_msg += ' Alerta asociada configurada.'
            
            flash(success_msg, 'success')
            return redirect(url_for('office_goals'))
            
        except Exception as e:
            db.session.rollback()
            print(f"DEBUG ERROR: Error al crear objetivo: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f'Error al crear el objetivo: {str(e)}', 'error')
            # CORREGIDO: Mantener datos existentes en caso de error
            goals_with_status = get_goals_with_status()
            return render_template('office/goals.html', form=form, goals=goals_with_status)
    else:
        # DEBUG: Mostrar errores de validación
        if form.errors:
            print(f"DEBUG: Errores de validación: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en {field}: {error}', 'error')
    
    # CORREGIDO: Usar la función auxiliar para obtener objetivos
    goals_with_status = get_goals_with_status()
    return render_template('office/goals.html', form=form, goals=goals_with_status)

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
           additional_created = 0
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
                       csv_filename=filename,
                       is_additional_movement=False  # Movimiento original del CSV
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
                   db.session.flush()  # Para obtener el ID del movimiento original
                   
                   movements_added += 1
                   
                   # NUEVO: Si es viban_purchase con compra, crear movimiento adicional de depósito
                   if (transaction_kind == 'viban_purchase' and 
                       category == 'Compra' and 
                       temp_movement.currency == 'EUR'):  # Solo si la moneda es EUR
                       
                       additional_movement = create_additional_deposit_movement(temp_movement)
                       
                       # Verificar duplicados del movimiento adicional
                       existing_additional_hash = CryptoCsvMovement.query.filter_by(
                           user_id=current_user.id,
                           transaction_hash_unique=additional_movement.transaction_hash_unique
                       ).first()
                       
                       if not existing_additional_hash:
                           db.session.add(additional_movement)
                           movements_added += 1
                           additional_created += 1
                   
                   # NUEVO: Si es un reward, crear movimiento adicional de compra
                   if category == 'Rewards':
                       additional_movement = create_additional_buy_movement_from_reward(temp_movement)
                       
                       # Verificar duplicados del movimiento adicional
                       existing_additional_hash = CryptoCsvMovement.query.filter_by(
                           user_id=current_user.id,
                           transaction_hash_unique=additional_movement.transaction_hash_unique
                       ).first()
                       
                       if not existing_additional_hash:
                           db.session.add(additional_movement)
                           movements_added += 1
                           additional_created += 1
                   
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
               if additional_created > 0:
                   flash(f'{additional_created} movimientos adicionales creados automáticamente.', 'info')
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
   
   # Estadísticas actualizadas
   total_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id).count()
   csv_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id, is_additional_movement=False).count()
   additional_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id, is_additional_movement=True).count()
   exchanges_count = len(set(m.exchange_name for m in CryptoCsvMovement.query.filter_by(user_id=current_user.id, is_additional_movement=False).all())) if csv_movements > 0 else 0
   orphans_count = CryptoCsvMovement.query.filter_by(user_id=current_user.id, process_status='Huérfano').count()
   uncategorized_count = CryptoCsvMovement.query.filter_by(user_id=current_user.id, category='Sin Categoría').count()
   
   
   # Calcular P&L por criptomoneda
   crypto_pnl_data = calculate_crypto_pnl(CryptoCsvMovement.query.filter_by(user_id=current_user.id).all())

   # Calcular capital propio
   own_capital_data = calculate_own_capital(CryptoCsvMovement.query.filter_by(user_id=current_user.id).all())

   # Calcular datos de rewards
   rewards_data = calculate_rewards_data(CryptoCsvMovement.query.filter_by(user_id=current_user.id).all())

   # Calcular P&L total
   total_pnl_data = calculate_total_pnl(
       CryptoCsvMovement.query.filter_by(user_id=current_user.id).all(),
       own_capital_data,
       rewards_data
   )
  
   # Obtener mapeos existentes
   existing_mappings = CryptoCategoryMapping.query.filter_by(user_id=current_user.id).order_by(CryptoCategoryMapping.mapping_type, CryptoCategoryMapping.source_value).all()

   return render_template(
       'crypto_movements.html',
       csv_form=csv_form,
       mapping_form=mapping_form,
       movements=movements,
       total_movements=total_movements,
       csv_movements=csv_movements,
       additional_movements=additional_movements,
       exchanges_count=exchanges_count,
       orphans_count=orphans_count,
       uncategorized_count=uncategorized_count,
       crypto_pnl_data=crypto_pnl_data,
       own_capital_data=own_capital_data,
       rewards_data=rewards_data,
       total_pnl_data=total_pnl_data,
       existing_mappings=existing_mappings,
       search_query=search_query
   )

@app.route('/admin/email-queue')
@login_required
@admin_required
def admin_email_queue():
    """Gestión completa de la cola de emails."""
    try:
        # Filtros desde query parameters
        status_filter = request.args.get('status', 'all')
        priority_filter = request.args.get('priority', 'all')
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # Construir consulta base
        query = EmailQueue.query
        
        # Aplicar filtros
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
            
        if priority_filter != 'all':
            query = query.filter_by(priority=int(priority_filter))
        
        # Ordenar y paginar
        emails = query.order_by(
            EmailQueue.created_at.desc()
        ).paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        # Estadísticas para la página
        total_emails = EmailQueue.query.count()
        pending_count = EmailQueue.query.filter_by(status='pending').count()
        sent_count = EmailQueue.query.filter_by(status='sent').count()
        failed_count = EmailQueue.query.filter_by(status='failed').count()
        cancelled_count = EmailQueue.query.filter_by(status='cancelled').count()
        
        return render_template('admin/email-queue.html',
                             title='Gestión de Cola de Emails',
                             emails=emails,
                             status_filter=status_filter,
                             priority_filter=priority_filter,
                             total_emails=total_emails,
                             pending_count=pending_count,
                             sent_count=sent_count,
                             failed_count=failed_count,
                             cancelled_count=cancelled_count)
                             
    except Exception as e:
        flash(f'Error cargando cola de emails: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/email-queue/<int:email_id>/retry', methods=['POST'])
@login_required
@admin_required
def admin_retry_email(email_id):
    """Reintentar envío de email fallido."""
    try:
        email = EmailQueue.query.get_or_404(email_id)

        if email.status == 'failed' and email.can_retry:
            email.status = 'pending'
            email.error_message = None
            email.scheduled_at = datetime.utcnow()

            db.session.commit()

            flash(f'Email reactivado para reintento: {email.subject}', 'success')
        else:
            flash('Este email no puede ser reintentado', 'warning')

    except Exception as e:
        flash(f'Error reintentando email: {str(e)}', 'danger')
        db.session.rollback()

    return redirect(url_for('admin_email_queue'))

@app.route('/admin/email-queue/<int:email_id>/cancel', methods=['POST'])
@login_required
@admin_required
def admin_cancel_email(email_id):
    """Cancelar email pendiente."""
    try:
        email = EmailQueue.query.get_or_404(email_id)

        if email.status == 'pending':
            email.status = 'cancelled'
            email.error_message = 'Cancelado manualmente por administrador'

            db.session.commit()

            flash(f'Email cancelado: {email.subject}', 'success')
        else:
            flash('Solo se pueden cancelar emails pendientes', 'warning')

    except Exception as e:
        flash(f'Error cancelando email: {str(e)}', 'danger')
        db.session.rollback()

    return redirect(url_for('admin_email_queue'))

@app.route('/admin/email-queue/<int:email_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_email(email_id):
    """Eliminar email de la cola."""
    try:
        email = EmailQueue.query.get_or_404(email_id)

        db.session.delete(email)
        db.session.commit()

        flash(f'Email eliminado: {email.subject}', 'success')

    except Exception as e:
        flash(f'Error eliminando email: {str(e)}', 'danger')
        db.session.rollback()

    return redirect(url_for('admin_email_queue'))


def log_task_execution(task_key, status, details=None, start_time=None):
    """Registra la ejecución de una tarea del scheduler de forma simple."""
    try:
        # Usar la sesión principal de Flask, no crear una nueva
        with app.app_context():
            try:
                # Registrar en SystemLog usando la sesión principal
                log_entry = SystemLog(
                    log_type=f'scheduler_{task_key}',
                    executed_at=start_time or datetime.utcnow(),
                    status=status,
                    details=details
                )
                db.session.add(log_entry)
                
                # Actualizar SchedulerTask si existe
                task_config = SchedulerTask.query.filter_by(task_key=task_key).first()
                if task_config:
                    task_config.last_executed = start_time or datetime.utcnow()
                    task_config.execution_count = (task_config.execution_count or 0) + 1
                
                db.session.commit()
                print(f"[{datetime.utcnow()}] Tarea {task_key}: {status} - {details}")
                
            except Exception as db_error:
                print(f"⚠️ Error en logging para {task_key}: {db_error}")
                # NO hacer rollback aquí, solo imprimir el error
                
    except Exception as e:
        print(f"⚠️ Error crítico en logging {task_key}: {e}")

def process_daily_alerts_global():
    """Versión global de process_daily_alerts para el scheduler."""
    start_time = datetime.utcnow()
    task_key = 'all_tasks'
    
    try:
        with app.app_context():
            print(f"[{start_time}] Iniciando procesamiento completo...")
            
            # Fase 1: Actualizar precios globalmente
            print("Fase 1: Actualizando precios globalmente...")
            update_all_prices_global()
            
            # Fase 2: Generar alertas globalmente  
            print("Fase 2: Generando alertas...")
            generate_alert_messages_global()
            
            # Fase 3: Enviar emails globalmente
            print("Fase 3: Enviando emails...")
            send_email_notifications_global()
            
            log_task_execution(
                task_key=task_key,
                status='success', 
                details='Procesamiento completo ejecutado exitosamente',
                start_time=start_time
            )
            
    except Exception as e:
        log_task_execution(
            task_key=task_key,
            status='error',
            details=f'Error en procesamiento completo: {str(e)}',
            start_time=start_time
        )

def add_email_to_queue(mailbox_message, alert_config, priority=5, delay_minutes=0):
    """Agrega un email a la cola de envío."""
    try:
        # Verificar que el usuario quiere recibir emails
        if not alert_config or not alert_config.notify_by_email:
            return False
            
        # Buscar email del usuario
        user = User.query.get(mailbox_message.user_id)
        if not user or not user.email:
            print(f"Usuario {mailbox_message.user_id} no tiene email configurado")
            return False
        
        # Verificar si ya existe en la cola para evitar duplicados
        existing = EmailQueue.query.filter_by(
            mailbox_message_id=mailbox_message.id,
            status='pending'
        ).first()
        if existing:
            print(f"Email ya está en cola para mensaje {mailbox_message.id}")
            return False
        
        # Generar contenido del email
        subject = f"[FollowUp] {mailbox_message.title}"
        content = generate_email_content(mailbox_message, alert_config)
        
        # Calcular cuándo enviar
        scheduled_at = datetime.utcnow()
        if delay_minutes > 0:
            scheduled_at += timedelta(minutes=delay_minutes)
        
        # Crear entrada en la cola
        email_entry = EmailQueue(
            mailbox_message_id=mailbox_message.id,
            alert_config_id=alert_config.id,
            recipient_email=user.email,
            subject=subject,
            content=content,
            priority=priority,
            scheduled_at=scheduled_at
        )
        
        db.session.add(email_entry)
        db.session.commit()
        
        print(f"✅ Email agregado a cola: {subject} para {user.email}")
        return True
        
    except Exception as e:
        print(f"❌ Error agregando email a cola: {e}")
        db.session.rollback()
        return False

def process_email_queue():
    """Procesa la cola de emails pendientes."""
    try:
        # Obtener emails listos para enviar, ordenados por prioridad y fecha
        pending_emails = EmailQueue.query.filter(
            EmailQueue.status == 'pending',
            EmailQueue.scheduled_at <= datetime.utcnow(),
            EmailQueue.attempts < EmailQueue.max_attempts
        ).order_by(
            EmailQueue.priority.asc(),
            EmailQueue.created_at.asc()
        ).limit(10).all()  # Procesar máximo 10 emails por ejecución
        
        sent_count = 0
        failed_count = 0
        
        for email_entry in pending_emails:
            try:
                # Verificar nuevamente que el usuario quiere recibir emails
                if email_entry.alert_config and not email_entry.alert_config.notify_by_email:
                    email_entry.status = 'cancelled'
                    email_entry.error_message = 'Usuario desactivó notificaciones por email'
                    continue
                
                # Intentar enviar
                send_email_from_queue(email_entry)
                
                # Marcar como enviado
                email_entry.status = 'sent'
                email_entry.sent_at = datetime.utcnow()
                email_entry.last_attempt_at = datetime.utcnow()
                sent_count += 1
                
                print(f"✅ Email enviado: {email_entry.subject} a {email_entry.recipient_email}")
                
            except Exception as e:
                # Incrementar intentos
                email_entry.attempts += 1
                email_entry.last_attempt_at = datetime.utcnow()
                email_entry.error_message = str(e)
                
                # Si se agotaron los intentos, marcar como fallido
                if email_entry.attempts >= email_entry.max_attempts:
                    email_entry.status = 'failed'
                    failed_count += 1
                    print(f"❌ Email fallido (max intentos): {email_entry.subject}")
                else:
                    print(f"⚠️ Email falló (intento {email_entry.attempts}): {e}")
        
        db.session.commit()
        return {'sent': sent_count, 'failed': failed_count, 'processed': len(pending_emails)}
        
    except Exception as e:
        print(f"❌ Error procesando cola de emails: {e}")
        db.session.rollback()
        return {'sent': 0, 'failed': 0, 'processed': 0, 'error': str(e)}

def send_email_from_queue(email_entry):
    """Envía un email específico desde la cola."""
    from flask_mail import Message
    
    msg = Message(
        subject=email_entry.subject,
        recipients=[email_entry.recipient_email],
        html=email_entry.content,
        sender=app.config['MAIL_DEFAULT_SENDER']
    )
    
    mail.send(msg)

def generate_email_content(mailbox_message, alert_config):
    """Genera el contenido HTML del email."""
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; margin: 20px;">
        <h2 style="color: #333;">{mailbox_message.title}</h2>
        <div style="background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <p>{mailbox_message.content}</p>
        </div>
        
        <div style="margin-top: 20px; padding: 10px; border-top: 1px solid #eee;">
            <small style="color: #666;">
                <strong>Fecha:</strong> {mailbox_message.created_at.strftime('%d/%m/%Y %H:%M')}<br>
                <strong>Tipo de alerta:</strong> {alert_config.alert_reason if alert_config else 'N/A'}<br>
                <br>
                Este email fue enviado automáticamente por FollowUp.<br>
                Para desactivar las notificaciones por email, accede a tu configuración de alertas.
            </small>
        </div>
    </body>
    </html>
    """


def update_all_prices_global():
    """Versión global de actualización de precios para todos los usuarios."""
    start_time = datetime.utcnow()
    task_key = 'update_prices'
    
    try:
        with app.app_context():
            updated_items = 0
            errors = []
            
            # 1. Actualizar precios de watchlist para TODOS los usuarios
            try:
                all_watchlist_items = WatchlistItem.query.all()
                for item in all_watchlist_items:
                    try:
                        update_watchlist_item_from_yahoo(item.id, force_update=True)
                        updated_items += 1
                    except Exception as e:
                        errors.append(f"Error actualizando {item.ticker}: {str(e)}")
            except Exception as e:
                errors.append(f"Error en watchlist global: {str(e)}")
            
            # 2. Actualizar metales preciosos (global)
            try:
                update_precious_metal_prices()
                updated_items += 2  # Oro y plata
            except Exception as e:
                errors.append(f"Error actualizando metales: {str(e)}")
            
            # 3. Actualizar criptomonedas para TODOS los usuarios
            try:
                all_users = User.query.filter_by(is_active=True).all()
                for user in all_users:
                    try:
                        update_crypto_prices(user.id)
                        crypto_count = CryptoTransaction.query.filter_by(user_id=user.id)\
                            .with_entities(CryptoTransaction.ticker_symbol).distinct().count()
                        updated_items += crypto_count
                    except Exception as e:
                        errors.append(f"Error actualizando criptos para usuario {user.username}: {str(e)}")
            except Exception as e:
                errors.append(f"Error en criptos global: {str(e)}")
            
            details = f"Actualizados {updated_items} elementos. {len(errors)} errores."
            status = 'partial' if errors else 'success'
            
            log_task_execution(
                task_key=task_key,
                status=status,
                details=details,
                start_time=start_time
            )
            
    except Exception as e:
        log_task_execution(
            task_key=task_key,
            status='error',
            details=f'Error en actualización global: {str(e)}',
            start_time=start_time
        )

def generate_alert_messages_global():
    """Versión global de generación de alertas."""
    start_time = datetime.utcnow()
    task_key = 'check_alerts'
    
    try:
        with app.app_context():
            today = date.today()
            check_and_resolve_warnings()
            
            # Obtener todas las configuraciones activas de TODOS los usuarios
            alert_configs = AlertConfiguration.query.filter_by(is_active=True).all()
            processed_alerts = 0
            
            for config in alert_configs:
                try:
                    if config.alert_reason == 'earnings_report':
                        process_earnings_alerts(config, today)
                    elif config.alert_reason == 'metric_threshold':
                        process_metric_alerts(config, today)
                    elif config.alert_reason == 'periodic_summary':
                        process_summary_alerts(config, today)
                    elif config.alert_reason == 'custom':
                        process_custom_alerts(config, today)
                    
                    processed_alerts += 1
                    
                except Exception as e:
                    print(f"Error procesando alerta {config.id}: {e}")
            
            log_task_execution(
                task_key=task_key,
                status='success',
                details=f'Procesadas {processed_alerts} configuraciones de alerta',
                start_time=start_time
            )
            
    except Exception as e:
        log_task_execution(
            task_key=task_key,
            status='error',
            details=f'Error generando alertas: {str(e)}',
            start_time=start_time
        )

def send_email_notifications_global():
    """Versión que usa la cola de emails."""
    start_time = datetime.utcnow()
    task_key = 'send_emails'
    
    try:
        with app.app_context():
            result = process_email_queue()
            
            # Determinar estado basado en resultados
            if 'error' in result:
                status = 'error'
                details = f"Error procesando cola: {result['error']}"
            else:
                sent = result.get('sent', 0)
                failed = result.get('failed', 0)
                
                if failed == 0:
                    status = 'success'
                    details = f'Enviados {sent} correos electrónicos'
                else:
                    status = 'partial'
                    details = f'Enviados {sent} correos, {failed} fallidos'
            
            log_task_execution(
                task_key=task_key,
                status=status,
                details=details,
                start_time=start_time
            )
            
    except Exception as e:
        log_task_execution(
            task_key=task_key,
            status='error',
            details=f'Error crítico en cola de emails: {str(e)}',
            start_time=start_time
        )

def initialize_default_scheduler_tasks():
    """Inicializa las tareas predeterminadas del scheduler si no existen."""
    try:
        # Verificar si ya existen tareas configuradas
        existing_tasks = SchedulerTask.query.count()
        
        if existing_tasks == 0:
            print("Inicializando tareas predeterminadas del scheduler...")
            
            for task_data in DEFAULT_SCHEDULER_TASKS:
                task = SchedulerTask(**task_data)
                db.session.add(task)
            
            db.session.commit()
            print(f"Inicializadas {len(DEFAULT_SCHEDULER_TASKS)} tareas del scheduler.")
        else:
            print(f"Ya existen {existing_tasks} tareas configuradas.")
            
    except Exception as e:
        print(f"Error inicializando tareas predeterminadas: {e}")
        db.session.rollback()

def get_task_function(function_name):
    """Obtiene la función correspondiente al nombre."""
    function_map = {
        'process_daily_alerts_global': process_daily_alerts_global,
        'update_all_prices_global': update_all_prices_global,
        'generate_alert_messages_global': generate_alert_messages_global,
        'send_email_notifications_global': send_email_notifications_global
    }
    return function_map.get(function_name)

def setup_dynamic_scheduled_tasks():
    """Configura las tareas programadas basándose en la configuración de la base de datos."""
    try:
        # Eliminar todos los jobs existentes
        scheduler.remove_all_jobs()
        print("Jobs anteriores eliminados.")
        
        # Obtener tareas activas de la base de datos
        active_tasks = SchedulerTask.query.filter_by(is_active=True).all()
        
        jobs_added = 0
        for task in active_tasks:
            try:
                # Obtener la función correspondiente
                task_function = get_task_function(task.task_function)
                if not task_function:
                    print(f"Función {task.task_function} no encontrada para tarea {task.task_key}")
                    continue
                
                # Configurar el trigger según el tipo de frecuencia
                if task.frequency_type == 'minutes':
                    scheduler.add_job(
                        func=task_function,
                        trigger='interval',
                        minutes=task.frequency_value,
                        start_date=datetime.now().replace(
                            hour=task.start_hour, 
                            minute=task.start_minute, 
                            second=0, 
                            microsecond=0
                        ),
                        id=f'task_{task.task_key}',
                        name=task.task_name,
                        replace_existing=True
                    )
                    
                elif task.frequency_type == 'hours':
                    scheduler.add_job(
                        func=task_function,
                        trigger='interval',
                        hours=task.frequency_value,
                        start_date=datetime.now().replace(
                            hour=task.start_hour, 
                            minute=task.start_minute, 
                            second=0, 
                            microsecond=0
                        ),
                        id=f'task_{task.task_key}',
                        name=task.task_name,
                        replace_existing=True
                    )
                    
                elif task.frequency_type == 'days':
                    scheduler.add_job(
                        func=task_function,
                        trigger='cron',
                        day='*/{}'.format(task.frequency_value),
                        hour=task.start_hour,
                        minute=task.start_minute,
                        id=f'task_{task.task_key}',
                        name=task.task_name,
                        replace_existing=True
                    )
                    
                elif task.frequency_type == 'weeks':
                    # Para semanas, ejecutar cada N*7 días
                    scheduler.add_job(
                        func=task_function,
                        trigger='cron',
                        day='*/{}'.format(task.frequency_value * 7),
                        hour=task.start_hour,
                        minute=task.start_minute,
                        id=f'task_{task.task_key}',
                        name=task.task_name,
                        replace_existing=True
                    )
                
                jobs_added += 1
                print(f"Tarea programada: {task.task_name} - {task.frequency_display}")
                
            except Exception as e:
                print(f"Error configurando tarea {task.task_key}: {e}")
        
        print(f"Scheduler configurado con {jobs_added} tareas activas.")
        
        # Mostrar información de debug
        for job in scheduler.get_jobs():
            print(f"Job activo: {job.id} - Próxima ejecución: {job.next_run_time}")
            
    except Exception as e:
        print(f"Error configurando scheduler dinámico: {e}")

def reload_scheduler_tasks():
    """Recarga las tareas del scheduler desde la base de datos."""
    setup_dynamic_scheduled_tasks()


def generate_automatic_goal_name(form):
    """Genera nombres automáticos para objetivos."""
    
    if form.goal_type.data == 'portfolio_percentage':
        return "Distribución Ideal de Activos"
    
    elif form.goal_type.data == 'target_amount':
        asset_names = {
            'bolsa': 'Bolsa',
            'cash': 'Efectivo',
            'crypto': 'Criptomonedas',
            'real_estate': 'Inmuebles',
            'metales': 'Metales Preciosos',
            'total_patrimonio': 'Patrimonio Total'
        }
        asset_name = asset_names.get(form.goal_asset_type.data, form.goal_asset_type.data)
        return f"Meta de {asset_name}"
    
    elif form.goal_type.data == 'auto_prediction':
        asset_names = {
            'bolsa': 'Bolsa',
            'cash': 'Efectivo',
            'crypto': 'Criptomonedas',
            'real_estate': 'Inmuebles',
            'metales': 'Metales Preciosos',
            'total_patrimonio': 'Patrimonio Total'
        }
        asset_name = asset_names.get(form.goal_asset_type.data, form.goal_asset_type.data)
        
        prediction_names = {
            'amount_to_time': 'Predicción de Tiempo',
            'time_to_amount': 'Predicción de Cantidad'
        }
        prediction_name = prediction_names.get(form.prediction_type.data, form.prediction_type.data)
        
        return f"{prediction_name} en {asset_name}"
    
    elif form.goal_type.data == 'savings_monthly':
        return "Ahorro Mensual"
    
    elif form.goal_type.data == 'debt_threshold':
        return "Techo de Deuda"
    
    else:
        return "Objetivo Personalizado"

def process_uploaded_csvs(files):
    """
    Función modificada para soportar tanto DeGiro como IBKR.
    Mantiene la misma interfaz que la función original.
    
    Returns:
        tuple: (processed_df_for_csv, combined_df_raw, errors)
    """
    all_dfs = []
    filenames_processed = []
    errors = []

    if not files or all(f.filename == '' for f in files):
        errors.append("Error: No archivos seleccionados.")
        return None, None, errors

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            
            # Validación de nombre de archivo más flexible
            if not validate_filename_format_flexible(filename):
                errors.append(f"Advertencia: Archivo '{filename}' ignorado (formato inválido).")
                continue
            
            df = None
            try:
                file.seek(0)
                
                # Detectar formato del CSV
                csv_format = detect_csv_format_simple(file)
                print(f"Formato detectado para '{filename}': {csv_format}")
                
                if csv_format == 'ibkr':
                    # Procesar CSV de IBKR
                    print(f"Procesando archivo IBKR: {filename}")
                    df = process_ibkr_file_complete(file, filename)
                    if df is not None:
                        df['csv_format'] = 'ibkr'
                    
                else:
                    # Procesar como DeGiro (lógica original)
                    file.seek(0)
                    try:
                        # Intenta leer con UTF-8 primero
                        df = pd.read_csv(io.BytesIO(file.read()), encoding='utf-8', sep=',', decimal='.', skiprows=0, header=0)
                        print(f"Archivo '{filename}' leído con UTF-8. Columnas: {df.columns.tolist()}")
                    except UnicodeDecodeError:
                        try:
                            file.seek(0)
                            # Si falla UTF-8, intenta con latin-1
                            df = pd.read_csv(io.BytesIO(file.read()), encoding='latin-1', sep=',', decimal='.', skiprows=0, header=0)
                            print(f"Archivo '{filename}' leído con latin-1. Columnas: {df.columns.tolist()}")
                        except Exception as e:
                            errors.append(f"Error leyendo '{filename}' (probado con UTF-8 y latin-1): {e}")
                            continue
                    except Exception as e:
                        errors.append(f"Error general leyendo '{filename}': {e}")
                        continue
                    
                    if df is not None:
                        df['csv_format'] = 'degiro'

            except Exception as e:
                errors.append(f"Error procesando archivo '{filename}': {e}")
                continue

            if df is not None and not df.empty:
                # Validar columnas para DeGiro
                if csv_format != 'ibkr':
                    missing_original_cols = [col for col in COLS_MAP.keys() if col not in df.columns]
                    if missing_original_cols:
                        errors.append(f"Advertencia: Columnas originales faltantes en '{filename}': {', '.join(missing_original_cols)}.")
                
                df['source_file'] = filename
                all_dfs.append(df)
                filenames_processed.append(filename)
            else:
                errors.append(f"Error: No se pudieron leer datos válidos de '{filename}'.")
        else:
            if file:
                errors.append(f"Archivo '{file.filename}' no permitido (debe ser .csv).")

    if not all_dfs:
        errors.append("Error: No se procesaron archivos válidos.")
        return None, None, errors

    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True)
        
        # Parsear fechas y ordenar
        try:
            if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
                combined_df_raw['FechaHora'] = pd.to_datetime(
                    combined_df_raw['Fecha'] + ' ' + combined_df_raw['Hora'], 
                    dayfirst=True, errors='coerce'
                )
                combined_df_raw = combined_df_raw.sort_values('FechaHora', ascending=True)
            elif 'Fecha' in combined_df_raw.columns:
                combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], dayfirst=True, errors='coerce')
                combined_df_raw = combined_df_raw.sort_values('Fecha', ascending=True)
        except Exception as e_date:
            errors.append(f"Advertencia: Error parseando fechas: {e_date}")

        # Preparar DataFrame para cálculo de portfolio
        df_for_portfolio_calc = combined_df_raw.copy()
        
        # Si contiene datos de IBKR, ajustar para calculate_portfolio
        has_ibkr_data = False
        if 'csv_format' in combined_df_raw.columns:
            has_ibkr_data = any(combined_df_raw['csv_format'] == 'ibkr')
        else:
            # Fallback: detectar por presencia de ciertos patrones
            has_ibkr_data = any('U12722327' in str(row.get('source_file', '')) 
                              for _, row in combined_df_raw.iterrows())
        
        if has_ibkr_data:
            print("Detectados datos IBKR, ajustando DataFrame para calculate_portfolio")
            df_for_portfolio_calc = prepare_dataframe_for_portfolio_calculation(df_for_portfolio_calc)

        # Preparar DataFrame para CSV final
        processed_df_for_csv = prepare_processed_dataframe(combined_df_raw, errors)

        return processed_df_for_csv, df_for_portfolio_calc, errors

    except Exception as e_concat:
        errors.append(f"Error al combinar archivos CSV o parsear fechas: {e_concat}")
        return None, None, errors

def check_and_add_debt_ceiling_column():
    """Verifica y añade la columna debt_ceiling_percentage si no existe."""
    try:
        # Intentar hacer una consulta que use la columna
        Goal.query.filter(Goal.debt_ceiling_percentage.isnot(None)).first()
        print("✅ Columna debt_ceiling_percentage ya existe")
    except Exception as e:
        print(f"❌ Columna debt_ceiling_percentage no existe, creándola...")
        try:
            # Crear la columna manualmente
            db.engine.execute('ALTER TABLE goals ADD COLUMN debt_ceiling_percentage FLOAT')
            print("✅ Columna debt_ceiling_percentage creada exitosamente")
        except Exception as alter_error:
            print(f"❌ Error creando columna: {alter_error}")

def prepare_dataframe_for_portfolio_calculation(df_input): # Renombrado el parámetro de entrada
    """
    Prepara el DataFrame para que calculate_portfolio funcione correctamente.
    Ajusta el signo de 'Número' para transacciones IBKR basado en 'Total'.
    Las filas de DeGiro deben pasar sin cambios en su columna 'Número'.
    """
    if df_input.empty:
        print("DEBUG: prepare_dataframe_for_portfolio_calculation recibió un DataFrame vacío.")
        return df_input
    
    # Trabajar sobre una copia para no modificar el DataFrame original que podría usarse en otro lado
    df_processed = df_input.copy() 
    
    print("DEBUG: Iniciando prepare_dataframe_for_portfolio_calculation...")
    stock_isin_to_debug = "SE0009554454" # ¡¡¡REEMPLAZA CON EL ISIN CORRECTO DE SBB!!!
    
    # Crear una lista para almacenar los nuevos valores de 'Número'
    nuevos_numeros = []
    
    for idx, row in df_processed.iterrows(): # Iterar sobre la copia
        is_sbb_row = row.get('ISIN') == stock_isin_to_debug
        current_csv_format = row.get('csv_format', 'desconocido')

        cantidad_original_str = str(row.get('Número', '0')) # Obtener como string para limpieza
        total_str = str(row.get('Total', '0'))           # Obtener como string para limpieza

        if is_sbb_row:
            print(f"  DEBUG SBB (Fila índice pandas: {idx}, Archivo: {row.get('source_file', 'N/A')}):")
            print(f"    Fila ANTES de cualquier ajuste en prepare_dataframe_for_portfolio_calculation:")
            print(f"      Número (str): '{cantidad_original_str}', Total (str): '{total_str}', "
                  f"csv_format: {current_csv_format}")

        try:
            cantidad_original = float(cantidad_original_str.replace(',', '.'))
        except ValueError:
            if is_sbb_row:
                print(f"    DEBUG SBB (Fila {idx}): 'Número' original ('{cantidad_original_str}') no es numérico. Usando 0.")
            cantidad_original = 0.0 # O manejar el error de otra forma

        try:
            total_value = float(total_str.replace(',', '.'))
        except ValueError:
            if is_sbb_row:
                print(f"    DEBUG SBB (Fila {idx}): 'Total' ('{total_str}') no es numérico. Usando 0 para lógica de signo.")
            total_value = 0.0

        cantidad_final = cantidad_original # Por defecto

        if current_csv_format == 'ibkr':
            if total_value < 0: # Compra IBKR
                cantidad_final = abs(cantidad_original) 
            elif total_value > 0: # Venta IBKR
                cantidad_final = -abs(cantidad_original)
            
            if is_sbb_row: # Esto no debería ocurrir si SBB es de DeGiro
                print(f"    DEBUG SBB (Fila {idx}): Identificada ERRÓNEAMENTE como 'ibkr'. "
                      f"total_value: {total_value}, cant_orig: {cantidad_original}, cant_final calculada (IBKR logic): {cantidad_final}")
        
        nuevos_numeros.append(cantidad_final)

        if is_sbb_row:
            print(f"    DEBUG SBB (Fila {idx}): Lógica de ajuste en prepare_dataframe_for_portfolio_calculation:")
            print(f"      total_value usado: {total_value}, cantidad_original: {cantidad_original}, "
                  f"cantidad_final a añadir a lista: {cantidad_final}")
            if cantidad_final != cantidad_original and current_csv_format != 'ibkr':
                 print(f"      ALERTA: ¡El valor 'Número' de SBB cambió de {cantidad_original} a {cantidad_final} y no es una fila IBKR!")
            elif cantidad_final == cantidad_original and current_csv_format != 'ibkr':
                 print(f"      INFO: El valor 'Número' de SBB ({current_csv_format}) no cambió: {cantidad_original} -> {cantidad_final}")
            elif current_csv_format == 'ibkr':
                 print(f"      INFO: Fila IBKR. Cantidad original: {cantidad_original}, Cantidad final (ajustada por Total): {cantidad_final}")


    # Asignar la lista completa de nuevos números al DataFrame de una vez
    df_processed['Número'] = nuevos_numeros
    
    # Comprobación final para SBB después de asignar toda la columna
    if stock_isin_to_debug in df_processed['ISIN'].values:
        sbb_final_check_rows = df_processed[df_processed['ISIN'] == stock_isin_to_debug]
        print(f"  DEBUG SBB: Valores FINALES de 'Número' en df_processed para SBB (después de asignar la columna 'nuevos_numeros'):")
        for _, sbb_row_final in sbb_final_check_rows.iterrows():
             print(f"    Fila índice pandas: {sbb_row_final.name}, 'Número': {sbb_row_final['Número']}")
    
    print("DEBUG: Fin de prepare_dataframe_for_portfolio_calculation.")
    return df_processed

def calculate_goal_status_with_model(goal):
    """Calcula estado usando el modelo Goal en lugar de AlertConfiguration."""
    try:
        if goal.goal_type == 'portfolio_percentage':
            return calculate_portfolio_distribution_status(goal)
        elif goal.goal_type == 'target_amount':
            return calculate_fixed_target_status(goal)
        elif goal.goal_type == 'auto_prediction':
            return calculate_auto_prediction_status(goal)
        elif goal.goal_type == 'savings_monthly':
            return calculate_monthly_savings_status(goal)
        elif goal.goal_type == 'debt_threshold':
            return calculate_debt_ceiling_status(goal)
        else:
            return {'error': 'Tipo de objetivo no reconocido'}
    except Exception as e:
        return {'error': f'Error calculando estado: {str(e)}'}

@app.route('/office/delete_goal/<int:goal_id>', methods=['POST'])
@login_required
def delete_goal(goal_id):
    try:
        goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first()
        if goal:
            db.session.delete(goal)
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False})
    except:
        return jsonify({'success': False})


def calculate_auto_prediction_status(goal):
    """Calcula objetivos con predicción automática."""
    try:
        current_value = get_current_asset_value_simple(goal.user_id, goal.goal_asset_type)
        
        # REEMPLAZAR la línea del histórico por estimación simple
        monthly_growth = current_value * 0.02 if current_value > 0 else 100  # 2% crecimiento estimado

        if monthly_growth <= 0:
            return {
                'type': 'auto_prediction',
                'error': 'Sin crecimiento histórico positivo para predicciones',
                'current_value': current_value
            }

        result = {
            'type': 'auto_prediction',
            'prediction_type': goal.prediction_type,
            'current_value': current_value,
            'monthly_growth_avg': monthly_growth,
            'last_calculated': datetime.now()
        }

        if goal.prediction_type == 'amount_to_time':
            # Usuario dice cantidad, programa predice tiempo
            target = goal.target_amount
            amount_needed = target - current_value

            if amount_needed <= 0:
                result.update({
                    'target_amount': target,
                    'progress_percentage': 100,
                    'estimated_months': 0,
                    'estimated_completion': 'Ya completado'
                })
            else:
                months_needed = amount_needed / monthly_growth
                completion_date = (date.today() + timedelta(days=months_needed*30))

                result.update({
                    'target_amount': target,
                    'amount_needed': amount_needed,
                    'progress_percentage': (current_value / target) * 100,
                    'estimated_months': months_needed,
                    'estimated_years': months_needed / 12,
                    'estimated_completion': completion_date.strftime('%B %Y')
                })

        elif goal.prediction_type == 'time_to_amount':
            # Usuario dice tiempo, programa predice cantidad
            months = goal.target_timeframe_months
            estimated_growth = monthly_growth * months
            estimated_final = current_value + estimated_growth

            # Calcular progreso temporal
            months_elapsed = ((date.today().year - goal.start_date.year) * 12 +
                             (date.today().month - goal.start_date.month)) if goal.start_date else 0

            result.update({
                'timeframe_months': months,
                'estimated_final_amount': estimated_final,
                'estimated_growth': estimated_growth,
                'progress_percentage': (months_elapsed / months) * 100 if months > 0 else 0,
                'months_elapsed': months_elapsed,
                'months_remaining': max(0, months - months_elapsed)
            })

        elif goal.prediction_type == 'both':
            # Usuario especifica cantidad Y tiempo - mostrar si es realista
            target = goal.target_amount
            months = goal.target_timeframe_months
            amount_needed = target - current_value
            required_monthly_growth = amount_needed / months if months > 0 else float('inf')

            is_realistic = required_monthly_growth <= monthly_growth * 1.1  # 10% de margen

            months_elapsed = ((date.today().year - goal.start_date.year) * 12 +
                             (date.today().month - goal.start_date.month)) if goal.start_date else 0

            result.update({
                'target_amount': target,
                'timeframe_months': months,
                'amount_needed': amount_needed,
                'required_monthly_growth': required_monthly_growth,
                'is_realistic': is_realistic,
                'progress_percentage': (current_value / target) * 100,
                'time_progress_percentage': (months_elapsed / months) * 100 if months > 0 else 0,
                'months_elapsed': months_elapsed,
                'months_remaining': max(0, months - months_elapsed)
            })

        return result

    except Exception as e:
        return {'error': f'Error en predicción automática: {str(e)}'}

def diagnose_foreign_key_issues():
    """Identifica todas las foreign keys problemáticas."""
    try:
        with app.app_context():
            from sqlalchemy import inspect

            # Obtener todos los modelos de SQLAlchemy
            models = []
            for attr_name in dir():
                attr = globals()[attr_name]
                if hasattr(attr, '__tablename__') and hasattr(attr, '__table__'):
                    models.append((attr_name, attr))

            print("🔍 MODELOS ENCONTRADOS:")
            for name, model in models:
                print(f"  - {name}: {model.__tablename__}")

                # Verificar foreign keys
                if hasattr(model, '__table__'):
                    for fk in model.__table__.foreign_keys:
                        print(f"    FK: {fk.parent.name} -> {fk.target_fullname}")

            return models

    except Exception as e:
        print(f"Error en diagnóstico: {e}")
        return []

def detect_csv_format_simple(file):
    """Detecta formato CSV de manera simple y robusta."""
    try:
        file.seek(0)
        # Leer primeras líneas como bytes y luego decodificar
        first_chunk = file.read(2048)  # Leer primeros 2KB
        
        if isinstance(first_chunk, bytes):
            try:
                content = first_chunk.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = first_chunk.decode('latin-1')
                except:
                    content = str(first_chunk)
        else:
            content = str(first_chunk)
        
        file.seek(0)  # Volver al inicio
        
        # Verificar las primeras líneas
        first_lines = content.split('\n')[:15]  # Verificar más líneas
        
        # Buscar indicadores claros de IBKR
        ibkr_indicators = 0
        for line in first_lines:
            line_lower = line.lower()
            if ('statement,' in line_lower or 
                'operaciones,' in line_lower or 
                'información de instrumento' in line_lower or
                'posiciones abiertas,' in line_lower or
                'valor liquidativo,' in line_lower):
                ibkr_indicators += 1
        
        if ibkr_indicators >= 2:  # Al menos 2 indicadores para estar seguro
            return 'ibkr'
        
        # Buscar indicadores de DeGiro
        degiro_indicators = ['fecha', 'hora', 'producto', 'isin', 'bolsa de', 'número', 'precio']
        for line in first_lines:
            line_lower = line.lower()
            degiro_matches = sum(1 for indicator in degiro_indicators if indicator in line_lower)
            if degiro_matches >= 4:  # Al menos 4 columnas conocidas de DeGiro
                return 'degiro'
        
        # Por defecto, asumir DeGiro
        return 'degiro'
        
    except Exception as e:
        print(f"Error detectando formato: {e}")
        return 'degiro'  # Fallback a DeGiro

def calculate_goal_status_safe(goal):
    """Calcula el estado de un objetivo con manejo seguro de errores."""
    try:
        if goal.goal_type == 'portfolio_percentage':
            return calculate_portfolio_percentage_status_safe(goal)
        elif goal.goal_type == 'target_amount_auto':  # Nuevo tipo
            return calculate_auto_target_status(goal)
        elif goal.goal_type == 'time_prediction':  # Nuevo tipo
            return calculate_time_prediction_status(goal)
        elif goal.goal_type == 'target_amount':
            return calculate_target_amount_status_safe(goal)
        elif goal.goal_type == 'savings_monthly':
            return calculate_savings_monthly_status_safe(goal)
        elif goal.goal_type == 'debt_threshold':
            return calculate_debt_threshold_status_safe(goal)
        else:
            return {'error': 'Tipo de objetivo no reconocido'}
    except Exception as e:
        return {'error': f'Error calculando estado: {str(e)}'}

@app.route('/office/calculate_prediction', methods=['POST'])
@login_required
def calculate_prediction():
    """Calcula predicciones en tiempo real para objetivos."""
    try:
        data = request.get_json()
        prediction_type = data.get('prediction_type')
        asset_type = data.get('asset_type')
        target_amount = data.get('target_amount')
        timeframe_months = data.get('timeframe_months')

        if not prediction_type or not asset_type:
            return jsonify({'success': False, 'message': 'Faltan datos requeridos'})

        # Verificar si hay historial suficiente
        current_value = get_current_asset_value_simple(current_user.id, asset_type)

        # Verificar historial (simplificado - necesitarías implementar esta función)
        has_sufficient_history = check_asset_history(current_user.id, asset_type)

        if not has_sufficient_history:
            return jsonify({
                'success': True,
                'has_history': False,
                'message': 'Sin historial suficiente'
            })

        # Calcular predicción
        if prediction_type == 'amount_to_time':
            if not target_amount:
                return jsonify({'success': False, 'message': 'Falta cantidad objetivo'})

            try:
                target_amount = float(target_amount)
            except ValueError:
                return jsonify({'success': False, 'message': 'Cantidad inválida'})

            # Calcular tiempo necesario
            monthly_growth = current_value * 0.02 if current_value > 0 else 100  # 2% estimado
            amount_needed = target_amount - current_value

            if amount_needed <= 0:
                prediction_html = f"""
                <div class="text-success">
                    <i class="bi bi-check-circle me-2"></i>
                    <strong>¡Meta ya alcanzada!</strong><br>
                    Valor actual: <strong>{current_value:.2f} €</strong><br>
                    Meta: <strong>{target_amount:.2f} €</strong>
                </div>
                """
            else:
                months_needed = amount_needed / monthly_growth if monthly_growth > 0 else 999
                years_needed = months_needed / 12

                completion_date = date.today() + timedelta(days=months_needed*30)

                prediction_html = f"""
                <div class="row">
                    <div class="col-6">
                        <small class="text-muted">Tiempo estimado</small><br>
                        <strong>{months_needed:.1f} meses</strong><br>
                        <small>({years_needed:.1f} años)</small>
                    </div>
                    <div class="col-6">
                        <small class="text-muted">Fecha estimada</small><br>
                        <strong>{completion_date.strftime('%B %Y')}</strong>
                    </div>
                </div>
                <hr class="my-2">
                <div class="small text-muted">
                    <i class="bi bi-info-circle me-1"></i>
                    Basado en crecimiento promedio mensual de {monthly_growth:.2f} €
                </div>
                """

        elif prediction_type == 'time_to_amount':
            if not timeframe_months:
                return jsonify({'success': False, 'message': 'Falta plazo en meses'})

            try:
                timeframe_months = int(timeframe_months)
            except ValueError:
                return jsonify({'success': False, 'message': 'Plazo inválido'})

            # Calcular cantidad estimada
            monthly_growth = current_value * 0.02 if current_value > 0 else 100  # 2% estimado
            estimated_growth = monthly_growth * timeframe_months
            estimated_final = current_value + estimated_growth

            prediction_html = f"""
            <div class="row">
                <div class="col-6">
                    <small class="text-muted">Cantidad estimada</small><br>
                    <strong>{estimated_final:.2f} €</strong>
                </div>
                <div class="col-6">
                    <small class="text-muted">Crecimiento total</small><br>
                    <strong>+{estimated_growth:.2f} €</strong>
                </div>
            </div>
            <hr class="my-2">
            <div class="small text-muted">
                <i class="bi bi-info-circle me-1"></i>
                Basado en crecimiento promedio mensual de {monthly_growth:.2f} €
            </div>
            """

        else:
            return jsonify({'success': False, 'message': 'Tipo de predicción no válido'})

        return jsonify({
            'success': True,
            'has_history': True,
            'prediction_html': prediction_html
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ========================================
# 2. FUNCIÓN PARA VERIFICAR HISTORIAL
# ========================================

def check_asset_history(user_id, asset_type, min_records=2):
    """Verifica si hay suficiente historial para un activo."""
    try:
        if asset_type == 'cash':
            # Verificar registros de cash
            records = CashHistoryRecord.query.filter_by(user_id=user_id).count()
            return records >= min_records

        elif asset_type == 'bolsa':
            # Verificar portfolio histórico
            records = PortfolioHistoryRecord.query.filter_by(user_id=user_id).count()
            return records >= min_records

        elif asset_type == 'crypto':
            # Verificar crypto histórico
            crypto_records = CryptoHistoryRecord.query.filter_by(user_id=user_id).count()
            return crypto_records >= min_records

        # Para otros activos, asumir que hay historial por simplicidad
        return True

    except Exception as e:
        print(f"Error verificando historial de {asset_type}: {e}")
        return False

# ========================================
# 3. VALIDACIONES DE UNICIDAD PARA OBJETIVOS
# ========================================

def validate_goal_uniqueness(form, user_id):
    """Valida que no existan objetivos duplicados según las reglas de unicidad."""
    
    goal_type = form.goal_type.data
    
    if goal_type == 'portfolio_percentage':
        # Solo puede haber UN objetivo de distribución
        existing = Goal.query.filter_by(
            user_id=user_id,
            goal_type='portfolio_percentage',
            is_active=True
        ).first()
        
        if existing:
            return {
                'error': True,
                'message': 'Ya existe un objetivo de Distribución de Activos. Solo puede haber uno activo.'
            }
    
    elif goal_type == 'target_amount':
        # No puede repetir: tipo + asset_type
        asset_type = form.goal_asset_type.data
        existing = Goal.query.filter_by(
            user_id=user_id,
            goal_type='target_amount',
            goal_asset_type=asset_type,
            is_active=True
        ).first()
        
        if existing:
            asset_names = {
                'bolsa': 'Bolsa',
                'cash': 'Efectivo',
                'crypto': 'Criptomonedas',
                'real_estate': 'Inmuebles',
                'metales': 'Metales Preciosos',
                'total_patrimonio': 'Patrimonio Total'
            }
            asset_name = asset_names.get(asset_type, asset_type)
            return {
                'error': True,
                'message': f'Ya existe un objetivo de cantidad fija para {asset_name}.'
            }
    
    elif goal_type == 'auto_prediction':
        # No puede repetir: tipo + prediction_type + asset_type
        prediction_type = form.prediction_type.data
        asset_type = form.goal_asset_type.data
        
        existing = Goal.query.filter_by(
            user_id=user_id,
            goal_type='auto_prediction',
            prediction_type=prediction_type,
            goal_asset_type=asset_type,
            is_active=True
        ).first()
        
        if existing:
            prediction_names = {
                'amount_to_time': 'Predicción de Tiempo',
                'time_to_amount': 'Predicción de Cantidad'
            }
            asset_names = {
                'bolsa': 'Bolsa',
                'cash': 'Efectivo',
                'crypto': 'Criptomonedas',
                'real_estate': 'Inmuebles',
                'metales': 'Metales Preciosos',
                'total_patrimonio': 'Patrimonio Total'
            }
            
            prediction_name = prediction_names.get(prediction_type, prediction_type)
            asset_name = asset_names.get(asset_type, asset_type)
            
            return {
                'error': True,
                'message': f'Ya existe un objetivo de {prediction_name} para {asset_name}.'
            }
    
    elif goal_type == 'savings_monthly':
        # Solo puede haber UNO de ahorro mensual
        existing = Goal.query.filter_by(
            user_id=user_id,
            goal_type='savings_monthly',
            is_active=True
        ).first()
        
        if existing:
            return {
                'error': True,
                'message': 'Ya existe un objetivo de Ahorro Mensual. Solo puede haber uno activo.'
            }
    
    elif goal_type == 'debt_threshold':
        # Solo puede haber UNO de techo de deuda
        existing = Goal.query.filter_by(
            user_id=user_id,
            goal_type='debt_threshold',
            is_active=True
        ).first()
        
        if existing:
            return {
                'error': True,
                'message': 'Ya existe un objetivo de Techo de Deuda. Solo puede haber uno activo.'
            }
    
    return {'error': False}

def generate_automatic_goal_name(form):
    """Genera nombres automáticos para objetivos."""
    
    if form.goal_type.data == 'portfolio_percentage':
        return "Distribución Ideal de Activos"
    
    elif form.goal_type.data == 'target_amount':
        asset_names = {
            'bolsa': 'Bolsa',
            'cash': 'Efectivo',
            'crypto': 'Criptomonedas',
            'real_estate': 'Inmuebles',
            'metales': 'Metales Preciosos',
            'total_patrimonio': 'Patrimonio Total'
        }
        asset_name = asset_names.get(form.goal_asset_type.data, form.goal_asset_type.data)
        return f"Meta de {asset_name}"
    
    elif form.goal_type.data == 'auto_prediction':
        asset_names = {
            'bolsa': 'Bolsa',
            'cash': 'Efectivo',
            'crypto': 'Criptomonedas',
            'real_estate': 'Inmuebles',
            'metales': 'Metales Preciosos',
            'total_patrimonio': 'Patrimonio Total'
        }
        asset_name = asset_names.get(form.goal_asset_type.data, form.goal_asset_type.data)
        
        prediction_names = {
            'amount_to_time': 'Predicción de Tiempo',
            'time_to_amount': 'Predicción de Cantidad'
        }
        prediction_name = prediction_names.get(form.prediction_type.data, form.prediction_type.data)
        
        return f"{prediction_name} en {asset_name}"
    
    elif form.goal_type.data == 'savings_monthly':
        return "Ahorro Mensual"
    
    elif form.goal_type.data == 'debt_threshold':
        return "Techo de Deuda"
    
    else:
        return "Objetivo Personalizado"

def calculate_auto_target_status(goal):
    """Calcula objetivos automáticos - usuario dice cantidad, programa estima tiempo."""
    try:
        asset_type = goal.goal_asset_type
        target_amount = goal.goal_target_amount
        current_value = get_current_asset_value(current_user.id, asset_type)

        # Obtener crecimiento histórico
        historical_data = get_historical_asset_growth(current_user.id, asset_type, months=12)
        monthly_growth = historical_data.get('monthly_avg', 0)

        if monthly_growth <= 0:
            return {
                'type': 'auto_target',
                'error': 'No hay crecimiento histórico positivo para hacer estimaciones'
            }

        # Calcular tiempo estimado
        amount_needed = target_amount - current_value
        if amount_needed <= 0:
            months_needed = 0
            progress_pct = 100
        else:
            months_needed = amount_needed / monthly_growth
            progress_pct = (current_value / target_amount) * 100

        years_needed = months_needed / 12

        return {
            'type': 'auto_target',
            'current_value': current_value,
            'target_amount': target_amount,
            'progress_percentage': min(100, max(0, progress_pct)),
            'amount_needed': max(0, amount_needed),
            'estimated_months': months_needed,
            'estimated_years': years_needed,
            'monthly_growth_avg': monthly_growth,
            'completion_date': (date.today() + timedelta(days=months_needed*30)).strftime('%B %Y') if months_needed > 0 else 'Ya completado',
            'last_calculated': datetime.now()
        }

    except Exception as e:
        return {'error': f'Error en cálculo automático: {str(e)}'}

def calculate_time_prediction_status(goal):
    """Calcula objetivos de predicción - usuario dice tiempo, programa estima cantidad."""
    try:
        asset_type = goal.goal_asset_type
        timeframe_months = goal.goal_target_timeframe_months
        current_value = get_current_asset_value(current_user.id, asset_type)
        
        # Obtener crecimiento histórico
        historical_data = get_historical_asset_growth(current_user.id, asset_type, months=12)
        monthly_growth = historical_data.get('monthly_avg', 0)
        
        # Calcular cantidad estimada
        estimated_growth = monthly_growth * timeframe_months
        estimated_final_value = current_value + estimated_growth
        
        # Calcular progreso (tiempo transcurrido)
        months_elapsed = ((date.today().year - goal.start_date.year) * 12 + 
                         (date.today().month - goal.start_date.month)) if goal.start_date else 0
        progress_pct = (months_elapsed / timeframe_months) * 100 if timeframe_months > 0 else 0
        
        return {
            'type': 'time_prediction',
            'current_value': current_value,
            'timeframe_months': timeframe_months,
            'estimated_final_value': estimated_final_value,
            'estimated_growth': estimated_growth,
            'progress_percentage': min(100, max(0, progress_pct)),
            'months_elapsed': months_elapsed,
            'months_remaining': max(0, timeframe_months - months_elapsed),
            'monthly_growth_avg': monthly_growth,
            'target_date': (goal.start_date + timedelta(days=timeframe_months*30)).strftime('%B %Y') if goal.start_date else 'No definida',
            'last_calculated': datetime.now()
        }
        
    except Exception as e:
        return {'error': f'Error en predicción temporal: {str(e)}'}

def validate_goal_prerequisites_updated(form):
    """Validaciones actualizadas para prerrequisitos de objetivos."""

    if form.goal_type.data == 'debt_threshold':
        # Verificar que tenga salario configurado
        income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
        if not income_data or not income_data.annual_net_salary:
            return {
                'message': 'Para crear objetivos de techo de deuda necesitas configurar tu salario neto anual. '
                          f'<a href="{url_for("fixed_income")}" class="alert-link">Configurar Salario</a>',
                'type': 'validation_error'
            }

    elif form.goal_type.data in ['target_amount', 'auto_prediction', 'savings_monthly']:
        # Para predicciones automáticas, verificar historial si es necesario
        if form.goal_type.data == 'auto_prediction':
            asset_type = form.goal_asset_type.data
            if asset_type and not check_asset_history(current_user.id, asset_type):
                return {
                    'message': f'Para predicciones automáticas en {asset_type} necesitas más historial. '
                              'El objetivo se creará pero las predicciones se mostrarán cuando tengas más datos.',
                    'type': 'info'
                }

    return None  # Sin errores

def calculate_days_until_next_alert(alert_config):
    """Calcula cuántos días faltan para que salte la próxima alerta."""
    try:
        today = date.today()
        
        if alert_config.alert_reason == 'objetivo':
            if alert_config.goal_alert_day_of_month:
                # Alerta mensual en día específico
                try:
                    next_alert_date = date(today.year, today.month, alert_config.goal_alert_day_of_month)
                    if next_alert_date <= today:
                        # Si ya pasó este mes, calcular para el próximo
                        if today.month == 12:
                            next_alert_date = date(today.year + 1, 1, alert_config.goal_alert_day_of_month)
                        else:
                            next_alert_date = date(today.year, today.month + 1, alert_config.goal_alert_day_of_month)
                    
                    days_remaining = (next_alert_date - today).days
                    return days_remaining
                except ValueError:
                    # Día inválido para el mes (ej: 31 en febrero)
                    return None
        
        elif alert_config.alert_reason == 'earnings_report':
            # Para alertas de resultados, buscar próxima fecha
            if alert_config.watchlist_item and alert_config.watchlist_item.fecha_resultados:
                earnings_date = alert_config.watchlist_item.fecha_resultados
                alert_date = earnings_date - timedelta(days=alert_config.days_notice)
                if alert_date > today:
                    return (alert_date - today).days
        
        elif alert_config.alert_reason == 'periodic_summary':
            if alert_config.summary_one_time_date:
                if alert_config.summary_one_time_date > today:
                    return (alert_config.summary_one_time_date - today).days
        
        elif alert_config.alert_reason == 'custom':
            if alert_config.custom_start_date:
                if alert_config.custom_start_date > today:
                    return (alert_config.custom_start_date - today).days
        
        return None  # No se puede calcular
        
    except Exception as e:
        print(f"Error calculando días restantes para alerta {alert_config.id}: {e}")
        return None

@app.route('/office/alert_details/<int:alert_id>', methods=['GET'])
@login_required
def alert_details(alert_id):
    """Obtiene detalles de una alerta específica."""
    try:
        alert = AlertConfiguration.query.filter_by(id=alert_id, user_id=current_user.id).first()
        if not alert:
            return jsonify({'success': False, 'message': 'Alerta no encontrada'})
        
        # Generar HTML con detalles
        html_content = f"""
        <div class="alert-details">
            <h6>Información General</h6>
            <p><strong>Tipo:</strong> {alert.alert_reason.replace('_', ' ').title()}</p>
            <p><strong>Creada:</strong> {alert.created_at.strftime('%d/%m/%Y %H:%M')}</p>
            <p><strong>Email:</strong> {'Sí' if alert.notify_by_email else 'No'}</p>
        """
        
        # Detalles específicos según tipo
        if alert.alert_reason == 'earnings_report':
            html_content += f"""
            <h6>Configuración de Resultados</h6>
            <p><strong>Alcance:</strong> {alert.scope.title() if alert.scope else 'No definido'}</p>
            <p><strong>Días de antelación:</strong> {alert.days_notice}</p>
            <p><strong>Frecuencia:</strong> {alert.frequency or 'No definida'}</p>
            """
            if alert.watchlist_item:
                html_content += f"<p><strong>Acción:</strong> {alert.watchlist_item.item_name or alert.watchlist_item.ticker}</p>"
        
        elif alert.alert_reason == 'metric_threshold':
            html_content += f"""
            <h6>Configuración de Métrica</h6>
            <p><strong>Métrica:</strong> {alert.metric_name or 'No definida'}</p>
            <p><strong>Condición:</strong> {alert.metric_operator or 'No definida'}</p>
            <p><strong>Valor objetivo:</strong> {alert.metric_target_value or alert.metric_target_text or 'No definido'}</p>
            """
            if alert.watchlist_item:
                html_content += f"<p><strong>Acción:</strong> {alert.watchlist_item.item_name or alert.watchlist_item.ticker}</p>"
        
        elif alert.alert_reason == 'periodic_summary':
            html_content += f"""
            <h6>Configuración de Resumen</h6>
            <p><strong>Tipo:</strong> {alert.summary_type.title() if alert.summary_type else 'No definido'}</p>
            <p><strong>Frecuencia:</strong> {alert.summary_frequency or 'Puntual'}</p>
            """
            if alert.summary_one_time_date:
                html_content += f"<p><strong>Fecha:</strong> {alert.summary_one_time_date.strftime('%d/%m/%Y')}</p>"
        
        elif alert.alert_reason == 'objetivo':
            html_content += f"""
            <h6>Configuración de Objetivo</h6>
            <p><strong>Nombre:</strong> {alert.goal_name or 'Sin nombre'}</p>
            <p><strong>Tipo:</strong> {alert.goal_type.replace('_', ' ').title() if alert.goal_type else 'No definido'}</p>
            """
            if alert.goal_alert_day_of_month:
                html_content += f"<p><strong>Día de alerta:</strong> {alert.goal_alert_day_of_month} de cada mes</p>"
        
        elif alert.alert_reason == 'custom':
            html_content += f"""
            <h6>Configuración Personalizada</h6>
            <p><strong>Título:</strong> {alert.custom_title or 'Sin título'}</p>
            """
            if alert.custom_description:
                html_content += f"<p><strong>Descripción:</strong> {alert.custom_description}</p>"
            if alert.custom_start_date:
                html_content += f"<p><strong>Fecha inicio:</strong> {alert.custom_start_date.strftime('%d/%m/%Y')}</p>"
        
        # Días restantes
        days_remaining = calculate_days_until_next_alert(alert)
        if days_remaining is not None:
            if days_remaining == 0:
                html_content += f"<p><strong>Próxima ejecución:</strong> <span class='text-danger'>Hoy</span></p>"
            elif days_remaining == 1:
                html_content += f"<p><strong>Próxima ejecución:</strong> <span class='text-warning'>Mañana</span></p>"
            else:
                html_content += f"<p><strong>Próxima ejecución:</strong> En {days_remaining} días</p>"
        
        html_content += "</div>"
        
        return jsonify({'success': True, 'html': html_content})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# 3. FUNCIONES AUXILIARES PARA OBTENER DATOS (agregar en app.py)
def get_current_patrimony_breakdown(user_id):
    """Obtiene el desglose actual del patrimonio por tipo de activo."""
    try:
        # Obtener datos usando la lógica existente de financial_summary
        # Simular el llamado a la lógica de financial_summary
        
        # Efectivo (Cash)
        bank_accounts = BankAccount.query.filter_by(user_id=user_id).all()
        cash_total = sum(account.current_balance for account in bank_accounts) if bank_accounts else 0
        
        # Inversiones (Bolsa)
        portfolio_record = UserPortfolio.query.filter_by(user_id=user_id).first()
        bolsa_total = 0
        if portfolio_record and portfolio_record.portfolio_data:
            portfolio_data = json.loads(portfolio_record.portfolio_data)
            bolsa_total = sum(float(item.get('market_value_eur', 0)) for item in portfolio_data 
                            if 'market_value_eur' in item and item['market_value_eur'] is not None)
        
        # Criptomonedas
        crypto_transactions = CryptoTransaction.query.filter_by(user_id=user_id).all()
        crypto_total = 0
        if crypto_transactions:
            crypto_holdings = {}
            for transaction in crypto_transactions:
                crypto_key = transaction.ticker_symbol
                if crypto_key not in crypto_holdings:
                    crypto_holdings[crypto_key] = {'quantity': 0, 'current_price': transaction.current_price}
                
                if transaction.transaction_type == 'buy':
                    crypto_holdings[crypto_key]['quantity'] += transaction.quantity
                else:
                    crypto_holdings[crypto_key]['quantity'] -= transaction.quantity
                
                if transaction.current_price is not None:
                    crypto_holdings[crypto_key]['current_price'] = transaction.current_price
            
            crypto_total = sum(crypto['quantity'] * crypto['current_price'] 
                             for crypto in crypto_holdings.values() 
                             if crypto['quantity'] > 0 and crypto['current_price'] is not None)
        
        # Inmuebles
        real_estate_assets = RealEstateAsset.query.filter_by(user_id=user_id).all()
        real_estate_total = sum(asset.current_market_value for asset in real_estate_assets) if real_estate_assets else 0
        
        # Metales preciosos
        gold_record = PreciousMetalPrice.query.filter_by(metal_type='gold').first()
        silver_record = PreciousMetalPrice.query.filter_by(metal_type='silver').first()
        gold_price = gold_record.price_eur_per_oz if gold_record else 0
        silver_price = silver_record.price_eur_per_oz if silver_record else 0
        
        metal_transactions = PreciousMetalTransaction.query.filter_by(user_id=user_id).all()
        metales_total = 0
        if metal_transactions:
            g_to_oz = 0.0321507466
            gold_oz = silver_oz = 0
            
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
            
            metales_total = (gold_oz * gold_price) + (silver_oz * silver_price)
        
        total_assets = cash_total + bolsa_total + crypto_total + real_estate_total + metales_total
        
        return {
            'cash': cash_total,
            'bolsa': bolsa_total,
            'crypto': crypto_total,
            'real_estate': real_estate_total,
            'metales': metales_total,
            'total_assets': total_assets
        }
        
    except Exception as e:
        print(f"Error obteniendo desglose de patrimonio: {e}")
        return {
            'cash': 0, 'bolsa': 0, 'crypto': 0, 'real_estate': 0, 'metales': 0, 'total_assets': 0
        }

def get_current_asset_value(user_id, asset_type):
    """Obtiene el valor actual de un tipo específico de activo."""
    patrimony = get_current_patrimony_breakdown(user_id)
    
    if asset_type == 'total_patrimonio':
        return patrimony['total_assets']
    elif asset_type == 'salario':
        income_data = FixedIncome.query.filter_by(user_id=user_id).first()
        return income_data.annual_net_salary if income_data else 0
    else:
        return patrimony.get(asset_type, 0)

def get_historical_asset_growth(user_id, asset_type, months=3):
    """Obtiene el crecimiento histórico promedio de un activo."""
    try:
        if asset_type == 'cash':
            # Obtener historial de efectivo
            history_records = CashHistoryRecord.query.filter_by(user_id=user_id)\
                .filter(CashHistoryRecord.record_date >= date.today() - timedelta(days=months*30))\
                .order_by(CashHistoryRecord.record_date.desc()).all()
            
            if len(history_records) >= 2:
                latest_value = history_records[0].total_cash
                oldest_value = history_records[-1].total_cash
                months_diff = len(history_records) / 4  # Aproximadamente semanal
                monthly_growth = (latest_value - oldest_value) / months_diff if months_diff > 0 else 0
                return {'monthly_avg': monthly_growth}
        
        # Para otros activos, implementar lógica similar
        return {'monthly_avg': 0}
        
    except Exception as e:
        print(f"Error obteniendo crecimiento histórico: {e}")
        return {'monthly_avg': 0}

def get_friendly_goal_name(goal):
    """Genera nombres amigables para objetivos automáticamente."""
    
    if goal.goal_type == 'portfolio_percentage':
        return "Distribución Ideal de Activos"
    
    elif goal.goal_type == 'target_amount':
        asset_names = {
            'bolsa': 'Bolsa',
            'cash': 'Efectivo',
            'crypto': 'Criptomonedas',
            'real_estate': 'Inmuebles',
            'metales': 'Metales Preciosos',
            'total_patrimonio': 'Patrimonio Total',
            'salario': 'Salario'
        }
        asset_name = asset_names.get(goal.goal_asset_type, goal.goal_asset_type)
        return f"Meta de {asset_name}"
    
    elif goal.goal_type == 'auto_prediction':
        asset_names = {
            'bolsa': 'Bolsa',
            'cash': 'Efectivo',
            'crypto': 'Criptomonedas',
            'real_estate': 'Inmuebles',
            'metales': 'Metales Preciosos',
            'total_patrimonio': 'Patrimonio Total'
        }
        asset_name = asset_names.get(goal.goal_asset_type, goal.goal_asset_type)
        
        prediction_names = {
            'amount_to_time': 'Predicción de Tiempo',
            'time_to_amount': 'Predicción de Cantidad'
        }
        prediction_name = prediction_names.get(goal.prediction_type, goal.prediction_type)
        
        return f"{prediction_name} en {asset_name}"
    
    elif goal.goal_type == 'savings_monthly':
        return "Ahorro Mensual"
    
    elif goal.goal_type == 'debt_threshold':
        return "Techo de Deuda"
    
    else:
        return "Objetivo Personalizado"

@app.route('/office/send_report_by_email', methods=['POST'])
@login_required
def send_report_by_email():
    """Envía informes por correo electrónico al buzón virtual y al email del usuario."""
    try:
        report_type = request.form.get('report_type', 'complete')
        
        # Generar datos del informe
        export_data = generate_custom_report_data(current_user.id, report_type)
        
        if not export_data:
            return jsonify({'success': False, 'message': 'No hay datos para generar el informe'})
        
        # Crear contenido HTML del informe
        report_html = generate_report_html(export_data, report_type)
        
        # Crear contenido de texto plano
        report_text = generate_report_text(export_data, report_type)
        
        # Obtener título del informe
        report_titles = {
            'complete': 'Informe Completo de Patrimonio',
            'bolsa': 'Informe de Inversiones (Bolsa)',
            'cash': 'Informe de Efectivo (Cuentas Bancarias)',
            'crypto': 'Informe de Criptomonedas',
            'real_estate': 'Informe de Inmuebles',
            'metales': 'Informe de Metales Preciosos',
            'debts': 'Informe de Deudas',
            'income_expenses': 'Informe de Ingresos y Gastos'
        }
        report_title = report_titles.get(report_type, 'Informe Personalizado')
        
        # 1. Crear mensaje en el buzón virtual
        mailbox_message = MailboxMessage(
            user_id=current_user.id,
            message_type='periodic_summary',
            title=f'📊 {report_title}',
            content=report_text[:500] + '...' if len(report_text) > 500 else report_text
        )
        db.session.add(mailbox_message)
        
        # 2. Enviar email al usuario (si tiene email configurado)
        if current_user.email:
            try:
                msg = Message(
                    subject=f'FollowUp - {report_title}',
                    recipients=[current_user.email]
                )
                
                # Contenido de texto plano
                msg.body = f"""Hola {current_user.username},

Adjunto encontrarás tu {report_title.lower()} generado automáticamente.

{report_text}

Este informe ha sido generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}.

Puedes acceder a más informes y configurar alertas en tu panel de control: {url_for('office_mailbox', _external=True)}

Saludos,
FollowUp App"""

                # Contenido HTML
                msg.html = f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
                        .content {{ padding: 20px; }}
                        .report-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                        .report-table th, .report-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                        .report-table th {{ background-color: #f8f9fa; font-weight: bold; }}
                        .highlight {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                        .footer {{ background-color: #f8f9fa; padding: 15px; text-align: center; font-size: 0.9em; color: #666; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>📊 {report_title}</h1>
                        <p>Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
                    </div>
                    <div class="content">
                        <p>Hola <strong>{current_user.username}</strong>,</p>
                        <p>Adjunto encontrarás tu {report_title.lower()} generado automáticamente.</p>
                        
                        <div class="highlight">
                            <h3>📈 Resumen del Informe</h3>
                            {report_html}
                        </div>
                        
                        <p>Puedes acceder a más informes y configurar alertas en tu <a href="{url_for('office_mailbox', _external=True)}">panel de control</a>.</p>
                    </div>
                    <div class="footer">
                        <p>Este mensaje fue generado automáticamente por FollowUp App</p>
                    </div>
                </body>
                </html>
                """
                
                mail.send(msg)
                app.logger.info(f"Informe {report_type} enviado por email a {current_user.email}")
                
            except Exception as e:
                app.logger.error(f"Error enviando email del informe: {e}")
                # No fallar si el email falla, el mensaje del buzón ya se creó
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Informe enviado correctamente. Revisa tu buzón virtual y tu email.'
        })
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error en send_report_by_email: {e}")
        return jsonify({'success': False, 'message': f'Error al enviar informe: {str(e)}'})


def generate_report_html(export_data, report_type):
    """Genera contenido HTML del informe para email."""
    if not export_data:
        return "<p>No hay datos disponibles para este informe.</p>"
    
    html = "<table class='report-table'>\n"
    
    # Encabezados (primera fila)
    if export_data:
        html += "<thead><tr>\n"
        for header in export_data[0]:
            html += f"<th>{header}</th>\n"
        html += "</tr></thead>\n"
        
        # Datos (resto de filas)
        html += "<tbody>\n"
        for row in export_data[1:]:  # Saltar encabezados
            html += "<tr>\n"
            for cell in row:
                html += f"<td>{cell}</td>\n"
            html += "</tr>\n"
        html += "</tbody>\n"
    
    html += "</table>\n"
    
    return html


def generate_report_text(export_data, report_type):
    """Genera contenido de texto plano del informe para email."""
    if not export_data:
        return "No hay datos disponibles para este informe."
    
    text = f"INFORME: {report_type.upper()}\n"
    text += "=" * 50 + "\n\n"
    
    if export_data:
        # Calcular ancho de columnas
        col_widths = []
        for i in range(len(export_data[0])):
            max_width = max(len(str(row[i])) if i < len(row) else 0 for row in export_data)
            col_widths.append(min(max_width + 2, 20))  # Máximo 20 caracteres por columna
        
        # Generar tabla de texto
        for row_idx, row in enumerate(export_data):
            line = ""
            for col_idx, cell in enumerate(row):
                if col_idx < len(col_widths):
                    cell_str = str(cell)[:col_widths[col_idx]-2]  # Truncar si es muy largo
                    line += cell_str.ljust(col_widths[col_idx])
            text += line + "\n"
            
            # Línea separadora después de encabezados
            if row_idx == 0:
                text += "-" * sum(col_widths) + "\n"
    
    text += "\n" + "=" * 50 + "\n"
    text += f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
    
    return text

def validate_filename_format_flexible(filename):
    """Validación de archivo más flexible que acepta tanto DeGiro como IBKR."""
    if not filename or not filename.lower().endswith('.csv'):
        return False
    
    # Permitir formato AAAA.csv para DeGiro
    if re.match(r"^\d{4}\.csv$", filename):
        return True
    
    # Permitir nombres de IBKR típicos (empiezan con U y contienen números)
    if re.match(r"^U\d+_\d{8}_\d{8}\.csv$", filename):
        return True
    
    # Permitir otros nombres válidos sin caracteres peligrosos
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    if any(char in filename for char in dangerous_chars):
        return False
    
    return len(filename) <= 255


def prepare_processed_dataframe(combined_df_raw, errors):
    """Prepara el DataFrame procesado aplicando las transformaciones necesarias."""
    try:
        # Determinar si necesitamos aplicar renombrado de columnas (solo para DeGiro)
        cols_to_rename_present = [col for col in COLS_MAP.keys() if col in combined_df_raw.columns]
        
        if cols_to_rename_present:
            # Aplicar renombrado de columnas de DeGiro
            filtered_df = combined_df_raw[cols_to_rename_present].copy()
            renamed = filtered_df.rename(columns=COLS_MAP)
        else:
            # Para IBKR, las columnas ya están en el formato correcto
            renamed = combined_df_raw.copy()
        
        # Añadir Exchange Yahoo si no existe pero tenemos datos de Bolsa
        if 'Bolsa' in renamed.columns and 'Exchange Yahoo' not in renamed.columns:
            renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna('')
        elif 'Bolsa de' in renamed.columns and 'Exchange Yahoo' not in renamed.columns:
            # Para datos que vienen de IBKR
            renamed['Exchange Yahoo'] = renamed['Bolsa de'].map(get_yahoo_suffix_mapping()).fillna('')
        
        # Convertir columnas numéricas
        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    # Limpieza de strings antes de convertir a numérico
                    cleaned_series = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False)
                    renamed[col] = pd.to_numeric(cleaned_series, errors='coerce')

                if pd.api.types.is_numeric_dtype(renamed[col]) or renamed[col].isnull().any():
                    renamed[col] = renamed[col].fillna(0)

                if col == 'Cantidad':
                    if pd.api.types.is_numeric_dtype(renamed[col]):
                        renamed[col] = renamed[col].abs()  # Cantidad siempre positiva

                if pd.api.types.is_numeric_dtype(renamed[col]):
                    renamed[col] = renamed[col].astype(float)
        
        return renamed
        
    except Exception as e:
        error_msg = f"Error preparando DataFrame procesado: {e}"
        print(error_msg)
        errors.append(error_msg)
        return combined_df_raw


def get_yahoo_suffix_mapping():
    """Obtiene el mapeo de mercados IBKR a sufijos Yahoo."""
    return {
        'NASDAQ': '', 'NYSE': '', 'SEHK': '.HK', 'TSE': '.TO', 'LSE': '.L',
        'SGX': '.SI', 'OMXNO': '.OL', 'GETTEX2': '.DE', 'BATS': '',
        'ARCA': '', 'ISLAND': '', 'IBIS2': '.DE', 'LSEIOB1': '.L',
        'DRCTEDGE': '', 'IBKR': '', 'IBKRATS': '', 'TSXDARK': '.TO',
        'TRIACT': '.TO', 'ALPHA': '.TO', 'CAIBFRSH': '.TO'
    }


def validate_goal_prerequisites(form):
    """Valida que el usuario tenga los datos necesarios para crear el objetivo."""
    
    if form.goal_type.data == 'debt_threshold':
        # Verificar que tenga salario configurado
        income_data = FixedIncome.query.filter_by(user_id=current_user.id).first()
        if not income_data or not income_data.annual_net_salary:
            return {
                'message': 'Para crear objetivos de techo de deuda necesitas configurar tu salario neto anual. '
                          f'<a href="{url_for("fixed_income")}" class="alert-link">Configurar Salario</a>',
                'type': 'validation_error'
            }
    
    elif form.goal_type.data in ['target_amount', 'auto_prediction', 'savings_monthly']:
        # Verificar que tenga datos históricos suficientes para predicciones
        if form.goal_asset_type.data == 'cash':
            cash_records = CashHistoryRecord.query.filter_by(user_id=current_user.id).count()
            if cash_records < 2:
                return {
                    'message': 'Para objetivos basados en efectivo necesitas al menos 2 registros históricos. '
                              f'<a href="{url_for("bank_accounts")}" class="alert-link">Gestionar Cuentas</a>',
                    'type': 'validation_error'
                }
    
    return None  # Sin errores

def calculate_portfolio_distribution_status(goal):
    """Calcula distribución de patrimonio usando modelo Goal."""
    try:
        if not goal.asset_distribution:
            return {'error': 'Sin configuración de distribución'}
        
        target_percentages = json.loads(goal.asset_distribution)
        patrimony = get_current_patrimony_breakdown_simple(goal.user_id)
        total_assets = patrimony.get('total_assets', 0)
        
        if total_assets <= 0:
            return {'error': 'Sin patrimonio suficiente'}
        
        gaps = {}
        overall_progress = 0
        
        for asset_type, target_pct in target_percentages.items():
            if target_pct > 0:
                current_value = patrimony.get(asset_type, 0)
                current_pct = (current_value / total_assets) * 100
                gap_pct = target_pct - current_pct
                
                gaps[asset_type] = {
                    'target_percentage': target_pct,
                    'current_percentage': current_pct,
                    'percentage_gap': gap_pct,
                    'current_value': current_value
                }
                
                # Calcular progreso: qué tan cerca está del objetivo
                if target_pct > 0:
                    asset_progress = min(100, (current_pct / target_pct) * 100)
                    overall_progress += asset_progress * (target_pct / 100)  # Ponderado
        
        return {
            'type': 'portfolio_percentage',
            'total_assets': total_assets,
            'gaps': gaps,
            'progress_percentage': min(100, overall_progress)
        }
        
    except Exception as e:
        return {'error': f'Error en distribución: {str(e)}'}

def calculate_fixed_target_status(goal):
    """Calcula objetivo de cantidad fija usando modelo Goal."""
    try:
        target_amount = goal.target_amount or 0
        current_value = get_current_asset_value_simple(goal.user_id, goal.goal_asset_type)

        progress_pct = (current_value / target_amount) * 100 if target_amount > 0 else 0
        amount_needed = max(0, target_amount - current_value)

        # Calcular tiempo
        timeframe_months = goal.target_timeframe_months or 12
        start_date = goal.start_date or goal.created_at.date()
        today = date.today()
        months_elapsed = ((today.year - start_date.year) * 12 + (today.month - start_date.month))
        months_remaining = max(0, timeframe_months - months_elapsed)

        # Crecimiento necesario
        monthly_growth_needed = amount_needed / months_remaining if months_remaining > 0 else 0

        return {
            'type': 'target_amount',
            'current_value': current_value,
            'target_amount': target_amount,
            'progress_percentage': min(100, progress_pct),
            'amount_needed': amount_needed,
            'months_remaining': months_remaining,
            'monthly_growth_needed': monthly_growth_needed
        }

    except Exception as e:
        return {'error': f'Error en objetivo cantidad: {str(e)}'}

def calculate_monthly_savings_status(goal):
    """Calcula ahorro mensual usando modelo Goal."""
    try:
        monthly_target = goal.monthly_savings_target or 0
        start_date = goal.start_date or goal.created_at.date()
        current_cash = get_current_asset_value_simple(goal.user_id, 'cash')

        # Calcular meses transcurridos
        today = date.today()
        months_elapsed = ((today.year - start_date.year) * 12 + (today.month - start_date.month)) + 1

        # Objetivo acumulado
        cumulative_target = monthly_target * months_elapsed

        # Progreso simplificado (asumiendo que partió de 0)
        progress_pct = min(100, (current_cash / cumulative_target) * 100) if cumulative_target > 0 else 0

        return {
            'type': 'savings_monthly',
            'monthly_target': monthly_target,
            'current_cash': current_cash,
            'months_elapsed': months_elapsed,
            'cumulative_target': cumulative_target,
            'actual_savings': current_cash,  # Simplificado
            'progress_percentage': progress_pct,
            'current_month_savings': 0,  # Simplificado
            'current_month_gap': monthly_target  # Simplificado
        }

    except Exception as e:
        return {'error': f'Error en ahorro mensual: {str(e)}'}

def calculate_debt_ceiling_status(goal):
    """Calcula techo de deuda usando modelo Goal."""
    try:
        target_percentage = goal.debt_ceiling_percentage or 0
        
        # Obtener datos de deuda
        income_data = FixedIncome.query.filter_by(user_id=goal.user_id).first()
        monthly_salary = (income_data.annual_net_salary / 12) if income_data and income_data.annual_net_salary else 0
        
        debt_plans = DebtInstallmentPlan.query.filter_by(user_id=goal.user_id, is_active=True).all()
        monthly_debt_payment = sum(plan.monthly_payment for plan in debt_plans) if debt_plans else 0
        
        current_debt_percentage = (monthly_debt_payment / monthly_salary * 100) if monthly_salary > 0 else 0
        
        target_debt_amount = (target_percentage / 100) * monthly_salary
        debt_margin = target_debt_amount - monthly_debt_payment
        is_over_limit = current_debt_percentage > target_percentage
        
        return {
            'type': 'debt_threshold',
            'target_debt_percentage': target_percentage,
            'current_debt_percentage': current_debt_percentage,
            'monthly_salary': monthly_salary,
            'target_debt_amount': target_debt_amount,
            'current_debt_payment': monthly_debt_payment,
            'debt_margin': debt_margin,
            'is_over_limit': is_over_limit,
            'utilization_percentage': (monthly_debt_payment / target_debt_amount) * 100 if target_debt_amount > 0 else 0
        }
        
    except Exception as e:
        return {'error': f'Error en techo de deuda: {str(e)}'}

def get_current_patrimony_breakdown_simple(user_id):
    """Obtiene desglose básico del patrimonio."""
    try:
        # Efectivo
        bank_accounts = BankAccount.query.filter_by(user_id=user_id).all()
        cash_total = sum(account.current_balance for account in bank_accounts) if bank_accounts else 0
        
        # Inversiones
        portfolio_record = UserPortfolio.query.filter_by(user_id=user_id).first()
        bolsa_total = 0
        if portfolio_record and portfolio_record.portfolio_data:
            try:
                portfolio_data = json.loads(portfolio_record.portfolio_data)
                bolsa_total = sum(float(item.get('market_value_eur', 0)) for item in portfolio_data 
                                if 'market_value_eur' in item and item['market_value_eur'] is not None)
            except:
                bolsa_total = 0
        
        # Criptomonedas (simplificado por ahora)
        crypto_total = 0
        try:
            crypto_transactions = CryptoTransaction.query.filter_by(user_id=user_id).all()
            if crypto_transactions:
                crypto_holdings = {}
                for transaction in crypto_transactions:
                    crypto_key = transaction.ticker_symbol
                    if crypto_key not in crypto_holdings:
                        crypto_holdings[crypto_key] = {'quantity': 0, 'current_price': transaction.current_price or 0}
                    
                    if transaction.transaction_type == 'buy':
                        crypto_holdings[crypto_key]['quantity'] += transaction.quantity
                    else:
                        crypto_holdings[crypto_key]['quantity'] -= transaction.quantity
                    
                    if transaction.current_price is not None:
                        crypto_holdings[crypto_key]['current_price'] = transaction.current_price
                
                crypto_total = sum(crypto['quantity'] * crypto['current_price'] 
                                 for crypto in crypto_holdings.values() 
                                 if crypto['quantity'] > 0 and crypto['current_price'] is not None)
        except:
            crypto_total = 0
        
        # Inmuebles
        real_estate_total = 0
        try:
            real_estate_assets = RealEstateAsset.query.filter_by(user_id=user_id).all()
            real_estate_total = sum(asset.current_market_value for asset in real_estate_assets) if real_estate_assets else 0
        except:
            real_estate_total = 0
        
        # Metales (simplificado por ahora)
        metales_total = 0
        
        total_assets = cash_total + bolsa_total + crypto_total + real_estate_total + metales_total
        
        return {
            'cash': cash_total,
            'bolsa': bolsa_total,
            'crypto': crypto_total,
            'real_estate': real_estate_total,
            'metales': metales_total,
            'total_assets': total_assets
        }
        
    except Exception as e:
        print(f"Error obteniendo patrimonio: {e}")
        return {'cash': 0, 'bolsa': 0, 'crypto': 0, 'real_estate': 0, 'metales': 0, 'total_assets': 0}

def get_current_asset_value_simple(user_id, asset_type):
    """Obtiene valor actual de un activo."""
    patrimony = get_current_patrimony_breakdown_simple(user_id)

    if asset_type == 'total_patrimonio':
        return patrimony['total_assets']
    elif asset_type == 'salario':
        try:
            income_data = FixedIncome.query.filter_by(user_id=user_id).first()
            return income_data.annual_net_salary if income_data else 0
        except:
            return 0
    else:
        return patrimony.get(asset_type, 0)


def detect_csv_format_simple(file):
    """Detecta formato CSV de manera simple y robusta."""
    try:
        file.seek(0)
        # Leer primeras líneas como bytes y luego decodificar
        first_chunk = file.read(2048)  # Leer primeros 2KB
        
        if isinstance(first_chunk, bytes):
            try:
                content = first_chunk.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = first_chunk.decode('latin-1')
                except:
                    content = str(first_chunk)
        else:
            content = str(first_chunk)
        
        file.seek(0)  # Volver al inicio
        
        # Verificar las primeras líneas
        first_lines = content.split('\n')[:15]  # Verificar más líneas
        
        # Buscar indicadores claros de IBKR
        ibkr_indicators = 0
        for line in first_lines:
            line_lower = line.lower()
            if ('statement,' in line_lower or 
                'operaciones,' in line_lower or 
                'información de instrumento' in line_lower or
                'posiciones abiertas,' in line_lower or
                'valor liquidativo,' in line_lower):
                ibkr_indicators += 1
        
        if ibkr_indicators >= 2:  # Al menos 2 indicadores para estar seguro
            return 'ibkr'
        
        # Buscar indicadores de DeGiro
        degiro_indicators = ['fecha', 'hora', 'producto', 'isin', 'bolsa de', 'número', 'precio']
        for line in first_lines:
            line_lower = line.lower()
            degiro_matches = sum(1 for indicator in degiro_indicators if indicator in line_lower)
            if degiro_matches >= 4:  # Al menos 4 columnas conocidas de DeGiro
                return 'degiro'
        
        # Por defecto, asumir DeGiro
        return 'degiro'
        
    except Exception as e:
        print(f"Error detectando formato: {e}")
        return 'degiro'  # Fallback a DeGiro


def validate_filename_format_flexible(filename):
    """Validación de archivo más flexible que acepta tanto DeGiro como IBKR."""
    if not filename or not filename.lower().endswith('.csv'):
        return False
    
    # Permitir formato AAAA.csv para DeGiro
    if re.match(r"^\d{4}\.csv$", filename):
        return True
    
    # Permitir nombres de IBKR típicos (empiezan con U y contienen números)
    if re.match(r"^U\d+_\d{8}_\d{8}\.csv$", filename):
        return True
    
    # Permitir otros nombres válidos sin caracteres peligrosos
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    if any(char in filename for char in dangerous_chars):
        return False
    
    return len(filename) <= 255





def prepare_processed_dataframe(combined_df_raw, errors):
    """Prepara el DataFrame procesado aplicando las transformaciones necesarias."""
    try:
        # Determinar si necesitamos aplicar renombrado de columnas (solo para DeGiro)
        cols_to_rename_present = [col for col in COLS_MAP.keys() if col in combined_df_raw.columns]
        
        if cols_to_rename_present:
            # Aplicar renombrado de columnas de DeGiro
            filtered_df = combined_df_raw[cols_to_rename_present].copy()
            renamed = filtered_df.rename(columns=COLS_MAP)
        else:
            # Para IBKR, las columnas ya están en el formato correcto
            renamed = combined_df_raw.copy()
        
        # Añadir Exchange Yahoo si no existe pero tenemos datos de Bolsa
        if 'Bolsa' in renamed.columns and 'Exchange Yahoo' not in renamed.columns:
            renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna('')
        elif 'Bolsa de' in renamed.columns and 'Exchange Yahoo' not in renamed.columns:
            # Para datos que vienen de IBKR
            renamed['Exchange Yahoo'] = renamed['Bolsa de'].map(get_yahoo_suffix_mapping()).fillna('')
        
        # Convertir columnas numéricas
        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    # Limpieza de strings antes de convertir a numérico
                    cleaned_series = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False)
                    renamed[col] = pd.to_numeric(cleaned_series, errors='coerce')

                if pd.api.types.is_numeric_dtype(renamed[col]) or renamed[col].isnull().any():
                    renamed[col] = renamed[col].fillna(0)

                if col == 'Cantidad':
                    if pd.api.types.is_numeric_dtype(renamed[col]):
                        renamed[col] = renamed[col].abs()  # Cantidad siempre positiva

                if pd.api.types.is_numeric_dtype(renamed[col]):
                    renamed[col] = renamed[col].astype(float)
        
        return renamed
        
    except Exception as e:
        error_msg = f"Error preparando DataFrame procesado: {e}"
        print(error_msg)
        errors.append(error_msg)
        return combined_df_raw



def get_yahoo_suffix_mapping():
    """Obtiene el mapeo de mercados IBKR a sufijos Yahoo."""
    return {
        'NASDAQ': '', 'NYSE': '', 'SEHK': '.HK', 'TSE': '.TO', 'LSE': '.L',
        'SGX': '.SI', 'OMXNO': '.OL', 'GETTEX2': '.DE', 'BATS': '',
        'ARCA': '', 'ISLAND': '', 'IBIS2': '.DE', 'LSEIOB1': '.L',
        'DRCTEDGE': '', 'IBKR': '', 'IBKRATS': '', 'TSXDARK': '.TO',
        'TRIACT': '.TO', 'ALPHA': '.TO', 'CAIBFRSH': '.TO'
    }


def get_google_ex_mapping():
    """Obtiene el mapeo de mercados IBKR a códigos Google Exchange."""
    return {
        'NASDAQ': 'NASDAQ', 'NYSE': 'NYSE', 'SEHK': 'HKG', 'TSE': 'TSE',
        'LSE': 'LON', 'SGX': 'SGX', 'OMXNO': 'OSL', 'GETTEX2': 'FRA',
        'BATS': 'BATS', 'ARCA': 'ARCA', 'ISLAND': 'NASDAQ',
        'IBIS2': 'FRA', 'LSEIOB1': 'LON', 'DRCTEDGE': 'NYSE',
        'IBKR': 'NASDAQ', 'IBKRATS': 'NASDAQ', 'TSXDARK': 'TSE',
        'TRIACT': 'TSE', 'ALPHA': 'TSE', 'CAIBFRSH': 'TSE'
    }


import csv
from io import StringIO

# -*- coding: utf-8 -*-
# ... (imports) ...

def process_ibkr_file_complete(file, filename):
    # ... (Fase 1: Extraer instrumentos - sin cambios) ...
    try:
        file.seek(0)
        content = file.read()
        if isinstance(content, bytes):
            try: content = content.decode('utf-8')
            except UnicodeDecodeError: content = content.decode('latin-1')
        
        lines = content.split('\n')
        transactions, instruments = [], {} # Definir instruments aquí
        
        # Fase 1: Extraer instrumentos (como estaba)
        for line_num, line_content in enumerate(lines, 1):
            line_str = line_content.strip()
            if not line_str or not line_str.startswith('Información de instrumento financiero,Data,Acciones'):
                continue
            try:
                csv_reader_instr = csv.reader(StringIO(line_str))
                parts_instr = next(csv_reader_instr)
                if len(parts_instr) >= 9:
                    symbol_instr, description_instr, isin_instr, market_instr = parts_instr[3].strip(), parts_instr[4].strip(), parts_instr[6].strip(), parts_instr[8].strip()
                    if symbol_instr and isin_instr:
                        instruments[symbol_instr] = {'isin': isin_instr, 'name': description_instr, 'market': market_instr}
            except Exception as e_instr:
                print(f"Error parseando instrumento en línea {line_num}: {line_str[:100]} -> {e_instr}")

        if instruments: print(f"Total instrumentos encontrados: {len(instruments)}")
        else: print("No se encontraron instrumentos en la Fase 1.")


        # Fase 2: Extraer transacciones
        transaction_lines_found = 0
        for line_num, line_content in enumerate(lines, 1):
            line_str_original = line_content.strip()
            if not line_str_original: continue

            # Determinar si es una línea de transacción
            # La línea puede estar entrecomillada o no.
            # Ej1: "Operaciones,Data,Trade,Acciones,..."
            # Ej2: Operaciones,Data,Trade,Acciones,...
            
            line_to_check_header = line_str_original
            if line_to_check_header.startswith('"'):
                line_to_check_header = line_to_check_header[1:] # Quitar solo la primera comilla para la comprobación del header

            if not line_to_check_header.startswith('Operaciones,Data,Trade,Acciones'):
                continue 
            
            transaction_lines_found += 1
            parts = []
            parsing_success = False

            # Lógica de limpieza de la línea para csv.reader:
            # Queremos la cadena que está entre la primera comilla (si existe) 
            # y la última comilla que precede a la posible basura final (";P;")
            # o la línea tal cual si no está entrecomillada globalmente.

            line_for_csv_reader = line_str_original
            if line_str_original.startswith('"'):
                # Encontrar el final del contenido CSV real, que debería ser justo antes de una comilla
                # que podría estar seguida por basura como ";P;"
                # Ejemplo: "CSV_CONTENT_ENDS_HERE";P;...
                #          ^                     ^
                #      start_quote           end_quote_of_content
                
                # Buscar la última comilla que es parte del contenido CSV.
                # A menudo, la basura como ";P;" no está entrecomillada.
                # Si ";P;" existe y hay una comilla justo antes, ese es el final del CSV.
                garbage_separator_pos = line_str_original.rfind('";') # Busca comilla seguida de punto y coma
                if garbage_separator_pos > 0 : # Si se encuentra ";
                    line_for_csv_reader = line_str_original[1:garbage_separator_pos]
                elif line_str_original.endswith('"'): # Si termina con comilla y no se encontró basura
                    line_for_csv_reader = line_str_original[1:-1]
                else: # Empieza con comilla pero no termina con comilla (o no se encontró ";)
                      # Esto es un caso difícil, podríamos intentar quitar solo la primera.
                      # O buscar la última comilla en la línea.
                    last_q = line_str_original.rfind('"')
                    if last_q > 0: # Si hay otra comilla
                        line_for_csv_reader = line_str_original[1:last_q]
                    else: # Solo comilla al inicio, caso raro
                        line_for_csv_reader = line_str_original[1:]


            try:
                csv_reader_trans = csv.reader(StringIO(line_for_csv_reader))
                parts = next(csv_reader_trans)
                if len(parts) >= 4 and parts[0] == "Operaciones" and parts[1] == "Data" and parts[2] == "Trade" and parts[3] == "Acciones":
                    if len(parts) >= 13: 
                        parsing_success = True
            except Exception as e_csv:
                if transaction_lines_found <= 3:
                    print(f"Línea {line_num}: Falló csv.reader en línea procesada '{line_for_csv_reader[:100]}...': {e_csv}")
                parts = [] 
                parsing_success = False
            
            # ----- DEBUG INICIAL (Mantenido y ajustado) -----
            if transaction_lines_found <= 3:
                print(f"\n=== DEBUG TRANSACCIÓN {transaction_lines_found} (línea CSV original: {line_num}) ===")
                print(f"Línea original stripped: '{line_str_original[:150]}...'")
                print(f"Línea pasada a csv.reader: '{line_for_csv_reader[:150]}...'")
                print(f"Parsing CSV exitoso: {parsing_success}")
                print(f"Total parts obtenidos: {len(parts)}")
                if parts: print(f"Parts (primeros 15 para ver estructura): {parts[:15]}")
            # ----- FIN DEBUG INICIAL -----

            if not parsing_success:
                if transaction_lines_found <= 3: 
                    print(f"  Línea {line_num}: Saltada por fallo en parseo o cabecera/longitud incorrecta. Parts len: {len(parts)}")
                    if parts and len(parts) >=4: print(f"    Header check: {parts[0]},{parts[1]},{parts[2]},{parts[3]}")
                if transaction_lines_found <= 3: print("=== FIN DEBUG (FALLO PARSEO/VALIDACIÓN) ===\n")
                continue
            
            # ----- Lógica adaptativa de índices y extracción de campos (como en la respuesta anterior) -----
            current_idx_currency = 4
            current_idx_symbol = 5
            
            current_idx_datetime_field_date = 6 
            current_idx_datetime_field_time = -1 
            current_idx_market = 7
            current_idx_quantity = 8
            current_idx_price = 9
            current_idx_total_value = 11
            current_idx_commission = 12
            is_format_urc_like = False

            if len(parts) >= 10:
                try:
                    float(str(parts[9]).replace(',', '').replace('"', '')) 
                    try:
                        float(str(parts[8]).replace(',', '').replace('"', '')) 
                    except ValueError: 
                        is_format_urc_like = True
                except ValueError: 
                    pass
            
            if is_format_urc_like:
                if transaction_lines_found <= 3: print("  Formato detectado: URC-like (parts[6]=fecha, parts[7]=hora, parts[9]=cantidad)")
                current_idx_datetime_field_time = 7 
                current_idx_market = 8
                current_idx_quantity = 9
                current_idx_price = 10
                current_idx_total_value = 12
                current_idx_commission = 13
            else: 
                 if transaction_lines_found <= 3: print("  Formato detectado: PYPL-like (parts[6]=fecha-hora, parts[8]=cantidad)")

            required_indices_check = [current_idx_currency, current_idx_symbol, current_idx_datetime_field_date, 
                                 current_idx_market, current_idx_quantity, current_idx_price, 
                                 current_idx_total_value, current_idx_commission]
            if current_idx_datetime_field_time != -1:
                required_indices_check.append(current_idx_datetime_field_time)

            is_crpu_qty_split_case = False
            symbol_check = parts[current_idx_symbol].strip() if current_idx_symbol < len(parts) else ""
            
            if symbol_check == "CRPU" and is_format_urc_like :
                qty_part1_check = str(parts[current_idx_quantity]) # ej. '5'
                if (current_idx_quantity + 1) < len(parts):
                    qty_part2_check = str(parts[current_idx_quantity + 1]) # ej. '400""'
                    # Comprobar si el primer char de qty_part1 es digito o '-' y el resto digitos,
                    # y si qty_part2 termina en '00""' y el resto son dígitos.
                    if (qty_part1_check.replace('-','').isdigit() and 
                        qty_part2_check.replace('"', '').endswith('00') and 
                        qty_part2_check.replace('"', '')[:-2].isdigit()):
                        is_crpu_qty_split_case = True
                        if transaction_lines_found <=3 : print(f"  CRPU Split Quantity Case DETECTADO para línea {line_num}! Ajustando índices de precio/total/comisión.")
                        current_idx_price += 1            
                        current_idx_total_value += 1      
                        current_idx_commission += 1       
                        # Actualizar required_indices_check si se desplazan los índices
                        required_indices_check = [current_idx_currency, current_idx_symbol, current_idx_datetime_field_date, 
                                                  current_idx_market, current_idx_quantity, # quantity y su parte2 siguen siendo qty_idx y qty_idx+1
                                                  current_idx_price, current_idx_total_value, current_idx_commission]
                        if current_idx_datetime_field_time != -1: required_indices_check.append(current_idx_datetime_field_time)
            
            if any(idx >= len(parts) or idx < 0 for idx in required_indices_check):
                print(f"Línea {line_num}: Partes insuficientes ({len(parts)}) para índices ({required_indices_check}). Parts: {parts[:15]}. Saltando.")
                if transaction_lines_found <= 3: print("=== FIN DEBUG (PARTES INSUFICIENTES PARA FORMATO) ===\n")
                continue
            
            datetime_str_for_parsing = ""
            date_val = parts[current_idx_datetime_field_date].strip().strip('"')
            if current_idx_datetime_field_time != -1:
                time_val = parts[current_idx_datetime_field_time].strip().strip('"')
                datetime_str_for_parsing = f"{date_val}, {time_val}"
            else: 
                datetime_str_for_parsing = date_val
            
            if transaction_lines_found <= 3: # DEBUG DETALLADO
                print(f"  String para parsear fecha/hora: '{datetime_str_for_parsing}'")
                print(f"  Valores por índice -> cur:'{parts[current_idx_currency]}', sym:'{parts[current_idx_symbol]}', "
                      f"dt_val_constr:'{datetime_str_for_parsing}', mkt:'{parts[current_idx_market]}', qty_str_raw:'{parts[current_idx_quantity]}', "
                      f"px_str_raw:'{parts[current_idx_price]}', total_str_raw:'{parts[current_idx_total_value]}', comm_str_raw:'{parts[current_idx_commission]}'")
                if is_crpu_qty_split_case: # Muestra las partes que formarían la cantidad CRPU
                     print(f"    CRPU RAW Qty parts: parts[{current_idx_quantity}]='{parts[current_idx_quantity]}', parts[{current_idx_quantity+1}]='{parts[current_idx_quantity+1]}'")
                print("=== FIN DEBUG ===\n")

            try:
                currency = parts[current_idx_currency].strip()
                symbol = parts[current_idx_symbol].strip()
                execution_market = parts[current_idx_market].strip()
                
                quantity_str_val = str(parts[current_idx_quantity]).strip().replace('"', '')
                if is_crpu_qty_split_case: # Si es CRPU y la cantidad se dividió
                    # parts[current_idx_quantity] es la parte antes de la coma (ej: '5' o '-5')
                    # parts[current_idx_quantity+1] es la parte después de la coma (ej: '400""')
                    part2_qty = str(parts[current_idx_quantity+1]).strip().replace('"', '') # ej: '400'
                    # Reconstruir el número como si no tuviera coma para la conversión.
                    # Ej: '5' + '400' -> '5400'. Si era '-5' + '400' -> '-5400'.
                    if quantity_str_val.startswith('-'):
                        quantity_str_val = "-" + quantity_str_val.replace('-','') + part2_qty.replace(',','') 
                    else:
                        quantity_str_val = quantity_str_val.replace(',','') + part2_qty.replace(',','')
                    print(f"  CRPU (Línea {line_num}): Cantidad reconstruida a '{quantity_str_val}'")


                price_str_val = str(parts[current_idx_price]).strip().replace('"', '')
                total_value_str_val = str(parts[current_idx_total_value]).strip().replace('"', '')
                commission_str_val = str(parts[current_idx_commission]).strip().replace('"', '')
                
                if not symbol or not quantity_str_val or not price_str_val:
                    print(f"Línea {line_num}: Datos esenciales vacíos. Símbolo='{symbol}', Cantidad='{quantity_str_val}', Precio='{price_str_val}'.")
                    continue
                
                try:
                    quantity_original = float(quantity_str_val.replace(',', '')) 
                    price = abs(float(price_str_val.replace(',', '')))
                except ValueError as ve_num:
                    print(f"Línea {line_num}: Error convirtiendo cantidad o precio. Cantidad='{quantity_str_val}', Precio='{price_str_val}'. Error: {ve_num}")
                    continue
                
                quantity = abs(quantity_original)
                is_buy = quantity_original > 0
                
                cleaned_total_value = total_value_str_val.replace(',', '')
                cleaned_commission = commission_str_val.replace(',', '')

                raw_total_value = abs(float(cleaned_total_value)) if cleaned_total_value and cleaned_total_value != '-' else quantity * price
                raw_commission = abs(float(cleaned_commission)) if cleaned_commission and cleaned_commission != '-' else 0.0
                
                if is_buy:
                    valor_local, valor, total = -raw_total_value, -raw_total_value, -(raw_total_value + raw_commission)
                else: 
                    valor_local, valor, total = raw_total_value, raw_total_value, raw_total_value - raw_commission
                
                commission_final = -raw_commission
                    
            except ValueError as ve_conv:
                print(f"Error convirtiendo valores numéricos en línea {line_num}: {ve_conv}. Parts: {parts[:15]}")
                continue
            except IndexError as ie_conv:
                print(f"Error de índice durante conversión en línea {line_num}: {ie_conv}. Parts: {parts[:15]}")
                continue
            
            fecha, hora = parse_ibkr_datetime_robust(datetime_str_for_parsing)
            
            transaction = {
                'Fecha': fecha, 'Hora': hora, 'Producto': symbol, 'ISIN': '', 
                'Bolsa de': execution_market, 
                'Número': quantity, 'Precio': price, 'Unnamed: 8': currency,
                'Valor local': valor_local, 'Unnamed: 10': currency,
                'Valor': valor, 'Unnamed: 12': currency,
                'Tipo de cambio': 1.0, 'Costes de transacción': commission_final,
                'Unnamed: 15': currency, 'Total': total, 'Unnamed: 17': currency
            }
            transactions.append(transaction)
    
        print(f"DEBUG FINAL: Se encontraron {transaction_lines_found} líneas que parecían transacciones.")
        print(f"Total transacciones procesadas exitosamente: {len(transactions)}")
        
        if not transactions: return None
        
        updated_transactions = []
        for transaction_item in transactions:
            symbol_key = transaction_item['Producto']
            if symbol_key in instruments:
                instrument_info = instruments[symbol_key]
                transaction_item['ISIN'] = instrument_info['isin']
                transaction_item['Producto'] = instrument_info['name'] or symbol_key
                isin = instrument_info['isin']
                if isin: update_mapping_for_ibkr_instrument(isin, symbol_key, instrument_info)
                updated_transactions.append(transaction_item)
            else:
                print(f"Advertencia: No se encontró info para símbolo '{symbol_key}'.")
                updated_transactions.append(transaction_item)
        
        if updated_transactions:
            df = pd.DataFrame(updated_transactions)
            # print(f"Archivo IBKR procesado exitosamente: {len(df)} transacciones") # Ya se imprime al final
            return df
        else:
            # print(f"No se pudieron procesar transacciones de {filename} (post-enriquecimiento)")
            return None

    except Exception as e_main:
        print(f"Error CRÍTICO procesando archivo IBKR '{filename}': {e_main}")
        traceback.print_exc()
        return None

# ... (resto de tu app.py)

def parse_ibkr_datetime_robust(datetime_str_original):
    """
    Parsea una cadena de fecha/hora de IBKR.
    Devuelve la fecha como string 'DD-MM-YYYY' y la hora como string 'HH:MM'.
    """
    try:
        datetime_str = str(datetime_str_original).strip().strip('"')
        if datetime_str.startswith('"') and datetime_str.endswith('"') and len(datetime_str) > 1:
            datetime_str = datetime_str[1:-1]

        date_part_str = ""
        time_part_str = "00:00:00"

        if ',' in datetime_str:
            parts_dt = datetime_str.split(',', 1)
            date_part_str = parts_dt[0].strip()
            if len(parts_dt) > 1:
                time_part_str = parts_dt[1].strip()
        elif ' ' in datetime_str:
            parts_dt = datetime_str.split(' ', 1)
            if len(parts_dt) == 2 and ('-' in parts_dt[0] or '/' in parts_dt[0]) and ':' in parts_dt[1]:
                date_part_str = parts_dt[0].strip()
                time_part_str = parts_dt[1].strip()
            else:
                date_part_str = datetime_str.strip()
        else:
            date_part_str = datetime_str.strip()

        fecha_final = "01-01-1900" # Fallback en formato DD-MM-YYYY
        if date_part_str:
            parsed_date_obj = None
            # Intentar parsear varios formatos comunes
            date_formats_to_try = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y']
            for fmt in date_formats_to_try:
                try:
                    parsed_date_obj = datetime.strptime(date_part_str, fmt)
                    break 
                except ValueError:
                    continue
            
            if not parsed_date_obj: # Si strptime falló para todos los formatos comunes
                try: # Intentar con Pandas, que es más flexible
                    parsed_date_obj = pd.to_datetime(date_part_str, errors='raise').to_pydatetime()
                except:
                     # Como último recurso, intentar regex
                    match_ymd = re.search(r'(\d{4})[-\./](\d{1,2})[-\./](\d{1,2})', date_part_str)
                    if match_ymd:
                        try: parsed_date_obj = datetime(int(match_ymd.group(1)), int(match_ymd.group(2)), int(match_ymd.group(3)))
                        except: pass
                    else:
                        match_dmy = re.search(r'(\d{1,2})[-\./](\d{1,2})[-\./](\d{4})', date_part_str)
                        if match_dmy:
                            try: parsed_date_obj = datetime(int(match_dmy.group(3)), int(match_dmy.group(2)), int(match_dmy.group(1)))
                            except: pass
            
            if parsed_date_obj:
                fecha_final = parsed_date_obj.strftime('%d-%m-%Y') # Formato de salida DD-MM-YYYY
            else:
                print(f"Advertencia parse_ibkr_datetime: No se pudo convertir '{date_part_str}' a fecha. Usando '{date_part_str}' o fallback.")
                fecha_final = date_part_str # Opcional: usar el string original si no se pudo parsear

        hora_final = "00:00"
        time_part_str_cleaned = time_part_str.split('.')[0]
        
        if ':' in time_part_str_cleaned:
            time_parts_arr = time_part_str_cleaned.split(':')
            h_str = time_parts_arr[0].strip().zfill(2)
            m_str = time_parts_arr[1].strip().zfill(2) if len(time_parts_arr) > 1 else "00"
            try:
                if 0 <= int(h_str) <= 23 and 0 <= int(m_str) <= 59:
                    hora_final = f"{h_str}:{m_str}"
                else:
                    print(f"Advertencia parse_ibkr_datetime: Hora/minuto inválido en '{time_part_str}'. Usando 00:00.")
            except ValueError:
                 print(f"Advertencia parse_ibkr_datetime: Componente de hora no numérico en '{time_part_str}'. Usando 00:00.")
        elif time_part_str_cleaned.strip().isdigit() and len(time_part_str_cleaned.strip()) <= 2:
            h_str = time_part_str_cleaned.strip().zfill(2)
            try:
                if 0 <= int(h_str) <= 23:
                    hora_final = f"{h_str}:00"
                else:
                    print(f"Advertencia parse_ibkr_datetime: Hora inválida en '{time_part_str}'. Usando 00:00.")
            except ValueError:
                print(f"Advertencia parse_ibkr_datetime: Componente de hora no numérico en '{time_part_str}'. Usando 00:00.")
        
        # El print de DEBUG muestra el formato de salida que produce esta función
        # print(f"DEBUG fecha: Original='{datetime_str_original}' -> FechaParseada='{fecha_final}', HoraParseada='{hora_final}'")
        
        return fecha_final, hora_final
        
    except Exception as e:
        print(f"Error CRÍTICO parseando fecha/hora IBKR '{datetime_str_original}': {e}")
        date_fallback_str = "01-01-1900" 
        if isinstance(datetime_str_original, str):
            try:
                first_part = datetime_str_original.split(',')[0].split(' ')[0].strip()
                # Intentar parsear y reformatear a DD-MM-YYYY si es posible
                parsed_dt_fallback = None
                if re.match(r"^\d{4}-\d{2}-\d{2}$", first_part): 
                    parsed_dt_fallback = datetime.strptime(first_part, '%Y-%m-%d')
                elif re.match(r"^\d{2}-\d{2}-\d{4}$", first_part):
                    parsed_dt_fallback = datetime.strptime(first_part, '%d-%m-%Y')
                if parsed_dt_fallback:
                    date_fallback_str = parsed_dt_fallback.strftime('%d-%m-%Y')
            except: pass
        return date_fallback_str, "00:00"




def parse_ibkr_datetime_robust(datetime_str):
    """Parsea fecha/hora de IBKR al formato DeGiro de forma robusta."""
    try:
        # Limpiar la cadena
        datetime_str = datetime_str.strip()
        
        if ',' in datetime_str:
            date_part, time_part = datetime_str.split(',', 1)
            date_part = date_part.strip()
            time_part = time_part.strip()
        else:
            date_part = datetime_str.strip()
            time_part = "00:00:00"
        
        # Convertir fecha de YYYY-MM-DD a DD-MM-YYYY (formato DeGiro)
        if '-' in date_part and len(date_part.split('-')) == 3:
            parts = date_part.split('-')
            if len(parts[0]) == 4:  # Formato YYYY-MM-DD
                year, month, day = parts
                fecha = f"{day.zfill(2)}-{month.zfill(2)}-{year}"
            else:
                fecha = date_part
        else:
            fecha = date_part
        
        # Formatear hora HH:MM:SS a HH:MM
        if ':' in time_part:
            hora_parts = time_part.split(':')
            if len(hora_parts) >= 2:
                hora = f"{hora_parts[0].zfill(2)}:{hora_parts[1].zfill(2)}"
            else:
                hora = time_part
        else:
            hora = "00:00"
        
        print(f"DEBUG fecha: '{datetime_str}' -> fecha='{fecha}', hora='{hora}'")
        return fecha, hora
        
    except Exception as e:
        print(f"Error parseando fecha/hora IBKR '{datetime_str}': {e}")
        return datetime_str, "00:00"

def update_mapping_for_ibkr_instrument(isin, symbol, instrument_info):
    """Actualiza mapping_db.json con información de IBKR de forma segura."""
    try:
        mapping_data = load_mapping()
        
        if isin not in mapping_data:
            # Mapear mercado IBKR a Yahoo suffix y Google exchange
            market = instrument_info.get('market', '')
            yahoo_suffix = get_yahoo_suffix_mapping().get(market, '')
            google_ex = get_google_ex_mapping().get(market, market)  # Si no se encuentra, usar el market original
            
            mapping_data[isin] = {
                'ticker': symbol,
                'name': instrument_info.get('name', ''),
                'yahoo_suffix': yahoo_suffix,
                'google_ex': google_ex
            }
            
            save_mapping(mapping_data)
            print(f"Mapping añadido automáticamente: {isin} -> {symbol} (market: {market} -> yahoo: '{yahoo_suffix}', google: '{google_ex}')")
        else:
            print(f"Mapping ya existe para {isin}")
            
    except Exception as e:
        print(f"Error actualizando mapping para {isin}: {e}")



def parse_ibkr_csv(file_content_or_path, filename):
    """
    Parsea un CSV de IBKR y extrae transacciones e información de instrumentos.
    
    Args:
        file_content_or_path: Contenido del archivo o ruta
        filename: Nombre del archivo para logs
    
    Returns:
        tuple: (transactions_list, instruments_dict, errors_list)
    """
    transactions = []
    instruments = {}
    errors = []
    
    try:
        # Leer contenido del archivo
        if isinstance(file_content_or_path, str) and os.path.exists(file_content_or_path):
            with open(file_content_or_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        elif hasattr(file_content_or_path, 'read'):
            file_content_or_path.seek(0)
            content = file_content_or_path.read()
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8')
                except UnicodeDecodeError:
                    content = content.decode('latin-1')
            lines = content.split('\n')
        else:
            lines = str(file_content_or_path).split('\n')
        
        print(f"Parseando archivo IBKR '{filename}' con {len(lines)} líneas")
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
                
            parts = line.split(',')
            if len(parts) < 5:
                continue
            
            # Extraer transacciones de acciones
            if line.startswith('Operaciones,Data,Trade,Acciones'):
                if len(parts) >= 13:
                    try:
                        currency = parts[4].strip()
                        symbol = parts[5].strip()
                        datetime_str = parts[6].strip().strip('"')
                        market = parts[7].strip()
                        quantity_str = parts[8].strip()
                        price_str = parts[9].strip()
                        total_value_str = parts[11].strip()
                        commission_str = parts[12].strip()
                        
                        # Validar datos esenciales
                        if not symbol or not quantity_str or not price_str:
                            continue
                        
                        # Convertir cantidad (positiva=compra, negativa=venta en IBKR)
                        # Para compatibilidad con DeGiro, convertir a valor absoluto
                        quantity = abs(float(quantity_str.replace(',', '')))
                        price = abs(float(price_str.replace(',', '')))
                        total_value = abs(float(total_value_str.replace(',', ''))) if total_value_str else quantity * price
                        commission = abs(float(commission_str.replace(',', ''))) if commission_str else 0.0
                        
                        # Parsear fecha y hora
                        fecha, hora = parse_ibkr_datetime(datetime_str)
                        
                        transaction = {
                            'Fecha': fecha,
                            'Hora': hora,
                            'Producto': symbol,  # Temporal, se actualizará con nombre real
                            'ISIN': '',  # Se completará después con información de instrumentos
                            'Ticker': symbol,
                            'Bolsa': market,
                            'Número': quantity,
                            'Precio': price,
                            'Precio Divisa': currency,
                            'Valor Local': total_value,
                            'Valor Local Divisa': currency,
                            'Valor': total_value,
                            'Valor Divisa': currency,
                            'Tipo de cambio': 1.0,  # Será calculado si es necesario
                            'Costes Transacción': commission,
                            'Costes Transacción Divisa': currency,
                            'Total': total_value + commission,
                            'Total Divisa': currency,
                            'source_file': filename
                        }
                        
                        transactions.append(transaction)
                        
                    except (ValueError, IndexError) as e:
                        errors.append(f"Error parseando transacción en línea {line_num}: {e}")
                        continue
            
            # Extraer información de instrumentos financieros
            elif line.startswith('Información de instrumento financiero,Data,Acciones'):
                if len(parts) >= 8:
                    try:
                        symbol = parts[2].strip()
                        description = parts[3].strip()
                        isin = parts[5].strip()
                        market = parts[7].strip()
                        
                        if symbol and isin:
                            # Determinar Yahoo suffix a partir del mercado
                            yahoo_suffix = IBKR_MARKET_TO_YAHOO_MAP.get(market, '')
                            google_ex = IBKR_MARKET_TO_GOOGLE_MAP.get(market, market)
                            
                            instruments[symbol] = {
                                'isin': isin,
                                'name': description,
                                'market': market,
                                'yahoo_suffix': yahoo_suffix,
                                'google_ex': google_ex
                            }
                            
                    except (ValueError, IndexError) as e:
                        errors.append(f"Error parseando instrumento en línea {line_num}: {e}")
                        continue
        
        print(f"IBKR parsing completado: {len(transactions)} transacciones, {len(instruments)} instrumentos")
        return transactions, instruments, errors
        
    except Exception as e:
        error_msg = f"Error general parseando archivo IBKR '{filename}': {e}"
        print(error_msg)
        errors.append(error_msg)
        return [], {}, errors


def get_historical_price_from_yfinance(symbol_yf: str, target_date: date, target_currency: str = 'EUR') -> Union[float, None]:    
    """
    Obtiene el precio de cierre de un símbolo de Yahoo Finance para una fecha específica y lo convierte a target_currency.
    Intenta obtener el precio para target_date. Si no hay datos (ej. fin de semana/festivo),
    prueba con el día anterior hasta encontrar datos o retroceder un máximo de 4 días.
    """
    price_native_currency = None
    fetched_date = None

    if target_date > date.today():
        print(f"  [yfinance-SKIP] No se consultan precios para fecha futura: {target_date} para {symbol_yf}")
        return None, None # Devuelve None para precio y fecha_obtenida

    for i in range(5): # Intentar hasta 5 días atrás (target_date y 4 días antes)
        current_fetch_date = target_date - timedelta(days=i)
        try:
            ticker = yf.Ticker(symbol_yf)
            # Pedir un rango pequeño para asegurar que obtenemos el cierre del día si está disponible
            hist = ticker.history(start=current_fetch_date, end=current_fetch_date + timedelta(days=1), auto_adjust=True)
            if not hist.empty and 'Close' in hist.columns and not pd.isna(hist['Close'].iloc[0]):
                price_native_currency = float(hist['Close'].iloc[0])
                fetched_date = current_fetch_date # Guardar la fecha para la que se obtuvo el precio
                
                # Obtener la divisa del ticker desde yfinance si es posible
                info = ticker.info
                asset_currency = info.get('currency', '').upper()

                if not asset_currency: # Fallback si yfinance no da la divisa (común para algunos futuros)
                    if symbol_yf in ["GC=F", "SI=F"]: asset_currency = "USD"
                    # Añade más fallbacks si es necesario para otros símbolos

                print(f"  [yfinance] {symbol_yf} en {fetched_date}: {price_native_currency} {asset_currency if asset_currency else 'N/A'}")
                
                if price_native_currency is not None:
                    break # Precio encontrado
            # else:
                # print(f"  [yfinance] No data for {symbol_yf} on {current_fetch_date}")
        except Exception as e:
            print(f"  [yfinance-WARN] Error fetching {symbol_yf} for {current_fetch_date}: {e}")
            continue # Intentar día anterior

    if price_native_currency is None or asset_currency is None:
        print(f"  [yfinance-FAIL] No se pudo obtener precio o divisa para {symbol_yf} alrededor de {target_date}")
        return None

    if asset_currency == target_currency:
        return price_native_currency, fetched_date
    else:
        exchange_rate = get_exchange_rate(asset_currency, target_currency) # Tu función existente
        if exchange_rate is not None:
            price_target_currency = price_native_currency * exchange_rate
            print(f"  [yfinance-CONV] {price_native_currency} {asset_currency} -> {price_target_currency:.2f} {target_currency} (Rate: {exchange_rate})")
            return price_target_currency, fetched_date
        else:
            print(f"  [yfinance-FAIL] No se pudo convertir {asset_currency} a {target_currency} para {symbol_yf}")
            return None, None


def get_historical_metal_price_eur(metal_symbol_yf: str, target_date: date) -> Union[float, None]:    
    """
    Obtiene el precio histórico en EUR para un metal desde la BD local o yfinance.
    metal_symbol_yf: Ej. "GC=F" para Oro, "SI=F" para Plata.
    """
    # 1. Consultar BD Local
    cached_price_obj = HistoricalMetalPrice.query.filter_by(
        metal_symbol_yf=metal_symbol_yf,
        date=target_date
    ).first()
    if cached_price_obj:
        # print(f"  [DB-HIT] Precio histórico metal {metal_symbol_yf} para {target_date}: {cached_price_obj.price_eur} EUR")
        return cached_price_obj.price_eur

    # 2. Si no está en BD, consultar yfinance
    print(f"  [API-CALL] Buscando precio histórico metal {metal_symbol_yf} para {target_date} en yfinance...")
    fetched_data = get_historical_price_from_yfinance(metal_symbol_yf, target_date, 'EUR')
    
    if fetched_data:
        price_eur, actual_fetched_date = fetched_data
        if price_eur is not None and actual_fetched_date is not None:
            # 3. Guardar en BD Local (para la target_date original, incluso si yf dio precio de día cercano)
            new_price_entry = HistoricalMetalPrice(
                metal_symbol_yf=metal_symbol_yf,
                date=target_date, # Usar la fecha solicitada para el cache, no la fecha real del dato de yf
                price_eur=price_eur
            )
            try:
                db.session.add(new_price_entry)
                db.session.commit()
                print(f"  [DB-SAVE] Precio histórico metal {metal_symbol_yf} para {target_date} ({price_eur} EUR de {actual_fetched_date}) guardado.")
            except Exception as e_save: # Podría ser UniqueConstraint si otra request lo guardó mientras tanto
                db.session.rollback()
                print(f"  [DB-WARN] No se pudo guardar precio histórico metal para {metal_symbol_yf} en {target_date}: {e_save}")
                # Re-consultar por si se guardó en paralelo
                cached_price_obj_retry = HistoricalMetalPrice.query.filter_by(metal_symbol_yf=metal_symbol_yf, date=target_date).first()
                if cached_price_obj_retry: return cached_price_obj_retry.price_eur

            return price_eur
    
    print(f"  [API-FAIL] No se pudo obtener precio histórico para metal {metal_symbol_yf} en {target_date}.")
    return None


def get_historical_crypto_price_eur(crypto_symbol_yf: str, target_date: date) -> Union[float, None]:    
    """
    Obtiene el precio histórico en EUR para una cripto desde la BD local o yfinance.
    crypto_symbol_yf: Ej. "BTC-EUR", "ETH-EUR".
    """
    # 1. Consultar BD Local
    cached_price_obj = HistoricalCryptoPrice.query.filter_by(
        crypto_symbol_yf=crypto_symbol_yf,
        date=target_date
    ).first()
    if cached_price_obj:
        # print(f"  [DB-HIT] Precio histórico cripto {crypto_symbol_yf} para {target_date}: {cached_price_obj.price_eur} EUR")
        return cached_price_obj.price_eur

    # 2. Si no está en BD, consultar yfinance
    print(f"  [API-CALL] Buscando precio histórico cripto {crypto_symbol_yf} para {target_date} en yfinance...")
    fetched_data = get_historical_price_from_yfinance(crypto_symbol_yf, target_date, 'EUR')

    if fetched_data:
        price_eur, actual_fetched_date = fetched_data
        if price_eur is not None and actual_fetched_date is not None:
            # 3. Guardar en BD Local
            new_price_entry = HistoricalCryptoPrice(
                crypto_symbol_yf=crypto_symbol_yf,
                date=target_date, # Usar la fecha solicitada
                price_eur=price_eur
            )
            try:
                db.session.add(new_price_entry)
                db.session.commit()
                print(f"  [DB-SAVE] Precio histórico cripto {crypto_symbol_yf} para {target_date} ({price_eur} EUR de {actual_fetched_date}) guardado.")
            except Exception as e_save:
                db.session.rollback()
                print(f"  [DB-WARN] No se pudo guardar precio histórico cripto para {crypto_symbol_yf} en {target_date}: {e_save}")
                cached_price_obj_retry = HistoricalCryptoPrice.query.filter_by(crypto_symbol_yf=crypto_symbol_yf, date=target_date).first()
                if cached_price_obj_retry: return cached_price_obj_retry.price_eur
            return price_eur
            
    print(f"  [API-FAIL] No se pudo obtener precio histórico para cripto {crypto_symbol_yf} en {target_date}.")
    return None


def parse_ibkr_datetime(datetime_str):
    """
    Parsea fecha y hora de IBKR al formato esperado por DeGiro.
    
    Args:
        datetime_str: String como "2024-04-25, 11:11:05"
    
    Returns:
        tuple: (fecha, hora) en formato compatible con DeGiro
    """
    try:
        # Remover comillas y espacios extra
        datetime_str = datetime_str.strip('"').strip()
        
        if ',' in datetime_str:
            date_part, time_part = datetime_str.split(',', 1)
            date_part = date_part.strip()
            time_part = time_part.strip()
        else:
            # Solo fecha, sin hora
            date_part = datetime_str
            time_part = "00:00:00"
        
        # Convertir fecha de YYYY-MM-DD a DD-MM-YYYY (formato DeGiro)
        if '-' in date_part and len(date_part.split('-')) == 3:
            year, month, day = date_part.split('-')
            fecha = f"{day.zfill(2)}-{month.zfill(2)}-{year}"
        else:
            fecha = date_part
        
        # Formatear hora
        if ':' in time_part:
            hora = time_part
        else:
            hora = "00:00"
        
        return fecha, hora
        
    except Exception as e:
        print(f"Error parseando fecha/hora IBKR '{datetime_str}': {e}")
        return datetime_str, "00:00"

def transform_ibkr_to_degiro_format(transactions, instruments, mapping_data=None):
    """
    Transforma transacciones e instrumentos de IBKR al formato esperado por DeGiro.
    
    Args:
        transactions: Lista de transacciones parseadas de IBKR
        instruments: Diccionario de instrumentos {symbol: info}
        mapping_data: Datos de mapping existentes (opcional)
    
    Returns:
        tuple: (dataframe_transformado, mappings_to_update, errors)
    """
    errors = []
    mappings_to_update = {}
    
    if not transactions:
        errors.append("No hay transacciones de IBKR para transformar")
        return pd.DataFrame(), {}, errors
    
    print(f"Transformando {len(transactions)} transacciones IBKR a formato DeGiro")
    
    # Enriquecer transacciones con información de instrumentos
    for transaction in transactions:
        symbol = transaction['Ticker']
        
        if symbol in instruments:
            instrument_info = instruments[symbol]
            
            # Actualizar información básica
            transaction['ISIN'] = instrument_info['isin']
            transaction['Producto'] = instrument_info['name'] or symbol
            
            # Mapear bolsa/mercado - usar el mercado original para 'Bolsa de'
            # pero mapear para Yahoo/Google exchanges
            transaction['Bolsa de'] = instrument_info['market']
            transaction['Exchange Yahoo'] = instrument_info['yahoo_suffix']
            transaction['Exchange Google'] = instrument_info['google_ex']
            
            # Preparar información para actualizar mappings si es necesario
            isin = instrument_info['isin']
            if isin and (not mapping_data or isin not in mapping_data):
                mappings_to_update[isin] = {
                    'ticker': symbol,
                    'name': instrument_info['name'],
                    'yahoo_suffix': instrument_info['yahoo_suffix'],
                    'google_ex': instrument_info['google_ex']
                }
        else:
            # No se encontró información del instrumento
            errors.append(f"No se encontró información para el símbolo '{symbol}'")
            transaction['ISIN'] = ''
            transaction['Producto'] = symbol
            transaction['Bolsa de'] = transaction.get('Bolsa', '')
            transaction['Exchange Yahoo'] = ''
            transaction['Exchange Google'] = ''
    
    # Convertir a DataFrame
    try:
        df = pd.DataFrame(transactions)
        
        # Asegurar que las columnas numéricas sean del tipo correcto
        numeric_columns = ['Número', 'Precio', 'Valor Local', 'Valor', 'Tipo de cambio', 
                          'Costes Transacción', 'Total']
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # Ordenar por fecha y hora
        if 'Fecha' in df.columns:
            try:
                # Crear columna FechaHora para ordenamiento
                df['FechaHora'] = pd.to_datetime(
                    df['Fecha'] + ' ' + df['Hora'], 
                    format='%d-%m-%Y %H:%M:%S', 
                    errors='coerce'
                )
                df = df.sort_values('FechaHora', ascending=True)
                df = df.drop('FechaHora', axis=1)  # Remover columna temporal
            except Exception as e:
                print(f"Advertencia: Error ordenando por fecha: {e}")
        
        print(f"Transformación IBKR completada: {len(df)} filas, {len(mappings_to_update)} mappings nuevos")
        return df, mappings_to_update, errors
        
    except Exception as e:
        error_msg = f"Error creando DataFrame desde transacciones IBKR: {e}"
        print(error_msg)
        errors.append(error_msg)
        return pd.DataFrame(), {}, errors


def merge_ibkr_with_mapping_data(df_ibkr, mapping_data):
    """
    Enriquece el DataFrame de IBKR con información adicional de mapping_db.json.
    
    Args:
        df_ibkr: DataFrame transformado de IBKR
        mapping_data: Datos cargados de mapping_db.json
    
    Returns:
        DataFrame enriquecido
    """
    if df_ibkr.empty or not mapping_data:
        return df_ibkr
    
    print(f"Enriqueciendo DataFrame IBKR con datos de mapping existentes")
    
    # Enriquecer con información adicional de mappings si existe
    for idx, row in df_ibkr.iterrows():
        isin = row.get('ISIN', '')
        if isin and isin in mapping_data:
            mapping_info = mapping_data[isin]
            
            # Actualizar campos si están vacíos o si el mapping tiene mejor información
            if not row.get('Ticker') and mapping_info.get('ticker'):
                df_ibkr.at[idx, 'Ticker'] = mapping_info['ticker']
            
            if not row.get('Exchange Yahoo') and mapping_info.get('yahoo_suffix'):
                df_ibkr.at[idx, 'Exchange Yahoo'] = mapping_info['yahoo_suffix']
            
            if not row.get('Exchange Google') and mapping_info.get('google_ex'):
                df_ibkr.at[idx, 'Exchange Google'] = mapping_info['google_ex']
            
            # Mejorar nombre del producto si el mapping tiene uno mejor
            if mapping_info.get('name') and len(mapping_info['name']) > len(row.get('Producto', '')):
                df_ibkr.at[idx, 'Producto'] = mapping_info['name']
    
    return df_ibkr

def create_additional_buy_movement_from_reward(original_movement):
    """Crea un movimiento adicional de compra basado en un movimiento de reward"""
    
    additional_movement = CryptoCsvMovement(
        user_id=original_movement.user_id,
        exchange_name=original_movement.exchange_name,
        timestamp_utc=original_movement.timestamp_utc,
        transaction_description=original_movement.transaction_description,
        currency=original_movement.native_currency,  # Moneda nativa del reward original
        amount=abs(original_movement.native_amount) if original_movement.native_amount else None,  # Cantidad nativa del reward original
        to_currency=original_movement.currency,  # Moneda del reward original
        to_amount=abs(original_movement.amount) if original_movement.amount else None,  # Cantidad del reward original
        native_currency=original_movement.native_currency,
        native_amount=original_movement.native_amount,
        native_amount_in_usd=original_movement.native_amount_in_usd,
        transaction_kind=original_movement.transaction_kind,
        transaction_hash=original_movement.transaction_hash,
        csv_filename=original_movement.csv_filename,
        category='Compra',  # Sets the category to 'Compra'
        process_status='OK',  # Sets the process status
        is_additional_movement=True,  # Marks this as an additional movement
        original_movement_id=original_movement.id  # Links to the original movement
    )
    
    # Generar hash único para evitar duplicados
    additional_movement.transaction_hash_unique = additional_movement.generate_hash()
    
    return additional_movement

def delete_additional_movements_for_original(original_movement_id):
    """Elimina todos los movimientos adicionales asociados a un movimiento original"""
    try:
        additional_movements = CryptoCsvMovement.query.filter_by(
            original_movement_id=original_movement_id,
            is_additional_movement=True
        ).all()

        deleted_count = 0
        for movement in additional_movements:
            db.session.delete(movement)
            deleted_count += 1

        return deleted_count
    except Exception as e:
        db.session.rollback()
        raise e

def calculate_rewards_data(movements):
    """Calcula datos de rewards acumulados"""
    
    total_rewards_eur = 0.0
    rewards_by_crypto = {}
    total_rewards_count = 0
    
    for movement in movements:
        if movement.category == 'Rewards' and movement.native_amount:
            # Acumular rewards en EUR
            total_rewards_eur += abs(movement.native_amount)
            total_rewards_count += 1
            
            # Acumular rewards por crypto
            if movement.currency:
                if movement.currency not in rewards_by_crypto:
                    rewards_by_crypto[movement.currency] = {
                        'total_amount': 0.0,
                        'total_value_eur': 0.0,
                        'count': 0
                    }
                
                rewards_by_crypto[movement.currency]['total_amount'] += abs(movement.amount) if movement.amount else 0
                rewards_by_crypto[movement.currency]['total_value_eur'] += abs(movement.native_amount)
                rewards_by_crypto[movement.currency]['count'] += 1
    
    return {
        'total_rewards_eur': total_rewards_eur,
        'rewards_by_crypto': rewards_by_crypto,
        'total_rewards_count': total_rewards_count,
        'avg_reward_value': total_rewards_eur / total_rewards_count if total_rewards_count > 0 else 0
    }

def calculate_total_pnl(movements, own_capital_data, rewards_data):
    """Calcula P&L total considerando capital propio, rewards y trading"""
    
    # P&L de trading (ya lo tienes)
    trading_pnl_data = calculate_crypto_pnl(movements)
    total_trading_pnl = sum(pnl['realized_pnl'] for pnl in trading_pnl_data)
    
    # Rewards = beneficio directo
    total_rewards = rewards_data['total_rewards_eur']
    
    # Capital en riesgo = dinero propio aportado
    capital_at_risk = own_capital_data['net_capital']
    
    # Beneficio/Pérdida total = Trading P&L + Rewards
    total_pnl = total_trading_pnl + total_rewards
    
    # ROI sobre capital propio
    roi_percentage = (total_pnl / capital_at_risk * 100) if capital_at_risk > 0 else 0
    
    return {
        'total_trading_pnl': total_trading_pnl,
        'total_rewards': total_rewards,
        'total_pnl': total_pnl,
        'capital_at_risk': capital_at_risk,
        'roi_percentage': roi_percentage,
        'pnl_breakdown': {
            'trading_percentage': (total_trading_pnl / total_pnl * 100) if total_pnl != 0 else 0,
            'rewards_percentage': (total_rewards / total_pnl * 100) if total_pnl != 0 else 0
        }
    }

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
        movements_to_delete_additional = []
        
        for movement in movements_to_update:
            old_category = movement.category
            movement.category = target_category
            
            # Actualizar process_status según la nueva categoría
            if target_category == 'Sin Categoría':
                movement.process_status = 'SKIP'
            elif movement.process_status == 'SKIP' and target_category != 'Sin Categoría':
                movement.process_status = 'OK'
            
            # Si el movimiento cambió de "Rewards" a otra categoría, marcar para eliminar adicionales
            if old_category == 'Rewards' and target_category != 'Rewards':
                movements_to_delete_additional.append(movement.id)
            
            # Si el movimiento cambió a "Rewards" desde otra categoría, crear movimiento adicional
            elif old_category != 'Rewards' and target_category == 'Rewards':
                # Crear movimiento adicional de compra para el nuevo reward
                additional_movement = create_additional_buy_movement_from_reward(movement)
                
                # Verificar duplicados del movimiento adicional
                existing_additional_hash = CryptoCsvMovement.query.filter_by(
                    user_id=user_id,
                    transaction_hash_unique=additional_movement.transaction_hash_unique
                ).first()
                
                if not existing_additional_hash:
                    db.session.add(additional_movement)
            
            updated_count += 1
        
        # Eliminar movimientos adicionales de movimientos que ya no son "Rewards"
        deleted_additional_count = 0
        for movement_id in movements_to_delete_additional:
            deleted_count = delete_additional_movements_for_original(movement_id)
            deleted_additional_count += deleted_count
        
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
            if deleted_additional_count > 0:
                flash(f'{deleted_additional_count} movimientos adicionales eliminados.', 'info')
            
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

# -*- coding: utf-8 -*-
# ... (otros imports y código existente en app.py) ...
import pandas as pd # Asegúrate que pandas está importado

def prepare_dataframe_for_portfolio_calculation(df):
    """
    Prepara el DataFrame para que calculate_portfolio funcione correctamente.
    Originalmente para ajustar cantidades de IBKR según el signo del Total.
    Ahora, con el guard if row.get('csv_format') == 'ibkr', solo debería
    modificar las filas de IBKR. Las filas de DeGiro deberían pasar sin cambios
    en su columna 'Número'.
    """
    if df.empty:
        print("DEBUG: prepare_dataframe_for_portfolio_calculation recibió un DataFrame vacío.")
        return df
    
    df_portfolio = df.copy() 
    
    print("DEBUG: Iniciando prepare_dataframe_for_portfolio_calculation...")
    stock_isin_to_debug = "SE0009554454" # ¡¡¡REEMPLAZA CON EL ISIN CORRECTO DE SBB!!!
    changes_made_to_sbb = False
    
    for idx, row in df_portfolio.iterrows():
        is_sbb_row = row.get('ISIN') == stock_isin_to_debug
        current_csv_format = row.get('csv_format', 'desconocido') # Obtener el formato del CSV

        if is_sbb_row:
            print(f"  DEBUG SBB (Fila índice pandas: {idx}, Archivo: {row.get('source_file', 'N/A')}):")
            print(f"    Fila ANTES de cualquier ajuste en prepare_dataframe_for_portfolio_calculation:")
            print(f"      Número: {row.get('Número')}, Total: {row.get('Total')}, "
                  f"Valor local: {row.get('Valor local')}, csv_format: {current_csv_format}")

        total_value = row.get('Total') # Obtener Total, puede ser NaN
        if pd.isna(total_value):
            total_value = 0  # Tratar NaN como 0 para la lógica de signo
            if is_sbb_row:
                print(f"    DEBUG SBB (Fila {idx}): 'Total' era NaN, tratado como 0 para la lógica de signo.")
        else:
            # Asegurarse de que total_value sea numérico si no es NaN
            try:
                total_value = float(total_value)
            except ValueError:
                if is_sbb_row:
                    print(f"    DEBUG SBB (Fila {idx}): 'Total' ('{row.get('Total')}') no es numérico y no es NaN. Tratado como 0.")
                total_value = 0


        cantidad_original = row.get('Número')
        if pd.isna(cantidad_original):
            if is_sbb_row:
                print(f"    DEBUG SBB (Fila {idx}): 'Número' (cantidad_original) es NaN. No se ajustará esta fila.")
            continue 
        
        try:
            cantidad_original = float(cantidad_original)
        except ValueError:
            if is_sbb_row:
                print(f"    DEBUG SBB (Fila {idx}): 'Número' (cantidad_original: '{row.get('Número')}') no es numérico. No se ajustará esta fila.")
            continue


        cantidad_final = cantidad_original # Por defecto, no cambiar

        if current_csv_format == 'ibkr':
            if total_value < 0: # Compra IBKR (Total negativo)
                cantidad_final = abs(cantidad_original) 
            elif total_value > 0: # Venta IBKR (Total positivo)
                cantidad_final = -abs(cantidad_original)
            # Si total_value es 0 para IBKR, cantidad_final sigue siendo cantidad_original
            
            if is_sbb_row: # Esto no debería ocurrir si SBB es de DeGiro
                print(f"    DEBUG SBB (Fila {idx}): Identificada ERRÓNEAMENTE como 'ibkr'. "
                      f"total_value: {total_value}, cant_orig: {cantidad_original}, cant_final: {cantidad_final}")

        # Aplicar el cambio si es necesario
        # La condición original `or (is_sbb_row and 'degiro' in current_csv_format)` era para forzar la impresión del debug.
        # Ahora, solo asignamos si realmente hubo un cambio.
        if cantidad_final != cantidad_original:
            df_portfolio.at[idx, 'Número'] = cantidad_final
            if is_sbb_row: # Si es SBB y hubo un cambio (no debería si es DeGiro)
                print(f"    DEBUG SBB (Fila {idx}): ¡CAMBIO INESPERADO APLICADO A FILA DEGIRO!")
                changes_made_to_sbb = True


        if is_sbb_row: # Imprimir estado final para SBB después de la lógica
            print(f"    DEBUG SBB (Fila {idx}): Fila DESPUÉS de lógica de ajuste en prepare_dataframe_for_portfolio_calculation:")
            print(f"      total_value usado: {total_value}, cantidad_original: {cantidad_original}, "
                  f"cantidad_final que se asignaría (si hubo cambio): {cantidad_final}, "
                  f"Valor actual 'Número' en df: {df_portfolio.at[idx, 'Número']}")
            if df_portfolio.at[idx, 'Número'] != row.get('Número'): # Compara con el valor original de la fila en esta iteración
                if not (current_csv_format == 'ibkr' and cantidad_final != cantidad_original) : # Si no es un cambio esperado de IBKR
                     print(f"      ALERTA: ¡El valor 'Número' de SBB cambió de {row.get('Número')} a {df_portfolio.at[idx, 'Número']} y no es una fila IBKR con cambio esperado!")
            
    if changes_made_to_sbb:
        print("ALERTA DEBUG: Se realizaron cambios en 'Número' para SBB en prepare_dataframe_for_portfolio_calculation, lo cual no se esperaba para filas DeGiro.")
    else:
        print("DEBUG: No se realizaron cambios inesperados en 'Número' para SBB en prepare_dataframe_for_portfolio_calculation.")

    print("DEBUG: Fin de prepare_dataframe_for_portfolio_calculation.")
    return df_portfolio

# ... (el resto de tu app.py, incluyendo calculate_portfolio y process_uploaded_csvs_unified
#      con sus respectivos bloques de depuración que ya tienes) ...

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
    elif transaction_kind in DEPOSIT_TRANSACTION_KINDS:
        return 'Deposito'
    else:
        return 'Sin Categoría'


def detect_orphans(movements):
    """Detecta movimientos huérfanos basado en acumulados por criptomoneda"""
    
    # Agrupar por moneda y ordenar por fecha
    currency_movements = {}
    for movement in movements:
        if movement.currency and movement.category in ['Compra', 'Venta', 'Deposito', 'Rewards', 'Staking Lock', 'Staking UnLock']:
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
            if movement.category in ['Compra', 'Deposito', 'Rewards'] and movement.amount:
                # Compras, Depósitos y Rewards suman al balance
                balance += abs(movement.amount)
            elif movement.category == 'Venta' and movement.amount:
                sale_amount = abs(movement.amount)
                if balance < sale_amount:
                    orphans.append(movement.id)
                else:
                    balance -= sale_amount
            elif movement.category == 'Staking Lock' and movement.amount:
                staking_balance += abs(movement.amount)
            elif movement.category == 'Staking UnLock' and movement.amount:
                unlock_amount = abs(movement.amount)
                if staking_balance < unlock_amount:
                    orphans.append(movement.id)
                else:
                    staking_balance -= unlock_amount
    
    return orphans



def calculate_own_capital(movements):
    """Calcula el capital propio aportado al exchange (Depositos - Retiros en EUR)"""
    
    total_deposits = 0.0
    total_withdrawals = 0.0
    
    for movement in movements:
        # Solo contar movimientos adicionales para depósitos (fondos propios reales)
        if (movement.category == 'Deposito' and 
            movement.is_additional_movement and 
            movement.native_amount):
            total_deposits += abs(movement.native_amount)
        elif movement.category == 'Retiro' and movement.native_amount:
            total_withdrawals += abs(movement.native_amount)
    
    return {
        'total_deposits': total_deposits,
        'total_withdrawals': total_withdrawals,
        'net_capital': total_deposits - total_withdrawals
    }

def calculate_crypto_pnl(movements):
    """Calcula P&L por criptomoneda basado en movimientos de compra/venta no huérfanos"""
    
    # Filtrar solo movimientos válidos para P&L (NO incluir Deposito adicionales)
    valid_movements = [
        m for m in movements 
        if m.category in ['Compra', 'Venta'] 
        and m.process_status != 'Huérfano'
        and not m.is_additional_movement  # Excluir movimientos adicionales
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


def detect_csv_format(file_content_or_path):
    """
    Detecta si un CSV es formato DeGiro o IBKR basándose en su contenido.
    
    Args:
        file_content_or_path: Puede ser:
            - String con el contenido del archivo
            - Path del archivo
            - Objeto file-like (BytesIO)
    
    Returns:
        str: 'degiro', 'ibkr', o 'unknown'
    """
    try:
        # Leer las primeras líneas del archivo
        if isinstance(file_content_or_path, str):
            if os.path.exists(file_content_or_path):
                # Es una ruta de archivo
                with open(file_content_or_path, 'r', encoding='utf-8') as f:
                    first_lines = [f.readline().strip() for _ in range(10)]
            else:
                # Es contenido directo
                first_lines = file_content_or_path.split('\n')[:10]
        else:
            # Es un objeto file-like (BytesIO)
            file_content_or_path.seek(0)
            content = file_content_or_path.read()
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8')
                except UnicodeDecodeError:
                    content = content.decode('latin-1')
            first_lines = content.split('\n')[:10]
            file_content_or_path.seek(0)  # Volver al inicio para procesamiento posterior
        
        # Verificar formato IBKR
        # IBKR tiene líneas que empiezan con "Statement,Header", "Statement,Data", etc.
        ibkr_indicators = [
            'Statement,Header',
            'Statement,Data', 
            'Operaciones,Header',
            'Operaciones,Data',
            'Información de instrumento financiero,Header',
            'Información de instrumento financiero,Data'
        ]
        
        for line in first_lines:
            for indicator in ibkr_indicators:
                if line.startswith(indicator):
                    print(f"Formato IBKR detectado: línea '{line[:50]}...'")
                    return 'ibkr'
        
        # Verificar formato DeGiro
        # DeGiro tiene headers directos como "Fecha,Hora,Producto,ISIN,Bolsa de"
        degiro_indicators = [
            'Fecha', 'Hora', 'Producto', 'ISIN', 'Bolsa de', 
            'Número', 'Precio', 'Valor local', 'Valor', 'Total'
        ]
        
        for line in first_lines:
            if any(indicator in line for indicator in degiro_indicators):
                # Verificar que sea realmente un header de DeGiro (múltiples columnas)
                columns = line.split(',')
                degiro_matches = sum(1 for col in columns if any(ind in col for ind in degiro_indicators))
                if degiro_matches >= 3:  # Al menos 3 columnas conocidas de DeGiro
                    print(f"Formato DeGiro detectado: línea '{line[:50]}...'")
                    return 'degiro'
        
        print("Formato de CSV no reconocido")
        return 'unknown'
        
    except Exception as e:
        print(f"Error detectando formato CSV: {e}")
        return 'unknown'



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
    """
    Calcula un conjunto completo de métricas financieras a lo largo del tiempo para el usuario.
    ACTUALIZADA para incluir operaciones de tipo 'Reinversión'.
    """
    # Obtiene las operaciones del broker para el usuario, ordenadas por fecha ascendente
    broker_ops = BrokerOperation.query.filter_by(user_id=user_id).order_by(BrokerOperation.date.asc()).all()

    # Carga las datos del CSV procesado del usuario (que contiene los movimientos de activos)
    _, csv_data_list, _ = load_user_portfolio(user_id)
    asset_movements_raw = csv_data_list if csv_data_list and isinstance(csv_data_list, list) else []

    all_events = [] # Lista para almacenar todos los eventos (operaciones de broker y transacciones de activos)

    # Procesa las operaciones del broker
    for op in broker_ops:
        # ACTUALIZADO: Incluir 'Reinversión' pero NO como cash flow externo
        is_external_cf = op.operation_type in ['Ingreso', 'Retirada', 'Comisión']
        # 'Reinversión' NO es cash flow externo (beneficio interno)
        
        # Para TWRR, los ingresos son flujos de caja positivos (dinero que entra al portfolio desde fuera),
        # las retiradas son flujos de caja negativos (dinero que sale del portfolio hacia fuera).
        # Las comisiones pagadas al broker se consideran como una "retirada" o un coste que disminuye el valor del portfolio.
        # Las reinversiones son NEUTRALES para TWRR (beneficio interno, no cash flow externo).
        cf_value = 0.0 # Valor del flujo de caja para el cálculo del TWRR
        if op.operation_type == 'Ingreso': # Dinero que entra al broker (flujo de caja positivo para TWRR)
            cf_value = -op.amount # op.amount es negativo, así que -(-x) = +x (positivo para TWRR)
        elif op.operation_type == 'Retirada': # Dinero que sale del broker (flujo de caja negativo para TWRR)
            cf_value = -op.amount # op.amount es positivo, así que -(+x) = -x (negativo para TWRR)
        elif op.operation_type == 'Comisión': # Comisión pagada (flujo de caja negativo para TWRR)
            cf_value = op.amount # op.amount es negativo, mantenemos negativo para TWRR
        elif op.operation_type == 'Reinversión': # ← NUEVO: Beneficio reinvertido
            cf_value = 0.0 # NEUTRAL para TWRR (beneficio interno, no afecta cash flows externos)

        all_events.append({
            'date': op.date,
            'type': 'broker_op',
            'value': op.amount, # 'value' es el impacto en el capital propio (signo ya ajustado en BrokerOperation)
            'operation_type': op.operation_type,  # ← AÑADIDO para distinguir tipos
            'concept': op.concept,  # ← AÑADIDO para distinguir conceptos
            'is_external_ewc_cf': is_external_cf, # Indica si es un flujo de caja externo para TWRR
            'ewc_cf_value': cf_value # 'ewc_cf_value' es el flujo de caja para TWRR con el signo correcto
        })

    # Procesa los movimientos de activos (compras/ventas del CSV) - SIN CAMBIOS
    for movement in asset_movements_raw:
        fecha_str = movement.get('Fecha')
        total_val = movement.get('Total') # Valor total de la transacción (negativo para compras, positivo para ventas)
        isin = movement.get('ISIN')
        cantidad_abs = movement.get('Cantidad') # Cantidad absoluta del activo

        if fecha_str and isinstance(fecha_str, str) and total_val is not None and isin and cantidad_abs is not None:
            try:
                event_date = datetime.strptime(fecha_str[:10], '%d-%m-%Y').date() # Parsea la fecha
                all_events.append({
                    'date': event_date,
                    'type': 'asset_trade',
                    'value': float(total_val),
                    'isin': isin,
                    'cantidad': float(cantidad_abs),
                    'is_external_ewc_cf': False, # Las compras/ventas de activos no son flujos de caja externos para TWRR
                    'ewc_cf_value': 0.0
                })
            except Exception as e:
                print(f"Metrics: Error procesando movimiento de activo: {movement}, Error: {e}")
        else:
            print(f"Metrics: Movimiento de activo omitido por datos faltantes: {movement}")

    # Si no hay eventos, retorna valores por defecto
    if not all_events:
        return {
            'current_capital_propio': 0.0, 'current_trading_cash_flow': 0.0,
            'current_realized_specific_pnl': 0.0, 'current_dividend_pnl': 0.0,  # ← AÑADIDO
            'current_apalancamiento': 0.0, 'first_event_date': None, 'last_event_date': None,
            'total_cost_of_all_buys_ever': 0.0,
            'twr_ewc_percentage': 0.0, 'twr_ewc_annualized_percentage': 0.0,
            'daily_chart_labels': [], 'daily_capital_propio_series': [],
            'daily_apalancamiento_series': [], 'daily_realized_specific_pnl_series': [],
            'daily_dividend_pnl_series': [],  # ← AÑADIDO
            'daily_twr_ewc_index_series': [], 'daily_twr_percentage_series': []
        }

    # Ordena todos los eventos por fecha, y dentro de la misma fecha, los flujos de caja externos primero
    all_events.sort(key=lambda x: (x['date'], 0 if x['is_external_ewc_cf'] else 1))

    first_event_date_overall = all_events[0]['date'] # Fecha del primer evento

    # Listas para las series diarias del gráfico
    daily_chart_labels = []
    daily_capital_propio_series = []
    daily_apalancamiento_series = []
    daily_realized_specific_pnl_series = []
    daily_dividend_pnl_series = []  # ← AÑADIDO
    daily_twr_ewc_index_series = [] # Serie del índice TWRR (base 100)
    daily_twr_percentage_series = [] # Serie del TWRR en porcentaje

    # Acumuladores de métricas
    cp_acc = 0.0  # Capital Propio Acumulado (Aportaciones netas al broker)
    tcf_acc = 0.0 # Trading Cash Flow Acumulado (Neto de compras y ventas de activos)
    rsp_acc = 0.0 # Realized Specific P&L Acumulado (Beneficio/Pérdida realizado por ventas de activos)
    div_acc = 0.0 # ← AÑADIDO: P/L Dividendos Acumulado (Beneficios de dividendos)

    holdings = {} # Diccionario para hacer seguimiento de las posiciones actuales (cantidad y coste base)
    total_buy_cost_acc = 0.0 # Coste base de todas las compras realizadas

    # Variables para el cálculo del TWRR (Time-Weighted Rate of Return)
    twr_factors = [] # Lista de factores de rendimiento entre flujos de caja
    cte_after_prev_cf = 0.0  # Valor de la Cartera (EWC) justo DESPUÉS del flujo de caja externo anterior
    current_twr_idx = 100.0 # Índice TWRR, comienza en 100
    twr_started = False # Flag para indicar si el cálculo del TWRR ha comenzado
    first_cf_date_for_annualization = None # Fecha del primer flujo de caja para el cálculo anualizado del TWRR

    final_apalancamiento_calculated = 0.0 # Apalancamiento calculado al final del período

    unique_dates = sorted(list(set(e['date'] for e in all_events))) # Lista única de fechas con eventos
    event_pointer = 0 # Puntero para recorrer la lista all_events

    # Itera sobre cada día único con eventos
    for current_day in unique_dates:
        # Procesa los flujos de caja externos (Broker Operations) PRIMERO en el día para TWRR
        # ACTUALIZADO: incluir dividendos en EWC
        ewc_before_any_cf_today = (-cp_acc) + rsp_acc + div_acc  # ← EWC incluye dividendos

        # Bucle para procesar todos los flujos de caja externos del día actual
        temp_event_pointer_for_cf = event_pointer
        while temp_event_pointer_for_cf < len(all_events) and all_events[temp_event_pointer_for_cf]['date'] == current_day:
            event = all_events[temp_event_pointer_for_cf]
            if event['is_external_ewc_cf']: # Si es un flujo de caja externo (operación de broker)
                # ACTUALIZADO: incluir dividendos en EWC
                ewc_val_for_factor_calc = (-cp_acc) + rsp_acc + div_acc  # ← EWC incluye dividendos

                if twr_started: # Si el TWRR ya ha comenzado
                    if abs(cte_after_prev_cf) > 1e-9: # Evita división por cero
                        period_factor = ewc_val_for_factor_calc / cte_after_prev_cf
                        twr_factors.append(period_factor)
                        current_twr_idx *= period_factor # Actualiza el índice TWRR
                    elif ewc_val_for_factor_calc == 0 and cte_after_prev_cf == 0: # Si ambos son 0, el factor es 1
                        twr_factors.append(1.0)
                
                # Actualiza el Capital Propio (cp_acc) con el valor de la operación del broker
                # SOLO para operaciones externas (Ingreso, Retirada, Comisión)
                cp_acc += event['value']
                
                # ACTUALIZADO: incluir dividendos en EWC
                cte_after_prev_cf = (-cp_acc) + rsp_acc + div_acc  # ← EWC incluye dividendos

                # Si el TWRR no ha comenzado y el valor de la cartera es significativo
                if not twr_started and abs(cte_after_prev_cf) > 1e-9:
                    twr_started = True
                    current_twr_idx = 100.0 # Inicia el índice TWRR en 100
                    if first_cf_date_for_annualization is None:
                         first_cf_date_for_annualization = current_day # Guarda la fecha del primer flujo para anualizar
            temp_event_pointer_for_cf +=1 # Avanza el puntero temporal

        # Procesa las transacciones de activos Y reinversiones del día actual
        temp_rsp_day_change = 0.0 # Cambio en P/L realizado durante el día
        temp_div_day_change = 0.0 # ← AÑADIDO: Cambio en P/L dividendos durante el día
        temp_tcf_day_change = 0.0 # Cambio en Trading Cash Flow durante el día

        while event_pointer < len(all_events) and all_events[event_pointer]['date'] == current_day:
            event = all_events[event_pointer]
            if event['type'] == 'broker_op':
                # ACTUALIZADO: Procesar reinversiones (beneficios internos)
                if event.get('operation_type') == 'Reinversión':
                    if event.get('concept') == 'Dividendo':
                        temp_div_day_change += abs(event['value'])  # Dividendos siempre positivos
                    # Aquí podrías añadir otros tipos de reinversión en el futuro
                    
                # Las operaciones externas (Ingreso, Retirada, Comisión) ya se procesaron arriba para TWRR
                # No necesitan procesamiento adicional aquí
                
            elif event['type'] == 'asset_trade': # Si es una transacción de activo
                temp_tcf_day_change += event['value'] # 'value' es el 'Total' del CSV (negativo para compras, positivo para ventas)
                isin, qty, val = event['isin'], event['cantidad'], event['value']

                if val < 0: # Compra de activo
                    total_buy_cost_acc += abs(val) # Acumula el coste base total de todas las compras
                    if isin not in holdings: holdings[isin] = {'qty': 0.0, 'total_cost_basis': 0.0}
                    holdings[isin]['qty'] += qty # Añade la cantidad comprada
                    holdings[isin]['total_cost_basis'] += abs(val) # Añade el coste de la compra al coste base de la posición
                elif val > 0: # Venta de activo
                    if isin in holdings and holdings[isin]['qty'] > 1e-6: # Si hay algo que vender
                        p = holdings[isin] # Posición actual
                        avg_c = p['total_cost_basis']/p['qty'] if p['qty'] > 0 else 0 # Coste medio de la posición
                        q_sold = min(qty, p['qty']) # Cantidad vendida (no más de lo que se tiene)
                        cost_sold = q_sold * avg_c # Coste de la parte vendida
                        proceeds = (val/qty)*q_sold if qty > 0 else 0 # Ingresos por la venta
                        pnl_sale = proceeds - cost_sold # P/L realizado de esta venta específica
                        temp_rsp_day_change += pnl_sale # Acumula el P/L realizado del día
                        p['qty'] -= q_sold # Actualiza la cantidad de la posición
                        p['total_cost_basis'] -= cost_sold # Actualiza el coste base de la posición
                        if p['qty'] < 1e-6: # Si la cantidad es prácticamente cero
                            p['qty'] = 0.0
                            p['total_cost_basis'] = 0.0
            event_pointer += 1 # Avanza el puntero principal de eventos

        rsp_acc += temp_rsp_day_change # Actualiza el P/L Realizado Acumulado
        div_acc += temp_div_day_change # ← AÑADIDO: Actualiza el P/L Dividendos Acumulado
        tcf_acc += temp_tcf_day_change # Actualiza el Trading Cash Flow Acumulado

        # ACTUALIZADO: Calcula el Apalancamiento al final del día incluyendo dividendos
        val_inv_bruto = max(0, -tcf_acc)
        aport_netas_usr = max(0, -cp_acc)  # Capital aportado usuario
        gnc_trading = max(0, tcf_acc)      # Ganancias trading en cash  
        gnc_dividendos = div_acc           # ← AÑADIDO: Ganancias dividendos (siempre positivas)
        
        # Fondos disponibles sin deuda = Aportaciones + Ganancias Trading + Ganancias Dividendos
        fondos_disp_s_d = aport_netas_usr + rsp_acc + gnc_dividendos # Usar rsp_acc en lugar de gnc_trading
        apalancamiento_eod = max(0, val_inv_bruto - fondos_disp_s_d)
        final_apalancamiento_calculated = apalancamiento_eod # Guarda el último apalancamiento calculado

        # Añade las métricas del día a las series para el gráfico
        daily_chart_labels.append(current_day.strftime('%Y-%m-%d'))
        daily_capital_propio_series.append(round(cp_acc, 2))
        daily_apalancamiento_series.append(round(apalancamiento_eod, 2))
        daily_realized_specific_pnl_series.append(round(rsp_acc, 2))
        daily_dividend_pnl_series.append(round(div_acc, 2))  # ← AÑADIDO

        # ACTUALIZADO: Calcula el índice TWRR diario incluyendo dividendos
        if twr_started:
            ewc_eod = (-cp_acc) + rsp_acc + div_acc  # ← EWC incluye dividendos
            if abs(cte_after_prev_cf) > 1e-9: # Evita división por cero
                factor_interno_periodo = ewc_eod / cte_after_prev_cf # Factor de rendimiento desde el último flujo de caja
                daily_twr_ewc_index_series.append(round(current_twr_idx * factor_interno_periodo, 2))
            else: # Si el valor de la cartera era 0 después del último CF, y continúa siendo 0, el índice no cambia.
                 daily_twr_ewc_index_series.append(round(current_twr_idx, 2))
        else: # Si el TWRR no ha comenzado
            daily_twr_ewc_index_series.append(100.0) # Muestra 100 (base)

    last_event_date_overall = all_events[-1]['date'] if all_events else date.today() # Fecha del último evento

    # Calcula el factor TWRR final global
    final_overall_twr_factor = 1.0
    if twr_factors: # Si ha habido flujos de caja y se han calculado factores
        for factor in twr_factors:
            final_overall_twr_factor *= factor

    # ACTUALIZADO: Aplica el factor del último tramo incluyendo dividendos
    final_ewc_val_for_last_factor = (-cp_acc) + rsp_acc + div_acc  # ← EWC incluye dividendos
    if twr_started and abs(cte_after_prev_cf) > 1e-9:
         last_stretch_factor = final_ewc_val_for_last_factor / cte_after_prev_cf
         final_overall_twr_factor *= last_stretch_factor
    elif twr_started and final_ewc_val_for_last_factor == 0 and cte_after_prev_cf == 0: # Si empezó en 0 y terminó en 0
         final_overall_twr_factor *= 1.0 # El factor es 1

    twr_ewc_percentage = (final_overall_twr_factor - 1) * 100 if twr_started else 0.0

    # Anualiza el TWRR - SIN CAMBIOS
    twr_ewc_annualized_percentage = 0.0
    if twr_started and first_cf_date_for_annualization and last_event_date_overall:
        if final_overall_twr_factor > 0: # Solo se puede anualizar si el factor es positivo
            dias_periodo_twr = (last_event_date_overall - first_cf_date_for_annualization).days
            if dias_periodo_twr >= 1: # Se necesita al menos un día para anualizar
                # Asegura que anios_periodo_twr no sea cero si dias_periodo_twr es pequeño
                anios_periodo_twr = max(dias_periodo_twr / 365.25, 1/365.25)
                twr_ewc_annualized_percentage = (math.pow(final_overall_twr_factor, 1.0 / anios_periodo_twr) - 1) * 100
            elif dias_periodo_twr == 0 : # Si el período es de un solo día
                 twr_ewc_annualized_percentage = twr_ewc_percentage # El TWRR es el mismo que el del período
        elif final_overall_twr_factor <= 0 and abs(cte_after_prev_cf if cte_after_prev_cf is not None else 0.0) > 1e-9 :
            # Si el valor de la cartera se vuelve cero o negativo desde un valor positivo, la pérdida es del 100% o más.
            twr_ewc_annualized_percentage = -100.0

    current_apalancamiento_final = final_apalancamiento_calculated # Apalancamiento final

    # Transforma la serie del índice TWRR a porcentaje de cambio desde 100
    daily_twr_percentage_series = [round(val - 100, 2) if isinstance(val, (int, float)) else 0 for val in daily_twr_ewc_index_series]

    return {
        'current_capital_propio': round(cp_acc, 2),
        'current_trading_cash_flow': round(tcf_acc, 2),
        'current_realized_specific_pnl': round(rsp_acc, 2),
        'current_dividend_pnl': round(div_acc, 2),  # ← AÑADIDO
        'current_apalancamiento': round(current_apalancamiento_final, 2),
        'first_event_date': first_event_date_overall,
        'last_event_date': last_event_date_overall,
        'total_cost_of_all_buys_ever': round(total_buy_cost_acc, 2), # Coste base total de todas las compras
        'twr_ewc_percentage': round(twr_ewc_percentage, 2) if isinstance(twr_ewc_percentage, float) and math.isfinite(twr_ewc_percentage) else "N/A",
        'twr_ewc_annualized_percentage': round(twr_ewc_annualized_percentage, 2) if isinstance(twr_ewc_annualized_percentage, float) and math.isfinite(twr_ewc_annualized_percentage) else "N/A",
        'daily_chart_labels': daily_chart_labels,
        'daily_capital_propio_series': daily_capital_propio_series,
        'daily_apalancamiento_series': daily_apalancamiento_series,
        'daily_realized_specific_pnl_series': daily_realized_specific_pnl_series,
        'daily_dividend_pnl_series': daily_dividend_pnl_series,  # ← AÑADIDO
        'daily_twr_ewc_index_series': daily_twr_ewc_index_series, # Serie del índice TWRR (base 100)
        'daily_twr_percentage_series': daily_twr_percentage_series # Serie del TWRR en %
    }



@app.route('/office/goal_details/<int:goal_id>', methods=['GET'])
@login_required
def goal_details(goal_id):
    """Obtiene detalles de un objetivo específico usando modelo Goal."""
    try:
        # CORREGIDO: Buscar en modelo Goal en lugar de AlertConfiguration
        goal = Goal.query.filter_by(id=goal_id, user_id=current_user.id).first()
        
        if not goal:
            return jsonify({'success': False, 'message': 'Objetivo no encontrado'})
        
        # Calcular estado actual
        try:
            goal_status = calculate_goal_status_with_model(goal)
        except Exception as e:
            goal_status = {'error': f'Error calculando estado: {str(e)}'}
        
        # Generar HTML con detalles
        html_content = f"""
        <div class="goal-details">
            <h6>Información General</h6>
            <p><strong>Tipo:</strong> {get_friendly_goal_name(goal)}</p>
            <p><strong>Creado:</strong> {goal.created_at.strftime('%d/%m/%Y %H:%M')}</p>
        """
        
        # Estado actual
        if goal_status.get('error'):
            html_content += f"<div class='alert alert-warning'>{goal_status['error']}</div>"
        else:
            html_content += "<h6>Estado Actual</h6>"
            
            if goal_status.get('progress_percentage') is not None:
                progress = goal_status['progress_percentage']
                html_content += f"""
                <div class="progress mb-2">
                    <div class="progress-bar bg-{'success' if progress >= 80 else 'warning' if progress >= 50 else 'danger'}" 
                         style="width: {progress}%">{progress:.1f}%</div>
                </div>
                """
            
            # Detalles específicos por tipo
            if goal.goal_type == 'target_amount':
                html_content += f"""
                <p><strong>Objetivo:</strong> {goal_status.get('target_amount', 0):.2f} €</p>
                <p><strong>Actual:</strong> {goal_status.get('current_value', 0):.2f} €</p>
                <p><strong>Falta:</strong> {goal_status.get('amount_needed', 0):.2f} €</p>
                """
                if goal_status.get('months_remaining'):
                    html_content += f"<p><strong>Tiempo restante:</strong> {goal_status['months_remaining']} meses</p>"
            
            elif goal.goal_type == 'savings_monthly':
                html_content += f"""
                <p><strong>Meta mensual:</strong> {goal_status.get('monthly_target', 0):.2f} €</p>
                <p><strong>Este mes:</strong> {goal_status.get('current_month_savings', 0):.2f} €</p>
                <p><strong>Acumulado:</strong> {goal_status.get('actual_savings', 0):.2f} € / {goal_status.get('cumulative_target', 0):.2f} €</p>
                """
            
            elif goal.goal_type == 'debt_threshold':
                html_content += f"""
                <p><strong>Límite objetivo:</strong> {goal_status.get('target_debt_percentage', 0)}% del salario</p>
                <p><strong>Uso actual:</strong> {goal_status.get('current_debt_percentage', 0):.1f}%</p>
                <p><strong>Margen disponible:</strong> {goal_status.get('debt_margin', 0):.2f} €/mes</p>
                """
        
        html_content += "</div>"
        
        return jsonify({'success': True, 'html': html_content})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/test_scheduler_status')
@login_required
def test_scheduler_status():
    """Ruta temporal para verificar el estado del scheduler."""
    if current_user.username != 'admin':
        return "No autorizado", 403
    
    jobs = scheduler.get_jobs()
    status = f"""
    <h2>Estado del Scheduler</h2>
    <p>Jobs activos: {len(jobs)}</p>
    """
    
    for job in jobs:
        status += f"""
        <p><strong>{job.id}</strong>: {job.name}<br>
        Próxima ejecución: {job.next_run_time}<br>
        Trigger: {job.trigger}</p>
        """
    
    status += '<br><a href="/">Volver al inicio</a>'
    return status

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
            old_category = movement.category
            movement.category = form.category.data
            movement.process_status = form.process_status.data
            
            # Si se marca como "Sin Categoría", automáticamente debe ser "SKIP"
            if movement.category == 'Sin Categoría':
                movement.process_status = 'SKIP'
            
            # Manejar cambios en movimientos adicionales
            if old_category == 'Rewards' and movement.category != 'Rewards':
                # Si cambió de Rewards a otra categoría, eliminar movimientos adicionales
                deleted_count = delete_additional_movements_for_original(movement.id)
                if deleted_count > 0:
                    flash(f'{deleted_count} movimientos adicionales eliminados.', 'info')
            
            elif old_category != 'Rewards' and movement.category == 'Rewards':
                # Si cambió a Rewards desde otra categoría, crear movimiento adicional
                additional_movement = create_additional_buy_movement_from_reward(movement)
                
                # Verificar duplicados del movimiento adicional
                existing_additional_hash = CryptoCsvMovement.query.filter_by(
                    user_id=current_user.id,
                    transaction_hash_unique=additional_movement.transaction_hash_unique
                ).first()
                
                if not existing_additional_hash:
                    db.session.add(additional_movement)
                    flash('Movimiento adicional de compra creado automáticamente.', 'info')
            
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
    """Elimina un mapeo de categoría y revierte los cambios aplicados"""
    mapping = CryptoCategoryMapping.query.filter_by(
        id=mapping_id,
        user_id=current_user.id
    ).first_or_404()
    
    try:
        # Guardar datos del mapeo antes de eliminarlo
        mapping_type = mapping.mapping_type
        source_value = mapping.source_value
        target_category = mapping.target_category
        
        # Encontrar movimientos que fueron afectados por este mapeo
        if mapping_type == 'Tipo':
            affected_movements = CryptoCsvMovement.query.filter_by(
                user_id=current_user.id,
                transaction_kind=source_value,
                category=target_category
            ).all()
        else:  # Descripción
            affected_movements = CryptoCsvMovement.query.filter_by(
                user_id=current_user.id,
                transaction_description=source_value,
                category=target_category
            ).all()
        
        # Eliminar el mapeo
        db.session.delete(mapping)
        db.session.flush()  # Asegurar que el mapeo se elimine antes de recategorizar
        
        # Recategorizar los movimientos afectados sin este mapeo
        reverted_count = 0
        movements_to_delete_additional = []
        movements_to_create_additional = []
        
        for movement in affected_movements:
            old_category = movement.category
            
            # Recategorizar usando la lógica automática (sin el mapeo eliminado)
            new_category = categorize_transaction(
                movement.transaction_kind, 
                movement.transaction_description, 
                current_user.id
            )
            
            # Solo actualizar si la categoría cambia
            if movement.category != new_category:
                movement.category = new_category
                
                # Actualizar process_status según la nueva categoría
                if new_category == 'Sin Categoría':
                    movement.process_status = 'SKIP'
                elif movement.process_status == 'SKIP' and new_category != 'Sin Categoría':
                    movement.process_status = 'OK'
                
                # Manejar movimientos adicionales según el cambio de categoría
                if old_category == 'Rewards' and new_category != 'Rewards':
                    # Si cambió de Rewards a otra categoría, marcar para eliminar adicionales
                    movements_to_delete_additional.append(movement.id)
                elif old_category != 'Rewards' and new_category == 'Rewards':
                    # Si cambió a Rewards desde otra categoría, marcar para crear adicionales
                    movements_to_create_additional.append(movement)
                
                reverted_count += 1
        
        # Eliminar movimientos adicionales de movimientos que ya no son "Rewards"
        deleted_additional_count = 0
        for movement_id in movements_to_delete_additional:
            deleted_count = delete_additional_movements_for_original(movement_id)
            deleted_additional_count += deleted_count
        
        # Crear movimientos adicionales para movimientos que ahora son "Rewards"
        created_additional_count = 0
        for movement in movements_to_create_additional:
            additional_movement = create_additional_buy_movement_from_reward(movement)
            
            # Verificar duplicados del movimiento adicional
            existing_additional_hash = CryptoCsvMovement.query.filter_by(
                user_id=current_user.id,
                transaction_hash_unique=additional_movement.transaction_hash_unique
            ).first()
            
            if not existing_additional_hash:
                db.session.add(additional_movement)
                created_additional_count += 1
        
        db.session.commit()
        
        # Recalcular huérfanos después de los cambios de categorías
        all_movements = CryptoCsvMovement.query.filter_by(user_id=current_user.id).all()
        orphan_ids = detect_orphans(all_movements)
        
        # Actualizar estado de huérfanos
        if orphan_ids:
            CryptoCsvMovement.query.filter(
                CryptoCsvMovement.id.in_(orphan_ids),
                CryptoCsvMovement.user_id == current_user.id
            ).update({'process_status': 'Huérfano'}, synchronize_session=False)
            db.session.commit()
        
        flash(f'Mapeo eliminado correctamente. {reverted_count} movimientos revertidos a categorización automática.', 'success')
        if deleted_additional_count > 0:
            flash(f'{deleted_additional_count} movimientos adicionales eliminados.', 'info')
        if created_additional_count > 0:
            flash(f'{created_additional_count} movimientos adicionales de compra creados automáticamente.', 'info')
        
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




@app.route('/portfolio_dashboard_data')
@login_required
def portfolio_dashboard_data():
    """
    Endpoint actualizado que incluye métricas de dividendos separadas.
    """
    user_id = current_user.id
    # Carga las datos del portfolio del usuario (lista de posiciones actuales)
    portfolio_summary_from_db, _, _ = load_user_portfolio(user_id)

    # Obtiene los items de la watchlist para mapear ISIN a sector y país
    watchlist_items_db = WatchlistItem.query.filter_by(user_id=user_id).all()
    watchlist_map = {
        item.isin: {'sector': item.sector, 'pais': item.pais}
        for item in watchlist_items_db if item.isin # Solo si el item tiene ISIN
    }

    sector_values = {} # Diccionario para acumular valor por sector
    country_values = {} # Diccionario para acumular valor por país
    total_market_value_eur = 0.0 # Valor total de mercado de todas las posiciones
    total_cost_basis_eur_open_positions = 0.0 # Coste base total de las posiciones abiertas
    total_unrealized_pl_eur = 0.0 # P/L no realizado total de las posiciones abiertas

    # Procesa cada item (posición) del portfolio
    if portfolio_summary_from_db: # portfolio_summary_from_db es la lista de items/posiciones
        for item in portfolio_summary_from_db:
            try:
                # Obtiene y convierte a float los valores numéricos, gestionando None o strings vacíos
                market_value = float(item.get('market_value_eur', 0.0) or 0.0)
                item_cost_basis = float(item.get('cost_basis_eur_est', 0.0) or 0.0)
                item_pl_eur = float(item.get('pl_eur_est', 0.0) or 0.0)
                isin = item.get('ISIN')

                # Acumula totales
                total_market_value_eur += market_value
                total_cost_basis_eur_open_positions += item_cost_basis
                total_unrealized_pl_eur += item_pl_eur

                # Agrupa por sector
                sector = 'Desconocido/Otros' # Valor por defecto
                if isin and isin in watchlist_map and watchlist_map[isin].get('sector'):
                    sector_item = watchlist_map[isin]['sector']
                    if sector_item and sector_item.strip(): # Asegura que no sea string vacío
                        sector = sector_item
                sector_values[sector] = sector_values.get(sector, 0.0) + market_value

                # Agrupa por país
                pais = 'Desconocido/Otros' # Valor por defecto
                if isin and isin in watchlist_map and watchlist_map[isin].get('pais'):
                    pais_item = watchlist_map[isin]['pais']
                    if pais_item and pais_item.strip(): # Asegura que no sea string vacío
                        pais = pais_item
                country_values[pais] = country_values.get(pais, 0.0) + market_value
            except (ValueError, TypeError) as e:
                print(f"Dashboard: Error procesando item del portfolio {item.get('ISIN')} para gráficos de tarta: {e}")
                continue # Salta a la siguiente iteración si hay un error con este item

    # ACTUALIZADO: Obtiene métricas cruzadas en el tiempo (incluyendo dividendos separados)
    crosstime_metrics = get_current_financial_crosstime_metrics(user_id)

    # ACTUALIZADO: Extrae las métricas necesarias incluyendo las nuevas
    current_capital_propio_abs = abs(crosstime_metrics.get('current_capital_propio', 0.0))
    current_apalancamiento = crosstime_metrics.get('current_apalancamiento', 0.0)
    current_realized_specific_pnl = crosstime_metrics.get('current_realized_specific_pnl', 0.0)
    current_dividend_pnl = crosstime_metrics.get('current_dividend_pnl', 0.0)  # ← AÑADIDO
    rentabilidad_acumulada_percentage = crosstime_metrics.get('twr_ewc_percentage', "N/A")
    rentabilidad_media_anual_percentage = crosstime_metrics.get('twr_ewc_annualized_percentage', "N/A")

    # ACTUALIZADO: Calcula el beneficio/pérdida global incluyendo dividendos
    # P/L Global = P/L No Realizado + P/L Trading Realizado + P/L Dividendos
    beneficio_perdida_global = total_unrealized_pl_eur + current_realized_specific_pnl + current_dividend_pnl

    # Calcula la rentabilidad porcentual de las posiciones abiertas sobre su coste base
    overall_return_percentage_open_positions = (total_unrealized_pl_eur / total_cost_basis_eur_open_positions * 100) if total_cost_basis_eur_open_positions != 0 else 0.0

    # Prepara las datos para los gráficos de tarta (sector y país)
    sector_chart_data = group_top_n_for_pie(sector_values)
    country_chart_data = group_top_n_for_pie(country_values)

    # ACTUALIZADO: Construye el diccionario de datos a retornar como JSON
    data_to_return = {
        "summary_metrics": {
            "total_market_value_eur": round(total_market_value_eur, 2),
            "total_cost_basis_eur_open_positions": round(total_cost_basis_eur_open_positions, 2),
            "total_unrealized_pl_eur": round(total_unrealized_pl_eur, 2),
            "overall_return_percentage_open_positions": round(overall_return_percentage_open_positions, 2),
            "current_capital_propio": round(current_capital_propio_abs, 2), # Asegura redondeo
            "current_dividend_pnl": round(current_dividend_pnl, 2),  # ← AÑADIDO
            "current_apalancamiento": round(current_apalancamiento, 2), # Asegura redondeo
            "beneficio_perdida_global": round(beneficio_perdida_global, 2),
            "rentabilidad_acumulada_percentage": rentabilidad_acumulada_percentage, # Ya viene redondeado o "N/A"
            "rentabilidad_media_anual_percentage": rentabilidad_media_anual_percentage # Ya viene redondeado o "N/A"
        },
        "sector_distribution": sector_chart_data,
        "country_distribution": country_chart_data
    }
    return jsonify(data_to_return)

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
    
    # Campos para categorización y procesamiento
    category = db.Column(db.String(50), nullable=True, default='Sin Categoría')
    process_status = db.Column(db.String(20), nullable=True, default='SKIP')
    
    # Nuevos campos para movimientos adicionales
    is_additional_movement = db.Column(db.Boolean, default=False, nullable=False)
    original_movement_id = db.Column(db.Integer, db.ForeignKey('crypto_csv_movements.id'), nullable=True)
    
    # Campos de control
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    csv_filename = db.Column(db.String(255), nullable=True)
    transaction_hash_unique = db.Column(db.String(64), nullable=True, index=True)
    
    # Relaciones
    user = db.relationship('User', backref=db.backref('crypto_csv_movements', lazy=True, cascade='all, delete-orphan'))
    original_movement = db.relationship('CryptoCsvMovement', remote_side=[id], backref='additional_movements')
    
    def generate_hash(self):
        """Genera un hash único basado en los datos principales de la transacción."""
        # Incluir is_additional_movement en el hash para evitar conflictos
        hash_data = f"{self.user_id}_{self.exchange_name}_{self.timestamp_utc}_{self.transaction_description}_{self.currency}_{self.amount}_{self.to_currency}_{self.to_amount}_{self.transaction_kind}_{self.transaction_hash}_{self.is_additional_movement}"
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

class AlertConfiguration(db.Model):
    """Configuración de alertas definida por el usuario."""
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Tipo de alerta
    alert_reason = db.Column(db.String(50), nullable=False)  # 'earnings_report', 'metric_threshold', 'periodic_summary', 'custom'
    
    # Configuración de alcance (para earnings_report y metric_threshold)
    scope = db.Column(db.String(20), nullable=True)  # 'all', 'portfolio', 'watchlist', 'individual'
    watchlist_item_id = db.Column(db.Integer, db.ForeignKey('watchlist_item.id', ondelete='CASCADE'), nullable=True, index=True)
    
    # Configuración para alertas de resultados
    days_notice = db.Column(db.Integer, nullable=True)  # 1, 7, 15
    frequency = db.Column(db.String(20), nullable=True)  # 'once', 'recurring'
    last_triggered_for_date = db.Column(db.Date, nullable=True)
    
    # Configuración para alertas de métricas
    metric_name = db.Column(db.String(50), nullable=True)  # 'ntm_pe', 'roe', etc.
    metric_operator = db.Column(db.String(10), nullable=True)  # '>', '>=', '<', '<=', '='
    metric_target_value = db.Column(db.Float, nullable=True)
    metric_target_text = db.Column(db.String(10), nullable=True)  # Para valores como 'Buy', 'Hold', 'Sell'

    # Configuración para resúmenes
    summary_type = db.Column(db.String(50), nullable=True)  # 'patrimonio', 'crypto', 'inmuebles', etc.
    summary_frequency = db.Column(db.String(20), nullable=True)  # 'weekly', 'monthly', 'annual'
    summary_one_time_date = db.Column(db.Date, nullable=True)
    last_summary_sent = db.Column(db.Date, nullable=True)
    
    # Configuración para alertas custom
    custom_title = db.Column(db.String(200), nullable=True)
    custom_description = db.Column(db.Text, nullable=True)
    custom_frequency_type = db.Column(db.String(20), nullable=True)  # 'one_time', 'recurring'
    custom_start_date = db.Column(db.Date, nullable=True)
    custom_interval_days = db.Column(db.Integer, nullable=True)
    last_custom_triggered = db.Column(db.Date, nullable=True)
    
    # Configuración de notificaciones
    notify_in_app_mailbox = db.Column(db.Boolean, nullable=False, default=True)
    notify_by_email = db.Column(db.Boolean, nullable=False, default=False)
    
    # Estado
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con WatchlistItem
    watchlist_item = db.relationship('WatchlistItem', backref='alert_configs')
    
    # Campos para objetivos
    goal_type = db.Column(db.String(50), nullable=True)  # 'portfolio_percentage', 'target_amount', 'savings_monthly', 'debt_threshold'
    goal_asset_type = db.Column(db.String(50), nullable=True)  # 'bolsa', 'cash', 'crypto', 'real_estate', 'metales', 'total_patrimonio'
    goal_target_percentage = db.Column(db.Float, nullable=True)  # Para objetivos de porcentaje
    goal_target_amount = db.Column(db.Float, nullable=True)  # Para objetivos de cantidad
    goal_target_timeframe_months = db.Column(db.Integer, nullable=True)  # Plazo en meses
    goal_savings_monthly_amount = db.Column(db.Float, nullable=True)  # Para objetivos de ahorro mensual
    goal_debt_ceiling_percentage = db.Column(db.Float, nullable=True)  # Para objetivos de techo de deuda personalizado
    goal_start_date = db.Column(db.Date, nullable=True)  # Fecha de inicio del objetivo
    goal_alert_day_of_month = db.Column(db.Integer, nullable=True)  # Día del mes para alertas (1-31)
    goal_name = db.Column(db.String(200), nullable=True)  # Nombre descriptivo del objetivo
   
        # NUEVOS CAMPOS para mejorar control de duplicados
    last_triggered_date = db.Column(db.Date, nullable=True)  # Última fecha de envío (cualquier tipo)
    times_triggered_total = db.Column(db.Integer, default=0)  # Contador total de envíos
    daily_send_count = db.Column(db.Integer, default=0)  # Cuántas veces se envió HOY
    last_daily_reset = db.Column(db.Date, nullable=True)  # Para resetear contador diario
    
    def should_send_today(self, today):
        """Determina si esta alerta debe enviarse hoy basándose en el tipo y frecuencia."""
        
        # Resetear contador diario si es un nuevo día
        if self.last_daily_reset != today:
            self.daily_send_count = 0
            self.last_daily_reset = today
        
        # Si ya se envió hoy, verificar según el tipo de alerta
        if self.last_triggered_date == today:
            
            # Para alertas de métricas: enviar solo UNA vez cuando se alcance
            if self.alert_reason == 'metric_threshold':
                return False
                
            # Para alertas de resultados: enviar solo UNA vez por fecha de resultado
            if self.alert_reason == 'earnings_report':
                return False
                
            # Para alertas custom puntuales: enviar solo UNA vez
            if self.alert_reason == 'custom' and self.custom_frequency_type == 'puntual':
                return False
                
            # Para resúmenes puntuales: enviar solo UNA vez
            if self.alert_reason == 'periodic_summary' and self.summary_frequency == 'puntual':
                return False
        
        return True
    
    def mark_as_sent(self, today):
        """Marca la alerta como enviada hoy."""
        self.last_triggered_date = today
        self.times_triggered_total = (self.times_triggered_total or 0) + 1
        self.daily_send_count = (self.daily_send_count or 0) + 1
        
        # Para alertas puntuales o de métrica, desactivar automáticamente
        if (self.alert_reason == 'metric_threshold' or 
            (self.alert_reason == 'custom' and self.custom_frequency_type == 'puntual') or
            (self.alert_reason == 'periodic_summary' and self.summary_frequency == 'puntual')):
            self.is_active = False

    def __repr__(self):
        return f'<AlertConfiguration {self.id} User:{self.user_id} Reason:{self.alert_reason} Active:{self.is_active}>'


class MailboxMessage(db.Model):
    """Mensajes del buzón virtual del usuario."""
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Tipo y contenido del mensaje
    message_type = db.Column(db.String(30), nullable=False)  # 'event_alert', 'config_warning', 'config_resolved', 'periodic_summary', 'custom_alert'
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=True)
    
    # Referencias opcionales
    related_watchlist_item_id = db.Column(db.Integer, db.ForeignKey('watchlist_item.id', ondelete='CASCADE'), nullable=True, index=True)
    related_alert_config_id = db.Column(db.Integer, db.ForeignKey('alert_configuration.id', ondelete='CASCADE'), nullable=True, index=True)
    
    # Metadatos del evento
    trigger_event_date = db.Column(db.Date, nullable=True)  # Fecha de resultados para la que se generó el mensaje
    
    # Estado
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Relaciones
    watchlist_item = db.relationship('WatchlistItem', backref='mailbox_messages')
    alert_config = db.relationship('AlertConfiguration', backref='mailbox_messages')
    
    def __repr__(self):
        return f'<MailboxMessage {self.id} User:{self.user_id} Type:{self.message_type} Read:{self.is_read}>'

class AlertConfigurationForm(FlaskForm):
    """Formulario para configurar alertas."""
    
    # Campo principal: tipo de alerta
    alert_reason = SelectField('Motivo de la Alerta', 
                              choices=[
                                  ('earnings_report', 'Presentación de Resultados'),
                                  ('metric_threshold', 'Métricas de Acción'),
                                  ('periodic_summary', 'Resumen Periódico'),
                                  ('objetivo', 'Objetivo'),
                                  ('custom', 'Alerta Personalizada')
                              ],
                              validators=[DataRequired()])
    
    # NUEVO: Campo para seleccionar objetivo existente
    existing_goal_id = SelectField('Seleccionar Objetivo Existente',
                                  choices=[],  # Se llenará dinámicamente
                                  coerce=int,
                                  validators=[Optional()])
    
    # Mantener campos existentes...
    scope = SelectField('Aplicar a',
                       choices=[
                           ('all', 'Todas las acciones'),
                           ('portfolio', 'Solo acciones en Portfolio'),
                           ('watchlist', 'Solo acciones en Seguimiento'),
                           ('individual', 'Acción Individual')
                       ],
                       validators=[Optional()])
    
    watchlist_item_id = SelectField('Acción', coerce=int, validators=[Optional()])
    
    # Para alertas de resultados
    days_notice = SelectField('Antelación',
                             choices=[
                                 (1, '1 día antes'),
                                 (7, '7 días antes'),
                                 (15, '15 días antes')
                             ],
                             coerce=int,
                             validators=[Optional()])
    
    frequency = SelectField('Frecuencia',
                           choices=[
                               ('once', 'Solo para la próxima presentación'),
                               ('recurring', 'Para todas las futuras presentaciones')
                           ],
                           validators=[Optional()])
    
    # Para alertas de métricas
    metric_watchlist_item_id = SelectField('Acción', coerce=int, validators=[Optional()])
    metric_name = SelectField('Métrica a vigilar',
                             choices=[
                                 ('profitability_calc', 'Profitability (%)'),
                                 ('riesgo', 'Upside (%)'),
                                 ('stake', 'Stake'),
                                 ('movimiento', 'Movimiento'),
                                 ('ntm_ps', 'P/S'),
                                 ('ntm_pe', 'P/E'),
                                 ('ntm_div_yield', 'DivYld (%)'),
                                 ('ltm_pbv', 'P/BV'),
                                 ('eps_yield_calc', 'EPS Yld 5Y(%)')
                             ],
                             validators=[Optional()])
    
    metric_operator = SelectField('Condición',
                                 choices=[
                                     ('>', 'Mayor que (>)'),
                                     ('>=', 'Mayor o igual (>=)'),
                                     ('<', 'Menor que (<)'),
                                     ('<=', 'Menor o igual (<=)'),
                                     ('=', 'Igual a (=)'),
                                     ('!=', 'Diferente de (!=)')
                                 ],
                                 validators=[Optional()])
    
    metric_target_value = StringField('Valor objetivo', validators=[Optional()])
    metric_target_text = SelectField('Valor objetivo',
                                    choices=[
                                        ('Buy', 'Buy'),
                                        ('Hold', 'Hold'),
                                        ('Sell', 'Sell')
                                    ],
                                    validators=[Optional()])
    
    current_metric_value = StringField('Valor actual (solo información)', 
                                      render_kw={'readonly': True})
    
    # Para resúmenes
    summary_type = SelectField('Tipo de resumen',
                              choices=[
                                  ('patrimonio', 'Patrimonio Neto Completo'),
                                  ('crypto', 'Criptomonedas'),
                                  ('inmuebles', 'Inmuebles'),
                                  ('metales', 'Metales Preciosos'),
                                  ('inversiones', 'Inversiones (Portfolio)'),
                                  ('pensiones', 'Planes de Pensiones')
                              ],
                              validators=[Optional()])
    
    summary_frequency = SelectField('Frecuencia',
                                   choices=[
                                       ('puntual', 'Puntual (una sola vez)'),
                                       ('weekly', 'Semanal'),
                                       ('monthly', 'Mensual'),
                                       ('quarterly', 'Trimestral'),
                                       ('semiannual', 'Semestral'),
                                       ('annual', 'Anual')
                                   ],
                                   validators=[Optional()])
    
    summary_date = StringField('Fecha de inicio/ejecución',
                              render_kw={"type": "date"},
                              validators=[Optional()])
    
    # Para alertas personalizadas
    custom_title = StringField('Título de la alerta', validators=[Optional(), Length(max=200)])
    custom_description = TextAreaField('Descripción (opcional)', validators=[Optional()])
    custom_frequency = SelectField('Frecuencia',
                                  choices=[
                                      ('puntual', 'Puntual (una sola vez)'),
                                      ('weekly', 'Semanal'),
                                      ('monthly', 'Mensual'),
                                      ('quarterly', 'Trimestral'),
                                      ('semiannual', 'Semestral'),
                                      ('annual', 'Anual')
                                  ],
                                  validators=[Optional()])
    
    custom_date = StringField('Fecha de inicio/ejecución',
                             render_kw={"type": "date"},
                             validators=[Optional()])
    
    # Campo común para permitir editar fecha de resultados si no existe
    earnings_date_override = StringField('Fecha de resultados (si no está definida)',
                                        render_kw={"type": "date"},
                                        validators=[Optional()])
    
    # Configuración de notificaciones
    notify_by_email = BooleanField('Recibir también por email', default=False)
    
    submit = SubmitField('Crear Alerta')
    
    def validate(self, **kwargs):
        """Validación personalizada según el tipo de alerta."""
        if not super().validate():
            return False
        
        # Validaciones específicas según el tipo de alerta
        if self.alert_reason.data == 'earnings_report':
            if not self.scope.data:
                self.scope.errors.append('Debe seleccionar el alcance para alertas de resultados.')
                return False
            if not self.days_notice.data:
                self.days_notice.errors.append('Debe seleccionar la antelación.')
                return False
            if not self.frequency.data:
                self.frequency.errors.append('Debe seleccionar la frecuencia.')
                return False
            if self.scope.data == 'individual' and not self.watchlist_item_id.data:
                self.watchlist_item_id.errors.append('Debe seleccionar una acción específica.')
                return False
        
        elif self.alert_reason.data == 'metric_threshold':
            if not self.metric_watchlist_item_id.data:
                self.metric_watchlist_item_id.errors.append('Debe seleccionar una acción específica.')
                return False
            if not self.metric_name.data:
                self.metric_name.errors.append('Debe seleccionar una métrica.')
                return False
            if not self.metric_operator.data:
                self.metric_operator.errors.append('Debe seleccionar una condición.')
                return False
            
            if self.metric_name.data == 'movimiento':
                if self.metric_operator.data not in ['=', '!=']:
                    self.metric_operator.errors.append('Para movimiento solo se permite "=" o "!=".')
                    return False
                if not self.metric_target_text.data:
                    self.metric_target_text.errors.append('Debe seleccionar un valor de movimiento.')
                    return False
            else:
                if not self.metric_target_value.data:
                    self.metric_target_value.errors.append('Debe especificar el valor objetivo.')
                    return False
                try:
                    float(self.metric_target_value.data)
                except (ValueError, TypeError):
                    self.metric_target_value.errors.append('El valor objetivo debe ser un número válido.')
                    return False
        
        elif self.alert_reason.data == 'periodic_summary':
            if not self.summary_type.data:
                self.summary_type.errors.append('Debe seleccionar el tipo de resumen.')
                return False
            if not self.summary_frequency.data:
                self.summary_frequency.errors.append('Debe seleccionar la frecuencia.')
                return False
            if not self.summary_date.data:
                self.summary_date.errors.append('Debe especificar la fecha de inicio/ejecución.')
                return False
        
        elif self.alert_reason.data == 'objetivo':
            # NUEVA VALIDACIÓN: Solo verificar que se seleccione un objetivo existente
            if not self.existing_goal_id.data:
                self.existing_goal_id.errors.append('Debe seleccionar un objetivo existente.')
                return False
        
        elif self.alert_reason.data == 'custom':
            if not self.custom_title.data:
                self.custom_title.errors.append('Debe especificar un título para la alerta personalizada.')
                return False
            if not self.custom_frequency.data:
                self.custom_frequency.errors.append('Debe seleccionar la frecuencia.')
                return False
            if not self.custom_date.data:
                self.custom_date.errors.append('Debe especificar la fecha de inicio/ejecución.')
                return False
        
        return True

@app.context_processor
def inject_unread_messages_count():
    """Inyecta el número de mensajes no leídos en todas las plantillas."""
    if current_user.is_authenticated:
        unread_count = MailboxMessage.query.filter_by(
            user_id=current_user.id, 
            is_read=False
        ).count()
        return {'unread_messages_count': unread_count}
    return {'unread_messages_count': 0}



@app.route('/office/configure_alerts', methods=['GET', 'POST'])
@login_required
def office_configure_alerts():
    """Configuración de alertas del usuario."""
    form = AlertConfigurationForm()
    
    # Poblar las opciones de acciones para el formulario
    user_watchlist = WatchlistItem.query.filter_by(user_id=current_user.id).all()
    watchlist_choices = [(0, 'Selecciona una acción')] + [
        (item.id, item.item_name or f"{item.ticker}{item.yahoo_suffix or ''}") 
        for item in user_watchlist
    ]
    
    # Aplicar las opciones a ambos campos de watchlist
    form.watchlist_item_id.choices = watchlist_choices
    form.metric_watchlist_item_id.choices = watchlist_choices
    
    # NUEVO: Poblar objetivos existentes
    user_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True).all()
    goal_choices = [(0, 'Selecciona un objetivo')] + [
        (goal.id, goal.goal_name) for goal in user_goals
    ]
    form.existing_goal_id.choices = goal_choices
    
    if form.validate_on_submit():
        try:
            # Crear nueva configuración de alerta
            alert_config = AlertConfiguration(
                user_id=current_user.id,
                alert_reason=form.alert_reason.data,
                notify_by_email=form.notify_by_email.data
            )
            
            # Configurar campos específicos según el tipo de alerta
            if form.alert_reason.data == 'earnings_report':
                alert_config.scope = form.scope.data
                alert_config.days_notice = form.days_notice.data
                alert_config.frequency = form.frequency.data
                if form.scope.data == 'individual':
                    alert_config.watchlist_item_id = form.watchlist_item_id.data
                    
                # Si se proporcionó una fecha de resultados override, actualizarla
                if form.earnings_date_override.data:
                    if form.scope.data == 'individual' and form.watchlist_item_id.data:
                        item = WatchlistItem.query.get(form.watchlist_item_id.data)
                        if item and item.user_id == current_user.id:
                            item.fecha_resultados = datetime.strptime(form.earnings_date_override.data, '%Y-%m-%d').date()
            
            elif form.alert_reason.data == 'metric_threshold':
                alert_config.scope = 'individual'  # Siempre individual para métricas
                alert_config.watchlist_item_id = form.metric_watchlist_item_id.data
                alert_config.metric_name = form.metric_name.data
                alert_config.metric_operator = form.metric_operator.data
                
                # Determinar el valor objetivo según el tipo de métrica
                if form.metric_name.data == 'movimiento':
                    alert_config.metric_target_value = 0  # Placeholder numérico
                    alert_config.metric_target_text = form.metric_target_text.data
                else:
                    try:
                        alert_config.metric_target_value = float(form.metric_target_value.data)
                    except (ValueError, TypeError):
                        flash('El valor objetivo debe ser un número válido.', 'error')
                        return render_template('office/configure_alerts.html', form=form, 
                                             user_alerts=get_user_alerts())
            
            elif form.alert_reason.data == 'periodic_summary':
                alert_config.summary_type = form.summary_type.data
                alert_config.summary_frequency = form.summary_frequency.data
                alert_config.summary_one_time_date = datetime.strptime(form.summary_date.data, '%Y-%m-%d').date()
            
            elif form.alert_reason.data == 'custom':
                alert_config.custom_title = form.custom_title.data
                alert_config.custom_description = form.custom_description.data
                alert_config.custom_frequency_type = form.custom_frequency.data
                alert_config.custom_start_date = datetime.strptime(form.custom_date.data, '%Y-%m-%d').date()

            elif form.alert_reason.data == 'objetivo':
                # NUEVA LÓGICA: Asociar alerta a objetivo existente
                selected_goal = Goal.query.get(form.existing_goal_id.data)
                if not selected_goal or selected_goal.user_id != current_user.id:
                    flash('Objetivo no válido.', 'error')
                    return render_template('office/configure_alerts.html', form=form, 
                                         user_alerts=get_user_alerts())
                
                # Configurar alerta basada en el objetivo existente
                alert_config.goal_name = selected_goal.goal_name
                alert_config.goal_type = selected_goal.goal_type
                alert_config.goal_start_date = selected_goal.start_date
                alert_config.custom_frequency_type = 'monthly'
                alert_config.custom_start_date = selected_goal.start_date
                
                # Copiar información específica del objetivo
                if selected_goal.goal_type == 'portfolio_percentage':
                    alert_config.custom_description = selected_goal.asset_distribution
                elif selected_goal.goal_type == 'target_amount':
                    alert_config.goal_asset_type = selected_goal.goal_asset_type
                    alert_config.goal_target_amount = selected_goal.target_amount
                    alert_config.goal_target_timeframe_months = selected_goal.target_timeframe_months
                elif selected_goal.goal_type == 'savings_monthly':
                    alert_config.goal_asset_type = 'cash'
                    alert_config.goal_savings_monthly_amount = selected_goal.monthly_savings_target
                elif selected_goal.goal_type == 'debt_threshold':
                    alert_config.goal_debt_ceiling_percentage = selected_goal.debt_ceiling_percentage
                elif selected_goal.goal_type == 'auto_prediction':
                    alert_config.goal_asset_type = selected_goal.goal_asset_type
                    alert_config.goal_target_amount = selected_goal.target_amount
                    alert_config.goal_target_timeframe_months = selected_goal.target_timeframe_months
            
            db.session.add(alert_config)
            db.session.commit()
            
            flash(f'Alerta "{form.alert_reason.data}" configurada correctamente.', 'success')
            return redirect(url_for('office_configure_alerts'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la alerta: {str(e)}', 'error')
    
    # Obtener alertas existentes del usuario
    user_alerts = get_user_alerts()
    
    return render_template('office/configure_alerts.html', form=form, user_alerts=user_alerts)

def get_user_alerts():
    """Obtiene las alertas configuradas del usuario actual."""
    return AlertConfiguration.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(AlertConfiguration.created_at.desc()).all()


@app.route('/office/mailbox')
@login_required
def office_mailbox():
    """Buzón virtual del usuario - control central con modelo Goal."""
    # Obtener mensajes ordenados
    messages = MailboxMessage.query.filter_by(user_id=current_user.id).order_by(
        db.case(
            (MailboxMessage.message_type == 'config_warning', 1),
            (MailboxMessage.is_read == False, 2),
            else_=3
        ),
        MailboxMessage.created_at.desc()
    ).all()
    
    # Obtener datos de resumen DINÁMICOS
    summary_data = get_mailbox_summary_data_enhanced(current_user.id)
    
    # Obtener alertas activas (sin objetivos)
    active_alerts = AlertConfiguration.query.filter(
        AlertConfiguration.user_id == current_user.id,
        AlertConfiguration.is_active == True,
        AlertConfiguration.alert_reason != 'objetivo'  # Excluir objetivos
    ).all()
    
    # Obtener alertas próximas ordenadas por días restantes
    upcoming_alerts = []
    for alert in active_alerts:
        days_remaining = calculate_days_until_next_alert(alert)
        upcoming_alerts.append({
            'config': alert,
            'days_remaining': days_remaining
        })
    
    # Ordenar por días restantes (nulls al final)
    upcoming_alerts.sort(key=lambda x: x['days_remaining'] if x['days_remaining'] is not None else 9999)
    upcoming_alerts = upcoming_alerts[:10]  # Solo top 5
    
    # Obtener objetivos activos con progreso usando modelo Goal
    active_goals = Goal.query.filter_by(user_id=current_user.id, is_active=True)\
        .order_by(Goal.created_at.desc()).limit(5).all()
    
    goals_summary = []
    for goal in active_goals:
        try:
            goal_status = calculate_goal_status_with_model(goal)
            if not goal_status.get('error'):
                goals_summary.append({
                    'config': goal,
                    'status': goal_status
                })
        except Exception as e:
            print(f"Error calculando estado de objetivo {goal.id}: {e}")
    
    # Formulario de exportación
    export_form = ReportExportForm()
    
    return render_template('office/mailbox.html', 
                         messages=messages,
                         summary_data=summary_data,
                         active_alerts_count=len(active_alerts),
                         upcoming_alerts=upcoming_alerts,
                         goals_summary=goals_summary,
                         export_form=export_form)

def migrate_goals_safely():
    """Migra objetivos existentes de forma segura."""
    try:
        # Verificar que las tablas existen
        if not db.engine.dialect.has_table(db.engine, 'goal'):
            print("❌ Tabla Goal no existe. Ejecuta db.create_all() primero.")
            return
        
        # Contar objetivos existentes
        existing_goals_count = Goal.query.count()
        existing_alerts_count = AlertConfiguration.query.filter_by(alert_reason='objetivo').count()
        
        print(f"📊 Estado actual:")
        print(f"   - Objetivos en tabla Goal: {existing_goals_count}")
        print(f"   - Alertas de objetivo: {existing_alerts_count}")
        
        if existing_goals_count >= existing_alerts_count:
            print("✅ Migración ya completada o no necesaria.")
            return
        
        # Migrar solo las que faltan
        goal_alerts = AlertConfiguration.query.filter_by(alert_reason='objetivo').all()
        migrated_count = 0
        
        for alert in goal_alerts:
            # Verificar que no existe ya
            existing = Goal.query.filter_by(
                user_id=alert.user_id,
                goal_name=alert.goal_name or f"Objetivo {alert.id}"
            ).first()
            
            if not existing:
                new_goal = Goal(
                    user_id=alert.user_id,
                    goal_name=alert.goal_name or f"Objetivo {alert.id}",
                    goal_type=alert.goal_type or 'target_amount',
                    goal_asset_type=alert.goal_asset_type,
                    target_amount=alert.goal_target_amount,
                    target_timeframe_months=alert.goal_target_timeframe_months,
                    monthly_savings_target=alert.goal_savings_monthly_amount,
                    debt_ceiling_percentage=alert.goal_debt_ceiling_percentage,
                    start_date=alert.goal_start_date or alert.created_at.date(),
                    created_at=alert.created_at,
                    is_active=alert.is_active
                )
                
                # Migrar distribución de activos
                if alert.custom_description:
                    try:
                        json.loads(alert.custom_description)  # Verificar que es JSON válido
                        new_goal.asset_distribution = alert.custom_description
                    except:
                        pass
                
                db.session.add(new_goal)
                migrated_count += 1
        
        db.session.commit()
        print(f"✅ Migración completada: {migrated_count} objetivos migrados.")
        
        # Verificar resultado
        final_count = Goal.query.count()
        print(f"📊 Total objetivos después de migración: {final_count}")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error en migración: {e}")

def get_mailbox_summary_data_enhanced(user_id):
    """Obtiene datos de resumen DINÁMICOS mejorados para el buzón."""
    try:
        # Obtener patrimonio usando la función existente
        patrimony = get_current_patrimony_breakdown(user_id)
        total_assets = patrimony['total_assets']
        
        # Obtener deudas activas REALES
        debt_plans = DebtInstallmentPlan.query.filter_by(user_id=user_id, is_active=True).all()
        total_debt_remaining = sum(plan.remaining_amount for plan in debt_plans) if debt_plans else 0
        monthly_debt_payment = sum(plan.monthly_payment for plan in debt_plans) if debt_plans else 0
        
        # Calcular tasa de ahorro REAL
        income_data = FixedIncome.query.filter_by(user_id=user_id).first()
        monthly_salary = (income_data.annual_net_salary / 12) if income_data and income_data.annual_net_salary else 0
        
        # Gastos fijos mensuales REALES
        fixed_expenses = Expense.query.filter_by(user_id=user_id, expense_type='fixed', is_recurring=True).all()
        monthly_fixed_expenses = sum(expense.amount for expense in fixed_expenses) if fixed_expenses else 0
        
        # Gastos variables promedio (últimos 3 meses)
        three_months_ago = date.today() - timedelta(days=90)
        variable_expenses = Expense.query.filter_by(user_id=user_id, expense_type='punctual')\
            .filter(Expense.date >= three_months_ago).all()
        monthly_variable_expenses = (sum(expense.amount for expense in variable_expenses) / 3) if variable_expenses else 0
        
        # Calcular tasa de ahorro real
        total_monthly_expenses = monthly_fixed_expenses + monthly_variable_expenses + monthly_debt_payment
        monthly_savings = monthly_salary - total_monthly_expenses
        savings_rate = (monthly_savings / monthly_salary * 100) if monthly_salary > 0 else 0
        
        # NUEVO: Obtener fecha de última ejecución de alertas
        last_execution = SystemLog.query.filter_by(
            log_type='daily_alerts', 
            status='success'
        ).order_by(SystemLog.executed_at.desc()).first()
        
        if last_execution:
            last_update = last_execution.executed_at.strftime('%d/%m/%Y %H:%M')
        else:
            last_update = 'Nunca ejecutado'
        
        return {
            'total_assets': total_assets,
            'total_debts': total_debt_remaining,
            'savings_rate': max(0, savings_rate),
            'monthly_salary': monthly_salary,
            'monthly_savings': monthly_savings,
            'debt_to_income_ratio': (monthly_debt_payment / monthly_salary * 100) if monthly_salary > 0 else 0,
            'last_update': last_update
        }
        
    except Exception as e:
        print(f"Error obteniendo datos de resumen del buzón: {e}")
        return {
            'total_assets': 0,
            'total_debts': 0,
            'savings_rate': 0,
            'monthly_salary': 0,
            'monthly_savings': 0,
            'debt_to_income_ratio': 0,
            'last_update': 'Error al obtener'
        }

@app.route('/office/mark_message_read/<int:message_id>', methods=['POST'])
@login_required
def mark_message_read(message_id):
    """Marca un mensaje como leído."""
    try:
        message = MailboxMessage.query.filter_by(id=message_id, user_id=current_user.id).first()
        if message:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Mensaje no encontrado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})



@app.route('/office/delete_message/<int:message_id>', methods=['POST'])
@login_required
def delete_message(message_id):
    """Elimina un mensaje del buzón."""
    try:
        message = MailboxMessage.query.filter_by(id=message_id, user_id=current_user.id).first()
        if message and message.message_type != 'config_warning':  # No permitir eliminar warnings
            db.session.delete(message)
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Mensaje no encontrado o no se puede eliminar'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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

@app.route('/office/delete_alert/<int:alert_id>', methods=['POST'])
@login_required
def delete_alert(alert_id):
    """Eliminar una configuración de alerta."""
    alert = AlertConfiguration.query.get_or_404(alert_id)

    if alert.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'No autorizado'}), 403

    try:
        db.session.delete(alert)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/office/test_alert', methods=['POST'])
@login_required
def send_test_alert():
    """Enviar una alerta de prueba al buzón del usuario."""
    try:
        test_message = MailboxMessage(
            user_id=current_user.id,
            message_type='custom_alert',
            title='🧪 Alerta de Prueba',
            content=f'Esta es una alerta de prueba generada el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}. Tu sistema de alertas está funcionando correctamente.'
        )

        db.session.add(test_message)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})


@app.route('/office/generate_summary', methods=['POST'])
@login_required
def generate_summary_now():
    """Generar un resumen on-demand."""
    try:
        data = request.get_json()
        summary_type = data.get('summary_type', 'patrimonio')

        # Aquí generarías el contenido del resumen según el tipo
        # Por ahora, un placeholder
        summary_content = f"Resumen de {summary_type} generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}."

        message = MailboxMessage(
            user_id=current_user.id,
            message_type='periodic_summary',
            title=f'📊 Resumen de {summary_type.title()}',
            content=summary_content
        )

        db.session.add(message)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

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
def admin_dashboard(): # MOSTRANDO COMPLETA CON CAMBIOS PARA LOGS Y SCHEDULER
    try:
        users = User.query.order_by(User.username).all()
        user_count = User.query.count()
        active_user_count = User.query.filter_by(is_active=True).count()
        admin_user_count = User.query.filter_by(is_admin=True).count()
        
        # Obtener los últimos N logs de actividad, ordenados por más reciente primero
        recent_activity_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(50).all()
        
        # Para la plantilla, es útil procesar los detalles si son JSON
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
        
        # === NUEVAS VARIABLES PARA EL SCHEDULER ===
        
        # Estadísticas del scheduler
        try:
            scheduler_tasks = SchedulerTask.query.order_by(SchedulerTask.id).all()
            active_scheduler_tasks = len([task for task in scheduler_tasks if task.is_active])
            total_scheduler_tasks = len(scheduler_tasks)
        except Exception as e:
            print(f"Error obteniendo tareas del scheduler: {e}")
            scheduler_tasks = []
            active_scheduler_tasks = 0
            total_scheduler_tasks = 0
        
        # Jobs activos del scheduler
        active_scheduler_jobs = {}
        try:
            for job in scheduler.get_jobs():
                task_key = job.id.replace('task_', '') if job.id.startswith('task_') else job.id
                active_scheduler_jobs[task_key] = {
                    'next_run': job.next_run_time,
                    'job_id': job.id
                }
        except Exception as e:
            print(f"Error obteniendo jobs activos: {e}")
        
        # Logs recientes del scheduler (para la sección del dashboard)
        try:
            recent_scheduler_logs = SystemLog.query.filter(
                SystemLog.log_type.like('scheduler_%')
            ).order_by(SystemLog.executed_at.desc()).limit(5).all()
            
            # Todos los logs del scheduler (para el tab)
            all_scheduler_logs = SystemLog.query.filter(
                SystemLog.log_type.like('scheduler_%')
            ).order_by(SystemLog.executed_at.desc()).limit(100).all()
        except Exception as e:
            print(f"Error obteniendo logs del scheduler: {e}")
            recent_scheduler_logs = []
            all_scheduler_logs = []
            
        try:
                from datetime import timedelta
                
                # Estadísticas generales
                total_emails = EmailQueue.query.count()
                pending_emails = EmailQueue.query.filter_by(status='pending').count()
                sent_emails = EmailQueue.query.filter_by(status='sent').count()
                failed_emails = EmailQueue.query.filter_by(status='failed').count()
                
                # Emails de las últimas 24 horas
                yesterday = datetime.utcnow() - timedelta(hours=24)
                emails_24h = EmailQueue.query.filter(EmailQueue.created_at >= yesterday).count()
                sent_24h = EmailQueue.query.filter(
                    EmailQueue.status == 'sent',
                    EmailQueue.sent_at >= yesterday
                ).count()
                
                # Emails recientes para mostrar en dashboard (últimos 5)
                recent_emails = EmailQueue.query.order_by(
                    EmailQueue.created_at.desc()
                ).limit(5).all()
                
                # Emails pendientes (para mostrar cola)
                pending_queue = EmailQueue.query.filter_by(status='pending').order_by(
                    EmailQueue.priority.asc(),
                    EmailQueue.scheduled_at.asc()
                ).limit(10).all()
                
        except Exception as e:
                print(f"Error obteniendo estadísticas de email queue: {e}")
                total_emails = pending_emails = sent_emails = failed_emails = 0
                emails_24h = sent_24h = 0
                recent_emails = []
                pending_queue = []
            
        admin_placeholder_email = app.config.get('ADMIN_PLACEHOLDER_EMAIL')   
            
        return render_template('admin/dashboard.html',
                            title="Panel de Administración",
                            users=users,
                            user_count=user_count,
                            active_user_count=active_user_count,
                            admin_user_count=admin_user_count,
                            admin_placeholder_email=admin_placeholder_email,
                            activity_logs=processed_logs, # Tu variable existente
                            # Variables del scheduler (existentes)
                            scheduler_tasks=scheduler_tasks,
                            active_scheduler_tasks=active_scheduler_tasks,
                            total_scheduler_tasks=total_scheduler_tasks,
                            active_scheduler_jobs=active_scheduler_jobs,
                            recent_scheduler_logs=recent_scheduler_logs,
                            all_scheduler_logs=all_scheduler_logs,
                            # NUEVAS VARIABLES DE EMAIL QUEUE
                            total_emails=total_emails,
                            pending_emails=pending_emails,
                            sent_emails=sent_emails,
                            failed_emails=failed_emails,
                            emails_24h=emails_24h,
                            sent_24h=sent_24h,
                            recent_emails=recent_emails,
                            pending_queue=pending_queue)       
                             
    except Exception as e:
        flash(f'Error cargando el panel de administración: {str(e)}', 'danger')
        return render_template('admin/dashboard.html',
                                title='Panel de Administración',
                                # ... valores por defecto existentes ...
                                # Valores por defecto para email queue
                                total_emails=0,
                                pending_emails=0,
                                sent_emails=0,
                                failed_emails=0,
                                emails_24h=0,
                                sent_24h=0,
                                recent_emails=[],
                                pending_queue=[])       

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



def process_daily_alerts():
    """Función principal que se ejecuta diariamente para procesar alertas."""
    start_time = datetime.utcnow()
    
    try:
        with app.app_context():
            print(f"[{start_time}] Iniciando procesamiento diario de alertas...")
            
            # Fase 1: Actualizar todos los precios
            print("Fase 1: Actualizando precios desde APIs externas...")
            update_all_prices()
            
            # Fase 2: Generar mensajes de alertas
            print("Fase 2: Generando mensajes de alertas...")
            generate_alert_messages()
            
            # Fase 3: Enviar emails (si están configurados)
            print("Fase 3: Enviando notificaciones por email...")
            send_email_notifications()
            
            # NUEVO: Registrar ejecución exitosa
            log_entry = SystemLog(
                log_type='daily_alerts',
                executed_at=start_time,
                status='success',
                details='Procesamiento diario completado exitosamente'
            )
            db.session.add(log_entry)
            db.session.commit()
            
            print(f"[{datetime.utcnow()}] Procesamiento diario completado exitosamente.")
            
    except Exception as e:
        # NUEVO: Registrar error
        log_entry = SystemLog(
            log_type='daily_alerts',
            executed_at=start_time,
            status='error',
            details=f'Error en procesamiento diario: {str(e)}'
        )
        db.session.add(log_entry)
        db.session.commit()
        
        print(f"[{datetime.utcnow()}] Error en procesamiento diario: {str(e)}")

@app.route('/office/update_all_prices', methods=['POST'])
@login_required
def update_all_prices():
    """Actualiza todos los precios de mercado."""
    try:
        updated_items = 0
        errors = []
        
        # 1. Actualizar precios de watchlist
        try:
            watchlist_items = WatchlistItem.query.filter_by(user_id=current_user.id).all()
            for item in watchlist_items:
                try:
                    ticker_with_suffix = f"{item.ticker}{item.yahoo_suffix or ''}"
                    update_watchlist_item_from_yahoo(item.id, force_update=True)
                    updated_items += 1
                except Exception as e:
                    errors.append(f"Error actualizando {item.ticker}: {str(e)}")
        except Exception as e:
            errors.append(f"Error general en watchlist: {str(e)}")
        
        # 2. Actualizar precios de metales preciosos
        try:
            update_precious_metal_prices()
            updated_items += 2  # Oro y plata
        except Exception as e:
            errors.append(f"Error actualizando metales: {str(e)}")
        
        # 3. Actualizar precios de criptomonedas
        try:
            update_crypto_prices(current_user.id)
            crypto_count = CryptoTransaction.query.filter_by(user_id=current_user.id)\
                .with_entities(CryptoTransaction.ticker_symbol).distinct().count()
            updated_items += crypto_count
        except Exception as e:
            errors.append(f"Error actualizando criptos: {str(e)}")
        
        # Crear mensaje en el buzón
        success_message = f"Actualización completada: {updated_items} elementos actualizados."
        if errors:
            success_message += f" {len(errors)} errores encontrados."
        
        mailbox_msg = MailboxMessage(
            user_id=current_user.id,
            message_type='system_update',
            title='Actualización de Precios Completada',
            content=success_message
        )
        db.session.add(mailbox_msg)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': success_message,
            'updated_items': updated_items,
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error durante la actualización: {str(e)}'
        })

@app.route('/office/export_custom_report', methods=['POST'])
@login_required
def export_custom_report():
    """Exporta informes personalizados desde el buzón."""
    try:
        report_type = request.form.get('report_type', 'complete')
        export_format = request.form.get('format', 'csv')
        
        if export_format not in ['csv', 'xlsx']:
            export_format = 'csv'
        
        # Generar datos según el tipo de informe
        export_data = generate_custom_report_data(current_user.id, report_type)
        
        # Crear archivo
        today_str = datetime.now().strftime('%Y%m%d')
        filename = f"informe_{report_type}_{today_str}.{export_format}"
        
        if export_format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')
            for row in export_data:
                writer.writerow(row)
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
        
        else:  # xlsx
            try:
                import pandas as pd
                from io import BytesIO
                
                df = pd.DataFrame(export_data)
                output = BytesIO()
                
                # Usar el motor xlsxwriter que es más confiable
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Informe', header=False, index=False)
                    
                    workbook = writer.book
                    worksheet = writer.sheets['Informe']
                    
                    # Formato para encabezados
                    header_format = workbook.add_format({
                        'bold': True,
                        'font_size': 12,
                        'bg_color': '#4F81BD',
                        'font_color': 'white'
                    })
                    
                    # Aplicar formato a la primera fila si hay datos
                    if export_data:
                        for col, value in enumerate(export_data[0]):
                            worksheet.write(0, col, value, header_format)
                    
                    worksheet.set_column('A:A', 40)
                    worksheet.set_column('B:B', 20)
                    worksheet.set_column('C:C', 20)
                
                output.seek(0)
                return Response(
                    output.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment;filename={filename}"}
                )
            
            except ImportError:
                flash("Para exportar a Excel necesitas instalar: pip install pandas xlsxwriter", "warning")
                return redirect(url_for('office_mailbox'))
        
    except Exception as e:
        flash(f"Error al exportar informe: {e}", "danger")
        return redirect(url_for('office_mailbox'))

def generate_custom_report_data(user_id, report_type):
    """Genera datos para informes personalizados."""
    try:
        export_data = []
        
        # Información general
        export_data.append([f"INFORME {report_type.upper()}", "", ""])
        export_data.append([f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", "", ""])
        export_data.append(["", "", ""])
        
        if report_type == 'complete':
            # Usar la lógica existente de export_financial_summary
            # (reutilizar la función existente pero adaptada)
            return generate_complete_financial_report(user_id)
            
        elif report_type == 'bolsa':
            return generate_investment_report(user_id)
            
        elif report_type == 'cash':
            return generate_cash_report(user_id)
            
        elif report_type == 'crypto':
            return generate_crypto_report(user_id)
            
        elif report_type == 'real_estate':
            return generate_real_estate_report(user_id)
            
        elif report_type == 'metales':
            return generate_metals_report(user_id)
            
        elif report_type == 'debts':
            return generate_debts_report(user_id)
            
        elif report_type == 'income_expenses':
            return generate_income_expenses_report(user_id)
        
        else:
            export_data.append(["Error: Tipo de informe no reconocido", "", ""])
            return export_data
            
    except Exception as e:
        return [["Error generando informe", str(e), ""]]

# 5. FUNCIONES ESPECÍFICAS PARA CADA TIPO DE INFORME (agregar en app.py)
def generate_investment_report(user_id):
    """Genera informe específico de inversiones."""
    export_data = []
    export_data.append(["INFORME DE INVERSIONES (BOLSA)", "", ""])
    export_data.append([f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", "", ""])
    export_data.append(["", "", ""])
    
    try:
        # Obtener datos del portfolio
        portfolio_record = UserPortfolio.query.filter_by(user_id=user_id).first()
        if portfolio_record and portfolio_record.portfolio_data:
            portfolio_data = json.loads(portfolio_record.portfolio_data)
            
            export_data.append(["RESUMEN GENERAL", "", ""])
            total_market_value = sum(float(item.get('market_value_eur', 0)) for item in portfolio_data 
                                   if 'market_value_eur' in item and item['market_value_eur'] is not None)
            export_data.append(["Valor Total del Portfolio", f"{total_market_value:.2f} €", ""])
            export_data.append(["", "", ""])
            
            export_data.append(["DETALLE POR POSICIÓN", "", ""])
            export_data.append(["Nombre", "Valor de Mercado", "P&L"])
            
            # Ordenar por valor de mercado
            sorted_items = sorted(
                [item for item in portfolio_data if 'market_value_eur' in item and item['market_value_eur'] is not None],
                key=lambda x: float(x['market_value_eur']),
                reverse=True
            )
            
            for item in sorted_items:
                name = item.get('item_name') or item.get('Producto', 'Desconocido')
                market_value = item.get('market_value_eur', 0)
                pl = item.get('profitability_calc', 0) or 0
                export_data.append([name, f"{market_value:.2f} €", f"{pl:.2f}%"])
        else:
            export_data.append(["No hay datos de inversiones disponibles", "", ""])
        
    except Exception as e:
        export_data.append(["Error generando informe de inversiones", str(e), ""])
    
    return export_data

def generate_cash_report(user_id):
    """Genera informe específico de efectivo."""
    export_data = []
    export_data.append(["INFORME DE EFECTIVO", "", ""])
    export_data.append([f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", "", ""])
    export_data.append(["", "", ""])
    
    try:
        bank_accounts = BankAccount.query.filter_by(user_id=user_id).all()
        if bank_accounts:
            total_cash = sum(account.current_balance for account in bank_accounts)
            export_data.append(["RESUMEN", "", ""])
            export_data.append(["Total en Cuentas Bancarias", f"{total_cash:.2f} €", ""])
            export_data.append(["", "", ""])
            
            export_data.append(["DETALLE POR CUENTA", "", ""])
            export_data.append(["Banco", "Saldo", "Tipo"])
            
            for account in bank_accounts:
                export_data.append([
                    account.bank_name,
                    f"{account.current_balance:.2f} €",
                    account.account_type or "No especificado"
                ])
        else:
            export_data.append(["No hay cuentas bancarias registradas", "", ""])
            
    except Exception as e:
        export_data.append(["Error generando informe de efectivo", str(e), ""])
    
    return export_data

def generate_crypto_report(user_id):
    """Genera informe específico de criptomonedas."""
    export_data = []
    export_data.append(["INFORME DE CRIPTOMONEDAS", "", ""])
    export_data.append([f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", "", ""])
    export_data.append(["", "", ""])
    
    try:
        crypto_transactions = CryptoTransaction.query.filter_by(user_id=user_id).all()
        if crypto_transactions:
            # Calcular holdings actuales
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
            
            # Filtrar holdings activos
            active_holdings = {k: v for k, v in crypto_holdings.items() if v['quantity'] > 0}
            
            if active_holdings:
                total_value = sum(crypto['quantity'] * (crypto['current_price'] or 0) 
                                for crypto in active_holdings.values())
                
                export_data.append(["RESUMEN", "", ""])
                export_data.append(["Valor Total Portfolio Crypto", f"{total_value:.2f} €", ""])
                export_data.append(["", "", ""])
                
                export_data.append(["DETALLE POR CRIPTOMONEDA", "", ""])
                export_data.append(["Nombre", "Cantidad", "Valor"])
                
                for ticker, crypto in active_holdings.items():
                    current_value = crypto['quantity'] * (crypto['current_price'] or 0)
                    export_data.append([
                        crypto['name'],
                        f"{crypto['quantity']:.6f} {ticker}",
                        f"{current_value:.2f} €"
                    ])
            else:
                export_data.append(["No hay criptomonedas en cartera", "", ""])
        else:
            export_data.append(["No hay transacciones de criptomonedas registradas", "", ""])
            
    except Exception as e:
        export_data.append(["Error generando informe de criptomonedas", str(e), ""])
    
    return export_data

def get_mailbox_summary_data(user_id):
    """Obtiene datos de resumen DINÁMICOS para mostrar en el buzón."""
    try:
        # Obtener patrimonio usando la función existente
        patrimony = get_current_patrimony_breakdown(user_id)
        total_assets = patrimony['total_assets']
        
        # Obtener deudas activas REALES
        debt_plans = DebtInstallmentPlan.query.filter_by(user_id=user_id, is_active=True).all()
        total_debt_remaining = sum(plan.remaining_amount for plan in debt_plans) if debt_plans else 0
        monthly_debt_payment = sum(plan.monthly_payment for plan in debt_plans) if debt_plans else 0
        
        # Calcular tasa de ahorro REAL
        income_data = FixedIncome.query.filter_by(user_id=user_id).first()
        monthly_salary = (income_data.annual_net_salary / 12) if income_data and income_data.annual_net_salary else 0
        
        # Gastos fijos mensuales REALES
        fixed_expenses = Expense.query.filter_by(user_id=user_id, expense_type='fixed', is_recurring=True).all()
        monthly_fixed_expenses = sum(expense.amount for expense in fixed_expenses) if fixed_expenses else 0
        
        # Gastos variables promedio (últimos 3 meses)
        three_months_ago = date.today() - timedelta(days=90)
        variable_expenses = Expense.query.filter_by(user_id=user_id, expense_type='punctual')\
            .filter(Expense.date >= three_months_ago).all()
        monthly_variable_expenses = (sum(expense.amount for expense in variable_expenses) / 3) if variable_expenses else 0
        
        # Calcular tasa de ahorro real
        total_monthly_expenses = monthly_fixed_expenses + monthly_variable_expenses + monthly_debt_payment
        monthly_savings = monthly_salary - total_monthly_expenses
        savings_rate = (monthly_savings / monthly_salary * 100) if monthly_salary > 0 else 0
        
        return {
            'total_assets': total_assets,
            'total_debts': total_debt_remaining,  # Deuda restante, no pagos anuales
            'savings_rate': max(0, savings_rate),
            'monthly_salary': monthly_salary,
            'monthly_savings': monthly_savings,
            'debt_to_income_ratio': (monthly_debt_payment / monthly_salary * 100) if monthly_salary > 0 else 0
        }
        
    except Exception as e:
        print(f"Error obteniendo datos de resumen del buzón: {e}")
        return {
            'total_assets': 0,
            'total_debts': 0,
            'savings_rate': 0,
            'monthly_salary': 0,
            'monthly_savings': 0,
            'debt_to_income_ratio': 0
        }

def generate_alert_messages():
    """Genera mensajes de alerta según las configuraciones activas."""
    try:
        today = date.today()
        check_and_resolve_warnings()
        alert_configs = AlertConfiguration.query.filter_by(is_active=True).all()
        
        for config in alert_configs:
            try:
                if config.alert_reason == 'earnings_report':
                    process_earnings_alerts(config, today)
                elif config.alert_reason == 'metric_threshold':
                    process_metric_alerts(config, today)
                elif config.alert_reason == 'periodic_summary':
                    process_summary_alerts(config, today)
                elif config.alert_reason == 'custom':
                    process_custom_alerts(config, today)
                    
            except Exception as e:
                print(f"Error procesando alerta {config.id}: {e}")
                
        print("Generación de mensajes completada.")
        
    except Exception as e:
        print(f"Error generando mensajes: {e}")


def send_email_notifications():
    """Envía notificaciones por email para mensajes recién creados."""
    try:
        # CORREGIR: Obtener solo mensajes de HOY que tienen configuración activa
        today_start = datetime.combine(date.today(), datetime.min.time())
        
        # Subconsulta para verificar que la configuración sigue activa
        messages_to_email = db.session.query(MailboxMessage).filter(
            MailboxMessage.created_at >= today_start,
            MailboxMessage.related_alert_config_id.isnot(None)
        ).all()
        
        emails_sent = 0
        for message in messages_to_email:
            # Verificar que la configuración de alerta sigue activa
            if message.related_alert_config_id:
                config = AlertConfiguration.query.get(message.related_alert_config_id)
                if config and config.is_active and config.notify_by_email:
                    try:
                        send_alert_email(message)
                        emails_sent += 1
                    except Exception as e:
                        print(f"Error enviando email para mensaje {message.id}: {e}")
                        
        print(f"Enviados {emails_sent} emails de notificación.")
        
    except Exception as e:
        print(f"Error enviando emails: {e}")

# Programar la tarea para que se ejecute diariamente a las 00:00
# Configurar las tareas programadas (AL FINAL, después de definir todas las funciones)
def setup_scheduled_tasks():
    """Configura las tareas programadas."""
    try:
        # Eliminar trabajos existentes para evitar duplicados
        scheduler.remove_all_jobs()
        
        # Añadir la tarea diaria
        scheduler.add_job(
            func=process_daily_alerts,
            trigger='cron',
            hour=0,
            minute=0,
            id='daily_alerts_job',
            name='Procesamiento diario de alertas',
            replace_existing=True
        )
        
        print(f"DEBUG: Tarea programada añadida. Jobs activos: {len(scheduler.get_jobs())}")
        for job in scheduler.get_jobs():
            print(f"DEBUG: Job: {job.id} - Próxima ejecución: {job.next_run_time}")
            
    except Exception as e:
        print(f"Error configurando tareas programadas: {e}")


def process_daily_alerts():
    """Función principal que se ejecuta diariamente para procesar alertas."""
    try:
        with app.app_context():
            print(f"[{datetime.now()}] Iniciando procesamiento diario de alertas...")
            
            # Fase 1: Actualizar todos los precios
            print("Fase 1: Actualizando precios desde APIs externas...")
            update_all_prices()
            
            # Fase 2: Generar mensajes de alertas
            print("Fase 2: Generando mensajes de alertas...")
            generate_alert_messages()
            
            # Fase 3: Enviar emails (si están configurados)
            print("Fase 3: Enviando notificaciones por email...")
            send_email_notifications()
            
            print(f"[{datetime.now()}] Procesamiento diario completado exitosamente.")
            
    except Exception as e:
        print(f"[{datetime.now()}] Error en procesamiento diario: {str(e)}")



def process_earnings_alerts(config, today):
    """Procesa alertas de resultados con cola de emails."""
    
    if not config.should_send_today(today):
        return
    
    # Obtener acciones aplicables según el scope
    if config.scope == 'individual':
        items = [config.watchlist_item] if config.watchlist_item else []
    elif config.scope == 'portfolio':
        items = WatchlistItem.query.filter_by(user_id=config.user_id, is_in_portfolio=True).all()
    elif config.scope == 'watchlist':
        items = WatchlistItem.query.filter_by(user_id=config.user_id, is_in_followup=True).all()
    else:  # scope == 'all'
        items = WatchlistItem.query.filter_by(user_id=config.user_id).all()
    
    alerts_sent = 0
    
    for item in items:
        if not item.fecha_resultados:
            existing_warning = MailboxMessage.query.filter_by(
                user_id=config.user_id,
                message_type='config_warning',
                related_watchlist_item_id=item.id,
                related_alert_config_id=config.id
            ).first()
            
            if not existing_warning:
                warning_msg = MailboxMessage(
                    user_id=config.user_id,
                    message_type='config_warning',
                    title=f'⚠️ Revisar fecha de resultados: {item.item_name or item.ticker}',
                    content=f'La alerta de resultados para {item.item_name or item.ticker} no puede activarse porque no hay fecha de resultados definida.',
                    related_watchlist_item_id=item.id,
                    related_alert_config_id=config.id
                )
                db.session.add(warning_msg)
            continue
        
        if item.fecha_resultados < today:
            continue
            
        days_until = (item.fecha_resultados - today).days
        
        if days_until == config.days_notice:
            if config.frequency == 'once' and config.last_triggered_for_date == item.fecha_resultados:
                continue
                
            alert_msg = MailboxMessage(
                user_id=config.user_id,
                message_type='event_alert',
                title=f'📅 Resultados próximos: {item.item_name or item.ticker}',
                content=f'Los resultados de {item.item_name or item.ticker} se presentarán el {item.fecha_resultados.strftime("%d/%m/%Y")} (en {days_until} día{"s" if days_until != 1 else ""}).',
                related_watchlist_item_id=item.id,
                related_alert_config_id=config.id,
                trigger_event_date=item.fecha_resultados
            )
            db.session.add(alert_msg)
            db.session.flush()  # Para obtener el ID
            
            # NUEVO: Agregar a cola de emails
            add_email_to_queue(alert_msg, config)
            
            config.last_triggered_for_date = item.fecha_resultados
            alerts_sent += 1
    
    if alerts_sent > 0:
        config.mark_as_sent(today)
    
    db.session.commit()

def process_metric_alerts(config, today):
    """Procesa alertas de métricas con cola de emails."""
    
    if not config.should_send_today(today):
        return
        
    item = config.watchlist_item
    if not item:
        return
    
    current_value = getattr(item, config.metric_name, None)
    if current_value is None:
        return
    
    target_value = config.metric_target_text if config.metric_name == 'movimiento' else config.metric_target_value
    condition_met = False
    
    if config.metric_operator == '>':
        condition_met = float(current_value) > float(target_value)
    elif config.metric_operator == '>=':
        condition_met = float(current_value) >= float(target_value)
    elif config.metric_operator == '<':
        condition_met = float(current_value) < float(target_value)
    elif config.metric_operator == '<=':
        condition_met = float(current_value) <= float(target_value)
    elif config.metric_operator == '=':
        if config.metric_name == 'movimiento':
            condition_met = str(current_value) == str(target_value)
        else:
            condition_met = float(current_value) == float(target_value)
    elif config.metric_operator == '!=':
        if config.metric_name == 'movimiento':
            condition_met = str(current_value) != str(target_value)
        else:
            condition_met = float(current_value) != float(target_value)
    
    if condition_met:
        alert_msg = MailboxMessage(
            user_id=config.user_id,
            message_type='event_alert',
            title=f'🎯 Métrica alcanzada: {item.item_name or item.ticker}',
            content=f'La métrica {config.metric_name} de {item.item_name or item.ticker} ha alcanzado el valor objetivo: {current_value} {config.metric_operator} {target_value}',
            related_watchlist_item_id=item.id,
            related_alert_config_id=config.id
        )
        db.session.add(alert_msg)
        db.session.flush()  # Para obtener el ID
        
        # NUEVO: Agregar a cola de emails
        add_email_to_queue(alert_msg, config)
        
        config.mark_as_sent(today)
        
        db.session.commit()

def process_summary_alerts(config, today):
    """Procesa alertas de resúmenes con cola de emails."""
    
    if not config.should_send_today(today):
        return
        
    should_send = False
    
    if config.summary_frequency == 'puntual':
        should_send = config.summary_one_time_date == today
    elif config.summary_frequency == 'weekly':
        if config.summary_one_time_date and today.weekday() == config.summary_one_time_date.weekday():
            should_send = config.last_summary_sent != today
    elif config.summary_frequency == 'monthly':
        if config.summary_one_time_date and today.day == config.summary_one_time_date.day:
            should_send = config.last_summary_sent != today
    
    if should_send:
        summary_content = generate_summary_content(config.summary_type, config.user_id)
        
        summary_msg = MailboxMessage(
            user_id=config.user_id,
            message_type='periodic_summary',
            title=f'📊 Resumen {config.summary_frequency}: {config.summary_type.title()}',
            content=summary_content,
            related_alert_config_id=config.id
        )
        db.session.add(summary_msg)
        db.session.flush()  # Para obtener el ID
        
        # NUEVO: Agregar a cola de emails
        add_email_to_queue(summary_msg, config)
        
        config.last_summary_sent = today
        config.mark_as_sent(today)
        
        db.session.commit()


def process_custom_alerts(config, today):
    """Procesa alertas personalizadas con cola de emails."""
    
    if not config.should_send_today(today):
        return
        
    should_send = False
    
    if config.custom_frequency_type == 'puntual':
        should_send = config.custom_start_date == today
    elif config.custom_frequency_type in ['weekly', 'monthly', 'quarterly', 'semiannual', 'annual']:
        if config.custom_start_date and config.custom_start_date <= today:
            should_send = config.last_custom_triggered != today
    
    if should_send:
        custom_msg = MailboxMessage(
            user_id=config.user_id,
            message_type='custom_alert',
            title=f'🔔 {config.custom_title}',
            content=config.custom_description or f'Recordatorio programado: {config.custom_title}',
            related_alert_config_id=config.id
        )
        db.session.add(custom_msg)
        db.session.flush()  # Para obtener el ID
        
        # NUEVO: Agregar a cola de emails
        add_email_to_queue(custom_msg, config)
        
        config.last_custom_triggered = today
        config.mark_as_sent(today)
            
        db.session.commit()

def generate_summary_content(summary_type, user_id):
    """Genera el contenido del resumen según el tipo."""
    # Implementación básica - puedes expandir con tus funciones existentes
    return f"Resumen de {summary_type} generado automáticamente el {date.today().strftime('%d/%m/%Y')}."


def send_alert_email(message):
    """Envía un email de notificación para un mensaje de alerta."""
    user = db.session.get(User, message.user_id)
    if not user or not user.email:
        return
    
    try:
        msg = Message(
            f'FollowUp - {message.title}',
            recipients=[user.email]
        )
        msg.body = f"""Hola {user.username},

{message.content}

Fecha: {message.created_at.strftime('%d/%m/%Y %H:%M')}

Puedes ver más detalles en tu buzón virtual: {url_for('office_mailbox', _external=True)}

Saludos,
FollowUp App"""
        
        mail.send(msg)
        print(f"Email enviado a {user.email} para mensaje {message.id}")
        
    except Exception as e:
        print(f"Error enviando email: {e}")


@app.route('/office/check_warnings', methods=['POST'])
@login_required
def check_warnings_now():
    """Resolver warnings manualmente."""
    try:
        warnings_resolved = 0
        warnings_deleted = 0
        
        warnings = MailboxMessage.query.filter_by(
            user_id=current_user.id,  # Para el usuario actual, no solo admin
            message_type='config_warning'
        ).all()
        
        print(f"DEBUG: Revisando {len(warnings)} warnings para usuario {current_user.username}")
        
        for warning in warnings:
            print(f"DEBUG: Procesando warning {warning.id}")
            
            # Si no tiene configuración relacionada, eliminar el warning huérfano
            if not warning.related_alert_config_id:
                db.session.delete(warning)
                warnings_deleted += 1
                continue
            
            # Verificar si la configuración aún existe
            config = AlertConfiguration.query.get(warning.related_alert_config_id)
            if not config or not config.is_active:
                db.session.delete(warning)
                warnings_deleted += 1
                continue
            
            # Verificar si el item de watchlist existe y tiene fecha válida
            if warning.related_watchlist_item_id:
                item = WatchlistItem.query.get(warning.related_watchlist_item_id)
                if not item:
                    db.session.delete(warning)
                    warnings_deleted += 1
                    continue
                
                print(f"DEBUG: Item {item.ticker} - fecha_resultados: {item.fecha_resultados}")
                
                # CONDICIÓN: Si ahora tiene fecha Y es futura (o hoy)
                if item.fecha_resultados and item.fecha_resultados >= date.today():
                    print(f"DEBUG: Resolviendo warning para {item.ticker}")
                    
                    # Crear mensaje de resolución (que aparece como leído)
                    resolved_msg = MailboxMessage(
                        user_id=current_user.id,
                        message_type='config_resolved',
                        title=f'✅ Problema resuelto: {item.item_name or item.ticker}',
                        content=f'La fecha de resultados para {item.item_name or item.ticker} ahora está definida ({item.fecha_resultados.strftime("%d/%m/%Y")}). La alerta de resultados está activa.',
                        related_watchlist_item_id=item.id,
                        related_alert_config_id=config.id,
                        is_read=True  # MARCARLO COMO LEÍDO PARA QUE SE ARCHIVE
                    )
                    db.session.add(resolved_msg)
                    
                    # Eliminar el warning
                    db.session.delete(warning)
                    warnings_resolved += 1
        
        db.session.commit()
        
        message = f'Resueltos: {warnings_resolved}, Eliminados: {warnings_deleted} warnings.'
        print(f"DEBUG: {message}")
        
        return jsonify({
            'success': True, 
            'warnings_resolved': warnings_resolved,
            'warnings_deleted': warnings_deleted,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error resolviendo warnings: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

def check_for_past_dates_alerts():
    """Crea warnings para fechas de resultados que están en el pasado."""
    try:
        today = date.today()
        
        # Buscar configuraciones activas de resultados
        earnings_configs = AlertConfiguration.query.filter_by(
            is_active=True,
            alert_reason='earnings_report'
        ).all()
        
        for config in earnings_configs:
            # Obtener acciones aplicables según el scope
            if config.scope == 'individual':
                items = [config.watchlist_item] if config.watchlist_item else []
            elif config.scope == 'portfolio':
                items = WatchlistItem.query.filter_by(user_id=config.user_id, is_in_portfolio=True).all()
            elif config.scope == 'watchlist':
                items = WatchlistItem.query.filter_by(user_id=config.user_id, is_in_followup=True).all()
            else:  # scope == 'all'
                items = WatchlistItem.query.filter_by(user_id=config.user_id).all()
            
            for item in items:
                if item.fecha_resultados and item.fecha_resultados < today:
                    # Verificar si ya existe un warning para fecha pasada
                    existing_warning = MailboxMessage.query.filter_by(
                        user_id=config.user_id,
                        message_type='config_warning',
                        related_watchlist_item_id=item.id,
                        related_alert_config_id=config.id
                    ).filter(
                        MailboxMessage.title.contains('fecha pasada')
                    ).first()
                    
                    if not existing_warning:
                        warning_msg = MailboxMessage(
                            user_id=config.user_id,
                            message_type='config_warning',
                            title=f'⚠️ Fecha pasada: {item.item_name or item.ticker}',
                            content=f'La fecha de resultados de {item.item_name or item.ticker} ({item.fecha_resultados.strftime("%d/%m/%Y")}) ya pasó. Por favor, actualízala para que la alerta funcione correctamente.',
                            related_watchlist_item_id=item.id,
                            related_alert_config_id=config.id
                        )
                        db.session.add(warning_msg)
        
        db.session.commit()
        
    except Exception as e:
        print(f"Error verificando fechas pasadas: {e}")

@app.route('/debug_warnings')
@login_required  
def debug_warnings():
    """Debug temporal para entender los warnings."""
    if current_user.username != 'admin':
        return "No autorizado", 403
    
    warnings = MailboxMessage.query.filter_by(
        user_id=current_user.id,
        message_type='config_warning'
    ).all()
    
    debug_info = f"<h2>Debug Warnings (Total: {len(warnings)})</h2>"
    
    for warning in warnings:
        debug_info += f"<div style='border: 1px solid #ccc; margin: 10px; padding: 10px;'>"
        debug_info += f"<h3>Warning ID: {warning.id}</h3>"
        debug_info += f"<p><strong>Título:</strong> {warning.title}</p>"
        debug_info += f"<p><strong>Contenido:</strong> {warning.content}</p>"
        debug_info += f"<p><strong>related_watchlist_item_id:</strong> {warning.related_watchlist_item_id}</p>"
        debug_info += f"<p><strong>related_alert_config_id:</strong> {warning.related_alert_config_id}</p>"
        
        if warning.related_watchlist_item_id:
            item = WatchlistItem.query.get(warning.related_watchlist_item_id)
            if item:
                debug_info += f"<p><strong>Acción:</strong> {item.item_name or item.ticker}</p>"
                debug_info += f"<p><strong>Fecha resultados actual:</strong> {item.fecha_resultados}</p>"
                debug_info += f"<p><strong>Fecha es futura:</strong> {item.fecha_resultados >= date.today() if item.fecha_resultados else 'No tiene fecha'}</p>"
            else:
                debug_info += f"<p style='color: red;'>ERROR: No se encontró WatchlistItem con ID {warning.related_watchlist_item_id}</p>"
        
        if warning.related_alert_config_id:
            config = AlertConfiguration.query.get(warning.related_alert_config_id)
            if config:
                debug_info += f"<p><strong>Configuración activa:</strong> {config.is_active}</p>"
                debug_info += f"<p><strong>Configuración existe:</strong> Sí</p>"
            else:
                debug_info += f"<p style='color: red;'>ERROR: No se encontró AlertConfiguration con ID {warning.related_alert_config_id}</p>"
        
        debug_info += "</div>"
    
    debug_info += '<br><a href="/office/mailbox">Volver al buzón</a>'
    return debug_info

@app.route('/test_alerts_processing')
@login_required
def test_alerts_processing():
    """Ruta temporal para probar el procesamiento de alertas."""
    if current_user.username != 'admin':
        return "No autorizado", 403
    
    process_daily_alerts()
    return "Procesamiento de alertas ejecutado. Revisa tu buzón y la consola."

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


def create_additional_deposit_movement(original_movement):
    """Crea un movimiento adicional de depósito basado en un movimiento de compra"""
    
    additional_movement = CryptoCsvMovement(
        user_id=original_movement.user_id,
        exchange_name=original_movement.exchange_name,
        timestamp_utc=original_movement.timestamp_utc,
        transaction_description=original_movement.transaction_description,
        currency=original_movement.currency,
        amount=abs(original_movement.amount) if original_movement.amount else None,  # Valor absoluto
        to_currency=None,  # Vacío
        to_amount=None,    # Vacío
        native_currency=original_movement.native_currency,
        native_amount=original_movement.native_amount,
        native_amount_in_usd=original_movement.native_amount_in_usd,
        transaction_kind=original_movement.transaction_kind,
        transaction_hash=original_movement.transaction_hash,
        csv_filename=original_movement.csv_filename,
        category='Deposito',
        process_status='OK',
        is_additional_movement=True,
        original_movement_id=original_movement.id
    )
    
    # Generar hash único para evitar duplicados
    additional_movement.transaction_hash_unique = additional_movement.generate_hash()
    
    return additional_movement


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



# -*- coding: utf-8 -*-
# ... (TODOS TUS IMPORTS) ...

@app.route('/financial_summary', methods=['GET', 'POST'])
@login_required
def financial_summary():
    # --- CONFIGURACIÓN INICIAL Y FORMULARIO ---
    config = FinancialSummaryConfig.query.filter_by(user_id=current_user.id).first()
    if not config:
        config = FinancialSummaryConfig(user_id=current_user.id) # Valores por defecto del modelo
        db.session.add(config)
        db.session.commit() # Guardar config por defecto si es la primera vez

    config_form = FinancialSummaryConfigForm(obj=config)

    if config_form.validate_on_submit() and request.method == 'POST':
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
        'income': {'available': False, 'data': {}}, 'variable_income': {'available': False, 'data': {}},
        'expenses': {'available': False, 'data': {'fixed_monthly': 0, 'punctual_last_month': 0, 'monthly_avg_expenses': 0, 'by_category': []}},
        'debts': {'available': False, 'data': {}}, 'investments': {'available': False, 'data': {}},
        'crypto': {'available': False, 'data': {}}, 'metals': {'available': False, 'data': {}},
        'bank_accounts': {'available': False, 'data': {}}, 'pension_plans': {'available': False, 'data': {}},
        'real_estate': {'available': False, 'data': {}}, 'net_worth': {'available': False, 'data': {}},
        'kpis': {'available': False, 'data': {}}, 'cash_flow': {'available': False, 'data': {}},
        'charts': {'available': False, 'data': {}}
    }
    user_id = current_user.id
    today_date_ref = date.today()
    historical_data_points = {}

    try:
        # --- CÁLCULO DE DATOS HISTÓRICOS PARA EL GRÁFICO DE EVOLUCIÓN ---
        print("DEBUG financial_summary: Iniciando cálculo de datos históricos para el gráfico...")
        
        # 1. OBTENER SERIES DIARIAS DE get_current_financial_crosstime_metrics para el broker_cash
        all_metrics_and_series_broker = get_current_financial_crosstime_metrics(user_id)
        daily_broker_equity_series_map = {} # {date_obj: value}

        if all_metrics_and_series_broker and all_metrics_and_series_broker.get('daily_chart_labels'):
            daily_labels_str_broker = all_metrics_and_series_broker['daily_chart_labels']
            daily_cp_acc_broker = all_metrics_and_series_broker['daily_capital_propio_series']
            daily_rsp_acc_broker = all_metrics_and_series_broker['daily_realized_specific_pnl_series']
            daily_div_acc_broker = all_metrics_and_series_broker['daily_dividend_pnl_series']
            
            for i, label_str in enumerate(daily_labels_str_broker):
                try:
                    d_obj = datetime.strptime(label_str, '%Y-%m-%d').date()
                    broker_equity_val = (-daily_cp_acc_broker[i]) + daily_rsp_acc_broker[i] + daily_div_acc_broker[i]
                    daily_broker_equity_series_map[d_obj] = broker_equity_val
                except (IndexError, ValueError) as e_daily_parse:
                    app.logger.warning(f"Error parseando series diarias de broker: {e_daily_parse} en índice {i}")
            print(f"DEBUG financial_summary: Mapa de EWC diario del broker creado con {len(daily_broker_equity_series_map)} puntos.")
        else:
            app.logger.info(f"No hay datos de get_current_financial_crosstime_metrics para el usuario {user_id} para broker_cash histórico.")


        first_dates = []
        # (Lógica completa para poblar first_dates)
        first_cash_val = db.session.query(func.min(CashHistoryRecord.date)).filter_by(user_id=user_id).scalar()
        if first_cash_val: first_dates.append(first_cash_val)
        first_pension_val = db.session.query(func.min(PensionPlanHistory.date)).filter_by(user_id=user_id).scalar()
        if first_pension_val: first_dates.append(first_pension_val)
        first_crypto_tx_val = db.session.query(func.min(CryptoTransaction.date)).filter_by(user_id=user_id).scalar()
        if first_crypto_tx_val: first_dates.append(first_crypto_tx_val)
        first_re_year_val = db.session.query(func.min(RealEstateAsset.purchase_year)).filter_by(user_id=user_id).scalar()
        if first_re_year_val: first_dates.append(date(first_re_year_val, 1, 1))
        if all_metrics_and_series_broker.get('first_event_date'): first_dates.append(all_metrics_and_series_broker['first_event_date'])
        _, csv_data_list_hist, _ = load_user_portfolio(user_id)
        if csv_data_list_hist and isinstance(csv_data_list_hist, list):
            csv_dates_hist_vals = []
            for m_csv_h in csv_data_list_hist:
                if m_csv_h.get('Fecha'):
                    try: csv_dates_hist_vals.append(datetime.strptime(m_csv_h['Fecha'], '%d-%m-%Y').date())
                    except ValueError: app.logger.warning(f"Fecha CSV malformada (historial): {m_csv_h.get('Fecha')}")
            if csv_dates_hist_vals: first_dates.append(min(csv_dates_hist_vals))
        first_metal_tx_val = db.session.query(func.min(PreciousMetalTransaction.date)).filter_by(user_id=user_id).scalar()
        if first_metal_tx_val: first_dates.append(first_metal_tx_val)
        first_debt_hist_val = db.session.query(func.min(DebtHistoryRecord.date)).filter_by(user_id=user_id).scalar()
        if first_debt_hist_val: first_dates.append(first_debt_hist_val)
        first_debt_plan_start_val = db.session.query(func.min(DebtInstallmentPlan.start_date)).filter_by(user_id=user_id).scalar()
        if first_debt_plan_start_val: first_dates.append(first_debt_plan_start_val)
        
        print(f"DEBUG financial_summary: Contenido de first_dates después de recolección: {first_dates}")
        valid_first_dates = [d for d in first_dates if d is not None]

        if not valid_first_dates:
            app.logger.info(f"No hay datos históricos suficientes (first_dates) para usuario {user_id} para gráfico de evolución.")
            summary_data['charts']['available'] = False
        else:
            start_date_hist = min(valid_first_dates).replace(day=1)
            end_date_hist = today_date_ref.replace(day=1)
            print(f"DEBUG financial_summary: Rango histórico para gráfico: {start_date_hist} a {end_date_hist}")

            all_cash_history_map = {r.date.strftime('%Y-%m'): r.total_cash for r in CashHistoryRecord.query.filter_by(user_id=user_id).all()}
            all_pension_history_map = {r.date.strftime('%Y-%m'): r.total_amount for r in PensionPlanHistory.query.filter_by(user_id=user_id).all()}
            all_crypto_transactions_list = CryptoTransaction.query.filter_by(user_id=user_id).order_by(CryptoTransaction.date.asc()).all()
            all_re_value_history_map = {str(r.valuation_year): r.market_value for r in RealEstateValueHistory.query.filter_by(user_id=user_id).all()}
            all_metal_transactions_list = PreciousMetalTransaction.query.filter_by(user_id=user_id).order_by(PreciousMetalTransaction.date.asc()).all()
            all_debt_history_map = {r.date.strftime('%Y-%m'): r.debt_amount for r in DebtHistoryRecord.query.filter_by(user_id=user_id).all()}
            all_debt_plans_list = DebtInstallmentPlan.query.filter_by(user_id=user_id).all()
            print(f"DEBUG financial_summary: Datos históricos pre-cargados (ej. Cash Hist: {len(all_cash_history_map)}).")

            current_month_loop = start_date_hist
            current_crypto_holdings_running = {}
            current_metal_holdings_oz_running = {'gold': 0.0, 'silver': 0.0}
            g_to_oz_const = 0.0321507466
            last_known_cash_in_bank, last_known_pensions, last_known_re_value, last_known_debt = 0,0,0,0
            last_known_broker_cash = 0 # Para el fallback del broker_cash
            ptr_crypto_tx, ptr_metal_tx = 0, 0
            processed_months_count_hist_loop = 0

            while current_month_loop <= end_date_hist:
                processed_months_count_hist_loop +=1
                month_key = current_month_loop.strftime('%Y-%m')
                _, last_day_this_month = monthrange(current_month_loop.year, current_month_loop.month)
                current_month_end_date_loop = date(current_month_loop.year, current_month_loop.month, last_day_this_month)
                is_current_month_point = (current_month_loop.year == today_date_ref.year and current_month_loop.month == today_date_ref.month)
                date_for_historical_lookup = today_date_ref if is_current_month_point else current_month_end_date_loop
                
                components = {
                    'date_obj': current_month_loop, 'cash_in_bank': 0, 'pensions': 0, 'crypto_value': 0,
                    'real_estate_value': 0, 'broker_cash': 0, 'metals_value': 0, 'debts_total': 0
                }

                # Efectivo en Banco
                if month_key in all_cash_history_map: last_known_cash_in_bank = all_cash_history_map[month_key]
                components['cash_in_bank'] = last_known_cash_in_bank
                # Pensiones
                if month_key in all_pension_history_map: last_known_pensions = all_pension_history_map[month_key]
                components['pensions'] = last_known_pensions
                
                # Broker Cash (EWC del broker)
                # Buscar el valor de EWC del broker más cercano a current_month_end_date_loop
                broker_ewc_for_month = None
                closest_broker_date = None
                for dt_broker, val_broker in daily_broker_equity_series_map.items():
                    if dt_broker <= current_month_end_date_loop:
                        if closest_broker_date is None or dt_broker > closest_broker_date:
                            closest_broker_date = dt_broker
                            broker_ewc_for_month = val_broker
                if broker_ewc_for_month is not None:
                    components['broker_cash'] = broker_ewc_for_month
                    last_known_broker_cash = broker_ewc_for_month # Actualizar para fallback
                else: # Si no hay datos diarios para este mes o antes, usar el último conocido
                    components['broker_cash'] = last_known_broker_cash


                # Criptomonedas (valor de mercado)
                while ptr_crypto_tx < len(all_crypto_transactions_list) and all_crypto_transactions_list[ptr_crypto_tx].date <= current_month_end_date_loop:
                    tx_c = all_crypto_transactions_list[ptr_crypto_tx]
                    current_crypto_holdings_running.setdefault(tx_c.ticker_symbol, 0)
                    if tx_c.transaction_type == 'buy': current_crypto_holdings_running[tx_c.ticker_symbol] += tx_c.quantity
                    else: current_crypto_holdings_running[tx_c.ticker_symbol] -= tx_c.quantity
                    ptr_crypto_tx += 1
                crypto_month_value_calc = 0
                for sym_c, qty_c in current_crypto_holdings_running.items():
                    if qty_c > 1e-9:
                        price_eur_c = None
                        if is_current_month_point:
                            price_eur_c = get_crypto_price(sym_c)
                            if price_eur_c is None: price_eur_c = get_historical_crypto_price_eur(sym_c, date_for_historical_lookup)
                        else: price_eur_c = get_historical_crypto_price_eur(sym_c, date_for_historical_lookup)
                        if price_eur_c is not None: crypto_month_value_calc += qty_c * price_eur_c
                components['crypto_value'] = crypto_month_value_calc
                
                # Inmuebles
                current_year_str_re = str(current_month_loop.year)
                if current_year_str_re in all_re_value_history_map: last_known_re_value = all_re_value_history_map[current_year_str_re]
                elif all_re_value_history_map : 
                    closest_year_re = max([yr_re for yr_re in all_re_value_history_map.keys() if int(yr_re) <= current_month_loop.year], default=None)
                    if closest_year_re: last_known_re_value = all_re_value_history_map[closest_year_re]
                components['real_estate_value'] = last_known_re_value
                
                # Metales Preciosos
                while ptr_metal_tx < len(all_metal_transactions_list) and all_metal_transactions_list[ptr_metal_tx].date <= current_month_end_date_loop:
                    tx_m_hist = all_metal_transactions_list[ptr_metal_tx]
                    qty_oz_tx = tx_m_hist.quantity if tx_m_hist.unit_type == 'oz' else tx_m_hist.quantity * g_to_oz_const
                    if tx_m_hist.metal_type == 'gold':
                        if tx_m_hist.transaction_type == 'buy': current_metal_holdings_oz_running['gold'] += qty_oz_tx
                        else: current_metal_holdings_oz_running['gold'] -= qty_oz_tx
                    elif tx_m_hist.metal_type == 'silver':
                        if tx_m_hist.transaction_type == 'buy': current_metal_holdings_oz_running['silver'] += qty_oz_tx
                        else: current_metal_holdings_oz_running['silver'] -= qty_oz_tx
                    ptr_metal_tx += 1
                metals_month_value_calc = 0
                if current_metal_holdings_oz_running['gold'] > 1e-9:
                    price_g_eur = None
                    if is_current_month_point:
                        price_g_eur = get_precious_metal_price('gold')
                        if price_g_eur is None or price_g_eur == 0: price_g_eur = get_historical_metal_price_eur("GC=F", date_for_historical_lookup)
                    else: price_g_eur = get_historical_metal_price_eur("GC=F", date_for_historical_lookup)
                    if price_g_eur is not None and price_g_eur > 0: metals_month_value_calc += current_metal_holdings_oz_running['gold'] * price_g_eur
                if current_metal_holdings_oz_running['silver'] > 1e-9:
                    price_s_eur = None
                    if is_current_month_point:
                        price_s_eur = get_precious_metal_price('silver')
                        if price_s_eur is None or price_s_eur == 0: price_s_eur = get_historical_metal_price_eur("SI=F", date_for_historical_lookup)
                    else: price_s_eur = get_historical_metal_price_eur("SI=F", date_for_historical_lookup)
                    if price_s_eur is not None and price_s_eur > 0: metals_month_value_calc += current_metal_holdings_oz_running['silver'] * price_s_eur
                components['metals_value'] = metals_month_value_calc

                # Deudas Totales
                if month_key in all_debt_history_map: last_known_debt = all_debt_history_map[month_key]
                elif all_debt_plans_list:
                    current_month_total_debt_from_plans_hist = 0
                    for plan_hist in all_debt_plans_list:
                        plan_start_month_first_day_hist = plan_hist.start_date.replace(day=1)
                        plan_end_property_hist = plan_hist.end_date 
                        if plan_start_month_first_day_hist <= current_month_loop:
                            if plan_end_property_hist is None or current_month_loop < plan_end_property_hist:
                                months_elapsed_hist = (current_month_loop.year - plan_start_month_first_day_hist.year) * 12 + (current_month_loop.month - plan_start_month_first_day_hist.month)
                                payments_made_hist = min(months_elapsed_hist + 1, plan_hist.duration_months)
                                remaining_balance_hist = plan_hist.total_amount - (payments_made_hist * plan_hist.monthly_payment)
                                current_month_total_debt_from_plans_hist += max(0, remaining_balance_hist)
                    last_known_debt = current_month_total_debt_from_plans_hist
                components['debts_total'] = last_known_debt
                
                historical_data_points[month_key] = components
                if processed_months_count_hist_loop <= 2 or is_current_month_point :
                    print(f"DEBUG financial_summary (hist_loop): Componentes para {month_key}: {components}")

                if current_month_loop.month == 12: current_month_loop = date(current_month_loop.year + 1, 1, 1)
                else: current_month_loop = date(current_month_loop.year, current_month_loop.month + 1, 1)
            
            # 4. Preparar series para el gráfico
            chart_list_intermediate_data = []
            if historical_data_points:
                sorted_month_keys_data = sorted(historical_data_points.keys())
                for mk_data in sorted_month_keys_data:
                    data_item = historical_data_points[mk_data]
                    total_assets_month_val = (data_item.get('cash_in_bank',0) + data_item.get('pensions',0) + data_item.get('crypto_value',0) +
                                          data_item.get('real_estate_value',0) + data_item.get('broker_cash',0) + data_item.get('metals_value',0))
                    total_liabilities_month_val = data_item.get('debts_total',0)
                    chart_list_intermediate_data.append({
                        'date_str': mk_data, 'date_obj': data_item['date_obj'],
                        'cash_in_bank': data_item.get('cash_in_bank',0), 'pensions': data_item.get('pensions',0),
                        'crypto': data_item.get('crypto_value',0), 'real_estate': data_item.get('real_estate_value',0),
                        'broker_cash': data_item.get('broker_cash',0), 'metals': data_item.get('metals_value',0),
                        'debts': data_item.get('debts_total',0),
                        'total_net_worth': total_assets_month_val - total_liabilities_month_val
                    })
            
            chart_list_final_data = chart_list_intermediate_data[-60:] if len(chart_list_intermediate_data) > 60 else chart_list_intermediate_data
            print(f"DEBUG financial_summary: chart_list_final_data (longitud): {len(chart_list_final_data)}")
            if chart_list_final_data:
                print(f"DEBUG financial_summary: chart_list_final_data (primer elemento si existe): {chart_list_final_data[0] if chart_list_final_data else 'N/A'}")
                print(f"DEBUG financial_summary: chart_list_final_data (último elemento si existe): {chart_list_final_data[-1] if chart_list_final_data else 'N/A'}")
                summary_data['charts']['available'] = True
                summary_data['charts']['data']['net_worth_evolution'] = {
                    'dates': [item['date_str'] for item in chart_list_final_data],
                    'series': {
                        'cash_in_bank': [item['cash_in_bank'] for item in chart_list_final_data],
                        'pensions': [item['pensions'] for item in chart_list_final_data],
                        'crypto': [item['crypto'] for item in chart_list_final_data],
                        'real_estate': [item['real_estate'] for item in chart_list_final_data],
                        'broker_cash': [item['broker_cash'] for item in chart_list_final_data],
                        'metals': [item['metals'] for item in chart_list_final_data],
                        'debts': [item['debts'] for item in chart_list_final_data],
                        'total_net_worth': [item['total_net_worth'] for item in chart_list_final_data]
                    }
                }
                summary_data['charts']['data']['cash_history'] = { # Para el gráfico pequeño de cash
                     'dates': [item['date_str'] for item in chart_list_final_data],
                     'values_list': [item['cash_in_bank'] for item in chart_list_final_data]
                }
                print(f"DEBUG financial_summary: Datos para gráfico net_worth_evolution preparados con {len(summary_data['charts']['data']['net_worth_evolution']['dates'])} puntos.")
            else:
                summary_data['charts']['available'] = False
                app.logger.info("chart_list_final_data está vacía después del bucle, no se generará gráfico de evolución.")
        # --- FIN DEL BLOQUE DE CÁLCULO HISTÓRICO ---

        # --- CÁLCULO DE VALORES ACTUALES PARA TARJETAS Y KPIs ---
        print("DEBUG financial_summary: Iniciando cálculo de valores ACTUALES para tarjetas de resumen...")
        # Ingresos Actuales
        current_total_monthly_income_for_kpi = 0.0
        if config.include_income:
            fixed_income_db_current = FixedIncome.query.filter_by(user_id=user_id).first()
            if fixed_income_db_current and fixed_income_db_current.annual_net_salary is not None:
                summary_data['income']['available'] = True
                monthly_salary_val_current = fixed_income_db_current.annual_net_salary / 12.0
                current_total_monthly_income_for_kpi += monthly_salary_val_current
                summary_data['income']['data'] = {
                    'annual_net_salary': fixed_income_db_current.annual_net_salary,
                    'monthly_salary_12': monthly_salary_val_current,
                    'monthly_salary_14': fixed_income_db_current.annual_net_salary / 14.0 if fixed_income_db_current.annual_net_salary else 0,
                    'last_updated': fixed_income_db_current.last_updated, 'history': []
                }
                salary_history_db_current = SalaryHistory.query.filter_by(user_id=user_id).order_by(SalaryHistory.year.desc()).all()
                prev_salary_current = None
                for entry_current in salary_history_db_current:
                    variation_current = None
                    if prev_salary_current is not None and prev_salary_current > 0:
                        variation_current = ((entry_current.annual_net_salary - prev_salary_current) / prev_salary_current) * 100
                    summary_data['income']['data']['history'].append({
                        'year': entry_current.year, 'salary': entry_current.annual_net_salary, 'variation': variation_current
                    })
                    prev_salary_current = entry_current.annual_net_salary
            
            three_months_ago_inc_current = today_date_ref - timedelta(days=90)
            variable_incomes_total_3m_current = 0.0
            all_var_incomes_expanded_current = []
            for vi_curr in VariableIncome.query.filter_by(user_id=user_id).all():
                if hasattr(vi_curr, 'is_recurring') and vi_curr.is_recurring and vi_curr.income_type == 'fixed':
                    start_calc_vi_curr = max(vi_curr.start_date or vi_curr.date, three_months_ago_inc_current)
                    end_calc_vi_curr = min(vi_curr.end_date or today_date_ref, today_date_ref)
                    current_calc_date_vi_curr = start_calc_vi_curr
                    while current_calc_date_vi_curr <= end_calc_vi_curr:
                        all_var_incomes_expanded_current.append(vi_curr.amount)
                        month_vi_curr, year_vi_curr = current_calc_date_vi_curr.month + (vi_curr.recurrence_months or 1), current_calc_date_vi_curr.year
                        while month_vi_curr > 12: month_vi_curr -=12; year_vi_curr +=1
                        try: current_calc_date_vi_curr = date(year_vi_curr, month_vi_curr, 1)
                        except ValueError: break
                elif vi_curr.date >= three_months_ago_inc_current and vi_curr.date <= today_date_ref:
                     all_var_incomes_expanded_current.append(vi_curr.amount)
            variable_incomes_total_3m_current = sum(all_var_incomes_expanded_current)
            if variable_incomes_total_3m_current > 0:
                avg_monthly_variable_income_current = variable_incomes_total_3m_current / 3.0
                current_total_monthly_income_for_kpi += avg_monthly_variable_income_current
                summary_data['variable_income']['available'] = True
                summary_data['variable_income']['data'] = {'total': variable_incomes_total_3m_current, 'monthly_avg': avg_monthly_variable_income_current}

        # Gastos Actuales (para tarjetas y KPIs)
        current_total_monthly_expenses_for_kpi = 0.0
        if config.include_expenses:
            all_user_expenses_current = Expense.query.filter_by(user_id=user_id).all()
            if all_user_expenses_current: summary_data['expenses']['available'] = True
            fixed_monthly_sum_val_current = sum(e.amount for e in all_user_expenses_current if e.expense_type == 'fixed' and e.is_recurring and (not e.end_date or e.end_date >= today_date_ref))
            summary_data['expenses']['data']['fixed_monthly'] = fixed_monthly_sum_val_current
            current_total_monthly_expenses_for_kpi += fixed_monthly_sum_val_current
            one_month_ago_current = today_date_ref - timedelta(days=30)
            summary_data['expenses']['data']['punctual_last_month'] = sum(e.amount for e in all_user_expenses_current if e.expense_type == 'punctual' and e.date >= one_month_ago_current and e.date <= today_date_ref)
            three_months_ago_exp_current = today_date_ref - timedelta(days=90)
            punctual_expenses_3m_sum_current = sum(e.amount for e in all_user_expenses_current if e.expense_type == 'punctual' and e.date >= three_months_ago_exp_current and e.date <= today_date_ref)
            fixed_expenses_3m_sum_current = 0.0
            for exp_fixed_3m_curr in all_user_expenses_current:
                if exp_fixed_3m_curr.expense_type == 'fixed' and exp_fixed_3m_curr.is_recurring:
                    start_loop_3m_curr = max(exp_fixed_3m_curr.start_date or exp_fixed_3m_curr.date, three_months_ago_exp_current)
                    end_loop_3m_curr = min(exp_fixed_3m_curr.end_date or today_date_ref, today_date_ref)
                    current_loop_3m_curr = start_loop_3m_curr
                    rec_3m_curr = exp_fixed_3m_curr.recurrence_months or 1
                    while current_loop_3m_curr <= end_loop_3m_curr:
                        if current_loop_3m_curr >= three_months_ago_exp_current: fixed_expenses_3m_sum_current += exp_fixed_3m_curr.amount
                        year_next_3m_curr, month_next_3m_curr = current_loop_3m_curr.year, current_loop_3m_curr.month + rec_3m_curr
                        while month_next_3m_curr > 12: month_next_3m_curr -= 12; year_next_3m_curr +=1
                        try: current_loop_3m_curr = date(year_next_3m_curr, month_next_3m_curr, 1)
                        except ValueError: break
            total_direct_expenses_3m_current = fixed_expenses_3m_sum_current + punctual_expenses_3m_sum_current
            summary_data['expenses']['data']['monthly_avg_expenses'] = total_direct_expenses_3m_current / 3.0 if total_direct_expenses_3m_current > 0 else 0.0
            current_total_monthly_expenses_for_kpi += (punctual_expenses_3m_sum_current / 3.0)
            six_months_ago_exp_cat_current = today_date_ref - timedelta(days=180)
            expenses_in_range_for_cat_chart_current = []
            for exp_cat_curr in all_user_expenses_current:
                if exp_cat_curr.expense_type == 'fixed' and exp_cat_curr.is_recurring:
                    start_loop_date_cat_curr = max(exp_cat_curr.start_date or exp_cat_curr.date, six_months_ago_exp_cat_current)
                    end_loop_date_cat_curr = min(exp_cat_curr.end_date or today_date_ref, today_date_ref)
                    current_loop_date_cat_curr = start_loop_date_cat_curr
                    recurrence_loop_cat_curr = exp_cat_curr.recurrence_months or 1
                    while current_loop_date_cat_curr <= end_loop_date_cat_curr:
                        if current_loop_date_cat_curr >= six_months_ago_exp_cat_current: expenses_in_range_for_cat_chart_current.append({'amount': exp_cat_curr.amount, 'category_id': exp_cat_curr.category_id})
                        year_next_cat_curr, month_next_cat_curr = current_loop_date_cat_curr.year, current_loop_date_cat_curr.month + recurrence_loop_cat_curr
                        while month_next_cat_curr > 12: month_next_cat_curr -=12; year_next_cat_curr+=1
                        try: current_loop_date_cat_curr = date(year_next_cat_curr, month_next_cat_curr, 1)
                        except ValueError: break
                elif exp_cat_curr.date >= six_months_ago_exp_cat_current and exp_cat_curr.date <= today_date_ref:
                     expenses_in_range_for_cat_chart_current.append({'amount': exp_cat_curr.amount, 'category_id': exp_cat_curr.category_id})
            expenses_by_cat_dict_current = {}
            for exp_item_cat_curr in expenses_in_range_for_cat_chart_current:
                cat_obj_curr = ExpenseCategory.query.get(exp_item_cat_curr['category_id']) if exp_item_cat_curr['category_id'] else None
                cat_name_curr = cat_obj_curr.name if cat_obj_curr else "Sin categoría"
                expenses_by_cat_dict_current[cat_name_curr] = expenses_by_cat_dict_current.get(cat_name_curr, 0) + exp_item_cat_curr['amount']
            summary_data['expenses']['data']['by_category'] = sorted(expenses_by_cat_dict_current.items(), key=lambda x:x[1], reverse=True)

        # Deudas Actuales para tarjetas y KPIs
        monthly_debt_payment_val_current = 0.0; total_general_debt_val_current = 0.0
        monthly_mortgage_payments_for_kpi = 0.0; total_re_mortgage_balance_val_current = 0.0
        current_month_date_cards = date(today_date_ref.year, today_date_ref.month, 1)
        if config.include_debts:
            debt_plans_db_cards = DebtInstallmentPlan.query.filter_by(user_id=user_id, is_active=True).all()
            summary_data['debts']['available'] = bool(debt_plans_db_cards)
            for plan_card in debt_plans_db_cards:
                is_payable_this_month_card = plan_card.start_date <= current_month_date_cards and \
                                             (plan_card.end_date is None or plan_card.end_date > current_month_date_cards)
                if plan_card.is_mortgage:
                    total_re_mortgage_balance_val_current += plan_card.remaining_amount
                    if is_payable_this_month_card: monthly_mortgage_payments_for_kpi += plan_card.monthly_payment
                else:
                    total_general_debt_val_current += plan_card.remaining_amount
                    if is_payable_this_month_card: monthly_debt_payment_val_current += plan_card.monthly_payment
            summary_data['debts']['data'] = {
                'total_debt': total_general_debt_val_current, 'monthly_payment': monthly_debt_payment_val_current,
                'debt_list': [{'description': p.description, 'remaining': p.remaining_amount, 'progress_pct':p.progress_percentage} 
                              for p in filter(lambda x: not x.is_mortgage, debt_plans_db_cards)][:3]
            }
        current_total_monthly_expenses_for_kpi += (monthly_debt_payment_val_current + monthly_mortgage_payments_for_kpi)

        # Activos Actuales (para tarjetas)
        total_cash_val_current = sum(acc.current_balance for acc in BankAccount.query.filter_by(user_id=user_id).all())
        if config.include_bank_accounts:
            summary_data['bank_accounts']['available'] = total_cash_val_current > 0 or BankAccount.query.filter_by(user_id=user_id).first() is not None
            summary_data['bank_accounts']['data'] = { 'total_cash': total_cash_val_current, 
                                                   'accounts': [{'bank_name':acc.bank_name, 'account_name':acc.account_name, 'balance':acc.current_balance} 
                                                                for acc in BankAccount.query.filter_by(user_id=user_id).all()]}
        
        total_market_value_inv_current = 0.0; total_cost_basis_inv_current = 0.0
        if config.include_investments:
            portfolio_record_db_current = UserPortfolio.query.filter_by(user_id=user_id).first()
            if portfolio_record_db_current and portfolio_record_db_current.portfolio_data:
                portfolio_data_json_current = json.loads(portfolio_record_db_current.portfolio_data)
                if portfolio_data_json_current:
                    summary_data['investments']['available'] = True
                    total_market_value_inv_current = sum(float(item.get('market_value_eur', 0) or 0) for item in portfolio_data_json_current)
                    total_cost_basis_inv_current = sum(float(item.get('cost_basis_eur_est', 0) or 0) for item in portfolio_data_json_current)
                    summary_data['investments']['data'] = {
                        'total_market_value': total_market_value_inv_current,
                        'total_pl': total_market_value_inv_current - total_cost_basis_inv_current,
                        'total_cost_basis': total_cost_basis_inv_current,
                        'top_positions': [{'name': item.get('item_name', item.get('Producto')), 'market_value': float(item.get('market_value_eur',0) or 0)} 
                                          for item in sorted(portfolio_data_json_current, key=lambda x: float(x.get('market_value_eur', 0) or 0), reverse=True)[:3]]
                    }

        current_crypto_value_live = 0.0; cost_of_remaining_crypto = 0.0
        if config.include_crypto:
            holdings_summary_live_card = {} 
            all_crypto_tx_live = CryptoTransaction.query.filter_by(user_id=user_id).all()
            if all_crypto_tx_live: summary_data['crypto']['available'] = True # Hay transacciones, así que la sección está disponible
            
            unique_tickers_live = {tx.ticker_symbol.upper() for tx in all_crypto_tx_live}
            live_prices_map = {ticker: get_crypto_price(ticker) for ticker in unique_tickers_live}

            for ct_live in all_crypto_tx_live:
                ticker_live = ct_live.ticker_symbol.upper()
                if ticker_live not in holdings_summary_live_card:
                    holdings_summary_live_card[ticker_live] = {'quantity': 0.0, 'name': ct_live.crypto_name, 
                                                               'current_price': live_prices_map.get(ticker_live) or 0.0, 
                                                               'investment':0.0 } # 'fees' no se usa directamente aquí para P/L
                
                cost_this_tx = ct_live.quantity * ct_live.price_per_unit + (ct_live.fees or 0)
                if ct_live.transaction_type == 'buy':
                    holdings_summary_live_card[ticker_live]['quantity'] += ct_live.quantity
                    holdings_summary_live_card[ticker_live]['investment'] += cost_this_tx # Sumar coste total de compra
                elif ct_live.transaction_type == 'sell':
                    qty_before_sell = holdings_summary_live_card[ticker_live]['quantity']
                    investment_before_sell = holdings_summary_live_card[ticker_live]['investment']
                    
                    # Coste de la porción vendida (asumiendo coste medio)
                    cost_of_units_sold = 0
                    if qty_before_sell > 1e-9: # Evitar división por cero
                        cost_of_units_sold = (investment_before_sell / qty_before_sell) * ct_live.quantity
                    
                    holdings_summary_live_card[ticker_live]['quantity'] -= ct_live.quantity
                    holdings_summary_live_card[ticker_live]['investment'] -= cost_of_units_sold # Reducir inversión por el coste de lo vendido
                    # Las comisiones de venta se pueden considerar como una reducción del beneficio o un aumento del coste
                    # Para P/L simple, se puede restar del beneficio o sumar al coste total.
                    # Aquí, para el coste de lo que queda, ya se ha ajustado.

            for data_crypto_live in holdings_summary_live_card.values():
                if data_crypto_live['quantity'] > 1e-9: # Considerar solo si hay tenencia
                    current_crypto_value_live += data_crypto_live['quantity'] * data_crypto_live['current_price']
                    cost_of_remaining_crypto += data_crypto_live['investment'] # Sumar coste de las tenencias actuales

            if summary_data['crypto']['available']: # Solo poblar si la sección está disponible
                summary_data['crypto']['data'] = {
                    'total_value': current_crypto_value_live,
                    'total_pl': current_crypto_value_live - cost_of_remaining_crypto,
                    'total_investment': cost_of_remaining_crypto,
                    'top_holdings': sorted([{'name': d['name'], 'ticker': tkr, 'quantity': d['quantity'], 'current_value': d['quantity'] * d['current_price']} 
                                           for tkr, d in holdings_summary_live_card.items() if d['quantity'] > 1e-9], 
                                          key=lambda x: x['current_value'], reverse=True)[:3]
                }
        
        total_metal_value_current = 0.0; total_invested_metal_current = 0.0
        if config.include_metals:
            gold_price_curr_card = get_precious_metal_price('gold') or 0.0
            silver_price_curr_card = get_precious_metal_price('silver') or 0.0
            current_gold_oz_curr_card = 0.0; invested_gold_curr_card = 0.0
            current_silver_oz_curr_card = 0.0; invested_silver_curr_card = 0.0
            all_metal_tx_cards = PreciousMetalTransaction.query.filter_by(user_id=user_id).all()
            if all_metal_tx_cards: summary_data['metals']['available'] = True

            for mt_curr_card in all_metal_tx_cards:
                qty_oz_curr_card = mt_curr_card.quantity if mt_curr_card.unit_type == 'oz' else mt_curr_card.quantity * g_to_oz_const
                # Para P/L de la tarjeta, la inversión es la suma de todos los costes de compra
                # y las ventas no reducen esta "inversión inicial total" sino que generan P/L.
                # Simplificamos: 'investment' es la suma de costes de compra.
                # 'current_value' es el valor de lo que queda. P/L = current_value - total_cost_of_buys_for_what_remains.
                # Para simplificar la tarjeta, mostremos P/L = current_value - sum_of_all_buy_costs + sum_of_all_sell_proceeds
                
                # Lógica de acumulación de cantidad e inversión neta (coste de lo que queda)
                cost_of_this_transaction = qty_oz_curr_card * mt_curr_card.price_per_unit + (mt_curr_card.taxes_fees or 0)

                if mt_curr_card.metal_type == 'gold':
                    if mt_curr_card.transaction_type == 'buy':
                        current_gold_oz_curr_card += qty_oz_curr_card
                        invested_gold_curr_card += cost_of_this_transaction
                    else: # sell
                        avg_cost_before_sell = invested_gold_curr_card / current_gold_oz_curr_card if current_gold_oz_curr_card > 1e-9 else 0
                        cost_of_sold_units = qty_oz_curr_card * avg_cost_before_sell
                        current_gold_oz_curr_card -= qty_oz_curr_card
                        invested_gold_curr_card -= cost_of_sold_units
                elif mt_curr_card.metal_type == 'silver':
                    if mt_curr_card.transaction_type == 'buy':
                        current_silver_oz_curr_card += qty_oz_curr_card
                        invested_silver_curr_card += cost_of_this_transaction
                    else: # sell
                        avg_cost_before_sell_silver = invested_silver_curr_card / current_silver_oz_curr_card if current_silver_oz_curr_card > 1e-9 else 0
                        cost_of_sold_units_silver = qty_oz_curr_card * avg_cost_before_sell_silver
                        current_silver_oz_curr_card -= qty_oz_curr_card
                        invested_silver_curr_card -= cost_of_sold_units_silver
            
            gold_value_curr_card = current_gold_oz_curr_card * gold_price_curr_card
            silver_value_curr_card = current_silver_oz_curr_card * silver_price_curr_card
            total_metal_value_current = gold_value_curr_card + silver_value_curr_card
            # Inversión neta en metales que quedan
            net_investment_in_remaining_metals = invested_gold_curr_card + invested_silver_curr_card

            if summary_data['metals']['available']:
                 summary_data['metals']['data'] = {
                    'total_value': total_metal_value_current, 
                    'total_pl': total_metal_value_current - net_investment_in_remaining_metals,
                    'gold': {'current_value': gold_value_curr_card, 'total_oz': current_gold_oz_curr_card},
                    'silver': {'current_value': silver_value_curr_card, 'total_oz': current_silver_oz_curr_card}
                }
        
        total_pension_val_current = sum(p.current_balance for p in PensionPlan.query.filter_by(user_id=user_id).all())
        if config.include_pension_plans:
            summary_data['pension_plans']['available'] = PensionPlan.query.filter_by(user_id=user_id).first() is not None
            summary_data['pension_plans']['data'] = { 'total_pension': total_pension_val_current, 
                                                   'plans': [{'entity_name': p.entity_name, 'plan_name':p.plan_name or '', 'balance':p.current_balance} 
                                                             for p in PensionPlan.query.filter_by(user_id=user_id).all()]}
        
        total_re_market_value_val_current = sum(asset.current_market_value or 0 for asset in RealEstateAsset.query.filter_by(user_id=user_id).all())
        if config.include_real_estate:
            summary_data['real_estate']['available'] = RealEstateAsset.query.filter_by(user_id=user_id).first() is not None
            summary_data['real_estate']['data'] = {
                'count': RealEstateAsset.query.filter_by(user_id=user_id).count(), 
                'total_market_value': total_re_market_value_val_current,
                'total_mortgage_balance': total_re_mortgage_balance_val_current, # Ya calculado con deudas
                'net_equity': total_re_market_value_val_current - total_re_mortgage_balance_val_current,
                'assets': [{'name': asset.property_name, 'value': asset.current_market_value or 0} 
                           for asset in RealEstateAsset.query.filter_by(user_id=user_id).order_by(db.desc(RealEstateAsset.current_market_value)).limit(3).all()]
            }

        # Efectivo en broker actual (tomado del último punto del historial)
        current_broker_cash_val_for_summary_card = 0.0
        if historical_data_points: # Asegurarse que historical_data_points se llenó
            final_month_key_for_broker_cash = sorted(historical_data_points.keys())[-1] if historical_data_points else None
            if final_month_key_for_broker_cash:
                current_broker_cash_val_for_summary_card = historical_data_points[final_month_key_for_broker_cash].get('broker_cash', 0.0)
        
        assets_final_current = (total_cash_val_current + current_crypto_value_live +
                               total_metal_value_current + total_pension_val_current + total_re_market_value_val_current +
                               current_broker_cash_val_for_summary_card) # Efectivo en broker (EWC)
        liabilities_final_current = total_general_debt_val_current + total_re_mortgage_balance_val_current
        net_worth_val_current = assets_final_current - liabilities_final_current
        
        summary_data['net_worth']['available'] = True
        summary_data['net_worth']['data'] = {
            'total_assets': assets_final_current, 
            'total_liabilities': liabilities_final_current, 
            'net_worth': net_worth_val_current
        }

        if current_total_monthly_income_for_kpi > 0 or current_total_monthly_expenses_for_kpi > 0 :
            summary_data['kpis']['available'] = True
            monthly_savings_val_current = current_total_monthly_income_for_kpi - current_total_monthly_expenses_for_kpi
            savings_rate_val_current = (monthly_savings_val_current / current_total_monthly_income_for_kpi * 100) if current_total_monthly_income_for_kpi > 0 else (-100 if current_total_monthly_expenses_for_kpi > 0 else 0)
            total_debt_payments_for_ratio_current = monthly_debt_payment_val_current + monthly_mortgage_payments_for_kpi
            debt_to_income_val_current = (total_debt_payments_for_ratio_current / current_total_monthly_income_for_kpi * 100) if current_total_monthly_income_for_kpi > 0 else 0
            debt_to_assets_val_current = (liabilities_final_current / assets_final_current * 100) if assets_final_current > 0 else 0
            summary_data['kpis']['data'] = {
                'monthly_income': current_total_monthly_income_for_kpi, 'monthly_expenses': current_total_monthly_expenses_for_kpi,
                'monthly_savings': monthly_savings_val_current, 'savings_rate': savings_rate_val_current,
                'debt_to_income': debt_to_income_val_current, 'debt_to_assets': debt_to_assets_val_current
            }
        if summary_data['kpis'].get('available') and summary_data['kpis']['data'].get('monthly_income') is not None : # Chequeo más robusto
            summary_data['cash_flow']['available'] = True
            summary_data['cash_flow']['data'] = {
                'total_income': summary_data['kpis']['data']['monthly_income'],
                'total_expenses': summary_data['kpis']['data']['monthly_expenses'],
                'net_cash_flow': summary_data['kpis']['data']['monthly_savings']
            }
        print("DEBUG financial_summary: Cálculo de valores ACTUALES para tarjetas completado.")


    except Exception as e:
        app.logger.error(f"Error CRÍTICO calculando datos para resumen financiero: {e}", exc_info=True)
        flash(f"Se produjo un error muy grave al calcular datos del resumen: {str(e)}. Algunos datos podrían no mostrarse.", "danger")
        summary_data['charts']['available'] = False 

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
    """Elimina un movimiento específico y maneja eliminación bidireccional."""
    movement = CryptoCsvMovement.query.filter_by(id=movement_id, user_id=current_user.id).first_or_404()
    
    try:
        deleted_count = 1  # El movimiento principal
        
        # Caso 1: Si es un movimiento original (no adicional)
        if not movement.is_additional_movement:
            # Eliminar todos los movimientos adicionales asociados
            additional_deleted = delete_additional_movements_for_original(movement.id)
            deleted_count += additional_deleted
            
            # Eliminar el movimiento original
            db.session.delete(movement)
            
            if additional_deleted > 0:
                flash(f'Movimiento eliminado junto con {additional_deleted} movimientos adicionales asociados.', 'success')
            else:
                flash('Movimiento eliminado correctamente.', 'success')
        
        # Caso 2: Si es un movimiento adicional
        else:
            # Si tiene un movimiento original asociado, eliminarlo también
            if movement.original_movement_id:
                original_movement = CryptoCsvMovement.query.filter_by(
                    id=movement.original_movement_id,
                    user_id=current_user.id
                ).first()
                
                if original_movement:
                    db.session.delete(original_movement)
                    deleted_count += 1
                    flash('Movimiento adicional eliminado junto con su movimiento original asociado.', 'success')
                else:
                    flash('Movimiento adicional eliminado (movimiento original no encontrado).', 'warning')
            else:
                flash('Movimiento adicional eliminado.', 'success')
            
            # Eliminar el movimiento adicional
            db.session.delete(movement)
        
        db.session.commit()
        
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
    """
    Valida el formato del nombre de archivo para CSVs.
    Acepta tanto formato DeGiro (AAAA.csv) como cualquier nombre para IBKR.
    
    Args:
        filename: Nombre del archivo a validar
    
    Returns:
        bool: True si el formato es válido
    """
    if not filename or not filename.lower().endswith('.csv'):
        return False
    
    # Formato DeGiro: AAAA.csv (cuatro dígitos para el año)
    if re.match(r"^\d{4}\.csv$", filename):
        return True
    
    # Para otros formatos, validar que sea un nombre de archivo válido
    # Permitir cualquier nombre que termine en .csv y no contenga caracteres peligrosos
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
    if any(char in filename for char in dangerous_chars):
        return False
    
    # Validar longitud razonable
    if len(filename) > 255:
        return False
    
    return True

# -*- coding: utf-8 -*-
# ... (todos tus imports y código anterior) ...

def process_uploaded_csvs_unified(files):
    """
    Procesa archivos CSV subidos, detectando automáticamente si son DeGiro o IBKR.
    Mantiene la misma interfaz que process_uploaded_csvs original.
    
    Args:
        files: Lista de archivos subidos
    
    Returns:
        tuple: (processed_df_for_csv, combined_df_raw, errors)
    """
    all_dfs = []
    filenames_processed = []
    errors = []
    mapping_data = load_mapping() # Asumo que load_mapping() está definida

    if not files or all(f.filename == '' for f in files):
        errors.append("Error: No archivos seleccionados.")
        return None, None, errors

    for file in files:
        if file and allowed_file(file.filename): # Asumo que allowed_file() está definida
            filename = secure_filename(file.filename)
            # Asumo que validate_filename_format() ha sido reemplazada o es la misma que validate_filename_format_flexible()
            if not validate_filename_format_flexible(filename): # Usando la versión flexible
                errors.append(f"Advertencia: Archivo '{filename}' ignorado (formato inválido).")
                continue
            
            df_current_file = None # Para almacenar el DataFrame del archivo actual
            try:
                file.seek(0)
                
                csv_format = detect_csv_format_simple(file) # Usando la versión simple
                print(f"Formato detectado para '{filename}': {csv_format}")
                
                if csv_format == 'degiro':
                    df_current_file = process_degiro_file(file, filename) # Asumo que process_degiro_file() está definida
                    if df_current_file is not None:
                        df_current_file['csv_format'] = 'degiro'
                
                elif csv_format == 'ibkr':
                    df_current_file = process_ibkr_file_complete(file, filename) # Esta es tu función compleja para IBKR
                    if df_current_file is not None:
                        df_current_file['csv_format'] = 'ibkr'
                
                else: # Fallback o formato desconocido
                    errors.append(f"Advertencia: Formato de archivo '{filename}' no reconocido o falló el procesamiento primario. Intentando como DeGiro...")
                    file.seek(0) # Rebobinar de nuevo por si acaso
                    df_current_file = process_degiro_file(file, filename)
                    if df_current_file is not None:
                        df_current_file['csv_format'] = 'degiro_fallback' # Marcar si es un fallback
                    else:
                        errors.append(f"Error: No se pudo procesar '{filename}' en ningún formato conocido.")

                if df_current_file is not None and not df_current_file.empty:
                    df_current_file['source_file'] = filename
                    all_dfs.append(df_current_file)
                    filenames_processed.append(filename)
                elif df_current_file is None and csv_format != 'unknown': # Si era un formato conocido pero falló
                     errors.append(f"Error: No se pudieron leer datos válidos de '{filename}' (formato: {csv_format}).")


            except Exception as e:
                errors.append(f"Error crítico procesando archivo '{filename}': {e}")
                traceback.print_exc() # Imprimir traza completa para errores inesperados
                continue
        else:
            if file and file.filename: # Solo añadir error si había un archivo con nombre
                errors.append(f"Archivo '{file.filename}' no permitido o inválido.")

    if not all_dfs:
        if not errors: # Si no hay DataFrames y no hay errores, es un caso raro
            errors.append("Error: No se procesaron archivos válidos (lista de DataFrames vacía sin errores explícitos).")
        return None, None, errors

    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True)
        
        # Parsear fechas y ordenar
        try:
            if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
                # Intentar combinar Fecha y Hora si ambas existen y no son NaT en su mayoría
                # Convertir 'Fecha' a datetime primero, manejando NaT
                combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
                
                # Solo proceder con FechaHora si 'Fecha' no es todo NaT
                if not combined_df_raw['Fecha'].isnull().all():
                    # Crear FechaHora solo donde Fecha no es NaT
                    combined_df_raw['FechaHora'] = pd.to_datetime(
                        combined_df_raw['Fecha'].dt.strftime('%Y-%m-%d') + ' ' + combined_df_raw['Hora'].astype(str),
                        errors='coerce'
                    )
                    combined_df_raw = combined_df_raw.sort_values('FechaHora', ascending=True, na_position='first')
                else: # Si 'Fecha' es todo NaT, intentar ordenar solo por 'Hora' si es útil, o no ordenar
                    combined_df_raw = combined_df_raw.sort_values('Hora', ascending=True, na_position='first')

            elif 'Fecha' in combined_df_raw.columns:
                combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
                combined_df_raw = combined_df_raw.sort_values('Fecha', ascending=True, na_position='first')
        except Exception as e_date:
            errors.append(f"Advertencia: Error parseando/ordenando fechas en combined_df_raw: {e_date}")


        # <<< INICIO BLOQUE DE DEBUG 1 >>>
        print("\nDEBUG: combined_df_raw ANTES de calculate_portfolio")
        stock_isin_to_debug = "SE0009554454" # ¡¡¡REEMPLAZA CON EL ISIN CORRECTO!!!
        if 'ISIN' in combined_df_raw.columns:
            debug_stock_rows = combined_df_raw[combined_df_raw['ISIN'] == stock_isin_to_debug]
            if not debug_stock_rows.empty:
                print(f"Filas para ISIN {stock_isin_to_debug} en combined_df_raw ANTES de calculate_portfolio:")
                cols_to_print_debug1 = ['ISIN', 'Producto', 'Número', 'Precio', 'Valor local', 'Bolsa de', 'Unnamed: 8', 'source_file', 'csv_format', 'Fecha', 'Hora']
                # Asegurar que solo imprimimos columnas que existen
                cols_to_print_debug1_existing = [col for col in cols_to_print_debug1 if col in debug_stock_rows.columns]
                print(debug_stock_rows[cols_to_print_debug1_existing].to_string())
            else:
                print(f"No se encontraron filas para ISIN {stock_isin_to_debug} en combined_df_raw.")
        else:
            print("Columna 'ISIN' no encontrada en combined_df_raw para depuración.")
        # <<< FIN BLOQUE DE DEBUG 1 >>>

        df_for_portfolio_calc = combined_df_raw.copy()
        
        # Ajuste para IBKR (tu lógica existente)
        has_ibkr_data = 'csv_format' in df_for_portfolio_calc.columns and \
                        (df_for_portfolio_calc['csv_format'] == 'ibkr').any()
        if has_ibkr_data:
            print("Detectados datos IBKR, ajustando DataFrame para calculate_portfolio (prepare_dataframe_for_portfolio_calculation)")
            df_for_portfolio_calc = prepare_dataframe_for_portfolio_calculation(df_for_portfolio_calc)
        
        # Preparar DataFrame para CSV final
        # La función prepare_processed_dataframe fue usada antes, asegúrate que es la correcta
        # o si tenías una prepare_final_csv_dataframe. Usaré prepare_processed_dataframe como en tu app.py.
        processed_df_for_csv = prepare_processed_dataframe(combined_df_raw, errors) # Tu función de app.py
        
        print(f"Procesamiento unificado completado: {len(processed_df_for_csv) if processed_df_for_csv is not None else 0} filas en CSV final, {len(df_for_portfolio_calc)} filas para cálculo de portfolio.")
        return processed_df_for_csv, df_for_portfolio_calc, errors
        
    except Exception as e_concat:
        errors.append(f"Error crítico al combinar o procesar DataFrames: {e_concat}")
        traceback.print_exc()
        return None, None, errors

# En process_degiro_file, después de que df se lee
def process_degiro_file(file, filename):
    # ... (try/except para pd.read_csv) ...
    if df is not None and not df.empty:
        # <<< NUEVO DEBUG AQUÍ >>>
        stock_isin_to_debug = "SE0009554454" # SBB ISIN
        # Intentar encontrar la transacción 1050 por ISIN y fecha/hora si el índice no es estable
        # Asumiendo que el índice original del CSV es relevante si 'ID Orden' o algo así
        # Por ahora, filtramos por ISIN y vemos si está la transacción 1050
        if 'ISIN' in df.columns and 'Número' in df.columns and filename == '2022.csv': # Solo para el archivo relevante
            sbb_rows_in_degiro_df = df[df['ISIN'] == stock_isin_to_debug]
            if not sbb_rows_in_degiro_df.empty:
                # Tratar de identificar la transacción 1050 (esto es heurístico si el índice no es el original)
                # Si el índice de df es el original del CSV, puedes usar df.loc[1050] si existe
                # Si no, buscamos por fecha y producto (o una combinación única)
                tx_1050_candidate = sbb_rows_in_degiro_df[
                    (pd.to_datetime(sbb_rows_in_degiro_df['Fecha'], dayfirst=True).dt.strftime('%d-%m-%Y') == '22-04-2022') &
                    (sbb_rows_in_degiro_df['Hora'] == '12:24') &
                    (sbb_rows_in_degiro_df['Precio'] == 33.54) # Usar más campos para identificarla
                ]
                if not tx_1050_candidate.empty:
                    print(f"DEBUG process_degiro_file ({filename}): SBB tx 1050 'Número' AS READ FROM CSV: {tx_1050_candidate['Número'].values}")
                else:
                    print(f"DEBUG process_degiro_file ({filename}): SBB tx 1050 NOT EXACTLY FOUND by criteria for printing 'Número'.")
            else:
                 print(f"DEBUG process_degiro_file ({filename}): SBB ISIN not found in this file for 'Número' debug.")

        missing_original_cols = [col for col in COLS_MAP.keys() if col not in df.columns]
        # ...
    return df

def prepare_final_csv_dataframe(combined_df_raw):
    """
    Prepara el DataFrame final aplicando renombrados y transformaciones.
    
    Args:
        combined_df_raw: DataFrame combinado sin procesar
    
    Returns:
        DataFrame procesado para CSV final
    """
    try:
        # Aplicar renombrado de columnas DeGiro si es necesario
        cols_to_rename_present = [col for col in COLS_MAP.keys() if col in combined_df_raw.columns]
        if cols_to_rename_present:
            filtered_df = combined_df_raw[cols_to_rename_present].copy()
            renamed = filtered_df.rename(columns=COLS_MAP)
        else:
            renamed = combined_df_raw.copy()
        
        # Añadir Exchange Yahoo si no existe pero tenemos datos de Bolsa
        if 'Exchange Yahoo' not in renamed.columns and 'Bolsa' in renamed.columns:
            renamed['Exchange Yahoo'] = renamed['Bolsa'].map(BOLSA_TO_YAHOO_MAP).fillna('')
        
        # Convertir columnas numéricas
        for col in NUMERIC_COLS:
            if col in renamed.columns:
                if not pd.api.types.is_numeric_dtype(renamed[col]):
                    # Limpieza de strings antes de convertir a numérico
                    cleaned_series = renamed[col].astype(str).str.replace(r'[$\s€]', '', regex=True).str.replace(',', '', regex=False)
                    renamed[col] = pd.to_numeric(cleaned_series, errors='coerce')
                
                if pd.api.types.is_numeric_dtype(renamed[col]) or renamed[col].isnull().any():
                    renamed[col] = renamed[col].fillna(0)
                
                if col == 'Cantidad':
                    if pd.api.types.is_numeric_dtype(renamed[col]):
                        renamed[col] = renamed[col].abs()  # Cantidad siempre positiva
                
                if pd.api.types.is_numeric_dtype(renamed[col]):
                    renamed[col] = renamed[col].astype(float)
        
        # Reordenar columnas según FINAL_COLS_ORDERED
        cols_final = [c for c in FINAL_COLS_ORDERED if c in renamed.columns]
        missing_cols = [c for c in FINAL_COLS_ORDERED if c not in renamed.columns]
        
        # Añadir columnas faltantes con valores vacíos
        for col in missing_cols:
            renamed[col] = ''
        
        # Reordenar según el orden deseado
        cols_final = [c for c in FINAL_COLS_ORDERED if c in renamed.columns]
        renamed = renamed.reindex(columns=cols_final, fill_value='')
        
        return renamed
        
    except Exception as e:
        print(f"Error preparando DataFrame final: {e}")
        return combined_df_raw

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
        Precio actual como float, o 0.0 si no se puede obtener.
    """
    if not yahoo_ticker: 
        return 0.0 # Devuelve float
    now = time.time()

    if not force_update and yahoo_ticker in price_cache:
        timestamp, price = price_cache[yahoo_ticker]
        # Devolver precio cacheado si es razonablemente reciente o si no se puede actualizar
        # Para esta función, si está en caché y no se fuerza, se devuelve.
        # La validación de antigüedad podría estar en otro nivel si es necesario.
        print(f"Precio {yahoo_ticker} (caché): {price}")
        if pd.isna(price): # Si el precio cacheado era NaN
            return 0.0
        return float(price) # Asegurar que es float

    print(f"Obteniendo precio {yahoo_ticker} (yfinance)...")
    try:
        ticker_obj = yf.Ticker(yahoo_ticker)
        # hist = ticker_obj.history(period="2d") # "2d" para asegurar que hay al menos un cierre anterior
        # Usar "1d" puede ser suficiente y más rápido si solo queremos el último cierre disponible
        data = ticker_obj.history(period="1d")

        if not data.empty and 'Close' in data and not data['Close'].empty:
            last_price = data['Close'].iloc[-1]
            if pd.isna(last_price): # Si yfinance devuelve NaN
                print(f"  -> Precio NaN para {yahoo_ticker}. Usando 0.0")
                last_price = 0.0
            else:
                last_price = float(last_price) # Convertir a float
            
            price_cache[yahoo_ticker] = (now, last_price) # Guardar float en caché
            print(f"  -> Obtenido y cacheado: {last_price}")
            return last_price
        else:
            print(f"  -> No historial reciente para {yahoo_ticker}. Usando 0.0")
            price_cache[yahoo_ticker] = (now, 0.0) # Guardar 0.0 en caché
            return 0.0
    except Exception as e:
        print(f"  -> Error yfinance obteniendo precio para {yahoo_ticker}: {e}")
        price_cache[yahoo_ticker] = (now, 0.0) # Guardar 0.0 en caché en caso de error
        return 0.0

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


# -*- coding: utf-8 -*-
# ... (tus imports y el resto de app.py) ...

def calculate_portfolio(df_transacciones):
    print("Iniciando cálculo portfolio...")
    stock_isin_to_debug = "SE0009554454" # ¡¡¡REEMPLAZA CON EL ISIN CORRECTO DE SBB!!!

    # DEBUG 2.1 (Como lo tenías, para ver la entrada completa para SBB)
    print(f"\nDEBUG: df_transacciones (ENTRADA) a calculate_portfolio")
    if 'ISIN' in df_transacciones.columns:
        debug_stock_input_rows = df_transacciones[df_transacciones['ISIN'] == stock_isin_to_debug]
        if not debug_stock_input_rows.empty:
            print(f"Filas para ISIN {stock_isin_to_debug} en la ENTRADA de calculate_portfolio:")
            cols_to_print_input = ['ISIN', 'Producto', 'Número', 'Precio', 'Valor local', 'Bolsa de', 'Unnamed: 8', 'Fecha', 'Hora', 'source_file', 'csv_format']
            cols_to_print_input_existing = [col for col in cols_to_print_input if col in debug_stock_input_rows.columns]
            print(debug_stock_input_rows[cols_to_print_input_existing].to_string())
            print("Tipos de datos ENTRADA (para ISIN debug):")
            print(debug_stock_input_rows[cols_to_print_input_existing].dtypes)
        else:
            print(f"No se encontraron filas para ISIN {stock_isin_to_debug} en la ENTRADA de calculate_portfolio.")
    else:
        print("Columna 'ISIN' no encontrada en df_transacciones (ENTRADA) para depuración.")

    # ----- INICIO CORRECCIÓN PARA KeyError -----
    required_cols = ["ISIN", "Producto", "Número", "Precio", "Valor local", "Bolsa de", "Unnamed: 8"]
    
    # Asegurar que Fecha y Hora están si existen en el input, para disponibilidad en el group
    if 'Fecha' in df_transacciones.columns:
        required_cols.append('Fecha')
    if 'Hora' in df_transacciones.columns:
        required_cols.append('Hora')

    sort_col = None
    if 'FechaHora' in df_transacciones.columns:
        if not df_transacciones['FechaHora'].isnull().all():
            if 'FechaHora' not in required_cols: # Añadir FechaHora si se va a usar para ordenar y no está ya
                required_cols.append('FechaHora')
            sort_col = 'FechaHora'
        # Si FechaHora es todo NaT, pero Fecha es usable, se usará Fecha (ya añadida a required_cols)
        elif 'Fecha' in required_cols and not df_transacciones['Fecha'].isnull().all():
            sort_col = 'Fecha'
    elif 'Fecha' in required_cols and not df_transacciones['Fecha'].isnull().all(): # No hay FechaHora, pero sí Fecha usable
        sort_col = 'Fecha'
    # ----- FIN CORRECCIÓN PARA KeyError -----
            
    missing = [c for c in required_cols if c not in df_transacciones.columns]
    if missing:
        # Si faltan columnas básicas (no Fecha/Hora/FechaHora que son para ordenar), es un error mayor.
        basic_missing = [m for m in missing if m not in ['Fecha', 'Hora', 'FechaHora']]
        if basic_missing:
            print(f"Error: Faltan columnas básicas para calculate_portfolio: {basic_missing}. Columnas disponibles: {df_transacciones.columns.tolist()}")
            return pd.DataFrame()
        # Si solo faltan de ordenación, podría continuar pero el orden no será garantizado.
        print(f"Advertencia: Faltan columnas para ordenación: {missing}. Se continuará sin ordenación si es posible.")


    existing_cols = [c for c in required_cols if c in df_transacciones.columns]
    df = df_transacciones[existing_cols].copy()

    num_cols = ['Número', 'Precio', 'Valor local']
    for col in num_cols:
         if col in df.columns:
              if df[col].dtype == 'object':
                  df[col] = df[col].astype(str).str.replace(',', '.', regex=False).str.strip()
              df[col] = pd.to_numeric(df[col], errors='coerce')
         else: # Esto no debería ocurrir si required_cols las incluye y no están en missing.
             print(f"Error: Columna numérica esperada '{col}' no encontrada en 'df' después de la selección inicial.")
             return pd.DataFrame()

    ess_cols = ['ISIN', 'Número', 'Precio', 'Valor local', 'Bolsa de', 'Unnamed: 8']
    existing_ess = [c for c in ess_cols if c in df.columns]

    if 'ISIN' in df.columns:
        df.dropna(subset=['ISIN'], inplace=True)
        df['ISIN'] = df['ISIN'].astype(str).str.strip()
        if df.empty:
            print("DataFrame vacío después de eliminar filas sin ISIN.")
            return pd.DataFrame()
    else: # Esto no debería ocurrir si 'ISIN' está en required_cols
        print("Error: Columna 'ISIN' no presente en 'df' antes de validación de datos esenciales.")
        return pd.DataFrame()

    # DEBUG 2.2 (Como lo tenías)
    print(f"\nDEBUG: df ANTES de dropna en calculate_portfolio (columnas esenciales: {existing_ess})")
    if 'ISIN' in df.columns: 
        debug_stock_before_dropna = df[df['ISIN'] == stock_isin_to_debug]
        if not debug_stock_before_dropna.empty:
            print(f"Filas para ISIN {stock_isin_to_debug} ANTES de dropna (mostrando columnas {existing_ess}):")
            print(debug_stock_before_dropna[existing_ess].to_string())
            print("Tipos de datos ANTES de dropna (para ISIN debug, columnas esenciales):")
            print(debug_stock_before_dropna[existing_ess].dtypes)
            cols_orig_debug = [col for col in ['Número', 'Precio', 'Valor local'] if col in debug_stock_before_dropna.columns]
            if cols_orig_debug:
                print("Valores Originales de cols numéricas (para ISIN debug):")
                print(debug_stock_before_dropna[cols_orig_debug].to_string())
        else:
            print(f"No se encontraron filas para ISIN {stock_isin_to_debug} ANTES de dropna.")
    
    if existing_ess: # Solo aplicar dropna si hay columnas esenciales definidas para ello
        df = df.dropna(subset=existing_ess)
    else:
        print("Advertencia: No hay columnas esenciales ('existing_ess') para validar con dropna. Saltando dropna.")


    # DEBUG 2.3 (Como lo tenías)
    print(f"\nDEBUG: df DESPUÉS de dropna en calculate_portfolio")
    if 'ISIN' in df.columns:
        debug_stock_after_dropna = df[df['ISIN'] == stock_isin_to_debug]
        if not debug_stock_after_dropna.empty:
            print(f"Filas para ISIN {stock_isin_to_debug} DESPUÉS de dropna (mostrando columnas {existing_ess}):")
            print(debug_stock_after_dropna[existing_ess].to_string())
        else:
            print(f"Filas para ISIN {stock_isin_to_debug} ELIMINADAS por dropna.")
    elif not df_transacciones.empty and 'ISIN' in df_transacciones.columns and \
         not df_transacciones[df_transacciones['ISIN'] == stock_isin_to_debug].empty :
        print(f"Filas para ISIN {stock_isin_to_debug} ELIMINADAS por dropna (o la columna ISIN se perdió).")


    if df.empty:
        print("DataFrame vacío después de limpiar NaNs en columnas esenciales en calculate_portfolio.")
        return pd.DataFrame()

    portfolio = {}
    print(f"Calculando portfolio sobre {len(df)} transacciones válidas...")
    
    for isin_val, group in df.groupby('ISIN'):
        # DEBUG DENTRO DEL GROUPBY (Como lo tenías)
        if isin_val == stock_isin_to_debug:
            print(f"\n---------- DEBUG DENTRO DEL BUCLE PARA ISIN: {stock_isin_to_debug} ----------")
            print("Datos del 'group' para este ISIN:")
            cols_to_print_group = ['ISIN', 'Producto', 'Número', 'Precio', 'Valor local', 'Fecha', 'Hora', 'source_file', 'csv_format']
            existing_cols_group = [col for col in cols_to_print_group if col in group.columns]
            print(group[existing_cols_group].to_string())
            if 'Número' in group.columns:
                print("Columna 'Número' en el 'group':")
                print(group['Número'].to_string())
                print(f"Tipo de dato de la columna 'Número' en el 'group': {group['Número'].dtype}")
            else:
                print("Advertencia: Columna 'Número' no encontrada en el 'group' para SBB.")
        
        if sort_col and sort_col in group.columns: # Asegurarse que sort_col existe antes de usarlo
            group = group.sort_values(by=sort_col, ascending=True, na_position='last')
        elif sort_col: # Si se definió sort_col pero no está en el group (no debería pasar con la lógica anterior)
            print(f"Advertencia: sort_col '{sort_col}' definido pero no encontrado en el grupo para ISIN {isin_val}. No se ordenará este grupo.")

        
        producto = group['Producto'].iloc[-1] if not group['Producto'].empty else 'Desconocido'
        bolsa_de = group['Bolsa de'].iloc[-1] if not group['Bolsa de'].empty else 'N/A'
        price_currency = group['Unnamed: 8'].iloc[-1] if not group['Unnamed: 8'].empty else 'N/A'

        col_qty = "Número"
        if not pd.api.types.is_numeric_dtype(group[col_qty]):
             if isin_val == stock_isin_to_debug:
                print(f"ADVERTENCIA PARA {stock_isin_to_debug}: La columna '{col_qty}' no es numérica antes de filtrar compras/ventas. Intentando convertir...")
             group[col_qty] = pd.to_numeric(group[col_qty], errors='coerce')

        compras = group[(group[col_qty] > 0) & pd.notna(group[col_qty])]
        ventas = group[(group[col_qty] < 0) & pd.notna(group[col_qty])]

        qty_bought = compras[col_qty].sum()
        qty_sold = ventas[col_qty].abs().sum() 
        qty_actual = qty_bought - qty_sold

        # DEBUG PARA CÁLCULO DE CANTIDADES (Como lo tenías, ahora las columnas Fecha y Hora deberían existir)
        if isin_val == stock_isin_to_debug:
            print(f"\nCálculos de cantidad para ISIN {stock_isin_to_debug}:")
            # Asegurarse de que las columnas existen en 'compras' y 'ventas' antes de intentar imprimirlas
            cols_debug_compras_ventas = ['Número', 'Precio']
            if 'Fecha' in compras.columns: cols_debug_compras_ventas.append('Fecha')
            if 'Hora' in compras.columns: cols_debug_compras_ventas.append('Hora')
            
            print("DataFrame 'compras' filtrado para SBB:")
            print(compras[cols_debug_compras_ventas].to_string() if not compras.empty else "DataFrame 'compras' vacío.")
            print(f"  qty_bought (sum de 'compras'): {qty_bought}")

            print("DataFrame 'ventas' filtrado para SBB:")
            print(ventas[cols_debug_compras_ventas].to_string() if not ventas.empty else "DataFrame 'ventas' vacío.")
            print(f"  qty_sold (sum de abs('ventas')): {qty_sold}")
            print(f"  qty_actual (qty_bought - qty_sold): {qty_actual}")
            print(f"  Condición para añadir a portfolio (qty_actual > 1e-6): {qty_actual > 1e-6}")
            print("------------------------------------------------------------")
        
        cost_pxq = 0.0
        if 'Precio' in compras.columns: # Chequear si existe la columna 'Precio'
             if pd.api.types.is_numeric_dtype(compras[col_qty]) and pd.api.types.is_numeric_dtype(compras['Precio']):
                 cost_pxq = (compras[col_qty] * compras['Precio'].abs()).sum()
        
        avg_buy_p = 0.0
        if qty_bought > 1e-9:
            avg_buy_p = cost_pxq / qty_bought
        
        if qty_actual > 1e-6:
            portfolio[isin_val] = {
                'ISIN': isin_val,
                'Producto': producto,
                'Bolsa de': bolsa_de,
                'currency': price_currency,
                'Cantidad Actual': round(qty_actual, 4),
                'Precio Medio Compra': round(avg_buy_p, 4)
            }

    if not portfolio:
        print("Portfolio final vacío después de procesar todos los grupos.")
    else:
        print(f"Portfolio final calculado con {len(portfolio)} activos.")
        
    df_portfolio = pd.DataFrame.from_dict(portfolio, orient='index')

    if df_portfolio.empty:
        return df_portfolio

    df_portfolio.reset_index(drop=True, inplace=True)

    if 'ISIN' not in df_portfolio.columns:
        print("Advertencia CRÍTICA: La columna 'ISIN' no está presente en el DataFrame de portfolio final después de las manipulaciones del índice.")
        return pd.DataFrame() 

    return df_portfolio

# No es necesario mostrar process_uploaded_csvs_unified de nuevo ya que no se ha modificado aquí.
# Asegúrate de que la función process_uploaded_csvs_unified que estés usando es la que te
# proporcioné en la respuesta anterior, que ya contenía el "DEBUG BLOQUE 1".

# También te incluyo la función process_uploaded_csvs_unified por si la necesitas completa
# con el DEBUG BLOCK 1 que habías pedido (sin cambios funcionales en esta, solo el print).
def process_uploaded_csvs_unified(files):
    """
    Procesa archivos CSV subidos, detectando automáticamente si son DeGiro o IBKR.
    Mantiene la misma interfaz que process_uploaded_csvs original.
    
    Args:
        files: Lista de archivos subidos
    
    Returns:
        tuple: (processed_df_for_csv, combined_df_raw, errors)
    """
    all_dfs = []
    filenames_processed = []
    errors = []
    mapping_data = load_mapping() 

    if not files or all(f.filename == '' for f in files):
        errors.append("Error: No archivos seleccionados.")
        return None, None, errors

    for file in files:
        if file and allowed_file(file.filename): 
            filename = secure_filename(file.filename)
            if not validate_filename_format_flexible(filename): 
                errors.append(f"Advertencia: Archivo '{filename}' ignorado (formato inválido).")
                continue
            
            df_current_file = None 
            try:
                file.seek(0)
                
                csv_format = detect_csv_format_simple(file) 
                print(f"Formato detectado para '{filename}': {csv_format}")
                
                if csv_format == 'degiro':
                    df_current_file = process_degiro_file(file, filename) 
                    if df_current_file is not None:
                        df_current_file['csv_format'] = 'degiro'
                
                elif csv_format == 'ibkr':
                    df_current_file = process_ibkr_file_complete(file, filename) 
                    if df_current_file is not None:
                        df_current_file['csv_format'] = 'ibkr'
                
                else: 
                    errors.append(f"Advertencia: Formato de archivo '{filename}' no reconocido o falló el procesamiento primario. Intentando como DeGiro...")
                    file.seek(0) 
                    df_current_file = process_degiro_file(file, filename)
                    if df_current_file is not None:
                        df_current_file['csv_format'] = 'degiro_fallback' 
                    else:
                        errors.append(f"Error: No se pudo procesar '{filename}' en ningún formato conocido.")

                if df_current_file is not None and not df_current_file.empty:
                    df_current_file['source_file'] = filename
                    all_dfs.append(df_current_file)
                    filenames_processed.append(filename)
                elif df_current_file is None and csv_format != 'unknown': 
                     errors.append(f"Error: No se pudieron leer datos válidos de '{filename}' (formato: {csv_format}).")

            except Exception as e:
                errors.append(f"Error crítico procesando archivo '{filename}': {e}")
                traceback.print_exc() 
                continue
        else:
            if file and file.filename: 
                errors.append(f"Archivo '{file.filename}' no permitido o inválido.")

    if not all_dfs:
        if not errors: 
            errors.append("Error: No se procesaron archivos válidos (lista de DataFrames vacía sin errores explícitos).")
        return None, None, errors

    try:
        combined_df_raw = pd.concat(all_dfs, ignore_index=True)
        
        try:
            if 'Fecha' in combined_df_raw.columns and 'Hora' in combined_df_raw.columns:
                combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
                if not combined_df_raw['Fecha'].isnull().all():
                    combined_df_raw['FechaHora'] = pd.to_datetime(
                        combined_df_raw['Fecha'].dt.strftime('%Y-%m-%d') + ' ' + combined_df_raw['Hora'].astype(str),
                        errors='coerce'
                    )
                    combined_df_raw = combined_df_raw.sort_values('FechaHora', ascending=True, na_position='first')
                else: 
                    combined_df_raw = combined_df_raw.sort_values('Hora', ascending=True, na_position='first')
            elif 'Fecha' in combined_df_raw.columns:
                combined_df_raw['Fecha'] = pd.to_datetime(combined_df_raw['Fecha'], errors='coerce', dayfirst=True)
                combined_df_raw = combined_df_raw.sort_values('Fecha', ascending=True, na_position='first')
        except Exception as e_date:
            errors.append(f"Advertencia: Error parseando/ordenando fechas en combined_df_raw: {e_date}")

        # <<< INICIO BLOQUE DE DEBUG 1 >>>
        print("\nDEBUG: combined_df_raw ANTES de calculate_portfolio")
        stock_isin_to_debug = "SE0009554454" # ¡¡¡REEMPLAZA CON EL ISIN CORRECTO!!!
        if 'ISIN' in combined_df_raw.columns:
            debug_stock_rows = combined_df_raw[combined_df_raw['ISIN'] == stock_isin_to_debug]
            if not debug_stock_rows.empty:
                print(f"Filas para ISIN {stock_isin_to_debug} en combined_df_raw ANTES de calculate_portfolio:")
                cols_to_print_debug1 = ['ISIN', 'Producto', 'Número', 'Precio', 'Valor local', 'Bolsa de', 'Unnamed: 8', 'source_file', 'csv_format', 'Fecha', 'Hora']
                cols_to_print_debug1_existing = [col for col in cols_to_print_debug1 if col in debug_stock_rows.columns]
                print(debug_stock_rows[cols_to_print_debug1_existing].to_string())
            else:
                print(f"No se encontraron filas para ISIN {stock_isin_to_debug} en combined_df_raw.")
        else:
            print("Columna 'ISIN' no encontrada en combined_df_raw para depuración.")
        # <<< FIN BLOQUE DE DEBUG 1 >>>

        df_for_portfolio_calc = combined_df_raw.copy()
        
        has_ibkr_data = 'csv_format' in df_for_portfolio_calc.columns and \
                        (df_for_portfolio_calc['csv_format'] == 'ibkr').any()
        if has_ibkr_data:
            print("Detectados datos IBKR, ajustando DataFrame para calculate_portfolio (prepare_dataframe_for_portfolio_calculation)")
            df_for_portfolio_calc = prepare_dataframe_for_portfolio_calculation(df_for_portfolio_calc)
        
        processed_df_for_csv = prepare_processed_dataframe(combined_df_raw, errors)
        
        print(f"Procesamiento unificado completado: {len(processed_df_for_csv) if processed_df_for_csv is not None else 0} filas en CSV final, {len(df_for_portfolio_calc)} filas para cálculo de portfolio.")
        return processed_df_for_csv, df_for_portfolio_calc, errors
        
    except Exception as e_concat:
        errors.append(f"Error crítico al combinar o procesar DataFrames: {e_concat}")
        traceback.print_exc()
        return None, None, errors

# ... (resto de tu código) ...




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
            
            # Aquí se llama a process_uploaded_csvs o process_uploaded_csvs_unified
            # Asumiré que process_uploaded_csvs es un alias o la versión que utilizas.
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
                            elif hasattr(item_db, 'is_manual'): item_db.is_manual = False # Campo antiguo
                            needs_update = True
                        new_portfolio_isins.discard(isin) 
                    else: 
                        if item_db.is_in_portfolio:
                            item_db.is_in_portfolio = False
                            if hasattr(item_db, 'is_in_followup'): item_db.is_in_followup = True
                            elif hasattr(item_db, 'is_manual'): item_db.is_manual = True # Campo antiguo
                            needs_update = True
                    if needs_update: items_to_commit_or_add.append(item_db)

                for isin_to_add in new_portfolio_isins:
                    portfolio_row = portfolio_df[portfolio_df['ISIN'] == isin_to_add].iloc[0]
                    map_info = mapping_data_sync.get(isin_to_add, {})
                    ticker = map_info.get('ticker', 'N/A')
                    google_ex = map_info.get('google_ex', None)
                    name = map_info.get('name', portfolio_row.get('Producto', 'Desconocido')).strip()
                    if not name: name = portfolio_row.get('Producto', 'Desconocido')

                    # --- INICIO: LÓGICA CORREGIDA PARA YAHOO SUFFIX ---
                    determined_yahoo_suffix = map_info.get('yahoo_suffix') # Prioridad 1: desde el mapeo global
                    if determined_yahoo_suffix is None or determined_yahoo_suffix == '':
                        # Prioridad 2: Derivar de 'Bolsa de' (para DeGiro o si el mapeo global no tiene sufijo)
                        degiro_bolsa_code_or_ibkr_market = portfolio_row.get('Bolsa de')
                        if degiro_bolsa_code_or_ibkr_market:
                            determined_yahoo_suffix = BOLSA_TO_YAHOO_MAP.get(degiro_bolsa_code_or_ibkr_market, '')
                        else:
                            determined_yahoo_suffix = '' # Default si no hay 'Bolsa de'
                    # --- FIN: LÓGICA CORREGIDA PARA YAHOO SUFFIX ---
                    
                    new_watch_item_data = {
                        'item_name': name, 'isin': isin_to_add, 'ticker': ticker,
                        'yahoo_suffix': determined_yahoo_suffix, # Usar el sufijo determinado correctamente
                        'google_ex': google_ex,
                        'user_id': current_user.id, 'is_in_portfolio': True
                    }
                    if hasattr(WatchlistItem, 'is_in_followup'): 
                        new_watch_item_data['is_in_followup'] = False
                    elif hasattr(WatchlistItem, 'is_manual'): # Manejar nombre de campo antiguo
                        new_watch_item_data['is_manual'] = False
                    
                    new_watch_item = WatchlistItem(**new_watch_item_data)
                    items_to_commit_or_add.append(new_watch_item)
                
                if items_to_commit_or_add:
                     db.session.add_all(items_to_commit_or_add)
                     db.session.commit()
                     print("Sincronización watchlist DB completada.")
            except Exception as e_sync: 
                db.session.rollback()
                traceback.print_exc() # Imprimir traza para depuración
                flash(f"Error Interno al actualizar la watchlist: {e_sync}", "danger")
        else:
            print("Portfolio vacío, no se sincroniza watchlist.")
        
        mapping_data = load_mapping() # Recargar por si se actualizó en process_ibkr_file_complete
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
                    
                    # Asegurar que FINAL_COLS_ORDERED tiene Ticker y Exchange Google en las posiciones correctas
                    # o añadirlos si no están y luego reordenar.
                    # Esta lógica asume que FINAL_COLS_ORDERED ya está definida y es correcta.
                    cols_final_ordered_existing = [c for c in FINAL_COLS_ORDERED if c in processed_df_for_csv.columns]
                    
                    # Añadir Ticker y Exchange Google si no están en cols_final_ordered_existing pero sí en df
                    if 'Ticker' in processed_df_for_csv.columns and 'Ticker' not in cols_final_ordered_existing:
                        # Intentar insertar en la posición deseada de FINAL_COLS_ORDERED
                        try:
                            idx_ticker = FINAL_COLS_ORDERED.index('Ticker')
                            cols_final_ordered_existing.insert(idx_ticker, 'Ticker')
                        except ValueError: # Si 'Ticker' no está en FINAL_COLS_ORDERED, añadir al final
                            cols_final_ordered_existing.append('Ticker')
                            
                    if 'Exchange Google' in processed_df_for_csv.columns and 'Exchange Google' not in cols_final_ordered_existing:
                        try:
                            idx_google_ex = FINAL_COLS_ORDERED.index('Exchange Google')
                            cols_final_ordered_existing.insert(idx_google_ex, 'Exchange Google')
                        except ValueError:
                            cols_final_ordered_existing.append('Exchange Google')
                    
                    # Reordenar y rellenar columnas faltantes de FINAL_COLS_ORDERED
                    processed_df_for_csv = processed_df_for_csv.reindex(columns=FINAL_COLS_ORDERED, fill_value='')
                    
                    uid_final = uuid.uuid4(); final_temp_csv_filename_for_session = f"processed_{uid_final}.csv"
                    path_final = os.path.join(OUTPUT_FOLDER, final_temp_csv_filename_for_session) 
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
                ) 
                if save_success: flash('Archivos procesados y portfolio listo.', 'success')
                else: flash('Error al guardar datos del portfolio en BD.', 'warning')
            else:
                session.pop('portfolio_data', None)
                if csv_data_list_for_db: # Guardar solo el CSV si el portfolio está vacío
                     save_user_portfolio(user_id=current_user.id, portfolio_data=None, csv_data=csv_data_list_for_db, csv_filename=final_csv_filename_to_save_in_db)
                flash('Archivos procesados. Portfolio vacío.', 'info')
            return redirect(url_for('show_portfolio'))

    # Este return solo se alcanzaría si el método no es POST, lo cual ya se maneja al principio
    return redirect(url_for('login'))

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
    temp_portfolio_filename = session.get('temp_portfolio_pending_filename') 

    # Limpiar sesión
    session.pop('missing_isins_for_mapping', None)
    session.pop('temp_csv_pending_filename', None)
    session.pop('temp_portfolio_pending_filename', None)
    print(f"Recuperado: {len(missing_isins_details)} ISINs, CSV: {temp_csv_filename}, Portfolio: {temp_portfolio_filename}")

    # --- Cargar DFs desde archivos temporales ---
    processed_df_for_csv = pd.DataFrame()
    portfolio_df = pd.DataFrame() 
    load_error = False
    
    if temp_csv_filename:
        path = os.path.join(OUTPUT_FOLDER, temp_csv_filename)
        try:
            if os.path.exists(path): 
                df_csv = pd.read_json(path, orient='records', lines=True)
                print(f"CSV cargado: {path}")
                os.remove(path)
                print(f"CSV temp elim.")
                processed_df_for_csv = df_csv
            else: 
                print(f"Error: Temp CSV no encontrado: {path}")
                load_error = True # Corrección: debe ser load_error, no solo error
        except Exception as e: 
            print(f"Error cargando CSV: {e}")
            load_error = True # Corrección: debe ser load_error, no solo error
    else: 
        print("Warn: No temp CSV.")

    if temp_portfolio_filename:
        temp_portfolio_path = os.path.join(OUTPUT_FOLDER, temp_portfolio_filename)
        try:
            if os.path.exists(temp_portfolio_path):
                portfolio_df = pd.read_json(temp_portfolio_path, orient='records', lines=True) 
                print(f"DF de Portfolio cargado desde: {temp_portfolio_path} ({len(portfolio_df)} filas)")
                os.remove(temp_portfolio_path) 
                print(f"Archivo temporal Portfolio pendiente eliminado.")
            else:
                 print(f"Error: Archivo temporal de Portfolio no encontrado: {temp_portfolio_path}")
                 load_error = True
        except Exception as e_load_port:
            print(f"Error CRÍTICO al cargar DF de Portfolio desde {temp_portfolio_path}: {e_load_port}")
            load_error = True
    else:
         print("Advertencia: No había nombre de archivo temporal de Portfolio en sesión.")
         if missing_isins_details: 
             load_error = True


    if load_error:
         flash("Error al recuperar datos temporales pendientes. Vuelve a subir.", "danger")
         return redirect(url_for('index')) # Asumiendo que 'index' es la página de subida principal

    # --- Procesar formulario y actualizar mapping_db.json ---
    mapping_data = load_mapping()
    updated_count = 0
    if missing_isins_details:
         print(f"Procesando form para {len(missing_isins_details)} ISINs...")
         for item in missing_isins_details:
            isin = item['isin']
            ticker = request.form.get(f'ticker_{isin}')
            google_ex = request.form.get(f'google_ex_{isin}')
            yahoo_s = request.form.get(f'yahoo_suffix_{isin}', '')
            name = request.form.get(f'name_{isin}', item.get('name', '')) # Usar nombre del item si no se envía
            
            if ticker and google_ex: 
               ticker_clean = ticker.strip().upper()
               google_ex_clean = google_ex.strip().upper()
               yahoo_s_clean = yahoo_s.strip()
               name_clean = name.strip()

               if isin in mapping_data: 
                   current_entry = mapping_data[isin]
                   changed_in_existing = False
                   if not current_entry.get('ticker') and ticker_clean: mapping_data[isin]['ticker'] = ticker_clean; changed_in_existing = True
                   if not current_entry.get('google_ex') and google_ex_clean: mapping_data[isin]['google_ex'] = google_ex_clean; changed_in_existing = True
                   if current_entry.get('yahoo_suffix') is None or (not current_entry.get('yahoo_suffix') and yahoo_s_clean): mapping_data[isin]['yahoo_suffix'] = yahoo_s_clean; changed_in_existing = True
                   if not current_entry.get('name') and name_clean: mapping_data[isin]['name'] = name_clean; changed_in_existing = True
                   
                   if changed_in_existing: updated_count += 1; print(f"  Mapeo existente ACTUALIZADO {isin}")
                   else: print(f"  Mapeo {isin} ya completo o sin cambios válidos.")
               else: 
                   mapping_data[isin] = {
                       "ticker": ticker_clean, 
                       "google_ex": google_ex_clean, 
                       "yahoo_suffix": yahoo_s_clean, 
                       "name": name_clean
                   }
                   updated_count += 1
                   print(f"  Mapeo NUEVO añadido {isin}")
            else: 
                print(f"Warn: Datos incompletos form {isin}")
                flash(f"Datos incompletos para {isin} ({item.get('name', isin)}). No se guardó mapeo global.", "warning")

    if updated_count > 0:
        save_mapping(mapping_data)
        flash(f"Guardados {updated_count} mapeos globales.", "success")
        mapping_data = load_mapping() 
    elif missing_isins_details:
         flash("No se guardó ningún mapeo global nuevo.", "info")


    # --- SINCRONIZAR WATCHLIST DB (AHORA que mapping_data está actualizado) ---
    if portfolio_df is not None and not portfolio_df.empty: 
        print(f"Sincronizando portfolio ({len(portfolio_df)} items) con watchlist DB TRAS GUARDAR MAPEO...")
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
                        print(f"  -> Marcar {isin} EN portfolio")
                        item_db.is_in_portfolio = True
                        if hasattr(item_db, 'is_in_followup'): item_db.is_in_followup = False
                        elif hasattr(item_db, 'is_manual'): item_db.is_manual = False
                        needs_update = True
                    new_portfolio_isins.discard(isin)
                else:
                    if item_db.is_in_portfolio: 
                        print(f"  -> Marcar {isin} FUERA portfolio (followup=True)")
                        item_db.is_in_portfolio = False
                        if hasattr(item_db, 'is_in_followup'): item_db.is_in_followup = True
                        elif hasattr(item_db, 'is_manual'): item_db.is_manual = True
                        needs_update = True
                if needs_update: items_to_commit_or_add.append(item_db)
            
            print(f" ISINs nuevos a añadir a watchlist DB: {len(new_portfolio_isins)}")
            for isin_to_add in new_portfolio_isins:
                portfolio_row = portfolio_df[portfolio_df['ISIN'] == isin_to_add].iloc[0]
                map_info = mapping_data.get(isin_to_add, {}) 
                ticker = map_info.get('ticker', 'N/A')
                google_ex = map_info.get('google_ex', None)
                name = map_info.get('name', portfolio_row.get('Producto', '???')).strip()
                if not name: name = portfolio_row.get('Producto', '???')

                # --- INICIO: LÓGICA CORREGIDA PARA YAHOO SUFFIX ---
                determined_yahoo_suffix = map_info.get('yahoo_suffix') # Prioridad 1: desde el mapeo global
                if determined_yahoo_suffix is None or determined_yahoo_suffix == '':
                    # Prioridad 2: Derivar de 'Bolsa de' (para DeGiro o si el mapeo global no tiene sufijo)
                    degiro_bolsa_code_or_ibkr_market = portfolio_row.get('Bolsa de')
                    if degiro_bolsa_code_or_ibkr_market:
                        determined_yahoo_suffix = BOLSA_TO_YAHOO_MAP.get(degiro_bolsa_code_or_ibkr_market, '')
                    else:
                        determined_yahoo_suffix = '' # Default si no hay 'Bolsa de'
                # --- FIN: LÓGICA CORREGIDA PARA YAHOO SUFFIX ---
                
                print(f"  -> Añadiendo a watchlist DB: {isin_to_add} ({ticker}{determined_yahoo_suffix})")
                new_watch_item_data = {
                    'item_name': name, 'isin': isin_to_add, 'ticker': ticker,
                    'yahoo_suffix': determined_yahoo_suffix, # Usar el sufijo determinado correctamente
                    'google_ex': google_ex, 'user_id': current_user.id,
                    'is_in_portfolio': True
                }
                if hasattr(WatchlistItem, 'is_in_followup'): 
                    new_watch_item_data['is_in_followup'] = False
                elif hasattr(WatchlistItem, 'is_manual'): 
                    new_watch_item_data['is_manual'] = False
                
                new_watch_item = WatchlistItem(**new_watch_item_data)
                items_to_commit_or_add.append(new_watch_item)

            if items_to_commit_or_add:
                db.session.add_all(items_to_commit_or_add)
                db.session.commit()
            print("Sincronización watchlist DB (tras mapeo) completada.")

        except Exception as e_sync:
            db.session.rollback()
            print(f"Error durante sincronización watchlist DB (tras mapeo): {e_sync}")
            traceback.print_exc()
            flash("Error al actualizar la watchlist tras guardar mapeo.", "danger")
    else:
        print("Advertencia: No hay datos de portfolio cargados para sincronizar watchlist después de guardar mapeo.")
    # --- FIN BLOQUE SINCRONIZACIÓN ---


    # --- Preparar y guardar CSV FINAL ---
    temp_csv_filename_final = None
    csv_data_list_for_db = None # Para guardar en UserPortfolio
    if processed_df_for_csv is not None and not processed_df_for_csv.empty:
        print("Enriqueciendo y guardando CSV final...")
        try:
            processed_df_for_csv['Ticker'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('ticker', ''))
            processed_df_for_csv['Exchange Yahoo'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('yahoo_suffix', '')) # Usar yahoo_suffix
            processed_df_for_csv['Exchange Google'] = processed_df_for_csv['ISIN'].map(lambda x: mapping_data.get(x, {}).get('google_ex', ''))
            
            # Reordenar y asegurar todas las columnas de FINAL_COLS_ORDERED
            processed_df_for_csv = processed_df_for_csv.reindex(columns=FINAL_COLS_ORDERED, fill_value='')
            
            uid_f = uuid.uuid4(); temp_csv_filename_final = f"processed_{uid_f}.csv"; 
            path_f = os.path.join(OUTPUT_FOLDER, temp_csv_filename_final); 
            processed_df_for_csv.to_csv(path_f, index=False, sep=';', decimal='.', encoding='utf-8-sig'); 
            session['csv_temp_file'] = temp_csv_filename_final; 
            csv_data_list_for_db = processed_df_for_csv.to_dict('records') # Para UserPortfolio
            print(f"CSV final guardado: {path_f}")
        except Exception as e: 
            flash(f"Error guardando CSV final: {e}", "danger"); 
            session.pop('csv_temp_file', None)
            temp_csv_filename_final = None # Asegurar que no se guarda en DB si falla
            csv_data_list_for_db = None
    else: 
        print("Warn: No datos CSV final."); 
        session.pop('csv_temp_file', None)


    # --- Guardar portfolio (cargado de temp) en sesión para mostrar y en DB ---
    if portfolio_df is not None and not portfolio_df.empty:
         portfolio_list_for_db = portfolio_df.to_dict('records')
         session['portfolio_data'] = portfolio_list_for_db # Para la vista inmediata
         save_user_portfolio(
            user_id=current_user.id,
            portfolio_data=portfolio_list_for_db,
            csv_data=csv_data_list_for_db, 
            csv_filename=temp_csv_filename_final 
        )
         print("Datos de portfolio puestos en sesión y guardados en DB.")
    else:
         session.pop('portfolio_data', None)
         # Si no hay portfolio pero sí CSV, guardar solo el CSV en DB
         if csv_data_list_for_db:
             save_user_portfolio(
                 user_id=current_user.id,
                 portfolio_data=None, # No hay portfolio
                 csv_data=csv_data_list_for_db,
                 csv_filename=temp_csv_filename_final
             )
         print("Advertencia: No hay datos de portfolio (o error carga) para poner en sesión/DB.")

    print("Redirigiendo a show_portfolio...")
    return redirect(url_for('show_portfolio'))



@app.route('/update_portfolio_prices')
@login_required
def update_portfolio_prices():
    """
    Actualiza los precios del portfolio existente desde yfinance.
    Maneja la conversión de GBX a GBP para cálculos en EUR.
    Los datos actualizados se guardan en la base de datos y se establecen a 0.0 si no se encuentran.
    """
    print("Iniciando /update_portfolio_prices...")

    portfolio_data_list, _, _ = load_user_portfolio(current_user.id)

    if not portfolio_data_list:
        flash("No hay datos de portfolio para actualizar. Por favor, carga tus CSVs primero.", "warning")
        return redirect(url_for('show_portfolio'))

    if not isinstance(portfolio_data_list, list):
        flash("Error: El formato de los datos del portfolio cargados desde la BD es incorrecto.", "danger")
        portfolio_data_list = []

    try:
        portfolio_df = pd.DataFrame(portfolio_data_list)
    except Exception as e_df:
        print(f"Error convirtiendo portfolio_data_list a DataFrame: {e_df}")
        flash("Error interno al procesar datos del portfolio.", "danger")
        return redirect(url_for('show_portfolio'))

    mapping_data = load_mapping()
    watchlist_items = WatchlistItem.query.filter_by(user_id=current_user.id, is_in_portfolio=True).all()
    watchlist_isin_map = {item.isin: item for item in watchlist_items if item.isin}

    enriched_portfolio_data = []
    precios_actualizados = 0
    precios_fallidos = 0

    print(f"Actualizando precios para {len(portfolio_df) if not portfolio_df.empty else 0} items del portfolio...")
    if not portfolio_df.empty:
        for _, row_series in portfolio_df.iterrows():
            new_item = row_series.to_dict()
            isin = new_item.get('ISIN')

            ticker_base = None
            yahoo_suffix = None
            original_currency = str(new_item.get('currency', '')).upper()
            avg_buy_price_original_unit = new_item.get('Precio Medio Compra', 0.0) # Default to 0.0 if missing
            if pd.isna(avg_buy_price_original_unit): avg_buy_price_original_unit = 0.0

            qty = new_item.get('Cantidad Actual', 0.0) # Default to 0.0 if missing
            if pd.isna(qty): qty = 0.0

            if isin in watchlist_isin_map:
                ticker_base = watchlist_isin_map[isin].ticker
                yahoo_suffix = watchlist_isin_map[isin].yahoo_suffix
            elif isin in mapping_data:
                ticker_base = mapping_data[isin].get('ticker')
                yahoo_suffix = mapping_data[isin].get('yahoo_suffix', '')

            if not ticker_base:
                precios_fallidos += 1
                print(f"  No se encontró ticker para ISIN {isin}. Valores EUR se calcularán como 0 o basados en coste 0.")
                new_item['current_price_local'] = 0.0 # Default si no hay ticker
                new_item['market_value_eur'] = 0.0
                # Preservar coste si existe, sino 0.0
                cost_basis_eur_existing = new_item.get('cost_basis_eur_est')
                new_item['cost_basis_eur_est'] = float(cost_basis_eur_existing) if pd.notna(cost_basis_eur_existing) else 0.0
                new_item['pl_eur_est'] = 0.0 - new_item['cost_basis_eur_est']
                enriched_portfolio_data.append(new_item)
                continue

            yahoo_ticker_full = f"{ticker_base}{yahoo_suffix}"
            price_from_yfinance = get_current_price(yahoo_ticker_full, force_update=True) # Ya devuelve float, 0.0 en fallo

            if price_from_yfinance != 0.0: # Solo proceder si se obtuvo un precio > 0
                precios_actualizados += 1
                actual_numeric_price_from_yfinance = price_from_yfinance # Ya es float

                price_for_eur_calc = actual_numeric_price_from_yfinance
                avg_buy_price_for_eur_calc = float(avg_buy_price_original_unit)
                currency_for_fx = original_currency

                is_lse_pence_ticker = yahoo_ticker_full.endswith('.L')

                if original_currency == 'GBX':
                    new_item['current_price_local'] = actual_numeric_price_from_yfinance
                    price_for_eur_calc = actual_numeric_price_from_yfinance / 100.0
                    avg_buy_price_for_eur_calc = avg_buy_price_for_eur_calc / 100.0
                    currency_for_fx = 'GBP'
                elif original_currency == 'GBP':
                    if is_lse_pence_ticker:
                        new_item['current_price_local'] = actual_numeric_price_from_yfinance / 100.0
                        price_for_eur_calc = new_item['current_price_local']
                    else:
                        new_item['current_price_local'] = actual_numeric_price_from_yfinance
                        price_for_eur_calc = actual_numeric_price_from_yfinance
                    currency_for_fx = 'GBP'
                else:
                    new_item['current_price_local'] = actual_numeric_price_from_yfinance

                exchange_rate = get_exchange_rate(currency_for_fx, 'EUR')
                new_item['exchange_rate_to_eur'] = exchange_rate

                if exchange_rate is not None and pd.notna(exchange_rate):
                    cost_basis_eur_est = qty * avg_buy_price_for_eur_calc * exchange_rate
                    market_value_eur = qty * price_for_eur_calc * exchange_rate

                    new_item['cost_basis_eur_est'] = float(cost_basis_eur_est)
                    new_item['market_value_eur'] = float(market_value_eur)
                    new_item['pl_eur_est'] = float(market_value_eur - cost_basis_eur_est)
                else:
                    print(f"  No se pudo obtener tipo de cambio para {currency_for_fx}->EUR para {isin}. Valores EUR serán 0.")
                    new_item['cost_basis_eur_est'] = 0.0 # O mantener el coste original si se prefiere y solo MktVal=0
                    new_item['market_value_eur'] = 0.0
                    new_item['pl_eur_est'] = 0.0 - new_item.get('cost_basis_eur_est', 0.0)
            else: # Precio de yfinance fue 0.0 (fallo en get_current_price)
                precios_fallidos += 1
                print(f"  No se pudo obtener precio > 0 para {isin} ({yahoo_ticker_full}). Precio yfinance: {price_from_yfinance}. Valores EUR se basarán en precio 0.")
                new_item['current_price_local'] = 0.0 # Reflejar que el precio actual es 0 o desconocido
                new_item['market_value_eur'] = 0.0

                # Mantener el coste base si ya existía, si no, 0.0
                cost_basis_existing = new_item.get('cost_basis_eur_est')
                new_item['cost_basis_eur_est'] = float(cost_basis_existing) if pd.notna(cost_basis_existing) else 0.0

                new_item['pl_eur_est'] = 0.0 - new_item['cost_basis_eur_est']

            enriched_portfolio_data.append(new_item)

    save_success = save_user_portfolio(
        user_id=current_user.id,
        portfolio_data=enriched_portfolio_data,
        csv_data=None,
        csv_filename=session.get('csv_temp_file')
    )

    if save_success:
        if precios_actualizados > 0 or precios_fallidos > 0: # Mostrar mensaje si hubo algún intento
            flash_msg = f"Precios actualizados en BD. Obtenidos: {precios_actualizados}, Fallidos/Cero: {precios_fallidos}."
            flash_cat = "success" if precios_actualizados > 0 else "warning"
            flash(flash_msg, flash_cat)
        else: # No hubo items en portfolio_df para procesar
            flash("No había items en el portfolio para actualizar precios.", "info")
    else:
        flash("Error al guardar el portfolio actualizado en la base de datos.", "danger")

    print("Fin /update_portfolio_prices.")
    return redirect(url_for('show_portfolio'))


# ... (resto de tu app.py, incluyendo show_portfolio, load_user_portfolio, save_user_portfolio, etc.) ...

@app.route('/portfolio')
@login_required
def show_portfolio():
    """
    Muestra la página con el resumen de la cartera, cargando SIEMPRE desde la base de datos.
    """
    print(f"Iniciando show_portfolio para usuario: {current_user.id}")
    
    # --- MODIFICACIÓN EN EL DESEMPAQUETADO AQUÍ ---
    portfolio_data_list, _, csv_filename_from_db = load_user_portfolio(current_user.id)
    # portfolio_data_list recibe el primer valor (datos del portfolio)
    # _ descarta el segundo valor (csv_data, la lista de diccionarios del CSV)
    # csv_filename_from_db recibe el tercer valor (el nombre del archivo CSV)
    
    csv_existe = False
    last_updated = None 
    
    if portfolio_data_list is None:
        print("No se encontraron datos de portfolio en la base de datos.")
        portfolio_data_list = [] 
        flash("No hay datos de portfolio disponibles. Por favor, carga tus CSVs.", "info")
    elif not isinstance(portfolio_data_list, list):
        print(f"Error: El formato de portfolio_data_list cargado de BD no es una lista (tipo: {type(portfolio_data_list)}).")
        flash("Error al cargar datos del portfolio desde la base de datos (formato incorrecto).", "danger")
        portfolio_data_list = []
    else:
        print(f"Datos cargados de BD: {len(portfolio_data_list)} items")
        portfolio_record = UserPortfolio.query.filter_by(user_id=current_user.id).first()
        if portfolio_record and portfolio_record.last_updated:
            # Formatear la fecha aquí para asegurar que es un string
            last_updated = portfolio_record.last_updated.strftime("%d/%m/%Y %H:%M:%S")

    if csv_filename_from_db: 
        session['csv_temp_file'] = csv_filename_from_db 
        # Usar current_app.config en lugar de solo app.config si estás dentro de funciones de blueprint o similar
        # o si 'app' no está directamente en el scope global de esta función.
        # Sin embargo, si 'app' es tu objeto Flask global, app.config['OUTPUT_FOLDER'] está bien.
        output_folder_path = app.config.get('OUTPUT_FOLDER', 'output') # Usar .get con default por seguridad
        path_to_check = os.path.join(output_folder_path, csv_filename_from_db)
        csv_existe = os.path.exists(path_to_check)
        if not csv_existe:
             print(f"Advertencia: El archivo CSV '{csv_filename_from_db}' (de la BD) no existe en disco en '{path_to_check}'. El enlace de descarga podría no funcionar.")
    else: 
        session.pop('csv_temp_file', None)

    enriched_portfolio_data = []
    total_market_value_eur = 0.0
    # total_cost_basis_eur_est = 0.0 # Ya no se calcula/muestra aquí directamente
    total_pl_eur_est = 0.0 # P&L Total no realizado

    if portfolio_data_list: 
        print(f"Procesando {len(portfolio_data_list)} items del portfolio para mostrar...")
        for item in portfolio_data_list:
            try:
                # Asegurar que new_item es un diccionario mutable
                new_item = dict(item) if isinstance(item, dict) else {} 
                if not new_item and isinstance(item, pd.Series): # Fallback si item es una Serie de Pandas
                    new_item = item.to_dict()

                # Sumar a totales si los valores son numéricos y existen
                market_val_eur = new_item.get('market_value_eur')
                if pd.notna(market_val_eur):
                    try: 
                        total_market_value_eur += float(market_val_eur)
                    except (ValueError, TypeError): 
                        if 'ISIN' in new_item: print(f"Advertencia: market_value_eur ('{market_val_eur}') para ISIN {new_item['ISIN']} no es numérico.")
                
                # El pl_eur_est ya debería estar calculado y guardado
                pl_eur = new_item.get('pl_eur_est')
                if pd.notna(pl_eur):
                    try: 
                        total_pl_eur_est += float(pl_eur)
                    except (ValueError, TypeError): 
                        if 'ISIN' in new_item: print(f"Advertencia: pl_eur_est ('{pl_eur}') para ISIN {new_item['ISIN']} no es numérico.")
                
                enriched_portfolio_data.append(new_item)
            except Exception as e_proc_item:
                print(f"Error procesando item del portfolio para mostrar: {item}. Error: {e_proc_item}")
                continue
        print(f"Portfolio procesado para mostrar: {len(enriched_portfolio_data)} items válidos")
    else:
        print("No hay datos de portfolio para procesar y mostrar.")

    return render_template(
        'portfolio.html', 
        portfolio=enriched_portfolio_data,
        temp_csv_file_exists=csv_existe, 
        total_value_eur=total_market_value_eur,
        total_pl_eur=total_pl_eur_est, # Este es el P&L no realizado total
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
        
        # GUARDAR LA FECHA ANTERIOR PARA COMPARAR
        old_fecha_resultados = item_to_edit.fecha_resultados
        
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
            
            # *** NUEVA FUNCIONALIDAD: RESOLVER WARNINGS AUTOMÁTICAMENTE ***
            print(f"Verificando si hay warnings para resolver para item {item_id}")
            warnings_resolved = resolve_warnings_for_item(current_user.id, item_to_edit, old_fecha_resultados)
            if warnings_resolved > 0:
                print(f"Se resolvieron automáticamente {warnings_resolved} warnings")
            
            # *** NUEVA FUNCIONALIDAD: DETECTAR FECHAS PASADAS ***
            check_past_date_for_item(current_user.id, item_to_edit)
            
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

def resolve_warnings_for_item(user_id, item, old_fecha_resultados):
    """Resuelve warnings automáticamente cuando se edita un item de watchlist."""
    warnings_resolved = 0
    today = date.today()

    try:
        # Buscar warnings relacionados con este item
        warnings = MailboxMessage.query.filter_by(
            user_id=user_id,
            message_type='config_warning',
            related_watchlist_item_id=item.id
        ).all()

        for warning in warnings:
            should_resolve = False

            # Caso 1: Warning por fecha faltante - ahora tiene fecha válida
            if 'no hay fecha de resultados definida' in warning.content:
                if item.fecha_resultados and item.fecha_resultados >= today:
                    should_resolve = True

            # Caso 2: Warning por fecha pasada - ahora tiene fecha futura
            elif 'fecha pasada' in warning.title.lower():
                if item.fecha_resultados and item.fecha_resultados >= today:
                    should_resolve = True

            if should_resolve:
                # Crear mensaje de resolución
                resolved_msg = MailboxMessage(
                    user_id=user_id,
                    message_type='config_resolved',
                    title=f'✅ Problema resuelto: {item.item_name or item.ticker}',
                    content=f'La fecha de resultados para {item.item_name or item.ticker} ha sido actualizada a {item.fecha_resultados.strftime("%d/%m/%Y")}. Las alertas están ahora activas.',
                    related_watchlist_item_id=item.id,
                    related_alert_config_id=warning.related_alert_config_id,
                    is_read=True  # Marcar como leído para archivar
                )
                db.session.add(resolved_msg)

                # Eliminar el warning
                db.session.delete(warning)
                warnings_resolved += 1

        db.session.commit()

    except Exception as e:
        print(f"Error resolviendo warnings para item {item.id}: {e}")
        db.session.rollback()

    return warnings_resolved


def check_past_date_for_item(user_id, item):
    """Verifica si la fecha actualizada es pasada y crea warning si es necesario."""
    if not item.fecha_resultados:
        return

    today = date.today()
    if item.fecha_resultados < today:
        try:
            # Verificar si ya existe un warning de fecha pasada para este item
            existing_warning = MailboxMessage.query.filter_by(
                user_id=user_id,
                message_type='config_warning',
                related_watchlist_item_id=item.id
            ).filter(
                MailboxMessage.title.contains('fecha pasada')
            ).first()

            if not existing_warning:
                # Buscar si hay configuraciones de alertas activas para este item
                has_active_alerts = AlertConfiguration.query.filter_by(
                    user_id=user_id,
                    is_active=True,
                    alert_reason='earnings_report'
                ).filter(
                    (AlertConfiguration.scope == 'individual') & (AlertConfiguration.watchlist_item_id == item.id) |
                    (AlertConfiguration.scope.in_(['all', 'portfolio', 'watchlist']))
                ).first()

                if has_active_alerts:
                    warning_msg = MailboxMessage(
                        user_id=user_id,
                        message_type='config_warning',
                        title=f'⚠️ Fecha pasada: {item.item_name or item.ticker}',
                        content=f'La fecha de resultados de {item.item_name or item.ticker} ({item.fecha_resultados.strftime("%d/%m/%Y")}) ya pasó. Por favor, actualízala para que las alertas funcionen correctamente.',
                        related_watchlist_item_id=item.id
                    )
                    db.session.add(warning_msg)
                    db.session.commit()

        except Exception as e:
            print(f"Error verificando fecha pasada para item {item.id}: {e}")
            db.session.rollback()

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


# ...
class BrokerOperationForm(FlaskForm):
    """Formulario actualizado con el nuevo tipo 'Reinversión' y campo 'Acción'"""

    date = StringField('Fecha', validators=[DataRequired()],
                      render_kw={"placeholder": "DD/MM/YYYY", "type": "date"})

    operation_type = SelectField('Tipo de Operación',
                               choices=[
                                   ('Ingreso', 'Ingreso (Dinero que entra al broker)'),
                                   ('Retirada', 'Retirada (Dinero que sale del broker)'),
                                   ('Comisión', 'Comisión (Pagada al broker)'),
                                   ('Reinversión', 'Reinversión (Beneficios obtenidos)')
                               ],
                               validators=[DataRequired()])

    concept = SelectField('Concepto Específico',
                          choices=[
                              # Se llenarán dinámicamente
                          ],
                          validators=[DataRequired()])

    # NUEVO CAMPO ACCIÓN
    accion = SelectField('Acción (Opcional)', choices=[], validators=[Optional()])

    amount = StringField('Cantidad (€)', validators=[DataRequired()],
                        render_kw={"placeholder": "Ej: 1500.50"})

    description = TextAreaField('Descripción (Opcional)',
                             render_kw={"placeholder": "Detalles adicionales", "rows": 3})

    submit = SubmitField('Registrar Operación')
# ...

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



# ... (otros imports)
from flask import request # Asegúrate de que request está importado
# ...

@app.route('/broker_operations', methods=['GET', 'POST'])
@login_required
def broker_operations():
    # Instanciar el formulario.
    # Si es POST, request.form contendrá los datos enviados.
    # WTForms usará request.form para poblar los campos del formulario.
    form = BrokerOperationForm(request.form if request.method == 'POST' else None)

    # --- Poblar SIEMPRE las opciones del campo 'Acción' ---
    # Esto es necesario tanto para la visualización inicial (GET)
    # como para volver a renderizar el formulario si falla la validación en POST.
    _, csv_data_list, _ = load_user_portfolio(current_user.id)
    product_choices = [("", "- Seleccionar Acción (si aplica) -")]
    if csv_data_list and isinstance(csv_data_list, list):
        try:
            unique_products = sorted(list(set(
                movement['Producto'] for movement in csv_data_list if 'Producto' in movement and movement['Producto']
            )))
            product_choices.extend([(product, product) for product in unique_products])
        except Exception as e:
            app.logger.error(f"Error al extraer productos para el dropdown 'Acción': {e}")
    form.accion.choices = product_choices
    # --- Fin poblar 'Acción' ---

    # --- Lógica específica para solicitudes POST ---
    if request.method == 'POST':
        # ANTES de validar, debemos establecer las opciones correctas para el campo 'concept'
        # basándonos en el 'operation_type' que se envió con el formulario.
        # form.operation_type.data ya tendrá el valor enviado porque form se inicializó con request.form.
        submitted_operation_type = form.operation_type.data
        concept_choices_for_validation = []

        if submitted_operation_type == 'Ingreso':
            concept_choices_for_validation = [('Inversión', 'Inversión')]
        elif submitted_operation_type == 'Retirada':
            # "Dividendos (OBSOLETO)" ya fue eliminado del JS, así que no debería llegar aquí.
            # Si llegara, fallaría la validación porque no está en esta lista.
            concept_choices_for_validation = [('Desinversión', 'Desinversión')]
        elif submitted_operation_type == 'Comisión':
            concept_choices_for_validation = [
                ('Compra/Venta', 'Comisión de Compra/Venta'),
                ('Apalancamiento', 'Comisión de Apalancamiento'),
                ('Otras', 'Otras Comisiones')
            ]
        elif submitted_operation_type == 'Reinversión':
            concept_choices_for_validation = [('Dividendo', 'Dividendo')]
        
        form.concept.choices = concept_choices_for_validation
        # --- Fin de establecer choices para 'concept' en POST ---

    # Ahora, si es POST, form.validate_on_submit() usará las choices que acabamos de establecer.
    if form.validate_on_submit(): # Para GET, esto siempre será False.
        try:
            operation_date = datetime.strptime(form.date.data, '%Y-%m-%d').date()
            amount_str = str(form.amount.data).replace(',', '.') # Asegurar que es string antes de replace
            amount_val = float(amount_str)

            final_amount = 0.0 # Inicializar
            if form.operation_type.data == 'Ingreso':
                final_amount = -abs(amount_val)
            elif form.operation_type.data == 'Retirada':
                final_amount = abs(amount_val)
            elif form.operation_type.data == 'Comisión':
                final_amount = -abs(amount_val)
            elif form.operation_type.data == 'Reinversión':
                final_amount = abs(amount_val)

            linked_product = None
            if form.operation_type.data == 'Reinversión' and form.concept.data == 'Dividendo':
                if form.accion.data and form.accion.data != "": # Asegurarse que no es el placeholder
                    linked_product = form.accion.data
            
            new_operation = BrokerOperation(
                user_id=current_user.id,
                date=operation_date,
                operation_type=form.operation_type.data,
                concept=form.concept.data,
                amount=final_amount,
                description=form.description.data,
                linked_product_name=linked_product
            )
            db.session.add(new_operation)
            db.session.commit()
            flash('Operación registrada correctamente.', 'success')
            return redirect(url_for('broker_operations')) # Esto debería ocurrir si todo va bien
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar la operación: {e}', 'danger')
            app.logger.error(f"Error registrando operación de broker: {e}", exc_info=True)
    # Si form.validate_on_submit() es False (o si hubo una excepción antes del redirect),
    # se ejecutará el código de abajo para re-renderizar la plantilla.
    # Los errores de validación se mostrarán automáticamente por WTForms en el template.

    # --- Lógica para solicitudes GET o si la validación POST falla ---
    operations = BrokerOperation.query.filter_by(user_id=current_user.id).order_by(BrokerOperation.date.desc()).all()
    
    totals = {
        'Inversión': 0, 'Desinversión': 0, 'Compra/Venta': 0, 'Apalancamiento': 0,
        'Otras': 0, 'Dividendo': 0, 'Neto Ingresos': 0, 'Neto Retiradas': 0,
        'Neto Comisiones': 0, 'Neto Reinversiones': 0, 'Balance Neto Usuario': 0
    }
    for op in operations:
        if op.operation_type == 'Ingreso': totals['Neto Ingresos'] += op.amount
        elif op.operation_type == 'Retirada': totals['Neto Retiradas'] += op.amount
        elif op.operation_type == 'Comisión': totals['Neto Comisiones'] += op.amount
        elif op.operation_type == 'Reinversión': totals['Neto Reinversiones'] += op.amount
        if op.concept in totals: totals[op.concept] += op.amount
    totals['Balance Neto Usuario'] = totals['Neto Ingresos'] + totals['Neto Retiradas'] + totals['Neto Comisiones']

    # Para una solicitud GET inicial, el JavaScript poblará los conceptos.
    # Si es una solicitud POST que falló la validación, form.concept.choices ya
    # fueron establecidos arriba y se usarán para re-renderizar el select correctamente.
    # No es estrictamente necesario volver a setearlos aquí para GET si el JS los maneja bien al inicio.

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
    
    # Crear formulario para la edición
    form = BrokerOperationForm()
    
    if form.validate_on_submit():
        try:
            # Obtener los datos del formulario
            operation_date = datetime.strptime(form.date.data, '%Y-%m-%d').date()
            operation_type = form.operation_type.data
            concept = form.concept.data
            amount = float(form.amount.data.replace(',', '.'))
            description = form.description.data
            
            # ACTUALIZADO: Aplicar signo según tipo de operación (con nueva lógica de signos)
            if operation_type == 'Ingreso':
                amount = -abs(amount)  # Negativo (dinero que sale del usuario hacia el broker)
            elif operation_type == 'Retirada':
                amount = abs(amount)   # Positivo (dinero que entra al usuario desde el broker)
            elif operation_type == 'Comisión':
                amount = -abs(amount)  # Negativo (costo)
            elif operation_type == 'Reinversión':  # ← NUEVO
                amount = abs(amount)   # Positivo (beneficio obtenido)
            
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
    
    # Para GET, pre-llenar el formulario con los datos actuales
    if request.method == 'GET':
        form.date.data = operation.date.strftime('%Y-%m-%d')
        form.operation_type.data = operation.operation_type
        form.concept.data = operation.concept
        form.amount.data = str(abs(operation.amount))  # Mostrar siempre positivo
        form.description.data = operation.description
    
    # Renderizar template con formulario
    return render_template(
        'edit_broker_operation.html',
        form=form,
        operation=operation
    )


# ...
@app.route('/get_broker_operation/<int:operation_id>')
@login_required
def get_broker_operation(operation_id):
    """Obtiene los datos de una operación específica para el modal de edición."""
    try:
        operation = BrokerOperation.query.filter_by(id=operation_id, user_id=current_user.id).first_or_404()

        # --- INICIO: Obtener productos para el dropdown del modal ---
        _, csv_data_list, _ = load_user_portfolio(current_user.id)
        product_options_for_modal = []
        if csv_data_list and isinstance(csv_data_list, list):
            unique_products_modal = sorted(list(set(
                movement['Producto'] for movement in csv_data_list if 'Producto' in movement and movement['Producto']
            )))
            product_options_for_modal = [{'value': product, 'text': product} for product in unique_products_modal]
        # --- FIN: Obtener productos para el dropdown del modal ---

        return jsonify({
            'success': True,
            'operation': {
                'id': operation.id,
                'date': operation.date.strftime('%Y-%m-%d'),
                'operation_type': operation.operation_type,
                'concept': operation.concept,
                'amount': float(operation.amount),
                'description': operation.description or '',
                'linked_product_name': operation.linked_product_name or '' # <-- AÑADIDO
            },
            'product_options': product_options_for_modal # <-- AÑADIDO
        })
    except Exception as e:
        app.logger.error(f"Error en get_broker_operation {operation_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/edit_broker_operation_ajax/<int:operation_id>', methods=['POST'])
@login_required
def edit_broker_operation_ajax(operation_id):
    """Actualiza una operación de broker vía AJAX desde el modal."""
    try:
        operation = BrokerOperation.query.filter_by(id=operation_id, user_id=current_user.id).first()

        if not operation:
            return jsonify({'success': False, 'error': 'Operación no encontrada'}), 404

        date_str = request.form.get('date')
        operation_type = request.form.get('operation_type')
        concept = request.form.get('concept')
        amount_str = request.form.get('amount')
        description = request.form.get('description', '')
        linked_product_form = request.form.get('accion') # <-- NUEVO: Obtener 'accion' del formulario modal

        if not all([date_str, operation_type, concept, amount_str]):
            return jsonify({'success': False, 'error': 'Faltan campos requeridos'}), 400

        try:
            operation_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'error': 'Formato de fecha inválido'}), 400

        try:
            amount_val = float(amount_str.replace(',', '.'))
            if amount_val <= 0: # La cantidad siempre debe ser positiva en el form
                return jsonify({'success': False, 'error': 'La cantidad debe ser mayor que cero'}), 400
        except ValueError:
            return jsonify({'success': False, 'error': 'Formato de cantidad inválido'}), 400

        # Aplicar signo
        if operation_type == 'Ingreso': final_amount = -abs(amount_val)
        elif operation_type == 'Retirada': final_amount = abs(amount_val)
        elif operation_type == 'Comisión': final_amount = -abs(amount_val)
        elif operation_type == 'Reinversión': final_amount = abs(amount_val)
        else: return jsonify({'success': False, 'error': f'Tipo de operación inválido: {operation_type}'}), 400

        operation.date = operation_date
        operation.operation_type = operation_type
        operation.concept = concept
        operation.amount = final_amount
        operation.description = description

        # --- INICIO: Guardar linked_product_name para edición ---
        if operation_type == 'Reinversión' and concept == 'Dividendo':
            operation.linked_product_name = linked_product_form if linked_product_form and linked_product_form != "" else None
        else:
            operation.linked_product_name = None # Limpiar si no aplica
        # --- FIN: Guardar linked_product_name para edición ---

        db.session.commit()
        return jsonify({'success': True, 'message': 'Operación actualizada correctamente'})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error actualizando operación AJAX {operation_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500
# ...

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


def setup_scheduled_tasks():
    """Configura las tareas programadas."""
    try:
        with app.app_context():
            # Inicializar tareas predeterminadas si no existen
            initialize_default_scheduler_tasks()
            # Configurar scheduler con tareas dinámicas
            setup_dynamic_scheduled_tasks()
    except Exception as e:
        print(f"Error configurando tareas programadas: {e}")

def create_scheduler_task_table():
    """Crea la tabla scheduler_tasks y inicializa datos predeterminados."""
    try:
        with app.app_context():
            # Crear todas las tablas (incluida la nueva SchedulerTask)
            db.create_all()
            print("✅ Tabla scheduler_tasks creada.")
            
            # Inicializar tareas predeterminadas
            initialize_default_scheduler_tasks()
            print("✅ Tareas predeterminadas inicializadas.")
            
            # Reconfigurar scheduler
            setup_dynamic_scheduled_tasks()
            print("✅ Scheduler reconfigurado.")
            
    except Exception as e:
        print(f"❌ Error en migración: {e}")

def configure_sqlite_for_concurrency():
    """Configura SQLite para mejor manejo de concurrencia."""
    try:
        # Usar conexión directa de SQLAlchemy
        from sqlalchemy import text
        
        # WAL mode permite lecturas concurrentes con escrituras
        db.session.execute(text('PRAGMA journal_mode=WAL'))
        
        # Modo normal es más rápido y permite más concurrencia
        db.session.execute(text('PRAGMA synchronous=NORMAL'))
        
        # Cache más grande en memoria
        db.session.execute(text('PRAGMA cache_size=10000'))
        
        # Usar memoria para tablas temporales
        db.session.execute(text('PRAGMA temp_store=MEMORY'))
        
        # Timeout para operaciones bloqueadas
        db.session.execute(text('PRAGMA busy_timeout=30000'))
        
        db.session.commit()
        print("✅ SQLite configurado para mejor concurrencia")
        
        # Verificar configuración
        result = db.session.execute(text('PRAGMA journal_mode')).fetchone()
        print(f"Journal mode: {result[0]}")
        
    except Exception as e:
        print(f"❌ Error configurando SQLite: {e}")

# --- Ejecución Principal ---
if __name__ == '__main__': # MOSTRANDO COMPLETA CON CAMBIOS
    # Define el email placeholder para el admin en la config para fácil acceso
    app.config['ADMIN_PLACEHOLDER_EMAIL'] = 'admin@no-reply.internal'
    
    with app.app_context():
        print("Verificando/Creando tablas de la base de datos...")
        db.create_all()
        print("Tablas verificadas/creadas.")

        configure_sqlite_for_concurrency()
        initialize_default_scheduler_tasks()

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
    
    setup_scheduled_tasks()
    # ... (app.run) ...
    app.run(debug=False, host='0.0.0.0', port=5000)
