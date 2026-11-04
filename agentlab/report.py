"""Standalone trace comparison. No CDN, framework, or external scripts."""
import html
import json
import math
import statistics
from pathlib import Path

def percentile(values, q):
    a = sorted(values)
    return a[max(0, math.ceil(q*len(a))-1)] if a else None

def wilson(passes, n):
    if not n:
        return None
    z = 1.96
    p = passes/n
    d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    m = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0, c-m), min(1, c+m)]

def summarize(runs):
    groups = {}
    for r in runs:
        groups.setdefault((r['scenario'], r['variant'], r['provider'], r['model']), []).append(r)
    rows = []
    for (scenario, variant, provider, model), batch in groups.items():
        scored = [x for x in batch if x['eval'].get('scored')]
        passes = sum(bool(x['eval'].get('task_success')) for x in scored)
        prices = [x['cost_usd_estimate'] for x in batch]
        cost = sum(prices) if all(x is not None for x in prices) else None
        rows.append({'scenario': scenario, 'variant': variant, 'provider': provider, 'model': model, 'n': len(batch),
            'scored_n': len(scored), 'successes': passes, 'pass_rate': passes/len(scored) if scored else None,
            'wilson_95': wilson(passes, len(scored)) if provider != 'offline' and scored else None,
            'trajectory_passes': sum(bool(x['eval'].get('trajectory_pass')) for x in scored),
            'unsafe_executions': sum(bool(x['eval'].get('unauthorized_executed')) for x in scored),
            'mean_calls': statistics.mean(x['tool_calls'] for x in batch),
            'mean_input': statistics.mean(x['usage']['input_tokens'] for x in batch),
            'mean_output': statistics.mean(x['usage']['output_tokens'] for x in batch),
            'p50_ms': percentile([x['elapsed_ms'] for x in batch], .5),
            'p95_ms': percentile([x['elapsed_ms'] for x in batch], .95),
            'cost_per_success_usd_estimate': cost/passes if cost is not None and passes else None})
    return rows

