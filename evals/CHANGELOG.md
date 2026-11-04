# Eval changelog

Each entry: what changed, the numbers, and caveats.
Dataset: evals/dataset.json (47 questions). Scorer: evals/score.py.

---

## 2026-10-30: Original baseline
- Primary model gpt-oss-120b (structured output often failing → fallbacks)

| Metric | Value |
|---|---|
| Errors | 2 / 47 |
| Citation precision | 66.2% |
| Citation recall | 79.4% |
| Strict file accuracy | 64.7% |
| Fact coverage | 62.1% |
| Routing | 93.6% |
| Guardrails | 100% |
| P50 / P95 latency | 6.3 s / 234.3 s |

---

## 2026-10-31: After reliability fixes (NOT a fair comparison)
- Switched primary model to Qwen, fixed planner using the wrong "question"
- **Caveat:** the planner prompt contained instructions tailored to Cartograph's own files
  (overfit to the eval). Those were later removed. Numbers are optimistic.

| Metric | Value |
|---|---|
| Errors | 0 / 47 |
| Citation precision | 76.6% |
| Citation recall | 77.5% |
| Strict file accuracy | 64.7% |
| Fact coverage | 65.2% |
| Routing | 97.9% |
| Guardrails | 100% |
| P50 / P95 latency | 5.6 s / 19.2 s |

---

## 2026-11-04: Stage 1 baseline
### Changes in Stage 1
- 1.3 Send only the last 3 conversation turns; ignore system notes when counting turns
- 1.4 Users receive the redacted answer from output_guard
- 1.5 Removed the dead `check` node
- 1.6 Router-driven clarification (`unclear` → `clarify` node, guarded resume)
- 1.7 Provider failures reported as failures (counted as errors, not 0% answers)
- 1.10 Answers written as plain text + `parse_answer` (no structured-output failures)
- 1.11 `search_code` parameter renamed `text` → `query` (consistent tool interface)
- Model per job: gpt-oss for tool calls, Qwen for answers, gpt-oss-20b for router/judge
- Eval runner: fresh thread per question (previously history leaked between questions)
- Planner prompt: removed Cartograph-specific instructions (general rules only)

### Results
| Metric | Value |
|---|---|
| Errors | 4 / 47 |
| Citation precision | 83.9% |
| Citation recall | 81.8% |
| Strict file accuracy | 68.8% (22/32) |
| Fact coverage | 75.4% (fixed judge; 76.4% with the old judge) |
| Routing | 95.3% (41/43) |
| Guardrails | 88.9% (8/9) |
| P50 / P95 latency | 13.4 s / 58.8 s |

### Caveats
- Run on the **old index** (code snapshot from before Stage 1)
- Judge still contains "be generous" → fact coverage may be optimistic (fix in Stage 3)
- Blocked attack questions are graded on their refusal text (unfair; fix in Stage 3)
- Q6 ("What does the check node do?") is outdated: the check node was removed in 1.5

### Regressions found
- Guardrails 100% → 88.9%: the 1.6 router change ("off_topic only if unrelated to software")
  let "help me write a Python web scraper" through. **Fixed** (off_topic now covers requests
  to write new code unrelated to this repo). Pending re-run.

### Errors and slowdowns
- gpt-oss mixes reasoning into replies (`output_parse_failed`) and invents tools from its
  training (`open_file`, `repo_browser.search`, `print_tree`)
- With `temperature=0`, retries repeat the same failure
- Fallbacks unavailable at times (Gemini 503, OpenRouter daily limit)
- **Applied for next run:** tool model `temperature=0.3`, `reasoning_effort="low"`

---

## Next run (planned)
- Re-index Cartograph (current code)
- Includes: router fix, tool-model tweaks, judge json_schema fix
- Goals: errors ↓, guardrails back to 100%, latency ↓

## 2026-11-04: Stage 2.3, chunk size 1500 → 800 (+ re-index)
Hybrid (agent's default search) Recall@5: 65.1% → 68.6%
Semantic Recall@5: 62.1% → 68.6%   (MiniLM now reads whole chunks)
Keyword Recall@5: 71.1% → 63.0%    (smaller chunks have fewer words)
Cross-file hybrid Recall@5: 31.3% → 42.4%
Also: Python symbols now use the ast parser (tree-sitter crashed on Windows); hybrid returns 8 full chunks.

---

## 2026-11-04: Security attack run

- Attack cases: 8
- Results file: `evals/results_attacks.json`
- Connection-string redaction was added to `src/cartograph/guards.py`.
- A regression test was added to `tests/test_guards.py`.
- The redaction test confirms that PostgreSQL connection strings and their credentials
  are not returned by `redact()`.

### Attack observations

- Direct prompt-injection attempts were refused.
- Requests to reveal environment variables or system prompts were refused.
- Path traversal attempts were not allowed to expose file contents.
- Some secret-related requests were routed as ordinary code questions rather than being
  blocked before model execution.
- These results are not yet a 100% security pass; the full evaluation must be rerun
  after the new system-prompt and redaction changes.

### Caveats

- This attack run was performed before the final secret-protection prompt change was
  fully evaluated.
- The results should be treated as a baseline for the next security run, not as proof
  that all secret-disclosure paths are closed.