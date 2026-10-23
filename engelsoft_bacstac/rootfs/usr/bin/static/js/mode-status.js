// Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution.
(() => {
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
        node.textContent = data.ready ? "Integrationsgesteuert" : "Wird gestartet";
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

  async function refreshTimeSync() {
    try {
      const response = await fetch("./apiv1/time-sync/status", {cache:"no-store"});
      if (!response.ok) return;
      const data = await response.json();
      if (!data.timestamp) return;
      const english = document.documentElement.lang.startsWith("en");
      const labels = english ? {matched:"Time verified",mismatch:"Clock differs",unverified:"Unverified",failed:"Failed",running:"Running …"} : {matched:"Zeit geprüft",mismatch:"Zeit weicht ab",unverified:"Nicht prüfbar",failed:"Fehlgeschlagen",running:"Läuft …"};
      const when = new Date(data.timestamp).toLocaleString(english?"en-GB":"de-DE",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"});
      const before = data.before_difference_seconds;
      const after = data.difference_seconds;
      const drift = typeof before === "number" && typeof after === "number" ? ` · Δ ${Math.abs(before).toFixed(1)} → ${after.toFixed(1)} s` : "";
      const detail = `${data.device_id} · ${data.mode.toUpperCase()}${drift}`;
      document.querySelectorAll("[data-time-sync-title]").forEach(n=>n.textContent=`${when} · ${labels[data.status]||data.status}`);
      document.querySelectorAll("[data-time-sync-detail]").forEach(n=>n.textContent=detail);
      document.querySelectorAll(".time-sync-summary").forEach(n=>{n.dataset.status=data.status;n.title=english?"Latest device attempt since add-on start. Absolute clock deviation before → after; no receipt acknowledgement.":"Letzter Geräteversuch seit Add-on-Start. Absolute Zeitabweichung vorher → nachher; keine Empfangsbestätigung."});
    } catch (_) { /* Retry on the next refresh. */ }
  }
  refreshTimeSync();
  window.setInterval(refreshTimeSync, 5000);
  refreshModeStatus();
  window.setInterval(refreshModeStatus, 3000);
})();
