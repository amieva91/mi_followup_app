/**
 * Charts.js - Configuración de gráficos con Chart.js
 * Sprint 4 - HITO 3: Gráficos de Evolución
 */

// Formato europeo de números
function formatEuropeanNumber(value, decimals = 2) {
    return value.toLocaleString('es-ES', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

// Configuración común de Chart.js
const commonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
        mode: 'index',
        intersect: false,
    },
    plugins: {
        legend: {
            display: true,
            position: 'top',
        },
        tooltip: {
            enabled: true,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            padding: 12,
            titleFont: {
                size: 14,
                weight: 'bold'
            },
            bodyFont: {
                size: 13
            }
        }
    }
};

/**
 * Gráfico 1: Evolución del Valor del Portfolio
 */
function createPortfolioValueChart(ctx, data) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '📈 Valor Real de la Cuenta',
                    data: data.datasets.portfolio_value,
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6
                },
                {
                    label: '💰 Capital Invertido',
                    data: data.datasets.capital_invested,
                    borderColor: 'rgb(156, 163, 175)',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            ...commonChartOptions,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatEuropeanNumber(value, 0) + ' €';
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                ...commonChartOptions.plugins,
                tooltip: {
                    ...commonChartOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += formatEuropeanNumber(context.parsed.y, 2) + ' €';
                            return label;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Gráfico 2: Rentabilidad Acumulada (Modified Dietz)
 */
function createReturnsChart(ctx, data) {
    // Determinar color según último valor
    const lastReturn = data.datasets.returns_pct[data.datasets.returns_pct.length - 1] || 0;
    const lineColor = lastReturn >= 0 ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)';
    const fillColor = lastReturn >= 0 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)';
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '📊 Rentabilidad Acumulada',
                    data: data.datasets.returns_pct,
                    borderColor: lineColor,
                    backgroundColor: fillColor,
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6
                }
            ]
        },
        options: {
            ...commonChartOptions,
            scales: {
                y: {
                    ticks: {
                        callback: function(value) {
                            return formatEuropeanNumber(value, 2) + '%';
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                ...commonChartOptions.plugins,
                tooltip: {
                    ...commonChartOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            const value = context.parsed.y;
                            label += (value >= 0 ? '+' : '') + formatEuropeanNumber(value, 2) + '%';
                            return label;
                        }
                    }
                }
            }
        }
    });
}

/**
 * Cargar datos y renderizar gráficos
 */
async function loadCharts(frequency = 'weekly') {
    try {
        // Mostrar loading
        document.getElementById('loadingIndicator').classList.remove('hidden');
        
        // Fetch data
        const response = await fetch(`/portfolio/api/evolution?frequency=${frequency}`);
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Ocultar loading
        document.getElementById('loadingIndicator').classList.add('hidden');
        
        // Mostrar gráficos
        document.getElementById('chartsContainer').classList.remove('hidden');
        
        // Destruir gráficos existentes si los hay
        if (window.portfolioValueChart && typeof window.portfolioValueChart.destroy === 'function') {
            window.portfolioValueChart.destroy();
        }
        if (window.returnsChart && typeof window.returnsChart.destroy === 'function') {
            window.returnsChart.destroy();
        }
        
        // Crear gráficos
        const ctx1 = document.getElementById('portfolioValueChart').getContext('2d');
        window.portfolioValueChart = createPortfolioValueChart(ctx1, data);
        
        const ctx2 = document.getElementById('returnsChart').getContext('2d');
        window.returnsChart = createReturnsChart(ctx2, data);
        
    } catch (error) {
        console.error('Error loading charts:', error);
        document.getElementById('loadingIndicator').classList.add('hidden');
        document.getElementById('errorMessage').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = 
            'Error al cargar los gráficos: ' + error.message;
    }
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    // Cargar gráficos en frecuencia mensual (optimizado)
    loadCharts('monthly');
});

