"""
Logger de depuración exhaustiva para importación CSV.
Escribe en logs/import_debug.log para revisar qué ocurrió tras cada import.
"""
import logging
import os
from pathlib import Path
from datetime import datetime


def setup_import_debug_logger():
    """
    Configura y retorna el logger de debug para importación.
    Trunca el archivo al inicio de cada sesión de import.
    """
    log_dir = Path(__file__).resolve().parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'import_debug.log'

    logger = logging.getLogger('import_debug')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-7s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.info(f"{'='*60}")
    logger.info(f"INICIO NUEVA IMPORTACIÓN CSV - {datetime.now().isoformat()}")
    logger.info(f"Log guardado en: {log_file.resolve()}")
    logger.info(f"{'='*60}")
    return logger


def get_import_debug_logger():
    """Obtiene el logger (crea uno básico si no existe)"""
    logger = logging.getLogger('import_debug')
    if not logger.handlers:
        setup_import_debug_logger()
    return logging.getLogger('import_debug')
