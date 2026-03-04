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
    from app.services.metrics.portfolio_evolution import PortfolioEvolutionService

    frequency = request.args.get('frequency', 'weekly')
    if frequency not in ['daily', 'weekly', 'monthly']:
        frequency = 'weekly'

    try:
        evolution_service = PortfolioEvolutionService(current_user.id)
        data = evolution_service.get_evolution_data(frequency=frequency)
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
    from app.services.metrics.benchmark_comparison import BenchmarkComparisonService

    try:
        service = BenchmarkComparisonService(current_user.id)
        data = service.get_comparison_data()
        return jsonify(data)
    except Exception as e:
        import traceback
        print(f"Error en api_benchmarks: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
