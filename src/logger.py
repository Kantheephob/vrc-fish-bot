"""
logger.py — Colored terminal logger for VRC FISH! bot

ใช้ ANSI escape codes แสดงสีใน terminal เพื่อให้อ่าน log ง่ายขึ้น
แต่ละ state มีสีต่างกัน และ events สำคัญมี emoji กำกับ
"""

import sys
import time
import io
from datetime import datetime


def _safe_print(text):
    """Print text safely — handle encoding errors on consoles like cp874 (Thai Windows)
    by replacing un-encodable characters instead of crashing."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: encode with 'replace' then decode back
        encoding = sys.stdout.encoding or 'utf-8'
        safe = text.encode(encoding, errors='replace').decode(encoding, errors='replace')
        print(safe)


# ─── ANSI color codes ────────────────────────────────────────────────────────
class _C:
    RESET   = '\033[0m'
    BOLD    = '\033[1m'
    DIM     = '\033[2m'

    # Foreground
    BLACK   = '\033[30m'
    RED     = '\033[31m'
    GREEN   = '\033[32m'
    YELLOW  = '\033[33m'
    BLUE    = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN    = '\033[36m'
    WHITE   = '\033[37m'

    # Bright foreground
    BRIGHT_RED     = '\033[91m'
    BRIGHT_GREEN   = '\033[92m'
    BRIGHT_YELLOW  = '\033[93m'
    BRIGHT_BLUE    = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN    = '\033[96m'
    BRIGHT_WHITE   = '\033[97m'

    # Background
    BG_RED    = '\033[41m'
    BG_GREEN  = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE   = '\033[44m'


# ─── State -> color/symbol mapping ────────────────────────────────────────────
STATE_STYLE = {
    'CASTING':      (_C.BRIGHT_YELLOW, '>'),
    'WAITING':      (_C.BRIGHT_BLUE,   '~'),
    'ACQUIRE':      (_C.BRIGHT_CYAN,   '*'),
    'FISHING':      (_C.BRIGHT_GREEN,  '#'),
    'RESULT':       (_C.BRIGHT_MAGENTA,'='),
    'BOUNCE_CHECK': (_C.YELLOW,        '?'),
    'RECOVER':      (_C.BRIGHT_RED,    '!'),
}

# ─── Special event symbols ────────────────────────────────────────────────────
EVENT_ICONS = {
    'cast':     '>',
    'bite':     '!',
    'caught':   '+',
    'escaped':  '-',
    'recover':  '!',
    'hook':     '^',
    'start':    '>',
    'stop':     'x',
    'error':    'X',
    'warning':  '!',
    'info':     'i',
    'track':    '*',
    'progress': '=',
}


def _enable_ansi_windows():
    """Enable ANSI escape code processing on Windows 10+ console."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandleA(-11)
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


_enable_ansi_windows()


