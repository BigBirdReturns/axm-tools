#!/usr/bin/env python3
"""Bounded, read-only i3X capture. Python standard library; never writes to a server."""
import argparse, datetime as dt, hashlib, json, pathlib, urllib.request, urllib.error

PUBLIC = 'https://api.i3x.dev/v1'
def capture(base=PUBLIC):
    base = base.rstrip('/')
    if not base.startswith('https://') and not base.startswith(('http://127.0.0.1:', 'http://localhost:')):
        raise ValueError('Use HTTPS, or an explicitly selected local test server.')
    now = dt.datetime.now(dt.timezone.utc)
    requests = [(n, 'GET', '/' + n, None) for n in ['info','namespaces','objecttypes','relationshiptypes','objects']]
    requests += [('related','POST','/objects/related',{'elementIds':['pump-101'],'includeMetadata':True}),
                 ('value','POST','/objects/value',{'elementIds':['pump-101-state','pump-101-production','pump-101-measurements-bearing-temperature-value'],'maxDepth':1}),
                 ('history','POST','/objects/history',{'elementIds':['pump-101-measurements-bearing-temperature-value'],'startTime':(now-dt.timedelta(minutes=2)).isoformat(),'endTime':now.isoformat(),'maxDepth':1})]
    records = []
    for name, method, route, body in requests:
        request = urllib.request.Request(base+route, data=None if body is None else json.dumps(body).encode(), method=method,
            headers={'Accept':'application/json','Content-Type':'application/json','User-Agent':'AXM-independent-i3X-proof/0.1'})
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                raw, status = response.read(2_000_001), response.status
            if len(raw)>2_000_000: raise ValueError('Response exceeds capture limit')
        except urllib.error.HTTPError as exc:
            raw, status = exc.read(100_000), exc.code
        text = raw.decode('utf-8'); json.loads(text)
        records.append({'id':name,'url':base+route,'method':method,'request':body,'status':status,
            'captured_at':dt.datetime.now(dt.timezone.utc).isoformat(),'body':text,'sha256':hashlib.sha256(raw).hexdigest()})
    return {'schema':'axm-i3x-capture/1','evidence_class':'public-demo-api-capture' if base==PUBLIC else 'operator-provided-read-only-capture',
        'base_url':base,'captured_at':now.isoformat(),'production_data':False if base==PUBLIC else None,'remote_writes':False,'records':records}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default=PUBLIC); parser.add_argument('--out',required=True)
    args=parser.parse_args(); target=pathlib.Path(args.out)
    if target.exists(): raise SystemExit('Refusing to overwrite a retained capture. Choose a new output path.')
    result=capture(args.base_url); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'path':str(target),'responses':len(result['records']),'http200':sum(r['status']==200 for r in result['records']),'remote_writes':False}))
