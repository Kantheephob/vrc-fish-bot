APP = 'VRChat'
IMG_SIZE = 512
CONF_THRESH = 0.5
FISH_CONF_THRESH = 0.3

CLASS_MAP = {
    0: "bar",
    1: "bg_track",
    2: "fish",
    3: "mark"
}

# ─── Action Timing (ปรับ delay ของแต่ละ state/action ได้) ───────────────────
# CASTING
CAST_INITIAL_WAIT = 1.0       # หน่วงเวลาก่อนเริ่มโยนเบ็ด 1.0 วิ เพื่อให้ดึงหน้าต่างเกมขึ้นมาโฟกัสเรียบร้อย
CAST_HOLD_TIME = 0.1          # ระยะเวลากด mouse down ตอน cast
CAST_AFTER_WAIT = 0.0         # หลัง cast แล้วรอกี่วิก่อนเริ่ม WAITING

# WAITING → bite detected
MARK_CLICK_WAIT = 0.0         # เจอ ! กดคลิกซ้ายได้เลยไม่ต้องรอ

# WAITING → ACQUIRE (เข้า UI ตกปลา)
WAIT_HOOK_TIME = 0.5          # รอหลังคลิก hook ก่อนเริ่ม ACQUIRE

# RESULT
RESULT_WAIT = 1.2             # ตกเสร็จ รอ 1.2 วิ ให้แอนิเมชันปลาขึ้นก่อนกดเก็บ
COLLECT_CLICK_WAIT = 1.2      # หลังคลิกเก็บปลา รอ 1.2 วิ ให้ระบบบันทึกปลา

# RECOVERY (ปลาหลุด / เบ็ดไม่เด้งกลับ)
RECOVERY_RIGHTCLICK_WAIT = 1.0   # คลิกขวาปล่อยเบ็ด แล้วรอ 0.8 วิ ให้เกมปล่อยเบ็ดแน่นอน
RECOVERY_KEY = 't'
RECOVERY_KEY_WAIT = 1.0         # กด T แล้วรอ 0.8 วิ ให้โมเดลเบ็ดใหม่เสกขึ้นมา
RECOVERY_CLICK_WAIT = 1.0       # คลิกซ้ายถือเบ็ด แล้วรอ 0.8 วิ ให้ตัวละครหยิบเบ็ดเรียบร้อย
RECOVERY_FINAL_WAIT = 1.0       # รอก่อนกลับไป CASTING

# ─── General timing ──────────────────────────────────────────────────────────
MAX_MISSING_FRAMES = 30
WAIT_COLLECT_TIME = 2.0        # (legacy, used by RESULT for backwards compat)
WAIT_BITE_TIMEOUT = 20.0

# ─── Window lock ─────────────────────────────────────────────────────────────
LOCK_WINDOW_SIZE = True
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 620

# ─── Model call throttling (CPU Load Management) ────────────────────────────
MODEL_POLL_INTERVAL = 0.40     # เว้นช่วงเรียกโมเดลหา 'mark' ตอน WAITING (ประหยัด CPU 2 คอร์)
ACQUIRE_RETRY_INTERVAL = 0.20  # ระยะรอระหว่างลองเรียกโมเดลหา bar/fish/bg_track
ACQUIRE_MAX_RETRIES = 12       # จำนวนครั้งลองหา minigame ก่อนรีเซ็ต
TRACK_RECHECK_INTERVAL = 4.0   # ความถี่เรียกโมเดล sanity-check (0 = ปิด)
TRACK_LOST_FRAMES = 10         # จำนวนเฟรมที่ CV tracker หาไม่เจอก่อนเรียกโมเดลใหม่
UI_GONE_CONFIRM_FRAMES = 5     # จำนวนเฟรมยืนยันว่า UI หายจริง

# ─── CV tracking ─────────────────────────────────────────────────────────────
TRACK_COLOR_TOLERANCE_H = 12
TRACK_COLOR_TOLERANCE_S = 70
TRACK_COLOR_TOLERANCE_V = 70
TRACK_MIN_CONTOUR_AREA = 6
TRACK_SEARCH_MARGIN = 12

