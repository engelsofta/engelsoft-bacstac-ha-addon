<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.12

Fehlende optionale BACnet-Eigenschaften wie `notification-class` oder
`relinquish-default` sind kein Gerätefehler. Die Discovery behandelt
`unknown-property` deshalb nun ruhig und fasst die Anzahl anschließend in einer
einzigen Meldung sowie in den Diagnosewerten zusammen.

Der bisherige Zähler **COV bestätigt** heißt jetzt **COV-Initialisierung**. Er
zeigt weiterhin, wie viele angeforderte COV-Ziele seit dem Add-on-Start
mindestens einmal erfolgreich bestätigt wurden. Ein späterer, nachgewiesener
Polling-Fallback lässt diesen Initialisierungsfortschritt bewusst unverändert.
