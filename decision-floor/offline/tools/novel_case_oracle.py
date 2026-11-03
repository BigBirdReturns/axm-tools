"""Independent randomized, reproducible new-material evaluation for Decision Floor.

Synthetic scenarios are never represented as real customer transactions. This
exercise tests code paths and invariants; it does not qualify enterprise feeds.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import random
from pathlib import Path
import shutil
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from decision_floor.core import make_db,ingest_folder,load_rules,reconcile,search,verify

HEADERS={}
for p in (ROOT/'sample_inputs'/'missed').glob('*.csv'):
    HEADERS[p.name]=next(csv.reader(io.StringIO(p.read_text(encoding='utf-8'))))
MODE=['converged','plan_miss','po_miss','floor_miss','all_miss','no_floor','deferred','late']


def generate(path:Path,cases=1000,seed=931527):
    if path.exists() and any(path.iterdir()):raise ValueError('Use an empty output directory for the generated source set')
    path.mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed)
    tables={name:[] for name in HEADERS}
    actual=[]
    shipment=[]
    oracle=[]
    def put(file,**kw):tables[file].append(kw)
    def time(d,h='08:30'):return f'2026-10-{d:02d}T{h}:00-07:00'
    for i in range(cases):
        sku=f'NEW-{seed % 10000:04d}-{i:05d}'
        site=f'PLANT-{rng.randint(1,3):02d}';period='2026-10'
        old=rng.randint(3000,28000);target=old-rng.randint(300,max(300,old//2))
        mode=MODE[i%len(MODE)]
        unit_cost=rng.randint(6,140)
        plan_qty=old if mode in ('plan_miss','all_miss') else target
        po_qty=old if mode in ('po_miss','all_miss','deferred') else target
        floor_qty=old if mode in ('floor_miss','all_miss') else target
        inventory=max(0,floor_qty-target) if mode!='no_floor' else None
        common=dict(site=site,sku=sku,period=period)
        put('sales_forecast.csv',Revision_ID=f'F0-{i}',Factory=site,Part_Number=sku,Plan_Month=period,Units=old,Effective_At=time(5),System_Captured_At=time(5,'08:35'),Owner='Sales',Change_Note='Initial forecast')
        put('sales_forecast.csv',Revision_ID=f'F1-{i}',Factory=site,Part_Number=sku,Plan_Month=period,Units=target,Effective_At=time(6,'09:00'),System_Captured_At=time(6,'09:03'),Owner='Sales',Change_Note='Revised demand')
        put('sop_decisions.csv',Decision_ID=f'D-{i}',Plant=site,Material=sku,Period=period,New_Target_Units=target,Approved_At=time(6,'11:00'),Entered_At=time(6,'11:08'),Approver='S&OP Chair',Status='approved',Reason='Change target')
        put('meeting_promises.csv',Action_ID=f'PM-{i}',Plant=site,Material=sku,Period=period,Promised_Units=target,Spoken_At=time(6,'11:12'),Written_At=time(6,'11:35'),Due_At=time(6,'18:00'),Responsible='Production',Related_Decision=f'D-{i}',System_Target='plan',Verbatim_Promise='Revise ERP')
        put('meeting_promises.csv',Action_ID=f'PP-{i}',Plant=site,Material=sku,Period=period,Promised_Units=target,Spoken_At=time(6,'11:14'),Written_At=time(6,'11:35'),Due_At=time(7,'12:00'),Responsible='Procurement',Related_Decision=f'D-{i}',System_Target='commitment',Verbatim_Promise='Revise released PO')
        put('erp_production.csv',Schedule_Revision=f'ERP0-{i}',Facility=site,Item=sku,Period=period,Planned_Units=old,Effective_Time=time(5,'08:40'),Extract_Record_Time=time(5,'08:45'),Approved_By='Planning',Change_Memo='Pre-decision')
        if mode!='deferred':
            day=10 if mode=='late' else 7
            put('erp_production.csv',Schedule_Revision=f'ERP1-{i}',Facility=site,Item=sku,Period=period,Planned_Units=plan_qty,Effective_Time=time(day,'08:30'),Extract_Record_Time=time(day,'09:00'),Approved_By='Planning',Change_Memo='Revised or unchanged')
        put('procurement_po.csv',PO_Revision=f'PO0-{i}',Ship_To=site,SKU=sku,Fiscal_Month=period,Committed_Units=old,Committed_Time=time(5,'10:00'),Stored_At=time(5,'10:10'),Buyer='Procurement',Vendor_Note='Original order')
        if mode!='deferred':
            day=10 if mode=='late' else 7
            put('procurement_po.csv',PO_Revision=f'PO1-{i}',Ship_To=site,SKU=sku,Fiscal_Month=period,Committed_Units=po_qty,Committed_Time=time(day,'09:30'),Stored_At=time(day,'10:00'),Buyer='Procurement',Vendor_Note='Revision or unchanged')
        if mode!='no_floor':
            put('mes_output.csv',Shift_Receipt=f'MES-{i}',Plant_ID=site,Item_Code=sku,Production_Month=period,Cumulative_Good_Units=floor_qty,Shift_End_Time=time(12,'16:00'),MES_Posted_Time=time(12,'16:05'),Line_Supervisor='Operations',Shift_Comment='Cumulative output')
            put('warehouse_stock.csv',Count_ID=f'WMS-{i}',Site=site,SKU=sku,Reporting_Period=period,On_Hand_Units=inventory,Counted_At=time(29,'16:00'),WMS_Recorded_At=time(29,'16:10'),Count_Owner='Warehouse',Reconciliation_Note='End-period physical count')
        put('inventory_policy.csv',Policy_ID=f'POL-{i}',Site=site,SKU=sku,Reporting_Period=period,Approved_Buffer_Units=0,Policy_Effective_At=time(5,'07:00'),Documented_At=time(5,'07:02'),Controller='Finance',Policy_Basis='Make-to-order policy')
        put('cost_master.csv',Cost_Revision=f'COST-{i}',Site=site,SKU=sku,Reporting_Period=period,Standard_Unit_Cost_USD=unit_cost,Valuation_At=time(5,'07:00'),Ledger_Recorded_At=time(5,'07:02'),Cost_Controller='Finance',Currency_Note='USD unit basis for test')
        shipment.append(dict(order_receipt=f'SHIP-{i}',site=site,sku=sku,period=period,shipped_units_total=target,shipped_at=time(29,'12:00'),posted_at=time(29,'12:10'),confirmed_by='Fulfillment',note='Cumulative shipments'))
        oracle.append({'case_key':f'{site}/{sku}/{period}','mode':mode,'target':target,'prior_plan':old,
                       'plan_state':'no_post_decision_observation' if mode=='deferred' else 'matched' if plan_qty==target else 'observed_different',
                       'po_state':'no_post_decision_observation' if mode=='deferred' else 'matched' if po_qty==target else 'observed_different',
                       'floor_state':'no_post_decision_observation' if mode=='no_floor' else 'matched' if floor_qty==target else 'observed_different',
                       'inventory':inventory,'book_value':None if inventory is None else inventory*unit_cost})
    for name,table in tables.items():
        p=path/name
        with p.open('w',encoding='utf8',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=HEADERS[name]);writer.writeheader();writer.writerows(table)
    (path/'customer_orders.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in shipment),encoding='utf8')
    return oracle


def evaluate(cases=1000,seed=931527,out=None):
    with tempfile.TemporaryDirectory(prefix='decision-floor-novel-') as d:
        root=Path(d);source=root/'input'; oracle=generate(source,cases,seed)
        state=root/'state';rules=load_rules(ROOT/'config'/'sources.json')
        # Hard fail if any unapproved network call is attempted during the engine run.
        with patch.object(socket,'socket',side_effect=AssertionError('NETWORK ATTEMPT')):
            db=make_db(state)
            try:
                first=ingest_folder(db,source,rules,state)
                rep=reconcile(db,'2026-11-01T12:00:00Z')
                archived=verify(db,state)
                matches=search(db,oracle[0]['case_key'].split('/')[1])
                bykey={c['case_key']:c for c in rep['cases']}
                assertions=0; failures=[]
                def check(cond,label,case):
                    nonlocal assertions
                    assertions+=1
                    if not cond and len(failures)<40:failures.append({'case':case,'invariant':label})
                check(first['new_sources']==10,'all ten structured export sets preserved','campaign')
                check(archived['status']=='PASS','source vault hashes verified','campaign')
                check(bool(matches),'generated case can be retrieved by source search','campaign')
                for expected in oracle:
                    key=expected['case_key'];current=bykey.get(key)
                    check(current is not None,'case must exist',key)
                    if current is None:continue
                    facts=current['facts'];tracks=current['tracks']
                    check(facts['approved_target']==expected['target'],'approved target',key)
                    check(facts['prior_plan']==expected['prior_plan'],'prior plan',key)
                    check(tracks['plan']['state']==expected['plan_state'],'ERP convergence state',key)
                    check(tracks['commitment']['state']==expected['po_state'],'procurement convergence state',key)
                    check(tracks['floor']['state']==expected['floor_state'],'physical floor convergence state',key)
                    check(facts['inventory_above_target_units']==expected['inventory'],'recorded inventory exposure units',key)
                    check(facts['inventory_above_target_book_value_usd']==expected['book_value'],'book value, not loss',key)
                    check(all(x.get('evidence') for x in current['questions']),'all questions have citations',key)
                check(len(rep['cases'])==cases,'expected number of cases','campaign')
                check(not failures,'invariant batch passed','campaign')
                result={'version':'0.2','qualification':'synthetic property checks, not real customer evidence',
                        'seed':seed,'cases':cases,'assertions':assertions,
                        'outcome':'PASS' if not failures else 'FAIL',
                        'source_versions':first['new_sources'],'event_count':rep.get('event_count'),
                        'vault_integrity':archived['status'],'network_attempts':0,'failures':failures}
                if out:Path(out).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
                return result
            finally:db.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--cases',type=int,default=1000);p.add_argument('--seed',type=int,default=931527);p.add_argument('--out');args=p.parse_args()
    if not 1<=args.cases<=2500:p.error('cases must be 1..2500')
    result=evaluate(args.cases,args.seed,args.out);print(json.dumps(result,indent=2));sys.exit(0 if result['outcome']=='PASS' else 2)

if __name__=='__main__':main()
