import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
import zipfile
from io import BytesIO
from unittest.mock import patch
from decision_floor.core import (make_db, load_rules, ingest_folder, reconcile, search, verify,
                                 parse_time, normalize_event, docx_chunks, xlsx_rows)
from decision_floor.report import render

HERE=Path(__file__).resolve().parents[1]
CONFIG=HERE/'config'/'sources.json'

class DecisionFloorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name)
        self.work=self.home/'state'
        self.db=make_db(self.work)
        self.addCleanup(self.db.close)
        self.rules=load_rules(CONFIG)

    def ingest(self,scenario='missed',date='2026-11-01T12:00:00Z'):
        stats=ingest_folder(self.db,HERE/'sample_inputs'/scenario,self.rules,self.work)
        return stats,reconcile(self.db,date)

    def test_missed_case_outcome_and_evidence(self):
        stats,rep=self.ingest()
        self.assertEqual(stats['new_sources'],12)
        self.assertEqual(stats['new_events'],15)
        self.assertFalse(rep['issues'])
        self.assertEqual(len(rep['cases']),1)
        case=rep['cases'][0]
        self.assertEqual(case['facts']['prior_plan'],12000)
        self.assertEqual(case['facts']['approved_target'],7000)
        self.assertEqual(case['tracks']['plan']['delta_units'],5000)
        self.assertEqual(case['tracks']['floor']['delta_units'],5000)
        self.assertEqual(case['facts']['inventory_above_target_book_value_usd'],210000)
        self.assertEqual(case['tracks']['commitment']['detection_hours'],4.25)
        self.assertEqual(case['tracks']['plan']['detection_hours'],47.0)
        self.assertEqual(case['facts']['forecast_revision_to_approval_hours'],2.0)
        self.assertGreaterEqual(len(case['questions']),6)
        self.assertIn('contradicted_by_observation',[q['status'] for q in case['questions']])
        self.assertEqual(len(case['related_documents']),2)
        self.assertEqual(verify(self.db,self.work)['status'],'PASS')

    def test_closed_case_converges_and_questions_close(self):
        _,rep=self.ingest('closed')
        case=rep['cases'][0]
        self.assertEqual(case['tracks']['plan']['state'],'matched')
        self.assertEqual(case['tracks']['commitment']['state'],'matched')
        self.assertEqual(case['tracks']['floor']['state'],'matched')
        self.assertEqual(case['facts']['inventory_above_target_book_value_usd'],0)
        self.assertEqual(len(case['questions']),0)
        self.assertEqual(case['tracks']['plan']['convergence_hours'],5.5)
        self.assertEqual(case['tracks']['commitment']['convergence_hours'],22.0)

    def test_idempotent_repeat_does_not_duplicate_sources_or_events(self):
        first,_=self.ingest()
        second,_=self.ingest()
        self.assertEqual(first['new_events'],15)
        self.assertEqual(second['new_events'],0)
        self.assertEqual(second['new_sources'],0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM events').fetchone()[0],15)

    def test_original_source_version_retained_after_new_export(self):
        incoming=self.home/'incoming';shutil.copytree(HERE/'sample_inputs'/'missed',incoming)
        ingest_folder(self.db,incoming,self.rules,self.work)
        original=self.db.execute('SELECT source_digest FROM events WHERE record_id="ERP-113"').fetchone()[0]
        file=incoming/'erp_production.csv'
        content=file.read_text()
        file.write_text(content.replace('12000,2026-10-07T08:30:00-07:00','7000,2026-10-07T08:30:00-07:00'))
        stats=ingest_folder(self.db,incoming,self.rules,self.work)
        self.assertEqual(stats['new_sources'],1)
        self.assertNotEqual(original,self.db.execute('SELECT source_digest FROM events WHERE record_id="ERP-113" ORDER BY rowid DESC').fetchone()[0])
        self.assertEqual(self.db.execute('SELECT count(*) FROM events WHERE record_id="ERP-113"').fetchone()[0],2)
        self.assertTrue((self.work/'vault'/'objects'/original).exists())

    def test_bitemporal_asof_excludes_late_recorded_erp(self):
        self.ingest()
        rep=reconcile(self.db,'2026-10-08T09:00:00-07:00')
        case=rep['cases'][0]
        self.assertEqual(case['tracks']['plan']['state'],'no_post_decision_observation')
        self.assertIn('UNOBSERVED_PLAN',[q['code'] for q in case['questions']])
        rep=reconcile(self.db,'2026-10-08T11:00:00-07:00')
        self.assertEqual(rep['cases'][0]['tracks']['plan']['state'],'observed_different')

    def test_before_decision_asof_has_no_hindsight(self):
        self.ingest()
        rep=reconcile(self.db,'2026-10-06T10:00:00-07:00')
        self.assertIsNone(rep['cases'][0]['facts']['approved_target'])
        self.assertIn('NO_APPROVED_DECISION',[q['code'] for q in rep['cases'][0]['questions']])

    def test_search_returns_precise_source_locator(self):
        self.ingest()
        found=search(self.db,'SOP-017')
        self.assertTrue(any(r['source']=='sop_decisions.csv' and 'csv:row:' in r['locator'] for r in found))
        self.assertTrue(all(len(r['sha256'])==64 for r in found))
        self.assertTrue(any(r['source']=='supply_note.eml' for r in found))

    def test_vault_tampering_is_visible(self):
        self.ingest()
        sh=self.db.execute('SELECT digest FROM sources LIMIT 1').fetchone()[0]
        (self.work/'vault'/'objects'/sh).write_bytes(b'tampered')
        result=verify(self.db,self.work)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue(any('hash_mismatch' in issue for issue in result['failures']))

    def test_reject_timestamps_without_timezone_or_inverted_clocks(self):
        with self.assertRaisesRegex(ValueError,'timezone'):parse_time('2026-10-06T10:00:00')
        with self.assertRaisesRegex(ValueError,'Invalid'):parse_time('not-a-time')
        self.assertEqual(parse_time('2026-10-06T10:00:00-07:00'),'2026-10-06T17:00:00+00:00')
        rule=self.rules[1]
        row={'Plant':'PLANT-07','Material':'VALVE-P204','Period':'2026-10','Approved_At':'2026-10-08T15:00:00Z','Entered_At':'2026-10-08T14:00:00Z','New_Target_Units':'7000','Approver':'Chair','Status':'approved'}
        with self.assertRaisesRegex(ValueError,'predates'):normalize_event(row,rule,'a'*64,'csv:row:2')

    def test_unapproved_presentation_is_not_accepted_decision(self):
        incoming=self.home/'incoming';shutil.copytree(HERE/'sample_inputs'/'missed',incoming)
        p=incoming/'sop_decisions.csv';p.write_text(p.read_text().replace(',approved,',',draft,'))
        ingest_folder(self.db,incoming,self.rules,self.work)
        case=reconcile(self.db,'2026-11-01T12:00:00Z')['cases'][0]
        self.assertIsNone(case['facts']['approved_target'])
        issues=[x['code'] for x in reconcile(self.db)['issues']]
        self.assertIn('EVENT_UNMAPPED',issues)

    def test_no_network_even_when_socket_creation_is_blocked(self):
        with patch.object(socket,'socket',side_effect=AssertionError('Network activity attempted')):
            self.ingest()
            self.assertEqual(verify(self.db,self.work)['status'],'PASS')
            self.assertTrue(search(self.db,'VALVE-P204'))

    def test_html_injection_stays_in_inert_json_data(self):
        _,rep=self.ingest()
        rep['cases'][0]['events'][0]['notes']='</script><img src="https://leak.example/">'
        out=self.home/'index.html';render(rep,out)
        content=out.read_text()
        self.assertNotIn('</script><img',content)
        self.assertIn('\\u003c/script\\u003e',content)
        self.assertIn("connect-src 'none'",content)

    def test_docx_and_xlsx_stdlib_parsers(self):
        docx=BytesIO()
        with zipfile.ZipFile(docx,'w') as z:
            z.writestr('word/document.xml','''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>SOP-017</w:t></w:r></w:p></w:body></w:document>''')
        self.assertIn('SOP-017',[x[1] for x in docx_chunks(docx.getvalue())])
        x=BytesIO()
        with zipfile.ZipFile(x,'w') as z:
            z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>''')
            z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
            z.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Part</t></is></c><c r="B1" t="inlineStr"><is><t>Quantity</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>VALVE-P204</t></is></c><c r="B2"><v>7000</v></c></row></sheetData></worksheet>''')
        result=list(xlsx_rows(x.getvalue()))
        self.assertEqual(result[0][0],'Sheet1')
        self.assertEqual(result[0][1][1][1]['B'],'7000')

    def test_duplicate_software_discussion_stays_candidate_not_receipt(self):
        _,rep=self.ingest()
        case=rep['cases'][0]
        self.assertTrue(all(d['relationship']=='candidate_text_mention_not_execution_proof' for d in case['related_documents']))
        self.assertNotEqual(case['facts']['approved_target'],case['tracks']['plan']['latest_quantity'])

