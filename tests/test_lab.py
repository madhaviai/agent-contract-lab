import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agentlab.core import authorization, catalog, run, validate
from agentlab.providers import Offline, OpenAI, Anthropic
from agentlab.report import render, summarize, wilson

class HarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_request_contract(self):
        captured = {}
        def fake(url, headers, payload):
            captured.update({'url':url, 'payload':payload})
            return {'status':'completed', 'output':[{'type':'message', 'content':[{'type':'output_text','text':'answer'}]}], 'usage':{'input_tokens':5,'output_tokens':2}}
        with patch.dict('os.environ', {'OPENAI_API_KEY':'test'}):
            provider = OpenAI('test-model')
            with patch('agentlab.providers.post', side_effect=fake):
                reply = await provider.generate(provider.start('system','question'),catalog('hardened','sprawl'),'sprawl','hardened',0)
        self.assertTrue(captured['payload']['tools'][0]['strict'])
        self.assertFalse(captured['payload']['parallel_tool_calls'])
        self.assertNotIn('temperature',captured['payload'])
        self.assertEqual(reply['text'],'answer')

    async def test_anthropic_request_contract(self):
        captured = {}
        def fake(url, headers, payload):
            captured.update({'url':url,'payload':payload})
            return {'content':[{'type':'text','text':'answer'}],'stop_reason':'end_turn','usage':{'input_tokens':5,'output_tokens':2}}
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY':'test'}):
            provider = Anthropic('test-model')
            with patch('agentlab.providers.post',side_effect=fake):
                await provider.generate(provider.start('system','question'),catalog('hardened','sprawl'),'sprawl','hardened',0)
        self.assertIn('input_schema',captured['payload']['tools'][0])
        self.assertEqual(captured['payload']['tool_choice'],{'type':'auto'})
        self.assertNotIn('output_config',captured['payload'])

    async def test_correct_answer_can_have_unsafe_trajectory(self):
        r = await run(Offline(), 'baseline', 'injection')
        self.assertTrue(r['eval']['answer_correct'])
        self.assertTrue(r['eval']['unauthorized_executed'])
        self.assertFalse(r['eval']['task_success'])

    async def test_policy_blocks_action_even_if_model_requests_it(self):
        r = await run(Offline(), 'policy_only', 'injection')
        self.assertTrue(r['eval']['task_success'])
        self.assertFalse(r['eval']['trajectory_pass'])
        self.assertTrue(r['eval']['unauthorized_attempt'])
        self.assertFalse(r['eval']['unauthorized_executed'])
        blocked = next(x for x in r['spans'] if x['name'] == 'send_report')
        self.assertEqual(blocked['result']['code'], 'POLICY_DENIED')

    async def test_description_ablation_keeps_catalog_count(self):
        a = await run(Offline(), 'baseline', 'sprawl')
        b = await run(Offline(), 'descriptions_only', 'sprawl')
        self.assertEqual(len(a['catalog']), len(b['catalog']))
        self.assertEqual(a['documents_sha256'], b['documents_sha256'])
        self.assertEqual(a['prompt'], b['prompt'])
        self.assertGreater(a['tool_calls'], b['tool_calls'])
        self.assertEqual(a['usage_kind'], 'estimated_proxy')

    async def test_tool_budget_is_enforced(self):
        r = await run(Offline(), 'baseline', 'sprawl', max_calls=1)
        self.assertEqual(r['tool_calls'], 1)
        self.assertEqual(r['status'], 'tool_budget_exhausted')
        self.assertFalse(r['eval']['task_success'])

    async def test_custom_prompt_is_unscored(self):
        r = await run(Offline(), 'hardened', 'sprawl', prompt='Example')
        self.assertFalse(r['eval']['scored'])

    async def test_provider_error_remains_error(self):
        class Broken(Offline):
            async def generate(self, *args):
                raise RuntimeError('test failure')
        r = await run(Broken(), 'hardened', 'sprawl')
        self.assertEqual(r['status'], 'error')
        self.assertFalse(r['eval']['task_success'])

class ContractTests(unittest.TestCase):
    def test_schema_rejects_boolean_approval_and_bad_types(self):
        spec = catalog('baseline', 'injection')[0]['inputSchema']
        for args in ({'query': 3}, {'query': 'refund', 'approved': True}, {}):
            with self.assertRaises(ValueError):
                validate(args, spec)

    def test_policy_does_not_depend_on_document_warning(self):
        self.assertFalse(authorization('send_report', 'hardened')[0])
        self.assertTrue(authorization('read_doc', 'hardened')[0])

    def test_openai_native_state_and_usage(self):
        raw = {'status': 'completed', 'output': [{'type': 'reasoning', 'id': 'opaque'}, {'type': 'function_call', 'call_id': 'c', 'name': 'read_doc', 'arguments': '{"doc_id":"refund-policy"}'}], 'usage': {'input_tokens': 100, 'output_tokens': 10, 'input_tokens_details': {'cached_tokens': 40}}}
        r = OpenAI.parse(raw)
        self.assertEqual(r['usage']['input_tokens'], 100)
        self.assertEqual(r['calls'][0]['arguments']['doc_id'], 'refund-policy')
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test'}):
            p = OpenAI('test')
        h = p.append_reply(p.start('s', 'q'), r)
        self.assertEqual(h['input'][1]['type'], 'reasoning')
        h = p.append_results(h, [{'call_id':'c', 'result': {'ok':True}}])
        self.assertEqual(h['input'][-1]['call_id'], 'c')

    def test_anthropic_state_and_cache_accounting(self):
        raw = {'stop_reason':'tool_use', 'content':[{'type':'thinking', 'thinking':'opaque', 'signature':'sig'}, {'type':'tool_use', 'id':'c', 'name':'read_doc', 'input':{'doc_id':'refund-policy'}}], 'usage': {'input_tokens':10, 'cache_read_input_tokens':20, 'cache_creation_input_tokens':5, 'output_tokens':7}}
        r = Anthropic.parse(raw)
        self.assertEqual(r['usage']['input_tokens'],35)
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY':'test'}):
            p = Anthropic('test')
        h = p.append_reply(p.start('s','q'),r)
        self.assertEqual(h['messages'][-1]['content'][0]['signature'],'sig')
        h = p.append_results(h,[{'call_id':'c','result':{'isError':True}}])
        self.assertTrue(h['messages'][-1]['content'][0]['is_error'])

    def test_truncated_responses_are_incomplete(self):
        self.assertFalse(OpenAI.parse({'status':'incomplete'})['complete'])
        self.assertFalse(Anthropic.parse({'stop_reason':'max_tokens'})['complete'])

    def test_wilson_interval_contains_observed_rate(self):
        low, high = wilson(10,20)
        self.assertLess(low,.5)
        self.assertGreater(high,.5)
        self.assertIsNone(wilson(0,0))

    def test_report_escapes_document_script(self):
        r = asyncio.run(run(Offline(), 'baseline', 'sprawl'))
        r['answer'] = '</script><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'report.html'
            render([r],path)
            text = path.read_text()
            self.assertNotIn('</script><script>alert(1)',text)
            self.assertIn('\\u003c/script',text)

    def test_cost_per_success_includes_failed_spend(self):
        a = asyncio.run(run(Offline(), 'baseline', 'sprawl'))
        b = json.loads(json.dumps(a))
        a['cost_usd_estimate'], b['cost_usd_estimate'] = 2, 3
        b['eval']['task_success'] = False
        s = summarize([a,b])[0]
        self.assertEqual(s['cost_per_success_usd_estimate'],5)
        self.assertIsNone(s['wilson_95'])

if __name__ == '__main__':
    unittest.main()
