"""COCO-Teilmengen train/valid/test wieder in dataset/PET zusammenfuehren."""

import argparse
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent


def merge_dataset(source, destination):
    if destination.exists():
        raise FileExistsError(
            f"Ziel existiert bereits: {destination}. "
            "Bitte einen anderen --output-Ordner angeben."
        )

    merged = None
    copies = []
    names = set()
    for split in ("train", "valid", "val", "test"):
        folder = source / split
        if not folder.is_dir():
            continue
        coco = json.loads((folder / "_annotations.coco.json").read_text(encoding="utf-8"))
        if merged is None:
            merged = {**coco, "images": [], "annotations": []}
        # Der Roboflow-Export verwendet dieselben Klassen und Lizenzen pro Split.
        for field in ("categories", "licenses"):
            if coco.get(field, []) != merged.get(field, []):
                raise ValueError(f"Unterschiedliche {field} in {split}.")

        category_ids = {category["id"] for category in coco["categories"]}
        image_ids = {}
        for img in coco["images"]:
            if img["id"] in image_ids:
                raise ValueError(f"Doppelte Bild-ID in {split}: {img['id']}")
            image_path = (folder / img["file_name"]).resolve()
            if not image_path.is_relative_to(folder.resolve()):
                raise ValueError(f"Bild liegt ausserhalb der Teilmenge: {image_path}")
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            # Split-Praefix verhindert gleiche Dateinamen zwischen Teilmengen.
            filename = f"{split}_{image_path.name}"
            if filename.casefold() in names:
                raise ValueError(f"Doppelter Dateiname: {filename}")
            names.add(filename.casefold())
            new_id = len(merged["images"])
            image_ids[img["id"]] = new_id
            merged["images"].append({**img, "id": new_id, "file_name": filename})
            copies.append((image_path, filename))

        for annotation in coco["annotations"]:
            if annotation["image_id"] not in image_ids:
                raise ValueError(f"Markierung ohne zugehoeriges Bild in {split}.")
            if annotation["category_id"] not in category_ids:
                raise ValueError(f"Unbekannte Klasse in {split}.")
            merged["annotations"].append({
                **annotation,
                "id": len(merged["annotations"]) + 1,
                "image_id": image_ids[annotation["image_id"]],
            })
        print(f"{split}: {len(coco['images'])} Bilder, {len(coco['annotations'])} Markierungen")

    if merged is None or not copies:
        raise ValueError(f"Keine COCO-Bilder in train/valid/val/test gefunden: {source}")

    # Erst nach der Pruefung schreiben. Quelldaten werden nur kopiert.
    destination.mkdir(parents=True)
    for image_path, filename in copies:
        shutil.copy2(image_path, destination / filename)
    (destination / "_annotations.coco.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Fertig: {len(copies)} Bilder, {len(merged['annotations'])} Markierungen")
    print(f"Zusammengefuehrter Datensatz: {destination}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BASE / "dataset")
    parser.add_argument("--output", type=Path, help="Standard: <source>/PET")
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.output.resolve() if args.output else source / "PET"
    try:
        merge_dataset(source, destination)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Fehler: {error}\n")


if __name__ == "__main__":
    main()