if __name__=='__main__':unittest.main()

class DurableInvestigationTests(unittest.TestCase):
    def test_late_resolution_preserves_question_and_original_record(self):
        from decision_floor.core import sync_investigations
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);incoming=p/'input';shutil.copytree(HERE/'sample_inputs'/'missed',incoming)
            db=make_db(p/'work')
            try:
                rules=load_rules(CONFIG)
                ingest_folder(db,incoming,rules,p/'work')
                original=reconcile(db,'2026-11-01T12:00:00Z')
                history=sync_investigations(db,original)
                self.assertIn('DIVERGENT_PLAN',[i['code'] for i in history['items']])
                # This later ERP update cannot erase the original delayed update.
                (incoming/'erp_production_followup.csv').write_text(
                    'Schedule_Revision,Facility,Item,Period,Planned_Units,Effective_Time,Extract_Record_Time,Approved_By,Change_Memo\n'
                    'ERP-114,PLANT-07,VALVE-P204,2026-10,7000,2026-10-11T08:00:00-07:00,2026-10-11T08:10:00-07:00,MRP Engine,Revised late after factory produced full old quantity\n')
                ingest_folder(db,incoming,rules,p/'work')
                later=reconcile(db,'2026-11-01T12:00:00Z')
                self.assertEqual(later['cases'][0]['tracks']['plan']['state'],'matched')
                hist=sync_investigations(db,later)
                plan_item=next(i for i in hist['items'] if i['code']=='DIVERGENT_PLAN')
                self.assertEqual(plan_item['state'],'closed_in_current_projection')
                self.assertTrue(any(t['finding_id']==plan_item['id'] and t['next_state']=='closed_in_current_projection' for t in hist['transitions']))
                self.assertIn('PROMISE_LATE_MTG-023',[i['code'] for i in hist['items']])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM events WHERE record_id="ERP-113"').fetchone()[0],1)
            finally:db.close()

