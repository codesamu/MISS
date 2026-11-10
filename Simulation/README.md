# MISS-Hauptprogramm am PC simulieren

Standardmäßig startet jetzt das eigentliche [MISS-Hauptprogramm](../miss_app/README.md):
Kamerabild → Einzelobjekt prüfen → sortieren → animierte Klassenanzeige mit
Daumenbewertung und 10-Sekunden-Timer → zurück zum Kamerabild.

Die neue Studio-Vorschau zeigt dieselbe moderne GUI wie das Hauptprogramm.
Animationen laufen unabhängig von den Testvorhersagen; die FPS-Anzeige rechts
misst nur das PC-Fenster. Mit `python -m miss_app.preview` lassen sich eine
Übersicht und eine animierte WebP-Vorschau exportieren.

```powershell
python Simulation/main.py
# Alternativ:
python -m miss_app --simulate
```

Kamera und KI liefern weiterhin Testdaten. Die gemeinsame Ablauflogik und
Darstellung aus `miss_app/` laufen auch im Hardwaremodus. Rechts können
Mehrfachobjekte, Plattenränder, Unsicherheit und ein nach der Sortierung liegen
gebliebener Gegenstand ausprobiert werden. Testbewertungen werden unter
`Simulation/data/miss/feedback.jsonl` gespeichert.

## Bisherige Testoberfläche

Die nachfolgend beschriebene Oberfläche öffnet man mit `--legacy`:

Im Projektordner starten:

```powershell
python -m pip install -r Simulation/requirements.txt
python Simulation/main.py --legacy
```

Unter Windows öffnet `Start-Simulation.bat` das neue Hauptprogramm. Python muss im
PATH verfügbar sein. Tkinter gehört zur üblichen Windows-Python-Installation;
unter Linux gegebenenfalls das Systempaket `python3-tk` installieren.
Die Vorschau startet standardmäßig mit nativen 480 × 320 Pixeln ohne Vergrößerung.
Unter Windows wird eine zusätzliche Bitmap-Skalierung durch die DPI-Einstellung
verhindert. Bei Bedarf vergrößern: `python Simulation/main.py --scale 2`.
1:1-Pixel entsprechen nicht automatisch den Zentimetern des echten Displays;
diese hängen von der Pixeldichte des PC-Monitors ab.

Die Simulation lädt die **bestehenden GUI-Dateien** aus `display-cam-gui/` und
`capture-photos/`. Ihre Oberflächen und Menüabläufe bleiben erhalten. Änderungen
an diesen GUI-Dateien werden beim nächsten Start auch in der Simulation sichtbar.
Es werden keine Raspberry-Pi-Treiber importiert und keine Servos angesteuert.
Alles neu Hinzugefügte liegt in `Simulation/`; der Simulator benötigt das restliche
Projekt als Quelle der vorhandenen Oberflächen.

## Bedienung

- Links ist das originale Display mit 480 × 320 Bildpunkten in nativer Größe.
  Ein Mausklick entspricht einem Fingertipp.
- Im Dashboard lassen sich Kamera, Servosteuerung, Fotoaufnahme und Live-Erkennung
  öffnen. Die üblichen Zurück-/Beenden-Buttons führen durch die vorhandenen Menüs.
- Mit `Esc` oder **Zum Dashboard** lässt sich eine Unteranwendung verlassen.
  Das Schließen des Fensters beendet die gesamte Simulation.
- Rechts lassen sich Plastikflasche, Aludose, beide oder eine leere Szene wählen.
  Die Erkennungssicherheit beeinflusst die simulierten KI-Ergebnisse. So lassen
  sich die vorhandenen Erkennungsschwellen und die Stabilisierung ausprobieren.
- **Eigenes Kamerabild laden** ersetzt die Demokamera durch ein Standbild. Bei
  eigenen Bildern werden keine Erkennungen erfunden. Über die Szenenauswahl
  gelangt man zurück zu den Demogegenständen.
- Die Servoanwendung zeigt die simulierten Positionen für GPIO 16 und 20 rechts an.
- Screenshots enthalten exakt die 480 × 320 Pixel des Displayinhalts.

## Daten und Grenzen

Testfotos, Kameraeinstellungen und Kategorien werden ausschließlich unter
`Simulation/data/` gespeichert, Screenshots unter `Simulation/screenshots/`.
Die Statistik der Kamera-App zählt diese Testfotos. Die vorhandene
`display-cam-gui/settings.json` und die echten Datensätze werden nicht verändert.

Kamera und **KI sind Testdoubles**: Es wird kein YOLO-Modell geladen. Die vorhandene
Modellauswahl verwendet die im Projekt vorhandenen Gewichtsdateien, aber alle
Einträge liefern dieselben simulierten Klassen `aluminum-can` und `plastic-bottle`.
Die Boxen und Erkennungswerte stammen aus der gewählten Demoszene. PyTorch,
Ultralytics, OpenCV und GPIO-Pakete sind für die Simulation nicht erforderlich.

Diese Simulation prüft Darstellung, Navigation, Fotoabläufe und Reaktionen auf
Testeingaben. Sie misst weder echte KI-Qualität noch SPI-Bildrate, Touch-Latenz
oder mechanische Servobewegungen. Die vorhandenen Bedienabläufe, einschließlich
Wartezeiten und Layouts, werden übernommen; Windows verwendet bei fehlenden
DejaVu-Schriften eine Ersatzschrift. Automatische Sortierung wurde nicht ergänzt.

## Aufbau und Prüfung

- `main.py`: PC-Fenster, Mausbedienung und Testregler.
- `adapters.py`: Ersatz für Display, Touch, Kamera, Servos und Modell.
- `runtime.py`: Lädt die bestehenden Apps und lenkt ihre Hardwarezugriffe und
  Schreibpfade im Simulationsprozess um. Originaldateien werden nicht geändert.

```powershell
python -m unittest discover -s Simulation -p "test_*.py" -v
```
