"""
Configuración de la aplicación FollowUp
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
basedir = Path(__file__).parent
load_dotenv(basedir / '.env')


class Config:
    """Configuración base"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{basedir / "instance" / "followup.db"}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')
    
    # Application
    APP_NAME = os.environ.get('APP_NAME', 'FollowUp')
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 20))
    
    # Upload folders
    UPLOAD_FOLDER = basedir / 'uploads'
    OUTPUT_FOLDER = basedir / 'output'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Allowed extensions
    ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'}


class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    TESTING = False
    
    # En producción, forzar que SECRET_KEY esté definido
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        assert os.environ.get('SECRET_KEY'), \
            'SECRET_KEY must be set in production'


class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Diccionario de configuraciones
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

