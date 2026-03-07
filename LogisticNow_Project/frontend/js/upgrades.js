/* ================================================================
   upgrades.js — What-If Simulation, Demand Forecast, Control Tower
   ================================================================ */

// ── Tab navigation ────────────────────────────────────────────────────────────

const Tabs = (() => {
    const TAB_IDS = ['dashboard', 'whatif', 'forecast', 'tower'];

    function show(tabId) {
        TAB_IDS.forEach(id => {
            document.getElementById(`panel-${id}`)?.classList.toggle('active', id === tabId);
            document.getElementById(`tab-${id}`)?.classList.toggle('active', id === tabId);
        });
        // Auto-load Control Tower live data when switching to that tab
        if (tabId === 'tower') Upgrades.refreshTower();
    }

    return { show };
})();


// ── Shared utils ──────────────────────────────────────────────────────────────

function fmtINR(n) {
    return typeof n === 'number' ? '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: 0 }) : '--';
}

function fmtNum(n, d = 0) {
    return typeof n === 'number' ? n.toLocaleString('en-IN', { maximumFractionDigits: d }) : '--';
}

function deltaClass(val) {
    if (val > 2) return 'delta-up';
    if (val < -2) return 'delta-dn';
    return 'delta-neu';
}

function deltaArrow(val) {
    if (val > 2) return `▲ +${val.toFixed(1)}%`;
    if (val < -2) return `▼ ${val.toFixed(1)}%`;
    return `→ ${val.toFixed(1)}%`;
}

// Chart ref store
const _charts = {};

function makeOrUpdateChart(id, config) {
    if (_charts[id]) { _charts[id].destroy(); }
    const ctx = document.getElementById(id);
    if (!ctx) return;
    _charts[id] = new Chart(ctx, config);
}

const DARK = {
    gridColor: 'rgba(30,45,80,0.5)',
    textColor: '#8b9dc3',
    font: { family: 'Inter, sans-serif', size: 11 },
};

function darkPlugins() {
    return {
        legend: { labels: { color: DARK.textColor, font: DARK.font } },
        tooltip: { titleFont: DARK.font, bodyFont: DARK.font },
    };
}
function darkScales() {
    return {
        x: { ticks: { color: DARK.textColor, font: DARK.font }, grid: { color: DARK.gridColor } },
        y: { ticks: { color: DARK.textColor, font: DARK.font }, grid: { color: DARK.gridColor } },
    };
}


// ── UPGRADE 1: What-If Simulation ────────────────────────────────────────────

