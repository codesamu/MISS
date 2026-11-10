# GUI und Animationen

Die Oberfläche des Hauptprogramms wurde vollständig neu gestaltet: Kameraansicht,
Sortierstatus, Bewertung, Startbild und Fehleransicht. Die früheren Test-Menüs
unter `display-cam-gui/` bleiben über `--legacy` erreichbar.

## Aktuelle Umsetzung

Während der Einzelobjektprüfung füllt sich ein kleiner Ring mit Stillhalten-Symbol.
Er zeigt die anhand neuer Kamerabilder bestätigte Wartezeit und die nötige Anzahl
an Erkennungsbildern. Die Darstellung wird weich nachgeführt; sie läuft ohne neue
Ergebnisse nicht weiter. Bewegung setzt den Ring zurück, mehrere Objekte,
unsichere Erkennung oder eine Position außerhalb der Platte blenden ihn aus.
Es werden keine Konfidenzwerte oder Prozentzahlen angezeigt. Die Sortierschwellen
und Wartezeiten bleiben unverändert.

Für die native 480×320-Ansicht sind die wichtigen Schriftgrößen angehoben:
Klassenname 34 px, Bewertungstasten 22 px, Countdown 22 px, Kameraklassen 18 px
und Bedienhinweise 19–21 px. Lange Hinweise werden zweizeilig gesetzt statt stark
verkleinert. Kleine doppelte Beschriftungen entfallen; Nebeninformationen haben
einen helleren Textton. Die Displayauflösung und der Maßstab der Vorschau bleiben
unverändert.

- Farbwelt in dunklem Petrol mit Mint-Akzenten, ruhige Typografie und dezente
  Statusanzeigen. Im Kamerabild erscheinen weiterhin keine Wahrscheinlichkeiten.
- Flasche und Dose werden aus einem selbst erzeugten, schattierten Rotationskörper
  gezeichnet. Je 96 vorberechnete Posen liegen als transparente PNG-Atlanten unter
  `assets/`. Zwischen benachbarten Posen wird interpoliert. Auf dem Pi ist dafür
  zur Laufzeit keine 3D-Berechnung nötig.
  Flasche und Dose drehen sich in vier Sekunden vollständig um ihre eigene Achse.
  Vorderseitenaufdruck, rückseitiger Barcode und der Dosenverschluss drehen mit;
  verdeckte Beschriftungen werden ausgeblendet. Der Übergang zur nächsten Runde
  ist nahtlos.
- Einblendungen mit sanftem Abbremsen, schwebende Objekte, kleine Orbitbewegung,
  neue Daumen-Buttons, Maus-Hervorhebung in der Simulation und ein Countdown-Ring.
- Statische Texte, Hintergründe, Icons und Kameraansichten werden wiederverwendet.
  Animationsphasen hängen von der Zeit ab, nicht von der Zahl gezeichneter Bilder.
- Der Bildtakt hat ein Budget von 1/60 Sekunde. Die Renderzeit wird davon abgezogen;
  sie wird nicht mehr zusätzlich zur Wartezeit gerechnet. Für dieses Budget wird
  `perf_counter` verwendet, um auch mit Python 3.12 unter Windows fein genug zu takten.
- Die Simulation erzeugt keine künstliche Pause in ihren Testvorhersagen mehr und
  verwendet dasselbe Tk-Bildobjekt erneut. Die Anzeige rechts misst die tatsächliche
  PC-Vorschau, nicht die Geschwindigkeit der KI oder des Raspberry-Pi-Displays.
- Beim Pi schreibt ein eigener Thread jeweils das neueste Bild. Überholte Bilder
  werden verworfen; sie bauen keine Warteschlange auf. Modell-Laden, Sortieren und
  Bewertung blockieren die Animation nicht.

`display.py` verwendet weiterhin die ST7796-Initialisierung des vorhandenen
Treibers. Der neue Ausgabepfad wandelt Bilder in RGB565 um, vergleicht 32×32-Pixel-
Bereiche und sendet nur geänderte Rechtecke. Unveränderte Bilder werden nicht
erneut gesendet. Ein vollständiges Querformatbild wird einmal übertragen; die
doppelte Übertragung des bisherigen `show_image()`-Pfads entfällt. Fenstergrenzen
sind inklusive und enden maximal bei Pixel 479/319.

