"""Serve only the extracted public map kit on loopback. No account or package needed."""
from pathlib import Path
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import argparse,webbrowser
ROOT=Path(__file__).resolve().parents[1]
class LocalFiles(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
 def log_message(self,*args):pass
 def do_GET(self):
  if self.headers.get('Host') not in ('127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)):
   self.send_error(403,'Local host required');return
  super().do_GET()
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8770);p.add_argument('--no-browser',action='store_true');a=p.parse_args();s=ThreadingHTTPServer(('127.0.0.1',a.port),LocalFiles);url='http://127.0.0.1:'+str(s.server_port)+'/review/'
 print('Suginami public map and review desk: '+url+'\nAll records remain browser-local; no external requests are required.',flush=True)
 if not a.no_browser:webbrowser.open(url)
 try:s.serve_forever()
 except KeyboardInterrupt:pass
 finally:s.server_close()