const Upgrades = (() => {

    async function runSimulation() {
        const btn = document.getElementById('run-sim-btn');
        btn.disabled = true;
        btn.textContent = 'Running...';

        const fp1 = parseFloat(document.getElementById('fuel-price').value);
        const ct1 = parseFloat(document.getElementById('carbon-tax').value);
        const fo = parseInt(document.getElementById('fleet-override').value);
        const pw1 = parseFloat(document.getElementById('priority-w').value);
        const fp2 = parseFloat(document.getElementById('fuel-price-2').value);
        const ct2 = parseFloat(document.getElementById('carbon-tax-2').value);

        const params = new URLSearchParams({
            fuel_price_1: fp1,
            carbon_tax_1: ct1,
            fleet_size_1: fo > 0 ? fo : '',
            priority_w_1: pw1,
            fuel_price_2: fp2,
            carbon_tax_2: ct2,
            priority_w_2: 1.2,
        });

        try {
            const res = await fetch(`/api/simulate?${params}`, { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                alert('Error: ' + (err.detail || 'Run optimization first'));
                return;
            }
            const data = await res.json();
            renderSimTable(data.comparison, data.scenarios);
            renderSimCharts(data.comparison);
        } catch (e) {
            alert('Simulation error: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Run Scenarios';
        }
    }

    function renderSimTable(comp, scenarios) {
        const wrap = document.getElementById('sim-table-wrap');
        if (!comp || comp.length === 0) {
            wrap.innerHTML = '<div class="empty-state"><div class="empty-state-text">No simulation data.</div></div>';
            return;
        }

        const rows = comp.map((sc, i) => {
            const cc = deltaClass(sc.cost_change_pct);
            const ec = deltaClass(sc.co2_change_pct);
            const isBase = i === 0;
            return `<tr>
        <td class="scenario-name">${sc.scenario}${isBase ? ' <span class="pill pill-blue" style="font-size:10px;">Base</span>' : ''}</td>
        <td style="font-family:var(--font-mono);">₹${sc.fuel_price}/L</td>
        <td style="font-family:var(--font-mono);">₹${sc.carbon_tax}/kg</td>
        <td style="font-family:var(--font-mono);font-weight:700;color:var(--text-primary);">${sc.trucks}</td>
        <td style="font-family:var(--font-mono);">${fmtINR(sc.total_cost)}</td>
        <td class="${cc}">${isBase ? '—' : deltaArrow(sc.cost_change_pct)}</td>
        <td style="font-family:var(--font-mono);">${fmtNum(sc.total_co2_kg, 0)} kg</td>
        <td class="${ec}">${isBase ? '—' : deltaArrow(sc.co2_change_pct)}</td>
        <td style="font-family:var(--font-mono);">${sc.avg_utilization}%</td>
      </tr>`;
        }).join('');

        wrap.innerHTML = `<table class="scenario-table">
      <thead><tr>
        <th>Scenario</th><th>Fuel</th><th>Carbon Tax</th><th>Trucks</th>
        <th>Total Cost</th><th>vs Base</th><th>CO2</th><th>CO2 Δ</th><th>Utilization</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
    }

    function renderSimCharts(comp) {
        if (!comp || comp.length === 0) return;
        const labels = comp.map(s => s.scenario);
        const costs = comp.map(s => s.total_cost);
        const co2s = comp.map(s => s.total_co2_kg);
        const colors = ['#3b82f6', '#ef4444', '#10b981'];

        makeOrUpdateChart('sim-cost-chart', {
            type: 'bar',
            data: { labels, datasets: [{ label: 'Total Cost (₹)', data: costs, backgroundColor: colors, borderRadius: 6 }] },
            options: { plugins: darkPlugins(), scales: darkScales(), animation: { duration: 700 } },
        });

        makeOrUpdateChart('sim-co2-chart', {
            type: 'bar',
            data: { labels, datasets: [{ label: 'CO2 (kg)', data: co2s, backgroundColor: colors, borderRadius: 6 }] },
            options: { plugins: darkPlugins(), scales: darkScales(), animation: { duration: 700 } },
        });
    }


    // ── UPGRADE 2: Demand Forecast ──────────────────────────────────────────────

    async function runForecast() {
        const horizon = document.getElementById('forecast-horizon').value;
        const zoneEl = document.getElementById('forecast-zones');
        const alertEl = document.getElementById('forecast-alerts');
        zoneEl.innerHTML = '<div class="empty-state"><div class="spinner" style="width:24px;height:24px;border-width:2px;"></div><div class="empty-state-text" style="margin-top:10px;">Generating forecast...</div></div>';
        alertEl.innerHTML = '';

        try {
            const res = await fetch(`/api/forecast?horizon_days=${horizon}`);
            if (!res.ok) throw new Error((await res.json()).detail);
            const data = await res.json();
            renderForecast(data);
        } catch (e) {
            zoneEl.innerHTML = `<div class="empty-state"><div class="empty-state-text">Forecast error: ${e.message}</div></div>`;
        }
    }

    function renderForecast(data) {
        // Summary stats
        document.getElementById('fc-total').textContent = fmtNum(data.total_tomorrow);
        document.getElementById('fc-fleet').textContent = data.suggested_fleet;
        document.getElementById('fc-zones').textContent = data.all_zones?.filter(z => z.tomorrow > 0).length || '--';

        // Alerts
        const alertEl = document.getElementById('forecast-alerts');
        alertEl.innerHTML = (data.alerts || []).map(a =>
            `<div class="alert-item warning">⚠ ${a}</div>`
        ).join('');

        // Zone cards
        const zoneEl = document.getElementById('forecast-zones');
        const sorted = [...(data.all_zones || [])].sort((a, b) => b.tomorrow - a.tomorrow);

        zoneEl.innerHTML = sorted.map(z => {
            const trend = z.trend_per_day;
            const tCls = trend > 1 ? 't-up' : trend < -1 ? 't-dn' : 't-flat';
            const tTxt = trend > 1 ? `▲ +${trend.toFixed(1)}/day` : trend < -1 ? `▼ ${trend.toFixed(1)}/day` : '→ Stable';
            const conf = ((data.all_zones.find(d => d.zone === z.zone)?.forecasts?.[0]?.confidence || 0.75) * 100).toFixed(0);
            return `<div class="fz-card">
        <div class="fz-name">${z.zone}</div>
        <div class="fz-count">${z.tomorrow}</div>
        <div class="fz-trend"><span class="${tCls}">${tTxt}</span></div>
        <div class="conf-bar"><div class="conf-fill" style="width:${conf}%"></div></div>
        <div style="font-size:10px;color:var(--text-muted);margin-top:3px;">Confidence: ${conf}%</div>
      </div>`;
        }).join('');

        // Forecast chart — top 5 zones, 3-day horizon
        const top5 = sorted.slice(0, 5);
        const days = top5[0]?.forecasts?.map(f => f.date) || [];
        const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'];

        makeOrUpdateChart('forecast-chart', {
            type: 'line',
            data: {
                labels: days,
                datasets: top5.map((z, i) => ({
                    label: z.zone,
                    data: z.forecasts.map(f => f.predicted_count),
                    borderColor: COLORS[i],
                    backgroundColor: COLORS[i] + '22',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 5,
                    pointBackgroundColor: COLORS[i],
                })),
            },
            options: {
                plugins: { ...darkPlugins(), title: { display: false } },
                scales: darkScales(),
                animation: { duration: 700 },
            },
        });
    }


    // ── UPGRADE 3: Control Tower ────────────────────────────────────────────────

    let _towerTimer = null;

    async function refreshTower() {
        const wrap = document.getElementById('tower-routes-wrap');
        const alerts = document.getElementById('tower-alerts');

        try {
            const res = await fetch('/api/live');
            if (!res.ok) throw new Error((await res.json()).detail);
            const data = await res.json();
            renderTower(data);
        } catch (e) {
            console.error('Tower error:', e);
        }
    }

    function renderTower(d) {
        // KPI values
        _set('tw-active', fmtNum(d.active_shipments));
        _set('tw-active-sub', `${fmtNum(d.delivered_today)} delivered today`);
        _set('tw-onroad', fmtNum(d.vehicles_on_road));
        _set('tw-onroad-sub', `${d.vehicles_idle} idle, ${d.vehicles_maintenance} maintenance`);
        _set('tw-util', `${d.avg_utilization}%`);
        _set('tw-util-sub', `${d.on_time_pct}% on-time`);
        _set('tw-co2', `${d.co2_today_ton} t`);
        _set('tw-co2-sub', `${fmtNum(d.co2_today_kg, 0)} kg total`);
        _set('tw-delivered', fmtNum(d.delivered_today));
        _set('tw-depot', fmtNum(d.at_depot));
        _set('tw-delayed', d.delayed_routes);
        _set('tw-delayed-sub', `${d.on_time_pct}% on-time`);
        _set('tw-cost', fmtINR(d.cost_today));

        // Alerts
        const alertEl = document.getElementById('tower-alerts');
        alertEl.innerHTML = (d.alerts || []).map(a =>
            `<div class="alert-item ${a.level}">${a.level === 'warning' ? '⚠' : a.level === 'success' ? '✔' : 'ℹ'} ${a.message}</div>`
        ).join('');

        // Live routes table
        const wrap = document.getElementById('tower-routes-wrap');
        if (!d.live_routes || d.live_routes.length === 0) {
            wrap.innerHTML = '<div class="empty-state"><div class="empty-state-text">No active routes.</div></div>';
            return;
        }

        const rows = d.live_routes.map(r => {
            const stCls = r.status === 'On Time' ? 'st-ok' : 'st-del';
            return `<tr>
        <td style="font-family:var(--font-mono);font-weight:700;color:var(--text-primary);">${r.vehicle_id}</td>
        <td>${r.origin}</td>
        <td>${r.destination}</td>
        <td>
          <div class="prog-wrap">
            <div class="prog-track"><div class="prog-fill" style="width:${r.progress_pct}%"></div></div>
            <span style="font-family:var(--font-mono);font-size:11px;">${r.progress_pct}%</span>
          </div>
        </td>
        <td class="${stCls}">${r.status}</td>
        <td style="font-family:var(--font-mono);">${r.eta_hours}h</td>
        <td style="font-family:var(--font-mono);">${fmtNum(r.load_kg)} kg</td>
      </tr>`;
        }).join('');

        wrap.innerHTML = `<table class="live-routes-tbl">
      <thead><tr><th>Vehicle</th><th>From</th><th>To</th><th>Progress</th><th>Status</th><th>ETA</th><th>Load</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;

        // Auto-refresh every 30s
        if (_towerTimer) clearInterval(_towerTimer);
        _towerTimer = setInterval(refreshTower, 30000);
    }

    function _set(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    return { runSimulation, runForecast, refreshTower };
})();
