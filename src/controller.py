import ctypes
import time
from ctypes import wintypes
from pynput.keyboard import Controller as KeyboardController, Key


# ─── Windows Mouse & Keyboard Constants ───────────────────────────────────────
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

_keyboard = KeyboardController()

# ─── ctypes SendInput Structures (DirectX / Unity Compatible) ────────────────
PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL)
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", PUL)
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]


class Input_I(ctypes.Union):
    _fields_ = [
        ("ki", KeyBdInput),
        ("mi", MouseInput),
        ("hi", HardwareInput)
    ]


class Input(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ii", Input_I)
    ]


# Scan code table for standard keys (QWERTY)
SCAN_CODES = {
    't': 0x14,
    'T': 0x14,
    'e': 0x12,
    'E': 0x12,
    'r': 0x13,
    'R': 0x13,
    'f': 0x21,
    'F': 0x21,
    'space': 0x39,
    '1': 0x02,
    '2': 0x03,
    '3': 0x04,
}


def _send_hardware_key(scan_code, hold_duration=0.15):
    """ส่ง Hardware Keyboard Scan Code ผ่าน Windows SendInput API
    รองรับ DirectX 11/12, DirectInput และ Unity Engine (VRChat) 100%"""
    extra = ctypes.c_ulong(0)

    # 1. Key Down
    ii_down = Input_I()
    ii_down.ki = KeyBdInput(0, scan_code, KEYEVENTF_SCANCODE, 0, ctypes.pointer(extra))
    input_down = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_down)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(input_down), ctypes.sizeof(input_down))

    time.sleep(hold_duration)

    # 2. Key Up
    ii_up = Input_I()
    ii_up.ki = KeyBdInput(0, scan_code, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
    input_up = Input(ctypes.c_ulong(INPUT_KEYBOARD), ii_up)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(input_up), ctypes.sizeof(input_up))


def press_key(key_char, hold_duration=0.15):
    """กดปุ่มคีย์บอร์ด — ใช้ Hardware Scan Code ผ่าน SendInput เพื่อให้ VRChat รับสัญญาณชัวร์"""
    char_lower = str(key_char).lower()
    scan_code = SCAN_CODES.get(char_lower)

    if scan_code is None:
        # หา Scan code จาก Virtual Key
        vk = ord(char_lower.upper()) if len(char_lower) == 1 else 0
        scan_code = ctypes.windll.user32.MapVirtualKeyA(vk, 0) if vk else 0

    if scan_code:
        try:
            _send_hardware_key(scan_code, hold_duration=hold_duration)
            return
        except Exception:
            pass

    # Fallback to keybd_event & pynput if SendInput fails
    try:
        vk_code = ord(char_lower.upper())
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        time.sleep(hold_duration)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        _keyboard.press(key_char)
        time.sleep(hold_duration)
        _keyboard.release(key_char)


def click(hold_duration=0.10):
    """คลิกซ้าย"""
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(hold_duration)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def mouse_down():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)


def mouse_up():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def right_click(hold_duration=0.10):
    """คลิกขวา — ปล่อยเบ็ด"""
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
    time.sleep(hold_duration)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)