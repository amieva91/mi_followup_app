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
 * Gráfico 3: Apalancamiento/Cash Histórico
 */
function createLeverageChart(ctx, data) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '⚡ Apalancamiento / 💵 Cash',
                    data: data.datasets.leverage,
                    borderColor: function(context) {
                        const value = context.dataset.data[context.dataIndex];
                        return value >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)'; // green-600 or red-500
                    },
                    segment: {
                        borderColor: function(context) {
                            const value = context.p1.parsed.y;
                            return value >= 0 ? 'rgb(16, 185, 129)' : 'rgb(239, 68, 68)';
                        }
                    },
                    backgroundColor: 'rgba(107, 114, 128, 0.1)',
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
                            const value = context.parsed.y;
                            const type = value >= 0 ? '💵 Cash' : '⚡ Apalancamiento';
                            return type + ': ' + formatEuropeanNumber(Math.abs(value), 2) + ' €';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Gráfico 4: Flujos de Caja Acumulados
 */
function createCashFlowsChart(ctx, data) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '💰 Capital Invertido Neto',
                    data: data.datasets.cash_flows_cumulative,
                    borderColor: 'rgb(99, 102, 241)', // indigo-500
                    backgroundColor: 'rgba(99, 102, 241, 0.1)',
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
                            return 'Capital Neto: ' + formatEuropeanNumber(context.parsed.y, 2) + ' €';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Gráfico 5: P&L Acumulado
 */
function createPLChart(ctx, data) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '📊 P&L Total Acumulado',
                    data: data.datasets.pl_accumulated,
                    borderColor: function(context) {
                        const value = context.dataset.data[context.dataIndex];
                        return value >= 0 ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'; // green-500 or red-500
                    },
                    segment: {
                        borderColor: function(context) {
                            const value = context.p1.parsed.y;
                            return value >= 0 ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)';
                        }
                    },
                    backgroundColor: function(context) {
                        const value = context.dataset.data[context.dataIndex];
                        return value >= 0 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)';
                    },
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
                            const value = context.parsed.y;
                            return 'P&L Total: ' + (value >= 0 ? '+' : '') + formatEuropeanNumber(value, 2) + ' €';
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
        if (window.leverageChart && typeof window.leverageChart.destroy === 'function') {
            window.leverageChart.destroy();
        }
        if (window.cashFlowsChart && typeof window.cashFlowsChart.destroy === 'function') {
            window.cashFlowsChart.destroy();
        }
        if (window.plChart && typeof window.plChart.destroy === 'function') {
            window.plChart.destroy();
        }
        
        // Crear gráficos
        const ctx1 = document.getElementById('portfolioValueChart').getContext('2d');
        window.portfolioValueChart = createPortfolioValueChart(ctx1, data);
        
        const ctx2 = document.getElementById('returnsChart').getContext('2d');
        window.returnsChart = createReturnsChart(ctx2, data);
        
        const ctx3 = document.getElementById('leverageChart').getContext('2d');
        window.leverageChart = createLeverageChart(ctx3, data);
        
        const ctx4 = document.getElementById('cashFlowsChart').getContext('2d');
        window.cashFlowsChart = createCashFlowsChart(ctx4, data);
        
        const ctx5 = document.getElementById('plChart').getContext('2d');
        window.plChart = createPLChart(ctx5, data);
        
    } catch (error) {
        console.error('Error loading charts:', error);
        document.getElementById('loadingIndicator').classList.add('hidden');
        document.getElementById('errorMessage').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = 
            'Error al cargar los gráficos: ' + error.message;
    }
}

/**
 * Gráfico 6: Comparación con Benchmarks (HITO 4)
 */
