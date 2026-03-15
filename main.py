# import subprocess
# import time
#
# import cv2
# from adbutils import adb
#
# SERVENT_SKILL = {
#     1: (110, 880),
#     2: (243, 880),
#     3: (376, 880),
#     4: (585, 880),
#     5: (718, 880),
#     6: (850, 880),
#     7: (1060, 880),
#     8: (1200, 880),
#     9: (1324, 880),
# }
# SERVENT_1 = {
#     "skill_1": (58, 812, 162, 921),
#     "skill_2": (191, 816, 292, 920),
#     "skill_3": (322, 810, 427, 922),
# }
# SERVENT_2 = {
#     "skill_1": (532, 811, 640, 922),
#     "skill_2": (665, 811, 773, 923),
#     "skill_3": (800, 810, 904, 923),
# }
# SERVENT_3 = {
#     "skill_1": (1011, 812, 1116, 923),
#     "skill_2": (1144, 812, 1249, 923),
#     "skill_3": (1277, 812, 1382, 923),
# }
#
# SKILL_SELECT_SERVENT = (849, 262, 1077, 314)
# ATTACK_BUTTON = (1600, 800, 1806, 1013)
#
# FIGHT_MENU = (1700, 220, 1882, 389)
# MASTER_SKILL = (1699, 379, 1885, 557)
#
# SPEED_SKIP = (1849, 651)
# IMAGE_PATH = r"test_image"
#
#
# class DailyAction:
#     def __init__(self, adb) -> None:
#         self.adb = adb
#
#     def skip_dialog(self):
#         self.adb.save_screenshot()
#         result = self.adb.cv_template(
#             IMAGE_PATH + "/skip.png", IMAGE_PATH + "/screen.png"
#         )
#         if result is not None:
#             x, y = result
#             self.adb.common_click(x, y)
#             time.sleep(0.2)
#             result = self.adb.cv_template(
#                 IMAGE_PATH + "/yes.png", IMAGE_PATH + "/screen.png"
#             )
#             if result is not None:
#                 x, y = result
#                 self.adb.common_click(x, y)
#                 time.sleep(0.2)
#
#     def adjust_speed(self):
#         pass
#
#     def normal_fight(self):
#         pass
#
#
# class AdbController:
#     def __init__(self) -> None:
#         devices = adb.device_list()
#         d = [d.serial for d in devices]
#         index = 1
#         for _ in d:
#             print(f"{index}: {_}")
#             index += 1
#         index = int(input("请输入设备编号："))
#         self.device_1 = adb.device(serial=d[index - 1])
#
#     def common_click(self, x, y):
#         self.device_1.click(x, y)
#
#     def servent_skill(self, num):
#         self.device_1.click(*SERVENT_SKILL[num])
#         time.sleep(0.2)
#         self.device_1.click(*SPEED_SKIP)
#         print(f"{num}技能释放完毕")
#
#     def save_screenshot(self):
#         self.device_1.screenshot().save(IMAGE_PATH + "/screen.png")
#         print("截取屏幕成功！")
#
#     def test(self):
#         pass
#
#     def cv_template(self, template_path, screen_path):
#         template = cv2.imread(template_path, 0)
#         screen_gray = cv2.imread(screen_path, 0)
#         result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
#         _, max_val, _, max_loc = cv2.minMaxLoc(result)
#         if max_val > 0.7:
#             h, w = template.shape
#             # center_x = max_loc[0] + w // 2
#             # center_y = max_loc[1] + h // 2
#             return max_loc[0] + w // 2, max_loc[1] + h // 2
#         else:
#             print(f"识别度过低！识别度为{max_val}")
#             return
#
#
# # class ImageRecognizer:
# #     TEMPLATE_PHOTO = {
# #         "fight_menu": (1700, 220, 1882, 389),
# #         "master_skill": (1699, 379, 1885, 557),
# #     }
#
# #     def __init__(self) -> None:
# #         pass
#
#
# def main():
#     subprocess.run(
#         [r"C:\Users\kk\scoop\apps\adb\current\platform-tools\adb.exe", "start-server"],
#         check=False,
#     )
#     adb_ctl = AdbController()
#     daily_action = DailyAction(adb_ctl)
#     while True:
#         daily_action.skip_dialog()
#
#
# if __name__ == "__main__":
#     main()


import logging

# ─────────────────────────────────────────────
# 日志配置
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")
