import win32gui
import numpy as np
import cv2

def get_window_rect(window_name):
    handle_window = win32gui.FindWindow(None, window_name)
    if handle_window:
        xyxy_position = win32gui.GetWindowRect(handle_window)
        return xyxy_position
    return None

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