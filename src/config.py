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

# General Settings
WAIT_HOOK_TIME = 0.5
MAX_MISSING_FRAMES = 30
WAIT_COLLECT_TIME = 2.0
WAIT_BITE_TIMEOUT = 17.0

# PID Tuning (จูนเนอร์หลัก)
# ถ้าตามปลาไม่ทัน: เพิ่ม KP
# ถ้าสวิงหรือหลอดพุ่งทะลุ: เพิ่ม KD (แต่ระวัง เพิ่มมากไปจะยิ่งขยาย noise)
KP = 0.8
KD = 0.5

# --- เพิ่มใหม่ สำหรับแก้ปัญหาสวิง/แกว่ง ---
# EMA_ALPHA: น้ำหนักของค่าเฟรมล่าสุดใน smoothing filter (0.0-1.0)
#   ค่ายิ่งน้อย -> ยิ่ง smooth มาก แต่ตอบสนองช้าลง (lag เยอะขึ้น)
#   ค่ายิ่งมาก -> ตอบสนองไว แต่ noise ยังหลุดผ่านเยอะ
#   เริ่มลองที่ 0.3-0.5
EMA_ALPHA = 0.4

# HYSTERESIS: ระยะกันชน (dead band) รอบๆ threshold เดิมแต่ละจุด (-15, -2)
#   ป้องกันไม่ให้ output แกว่งใกล้ threshold แล้วสลับ action รัวๆ (chattering)
#   ยิ่งมาก ยิ่งกันสวิงได้ดี แต่การตอบสนองจะหน่วงขึ้นเล็กน้อย
#   เริ่มลองที่ 3.0-7.0
HYSTERESIS = 5.0

# อัตราการรัวคลิกประคอง
LOOP_SLEEP_TIME = 0.02