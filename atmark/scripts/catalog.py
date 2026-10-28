#!/usr/bin/env python3
"""Atmark catalog workshop. Standard library only; read-only acquisition, no eBay writes.
The public-web observation seam is an explicit fallback, never a complete-inventory claim.
"""
from __future__ import annotations
import argparse, collections, csv, datetime, hashlib, html, io, json, os, re, struct, sys, time
import urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'
INTEL = 'https://www.intel.com/content/www/us/en/products/sku/212264/intel-xeon-w1350p-processor-12m-cache-up-to-5-10-ghz/specifications.html'
POLICY = 'https://www.ebay.com/help/selling/listings/adding-pictures-listing?id=4148'
UA = 'AXM-AtmarkWorkshop/1.0 (read-only; https://bigbirdreturns.github.io/axm-tools/atmark/)'
MAX_BYTES = 12 * 1024 * 1024

def stamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(o): return json.dumps(o, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def digest(o): return hashlib.sha256(canonical(o)).hexdigest()
def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def clean(value): return re.sub(r'\s+', ' ', str(value or '')).strip()
def money(v):
    if v is None or v == '': return None
    t = re.sub(r'[^0-9.\-]', '', str(v))
    try:
        x = float(t)
        return round(x, 2) if 0 <= x < 1e9 else None
    except ValueError: return None

def checked_url(url, host):
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.hostname != host or p.username or p.password or p.port not in (None,443):
        raise ValueError('Unapproved URL host or scheme')
    return url

class PinnedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host): self.host = host
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl, self.host)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def get_bytes(url, host, headers=None):
    checked_url(url, host)
    req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.build_opener(PinnedRedirect(host)).open(req, timeout=35) as r:
        b = r.read(MAX_BYTES + 1)
        if len(b) > MAX_BYTES: raise ValueError('Response exceeds bounded byte limit')
        return b, r.headers.get('Content-Type', '')

def category(title):
    t = title.lower()
    if re.search(r'bare\s*bones?|barebone', t): return 'Barebones'
    if re.search(r'caddy|heatsink|heat\s*sink|front fan|fan /|motherboard|power supply|card holder|front bezel|vroc|cpu kit|p02509', t): return 'Parts & upgrades'
    if re.search(r'laptop|touchscreen|precision 3560', t): return 'Laptops'
    if re.search(r'poweredge|proliant|dl380', t) and 'processor' not in t: return 'Servers'
    if re.search(r'tower|desktop|think\s*station|optiplex|hp z[246]|precision|hp pro 400', t): return 'Workstations & desktops'
    if re.search(r'video card|graphics.*card|radeon|geforce|nvidia quadro', t): return 'Graphics'
    if re.search(r'processor|xeon|pentium', t): return 'Processors'
    if re.search(r'ram|dimm|ddr[345]|hard drive|ssd', t): return 'Memory & storage'
    return 'Parts & upgrades'

def platform(title, cat):
    s = re.sub(r'think\s+station', 'ThinkStation', title, flags=re.I)
    if cat not in ('Barebones','Workstations & desktops','Laptops','Servers'): return None
    patterns = [r'(HP Z[246]\s+G\d)', r'(Dell Precision(?: Workstation)?\s+\d{4})',
                r'(Lenovo ThinkStation\s+P\d+[cC]?)',r'(Dell OptiPlex\s+\d+)',
                r'(HP Pro\s+\d+\s+G\d)',r'(Lenovo T\d+)',r'(HP ProLiant\s+DL\d+\s+G\d+)']
    for pat in patterns:
        m = re.search(pat, s, re.I)
        if m:
            v = m.group(1).replace(' Workstation','')
            # Form factor and generation are identity-bearing, never silently pooled.
            if re.search(r'\bSFF\b', s, re.I): v += ' SFF'
            if re.search(r'\b(?:G2|Gen 2)\b', s, re.I): v += ' Gen 2'
            return v
    return None

