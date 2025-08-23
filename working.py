from ultralytics import YOLO

# Load the YOLOv9 model from the checkpoint
model = YOLO('glove_tracking_v4_YOLOv11.pt')

# Now you can use model.train(), model.predict(), etc.
# Example: Run inference on an image
results = model.predict(r'C:\Users\do25.krjanos\Downloads\BaseballCV-main\BaseballCV-main\baseball_rubber_home_glove\baseball_rubber_home_glove\test\images\0000355.jpg')
for result in results:
    for box in result.boxes:
        print(f"Class ID: {int(box.cls)}")
        print(f"Class: {result.names[int(box.cls)]}")
        print(f"Confidence: {box.conf.item():.2f}")
        print(f"Coordinates (xyxy): {box.xyxy.tolist()}")
        print("---")

# Example for one box
img_width, img_height = 1280, 720  # replace with your actual image size
class_id, x_c, y_c, w, h = 0, 0.502344, 0.415972, 0.031250, 0.045833

x_center = x_c * img_width
y_center = y_c * img_height
box_width = w * img_width
box_height = h * img_height

x1 = x_center - box_width / 2
y1 = y_center - box_height / 2
x2 = x_center + box_width / 2
y2 = y_center + box_height / 2

print(f"Class: {class_id}, Box: ({x1}, {y1}, {x2}, {y2})")