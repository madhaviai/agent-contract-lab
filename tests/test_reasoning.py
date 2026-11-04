import json
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from agentlab.observability import LangfuseObserver
from agentlab.reasoning import (
    DemoServer,
    QUESTION,
    SELECTED_MODEL,
    default_trace_name,
    run_document_question,
)
from tests.test_chatbot import Client


class ReasoningTraceTests(unittest.TestCase):
    def test_selected_settings_are_overridden_before_search(self):
        degraded = {
            'effective_model': 'grok-3',
            'effective_effort': 'low',
            'drop_prior_reasoning': True,
        }
        with patch('agentlab.reasoning.apply_request_middleware', return_value=degraded):
            trace = run_document_question(QUESTION, SELECTED_MODEL, 'high')
        generations = [span for span in trace['spans'] if span['kind'] == 'generation']
        search_index = next(i for i, span in enumerate(trace['spans']) if span['name'] == 'search_docs')

        self.assertLess(trace['spans'].index(generations[0]), search_index)
        self.assertEqual(trace['input']['question'], QUESTION)
        self.assertEqual(trace['input']['selected_model'], SELECTED_MODEL)
        self.assertEqual(trace['input']['requested_reasoning_effort'], 'high')
        self.assertIn(SELECTED_MODEL, trace['input']['context'])
        self.assertEqual(generations[0]['model'], 'grok-3')
        self.assertEqual(generations[0]['metadata']['effective_reasoning_effort'], 'low')
        self.assertTrue(generations[0]['metadata']['model_overridden'])
        self.assertTrue(generations[0]['metadata']['reasoning_effort_overridden'])
        self.assertEqual(generations[1]['metadata']['prior_reasoning_state_count'], 0)
        self.assertTrue(generations[1]['metadata']['dropped_prior_reasoning_state'])
        self.assertIn('30 days', trace['answer'])
        self.assertIn('refund-policy', trace['answer'])

    def test_passthrough_middleware_preserves_selected_settings_and_state(self):
        passthrough = {
            'effective_model': SELECTED_MODEL,
            'effective_effort': 'high',
            'drop_prior_reasoning': False,
        }
        with patch('agentlab.reasoning.apply_request_middleware', return_value=passthrough):
            trace = run_document_question(QUESTION, SELECTED_MODEL, 'high')
        generations = [span for span in trace['spans'] if span['kind'] == 'generation']

        self.assertEqual(generations[0]['model'], SELECTED_MODEL)
        self.assertFalse(generations[0]['metadata']['model_overridden'])
        self.assertEqual(generations[0]['metadata']['effective_reasoning_effort'], 'high')
        self.assertFalse(generations[0]['metadata']['reasoning_effort_overridden'])
        self.assertEqual(generations[1]['metadata']['prior_reasoning_state_count'], 1)
        self.assertFalse(any(g['metadata']['dropped_prior_reasoning_state'] for g in generations))
        self.assertIn('Why:', trace['answer'])
        self.assertIn('Evidence:', trace['answer'])
        self.assertIn('Source: refund-policy.', trace['answer'])
        degraded = {
            'effective_model': 'grok-3',
            'effective_effort': 'low',
            'drop_prior_reasoning': True,
        }
        with patch('agentlab.reasoning.apply_request_middleware', return_value=degraded):
            brief_answer = run_document_question(QUESTION, SELECTED_MODEL, 'high')['answer']
        self.assertGreater(len(trace['answer']), len(brief_answer))

    def test_question_and_langfuse_observations(self):
        question = 'Which document describes escalation?'
        trace = run_document_question(
            question,
            selected_model='grok-3',
            requested_effort='low',
            trace_name='support-escalation',
        )

        self.assertEqual(trace['prompt'], question)
        self.assertEqual(trace['trace_name'], 'support-escalation')
        self.assertEqual(trace['langfuse']['name'], 'support-escalation')
        self.assertEqual(trace['langfuse']['input']['question'], question)
        self.assertEqual(trace['langfuse']['input']['selected_model'], 'grok-3')
        generation = next(o for o in trace['langfuse']['observations'] if o['type'] == 'GENERATION')
        self.assertEqual(generation['model'], 'grok-3')
        self.assertEqual(generation['metadata']['selected_model'], 'grok-3')
        self.assertEqual(generation['metadata']['effective_reasoning_effort'], 'low')

    def test_high_effort_escalation_answer_explains_evidence(self):
        with patch(
            'agentlab.reasoning.apply_request_middleware',
            side_effect=lambda model, effort: {
                'effective_model': model,
                'effective_effort': effort,
                'drop_prior_reasoning': False,
            },
        ):
            trace = run_document_question(
                'How do I escalate a billing dispute?',
                selected_model=SELECTED_MODEL,
                requested_effort='high',
            )

        self.assertIn('human support specialist', trace['answer'])
        self.assertIn('Why:', trace['answer'])
        self.assertIn('Evidence:', trace['answer'])
        self.assertIn('Source: escalation.', trace['answer'])

    def test_trace_name_defaults_to_question_slug(self):
        question = 'How do I escalate a billing dispute?'
        trace = run_document_question(question)
        self.assertEqual(trace['trace_name'], default_trace_name(question))

    def test_invalid_model_and_effort_are_rejected(self):
        with self.assertRaises(ValueError):
            run_document_question(selected_model='unknown-model')
        with self.assertRaises(ValueError):
            run_document_question(requested_effort='maximum')

    def test_observer_records_generation_model_and_context(self):
        client = Client()
        with patch(
            'agentlab.reasoning.apply_request_middleware',
            side_effect=lambda model, effort: {
                'effective_model': model,
                'effective_effort': effort,
                'drop_prior_reasoning': False,
            },
        ):
            trace = run_document_question(observer=LangfuseObserver(client))

        self.assertTrue(all(observation.ends == 1 for observation in client.obs))
        root = next(o for o in client.obs if o.args['name'] == trace['trace_name'])
        self.assertEqual(root.args['input']['selected_model'], SELECTED_MODEL)
        self.assertEqual(root.args['metadata']['selected_model'], SELECTED_MODEL)
        generation = next(o for o in client.obs if o.args['name'] == 'model turn 1')
        self.assertEqual(generation.args['model'], SELECTED_MODEL)
        self.assertEqual(generation.args['metadata']['selected_model'], SELECTED_MODEL)
        self.assertEqual(generation.args['metadata']['effective_reasoning_effort'], 'high')
        self.assertTrue(trace['eval']['reasoning_effort_matches_requested'])


