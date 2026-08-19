#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps, ImageStat
from playwright.sync_api import sync_playwright

APERTURES=['plant','household','property','street','neighborhood','region','stewardship']

def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()
def metrics(path: Path):
    im=Image.open(path).convert('RGB')
    sample=ImageOps.fit(im,(256,160),Image.Resampling.LANCZOS).convert('L')
    return {'bytes':path.stat().st_size,'sha256':sha(path),'width':im.width,'height':im.height,'entropy':round(sample.entropy(),4),'variance':round(ImageStat.Stat(sample).var[0],2)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--url',required=True); ap.add_argument('--output',required=True); args=ap.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    result={'schema':'manzanita-works/real-estate-visual-review@1','target':args.url,'apertures':{},'responsive':{},'result':'PASS','failures':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':960},device_scale_factor=1)
        page.goto(args.url,wait_until='networkidle')
        page.wait_for_function("document.querySelector('#sceneImage') && document.querySelector('#sceneImage').complete && document.querySelector('#sceneImage').naturalWidth > 800")
        desktop=page.evaluate('''() => { const stage=document.querySelector('.stage').getBoundingClientRect(); const h=document.querySelector('.hero h1'); const r=h.getBoundingClientRect(); const cs=getComputedStyle(h); return {viewport:[innerWidth,innerHeight],stage_width:stage.width,stage_height:stage.height,stage_share:+(stage.width/innerWidth).toFixed(3),headline_width:r.width,headline_height:r.height,headline_font:parseFloat(cs.fontSize),body_overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),apertures:document.querySelectorAll('#apertureRail button').length,scene:[document.querySelector('#sceneImage').naturalWidth,document.querySelector('#sceneImage').naturalHeight]}; }''')
        if desktop['stage_share'] < .92: result['failures'].append(f"desktop stage width share too small: {desktop['stage_share']}")
        if desktop['headline_font'] > 82: result['failures'].append(f"desktop headline too large: {desktop['headline_font']}")
        if desktop['body_overflow'] > 1: result['failures'].append(f"desktop overflow {desktop['body_overflow']}")
        if desktop['apertures'] != 7: result['failures'].append(f"aperture count {desktop['apertures']}")
        page.screenshot(path=str(out/'desktop-household.png'),full_page=False)
        result['responsive']['desktop']=desktop | {'screenshot':metrics(out/'desktop-household.png')}

        for key in APERTURES:
            btn=page.locator(f'#apertureRail button[data-aperture="{key}"]')
            btn.click(); page.wait_for_timeout(250)
            state=page.evaluate('''() => ({key:new URL(location.href).searchParams.get('aperture'),src:document.querySelector('#sceneImage').getAttribute('src'),title:document.querySelector('#sceneTitle').textContent,cls:document.querySelector('#evidenceClass').textContent})''')
            shot=out/f'aperture-{key}.png'; page.locator('.stage').screenshot(path=str(shot)); result['apertures'][key]=state | {'screenshot':metrics(shot)}

        imgs={k:ImageOps.fit(Image.open(out/f'aperture-{k}.png').convert('RGB'),(192,120),Image.Resampling.LANCZOS) for k in APERTURES}
        pairs={}
        for i,a in enumerate(APERTURES):
            for b in APERTURES[i+1:]:
                aa=list(imgs[a].getdata()); bb=list(imgs[b].getdata()); mse=sum((x-y)**2 for pa,pb in zip(aa,bb) for x,y in zip(pa,pb))/(len(aa)*3); rms=math.sqrt(mse); pairs[f'{a}:{b}']=round(rms,2)
                if rms < 9: result['failures'].append(f"aperture render too similar {a}:{b} rms={rms:.2f}")
        result['pairwise_rms']=pairs

        for name,viewport in [('tablet',{'width':1024,'height':900}),('mobile',{'width':390,'height':844})]:
            pg=browser.new_page(viewport=viewport,device_scale_factor=1); pg.goto(args.url+'?aperture=street',wait_until='networkidle'); pg.wait_for_function("document.querySelector('#sceneImage').complete && document.querySelector('#sceneImage').naturalWidth > 800")
            m=pg.evaluate('''() => { const h=document.querySelector('.hero h1'); const hs=getComputedStyle(h); const taps=[...document.querySelectorAll('#apertureRail button,#conditionRail button,#seatRail button')].map(x=>x.getBoundingClientRect().height); return {viewport:[innerWidth,innerHeight],horizontal_overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth),headline_font:parseFloat(hs.fontSize),min_control_height:Math.min(...taps),nav_visible:getComputedStyle(document.querySelector('.topbar nav')).display!=='none',scene:[document.querySelector('#sceneImage').naturalWidth,document.querySelector('#sceneImage').naturalHeight]}; }''')
            if m['horizontal_overflow'] > 1: result['failures'].append(f"{name} overflow {m['horizontal_overflow']}")
            if m['min_control_height'] < 43: result['failures'].append(f"{name} min control {m['min_control_height']}")
            if name=='mobile' and m['headline_font'] > 50: result['failures'].append(f"mobile headline {m['headline_font']}")
            shot=out/f'{name}-street.png'; pg.screenshot(path=str(shot),full_page=False); result['responsive'][name]=m | {'screenshot':metrics(shot)}; pg.close()
        browser.close()

    if result['failures']: result['result']='FAIL'
    (out/'VISUAL_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
    files=[out/'desktop-household.png']+[out/f'aperture-{k}.png' for k in APERTURES]+[out/'tablet-street.png',out/'mobile-street.png']
    labels=['DESKTOP · HOUSEHOLD']+[f'APERTURE · {k.upper()}' for k in APERTURES]+['TABLET · STREET','MOBILE · STREET']
    cell=(620,430); cols=2; rows=math.ceil(len(files)/cols); sheet=Image.new('RGB',(cell[0]*cols,cell[1]*rows),'#0f130f'); draw=ImageDraw.Draw(sheet)
    for idx,(path,label) in enumerate(zip(files,labels)):
        im=Image.open(path).convert('RGB'); thumb=ImageOps.contain(im,(cell[0]-24,cell[1]-52),Image.Resampling.LANCZOS); x=(idx%cols)*cell[0]+12; y=(idx//cols)*cell[1]+38; sheet.paste(thumb,(x,y)); draw.text((x,12+(idx//cols)*cell[1]),label,fill='#f0ebdd')
    sheet.save(out/'contact-sheet.jpg','JPEG',quality=90,optimize=True)
    if result['failures']: raise SystemExit('\n'.join(result['failures']))
    print(json.dumps({'result':'PASS','contact_sheet':str(out/'contact-sheet.jpg'),'apertures':7},indent=2))

if __name__=='__main__': main()
