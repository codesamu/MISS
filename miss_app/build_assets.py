"""Reproduce the small, original animation atlases; no external art dependencies."""

from pathlib import Path

from PIL import Image

from .view import POSES, mesh_sprite


def main():
    destination = Path(__file__).with_name("assets")
    destination.mkdir(exist_ok=True)
    for name, label in (("bottle", "plastic-bottle"), ("can", "aluminum-can")):
        sheet = Image.new("RGBA", (12 * 156, 8 * 176))
        for phase in range(POSES):
            sheet.paste(mesh_sprite(label, phase), ((phase % 12) * 156, (phase // 12) * 176))
        path = destination / f"{name}.png"
        sheet.save(path, optimize=True)
        print(f"{path}: {POSES} Posen")


if __name__ == "__main__":
    main()
