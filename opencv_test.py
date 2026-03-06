import cv2

# import numpy as np
# from PIL import Image

# img = Image.open("test_image/Attack.png")
# arr = np.array(img)

# bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
# gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

template = cv2.imread("test_image/Attack.png", 0)
screen_gray = cv2.imread("test_image/screen.png", 0)
# screen = cv2.imread("test_image/screen.png")
result = cv2.matchTemplate(screen_gray, template, cv2.TM_CCOEFF_NORMED)
_, max_val, _, max_loc = cv2.minMaxLoc(result)
h, w = template.shape
center_x = max_loc[0] + w // 2
center_y = max_loc[1] + h // 2
# cv2.rectangle(screen, max_loc, (max_loc[0] + w, max_loc[1] + h), (0, 255, 0), 2)
# cv2.imwrite("test_image/match_result.png", screen)
