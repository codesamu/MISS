# Trainingsbericht PET

- Ultralytics-Version: 8.4.146
- Startmodell: yolo26n.pt (vortrainiert)
- Aufgabe: Objekterkennung; Klasse 0 = PET
- Angeforderte Epochen: 30
- Bildgroesse: 640; Batch: 8; Workers: 0; Seed: 42
- Aufteilung: 80 % Training / 10 % Validierung / 10 % Test
- Laufzeit inklusive Test: 14.9 Minuten
- Dataset-Konfiguration: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\runs\pet_y1ses821\dataset\data.yaml
- Bestes Modell dieses Laufs: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\runs\pet_y1ses821\train\weights\best.pt
- Modellkopie: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\pet.pt

## Bilder pro Teilmenge

- train: 595
- val: 74
- test: 75

## Validierung

| Metrik | Wert |
| --- | ---: |
| metrics/precision(B) | 0.9109 |
| metrics/recall(B) | 0.8869 |
| metrics/mAP50(B) | 0.9572 |
| metrics/mAP50-95(B) | 0.7236 |
| fitness | 0.7236 |

## Test

| Metrik | Wert |
| --- | ---: |
| metrics/precision(B) | 0.8858 |
| metrics/recall(B) | 0.8575 |
| metrics/mAP50(B) | 0.9467 |
| metrics/mAP50-95(B) | 0.7031 |
| fitness | 0.7031 |

## Detaildateien

- `train/args.yaml`: alle tatsaechlich verwendeten Trainingseinstellungen
- `train/results.csv`: Metriken und Verluste pro abgeschlossener Epoche
- `train/results.png`: Verlauf des Trainings
- `train/`: weitere Diagramme und Beispielbilder der Validierung
- `test/`: Diagramme und Beispielbilder der Testauswertung

Erklaerungen und Grenzen der Auswertung stehen in `YOLO/README.md`.
