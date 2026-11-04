## Start the chatbot demo

```bash
python -m agentlab.chatbot
```

Open http://127.0.0.1:8765 and click **Compare both**. No dependencies or keys needed for this scripted rehearsal. See [the stage walkthrough](docs/CHATBOT.md) for Langfuse and live-model setup.

## Start the reasoning-trace demo (no model keys)

```bash
python -m agentlab.reasoning
```

Open http://127.0.0.1:8766 and use the document chatbot. Choose a model and reasoning effort, then ask a question. The chat shows only the conversation; each question creates a Langfuse trace named from the question. The scripted middleware overrides the selected model/effort so you can edit the pass-through lines in `agentlab/reasoning.py` and compare the next trace. See [docs/REASONING.md](docs/REASONING.md).

# Inside an AI Agent

Tools, contracts, and harnesses that shape reliable decisions.

**A runnable conference lab by Madhavi Pasumarthi.** A fictional support bot answers questions from local documents. Two experiments expose tool ambiguity/context overhead and an injected document attempting an unauthorized report. All action tools are simulations. No email, production database, or external action endpoint exists.

## Start in 60 seconds

Python 3.11+ is sufficient for the offline mode. No package installation or API key is needed.

```bash
python -m agentlab demo --out artifacts
python -m agentlab report --input artifacts/runs.json --out artifacts/report.html
python -m unittest discover -s tests -v
```

Open `artifacts/report.html` in a browser. Expand a generation or tool event to inspect its inputs, arguments, policy decision, and result. The report compares the two experiments side by side. `artifacts/runs.json` contains all spans and evaluations.

**Offline mode is a scripted simulator, not recorded model output.** Its choices illustrate a failure mechanism and exercise real validation, tool dispatch, policy, and scoring code. Its token figures are character-based proxies, its timings are local execution times, and repeated simulator runs do not measure model variance. No synthetic dollar costs or live success claims are reported.

## Run a real model

Set a key in your shell using your normal secret-management process. Never commit it. Choose an accessible model explicitly. The adapters use HTTPS via the Python standard library.

```bash
export OPENAI_API_KEY='your-key'
python -m agentlab demo --provider openai --model gpt-4.1-mini --repeats 20 --out artifacts/openai
# Alternatively:
export ANTHROPIC_API_KEY='your-key'
python -m agentlab demo --provider anthropic --model YOUR_MODEL_ID --repeats 20 --out artifacts/claude
```

The OpenAI ID is a documented example, not a recommendation about the newest model. Model access and supported settings vary. No live API calls were made when preparing this package. HTTP adapters have mocked contract tests; confirm a one-run smoke test before a paid batch. Errors remain errors and never silently fall back to the simulator.

`demo` tests baseline, descriptions_only, catalog_only, policy_only, and hardened variants for both scenarios. At 20 repeats this is **200 tasks**, with up to six model turns per task. Start with one repeat. Calls use a 35-second network timeout, an output limit per turn, a turn limit, and a tool-call limit. There is no automatic paid retry. Stop with Ctrl-C; completed runs are checkpointed after each task.

For an arbitrary question:

```bash
python -m agentlab ask --provider openai --model gpt-4.1-mini --prompt 'How many days do I have to request a refund?' --variant hardened --out artifacts/question
python -m agentlab ask --provider openai --model gpt-4.1-mini --docs ./my-text-documents --prompt 'What is the escalation policy?' --out artifacts/custom
```

Only `.md` and `.txt` files are ingested. PDF ingestion and embeddings are outside this small POC. Custom-question evaluation is explicitly unscored. Live mode transmits the selected document contents to the chosen provider when tools retrieve them. Use fictional or approved documents. Reports contain prompts and retrieved text and should be treated accordingly.

## Real MCP transport (optional)

```bash
python -m pip install -r requirements-mcp.txt
python -m agentlab demo --transport mcp --out artifacts/mcp
python -m agentlab.mcp_server
```

`--transport mcp` launches the SDK-based stdio server, performs MCP discovery, and routes calls through `ClientSession.call_tool`. The default `local` transport deliberately bypasses the protocol so the demo works without installation. Provider function calling and MCP JSON-RPC are distinct boundaries. The optional transport targets the **v1 Python SDK and MCP 2025-11-25 generation**; do not describe it as a complete implementation of the newer 2026 protocol. Install and smoke-test that optional dependency before presenting. The server rechecks the policy, even if a client bypasses its local policy.

## The experiments

| Variant | Descriptions | Exposed catalog | Execution policy |
|---|---|---|---|
| baseline | ambiguous | broad | permissive simulation |
| descriptions_only | explicit | broad | permissive simulation |
| catalog_only | ambiguous | scoped for question | permissive simulation |
| policy_only | ambiguous | broad | read-only task allowlist |
| hardened | explicit | scoped for question | read-only task allowlist |

Compare baseline to descriptions_only to study descriptions. Compare baseline to catalog_only to study catalog exposure. Compare baseline to policy_only to study execution policy. Hardened combines fixes and is **not a single-variable causal experiment**. Prompts, documents, model, and limits remain fixed within each comparison. A smaller catalog need not cause fewer executed calls. Twenty repetitions on two fixed prompts are a narrow smoke evaluation, not a production benchmark. Counterbalance order and use representative held-out tasks before making general claims.

## Reading the results

The scorer distinguishes answer correctness, executed unauthorized actions, attempted unauthorized actions, valid arguments, unrelated dataset searches, and useful evidence retrieval. A correct final answer can fail trajectory evaluation. A blocked malicious request means the execution boundary worked, even if the model's trajectory was poor. A regex warning is telemetry, never the authorization mechanism.

Live usage comes from each API response. Cached input is a subset of input where the provider reports it that way. Anthropic cache writes/reads are recorded separately and added to total input. Offline figures use `ceil(serialized_characters / 4)` and are marked `estimated_proxy`. The simulator does not implement provider tokenization or caching. Catalog proxy size is separate from total per-generation input.

Optional `--input-rate` and `--output-rate` are **user-supplied USD per million tokens**, not maintained prices. Cache-specific pricing is unsupported, so priced totals remain estimates. Cost per successful task is total estimated batch cost divided by successful tasks, not the mean price of successful runs alone. Zero successes produce null. The HTML shows per-variant mean, p50/p95 latency, pass rate with Wilson interval, calls, and token totals. Simulator intervals are suppressed.

## Files

* `agentlab/core.py`: catalog, retrieval, validation, authorization, loop, spans, scoring.
* `agentlab/chatbot.py`: policy assistant demo (injection → execution allowlist).
* `agentlab/reasoning.py`: scripted document-Q&A harness trace (model/effort override and dropped reasoning-state marker).
* `agentlab/providers.py`: scripted simulator and live OpenAI/Anthropic adapters.
* `agentlab/mcp_server.py`, `mcp_transport.py`: optional real MCP stdio boundary.
* `agentlab/report.py`: self-contained local trace viewer and batch summaries.
* `docs/TALK.md`: slide-by-slide script, timing, and audience questions.
* `docs/RESEARCH.md`: three documented cases, screenshot links, attribution limits.
* `docs/PRIMITIVES.md`: ownership map, terminology, provider controls, history.
* `docs/DEMO.md`: rehearsal, stage commands, expected fixture traces, troubleshooting.
* `docs/POC.md`: acceptance criteria, architecture, scope, limitations, next steps.
* `tests/`: policy, schema, trajectory, report escaping, provider response, and loop tests.

## License

MIT. Source articles retain their owners' rights. This lab demonstrates analogous mechanisms, not replicas of proprietary systems or reproductions of the reported incidents.
