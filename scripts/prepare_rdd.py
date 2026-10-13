"""Convert RDD VOC XML annotations into deterministic 70/20/10 YOLO splits.

Only D40 (potholes) is retained. Other road images become useful negative examples.
Split by route before using this utility if adjacent frames could leak across splits.
"""
import argparse
import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
import yaml

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,help='Extracted RDD2022 directory (nested country directories allowed)')
    p.add_argument('--output',required=True,help='New output directory; must not already exist')
    args=p.parse_args()
    source,output=Path(args.source).resolve(),Path(args.output).resolve()
    if output.exists():
        p.error('Output directory already exists; choose a new directory to avoid mixing splits.')
    images={}
    for image in source.rglob('*'):
        if image.suffix.lower() not in {'.jpg','.jpeg','.png'}:continue
        if image.stem in images:
            p.error(f'Ambiguous image basename {image.stem}; process each source separately or rename consistently.')
        images[image.stem]=image
    pairs=[(xml,images[xml.stem]) for xml in sorted(source.rglob('*.xml')) if xml.stem in images]
    if len(pairs)<10:
        p.error('Need at least 10 image/XML pairs to build train, validation, and test splits.')
    random.Random(42).shuffle(pairs)
    n=len(pairs)
    for i,(xml,image) in enumerate(pairs):
        split='train' if i<int(.7*n) else 'val' if i<int(.9*n) else 'test'
        imdir,lbdir=output/'images'/split,output/'labels'/split
        imdir.mkdir(parents=True,exist_ok=True);lbdir.mkdir(parents=True,exist_ok=True)
        root=ET.parse(xml).getroot()
        w,h=float(root.findtext('size/width')),float(root.findtext('size/height'))
        if w<=0 or h<=0:
            raise ValueError(f'Invalid image dimensions in {xml}')
        lines=[]
        for obj in root.findall('object'):
            if obj.findtext('name','').upper()!='D40':continue
            b=obj.find('bndbox')
            x1,y1,x2,y2=[float(b.findtext(k)) for k in ('xmin','ymin','xmax','ymax')]
            x1,x2=max(0,min(w,x1)),max(0,min(w,x2))
            y1,y2=max(0,min(h,y1)),max(0,min(h,y2))
            if x2>x1 and y2>y1:lines.append(f'0 {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}')
        # Prefix with ordinal to avoid overwriting same-name images across sources.
        name=f'{i:06d}_{image.stem}'
        shutil.copy2(image,imdir/(name+image.suffix.lower()))
        (lbdir/(name+'.txt')).write_text('\n'.join(lines))
    (output/'data.yaml').write_text(yaml.safe_dump({'path':str(output),'train':'images/train','val':'images/val','test':'images/test','names':{0:'pothole'}}))
    print(f'Converted {n} images. Dataset: {output / "data.yaml"}')

if __name__=='__main__':main()
