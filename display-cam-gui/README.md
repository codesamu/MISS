# Live-Erkennung

Im Projektordner einmal einrichten (Systempakete fuer das Display mitverwenden):

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r display-cam-gui/requirements.txt
```

Direkt starten:

```bash
.venv/bin/python display-cam-gui/live-detection.py
```

Oder im Dashboard **Live-Erkennung** antippen. Beenden mit dem roten
Touch-Button unten rechts oder Strg+C. Andere Kamera-Apps vorher beenden.

Das Programm zeigt den rpicam-vid-Kamerastream auf dem ST7796-LCD (480x320).
Es verarbeitet immer das neueste verfuegbare Bild und zeichnet Ergebnisse
auf genau dieses Bild. Die Bildrate haengt von der Inferenzzeit ab; waehrend
einer Vorhersage bleibt das zuletzt ausgewertete Bild sichtbar.
Das volle 4:3-Kamerabild bleibt mit schwarzen Raendern erhalten.
Die Kamera laeuft mit 30 FPS; die KI verarbeitet davon nur die jeweils neuesten
Bilder. Die FPS-Anzeige unten misst die Geschwindigkeit der Modellauswertung.

Ohne Argument erscheint zuerst eine **Modellauswahl auf dem Touchdisplay**.
Sie zeigt `YOLO/pet.pt` und die Detection-`best.pt` aus `YOLO/runs/`
beziehungsweise `runs/detect/`, neueste zuerst. Jeder Eintrag zeigt den Namen
des Trainingslaufs. Mit **Weiter/Zurueck** blaettern und den gewuenschten Lauf
antippen. **Abbrechen** kehrt ohne Kamerastart zurueck. Das gilt auch beim
Start aus dem Dashboard. Auf dem Raspberry Pi muessen die gewuenschten
Laufordner mit `train/weights/best.pt` vorhanden sein. Die alten Modelle unter
`runs/classify/` werden absichtlich nicht mehr geladen: Eine Bildklassifikation
kann keine Objektposition und damit keine Bounding Box liefern. Fehlt ein
trainierter Detektor, beendet sich die Anwendung mit einer klaren Meldung.

Bounding Boxes, Klassenname und Confidence werden direkt auf das ausgewertete
Kamerabild gezeichnet. Klassennamen werden aus dem Modell gelesen, etwa
`aluminum-can` und `plastic-bottle`; auch alte PET-Modelle funktionieren.
Jede Klasse hat eine eigene Farbe (die Palette wiederholt sich ab fuenf Klassen).
Mehrere Klassen koennen gleichzeitig erkannt werden. Der Status oben links
wird **pro Klasse getrennt** stabilisiert: Zwei Frames hintereinander muessen mindestens
60 % erreichen. Eine aktive Erkennung bleibt bis zu vier schwache Frames
erhalten; auch die Halteschwelle liegt bei 60 %. Dadurch
springt die Anzeige bei einzelnen unsicheren Frames nicht mehr sofort zwischen
erkannt und nicht erkannt. Ohne aktive Klasse steht dort **Kein Objekt erkannt**.
Mehrere erkannte Klassen erhalten eigene Statuszeilen. Ab fuenf Klassen werden
weitere zusammengefasst; Boxen werden weiterhin fuer alle Klassen gezeichnet. API:
[Ultralytics Predict](https://docs.ultralytics.com/modes/predict/).

Modelle auflisten bzw. einen Run explizit auswaehlen:

```bash
.venv/bin/python display-cam-gui/live-detection.py --list-models
.venv/bin/python display-cam-gui/live-detection.py --model YOLO/pet.pt
.venv/bin/python display-cam-gui/live-detection.py --model YOLO/runs/pet_jhp02naa/train/weights/best.pt
```

`--model` ueberspringt die Touch-Auswahl und akzeptiert auch mehrere Pfade, die nacheinander auf demselben Bild
ausgewertet werden. Das kostet entsprechend mehr Rechenzeit.
Mit `--conf 0.6` die Einschaltschwelle und mit `--keep-conf 0.35` die niedrigere
Halteschwelle ändern. `--confirm-frames` und `--release-frames` steuern die
zeitliche Entprellung. Mit `--imgsz 320` kann die Inferenzgröße verkleinert
werden (Standard: 640); das ist schneller, kann aber Erkennungsqualität kosten.
Fuer einen kurzen Hardwaretest: `--max-frames 10`.
