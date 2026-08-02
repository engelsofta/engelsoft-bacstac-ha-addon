/* Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. */
(function () {
  "use strict";

  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");

  function colorIsDark(color) {
    const hex = color.match(/^#([\da-f]{3}|[\da-f]{6})$/i)?.[1];
    if (hex) {
      const expanded = hex.length === 3
        ? hex.split("").map((character) => character + character).join("")
        : hex;
      const numeric = Number.parseInt(expanded, 16);
      const red = (numeric >> 16) & 255;
      const green = (numeric >> 8) & 255;
      const blue = numeric & 255;
      return (0.2126 * red + 0.7152 * green + 0.0722 * blue) < 140;
    }

    const values = color.match(/[\d.]+/g);
    if (!values || values.length < 3) return null;
    const [red, green, blue] = values.slice(0, 3).map(Number);
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) < 140;
  }

  function homeAssistantDarkMode() {
    try {
      if (window.parent === window) return null;
      const homeAssistant = window.parent.document.querySelector("home-assistant");
      const darkMode = homeAssistant?.hass?.themes?.darkMode;
      if (typeof darkMode === "boolean") return darkMode;

      const parentStyle = window.parent.getComputedStyle(
        window.parent.document.documentElement
      );
      const background = parentStyle.getPropertyValue("--primary-background-color").trim();
      return background ? colorIsDark(background) : null;
    } catch (_error) {
      return null;
    }
  }

  function applyTheme() {
    const homeAssistantTheme = homeAssistantDarkMode();
    const darkMode = homeAssistantTheme ?? systemTheme.matches;
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
  }

  applyTheme();
  systemTheme.addEventListener?.("change", applyTheme);
  window.addEventListener("focus", applyTheme);
  window.setInterval(applyTheme, 1500);
})();