function createBenchmarkChart(ctx, data) {
    // Colores para cada benchmark
    const benchmarkColors = {
        'S&P 500': 'rgb(34, 197, 94)',      // Verde
        'NASDAQ 100': 'rgb(59, 130, 246)',  // Azul
        'MSCI World': 'rgb(168, 85, 247)',  // Púrpura
        'EuroStoxx 50': 'rgb(245, 158, 11)' // Amarillo/Naranja
    };
    
    // Datasets: Portfolio primero (más destacado)
    const datasets = [
        {
            label: '📊 Tu Portfolio',
            data: data.datasets.portfolio,
            borderColor: 'rgb(239, 68, 68)',  // Rojo para destacar
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            borderWidth: 4,
            fill: false,
            tension: 0.4,
            pointRadius: 0,
            pointHoverRadius: 8
        }
    ];
    
    // Añadir benchmarks
    for (const [name, color] of Object.entries(benchmarkColors)) {
        if (data.datasets[name] && data.datasets[name].length > 0) {
            datasets.push({
                label: name,
                data: data.datasets[name],
                borderColor: color,
                backgroundColor: 'transparent',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 0,
                pointHoverRadius: 6,
                borderDash: [0]
            });
        }
    }
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: datasets
        },
        options: {
            ...commonChartOptions,
            plugins: {
                ...commonChartOptions.plugins,
                legend: {
                    display: true,
                    position: 'top',
                    onClick: function(e, legendItem) {
                        // Toggle visibility al hacer click (comportamiento estándar)
                        const index = legendItem.datasetIndex;
                        const chart = this.chart;
                        const meta = chart.getDatasetMeta(index);
                        meta.hidden = meta.hidden === null ? !chart.data.datasets[index].hidden : null;
                        chart.update();
                    }
                },
                tooltip: {
                    ...commonChartOptions.plugins.tooltip,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            // Mostrar como índice (base 100)
                            label += formatEuropeanNumber(context.parsed.y, 2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(value) {
                            // Mostrar como porcentaje desde inicio (100 = punto de partida)
                            return formatEuropeanNumber(value, 0);
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    title: {
                        display: true,
                        text: 'Índice (Base 100)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/**
 * Renderizar tabla comparativa anual
 */
function renderBenchmarkTable(annualData) {
    const tableBody = document.getElementById('benchmarkTableBody');
    if (!tableBody || !annualData) {
        console.error('❌ No se puede renderizar tabla: tableBody o annualData es null', { tableBody, annualData });
        return;
    }
    
    console.log('🔍 Renderizando tabla con datos:', {
        annual_count: annualData.annual?.length || 0,
        has_total: !!annualData.total,
        first_year_benchmarks: annualData.annual?.[0]?.benchmarks ? Object.keys(annualData.annual[0].benchmarks) : []
    });
    
    tableBody.innerHTML = '';
    
    // Añadir filas anuales
    annualData.annual.forEach(yearData => {
        const row = document.createElement('tr');
        row.className = 'border-b border-gray-200 hover:bg-gray-50';
        
        // Año
        const yearCell = document.createElement('td');
        yearCell.className = 'px-4 py-3 font-medium text-gray-900';
        yearCell.textContent = yearData.year;
        row.appendChild(yearCell);
        
        // Portfolio
        const portfolioCell = document.createElement('td');
        portfolioCell.className = 'px-4 py-3 text-gray-900 font-semibold';
        portfolioCell.textContent = formatEuropeanNumber(yearData.portfolio, 2) + '%';
        row.appendChild(portfolioCell);
        
        // Benchmarks y diferencias
        for (const benchmarkName of ['S&P 500', 'NASDAQ 100', 'MSCI World', 'EuroStoxx 50']) {
            const benchmarkCell = document.createElement('td');
            benchmarkCell.className = 'px-4 py-3';
            
            // Debug para NASDAQ 100
            if (benchmarkName === 'NASDAQ 100' && yearData.year === 2018) {
                console.log(`🔍 Verificando ${benchmarkName} para año ${yearData.year}:`, {
                    has_benchmarks: !!yearData.benchmarks,
                    benchmark_keys: yearData.benchmarks ? Object.keys(yearData.benchmarks) : [],
                    nasdaq_in_benchmarks: yearData.benchmarks && benchmarkName in yearData.benchmarks,
                    nasdaq_value: yearData.benchmarks?.[benchmarkName]
                });
            }
            
            if (benchmarkName in yearData.benchmarks) {
                const benchReturn = yearData.benchmarks[benchmarkName];
                const diff = yearData.differences[benchmarkName] || 0;
                
                const container = document.createElement('div');
                container.className = 'space-y-1';
                
                // Rentabilidad del benchmark
                const benchSpan = document.createElement('div');
                benchSpan.className = 'text-gray-700';
                benchSpan.textContent = formatEuropeanNumber(benchReturn, 2) + '%';
                container.appendChild(benchSpan);
                
                // Diferencia (portfolio - benchmark)
                const diffSpan = document.createElement('div');
                diffSpan.className = diff >= 0 ? 'text-green-600 text-sm font-medium' : 'text-red-600 text-sm font-medium';
                const diffSign = diff >= 0 ? '+' : '';
                diffSpan.textContent = diffSign + formatEuropeanNumber(diff, 2) + '%';
                container.appendChild(diffSpan);
                
                benchmarkCell.appendChild(container);
            } else {
                benchmarkCell.textContent = '-';
                benchmarkCell.className += ' text-gray-400';
            }
            
            row.appendChild(benchmarkCell);
        }
        
        tableBody.appendChild(row);
    });
    
    // Añadir fila de total
    const totalRow = document.createElement('tr');
    totalRow.className = 'border-t-2 border-gray-400 bg-gray-50 font-semibold';
    
    const totalLabelCell = document.createElement('td');
    totalLabelCell.className = 'px-4 py-3 text-gray-900';
    totalLabelCell.textContent = 'Total';
    totalRow.appendChild(totalLabelCell);
    
    const totalPortfolioCell = document.createElement('td');
    totalPortfolioCell.className = 'px-4 py-3 text-gray-900';
    totalPortfolioCell.textContent = formatEuropeanNumber(annualData.total.portfolio, 2) + '%';
    totalRow.appendChild(totalPortfolioCell);
    
    for (const benchmarkName of ['S&P 500', 'NASDAQ 100', 'MSCI World', 'EuroStoxx 50']) {
        const totalCell = document.createElement('td');
        totalCell.className = 'px-4 py-3';
        
        if (benchmarkName in annualData.total.benchmarks) {
            const benchReturn = annualData.total.benchmarks[benchmarkName];
            const diff = annualData.total.differences[benchmarkName] || 0;
            
            const container = document.createElement('div');
            container.className = 'space-y-1';
            
            const benchSpan = document.createElement('div');
            benchSpan.className = 'text-gray-700';
            benchSpan.textContent = formatEuropeanNumber(benchReturn, 2) + '%';
            container.appendChild(benchSpan);
            
            const diffSpan = document.createElement('div');
            diffSpan.className = diff >= 0 ? 'text-green-600 text-sm font-medium' : 'text-red-600 text-sm font-medium';
            const diffSign = diff >= 0 ? '+' : '';
            diffSpan.textContent = diffSign + formatEuropeanNumber(diff, 2) + '%';
            container.appendChild(diffSpan);
            
            totalCell.appendChild(container);
        } else {
            totalCell.textContent = '-';
            totalCell.className += ' text-gray-400';
        }
        
        totalRow.appendChild(totalCell);
    }
    
    tableBody.appendChild(totalRow);
}

/**
 * Cargar y mostrar datos de comparación con benchmarks
 */
async function loadBenchmarkData() {
    try {
        const response = await fetch('/portfolio/api/benchmarks');
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Debug: verificar datos recibidos
        console.log('📊 Datos de benchmarks recibidos:', {
            has_annual_returns: !!data.annual_returns,
            annual_count: data.annual_returns?.annual?.length || 0,
            first_year_benchmarks: data.annual_returns?.annual?.[0]?.benchmarks ? Object.keys(data.annual_returns.annual[0].benchmarks) : []
        });
        
        // Crear gráfico
        const ctx = document.getElementById('benchmarkChart').getContext('2d');
        if (window.benchmarkChart && typeof window.benchmarkChart.destroy === 'function') {
            window.benchmarkChart.destroy();
        }
        window.benchmarkChart = createBenchmarkChart(ctx, data);
        
        // Renderizar tabla
        renderBenchmarkTable(data.annual_returns);
        
    } catch (error) {
        console.error('Error loading benchmark data:', error);
        const errorDiv = document.getElementById('benchmarkError');
        if (errorDiv) {
            errorDiv.classList.remove('hidden');
            errorDiv.textContent = 'Error al cargar datos de benchmarks: ' + error.message;
        }
    }
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    // Cargar gráficos en frecuencia mensual (optimizado)
    loadCharts('monthly');
    
    // Cargar datos de benchmarks (HITO 4)
    loadBenchmarkData();
});

