"""Ephemeral loopback adapter to a network-isolated vLLM container.
Preserves JSON bytes and native harness deadlines; never retries or scores.
Only used while one_gpu.py owns and monitors that container. No public listener.
"""
from __future__ import annotations
import hashlib, http.server, json, secrets, subprocess, threading, time

# Executed inside the already chosen container, not downloaded from the page.
CLIENT = '''import sys,urllib.request,urllib.error
path=sys.argv[1];data=sys.stdin.buffer.read();method=sys.argv[2]
try:
 r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000'+path,data=data if method=='POST' else None,method=method,headers={'Content-Type':'application/json'}),timeout=float(sys.argv[3]))
except urllib.error.HTTPError as e:r=e
sys.stdout.buffer.write(str(r.status).encode()+b'\\n');sys.stdout.buffer.flush()
while True:
 b=r.read1(65536) if hasattr(r,'read1') else r.read(65536)
 if not b:break
 sys.stdout.buffer.write(b);sys.stdout.buffer.flush()
'''

class Bridge:
    def __init__(self, container, model, timeout, directory):
        self.token=secrets.token_urlsafe(32); self.model=model;self.container=container
        self.timeout=timeout;self.directory=directory;self.lock=threading.Lock()
        self.processes=set();self.closed=False;self.count=0
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_OPTIONS(self): self.send_error(403,'No browser origin access')
            def do_GET(self): self.handle_api('GET')
            def do_POST(self): self.handle_api('POST')
            def handle_api(self, method):
                start=time.monotonic(); n=0; returned=0;digest=None;process=None
                record={'method':method,'path':self.path,'started_at':time.time()}
                try:
                    if self.headers.get('Host')!=f'127.0.0.1:{owner.port}' or self.headers.get('Origin'):
                        self.send_error(403);return
                    if not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+owner.token):
                        self.send_error(401);return
                    if owner.closed: self.send_error(503);return
                    if method=='GET' and self.path not in ('/health','/v1/models'):
                        self.send_error(404);return
                    if method=='POST' and self.path not in ('/v1/chat/completions','/v1/completions'):
                        self.send_error(404);return
                    if self.headers.get('Transfer-Encoding'): self.send_error(400);return
                    n=int(self.headers.get('Content-Length','0'))
                    if n<0 or n>16*1024*1024: self.send_error(413);return
                    data=self.rfile.read(n)
                    if len(data)!=n: self.send_error(400);return
                    if method=='POST':
                        obj=json.loads(data)
                        if obj.get('model')!=owner.model: self.send_error(400,'Exact model identity required');return
                        if not any(k in obj for k in ('max_tokens','max_completion_tokens')):
                            self.send_error(400,'Explicit benchmark output budget required');return
                        digest=hashlib.sha256(data).hexdigest()
                    with owner.lock:
                        if len(owner.processes)>=4: self.send_error(429,'At most four queued transport clients');return
                        process=subprocess.Popen(['docker','exec','-i',owner.container,'python3','-c',CLIENT,self.path,method,str(owner.timeout)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
                        owner.processes.add(process);owner.count+=method=='POST'
                    timer=threading.Timer(owner.timeout,process.kill);timer.daemon=True;timer.start()
                    try:
                        process.stdin.write(data);process.stdin.close()
                        status_line=process.stdout.readline(16)
                        status=int(status_line);record['http_status']=status
                        self.send_response(status)
                        self.send_header('Content-Type','text/event-stream' if method=='POST' and obj.get('stream') else 'application/json')
                        self.send_header('Connection','close');self.end_headers()
                        h=hashlib.sha256()
                        while True:
                            block=process.stdout.read1(65536)
                            if not block:break
                            h.update(block);returned+=len(block)
                            if returned>64*1024*1024: raise ValueError('Response exceeds 64 MiB bound')
                            self.wfile.write(block);self.wfile.flush()
                        code=process.wait(timeout=5);record.update(response_sha256=h.hexdigest(),transport_exit=code)
                        # Preserve an abruptly terminated response. The native harness owns timeout/failure grading.
                    finally:
                        timer.cancel()
                except (Exception, BrokenPipeError) as e:
                    record['transport_error']=str(e)[:300]
                    if process is None: self.close_connection=True
                finally:
                    if process:
                        if process.poll() is None:process.kill()
                        try:process.wait(timeout=5)
                        except subprocess.TimeoutExpired:pass
                        for pipe in (process.stdin,process.stdout):
                            if pipe and not pipe.closed:pipe.close()
                        with owner.lock:owner.processes.discard(process)
                    record.update(request_sha256=digest,request_bytes=n,response_bytes=returned,wall_s=time.monotonic()-start)
                    with owner.lock:
                        with (owner.directory/'native-transport.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True;self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def close(self):
        self.closed=True
        with self.lock:
            for process in list(self.processes):
                if process.poll() is None:process.kill()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)
