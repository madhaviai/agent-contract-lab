"""Scripted document-Q&A trace for inspecting harness setting overrides."""
import argparse
import asyncio
import hashlib
import json
import re
import secrets
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .core import ToolBackend, documents

PAGE = Path(__file__).with_name('reasoning.html')
QUESTION = 'What is the refund window for a paid subscription?'
SELECTED_MODEL = 'claude-sonnet-4-5'
MODEL_OPTIONS = ('claude-sonnet-4-5', 'grok-3')
EFFORT_OPTIONS = ('low', 'high')


def default_trace_name(question):
    slug = re.sub(r'[^a-z0-9]+', '-', question.lower()).strip('-')
    return ('document-qa-' + (slug[:72].rstrip('-') or 'question'))


def _span(trace, identifier, parent, kind, name, **fields):
    span = {
        'id': identifier,
        'parent_id': parent,
        'kind': kind,
        'name': name,
        **fields,
    }
    trace['spans'].append(span)
    return span


def _start_observation(observer, span, input_data, model=None):
    if observer:
        observer.start_span(
            span['id'],
            span['parent_id'],
            span['kind'],
            span['name'],
            input_data,
            model,
            metadata=span.get('metadata'),
        )


def apply_request_middleware(selected_model, requested_effort):
    # Demo bug: middleware replaces the model and effort after the UI selection.
    effective_model = 'grok-3'
    effective_effort = 'low'
    drop_prior_reasoning = True
    # Fix: comment out the three assignments above and uncomment these instead.
    effective_model = selected_model
    effective_effort = requested_effort
    drop_prior_reasoning = False
    return {
        'effective_model': effective_model,
        'effective_effort': effective_effort,
        'drop_prior_reasoning': drop_prior_reasoning,
    }


