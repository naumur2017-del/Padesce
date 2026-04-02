(function() {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  function warmCache() {
    navigator.serviceWorker.ready
      .then((registration) => {
        const urls = Array.from(document.querySelectorAll("a[href]"))
          .map((link) => link.href)
          .filter((href) => href && href.startsWith(window.location.origin))
          .filter((href) => !href.includes("/logout"))
          .slice(0, 24);

        urls.unshift(window.location.href);
        registration.active?.postMessage({
          type: "PADESCE_WARM_CACHE",
          urls: Array.from(new Set(urls)),
        });
      })
      .catch(() => {
        // Ignore warm-cache failures.
      });
  }

  window.addEventListener("load", function() {
    navigator.serviceWorker
      .register("/service-worker.js")
      .then(() => warmCache())
      .catch(() => {
        // Ignore registration failures.
      });
  });

  window.addEventListener("online", warmCache);

  navigator.serviceWorker.addEventListener("message", function(event) {
    if (!event.data || event.data.type !== "PADESCE_CACHE_REFRESHED") {
      return;
    }
    window.dispatchEvent(new CustomEvent("padesce:cache-refreshed", { detail: event.data }));
  });
})();
