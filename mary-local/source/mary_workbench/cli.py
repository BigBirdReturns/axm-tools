"""Installed entry point for MARY's local personal-work profile."""
from __future__ import annotations
import argparse,getpass,json,os,secrets,socket,sys,threading,uuid,webbrowser
from pathlib import Path
from . import __version__
from .common import BoundaryError,atomic_json,default_home,init_home,local_path,read_json

def output(value):print(json.dumps(value,ensure_ascii=False,indent=2,default=str))

def main(argv=None)->int:
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='backslashreplace')
    p=argparse.ArgumentParser(description='MARY: owned local context, bounded tools, qualified workers.')
    p.add_argument('--home',type=Path,default=default_home());p.add_argument('--version',action='version',version=__version__)
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('init');sub.add_parser('scan');sub.add_parser('status');sub.add_parser('qualify');sub.add_parser('rebuild')
    a=sub.add_parser('serve');a.add_argument('--port',type=int,default=8765);a.add_argument('--no-browser',action='store_true');a.add_argument('--container',action='store_true',help='Bind inside an isolated container; publish only host loopback.')
    a=sub.add_parser('import');a.add_argument('path',type=Path);a.add_argument('--request-id');a.add_argument('--batch-files',type=int,default=128)
    a=sub.add_parser('search');a.add_argument('question');a.add_argument('--history',action='store_true')
    a=sub.add_parser('model');a.add_argument('--url',required=True);a.add_argument('--name',required=True);a.add_argument('--transport',choices=['openai-compatible','ollama-native'],default='openai-compatible');a.add_argument('--private-network',action='store_true');a.add_argument('--ask-key',action='store_true')
    a=sub.add_parser('work');a.add_argument('message');a.add_argument('--action',choices=['auto','answer','draft','compare','calculate','table','transcribe'],default='auto');a.add_argument('--source',action='append',default=[]);a.add_argument('--options',default='{}');a.add_argument('--request-id')
    a=sub.add_parser('job');a.add_argument('id');a.add_argument('--resume',action='store_true')
    a=sub.add_parser('tools');a.add_argument('operation',choices=['install'])
    a=sub.add_parser('backup');a.add_argument('repository',type=Path)
    a=sub.add_parser('restore');a.add_argument('repository',type=Path);a.add_argument('destination',type=Path);a.add_argument('--snapshot',default='latest')
    args=p.parse_args(argv);root=local_path(args.home)
    try:
        cfg=init_home(root)
        if args.command=='init':
            from .sources import Sources
            Sources(root);output({'status':'ready','home':str(root),'owner':cfg['owner'],'version':__version__});return 0
        if args.command=='scan':
            from .hardware import observe
            result=observe();atomic_json(root/'hardware.json',result);output(result);return 0
        if args.command=='serve':
            if not 1024<=args.port<=65535:raise BoundaryError('Use an unprivileged port between 1024 and 65535.')
            from .server import create_app
            import uvicorn
            app=create_app(root);token=(root/'keys/web.token').read_text();url=f'http://127.0.0.1:{args.port}/#'+token
            # The token is shown only to the local operator, never logged by HTTP.
            print('MARY local workspace: '+url,flush=True)
            if not args.no_browser and not args.container:threading.Timer(1.5,lambda:webbrowser.open(url)).start()
            uvicorn.run(app,host='0.0.0.0' if args.container else '127.0.0.1',port=args.port,access_log=False,log_level='warning');return 0
        if args.command=='tools':
            from .tools import restic_path
            output({'recovery_executable':str(restic_path(root,install=True)),'status':'prepared'});return 0
        if args.command in {'backup','restore'}:
            from .recovery import backup,restore
            password=getpass.getpass('Recovery password: ')
            result=backup(root,args.repository,password) if args.command=='backup' else restore(root,args.repository,password,args.destination,args.snapshot)
            output(result);return 0
        if args.command=='model':
            from .models import configure
            result=configure(root,{'base_url':args.url,'model':args.name,'transport':args.transport,'allow_private_network':args.private_network,'api_key':getpass.getpass('Local model API key: ') if args.ask_key else ''});output(result);return 0
        if args.command=='qualify':
            from .models import qualify
            result=qualify(root);output(result);return 0 if result['status']=='passed' else 2
        if args.command in {'import','search','rebuild'}:
            from .sources import Sources
            library=Sources(root)
            if args.command=='import':
                identity=args.request_id or uuid.uuid4().hex;library.begin_import(args.path,identity)
                while True:
                    result=library.import_batch(identity,max_files=args.batch_files);print(json.dumps({'id':identity,'status':result['status'],'processed':result['processed'],'admitted':result['admitted'],'errors':len(result['errors'])}),flush=True)
                    if result['status']=='complete':break
                output(result);return 0 if result['coverage']=='complete-supported-files' else 3
            output(library.search(args.question,history=args.history) if args.command=='search' else library.rebuild());return 0
        from .jobs import Workbench
        bench=Workbench(root)
        try:
            if args.command=='status':output({'owner':cfg['owner'],'sources':bench.sources.list(),'work':bench.list(),'qualification':read_json(root/'qualification.json')});return 0
            if args.command=='work':result=bench.submit({'request_id':args.request_id or uuid.uuid4().hex,'message':args.message,'action':args.action,'source_ids':args.source,'options':json.loads(args.options)},wait=True)
            else:result=bench.resume(args.id,wait=True) if args.resume else bench.get(args.id)
            output(result);return 0 if result['status']=='completed' else 2
        finally:bench.close()
    except (BoundaryError,OSError,ValueError) as e:
        print(json.dumps({'status':'refused','error':str(e)},ensure_ascii=False),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
