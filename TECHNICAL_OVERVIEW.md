# Technical Overview

## System style

This repository is organized as an iteration-based data engineering pipeline for auction-property screening.

Each iteration is a self-contained batch run that typically includes:
- `input/` for source or filtered inputs
- `cleaned_data/` for intermediate and final tabular artifacts
- `scripts/` for deterministic pipeline steps
- `logs/` for run-time diagnostics and validation output
- `output_excel/` for analyst-facing deliverables
- `README.md` for run-specific methodology and limitations

The repo behaves more like a research ETL and scoring workflow than a conventional web app.

## Core pipeline pattern

The pipeline has gradually converged on this shape:

1. **Source ingestion**
   - start from an auction PDF, prior cleaned CSV, or a hand-curated shortlist
   - extract or load rows into a structured base table

2. **Normalization**
   - standardize columns such as parcel ID, property address, city, state, bid cost
   - normalize address strings for later joins and geocoding retries
   - preserve row identity so downstream outputs can always be traced back to the source row

3. **Cross-iteration enrichment**
   - merge prior iteration findings by parcel ID first
   - fall back to exact normalized address matching only when parcel matching fails
   - carry forward fields such as legal description, property type, prior geocodes, prior AI summaries, crime/economic context, and risk notes

4. **Geospatial enrichment**
   - reuse prior coordinates when available
   - otherwise geocode with public sources such as the U.S. Census Geocoder and Nominatim
   - store latitude, longitude, geocode status, confidence, matched display name, ZIP, tract, and block group when available

5. **Area-context enrichment**
   - attach Census ACS-derived economic fields using tract-first and ZIP-fallback geography selection
   - attach best-available crime context from prior iterations or public proxies
   - mark confidence explicitly when data is approximate, area-level, or incomplete

6. **Rule-based scoring**
   - compute interpretable feature scores such as property clarity, geocoding quality, residential likelihood, crime, economics, bid attractiveness, and data confidence
   - combine them with weighted scoring into a reproducible rule score and category

7. **AI review layer**
   - provide the model with only the row-level facts already present in the pipeline output
   - require structured JSON responses
   - validate that the model references concrete fields instead of producing generic investment language
   - fall back to deterministic rule-based output if the model is unavailable or weak

8. **Final ranking and packaging**
   - combine rule score and AI score
   - apply explicit penalties and bonuses for red flags or stronger confidence
   - sort into analyst-ready priority tiers
   - export Excel workbooks for the full ranked list, top targets, drive-by list, and watchlist

9. **Validation**
   - verify row counts, enum integrity, workbook readability, parcel coverage, and git hygiene
   - fail the run if required deliverables are missing or inconsistent

## Data model philosophy

The pipeline is intentionally conservative.

Key principles:
- do not invent missing property facts
- keep `Unknown` values explicit instead of silently imputing them
- prefer tractable deterministic joins over fuzzy guessing
- preserve all candidate rows unless the iteration explicitly filters them out
- store confidence fields next to enriched values so downstream ranking can penalize uncertainty

This makes the outputs more honest and easier to audit.

## Geocoding design

Geocoding is not treated as a binary success/fail step.

The pipeline stores multiple layers of geospatial confidence:
- geocode status
- geocode source
- geocode confidence
- matched display name
- confirmed ZIP code
- tract and block group when available

This matters because auction lists often contain abbreviated, inconsistent, or incomplete addresses. A cheap property with weak address fidelity should not rank the same as a property with strong parcel and geocode confidence.

## Economic enrichment design

Economic data is attached as area-level screening context, not parcel valuation proof.

Typical economic sources and fields:
- Census ACS 5-year style data
- median household income
- poverty rate
- unemployment rate
- median home value
- median gross rent
- vacancy rate
- owner-occupied rate

The pipeline generally prefers:
1. tract-level joins
2. ZIP-level fallback

Confidence is lowered when only broader geographies are available.

## Crime enrichment design

Crime enrichment is handled conservatively because reliable parcel-radius incident automation is often difficult or inconsistent across public endpoints.

So the repo uses a hierarchy like:
1. prior iteration crime context if it is already present and traceable
2. reachable public or area-level sources
3. city-level proxy context when no parcel-radius source is available
4. `Unknown` if no usable source exists

This is why crime outputs include both:
- a risk level or score
- a confidence field and caveat notes

## Rule-based scoring architecture

The rule-based layer is the core deterministic ranking engine.

Its job is to convert mixed-quality property, location, and area-context signals into an interpretable score.

Feature examples used across later iterations include:
- property clarity
- address/geocode confidence
- residential or improved likelihood
- crime risk
- economic strength
- bid price attractiveness
- prior shortlist strength
- data confidence

This approach keeps the ranking explainable even when the AI layer is unavailable.

## AI integration design

The AI layer is deliberately constrained.

### What the model gets

The model is prompted with structured row-level data only, including:
- source-list context
- parcel ID and property address
- bid cost
- legal description and property type if available
- geocoding status and confidence
- crime context
- economic context
- prior iteration signals
- rule-based scores and reasoning

### What the model is not allowed to do

The prompts explicitly prohibit inventing:
- ARV
- rehab cost
- rent
- property condition
- title status
- liens
- code violations
- parcel-specific crime facts that do not exist in the row
- development claims without source support

### Output contract

The model must return machine-parseable JSON with fields like:
- AI score
- AI tier
- recommendation
- reasoning summary
- key risks
- missing information
- next due-diligence step
- confidence level

### Guardrails

The pipeline validates whether the model output references concrete facts such as:
- the bid cost
- the parcel ID or property address
- the crime signal
- at least one economic field or explicit economic uncertainty
- confidence or missing-data context

If the response is too generic or invalid, the pipeline retries once or falls back to deterministic rule-based output.

## Why the repo uses both rule-based logic and AI

The rule-based layer provides:
- reproducibility
- auditability
- stable fallback behavior
- explicit scoring mechanics

The AI layer provides:
- better synthesis across mixed signals
- clearer analyst-facing reasoning summaries
- more usable next-step recommendations

The combined design tries to get the best of both:
- deterministic structure
- flexible but constrained narrative review

## Iteration 12 as the current reference implementation

Iteration 12 is a good snapshot of the current architecture because it shows:
- locked custom input creation
- prior-iteration enrichment
- conservative geocoding
- Census-based economic enrichment
- low-confidence-aware crime context
- weighted rule ranking
- structured AI review with fallback
- final Excel packaging and validation

See:
- `iterations/iteration_12_custom_33_property_ranking/README.md`
- `iterations/iteration_12_custom_33_property_ranking/scripts/`

## Operational limitations

This pipeline is still a research workflow, not a production-grade real estate underwriting platform.

Technical limitations include:
- dependence on public geocoding and public area-context endpoints
- inconsistent availability of parcel-radius crime data
- auction-list address ambiguity
- reliance on CSV/Excel artifacts rather than a formal database
- no centralized orchestration framework yet
- no persistent metadata catalog across all iterations

Even so, the repo already functions as a reproducible analyst-support pipeline with clear intermediate artifacts and validation checkpoints.
