import win32gui
import win32con
import numpy as np
import cv2


def bring_window_to_front(window_name):
    """ดึงหน้าต่างเกมขึ้นมาแสดงและโฟกัส (bring to foreground) 100%
    ใช้ AttachThreadInput + BringWindowToTop เพื่อ bypass ข้อจำกัดของ Windows"""
    handle = win32gui.FindWindow(None, window_name)
    if not handle:
        return False
    try:
        import win32process
        import win32api

        # 1. ขยายหน้าต่างถ้าถูกย่อไว้
        if win32gui.IsIconic(handle):
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(handle, win32con.SW_SHOW)

        # 2. Bypass ข้อจำกัดสิทธิ์ของ Windows ด้วย AttachThreadInput
        fore_hwnd = win32gui.GetForegroundWindow()
        cur_thread_id = win32api.GetCurrentThreadId()
        fore_thread_id, _ = win32process.GetWindowThreadProcessId(fore_hwnd)

        if fore_thread_id != cur_thread_id:
            try:
                win32process.AttachThreadInput(cur_thread_id, fore_thread_id, True)
            except Exception:
                pass

        # 3. ดึงหน้าต่างขึ้นบนสุดและโฟกัส
        win32gui.BringWindowToTop(handle)
        win32gui.SetForegroundWindow(handle)
        win32gui.SetWindowPos(
            handle, win32con.HWND_TOP, 0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
        )

        if fore_thread_id != cur_thread_id:
            try:
                win32process.AttachThreadInput(cur_thread_id, fore_thread_id, False)
            except Exception:
                pass

        return True
    except Exception as e:
        try:
            win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(handle)
            return True
        except Exception:
            print(f'[GameCapture] bring_window_to_front failed: {e}')
            return False


def move_cursor_to_window(window_name):
    """ย้ายเคอร์เซอร์เมาส์เข้าไปอยู่ตรงกลางหน้าต่างเกม กันเผลอคลิกโดน background / หน้าต่างอื่น"""
    rect = get_client_rect_screen(window_name)
    if rect is None:
        return False
    left, top, right, bottom = rect
    cx = int((left + right) / 2)
    cy = int((top + bottom) / 2)
    try:
        import win32api
        win32api.SetCursorPos((cx, cy))
        return True
    except Exception:
        import ctypes
        ctypes.windll.user32.SetCursorPos(cx, cy)
        return True


def get_window_handle(window_name):
    return win32gui.FindWindow(None, window_name)


def get_window_rect(window_name):
    handle_window = win32gui.FindWindow(None, window_name)
    if handle_window:
        xyxy_position = win32gui.GetWindowRect(handle_window)
        return xyxy_position
    return None


def get_client_rect_screen(window_name):
    """คืนกรอบ 'client area' (ไม่รวม title bar/border) เทียบพิกัดจอจริง
    ใช้อันนี้แทน GetWindowRect เวลาต้องคำนวณ offset จากขอบเกม เพราะ
    title bar/border ทำให้พิกัดเพี้ยนได้"""
    handle_window = get_window_handle(window_name)
    if not handle_window:
        return None
    left, top, right, bottom = win32gui.GetClientRect(handle_window)
    left_top = win32gui.ClientToScreen(handle_window, (left, top))
    right_bottom = win32gui.ClientToScreen(handle_window, (right, bottom))
    return (left_top[0], left_top[1], right_bottom[0], right_bottom[1])


def set_window_size(window_name, width, height):
    """Lock ขนาด client-area ของหน้าต่างเกมให้คงที่ เพื่อให้ capture region/
    offset ที่ calibrate ไว้ใช้ได้เสมอในทุก session ไม่ต้องคำนวณสเกลใหม่ทุกครั้ง.
    คืนค่า True ถ้าทำสำเร็จ, False ถ้าหาไม่เจอ/ผิดพลาด"""
    handle_window = get_window_handle(window_name)
    if not handle_window:
        return False
    try:
        win_l, win_t, win_r, win_b = win32gui.GetWindowRect(handle_window)
        cli_l, cli_t, cli_r, cli_b = win32gui.GetClientRect(handle_window)
        # ส่วนต่างระหว่างขนาดหน้าต่างทั้งก้อนกับ client area (border/title bar)
        border_w = (win_r - win_l) - (cli_r - cli_l)
        border_h = (win_b - win_t) - (cli_b - cli_t)

        win32gui.SetWindowPos(
            handle_window, win32con.HWND_TOP,
            win_l, win_t,
            width + border_w, height + border_h,
            win32con.SWP_NOZORDER
        )
        return True
    except Exception as e:
        print(f'[GameCapture] set_window_size failed: {e}')
        return False


def get_game_screen(sct, window_name='VRChat'):
    xyxy = get_window_rect(window_name=window_name)

    if xyxy is None:
        return None

    monitor = {
        'left': xyxy[0],
        'top': xyxy[1],
        'width': xyxy[2] - xyxy[0],
        'height': xyxy[3] - xyxy[1]
    }

    screenshot = sct.grab(monitor)
    frame = np.array(screenshot)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    return frame


def get_region_screen(sct, left, top, width, height):
    """Capture เฉพาะ sub-region ของจอจริง (พิกัด absolute) แทนที่จะจับทั้งหน้าต่าง
    แล้วมา crop ทีหลัง — เร็วกว่าเพราะ mss จับแค่พื้นที่เล็กลง ใช้ช่วง FISHING ที่รู้
    ตำแหน่ง bg_track แน่นอนแล้ว"""
    if width <= 0 or height <= 0:
        return None
    monitor = {'left': int(left), 'top': int(top), 'width': int(width), 'height': int(height)}
    screenshot = sct.grab(monitor)
    raw = np.frombuffer(screenshot.raw, dtype=np.uint8).reshape((screenshot.height, screenshot.width, 4))
    frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
    return frame