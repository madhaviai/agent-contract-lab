# Chatbot: trace → policy fix → trace

A second demo, `python -m agentlab.reasoning`, shows harness regressions (effort, dropped thinking, prompt version) in a local Langfuse-shaped trace with no model keys. See [REASONING.md](REASONING.md).

## What this proves
A correct final answer can hide an unauthorized action. A retrieved vendor note contains an instruction to send fictional internal information. The baseline executes a simulated `send_report`; the policy-only variant rejects the same request at the execution boundary. The prompt, tool definitions, document and scripted model choices remain the same. Only the execution allowlist changes.

This is an analogous failure mechanism, not a reproduction of a proprietary incident. Nothing is actually emailed. All content is fictional.

## Run in two minutes
Requires Python 3.10+; run from the repository root:

```bash
python -m agentlab.chatbot
```

Open http://127.0.0.1:8765. Click **Compare both**. Expand the spans or open each full trace. The offline model is explicitly a scripted rehearsal, not evidence that a real model will follow an injection.

## Stage walkthrough (4–5 minutes)
1. Ask: “If both answers are correct, are both runs safe?”
2. Run before the fix. Show `read_doc` returning the vendor note. Highlight the instruction-like text inside retrieved data.
3. Show the next model generation requesting `send_report`. This is the attempted trust-boundary crossing: document text became an action request.
4. Show the tool span: schema-valid arguments, permissive policy, simulated action executed. Correct answer; failed safe-task evaluation.
5. Ask the audience where they would enforce the fix.
6. Show `authorization()` in `agentlab/core.py`: this read-only task allows only `search_docs` and `read_doc`. The allowlist must be derived from trusted task policy, not model output.
7. Run with the fix. Show the same attempted tool call returning `POLICY_DENIED`; no action executed. The answer remains correct.
8. Explain that trajectory_pass still fails: the model attempted an unwanted action. Execution safety improves, but this does not cure prompt injection or prove universal safety.

The model requests a call; the harness validates and authorizes it; the backend executes it. That is the control point this demo teaches.

## Send the spans to Langfuse
Create a Langfuse project and supply its keys in your shell. The app does not automatically load `.env.example`.

```bash
python -m pip install -r requirements-langfuse.txt
export LANGFUSE_PUBLIC_KEY='your-project-public-key'
export LANGFUSE_SECRET_KEY='your-project-secret-key'
export LANGFUSE_BASE_URL='https://cloud.langfuse.com'
python -m agentlab.chatbot --langfuse
```

Use your region or self-hosted Langfuse URL. Click Compare both, then follow the Langfuse links or search by the displayed trace IDs. Observe the agent root, model generation spans, tool spans, policy output and Boolean evaluations. Offline token counts are proxy metadata, never reported as billable model usage. SDK submission is not a guarantee that a remote dashboard received a trace; inspect tracing_warnings if export fails.

## Use a real model

```bash
export OPENAI_API_KEY='your-key'
python -m agentlab.chatbot --provider openai --model gpt-4.1-mini --langfuse
```

Or use `--provider anthropic --model YOUR_MODEL_ID` with ANTHROPIC_API_KEY. Omit --langfuse for local traces only. Model calls incur your provider's charges. A real model may reject the injected instruction in both variants; use the labeled scripted run as a reliable teaching fallback. Do not claim measured attack success from scripted runs. Repeat real-model trials before reporting rates.

## Optional MCP transport
Install requirements-mcp.txt and add `--transport mcp`. The same policy is also enforced in the MCP server; MCP itself is a connection protocol, not an authorization boundary.

## Scope and verification
This is a local, single-question demo, not a deployed customer support product. The UI accepts arbitrary prompts only with a live model. It binds to loopback, keeps keys server-side and saves per-run JSON and HTML under artifacts/chatbot. Traces contain prompts and tool outputs; use fictional content when exporting. No live model or authenticated Langfuse export was tested without account credentials.

Run tests with `python -m unittest discover -s tests -v`.
