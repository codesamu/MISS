# Plastikflaschen und Aludosen trainieren

## Neuen Datensatz wieder zusammenfuehren

Wenn der COCO-Export bereits in `dataset/train`, `dataset/valid` (oder `val`)
und `dataset/test` aufgeteilt ist, im Ordner `YOLO` ausfuehren:

```powershell
python merge_dataset.py
```

Das Programm kopiert alle Bilder nach `dataset/PET` und erstellt dort eine
gemeinsame `_annotations.coco.json`. Bild- und Markierungs-IDs werden eindeutig
neu vergeben; die Zuordnung der Markierungen zu ihren Bildern bleibt erhalten.
Dateinamen bekommen den bisherigen Split als Praefix, etwa `train_bild.jpg`.
Boxen, Klassen, Lizenzen und weitere Metadaten bleiben erhalten.

Der neue Export enthaelt 1741 Bilder und 4478 Markierungen fuer Plastikflaschen
(`plastic-bottle`) und Aludosen (` aluminum-can`). Der Zielordner heisst wie
bisher `PET`, enthaelt aber **beide Klassen**. Die urspruenglichen Teilmengen
werden nicht geloescht. Ein vorhandener Zielordner wird nicht ueberschrieben.
Das Skript benoetigt nur Python, keine zusaetzlichen Bibliotheken.

Andere Ordner lassen sich so angeben:

```powershell
python merge_dataset.py --source "pfad/zum/export" --output "pfad/zum/gesamt"
```

Die Zusammenfuehrung hebt die bisherige Trennung der Testdaten auf. Ein spaeterer
neuer Split ist deshalb eine neue Versuchsaufteilung.

## Training starten

Im Terminal im Ordner `YOLO` ausfuehren:

```powershell
python -m pip install -r requirements.txt
python train.py
```

Das Skript liest `dataset/PET/_annotations.coco.json`, wandelt die Boxen ins
YOLO-Format um und teilt die Bilder reproduzierbar in 80 % Training,
10 % Validierung und 10 % Test. Anschliessend trainiert es YOLO26n fuer
30 Epochen und wertet das beste Modell auf den Testbildern aus.
Beim ersten Training wird das vortrainierte Modell heruntergeladen.

Das fertige Modell liegt unter `YOLO/pet.pt` (wird beim naechsten Training
ersetzt). Jeder Aufruf legt einen eigenen Ordner unter `YOLO/runs/` fuer
Datenkopien und Ergebnisse an. Die Originaldaten bleiben erhalten.
Der Modellname `pet.pt` bleibt aus Kompatibilitaetsgruenden bestehen;
das neu trainierte Modell erkennt beide Klassen.

Optional:

```powershell
python train.py --epochs 50
python train.py --split-only
```

`--split-only` funktioniert auch ohne installierte Trainingsbibliotheken.

Ein Bild mit dem trainierten Modell pruefen:

```powershell
yolo predict model=pet.pt source="pfad/zum/bild.jpg" save=True
```

