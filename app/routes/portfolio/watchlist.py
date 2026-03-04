"""
Rutas de watchlist
"""
from collections import defaultdict
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user

from app.routes import portfolio_bp
from app import db, csrf
from app.models import BrokerAccount, Asset, PortfolioHolding, Watchlist, AssetRegistry
from app.services.currency_service import convert_to_eur

@portfolio_bp.route('/watchlist')
@login_required
def watchlist():
    """
    Página principal de watchlist con tabla combinada (portfolio holdings + watchlist items)
    """
    from collections import defaultdict
    from app.models import Asset
    from app.services.watchlist_service import WatchlistService
    from app.services.watchlist_metrics_service import WatchlistMetricsService
    
    # Obtener configuración de watchlist
    config = WatchlistService.get_or_create_config(current_user.id)
    
    # ========== PARTE 1: HOLDINGS EN CARTERA ==========
    # Obtener todos los holdings individuales (igual que dashboard), solo Stock y ETF
    all_holdings = (
        PortfolioHolding.query
        .join(Asset, PortfolioHolding.asset_id == Asset.id)
        .filter(
            PortfolioHolding.user_id == current_user.id,
            PortfolioHolding.quantity > 0,
            Asset.asset_type.in_(['Stock', 'ETF'])
        )
        .all()
    )
    
    # Agrupar por asset_id (unificar)
    grouped = defaultdict(lambda: {
        'asset': None,
        'total_quantity': 0,
        'total_cost': 0,
        'accounts': [],
        'first_purchase_date': None,
        'last_transaction_date': None
    })
    
    for holding in all_holdings:
        asset_id = holding.asset_id
        group = grouped[asset_id]
        
        if group['asset'] is None:
            group['asset'] = holding.asset
        
        group['total_quantity'] += holding.quantity
        group['total_cost'] += holding.total_cost
        
        group['accounts'].append({
            'broker': holding.account.broker.name,
            'account_name': holding.account.account_name,
            'quantity': holding.quantity,
            'average_buy_price': holding.average_buy_price
        })
        
        if group['first_purchase_date'] is None or holding.first_purchase_date < group['first_purchase_date']:
            group['first_purchase_date'] = holding.first_purchase_date
        
        if group['last_transaction_date'] is None or holding.last_transaction_date > group['last_transaction_date']:
            group['last_transaction_date'] = holding.last_transaction_date
    
    # Convertir a lista y calcular valores
    holdings_unified = []
    total_value = 0
    
    for asset_id, data in grouped.items():
        data['average_buy_price'] = data['total_cost'] / data['total_quantity'] if data['total_quantity'] > 0 else 0
        data['asset_id'] = asset_id
        
        asset = data['asset']
        cost_eur = convert_to_eur(data['total_cost'], asset.currency)
        data['cost_eur'] = cost_eur
        
        if asset and asset.current_price:
            current_value_local = data['total_quantity'] * asset.current_price
            current_value_eur = convert_to_eur(current_value_local, asset.currency)
            data['current_value_eur'] = current_value_eur
            total_value += current_value_eur
        else:
            data['current_value_eur'] = cost_eur
            total_value += cost_eur
        
        holdings_unified.append(data)
    
    # Calcular peso % de cada holding
    for h in holdings_unified:
        if 'current_value_eur' in h and total_value > 0:
            h['weight_pct'] = (h['current_value_eur'] / total_value) * 100
        else:
            h['weight_pct'] = 0
    
    # ========== PARTE 2: WATCHLIST ITEMS ==========
    watchlist_items = WatchlistService.get_user_watchlist(current_user.id)
    
    # Obtener asset_ids de holdings para identificar qué assets están en cartera
    holdings_asset_ids = set([h['asset_id'] for h in holdings_unified])
    
    # Crear diccionario para acceder rápido a holdings por asset_id
    holdings_by_asset_id = {h['asset_id']: h for h in holdings_unified}
    
    # ========== PARTE 3: COMBINAR Y CALCULAR MÉTRICAS ==========
    # Preparar datos para la tabla combinada
    table_data = []
    
    # Primero: Assets en cartera
    for holding in holdings_unified:
        asset = holding['asset']
        asset_id = asset.id
        
        # Buscar si tiene item en watchlist
        watchlist_item = next((w for w in watchlist_items if w.asset_id == asset_id), None)
        
        # Si está en cartera pero no tiene watchlist_item, crear uno automáticamente
        # para que pueda editar métricas
        if not watchlist_item:
            # Usar get_watchlist_item para verificar si existe (por si acaso)
            watchlist_item = WatchlistService.get_watchlist_item(current_user.id, asset_id)
            if not watchlist_item:
                # Crear nuevo watchlist_item
                watchlist_item = Watchlist(
                    user_id=current_user.id,
                    asset_id=asset_id,
                    operativa_indicator='-'
                )
                db.session.add(watchlist_item)
                db.session.flush()
                # Añadir a la lista para evitar duplicados en la siguiente iteración
                watchlist_items.append(watchlist_item)
        
        # Actualizar métricas del watchlist item
        if watchlist_item:
            # Actualizar precio_actual desde asset si está disponible
            if asset.current_price is not None:
                watchlist_item.precio_actual = asset.current_price
            
            # Calcular métricas con cantidad invertida actual
            current_value_eur = holding.get('current_value_eur', 0)
            WatchlistMetricsService.update_all_metrics(watchlist_item, config, current_value_eur=current_value_eur)
            
            db.session.flush()  # Flush para tener datos actualizados
        
        table_data.append({
            'type': 'portfolio',
            'asset': asset,
            'asset_id': asset_id,
            'holding': holding,
            'watchlist_item': watchlist_item,
            'weight_pct': holding.get('weight_pct', 0),
            'current_value_eur': holding.get('current_value_eur', 0)
        })
    
    # Segundo: Assets solo en watchlist (no en cartera) - solo Stock y ETF
    for watchlist_item in watchlist_items:
        if watchlist_item.asset_id not in holdings_asset_ids:
            asset = watchlist_item.asset
            if not asset or asset.asset_type not in ('Stock', 'ETF'):
                continue
            
            # Actualizar precio_actual desde asset si está disponible
            if asset.current_price is not None:
                watchlist_item.precio_actual = asset.current_price
            
            # Actualizar métricas (sin cantidad invertida)
            WatchlistMetricsService.update_all_metrics(watchlist_item, config, current_value_eur=None)
            db.session.flush()
            
            table_data.append({
                'type': 'watchlist_only',
                'asset': asset,
                'asset_id': asset.id,
                'holding': None,
                'watchlist_item': watchlist_item,
                'weight_pct': None,
                'current_value_eur': None
            })
    
    # Guardar cambios en BD
    db.session.commit()
    
    # Fecha actual para comparaciones en el template
    today = date.today()
    max_date = date.max  # Capturar date.max antes de la función anidada
    
    # Ordenar por fecha próximos resultados por defecto (descendente - fechas más lejanas primero)
    # Los que no tienen fecha van al final
    def get_sort_key(item):
        watchlist_item = item.get('watchlist_item')
        if watchlist_item and watchlist_item.next_earnings_date:
            # Para orden descendente, usamos el negativo de los días desde una fecha de referencia
            # Fechas más lejanas (mayores) aparecerán primero
            return (0, watchlist_item.next_earnings_date)
        else:
            return (1, max_date)  # Sin fecha (prioridad 1, al final)
    
    # Ordenar primero, luego revertir para que las fechas más lejanas estén primero
    table_data.sort(key=get_sort_key, reverse=True)
    
    from app.models import ReportTemplate
    from app.services.gemini_service import is_gemini_available
    report_templates = ReportTemplate.query.filter_by(user_id=current_user.id).order_by(ReportTemplate.title).all()
    has_valid_templates = any(t.has_valid_description() for t in report_templates)
    gemini_available = is_gemini_available()

    return render_template(
        'portfolio/watchlist.html',
        table_data=table_data,
        config=config,
        total_value=total_value,
        max_weight_threshold=config.max_weight_threshold,
        tier_ranges=config.get_tier_ranges_dict(),
        tier_amounts=config.get_tier_amounts_dict(),
        color_thresholds=config.get_color_thresholds_dict(),
        today=today,
        report_templates=report_templates,
        has_valid_templates=has_valid_templates,
        gemini_available=gemini_available
    )


