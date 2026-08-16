import cv2
import numpy as np

from game_capture import get_game_screen
import config as c


def preprocess(img, target_size=c.IMG_SIZE):
    h, w = img.shape[:2]

    # หา scale
    scale = min(target_size / h, target_size / w)

    # คำนวณขนาดดภาพใหม้
    new_h = int(scale * h)
    new_w = int(scale * w)

    # resize รูปภาพ
    resize_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # สร้างภาพสีดำขนาดเท่ารูปที่ต้องการ
    pad_img = np.zeros((target_size, target_size, 3), dtype=np.uint8)

    # หาจุดที่จะเอาสีดำไปแปะ
    pad_h = (target_size - new_h) // 2
    pad_w = (target_size - new_w) // 2

    # ทาสีดำ
    pad_img[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = resize_img

    # เตรียม tensor image
    rgb_img = cv2.cvtColor(pad_img, cv2.COLOR_BGR2RGB)  # (H, W, C)
    tensor_img = rgb_img.astype(np.float32) / 255.0     # normalize
    tensor_img = tensor_img.transpose(2, 0, 1)          # (C, H, W)
    tensor_img = np.expand_dims(tensor_img, axis=0)     # (1, C, H, W)

    return tensor_img, scale, pad_h, pad_w


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def postprocess(outputs, scale, pad_w, pad_h, target_size=c.IMG_SIZE, conf_threshold=c.CONF_THRESH):
    # 1. แยกข้อมูลกล่องและค่า Logits
    boxes = outputs[0][0]   # Shape: (300, 4) -> [cx, cy, w, h] แบบ 0.0-1.0
    logits = outputs[1][0]  # Shape: (300, 4) -> ค่าดิบติดลบ

    # 2. แปลง Logits เป็น Confidence Score (0.0 - 1.0) แบบ vectorized ทั้งก้อน
    scores = sigmoid(logits)                    # (300, 4)
    class_ids = np.argmax(scores, axis=1)       # (300,)
    max_scores = scores[np.arange(len(scores)), class_ids]  # (300,)

    # 3. threshold ต่างกันตามคลาส (fish ใช้ threshold ต่ำกว่า) แบบ vectorized
    # ดู class index ของ "fish" จาก config แทนการ hardcode เลข เผื่อ CLASS_MAP เปลี่ยน
    fish_class_id = next(
        (idx for idx, name in c.CLASS_MAP.items() if name == "fish"), 2
    )
    per_box_thresh = np.where(
        class_ids == fish_class_id, c.FISH_CONF_THRESH, conf_threshold
    )

    # 4. กรองเฉพาะวัตถุที่มั่นใจเกินกำหนด — คำนวณ mask เดียวจบ ไม่ loop
    keep_mask = max_scores >= per_box_thresh

    kept_boxes = boxes[keep_mask]
    kept_class_ids = class_ids[keep_mask]
    kept_scores = max_scores[keep_mask]

    if len(kept_boxes) == 0:
        return []

    # 5. แปลง Normalized -> Pixel บนภาพ target_size x target_size ทั้งก้อน
    cx_pixel = kept_boxes[:, 0] * target_size
    cy_pixel = kept_boxes[:, 1] * target_size
    w_pixel = kept_boxes[:, 2] * target_size
    h_pixel = kept_boxes[:, 3] * target_size

    x1 = cx_pixel - (w_pixel / 2)
    y1 = cy_pixel - (h_pixel / 2)
    x2 = cx_pixel + (w_pixel / 2)
    y2 = cy_pixel + (h_pixel / 2)

    # 6. แมพพิกัดกลับไปหาหน้าจอเกมจริงๆ (ลบขอบดำทิ้ง แล้วหารด้วย Scale)
    orig_x1 = ((x1 - pad_w) / scale).astype(int)
    orig_y1 = ((y1 - pad_h) / scale).astype(int)
    orig_x2 = ((x2 - pad_w) / scale).astype(int)
    orig_y2 = ((y2 - pad_h) / scale).astype(int)
    orig_cx = ((cx_pixel - pad_w) / scale).astype(int)
    orig_cy = ((cy_pixel - pad_h) / scale).astype(int)

    # 7. ประกอบผลลัพธ์ — loop รอบนี้วนแค่จำนวนที่ผ่าน threshold แล้ว (ปกติน้อยมาก)
    valid_detections = []
    for i in range(len(kept_boxes)):
        class_id = int(kept_class_ids[i])
        valid_detections.append({
            "class_name": c.CLASS_MAP.get(class_id, "unknown"),
            "class_id": class_id,
            "score": float(kept_scores[i]),
            "box": (int(orig_x1[i]), int(orig_y1[i]), int(orig_x2[i]), int(orig_y2[i])),
            "center": (int(orig_cx[i]), int(orig_cy[i]))
        })

    return valid_detections


def detection(session, img):
    # preprocess
    input_img, scale, pad_h, pad_w = preprocess(img)

    # run inference
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_img})

    # postprocess
    results = postprocess(outputs, scale, pad_w, pad_h, conf_threshold=c.CONF_THRESH)

    return results