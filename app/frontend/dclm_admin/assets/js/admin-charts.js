(function () {
  function initCharts(root) {
    if (!window.Chart) return;
    const scope = root instanceof Element ? root : document;
    const hosts = scope.matches?.("[data-chartjs-config]")
      ? [scope]
      : Array.from(scope.querySelectorAll("[data-chartjs-config]"));

    hosts.forEach((host) => {
      const canvas = host.querySelector("canvas");
      const rawConfig = host.getAttribute("data-chartjs-config");
      if (!canvas || !rawConfig) return;
      if (host.__chartRaw === rawConfig && host.__chartInstance) return;

      if (host.__chartInstance) {
        host.__chartInstance.destroy();
        host.__chartInstance = null;
      }

      try {
        const parsed = JSON.parse(rawConfig);
        const context = canvas.getContext("2d");
        if (!context) return;
        host.__chartInstance = new window.Chart(context, parsed);
        host.__chartRaw = rawConfig;
      } catch (error) {
        console.error("Failed to initialize admin chart", error);
      }
    });
  }

  function boot() {
    initCharts(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  document.body.addEventListener("htmx:afterSwap", (event) => {
    initCharts(event.target || document);
  });

  document.body.addEventListener("htmx:afterSettle", (event) => {
    initCharts(event.target || document);
  });

  window.AdminChartInit = initCharts;
})();