# ─── Progress bar reading ────────────────────────────────────────────────────
PROGRESS_OFFSET_PCT = 0.18
PROGRESS_WIDTH_PCT = 0.06
PROGRESS_HEIGHT_MARGIN_PCT = 0.0
PROGRESS_FULL_THRESH = 0.60    # สัดส่วนความเต็มของหลอดที่นับว่าตกสำเร็จ (ปรับจาก 0.90 -> 0.60 เพื่อไม่ให้พลาด)
PROGRESS_EMPTY_THRESH = 0.15   # สัดส่วนต่ำกว่านี้ถือว่าปลาหลุด

# ─── Recovery flow ───────────────────────────────────────────────────────────
BOUNCE_CHECK_TIMEOUT = 4.0

# ─── Debug / calibration ─────────────────────────────────────────────────────
CALIBRATE_MODE = False          # ปิดโหมด Calibrate (ตั้งเป็น True เฉพาะตอนต้องการดู Telemetry ละเอียดใน Terminal หรือเซฟรูป debug)
CALIBRATE_LOG_INTERVAL = 0.08   # หน่วงเวลาระหว่างบรรทัด log ใน terminal (วิ) เพื่อให้อ่านง่ายไม่ spam
DEBUG_DIR = 'debug_frames'

# ─── PID + PWM Controller Tuning ─────────────────────────────────────────────
# error เป็น "% ของความยาว track ตามแนวแกนจริง"
#   error > 0 (+) -> ปลาอยู่สูงกว่าเบ็ด -> ต้องการแรงดึงขึ้น (Duty Cycle เพิ่มขึ้น)
#   error < 0 (-) -> เบ็ดอยู่สูงกว่าปลา -> ต้องการให้เบ็ดตก (Duty Cycle ลดลง)
#   error = 0     -> เบ็ดตรงกับปลาพอดี -> รักษาระดับด้วย BASE_DUTY (แรงลอยตัวสู้แรงโน้มถ่วง)

KP = 1.00                     # Proportional: แรงตอบสนองตามระยะห่างปัจจุบัน (แนะนำ 0.8 - 1.5)
KI = 0.05                     # Integral: แรงชดเชยสะสมป้องกันเบ็ดจม/ลอยค้าง (แนะนำ 0.02 - 0.10)
KD = 0.70                     # Derivative: แรงหน่วงเบรกกันพุ่งเลยและลดการสั่น (แนะนำ 0.50 - 1.00)
BASE_DUTY = 25.0              # Base Duty Cycle (%): แรงกดเมาส์เฉลี่ยที่ทำให้เบ็ดลอยนิ่งสู้แรงโน้มถ่วง (20% - 35%)

PWM_PERIOD = 0.12             # ความยาวรอบของ PWM Pulse (วินาที) • แนะนำ 0.10 - 0.14s (8 - 10 Hz)
MIN_DUTY = 0.0                # Duty cycle ขั้นต่ำ (%)
MAX_DUTY = 100.0              # Duty cycle สูงสุด (%)
I_MAX = 30.0                  # ขอบเขตสะสมสูงสุดของ Integral term (%) ป้องกัน Integral Windup
EMA_ALPHA = 0.45              # ค่ากรองสัญญาณรบกวนของ Error (0.0 - 1.0) • ยิ่งมากยิ่งตอบสนองไว

# Sleep time ระหว่างลูปตกปลา (0.0 = User Full FPS ใช้ความเร็วสูงสุดของจอ/ระบบ capture)
LOOP_SLEEP_TIME = 0.0

