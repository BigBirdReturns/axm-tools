"""Read-only hardware observations and ODS configuration candidates."""
from __future__ import annotations
import json,os,platform,shutil,subprocess,sys
from pathlib import Path
from .common import BoundaryError,hash_file,now,read_json,memory_budget

def command(args:list[str],seconds:int=5)->dict:
    try:
        p=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=seconds,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        return {'exit_code':p.returncode,'stdout':p.stdout[:16000],'stderr':p.stderr[:2000]}
    except (OSError,subprocess.TimeoutExpired) as e:return {'error':str(e)[:300]}

def observe()->dict:
    import psutil
    mem=psutil.virtual_memory();gpus=[];backend='cpu';memory_type='none';vram=0
    smi=shutil.which('nvidia-smi')
    if smi:
        r=command([smi,'--query-gpu=uuid,name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'])
        if r.get('exit_code')==0:
            for line in r['stdout'].splitlines():
                fields=[f.strip() for f in line.split(',')]
                if len(fields)==5:
                    try:gpus.append({'uuid':fields[0],'name':fields[1],'vram_mib':int(fields[2]),'free_mib':int(fields[3]),'driver':fields[4],'supplier':'nvidia'})
                    except ValueError:pass
            if gpus:backend='nvidia';memory_type='discrete';vram=max(g['free_mib'] for g in gpus)
    if platform.system()=='Linux':
        for device in sorted(Path('/sys/class/drm').glob('card[0-9]*/device')):
            vendor=device/'vendor'
            if not vendor.exists():continue
            vendor_id=vendor.read_text().strip();size=device/'mem_info_vram_total'
            if vendor_id not in {'0x1002','0x8086'}:continue
            entry={'supplier':'amd' if vendor_id=='0x1002' else 'intel','pci_device':(device/'device').read_text().strip(),'sysfs_device':str(device.resolve())}
            if size.exists():
                try:entry['vram_mib']=int(size.read_text())//1024**2
                except ValueError:pass
            gpus.append(entry)
            if backend=='cpu' and entry.get('vram_mib',0)>2048:backend=entry['supplier'];memory_type='discrete';vram=entry['vram_mib']
        pci=command(['lspci','-nn']) if shutil.which('lspci') else {}
        description='\n'.join(x for x in pci.get('stdout','').splitlines() if any(w in x.lower() for w in ['vga','display controller','3d controller','thunderbolt']))
    else:description=''
    if platform.system()=='Darwin' and platform.machine().lower()=='arm64':backend='apple';memory_type='unified';vram=mem.available//1024**2
    budget=memory_budget()
    result={'execution_memory_budget':budget,'observed_at':now(),'system':platform.system(),'release':platform.release(),'architecture':platform.machine(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'ram_bytes':mem.total,'available_ram_bytes':mem.available,'gpus':gpus,'pci_description':description,'model_selection_envelope':{'backend':backend,'memory_type':memory_type,'vram_mib':vram,'ram_gib':budget['effective_total_bytes']//1024**3},'standing':'observation; neither GPU runtime nor task quality is inferred','power_or_driver_changes':False}
    try:result['ods_candidate']=ods_candidate(result)
    except (BoundaryError,OSError,ValueError) as e:result['ods_candidate']={'status':'unavailable','reason':str(e)[:400]}
    return result

def ods_candidate(hardware:dict)->dict:
    root=Path(__file__).parent/'vendor/ods';manifest=read_json(Path(__file__).with_name('supplier-lock.json'))
    if not manifest:raise BoundaryError('Pinned ODS supplier files are missing.')
    for name,expected in manifest['files'].items():
        if hash_file(root/name)!=expected:raise BoundaryError('ODS supplier identity changed: '+name)
    e=hardware['model_selection_envelope'];backend=e['backend']
    if backend=='intel':backend='sycl'
    args=[sys.executable,'-B',str(root/'ods/scripts/select-model.py'),'--catalog',str(root/'ods/config/model-library.json'),'--backend',backend,'--memory-type',e['memory_type'],'--vram-mb',str(e['vram_mib']),'--ram-gb',str(e['ram_gib']),'--host-arch',hardware['architecture'],'--installable-only','--min-context','4096']
    r=command(args,10)
    if r.get('exit_code')!=0:return {'status':'no_candidate','detail':r.get('stderr',r.get('error','unknown')),'commit':manifest['commit']}
    value=json.loads(r['stdout']);return {'status':'candidate-not-qualified','commit':manifest['commit'],'selected':value.get('selected'),'alternatives':value.get('alternatives',[]),'reason':value.get('reason'),'scope':'ODS catalog memory/runtime estimate; local execution and task checks still required'}
