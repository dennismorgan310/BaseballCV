from ultralytics import YOLO

# Load pretrained model
model = YOLO('glove_tracking_v4_YOLOv11.pt')

# Train (fine-tune) on your new dataset
model.train(data='glove_data.yaml', epochs=20, imgsz=640, batch=16)