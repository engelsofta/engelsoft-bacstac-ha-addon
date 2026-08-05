<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.12

Fehlende optionale BACnet-Eigenschaften wie `notification-class` oder
`relinquish-default` sind kein Gerätefehler. Die Discovery behandelt
`unknown-property` deshalb nun ruhig und fasst die Anzahl anschließend in einer
einzigen Meldung sowie in den Diagnosewerten zusammen.

Die Geräteerkennung ist außerdem deutlich schonender: Objektlisten und
Metadaten werden strikt nacheinander und mit einer kurzen Pause gelesen. Wenn
ein BACnet-Objekt `propertyList` unterstützt, fragt BACstac nur die tatsächlich
angebotenen Eigenschaften ab; ältere Geräte erhalten einen kompakten
Kompatibilitäts-Satz. Nach Zeitüberschreitungen wird die laufende Erkennung
abgebrochen und für das betroffene Gerät eine kurze Pause eingelegt. Damit
bekommen auch Gateways im Tiefschlaf genug Zeit für ihren ersten Kaffee.

Der bisherige Zähler **COV bestätigt** heißt jetzt **COV-Initialisierung**. Er
zeigt weiterhin, wie viele angeforderte COV-Ziele seit dem Add-on-Start
mindestens einmal erfolgreich bestätigt wurden. Ein späterer, nachgewiesener
Polling-Fallback lässt diesen Initialisierungsfortschritt bewusst unverändert.
