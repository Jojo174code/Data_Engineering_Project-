# Repo Cleanup Notes

This file explains the current shape of the repository and how to make it cleaner without losing research history.

## Current reality

This repo contains both:
- iteration-based deliverables that are useful to keep
- older root-level files and scripts that make the repo look less polished to new visitors

Some unrelated tracked file deletions and modifications already existed in git history/worktree before the latest iteration 12 work. Because of that, cleanup should be done deliberately, not with a blind mass delete.

## Recommended cleanup approach

### 1. Keep the iteration model

The `iterations/` layout is the clearest part of the repo.
Keep using it as the main structure for research runs.

### 2. Move or retire root-level loose artifacts in a dedicated pass

Candidates for future cleanup review:
- `2026 auction.pdf`
- `final_manual_review_top_candidates_final(Final Manual).csv`
- `final_manual_review_top_candidates_final.pdf`
- `run_ai.sh`
- `run_assessor.sh`
- `run_map.sh`
- `run_rest.sh`
- `tmp_inspect_900_1000.py`

These files are not necessarily bad, but they make the repo feel like an active scratchpad rather than a polished research project.

A cleaner long-term structure would be:
- keep source auction files in `auction_lists/`
- keep one-off helpers under `scripts/maintenance/` or archive them
- keep final/manual source artifacts under a dedicated `reference_inputs/` or `archived_inputs/` folder

### 3. Avoid deleting tracked files casually

Because the repo already has unrelated tracked deletions/modifications in the working tree, do cleanup in small reviewed commits.
That makes it easier to preserve research provenance and avoid accidentally dropping something still needed.

### 4. Prefer documentation cleanup first

The fastest way to improve how the repo looks publicly is:
- strong root README
- clear project overview
- consistent iteration READMEs
- an explicit due-diligence warning
- light notes about limits and methodology

That work improves the repo immediately, even before deeper file reorganization.

## Suggested next cleanup pass

A future repo-polish pass could do all of this together:
- create a dedicated `reference_inputs/` folder
- move loose root PDFs/CSVs there
- move one-off shell runners into `scripts/maintenance/`
- archive or delete truly obsolete temporary files
- add a small `docs/` folder for methodology notes if needed

## Important safety note

Do not expose `.env`, `.venv`, or API keys during cleanup.
Keep commit scope narrow and review `git status` before each cleanup commit.
