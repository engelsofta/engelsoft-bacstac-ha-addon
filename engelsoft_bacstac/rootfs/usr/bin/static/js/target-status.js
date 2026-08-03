// Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution.
(() => {
  const input = document.getElementById("target-filter");
  const rows = Array.from(document.querySelectorAll("[data-target-row]"));
  const count = document.getElementById("visible-target-count");
  const buttons = Array.from(document.querySelectorAll("[data-target-filter]"));
  if (!input || !count) return;

  let selected = "active";
  const apply = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    rows.forEach((row) => {
      const state = row.dataset.state || "";
      const matchesState =
        selected === "all" ||
        (selected === "active" && state !== "disabled" && state !== "cancelled") ||
        (selected === "cov" && state.startsWith("cov")) ||
        (selected === "polling" && state === "polling") ||
        (selected === "fallback" && row.dataset.fallback === "true") ||
        (selected === "disabled" && state === "disabled");
      const matchesText = !query || (row.dataset.search || "").toLocaleLowerCase().includes(query);
      row.hidden = !(matchesState && matchesText);
      if (!row.hidden) visible += 1;
    });
    count.textContent = String(visible);
  };

  input.addEventListener("input", apply);
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      selected = button.dataset.targetFilter || "all";
      buttons.forEach((item) => item.classList.toggle("active", item === button));
      apply();
    });
  });
})();
