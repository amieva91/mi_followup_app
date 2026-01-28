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
        
        Fórmula: Cantidad_aumentar_reducir = Cantidad_del_Tier - Cantidad_invertida_actual
        
        Interpretación:
        - Positivo: Necesitas comprar más (INCREASE) - tienes menos que el Tier
        - Negativo: Necesitas reducir (REDUCE) - tienes más que el Tier
        
        Args:
            current_value_eur: Cantidad invertida actual (EUR)
            tier_amount: Cantidad del Tier objetivo (EUR)
        
        Returns:
            Diferencia en EUR (positivo = comprar, negativo = vender) o None si faltan datos
        """
        if current_value_eur is None or tier_amount is None:
            return None
        
        cantidad_aumentar_reducir = tier_amount - current_value_eur
        
        return cantidad_aumentar_reducir
    
    @staticmethod
    def calculate_operativa_indicator(cantidad_aumentar_reducir: Optional[float], tier_amount: Optional[float]) -> str:
        """
        Calcula indicador de operativa basado en cantidad a aumentar/reducir respecto al Tier
        
        Indicador basado en Tier (no en reglas globales):
        - HOLD: si |cantidad_aumentar_reducir| <= Tier_amount * 0.25 (dentro del margen ±25%)
        - INCREASE: si cantidad_aumentar_reducir > Tier_amount * 0.25 (positivo, necesitas comprar más)
        - REDUCE: si cantidad_aumentar_reducir < -(Tier_amount * 0.25) (negativo, necesitas vender/reducir)
        
        Args:
            cantidad_aumentar_reducir: Diferencia vs Tier (EUR) - Positivo = comprar, Negativo = vender
            tier_amount: Cantidad del Tier objetivo (EUR)
        
        Returns:
            'INCREASE', 'REDUCE', 'HOLD', o '-' (si faltan datos)
        """
        if cantidad_aumentar_reducir is None or tier_amount is None:
            return '-'
        
        if tier_amount <= 0:
            return '-'
        
        margen = tier_amount * 0.25  # 25% del Tier
        
        if abs(cantidad_aumentar_reducir) <= margen:
            return 'HOLD'
        elif cantidad_aumentar_reducir > margen:
            # Positivo: tienes menos que el Tier, necesitas comprar
            return 'INCREASE'
        else:  # cantidad_aumentar_reducir < -margen
            # Negativo: tienes más que el Tier, necesitas vender
            return 'REDUCE'

    @staticmethod
    def _evaluate_rule_condition(metric_value: Optional[float], rule_config: Optional[Dict[str, Any]]) -> Optional[bool]:
        """
        Evalúa una condición simple (operador + valor) sobre una métrica.
        
        Returns:
            True / False si la regla está definida, None si no hay regla que evaluar.
        """
        if not rule_config:
            return None
        
        op = rule_config.get("op")
        value = rule_config.get("value")
        
        if op is None or value is None:
            return None
        
        if metric_value is None:
            # Si no hay dato de métrica, la condición no se puede cumplir
            return False
        
        if op == "=":
            return metric_value == value
        if op == ">":
            return metric_value > value
        if op == "<":
            return metric_value < value
        if op == ">=":
            return metric_value >= value
        if op == "<=":
            return metric_value <= value
        
        # Operador desconocido: considerar que no se cumple
        return False

    @staticmethod
    def calculate_operativa_global(
        watchlist_item: Watchlist,
        operativa_rules: Optional[Dict[str, Any]],
        has_position: bool
    ) -> Optional[str]:
        """
        Calcula indicador de operativa global (BUY/SELL) basado en reglas configurables.
        
        - BUY: señal fuerte de compra (solo para assets en seguimiento sin posición en cartera)
        - SELL: señal fuerte de venta (solo para assets con posición en cartera)
        
        Las reglas se definen en WatchlistConfig.color_thresholds["operativa_rules"] con esta estructura:
        
        {
            "buy": {
                "valoracion_12m": {"op": ">", "value": -12.5},
                "rentabilidad_anual": {"op": ">=", "value": 60.0},
                "combiner": "AND"  # o "OR"
            },
            "sell": {
                "valoracion_12m": {...},
                "rentabilidad_anual": {...},
                "combiner": "AND" | "OR"
            }
        }
        """
        if not operativa_rules:
            return None
        
        valoracion_12m = watchlist_item.valoracion_12m
        rent_anual = watchlist_item.rentabilidad_anual
        
        def eval_rule(rule_key: str) -> Optional[bool]:
            cfg = operativa_rules.get(rule_key) or {}
            val_cfg = cfg.get("valoracion_12m")
            rent_cfg = cfg.get("rentabilidad_anual")
            combiner = (cfg.get("combiner") or "AND").upper()
            
            val_res = WatchlistMetricsService._evaluate_rule_condition(valoracion_12m, val_cfg)
            rent_res = WatchlistMetricsService._evaluate_rule_condition(rent_anual, rent_cfg)
            
            # Si ninguna condición está definida, no hay regla que evaluar
            if val_res is None and rent_res is None:
                return None
            
            # Si solo hay una condición definida, usarla directamente
            if val_res is None:
                return rent_res
            if rent_res is None:
                return val_res
            
            if combiner == "OR":
                return bool(val_res or rent_res)
            # Por defecto AND
            return bool(val_res and rent_res)
        
        # BUY solo para assets SIN posición (watchlist)
        if not has_position:
            buy_match = eval_rule("buy")
            if buy_match:
                return "BUY"
        
        # SELL solo para assets CON posición (cartera)
        if has_position:
            sell_match = eval_rule("sell")
            if sell_match:
                return "SELL"
        
        return None
    
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
        
        # 4. Si hay Tier y cantidad invertida, calcular cantidad a aumentar/reducir e indicador basado en Tier
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
                
                # Indicador basado en Tier: INCREASE / HOLD / REDUCE
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
        
        # 5. Calcular Rentabilidad a 5 años
        rentabilidad_5yr = WatchlistMetricsService.calculate_rentabilidad_5yr(
            target_price_5yr,
            watchlist_item.precio_actual,
            watchlist_item.ntm_dividend_yield
        )
        watchlist_item.rentabilidad_5yr = rentabilidad_5yr
        
        # 6. Calcular Rentabilidad Anual
        rentabilidad_anual = WatchlistMetricsService.calculate_rentabilidad_anual(
            target_price_5yr,
            watchlist_item.precio_actual,
            watchlist_item.ntm_dividend_yield
        )
        watchlist_item.rentabilidad_anual = rentabilidad_anual
        
        # 7. Aplicar reglas globales de BUY/SELL (prevalecen sobre INCREASE/HOLD/REDUCE)
        color_thresholds = config.get_color_thresholds_dict()
        operativa_rules = color_thresholds.get("operativa_rules", {}) if isinstance(color_thresholds, dict) else {}
        has_position = current_value_eur is not None and current_value_eur > 0
        
        global_indicator = WatchlistMetricsService.calculate_operativa_global(
            watchlist_item,
            operativa_rules,
            has_position=has_position
        )
        
        if global_indicator:
            # BUY / SELL global prevalecen sobre INCREASE/HOLD/REDUCE
            watchlist_item.operativa_indicator = global_indicator
        else:
            # Si antes había un BUY global en un asset sin posición y ahora ya no se cumplen
            # las reglas, devolver a estado neutro '-'
            if not has_position:
                watchlist_item.operativa_indicator = '-'
        
        return watchlist_item

