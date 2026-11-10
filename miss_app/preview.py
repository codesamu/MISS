"""Export a review sheet, animated preview and local render/transfer measurements."""

import json
from pathlib import Path
import statistics
import time
from types import SimpleNamespace

from PIL import Image, ImageDraw

from .config import Config, PROJECT
from .core import Detection, State, Workflow
from .view import Renderer, center, feedback, render


def main():
    output = PROJECT / "Simulation" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    config = Config()
    machine = SimpleNamespace(state=State.LIVE, selected="plastic-bottle", message="",
                              feedback_started=0, deadline=10)
    camera = Image.new("RGB", (640, 480), "#243940")
    d = ImageDraw.Draw(camera)
    d.rounded_rectangle((115, 77, 525, 422), radius=22, fill="#31484b", outline="#617777", width=2)
    box = Detection("plastic-bottle", .9, (.32, .25, .49, .8))
    # Use the same packaged art as a camera stand-in, clearly separate from YOLO.
    from .view import object_sprite
    sprite = object_sprite("plastic-bottle", 14).resize((210, 248), Image.Resampling.LANCZOS)
    camera.paste(sprite, (150, 100), sprite)
    scenes = [("01 / BEREIT", render(camera, [box], machine, config, 0))]
    machine.state = State.SORTING
    scenes.append(("02 / SORTIERUNG", render(camera, [box], machine, config, .6)))
    machine.state = State.FEEDBACK
    scenes.append(("03 / PLASTIKFLASCHE", feedback(machine, config, 1.4)))
    animation = [feedback(machine, config, i / 30) for i in range(120)]
    animation[0].save(output / "MISS-Animation.webp", save_all=True, append_images=animation[1:],
                      duration=33, loop=0, quality=88, method=4)
    machine.selected = "aluminum-can"
    scenes.append(("04 / ALUDOSE", feedback(machine, config, 1.4)))
    machine.state = State.FAULT
    scenes.append(("05 / SYSTEMPAUSE", render(camera, [], machine, config, 0)))
    scenes.append(("06 / START", render(None, [], SimpleNamespace(state=State.LIVE), config, .4)))
    sheet = Image.new("RGB", (1020, 1120), "#101c24")
    draw = ImageDraw.Draw(sheet)
    center(draw, (510, 31), "MISS / Interface & Motion", 22, bold=True)
    for index, (caption, image) in enumerate(scenes):
        x, y = 20 + (index % 2) * 500, 78 + (index // 2) * 346
        draw.text((x, y - 21), caption, fill="#91f0cf")
        sheet.paste(image, (x, y))
        image.save(output / (caption[:2] + "-MISS.png"))
    sheet.save(output / "MISS-GUI-Uebersicht.png")

    check = Workflow(config, SimpleNamespace(start=lambda *args: None))
    check_renderer, check_frames = Renderer(), []
    for index in range(45):
        now = index / 30
        if index % 3 == 0:
            check.observe([box], now, index, now)
        check_frames.append(check_renderer.render(camera, [box], check, config, now))
    check_frames[18].save(output / "MISS-Erkennungsfortschritt.png")
    check_frames[0].save(output / "MISS-Erkennungsfortschritt.webp", save_all=True,
                         append_images=check_frames[1:], duration=33, loop=0, quality=88, method=4)

    for correct, name in ((True, "hoch"), (False, "runter")):
        machine.state, machine.selected = State.FEEDBACK, "plastic-bottle"
        click_renderer = Renderer()
        click_frames = []
        for index in range(90):
            now = 1 + index / 30
            if index == 10:
                click_renderer.acknowledge(correct, now)
                machine.state = State.LIVE
            click_frames.append(click_renderer.render(camera, [box], machine, config, now))
        click_frames[0].save(output / f"MISS-Daumen-{name}.webp", save_all=True,
                             append_images=click_frames[1:], duration=33, loop=0, quality=88, method=4)

    machine.state, machine.selected = State.FEEDBACK, "plastic-bottle"
    renderer = Renderer()
    samples = []
    for index in range(180):
        start = time.perf_counter()
        renderer.render(camera, [box], machine, config, index / 60)
        samples.append((time.perf_counter() - start) * 1000)
    result = {"render_ms_median": round(statistics.median(samples), 3),
              "render_ms_p95": round(sorted(samples)[int(len(samples) * .95)], 3),
              "frames": len(samples), "note": "Local CPU rendering only; not measured LCD FPS."}
    try:
        from .display import DamageDisplay
        driver = SimpleNamespace(command=lambda *a: None, data=lambda *a: None,
                                 set_windows=lambda *a: None, digital_write=lambda *a: None,
                                 SPI=SimpleNamespace(writebytes2=lambda payload: None))
        display = DamageDisplay(driver)
        for image in animation:
            display.show_image(image)
        result["SPI_simulated_bytes_per_frame"] = round(display.bytes_sent / len(animation))
        result["SPI_previous_duplicate_full_frame_bytes"] = 480 * 320 * 2 * 2
    except ImportError:
        pass
    (output / "render-benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(output / "MISS-GUI-Uebersicht.png")
    print(output / "MISS-Animation.webp")


if __name__ == "__main__":
    main()
