"""Analyze dashcam video with optional per-frame GPS telemetry via the running API."""
import argparse
import bisect
import csv
import uuid
import base64
import cv2
import httpx
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video')
    p.add_argument('--api',default='http://127.0.0.1:8011')
    p.add_argument('--gps',help='CSV: seconds,latitude,longitude,accuracy_m (seconds relative to video start)')
    p.add_argument('--every',type=float,default=1,help='Analyze one frame every N video seconds')
    p.add_argument('--max-gps-gap',type=float,default=2,help='Omit location when nearest GPS sample is older/newer than N seconds')
    p.add_argument('--output',help='Optional annotated MP4 of sampled frames')
    p.add_argument('--preview-only',action='store_true',help='Do not save repair tickets')
    args=p.parse_args()
    if args.every<=0 or args.max_gps_gap<0:p.error('Invalid sampling interval / GPS gap.')
    gps=[]
    if args.gps:
        with open(args.gps,newline='') as f:
            gps=sorted([{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)],key=lambda r:r['seconds'])
    stamps=[r['seconds'] for r in gps]
    cap=cv2.VideoCapture(args.video)
    if not cap.isOpened():p.error('Cannot open video.')
    fps=cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps<=0:cap.release();p.error('Video has no valid frame rate.')
    stride=max(1,round(fps*args.every));frame_index=0;session=str(uuid.uuid4());writer=None
    try:
        with httpx.Client(timeout=120) as client:
            while True:
                ok,frame=cap.read()
                if not ok:break
                frame_index+=1
                if (frame_index-1)%stride:continue
                timestamp=(frame_index-1)/fps
                data={'source':'video','session_id':session,'persist':str(not args.preview_only).lower()}
                if gps:
                    i=bisect.bisect_left(stamps,timestamp)
                    candidates=gps[max(0,i-1):i+1]
                    closest=min(candidates,key=lambda r:abs(r['seconds']-timestamp))
                    if abs(closest['seconds']-timestamp)<=args.max_gps_gap:
                        data.update(latitude=closest['latitude'],longitude=closest['longitude'])
                        if 'accuracy_m' in closest:data['gps_accuracy']=closest['accuracy_m']
                ok,encoded=cv2.imencode('.jpg',frame)
                if not ok:raise RuntimeError('Cannot encode frame.')
                response=client.post(args.api+'/api/detect',files={'file':(f'frame-{timestamp:.2f}s.jpg',encoded.tobytes(),'image/jpeg')},data=data)
                response.raise_for_status();result=response.json()
                print(f"{timestamp:8.2f}s | {len(result['detections'])} detections | {result['inference_ms']} ms | GPS {'yes' if 'latitude' in data else 'no'}",flush=True)
                if args.output:
                    annotated=cv2.imdecode(np.frombuffer(base64.b64decode(result['preview'].split(',')[1]),dtype=np.uint8),cv2.IMREAD_COLOR)
                    if writer is None:
                        h,w=annotated.shape[:2]
                        writer=cv2.VideoWriter(args.output,cv2.VideoWriter_fourcc(*'mp4v'),fps/stride,(w,h))
                        if not writer.isOpened():raise RuntimeError('Cannot create output video.')
                    writer.write(annotated)
    finally:
        cap.release()
        if writer:writer.release()

if __name__=='__main__':main()
