/* ================================================================
   map.js — Leaflet route visualization
   ================================================================ */

const MapModule = (() => {
  let _map = null;
  let _routeLayers = [];
  let _markerLayers = [];

  const INDIA_CENTER = [20.5937, 78.9629];

  function init() {
    if (_map) return;
    _map = L.map('map', {
      center: INDIA_CENTER,
      zoom: 5,
      zoomControl: true,
      attributionControl: false,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 18,
    }).addTo(_map);

    // Custom attribution
    L.control.attribution({ position: 'bottomright' })
      .addAttribution('LogisticNow | Team Sypnatix')
      .addTo(_map);
  }

  function clear() {
    _routeLayers.forEach(l => _map.removeLayer(l));
    _markerLayers.forEach(l => _map.removeLayer(l));
    _routeLayers = [];
    _markerLayers = [];
  }

  function _makeDepotIcon(color) {
    return L.divIcon({
      className: '',
      html: `<div style="
        width:16px;height:16px;
        background:${color};
        border:3px solid #fff;
        border-radius:3px;
        box-shadow:0 2px 8px rgba(0,0,0,0.6);
      "></div>`,
      iconAnchor: [8, 8],
    });
  }

  function _makeDeliveryIcon(color) {
    return L.divIcon({
      className: '',
      html: `<div style="
        width:10px;height:10px;
        background:${color};
        border:2px solid rgba(255,255,255,0.8);
        border-radius:50%;
        box-shadow:0 1px 4px rgba(0,0,0,0.5);
      "></div>`,
      iconAnchor: [5, 5],
    });
  }

  function renderRoutes(routes) {
    if (!_map) init();
    clear();
    if (!routes || routes.length === 0) return;

    const allBounds = [];

    routes.forEach((route, idx) => {
      const color = route.color || '#3b82f6';

      // Depot marker
      const depotM = L.marker([route.depot_lat, route.depot_lon], { icon: _makeDepotIcon(color) })
        .bindPopup(`
          <div style="font-family:Inter,sans-serif;min-width:160px;">
            <b style="color:${color}">${route.vehicle_id}</b><br/>
            <small style="color:#888">${route.vehicle_type}</small><br/><br/>
            <strong>Load:</strong> ${route.total_weight_kg.toFixed(0)} / ${route.capacity_kg.toFixed(0)} kg<br/>
            <strong>Utilization:</strong> ${route.utilization_pct.toFixed(1)}%<br/>
            <strong>Distance:</strong> ${route.total_distance_km.toFixed(1)} km<br/>
            <strong>Cost:</strong> ₹${route.total_cost.toFixed(0)}<br/>
            <strong>CO2:</strong> ${route.total_co2_kg.toFixed(1)} kg
          </div>
        `);
      depotM.addTo(_map);
      _markerLayers.push(depotM);
      allBounds.push([route.depot_lat, route.depot_lon]);

      // Build route path: depot → stops → depot
      const pathCoords = [[route.depot_lat, route.depot_lon]];

      route.stops.forEach((stop, si) => {
        pathCoords.push([stop.delivery_lat, stop.delivery_lon]);
        allBounds.push([stop.delivery_lat, stop.delivery_lon]);

        const m = L.marker([stop.delivery_lat, stop.delivery_lon], { icon: _makeDeliveryIcon(color) })
          .bindPopup(`
            <div style="font-family:Inter,sans-serif;min-width:150px;">
              <b style="color:${color}">${stop.shipment_id}</b>
              <span style="float:right;font-size:10px;background:rgba(59,130,246,0.15);
                color:#60a5fa;padding:1px 6px;border-radius:8px;">${stop.priority}</span><br/>
              <small style="color:#888">${stop.ship_type}</small><br/><br/>
              <strong>Weight:</strong> ${stop.weight_kg.toFixed(0)} kg<br/>
              <strong>Deadline:</strong> ${stop.deadline} h<br/>
              <strong>Service:</strong> ${stop.service_time} min
            </div>
          `);
        m.addTo(_map);
        _markerLayers.push(m);
      });

      // Return to depot
      pathCoords.push([route.depot_lat, route.depot_lon]);

      // Draw route
      const polyline = L.polyline(pathCoords, {
        color: color,
        weight: 2.5,
        opacity: 0.85,
        dashArray: null,
        smoothFactor: 1.5,
      });

      // Animate drawing
      polyline.addTo(_map);
      _routeLayers.push(polyline);
    });

    // Fit bounds
    if (allBounds.length > 0) {
      const bounds = L.latLngBounds(allBounds);
      _map.fitBounds(bounds, { padding: [30, 30] });
    }

    // Invalidate size to fix potential rendering issues
    setTimeout(() => _map && _map.invalidateSize(), 200);
  }

  return { init, renderRoutes, clear };
})();
