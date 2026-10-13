import io
import os
import tempfile
from unittest.mock import patch
import pytest
from PIL import Image
from fastapi.testclient import TestClient

os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='roadwatch-tests-')
from backend.app.main import app
from backend.app.database import Session, Report, engine, Base
from backend.app.detector import severity_for
from sqlalchemy import delete

@pytest.fixture
def client():
    with TestClient(app) as c:
        with Session.begin() as db:
            db.execute(delete(Report))
        yield c

@pytest.fixture
def image():
    f=io.BytesIO()
    Image.new('RGB',(200,200),'gray').save(f,'JPEG')
    return f.getvalue()

DETECTIONS=[{'box':[10,10,100,100],'confidence':.91,'severity':'high','area_ratio':.2025}]

def detect(client,image,**data):
    with patch('backend.app.main.detector.predict',return_value=(DETECTIONS,12.3)):
        return client.post('/api/detect',files={'file':('road.jpg',image,'image/jpeg')},data=data)

def test_detection_persistence_status_export(client,image):
    result=detect(client,image,latitude=0,longitude=0).json()
    assert result['detections'][0]['confidence']==.91
    ident=result['report']['id']
    assert client.get(result['report']['image_url']).status_code==200
    assert len(client.get('/api/reports').json())==1
    updated=client.patch(f'/api/reports/{ident}',json={'status':'resolved','notes':'Repair verified'})
    assert updated.json()['status']=='resolved'
    exported=client.get('/api/export/geojson').json()
    assert exported['features'][0]['geometry']['coordinates']==[0,0]
    assert 'Repair verified' in client.get('/api/export/csv').text

def test_no_detection_does_not_create_ticket(client,image):
    with patch('backend.app.main.detector.predict',return_value=([],5)):
        r=client.post('/api/detect',files={'file':('road.jpg',image,'image/jpeg')})
    assert r.status_code==200 and r.json()['report'] is None
    assert client.get('/api/reports').json()==[]

def test_preview_does_not_persist(client,image):
    assert detect(client,image,persist='false').json()['report'] is None
    assert client.get('/api/reports').json()==[]

def test_invalid_image(client):
    assert client.post('/api/detect',files={'file':('bad.jpg',b'not an image','image/jpeg')}).status_code==400

@pytest.mark.parametrize('data',[{'latitude':20},{'latitude':91,'longitude':12},{'confidence':1.1},{'latitude':'nan','longitude':1},{'source':'unknown'}])
def test_invalid_inputs(client,image,data):
    assert detect(client,image,**data).status_code==422

def test_missing_model(client,image):
    with patch('backend.app.main.detector.predict',side_effect=FileNotFoundError('Missing model')):
        r=client.post('/api/detect',files={'file':('road.jpg',image,'image/jpeg')})
    assert r.status_code==503

def test_session_merge_is_scoped_and_distant_reports_separate(client,image):
    first=detect(client,image,latitude=19,longitude=72,session_id='drive1').json()['report']
    next_=detect(client,image,latitude=19,longitude=72,session_id='drive1').json()
    assert next_['merged'] and next_['report']['id']==first['id']
    assert next_['report']['observations']==2
    detect(client,image,latitude=19,longitude=72,session_id='drive2')
    detect(client,image,latitude=20,longitude=72,session_id='drive1')
    assert len(client.get('/api/reports').json())==3

def test_reports_without_gps_are_not_in_geojson(client,image):
    detect(client,image)
    assert client.get('/api/export/geojson').json()['features']==[]

def test_status_validation_and_missing_report(client,image):
    ident=detect(client,image).json()['report']['id']
    assert client.patch(f'/api/reports/{ident}',json={'status':'invalid'}).status_code==422
    assert client.patch('/api/reports/no-such-id',json={'status':'open'}).status_code==404

def test_csv_formula_escape(client,image):
    ident=detect(client,image).json()['report']['id']
    client.patch(f'/api/reports/{ident}',json={'status':'open','notes':'=1+1'})
    assert "'=1+1" in client.get('/api/export/csv').text

def test_severity_boundaries():
    assert severity_for(.02499)=='low'
    assert severity_for(.025)=='medium'
    assert severity_for(.08)=='high'

def test_location_can_be_attached_after_detection_and_survives_reload(client,image):
    r=detect(client,image).json()['report']
    client.patch(f"/api/reports/{r['id']}",json={'status':'scheduled','notes':'Crew assigned'})
    response=client.patch(f"/api/reports/{r['id']}",json={'latitude':19.076,'longitude':72.8777,'gps_accuracy':8})
    assert response.status_code==200
    saved=client.get('/api/reports').json()[0]
    assert (saved['latitude'],saved['longitude'],saved['gps_accuracy'])==(19.076,72.8777,8)
    assert saved['status']=='scheduled' and saved['notes']=='Crew assigned'
    assert client.get('/api/export/geojson').json()['features'][0]['geometry']['coordinates']==[72.8777,19.076]
    # A subsequent notes/status-only save must preserve coordinates.
    client.patch(f"/api/reports/{r['id']}",json={'status':'resolved','notes':'Done'})
    assert client.get('/api/reports').json()[0]['latitude']==19.076


def test_correct_and_clear_saved_location(client,image):
    r=detect(client,image,latitude=19,longitude=72,gps_accuracy=10).json()['report']
    url=f"/api/reports/{r['id']}"
    moved=client.patch(url,json={'latitude':-12.5,'longitude':0}).json()
    assert moved['latitude']==-12.5 and moved['longitude']==0 and moved['gps_accuracy'] is None
    cleared=client.patch(url,json={'latitude':None,'longitude':None}).json()
    assert cleared['latitude'] is None and cleared['longitude'] is None and cleared['gps_accuracy'] is None
    assert client.get('/api/export/geojson').json()['features']==[]


@pytest.mark.parametrize('body',[
    {'latitude':19}, {'longitude':72}, {'gps_accuracy':5},
    {'latitude':None,'longitude':72}, {'latitude':91,'longitude':72},
    {'latitude':19,'longitude':181}, {'latitude':'nan','longitude':72},
    {'latitude':None,'longitude':None,'gps_accuracy':10},
    {'latitude':19,'longitude':72,'gps_accuracy':-1},
])
def test_invalid_location_edits_leave_saved_location_unchanged(client,image,body):
    r=detect(client,image,latitude=10,longitude=20).json()['report']
    assert client.patch(f"/api/reports/{r['id']}",json=body).status_code==422
    saved=client.get('/api/reports').json()[0]
    assert (saved['latitude'],saved['longitude'])==(10,20)
