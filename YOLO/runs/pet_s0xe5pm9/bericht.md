# Trainingsbericht PET

- Ultralytics-Version: 8.4.144
- Startmodell: yolo26n.pt (vortrainiert)
- Aufgabe: Objekterkennung; Klasse 0 = PET
- Angeforderte Epochen: 30
- Bildgroesse: 640; Batch: 8; Workers: 0; Seed: 42
- Aufteilung: 80 % Training / 10 % Validierung / 10 % Test
- Laufzeit inklusive Test: 77.4 Minuten
- Dataset-Konfiguration: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\runs\pet_s0xe5pm9\dataset\data.yaml
- Bestes Modell dieses Laufs: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\runs\pet_s0xe5pm9\train\weights\best.pt
- Modellkopie: C:\Users\maxig\OneDrive\Desktop\smartbin\MISS\YOLO\pet.pt

## Bilder pro Teilmenge

- train: 595
- val: 74
- test: 75

## Validierung

| Metrik | Wert |
| --- | ---: |
| metrics/precision(B) | 0.9096 |
| metrics/recall(B) | 0.8746 |
| metrics/mAP50(B) | 0.9559 |
| metrics/mAP50-95(B) | 0.7227 |
| fitness | 0.7227 |

## Test

| Metrik | Wert |
| --- | ---: |
| metrics/precision(B) | 0.8623 |
| metrics/recall(B) | 0.8939 |
| metrics/mAP50(B) | 0.9513 |
| metrics/mAP50-95(B) | 0.7088 |
| fitness | 0.7088 |

## Detaildateien

- `train/args.yaml`: alle tatsaechlich verwendeten Trainingseinstellungen
- `train/results.csv`: Metriken und Verluste pro abgeschlossener Epoche
- `train/results.png`: Verlauf des Trainings
- `train/`: weitere Diagramme und Beispielbilder der Validierung
- `test/`: Diagramme und Beispielbilder der Testauswertung

Erklaerungen und Grenzen der Auswertung stehen in `YOLO/README.md`.
