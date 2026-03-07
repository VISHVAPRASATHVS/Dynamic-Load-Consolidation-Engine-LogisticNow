/* ================================================================
   charts.js — Chart.js visualizations
   ================================================================ */

const Charts = (() => {
    const _instances = {};

    const THEME = {
        grid: 'rgba(30, 45, 80, 0.6)',
        text: '#8b9dc3',
        blue: '#3b82f6',
        green: '#10b981',
        amber: '#f59e0b',
        red: '#ef4444',
        purple: '#8b5cf6',
    };

    const _defaultOptions = {
        responsive: true,
        maintainAspectRatio: true,
        animation: { duration: 800, easing: 'easeInOutQuart' },
        plugins: {
            legend: { labels: { color: THEME.text, font: { family: 'Inter', size: 12 }, padding: 16 } },
            tooltip: {
                backgroundColor: '#0f1628',
                borderColor: '#1e2d50',
                borderWidth: 1,
                titleColor: '#e8edf7',
                bodyColor: '#8b9dc3',
                cornerRadius: 8,
                padding: 10,
            },
        },
        scales: {
            x: { grid: { color: THEME.grid }, ticks: { color: THEME.text, font: { family: 'Inter', size: 11 } } },
            y: { grid: { color: THEME.grid }, ticks: { color: THEME.text, font: { family: 'Inter', size: 11 } } },
        },
    };

    function _destroy(id) {
        if (_instances[id]) {
            _instances[id].destroy();
            delete _instances[id];
        }
    }

    function renderCostChart(before, after) {
        _destroy('cost-chart');
        const ctx = document.getElementById('cost-chart');
        if (!ctx) return;
        _instances['cost-chart'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Before Optimization', 'After Optimization'],
                datasets: [{
                    label: 'Total Route Cost (₹)',
                    data: [before, after],
                    backgroundColor: [
                        'rgba(239, 68, 68, 0.5)',
                        'rgba(16, 185, 129, 0.5)',
                    ],
                    borderColor: [THEME.red, THEME.green],
                    borderWidth: 2,
                    borderRadius: 6,
                }],
            },
            options: {
                ..._defaultOptions,
                plugins: { ..._defaultOptions.plugins, legend: { display: false } },
                scales: {
                    ..._defaultOptions.scales,
                    y: { ..._defaultOptions.scales.y, ticks: { ..._defaultOptions.scales.y.ticks, callback: v => '₹' + v.toLocaleString() } },
                },
            },
        });
    }

    function renderCO2Chart(before, after) {
        _destroy('co2-chart');
        const ctx = document.getElementById('co2-chart');
        if (!ctx) return;
        _instances['co2-chart'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Before Optimization', 'After Optimization'],
                datasets: [{
                    label: 'Total CO2 (kg)',
                    data: [before, after],
                    backgroundColor: ['rgba(239, 68, 68, 0.5)', 'rgba(16, 185, 129, 0.5)'],
                    borderColor: [THEME.red, THEME.green],
                    borderWidth: 2,
                    borderRadius: 6,
                }],
            },
            options: {
                ..._defaultOptions,
                plugins: { ..._defaultOptions.plugins, legend: { display: false } },
                scales: {
                    ..._defaultOptions.scales,
                    y: { ..._defaultOptions.scales.y, ticks: { ..._defaultOptions.scales.y.ticks, callback: v => v.toFixed(0) + ' kg' } },
                },
            },
        });
    }

    function renderUtilChart(routes) {
        _destroy('util-chart');
        const ctx = document.getElementById('util-chart');
        if (!ctx || !routes) return;
        const labels = routes.map(r => r.vehicle_id);
        const values = routes.map(r => r.utilization_pct);
        const colors = routes.map(r => r.color || THEME.blue);

        _instances['util-chart'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Utilization %',
                    data: values,
                    backgroundColor: colors.map(c => c + '88'),
                    borderColor: colors,
                    borderWidth: 2,
                    borderRadius: 4,
                }],
            },
            options: {
                ..._defaultOptions,
                indexAxis: 'y',
                plugins: { ..._defaultOptions.plugins, legend: { display: false } },
                scales: {
                    x: { ..._defaultOptions.scales.x, min: 0, max: 100, ticks: { ..._defaultOptions.scales.x.ticks, callback: v => v + '%' } },
                    y: { ..._defaultOptions.scales.y },
                },
            },
        });
    }

    function renderWeightChart(routes) {
        _destroy('weight-chart');
        const ctx = document.getElementById('weight-chart');
        if (!ctx || !routes) return;
        const labels = routes.map(r => r.vehicle_id);
        const vals = routes.map(r => r.total_weight_kg);
        const caps = routes.map(r => r.capacity_kg);

        _instances['weight-chart'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Loaded (kg)',
                        data: vals,
                        backgroundColor: 'rgba(59, 130, 246, 0.5)',
                        borderColor: THEME.blue,
                        borderWidth: 2,
                        borderRadius: 4,
                    },
                    {
                        label: 'Capacity (kg)',
                        data: caps,
                        backgroundColor: 'rgba(30, 45, 80, 0.4)',
                        borderColor: '#1e2d50',
                        borderWidth: 1,
                        borderRadius: 4,
                        type: 'bar',
                    }
                ],
            },
            options: {
                ..._defaultOptions,
                scales: {
                    ..._defaultOptions.scales,
                    y: { ..._defaultOptions.scales.y, ticks: { ..._defaultOptions.scales.y.ticks, callback: v => v.toLocaleString() + ' kg' } },
                },
            },
        });
    }

    function updateAll(data) {
        const { before, after, routes } = data;
        if (before && after) {
            renderCostChart(before.total_cost, after.total_cost);
            renderCO2Chart(before.total_co2_kg, after.total_co2_kg);
        }
        if (routes) {
            renderUtilChart(routes);
            renderWeightChart(routes);
        }
    }

    return { renderCostChart, renderCO2Chart, renderUtilChart, renderWeightChart, updateAll };
})();
