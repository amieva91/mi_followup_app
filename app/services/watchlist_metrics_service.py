"""
Watchlist Metrics Service - Cálculos de métricas para watchlist
"""
from typing import Optional, Dict, Any
from app.models import Watchlist, WatchlistConfig
import math


class WatchlistMetricsService:
    """
    Servicio para calcular métricas de watchlist (Target Price, Valoración, Rentabilidades, Tier, etc.)
    """
    
    @staticmethod
    def calculate_target_price_5yr(eps: Optional[float], cagr: Optional[float], per: Optional[float]) -> Optional[float]:
        """
        Calcula Target Price a 5 años
        
        Fórmula: Target Price = (EPS * (1 + CAGR Revenue YoY%)^5) * PER
        
        Args:
            eps: Earnings Per Share
            cagr: CAGR Revenue YoY (%)
            per: PER o NTM P/E
        
        Returns:
            Target Price calculado o None si faltan datos
        """
        if eps is None or cagr is None or per is None:
            return None
        
        if eps <= 0 or per <= 0:
            return None
        
        # CAGR en decimal (ej: 20% = 0.20)
        cagr_decimal = cagr / 100.0
        
        # Calcular: EPS * (1 + CAGR)^5 * PER
        target_price = eps * ((1 + cagr_decimal) ** 5) * per
        
        return target_price
    
    @staticmethod
    def calculate_valoracion_12m(per: Optional[float], dividend_yield: Optional[float], cagr: Optional[float]) -> Optional[float]:
        """
        Calcula Valoración actual 12 meses (%)
        
        Fórmula PEGY Ratio: Valoración actual = ((PER / (CAGR% + Dividend Yield%)) - 1) * 100
        Luego se invierte el signo: resultado_final = -valoracion_calculada
        
        Esto permite que:
        - Resultado negativo de la fórmula (infravalorado = bueno) → se muestra positivo (verde)
        - Resultado positivo de la fórmula (sobrevalorado = malo) → se muestra negativo (rojo)
        
        Args:
            per: PER o NTM P/E
            dividend_yield: NTM Dividend Yield (%) - Se suma al denominador: (CAGR + Dividend Yield)
            cagr: CAGR Revenue YoY (%)
        
        Returns:
            Valoración actual 12 meses (%) con signo invertido, redondeada a 2 decimales, o None si faltan datos
        """
        if per is None or cagr is None:
            return None
        
        if per <= 0:
            return None
        
        # Dividend Yield puede ser None o 0, en ese caso se trata como 0
        if dividend_yield is None:
            dividend_yield = 0.0
        
        # Denominador: CAGR + Dividend Yield (Rendimiento Total)
        denominator = cagr + dividend_yield
        
        if denominator == 0:
            return None
        
        # Calcular: (PEGY - 1) * 100 donde PEGY = PER / (Crecimiento + Dividend Yield)
        # PEGY = PER / (CAGR% + Dividend Yield%)
        pegy = per / denominator
        
        # Desviación = (PEGY - 1) * 100
        valoracion_calculada = (pegy - 1) * 100
        
        # Invertir el signo para la interpretación visual
        # Si es negativo (infravalorado = bueno) → positivo (verde)
        # Si es positivo (sobrevalorado = malo) → negativo (rojo)
        valoracion = -valoracion_calculada
        
        # Redondear a 2 decimales para evitar problemas de precisión de punto flotante
        # Esto asegura que valores como 19.999999... se conviertan en 20.00
        valoracion = round(valoracion, 2)
        
        return valoracion
    
    @staticmethod
    def calculate_rentabilidad_5yr(target_price: Optional[float], current_price: Optional[float], 
                                   dividend_yield: Optional[float]) -> Optional[float]:
        """
        Calcula Rentabilidad a 5 años (%)
        
        Basada en Target Price (5 yr) calculado + NTM Dividend Yield (dividendo constante anual)
        
        Args:
            target_price: Target Price a 5 años
            current_price: Precio actual
            dividend_yield: NTM Dividend Yield (%)
        
        Returns:
            Rentabilidad a 5 años (%) o None si faltan datos
        """
        if target_price is None or current_price is None:
            return None
        
        if current_price <= 0:
            return None
        
        # Dividend yield en decimal
        div_yield_decimal = (dividend_yield / 100.0) if dividend_yield else 0.0
        
        # Ganancia de capital en 5 años
        capital_gain = target_price - current_price
        capital_gain_pct = (capital_gain / current_price) * 100
        
        # Dividendos acumulados en 5 años (dividendo constante anual)
        total_dividends_pct = div_yield_decimal * 5 * 100  # 5 años * dividend yield anual
        
        # Rentabilidad total a 5 años
        rentabilidad_5yr = capital_gain_pct + total_dividends_pct
        
        return rentabilidad_5yr
    
    @staticmethod
    def calculate_rentabilidad_anual(target_price: Optional[float], current_price: Optional[float],
                                     dividend_yield: Optional[float]) -> Optional[float]:
        """
        Calcula Rentabilidad Anual (%)
        
        Basada en Target Price (5 yr) calculado + NTM Dividend Yield
        
        Args:
            target_price: Target Price a 5 años
            current_price: Precio actual
            dividend_yield: NTM Dividend Yield (%)
        
        Returns:
            Rentabilidad anual (%) o None si faltan datos
        """
        if target_price is None or current_price is None:
            return None
        
        if current_price <= 0:
            return None
        
        # Dividend yield en decimal
        div_yield_decimal = (dividend_yield / 100.0) if dividend_yield else 0.0
        
        # Ganancia de capital anualizada (5 años)
        capital_gain = target_price - current_price
        if capital_gain > 0:
            # Rentabilidad anualizada: ((precio_final / precio_inicial)^(1/años)) - 1
            annual_capital_gain_pct = (((target_price / current_price) ** (1.0 / 5.0)) - 1.0) * 100
        else:
            annual_capital_gain_pct = (capital_gain / current_price) / 5.0 * 100  # Pérdida anualizada
        
        # Rentabilidad anual = ganancia capital anualizada + dividend yield anual
        rentabilidad_anual = annual_capital_gain_pct + div_yield_decimal * 100
        
        return rentabilidad_anual
    
    @staticmethod
    def calculate_tier(valoracion_12m: Optional[float], tier_ranges_config: Dict) -> Optional[int]:
        """
        Calcula Tier (1-5) basado en Valoración actual 12 meses (%)
        
        Args:
            valoracion_12m: Valoración actual 12 meses (%)
            tier_ranges_config: Diccionario con rangos de Tier (del WatchlistConfig)
                Ejemplo: {"tier_5": {"min": 50.0}, "tier_4": {"min": 30.0, "max": 50.0}, ...}
        
        Returns:
            Tier (1-5) o None si no se puede determinar
        """
        if valoracion_12m is None:
            return None
        
        # Probar desde Tier 5 (mayor) hasta Tier 1 (menor)
        for tier_num in [5, 4, 3, 2, 1]:
            tier_key = f"tier_{tier_num}"
            if tier_key not in tier_ranges_config:
                continue
            
            tier_range = tier_ranges_config[tier_key]
            min_val = tier_range.get("min")
            max_val = tier_range.get("max")
            
            # Verificar si valoración está dentro del rango
            matches = True
            
            # Si hay min y max, verificar que el rango sea válido (max >= min)
            if min_val is not None and max_val is not None:
                if max_val < min_val:
                    # Rango inválido (max < min), saltar este tier
                    continue
            
            # Verificar si valoración está dentro del rango
            # Para Tier con min: valoracion >= min
            if min_val is not None and valoracion_12m < min_val:
                matches = False
            # Para Tier con max: valoracion < max (estricto, no <=)
            if max_val is not None and valoracion_12m >= max_val:
                matches = False
            
            if matches:
                return tier_num
        
        return None  # No coincide con ningún rango
    
    @staticmethod
    def calculate_cantidad_aumentar_reducir(current_value_eur: Optional[float], tier_amount: Optional[float]) -> Optional[float]:
        """
        Calcula cantidad a aumentar/reducir (EUR)
        
        Fórmula: Cantidad_aumentar_reducir = Cantidad_invertida_actual - Cantidad_del_Tier
        
        Args:
            current_value_eur: Cantidad invertida actual (EUR)
            tier_amount: Cantidad del Tier (EUR)
        
        Returns:
            Diferencia en EUR (negativo = vender, positivo = comprar) o None si faltan datos
        """
        if current_value_eur is None or tier_amount is None:
            return None
        
        cantidad_aumentar_reducir = current_value_eur - tier_amount
        
        return cantidad_aumentar_reducir
    
    @staticmethod
    def calculate_operativa_indicator(cantidad_aumentar_reducir: Optional[float], tier_amount: Optional[float]) -> str:
        """
        Calcula indicador de operativa (BUY/SELL/HOLD) basado en cantidad a aumentar/reducir
        
        Lógica:
        - HOLD: si |cantidad_aumentar_reducir| <= Tier_amount * 0.25 (dentro del margen ±25%)
        - BUY: si cantidad_aumentar_reducir > Tier_amount * 0.25 (positivo, por debajo del Tier)
        - SELL: si cantidad_aumentar_reducir < -(Tier_amount * 0.25) (negativo, por encima del Tier)
        
        Args:
            cantidad_aumentar_reducir: Diferencia vs Tier (EUR)
            tier_amount: Cantidad del Tier (EUR)
        
        Returns:
            'BUY', 'SELL', 'HOLD', o '-' (si faltan datos)
        """
        if cantidad_aumentar_reducir is None or tier_amount is None:
            return '-'
        
        if tier_amount <= 0:
            return '-'
        
        margen = tier_amount * 0.25  # 25% del Tier
        
        if abs(cantidad_aumentar_reducir) <= margen:
            return 'HOLD'
        elif cantidad_aumentar_reducir > margen:
            return 'BUY'
        else:  # cantidad_aumentar_reducir < -margen
            return 'SELL'
    
    @staticmethod
    def calculate_tier_color(current_value_eur: Optional[float], tier_amount: Optional[float]) -> Optional[str]:
        """
        Calcula color del Tier (verde/amarillo/rojo) basado en cantidad invertida vs Tier
        
        Lógica:
        - Verde: dentro del rango del Tier (±25%)
        - Amarillo: fuera del rango por más del 25% pero menos del 50%
        - Rojo: fuera del rango por más del 50%
        
        Args:
            current_value_eur: Cantidad invertida actual (EUR)
            tier_amount: Cantidad del Tier (EUR)
        
        Returns:
            'green', 'yellow', 'red', o None si faltan datos
        """
        if current_value_eur is None or tier_amount is None:
            return None
        
        if tier_amount <= 0:
            return None
        
        # Calcular desviación porcentual
        desviacion = abs(current_value_eur - tier_amount)
        desviacion_pct = (desviacion / tier_amount) * 100
        
        if desviacion_pct <= 25.0:
            return 'green'
        elif desviacion_pct <= 50.0:
            return 'yellow'
        else:
            return 'red'
    
    @staticmethod
    def update_all_metrics(watchlist_item: Watchlist, config: Optional[WatchlistConfig] = None, current_value_eur: Optional[float] = None) -> Watchlist:
        """
        Actualiza todas las métricas calculadas de un item de watchlist
        
        Args:
            watchlist_item: Item de watchlist a actualizar
            config: Configuración del usuario (opcional, se obtiene si no se proporciona)
            current_value_eur: Valor actual invertido en EUR (opcional, para assets en cartera)
        
        Returns:
            Watchlist item actualizado
        """
        from app.services.watchlist_service import WatchlistService
        
        # Obtener configuración si no se proporciona
        if config is None:
            config = WatchlistService.get_or_create_config(watchlist_item.user_id)
        
        # 1. Calcular Target Price (5 yr)
        target_price_5yr = WatchlistMetricsService.calculate_target_price_5yr(
            watchlist_item.eps,
            watchlist_item.cagr_revenue_yoy,
            watchlist_item.per_ntm
        )
        watchlist_item.target_price_5yr = target_price_5yr
        
        # 2. Calcular Valoración actual 12 meses (%)
        # Fórmula PEGY: -((PER / (CAGR% + Dividend Yield%)) - 1) * 100
        valoracion_12m = WatchlistMetricsService.calculate_valoracion_12m(
            watchlist_item.per_ntm,
            watchlist_item.ntm_dividend_yield,  # Se suma al denominador: (CAGR + Dividend Yield)
            watchlist_item.cagr_revenue_yoy
        )
        watchlist_item.valoracion_12m = valoracion_12m
        
        # 3. Calcular Tier
        tier_ranges = config.get_tier_ranges_dict()
        tier = WatchlistMetricsService.calculate_tier(valoracion_12m, tier_ranges)
        
        # Debug: Log para verificar asignación de Tier
        if valoracion_12m is not None and abs(valoracion_12m - 20.0) < 1.0:
            print(f"DEBUG Tier: Asset {watchlist_item.asset_id}, Valoración={valoracion_12m:.6f}%, Tier asignado={tier}, Rangos={tier_ranges}")
        
        watchlist_item.tier = tier
        
        # 4. Si hay Tier y cantidad invertida, calcular cantidad a aumentar/reducir
        if tier is not None and current_value_eur is not None:
            tier_amounts = config.get_tier_amounts_dict()
            tier_key = f"tier_{tier}"
            tier_amount = tier_amounts.get(tier_key)
            
            if tier_amount is not None:
                cantidad_aumentar_reducir = WatchlistMetricsService.calculate_cantidad_aumentar_reducir(
                    current_value_eur,
                    tier_amount
                )
                watchlist_item.cantidad_aumentar_reducir = cantidad_aumentar_reducir
                
                # 5. Calcular indicador de operativa
                operativa_indicator = WatchlistMetricsService.calculate_operativa_indicator(
                    cantidad_aumentar_reducir,
                    tier_amount
                )
                watchlist_item.operativa_indicator = operativa_indicator
        else:
            # Si no hay cantidad invertida (asset solo en watchlist), mantener operativa_indicator en '-'
            if watchlist_item.operativa_indicator is None:
                watchlist_item.operativa_indicator = '-'
            watchlist_item.cantidad_aumentar_reducir = None
        
        # 6. Calcular Rentabilidad a 5 años
        rentabilidad_5yr = WatchlistMetricsService.calculate_rentabilidad_5yr(
            target_price_5yr,
            watchlist_item.precio_actual,
            watchlist_item.ntm_dividend_yield
        )
        watchlist_item.rentabilidad_5yr = rentabilidad_5yr
        
        # 7. Calcular Rentabilidad Anual
        rentabilidad_anual = WatchlistMetricsService.calculate_rentabilidad_anual(
            target_price_5yr,
            watchlist_item.precio_actual,
            watchlist_item.ntm_dividend_yield
        )
        watchlist_item.rentabilidad_anual = rentabilidad_anual
        
        return watchlist_item

