// Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution.
(() => {
  const translations = [
    ["BACnet/IP-Schnittstelle", "BACnet/IP interface"],
    ["Geräte, Objekte und aktuelle Werte", "Devices, objects and current values"],
    ["Geräte", "Devices"], ["Gerät", "Device"], ["Objekte", "Objects"], ["Objekt", "Object"],
    ["Aktualisierungen", "Updates"], ["AKTUALISIERUNGSSTEUERUNG", "UPDATE CONTROL"],
    ["Integrationsgesteuert", "Integration controlled"], ["Wird gestartet", "Starting"],
    ["Ziele", "Targets"], ["Zielstatus", "Target status"], ["Zielstatus filtern", "Filter target status"],
    ["Objekte werden erst beim Öffnen geladen", "Objects are loaded when opened"],
    ["Gerät, Name, Hersteller oder Modell suchen …", "Search device, name, vendor or model …"],
    ["Datenpunkt suchen …", "Search data point …"], ["Wird geladen …", "Loading …"],
    ["Geräteschutz", "Device protection"], ["Betrieb", "Runtime"], ["GERÄT", "DEVICE"],
    ["Standard für alle Geräte", "Default for all devices"], ["Globale Schutzregel", "Global protection rule"],
    ["Gerät suchen", "Search device"], ["Geräte-ID oder Name …", "Device ID or name …"],
    ["COV-Laufzeit in Sekunden", "COV lifetime in seconds"],
    ["Maximale COV-Anmeldungen", "Maximum COV subscriptions"],
    ["COV nach I-Am erneuern", "Renew COV after I-Am"],
    ["Fehlende Anmeldungen nach einem Geräteneustart wiederherstellen.", "Restore missing subscriptions after a device restart."],
    ["Objektliste nach I-Am prüfen", "Check object list after I-Am"],
    ["Objekte bei einer erneuten I-Am-Meldung prüfen.", "Check objects when another I-Am is received."],
    ["Übernehmen", "Apply"], ["Gerätestandard verwenden", "Use device default"],
    ["LAUFENDER BETRIEB", "RUNTIME"], ["Aktualisierung", "Updates"],
    ["Änderungen wirken ohne Neustart", "Changes apply without a restart"],
    ["Polling-Intervall in Sekunden", "Polling interval in seconds"],
    ["Abstand zwischen COV-Anmeldungen in ms", "Delay between COV subscriptions in ms"],
    ["COV-Prüfzeit in Sekunden", "COV verification time in seconds"],
    ["Standard-Schreibpriorität", "Default write priority"],
    ["Aus Cache", "Cached"], ["Eigene Regel", "Custom rule"], ["Standardregel", "Default rule"],
    ["Status", "Status"], ["Adresse", "Address"], ["Hersteller", "Vendor"], ["Modell", "Model"],
    ["Diese Regel gilt für alle Geräte ohne eigene Einstellung.", "This rule applies to all devices without custom settings."],
    ["Datenpunkte konnten nicht geladen werden.", "Data points could not be loaded."],
    ["Keine passenden Datenpunkte.", "No matching data points."],
    ["Gespeichert und live übernommen.", "Saved and applied live."], ["Speichern fehlgeschlagen.", "Saving failed."],
    ["COV- und Polling-Status", "COV and polling status"],
    ["COV-Bestätigung, letzter Transport und Wertealter", "COV confirmation, latest transport and value age"],
    ["Seit dem Add-on-Start mindestens einmal bestätigte COV-Anmeldungen", "COV subscriptions confirmed at least once since add-on start"],
    ["COV-Initialisierung", "COV initialization"],
    ["Gerät, Objekt oder Status filtern …", "Filter device, object or status …"],
    ["Aktiv", "Active"], ["Alle", "All"], ["Aus", "Off"], ["sichtbar", "visible"],
    ["Gerät / Objekt", "Device / object"], ["Letztes COV", "Latest COV"], ["Letzter Poll", "Latest poll"], ["Wertealter", "Value age"],
    ["Gerät auswählen:", "Select device:"], ["BACnet-Gerät auswählen.", "Select BACnet device."],
    ["Objekt auswählen:", "Select object:"], ["BACnet-Objekt auswählen.", "Select BACnet object."],
    ["Bestätigungsart:", "Confirmation type:"], ["Bestätigt", "Confirmed"], ["Unbestätigt", "Unconfirmed"],
    ["COV-Laufzeit:", "COV lifetime:"], ["Laufzeit in Sekunden.", "Lifetime in seconds."],
    ["COV anmelden", "Subscribe to COV"], ["COV-Anmeldung senden.", "Send COV subscription."],
    ["COV ausgewählt", "COV selected"], ["Ausgewählte COV beenden", "Cancel selected COV"],
    ["Ausgewählte COV-Subscriptions beenden.", "Cancel selected COV subscriptions."],
    ["COV aktiv", "COV active"], ["Wartet auf COV", "Waiting for COV"], ["COV-Anmeldung", "COV subscription"],
    ["Wartet auf Gerät", "Waiting for device"], ["Polling gestört", "Polling error"],
    ["Deaktiviert", "Disabled"], ["Beendet", "Cancelled"], ["Wartend", "Waiting"],
    ["Keine COV-Werte", "No COV values"], ["COV fehlgeschlagen", "COV failed"],
    ["Grund:", "Reason:"], ["Kontroll-Poll aktiv", "Verification poll active"], ["Fehler:", "Error:"],
    ["Anmeldung läuft", "Subscription pending"], ["war bestätigt", "was confirmed"],
    ["Noch keine Aktualisierungsziele aktiv. In einem verwalteten Modus werden sie von Engelsoft Beacon BACnet/IP übermittelt.", "No update targets are active yet. In a managed mode they are provided by Engelsoft Beacon BACnet/IP."],
    ["EDE-Dateien:", "EDE files:"], ["EDE-Datei auswählen", "Select EDE file"],
    ["Statustexte auswählen", "Select state texts"], ["Dateien hochladen", "Upload files"],
    ["EDE-Dateien hochladen", "Upload EDE files"], ["Auswahl löschen", "Delete selection"],
    ["Ausgewählte EDE-Dateien löschen", "Delete selected EDE files"],
    ["Warte auf BACnet-Geräteadresse", "Waiting for BACnet device address"],
    [" von ", " of "], [" angefordert", " requested"], [" COV-Plätzen aktiv", " COV slots active"],
    [" COV-Ziele werden wegen des Limits gepollt.", " COV targets are polled because of the limit."],
  ];
  translations.sort((left, right) => right[0].length - left[0].length);

  function homeAssistantLanguage() {
    const explicit = new URLSearchParams(location.search).get("lang");
    if (explicit) return explicit;
    try {
      const parentLang = window.parent?.document?.documentElement?.lang;
      if (parentLang) return parentLang;
    } catch (_error) { /* Cross-origin embedding: use browser language below. */ }
    return navigator.language || "en";
  }

  if (!homeAssistantLanguage().toLowerCase().startsWith("en")) return;
  document.documentElement.lang = "en";

  const translate = (value) => {
    let result = value;
    translations.forEach(([source, target]) => { result = result.split(source).join(target); });
    return result;
  };
  const translateElement = (element) => {
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.parentElement?.closest("script, style")) continue;
      node.nodeValue = translate(node.nodeValue);
    }
    element.querySelectorAll?.("[title], [placeholder], [aria-label], input[value]").forEach((node) => {
      ["title", "placeholder", "aria-label", "value"].forEach((name) => {
        if (node.hasAttribute(name)) node.setAttribute(name, translate(node.getAttribute(name)));
      });
    });
  };
  const start = () => {
    document.title = translate(document.title);
    translateElement(document.body);
    new MutationObserver((mutations) => mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) node.nodeValue = translate(node.nodeValue);
      else if (node.nodeType === Node.ELEMENT_NODE) translateElement(node);
    }))).observe(document.body, { childList: true, subtree: true });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