def run_document_question(
    question=QUESTION,
    selected_model=SELECTED_MODEL,
    requested_effort='high',
    observer=None,
    trace_name=None,
):
    if selected_model not in MODEL_OPTIONS:
        raise ValueError(f'model must be one of {", ".join(MODEL_OPTIONS)}')
    if requested_effort not in EFFORT_OPTIONS:
        raise ValueError(f'reasoning effort must be one of {", ".join(EFFORT_OPTIONS)}')
    middleware = apply_request_middleware(selected_model, requested_effort)
    effective_model = middleware['effective_model']
    effective_effort = middleware['effective_effort']
    drop_prior_reasoning = middleware['drop_prior_reasoning']
    trace_name = (trace_name or default_trace_name(question)).strip()
    if not trace_name or len(trace_name) > 120 or any(ord(char) < 32 for char in trace_name):
        raise ValueError('trace name must contain 1 to 120 printable characters')
    docs = documents()
    trace_id = uuid.uuid4().hex
    content_hash = hashlib.sha256(
        json.dumps(docs, sort_keys=True).encode()
    ).hexdigest()
    trace = {
        'trace_id': trace_id,
        'trace_name': trace_name,
        'started_at': datetime.now(timezone.utc).isoformat(),
        'provider': 'offline fixture',
        'model': effective_model,
        'mode': 'scripted_simulator',
        'usage_kind': 'scripted_fixture',
        'prompt': question,
        'context': (
            f'The user selected model {selected_model} and requested '
            f'{requested_effort} reasoning effort.'
        ),
        'input': {
            'question': question,
            'context': (
                f'The user selected model {selected_model} and requested '
                f'{requested_effort} reasoning effort.'
            ),
            'selected_model': selected_model,
            'requested_reasoning_effort': requested_effort,
        },
        'status': 'running',
        'documents_sha256': content_hash,
        'harness': {
            'selected_model': selected_model,
            'requested_reasoning_effort': requested_effort,
            'effective_model': effective_model,
            'effective_reasoning_effort': effective_effort,
            'model_overridden': effective_model != selected_model,
            'reasoning_effort_overridden': effective_effort != requested_effort,
            'inference_layer': 'unaffected',
            'reasoning_retention': 'drop_prior_thinking' if drop_prior_reasoning else 'preserve_prior_thinking',
        },
        'spans': [],
        'answer': '',
    }
    if observer:
        trace['metadata'] = {
            **trace['harness'],
            'simulated': True,
            'documents_sha256': content_hash,
        }
        observer.start_run(trace)

    backend = ToolBackend(docs)
    retained_reasoning_state = 0
    search_result = None
    document_result = None
    search_query = question
    if 'refund' in question.lower():
        search_query = question + ' approved subscription policy purchase'
    for turn, tool_name in enumerate(('search_docs', 'read_doc', None), start=1):
        generation_id = f'g{turn}'
        prior_state_count = retained_reasoning_state
        dropped_prior_state = bool(drop_prior_reasoning and turn > 1 and prior_state_count == 0)
        metadata = {
            'selected_model': selected_model,
            'requested_reasoning_effort': requested_effort,
            'effective_model': effective_model,
            'model_overridden': effective_model != selected_model,
            'effective_reasoning_effort': effective_effort,
            'reasoning_effort_overridden': effective_effort != requested_effort,
            'prior_reasoning_state_count': prior_state_count,
            'dropped_prior_reasoning_state': dropped_prior_state,
            'inference_layer': 'unaffected',
            'simulated': True,
        }
        calls = []
        if tool_name == 'search_docs':
            calls = [{'name': tool_name, 'arguments': {'query': search_query}}]
        elif tool_name == 'read_doc':
            doc_id = search_result['documents'][0]['doc_id']
            calls = [{'name': tool_name, 'arguments': {'doc_id': doc_id}}]

        generation = _span(
            trace,
            generation_id,
            trace_id,
            'generation',
            f'model turn {turn}',
            model=effective_model,
            input={
                'question': question,
                'context': trace['context'],
                'selected_model': selected_model,
                'requested_reasoning_effort': requested_effort,
                'effective_model': effective_model,
                'effective_reasoning_effort': effective_effort,
                'tool_results_available': turn > 1,
            },
            output={'tool_calls': calls, 'status': 'tool_use' if calls else 'completed'},
            metadata=metadata,
        )
        _start_observation(
            observer,
            generation,
            generation['input'],
            model=effective_model,
        )
        if observer:
            observer.end_span(generation_id, generation['output'])

        if not calls:
            trace['answer'] = _answer_from_document(
                document_result['doc_id'],
                document_result['text'],
                effective_effort,
            )
            break

        call = calls[0]
        if tool_name == 'search_docs':
            result = asyncio.run(backend.call(tool_name, call['arguments']))
            search_result = result
        else:
            result = asyncio.run(backend.call(tool_name, call['arguments']))
            document_result = result

        tool_id = f't{turn}'
        tool_span = _span(
            trace,
            tool_id,
            generation_id,
            'tool',
            tool_name,
            arguments=call['arguments'],
            result=result,
            executed=True,
            metadata={'simulated': True},
        )
        _start_observation(observer, tool_span, tool_span['arguments'])
        if observer:
            observer.end_span(tool_id, {'result': result, 'executed': True})

        retained_reasoning_state = 0 if drop_prior_reasoning else 1

    trace['status'] = 'completed'
    trace['eval'] = {
        'scored': False,
        'reasoning_state_intact': not drop_prior_reasoning,
        'reasoning_effort_matches_requested': not trace['harness']['reasoning_effort_overridden'],
        'selected_model_preserved': not trace['harness']['model_overridden'],
    }
    trace['langfuse'] = to_langfuse_shape(trace)
    if observer:
        observer.finish_run(trace)
    return trace


def _answer_from_document(doc_id, text, reasoning_effort):
    body = ' '.join(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.startswith('#') and not line.startswith('Document ID:')
    )
    sentences = re.split(r'(?<=[.!?])\s+', body)
    if doc_id == 'refund-policy':
        policy = next((sentence for sentence in sentences if 'refund within' in sentence.lower()), None)
        verification = next((sentence for sentence in sentences if 'verifies the purchase date' in sentence.lower()), None)
        if not policy:
            return 'I could not find the refund window in the document.'
        if reasoning_effort == 'low':
            return f'{policy} Source: refund-policy.'
        details = f' {verification}' if verification else ''
        return (
            f'{policy}\n\n'
            f'Why: The policy sets a 30-day request window and requires support to verify '
            f'the purchase date before approving a refund. Meeting the time window does '
            f'not by itself mean a refund has been approved.\n\n'
            f'Evidence: {policy}{details}\n\n'
            'Source: refund-policy.'
        )
    if doc_id == 'escalation':
        policy = next((sentence for sentence in sentences if 'escalate billing disputes' in sentence.lower()), None)
        if not policy:
            return 'I could not find the escalation guidance in the document.'
        if reasoning_effort == 'high':
            return (
                f'{policy}\n\n'
                'Why: The document assigns billing disputes to a human support specialist, '
                'so the appropriate next step is escalation rather than promising a resolution here.\n\n'
                f'Evidence: {policy}\n\n'
                'Source: escalation.'
            )
        return (
            f'{policy} Source: escalation.'
        )
    return 'I could not find a relevant approved policy document.'


