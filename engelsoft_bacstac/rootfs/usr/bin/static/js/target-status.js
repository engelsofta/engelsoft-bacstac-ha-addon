// Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution.
(() => {
  const input = document.getElementById("target-filter");
  const rows = Array.from(document.querySelectorAll("[data-target-row]"));
  const count = document.getElementById("visible-target-count");
  const buttons = Array.from(document.querySelectorAll("[data-target-filter]"));
  const sortButtons = Array.from(document.querySelectorAll("[data-sort]"));
  const table = document.querySelector(".target-status-table");
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

  const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  let sortKey = "target";
  let sortDirection = 1;
  const numericKeys = new Set(["cov", "last_cov", "last_poll", "value_age"]);

  function sortRows(key, direction) {
    rows.sort((left, right) => {
      const leftValue = left.dataset[`sort${key.replace(/(^|_)(.)/g, (_m, _p, char) => char.toUpperCase())}`] ?? "";
      const rightValue = right.dataset[`sort${key.replace(/(^|_)(.)/g, (_m, _p, char) => char.toUpperCase())}`] ?? "";
      if (numericKeys.has(key)) {
        if (leftValue === "null" && rightValue === "null") return 0;
        if (leftValue === "null") return 1;
        if (rightValue === "null") return -1;
        const leftNumber = Number(leftValue);
        const rightNumber = Number(rightValue);
        return (leftNumber - rightNumber) * direction;
      }
      return collator.compare(leftValue, rightValue) * direction;
    });
    rows.forEach((row) => table.appendChild(row));
  }

  sortButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      sortDirection = sortKey === key ? -sortDirection : 1;
      sortKey = key;
      sortButtons.forEach((item) => {
        const active = item === button;
        item.classList.toggle("active", active);
        item.setAttribute("aria-sort", active ? (sortDirection === 1 ? "ascending" : "descending") : "none");
      });
      sortRows(sortKey, sortDirection);
    });
  });
})();
