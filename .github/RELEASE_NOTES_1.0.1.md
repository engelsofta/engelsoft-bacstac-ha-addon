<!-- Created by engelsofta in 2026 for Engelsoft BACstac. -->

# Engelsoft BACstac 1.0.1

Dieses Wartungsupdate behebt einen Startfehler aus Version 1.0.0.

## Behoben

- Die s6-Startskripte besitzen wieder die erforderlichen Unix-Ausführungsrechte.
- Der Container-Build setzt diese Rechte zusätzlich explizit, damit sie auch bei
  einer Bearbeitung des Repositories unter Windows erhalten bleiben.

Betroffen war der Start mit `Permission denied` beziehungsweise Exit-Code `126`
bei `init-nginx` und `init-interface`.

## Installation

Im Home-Assistant-App-Store nach Updates suchen und **Engelsoft BACstac 1.0.1**
installieren.

