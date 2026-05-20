# OpenClaw Context Repository

This repository stores iterative Tulsa auction analysis experiments and supporting files.

## Iteration history

| Iteration | Folder | Purpose | Status |
|---|---|---|---|
| Iteration 03 | `iterations/iteration_03_openai_ai_review/` | Corrected pipeline with OpenAI review and validation | Archived baseline |
| Iteration 04 | `iterations/iteration_04_development_intelligence_ai_review/` | Corrected spreadsheet with OpenAI review and Tulsa development intelligence | Historical |
| Iteration 05 | `iterations/iteration_05_strict_development_matching/` | Strict development matching pass that removed weak generic location matches | Historical |
| Iteration 06 | `iterations/iteration_06_final_robust_ai_due_diligence/` | Final robust spreadsheet with strict development verification, geocoding checks, and OpenAI review | Final |
| Iteration 08 | `iterations/iteration_08_1500_to_2000_top50/` | Top 50 properties in the $1,500-$2,000 bid range with AI review | Historical |
| Iteration 10 | `iterations/iteration_10_900_to_1000_top50_crime_economic_ai/` | Top 50 $900-$1,000 properties with crime and economic area intelligence baked into AI ranking | Current |

## Repository layout

- `auction_lists/` keeps the source auction PDF
- `iterations/` stores self-contained runs
- `iterations/iteration_03_openai_ai_review/` stores the prior OpenAI-backed baseline
- `iterations/iteration_04_development_intelligence_ai_review/` stores the development-intelligence pass
- `iterations/iteration_05_strict_development_matching/` stores the strict text-matching pass
- `iterations/iteration_06_final_robust_ai_due_diligence/` stores the final conservative screening pipeline with geocoding and AI review

## Due diligence warning

This tool is a screening system only. It does not verify title, liens, code violations, zoning, flood zone, property condition, occupancy, structure quality, ARV, rehab cost, rentability, legal ownership, or whether the parcel is practically usable. Crime and economic data are area-level screening signals, not guarantees. Before bidding, manually verify through Tulsa County Assessor, Tulsa County Treasurer, title/lien research, code violation checks, zoning records, Google Street View, drive-by inspection, and nearby sold comps.
