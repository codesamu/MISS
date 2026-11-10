# MISS-Hauptprogramm

Eine gemeinsame Anwendung für den Raspberry Pi und die PC-Simulation. Der Start
führt direkt zum Kamerabild, ohne Dashboard oder Modellauswahl. Klassen und
Bounding Boxes sind sichtbar; Konfidenzwerte werden ausschließlich intern benutzt.

Die GUI verwendet jetzt eine neue Gestaltung mit schattierten Objektanimationen,
weichen Übergängen und Countdown-Ring. Details zu Leistung und Alternativen wie
LVGL/Qt Quick stehen in [GUI-Technik.md](GUI-Technik.md).

## Jetzt am PC ausprobieren

Im Projektordner:

```powershell
python -m pip install -r Simulation/requirements.txt
python -m miss_app --simulate
```

Auch `python Simulation/main.py` und `Simulation/Start-Simulation.bat` starten
dieses Hauptprogramm. Im PC-Modus sind Kamera, YOLO-Ergebnisse und Servos simuliert;
es werden keine Gewichte geladen und keine GPIOs verwendet. Die eigentliche
Ablauflogik und die Displaydarstellung sind identisch mit dem Hardwaremodus.

Die Vorschau zeigt standardmäßig native 480 × 320 Pixel (1:1), ohne Hochskalierung.
Mit `--scale 2` lässt sie sich bei Bedarf vergrößern.

Rechts Gegenstände oder Fehlersituationen wählen: beide Gegenstände, niedrige
Erkennungssicherheit, ein Objekt am Plattenrand oder außerhalb der Platte.
Standardmäßig entfernt die Simulation den Gegenstand nach der Servobewegung.
**Nach Sortierung entfernen** ausschalten, um einen liegen gebliebenen Gegenstand
zu testen. **Esc** oder das Schließen des Fensters beendet die Simulation.

Die bisherige Testoberfläche bleibt über `python Simulation/main.py --legacy`
erreichbar.

## Ablauf

1. Die Anwendung erkennt Gegenstände im Kamerabild. Die mittige Plattenfläche
   wird in normierten Bildkoordinaten festgelegt.
2. Genau eine erkannte Box darf diese Fläche berühren und muss vollständig darin
   liegen. Auch eine zweite Box derselben Klasse oder eine zweite Box mit nur
   25 % Konfidenz verhindert die Sortierung. Erkennungen vollständig außerhalb
   der Platte werden ignoriert.
3. Das Objekt benötigt intern mindestens 60 % Konfidenz, mindestens drei neue
   Erkennungsbilder und eine Sekunde stabile Position/Klasse. Die Box wird mit
   der anfänglichen Box verglichen, damit langsames Wandern nicht als Stillstand
   gilt. Verspätete oder wiederholte Ergebnisse bestätigen kein Objekt.
4. Die Servos bewegen sich nacheinander: horizontal zur Zielrichtung, vertikal
   zur Zielrichtung, Fallzeit abwarten, vertikal zurück, horizontal zurück.
   Die Bewegung läuft ohne blockierende `sleep`-Kette im Bedienablauf.
5. Nach Abschluss erscheint die Klasse als animierte Flasche oder Dose. Links
   ist der Daumen nach oben, rechts der Daumen nach unten. Jetzt beginnen die
   zehn Sekunden. Ein neuer Tipp bewertet und führt sofort zum Kamerabild;
   ohne Tipp kehrt die Anwendung nach Ablauf zurück.
6. Das Kamerabild erscheint sofort wieder. Für die nächste Sortierung muss die
   Platte für mindestens 0,5 Sekunden leer erkannt worden sein. Das kann bereits
   während der Bewertungsanzeige geschehen. Ein liegen gebliebenes Objekt löst
   dadurch keine erneute Sortierung aus.

Unbekannte Klassen ohne Zielzuordnung, mehrere Objekte und unsichere Ergebnisse
bewegen die Servos nicht. Bei Kamera-/Inferenzfehlern hält die Anwendung an und
zeigt eine Fehlermeldung. Ein Neustart ist dann erforderlich.

## Auf dem Raspberry Pi