def specs(title):
    d = {}
    p = re.search(r'\b(?:i[3579]-\d+[A-Z]*|[EW]-\d+[A-Z]*|G7400)\b', title, re.I)
    if p: d['CPU'] = p.group(0)
    p = re.search(r'Xeon[ -]+Gold\s+(\d+)', title, re.I)
    if p: d['CPU'] = ('2 × ' if re.search(r'\b2x\b', title, re.I) else '') + 'Xeon Gold '+p.group(1)
    p = re.search(r'RTX\s+\d+(?:\s+Ti)?|\bP(?:4000|2000|1000|620|400)\b|\bT500\b|WX\s?3100', title, re.I)
    if p: d['GPU'] = p.group(0)
    p = re.search(r'(\d+)\s?GB(?:\s+DDR\d)?(?:\s+RAM)?(?=\s+\d+\s?(?:TB|GB)\s+SSD)', title, re.I)
    if p: d['RAM'] = p.group(1)+' GB'
    p = re.search(r'(\d+)\s?(TB|GB)\s+SSD', title, re.I)
    if p: d['Storage'] = p.group(1)+' '+p.group(2).upper()+' SSD'
    p = re.search(r'(?:Win(?:dows)?\s*|\bW\s*)(10|11)(?:\s*(?:Pro|P))?', title, re.I)
    if p: d['OS'] = 'Windows '+p.group(1) + (' Pro' if re.search(r'(?:Pro|W10P|W11P)',title,re.I) else '')
    return d

def display_title(title):
    s = clean(title)
    s = re.sub(r'\b(?:CTO|BTO)\b', '', s, flags=re.I)
    s = re.sub(r'\bWin(?:dows)?\s*(10|11)\s*Pro\b', r'Windows \1 Pro', s, flags=re.I)
    s = re.sub(r'\bW\s*(10|11)P\b', r'Windows \1 Pro', s, flags=re.I)
    s = re.sub(r'\bW\s*(10|11)\b', r'Windows \1', s, flags=re.I)
    s = re.sub(r'\bThink Station\b', 'ThinkStation', s, flags=re.I)
    return clean(s)

def issue(code, severity, note, sources=None):
    return {'code':code,'severity':severity,'note':note,'sources':sources or []}

def normalize(o, media=None):
    id = str(o.get('item_id',''))
    if not re.fullmatch(r'\d{9,15}', id): raise ValueError('Invalid item ID: '+id)
    if o.get('seller') != 'atmarktradinginc': raise ValueError('Seller mismatch: '+id)
    title = clean(o.get('title'))
    if not title: raise ValueError('Missing title: '+id)
    checked_url(o['url'], 'www.ebay.com')
    if urllib.parse.urlsplit(o['url']).path != '/itm/'+id: raise ValueError('Item URL / identity mismatch')
    cat = category(title); model = platform(title,cat); details = specs(title)
    issues=[]; proposed=display_title(title); aspects=dict(o.get('aspects',{})); corrections=[]
    if re.search(r'\bW-1350P\b', title, re.I):
        if 'Emerald Rapids' in title:
            proposed='Intel Xeon W-1350P SRKP9 6-Core 4.0GHz LGA1200 Rocket Lake CPU'
            corrections.append({'field':'title','before':title,'after':proposed,'evidence':INTEL})
            issues.append(issue('cpu-generation','confirmed-correction','Intel identifies W-1350P as Rocket Lake; the source title says Emerald Rapids.',[INTEL,o['url']]))
        if aspects.get('Socket Type') == 'Socket P':
            corrections.append({'field':'Socket Type','before':'Socket P','after':'FCLGA1200','evidence':INTEL})
            aspects['Socket Type']='FCLGA1200'
            issues.append(issue('cpu-socket','confirmed-correction','Intel specifies FCLGA1200; the source item specifics say Socket P.',[INTEL,o['url']]))
    if o.get('aspects',{}).get('Color') == 'Gold' and cat=='Workstations & desktops':
        issues.append(issue('color-field','review','The Color field says Gold beside a Xeon Gold CPU. Inspect the unit before replacing this field.',[o['url']]))
    if id=='227543292463' and '2.8' in title and '3.10' in str(o.get('aspects',{})):
        issues.append(issue('clock-conflict','review','Title says 2.8 GHz; item specifics say 3.10 GHz. Resolve CPU identity and base/turbo meaning before editing.',[o['url']]))
    if id=='227473686089' and any('FMYAAOSwXfZl-zL5' in u for u in o.get('image_urls',[])):
        issues.append(issue('photo-model-conflict','hold','This listing for Precision 3650 uses the same image URL as a Precision 3630 listing; the pictured front badge reads Precision 3630. This image is withheld from its product card.',[o['url'],'https://www.ebay.com/itm/226202561474']))
    if id=='225749481734' and any('l3kAAOSwYEhjx0Sp' in u for u in o.get('image_urls',[])):
        issues.append(issue('photo-model-review','review','The front model badge is not established by this capture. Confirm the image matches Precision 3430.',[o['url']]))
    if id=='226924094753' and any('hU0AAeSwSz1ooMzO' in u for u in o.get('image_urls',[])):
        issues.append(issue('accessory-exclusion','review','The photograph shows a 512GB-labelled insert; the title explicitly excludes the SSD. Keep NO SSD prominent and photograph the actual included parts.',[o['url']]))
    if o.get('availability')=='out-of-stock-observed':
        issues.append(issue('availability','hold','The followed item page reports out of stock. The older store snapshot still contains this item.',[o['url']]))
    if o.get('additional_observations'):
        issues.append(issue('price-conflict','review','A later public observation shows $105, while the retained store snapshot shows $109. No automated price change is proposed.',[x['source_url'] for x in o['additional_observations']]))
    if details.get('OS','').startswith('Windows 10'):
        issues.append(issue('os-support','review','Disclose the installed edition and applicable support/ESU status; inspect licensing and eligibility rather than assuming them.', ['https://learn.microsoft.com/en-us/lifecycle/products/windows-10-home-and-pro']))
    m = (media or {}).get(id, {})
    image = m.get('local_path') or (o.get('image_urls') or [None])[0]
    if any(x['code']=='photo-model-conflict' for x in issues): image=None
    photo_status='listing-image-unverified' if image else 'photo-needed'
    if max(m.get('width',0),m.get('height',0)) and max(m.get('width',0),m.get('height',0))<500:
        issues.append(issue('photo-resolution','review','The captured source is below 500 pixels on its longest side. Obtain a larger original; no detail is synthesized.',[POLICY]))
    if len(proposed)>80:
        # Keep all meaning in the full display title; do not truncate a publication proposal.
        issues.append(issue('title-length','review','The display title exceeds 80 characters. Review the marketplace title before publication.'))
    return {'id':id,'sku':'ebay:'+id,'physical_inventory_id':None,'source_hash':digest(o),'original':o,
            'title':proposed,'family':model or proposed,'category':cat,'specs':details,
            'aspects':aspects,'price_min':o.get('price_min'),'price_max':o.get('price_max'),
            'currency':o.get('currency','USD'),'availability':o.get('availability','unverified'),
            'url':o['url'],'image':image,'media':m,'photo_status':photo_status,'issues':issues,
            'corrections':corrections,'configurable':bool(re.search(r'\b(?:CTO|BTO)\b|Build to Order',title,re.I)) or (o.get('price_min')!=o.get('price_max')),
            'variations':o.get('variations',{}),'publication_state':'review-only'}