class BotLogger:
    """Colored logger for the fishing bot."""

    def __init__(self, name='Bot'):
        self.name = name
        self._start_time = time.time()

    def _timestamp(self):
        return datetime.now().strftime('%H:%M:%S')

    def _format_state(self, state):
        color, emoji = STATE_STYLE.get(state, (_C.WHITE, '❓'))
        return f'{color}{_C.BOLD}{emoji} {state:13s}{_C.RESET}'

    def log(self, state, msg, event=None):
        """Log a message with state coloring.

        Args:
            state: Current bot state (CASTING, WAITING, etc.)
            msg: Message text
            event: Optional event key for special emoji (bite, caught, etc.)
        """
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        state_str = self._format_state(state)

        prefix = ''
        if event and event in EVENT_ICONS:
            prefix = f'{EVENT_ICONS[event]} '

        _safe_print(f'{ts} {state_str} {prefix}{msg}')

    def info(self, msg):
        """General info message (no state)."""
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        _safe_print(f'{ts} {_C.BRIGHT_CYAN}{_C.BOLD}[INFO]        {_C.RESET} {msg}')

    def warn(self, msg):
        """Warning message."""
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        _safe_print(f'{ts} {_C.BRIGHT_YELLOW}{_C.BOLD}[WARNING]     {_C.RESET} {_C.YELLOW}{msg}{_C.RESET}')

    def error(self, msg):
        """Error message."""
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        _safe_print(f'{ts} {_C.BRIGHT_RED}{_C.BOLD}[ERROR]       {_C.RESET} {_C.RED}{msg}{_C.RESET}')

    def success(self, msg):
        """Success message."""
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        _safe_print(f'{ts} {_C.BRIGHT_GREEN}{_C.BOLD}[SUCCESS]     {_C.RESET} {_C.GREEN}{msg}{_C.RESET}')

    def pid_telemetry(self, state, telemetry):
        """Rich calibration log with FPS, error, PID terms, PWM duty cycle, and progress."""
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        state_str = self._format_state(state)

        fps = telemetry.get('fps', 0.0)
        err = telemetry.get('filtered_error', 0.0)
        p_val = telemetry.get('p_term', 0.0)
        i_val = telemetry.get('i_term', 0.0)
        d_val = telemetry.get('d_term', 0.0)
        duty = telemetry.get('duty_cycle', 0.0)
        is_down = telemetry.get('mouse_down', False)
        prog = telemetry.get('progress', 0.0)

        # Color-code error value
        abs_err = abs(err)
        if abs_err < 4.0:
            err_color = _C.BRIGHT_GREEN
        elif abs_err < 12.0:
            err_color = _C.BRIGHT_YELLOW
        else:
            err_color = _C.BRIGHT_RED

        # Color-code mouse / PWM state
        if is_down:
            act_str = f'{_C.BRIGHT_MAGENTA}{_C.BOLD}DOWN{_C.RESET}'
        else:
            act_str = f'{_C.DIM}UP  {_C.RESET}'

        # Visual duty cycle bar (10 chars)
        duty_clamped = max(0.0, min(100.0, duty))
        duty_filled = int(round(duty_clamped / 10.0))
        duty_bar = f'{_C.BRIGHT_CYAN}{"#" * duty_filled}{_C.DIM}{"." * (10 - duty_filled)}{_C.RESET}'

        # Visual progress bar (10 chars)
        prog_clamped = max(0.0, min(1.0, prog))
        prog_filled = int(round(prog_clamped * 10.0))
        prog_bar = f'{_C.BRIGHT_GREEN}{"=" * prog_filled}{_C.DIM}{"." * (10 - prog_filled)}{_C.RESET}'

        fps_str = f'{_C.BRIGHT_CYAN}{fps:4.0f} FPS{_C.RESET}'

        _safe_print(
            f'{ts} {state_str} {fps_str} | '
            f'Err:{err_color}{err:+5.1f}%{_C.RESET} | '
            f'PID:({_C.WHITE}P{_C.RESET}{p_val:+5.1f} {_C.WHITE}I{_C.RESET}{i_val:+4.1f} {_C.WHITE}D{_C.RESET}{d_val:+5.1f}) | '
            f'Duty:{_C.BRIGHT_CYAN}{duty:4.0f}%{_C.RESET}[{duty_bar}] ({act_str}) | '
            f'Prog:[{prog_bar}]{prog:3.0%}'
        )

    def fishing_status(self, state, error_val, output_val, action, progress):
        """Legacy status fallback."""
        ts = f'{_C.DIM}{self._timestamp()}{_C.RESET}'
        state_str = self._format_state(state)

        if abs(error_val) < 3:
            err_color = _C.GREEN
        elif abs(error_val) < 10:
            err_color = _C.YELLOW
        else:
            err_color = _C.RED

        act_colors = {'up': _C.CYAN, 'down': _C.MAGENTA, 'click': _C.YELLOW}
        act_color = act_colors.get(action, _C.WHITE)

        filled = int(progress * 10)
        bar = f'{_C.GREEN}{"#" * filled}{_C.DIM}{"." * (10 - filled)}{_C.RESET}'

        _safe_print(
            f'{ts} {state_str} '
            f'err={err_color}{error_val:+6.1f}{_C.RESET} '
            f'out={output_val:+6.1f} '
            f'act={act_color}{action:5s}{_C.RESET} '
            f'[{bar}] {progress:.0%}'
        )


    def divider(self, char='-', width=60):
        """Print a visual divider line."""
        _safe_print(f'{_C.DIM}{char * width}{_C.RESET}')

    def banner(self, msg):
        """Print a prominent banner message."""
        width = len(msg) + 4
        _safe_print(f'\n{_C.BRIGHT_CYAN}{_C.BOLD}{"=" * width}')
        _safe_print(f'  {msg}')
        _safe_print(f'{"=" * width}{_C.RESET}\n')


# Module-level singleton for convenience
bot_logger = BotLogger()
