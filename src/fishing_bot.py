import time
import threading
import os
import mss
import cv2

from game_capture import get_game_screen, get_region_screen, get_window_rect, set_window_size, bring_window_to_front, move_cursor_to_window
from detector import detection
from tracker import ColorBlobTracker, read_progress_fraction, estimate_track_axis
from pid_pwm import PIDPWMController
from logger import bot_logger as log
import controller
import config as c


def _pick_best(detections, class_name):
    """เลือก detection ที่ score สูงสุดของคลาสนั้น (กันกรณีโมเดลเห็นซ้ำ)"""
    candidates = [d for d in detections if d['class_name'] == class_name]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d['score'])


class FishingBot:
    def __init__(self, session):
        self.session = session
        self.is_running = False
        self.state = 'CASTING'
        self.thread = None

        self.missing_frames = 0
        self.last_action_time = 0
        self.wait_start_time = 0

        # --- PID + PWM Controller ---
        self.pid = PIDPWMController()
        self.last_telemetry_log_time = 0.0

        # --- ACQUIRE / tracking state ---
        self.acquire_attempts = 0
        self.bar_tracker = None
        self.fish_tracker = None
        self.capture_region_abs = None   # (left, top, width, height) พิกัดจอจริง
        self.progress_box_local = None   # (x1,y1,x2,y2) เทียบ capture_region
        self.track_axis = (0.0, 1.0)     # (ux, uy) unit vector ของแกน track รองรับ UI เอียง
        self.track_length = 1.0          # ความยาวของ track ตามแนวแกนจริง (px)
        self.bar_half_h_pct = 6.0        # รัศมีปลอดภัยของแท่งเบ็ด (% ของ track_length) คำนวณจากขนาดจริง
        self.last_progress_fraction = 0.0
        self.max_progress = 0.0
        self.last_recheck_time = 0
        self.ui_gone_streak = 0
        self.window_name = c.APP

        if c.CALIBRATE_MODE:
            os.makedirs(c.DEBUG_DIR, exist_ok=True)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.state = 'CASTING'
            self.missing_frames = 0
            self.max_progress = 0.0
            self.pid.reset()
            self.last_telemetry_log_time = 0.0

            # Bring game window to front & lock cursor into game window
            if bring_window_to_front(self.window_name):
                log.info(f'Game window "{self.window_name}" brought to front')
                if move_cursor_to_window(self.window_name):
                    log.info('Mouse cursor centered in game window')
            else:
                log.warn(f'Could not find window "{self.window_name}" — make sure the game is running')

            self.thread = threading.Thread(target=self.run_loop, daemon=True)
            self.thread.start()
            log.banner('VRC FISH! Bot Started')
            log.info(f'Controller: PID + PWM | Full FPS Mode (Sleep: {c.LOOP_SLEEP_TIME}s)')

    def stop(self):
        self.is_running = False
        self.pid.stop()
        controller.mouse_up()
        log.banner('VRC FISH! Bot Stopped')

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _log(self, msg, event=None):
        log.log(self.state, msg, event=event)

    def _lock_window(self):
        if not c.LOCK_WINDOW_SIZE:
            return
        ok = set_window_size(self.window_name, c.WINDOW_WIDTH, c.WINDOW_HEIGHT)
        if ok:
            self._log(f'Window locked to {c.WINDOW_WIDTH}x{c.WINDOW_HEIGHT}')
        else:
            log.warn('Could not lock window size (window not found?)')

    def _setup_tracking_from_boxes(self, frame, bar_det, fish_det, bg_det):
        """สร้าง trackers + คำนวณ capture region และ orientation vector ของ bg_track
        รองรับ UI ที่เอียง (tilted) ได้แม่นยำ"""
        bx1, by1, bx2, by2 = bg_det['box']
        bg_w = max(1, bx2 - bx1)
        bg_h = max(1, by2 - by1)

        # ประมาณแกนความยาวและมุมเอียงของ track
        ux, uy, track_len = estimate_track_axis(frame, bg_det['box'])
        self.track_axis = (ux, uy)
        self.track_length = max(1.0, track_len)

        prog_offset_px = bg_w * c.PROGRESS_OFFSET_PCT
        prog_width_px = bg_w * c.PROGRESS_WIDTH_PCT
        prog_margin_px = bg_h * c.PROGRESS_HEIGHT_MARGIN_PCT

        # ขยายกรอบ capture ให้ครอบคลุมทั้ง bg_track + progress bar
        margin = c.TRACK_SEARCH_MARGIN
        region_x1 = max(0, bx1 - margin)
        region_y1 = max(0, by1 - margin)
        region_x2 = bx2 + prog_offset_px + prog_width_px + margin
        region_y2 = by2 + margin

        win_rect = get_window_rect(self.window_name)
        if win_rect is None:
            log.error('Window disappeared during ACQUIRE')
            return False
        win_left, win_top, _, _ = win_rect

        self.capture_region_abs = (
            win_left + region_x1,
            win_top + region_y1,
            region_x2 - region_x1,
            region_y2 - region_y1,
        )

        def to_local(box):
            x1, y1, x2, y2 = box
            return (x1 - region_x1, y1 - region_y1, x2 - region_x1, y2 - region_y1)

        bar_local = to_local(bar_det['box'])
        fish_local = to_local(fish_det['box'])

        self.progress_box_local = (
            int((bx2 - region_x1) + prog_offset_px),
            int(by1 - region_y1 + prog_margin_px),
            int((bx2 - region_x1) + prog_offset_px + prog_width_px),
            int(by2 - region_y1 - prog_margin_px),
        )

        self.bar_tracker = ColorBlobTracker(
            frame, bar_det['box'],
            tol_h=c.TRACK_COLOR_TOLERANCE_H, tol_s=c.TRACK_COLOR_TOLERANCE_S,
            tol_v=c.TRACK_COLOR_TOLERANCE_V, min_area=c.TRACK_MIN_CONTOUR_AREA,
        )
        self.fish_tracker = ColorBlobTracker(
            frame, fish_det['box'],
            tol_h=c.TRACK_COLOR_TOLERANCE_H, tol_s=c.TRACK_COLOR_TOLERANCE_S,
            tol_v=c.TRACK_COLOR_TOLERANCE_V, min_area=c.TRACK_MIN_CONTOUR_AREA,
        )

        self.bar_tracker.last_center = ((bar_local[0] + bar_local[2]) // 2, (bar_local[1] + bar_local[3]) // 2)
        self.fish_tracker.last_center = ((fish_local[0] + fish_local[2]) // 2, (fish_local[1] + fish_local[3]) // 2)

        # คำนวณขนาดจริงของแถบเบ็ดในรอบนี้ (ปรับตัวตามประเภทเบ็ดและความยากของปลาอัตโนมัติ)
        bar_box = bar_det['box']
        bar_h = bar_box[3] - bar_box[1]
        self.bar_half_h_pct = max(3.5, ((bar_h / 2.0) / max(self.track_length, 1.0)) * 100.0)

        self.pid.reset()
        self.last_telemetry_log_time = 0.0
        self.max_progress = 0.0
        self.last_progress_fraction = 0.0

        self._log(
            f'Tracking acquired | track_len={self.track_length:.1f}px axis=({ux:.2f},{uy:.2f}) '
            f'bar_radius={self.bar_half_h_pct:.1f}% region={self.capture_region_abs}',
            event='track'
        )

        if c.CALIBRATE_MODE:
            dbg = frame.copy()
            cv2.rectangle(dbg, (bx1, by1), (bx2, by2), (0, 255, 0), 2)
            px1 = int(bx2 + prog_offset_px)
            py1 = int(by1 + prog_margin_px)
            px2 = int(bx2 + prog_offset_px + prog_width_px)
            py2 = int(by2 - prog_margin_px)
            cv2.rectangle(dbg, (px1, py1), (px2, py2), (0, 0, 255), 2)
            path = os.path.join(c.DEBUG_DIR, f'acquire_{int(time.time())}.png')
            cv2.imwrite(path, dbg)

        return True

    def _reacquire_via_model(self, sct):
        """เรียกโมเดล 1 ครั้งบนภาพเต็มหน้าต่าง เพื่อยืนยัน/แก้ตำแหน่ง bar/fish/bg_track"""
        frame = get_game_screen(sct, window_name=self.window_name)
        if frame is None:
            return None
        detections = detection(self.session, frame)
        bar_det = _pick_best(detections, 'bar')
        fish_det = _pick_best(detections, 'fish')
        bg_det = _pick_best(detections, 'bg_track')
        return frame, bar_det, fish_det, bg_det

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------

    def run_loop(self):
        with mss.MSS() as sct:
            self._lock_window()

            while self.is_running:
                if self.state == 'CASTING':
                    self._log('Casting line...', event='cast')
                    if c.CAST_INITIAL_WAIT > 0:
                        time.sleep(c.CAST_INITIAL_WAIT)
                    controller.mouse_down()
                    time.sleep(c.CAST_HOLD_TIME)
                    controller.mouse_up()
                    if c.CAST_AFTER_WAIT > 0:
                        time.sleep(c.CAST_AFTER_WAIT)
                    self.wait_start_time = time.time()
                    self.last_action_time = 0
                    self.state = 'WAITING'

                elif self.state == 'WAITING':
                    now = time.time()
                    if now - self.last_action_time >= c.MODEL_POLL_INTERVAL:
                        self.last_action_time = now
                        frame = get_game_screen(sct, window_name=self.window_name)
                        if frame is not None:
                            detections = detection(self.session, frame)
                            if any(d['class_name'] == 'mark' for d in detections):
                                self._log('Bite detected! Hooking...', event='bite')
                                if c.MARK_CLICK_WAIT > 0:
                                    time.sleep(c.MARK_CLICK_WAIT)
                                controller.click()
                                self.acquire_attempts = 0
                                self.state = 'ACQUIRE'
                                time.sleep(c.WAIT_HOOK_TIME)
                                continue
                    if time.time() - self.wait_start_time > c.WAIT_BITE_TIMEOUT:
                        self._log('No bite within timeout → re-casting')
                        self.state = 'CASTING'
                    time.sleep(0.08)  # idle: ประหยัด CPU

                elif self.state == 'ACQUIRE':
                    result = self._reacquire_via_model(sct)
                    if result is None:
                        time.sleep(c.ACQUIRE_RETRY_INTERVAL)
                        continue
                    frame, bar_det, fish_det, bg_det = result
                    if bar_det and fish_det and bg_det:
                        ok = self._setup_tracking_from_boxes(frame, bar_det, fish_det, bg_det)
                        if ok:
                            self.missing_frames = 0
                            self.last_recheck_time = time.time()
                            self.ui_gone_streak = 0
                            self.state = 'FISHING'
                        else:
                            self.state = 'CASTING'
                    else:
                        self.acquire_attempts += 1
                        self._log(
                            f'Waiting for minigame elements... attempt {self.acquire_attempts}/{c.ACQUIRE_MAX_RETRIES} '
                            f'(bar={bool(bar_det)} fish={bool(fish_det)} bg={bool(bg_det)})'
                        )
                        if self.acquire_attempts >= c.ACQUIRE_MAX_RETRIES:
                            self._log('Could not acquire minigame elements → back to CASTING')
                            self.state = 'CASTING'
                        else:
                            time.sleep(c.ACQUIRE_RETRY_INTERVAL)

                elif self.state == 'FISHING':
                    self._run_fishing_step(sct)
                    continue  # Full FPS: ไม่ sleep ในลูปหลัก

                elif self.state == 'RESULT':
                    self._handle_result()

                elif self.state == 'BOUNCE_CHECK':
                    now = time.time()
                    if now - self.last_action_time >= c.MODEL_POLL_INTERVAL:
                        self.last_action_time = now
                        frame = get_game_screen(sct, window_name=self.window_name)
                        if frame is not None:
                            detections = detection(self.session, frame)
                            if any(d['class_name'] == 'mark' for d in detections):
                                self._log('Hook bounced back and bit again → hooking', event='bite')
                                controller.click()
                                self.acquire_attempts = 0
                                self.state = 'ACQUIRE'
                                time.sleep(c.WAIT_HOOK_TIME)
                                continue
                    if time.time() - self.wait_start_time > c.BOUNCE_CHECK_TIMEOUT:
                        self._log('Hook did not return in time → RECOVER')
                        self.state = 'RECOVER'
                    time.sleep(0.08)

                elif self.state == 'RECOVER':
                    self._log('Running recovery macro', event='recover')
                    controller.right_click()
                    time.sleep(c.RECOVERY_RIGHTCLICK_WAIT)
                    controller.press_key(c.RECOVERY_KEY)
                    time.sleep(c.RECOVERY_KEY_WAIT)
                    controller.click()
                    time.sleep(c.RECOVERY_CLICK_WAIT)
                    time.sleep(c.RECOVERY_FINAL_WAIT)
                    self.state = 'CASTING'

                time.sleep(0.002)

    # ------------------------------------------------------------------
    # FISHING state internals
    # ------------------------------------------------------------------

    def _run_fishing_step(self, sct):
        left, top, width, height = self.capture_region_abs
        frame = get_region_screen(sct, left, top, width, height)

        if frame is None or frame.size == 0:
            self._note_ui_maybe_gone(sct)
            if c.LOOP_SLEEP_TIME > 0:
                time.sleep(c.LOOP_SLEEP_TIME)
            return

        # periodic sanity recheck (ถ้าเปิดไว้; ปกติตั้ง 0 เพื่อ Full FPS ไม่ให้กระตุก)
        if c.TRACK_RECHECK_INTERVAL > 0 and time.time() - self.last_recheck_time >= c.TRACK_RECHECK_INTERVAL:
            self.last_recheck_time = time.time()
            result = self._reacquire_via_model(sct)
            if result is not None:
                full_frame, bar_det, fish_det, bg_det = result
                if bar_det and fish_det and bg_det:
                    self._log('Sanity recheck OK, re-syncing tracker', event='track')
                    self._setup_tracking_from_boxes(full_frame, bar_det, fish_det, bg_det)
                    self.ui_gone_streak = 0
                else:
                    self.ui_gone_streak += 1
                    if self.ui_gone_streak >= 2:
                        self._log('Fishing UI confirmed gone (sanity recheck) → RESULT')
                        self.state = 'RESULT'
                        return

        # อ่าน progress bar
        if self.progress_box_local is not None:
            self.last_progress_fraction = read_progress_fraction(frame, self.progress_box_local)

        margin = c.TRACK_SEARCH_MARGIN
        bar_found, bar_center = self.bar_tracker.update(frame, self.bar_tracker.search_box_for(margin))
        fish_found, fish_center = self.fish_tracker.update(frame, self.fish_tracker.search_box_for(margin))

        if bar_found and fish_found:
            self.missing_frames = 0
            self.ui_gone_streak = 0

            # 1D Vector Projection ตามแนวแกนจริงของ track (รองรับ UI เอียง)
            # ux, uy = vector ชี้จากบนลงล่างตามแนวความยาวของ track
            ux, uy = self.track_axis
            dx = fish_center[0] - bar_center[0]
            dy = fish_center[1] - bar_center[1]
            raw_axis_disp = dx * ux + dy * uy
            # เมื่อปลาอยู่สูงกว่าเบ็ด (dy < 0) -> raw_axis_disp < 0 -> error_pct > 0 (ต้องการแรงดึงขึ้น)
            error_pct = -(raw_axis_disp / self.track_length) * 100.0

            # PID + PWM Controller Update
            telemetry = self.pid.update(error_pct, self.last_progress_fraction)

            # แสดง telemetry การ Calibrate ใน Terminal
            now = time.perf_counter()
            log_interval = getattr(c, 'CALIBRATE_LOG_INTERVAL', 0.08)
            if c.CALIBRATE_MODE and (now - self.last_telemetry_log_time >= log_interval):
                self.last_telemetry_log_time = now
                log.pid_telemetry(self.state, telemetry)
        else:
            self.missing_frames += 1
            self.pid.stop()  # ปล่อยเมาส์ชั่วคราวระหว่างหลุดโฟกัส
            lost_bar = self.bar_tracker.lost_streak
            lost_fish = self.fish_tracker.lost_streak

            if max(lost_bar, lost_fish) >= c.TRACK_LOST_FRAMES:
                self._log(f'Tracker lost (bar_lost={lost_bar} fish_lost={lost_fish}) → reacquiring via model')
                result = self._reacquire_via_model(sct)
                if result is not None:
                    full_frame, bar_det, fish_det, bg_det = result
                    if bar_det and fish_det and bg_det:
                        self._setup_tracking_from_boxes(full_frame, bar_det, fish_det, bg_det)
                        self.ui_gone_streak = 0
                    else:
                        self.ui_gone_streak += 1
                        if self.ui_gone_streak >= c.UI_GONE_CONFIRM_FRAMES:
                            self._log('Fishing UI confirmed gone → RESULT')
                            self.state = 'RESULT'
                            return

        if c.LOOP_SLEEP_TIME > 0:
            time.sleep(c.LOOP_SLEEP_TIME)

    def _note_ui_maybe_gone(self, sct):
        self.ui_gone_streak += 1
        if self.ui_gone_streak >= c.UI_GONE_CONFIRM_FRAMES:
            self._log('Capture region invalid repeatedly → assuming round ended → RESULT')
            self.state = 'RESULT'

    def _handle_result(self):
        frac = self.last_progress_fraction
        self.pid.stop()
        controller.mouse_up()
        self.current_action = 'up'

        # เมื่อจบมินิเกม ให้รอแอนิเมชันปลา -> คลิกเก็บปลา -> รีเซ็ตเบ็ดเสมอ (กัน False Negative จากการที่หลอดหายก่อนอ่านเฟรมสุดท้าย)
        self._log(f'Round ended (last progress={frac:.2f}) -> waiting {c.RESULT_WAIT}s for fish animation', event='caught')
        time.sleep(c.RESULT_WAIT)

        # 1. คลิกซ้ายเก็บปลา (ส่งสัญญาณ 2 ครั้งเพื่อให้เกมรับ interaction แน่นอน)
        self._log('Left-click: collecting fish...', event='caught')
        controller.click(hold_duration=0.12)
        time.sleep(0.20)
        controller.click(hold_duration=0.12)
        time.sleep(c.COLLECT_CLICK_WAIT)

        # 2. คลิกขวาปล่อยเบ็ด
        self._log('Right-click: releasing rod...')
        controller.right_click(hold_duration=0.12)
        time.sleep(c.RECOVERY_RIGHTCLICK_WAIT)

        # 3. กด T รีเซ็ตเบ็ดใหม่ (Hardware Scan Code)
        self._log(f'Key {c.RECOVERY_KEY.upper()}: summoning fresh rod...')
        controller.press_key(c.RECOVERY_KEY, hold_duration=0.15)
        time.sleep(c.RECOVERY_KEY_WAIT)

        # 4. คลิกซ้ายหยิบเบ็ด
        self._log('Left-click: picking up rod...')
        controller.click(hold_duration=0.12)
        time.sleep(c.RECOVERY_CLICK_WAIT)

        # 5. รอก่อนเริ่มรอบใหม่
        time.sleep(c.RECOVERY_FINAL_WAIT)
        self.state = 'CASTING'