def build(packet, media=None):
    items=[]; seen={}; conflicts=[]
    for o in packet['items']:
        id=str(o.get('item_id',''))
        if id in seen:
            if digest(o)!=seen[id]: conflicts.append({'item_id':id,'reason':'Conflicting duplicate observation; retained separately, not silently overwritten.'})
            continue
        seen[id]=digest(o);items.append(normalize(o,media))
    groups=collections.defaultdict(list)
    for item in items:
        # Only OS wording is removed; GPU/CPU/RAM/storage/form-factor differences remain.
        key=re.sub(r'(?:Windows|Win|W)\s*(?:10|11)\s*(?:Pro|P)?','',item['original']['title'],flags=re.I)
        key=clean(re.sub(r'\b(?:CTO|BTO)\b','',key,flags=re.I)).lower()
        groups[key].append(item)
    os_groups=[]
    for g in groups.values():
        if len(g)>1 and len({i['specs'].get('OS') for i in g})>1:
            os_groups.append({'ids':[i['id'] for i in g],'family':g[0]['family'],'reason':'Same title-level hardware, different OS; grouping proposal only. Quantities remain independent and unknown.'})
            for i in g:i['issues'].append(issue('os-sibling','organization','Show related OS offers together without ending or merging any listing.'))
    media_groups=collections.defaultdict(list)
    for i in items:
        for url in i['original'].get('image_urls',[]):media_groups[url].append(i['id'])
    aliases=[{'url':k,'ids':v} for k,v in media_groups.items() if len(v)>1]
    issues=[dict(x,item_id=i['id']) for i in items for x in i['issues']]
    return {'schema_version':1,'version':VERSION,'captured_at':packet['captured_at'],'built_at':stamp(),
            'source_packet_sha256':digest(packet),'source_method':packet.get('collection_method'),
            'coverage':packet['coverage'],'items':items,'os_groups':os_groups,'shared_images':aliases,
            'conflicts':conflicts,'issues':issues,'metrics':{'items':len(items),'families':len({(i['category'],i['family']) for i in items}),
            'images':sum(bool(i['image']) for i in items),'confirmed_corrections':sum(len(i['corrections']) for i in items),
            'review_findings':len(issues),'os_groups':len(os_groups),'out_of_stock':sum(i['availability']=='out-of-stock-observed' for i in items)},
            'authority':{'live_store_writes':False,'stock_verified':False,'seller_endorsement':False,'image_rights':'Seller / original rights holders. Images shown as attributed listing references in an independent demonstration; no blanket redistribution license is asserted.'}}

