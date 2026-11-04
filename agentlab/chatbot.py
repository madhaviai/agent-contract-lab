"""Local chatbot and before/after policy demo. Binds only to loopback."""
import argparse
import asyncio
import json
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .core import SCENARIOS, run
from .providers import Offline, OpenAI, Anthropic
from .report import render

PAGE = Path(__file__).with_name('chatbot.html')

class DemoServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, provider, output, langfuse=False, transport='local'):
        super().__init__(address, DemoHandler)
        self.provider, self.output, self.langfuse, self.transport = provider, Path(output), langfuse, transport
        self.output.mkdir(parents=True,exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.allowed_hosts = {f'127.0.0.1:{self.server_port}',f'localhost:{self.server_port}'}

class DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log prompts, request bodies, or credentials.

    def send(self, code, body, content_type='application/json'):
        content = body if isinstance(body,bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type',content_type+'; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.end_headers()
        self.wfile.write(content)

    def valid_host(self):
        return self.headers.get('Host') in self.server.allowed_hosts

    def do_GET(self):
        if not self.valid_host():
            return self.send(403,'{"error":"invalid host"}')
        path=urlsplit(self.path).path
        if path=='/':
            config={'csrf':self.server.token,'provider':self.server.provider.name,'model':self.server.provider.model,
                    'langfuse':self.server.langfuse,'prompt':SCENARIOS['injection']}
            data=json.dumps(config).replace('<','\\u003c')
            return self.send(200,PAGE.read_text().replace('__CONFIG__',data),'text/html')
        match=re.fullmatch(r'/reports/([a-f0-9]{32})\.html',path)
        if match:
            file=self.server.output/(match[1]+'.html')
            if file.is_file():
                return self.send(200,file.read_bytes(),'text/html')
        return self.send(404,'{"error":"not found"}')

    def do_POST(self):
        if not self.valid_host():
            return self.send(403,'{"error":"invalid host"}')
        origin=self.headers.get('Origin')
        if origin and origin not in {'http://'+h for h in self.server.allowed_hosts}:
            return self.send(403,'{"error":"invalid origin"}')
        if not secrets.compare_digest(self.headers.get('X-Demo-Token',''),self.server.token):
            return self.send(403,'{"error":"invalid token"}')
        if self.path!='/api/run':
            return self.send(404,'{"error":"not found"}')
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 16_384:
                raise ValueError('request too large or empty')
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict) or set(data)-{'variant','prompt'}:
                raise ValueError('invalid request')
            variant=data.get('variant')
            if variant not in ('baseline','policy_only'):
                raise ValueError('variant must be baseline or policy_only')
            prompt=data.get('prompt')
            if not isinstance(prompt,str) or not 1 <= len(prompt) <= 2000:
                raise ValueError('prompt must contain 1 to 2000 characters')
            if self.server.provider.name=='offline' and prompt!=SCENARIOS['injection']:
                raise ValueError('scripted mode uses the fixed rehearsal question; choose a live provider for arbitrary questions')
        except (ValueError,TypeError):
            return self.send(400,'{"error":"invalid variant or prompt; scripted mode requires the bundled question"}')
        if not self.server.lock.acquire(blocking=False):
            return self.send(409,'{"error":"a run is already in progress"}')
        try:
            observer=None
            if self.server.langfuse:
                from .observability import LangfuseObserver
                observer=LangfuseObserver()
            trace=asyncio.run(run(self.server.provider,variant,'injection',
                prompt=None if prompt==SCENARIOS['injection'] else prompt,
                observer=observer,transport=self.server.transport))
            key=trace['trace_id']
            (self.server.output/(key+'.json')).write_text(json.dumps(trace,indent=2))
            render([trace],self.server.output/(key+'.html'))
            trace['local_report_url']='/reports/'+key+'.html'
            self.send(200,json.dumps(trace))
        except Exception:
            self.send(500,'{"error":"run failed; check server configuration"}')
        finally:
            self.server.lock.release()

def main():
    p=argparse.ArgumentParser(description='Local policy chatbot: before/after execution policy')
    p.add_argument('--provider',choices=['offline','openai','anthropic'],default='offline')
    p.add_argument('--model')
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--out',default='artifacts/chatbot')
    p.add_argument('--transport',choices=['local','mcp'],default='local')
    p.add_argument('--langfuse',action='store_true')
    args=p.parse_args()
    if args.provider!='offline' and not args.model:
        p.error('--model is required for a live provider')
    try:
        provider=Offline() if args.provider=='offline' else {'openai':OpenAI,'anthropic':Anthropic}[args.provider](args.model)
        if args.langfuse:
            from .observability import LangfuseObserver
            LangfuseObserver()  # Fail early on missing SDK or credentials.
    except ValueError as exc:
        p.error(str(exc))
    server=DemoServer(('127.0.0.1',args.port),provider,args.out,args.langfuse,args.transport)
    print(f'Open http://127.0.0.1:{server.server_port} · provider={provider.name} · all outbound actions are simulated',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__=='__main__':
    main()
