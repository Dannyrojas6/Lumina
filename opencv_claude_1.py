from pathlib import Path

import cv2
import numpy as np


class FGORecognizer:
    # 提前定义好各UI区域，避免全图搜索
    ROI = {
        "command_cards": (0, 620, 1280, 720),  # x1,y1,x2,y2（示例分辨率1280x720）
        "attack_button": (1050, 630, 1280, 720),
        "skill_bar": (0, 530, 1280, 620),
        "np_gauge": (100, 500, 1180, 540),
    }

    def __init__(self, template_dir: str):
        self.templates = {}
        self._load_templates(template_dir)

    def _load_templates(self, template_dir: str):
        """启动时一次性加载所有模板到内存，避免运行时IO"""
        for path in Path(template_dir).glob("*.png"):
            img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            name = path.stem
            self.templates[name] = img
        print(f"已加载 {len(self.templates)} 个模板")

    def _get_roi(self, screenshot_gray, roi_key):
        """裁剪感兴趣区域，大幅减少matchTemplate的计算范围"""
        if roi_key not in self.ROI:
            return screenshot_gray, (0, 0)
        x1, y1, x2, y2 = self.ROI[roi_key]
        return screenshot_gray[y1:y2, x1:x2], (x1, y1)

    def find(self, screenshot, template_name, roi_key=None, threshold=0.85):
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        tmpl = self.templates.get(template_name)
        if tmpl is None:
            raise KeyError(f"模板不存在: {template_name}")

        search_area, (ox, oy) = self._get_roi(gray, roi_key)

        result = cv2.matchTemplate(search_area, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = tmpl.shape
            # 坐标还原到原图
            center = (max_loc[0] + ox + w // 2, max_loc[1] + oy + h // 2)
            return True, center, round(max_val, 3)
        return False, None, round(max_val, 3)


# ---- 使用示例 ----
recognizer = FGORecognizer("./templates")
screenshot = cv2.imread("fgo_screen.png")

found, pos, conf = recognizer.find(screenshot, "attack_btn", roi_key="attack_button")
if found:
    print(f"找到攻击按钮，位置: {pos}，置信度: {conf}")
