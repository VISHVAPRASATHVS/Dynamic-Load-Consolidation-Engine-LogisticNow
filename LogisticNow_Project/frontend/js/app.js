/* ================================================================
   app.js — Main application controller
   ================================================================ */

const App = (() => {
    const API = '';   // Same-origin
    let _lastData = null;

    // ── Utilities ────────────────────────────────────────────────

    function toast(msg, type = 'info', duration = 4000) {
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = msg;
        document.getElementById('toast-container').appendChild(el);
        setTimeout(() => el.remove(), duration);
    }

    function fmtNum(n, decimals = 0) {
        return typeof n === 'number' ? n.toLocaleString('en-IN', { maximumFractionDigits: decimals }) : '--';
    }

    function countUp(el, target, suffix = '', decimals = 0, duration = 900) {
        if (!el) return;
        const start = 0;
        const step = duration / 60;
        let current = start;
        const inc = target / (duration / step);
        const timer = setInterval(() => {
            current += inc;
            if (current >= target) { current = target; clearInterval(timer); }
            el.textContent = fmtNum(current, decimals) + suffix;
        }, step);
    }

    // ── API Calls ────────────────────────────────────────────────

    async function checkHealth() {
        try {
            const res = await fetch(`${API}/api/health`);
            const dot = document.getElementById('api-status-dot');
            if (res.ok) {
                dot.style.background = '#10b981';
                dot.style.boxShadow = '0 0 8px #10b981';
            } else {
                dot.style.background = '#ef4444';
                dot.style.boxShadow = '0 0 8px #ef4444';
            }
        } catch {
            const dot = document.getElementById('api-status-dot');
            dot.style.background = '#ef4444';
            dot.style.boxShadow = '0 0 8px #ef4444';
        }
    }

    async function uploadFile(type, input) {
        if (!input.files[0]) return;
        const formData = new FormData();
        formData.append('file', input.files[0]);
        const zoneId = type === 'shipments' ? 'ship-upload-zone' : 'fleet-upload-zone';
        const zone = document.getElementById(zoneId);
        const status = document.getElementById('upload-status');

        zone.classList.add('active');
        status.textContent = `Uploading ${type}...`;

        try {
            const res = await fetch(`${API}/api/upload/${type}`, { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                zone.style.borderColor = 'var(--green)';
                status.innerHTML = `<span style="color:var(--green)">${type.charAt(0).toUpperCase() + type.slice(1)}: ${data.rows} rows loaded</span>`;
                toast(`${type} data uploaded (${data.rows} rows)`, 'success');
                if (type === 'shipments') document.getElementById('ds-ships').textContent = data.rows;
                else document.getElementById('ds-fleet').textContent = data.rows;
            } else {
                toast(`Upload error: ${data.detail}`, 'error');
            }
        } catch (e) {
            toast(`Upload failed: ${e.message}`, 'error');
        } finally {
            zone.classList.remove('active');
        }
    }

    // ── Optimization ─────────────────────────────────────────────

    async function runOptimization() {
        const btn = document.getElementById('run-btn');
        const overlay = document.getElementById('map-overlay');
        const overlayText = document.getElementById('overlay-text');
        const nShips = document.getElementById('num-shipments').value;
        const nVehicles = document.getElementById('num-vehicles').value;

        // UI state
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px;"></div> Optimizing...';
        overlay.classList.remove('hidden');
        overlayText.textContent = 'Running VRP solver...';

        // Reset agent cards
        for (let i = 0; i < 4; i++) updateAgent(i, 'running', 'Processing...');

        try {
            const res = await fetch(`${API}/api/optimize?num_shipments=${nShips}&num_vehicles=${nVehicles}`, { method: 'POST' });
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || 'Optimization failed');

            _lastData = data;

            // Render everything
            overlay.classList.add('hidden');
            renderKPIs(data);
            MapModule.renderRoutes(data.routes);
            renderAgents(data.agents);
            renderRoutesTable(data.routes);
            renderComparison(data.before, data.after, data.comparison);
            renderClusterSummary(data.cluster_summary);
            Charts.updateAll({ before: data.before, after: data.after, routes: data.routes });

            document.getElementById('ds-ships').textContent = data.total_shipments;
            document.getElementById('ds-fleet').textContent = nVehicles;
            document.getElementById('export-btn').style.display = '';
            document.getElementById('route-count-sub').textContent = `${data.trucks_used} vehicle routes | ${data.total_shipments} shipments | ${data.unassigned?.length || 0} unassigned`;

            toast(`Optimization complete — ${data.trucks_used} routes generated`, 'success');

        } catch (e) {
            overlay.classList.remove('hidden');
            overlayText.textContent = 'Error: ' + e.message;
            toast('Optimization error: ' + e.message, 'error');
            console.error(e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Optimization';
        }
    }

    // ── KPIs ─────────────────────────────────────────────────────

    function renderKPIs(data) {
        const { after, comparison } = data;
        if (!after || !comparison) return;

        countUp(document.getElementById('kpi-trucks'), after.trucks_used);
        countUp(document.getElementById('kpi-cost'), comparison.cost_reduction_pct, '%', 1);
        countUp(document.getElementById('kpi-co2'), comparison.co2_reduction_pct, '%', 1);
        countUp(document.getElementById('kpi-util'), after.avg_utilization, '%', 1);
        countUp(document.getElementById('kpi-sla'), after.sla_compliance_pct, '%', 1);

        const d = (id, txt, cls) => {
            const el = document.getElementById(id);
            el.className = `kpi-delta ${cls}`;
            el.textContent = txt;
        };

        d('kpi-trucks-delta', `vs ${comparison.before_trucks} before`, 'pos');
        d('kpi-cost-delta', `₹${fmtNum(comparison.before_cost - after.total_cost, 0)} saved`, 'pos');
        d('kpi-co2-delta', `${fmtNum(comparison.before_co2 - after.total_co2_kg, 0)} kg saved`, 'pos');
        d('kpi-util-delta', `was ${comparison.before_utilization.toFixed(1)}%`, 'neu');
        d('kpi-sla-delta', `was ${comparison.before_sla.toFixed(1)}%`, after.sla_compliance_pct >= comparison.before_sla ? 'pos' : 'neg');
    }

    // ── Agent Status ──────────────────────────────────────────────

    function updateAgent(idx, status, msg, metric = null) {
        const card = document.getElementById(`agent-${idx}`);
        if (!card) return;
        card.className = `agent-card ${status}`;
        const badge = card.querySelector('.agent-status-badge');
        badge.className = `agent-status-badge badge-${status}`;
        badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        card.querySelector('.agent-msg').textContent = msg;
        const existingMetric = card.querySelector('.agent-metric');
        if (existingMetric) existingMetric.remove();
        if (metric) {
            const m = document.createElement('div');
            m.className = 'agent-metric';
            m.textContent = metric;
            card.appendChild(m);
        }
    }

    function renderAgents(agents) {
        if (!agents || !agents.length) return;
        const metricMap = {
            'Clustering Agent': a => `${a.result?.clusters_formed || 0} clusters`,
            'Capacity Agent': a => `${a.result?.avg_utilization_pct || 0}% avg util`,
            'SLA Agent': a => `${a.result?.compliance_pct || 0}% on-time`,
            'Carbon Agent': a => `${a.result?.co2_reduction_pct || 0}% CO2 cut`,
        };
        const names = ['Clustering Agent', 'Capacity Agent', 'SLA Agent', 'Carbon Agent'];
        agents.forEach((ag, i) => {
            const metric = metricMap[ag.agent] ? metricMap[ag.agent](ag) : null;
            updateAgent(i, ag.status, ag.message, metric);
        });
    }

    // ── Routes Table ──────────────────────────────────────────────

    function renderRoutesTable(routes) {
        const wrap = document.getElementById('routes-table-wrap');
        if (!routes || routes.length === 0) {
            wrap.innerHTML = '<div class="empty-state"><div class="empty-state-icon">&#128666;</div><div class="empty-state-text">No routes to display.</div></div>';
            return;
        }

        const rows = routes.map(r => {
            const utilColor = r.utilization_pct >= 80 ? 'var(--green)' : r.utilization_pct >= 50 ? 'var(--amber)' : 'var(--red)';
            const slaClass = r.sla_violations === 0 ? 'pill-green' : 'pill-red';
            const slaText = r.sla_violations === 0 ? 'OK' : `${r.sla_violations} late`;
            const effColor = (r.efficiency_score || 0) >= 75 ? 'pill-green' : (r.efficiency_score || 0) >= 50 ? 'pill-amber' : 'pill-red';
            const stopsList = r.stops.map(s => s.shipment_id).join(' → ');

            return `<tr>
        <td>
          <span class="route-color-dot" style="background:${r.color}"></span>
          <span style="font-family:var(--font-mono)">${r.vehicle_id}</span>
        </td>
        <td>${r.vehicle_type}</td>
        <td>${r.stops.length} stops</td>
        <td>
          <div class="util-bar">
            <div class="util-bar-track" style="width:70px;">
              <div class="util-bar-fill" style="width:${r.utilization_pct.toFixed(0)}%;background:${utilColor}"></div>
            </div>
            <span style="color:${utilColor};font-weight:600;font-family:var(--font-mono);font-size:12px;">${r.utilization_pct.toFixed(1)}%</span>
          </div>
        </td>
        <td style="font-family:var(--font-mono)">${r.total_distance_km.toFixed(0)} km</td>
        <td style="font-family:var(--font-mono)">₹${fmtNum(r.total_cost, 0)}</td>
        <td style="font-family:var(--font-mono)">${r.total_co2_kg.toFixed(1)} kg</td>
        <td><span class="pill ${slaClass}">${slaText}</span></td>
        <td><span class="pill ${effColor}">${(r.efficiency_score || 0).toFixed(0)}</span></td>
      </tr>`;
        }).join('');

        wrap.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Vehicle</th>
            <th>Type</th>
            <th>Stops</th>
            <th>Utilization</th>
            <th>Distance</th>
            <th>Cost</th>
            <th>CO2</th>
            <th>SLA</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
    }

    // ── Comparison ────────────────────────────────────────────────

    function renderComparison(before, after, comp) {
        if (!before || !after || !comp) return;

        const grid = document.getElementById('comparison-grid');

        const makeRow = (key, val, cls = '') =>
            `<div class="compare-row"><span class="compare-key">${key}</span><span class="compare-val ${cls}">${val}</span></div>`;

        const beforeHTML = `
      <div class="compare-col before">
        <div class="compare-col-title">Before Optimization</div>
        ${makeRow('Trucks Used', before.trucks_used, 'bad')}
        ${makeRow('Total Cost', '₹' + fmtNum(before.total_cost, 0), 'bad')}
        ${makeRow('CO2 Emissions', fmtNum(before.total_co2_kg, 1) + ' kg', 'bad')}
        ${makeRow('Distance', fmtNum(before.total_distance_km, 0) + ' km', '')}
        ${makeRow('Avg Utilization', before.avg_utilization + '%', '')}
        ${makeRow('SLA Compliance', before.sla_compliance_pct + '%', '')}
      </div>`;

        const afterHTML = `
      <div class="compare-col after">
        <div class="compare-col-title">After Optimization</div>
        ${makeRow('Trucks Used', after.trucks_used, 'good')}
        ${makeRow('Total Cost', '₹' + fmtNum(after.total_cost, 0), 'good')}
        ${makeRow('CO2 Emissions', fmtNum(after.total_co2_kg, 1) + ' kg', 'good')}
        ${makeRow('Distance', fmtNum(after.total_distance_km, 0) + ' km', '')}
        ${makeRow('Avg Utilization', after.avg_utilization + '%', 'good')}
        ${makeRow('SLA Compliance', after.sla_compliance_pct + '%', after.sla_compliance_pct >= 85 ? 'good' : 'bad')}
      </div>`;

        grid.innerHTML = beforeHTML + afterHTML;

        // Savings summary
        const savings = document.getElementById('savings-summary');
        savings.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:12px;">
        ${[
                ['Trucks Reduced', comp.truck_reduction_pct, '%'],
                ['Cost Saved', comp.cost_reduction_pct, '%'],
                ['CO2 Reduced', comp.co2_reduction_pct, '%'],
                ['Distance Cut', comp.dist_reduction_pct, '%'],
            ].map(([label, val, sfx]) => `
          <div class="savings-row" style="flex-direction:column;align-items:flex-start;gap:4px;">
            <span class="savings-label">${label}</span>
            <span class="savings-pct ${val < 0 ? 'neg' : ''}">${val > 0 ? '-' : ''}${Math.abs(val).toFixed(1)}${sfx}</span>
          </div>`
            ).join('')}
      </div>`;
    }

    // ── Cluster Summary ───────────────────────────────────────────

    function renderClusterSummary(summary) {
        if (!summary || Object.keys(summary).length === 0) return;
        const section = document.getElementById('cluster-section');
        const grid = document.getElementById('cluster-grid');
        section.style.display = '';

        const PRIORITY_COLORS = { Critical: '#ef4444', High: '#f59e0b', Medium: '#3b82f6', Low: '#8b9dc3' };

        grid.innerHTML = Object.entries(summary).map(([cid, info]) => {
            const topPri = Object.entries(info.priorities || {}).sort((a, b) => b[1] - a[1])[0];
            const priStr = topPri ? topPri[0] : '';
            const priColor = PRIORITY_COLORS[priStr] || '#8b9dc3';
            return `
        <div class="cluster-chip">
          <div class="cluster-chip-id">Cluster ${cid}</div>
          <div class="cluster-chip-info">
            ${info.count} shipments<br/>
            ${(info.total_weight_kg / 1000).toFixed(1)} t total<br/>
            <span style="color:${priColor};font-weight:600;font-size:11px;">${priStr}</span>
          </div>
        </div>`;
        }).join('');
    }

    // ── Export ────────────────────────────────────────────────────

    function exportCSV() {
        if (!_lastData || !_lastData.routes) return;
        const rows = [['Vehicle', 'Type', 'Stops', 'Load_kg', 'Capacity_kg', 'Util_%', 'Distance_km', 'Cost_INR', 'CO2_kg', 'SLA_Violations', 'Score']];
        _lastData.routes.forEach(r => {
            rows.push([r.vehicle_id, r.vehicle_type, r.stops.length, r.total_weight_kg, r.capacity_kg,
            r.utilization_pct, r.total_distance_km, r.total_cost.toFixed(2), r.total_co2_kg, r.sla_violations, r.efficiency_score || '']);
        });
        const csv = rows.map(r => r.join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `logisticnow_routes_${Date.now()}.csv`;
        a.click();
        toast('Routes exported to CSV', 'success');
    }

    // ── Init ──────────────────────────────────────────────────────

    function init() {
        // Range inputs
        ['num-shipments', 'num-vehicles'].forEach(id => {
            const el = document.getElementById(id);
            const out = document.getElementById(id + '-val');
            el.addEventListener('input', () => out.textContent = el.value);
        });

        // Init map
        MapModule.init();

        // Set initial map overlay text
        const overlay = document.getElementById('map-overlay');
        overlay.classList.remove('hidden');

        // Health check
        checkHealth();
        setInterval(checkHealth, 30000);
    }

    // Public
    return { init, runOptimization, uploadFile, exportCSV };
})();

// Bootstrap
document.addEventListener('DOMContentLoaded', App.init);
