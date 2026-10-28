"""Finite task worker; source documents and model replies never become code."""
from __future__ import annotations
import json,os,sys,time,traceback
from pathlib import Path
from .common import BoundaryError,atomic_json,read_json

def limits(memory_mib:int,cpu_seconds:int)->None:
    if os.name=='posix':
        import resource
        def lower(kind,desired_soft,desired_hard=None):
            soft,hard=resource.getrlimit(kind)
            ceiling=desired_soft if desired_hard is None else desired_hard
            if hard!=resource.RLIM_INFINITY:ceiling=min(ceiling,hard)
            resource.setrlimit(kind,(min(desired_soft,ceiling),ceiling))
        # macOS rejects RLIMIT_AS in otherwise valid hosted processes. Its
        # inherited limits remain intact; the parent independently measures RSS.
        if sys.platform.startswith('linux'):lower(resource.RLIMIT_AS,memory_mib*1024**2)
        lower(resource.RLIMIT_CPU,cpu_seconds,cpu_seconds+1)
        lower(resource.RLIMIT_FSIZE,128*1024**2)
        lower(resource.RLIMIT_NOFILE,256)
        os.umask(0o077)
    # All platforms additionally have parent-observed RSS/CPU/deadline bounds.
    # These finite worker controls do not claim hostile-code sandboxing.

def perform(operation:str,payload:dict)->dict:
    if operation=='extract':
        from .axm import extract_document
        return extract_document(Path(payload['path']))
    if operation=='calculate':
        from .calculations import calculate
        return calculate(payload['expression'])
    if operation=='table':
        from .calculations import analyze_table
        return analyze_table(Path(payload['path']),operation=payload.get('operation','describe'),column=payload.get('column'),group_by=payload.get('group_by'),sheet=payload.get('sheet'))
    if operation=='model':
        import urllib.request
        from .models import NoRedirect,endpoint_url
        from axm_forge.model_runner import generate_text
        root=Path(payload['root']);settings=read_json(root/'settings.json');model=settings['model'];base=endpoint_url(model['base_url'],model.get('allow_private_network',False))
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        urllib.request.install_opener(opener)
        from axm_forge import model_runner
        original_http=model_runner._http_json
        purpose=payload['purpose']
        answer_schema={'type':'object','properties':{'text':{'type':'string'},'citations':{'type':'array','maxItems':12,'items':{'type':'integer'}},'uncertainties':{'type':'array','items':{'type':'string'}}},'required':['text','citations','uncertainties'],'additionalProperties':False}
        plan_schema={'type':'object','properties':{'steps':{'type':'array','maxItems':4,'items':{'type':'object','properties':{'action':{'type':'string','enum':['answer','draft','compare','calculate','table']},'message':{'type':'string'},'options':{'type':'object'}},'required':['action','message','options'],'additionalProperties':False}},'missing':{'type':'string'}},'required':['steps'],'additionalProperties':False}
        schema=plan_schema if purpose=='mary/intent-plan' else answer_schema if purpose in {'mary/answer','mary/draft','mary/compare'} else {'type':'object'}
        def bounded_http(endpoint,payload,**kwargs):
            payload=dict(payload)
            if model['transport']=='openai-compatible':payload['response_format']={'type':'json_schema','json_schema':{'name':'mary_work','strict':True,'schema':schema}}
            elif model['transport']=='ollama-native':payload['format']=schema
            body=original_http(endpoint,payload,**kwargs)
            if isinstance(body,dict) and isinstance(body.get('choices'),list):
                for choice in body['choices']:
                    if choice.get('finish_reason') not in {'stop',None}:raise BoundaryError('Model response ended before its output contract was complete.')
            if body.get('done_reason') not in {'stop',None}:raise BoundaryError('Local model response is incomplete.')
            return body
        model_runner._http_json=bounded_http
        for key in list(os.environ):
            if key.startswith('AXM_MODEL_'):os.environ.pop(key,None)
        os.environ.update(AXM_MODEL_TRANSPORT=model['transport'],AXM_MODEL_CACHE='off',AXM_MODEL_NAME=model['model'],AXM_MODEL_NUM_CTX=str(settings['context_tokens']))
        token=(root/'keys/model.token').read_text() if (root/'keys/model.token').exists() else ''
        os.environ['AXM_MODEL_API_KEY']=token
        started=time.monotonic()
        result=generate_text(payload['system'],payload['user'],model=model['model'],profile='mary.semantic@1',purpose=payload['purpose'],response_schema='mary/work-candidate@1',base_url=base,timeout=settings['max_model_seconds']-5,max_output_tokens=payload['max_tokens'],num_ctx=settings['context_tokens'],temperature=0.,seed=17)
        if len(result.get('text','').encode())>128*1024:raise BoundaryError('Model output exceeded its task contract.')
        result['seconds']=round(time.monotonic()-started,3);result['caller_cache_policy']='disabled; native receipt write label is not evidence of a cache file';return result
    raise BoundaryError('Unknown worker function; arbitrary execution is not enabled.')

def main()->int:
    request=read_json(Path(sys.argv[1]),max_bytes=1024*1024);result=Path(request['result']);limits(int(request.get('memory_mib',4096)),int(request.get('cpu_seconds',120)))
    try:
        output=perform(request['operation'],request['payload']);atomic_json(result,{'ok':True,'result':output});return 0
    except BaseException as e:
        atomic_json(result,{'ok':False,'error':type(e).__name__+': '+str(e)[:1200]});return 0
if __name__=='__main__':raise SystemExit(main())