class ReasoningHttpTests(unittest.TestCase):
    def test_document_chat_posts_selected_settings_and_creates_traces(self):
        with tempfile.TemporaryDirectory() as folder:
            server = DemoServer(('127.0.0.1', 0), folder)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'

            def post(question=QUESTION, selected_model=SELECTED_MODEL, effort='high', extra=None):
                payload = {
                    'question': question,
                    'selected_model': selected_model,
                    'requested_reasoning_effort': effort,
                }
                payload.update(extra or {})
                request = Request(
                    base + '/api/run',
                    data=json.dumps(payload).encode(),
                    headers={'Content-Type': 'application/json', 'X-Demo-Token': server.token},
                )
                return json.load(urlopen(request))

            try:
                page = urlopen(base).read()
                self.assertIn(b'Welcome!', page)
                self.assertIn(b'Document Assistant', page)
                self.assertIn(b'Reasoning effort', page)
                self.assertNotIn(b'Open trace', page)
                self.assertNotIn(b'Trace:', page)
                self.assertNotIn(b'harness', page.lower())
                with patch(
                    'agentlab.reasoning.apply_request_middleware',
                    return_value={
                        'effective_model': SELECTED_MODEL,
                        'effective_effort': 'high',
                        'drop_prior_reasoning': False,
                    },
                ):
                    first = post('How many days for refund?')
                    second = post('How do I escalate a billing dispute?', effort='low')
                self.assertEqual(first['harness']['selected_model'], SELECTED_MODEL)
                self.assertEqual(first['harness']['effective_model'], SELECTED_MODEL)
                self.assertEqual(first['harness']['requested_reasoning_effort'], 'high')
                self.assertEqual(first['harness']['effective_reasoning_effort'], 'high')
                self.assertEqual(first['trace_name'], default_trace_name('How many days for refund?'))
                self.assertEqual(second['trace_name'], default_trace_name('How do I escalate a billing dispute?'))
                self.assertNotEqual(first['trace_id'], second['trace_id'])
                self.assertIn('30 days', first['answer'])
                self.assertIn('Why:', first['answer'])
                self.assertIn('Evidence:', first['answer'])
                self.assertIn('Source: refund-policy.', first['answer'])
                self.assertIn('human support specialist', second['answer'])
                self.assertEqual(first['langfuse']['name'], first['trace_name'])
                with self.assertRaises(HTTPError) as error:
                    post(extra={'unexpected': True})
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
                with self.assertRaises(HTTPError) as error:
                    post(question='')
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
                with self.assertRaises(HTTPError) as error:
                    post(selected_model='invalid')
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main()
