# Runtime adapter contract

The engine does not know what runs a candidate. It knows this interface, and
every runtime — Venice, a headless Claude Code CLI, Hermes, whatever comes
next — implements it. The skills are the Medical Affairs knowledge; the
harness is replaceable (§39).

```python
class Adapter(Protocol):
    name: str

    def estimate(self, genome: Genome, environment: Environment,
                 budget: Budget) -> CostEstimate:
        """Token and dollar estimate. Fetches live model prices; never
        reads a hardcoded price table. Called before every experiment and
        shown to the operator, who must confirm before anything executes."""

    def run(self, genome: Genome, environment: Environment,
            budget: Budget, seed: int) -> Phenotype:
        """Execute one candidate against one environment, once.

        Must abort and return a partial Phenotype marked `budget_exceeded`
        rather than silently overrun any limit in `budget`.

        Evidence retrieval goes through the environment's fixture store,
        not the network, unless the environment is in `live` mode."""
```

`Phenotype` is the full observable behaviour (§6), not just the brief:
artifacts, complete transcript, every tool call with its arguments and
result, token usage, wall-clock time, and any budget breach. The engine
evaluates the behaviour; the document is only the most visible part of it.

## Implementations

| Adapter | Status | Purpose |
|---|---|---|
| `mock` | first to build | Replays recorded phenotypes. Makes the entire engine testable in CI for $0 — every bug that is not "the model said something surprising" is caught before a run is paid for. |
| `venice` | primary | Metered, dollar-quotable, multi-model. Executor `z-ai-glm-5-3`, judge `gemini-3-8-flash`. Implements a real agentic loop via function calling against the fixture-backed evidence tools. |
| `claude_cli` | second | Headless `claude -p`. The actual deployment target, so a champion must be re-validated here before promotion. Cost is denominated in usage limits rather than dollars when run on a subscription — the preflight says so instead of quoting a false number. |
| `hermes` | stub | Documented, unimplemented. Nothing in the engine depends on it (§39). |

## Why the judge is a different family from the executor

`z-ai-glm-5-3` executes; `gemini-3-8-flash` judges. A model scoring its own
output inflates its scores, and the effect is largest exactly where the
margins are smallest. The pairing is recorded in every manifest so that
judge agreement can be measured later, and re-measured when either model
changes.

## Privacy note

`gemini-3-8-flash` is listed by Venice as *Anonymized*, not *Private*. That
is acceptable for synthetic workshop data, which is all this repository
contains. It is not automatically acceptable for a company Twin holding real
interaction notes (§38) — that deployment needs a Private-tier judge, and the
manifest records the privacy tier of every model used so the question can be
answered after the fact rather than assumed.
