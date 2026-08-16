import ctypes
import time


MOUSEEVENTF_LEFTDOWN = 0x0002   # กด
MOUSEEVENTF_LEFTUP = 0x0004     # ปล่อย


def click():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)  # กด
    time.sleep(0.05)    # รอแปปนึง
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)    # ปล่อย
    

def mouse_down():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)  # กดค้าง
    
    
def mouse_up():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)    # ปล่อย