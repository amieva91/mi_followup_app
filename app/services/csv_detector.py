"""
CSV Detector - Detecta el formato de CSVs (IBKR vs DeGiro)
"""
import csv
import io
import logging

_import_debug = logging.getLogger('import_debug')


class CSVDetector:
    """Detecta el tipo de CSV basándose en su estructura"""
    
    @staticmethod
    def detect_format(file_content: str) -> str:
        """
        Detecta si el CSV es de IBKR, DeGiro o desconocido
        
        Args:
            file_content: Contenido del archivo CSV como string
            
        Returns:
            'IBKR', 'DEGIRO', o 'UNKNOWN'
        """
        lines = file_content.strip().split('\n')
        
        if len(lines) < 2:
            return 'UNKNOWN'
        
        # Leer primera línea
        first_line = lines[0].strip()
        
        # Detectar IBKR
        # IBKR empieza con "Statement,Header," o similar
        if first_line.startswith('Statement,'):
            return 'IBKR'
        
        # Buscar palabras clave de IBKR en las primeras líneas
        ibkr_keywords = ['BrokerName', 'Información sobre la cuenta', 'Account Information']
        for line in lines[:10]:
            if any(keyword in line for keyword in ibkr_keywords):
                return 'IBKR'
        
        # Detectar DeGiro
        # DeGiro tiene dos formatos:
        # 1. "Transacciones" - tiene columna "Número" y "ID Orden"
        # 2. "Estado de Cuenta" - tiene columna "Descripción" y "Saldo"
        
        degiro_basic_columns = ['Fecha', 'Hora', 'Producto', 'ISIN']
        
        if all(col in first_line for col in degiro_basic_columns):
            # Es DeGiro, ahora determinar qué formato
            if 'Número' in first_line and 'ID Orden' in first_line:
                return 'DEGIRO_TRANSACTIONS'  # Formato "Transacciones" (más completo)
            elif 'Descripción' in first_line and 'Saldo' in first_line:
                return 'DEGIRO_ACCOUNT'  # Formato "Estado de Cuenta"
            else:
                return 'DEGIRO'  # Formato genérico por compatibilidad
        
        # Detectar Revolut X (crypto)
        # Formato: Symbol,Type,Quantity,Price,Value,Fees,Date
        revx_columns = ['Symbol', 'Type', 'Quantity', 'Price', 'Value', 'Fees', 'Date']
        if all(col in first_line for col in revx_columns):
            return 'REVOLUT_X'
        
        return 'UNKNOWN'
    
    @staticmethod
    def detect_format_from_file(file_path: str) -> str:
        """
        Detecta el formato leyendo el archivo desde disco
        
        Args:
            file_path: Ruta al archivo CSV
            
        Returns:
            'IBKR', 'DEGIRO', o 'UNKNOWN'
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = ''.join([f.readline() for _ in range(1000)])
            fmt = CSVDetector.detect_format(content)
            _import_debug.debug(f"detect_format_from_file: primera línea ~{content[:80]}... -> {fmt}")
            return fmt
        except Exception as e:
            _import_debug.error(f"Error detectando formato: {e}")
            return 'UNKNOWN'
    
    @staticmethod
    def get_parser_class(format_type: str):
        """
        Obtiene la clase de parser apropiada para el formato
        
        Args:
            format_type: 'IBKR', 'DEGIRO_TRANSACTIONS', 'DEGIRO_ACCOUNT', o 'DEGIRO'
            
        Returns:
            Clase del parser apropiado
        """
        if format_type == 'IBKR':
            from app.services.parsers.ibkr_parser import IBKRParser
            return IBKRParser
        elif format_type == 'DEGIRO_TRANSACTIONS':
            from app.services.parsers.degiro_transactions_parser import DeGiroTransactionsParser
            return DeGiroTransactionsParser
        elif format_type in ('DEGIRO_ACCOUNT', 'DEGIRO'):
            from app.services.parsers.degiro_parser import DeGiroParser
            return DeGiroParser
        elif format_type == 'REVOLUT_X':
            from app.services.parsers.revolut_x_parser import RevolutXParser
            return RevolutXParser
        else:
            raise ValueError(f"Formato no soportado: {format_type}")


def detect_and_parse(file_path: str):
    """
    Función de conveniencia para detectar formato y parsear automáticamente

    Args:
        file_path: Ruta al archivo CSV

    Returns:
        Datos parseados en formato normalizado
    """
    try:
        _import_debug.debug(f"csv_detector: detectando formato de {file_path}")
        format_type = CSVDetector.detect_format_from_file(file_path)
        _import_debug.info(f"csv_detector: formato detectado = {format_type}")

        if format_type == 'UNKNOWN':
            _import_debug.error("csv_detector: formato UNKNOWN - no se pudo detectar")
            raise ValueError("No se pudo detectar el formato del CSV")

        parser_class = CSVDetector.get_parser_class(format_type)
        parser = parser_class()
        _import_debug.debug(f"csv_detector: usando parser {parser_class.__name__}")

        parsed_data = parser.parse(file_path)
        parsed_data['format'] = format_type
        _import_debug.debug(f"csv_detector: parse OK, claves={list(parsed_data.keys())}")
        return parsed_data
    except Exception as e:
        _import_debug.error(f"csv_detector: excepción en detect_and_parse: {e}")
        raise

