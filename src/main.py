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


# ─── Color palette ────────────────────────────────────────────────────────────
_BG_DARK = '#1e1e2e'
_BG_CARD = '#2a2a3e'
_BG_INPUT = '#363650'
_FG_PRIMARY = '#e0e0f0'
_FG_SECONDARY = '#8888aa'
_FG_DIM = '#666680'
_ACCENT = '#7c6ff5'
_ACCENT_HOVER = '#9d93f7'
_SUCCESS = '#4ade80'
_DANGER = '#f87171'
_WARNING = '#fbbf24'
_BORDER = '#404060'


# --- Editable parameters shown in the Settings window ---
SETTINGS_SCHEMA = [
    {
        "group": "🎯 ความแม่นยำในการตรวจจับ (Detection Confidence)",
        "fields": [
            {
                "key": "CONF_THRESH", "type": float,
                "label": "ความมั่นใจทั่วไป (หลอด/ทุ่น)",
                "desc": "ค่าความมั่นใจขั้นต่ำของ AI สำหรับตรวจจับหลอดและทุ่น (0.0 - 1.0) • แนะนำ 0.50 • ถ้าตั้งสูงไป AI อาจมองไม่เห็นหลอด"
            },
            {
                "key": "FISH_CONF_THRESH", "type": float,
                "label": "ความมั่นใจเฉพาะปลา (Fish)",
                "desc": "ค่าความมั่นใจสำหรับตรวจจับไอคอนปลาโดยเฉพาะ • แนะนำ 0.28 - 0.30 เพราะไอคอนปลามีขนาดเล็ก AI จะมั่นใจน้อยกว่าหลอด"
            },
        ]
    },
    {
        "group": "⏱️ จังหวะเวลาการทำงาน (Action Timing)",
        "fields": [
            {
                "key": "CAST_INITIAL_WAIT", "type": float,
                "label": "เวลารอก่อนโยนเบ็ด (วิ)",
                "desc": "หน่วงเวลาก่อนคลิกซ้ายโยนเบ็ด • ตั้งเป็น 0.0 เพื่อโยนเบ็ดทันทีที่กด F8"
            },
            {
                "key": "CAST_HOLD_TIME", "type": float,
                "label": "เวลากดค้างตอนโยนเบ็ด (วิ)",
                "desc": "ระยะเวลาคลิกซ้ายค้างตอนเหวี่ยงเบ็ด • แนะนำ 0.10 - 0.15s เพื่อให้เกมรับสัญญาณการเหวี่ยงเบ็ด"
            },
            {
                "key": "CAST_AFTER_WAIT", "type": float,
                "label": "เวลารอหลังโยนเบ็ด (วิ)",
                "desc": "หน่วงเวลาหลังโยนเบ็ดเสร็จ ก่อนเริ่มตรวจจับปลากินเบ็ด • ตั้งเป็น 0.0 เพื่อตรวจจับทันที"
            },
            {
                "key": "MARK_CLICK_WAIT", "type": float,
                "label": "เวลารอก่อนดึงเบ็ดเมื่อปลากิน (วิ)",
                "desc": "หน่วงเวลาก่อนคลิกเมื่อเจอปลาติดเบ็ด (!) • แนะนำ 0.0 เพื่อดึงเบ็ดทันทีไม่ให้ปลาหลุด"
            },
            {
                "key": "WAIT_HOOK_TIME", "type": float,
                "label": "เวลารอเปิดมินิเกม (วิ)",
                "desc": "หน่วงเวลาหลังดึงเบ็ดเพื่อให้ UI มินิเกมกางออกมาเต็มที่ • แนะนำ 0.5s"
            },
            {
                "key": "RESULT_WAIT", "type": float,
                "label": "เวลารอดึงปลาขึ้นมา (วิ)",
                "desc": "หน่วงเวลาหลังจบมินิเกม เพื่อรอแอนิเมชันปลาลอยขึ้นมาให้เสร็จก่อนคลิกเก็บ • แนะนำ 1.5 - 2.0s (ถ้าเก็บปลาไม่ทันให้เพิ่มค่านี้)"
            },
            {
                "key": "COLLECT_CLICK_WAIT", "type": float,
                "label": "เวลารอหลังเก็บปลา (วิ)",
                "desc": "หน่วงเวลาหลังคลิกเก็บปลา เพื่อให้เกมบันทึกปลาเข้ากระเป๋า • แนะนำ 1.2 - 1.5s"
            },
            {
                "key": "RECOVERY_RIGHTCLICK_WAIT", "type": float,
                "label": "เวลารอหลังปล่อยเบ็ด (วิ)",
                "desc": "หน่วงเวลาหลังคลิกขวาปล่อยเบ็ด เพื่อให้ตัวละครวางเบ็ดลงพื้นแน่นอน • แนะนำ 0.8 - 1.2s"
            },
            {
                "key": "RECOVERY_KEY_WAIT", "type": float,
                "label": "เวลารอหลังเสกเบ็ดใหม่ (วิ)",
                "desc": "หน่วงเวลาหลังกดปุ่ม T เพื่อให้โมเดลเบ็ดใหม่ปรากฏขึ้นมาบนจอ • แนะนำ 1.0 - 1.5s (ถ้าเสกเบ็ดไม่ทันให้เพิ่มค่านี้)"
            },
            {
                "key": "RECOVERY_CLICK_WAIT", "type": float,
                "label": "เวลารอหลังหยิบเบ็ด (วิ)",
                "desc": "หน่วงเวลาหลังคลิกซ้ายหยิบเบ็ดขึ้นมาถือ • แนะนำ 0.8 - 1.0s"
            },
            {
                "key": "RECOVERY_FINAL_WAIT", "type": float,
                "label": "เวลารอก่อนเริ่มรอบใหม่ (วิ)",
                "desc": "หน่วงเวลาก่อนกลับไปโยนเบ็ดรอบถัดไป • แนะนำ 1.0s"
            },
        ]
    },
    {
        "group": "🎛️ การจูนการเลี้ยงเบ็ด (PID + PWM Tuning)",
        "fields": [
            {
                "key": "KP", "type": float,
                "label": "KP (แรงตอบสนองตามระยะห่าง)",
                "desc": "ความแรงในการดึงเบ็ดเข้าหาตัวปลา • แนะนำ 0.8 - 1.5 • เพิ่มถ้าเบ็ดตามปลาไม่ทัน / ลดถ้าเบ็ดกระชากเกินไป"
            },
            {
                "key": "KI", "type": float,
                "label": "KI (แรงชดเชยสะสม Integral)",
                "desc": "แรงชดเชยสะสมเพื่อล็อกตำแหน่งเบ็ดให้อยู่ตรงกลางปลาเป๊ะ • แนะนำ 0.02 - 0.08 • ป้องกันเบ็ดจมหรือลอยค้าง"
            },
            {
                "key": "KD", "type": float,
                "label": "KD (แรงเบรก Derivative)",
                "desc": "แรงหน่วงเบรกตามความเร็ว • แนะนำ 0.50 - 0.90 • เพิ่มถ้าเบ็ดพุ่งทะลุเลยตัวปลาหรือเบ็ดสวิง"
            },
            {
                "key": "BASE_DUTY", "type": float,
                "label": "BASE_DUTY (แรงลอยตัวพื้นฐาน %)",
                "desc": "Duty Cycle (%) เฉลี่ยที่ใช้พยุงเบ็ดให้ลอยนิ่งสู้แรงโน้มถ่วงเมื่ออยู่ตรงกับปลาพอดี • แนะนำ 20.0 - 30.0%"
            },
            {
                "key": "PWM_PERIOD", "type": float,
                "label": "PWM Period (ความยาวรอบ Pulse วิ)",
                "desc": "ความยาวรอบของ Pulse Modulation (วิ) • แนะนำ 0.10 - 0.14s (8 - 10 Hz) ช่วยให้การกดเมาส์นุ่มนวลต่อเนื่อง"
            },
            {
                "key": "I_MAX", "type": float,
                "label": "I_MAX (ขอบเขต Integral สูงสุด %)",
                "desc": "ขอบเขตสูงสุดของ Integral term ป้องกัน Integral Windup • แนะนำ 25.0 - 35.0%"
            },
            {
                "key": "EMA_ALPHA", "type": float,
                "label": "EMA Smoothing (ความนุ่มนวล)",
                "desc": "ค่าน้ำหนักกรองสัญญาณรบกวนของ Error (0.0 - 1.0) • แนะนำ 0.40 - 0.50 • ยิ่งมากยิ่งตอบสนองไว"
            },
        ]
    },
    {
        "group": "⚡ ประสิทธิภาพและการกิน CPU (Loop & Throttling)",
        "fields": [
            {
                "key": "LOOP_SLEEP_TIME", "type": float,
                "label": "เวลาพักในลูปตกปลา (วิ)",
                "desc": "หน่วงเวลาในลูปตกปลา • ตั้งเป็น 0.0 เพื่อใช้ User Full FPS (100+ FPS) เต็มประสิทธิภาพ หรือ 0.005s สำหรับ CPU รุ่นเล็ก"
            },
            {
                "key": "CALIBRATE_LOG_INTERVAL", "type": float,
                "label": "ความถี่แสดง Log ใน Terminal (วิ)",
                "desc": "ระยะห่างในการแสดงผล Telemetry (FPS, Error, PID, Duty) ใน Terminal • แนะนำ 0.08s ให้อ่านง่ายไม่แล็ก"
            },
            {
                "key": "MODEL_POLL_INTERVAL", "type": float,
                "label": "ความถี่ตรวจจับตอนรอเบ็ด (วิ)",
                "desc": "ระยะห่างในการเรียก AI หาปลากินเบ็ด (!) • แนะนำ 0.35 - 0.45s ช่วยประหยัด CPU ได้มากตอนยืนรอปลากิน"
            },
            {
                "key": "ACQUIRE_RETRY_INTERVAL", "type": float,
                "label": "ระยะรอระหว่างหาหลอด (วิ)",
                "desc": "หน่วงเวลาระหว่างลองเรียก AI หาตำแหน่งหลอดตกปลาหลังปลากินเบ็ด • แนะนำ 0.15 - 0.20s"
            },
            {
                "key": "ACQUIRE_MAX_RETRIES", "type": int,
                "label": "จำนวนครั้งสูงสุดที่ลองหาหลอด",
                "desc": "จำนวนครั้งที่ลองหาหลอดตกปลา ถ้าเกินนี้จะถือว่าหาไม่เจอแล้วรีเซ็ตไปโยนเบ็ดใหม่ • แนะนำ 12 - 15 ครั้ง"
            },
            {
                "key": "TRACK_RECHECK_INTERVAL", "type": float,
                "label": "ความถี่เช็คตำแหน่งหลอดซ้ำ (วิ)",
                "desc": "ความถี่ให้ AI เช็คตำแหน่งหลอดซ้ำระหว่างเล่นมินิเกม • แนะนำ 0.0 เพื่อให้ CV2 ทำงาน Full FPS ไม่สะดุด"
            },
            {
                "key": "TRACK_LOST_FRAMES", "type": int,
                "label": "จำนวนเฟรมหลุดก่อนเรียก AI",
                "desc": "จำนวนเฟรมที่ระบบจับสีหาไม่เจอ ก่อนจะบังคับเรียก AI มาช่วยหาพิกัดใหม่ • แนะนำ 8 - 10 เฟรม"
            },
            {
                "key": "UI_GONE_CONFIRM_FRAMES", "type": int,
                "label": "จำนวนเฟรมยืนยันจบเกม",
                "desc": "จำนวนเฟรมที่หลอดตกปลาหายไปติดกัน ก่อนจะสรุปว่ามินิเกมจบลงแล้ว • แนะนำ 5 เฟรม"
            },
        ]
    },
    {
        "group": "📊 การตรวจจับหลอดเก็บปลาและ Calibrate (Progress & Debug)",
        "fields": [
            {
                "key": "CALIBRATE_MODE", "type": bool,
                "label": "เปิดโหมด Calibrate Telemetry",
                "desc": "แสดงค่า FPS, Error %, ค่า P/I/D, Duty Cycle % และ Progress ใน Terminal แบบเรียลไทม์"
            },
            {
                "key": "PROGRESS_OFFSET_PCT", "type": float,
                "label": "ระยะห่างหลอดเก็บปลา (%)",
                "desc": "ระยะห่างแนวนอนจากขอบขวาของหลอดตกปลาไปยังหลอดเก็บปลา (% ของความกว้างหลอด) • ค่าปกติ 0.18"
            },
            {
                "key": "PROGRESS_WIDTH_PCT", "type": float,
                "label": "ความกว้างหลอดเก็บปลา (%)",
                "desc": "ความกว้างของพื้นที่สแกนหลอดเก็บปลา (% ของความกว้างหลอด) • ค่าปกติ 0.06"
            },
            {
                "key": "PROGRESS_FULL_THRESH", "type": float,
                "label": "เกณฑ์ถือว่าตกสำเร็จ (0.0-1.0)",
                "desc": "สัดส่วนความเต็มของหลอดที่ถือว่าตกปลาได้สำเร็จ • แนะนำ 0.50 - 0.60 • แนะนำให้ลดลง ถ้าบอทชอบคิดว่าปลาหลุดทั้งที่ตกได้"
            },
            {
                "key": "PROGRESS_EMPTY_THRESH", "type": float,
                "label": "เกณฑ์ถือว่าปลาหลุด (0.0-1.0)",
                "desc": "สัดส่วนความเต็มของหลอดที่ถือว่าปลาหลุด • แนะนำ 0.15 • หากหลอดลดต่ำกว่านี้บอทจะเข้าสู่โหมดกู้คืนเบ็ด"
            },
        ]
    },
    {
        "group": "🪟 การล็อกขนาดหน้าต่างเกม (Window Lock)",
        "fields": [
            {
                "key": "LOCK_WINDOW_SIZE", "type": bool,
                "label": "บังคับล็อกขนาดหน้าต่าง",
                "desc": "ปรับขนาดหน้าต่าง VRChat ให้คงที่อัตโนมัติเมื่อบอทเริ่มทำงาน เพื่อให้พิกัดและสเกลนิ่งตลอดเวลา"
            },
            {
                "key": "WINDOW_WIDTH", "type": int,
                "label": "ความกว้างหน้าต่าง (px)",
                "desc": "ความกว้างของพื้นที่เกมที่จะล็อก • ค่าปกติ 700 พิกเซล"
            },
            {
                "key": "WINDOW_HEIGHT", "type": int,
                "label": "ความสูงหน้าต่าง (px)",
                "desc": "ความสูงของพื้นที่เกมที่จะล็อก • ค่าปกติ 620 พิกเซล"
            },
        ]
    },
    {
        "group": "🔄 การรอและกู้คืน (Recovery Timeout)",
        "fields": [
            {
                "key": "BOUNCE_CHECK_TIMEOUT", "type": float,
                "label": "เวลารอทุ่นเด้งกลับมากินซ้ำ (วิ)",
                "desc": "ระยะเวลารอดูว่าทุ่นเบ็ดจะเด้งกลับมากินอีกรอบไหม ถ้าหมดเวลานี้จะกดเสกเบ็ดใหม่ • แนะนำ 4.0s"
            },
            {
                "key": "WAIT_BITE_TIMEOUT", "type": float,
                "label": "เวลารอปลาตอดสูงสุด (วิ)",
                "desc": "เวลารอปลาตอดสูงสุด ถ้ารอนานเกินเวลานี้จะดึงเบ็ดกลับมาโยนใหม่ • แนะนำ 17.0s"
            },
        ]
    },
]


class SettingsWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("⚙️ Bot Settings")
        self.geometry("620x720")
        self.minsize(620, 500)
        self.resizable(False, True)  # ล็อกความกว้าง 620px ให้สวยงามเป๊ะ ปรับได้เฉพาะความสูง
        self.attributes("-topmost", True)
        self.configure(bg=_BG_DARK)

        self.entries = {}  # key -> (widget_or_var, type)
        self._is_populating = False

        # ── 1. Top Bar: Header (PINNED / ไม่ Scroll ตามเนื้อหา) ───────────
        top_bar = tk.Frame(self, bg=_BG_DARK, padx=15, pady=12)
        top_bar.pack(side="top", fill=tk.X)

        tk.Label(
            top_bar, text="Preset:", font=("Segoe UI", 12, "bold"),
            bg=_BG_DARK, fg=_FG_PRIMARY
        ).pack(side="left", padx=(0, 10))

        self.preset_var = tk.StringVar(value="Custom")
        self.preset_combo = ttk.Combobox(
            top_bar, textvariable=self.preset_var,
            values=["High", "Medium", "Low", "Custom"],
            state="readonly", width=14, font=("Segoe UI", 10)
        )
        self.preset_combo.pack(side="left")
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)

        sep = tk.Frame(self, bg=_BORDER, height=1)
        sep.pack(side="top", fill=tk.X, padx=15)

        # ── 2. Bottom Button Bar: Footer (PINNED ด้านล่างเสมอ) ─────────────
        btn_frame = tk.Frame(self, bg=_BG_DARK, padx=15, pady=14)
        btn_frame.pack(side="bottom", fill=tk.X)

        sep2 = tk.Frame(self, bg=_BORDER, height=1)
        sep2.pack(side="bottom", fill=tk.X, padx=15)

        btn_apply = tk.Button(
            btn_frame, text="Apply (this session)",
            command=self.apply_only,
            bg=_BG_INPUT, fg=_FG_PRIMARY, activebackground=_ACCENT,
            activeforeground='white', font=("Segoe UI", 10, "bold"),
            relief='flat', padx=16, pady=8, cursor='hand2'
        )
        btn_apply.pack(side="left", expand=True, fill=tk.X, padx=(0, 6))

        btn_save = tk.Button(
            btn_frame, text="Apply + Save",
            command=self.apply_and_save,
            bg=_ACCENT, fg='white', activebackground=_ACCENT_HOVER,
            activeforeground='white', font=("Segoe UI", 10, "bold"),
            relief='flat', padx=16, pady=8, cursor='hand2'
        )
        btn_save.pack(side="left", expand=True, fill=tk.X, padx=(6, 0))

        # ── 3. Middle Scrollable Content Area ─────────────────────────────
        container = tk.Frame(self, bg=_BG_DARK)
        container.pack(side="top", fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(container, bg=_BG_DARK, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scroll_frame = tk.Frame(self.canvas, bg=_BG_DARK)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw"
        )

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width)
        )

        # ── Global Mouse Wheel Scrolling ─────────────────────────────────
        self._bind_mousewheel_global()

        # ── Build setting fields ─────────────────────────────────────────
        for group in SETTINGS_SCHEMA:
            self._build_group(self.scroll_frame, group)

    def _bind_mousewheel_global(self):
        """Bind mouse wheel across the entire settings window so it scrolls everywhere."""
        def _on_mousewheel(event):
            try:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        self.bind("<MouseWheel>", _on_mousewheel)
        self.canvas.bind("<MouseWheel>", _on_mousewheel)
        self.scroll_frame.bind("<MouseWheel>", _on_mousewheel)

    def _on_value_edited(self, *args):
        """Called whenever an entry or checkbox is changed by the user."""
        if not self._is_populating:
            self.preset_var.set("Custom")

    def _build_group(self, parent, group):
        """Build a settings group with header + fields."""
        header = tk.Frame(parent, bg=_BG_DARK)
        header.pack(fill=tk.X, padx=15, pady=(16, 6))

        tk.Label(
            header, text=group["group"],
            font=("Segoe UI", 12, "bold"),
            bg=_BG_DARK, fg=_ACCENT
        ).pack(anchor="w")

        sep = tk.Frame(parent, bg=_BORDER, height=1)
        sep.pack(fill=tk.X, padx=15, pady=(0, 6))

        for field in group["fields"]:
            self._build_field(parent, field)

    def _build_field(self, parent, field):
        """Build a single setting field row with right-aligned input."""
        card = tk.Frame(parent, bg=_BG_CARD, padx=12, pady=8)
        card.pack(fill=tk.X, padx=15, pady=3)

        row = tk.Frame(card, bg=_BG_CARD)
        row.pack(fill=tk.X)

        # Label ชิดซ้าย
        tk.Label(
            row, text=field["label"],
            font=("Segoe UI", 10, "bold"), bg=_BG_CARD, fg=_FG_PRIMARY,
            anchor="w"
        ).pack(side="left", fill=tk.X, expand=True)

        # Input / Checkbox ชิดขวา
        if field["type"] is bool:
            var = tk.BooleanVar(value=bool(getattr(c, field["key"])))
            var.trace_add("write", self._on_value_edited)
            cb = tk.Checkbutton(
                row, variable=var,
                bg=_BG_CARD, fg=_ACCENT, selectcolor=_BG_INPUT,
                activebackground=_BG_CARD, activeforeground=_ACCENT,
                relief='flat', cursor='hand2'
            )
            cb.pack(side="right", padx=(5, 0))
            self.entries[field["key"]] = (var, bool)
        else:
            entry = tk.Entry(
                row, width=12,
                bg=_BG_INPUT, fg=_FG_PRIMARY, insertbackground=_FG_PRIMARY,
                relief='flat', font=("Consolas", 11, "bold"), justify='right',
                highlightthickness=1, highlightcolor=_ACCENT,
                highlightbackground=_BORDER
            )
            entry.insert(0, str(getattr(c, field["key"])))
            entry.bind("<KeyRelease>", self._on_value_edited)
            entry.pack(side="right", padx=(5, 0))
            self.entries[field["key"]] = (entry, field["type"])

        # Description ตัวหนังสือขนาดอ่านสบายตา
        tk.Label(
            card, text=field["desc"],
            font=("Segoe UI", 9), bg=_BG_CARD, fg='#9898b8',
            wraplength=520, justify="left", anchor="w"
        ).pack(anchor="w", pady=(4, 0))

    def _on_preset_changed(self, event=None):
        """Fill entries with preset values when a preset is selected."""
        preset_name = self.preset_var.get()
        if preset_name == "Custom" or preset_name not in c.PRESETS:
            return

        self._is_populating = True
        try:
            preset = c.PRESETS[preset_name]
            for key, value in preset.items():
                if key not in self.entries:
                    continue
                widget, cast_type = self.entries[key]
                if cast_type is bool:
                    widget.set(value)
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value))
        finally:
            self._is_populating = False

    def _collect_values(self):
        new_values = {}
        for key, (widget, cast_type) in self.entries.items():
            if cast_type is bool:
                new_values[key] = bool(widget.get())
                continue
            raw = widget.get().strip()
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
        messagebox.showinfo("Applied", "New values applied (this session only).")

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
        messagebox.showinfo("Saved", "Values applied and saved to settings.json.")


class BotUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat FISH! Auto Fishing")
        self.root.geometry("400x310")
        self.root.attributes("-topmost", True)
        self.root.configure(bg=_BG_DARK)
        self.root.resizable(True, True)
        self.root.minsize(360, 280)

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
            # Optimize ONNX runtime for low-end 2-core CPUs (e.g. AMD Athlon 3000G)
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            providers = [
                "DmlExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider"
            ]

            self.session = ort.InferenceSession(
                resource_path("models/rfdetr-small.onnx"),
                sess_options=opts,
                providers=providers
            )

            self.active_provider = self.session.get_providers()[0]
            self.bot = FishingBot(self.session)

        except Exception as e:
            messagebox.showerror("Model Error", f"Failed to load model:\n{e}")
            self.root.destroy()

    def create_widgets(self):
        header_frame = tk.Frame(self.root, bg=_BG_DARK, padx=20, pady=15)
        header_frame.pack(fill=tk.X)

        tk.Label(
            header_frame, text="🐟 VRC FISH!",
            font=("Segoe UI", 18, "bold"), bg=_BG_DARK, fg=_FG_PRIMARY
        ).pack()

        self.lbl_status = tk.Label(
            header_frame, text="⏹  STOPPED",
            font=("Segoe UI", 13, "bold"), bg=_BG_DARK, fg=_DANGER
        )
        self.lbl_status.pack(pady=(6, 4))

        provider_name = self.active_provider.replace("ExecutionProvider", "")
        tk.Label(
            header_frame, text=f"⚡ {provider_name}",
            font=("Segoe UI", 9), bg=_BG_DARK, fg=_FG_DIM
        ).pack()

        sep = tk.Frame(self.root, bg=_BORDER, height=1)
        sep.pack(fill=tk.X, padx=20, pady=5)

        control_frame = tk.Frame(self.root, bg=_BG_DARK, padx=20, pady=10)
        control_frame.pack(fill=tk.X)

        self.btn_toggle = tk.Button(
            control_frame, text="▶  START  (F8)",
            command=self.toggle_bot,
            bg=_SUCCESS, fg=_BG_DARK, activebackground='#22c55e',
            activeforeground=_BG_DARK,
            font=("Segoe UI", 13, "bold"), relief='flat',
            padx=10, pady=10, cursor='hand2'
        )
        self.btn_toggle.pack(fill=tk.X)

        self.btn_settings = tk.Button(
            control_frame, text="⚙️  Settings",
            command=self.open_settings,
            bg=_BG_CARD, fg=_FG_PRIMARY, activebackground=_BG_INPUT,
            activeforeground=_FG_PRIMARY,
            font=("Segoe UI", 10), relief='flat',
            padx=10, pady=6, cursor='hand2'
        )
        self.btn_settings.pack(fill=tk.X, pady=(8, 0))

        tk.Label(
            self.root, text="Press F8 to toggle • Settings to configure",
            font=("Segoe UI", 7), bg=_BG_DARK, fg=_FG_DIM
        ).pack(side="bottom", pady=6)

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self.settings_window = SettingsWindow(self.root)

    def toggle_bot(self):
        if self.bot and self.bot.is_running:
            self.bot.stop()
            self.lbl_status.config(text="⏹  STOPPED", fg=_DANGER)
            self.btn_toggle.config(
                text="▶  START  (F8)", bg=_SUCCESS,
                activebackground='#22c55e'
            )
        else:
            self.bot.start()
            self.lbl_status.config(text="▶  RUNNING", fg=_SUCCESS)
            self.btn_toggle.config(
                text="⏹  STOP  (F8)", bg=_DANGER,
                activebackground='#ef4444'
            )

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
    style.theme_use("clam")

    style.configure(".", background=_BG_DARK, foreground=_FG_PRIMARY, fieldbackground=_BG_INPUT)
    style.configure("TLabel", background=_BG_DARK, foreground=_FG_PRIMARY)
    style.configure("TFrame", background=_BG_DARK)
    style.configure("TScrollbar", background=_BG_CARD, troughcolor=_BG_DARK)
    style.configure("TCombobox",
                     fieldbackground=_BG_INPUT, background=_BG_INPUT,
                     foreground=_FG_PRIMARY, selectbackground=_ACCENT,
                     arrowcolor=_FG_PRIMARY)
    style.map("TCombobox",
              fieldbackground=[("readonly", _BG_INPUT)],
              foreground=[("readonly", _FG_PRIMARY)],
              selectbackground=[("readonly", _ACCENT)])

    app = BotUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()