# ─── Presets ──────────────────────────────────────────────────────────────────
# ปรับแต่งตามประสิทธิภาพเครื่องจริง
PRESETS = {
    'High': {
        # เครื่องแรง (RTX 3060+, 144Hz+) — Full FPS 100+ FPS ตอบสนองฉับไว
        'LOOP_SLEEP_TIME': 0.0,
        'MODEL_POLL_INTERVAL': 0.25,
        'ACQUIRE_RETRY_INTERVAL': 0.10,
        'ACQUIRE_MAX_RETRIES': 20,
        'TRACK_RECHECK_INTERVAL': 0.0,
        'TRACK_LOST_FRAMES': 6,
        'UI_GONE_CONFIRM_FRAMES': 4,
        'EMA_ALPHA': 0.50,
        'KP': 1.10,
        'KI': 0.06,
        'KD': 0.75,
        'BASE_DUTY': 26.0,
        'PWM_PERIOD': 0.10,
        'I_MAX': 30.0,
        'CALIBRATE_LOG_INTERVAL': 0.08,
        'CONF_THRESH': 0.5,
        'FISH_CONF_THRESH': 0.3,
        'CAST_INITIAL_WAIT': 1.0,
        'CAST_HOLD_TIME': 0.12,
        'CAST_AFTER_WAIT': 0.0,
        'MARK_CLICK_WAIT': 0.0,
        'WAIT_HOOK_TIME': 0.5,
        'RESULT_WAIT': 1.8,
        'COLLECT_CLICK_WAIT': 1.5,
        'RECOVERY_RIGHTCLICK_WAIT': 1.0,
        'RECOVERY_KEY_WAIT': 1.2,
        'RECOVERY_CLICK_WAIT': 1.0,
        'RECOVERY_FINAL_WAIT': 1.0,
    },
    'Medium': {
        # เครื่องระดับกลาง — Full FPS สมดุล นิ่งและแม่นยำ
        'LOOP_SLEEP_TIME': 0.0,
        'MODEL_POLL_INTERVAL': 0.35,
        'ACQUIRE_RETRY_INTERVAL': 0.15,
        'ACQUIRE_MAX_RETRIES': 15,
        'TRACK_RECHECK_INTERVAL': 0.0,
        'TRACK_LOST_FRAMES': 8,
        'UI_GONE_CONFIRM_FRAMES': 5,
        'EMA_ALPHA': 0.45,
        'KP': 1.00,
        'KI': 0.05,
        'KD': 0.70,
        'BASE_DUTY': 25.0,
        'PWM_PERIOD': 0.12,
        'I_MAX': 30.0,
        'CALIBRATE_LOG_INTERVAL': 0.08,
        'CONF_THRESH': 0.5,
        'FISH_CONF_THRESH': 0.3,
        'CAST_INITIAL_WAIT': 1.0,
        'CAST_HOLD_TIME': 0.12,
        'CAST_AFTER_WAIT': 0.0,
        'MARK_CLICK_WAIT': 0.0,
        'WAIT_HOOK_TIME': 0.5,
        'RESULT_WAIT': 1.8,
        'COLLECT_CLICK_WAIT': 1.5,
        'RECOVERY_RIGHTCLICK_WAIT': 1.0,
        'RECOVERY_KEY_WAIT': 1.2,
        'RECOVERY_CLICK_WAIT': 1.0,
        'RECOVERY_FINAL_WAIT': 1.0,
    },
    'Low': {
        # เครื่องประหยัดพลังงาน (2-Core CPU) — เสถียร ไม่โหลดเครื่อง
        'LOOP_SLEEP_TIME': 0.005,
        'MODEL_POLL_INTERVAL': 0.40,
        'ACQUIRE_RETRY_INTERVAL': 0.20,
        'ACQUIRE_MAX_RETRIES': 12,
        'TRACK_RECHECK_INTERVAL': 0.0,
        'TRACK_LOST_FRAMES': 10,
        'UI_GONE_CONFIRM_FRAMES': 5,
        'EMA_ALPHA': 0.40,
        'KP': 0.90,
        'KI': 0.04,
        'KD': 0.65,
        'BASE_DUTY': 24.0,
        'PWM_PERIOD': 0.14,
        'I_MAX': 25.0,
        'CALIBRATE_LOG_INTERVAL': 0.10,
        'CONF_THRESH': 0.50,
        'FISH_CONF_THRESH': 0.30,
        'CAST_INITIAL_WAIT': 1.0,
        'CAST_HOLD_TIME': 0.12,
        'CAST_AFTER_WAIT': 0.0,
        'MARK_CLICK_WAIT': 0.0,
        'WAIT_HOOK_TIME': 0.5,
        'RESULT_WAIT': 1.8,
        'COLLECT_CLICK_WAIT': 1.5,
        'RECOVERY_RIGHTCLICK_WAIT': 1.0,
        'RECOVERY_KEY_WAIT': 1.2,
        'RECOVERY_CLICK_WAIT': 1.0,
        'RECOVERY_FINAL_WAIT': 1.0,
    },
}