Die bestehenden Systempakete für `spidev`, `RPi.GPIO`, `gpiozero`, `smbus` und
`rpicam-vid` sowie aktiviertes SPI/I²C werden weiterverwendet.

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r miss_app/requirements.txt
.venv/bin/python -m miss_app
```

Das Standardmodell ist `YOLO/pet.pt`. Auf dem Raspberry Pi wird es tatsächlich
mit Ultralytics/PyTorch geladen und auf der CPU ausgeführt. Die Kamera läuft
über den vorhandenen MJPEG-Leser mit 640 × 480, angeforderten 30 FPS und dem
vorhandenen OV5647-Sensormodus. Die KI verarbeitet jeweils aktuelle Bilder in
einem Hintergrundthread. Boxen werden auf dem zugehörigen ausgewerteten Bild
gezeichnet; die Anzeige des Kamerabilds hängt daher von der Inferenzgeschwindigkeit
ab. Countdown, Animation und Touch laufen unabhängig davon.

Die Displayinitialisierung und Touch-Eingabe nutzen die vorhandenen ST7796-/FT6336U-Treiber.
Die Bildausgabe erfolgt über einen eigenen Thread mit RGB565-Teilaktualisierungen.
Horizontales
Servo: GPIO 16; vertikales Servo: GPIO 20. Beenden am Pi mit Strg+C.

## Einstellen

`miss_app/config.json` enthält die gemeinsame Konfiguration. Alternativ:

```bash
python -m miss_app --config /pfad/zur/config.json
```

| Einstellung | Vorgabe / Bedeutung |
| --- | --- |
| `model` | `YOLO/pet.pt`, relative Pfade gelten ab Projektwurzel |
| `plate` | `[0.18, 0.16, 0.82, 0.88]`, linke/obere/rechte/untere Kante im Originalbild; 0 bis 1 |
| `routes` | Vorläufig Plastikflasche → `rf`, Aludose → `lf` |
| `labels` | Anzeigenamen der Modellklassen |
| `presence_confidence` | 0,25; ab hier zählt eine erkannte Box als anwesend |
| `sort_confidence` | 0,60; Mindestwert zum Sortieren, wird nicht angezeigt |
| `stable_seconds`, `stable_frames` | 1 Sekunde und mindestens 3 unterschiedliche Bilder |
| `stable_iou` | 0,85; nötige Überlappung mit der ersten Objektbox |
| `clear_seconds` | 0,5 Sekunden leer, bevor erneut sortiert wird |
| `feedback_seconds` | 10 Sekunden für die Bewertung |
| `max_observation_age` | 2,5 Sekunden; ältere Ergebnisse lösen keine Bewegung aus |
| `servo_settle_seconds`, `drop_seconds` | 0,7 bzw. 1,0 Sekunden aus dem bisherigen Servoablauf |
| `show_plate` | `false`; zum Einrichten die Plattenumrandung im Kamerabild einblenden |

Die Richtungen entsprechen dem bestehenden Projekt: `rf` = beide Minimum,
`lf` = horizontal Maximum / vertikal Minimum, `lb` = horizontal Minimum /
vertikal Maximum, `rb` = beide Maximum. Die Zuordnung und mittige Plattenfläche
sind zunächst Annahmen; vor dem echten Einsatz am Aufbau ausrichten und die
Bewegungszeiten prüfen.

Eine stabile Box innerhalb der Plattenfläche ist eine kamerabasierte Annäherung
an „liegt auf der Platte“. Sie misst weder Höhe noch Gewicht. Nicht erkannte
oder verdeckte zusätzliche Gegenstände können damit nicht zuverlässig gezählt
werden. Falls das zwingend sicher festgestellt werden muss, ist zusätzliche
Sensorik oder eine entsprechend trainierte Belegungserkennung nötig.

## Bewertungen

`miss_app/data/feedback.jsonl` enthält im Hardwaremodus pro abgeschlossener
Sortierung ein `sorted`-Ereignis und bei Bewertung/Timeout ein `feedback`-Ereignis.
Beide enthalten dieselbe Vorgangs-ID, Klasse, Richtung und UTC-Zeit. `correct`
ist `true`, `false` oder `null` für unbeantwortet. Diese Bewertung bestätigt die
erkannte Klasse; sie misst nicht, ob das Objekt mechanisch im richtigen Fach
gelandet ist. Ein Daumen nach unten trainiert das Modell nicht automatisch um.

Die Simulation schreibt separat nach `Simulation/data/miss/feedback.jsonl` und
kennzeichnet ihre Einträge mit `simulated: true`.

## Tests

```powershell
python -m unittest discover -s miss_app/tests -v
python -m unittest discover -s Simulation -p "test_*.py" -v
python -m unittest discover -s display-cam-gui -p test_live_detection.py -v
```

Die Tests prüfen die Ablauflogik, Mehrfachobjekte, Plattenränder, Stillstand,
veraltete Bilder, Wiederanlaufsperre, Servoreihenfolge, Countdown, Bewertungen
und die Integration mit den vorhandenen Testoberflächen. Echte Mechanik und
Erkennungsqualität müssen anschließend am Raspberry Pi geprüft werden.