def parse_csv(path):
    # Seller Hub has multiple exports; map field names, preserve every original row.
    source_bytes=Path(path).read_bytes(); raw=source_bytes.decode('utf-8-sig'); rows=list(csv.DictReader(io.StringIO(raw)))
    def key(s):return re.sub('[^a-z0-9]','',s.lower())
    result=[]; rejected=[]
    for n,row in enumerate(rows,2):
        d={key(k):v for k,v in row.items() if k}
        def take(*names):return next((d[k] for k in names if d.get(k) not in (None,'')),None)
        id=clean(take('itemnumber','itemid','legacyitemid'));title=clean(take('title','itemtitle'))
        seller=clean(take('seller','sellerusername'))
        if seller and seller.lower()!='atmarktradinginc':
            rejected.append({'row':n,'reason':'Seller outside Atmark scope'});continue
        if not re.fullmatch(r'\d{9,15}',id) or not title:
            rejected.append({'row':n,'reason':'Missing/invalid item ID or title'});continue
        price=money(take('currentprice','startprice','buyitnowprice','price'))
        result.append({'item_id':id,'seller':'atmarktradinginc','title':title,'url':'https://www.ebay.com/itm/'+id,
            'price_min':price,'price_max':price,'currency':take('currency') or 'USD','image_urls':[],
            'availability':'seller-export-unverified','aspects':{},'seller_sku':take('customlabel','customlabelsku','sku'),
            'reported_quantity':take('availablequantity','quantity'),'source_kind':'seller_csv','source_row':n,
            'source_file_sha256':hashlib.sha256(source_bytes).hexdigest(),'raw_row':row})
    return {'schema_version':1,'seller':'atmarktradinginc','captured_at':stamp(),'collection_method':'Local seller-supplied CSV; not authenticated or live stock verification.',
        'coverage':{'complete':False,'listing_records':len(result),'expected_total':None,'reason':'Completeness requires reconciliation with a seller-authoritative export.','rejected_rows':rejected},'items':result}

def image_dimensions(data):
    if data[:8]==b'\x89PNG\r\n\x1a\n':return struct.unpack('>II',data[16:24])
    if data[:2]==b'\xff\xd8':
        p=2
        while p+9<len(data):
            if data[p]!=255:p+=1;continue
            marker=data[p+1];p+=2
            if marker in (0xD8,0xD9):continue
            if marker==0xDA:break
            if p+2>len(data):break
            length=int.from_bytes(data[p:p+2],'big')
            if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                return (int.from_bytes(data[p+5:p+7],'big'),int.from_bytes(data[p+3:p+5],'big'))
            if length<2:break
            p+=length
    if data[:4]==b'RIFF' and data[8:12]==b'WEBP':
        if data[12:16]==b'VP8X':return (1+int.from_bytes(data[24:27],'little'),1+int.from_bytes(data[27:30],'little'))
        if data[12:16]==b'VP8 ':
            p=data.find(b'\x9d\x01\x2a',20,40)
            if p!=-1:return (int.from_bytes(data[p+3:p+5],'little')&16383,int.from_bytes(data[p+5:p+7],'little')&16383)
        if data[12:16]==b'VP8L' and len(data)>25:
            b=data[21:25];return (1+((b[1]&63)<<8|b[0]),1+((b[3]&15)<<10|b[2]<<2|b[1]>>6))
    return (0,0)

