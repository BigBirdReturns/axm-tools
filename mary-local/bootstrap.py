#!/usr/bin/env python3
"""Auditable per-user build. No administrator rights, Git, cloud key or service."""
from __future__ import annotations
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,time,uuid,venv
from pathlib import Path
VERSION='0.3.0'
ROOT=Path(__file__).resolve().parent

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def run(args,env=None):
    result=subprocess.run([str(a) for a in args],env=env)
    if result.returncode:raise RuntimeError('Build step failed with exit '+str(result.returncode)+'. Earlier installed versions and personal data remain intact.')
def default_install():
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'MARY-App'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/MARY-App'
    return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'mary-app'
def verify():
    manifest=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'))
    for name,item in manifest['files'].items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file() or p.stat().st_size!=item['size'] or digest(p)!=item['sha256']:raise RuntimeError('Build-kit verification failed: '+name)
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--uv',type=Path);parser.add_argument('--install-dir',type=Path,default=default_install());parser.add_argument('--home',type=Path);parser.add_argument('--no-launch',action='store_true');parser.add_argument('--offline',action='store_true');parser.add_argument('--test-system-python',action='store_true',help=argparse.SUPPRESS);args=parser.parse_args()
    if sys.version_info<(3,11):raise RuntimeError('Use the supplied launcher to obtain its pinned managed Python.')
    manifest=verify();install=args.install_dir.expanduser().resolve();install.mkdir(parents=True,exist_ok=True)
    if install==Path.home().resolve() or install==Path(install.anchor):raise RuntimeError('Use a dedicated installation directory.')
    if os.name=='posix':install.chmod(0o700)
    tmp=install/'build-temp';tmp.mkdir(exist_ok=True);env={**os.environ,'TMPDIR':str(tmp),'TMP':str(tmp),'TEMP':str(tmp),'PYTHONDONTWRITEBYTECODE':'1','UV_LINK_MODE':'copy','UV_NO_PROGRESS':'1'}
    release_id=VERSION+'-'+digest(ROOT/'MANIFEST.json')[:12];generation=install/'versions'/release_id;generation.mkdir(parents=True,exist_ok=True);environment=generation/'environment';python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    complete=generation/'INSTALLATION.json';expected={'release':VERSION,'manifest_sha256':digest(ROOT/'MANIFEST.json'),'python_minor':list(sys.version_info[:2]),'source':'published source and hash-pinned package artifacts'}
    if complete.exists():
        saved=json.loads(complete.read_text())
        if saved.get('manifest_sha256')!=expected['manifest_sha256']:raise RuntimeError('Existing generation does not match the build kit.')
    else:
        if not python.exists():
            if args.uv:run([args.uv,'venv','--python',sys.executable,environment],env)
            else:venv.EnvBuilder(with_pip=True).create(environment)
        wheels=sorted((ROOT/'wheels').glob('*.whl'))
        if len(wheels)!=3:raise RuntimeError('Expected the exact MARY, Core and Genesis wheel set.')
        if args.uv:
            command=[args.uv,'pip','sync','--python',python,'--require-hashes',ROOT/'requirements.lock']
            if args.offline:command.append('--offline')
            run(command,env)
            run([args.uv,'pip','install','--python',python,'--no-deps',*wheels],env)
        else:
            command=[python,'-m','pip','install','--require-hashes','-r',ROOT/'requirements.lock']
            if args.offline:command.extend(['--no-index','--find-links',str(ROOT/'wheelhouse')])
            run(command,env);run([python,'-m','pip','install','--no-deps',*wheels],env)
        # Independently exercise the installed wheel rather than importing source.
        smoke="from mary_workbench.calculations import calculate; from mary_workbench import __version__; from axm_build.sign import hybrid1_keygen,hybrid1_public_key; p,s=hybrid1_keygen(); assert p==hybrid1_public_key(s); assert calculate('0.1+0.2')['exact']=='3/10'; print('MARY',__version__,'installed kernel and exact-tool checks passed')"
        run([python,'-B','-c',smoke],env)
        complete.write_text(json.dumps({**expected,'installed_at':time.time()},indent=2)+'\n')
        # Keep recipes and original wheels. Dependency environments stay regenerable.
        kit=generation/'build-kit';kit.mkdir(exist_ok=True)
        for name in ['requirements.lock','SOURCE-PROVENANCE.json','MANIFEST.json','LICENSE','NOTICE','bootstrap.py']:
            shutil.copyfile(ROOT/name,kit/name)
        shutil.copytree(ROOT/'wheels',kit/'wheels',dirs_exist_ok=True)
    cli=[str(python),'-B','-m','mary_workbench.cli']
    if args.home:cli+=['--home',str(args.home.expanduser().resolve())]
    run(cli+['init'],env)
    pointer=install/'CURRENT.json';pending=install/('.CURRENT-'+uuid.uuid4().hex);pending.write_text(json.dumps({'release':release_id,'python':str(python),'home':str(args.home) if args.home else None},indent=2));os.replace(pending,pointer)
    if os.name=='nt':
        launcher=install/'Start MARY.cmd';home_argument=(' --home "'+str(args.home.expanduser().resolve())+'"') if args.home else ''
        launcher.write_text('@echo off\r\n"'+str(python)+'" -B -m mary_workbench.cli'+home_argument+' serve\r\nif errorlevel 1 pause\r\n',encoding='utf-8')
    else:
        import shlex
        launcher=install/('Start MARY.command' if sys.platform=='darwin' else 'start-mary.sh');launcher.write_text('#!/bin/sh\nexec '+' '.join(shlex.quote(x) for x in cli+['serve'])+'\n');launcher.chmod(0o700)
    print('\nReady. Start MARY with: '+str(launcher))
    print('Your workspace is separate from this versioned installation. Source folders remain unchanged.')
    if not args.no_launch:run(cli+['serve'],env)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:print('Build stopped: '+str(exc),file=sys.stderr);raise SystemExit(2)
