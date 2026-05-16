# Iteration 05 - Strict development matching

This iteration reuses iteration_04 auction and development inputs, but tightens the development matching rules so generic location words like Tulsa, Oklahoma, County, City, North, South, East, and West cannot create false positive development matches.

## What changed

- weak generic overlap terms are explicitly blocked from matching
- prior weak development matches are downgraded and flagged
- `development_match_quality` is added
- `development_match_warning` is added
- rule-based scoring is recalculated under strict match rules
- OpenAI review is rerun using the stricter development context
- strict output workbooks are written with new filenames

## Core rule

The word `Tulsa` by itself is never acceptable as a development match signal.

## Outputs

- `cleaned_data/property_development_matches.csv`
- `cleaned_data/ai_property_reviews.csv`
- `output_excel/investment_ranked_properties_strict.xlsx`
- `output_excel/manual_review_top_candidates_strict.xlsx`
- `output_excel/development_opportunity_properties_strict.xlsx`
