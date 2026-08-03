// Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution.
(() => {
  const labels = {
    integration_controlled: "Integrationsgesteuert",
    managed_polling: "Verwaltetes Polling",
    managed_cov: "COV bevorzugt",
    legacy: "Legacy / manuell",
    starting: "Wird gestartet",
  };

  function setMetric(name, value) {
    document.querySelectorAll(`[data-mode-metric="${name}"]`).forEach((node) => {
      const number = node.querySelector("b");
      if (number) number.textContent = String(value ?? 0);
      if (name === "fallback" || name === "disabled") {
        node.hidden = !value;
      }
    });
  }

  async function refreshModeStatus() {
    try {
      const response = await fetch("./apiv1/diagnostics/subscriptions", {
        cache: "no-store",
      });
      if (!response.ok) return;
      const data = await response.json();
      const fallback = (data.target_status || []).filter(
        (target) => target.fallback_active,
      ).length;
      document.querySelectorAll("[data-mode-label]").forEach((node) => {
        node.textContent = labels[data.subscription_mode] || data.subscription_mode;
      });
      setMetric("targets", data.managed_targets);
      setMetric("cov", data.managed_cov_targets);
      setMetric("polling", data.managed_poll_targets);
      setMetric("fallback", fallback);
      setMetric("disabled", data.managed_disabled_targets);
    } catch (_error) {
      // The next interval retries quietly while the add-on is starting.
    }
  }

  refreshModeStatus();
  window.setInterval(refreshModeStatus, 3000);
})();
