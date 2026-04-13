
  (function () {
    const GEO_STORAGE_KEY = "padesce_geo_debug";
    const canvas = document.getElementById("activity-globe");
    const statsOnline = document.getElementById("online-users-value");
    const statsTotal = document.getElementById("total-users-value");
    const statsPoints = document.getElementById("globe-points-value");
    const onlineFeed = document.getElementById("online-feed");
    const liveApiUrl = "{% url 'user_tracking_live_api' %}";
    let points = JSON.parse(document.getElementById("globe-points-data").textContent || "[]");
    let rotation = 15;

    function renderGeoDebug() {
      let data = null;
      try {
        data = JSON.parse(localStorage.getItem(GEO_STORAGE_KEY) || "null");
      } catch (error) {
        data = null;
      }
      const statusEl = document.getElementById("geo-debug-status");
      const latEl = document.getElementById("geo-debug-latitude");
      const lonEl = document.getElementById("geo-debug-longitude");
      const accEl = document.getElementById("geo-debug-accuracy");
      const recEl = document.getElementById("geo-debug-recorded-at");
      const msgEl = document.getElementById("geo-debug-message");
      const secureEl = document.getElementById("geo-debug-secure");
      if (!data) {
        if (statusEl) statusEl.textContent = "Aucune donnee";
        if (latEl) latEl.textContent = "-";
        if (lonEl) lonEl.textContent = "-";
        if (accEl) accEl.textContent = "-";
        if (recEl) recEl.textContent = "-";
        if (msgEl) msgEl.textContent = "Le navigateur n'a encore rien enregistre.";
        if (secureEl) secureEl.textContent = window.isSecureContext ? "Oui" : "Non";
        return;
      }
      if (statusEl) statusEl.textContent = data.status || "-";
      if (latEl) latEl.textContent = data.latitude !== null && typeof data.latitude !== "undefined" ? data.latitude : "-";
      if (lonEl) lonEl.textContent = data.longitude !== null && typeof data.longitude !== "undefined" ? data.longitude : "-";
      if (accEl) accEl.textContent = data.accuracy !== null && typeof data.accuracy !== "undefined" ? data.accuracy : "-";
      if (recEl) recEl.textContent = data.recorded_at ? new Date(data.recorded_at).toLocaleString() : "-";
      if (msgEl) msgEl.textContent = data.message || "-";
      if (secureEl) secureEl.textContent = data.secure_context === "yes" ? "Oui" : data.secure_context === "no" ? "Non" : "-";
    }

    function projectPoint(lat, lon, centerLon, centerLat, radius) {
      const deg = Math.PI / 180;
      const phi = lat * deg;
      const lambda = lon * deg;
      const lambda0 = centerLon * deg;
      const phi0 = centerLat * deg;
      const cosc = Math.sin(phi0) * Math.sin(phi) + Math.cos(phi0) * Math.cos(phi) * Math.cos(lambda - lambda0);
      if (cosc <= 0) return null;
      const x = radius * Math.cos(phi) * Math.sin(lambda - lambda0);
      const y = radius * (Math.cos(phi0) * Math.sin(phi) - Math.sin(phi0) * Math.cos(phi) * Math.cos(lambda - lambda0));
      return { x, y };
    }

    function drawGlobe() {
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.min(width, height) * 0.39;
      ctx.clearRect(0, 0, width, height);

      const ocean = ctx.createRadialGradient(cx - radius * 0.25, cy - radius * 0.35, radius * 0.1, cx, cy, radius);
      ocean.addColorStop(0, "#2aa4d6");
      ocean.addColorStop(0.55, "#0d5d89");
      ocean.addColorStop(1, "#07344e");
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = ocean;
      ctx.fill();

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.clip();

      ctx.strokeStyle = "rgba(255,255,255,0.16)";
      ctx.lineWidth = 1;
      for (let lat = -60; lat <= 60; lat += 30) {
        ctx.beginPath();
        let started = false;
        for (let lon = -180; lon <= 180; lon += 3) {
          const p = projectPoint(lat, lon, rotation, 10, radius);
          if (!p) {
            started = false;
            continue;
          }
          if (!started) {
            ctx.moveTo(cx + p.x, cy - p.y);
            started = true;
          } else {
            ctx.lineTo(cx + p.x, cy - p.y);
          }
        }
        ctx.stroke();
      }
      for (let lon = -150; lon <= 180; lon += 30) {
        ctx.beginPath();
        let started = false;
        for (let lat = -89; lat <= 89; lat += 3) {
          const p = projectPoint(lat, lon, rotation, 10, radius);
          if (!p) {
            started = false;
            continue;
          }
          if (!started) {
            ctx.moveTo(cx + p.x, cy - p.y);
            started = true;
          } else {
            ctx.lineTo(cx + p.x, cy - p.y);
          }
        }
        ctx.stroke();
      }

      const africaPath = [
        [-17, 37], [-5, 36], [9, 34], [25, 31], [34, 25], [45, 12], [50, 2], [43, -12],
        [32, -34], [18, -35], [8, -30], [-1, -18], [-6, 2], [-10, 14], [-17, 28], [-17, 37]
      ];
      ctx.beginPath();
      africaPath.forEach(([lon, lat], index) => {
        const p = projectPoint(lat, lon, rotation, 10, radius);
        if (!p) return;
        if (index === 0) ctx.moveTo(cx + p.x, cy - p.y);
        else ctx.lineTo(cx + p.x, cy - p.y);
      });
      ctx.closePath();
      ctx.fillStyle = "rgba(113, 230, 179, 0.18)";
      ctx.fill();

      points.forEach((point) => {
        const projected = projectPoint(point.latitude, point.longitude, rotation, 10, radius);
        if (!projected) return;
        const px = cx + projected.x;
        const py = cy - projected.y;
        ctx.beginPath();
        ctx.arc(px, py, point.online ? 6 : 4, 0, Math.PI * 2);
        ctx.fillStyle = point.online ? "#22c55e" : "#94a3b8";
        ctx.fill();
        if (point.online) {
          ctx.beginPath();
          ctx.arc(px, py, 12, 0, Math.PI * 2);
          ctx.strokeStyle = "rgba(34, 197, 94, 0.28)";
          ctx.lineWidth = 3;
          ctx.stroke();
        }
      });
      ctx.restore();

      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.22)";
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    function renderOnlineFeed(rows) {
      if (!onlineFeed) return;
      if (!rows.length) {
        onlineFeed.innerHTML = '<article class="online-card"><h3>Aucun agent actif</h3><p>La liste se mettra a jour automatiquement des qu\\'un utilisateur sera detecte en ligne.</p></article>';
        return;
      }
      onlineFeed.innerHTML = rows.map((row) => `
        <article class="online-card">
          <h3>${row.username}</h3>
          <p><strong>Page:</strong> ${row.current_page_title || row.current_page || "-"}</p>
          <p><strong>Derniere action:</strong> ${row.last_action_type || "-"}${row.last_action_label ? " - " + row.last_action_label : ""}</p>
          <p><strong>Lieu:</strong> ${row.city || "-"}, ${row.country || "-"}</p>
          <p><strong>Vu a:</strong> ${row.last_action_at || "-"}</p>
        </article>
      `).join("");
    }

    async function refreshLive() {
      try {
        const response = await fetch(liveApiUrl, { headers: { Accept: "application/json" }, credentials: "same-origin" });
        if (!response.ok) return;
        const payload = await response.json();
        if (!payload.ok) return;
        points = payload.globe_points || [];
        if (statsOnline) statsOnline.textContent = typeof payload.online_count !== "undefined" && payload.online_count !== null ? payload.online_count : "0";
        if (statsTotal) statsTotal.textContent = typeof payload.total_users !== "undefined" && payload.total_users !== null ? payload.total_users : "0";
        if (statsPoints) statsPoints.textContent = points.length;
        renderOnlineFeed(payload.online_rows || []);
      } catch (error) {
      }
    }

    function animate() {
      rotation = (rotation + 0.2) % 360;
      drawGlobe();
      window.requestAnimationFrame(animate);
    }

    drawGlobe();
    renderGeoDebug();
    var geoDebugTrigger = document.getElementById("geo-debug-trigger");
    if (geoDebugTrigger) {
      geoDebugTrigger.addEventListener("click", function () {
        if (typeof window.__padesceGeoRequest === "function") {
          window.__padesceGeoRequest();
          window.setTimeout(renderGeoDebug, 1200);
        }
      });
    }
    animate();
    refreshLive();
    window.setInterval(refreshLive, 5000);
    window.setInterval(renderGeoDebug, 3000);
  })();

