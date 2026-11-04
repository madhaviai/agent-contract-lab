import asyncio,json,tempfile,threading,unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from agentlab.chatbot import DemoServer
from agentlab.core import SCENARIOS,run
from agentlab.providers import Offline
from agentlab.observability import LangfuseObserver
class Observation:
    def __init__(self,args): self.args=args; self.id='a'*16; self.updates=[]; self.ends=0
    def update(self,**args): self.updates.append(args)
    def end(self): self.ends+=1
class Client:
    def __init__(self): self.obs=[]; self.scores=[]
    def start_observation(self,**args):
        o=Observation(args); self.obs.append(o); return o
    def create_score(self,**args): self.scores.append(args)
    def flush(self): pass
    def get_trace_url(self,**args): return None
class TracingTests(unittest.TestCase):
    def test_parenting_scores_and_proxy_usage(self):
        c=Client(); t=asyncio.run(run(Offline(),'policy_only','injection',observer=LangfuseObserver(c)))
        self.assertTrue(t['eval']['execution_safe']); self.assertEqual(len(c.scores),4)
        self.assertTrue(all(o.ends==1 for o in c.obs))
        self.assertTrue(all('parent_span_id' in o.args['trace_context'] for o in c.obs[1:]))
        self.assertFalse(any('usage_details' in u for o in c.obs for u in o.updates))
    def test_export_failure_preserves_policy(self):
        class Broken(Client):
            def start_observation(self,**args): raise RuntimeError('offline')
        t=asyncio.run(run(Offline(),'policy_only','injection',observer=LangfuseObserver(Broken())))
        self.assertTrue(t['eval']['execution_safe']); self.assertTrue(t['tracing_warnings'])
class HttpTests(unittest.TestCase):
    def test_before_after_and_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            s=DemoServer(('127.0.0.1',0),Offline(),folder)
            th=threading.Thread(target=s.serve_forever,daemon=True); th.start()
            base=f'http://127.0.0.1:{s.server_port}'
            def post(v,token=None,prompt=None):
                r=Request(base+'/api/run',data=json.dumps({'variant':v,'prompt':prompt or SCENARIOS['injection']}).encode(),headers={'Content-Type':'application/json','X-Demo-Token':token or s.token})
                return json.load(urlopen(r))
            try:
                self.assertIn(b'Compare both',urlopen(base).read())
                a=post('baseline'); b=post('policy_only')
                self.assertTrue(a['eval']['unauthorized_executed']); self.assertFalse(b['eval']['unauthorized_executed'])
                self.assertTrue(b['eval']['answer_correct']); self.assertEqual(a['prompt'],b['prompt'])
                self.assertEqual(urlopen(base+b['local_report_url']).status,200)
                for args,code in [({'token':'wrong'},403),({'prompt':'other'},400)]:
                    with self.assertRaises(HTTPError) as e: post('baseline',**args)
                    self.assertEqual(e.exception.code,code)
            finally: s.shutdown(); s.server_close(); th.join()
