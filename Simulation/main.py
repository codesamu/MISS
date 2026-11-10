#!/usr/bin/env python3
"""Desktop simulation of the existing MISS touchscreen applications."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time

from PIL import Image, ImageTk

PROJECT = Path(__file__).resolve().parent.parent
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

if __package__:
    from .adapters import SCENES, SIZE, SimulationClosed, Surface
    from .runtime import Runtime
else:
    from adapters import SCENES, SIZE, SimulationClosed, Surface
    from runtime import Runtime


def enable_native_pixels():
    """Keep Windows from bitmap-scaling the entire Tk window on high-DPI monitors."""
    if sys.platform != "win32":
        return
    import ctypes

    try:
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class Desktop(Surface):
    def __init__(self, scale, legacy=False):
        super().__init__()
        import tkinter as tk
        from tkinter import filedialog, ttk

        self.tk = tk
        self.filedialog = filedialog
        self.scale = scale
        self.legacy = legacy
        enable_native_pixels()
        self.root = tk.Tk()
        self.root.title("MISS · Bildschirm-Simulation")
        self.root.configure(bg="#141922")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.root.bind("<Escape>", lambda event: self.request_home())

        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TButton", background="#1b3039", foreground="#e7f5f0", borderwidth=0, padding=(12, 9), font=("Arial", 10))
        style.map("TButton", background=[("active", "#29494f")])
        style.configure("TCombobox", fieldbackground="#172c35", background="#233e48", foreground="#e4f0ec", arrowcolor="#91f0cf", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", "#172c35")], foreground=[("readonly", "#e4f0ec")], selectbackground=[("readonly", "#172c35")], selectforeground=[("readonly", "#e4f0ec")])
        style.configure("Horizontal.TScale", background="#202938", troughcolor="#15242d")
        body = tk.Frame(self.root, bg="#141922", padx=22, pady=20)
        body.pack()
        tk.Label(body, text="MISS  /  Studio", font=("Arial", 21, "bold"), fg="#eaf6f1", bg="#141922").grid(row=0, column=0, sticky="w")
        subtitle = "Bisherige Oberfläche" if legacy else "MISS-Hauptprogramm"
        zoom = "1:1 · native Pixel" if scale == 1 else f"{scale}× vergrößert"
        tk.Label(body, text=f"{subtitle} · 480 × 320 · {zoom}", fg="#acb8ca", bg="#141922").grid(row=1, column=0, sticky="w", pady=(0, 12))
        self.screen = tk.Label(body, bd=0, highlightthickness=2, highlightbackground="#315453", cursor="hand2")
        self.screen.grid(row=2, column=0, sticky="n")
        self.screen.bind("<ButtonPress-1>", self.click)
        self.screen.bind("<Motion>", self.move_pointer)
        self.screen.bind("<Leave>", lambda event: setattr(self, "pointer", None))
        controls = tk.Frame(body, bg="#202938", padx=16, pady=16, width=250)
        controls.grid(row=2, column=1, padx=(18, 0), sticky="ns")

        def label(text):
            widget = tk.Label(controls, text=text, anchor="w", justify="left", fg="white", bg="#202938")
            widget.pack(fill="x", pady=(0, 8))
            return widget

        label("TESTUMGEBUNG").configure(font=("Arial", 11, "bold"), fg="#91f0cf")
        label("Kamera und KI sind simuliert.\nEs wird keine Hardware angesteuert.")
        label("Gegenstand im Kamerabild")
        self.scene_var = tk.StringVar(value=self.scene)
        scenes = ttk.Combobox(controls, textvariable=self.scene_var, values=SCENES, state="readonly", width=25)
        scenes.pack(fill="x", pady=(0, 12))
        scenes.bind("<<ComboboxSelected>>", self.change_scene)
        label("Simulierte Erkennungssicherheit")
        self.confidence_var = tk.DoubleVar(value=85)
        ttk.Scale(controls, from_=0, to=100, orient="horizontal", variable=self.confidence_var,
                 command=lambda value: setattr(self, "confidence", float(value) / 100),
                 ).pack(fill="x", pady=(0, 8))
        self.remove_var = tk.BooleanVar(value=True)
        if not legacy:
            tk.Checkbutton(controls, text="Nach Sortierung entfernen", variable=self.remove_var,
                           command=lambda: setattr(self, "remove_after_sort", self.remove_var.get()),
                           bg="#202938", fg="white", selectcolor="#141922", activebackground="#202938").pack(fill="x", pady=4)
        ttk.Button(controls, text="Eigenes Kamerabild laden …", command=self.load_image).pack(fill="x", pady=4)
        label("Bei eigenen Bildern: keine KI-Erkennung.")
        ttk.Button(controls, text="Screenshot speichern", command=self.save_screenshot).pack(fill="x", pady=4)
        ttk.Button(controls, text="Zum Dashboard (Esc)" if legacy else "Simulation beenden (Esc)", command=self.request_home).pack(fill="x", pady=4)
        self.servo_label = label("Servos\nHorizontal: —\nVertikal: —")
        self.status_label = label("Dashboard")
        self.fps_label = label("Vorschau startet …")
        self.fps_label.configure(fg="#91f0cf", font=("Arial", 9))
        note = "Bereit. Im Display auf eine Anwendung klicken." if legacy else "Gegenstand rechts wählen. Nach stabiler Erkennung wird automatisch sortiert."
        self.note = tk.Label(body, text=note, anchor="w", fg="#acb8ca", bg="#141922")
        self.note.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self._photo = None
        self._servo_text = None
        self._status_text = None
        self._presented = 0
        self._fps_at = time.perf_counter()

    def request_close(self):
        self.closed = True

    def request_home(self):
        if self.legacy:
            self.home_requested = self.active_app != "dashboard"
        else:
            self.closed = True

    def sort_completed(self):
        super().sort_completed()
        self.scene_var.set(self.scene)

    def click(self, event):
        border = int(self.screen.cget("highlightthickness"))
        x, y = (event.x - border) // self.scale, (event.y - border) // self.scale
        if 0 <= x < SIZE[0] and 0 <= y < SIZE[1]:
            self.clicks.append((x, y))

    def move_pointer(self, event):
        border = int(self.screen.cget("highlightthickness"))
        self.pointer = ((event.x - border) // self.scale, (event.y - border) // self.scale)

    def change_scene(self, event=None):
        self.scene = self.scene_var.get()
        self.custom_image = None

    def load_image(self):
        path = self.filedialog.askopenfilename(filetypes=[("Bilder", "*.jpg *.jpeg *.png *.bmp"), ("Alle Dateien", "*.*")])
        if path:
            try:
                with Image.open(path) as image:
                    self.custom_image = image.convert("RGB")
                self.note.configure(text=f"Kamerabild: {Path(path).name} · Erkennung deaktiviert")
            except (OSError, ValueError) as error:
                self.note.configure(text=f"Bild konnte nicht geladen werden: {error}")

    def save_screenshot(self):
        directory = Path(__file__).resolve().parent / "screenshots"
        directory.mkdir(exist_ok=True)
        path = directory / (datetime.now().strftime("MISS_%Y%m%d_%H%M%S_%f") + ".png")
        self.frame.save(path)
        self.note.configure(text=f"Gespeichert: {path.relative_to(directory.parent)}")

    def pump(self):
        super().pump()
        positions = {None: "—", -1: "Minimum", 0: "Mitte", 1: "Maximum"}
        text = "Servos\nHorizontal: {}\nVertikal: {}".format(
            positions.get(self.servos.get(16), "—"), positions.get(self.servos.get(20), "—"))
        if text != self._servo_text:
            self.servo_label.configure(text=text)
            self._servo_text = text
        names = {"live": "Erkennung läuft", "sorting": "Gegenstand wird sortiert", "feedback": "Bewertung · 10 Sekunden", "fault": "System angehalten"}
        status = names.get(self.workflow_state, self.active_app) + ("\n" + self.events[-1] if self.events else "")
        if status != self._status_text:
            self.status_label.configure(text=status)
            self._status_text = status
        self.root.update_idletasks()
        self.root.update()
        super().pump()

    def show(self, frame):
        self.frame = frame.convert("RGB").copy()
        image = self.frame if self.scale == 1 else self.frame.resize(
            (SIZE[0] * self.scale, SIZE[1] * self.scale), Image.Resampling.BILINEAR)
        if self._photo is None:
            self._photo = ImageTk.PhotoImage(image, master=self.root)
            self.screen.configure(image=self._photo)
        else:
            self._photo.paste(image)
        self._presented += 1
        elapsed = time.perf_counter() - self._fps_at
        if elapsed >= 0.75:
            self.fps_label.configure(text=f"Vorschau: {self._presented / elapsed:.0f} FPS · 480 × 320")
            self._presented = 0
            self._fps_at = time.perf_counter()
        self.pump()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", type=int, choices=(1, 2, 3), default=1, help="Display-Vergrößerung (Standard: 1, native 480 × 320 Pixel)")
    parser.add_argument("--legacy", action="store_true", help="Die bisherigen Test-Menüs statt des Hauptprogramms öffnen")
    parser.add_argument("--config", type=Path, help="Einstellungen des Hauptprogramms")
    args = parser.parse_args(argv)
    surface = Desktop(args.scale, legacy=args.legacy)
    try:
        with Runtime(surface).installed() as runtime:
            if args.legacy:
                runtime.run_app()
            else:
                runtime.run_miss(args.config)
    except (SimulationClosed, KeyboardInterrupt):
        pass
    finally:
        surface.root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
