# Spec delta: classifier-hybrid

## REMOVED Requirements

### Requirement: Hybrid classifier with regex first
**Replaced** by the new `llm-first-response` capability
(see `openspec/changes/llm-first-con-auto-mejora/specs/llm-first-response/spec.md`).

The previous model was "regex first, LLM as fallback". The
business decided to invert this: **LLM is always invoked
first**, and the regex is kept as a cheap pre-filter to bypass
the LLM when the match has very high confidence.

The new behavior is defined in `llm-first-response` and the
spec is removed from `classifier-hybrid`. Tenants that want
to keep the old behavior can opt into `mode = "regex_first"`
in their `llm_strategy` configuration.

### Requirement: Caching of classifications

**Replaced** by the bypass mechanism in `llm-first-response`:
when the regex match is clear (score > `bypass_threshold`), the
LLM is skipped entirely (not just the classification). The
intent remains in cache via the standard `recent_turns`
mechanism.

## UNCHANGED Requirements

### Requirement: Anti-injection three-layer protection
**Preserved.** All three layers (pre-filter regex, system
prompt rules, post-response validation) still apply. The
change only adds a new validation layer in `llm-first-response`
that checks the LLM's structured JSON response for prompt leaks.
