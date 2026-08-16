import time
import threading
import mss
from collections import deque

from game_capture import get_game_screen
from detector import detection
import controller
import config as c


class FishingBot:
    def __init__(self, session):
        self.session = session
        self.is_running = False
        self.state = 'CASTING'
        self.thread = None

        self.missing_frames = 0
        self.last_action_time = 0
        self.last_distance = 0.0     # เก็บ filtered_error รอบก่อนหน้า สำหรับ Derivative (D)
        self.wait_start_time = 0

        # --- เพิ่มใหม่ สำหรับแก้ปัญหาสวิง ---
        self.filtered_error = 0.0    # ค่า error หลังผ่าน EMA filter
        self.last_time = time.time()
        self.current_action = 'up'   # state ปัจจุบันของ actuator: 'up' | 'down' | 'click'

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.state = 'CASTING'
            self.missing_frames = 0
            self.last_distance = 0.0
            self.filtered_error = 0.0
            self.last_time = time.time()
            self.current_action = 'up'
            self.thread = threading.Thread(target=self.run_loop, daemon=True)
            self.thread.start()
            print('[Bot] Starting PD-Controller Fishing...')

    def stop(self):
        self.is_running = False
        controller.mouse_up()
        print('[Bot] Stopped.')

    def run_loop(self):
        with mss.MSS() as sct:
            while self.is_running:
                frame = get_game_screen(sct, window_name=c.APP)
                if frame is None:
                    time.sleep(1.0)
                    continue

                detections = detection(self.session, frame)
                found_mark = any(d['class_name'] == 'mark' for d in detections)
                found_bar = any(d['class_name'] == 'bar' for d in detections)
                found_fish = any(d['class_name'] == 'fish' for d in detections)

                if self.state == 'CASTING':
                    time.sleep(1.0)
                    controller.mouse_down()
                    time.sleep(0.1)
                    controller.mouse_up()
                    time.sleep(1.5)
                    self.wait_start_time = time.time()
                    self.state = 'WAITING'

                elif self.state == 'WAITING':
                    if found_mark:
                        controller.click()
                        self.state = 'FISHING'
                        self.last_distance = 0.0
                        self.filtered_error = 0.0
                        self.last_time = time.time()
                        self.current_action = 'up'
                        time.sleep(c.WAIT_HOOK_TIME)
                    elif time.time() - self.wait_start_time > c.WAIT_BITE_TIMEOUT:
                        self.state = 'CASTING'

                elif self.state == 'FISHING':
                    if found_bar and found_fish:
                        self.missing_frames = 0
                        bar_data = next(d for d in detections if d['class_name'] == 'bar')
                        fish_data = next(d for d in detections if d['class_name'] == 'fish')

                        now = time.time()
                        dt = max(now - self.last_time, 1e-3)  # กัน dt=0 หรือติดลบ
                        self.last_time = now

                        # error ดิบจาก detection (มี noise ทุกเฟรม)
                        raw_error = fish_data['center'][1] - bar_data['center'][1]

                        # 1) EMA smoothing กัน noise ก่อนเข้า controller
                        self.filtered_error = (
                            c.EMA_ALPHA * raw_error
                            + (1 - c.EMA_ALPHA) * self.filtered_error
                        )

                        # 2) derivative normalize ด้วยเวลาจริง (ต่อวินาที ไม่ใช่ต่อเฟรม)
                        derivative = (self.filtered_error - self.last_distance) / dt
                        self.last_distance = self.filtered_error

                        # --- PD Controller Calculation ---
                        output = (c.KP * self.filtered_error) + (c.KD * derivative)

                        # 3) Hysteresis state machine กันการสลับ action รัวๆ (chattering)
                        # โซนเดิม: down < -15, click -15..-2, up -2..15+, up > 15
                        # เพิ่ม HYSTERESIS (h) เป็นระยะกันชนรอบๆ threshold แต่ละจุด
                        h = c.HYSTERESIS

                        if self.current_action == 'down':
                            # อยู่ในสถานะกดค้าง จะออกก็ต่อเมื่อ error ขยับพ้นโซนไปจริงๆ
                            if output > -15 + h:
                                self.current_action = 'click' if output < -2 else 'up'
                        elif self.current_action == 'click':
                            if output < -15 - h:
                                self.current_action = 'down'
                            elif output > -2 + h:
                                self.current_action = 'up'
                        else:  # 'up'
                            if output < -15 - h:
                                self.current_action = 'down'
                            elif output < -2 - h:
                                self.current_action = 'click'
                            # else: อยู่ในโซน up ต่อ ไม่ทำอะไร

                        if self.current_action == 'down':
                            controller.mouse_down()
                        elif self.current_action == 'click':
                            controller.click()
                        else:
                            controller.mouse_up()
                    else:
                        self.missing_frames += 1
                        if self.missing_frames > c.MAX_MISSING_FRAMES:
                            controller.mouse_up()
                            self.current_action = 'up'
                            time.sleep(1.0)
                            # เช็คว่าหลุดหรือตกได้
                            if abs(self.last_distance) > 150:
                                time.sleep(1.0)
                            else:
                                time.sleep(c.WAIT_COLLECT_TIME)
                                controller.click()
                                time.sleep(2.0)
                            self.state = 'CASTING'

                time.sleep(c.LOOP_SLEEP_TIME)