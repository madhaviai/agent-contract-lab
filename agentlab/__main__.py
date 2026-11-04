import argparse
import asyncio
import json
import random
from pathlib import Path
from .core import SCENARIOS, VARIANTS, run
from .providers import Offline, OpenAI, Anthropic
from .report import render, summarize

def parser():
    p = argparse.ArgumentParser(description='Inside an AI Agent: trace and contract lab')
    sub = p.add_subparsers(dest='command', required=True)
    for command in ('demo', 'ask'):
        q = sub.add_parser(command)
        q.add_argument('--provider', choices=['offline', 'openai', 'anthropic'], default='offline')
        q.add_argument('--model')
        q.add_argument('--out', type=Path, default=Path('artifacts'))
        q.add_argument('--transport', choices=['local', 'mcp'], default='local')
        q.add_argument('--docs')
        q.add_argument('--max-turns', type=int, default=6)
        q.add_argument('--max-calls', type=int, default=8)
        q.add_argument('--max-output', type=int, default=900)
        q.add_argument('--temperature', type=float)
        q.add_argument('--effort', help='Provider-specific setting. Omitted by default. Check selected model compatibility.')
        q.add_argument('--input-rate', type=float, help='User-supplied USD per million input tokens')
        q.add_argument('--output-rate', type=float, help='User-supplied USD per million output tokens')
        if command == 'demo':
            q.add_argument('--repeats', type=int, default=1)
            q.add_argument('--variants', nargs='+', choices=VARIANTS, default=list(VARIANTS))
            q.add_argument('--scenarios', nargs='+', choices=list(SCENARIOS), default=list(SCENARIOS))
        else:
            q.add_argument('--prompt', required=True)
            q.add_argument('--variant', choices=VARIANTS, default='hardened')
    q = sub.add_parser('report')
    q.add_argument('--input', type=Path, required=True)
    q.add_argument('--out', type=Path, required=True)
    return p

async def main(args):
    if args.command == 'report':
        render(json.loads(args.input.read_text()), args.out)
        print(f'Report: {args.out.resolve()}')
        return
    if args.provider != 'offline' and not args.model:
        raise ValueError('--model is required for live providers')
    if args.command == 'ask' and args.provider == 'offline':
        raise ValueError('arbitrary questions require --provider openai or anthropic; offline mode only illustrates scripted scenarios')
    if min(args.max_turns, args.max_calls, args.max_output) < 1:
        raise ValueError('limits must be positive')
    if args.command == 'demo' and not 1 <= args.repeats <= 100:
        raise ValueError('--repeats must be between 1 and 100')
    if (args.input_rate is None) != (args.output_rate is None):
        raise ValueError('supply both input and output rates, or neither')
    if args.input_rate is not None and min(args.input_rate, args.output_rate) < 0:
        raise ValueError('rates cannot be negative')
    provider = Offline() if args.provider == 'offline' else {'openai': OpenAI, 'anthropic': Anthropic}[args.provider](args.model, args.max_output, args.temperature, args.effort)
    args.out.mkdir(parents=True, exist_ok=True)
    runs = []
    if args.command == 'demo':
        jobs = [(s, v, i) for i in range(args.repeats) for s in args.scenarios for v in args.variants]
        random.Random(42).shuffle(jobs)  # Counterbalance temporal provider/load effects.
    else:
        jobs = [('custom', args.variant, 0)]
    for scenario, variant, repeat in jobs:
        trace = await run(provider, variant, scenario, prompt=getattr(args, 'prompt', None), docs_dir=args.docs,
            transport=args.transport, repeat=repeat, max_turns=args.max_turns, max_calls=args.max_calls, input_rate=args.input_rate, output_rate=args.output_rate)
        runs.append(trace)
        (args.out/'runs.json').write_text(json.dumps(runs, indent=2), encoding='utf-8')
        print(f'{scenario:10} {variant:18} repeat={repeat+1} {trace["status"]:20} calls={trace["tool_calls"]} mode={trace["mode"]}')
    (args.out/'summary.json').write_text(json.dumps(summarize(runs), indent=2), encoding='utf-8')
    render(runs, args.out/'report.html')
    print(f'Open {(args.out/"report.html").resolve()}')
    if any(x['status'] == 'error' for x in runs):
        raise RuntimeError('one or more tasks failed; inspect runs.json. No simulator fallback was used.')

if __name__ == '__main__':
    try:
        asyncio.run(main(parser().parse_args()))
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc))
