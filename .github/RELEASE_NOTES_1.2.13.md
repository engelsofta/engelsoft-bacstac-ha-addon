<!-- Created by engelsofta in 2026 for the modified Engelsoft BACstac distribution. -->

# Engelsoft BACstac 1.2.13

Dieses Release räumt die letzten irreführenden Fehlermeldungen während der
BACnet-Geräteerkennung auf.

Ein Gerät ohne Unterstützung für `ReadPropertyMultiple` löst nun einen normalen
Wechsel auf die schonende Einzelabfrage aus und wird nicht mehr als Fehler
protokolliert. Optionale Geräteinformationen, die mit `unknown-property`
abgelehnt werden, erscheinen nur noch im Debug-Log.

BACstac merkt sich solche nicht unterstützten Eigenschaften außerdem für die
aktuelle Laufzeit. Wiederholte I-Am-Erkennungen fragen sie daher nicht erneut
ab. Echte Kommunikationsfehler und ausbleibende Geräteantworten bleiben
weiterhin deutlich sichtbar – das Log wird ruhiger, aber nicht blind.