def to_langfuse_shape(trace):
    observations = []
    for span in trace['spans']:
        observations.append({
            'id': span['id'],
            'traceId': trace['trace_id'],
            'parentObservationId': span.get('parent_id'),
            'type': 'GENERATION' if span['kind'] == 'generation' else 'SPAN',
            'name': span['name'],
            'model': span.get('model'),
            'input': span.get('input') or span.get('arguments'),
            'output': span.get('output') or span.get('result'),
            'metadata': span.get('metadata', {}),
        })
    return {
        'id': trace['trace_id'],
        'name': trace['trace_name'],
        'timestamp': trace['started_at'],
        'input': trace['input'],
        'output': {'answer': trace['answer'], 'status': trace['status']},
        'metadata': {
            **trace['harness'],
            'simulated': True,
            'documents_sha256': trace['documents_sha256'],
        },
        'observations': observations,
        'scores': [],
    }


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, output, langfuse=False):
        super().__init__(address, DemoHandler)
        self.output, self.langfuse = Path(output), langfuse
        self.output.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.allowed_hosts = {f'127.0.0.1:{self.server_port}', f'localhost:{self.server_port}'}


class DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, content_type='application/json'):
        content = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(content)

    def valid_host(self):
        return self.headers.get('Host') in self.server.allowed_hosts

    def do_GET(self):
        if not self.valid_host():
            return self.send(403, '{"error":"invalid host"}')
        path = urlsplit(self.path).path
        if path == '/':
            config = {'csrf': self.server.token}
            data = json.dumps(config).replace('<', '\\u003c')
            return self.send(200, PAGE.read_text(encoding='utf-8').replace('__CONFIG__', data), 'text/html')
        return self.send(404, '{"error":"not found"}')

    def do_POST(self):
        if not self.valid_host():
            return self.send(403, '{"error":"invalid host"}')
        origin = self.headers.get('Origin')
        if origin and origin not in {'http://' + host for host in self.server.allowed_hosts}:
            return self.send(403, '{"error":"invalid origin"}')
        if not secrets.compare_digest(self.headers.get('X-Demo-Token', ''), self.server.token):
            return self.send(403, '{"error":"invalid token"}')
        if self.path != '/api/run':
            return self.send(404, '{"error":"not found"}')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16_384:
                raise ValueError('request too large or empty')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict) or set(data) != {
                'question', 'selected_model', 'requested_reasoning_effort'
            }:
                raise ValueError('invalid request')
            question = data.get('question', QUESTION)
            if not isinstance(question, str) or not 1 <= len(question.strip()) <= 400:
                raise ValueError('question must contain 1 to 400 characters')
            selected_model = data.get('selected_model')
            requested_effort = data.get('requested_reasoning_effort')
            if selected_model not in MODEL_OPTIONS or requested_effort not in EFFORT_OPTIONS:
                raise ValueError('model or reasoning effort is invalid')
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.send(400, '{"error":"question must contain 1 to 400 characters"}')
        if not self.server.lock.acquire(blocking=False):
            return self.send(409, '{"error":"a run is already in progress"}')
        try:
            observer = None
            if self.server.langfuse:
                from .observability import LangfuseObserver
                observer = LangfuseObserver(include_trace_url=False)
            trace = run_document_question(
                question.strip(),
                selected_model=selected_model,
                requested_effort=requested_effort,
                observer=observer,
            )
            key = trace['trace_id']
            (self.server.output / (key + '.json')).write_text(json.dumps(trace, indent=2), encoding='utf-8')
            (self.server.output / (key + '.langfuse.json')).write_text(
                json.dumps(trace['langfuse'], indent=2), encoding='utf-8')
            return self.send(200, json.dumps(trace))
        except Exception as exc:
            print(f'Reasoning demo run failed: {type(exc).__name__}', flush=True)
            return self.send(500, json.dumps({'error': f'run failed: {type(exc).__name__}'}))
        finally:
            self.server.lock.release()
def main():
    parser = argparse.ArgumentParser(description='Document Q&A harness regression trace demo')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--out', default='artifacts/reasoning')
    parser.add_argument('--langfuse', action='store_true', help='Send traces to the configured Langfuse instance')
    args = parser.parse_args()
    if args.langfuse:
        from .observability import LangfuseObserver
        LangfuseObserver()
    server = DemoServer(('127.0.0.1', args.port), args.out, args.langfuse)
    print(f'Open http://127.0.0.1:{server.server_port} · scripted document Q&A · no model API keys', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
