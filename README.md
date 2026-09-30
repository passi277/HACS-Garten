# Garten – Home Assistant Integration

Eigene Integration für den Garten. Sie bündelt vorhandene Geräte zu Garten-Bereichen und ergänzt sie um zusätzliche Logik, eigene Entitäten und Ereignisse. Bestehende Automationen und Helfer bleiben unangetastet: Die Integration **liest** nur fremde Entitäten und schaltet selbst nichts.

## Bereiche

| Bereich | Status |
|---|---|
| Outdoor-Küche: Grillgeräte, Sonden, Garprofile inkl. Wild | ✅ verfügbar |
| Bewässerung (Verbrauch, Wasserbedarf, Gießempfehlung) | geplant |
| Pool: Wasserwerte-Ampel, Rückspül-Erinnerung, Energie & Solar-Anteil, eigene Dashboard-Karte | ✅ verfügbar |
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
   - **Pool hinzufügen**: Pumpe, Wasserwerte, Kamera, Solar-Überschuss …

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

## Pool

**Pool hinzufügen** bündelt deinen Pool und seine Geräte zu einem Gerät. Pflicht ist nur die Pumpe, alles andere ist optional:

| Feld | Beispiel |
|---|---|
| Pumpe | `switch.stecker_pool_switch_0` |
| Pumpenleistung (W) | `sensor.stecker_pool_switch_0_power`, nötig für Energie, Kosten und Solar-Anteil |
| Wassertemperatur, pH, Redox, freies Chlor, Salz | `sensor.pool_temperature`, `sensor.pool_ph`, `sensor.pool_orp` … |
| Zeitpunkt der letzten Messung | `sensor.pool_last_measurement`, warnt nach 12 h ohne neue Messung |
| Pflegehinweis | `sensor.pool_guidance` |
| Empfohlene Laufzeit (h) | `sensor.pool_empfohlene_laufzeit` |
| Solar-Überschuss (W) | `sensor.solar_aktueller_uberschuss`: Einspeisung **nach** allen Verbrauchern inkl. Pumpe, negative Werte = Netzbezug |
| Kamera | `camera.pool` |

Die Integration **schaltet nichts selbst**. Deine Pool-Automationen bleiben unverändert.

### Entitäten (Gerät „Pool“)

| Entität | Beschreibung |
|---|---|
| `sensor` Wasserqualität | OK / Prüfen / Kritisch, der schlechteste Einzelwert. Trägt auch alles, was die Karte braucht. |
| `sensor` pH-/Redox-/Chlor-/Salz-Status | Ampel pro Wert. Standardbereiche siehe unten. |
| `binary_sensor` Messung veraltet | Letzte Messung älter als 12 h |
| `sensor` Pumpenlaufzeit heute | Stunden; Attribut `recommended_runtime` |
| `sensor` Pumpenstunden seit Rückspülen, `sensor` Letztes Rückspülen | |
| `binary_sensor` Rückspülen fällig | Pumpenstunden ≥ Intervall **oder** Tage ≥ Maximum |
| `button` Rückgespült | Setzt den Zähler zurück. Tipp: in deinem Skript „Pool: Rückspülen Start“ mit aufrufen. |
| `number` Rückspülen nach Pumpenstunden / spätestens nach Tagen / Strompreis | Einstellungen (Standard 50 h, 14 Tage, 0,30 €/kWh) |
| `sensor` Energie heute / Jahr, Solar-Anteil heute / Jahr, Stromkosten heute, Solar-Ersparnis Jahr | Aus Pumpenleistung und Solar-Überschuss berechnet |
| `event` Pool-Ereignis | `water_quality_changed` (nur bei Verschlechterung), `measurement_stale`, `backwash_due`, `backwash_done`, zusätzlich Bus-Event `garten_pool_event` |

Standardbereiche (angelehnt an Blue Riiot):

| Wert | OK | Prüfen | sonst |
|---|---|---|---|
| pH | 7,2 – 7,6 | 6,8 – 8,0 | Kritisch |
| Redox | 650 – 800 mV | 400 – 900 mV | Kritisch |
| Freies Chlor | 0,5 – 1,5 mg/l | 0,2 – 3,0 mg/l | Kritisch |
| Salz | 3,0 – 4,5 g/l | 2,5 – 6,0 g/l | Kritisch |

### Dashboard-Karte

Die Integration bringt die Karte **Garten Pool** mit. Du musst sie weder separat über HACS noch als Ressource installieren. Im Dashboard: *Karte hinzufügen → „Garten Pool“*, oder per YAML:

```yaml
type: custom:garten-pool-card
entity: sensor.pool_wasserqualitat   # Wasserqualität-Sensor deines Pools
show_camera: true                    # false = kompakt ohne Kamerabild
```

Die Karte zeigt die Wassertemperatur, die Pumpe (antippen schaltet sie), die Wasserwerte mit Ampel und Bereichsbalken, den Pflegehinweis, Laufzeit und Rückspülen samt Button „Rückgespült“ sowie Energie, Solar-Anteil, Kosten und Ersparnis. Ein Tipp auf einen Wert öffnet dessen Details.

## Entwicklung

```bash
pip install -r requirements_test.txt ruff
ruff check custom_components tests && ruff format --check custom_components tests
pytest
```
