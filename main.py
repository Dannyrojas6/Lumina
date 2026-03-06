import subprocess
import time

import cv2
from adbutils import adb

SERVENT_SKILL = {
    1: (110, 880),
    2: (243, 880),
    3: (376, 880),
    4: (585, 880),
    5: (718, 880),
    6: (850, 880),
    7: (1060, 880),
    8: (1200, 880),
    9: (1324, 880),
}
SPEED_SKIP = (1849, 651)
IMAGE_PATH = r"test_image"


class DailyAction:
    def __init__(self, adb) -> None:
        self.adb = adb

    def skip_dialog(self):
        self.adb.save_screenshot()
        result = self.adb.cv_template(
            IMAGE_PATH + "/skip.png", IMAGE_PATH + "/screen.png"
        )
        if result is not None:
            x, y = result
            self.adb.common_click(x, y)
            time.sleep(0.2)
            result = self.adb.cv_template(
                IMAGE_PATH + "/yes.png", IMAGE_PATH + "/screen.png"
            )
            if result is not None:
                x, y = result
                self.adb.common_click(x, y)
                time.sleep(0.2)


class AdbController:
    def __init__(self) -> None:
        devices = adb.device_list()
        d = [d.serial for d in devices]
        index = 1
        for _ in d:
            print(f"{index}: {_}")
            index += 1
        index = int(input("请输入设备编号："))
        self.device_1 = adb.device(serial=d[index - 1])

    def common_click(self, x, y):
        self.device_1.click(x, y)

    def servent_skill(self, num):
        self.device_1.click(*SERVENT_SKILL[num])
        time.sleep(0.2)
        self.device_1.click(*SPEED_SKIP)
        print(f"{num}技能释放完毕")

    def save_screenshot(self):
        self.device_1.screenshot().save(IMAGE_PATH + "/screen.png")
        print("截取屏幕成功！")

    def test(self):
        pass

    def cv_template(self, template_path, screen_path):
        template = cv2.imread(template_path, 0)
        screen_gray = cv2.imread(screen_path, 0)
        result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > 0.7:
            h, w = template.shape
            # center_x = max_loc[0] + w // 2
            # center_y = max_loc[1] + h // 2
            return max_loc[0] + w // 2, max_loc[1] + h // 2
        else:
            print(f"识别度过低！识别度为{max_val}")
            return


def main():
    # subprocess.run(
    #     [r"C:\Users\kk\scoop\apps\adb\current\platform-tools\adb.exe", "kill-server"]
    # )
    subprocess.run(
        [r"C:\Users\kk\scoop\apps\adb\current\platform-tools\adb.exe", "start-server"],
        check=False,
    )
    adb_ctl = AdbController()
    daily_action = DailyAction(adb_ctl)
    while True:
        daily_action.skip_dialog()
    # while True:
    #     adb_ctl.save_screenshot()
    #     result = adb_ctl.cv_template(
    #         IMAGE_PATH + "/skip.png", IMAGE_PATH + "/screen.png"
    #     )
    #     if result is not None:
    #         x, y = result
    #         adb_ctl.common_click(x, y)
    #         time.sleep(0.2)
    #         result = adb_ctl.cv_template(
    #             IMAGE_PATH + "/yes.png", IMAGE_PATH + "/screen.png"
    #         )
    #         if result is not None:
    #             x, y = result
    #             adb_ctl.common_click(x, y)
    #             time.sleep(0.2)


if __name__ == "__main__":
    main()
