from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.val(data="coco8.yaml")
