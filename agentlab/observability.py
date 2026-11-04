"""Optional, live-timed Langfuse observations. No proxy tokens as real usage."""
import os

class LangfuseObserver:
    def __init__(self, client=None, *, include_trace_url=True):
        self._propagate_attributes = None
        if client is None:
            if not all(os.environ.get(k) for k in ('LANGFUSE_PUBLIC_KEY','LANGFUSE_SECRET_KEY')):
                raise ValueError('Langfuse tracing needs LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY')
            try:
                from langfuse import Langfuse, propagate_attributes
            except ImportError:
                raise ValueError('install requirements-langfuse.txt before enabling Langfuse') from None
            client = Langfuse()
            self._propagate_attributes = propagate_attributes
        self.client = client
        self.include_trace_url = include_trace_url
        self.observations = {}
        self.trace = None
        self.ended = set()
        self.attribute_context = None

    def _safe(self, action):
        try:
            return action()
        except Exception as exc:
            # A telemetry failure must not silently change the tested agent policy.
            if self.trace is not None:
                self.trace.setdefault('tracing_warnings', []).append(type(exc).__name__)
            return None

    def start_run(self, trace):
        self.trace = trace
        def action():
            if self._propagate_attributes:
                context = self._propagate_attributes(trace_name=trace['trace_name'])
                context.__enter__()
                self.attribute_context = context
            self.observations[trace['trace_id']] = self.client.start_observation(
                name=trace.get('trace_name', 'policy-chatbot'), as_type='agent',
                trace_context={'trace_id':trace['trace_id']}, input=trace.get('input', {'prompt':trace['prompt']}),
                metadata={'mode':trace['mode'],'usage_kind':trace['usage_kind'],
                          'documents_sha256':trace['documents_sha256'],'simulated_actions':True,
                          **trace.get('metadata', {})})
        self._safe(action)

    def start_span(self, identifier, parent, kind, name, input_data, model=None, metadata=None):
        def action():
            p = self.observations.get(parent)
            context = {'trace_id':self.trace['trace_id']}
            if p is not None:
                context['parent_span_id'] = p.id
            args = {'name':name,'as_type':kind,'trace_context':context,'input':input_data,
                    'metadata':{'mode':self.trace['mode'],'usage_kind':self.trace['usage_kind'],
                                **(metadata or {})}}
            if kind == 'generation':
                args['model'] = model
            self.observations[identifier] = self.client.start_observation(**args)
        self._safe(action)

    def end_span(self, identifier, output, usage=None, warning=False):
        def action():
            obs = self.observations.get(identifier)
            if obs is None:
                return
            args = {'output':output}
            if warning:
                args.update(level='WARNING', status_message='Rejected by execution policy or validation')
            if usage:
                if self.trace['usage_kind'] == 'provider_reported':
                    args['usage_details'] = {'input':usage['input_tokens'],'output':usage['output_tokens']}
                else:
                    args['metadata'] = {'usage_kind':'estimated_proxy','proxy_usage':usage,'mode':'scripted_simulator'}
            obs.update(**args)
            obs.end()
            self.ended.add(identifier)
        self._safe(action)

    def finish_run(self, trace):
        def action():
            for identifier, obs in self.observations.items():
                if identifier in self.ended:
                    continue
                if obs is self.observations.get(trace['trace_id']):
                    obs.update(output={'answer':trace['answer'],'status':trace['status'],'evaluation':trace['eval']})
                obs.end()
                self.ended.add(identifier)
            if trace['eval'].get('scored'):
                names = ('answer_correct','execution_safe','trajectory_pass','task_success',
                         'coding_quality','reasoning_state_intact','effort_matches_configured')
                for name in names:
                    if name not in trace['eval'] or not isinstance(trace['eval'][name], bool):
                        continue
                    self.client.create_score(trace_id=trace['trace_id'],name=name,
                        value=float(trace['eval'][name]),data_type='BOOLEAN',
                        comment='Fictional demo task; all action tools are simulated.')
            self.client.flush()
            return True
        if self._safe(action):
            trace['langfuse_status'] = 'submitted_to_sdk'
            if self.include_trace_url:
                trace['langfuse_trace_url'] = self._safe(
                    lambda: self.client.get_trace_url(trace_id=trace['trace_id'])
                )
        if self.attribute_context is not None:
            context, self.attribute_context = self.attribute_context, None
            self._safe(lambda: context.__exit__(None, None, None))