Wenn vorhanden, nimmt `spidev.writebytes2()` den Byte-Puffer direkt entgegen und
teilt ihn nach Bedarf in Betriebssystem-Puffer auf. Für ältere Installationen ist
ein 4096-Byte-Fallback vorhanden. Siehe [py-spidev](https://github.com/doceme/py-spidev).

## Messung und Grenzen

Auf dem Entwicklungs-PC wurde die Tk-Vorschau bei doppelter Displaygröße mit
etwa 59 FPS geprüft. Das ist keine Messung am Raspberry Pi. Die reproduzierbare
Vorschau und Messung erstellt man mit:

```powershell
python -m miss_app.preview
```

Unter `Simulation/screenshots/` entstehen eine Übersicht, ein animiertes WebP
und `render-benchmark.json`. Der Benchmark misst die reine CPU-Zeichenzeit und
mit einem Testtreiber die übertragenen Bilddaten. Tatsächliche SPI-Wartezeit,
GPIO-Kommandos und Inferenzleistung sind darin nicht enthalten.

Bei 40 MHz und RGB565 benötigt ein vollständiges 480×320-Bild 307.200 Bytes.
Das ergibt allein für die Pixel theoretisch rund 61,4 ms, also maximal etwa
16,3 vollständige Bilder pro Sekunde vor weiterem Overhead. Ein anderes
GUI-Framework hebt diese Übertragungsgrenze nicht auf. Kleine Änderungen an
Objekt, Countdown und Buttons benötigen deutlich weniger Daten; das macht
Teilaktualisierungen für dieses Display besonders hilfreich. Echte Bildrate und
Bildaufbau müssen am ST7796 geprüft werden. Der Kameraausschnitt wird weiterhin
mit dem dazugehörigen ausgewerteten Bild gezeigt; seine Aktualisierung hängt
von YOLO ab, die Animation der Oberfläche nicht.

Die 0,2-Sekunden-Überblendung ändert keine Workflow-Fristen. Bewertungstasten
werden erst nach der Einblendung angenommen, damit ein Tipp auf die vorherige
Ansicht nicht versehentlich bewertet. Die Rückkehr zum Kamerabild beginnt direkt
bei Bewertung oder Timeout; es wird keine zusätzliche Bestätigungsseite eingeführt.

Nach einem Bewertungstipp folgt eine 0,42 Sekunden lange Druckanimation: Der
gewählte Daumen federt ein und zurück, leuchtet in Mint beziehungsweise Rosé auf
und erhält einen kurzen Impulsring. Der andere Button wird abgedunkelt. Zum Ende
bleibt die Ergebnisansicht insgesamt 1,5 Sekunden nach dem Tipp sichtbar und zeigt
„Bewertung gespeichert“. In den letzten 0,25 Sekunden blendet sie zum Kamerabild.
Die Stimme wird bereits beim Tipp gespeichert. Kamera und KI laufen weiter;
ein neuer Gegenstand wird erst nach dieser kurzen Ergebnisanzeige zur Sortierung
geprüft. Bei
einem Timeout wird keine Daumenanimation ausgelöst.

## Alternativen zu Pillow

| Lösung | Eignung für MISS | Umstellung |
| --- | --- | --- |
| **LVGL** | Meine erste Wahl für eine spätere, auf das SPI-Touchdisplay zugeschnittene Embedded-GUI. Unterstützt Teil-Rendering und einen eigenen Flush-Callback für die Displayausgabe. | Neuer Display-/Touch-Port und Anbindung an den Python-Workflow nötig. Die dokumentierten Python-Bindings verwenden MicroPython; das ist kein direkter Ersatz für den vorhandenen CPython-/PyTorch-Prozess. |
| **Qt Quick / QML** | Meine erste Wahl bei einem Wechsel zu einer GPU-gestützten Bildschirmoberfläche, etwa mit einem passenden HDMI-/DRM-Display. Bietet Szenengraph, Animationen und GPU-Rendering. | Neue Oberfläche und Displayanbindung. Der aktuelle Python-SPI-Treiber ist kein Qt-Bildschirmbackend; eine zusätzliche Offscreen-/Kopierlösung würde die SPI-Grenze weiter behalten. |
| **Optimiertes Pillow** | Passt zur vorhandenen Pi-/Python-/ST7796-Anbindung und lässt sich bereits heute mit derselben Oberfläche simulieren. | Bereits umgesetzt. Zeichen- und SPI-Ausgabe bleiben CPU-/Bus-basiert. |

LVGL beschreibt [Teil-Rendering und Flush-Callbacks](https://lvgl.io/docs/open/9.4/details/main-modules/display/setup)
sowie seine [MicroPython-Bindings](https://github.com/lvgl/lv_binding_micropython).
Qt beschreibt den [GPU-basierten Qt-Quick-Szenengraphen](https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph.html).
Die Einschätzung der nötigen MISS-Integration ergibt sich aus diesen Schnittstellen
und dem aktuellen Projektcode.

Für den bestehenden Aufbau bleibt die optimierte Ausgabe deshalb vorerst erhalten.
Die Ablauflogik in `core.py` ist von `view.py` getrennt und kann später auch mit
LVGL oder QML verbunden werden.

## Grafiken reproduzieren

```powershell
python -m miss_app.build_assets
```

Die beiden Atlanten werden ausschließlich aus dem projektinternen Zeichen-Code
erzeugt. Dafür sind keine Bildgeneratoren, Downloads oder 3D-Bibliotheken nötig.
