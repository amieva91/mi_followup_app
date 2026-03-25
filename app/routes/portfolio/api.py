"""
Rutas API: evolution, benchmarks
"""
from flask import request, jsonify
from flask_login import login_required, current_user

from app.routes import portfolio_bp


@portfolio_bp.route('/api/evolution')
@login_required
def api_evolution():
    """API de evolución del portfolio para Chart.js"""
    from app.services.portfolio_evolution_cache import PortfolioEvolutionCacheService

    frequency = request.args.get('frequency', 'weekly')
    if frequency not in ['daily', 'weekly', 'monthly']:
        frequency = 'weekly'

    try:
        data = PortfolioEvolutionCacheService.get_state(current_user.id, frequency=frequency)
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"Error en api_evolution: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@portfolio_bp.route('/api/benchmarks')
@login_required
def api_benchmarks():
    """API de comparación con benchmarks"""
    from app.services.portfolio_benchmarks_cache import PortfolioBenchmarksCacheService

    try:
        data = PortfolioBenchmarksCacheService.get_comparison_state(current_user.id)
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"Error en api_benchmarks: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