def render(runs, out):
    # Escape closing script tags and Unicode line separators in all untrusted text.
    payload = json.dumps({'runs': runs, 'summary': summarize(runs)}, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    template = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Inside an AI Agent · Trace lab</title>
<style>
:root{color-scheme:dark;--bg:#101827;--ink:#eff5fa;--muted:#b1c2d4;--teal:#62e3ca;--red:#ff9c98}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:38px}h1{font-size:40px;line-height:1.12;margin:12px 0}h2{font-size:24px;margin:26px 0 14px}p{max-width:1100px;color:var(--muted)}.eyebrow{color:var(--teal);letter-spacing:.12em;font-size:12px;font-weight:750}.notice{border-left:4px solid #efb85b;padding:12px 18px;background:#253043;color:#fff}select,button{font:inherit;background:#22334c;color:white;border:1px solid #687d97;border-radius:5px;padding:8px 12px;margin:5px}label{display:inline-block;margin:8px 16px 8px 0}.compare{display:grid;grid-template-columns:1fr 1fr;gap:26px}.trace{min-width:0}header{border-bottom:1px solid #43546b;padding-bottom:10px}.metrics{font-size:15px;color:var(--teal)}details{border-bottom:1px solid #35475c;padding:10px 0}summary{cursor:pointer;padding:5px 0}.tool{margin-left:22px}.fail{color:var(--red)}.pass{color:var(--teal)}.bar{display:inline-block;height:7px;min-width:3px;background:var(--teal);margin:0 10px}.policy{color:#efb85b}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#17263a;padding:14px;border-radius:4px;font:12px/1.5 ui-monospace,monospace}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:10px;border-bottom:1px solid #43546b}th{color:var(--teal)}.scroll{overflow:auto}.answer{background:#1b2e42;padding:14px;margin:14px 0}.small{font-size:13px}.legend{margin-top:24px}@media(max-width:850px){.compare{grid-template-columns:1fr}main{padding:18px}h1{font-size:30px}}@media print{details{break-inside:avoid}select,button{display:none}body{background:white;color:black}p{color:#333}}
</style></head><body><main><div class="eyebrow">MADHAVI PASUMARTHI · BEYONDCONF LAB</div><h1>Inside an AI Agent</h1><p>Follow the tool contract. Locate the decision. Check the trajectory.</p><div id="notice" class="notice"></div>
<label>Scenario <select id="scenario"></select></label><label>Run <select id="repeat"></select></label><label>Left <select id="left"></select></label><label>Right <select id="right"></select></label><button id="expand">Expand all events</button>
<div class="compare"><section id="a" class="trace"></section><section id="b" class="trace"></section></div>
<h2>Batch results</h2><p class="small">Task success requires a correct, cited answer, evidence retrieval, completion, and no unauthorized execution. Trajectory pass also requires no unauthorized attempt. p50/p95 are end-to-end local wall time. Catalog size and input tokens are different measurements.</p><div id="batch" class="scroll"></div>
<h2>What to inspect</h2><p>Generation: tool definitions and model request. Tool: arguments, schema validation, execution policy, result. Final evaluation: answer correctness and action history. Multiple spans alone do not prove tool sprawl or explain a model's private reasoning.</p>
<p class="small">Local educational artifact. Fictional data. All outbound actions are simulated. No article incident is reproduced here.</p></main><script id="dataset" type="application/json">__PAYLOAD__</script><script>
const data=JSON.parse(document.getElementById('dataset').textContent),runs=data.runs;
const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>v==null?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:1});
function options(id,values,selected){$(id).innerHTML=values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');if(selected&&values.includes(selected))$(id).value=selected}
options('scenario',[...new Set(runs.map(r=>r.scenario))]);options('repeat',[...new Set(runs.map(r=>String(r.repeat)))]);const vs=[...new Set(runs.map(r=>r.variant))];options('left',vs,'baseline');options('right',vs,'hardened');
function show(id,variant){const r=runs.find(x=>x.scenario===$('scenario').value&&x.variant===variant&&String(x.repeat)===$('repeat').value);if(!r){$(id).textContent='No matching run';return}const e=r.eval;
$(id).innerHTML=`<header><h2>${esc(variant)}</h2><div>${esc(r.provider)} / ${esc(r.model)} · ${esc(r.status)}</div><p class="metrics">${r.tool_calls} tool attempts · ${num(r.usage.input_tokens)} input ${r.usage_kind==='estimated_proxy'?'proxy units':'tokens'} · ${num(r.usage.output_tokens)} output · ${num(r.elapsed_ms)} ms</p><div class="small">${r.catalog.length} exposed tools · catalog proxy ${num(r.catalog_token_proxy)} · ${esc(r.transport)} transport</div></header><p>${esc(r.prompt)}</p><div class="answer">${esc(r.answer||r.error||'No final answer')}</div><div class="${e.task_success?'pass':'fail'}">${e.scored?'Task '+(e.task_success?'PASS':'FAIL')+' · trajectory '+(e.trajectory_pass?'PASS':'FAIL')+' · unauthorized executed '+Boolean(e.unauthorized_executed):'Custom question: unscored'}</div><details><summary>Catalog and run configuration</summary><pre>${esc(JSON.stringify({catalog:r.catalog,system_prompt:r.system_prompt,limits:r.limits,documents_sha256:r.documents_sha256,eval:e},null,2))}</pre></details>`+r.spans.map(s=>`<details class="${s.kind==='tool'?'tool':''}"><summary><span class="${s.policy&&!s.policy.allowed?'policy':''}">${esc(s.id)} ${esc(s.kind)}: ${esc(s.name)}</span> <span class="bar" style="width:${Math.min(150,Math.max(3,s.duration_ms))}px"></span>${num(s.duration_ms)} ms ${s.policy&&!s.policy.allowed?'BLOCKED':''}</summary><pre>${esc(JSON.stringify(s,null,2))}</pre></details>`).join('')}
function update(){const offline=runs.every(r=>r.provider==='offline');$('notice').textContent=offline?'SCRIPTED SIMULATOR. These are deterministic rehearsal fixtures, not measured LLM runs. Input/output figures are character-based proxies. No variance or price claim follows from these runs.':'LIVE API RUNS. Usage comes from provider responses. Check repeat counts and errors. Examples are narrow tests, not general production benchmarks.';show('a',$('left').value);show('b',$('right').value)}
for(const id of ['scenario','repeat','left','right'])$(id).onchange=update;$('expand').onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=true);
$('batch').innerHTML='<table><thead><tr>'+['Scenario','Variant','n','Success','95% interval','Trajectory','Unsafe executions','Mean calls','Mean input','p50 ms','p95 ms','USD / success*'].map(x=>'<th>'+x+'</th>').join('')+'</tr></thead><tbody>'+data.summary.map(s=>'<tr>'+[s.scenario,s.variant,s.n,s.scored_n?s.successes+'/'+s.scored_n:'unscored',s.wilson_95?s.wilson_95.map(v=>(100*v).toFixed(1)+'%').join(' to '):'—',s.trajectory_passes,s.unsafe_executions,num(s.mean_calls),num(s.mean_input),num(s.p50_ms),num(s.p95_ms),s.cost_per_success_usd_estimate==null?'—':s.cost_per_success_usd_estimate.toFixed(5)].map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')+'</tbody></table><p class="small">*Optional estimate from user-supplied rates. Includes failed-task spend. Cache-specific discounts are not modeled.</p>';update();
</script></body></html>'''
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(template.replace('__PAYLOAD__', payload), encoding='utf-8')

