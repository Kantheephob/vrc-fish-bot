"""
tracker.py — เบา ๆ แทนโมเดล ระหว่างช่วง FISHING

แนวคิด: bg_track อยู่นิ่งตลอดรอบ (มีแค่สั่นเล็กน้อย) และ bar/fish เคลื่อนอยู่
"ภายใน" กรอบนั้นเท่านั้น เมื่อรู้ตำแหน่งเริ่มต้นจากโมเดลแล้ว (ครั้งเดียวตอน
ACQUIRE) ไม่จำเป็นต้องยิงโมเดลซ้ำทุกเฟรม — ใช้ color-mask + contour centroid
(ถูกกว่า NN inference มาก) หาตำแหน่งต่อเนื่องแทนได้ โดยจำกัดพื้นที่ค้นหาแคบ ๆ
รอบตำแหน่งล่าสุด (+ margin) เพื่อกันไปชนกับวัตถุอื่นที่สีใกล้เคียงกัน

ถ้า mask หาไม่เจอ (เช่น สีเปลี่ยนเพราะเอฟเฟกต์แสง/บั๊กตกปลา) จะ fallback ไป
template matching ด้วย grayscale patch ที่เก็บไว้ตอน init
"""

import cv2
import numpy as np


class ColorBlobTracker:
    """ติดตามวัตถุชิ้นเดียว (bar หรือ fish) ด้วยสี + template fallback"""

    def __init__(self, frame_bgr, box, tol_h=12, tol_s=70, tol_v=70, min_area=6):
        self.tol_h = tol_h
        self.tol_s = tol_s
        self.tol_v = tol_v
        self.min_area = min_area

        x1, y1, x2, y2 = box
        x1, y1 = max(0, x1), max(0, y1)
        x2 = min(frame_bgr.shape[1], x2)
        y2 = min(frame_bgr.shape[0], y2)

        self.w = max(1, x2 - x1)
        self.h = max(1, y2 - y1)
        self.min_area = max(min_area, int(self.w * self.h * 0.12))
        self.last_center = ((x1 + x2) // 2, (y1 + y2) // 2)

        patch = frame_bgr[y1:y2, x1:x2]
        if patch.size == 0:
            patch = frame_bgr[max(0, y1 - 1):y1 + 1, max(0, x1 - 1):x1 + 1]

        hsv_patch = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        ch, cw = hsv_patch.shape[:2]
        cy0, cy1 = int(ch * 0.25), max(int(ch * 0.75), int(ch * 0.25) + 1)
        cx0, cx1 = int(cw * 0.25), max(int(cw * 0.75), int(cw * 0.25) + 1)
        core = hsv_patch[cy0:cy1, cx0:cx1].reshape(-1, 3)
        self.target_hsv = np.median(core, axis=0) if core.size else np.array([0, 0, 0])

        self.template_gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if patch.size else None
        self.template_usable = (
            self.template_gray is not None
            and self.template_gray.size > 0
            and float(np.std(self.template_gray)) > 4.0
        )
        self.lost_streak = 0

    def _color_mask_center(self, roi_bgr):
        hsv = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV)
        lower = np.array([
            max(0, self.target_hsv[0] - self.tol_h),
            max(0, self.target_hsv[1] - self.tol_s),
            max(0, self.target_hsv[2] - self.tol_v),
        ])
        upper = np.array([
            min(179, self.target_hsv[0] + self.tol_h),
            min(255, self.target_hsv[1] + self.tol_s),
            min(255, self.target_hsv[2] + self.tol_v),
        ])
        mask = cv2.inRange(hsv, lower, upper)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        biggest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(biggest) < self.min_area:
            return None
        M = cv2.moments(biggest)
        if M['m00'] == 0:
            return None
        cx = int(M['m10'] / M['m00'])
        cy = int(M['m01'] / M['m00'])
        return (cx, cy)

    def _template_center(self, roi_bgr):
        if not self.template_usable:
            return None
        roi_gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        th, tw = self.template_gray.shape[:2]
        if roi_gray.shape[0] < th or roi_gray.shape[1] < tw:
            return None
        if float(np.std(roi_gray)) < 4.0:
            return None
        result = cv2.matchTemplate(roi_gray, self.template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val < 0.68:
            return None
        return (max_loc[0] + tw // 2, max_loc[1] + th // 2)

    def update(self, frame_bgr, search_box):
        """search_box: (x1,y1,x2,y2) พิกัดเทียบ frame_bgr ที่ส่งเข้ามา (crop ของ bg_track)
        คืน (found: bool, center: (x,y) พิกัดเทียบ frame_bgr เต็ม)"""
        sx1, sy1, sx2, sy2 = search_box
        sx1 = max(0, sx1)
        sy1 = max(0, sy1)
        sx2 = min(frame_bgr.shape[1], sx2)
        sy2 = min(frame_bgr.shape[0], sy2)
        roi = frame_bgr[sy1:sy2, sx1:sx2]

        if roi.size == 0:
            self.lost_streak += 1
            return False, self.last_center

        center = self._color_mask_center(roi)
        if center is None:
            center = self._template_center(roi)

        if center is None:
            self.lost_streak += 1
            return False, self.last_center

        abs_center = (center[0] + sx1, center[1] + sy1)
        self.last_center = abs_center
        self.lost_streak = 0
        return True, abs_center

    def search_box_for(self, margin):
        cx, cy = self.last_center
        return (
            cx - self.w // 2 - margin,
            cy - self.h // 2 - margin,
            cx + self.w // 2 + margin,
            cy + self.h // 2 + margin,
        )


def estimate_track_axis(frame_bgr, bg_box):
    """
    คำนวณเวกเตอร์แกนความยาวของ bg_track (unit vector ux, uy) และความยาว track_len
    เพื่อรองรับ UI ที่เอียง (tilted in screen space) โดยไม่ต้องเทรน segmentation model
    
    คืนค่า (ux, uy, track_len):
      - (ux, uy): unit vector ชี้จากบนลงล่างตามแนวความยาวของ track
      - track_len: ความยาวจริงของ track ตามแนวแกน (px)
    """
    x1, y1, x2, y2 = bg_box
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame_bgr.shape[1], x2), min(frame_bgr.shape[0], y2)
    patch = frame_bgr[y1:y2, x1:x2]

    h_box = max(1, y2 - y1)
    w_box = max(1, x2 - x1)
    fallback = (0.0, 1.0, float(h_box))

    if patch.size == 0 or h_box < 10 or w_box < 5:
        return fallback

    try:
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return fallback

        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) < (h_box * w_box * 0.15):
            return fallback

        rect = cv2.minAreaRect(largest)
        (cx, cy), (rw, rh), angle = rect

        # กำหนดให้ length คือด้านที่ยาวกว่า
        if rw < rh:
            rad = np.deg2rad(angle + 90.0)
            length = rh
        else:
            rad = np.deg2rad(angle)
            length = rw

        ux = float(np.cos(rad))
        uy = float(np.sin(rad))

        # บังคับให้ vector ชี้ลงล่าง (Y บวก)
        if uy < 0:
            ux = -ux
            uy = -uy

        if uy < 0.3:
            return fallback

        norm = np.hypot(ux, uy)
        if norm > 1e-6:
            ux /= norm
            uy /= norm
        else:
            return fallback

        return (ux, uy, float(max(length, h_box * 0.8)))
    except Exception:
        return fallback


def read_progress_fraction(frame_bgr, box, empty_bg_sample=None):
    """อ่านสัดส่วนพื้นที่ 'ติดสี' ใน progress bar region (0.0-1.0)"""
    x1, y1, x2, y2 = box
    x1, y1 = max(0, x1), max(0, y1)
    x2 = min(frame_bgr.shape[1], x2)
    y2 = min(frame_bgr.shape[0], y2)
    roi = frame_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    filled_mask = (sat > 60) & (val > 60)
    fraction = float(np.count_nonzero(filled_mask)) / float(filled_mask.size)
    return fraction
