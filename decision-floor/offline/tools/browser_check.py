"""Optional static browser check with fixture-backed API responses.

The managed browser in some environments blocks localhost. HTTP API integration
is tested separately in tests/test_console.py. This check explicitly exercises
HTML/CSS/JS against a synthetic fixture, not a live connected API server.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decision_floor.cli import execute
from types import SimpleNamespace
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    raise SystemExit('Optional engineering UI check requires Playwright locally; product does not.')
ROOT=Path(__file__).resolve().parents[1]

def main():
    checks=[];errors=[];requests=[]
    with TemporaryDirectory() as tmp:
        p=Path(tmp)
        shutil.copytree(ROOT/'sample_inputs'/'missed',p/'incoming')
        execute(SimpleNamespace(input=str(p/'incoming'),workspace=str(p/'state'),out=str(p/'report'),config=str(ROOT/'config'/'sources.json'),as_of=None))
        report=json.loads((p/'report'/'decision_floor_report.json').read_text())
        config=json.loads((ROOT/'config'/'sources.json').read_text())
        summary={k:report.get(k) for k in ('cases','source_count','event_count','issues','skipped_files','as_of')}
        summary['questions']=[{'case_key':c['case_key'],**q} for c in report['cases'] for q in c['questions']]
        summary['history']={'items':[],'transitions':[]}
        summary['last_run']={'files_scanned':12,'new_sources':12}
        search={'hits':[{'source':'sop_decisions.csv','locator':'csv:row:2','sha256':'f'*64,'snippet':'SOP-017 approved 7000 units'}]}
        fixtures={'/api/summary':summary,'/api/config':config,'/api/verify':{'status':'PASS','checked':12,'failures':[]},
                  '/api/reviews':{'reviews':[]},'/api/scan':{'case_count':1,'questions':len(summary['questions']), 'verification':{'status':'PASS'}},
                  '/api/search':search}
        html=(ROOT/'ui'/'index.html').read_text().replace('__TOKEN_JSON__',json.dumps('static-ui-token')).replace('__TOKEN__','static-ui-token')
        html=html.replace('<link rel="stylesheet" href="/style.css?token=static-ui-token">','').replace('<script src="/app.js?token=static-ui-token"></script>','')
        js=(ROOT/'ui'/'app.js').read_text()
        css=(ROOT/'ui'/'style.css').read_text()
        def open_view(browser,mobile=False):
            context=browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1320,'height':900},is_mobile=mobile)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:requests.append(r.url))
            page.set_content(html);page.add_style_tag(content=css)
            page.evaluate('''fixtures=>{window.fetch=async (url,options)=>{
                const key=String(url).split('?')[0];
                const data=fixtures[key]||{error:'Not in static browser fixtures'};
                return {ok:!data.error,status:data.error?404:200,headers:{get:()=> 'application/json'},json:async()=>data};
            }}''',fixtures)
            page.add_script_tag(content=js)
            return context,page
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            context,page=open_view(browser)
            page.wait_for_function("document.querySelector('#metrics').textContent.includes('12')")
            checks.append(['static app loads',page.locator('h1').inner_text()=='Decision Floor'])
            checks.append(['synthetic source coverage visible','12' in page.locator('#metrics').inner_text()])
            checks.append(['source-keyed case rendered','PLANT-07' in page.locator('#cases').inner_text()])
            checks.append(['physical divergence visible','12,000' in page.locator('#case-detail').inner_text()])
            page.get_by_role('button',name='Open investigations').click()
            checks.append(['questions rendered',page.locator('#question-list .finding').count()>=5])
            page.get_by_role('button',name='Evidence search').click()
            page.locator('#query').fill('SOP-017')
            page.get_by_role('button',name='Search source archive').click()
            page.wait_for_function("document.querySelector('#search-results').textContent.includes('sop_decisions.csv')")
            checks.append(['source locator and SHA rendered','SHA-256' in page.locator('#search-results').inner_text()])
            page.get_by_role('button',name='Source mapping').click()
            checks.append(['editable mapping contents','sales_forecast.csv' in page.locator('#mappingeditor').input_value()])
            page.get_by_role('button',name='Verify & export').click()
            page.get_by_role('button',name='Verify archived bytes').click()
            page.wait_for_function("document.querySelector('#verifyoutput').textContent.includes('PASS')")
            checks.append(['verification displayed','PASS' in page.locator('#verifyoutput').inner_text()])
            checks.append(['no script errors',not errors])
            checks.append(['no network requests',not requests])
            context.close()
            mobile_context,mobile=open_view(browser,True)
            mobile.wait_for_function("document.querySelector('#metrics').textContent.includes('12')")
            checks.append(['mobile app visible',mobile.locator('h1').is_visible()])
            checks.append(['mobile no horizontal overflow',mobile.evaluate('document.body.scrollWidth <= window.innerWidth + 6')])
            mobile.screenshot(path=str(ROOT/'acceptance'/'browser_preview.png'),full_page=True)
            mobile_context.close();browser.close()
    result={'qualification':'fixture-backed HTML/CSS/JS; separate Python tests cover live HTTP API',
            'browser':'Chromium','checks':len(checks),'pass_count':sum(bool(v) for _,v in checks),
            'status':'PASS' if all(v for _,v in checks) else 'FAIL',
            'details':[{'name':n,'pass':bool(v)} for n,v in checks],
            'javascript_errors':errors,'network_requests':requests}
    (ROOT/'acceptance'/'browser_check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS' else 2

if __name__=='__main__':sys.exit(main())
