import csv
import io
import json
import math
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, model_validator
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from sqlalchemy import select, text
from .database import Base, engine, Session, Report, MEDIA, ROOT, now, serialize
from .detector import detector, MODEL_PATH

Image.MAX_IMAGE_PIXELS = 24_000_000
MAX_UPLOAD = 15 * 1024 * 1024

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if engine.dialect.name == 'postgresql':
        with engine.begin() as db:
            db.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
            db.execute(text("""CREATE OR REPLACE VIEW reports_geo AS
                SELECT *, ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography AS location
                FROM reports WHERE latitude IS NOT NULL AND longitude IS NOT NULL"""))
            db.execute(text("""CREATE INDEX IF NOT EXISTS reports_location_gist ON reports
                USING GIST ((ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography))
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL"""))
    yield

app = FastAPI(title='Roadwatch API', version='1.0.0', lifespan=lifespan)
app.mount('/media', StaticFiles(directory=MEDIA), name='media')

@app.get('/api/health')
def health():
    return {'status': 'ok', 'model_available': MODEL_PATH.is_file(), 'model_loaded': detector.model is not None,
            'model': MODEL_PATH.name, 'device': __import__('os').getenv('YOLO_DEVICE', 'cpu')}


def decode_image(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(raw))
            if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise ValueError('Use a JPEG, PNG, or WebP image.')
            image.load()
            return ImageOps.exif_transpose(image).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, 'Invalid or oversized image. Use JPEG, PNG, or WebP up to 24 megapixels.')


def distance_m(a, b, c, d):
    p, q = math.radians(a), math.radians(c)
    h = math.sin((q-p)/2)**2 + math.cos(p)*math.cos(q)*math.sin(math.radians(d-b)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def process(image, confidence, latitude, longitude, accuracy, source, filename, session_id, persist):
    try:
        detections, elapsed = detector.predict(image, confidence)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))
    except Exception:
        import logging
        logging.exception('Inference failed')
        raise HTTPException(503, 'Model inference failed. Check the server log and installed model compatibility.')
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    colors = {'high': '#ef654d', 'medium': '#e8a530', 'low': '#16ad93'}
    for d in detections:
        box = d['box']
        draw.rectangle(box, outline=colors[d['severity']], width=max(3, image.width//250))
        draw.text((box[0]+5, max(0, box[1]-16)), f"Pothole {d['confidence']:.0%} | {d['severity']}", fill=colors[d['severity']])
    buf = io.BytesIO()
    annotated.save(buf, format='JPEG', quality=85)
    import base64
    result = {'detections': detections, 'inference_ms': elapsed, 'width': image.width, 'height': image.height,
              'preview': 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode(), 'report': None,
              'merged': False}
    if not detections or not persist:
        return result
    severity = max((d['severity'] for d in detections), key=['low', 'medium', 'high'].index)
    # Merge nearby observations only within this capture session and 30 seconds.
    # A ticket is an observation group, not a count of unique physical potholes.
    with Session.begin() as db:
        previous = None
        if session_id and latitude is not None:
            cutoff = (datetime.now(timezone.utc)-timedelta(seconds=30)).isoformat()
            recent = db.scalars(select(Report).where(Report.session_id == session_id, Report.updated_at >= cutoff, Report.status != 'resolved').order_by(Report.updated_at.desc())).all()
            previous = next((r for r in recent if r.latitude is not None and distance_m(latitude, longitude, r.latitude, r.longitude) < 15), None)
        if previous:
            previous.observations += 1
            previous.updated_at = now()
            if ['low','medium','high'].index(severity) > ['low','medium','high'].index(previous.severity):
                previous.severity = severity
            if max(d['confidence'] for d in detections) > previous.confidence:
                previous.confidence = max(d['confidence'] for d in detections)
                previous.detections = json.dumps(detections)
                previous.count = len(detections)
                (MEDIA / previous.image).write_bytes(buf.getvalue())
            result['report'] = serialize(previous)
            result['merged'] = True
        else:
            ident = str(uuid.uuid4())
            image_name = f'{ident}.jpg'
            (MEDIA / image_name).write_bytes(buf.getvalue())
            r = Report(id=ident, created_at=now(), updated_at=now(), source=source, filename=filename[:255],
                       latitude=latitude, longitude=longitude, gps_accuracy=accuracy, severity=severity,
                       status='open', confidence=max(d['confidence'] for d in detections), count=len(detections),
                       detections=json.dumps(detections), image=image_name, notes='', session_id=session_id, observations=1)
            db.add(r)
            result['report'] = serialize(r)
    return result

@app.post('/api/detect')
async def detect(file: UploadFile = File(...), confidence: float = Form(.35, ge=.05, le=.95),
                 latitude: float | None = Form(None, ge=-90, le=90), longitude: float | None = Form(None, ge=-180, le=180),
                 gps_accuracy: float | None = Form(None, ge=0), source: Literal['image','video','camera'] = Form('image'),
                 session_id: str | None = Form(None, max_length=64), persist: bool = Form(True)):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, 'Provide both latitude and longitude, or neither.')
    if any(v is not None and not math.isfinite(v) for v in (latitude, longitude, gps_accuracy, confidence)):
        raise HTTPException(422, 'Coordinates, accuracy, and confidence must be finite numbers.')
    raw = await file.read(MAX_UPLOAD+1)
    await file.close()
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, 'Image exceeds the 15 MB limit.')
    image = await run_in_threadpool(decode_image, raw)
    # Bound inference and response memory while preserving original aspect ratio.
    image.thumbnail((1920, 1920))
    return await run_in_threadpool(process, image, confidence, latitude, longitude, gps_accuracy, source,
                                   file.filename or 'capture.jpg', session_id, persist)