class CoverageAndConflicts(unittest.TestCase):
    def test_unsupported_file_is_reported_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'in';inp.mkdir()
            (inp/'production_powerpoint.pptx').write_bytes(b'not parsed by this version')
            db=make_db(root/'state')
            try:
                ingest_folder(db,inp,load_rules(CONFIG),root/'state')
                rep=reconcile(db,'2026-11-01T12:00:00Z')
                self.assertEqual(rep['skipped_files'][0]['reason'],'UNSUPPORTED_FORMAT')
                self.assertEqual(rep['skipped_files'][0]['path'],'production_powerpoint.pptx')
            finally:db.close()

    def test_conflicting_same_time_decisions_raise_source_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inp=root/'in';inp.mkdir()
            text='Decision_ID,Plant,Material,Period,New_Target_Units,Approved_At,Entered_At,Approver,Status,Reason\n'
            text+='D-1,PLANT-07,VALVE-P204,2026-10,7000,2026-10-06T11:00:00-07:00,2026-10-06T11:01:00-07:00,Chair,approved,A\n'
            text+='D-2,PLANT-07,VALVE-P204,2026-10,9000,2026-10-06T11:00:00-07:00,2026-10-06T11:02:00-07:00,Chair,approved,B\n'
            (inp/'sop_decisions.csv').write_text(text)
            db=make_db(root/'state')
            try:
                ingest_folder(db,inp,load_rules(CONFIG),root/'state')
                rep=reconcile(db,'2026-11-01T12:00:00Z')
                self.assertTrue(any(q['status']=='source_conflict' for q in rep['cases'][0]['questions']))
            finally:db.close()
