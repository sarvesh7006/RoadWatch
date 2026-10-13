"""Opt-in real inference checks: RUN_MODEL_TESTS=1 python -m pytest tests/test_model_regression.py.

Local user-provided photos are not redistributed by this test. Approximate manually
reviewed boxes check localization, not just whether an arbitrary box was emitted.
"""
import os
from pathlib import Path
import pytest
from PIL import Image

pytestmark = pytest.mark.skipif(os.getenv('RUN_MODEL_TESTS') != '1', reason='Opt-in real model tests')
ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def detector():
    from backend.app.detector import Detector, MODEL_PATH
    if not MODEL_PATH.exists():
        pytest.fail('Download the checkpoint with scripts/download_model.py first.')
    return Detector()


def iou(a,b):
    intersect=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    union=(a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersect
    return intersect/union if union else 0

@pytest.mark.parametrize('filename,expected',[
    ('pothole.jpg',[170,195,350,350]),
    ('pothole img.jpg',[150,170,385,270]),
    ('potholeimg.webp',[215,350,730,630]),
])
def test_pothole_localization(detector,filename,expected):
    path=ROOT/'examples'/filename
    if not path.exists():pytest.skip('Local regression photo is not included in this checkout.')
    with Image.open(path) as source:
        predictions,_=detector.predict(source.convert('RGB'),.35)
    assert any(iou(d['box'],expected)>=.5 for d in predictions), predictions

@pytest.mark.parametrize('filename',['bus.jpg','zidane.jpg'])
def test_non_pothole_photos(detector,filename):
    import ultralytics
    path=Path(ultralytics.__file__).parent/'assets'/filename
    with Image.open(path) as source:
        predictions,_=detector.predict(source.convert('RGB'),.35)
    assert predictions==[]

@pytest.mark.parametrize('color',['black','gray','white'])
def test_empty_frames(detector,color):
    predictions,_=detector.predict(Image.new('RGB',(640,640),color),.35)
    assert predictions==[]
