from pathlib import Path
import hashlib,json,time,uuid,pytest
from fastapi.testclient import TestClient
from mary_workbench.jobs import Workbench
from mary_workbench.server import create_app
from mary_workbench.common import BoundaryError

@pytest.fixture
def bench(tmp_path):
    w=Workbench(tmp_path/'owned')
    yield w
    w.close()

def test_real_calculation_artifacts_and_idempotence(bench):
    request={'request_id':'work-calculation-001','message':'0.1 + 0.2','action':'calculate'}
    result=bench.submit(request,wait=True);assert result['status']=='completed',result
    assert '3/10' in result['result']['text'];assert len(result['artifacts'])==2
    records=(bench.root/'work/work-calculation-001/outcomes.jsonl').read_bytes()
    assert bench.submit(request,wait=True)==result
    assert (bench.root/'work/work-calculation-001/outcomes.jsonl').read_bytes()==records
    with pytest.raises(BoundaryError):bench.submit({**request,'message':'2+2'},wait=True)
    path=bench.artifact(result['id'],result['artifacts'][0]['name']);assert path.is_file()
    path.write_bytes(b'changed')
    with pytest.raises(BoundaryError):bench.artifact(result['id'],result['artifacts'][0]['name'])

def test_real_table_artifact(bench,tmp_path):
    p=tmp_path/'costs.csv';p.write_text('Team,Cost\nA,12.5\nA,2.5\nB,3\n');source=bench.sources.admit(p)
    result=bench.submit({'request_id':'table-source-bound-001','message':'Total Cost by Team','action':'table','source_ids':[source['source_id']],'options':{'operation':'group_sum','column':'Cost','group_by':'Team'}},wait=True)
    assert result['status']=='completed',result
    assert any(x['name'].endswith('.csv') for x in result['artifacts'])
    data=bench.artifact(result['id'],'01-table.csv').read_text();assert 'A,15.0' in data;assert 'B,3' in data

def test_model_absent_does_not_fabricate_result(bench,tmp_path):
    p=tmp_path/'note.txt';p.write_text('The Alder owner is Morgan.');s=bench.sources.admit(p)
    result=bench.submit({'request_id':'no-model-honest-001','message':'Who owns Alder?','action':'answer','source_ids':[s['source_id']]},wait=True)
    assert result['status']=='needs_context';assert not result['artifacts'];assert 'model' in result['error'].lower()

def test_http_boundaries_and_upload(tmp_path):
    app=create_app(tmp_path/'owned');token=(tmp_path/'owned/keys/web.token').read_text();headers={'Authorization':'Bearer '+token};body=b'The harbor owner is Morgan.\n';identity='upload-real-bytes-001'
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        assert c.get('/api/status').status_code==401
        assert c.post('/api/work',headers={**headers,'Origin':'https://other.invalid'},json={'request_id':'cross-origin-001','message':'2+2','action':'calculate'}).status_code==403
        assert c.get('/api/status',headers={**headers,'Host':'attacker.invalid'}).status_code==403
        upload=c.post('/api/upload',headers={**headers,'X-Mary-Filename':'harbor.txt','X-Mary-Request-ID':identity,'X-Mary-SHA256':hashlib.sha256(body).hexdigest(),'Content-Type':'application/octet-stream'},content=body)
        assert upload.status_code==200,upload.text
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            job=c.get('/api/work/'+identity,headers=headers).json()
            if job['status'] not in {'queued','running'}:break
            time.sleep(.1)
        assert job['status']=='completed',job
        repeated=c.post('/api/upload',headers={**headers,'X-Mary-Filename':'harbor.txt','X-Mary-Request-ID':identity,'X-Mary-SHA256':hashlib.sha256(body).hexdigest(),'Content-Type':'application/octet-stream'},content=body)
        assert repeated.status_code==200
        sources=c.get('/api/sources',headers=headers).json()['items'];assert len(sources)==1
        downloaded=c.get('/api/source/'+sources[0]['id']+'/original',headers=headers)
        assert downloaded.content==body
        assert not (tmp_path/'owned/uploads'/identity).exists()
        bad=c.post('/api/model',headers=headers,json={'base_url':'https://example.com/v1','model':'x','api_key':''})
        assert bad.status_code==409
        assert c.get('/app.js').status_code==200

def test_resume_does_not_repeat_accepted_step(bench,tmp_path,monkeypatch):
    result=bench.submit({'request_id':'resume-checkpoint-001','message':'12+3','action':'calculate'},wait=True)
    directory=bench.root/'work'/result['id'];state=json.loads((directory/'state.json').read_text());state['status']='interrupted';(directory/'state.json').write_text(json.dumps(state))
    def forbidden(*args,**kwargs):raise AssertionError('accepted step was repeated')
    monkeypatch.setattr(bench,'_step',forbidden)
    resumed=bench.resume(result['id'],wait=True);assert resumed['status']=='completed';assert '15' in resumed['result']['text']
