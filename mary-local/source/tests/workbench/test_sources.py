from pathlib import Path
from contextlib import closing
import json,sqlite3,pytest
from mary_workbench.sources import Sources
from mary_workbench.common import BoundaryError

@pytest.fixture
def library(tmp_path):return Sources(tmp_path/'owned')

def source(tmp_path,name='project.md',text='# Alder\nThe review owner is Morgan.\nThe budget is 1250 units.\n'):
    p=tmp_path/'inputs'/name;p.parent.mkdir(exist_ok=True);p.write_text(text,encoding='utf-8');return p

def test_real_forge_genesis_spectra_roundtrip(library,tmp_path):
    p=source(tmp_path);before=p.read_bytes();r=library.admit(p);assert r['status']=='admitted';assert p.read_bytes()==before
    hits=library.search('Who is the review owner?');assert hits and 'Morgan' in hits[0]['text'];assert hits[0]['shard_id'].startswith('sh1_')
    assert library.original(r['source_id']).read_bytes()==before

def test_import_cursor_advances_and_reuses(library,tmp_path):
    for n in range(3):source(tmp_path,f'{n}.txt',f'harbor record {n}')
    identity='bounded-import-001';library.begin_import(tmp_path/'inputs',identity)
    for _ in range(3):r=library.import_batch(identity,max_files=1)
    assert len(library.list())==3;assert r['processed']==3
    if r['status']!='complete':r=library.import_batch(identity,max_files=1)
    assert r['status']=='complete';assert r['admitted']==3

def test_current_history_and_withdrawal(library,tmp_path):
    p=source(tmp_path,text='harbor access enabled');a=library.admit(p);p.write_text('harbor access revoked');b=library.admit(p)
    assert len(library.search('harbor'))==1;assert 'revoked' in library.search('harbor')[0]['text'];assert len(library.search('harbor',history=True))==2
    library.withdraw(b['source_id']);assert library.search('harbor')==[];assert len(library.search('harbor',history=True))==2

def test_original_corruption_stops_evidence(library,tmp_path):
    r=library.admit(source(tmp_path));p=library.original(r['source_id']);p.write_bytes(b'tampered')
    with pytest.raises(BoundaryError):library.search('Morgan')

def test_cache_coordinates_cannot_override_signed_evidence(library,tmp_path):
    library.admit(source(tmp_path))
    with closing(library.db()) as c:c.execute('UPDATE chunks SET locator=?',('{"page":999}',));c.commit()
    with pytest.raises(BoundaryError):library.search('Morgan')
    library.rebuild();assert library.search('Morgan')

def test_transaction_failure_does_not_activate_source(library,tmp_path,monkeypatch):
    p=source(tmp_path);library.admit(p);old=library.list()[0]['current_shard'];p.write_text('Alder new budget is 9900 units.')
    from mary_workbench import axm
    real=axm.verified_document
    def fail_new(root,sid):
        if sid!=old:raise BoundaryError('injected failure before atomic activation')
        return real(root,sid)
    monkeypatch.setattr(axm,'verified_document',fail_new)
    with pytest.raises(BoundaryError):library.admit(p)
    assert library.list()[0]['current_shard']==old;assert '1250' in library.search('budget')[0]['text']

def test_known_content_reuses_even_at_capacity(library,tmp_path):
    p=source(tmp_path);r=library.admit(p);library.config['max_workspace_bytes']=1
    assert library.admit(p)['status']=='reused';assert len(library.list())==1

def test_root_and_home_are_not_intake(library,tmp_path):
    with pytest.raises(BoundaryError):library.begin_import(Path.home(),'home-blocked-0001')
    with pytest.raises(BoundaryError):library.begin_import(library.root,'state-blocked-0001')

def test_empty_and_nontext_are_visible_failures(library,tmp_path):
    p=source(tmp_path,text='')
    with pytest.raises(BoundaryError):library.admit(p)
    assert not library.list()

def test_request_identity_conflict(library,tmp_path):
    p=source(tmp_path);library.begin_import(p.parent,'identity-bound-0001');other=tmp_path/'other';other.mkdir()
    with pytest.raises(BoundaryError):library.begin_import(other,'identity-bound-0001')
