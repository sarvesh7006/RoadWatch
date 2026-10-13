"""Train / evaluate a YOLOv8 pothole detector on your own YOLO-format dataset."""
import argparse
from pathlib import Path
from ultralytics import YOLO

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',required=True,help='Dataset YAML path')
    p.add_argument('--model',default='yolov8s.pt',help='Base checkpoint; use yolov8s-seg.pt for segmentation labels')
    p.add_argument('--epochs',type=int,default=100)
    p.add_argument('--batch',type=int,default=16)
    p.add_argument('--device',default='cpu',help='cpu, mps or 0 (CUDA)')
    p.add_argument('--evaluate',action='store_true',help='Evaluate --model on test split without training')
    args=p.parse_args()
    if not Path(args.data).is_file():
        p.error('Dataset YAML does not exist.')
    model=YOLO(args.model)
    if args.evaluate:
        result=model.val(data=args.data,split='test',imgsz=640,device=args.device)
    else:
        result=model.train(data=args.data,epochs=args.epochs,batch=args.batch,imgsz=640,device=args.device,
                           seed=42,project='runs/pothole',name='train',fliplr=.5,hsv_v=.4,degrees=5)
    print(result.results_dict)
