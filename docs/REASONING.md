# Document assistant

## Set up and run

From the project directory, create and activate a virtual environment and install the optional Langfuse SDK:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-langfuse.txt
```

Then run the assistant with Langfuse tracing:

```bash
python -m agentlab.reasoning --langfuse
```

Open http://127.0.0.1:8766. The page is a small document chatbot: choose a model and reasoning effort, ask a question, and read the answer. It does not show traces or debugging details. Each submitted question creates a Langfuse trace named from that question.

To run without Langfuse, omit `--langfuse`; the offline chatbot needs no extra packages or API keys. The app does not load `.env` files automatically. For Langfuse, set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` in the terminal before starting it. `.env.example` is a placeholder reference, not an active configuration file.

The app is an offline scripted fixture, not a live Claude or Grok call. It needs no model API key and does not generate or expose private chain-of-thought. With high effort passed through, the scripted answer includes a short explanation, supporting policy evidence, and a document citation. This is a deterministic demonstration of a useful, evidence-grounded explanation—not raw private reasoning.

## Demonstrate the middleware override

1. Select **Claude Sonnet 4.5** and **High**, then ask a question. The UI sends the question and both selections to the app.
2. Open `agentlab/reasoning.py` and find `apply_request_middleware`. The active assignments determine whether the settings are overridden. To reproduce the issue, comment out the three pass-through assignments and uncomment the three demo-override assignments.
3. Restart the app, select the same settings, and ask the same question. The trace root input keeps the submitted question and selections; the generation immediately before `search_docs` records the effective model, effort, and override flags.
4. To apply the fix, restore the pass-through assignments, restart, and submit the same question. The generation should now show Claude/high and preserved reasoning state; the answer includes a document-grounded explanation, evidence, and citation.

Compare the two traces in Langfuse using their timestamps and question-derived names. No trace viewer or links are added to the chatbot page. The trace stores only state-preservation flags/counts, never reasoning text.

This demonstrates a harness/request-construction override in application middleware. A system prompt cannot reliably set the API request's model or provider-level reasoning-effort field. The fixture illustrates that failure mechanism; it is not a reproduction of Anthropic's reported incident.

## Local Langfuse setup

Install `requirements-langfuse.txt` and configure `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` in the environment. The app sends each run to Langfuse and saves JSON data under `artifacts/reasoning/`. The chat page itself contains no trace viewer or links.