def media_collect(packet,out,delay=1.5):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);manifest={};cache={};failures=[]
    cache_index=out/'source-index.json'
    if cache_index.exists():
        for u,m in read_json(cache_index).items():
            name=Path(m['local_path']).name
            f=out/name
            if f.exists() and hashlib.sha256(f.read_bytes()).hexdigest()==m['sha256']:
                cache[u]=m
    for o in packet['items']:
        if not o.get('image_urls'):continue
        url=o['image_urls'][0]
        try:
            checked_url(url,'i.ebayimg.com')
            if url not in cache:
                b,ctype=get_bytes(url,'i.ebayimg.com')
                if not ctype.startswith('image/') or 'svg' in ctype:raise ValueError('Unexpected image type')
                h=hashlib.sha256(b).hexdigest();ext='.webp' if b[:4]==b'RIFF' else '.png' if b[:8]==b'\x89PNG\r\n\x1a\n' else '.jpg'
                file=out/(h+ext)
                if file.exists() and hashlib.sha256(file.read_bytes()).hexdigest()!=h:raise ValueError('Existing asset hash mismatch')
                file.write_bytes(b);w,ht=image_dimensions(b)
                cache[url]={'source_url':url,'sha256':h,'bytes':len(b),'width':w,'height':ht,'local_path':'assets/'+file.name,
                    'captured_at':stamp(),'operation':'original bytes; full-frame CSS contain only','rights_status':'reference-only; rights holder not independently established','identity_status':'unit-unverified','display_status':'source-frame-preserved'}
                time.sleep(delay)
            manifest[o['item_id']]=dict(cache[url],listing_url=o['url'])
            print('MEDIA',o['item_id'],manifest[o['item_id']]['sha256'][:12],flush=True)
        except Exception as e:
            failures.append({'item_id':o['item_id'],'url':url,'error':str(e),'disposition':'blocked; not bypassed'})
            print('MEDIA BLOCKED',o['item_id'],str(e),flush=True)
            if isinstance(e,urllib.error.HTTPError) and e.code in (401,403,429):break
    write_json(cache_index,cache)
    return {'assets':manifest,'failures':failures,'unique_assets':len({m['sha256'] for m in manifest.values()})}

def browse(seller,category_id,out,token):
    if not token:raise ValueError('EBAY_APP_TOKEN is absent. Use an authorized eBay application token or a local seller export; credentials never enter the site.')
    if seller!='atmarktradinginc':raise ValueError('This run is scoped to atmarktradinginc')
    Path(out).mkdir(parents=True,exist_ok=True);items=[];offset=0;total=None;pages=[];complete=False
    while offset<10000:
        params=urllib.parse.urlencode({'category_ids':str(category_id),'filter':'sellers:{'+seller+'}','limit':200,'offset':offset})
        url='https://api.ebay.com/buy/browse/v1/item_summary/search?'+params
        b,_=get_bytes(url,'api.ebay.com',{'Authorization':'Bearer '+token,'X-EBAY-C-MARKETPLACE-ID':'EBAY_US'})
        Path(out,f'page-{offset:05d}.json').write_bytes(b);r=json.loads(b);total=r.get('total');summaries=r.get('itemSummaries',[])
        pages.append({'offset':offset,'sha256':hashlib.sha256(b).hexdigest(),'count':len(summaries)})
        for s in summaries:
            if s.get('seller',{}).get('username','').lower()!=seller:raise ValueError('API result escaped seller scope')
            id=str(s.get('legacyItemId') or s['itemId'].split('|')[1]);p=money(s.get('price',{}).get('value'))
            items.append({'item_id':id,'seller':seller,'title':s['title'],'url':'https://www.ebay.com/itm/'+id,
                'price_min':p,'price_max':p,'currency':s.get('price',{}).get('currency','USD'),
                'image_urls':[s['image']['imageUrl']] if s.get('image') else [],'availability':'api-search-result','condition':s.get('condition','not-captured'),
                'aspects':{},'source_kind':'ebay_browse_api','source_url':url,'raw_summary':s})
        if not r.get('next'):complete=True;break
        if not summaries:break
        offset+=200;time.sleep(1.5)
    return {'schema_version':1,'seller':seller,'captured_at':stamp(),'collection_method':'Official eBay Browse API; category-scoped public discovery, not a physical stock ledger.',
        'coverage':{'complete':False,'pagination_complete':complete,'category_id':category_id,'listing_records':len(items),'reported_api_total':total,'expected_total':None,'reason':'Category discovery is not a whole-store seller inventory export.'},'pages':pages,'items':items}