@app.get('/api/reports')
def reports():
    with Session() as db:
        return [serialize(r) for r in db.scalars(select(Report).order_by(Report.created_at.desc()).limit(2000))]

class Update(BaseModel):
    status: Literal['open','scheduled','resolved'] | None = None
    notes: str | None = Field(None, max_length=2000)
    latitude: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(None, ge=-180, le=180, allow_inf_nan=False)
    gps_accuracy: float | None = Field(None, ge=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def validate_update(self):
        fields = self.model_fields_set
        for field in ('status', 'notes'):
            if field in fields and getattr(self, field) is None:
                raise ValueError(f'{field} cannot be null.')
        if fields & {'latitude', 'longitude', 'gps_accuracy'}:
            if not {'latitude', 'longitude'} <= fields:
                raise ValueError('Provide both latitude and longitude to update the location.')
            if (self.latitude is None) != (self.longitude is None):
                raise ValueError('Provide both coordinates, or set both to null to clear the location.')
            if self.latitude is None and self.gps_accuracy is not None:
                raise ValueError('Location accuracy requires coordinates.')
        return self

@app.patch('/api/reports/{report_id}')
def update(report_id: str, body: Update):
    with Session.begin() as db:
        r = db.get(Report, report_id)
        if not r:
            raise HTTPException(404, 'Report not found.')
        if 'status' in body.model_fields_set:
            r.status = body.status
        if 'notes' in body.model_fields_set:
            r.notes = body.notes
        if 'latitude' in body.model_fields_set:
            r.latitude, r.longitude = body.latitude, body.longitude
            # A manually changed position must not inherit old device accuracy.
            r.gps_accuracy = body.gps_accuracy
        r.updated_at = now()
        return serialize(r)

@app.get('/api/export/{format}')
def export(format: Literal['csv','geojson']):
    rows = reports()
    if format == 'geojson':
        features = [{'type':'Feature', 'geometry':{'type':'Point','coordinates':[r['longitude'],r['latitude']]},
                     'properties':{k:v for k,v in r.items() if k not in ('detections','image_url')}} for r in rows if r['latitude'] is not None]
        return Response(json.dumps({'type':'FeatureCollection','features':features}), media_type='application/geo+json',
                        headers={'Content-Disposition':'attachment; filename="roadwatch.geojson"'})
    out = io.StringIO()
    fields = ['id','created_at','severity','status','confidence','count','latitude','longitude','gps_accuracy','source','filename','notes','observations']
    writer = csv.DictWriter(out, fields, extrasaction='ignore')
    writer.writeheader()
    for r in rows:
        # Prevent spreadsheet formula execution from uploaded filenames/notes.
        writer.writerow({k: ("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in r.items()})
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition':'attachment; filename="roadwatch.csv"'})

DIST = ROOT / 'frontend' / 'dist'
if DIST.exists():
    app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='assets')

@app.get('/')
def index():
    if (DIST / 'index.html').exists():
        return FileResponse(DIST / 'index.html')
    return {'message': 'Run npm run build in frontend, then restart the server.', 'api_docs': '/docs'}
