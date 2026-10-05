# Outlook Phase 6A — Grounded LLM Intelligence Foundation

## Architecture and boundary

Phase 6A is an isolated backend/CLI prototype. Existing Outlook routes, deterministic ratings, Phase 4C.3/5 services, and the production UI are unchanged.

`verified providers -> deterministic Outlook and event calculations -> OutlookContextPacket -> OutlookIntelligenceProvider -> AIOutlookResponse -> grounding validation -> process cache`

The provider protocol accepts only the normalized packet. `OpenAIOutlookIntelligenceProvider` is the sole vendor adapter and uses the Responses API with Pydantic Structured Outputs. It enables no tools or web search. A deterministic mock exercises the same validation/cache path without paid calls.

## Context packet and provenance

The packet has a normalized ticker, optional issuer, timestamp, bounded facts, explicit upcoming-event references, sources, and inclusion/omission diagnostics. Each fact has a stable existing evidence ID or `event:<event_id>` identity, category, type, plain statement, scalar deterministic values, source IDs, materiality, directionality eligibility and reason, timing, and event identity. Materiality answers whether a fact matters; directionality answers whether deterministic evidence supports a positive, negative, mixed, or informational interpretation. Sources retain name, URL, and publication time. Each upcoming-event reference pairs one opaque event ID with its internal fact ID and safe deterministic title, type, and date.

Facts are deduplicated by ID, then ordered deterministically by materiality, recency, and ID. At most eight facts per category are included. Raw HTML, complete filings, provider objects, user/auth/portfolio/watchlist/preferences state, and arbitrary application state are not accepted. The fingerprint excludes generation time and diagnostics, and includes all meaningful model input.

Deterministic calculations remain outside the model. Existing earnings actual/expected/surprise fields, market measurements, sector/market comparisons, and exposure decisions are copied only when the grounding layer supplies them.

## Output and rating semantics

Schema version `2.2`, owned by TradePilot diagnostics and cache identity rather than echoed by the model, requires an overall rating and summary, all six fixed categories, a controlled rating enum, concise category summaries, at most three key points per category, supporting fact IDs, limitations, and at most five watch selections. The overall object deliberately contains no repeated category-support list; TradePilot derives overall eligibility from the six validated category ratings. A key point contains only interpretive text and opaque supporting fact IDs. A watch selection contains only an opaque supplied event ID and an interpretive reason. The model does not reproduce ticker, schema version, numbers, units, dates, source metadata, event metadata, or watch fact IDs. Ratings are `very_positive`, `mostly_positive`, `mixed`, `mostly_negative`, `very_negative`, or `insufficient_data`. They are qualitative, not probabilities or trade recommendations.

Very/mostly positive and negative represent strongly/net supportive or adverse verified context and require at least one cited fact with compatible deterministic directionality. Mixed means meaningful offsetting factors, material informational context, or unclear direction. Insufficient Data means relevant verified context is inadequate. Substantive ratings require facts; insufficient categories cannot assert key points. Calendar events, filing metadata, and recency alone are informational and cannot justify a directional category rating. Non-material SEC filing metadata is omitted from Company context rather than presented as investment evidence.

## Prompt and safeguards

Prompt version `outlook-analyst-2.4` defines the model as an interpreter rather than a factual transcription layer. It selects material supplied facts, explains investment relevance, synthesizes qualitative ratings, and selects supplied upcoming events. It explicitly separates materiality from directionality and forbids directional ratings based only on an upcoming event, filing existence, activity, or recency. It defines the six TradePilot categories, makes supplied category ownership authoritative, requires category-local evidence, and states that an empty category is preferable to borrowing another category's facts. Company is reserved for material issuer developments outside ordinary earnings and financial-performance analysis; Earnings owns revenue, EPS, margins, comparisons, guidance, reported-period trends, and the next earnings catalyst. The overall summary may discuss any category, including insufficient evidence and upcoming catalysts, while TradePilot derives overall eligibility from validated category ratings. It may not reproduce numbers, dates, calculations, metric formatting, identifiers other than exact opaque selections, provenance, source names, or URLs. Evidence is delimited and explicitly declared untrusted; instruction-like source text cannot override the system instructions.

After schema validation, TradePilot checks every selected fact ID, category ownership, compatibility between directional ratings and deterministic fact directionality, overall rating eligibility derived from all six validated category ratings, unique watch selections, and exact membership in the supplied upcoming-event collection. Positive and negative overall ratings require a compatible substantive category; Mixed requires a substantive Mixed category or conflicting substantive directions; Insufficient Data requires all categories to be insufficient. Numeric values remain in the packet for reasoning and future deterministic rendering but are absent from model output. The prompt prohibits numeric prose; deliberately fragile arbitrary-number extraction is not used as a validator.

## Cache, single-flight, cost, and failures

The process cache key is ticker, provider, model, prompt version, schema version, and context fingerprint. Unchanged context is reused across users; changed facts or contract versions invalidate it. A locked future provides single-flight generation for identical concurrent inputs. Diagnostics include provider/model, prompt/schema versions, fingerprint, fact count, cache state, latency, validation state, failure class, and token usage. Pricing is intentionally not hard-coded because it changes; estimated cost remains unavailable until a maintained pricing table is approved.

LLM disablement, missing keys, unsupported provider configuration, timeouts, malformed output, provider errors, and grounding failures produce explicit unavailable/error behavior in the CLI. Exception messages and secrets are not logged or returned. The deterministic Outlook path continues independently.

## Configuration and CLI

Example-only settings are in `.env.example`; real environment configuration is unchanged. LLM generation defaults off. Context inspection is the default and cannot call OpenAI:

```text
python -m app.cli.inspect_ai_outlook AAPL
python -m app.cli.inspect_ai_outlook AAPL --context-only
python -m app.cli.inspect_ai_outlook AAPL --mock
python -m app.cli.inspect_ai_outlook AAPL --generate
python -m app.cli.inspect_ai_outlook AAPL --mock --resolve-facts
```

`--generate` requires `OUTLOOK_LLM_ENABLED=true`, provider `openai`, and a backend-only API key. JSON output is available with `--json`. `--resolve-facts` resolves selected IDs only against the sanitized local context packet for developer inspection. No key is printed.

## Evaluation and known data gaps

Automated checks cover packet bounding and stability, provenance, hostile source text, schema/rating constraints, unknown and cross-category fact references, exact watch-event selection, absence of factual duplication in model output, mock behavior, missing data, cache invalidation, single-flight, and failure isolation. Existing Outlook evaluation corpora remain relevant to deterministic evidence, reporting identity, provenance, and missing-data behavior; their old aggregate presentation labels are not golden answers for LLM prose.

- Industry currently supports sector versus broad-market return and bounded peer breadth. A robust company-versus-sector return and representative company-versus-peer return are not consistently exposed as first-class deterministic measurements, so the model must not claim them when absent.
- Geopolitical context remains correctly sparse and only enters the packet after the existing explicit exposure gate. Generic world commentary is disallowed; Insufficient Data is valid.
- Earnings actuals and deterministic comparisons are available for supported releases. Consensus, implied move, and beat probability remain absent unless a valid snapshot/model supplies them; actual-only results cannot be called beats or misses.
- Process-local cache/single-flight is suitable for this prototype, not multi-worker coordination. No persisted audit artifact or production route exists.

## Phase 6B recommendation

First run explicit, bounded live CLI evaluation for AAPL, MSFT, NVDA, JPM, and ABTC and review materiality, language, omissions, and grounding. Only after output approval should Phase 6B consider a shared cache/persistence layer and a simple UI contract. Do not replace the production Outlook UI until that evaluation is accepted.