@portfolio_bp.route('/watchlist/api/config', methods=['GET'])
@login_required
def watchlist_get_config():
    """
    API: Obtener configuración de watchlist del usuario
    """
    try:
        from app.services.watchlist_service import WatchlistService
        
        config = WatchlistService.get_or_create_config(current_user.id)
        
        return jsonify({
            'success': True,
            'config': {
                'max_weight_threshold': config.max_weight_threshold,
                'tier_ranges': config.get_tier_ranges_dict(),
                'tier_amounts': config.get_tier_amounts_dict(),
                'color_thresholds': config.get_color_thresholds_dict()
            }
        })
    except Exception as e:
        import traceback
        print(f"Error en watchlist_get_config: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/watchlist/api/config', methods=['POST'])
@login_required
@csrf.exempt
def watchlist_update_config():
    """
    API: Actualizar configuración de watchlist del usuario
    """
    try:
        from app.services.watchlist_service import WatchlistService
        
        data = request.get_json()
        
        max_weight_threshold = data.get('max_weight_threshold')
        tier_ranges = data.get('tier_ranges')
        tier_amounts = data.get('tier_amounts')
        color_thresholds = data.get('color_thresholds')
        
        config = WatchlistService.update_config(
            current_user.id,
            max_weight_threshold=max_weight_threshold,
            tier_ranges=tier_ranges,
            tier_amounts=tier_amounts,
            color_thresholds=color_thresholds
        )
        
        return jsonify({
            'success': True,
            'message': 'Configuración actualizada correctamente',
            'config': {
                'max_weight_threshold': config.max_weight_threshold,
                'tier_ranges': config.get_tier_ranges_dict(),
                'tier_amounts': config.get_tier_amounts_dict(),
                'color_thresholds': config.get_color_thresholds_dict()
            }
        })
    except Exception as e:
        import traceback
        print(f"Error en watchlist_update_config: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/watchlist/add', methods=['POST'])
@login_required
@csrf.exempt
def watchlist_add():
    """
    API: Añadir asset a watchlist
    Opción 1: Desde URL Yahoo Finance (extrae info, guarda en AssetRegistry, crea Asset, añade a watchlist)
    Opción 2: Desde AssetRegistry (búsqueda por ID)
    """
    try:
        from app.services.watchlist_service import WatchlistService
        from app.services.asset_registry_service import AssetRegistryService
        from app.models import AssetRegistry
        
        data = request.get_json()
        yahoo_url = data.get('yahoo_url')
        asset_registry_id = data.get('asset_registry_id')
        asset_id = data.get('asset_id')  # Opción directa si ya tenemos el Asset
        
        # Opción 1: Desde URL Yahoo Finance
        if yahoo_url:
            service = AssetRegistryService()
            parsed = service.enricher.update_from_yahoo_url(yahoo_url)
            
            if not parsed:
                return jsonify({'success': False, 'error': 'URL de Yahoo Finance inválida'}), 400
            
            symbol = parsed['symbol']
            suffix = parsed['suffix']
            
            # Buscar o crear AssetRegistry
            # Primero buscar por symbol + suffix (yahoo_ticker)
            registry = AssetRegistry.query.filter_by(
                symbol=symbol,
                yahoo_suffix=suffix
            ).first()
            
            if not registry:
                # Necesitamos ISIN para crear AssetRegistry (campo requerido)
                # Intentar obtener desde Yahoo Finance usando yfinance
                import yfinance as yf
                ticker_str = f"{symbol}{suffix}"
                isin = None
                name = None
                currency = 'USD'
                
                try:
                    ticker = yf.Ticker(ticker_str)
                    info = ticker.info
                    if info:
                        # Intentar obtener ISIN desde info
                        isin = info.get('isin') or info.get('isinCode')
                        name = info.get('longName') or info.get('shortName') or symbol
                        currency = info.get('currency', 'USD')
                except Exception as e:
                    # Si falla, continuar sin ISIN (generaremos uno temporal)
                    pass
                
                # Si no tenemos ISIN, generar uno temporal único basado en symbol
                # Formato: TEMP-{symbol}-{suffix sin punto}
                if not isin:
                    suffix_clean = suffix.replace('.', '') if suffix else 'US'
                    isin = f"TEMP{symbol}{suffix_clean}".upper()[:12]  # ISIN tiene max 12 chars
                
                # Buscar si ya existe un registry con este ISIN temporal
                existing_registry = AssetRegistry.query.filter_by(isin=isin).first()
                if existing_registry:
                    registry = existing_registry
                else:
                    # Crear nuevo AssetRegistry
                    registry = AssetRegistry(
                        isin=isin,
                        symbol=symbol,
                        yahoo_suffix=suffix,
                        currency=currency,
                        asset_type='Stock',
                        name=name or symbol
                    )
                    db.session.add(registry)
                    db.session.flush()
                    
                    # Intentar enriquecer con Yahoo Finance para obtener datos completos
                    try:
                        service.enrich_from_yahoo_url(registry, yahoo_url, update_db=False)
                    except Exception:
                        # Si falla el enriquecimiento, continuar con datos básicos
                        pass
            
            # Buscar o crear Asset
            asset = Asset.query.filter_by(isin=registry.isin).first() if registry.isin else None
            
            if not asset:
                # Crear Asset desde AssetRegistry
                asset = service.create_asset_from_registry(registry)
            
            # Añadir a watchlist
            watchlist_item = WatchlistService.add_to_watchlist(current_user.id, asset.id)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Asset añadido a watchlist: {asset.symbol}',
                'asset_id': asset.id,
                'watchlist_id': watchlist_item.id
            })
        
        # Opción 2: Desde AssetRegistry ID
        elif asset_registry_id:
            registry = AssetRegistry.query.get(asset_registry_id)
            if not registry:
                return jsonify({'success': False, 'error': 'AssetRegistry no encontrado'}), 404
            
            if not registry.is_enriched or not registry.symbol:
                return jsonify({'success': False, 'error': 'El asset debe estar enriquecido (tener symbol)'}), 400
            
            service = AssetRegistryService()
            
            # Buscar o crear Asset
            asset = Asset.query.filter_by(isin=registry.isin).first() if registry.isin else None
            
            if not asset:
                asset = service.create_asset_from_registry(registry)
            
            # Añadir a watchlist
            watchlist_item = WatchlistService.add_to_watchlist(current_user.id, asset.id)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Asset añadido a watchlist: {asset.symbol}',
                'asset_id': asset.id,
                'watchlist_id': watchlist_item.id
            })
        
        # Opción 3: Desde Asset ID directo
        elif asset_id:
            asset = Asset.query.get(asset_id)
            if not asset:
                return jsonify({'success': False, 'error': 'Asset no encontrado'}), 404
            
            watchlist_item = WatchlistService.add_to_watchlist(current_user.id, asset_id)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Asset añadido a watchlist: {asset.symbol}',
                'asset_id': asset.id,
                'watchlist_id': watchlist_item.id
            })
        
        else:
            return jsonify({'success': False, 'error': 'Debe proporcionar yahoo_url, asset_registry_id o asset_id'}), 400
    
    except ValueError as e:
        db.session.rollback()
        import traceback
        error_msg = str(e)
        print(f"❌ ValueError en watchlist_add: {error_msg}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': error_msg}), 400
    except Exception as e:
        import traceback
        db.session.rollback()
        error_msg = str(e)
        error_trace = traceback.format_exc()
        print(f"❌ ERROR en watchlist_add: {error_msg}")
        print(error_trace)
        return jsonify({
            'success': False, 
            'error': f'{error_msg}'
        }), 500


@portfolio_bp.route('/watchlist/<int:watchlist_id>', methods=['GET'])
@login_required
def watchlist_get(watchlist_id):
    """
    API: Obtener datos de un item de watchlist
    """
    try:
        from app.models import Watchlist
        
        watchlist_item = Watchlist.query.get(watchlist_id)
        if not watchlist_item:
            return jsonify({'success': False, 'error': 'Item de watchlist no encontrado'}), 404
        
        # Verificar que pertenece al usuario actual
        if watchlist_item.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        return jsonify({
            'success': True,
            'data': {
                'id': watchlist_item.id,
                'asset_id': watchlist_item.asset_id,
                'next_earnings_date': watchlist_item.next_earnings_date.strftime('%Y-%m-%d') if watchlist_item.next_earnings_date else None,
                'per_ntm': watchlist_item.per_ntm,
                'ntm_dividend_yield': watchlist_item.ntm_dividend_yield,
                'eps': watchlist_item.eps,
                'cagr_revenue_yoy': watchlist_item.cagr_revenue_yoy
            }
        })
    
    except Exception as e:
        import traceback
        print(f"Error en watchlist_get: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/watchlist/<int:watchlist_id>/update', methods=['POST'])
@login_required
@csrf.exempt
def watchlist_update(watchlist_id):
    """
    API: Actualizar métricas manuales de un item de watchlist
    """
    try:
        from app.services.watchlist_service import WatchlistService
        
        data = request.get_json()
        
        # Debug: Log de datos recibidos
        print(f"DEBUG watchlist_update: Datos recibidos: {data}")
        
        # Filtrar solo campos permitidos y convertir a float si es necesario
        allowed_fields = ['next_earnings_date', 'per_ntm', 'ntm_dividend_yield', 'eps', 'cagr_revenue_yoy']
        update_data = {}
        for k, v in data.items():
            if k in allowed_fields:
                # Asegurar que los valores numéricos sean float (no string)
                if k != 'next_earnings_date' and v is not None:
                    try:
                        update_data[k] = float(v) if v != '' else None
                    except (ValueError, TypeError):
                        update_data[k] = None
                else:
                    update_data[k] = v
        
        # Convertir next_earnings_date de string a date si viene
        if 'next_earnings_date' in update_data and update_data['next_earnings_date']:
            if isinstance(update_data['next_earnings_date'], str):
                update_data['next_earnings_date'] = datetime.strptime(update_data['next_earnings_date'], '%Y-%m-%d').date()
        
        # Actualizar campos manuales SIN commit para poder recalcular después
        watchlist_item = WatchlistService.update_watchlist_asset(watchlist_id, update_data, commit=False)
        
        if not watchlist_item:
            return jsonify({'success': False, 'error': 'Item de watchlist no encontrado'}), 404
        
        # Verificar que pertenece al usuario actual
        if watchlist_item.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        # Obtener current_value_eur si el asset está en cartera
        current_value_eur = None
        holding = PortfolioHolding.query.filter_by(
            user_id=current_user.id,
            asset_id=watchlist_item.asset_id
        ).filter(PortfolioHolding.quantity > 0).first()
        
        if holding:
            cost_eur = convert_to_eur(holding.total_cost, holding.asset.currency)
            if holding.asset.current_price:
                current_value_local = holding.quantity * holding.asset.current_price
                current_value_eur = convert_to_eur(current_value_local, holding.asset.currency)
            else:
                current_value_eur = cost_eur
        
        # Obtener configuración para recalcular métricas
        from app.services.watchlist_service import WatchlistService
        config = WatchlistService.get_or_create_config(current_user.id)
        
        # Actualizar métricas calculadas con la nueva fórmula
        from app.services.watchlist_metrics_service import WatchlistMetricsService
        
        # Debug: Log de valores antes del cálculo
        print(f"DEBUG update_watchlist: Asset {watchlist_item.asset_id}")
        print(f"  PER recibido: {update_data.get('per_ntm')}")
        print(f"  PER guardado: {watchlist_item.per_ntm}")
        print(f"  Valoración 12m antes: {watchlist_item.valoracion_12m}")
        print(f"  Tier antes: {watchlist_item.tier}")
        print(f"  Cantidad antes: {watchlist_item.cantidad_aumentar_reducir}")
        
        WatchlistMetricsService.update_all_metrics(watchlist_item, config, current_value_eur=current_value_eur)
        
        # Debug: Log de valores después del cálculo
        print(f"  Valoración 12m después: {watchlist_item.valoracion_12m}")
        print(f"  Tier después: {watchlist_item.tier}")
        print(f"  Cantidad después: {watchlist_item.cantidad_aumentar_reducir}")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Item actualizado correctamente',
            'watchlist_id': watchlist_item.id
        })
    
    except Exception as e:
        import traceback
        db.session.rollback()
        print(f"Error en watchlist_update: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/watchlist/<int:watchlist_id>/delete', methods=['POST'])
@login_required
@csrf.exempt
def watchlist_delete(watchlist_id):
    """
    API: Eliminar asset de watchlist
    """
    try:
        from app.services.watchlist_service import WatchlistService
        from app.models import Watchlist
        
        # Verificar que el item existe y pertenece al usuario
        watchlist_item = Watchlist.query.get(watchlist_id)
        if not watchlist_item:
            return jsonify({'success': False, 'error': 'Item de watchlist no encontrado'}), 404
        
        if watchlist_item.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
        
        asset_symbol = watchlist_item.asset.symbol if watchlist_item.asset else 'N/A'
        
        success = WatchlistService.remove_from_watchlist(current_user.id, watchlist_item.asset_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Asset eliminado de watchlist: {asset_symbol}'
            })
        else:
            return jsonify({'success': False, 'error': 'No se pudo eliminar'}), 400
    
    except Exception as e:
        import traceback
        db.session.rollback()
        print(f"Error en watchlist_delete: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@portfolio_bp.route('/watchlist/update-prices', methods=['POST'])
@login_required
@csrf.exempt
def watchlist_update_prices():
    """
    API: Actualizar precios de todos los assets en watchlist
    """
    try:
        from app.services.watchlist_price_update_service import WatchlistPriceUpdateService
        
        result = WatchlistPriceUpdateService.update_prices_batch(current_user.id)
        
        # Actualizar métricas calculadas para todos los items
        from app.services.watchlist_service import WatchlistService
        from app.services.watchlist_metrics_service import WatchlistMetricsService
        
        watchlist_items = WatchlistService.get_user_watchlist(current_user.id)
        config = WatchlistService.get_or_create_config(current_user.id)
        
        # Obtener holdings para calcular current_value_eur
        from collections import defaultdict
        all_holdings = PortfolioHolding.query.filter_by(
            user_id=current_user.id
        ).filter(PortfolioHolding.quantity > 0).all()
        
        holdings_by_asset_id = {}
        for holding in all_holdings:
            if holding.asset_id not in holdings_by_asset_id:
                cost_eur = convert_to_eur(holding.total_cost, holding.asset.currency)
                if holding.asset.current_price:
                    current_value_local = holding.quantity * holding.asset.current_price
                    current_value_eur = convert_to_eur(current_value_local, holding.asset.currency)
                else:
                    current_value_eur = cost_eur
                holdings_by_asset_id[holding.asset_id] = current_value_eur
        
        for item in watchlist_items:
            current_value_eur = holdings_by_asset_id.get(item.asset_id)
            WatchlistMetricsService.update_all_metrics(item, config, current_value_eur=current_value_eur)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Precios actualizados: {result["success"]} éxitos, {result["failed"]} fallos',
            'result': result
        })
    
    except Exception as e:
        import traceback
        db.session.rollback()
        print(f"Error en watchlist_update_prices: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500