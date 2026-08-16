import sys
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from pynput import keyboard
import onnxruntime as ort

from fishing_bot import FishingBot
import config as c


# --- Path helpers: work both when run as `python main.py` AND when frozen as .exe ---

def get_base_path():
    """Folder next to the running .exe (frozen), or next to this script (source).
    Used for things that must be WRITABLE (e.g. settings.json)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path):
    """Path to a bundled, READ-ONLY resource (e.g. the .onnx model).
    When frozen, PyInstaller unpacks --add-data into sys._MEIPASS."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


SETTINGS_FILE = os.path.join(get_base_path(), "settings.json")


def load_saved_settings():
    """Load settings.json (if it exists) and apply saved values on top of config.py
    defaults. Runs once at startup, before the UI is built."""
    if not os.path.exists(SETTINGS_FILE):
        return
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, value in data.items():
            if hasattr(c, key):
                setattr(c, key, value)
    except Exception as e:
        print(f"[Settings] Failed to load settings.json: {e}")


def save_settings_to_file(values: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2)


# --- Editable parameters shown in the Settings window ---
SETTINGS_SCHEMA = [
    {
        "group": "Detection Confidence",
        "fields": [
            {
                "key": "CONF_THRESH", "type": float,
                "label": "Confidence Threshold (general)",
                "desc": "Minimum confidence accepted for the bar / mark / bg_track classes "
                        "(0.0-1.0). Higher = fewer false positives, but risks missing real detections."
            },
            {
                "key": "FISH_CONF_THRESH", "type": float,
                "label": "Confidence Threshold (Fish)",
                "desc": "Minimum confidence specifically for the fish class (usually set lower "
                        "than the general threshold since the fish marker is small and the model "
                        "is less confident about it)."
            },
        ]
    },
    {
        "group": "Timing",
        "fields": [
            {
                "key": "WAIT_HOOK_TIME", "type": float,
                "label": "Wait Hook Time (sec)",
                "desc": "Delay after clicking to hook a bite, before entering the FISHING state."
            },
            {
                "key": "MAX_MISSING_FRAMES", "type": int,
                "label": "Max Missing Frames",
                "desc": "Max consecutive frames allowed with no bar/fish detected before the bot "
                        "assumes this fishing attempt is over."
            },
            {
                "key": "WAIT_COLLECT_TIME", "type": float,
                "label": "Wait Collect Time (sec)",
                "desc": "Delay before clicking to collect the catch after a successful catch is detected."
            },
            {
                "key": "WAIT_BITE_TIMEOUT", "type": float,
                "label": "Wait Bite Timeout (sec)",
                "desc": "Max time to wait for a bite before automatically re-casting."
            },
        ]
    },
    {
        "group": "PD Controller Tuning",
        "fields": [
            {
                "key": "KP", "type": float,
                "label": "KP (Proportional Gain)",
                "desc": "Response strength based on the current distance between fish and bar. "
                        "If the bot can't keep up with the fish, increase this."
            },
            {
                "key": "KD", "type": float,
                "label": "KD (Derivative Gain)",
                "desc": "Damping based on the rate of change of the distance — helps prevent "
                        "overshoot. Too high amplifies detection noise and causes oscillation."
            },
            {
                "key": "EMA_ALPHA", "type": float,
                "label": "EMA Alpha (Smoothing)",
                "desc": "Weight given to the latest frame in the noise-smoothing filter (0.0-1.0). "
                        "Lower = smoother but more lag. Higher = more responsive but noisier."
            },
            {
                "key": "HYSTERESIS", "type": float,
                "label": "Hysteresis (anti-oscillation)",
                "desc": "Dead-band around the press/release/click switching points, prevents rapid "
                        "state flapping (oscillation). Higher = more stable, slightly slower to react."
            },
        ]
    },
    {
        "group": "Loop",
        "fields": [
            {
                "key": "LOOP_SLEEP_TIME", "type": float,
                "label": "Loop Sleep Time (sec)",
                "desc": "Delay between iterations of the main bot loop (not counting capture + "
                        "inference time). Lower = tighter loop, but higher CPU usage."
            },
        ]
    },
]


class SettingsWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("⚙️ Bot Settings")
        self.geometry("480x560")
        self.attributes("-topmost", True)

        self.entries = {}  # key -> (entry, type)

        canvas = tk.Canvas(self, borderwidth=0)
        scroll_frame = ttk.Frame(canvas)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        for group in SETTINGS_SCHEMA:
            ttk.Label(
                scroll_frame, text=group["group"], font=("Helvetica", 11, "bold")
            ).pack(anchor="w", padx=10, pady=(12, 2))
            ttk.Separator(scroll_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

            for field in group["fields"]:
                self._build_field(scroll_frame, field)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(side="bottom", fill=tk.X)

        ttk.Button(
            btn_frame, text="Apply (this session only)", command=self.apply_only
        ).pack(side="left", expand=True, fill=tk.X, padx=(0, 5))

        ttk.Button(
            btn_frame, text="Apply + Save", command=self.apply_and_save
        ).pack(side="left", expand=True, fill=tk.X, padx=(5, 0))

    def _build_field(self, parent, field):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, padx=10, pady=4)

        row = ttk.Frame(frame)
        row.pack(fill=tk.X)

        ttk.Label(row, text=field["label"], width=26).pack(side="left")

        entry = ttk.Entry(row, width=12)
        entry.insert(0, str(getattr(c, field["key"])))
        entry.pack(side="left", padx=5)
        self.entries[field["key"]] = (entry, field["type"])

        ttk.Label(
            frame, text=field["desc"], foreground="gray",
            wraplength=440, justify="left", font=("Helvetica", 8)
        ).pack(anchor="w", pady=(2, 0))

    def _collect_values(self):
        new_values = {}
        for key, (entry, cast_type) in self.entries.items():
            raw = entry.get().strip()
            try:
                value = cast_type(raw)
            except ValueError:
                messagebox.showerror(
                    "Invalid value",
                    f"'{key}' must be a {cast_type.__name__} (got: '{raw}')"
                )
                return None
            new_values[key] = value
        return new_values

    def apply_only(self):
        new_values = self._collect_values()
        if new_values is None:
            return
        for key, value in new_values.items():
            setattr(c, key, value)
        messagebox.showinfo("Applied", "New values applied (this session only — "
                                        "will reset if you restart the app).")

    def apply_and_save(self):
        new_values = self._collect_values()
        if new_values is None:
            return
        for key, value in new_values.items():
            setattr(c, key, value)
        try:
            save_settings_to_file(new_values)
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not save settings.json:\n{e}")
            return
        messagebox.showinfo("Saved", "Values applied and saved to settings.json — "
                                      "they'll be reloaded next time you start the app.")


class BotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat FISH! Auto Fishing")
        self.root.geometry("380x290")
        self.root.attributes("-topmost", True)

        self.bot = None
        self.session = None
        self.listener = None
        self.hotkey = keyboard.Key.f8
        self.settings_window = None

        self.init_model()
        self.create_widgets()
        self.start_hotkey_listener()

    def init_model(self):
        try:
            providers = [
                "DmlExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider"
            ]

            self.session = ort.InferenceSession(
                resource_path("models/rfdetr-small.onnx"),
                providers=providers
            )

            self.active_provider = self.session.get_providers()[0]
            self.bot = FishingBot(self.session)

        except Exception as e:
            messagebox.showerror("Model Error", f"Failed to load model:\n{e}")
            self.root.destroy()

    def create_widgets(self):
        header_frame = ttk.Frame(self.root, padding=10)
        header_frame.pack(fill=tk.X)

        self.lbl_status = ttk.Label(
            header_frame, text="🔴 Status: STOPPED",
            font=("Helvetica", 14, "bold"), foreground="red"
        )
        self.lbl_status.pack(pady=5)

        provider_name = self.active_provider.replace("ExecutionProvider", "")
        ttk.Label(
            header_frame, text=f"⚡ Hardware: {provider_name}", foreground="gray"
        ).pack()

        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=10)

        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X)

        self.btn_toggle = tk.Button(
            control_frame, text="START (F8)", command=self.toggle_bot,
            bg="#4CAF50", fg="white", font=("Helvetica", 12, "bold"), height=2
        )
        self.btn_toggle.pack(fill=tk.X)

        self.btn_settings = tk.Button(
            control_frame, text="⚙️ Settings", command=self.open_settings,
            bg="#607D8B", fg="white", font=("Helvetica", 10), height=1
        )
        self.btn_settings.pack(fill=tk.X, pady=(8, 0))

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self.settings_window = SettingsWindow(self.root)

    def toggle_bot(self):
        if self.bot and self.bot.is_running:
            self.bot.stop()
            self.lbl_status.config(text="🔴 Status: STOPPED", foreground="red")
            self.btn_toggle.config(text="START (F8)", bg="#4CAF50")
        else:
            self.bot.start()
            self.lbl_status.config(text="🟢 Status: RUNNING", foreground="green")
            self.btn_toggle.config(text="STOP (F8)", bg="#f44336")

    def on_press(self, key):
        if key == self.hotkey:
            self.root.after(0, self.toggle_bot)

    def start_hotkey_listener(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def on_closing(self):
        if self.bot:
            self.bot.stop()
        if self.listener:
            self.listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    load_saved_settings()

    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")

    app = BotUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()