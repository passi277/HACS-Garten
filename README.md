# Garten – Home Assistant Integration

Eigene Integration für den Garten. Sie bündelt vorhandene Geräte zu Garten-Bereichen und ergänzt sie um zusätzliche Logik, eigene Entitäten und Ereignisse. Bestehende Automationen und Helfer bleiben unangetastet: Die Integration **liest** nur fremde Entitäten und schaltet selbst nichts.

## Bereiche

| Bereich | Status |
|---|---|
| Outdoor-Küche: Grillgeräte, Sonden, Garprofile inkl. Wild | ✅ verfügbar |
| Bewässerung (Verbrauch, Wasserbedarf, Gießempfehlung) | geplant |
| Pool (Filterlaufzeit, Wasserwerte, Rückspülen) | geplant |
| Garten-Übersicht (Frost, Mähfenster, Batterien) | geplant |
| Pflanzen & Kalender (Pflegeaufgaben, Saisonkalender) | geplant |
| Floorplan-Karte mit Kameras | geplant |

## Installation

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/passi277/HACS-Garten`, Typ *Integration*
2. „Garten“ installieren und Home Assistant neu starten
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Garten*. Optional wählst du hier den Sensor für die **Außentemperatur**, entweder einen Temperatursensor oder eine Wetter-Entität. Ändern lässt sich das später über *⋮ → Neu konfigurieren*.
4. Am Eintrag „Garten“ fügst du deine Geräte hinzu:
   - **Grill hinzufügen**: z. B. Spanferkelgrill, Smoker, Gasgrill, Holzkohlegrill, Dutch Oven, Elektro-Kochplatte oder Pizzaofen
   - **Sonde hinzufügen**: z. B. Meater 2, Meater plus

## Outdoor-Küche

Grillgeräte und Sonden sind **getrennte Geräte**. Welche Sonde an welchem Grill steckt, legst du beim Grillen fest: An der Sonde wählst du im Feld **Grill** den passenden Grill aus.

- **Sonde einem Grill zuordnen**: Die Session dieses Grills startet automatisch.
- **Letzte Sonde abziehen** (Grill = „Keiner“) oder **Session beenden** drücken: Die Session endet und wird in der Historie gespeichert, samt Außentemperatur. Die Sonden werden wieder frei.
- **Session starten** geht auch ohne Sonde, z. B. zum Vorheizen.

Die Integration führt Zieltemperatur und Phase selbst. Du musst also keinen Garvorgang in der Meater-App starten.

### Grill-Gerät

| Entität | Beschreibung |
|---|---|
| `number` Garraum-Soll | Vorbelegt je Grilltyp (Spanferkelgrill 160 °C, Smoker 110 °C, Gasgrill 220 °C …) |
| `sensor` Garraumtemperatur | Eigener Garraum-Sensor des Grills. Ist keiner eingestellt, gilt die Umgebungstemperatur der zugeordneten Sonde. |
| `binary_sensor` Garraum außerhalb Bereich | Nur, wenn der Garraum den Sollbereich schon einmal erreicht hat (Toleranz einstellbar) |
| `sensor` Außentemperatur | Wenn am Garten-Eintrag eingestellt |
| `sensor` Zugeordnete Sonden | Anzahl, Attribut `probes` mit den Namen |
| `sensor` Session-Dauer | Minuten; Attribut `last_session` mit der letzten Session |
| `button` Session starten / beenden | |
| `event` Grill-Ereignis | siehe unten |

### Sonden-Gerät

| Entität | Beschreibung |
|---|---|
| `select` Grill | Keiner / deine Grills |
| `select` Gargut | Rind, Schwein, Geflügel, Lamm, **Wild** (Reh, Hirsch, Wildschwein, Hase, Wildente), Fisch … |
| `number` Zieltemperatur | Wird vom Gargut gesetzt und ist überschreibbar |
| `sensor` Kerntemperatur | Attribut `rate_per_minute` |
| `sensor` Umgebungstemperatur | Wenn für die Sonde eingestellt |
| `sensor` Fortschritt | % von der Starttemperatur bis zum Ziel |
| `sensor` Restzeit | Schätzung über den Temperaturanstieg der letzten 10 min |
| `sensor` Phase | Bereit, Aufheizen, Garen, Stall, Fast fertig, Ziel erreicht, Ruhen |
| `binary_sensor` Ziel erreicht | |

### Ereignisse

Das Event-Entity des Grills und zusätzlich das Bus-Event `garten_kitchen_event` melden:
`session_started`, `near_done` (5 °C vor Ziel), `target_reached`, `stall_detected` (Smoker/Spanferkelgrill: < 0,5 °C Anstieg in 15 min zwischen 60 und 80 °C), `chamber_deviation`, `probe_offline`, `session_ended`.

Die Event-Daten enthalten `grill`, `grill_type`, `probe`, `profile`, `temperature`, `target` und `outdoor_temperature`.

Beispiel-Automation für eine Push-Nachricht:

```yaml
triggers:
  - trigger: event
    event_type: garten_kitchen_event
    event_data:
      type: target_reached
actions:
  - action: notify.mobile_app_DEIN_HANDY  # anpassen
    data:
      title: "🔥 {{ trigger.event.data.probe }} am {{ trigger.event.data.grill }} ist fertig"
      message: >-
        {{ trigger.event.data.temperature | round(1) }} °C erreicht
        (Ziel {{ trigger.event.data.target | round(0) }} °C)
```

### Update von Version 0.1

Bestehende „Outdoor-Küche“-Einträge werden beim ersten Start automatisch umgewandelt: Jede Küche wird zu einem Grill (Spanferkel → Spanferkelgrill, sonst Gasgrill), ihre Sonden werden zu eigenständigen Sonden. Gargut, Zieltemperaturen und die Session-Historie bleiben erhalten. Die Entity-IDs ändern sich dabei, und eine laufende Session wird beendet.

## Entwicklung

```bash
pip install -r requirements_test.txt ruff
ruff check custom_components tests && ruff format --check custom_components tests
pytest
```