Training und Auswertung verwenden die [Ultralytics-API](https://docs.ultralytics.com/tasks/detect/).

## Dataset und Vorbereitung

Das zusammengefuehrte Dataset enthaelt 1741 Bilder und 4478 Markierungen.
Die Markierungen stehen im COCO-Format in `_annotations.coco.json`.
Das Training uebernimmt automatisch alle Klassen mit Markierungen und vergibt
fortlaufende YOLO-Klassen-IDs. Leerzeichen am Rand der Klassennamen werden entfernt:

| COCO-ID | YOLO-ID | Klasse |
| --- | --- | --- |
| 1 | 0 | `aluminum-can` (Aludose) |
| 2 | 1 | `plastic-bottle` (Plastikflasche) |

Die unbenutzte Oberkategorie `smartbin` wird nicht als Erkennungsklasse trainiert.

Eine COCO-Box beschreibt `x, y, Breite, Hoehe` in Pixeln, wobei `x, y` die
linke obere Ecke angeben. Eine YOLO-Labelzeile enthaelt dagegen:

```text
Klasse Mittelpunkt_X Mittelpunkt_Y Breite Hoehe
```

Alle vier Koordinaten werden durch die jeweilige Bildbreite bzw. Bildhoehe
geteilt. Sie liegen damit zwischen 0 und 1. Fuer jedes markierte Objekt entsteht
eine Zeile; Bilder ohne Markierung erhalten eine leere Labeldatei.

Die Bilder werden nach ID sortiert und mit Seed 42 gemischt. Beim aktuellen
Dataset entstehen 1392 Trainingsbilder, 174 Validierungsbilder und 175 Testbilder.
Der Rundungsrest geht in die Testmenge. Jedes Bild gehoert genau einer Menge an:

| Teilmenge | Verwendung |
| --- | --- |
| Training | Anpassung der Modellgewichte |
| Validierung | Kontrolle nach den Epochen und Auswahl des besten Modells |
| Test | Abschliessende Auswertung des besten Modells auf zurueckgehaltenen Bildern |

Bei unveraenderten Quelldaten bleibt die Aufteilung bei jedem Aufruf gleich.
Das Training selbst kann je nach Hardware und Bibliotheksversion leicht
unterschiedliche Ergebnisse liefern.

## Trainingseinstellungen

| Einstellung | Wert | Bedeutung |
| --- | --- | --- |
| Modell | `yolo26n.pt` | Kleines vortrainiertes Modell als Ausgangspunkt |
| Epochen | 30 | Angeforderte Durchlaeufe durch die Trainingsdaten; mit `--epochs` aenderbar |
| Bildgroesse | 640 | Zielgroesse fuer die Bildaufbereitung; Originaldateien bleiben unveraendert |
| Batch | 8 | Bilder pro Trainingsschritt |
| Workers | 0 | Laden der Daten im Hauptprozess, einfach unter Windows |
| Seed | 42 | Zufallsstartwert fuer Split und Training |
| Geraet | automatisch | Ultralytics waehlt das verfuegbare Geraet |

Weitere Einstellungen wie Optimierer, Lernrate, Datenaugmentation und vorzeitiges
Beenden verwenden die Standardwerte der installierten Ultralytics-Version.
Die konkret aufgeloesten Werte werden in `train/args.yaml` gespeichert.
Die tatsaechlich abgeschlossenen Epochen stehen in `train/results.csv`.
Auf der CPU kann das Training deutlich laenger dauern als auf einer GPU.

Nach dem Training wird `weights/best.pt` als `YOLO/pet.pt` kopiert und auf der
Testmenge ausgewertet. `best.pt` ist das anhand der Validierung ausgewaehlte
Modell; `last.pt` enthaelt den zuletzt gespeicherten Trainingsstand.

## Automatische Dokumentation

Jeder Lauf erhaelt unter `YOLO/runs/pet_.../` einen eigenen Ordner:

```text
pet_.../
  bericht.md           Zusammenfassung mit Einstellungen, Laufzeit und Metriken
  dataset/
    data.yaml          Dataset-Pfad, Teilmengen und Klassennamen
    images/            Bilder in train/, val/ und test/
    labels/            Passende YOLO-Labels in train/, val/ und test/
  train/
    args.yaml          Vollstaendige Trainingseinstellungen
    results.csv        Verluste und Metriken pro Epoche
    results.png        Diagramme zum Trainingsverlauf
    weights/
      best.pt          Bestes Modell nach Validierung
      last.pt          Zuletzt gespeicherter Trainingsstand
  test/                Diagramme und Beispielbilder der Testauswertung
```

Ultralytics erzeugt zusaetzlich unter anderem Konfusionsmatrizen, Kurven zur
Erkennungsqualitaet und Bilder mit eingezeichneten Vorhersagen. Die genauen
Dateinamen haengen von der installierten Version ab. `bericht.md` wird nach
erfolgreichem Abschluss der Testauswertung geschrieben. Bei `--split-only`
entsteht nur der vorbereitete Dataset-Ordner.

## Ergebnisse verstehen

| Metrik | Bedeutung |
| --- | --- |
| Precision | Welcher Anteil der erkannten Objekte tatsaechlich korrekt ist; hoch bedeutet wenige Fehlalarme |
| Recall | Welcher Anteil der markierten Objekte gefunden wird; hoch bedeutet wenige uebersehene Objekte |
| mAP50 | Erkennungsqualitaet bei mindestens 50 % Ueberlappung (IoU) zwischen vorhergesagter und echter Box |
| mAP50-95 | Mittlere Erkennungsqualitaet ueber IoU-Schwellen von 0,50 bis 0,95; bewertet die Genauigkeit der Boxen strenger |
| Trainings-/Validierungsverlust | Fehlerfunktion beim Lernen bzw. Pruefen; kleinere Werte sind meist besser |

Precision, Recall und mAP liegen zwischen 0 und 1; groessere Werte sind besser.
Sinkender Trainingsverlust bei schlechter werdender Validierung kann auf
Ueberanpassung hinweisen. Zusaetzlich immer einige Vorhersagebilder anschauen:
Werden Flaschen oder Dosen uebersehen, verwechselt, doppelt markiert oder andere Gegenstaende erkannt?

## Grenzen der Auswertung

Der einfache Split mischt einzelne Bilder. Sehr aehnliche Bilder aus derselben
Aufnahmeserie koennen dadurch in verschiedenen Teilmengen landen und Ergebnisse
zu gut erscheinen lassen. Fuer eine belastbare Beurteilung spaeter mit neuen
Aufnahmeserien, anderen Lichtverhaeltnissen und anderen Flaschen und Dosen testen.

Das Modell lernt die Klassen Plastikflasche und Aludose. Fuer den Einsatz im
Smartbin sind auch Testbilder mit anderem Muell und ohne diese Objekte sinnvoll,
um Fehlalarme zu messen.
Die Testmenge sollte fuer die abschliessende Beurteilung dienen; Einstellungen
anhand der Validierung auswaehlen.

Fuer einen nachvollziehbaren Versuch den gesamten Laufordner zusammen mit der
verwendeten Version von `train.py` und den Originaldaten aufbewahren.
