# Garten – Home Assistant Integration

Eigene Integration für den Garten. Sie bündelt vorhandene Geräte zu Garten-Bereichen und ergänzt sie um zusätzliche Logik, eigene Entitäten und Ereignisse. Bestehende Automationen und Helfer bleiben unangetastet: Die Integration **liest** nur fremde Entitäten und schaltet selbst nichts.

## Bereiche

| Bereich | Status |
|---|---|
| Outdoor-Küche (Grillthermometer, Garmethoden, Garprofile) | ✅ verfügbar |
| Bewässerung (Verbrauch, Wasserbedarf, Gießempfehlung) | geplant |
| Pool (Filterlaufzeit, Wasserwerte, Rückspülen) | geplant |
| Garten-Übersicht (Frost, Mähfenster, Batterien) | geplant |
| Pflanzen & Kalender (Pflegeaufgaben, Saisonkalender) | geplant |
| Floorplan-Karte mit Kameras | geplant |

## Installation

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/passi277/HACS-Garten`, Typ *Integration*
2. „Garten“ installieren und Home Assistant neu starten
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Garten*
4. Am Eintrag „Garten“ → **Outdoor-Küche hinzufügen**

## Outdoor-Küche

Bei der Einrichtung wählst du pro Sonde (bis zu 4) den Sensor für die **Kerntemperatur** (z. B. `sensor.…_meater_2_innentemperatur`) und optional die **Umgebungstemperatur** als Garraum-Sensor. Kamera, Licht und Stromschalter kannst du verknüpfen. Sie werden als Attribute bereitgestellt und später im Floorplan genutzt.

Die Integration führt Zieltemperatur und Phase selbst. Du musst also keinen Garvorgang in der Meater-App starten.

### Entitäten (Gerät „Outdoor-Küche“)

| Entität | Beschreibung |
|---|---|
| `select` Garmethode | Aus, Gasgrill, Smoker, Spanferkel, Dutch Oven, Elektro-Herdplatte. Eine Auswahl ≠ Aus startet die Session, „Aus“ beendet sie. |
| `number` Garraum-Soll | Wird je Methode vorbelegt (Gasgrill 220 °C, Smoker 110 °C, Spanferkel 160 °C, Dutch Oven 180 °C) |
| `sensor` Garraumtemperatur | Umgebungstemperatur der ersten verfügbaren Sonde |
| `binary_sensor` Garraum außerhalb Bereich | Nur, wenn der Garraum den Sollbereich schon einmal erreicht hat (Toleranz einstellbar) |
| `button` Session starten / beenden | |
| `sensor` Session-Dauer | Minuten; Attribut `last_session` mit der letzten Session |
| `event` Küchen-Ereignis | siehe unten |

Pro Sonde:

| Entität | Beschreibung |
|---|---|
| `select` Gargut | z. B. Rind medium (58 °C), Pulled Pork (93 °C), Spanferkel (75 °C), Hähnchen (74 °C), Lachs (52 °C) |
| `number` Zieltemperatur | Wird vom Gargut gesetzt und ist überschreibbar |
| `sensor` Kerntemperatur | Gespiegelt, Attribut `rate_per_minute` |
| `sensor` Fortschritt | % von Starttemperatur bis Ziel |
| `sensor` Restzeit | Schätzung über den Temperaturanstieg der letzten 10 min |
| `sensor` Phase | Bereit, Aufheizen, Garen, Stall, Fast fertig, Ziel erreicht, Ruhen |
| `binary_sensor` Ziel erreicht | |

### Ereignisse

Das Event-Entity und zusätzlich das Bus-Event `garten_kitchen_event` melden:
`session_started`, `near_done` (5 °C vor Ziel), `target_reached`, `stall_detected` (Smoker/Spanferkel: < 0,5 °C Anstieg in 15 min zwischen 60 und 80 °C), `chamber_deviation`, `probe_offline`, `session_ended`.

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
      title: "🔥 {{ trigger.event.data.probe }} ist fertig"
      message: >-
        {{ trigger.event.data.temperature | round(1) }} °C erreicht
        (Ziel {{ trigger.event.data.target | round(0) }} °C)
```

## Entwicklung

```bash
pip install -r requirements_test.txt ruff
ruff check custom_components tests && ruff format --check custom_components tests
pytest
```