def export_files(catalog,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);write_json(out/'catalog.json',catalog)
    fields=['Item ID','Original title','Proposed display title','Price low USD','Price high USD','Finding codes','Source URL','Source hash','Status']
    def safe(v):
        s=str(v if v is not None else '')
        return "'"+s if s[:1] in '=+-@\t\r' else s
    with (out/'listing-review.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(fields)
        for i in catalog['items']:
            w.writerow([safe(x) for x in [i['id'],i['original']['title'],i['title'],i['price_min'],i['price_max'],','.join(x['code'] for x in i['issues']),i['url'],i['source_hash'],'REVIEW ONLY - not an eBay upload template']])
    queue=[{'item_id':i['id'],'title':i['title'],'source_hash':i['source_hash'],'current_media':i['media'],
        'required_views':['front','rear / connectors','inside / installed parts','model and part-number label','wear / defects','included accessories'] if i['category'] in ('Barebones','Workstations & desktops','Laptops','Servers') else ['whole item','part-number label','connectors / contacts','wear / defects','included accessories'],
        'identity_review':'pending','display_review':'pending','physical_stock_match':'pending','publication':'held'} for i in catalog['items']]
    write_json(out/'photo-queue.json',queue)
    write_json(out/'change-plan.json',{'live_writes':False,'scope':'review-only proposals','input_sha256':catalog['source_packet_sha256'],
        'changes':[{'item_id':i['id'],'expected_source_hash':i['source_hash'],'corrections':i['corrections'],'issues':i['issues']} for i in catalog['items']],
        'preconditions':['Refresh seller-authoritative records','Match each SKU to physical inventory','Approve every before/after diff','Verify category and variation rules','Separately authorize an authenticated seller write integration']})

def check(catalog,packet,base):
    by={}
    for o in packet['items']:by.setdefault(str(o['item_id']),o)
    errors=[]
    if catalog.get('source_packet_sha256')!=digest(packet):errors.append('Source packet mismatch')
    if len({i['id'] for i in catalog['items']})!=len(catalog['items']):errors.append('Duplicate canonical ID')
    if {i['id'] for i in catalog['items']}!=set(by):errors.append('Unaccounted source IDs')
    for i in catalog['items']:
        if i['source_hash']!=digest(by[i['id']]):errors.append(i['id']+': stale source')
        if i['price_min']!=by[i['id']].get('price_min') or i['price_max']!=by[i['id']].get('price_max'):errors.append(i['id']+': price mutated')
        if i['publication_state']!='review-only':errors.append(i['id']+': unapproved publication state')
        m=i.get('media',{})
        if m.get('local_path'):
            p=(Path(base)/m['local_path']).resolve()
            if not p.is_relative_to(Path(base).resolve()):errors.append(i['id']+': path escaped');continue
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=m['sha256']:errors.append(i['id']+': image integrity')
    if catalog['authority']['live_store_writes']:errors.append('Live writes enabled')
    if catalog['coverage'].get('complete'):errors.append('Unproven whole-store coverage')
    return errors

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('build');p.add_argument('--input',default=str(ROOT/'data/observed.json'));p.add_argument('--media',default=str(ROOT/'data/media.json'));p.add_argument('--out',default=str(ROOT/'data'))
    p=sub.add_parser('import-csv');p.add_argument('input');p.add_argument('--out',required=True)
    p=sub.add_parser('collect-media');p.add_argument('--input',default=str(ROOT/'data/observed.json'));p.add_argument('--out',default=str(ROOT/'assets'));p.add_argument('--manifest',default=str(ROOT/'data/media.json'))
    p=sub.add_parser('browse');p.add_argument('--seller',default='atmarktradinginc');p.add_argument('--category',default='58058');p.add_argument('--out',required=True)
    p=sub.add_parser('verify');p.add_argument('--input',default=str(ROOT/'data/observed.json'));p.add_argument('--catalog',default=str(ROOT/'data/catalog.json'));p.add_argument('--base',default=str(ROOT))
    args=ap.parse_args()
    try:
        if args.cmd=='build':
            packet=read_json(args.input);media=read_json(args.media).get('assets',{}) if Path(args.media).exists() else {}
            c=build(packet,media);export_files(c,args.out);print(json.dumps(c['metrics'],indent=2))
        elif args.cmd=='import-csv':write_json(args.out,parse_csv(args.input))
        elif args.cmd=='collect-media':write_json(args.manifest,media_collect(read_json(args.input),args.out))
        elif args.cmd=='browse':
            result=browse(args.seller,args.category,args.out,os.environ.get('EBAY_APP_TOKEN'));write_json(Path(args.out)/'observed.json',result)
        elif args.cmd=='verify':
            errors=check(read_json(args.catalog),read_json(args.input),args.base);print(json.dumps({'pass':not errors,'errors':errors}));return bool(errors)
    except (ValueError,KeyError,OSError,urllib.error.URLError) as e:
        print('BLOCKED: '+str(e),file=sys.stderr);return 2
    return 0
if __name__=='__main__':sys.exit(main())
