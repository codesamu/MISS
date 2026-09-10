"""PET-Daten aufteilen, COCO-Boxen konvertieren und YOLO trainieren."""

import argparse
import json
import random
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "dataset" / "PET"


def prepare_data():
    coco = json.loads((SOURCE / "_annotations.coco.json").read_text(encoding="utf-8"))
    pet_id = next(c["id"] for c in coco["categories"] if c["name"] == "PET")
    images = sorted(coco["images"], key=lambda img: img["id"])
    if len(images) < 10:
        raise ValueError("Mindestens 10 Bilder fuer den 80/10/10-Split erforderlich.")
    for img in images:
        if not (SOURCE / img["file_name"]).is_file():
            raise FileNotFoundError(SOURCE / img["file_name"])

    annotations = defaultdict(list)
    for annotation in coco["annotations"]:
        if annotation["category_id"] == pet_id:
            annotations[annotation["image_id"]].append(annotation)

    random.Random(42).shuffle(images)
    train_end = int(len(images) * 0.8)
    val_end = train_end + int(len(images) * 0.1)
    splits = {
        "train": images[:train_end],
        "val": images[train_end:val_end],
        "test": images[val_end:],
    }

    # Jeder Aufruf bekommt einen eigenen Ordner. Originaldaten bleiben erhalten.
    (BASE / "runs").mkdir(exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="pet_", dir=BASE / "runs"))
    dataset = run / "dataset"
    for split, items in splits.items():
        image_dir = dataset / "images" / split
        label_dir = dataset / "labels" / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        for img in items:
            source = SOURCE / img["file_name"]
            # Bild-ID als Dateiname verhindert Namenskollisionen.
            shutil.copy2(source, image_dir / f"{img['id']}{source.suffix}")
            labels = []
            for annotation in annotations[img["id"]]:
                x, y, w, h = annotation["bbox"]
                width, height = img["width"], img["height"]
                # COCO: linke obere Ecke; YOLO: normierter Mittelpunkt.
                labels.append(
                    f"0 {(x + w / 2) / width:.6f} {(y + h / 2) / height:.6f} "
                    f"{w / width:.6f} {h / height:.6f}"
                )
            (label_dir / f"{img['id']}.txt").write_text(
                "\n".join(labels), encoding="utf-8"
            )
        print(f"{split}: {len(items)} Bilder")

    data_yaml = dataset / "data.yaml"
    data_yaml.write_text(
        f"path: {json.dumps(dataset.as_posix())}\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: PET\n",
        encoding="utf-8",
    )
    print(f"Daten: {data_yaml}")
    return run, data_yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--split-only", action="store_true", help="Nur Daten vorbereiten")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs muss mindestens 1 sein")

    if not args.split_only:
        import ultralytics
        from ultralytics import YOLO

    run, data_yaml = prepare_data()
    if args.split_only:
        return

    started = time.perf_counter()
    model = YOLO("yolo26n.pt")
    model.train(
        data=str(data_yaml), epochs=args.epochs, imgsz=640, batch=8,
        workers=0, seed=42, project=str(run), name="train",
    )
    best = Path(model.trainer.best)
    shutil.copy2(best, BASE / "pet.pt")
    validation = dict(model.metrics.results_dict)
    test = YOLO(str(best)).val(
        data=str(data_yaml), split="test", workers=0,
        project=str(run), name="test",
    )
    report = [
        "# Trainingsbericht PET\n",
        f"- Ultralytics-Version: {ultralytics.__version__}",
        "- Startmodell: yolo26n.pt (vortrainiert)",
        "- Aufgabe: Objekterkennung; Klasse 0 = PET",
        f"- Angeforderte Epochen: {args.epochs}",
        "- Bildgroesse: 640; Batch: 8; Workers: 0; Seed: 42",
        "- Aufteilung: 80 % Training / 10 % Validierung / 10 % Test",
        f"- Laufzeit inklusive Test: {(time.perf_counter() - started) / 60:.1f} Minuten",
        f"- Dataset-Konfiguration: {data_yaml}",
        f"- Bestes Modell dieses Laufs: {best}",
        f"- Modellkopie: {BASE / 'pet.pt'}\n",
        "## Bilder pro Teilmenge\n",
    ]
    for split in ("train", "val", "test"):
        count = len(list((data_yaml.parent / "images" / split).iterdir()))
        report.append(f"- {split}: {count}")
    for title, metrics in (("Validierung", validation), ("Test", test.results_dict)):
        report.extend([f"\n## {title}\n", "| Metrik | Wert |", "| --- | ---: |"])
        report.extend(f"| {key} | {float(value):.4f} |" for key, value in metrics.items())
    report.extend([
        "\n## Detaildateien\n",
        "- `train/args.yaml`: alle tatsaechlich verwendeten Trainingseinstellungen",
        "- `train/results.csv`: Metriken und Verluste pro abgeschlossener Epoche",
        "- `train/results.png`: Verlauf des Trainings",
        "- `train/`: weitere Diagramme und Beispielbilder der Validierung",
        "- `test/`: Diagramme und Beispielbilder der Testauswertung",
        "\nErklaerungen und Grenzen der Auswertung stehen in `YOLO/README.md`.",
    ])
    (run / "bericht.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Fertig! Modell: {BASE / 'pet.pt'}")
    print(f"Trainingsbericht: {run / 'bericht.md'}")


if __name__ == "__main__":
    main()
