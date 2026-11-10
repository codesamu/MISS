"""Cached, antialiased scenes with time-based motion, shared by LCD and desktop."""

from functools import lru_cache
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

from .core import State


SIZE = (480, 320)
UP = (16, 116, 120, 254)
DOWN = (360, 116, 464, 254)
BG = "#0a141c"
MINT = "#91f0cf"
WHITE = "#eff8f5"
MUTED = "#a8bec8"
POSES = 96


@lru_cache(maxsize=32)
def font(size, bold=False):
    names = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
             "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def center(draw, xy, text, size=16, fill=WHITE, bold=False, max_width=460):
    while size > 10 and draw.textlength(text, font=font(size, bold)) > max_width:
        size -= 1
    draw.text(xy, text, font=font(size, bold), fill=fill, anchor="mm")


def readable_lines(text, width=438, size=19, max_lines=2):
    """Wrap guidance instead of shrinking its font to fit one line."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and font(size).getlength(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        tail = lines[-1]
        while tail and font(size).getlength(tail + "…") > width:
            tail = tail[:-1]
        lines[-1] = tail.rstrip() + "…"
    return lines


def clamp(value):
    return max(0.0, min(1.0, value))


def ease(value):
    return 1 - (1 - clamp(value)) ** 3


def vote_at(point):
    if point is not None:
        x, y = point
        for bounds, value in ((UP, True), (DOWN, False)):
            if bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]:
                return value
    return None


@lru_cache(maxsize=4)
def background(kind="feedback"):
    image = Image.new("RGB", SIZE, BG)
    d = ImageDraw.Draw(image)
    for y in range(320):
        p = y / 319
        d.line((0, y, 480, y), fill=(10 + round(p * 2), 20 + round(p * 5), 28 + round(p * 5)))
    glow = Image.new("RGB", SIZE, "black")
    ImageDraw.Draw(glow).ellipse((120, 58, 360, 292), fill="#0a2828" if kind == "feedback" else "#122733")
    image = ImageChops.add(image, glow.filter(ImageFilter.GaussianBlur(48)))
    d = ImageDraw.Draw(image)
    d.line((16, 54, 464, 54), fill="#30434c")
    d.text((17, 15), "MISS", font=font(19, True), fill=WHITE)
    return image


@lru_cache(maxsize=2)
def thumb(up):
    scale = 3
    image = Image.new("RGBA", (60 * scale, 60 * scale))
    d = ImageDraw.Draw(image)
    color = "#a3efd5" if up else "#f2acae"
    pts = [(23, 48), (44, 48), (49, 44), (53, 27), (50, 23), (37, 23),
           (40, 12), (38, 7), (34, 7), (29, 21), (23, 28), (23, 48)]
    d.line([(x * scale, y * scale) for x, y in pts], fill=color, width=2 * scale, joint="curve")
    d.rounded_rectangle((8 * scale, 27 * scale, 19 * scale, 49 * scale), radius=3 * scale, outline=color, width=2 * scale)
    image = image.resize((60, 60), Image.Resampling.LANCZOS)
    return image if up else ImageOps.flip(image)


def material(color, normal, highlight=1.0):
    diffuse = 0.48 + 0.43 * max(0, normal[0] * -0.45 + normal[1] * 0.89)
    specular = max(0, normal[0] * -0.35 + normal[1] * 0.94) ** 30 * 75 * highlight
    return tuple(min(255, round(c * diffuse + specular)) for c in color)


@lru_cache(maxsize=4)
def packaging_texture(bottle, rear):
    """Small front print / back barcode that travels around the curved surface."""
    image = Image.new("RGBA", (128, 96))
    d = ImageDraw.Draw(image)
    color = "#23675d" if bottle else "#583b27"
    if rear:
        pattern = "110100101110010110100110101101001"
        for index, bar in enumerate(pattern):
            if bar == "1":
                x = 18 + index * 3
                d.rectangle((x, 17, x + 1, 63), fill=color)
        center(d, (64, 79), "PET 01" if bottle else "ALU 41", 14, color, max_width=118)
    else:
        center(d, (64, 35), "MISS", 42, color, True, 120)
        center(d, (64, 69), "01 / PET" if bottle else "41 / ALU", 16, color, max_width=116)
    return image.resize((64, 48), Image.Resampling.LANCZOS)


def curved_print(draw, project, bottle, angle, rear=False):
    texture = packaging_texture(bottle, rear)
    pixels = texture.load()
    middle = angle + (math.pi if rear else 0)
    ystart, yend = (-9, 24) if bottle else (-13, 24)
    base = (214, 237, 217) if bottle else (198, 132, 80)
    for col in range(texture.width):
        a = middle + (col / texture.width - 0.5) * 1.8
        b = middle + ((col + 1) / texture.width - 0.5) * 1.8
        normal = (math.sin((a + b) / 2), math.cos((a + b) / 2))
        if normal[1] <= 0:
            continue  # The far side is occluded by the object itself.
        backing = material(base, normal, 0.55 if bottle else 1)

        def point(theta, y):
            radius = 28 - max(0, y - 10) / 17 if bottle else 28
            return project(math.sin(theta) * radius, y, math.cos(theta) * radius)

        for row in range(texture.height):
            red, green, blue, alpha = pixels[col, row]
            if not alpha:
                continue
            foreground = material((red, green, blue), normal, 0)
            color = tuple(round((fg * alpha + bg * (255 - alpha)) / 255)
                          for fg, bg in zip(foreground, backing))
            ya = ystart + row / texture.height * (yend - ystart)
            yb = ystart + (row + 1) / texture.height * (yend - ystart)
            draw.polygon([point(a, ya), point(b, ya), point(b, yb), point(a, yb)], fill=color)


@lru_cache(maxsize=256)
def mesh_sprite(label, phase=0):
    """Shaded lathe mesh; cached poses avoid doing the 3D work every tick."""
    s = 2
    image = Image.new("RGBA", (156 * s, 176 * s))
    d = ImageDraw.Draw(image)
    bottle = "bottle" in label or "pet" in label.lower()
    can = "can" in label
    angle = (phase % POSES) / POSES * math.tau
    lean = -0.05
    if bottle:
        profile = [(-76, 12), (-70, 13), (-64, 11), (-56, 11), (-45, 23), (-37, 28),
                   (-20, 27), (-12, 28), (10, 28), (27, 27), (41, 28), (55, 27), (62, 23)]
    else:
        profile = [(-56, 23), (-53, 27), (-48, 28), (49, 28), (55, 26), (58, 23)]

    def project(x, y, z):
        yy = y - z * 0.19
        return ((78 + x * math.cos(lean) - yy * math.sin(lean)) * s,
                (92 + x * math.sin(lean) + yy * math.cos(lean)) * s)

    faces = []
    count = 40
    for index, ((ya, ra), (yb, rb)) in enumerate(zip(profile, profile[1:])):
        for j in range(count):
            a, b = j / count * math.tau + angle, (j + 1) / count * math.tau + angle
            nx, nz = math.sin((a + b) / 2), math.cos((a + b) / 2)
            corners = [(math.sin(a) * ra, ya, math.cos(a) * ra),
                       (math.sin(b) * ra, ya, math.cos(b) * ra),
                       (math.sin(b) * rb, yb, math.cos(b) * rb),
                       (math.sin(a) * rb, yb, math.cos(a) * rb)]
            if bottle:
                base = (79, 168, 176)
                if index < 2:
                    base = (65, 177, 143)
                elif -12 <= ya and yb <= 27:
                    base = (214, 237, 217)
            else:
                base = (200, 213, 222) if index != 2 else (198, 132, 80)
            color = material(base, (nx, nz), 0.55 if bottle and -12 <= ya < 27 else 1)
            faces.append((nz * (ra + rb) / 2 + (ya + yb) * 0.02, [project(*p) for p in corners], color))
    for _, polygon, color in sorted(faces, key=lambda face: face[0]):
        d.polygon(polygon, fill=color)
    ytop, radius = profile[0]
    top = [project(math.sin(j / 80 * math.tau) * radius, ytop, math.cos(j / 80 * math.tau) * radius) for j in range(80)]
    d.polygon(top, fill="#a0ebcf" if bottle else "#e1e8ec")
    if can:
        tab = []
        for index in range(40):
            theta = index / 40 * math.tau
            x, z = math.cos(theta) * 4 - 2, math.sin(theta) * 8
            tab.append(project(x * math.cos(angle) + z * math.sin(angle), ytop - 0.5,
                               z * math.cos(angle) - x * math.sin(angle)))
        d.line(tab + [tab[0]], fill="#6e818c", width=2 * s, joint="curve")
    if bottle or can:
        curved_print(d, project, bottle, angle)
        curved_print(d, project, bottle, angle, rear=True)
    if not (bottle or can):
        center(d, (78 * s, 92 * s), "?", 32 * s, WHITE, True)
    return image.resize((156, 176), Image.Resampling.LANCZOS)


@lru_cache(maxsize=2)
def _atlas(kind):
    path = Path(__file__).with_name("assets") / f"{kind}.png"
    if not path.is_file():
        return None
    with Image.open(path) as source:
        source.load()
        if source.size != (156 * 12, 176 * 8):
            raise ValueError(f"Ungültiger Animationsatlas: {path}")
        return source.convert("RGBA")


@lru_cache(maxsize=256)
def object_sprite(label, phase=0):
    kind = "bottle" if "bottle" in label or "pet" in label.lower() else "can" if "can" in label else None
    atlas = _atlas(kind) if kind else None
    if atlas is None:
        return mesh_sprite(label, phase)
    index = phase % POSES
    x, y = (index % 12) * 156, (index // 12) * 176
    return atlas.crop((x, y, x + 156, y + 176))


@lru_cache(maxsize=8)
def card(up, hover=False):
    image = Image.new("RGBA", (208, 276))
    d = ImageDraw.Draw(image)
    fill = "#183c33" if up and hover else "#35282f" if hover else "#13252c"
    outline = "#6dceb0" if up else "#bd7f88"
    d.rounded_rectangle((1, 1, 206, 274), radius=40, fill=fill, outline=outline if hover else "#2a4149", width=2)
    d.rounded_rectangle((3, 3, 204, 272), radius=38, outline="#1a3036", width=2)
    image.alpha_composite(thumb(up).resize((120, 120), Image.Resampling.LANCZOS), (44, 34))
    center(d, (104, 222), "Richtig" if up else "Falsch", 44, WHITE, True, 188)
    return image.resize((104, 138), Image.Resampling.LANCZOS)


@lru_cache(maxsize=64)
def pressed_card(up, step):
    progress = step / 31
    image = card(up, True).copy()
    draw = ImageDraw.Draw(image)
    draw.rectangle((19, 12, 87, 86), fill="#183c33" if up else "#35282f")
    wave = math.sin(math.pi * progress)
    symbol = thumb(up).rotate((-11 if up else 11) * wave,
                              resample=Image.Resampling.BICUBIC, expand=True)
    x = round(52 - symbol.width / 2)
    y = round(47 - symbol.height / 2 + (-7 if up else 5) * wave)
    image.alpha_composite(symbol, (x, y))
    draw.rounded_rectangle((1, 1, 102, 136), radius=19,
                           outline="#a3efd5" if up else "#f2acae", width=2)
    return image


def press_animation(snapshot, up, progress):
    """A brief compress/rebound and ripple, followed by the live-view transition."""
    image = snapshot.copy()
    image.paste(background().crop((416, 0, 468, 53)), (416, 0))
    image.paste(background().crop((0, 268, 480, 320)), (0, 268))
    notice = ImageDraw.Draw(image)
    center(notice, (240, 281), "Vielen Dank!", 22, WHITE, True)
    center(notice, (240, 307), "Bewertung gespeichert", 17, MUTED)
    bounds = UP if up else DOWN
    x1, y1, x2, y2 = bounds
    # Restore the backdrop so shrinking the selected card leaves no old edges.
    clear = (max(0, x1 - 14), y1 - 14, min(480, x2 + 14), y2 + 14)
    image.paste(background().crop(clear), clear[:2])
    other = DOWN if up else UP
    other_card = image.crop(other)
    image.paste(Image.blend(other_card, Image.new("RGB", other_card.size, BG), 0.38), other[:2])
    if progress < 0.2:
        scale = 1 - 0.1 * ease(progress / 0.2)
    elif progress < 0.55:
        scale = 0.9 + 0.14 * ease((progress - 0.2) / 0.35)
    else:
        scale = 1 + 0.04 * (1 - ease((progress - 0.55) / 0.45))
    sprite = pressed_card(up, min(31, round(progress * 31)))
    sprite = sprite.resize((round(104 * scale), round(138 * scale)), Image.Resampling.LANCZOS)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    image.paste(sprite, (round(cx - sprite.width / 2), round(cy - sprite.height / 2)), sprite)
    ripple = Image.new("RGBA", SIZE)
    draw = ImageDraw.Draw(ripple)
    color = (145, 240, 207) if up else (242, 172, 174)
    alpha = round(200 * (1 - progress))
    spread = round(4 + 9 * ease(progress))
    draw.rounded_rectangle((x1 - spread, y1 - spread, x2 + spread, y2 + spread),
                           radius=20 + spread, outline=(*color, alpha), width=2)
    for angle in (-135, -45, 45, 135):
        theta = math.radians(angle)
        radius = 38 + 17 * ease(progress)
        x, y = cx + math.cos(theta) * radius, y1 + 47 + math.sin(theta) * radius
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(*color, alpha))
    image.paste(ripple, (0, 0), ripple)
    return image


@lru_cache(maxsize=16)
def feedback_base(label, title):
    image = background().copy()
    d = ImageDraw.Draw(image)
    d.ellipse((304, 24, 312, 32), fill=MINT)
    d.text((323, 18), "Sortiert", font=font(17, True), fill=MINT)
    center(d, (240, 79), title, 34, WHITE, True, 440)
    d.ellipse((181, 239, 299, 256), fill="#183237", outline="#25474a", width=1)
    d.arc((166, 234, 314, 263), 8, 164, fill="#305454", width=1)
    center(d, (240, 280), "War die Erkennung richtig?", 21, WHITE)
    center(d, (240, 306), "Tippen oder warten", 17, MUTED)
    return image


@lru_cache(maxsize=32)
def counter_sprite(value):
    image = Image.new("RGBA", (40, 40))
    center(ImageDraw.Draw(image), (20, 20), str(value), 22, WHITE, True, 36)
    return image


@lru_cache(maxsize=362)
def countdown_ring(degrees):
    image = Image.new("RGBA", (104, 104))
    d = ImageDraw.Draw(image)
    d.arc((4, 4, 100, 100), -90, 270, fill="#2a424b", width=5)
    if degrees:
        d.arc((4, 4, 100, 100), -90, -90 + degrees, fill=MINT, width=5)
    return image.resize((52, 52), Image.Resampling.LANCZOS)


def stability_progress(machine, now):
    read = getattr(machine, "stability_progress", None)
    return read(now) if read else None


@lru_cache(maxsize=362)
def stability_ring(degrees):
    image = countdown_ring(degrees).copy()
    draw = ImageDraw.Draw(image)
    for x in (20, 29):
        draw.rounded_rectangle((x, 19, x + 3, 32), radius=1, fill=MINT)
    return image


def draw_stability(image, progress):
    ring = stability_ring(round(360 * clamp(progress)))
    image.paste(ring, (214, 214), ring)


def feedback(machine, config, now, pointer=None):
    image = feedback_base(machine.selected, config.labels.get(machine.selected, machine.selected)).copy()
    d = ImageDraw.Draw(image)
    remaining = max(0, machine.deadline - now)
    ring = countdown_ring(round(360 * min(1, remaining / config.feedback_seconds)))
    image.paste(ring, (416, 0), ring)
    digit = counter_sprite(math.ceil(remaining))
    image.paste(digit, (422, 6), digit)
    elapsed = max(0, now - machine.feedback_started)
    enter = ease(elapsed / 0.55)
    bob = math.sin(elapsed * 2.2) * 3
    theta = elapsed * 0.85
    px, py = 240 + math.cos(theta) * 70, 247 + math.sin(theta) * 13
    d.ellipse((px - 2, py - 2, px + 2, py + 2), fill="#83d8bf")
    pose = elapsed / 4.0 * POSES
    index = int(pose) % POSES
    sprite = Image.blend(object_sprite(machine.selected, index),
                         object_sprite(machine.selected, (index + 1) % POSES), pose % 1)
    image.paste(sprite, (162, round(87 + bob + 18 * (1 - enter))), sprite)
    for bounds, up in ((UP, True), (DOWN, False)):
        hover = vote_at(pointer) is up
        offset = round((1 - ease((elapsed - 0.08) / 0.42)) * (-12 if up else 12))
        face = card(up, hover)
        image.paste(face, (bounds[0] + offset, bounds[1]), face)
    return image


@lru_cache(maxsize=64)
def label_chip(text, color):
    text = text[:50]
    text_font = font(18, True)
    if text_font.getlength(text) > 300:
        while text and text_font.getlength(text + "…") > 300:
            text = text[:-1]
        text = text.rstrip() + "…"
    width = int(text_font.getlength(text)) + 28
    image = Image.new("RGBA", (width, 36))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((0, 0, width - 1, 35), radius=9, fill="#0e2229", outline="#527778")
    d.ellipse((9, 15, 14, 20), fill=color)
    d.text((21, 18), text, font=text_font, fill=WHITE, anchor="lm")
    return image


def brackets(draw, bounds, color, length=14, width=2):
    x1, y1, x2, y2 = bounds
    length = min(length, (x2 - x1) / 3, (y2 - y1) / 3)
    for x, y, dx, dy in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
        draw.line((x + dx * length, y, x, y, x, y + dy * length), fill=color, width=width, joint="curve")


@lru_cache(maxsize=1)
def camera_shade():
    shade = Image.new("RGBA", SIZE)
    d = ImageDraw.Draw(shade)
    for y in range(320):
        alpha = round(max(0, 1 - y / 74) * 180 + max(0, (y - 236) / 84) * 235)
        if alpha:
            d.line((0, y, 479, y), fill=(7, 17, 23, min(245, alpha)))
    return shade


def live(frame, detections, machine, config, now=0, animate=True):
    if frame is None:
        return loading(now)
    image = Image.new("RGB", SIZE, "#071116")
    preview = ImageOps.contain(frame, SIZE)
    ox, oy = (480 - preview.width) // 2, (320 - preview.height) // 2
    image.paste(preview, (ox, oy))
    image.paste(camera_shade(), (0, 0), camera_shade())
    draw = ImageDraw.Draw(image)
    draw.text((17, 14), "MISS", font=font(19, True), fill=WHITE)
    progress = stability_progress(machine, now)
    status = "Sortieren" if machine.state == State.SORTING else "Prüfen" if progress is not None else "Bereit"
    draw.rounded_rectangle((335, 10, 464, 44), radius=16, fill="#10272a")
    draw.ellipse((347, 24, 353, 30), fill=MINT)
    center(draw, (406, 27), status, 16, MINT, True, 98)

    def coords(box):
        return (ox + box[0] * preview.width, oy + box[1] * preview.height,
                ox + box[2] * preview.width, oy + box[3] * preview.height)

    if config.show_plate:
        brackets(draw, coords(config.plate), "#70939d", length=20, width=1)
    for item in detections:
        if not item.valid() or item.confidence < config.presence_confidence:
            continue
        bounds = coords(item.box)
        color = MINT if item.label == "plastic-bottle" else "#f6c08a"
        brackets(draw, bounds, color)
        chip = label_chip(config.labels.get(item.label, item.label), color)
        tx = round(max(ox + 2, min(bounds[0] - 2, ox + preview.width - chip.width - 2)))
        ty = round(max(50, bounds[1] - 43))
        image.paste(chip, (tx, ty), chip)
    if machine.state == State.SORTING:
        message, subtitle = "Wird sortiert", "Bitte kurz warten"
    elif machine.message == "Gegenstand wird geprüft":
        message, subtitle = "Bitte kurz stillhalten", None
    else:
        message = machine.message or "Gegenstand einlegen"
        subtitle = None if machine.message else "Mittig auf die Platte"
    lines = readable_lines(message)
    if len(lines) > 1:
        for y, line in zip((274, 300), lines):
            center(draw, (240, y), line, 19, WHITE, max_width=438)
    elif subtitle:
        center(draw, (240, 278), message, 21, WHITE, max_width=438)
        center(draw, (240, 304), subtitle, 17, MUTED)
    else:
        center(draw, (240, 292), message, 20, WHITE, max_width=438)
    if machine.state == State.SORTING and animate:
        sorting_spinner(image, now)
    elif animate and progress is not None:
        draw_stability(image, progress)
    return image


def sorting_spinner(image, now):
    a = now * 220 % 360
    ImageDraw.Draw(image).arc((226, 230, 254, 258), a, a + 250, fill=MINT, width=2)


@lru_cache(maxsize=1)
def loading_base():
    image = background("loading").copy()
    d = ImageDraw.Draw(image)
    center(d, (240, 137), "Einfach richtig sortiert.", 28, bold=True, max_width=440)
    center(d, (240, 177), "MISS startet", 19, MUTED)
    return image


def loading(now=0):
    image = loading_base().copy()
    angle = now * 220 % 360
    ImageDraw.Draw(image).arc((223, 204, 257, 238), angle, angle + 240, fill=MINT, width=2)
    return image


def render(frame, detections, machine, config, now, pointer=None, animate=True):
    if machine.state == State.FEEDBACK:
        return feedback(machine, config, now, pointer)
    if machine.state == State.FAULT:
        image = background("fault").copy()
        d = ImageDraw.Draw(image)
        d.ellipse((222, 86, 258, 122), outline="#f2acae", width=2)
        center(d, (240, 104), "!", 22, "#f2acae", True)
        center(d, (240, 157), "MISS ist angehalten", 28, bold=True)
        center(d, (240, 197), "Bitte das System prüfen", 19, MUTED)
        center(d, (240, 224), "und neu starten.", 19, MUTED)
        return image
    return live(frame, detections, machine, config, now, animate)


class Renderer:
    """Presentation state only; transitions never delay the sorting workflow."""

    TRANSITION = 0.20
    PRESS_DURATION = 0.42
    RESULT_DURATION = 1.5

    def __init__(self):
        # Decode packaged atlases once before the frame loop, never mid-animation.
        object_sprite("plastic-bottle", 0)
        object_sprite("aluminum-can", 0)
        self.state = None
        self.changed_at = 0
        self.previous = None
        self.last_frame = None
        self.toast = None
        self.press = None
        self._live_key = None
        self._live_inputs = None
        self._live_image = None
        self._stability_shown = 0
        self._stability_at = None

    def acknowledge(self, correct, now):
        self.toast = (correct, now)
        if self.state == State.FEEDBACK and self.last_frame is not None:
            self.press = (correct, now, self.last_frame.copy())

    def can_vote(self, now):
        return self.state == State.FEEDBACK and now - self.changed_at >= self.TRANSITION

    def holding_result(self, now):
        return self.press is not None and now - self.press[1] < self.RESULT_DURATION

    def render(self, frame, detections, machine, config, now, pointer=None):
        if machine.state != self.state:
            self.previous = self.last_frame
            self.changed_at = now
            self.state = machine.state
        progress = stability_progress(machine, now)
        key = (id(frame), id(detections), machine.state, machine.message, config.show_plate, progress is not None)
        camera_scene = machine.state in (State.LIVE, State.SORTING) and frame is not None
        if camera_scene and key == self._live_key:
            image = self._live_image.copy()
        else:
            image = render(frame, detections, machine, config, now, pointer, animate=False)
            if camera_scene:
                self._live_key = key
                self._live_inputs = (frame, detections)
                self._live_image = image.copy()
        if machine.state == State.SORTING:
            sorting_spinner(image, now)
        if progress is not None and camera_scene:
            if self._stability_at is None or progress < self._stability_shown:
                self._stability_shown = progress
            else:
                dt = max(0, now - self._stability_at)
                self._stability_shown += (progress - self._stability_shown) * (1 - math.exp(-dt / 0.045))
            draw_stability(image, self._stability_shown)
            self._stability_at = now
        else:
            self._stability_shown = 0
            self._stability_at = None
        if self.previous is not None and now - self.changed_at < self.TRANSITION:
            image = Image.blend(self.previous, image, ease((now - self.changed_at) / self.TRANSITION))
        else:
            self.previous = None
        if self.toast and not self.press and now - self.toast[1] < 1.6 and machine.state == State.LIVE:
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((48, 54, 432, 96), radius=12, fill="#163b31", outline="#3c7562")
            center(draw, (240, 75), "Danke für deine Rückmeldung", 19, MINT, True, 366)
        if self.press:
            up, started, snapshot = self.press
            elapsed = max(0, now - started)
            progress = clamp(elapsed / self.PRESS_DURATION)
            if elapsed < self.RESULT_DURATION and machine.state == State.LIVE:
                pressed = press_animation(snapshot, up, progress)
                fade = ease((elapsed - (self.RESULT_DURATION - 0.25)) / 0.25)
                image = Image.blend(pressed, image, fade)
            else:
                self.press = None
                self.toast = None
        self.last_frame = image
        return image
