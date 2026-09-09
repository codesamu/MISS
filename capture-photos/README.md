# Automatische Fotoaufnahme

Das Programm zeigt das aktuelle Kamerabild auf dem 480x320-Touchdisplay an und
speichert alle fuenf Sekunden ein Foto. Die Aufnahme endet, sobald auf dem
Display **STOP** gedrueckt wird.

## Start

Im Projektordner ausfuehren:

```bash
python3 glatz/main.py
```

Vor dem Start muss die bisherige Kamera-App beziehungsweise das Dashboard
vollstaendig beendet sein, da Kamera, Display und Touch nicht von zwei
Programmen gleichzeitig verwendet werden koennen.

Die JPEG-Bilder werden standardmaessig unter `glatz/photos/` abgelegt. Ihre
Dateinamen enthalten Datum und Uhrzeit, zum Beispiel
`muell_20260901_143012_123.jpg`.

Optional lassen sich Zielordner und Intervall aendern:

```bash
python3 glatz/main.py --output-dir /pfad/zu/fotos --interval 5
```

Die Kamera wird fest im 4:3-Modus 1296x972 betrieben. Bei der verbauten OV5647
verwendet dieser Modus den kompletten 2592x1944-Sensorbereich und damit das volle
Sichtfeld. Die Vorschau wird mit schwarzen Seitenraendern eingepasst, damit auch
auf dem 16:9-Bildbereich des Displays nichts abgeschnitten wird.

Das Programm verwendet die bereits im Projekt vorhandenen Display- und
Touch-Treiber aus `display-cam-gui/`. Labeling oder Klassifizierung findet nicht
statt.
