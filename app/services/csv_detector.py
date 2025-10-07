"""
CSV Detector - Detecta el formato de CSVs (IBKR vs DeGiro)
"""
import csv
import io


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
        # DeGiro tiene columnas específicas en el header
        degiro_columns = ['Fecha', 'Hora', 'Producto', 'ISIN', 'Descripción']
        if all(col in first_line for col in degiro_columns[:3]):
            return 'DEGIRO'
        
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
                # Leer solo las primeras 1000 líneas para detectar
                content = ''.join([f.readline() for _ in range(1000)])
                return CSVDetector.detect_format(content)
        except Exception as e:
            print(f"Error detectando formato: {e}")
            return 'UNKNOWN'
    
    @staticmethod
    def get_parser_class(format_type: str):
        """
        Obtiene la clase de parser apropiada para el formato
        
        Args:
            format_type: 'IBKR' o 'DEGIRO'
            
        Returns:
            Clase del parser apropiado
        """
        if format_type == 'IBKR':
            from app.services.parsers.ibkr_parser import IBKRParser
            return IBKRParser
        elif format_type == 'DEGIRO':
            from app.services.parsers.degiro_parser import DeGiroParser
            return DeGiroParser
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
    format_type = CSVDetector.detect_format_from_file(file_path)
    
    if format_type == 'UNKNOWN':
        raise ValueError("No se pudo detectar el formato del CSV")
    
    parser_class = CSVDetector.get_parser_class(format_type)
    parser = parser_class()
    
    return parser.parse(file_path)

