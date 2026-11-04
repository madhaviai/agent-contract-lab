# The objects inside an agent system

## Vocabulary that survives a framework change

**Task** means the user's desired outcome and its acceptance criteria. **Tool contract** means the interface for a capability: purpose, inputs, outputs, errors, and preconditions. A task can need zero, one, or many tool calls. MCP also has version-dependent task facilities for long-running execution; that protocol object is distinct from the ordinary user task.

**Model** proposes text and tool calls. **Tool** implements a capability. **Agent loop** repeatedly lets the model choose a next step using observations. **Harness** owns execution, state, budgets, and policy. **MCP** standardizes the host/client/server connection and capability exchange. The LLM does not itself open an MCP socket in this lab: the host bridges the model's function-call format to the tool boundary.

Tools and agents have a longer history than modern LLM products. The timelines in this deck are selected API milestones, not the invention of agents or tool use.

## MCP server primitives

| Primitive | Purpose | Example |
|---|---|---|
| Tools | Invocable capabilities with described inputs and results | `search_docs(query)` |
| Resources | Identified context/data that a client can retrieve | a policy document URI |
| Prompts | Reusable interaction templates with arguments | a support-triage template |

MCP also defines discovery, messages, errors, and transport behavior. It is more than a file of tool definitions. The POC implements tools only. Host, client, and server are software roles, not three kinds of models. Check version-specific capabilities rather than treating every SDK generation as the same protocol.

## Ownership map

| Surface | Objects and fields | Who owns enforcement? | Typical failure | First inspection |
|---|---|---|---|---|
| User task | goal, acceptance criteria, allowed actions | application and user workflow | wrong objective | original request and scope |
| Instructions | system/developer text, examples, version | application/harness | conflicting rules | exact prompt and revision |
| Context | messages, documents, tool results, token limits | harness/provider | lost evidence or bloat | per-turn serialized request |
| Memory | stored records, retrieval, provenance, expiry | application storage | stale or cross-user state | tenant scope and record source |
| Model request | model ID, endpoint, output limit, effort, sampling | provider and caller | unsupported or poor setting | request metadata and error |
| Tool catalog | names, descriptions, exposure policy | host and tool author | ambiguous selection | exposed definitions |
| Input contract | types, required keys, enums, units | decoder plus server validator | valid shape, wrong meaning | proposed arguments and validation |
| Output contract | content, structured data, errors, retryability | tool server and harness | false success or huge response | result before it returns to model |
| MCP boundary | host, client, server, transport, discovery | SDK and server | protocol mismatch | negotiated version and messages |
| Execution | identity, allowlist, approval, idempotency | tool server/backend | unauthorized side effect | permission decision before call |
| Loop control | turn limit, call budget, retry rule, timeout | harness | repeated or unbounded work | stop reason and attempt count |
| Routing | selected model/tool set, classifier, fallback | application/harness | wrong route | route and evidence for selection |
| Evaluation | reference facts, trajectory constraints, labels | application/test harness | correct answer hides bad action | complete sequence and outcome |
| Observability | trace ID, parent span, time, usage, version | instrumentation | unlinked or misleading traces | span lineage and missing events |

A trace records observable execution. It cannot establish the model's full private reasoning or prove causality from one run.

## Provider controls: conceptual comparison

| Intent | OpenAI Responses example | Claude Messages example | Design caution |
|---|---|---|---|
| Define tools | `tools`, function `parameters` | `tools`, `input_schema` | provider wire shape differs from MCP |
| Let model choose | `tool_choice: "auto"` | `tool_choice: {"type":"auto"}` | default does not guarantee a call |
| Force a tool | named function choice | named `tool` choice where supported | model/thinking compatibility differs |
| Constrain shape | function `strict` | strict tool use on supported models | shape does not ensure correct meaning |
| Reasoning effort | `reasoning.effort` on supported models | `output_config.effort` on supported models | effort values are not calibrated across vendors |
| Sampling | `temperature`, model dependent | `temperature`, model dependent | omit unless supported and deliberately tested |
| Limit output | `max_output_tokens` | `max_tokens` | exhaustion can truncate useful output |
| Return observations | `function_call_output` and `call_id` | `tool_result` and `tool_use_id` | preserve IDs and native state |
| Cache/context | provider cache and context facilities | provider cache and context facilities | log cache usage and state lifecycle |

The runnable adapters use auto tool choice, explicit output limits, and optional settings. They intentionally do not normalize every feature or guarantee feature parity. Newer models can reject parameters accepted by older ones. An SDK's existence does not imply every setting works on every model. Current source links are in RESEARCH.md.

## Fault-location questions

1. Was the task understood and bounded correctly?
2. Which definitions and prior observations reached the model?
3. Was the tool selection appropriate? Were its arguments structurally and semantically valid?
4. Did the server authorize execution for this identity and task?
5. Did the backend succeed, fail, time out, or leave an uncertain result?
6. Did the harness preserve the right state and stop at the right time?
7. Did the answer satisfy the task? Did the trajectory stay within its authority?

More tools do not necessarily mean more tool calls. More spans can reflect retries, parallel work, richer instrumentation, or a genuinely necessary workflow. Diagnose using the request and trajectory, then test a hypothesis.
