# Trainingsbericht Smartbin

- Ultralytics-Version: 8.4.146
- Startmodell: yolo26n.pt (vortrainiert)
- Aufgabe: Objekterkennung
- Klassen: 0 = aluminum-can, 1 = plastic-bottle
- Angeforderte Epochen: 30
- Bildgroesse: 640; Batch: 8; Workers: 0; Seed: 42
- Aufteilung: 80 % Training / 10 % Validierung / 10 % Test
- Laufzeit inklusive Test: 25.6 Minuten
- Dataset-Konfiguration: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\runs\pet_jhp02naa\dataset\data.yaml
- Bestes Modell dieses Laufs: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\runs\pet_jhp02naa\train\weights\best.pt
- Modellkopie: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\pet.pt

## Bilder pro Teilmenge

- train: 1392
- val: 174
- test: 175

## Validierung

| Metrik | Wert |
| --- | ---: |
| metrics/precision(B) | 0.9572 |
| metrics/recall(B) | 0.9214 |
| metrics/mAP50(B) | 0.9708 |
| metrics/mAP50-95(B) | 0.8477 |
| fitness | 0.8477 |

## Test

| Metrik | Wert |
| --- | ---: |
| metrics/precision(B) | 0.9346 |
| metrics/recall(B) | 0.9260 |
| metrics/mAP50(B) | 0.9615 |
| metrics/mAP50-95(B) | 0.8393 |
| fitness | 0.8393 |

## Detaildateien

- `train/args.yaml`: alle tatsaechlich verwendeten Trainingseinstellungen
- `train/results.csv`: Metriken und Verluste pro abgeschlossener Epoche
- `train/results.png`: Verlauf des Trainings
- `train/`: weitere Diagramme und Beispielbilder der Validierung
- `test/`: Diagramme und Beispielbilder der Testauswertung

Erklaerungen und Grenzen der Auswertung stehen in `YOLO/README.md`.
