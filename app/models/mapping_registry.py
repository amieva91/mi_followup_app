"""
Registro de Mapeos - Sistema flexible para gestionar conversiones
Reemplaza los diccionarios hardcodeados en los mappers
"""
from app import db
from datetime import datetime


class MappingRegistry(db.Model):
    """
    Tabla de mapeos configurables (reemplaza diccionarios hardcodeados)
    
    Tipos de mapeos:
    - MIC_TO_YAHOO: MIC ISO 10383 → Yahoo Suffix (ej: XMAD → .MC)
    - EXCHANGE_TO_YAHOO: Exchange IBKR → Yahoo Suffix (ej: BM → .MC)
    - DEGIRO_TO_IBKR: Exchange DeGiro → Exchange IBKR (ej: MAD → BM)
    - MIC_TO_EXCHANGE: MIC → Exchange IBKR (ej: XMAD → BM)
    """
    __tablename__ = 'mapping_registry'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Tipo de mapeo
    mapping_type = db.Column(db.String(30), nullable=False, index=True)
    # Valores: 'MIC_TO_YAHOO', 'EXCHANGE_TO_YAHOO', 'DEGIRO_TO_IBKR', 'MIC_TO_EXCHANGE'
    
    # Clave y valor del mapeo
    source_key = db.Column(db.String(20), nullable=False, index=True)  # XMAD, BM, MAD, etc.
    target_value = db.Column(db.String(20), nullable=False)  # .MC, '', BM, etc.
    
    # Información adicional
    description = db.Column(db.String(100))  # ej: "Madrid Stock Exchange", "New York Stock Exchange"
    country = db.Column(db.String(2))  # ES, US, GB, etc. (código ISO 3166-1 alpha-2)
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Metadata
    created_by = db.Column(db.String(20), default='SYSTEM')  # 'SYSTEM', 'MANUAL', 'IMPORT'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índice compuesto para búsquedas rápidas
    __table_args__ = (
        db.Index('idx_mapping_lookup', 'mapping_type', 'source_key', 'is_active'),
        db.UniqueConstraint('mapping_type', 'source_key', name='uq_mapping_type_key'),
    )
    
    def __repr__(self):
        return f"<MappingRegistry({self.mapping_type}: {self.source_key} → {self.target_value})>"
    
    @classmethod
    def get_mapping(cls, mapping_type: str, source_key: str) -> str:
        """
        Obtiene el valor de un mapeo
        
        Args:
            mapping_type: Tipo de mapeo ('MIC_TO_YAHOO', etc.)
            source_key: Clave a buscar (ej: 'XMAD', 'BM')
            
        Returns:
            target_value o None si no existe
        """
        mapping = cls.query.filter_by(
            mapping_type=mapping_type,
            source_key=source_key.upper(),
            is_active=True
        ).first()
        
        return mapping.target_value if mapping else None
    
    @classmethod
    def get_all_mappings(cls, mapping_type: str) -> dict:
        """
        Obtiene todos los mapeos de un tipo como diccionario
        
        Args:
            mapping_type: Tipo de mapeo
            
        Returns:
            dict con source_key → target_value
        """
        mappings = cls.query.filter_by(
            mapping_type=mapping_type,
            is_active=True
        ).all()
        
        return {m.source_key: m.target_value for m in mappings}
    
    @classmethod
    def set_mapping(cls, mapping_type: str, source_key: str, target_value: str,
                   description: str = None, country: str = None, created_by: str = 'MANUAL'):
        """
        Crea o actualiza un mapeo
        
        Args:
            mapping_type: Tipo de mapeo
            source_key: Clave origen
            target_value: Valor destino
            description: Descripción opcional
            country: Código país opcional
            created_by: Origen del dato
        """
        mapping = cls.query.filter_by(
            mapping_type=mapping_type,
            source_key=source_key.upper()
        ).first()
        
        if mapping:
            # Actualizar existente
            mapping.target_value = target_value
            mapping.description = description
            mapping.country = country
            mapping.updated_at = datetime.utcnow()
        else:
            # Crear nuevo
            mapping = cls(
                mapping_type=mapping_type,
                source_key=source_key.upper(),
                target_value=target_value,
                description=description,
                country=country,
                created_by=created_by
            )
            db.session.add(mapping)
        
        db.session.commit()
        return mapping

