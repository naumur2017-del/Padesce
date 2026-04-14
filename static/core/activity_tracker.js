// Activity tracking script
(function () {
  const trackUrl = window.PADESCE_ACTIVITY_TRACK_URL || "/api/activity/track/";
  const currentPath = window.location.pathname || "";
  const currentTitle = document.title || "";
  let browserGeo = null;
  const GEO_STORAGE_KEY = "padesce_geo_debug";

  function getCsrfToken() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function normalizeLabel(text) {
    return String(text || "").replace(/\s+/g, " ").trim().slice(0, 255);
  }

  function shouldTrackElement(element) {
    if (!element) return false;
    if (element.closest("[data-no-activity-track='1']")) return false;
    return true;
  }

  async function sendActivity(payload) {
    try {
      let enrichedPayload = payload;
      if (browserGeo) {
        enrichedPayload = Object.assign({}, payload, browserGeo);
      }
      await fetch(trackUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        credentials: "same-origin",
        body: JSON.stringify(enrichedPayload),
        keepalive: true,
      });
    } catch (error) {
      // Silently fail
    }
  }

  function saveGeoDebug(data) {
    try {
      var stored = Object.assign({}, data, {
        recorded_at: new Date().toISOString(),
      });
      localStorage.setItem(GEO_STORAGE_KEY, JSON.stringify(stored));
    } catch (error) {
      // Silently fail
    }
  }

  function fetchGeoFromBrowser() {
    if (!navigator.geolocation) {
      saveGeoDebug({
        status: "unsupported",
        latitude: null,
        longitude: null,
        accuracy: null,
        message: "Ce navigateur ne supporte pas la geolocalisation.",
        secure_context: window.isSecureContext ? "yes" : "no",
      });
      return;
    }
    saveGeoDebug({
      status: "requesting",
      latitude: null,
      longitude: null,
      accuracy: null,
      message: window.isSecureContext
        ? "Demande de position envoyee au navigateur."
        : "Contexte non securise: la geolocalisation peut etre bloquee hors HTTPS.",
      secure_context: window.isSecureContext ? "yes" : "no",
    });
    navigator.geolocation.getCurrentPosition(
      function (position) {
        browserGeo = {
          browser_latitude: Number(position.coords.latitude.toFixed(6)),
          browser_longitude: Number(position.coords.longitude.toFixed(6)),
        };
        saveGeoDebug({
          status: "success",
          latitude: browserGeo.browser_latitude,
          longitude: browserGeo.browser_longitude,
          accuracy: position.coords.accuracy || null,
          message: "Position navigateur recue.",
          secure_context: window.isSecureContext ? "yes" : "no",
        });
        sendActivity({
          event_type: "page_view",
          page_path: currentPath,
          page_title: currentTitle,
          target_label: currentTitle,
          target_path: currentPath,
        });
      },
      function (error) {
        saveGeoDebug({
          status: "error",
          latitude: null,
          longitude: null,
          accuracy: null,
          message: error && error.message ? error.message : "Geolocalisation refusee ou indisponible.",
          code: error && typeof error.code !== "undefined" ? error.code : null,
          secure_context: window.isSecureContext ? "yes" : "no",
        });
      },
      {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 300000,
      }
    );
  }

  // Send initial page view event
  sendActivity({
    event_type: "page_view",
    page_path: currentPath,
    page_title: currentTitle,
    target_label: currentTitle,
    target_path: currentPath,
  });

  // Fetch geolocation asynchronously
  window.__padesceGeoRequest = fetchGeoFromBrowser;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fetchGeoFromBrowser);
  } else {
    fetchGeoFromBrowser();
  }

  // Track clicks on buttons and links
  document.addEventListener("click", function (event) {
    const button = event.target.closest("button");
    const link = event.target.closest("a");
    const element = button || link;
    if (!shouldTrackElement(element)) return;

    const payload = {
      event_type: button ? "button_click" : "link_click",
      page_path: currentPath,
      page_title: currentTitle,
      target_label: normalizeLabel(
        element.getAttribute("data-track-label")
        || element.getAttribute("aria-label")
        || element.innerText
        || element.textContent
      ),
      target_path: normalizeLabel(
        element.getAttribute("href")
        || element.getAttribute("data-track-target")
        || element.getAttribute("id")
      ),
    };
    if (!payload.target_label && !payload.target_path) return;
    sendActivity(payload);
  }, true);
})();
