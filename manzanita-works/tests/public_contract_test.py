#!/usr/bin/env python3
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'index.html').read_text(encoding='utf-8')
css=(ROOT/'style.css').read_text(encoding='utf-8')
js=(ROOT/'app.js').read_text(encoding='utf-8')
data=json.loads((ROOT/'data/estate.json').read_text(encoding='utf-8'))
errors=[]
for marker in ['mw-operating-fabric-v0.1.0','Operating picture','Projects','Commons','Pilotage','Money','Commodity perimeter','Architecture','Handoff']:
    if marker not in html: errors.append(f'missing html marker: {marker}')
if data['release']['id']!='mw-operating-fabric-v0.1.0': errors.append('release id mismatch')
if len(data['capacities'])<8: errors.append('capacity floor')
if len(data['modules'])<7: errors.append('module floor')
if len(data['perimeter'])<8: errors.append('perimeter floor')
if any(x.get('decision') not in {'WRAP','ADAPT','DONOR','HOLD'} for x in data['perimeter']): errors.append('invalid commodity decision')
for banned in ['https://','http://','fetch("http','fetch(\'http']:
    if banned in html+css+js: errors.append(f'external runtime reference: {banned}')
for phrase in ['LIVE EXTERNAL EFFECTS','Fundraising is a view','MAKE THE WORLD OUR FLOOR','The dashboard Stu was being asked to build']:
    if phrase not in html: errors.append(f'missing product claim: {phrase}')
if errors:
    print('Operating Fabric static contract: FAIL')
    for e in errors: print(' -',e)
    sys.exit(1)
print('Operating Fabric static contract: PASS')
print('  capacities:',len(data['capacities']))
print('  modules:',len(data['modules']))
print('  perimeter candidates:',len(data['perimeter']))
