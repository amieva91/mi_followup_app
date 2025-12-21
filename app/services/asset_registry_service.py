"""
Servicio de AssetRegistry - Gestión de cache global de assets
"""
from typing import Dict, List, Optional, Tuple
from app import db
from app.models import Asset, AssetRegistry
from app.services.market_data import AssetEnricher
from app.services.market_data.mappers import ExchangeMapper, YahooSuffixMapper


class AssetRegistryService:
    """
    Servicio para gestionar la tabla global AssetRegistry
    Cache compartida entre todos los usuarios
    """
    
    def __init__(self):
        self.enricher = AssetEnricher()
    
    def get_or_create_from_isin(
        self,
        isin: str,
        currency: str,
        name: str = None,
        symbol: str = None,
        exchange: str = None,
        mic: str = None,
        degiro_exchange: str = None,
        asset_type: str = 'Stock'
    ) -> AssetRegistry:
        """
        Obtiene o crea un registro en AssetRegistry desde ISIN
        Si existe, incrementa usage_count
        Si no existe, lo crea con los datos disponibles
        
        Returns:
            AssetRegistry instance
        """
        # Buscar en cache
        registry = AssetRegistry.query.filter_by(isin=isin).first()
        
        if registry:
            # Existe - actualizar campos si vienen nuevos datos más completos
            registry.usage_count += 1
            
            # Actualizar symbol si viene y no existía (IBKR aporta esto)
            if symbol and not registry.symbol:
                registry.symbol = symbol
                registry.mark_as_enriched('CSV_IMPORT')
            
            # Actualizar exchange si viene y no existía (IBKR aporta esto)
            if exchange and not registry.ibkr_exchange:
                registry.ibkr_exchange = exchange
            
            # Actualizar name si viene uno más largo/completo
            if name and (not registry.name or len(name) > len(registry.name)):
                registry.name = name
            
            # Actualizar MIC si viene
            if mic and not registry.mic:
                registry.mic = mic
                if not registry.yahoo_suffix:
                    registry.yahoo_suffix = YahooSuffixMapper.mic_to_yahoo_suffix(mic)
            
            return registry
        
        # No existe - crear nuevo registro
        registry = AssetRegistry(
            isin=isin,
            symbol=symbol or None,
            currency=currency,
            name=name,
            mic=mic,
            degiro_exchange=degiro_exchange,
            ibkr_exchange=exchange,  # IBKR ya trae el exchange unificado
            asset_type=asset_type,
            is_enriched=bool(symbol)  # Si tiene symbol, ya está enriquecido (IBKR)
        )
        
        # Si vino con symbol (IBKR), marcar como enriquecido
        if symbol:
            registry.mark_as_enriched('CSV_IMPORT')
        
        # Generar ibkr_exchange desde mapper si solo tenemos degiro_exchange
        if not registry.ibkr_exchange and degiro_exchange:
            registry.ibkr_exchange = ExchangeMapper.degiro_to_unified(degiro_exchange)
        
        # Generar yahoo_suffix con PRIORIDAD: MIC > ibkr_exchange
        self._set_yahoo_suffix(registry, mic, exchange)
        
        db.session.add(registry)
        db.session.flush()
        
        return registry
    
    def _set_yahoo_suffix(self, registry: AssetRegistry, mic: str = None, exchange: str = None):
        """
        Establece yahoo_suffix con prioridad: MIC > ibkr_exchange
        MIC es más confiable por ser estándar internacional ISO 10383
        
        Si MIC no tiene mapeo (retorna ''), se usa exchange como fallback.
        """
        # PRIORIDAD 1: Usar MIC (más confiable)
        if mic:
            suffix = YahooSuffixMapper.mic_to_yahoo_suffix(mic)
            # Solo usar MIC si tiene un valor válido (no None y no vacío)
            if suffix is not None and suffix != '':
                registry.yahoo_suffix = suffix
                registry.mic = mic
                return
        
        # PRIORIDAD 2: Usar ibkr_exchange (fallback)
        # Se ejecuta si MIC no tiene mapeo o si no hay MIC
        if not registry.yahoo_suffix and (exchange or registry.ibkr_exchange):
            target_exchange = exchange or registry.ibkr_exchange
            suffix = YahooSuffixMapper.exchange_to_yahoo_suffix(target_exchange)
            if suffix is not None:
                registry.yahoo_suffix = suffix
    
    def create_asset_from_registry(self, registry: AssetRegistry, user_id: int = None) -> Asset:
        """
        Crea un Asset local desde AssetRegistry
        Los Assets son específicos por usuario (por si quieren personalizar nombres)
        pero apuntan al registro global
        """
        asset = Asset(
            symbol=registry.symbol,
            isin=registry.isin,
            name=registry.name,
            asset_type=registry.asset_type,
            currency=registry.currency,
            country=registry.country,
            exchange=registry.ibkr_exchange,
            mic=registry.mic,
            yahoo_suffix=registry.yahoo_suffix
        )
        
        db.session.add(asset)
        db.session.flush()
        
        return asset
    
    def get_assets_needing_enrichment(self, isins: List[str]) -> List[AssetRegistry]:
        """
        Identifica qué assets de la lista necesitan enriquecimiento
        
        Args:
            isins: Lista de ISINs a verificar
            
        Returns:
            Lista de AssetRegistry que necesitan enriquecimiento (sin symbol o ibkr_exchange)
        """
        registries = AssetRegistry.query.filter(
            AssetRegistry.isin.in_(isins),
            db.or_(
                AssetRegistry.symbol.is_(None),
                AssetRegistry.ibkr_exchange.is_(None)
            )
        ).all()
        
        return registries
    
    def enrich_from_openfigi(
        self,
        registry: AssetRegistry,
        update_db: bool = True
    ) -> Tuple[bool, str]:
        """
        Enriquece un AssetRegistry usando OpenFIGI
        
        Args:
            registry: Instancia de AssetRegistry
            update_db: Si True, guarda cambios en BD
            
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            enriched_data = self.enricher.enrich_from_isin(
                isin=registry.isin,
                currency=registry.currency,
                degiro_exchange=registry.degiro_exchange,
                degiro_mic=registry.mic
            )
            
            if not enriched_data or not enriched_data.get('symbol'):
                return False, "OpenFIGI no devolvió symbol"
            
            # Actualizar symbol si viene
            if enriched_data.get('symbol'):
                registry.symbol = enriched_data['symbol']
            
            # Actualizar name si viene y es mejor que el actual
            if enriched_data.get('name'):
                if not registry.name or len(enriched_data['name']) > len(registry.name or ''):
                    registry.name = enriched_data['name']
            
            # Actualizar asset_type
            registry.asset_type = enriched_data.get('asset_type', registry.asset_type)
            
            # MIC: Actualizar si OpenFIGI lo proporciona y es válido
            openfigi_mic = enriched_data.get('mic')
            if openfigi_mic and openfigi_mic != 'N/A' and openfigi_mic.strip():
                registry.mic = openfigi_mic
                print(f"   ✅ MIC obtenido: {openfigi_mic}")
            
            # ibkr_exchange: Actualizar si OpenFIGI lo proporciona
            if enriched_data.get('exchange'):
                registry.ibkr_exchange = enriched_data['exchange']
            elif not registry.ibkr_exchange and registry.degiro_exchange:
                registry.ibkr_exchange = ExchangeMapper.degiro_to_unified(registry.degiro_exchange)
            
            # yahoo_suffix: Recalcular con prioridad MIC > exchange
            self._set_yahoo_suffix(registry, registry.mic, registry.ibkr_exchange)
            
            # Marcar como enriquecido si ahora tiene symbol
            if registry.symbol:
                registry.mark_as_enriched('OPENFIGI')
            
            if update_db:
                db.session.commit()
            
            return True, f"✅ {registry.symbol}"
        
        except Exception as e:
            return False, f"❌ Error: {str(e)[:50]}"
    
    def enrich_from_yahoo_url(
        self,
        registry: AssetRegistry,
        yahoo_url: str,
        update_db: bool = True
    ) -> Tuple[bool, str]:
        """
        Enriquece un AssetRegistry desde URL de Yahoo Finance
        
        Args:
            registry: Instancia de AssetRegistry
            yahoo_url: URL de Yahoo Finance
            update_db: Si True, guarda cambios en BD
            
        Returns:
            Tuple (success: bool, message: str)
        """
        try:
            parsed = self.enricher.update_from_yahoo_url(yahoo_url)
            
            if not parsed:
                return False, "URL inválida"
            
            registry.symbol = parsed['symbol']
            registry.yahoo_suffix = parsed['suffix']
            
            # Intentar derivar ibkr_exchange desde MIC si no lo tenemos
            if not registry.ibkr_exchange and registry.degiro_exchange:
                registry.ibkr_exchange = ExchangeMapper.degiro_to_unified(registry.degiro_exchange)
            
            registry.mark_as_enriched('YAHOO_URL')
            
            if update_db:
                db.session.commit()
            
            return True, f"✅ {registry.yahoo_ticker}"
        
        except Exception as e:
            return False, f"❌ Error: {str(e)[:50]}"
    
    def sync_asset_from_registry(self, asset: Asset, registry: AssetRegistry):
        """
        Sincroniza un Asset local con su AssetRegistry
        Útil después de enriquecer el registro
        """
        asset.symbol = registry.symbol
        asset.name = registry.name
        asset.asset_type = registry.asset_type
        asset.currency = registry.currency
        asset.country = registry.country
        asset.exchange = registry.ibkr_exchange
        asset.mic = registry.mic
        asset.yahoo_suffix = registry.yahoo_suffix
    
    def get_enrichment_stats(self) -> Dict:
        """
        Obtiene estadísticas del registro
        """
        total = AssetRegistry.query.count()
        enriched = AssetRegistry.query.filter_by(is_enriched=True).count()
        
        return {
            'total': total,
            'enriched': enriched,
            'pending': total - enriched,
            'percentage': (enriched / total * 100) if total > 0 else 0
        }

