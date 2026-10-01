"""
YCSB-cpp analysis layer: one merged time+memory series per run, on BenchGrid.

The module mirrors the insert_only_v2 layout so both workloads read the same
way — :mod:`.paths` (where the data is), :mod:`.enrich` (what a YCSB run *is*),
:mod:`.dataset` (the ``Dataset`` and its metric registry), :mod:`.adapter`
(declarations), :mod:`.curves` / :mod:`.tabs` (views), :mod:`.app` (the streamlit
shell) and :mod:`.cli` (headless questions).  Nothing here is imported by the
benchmark runner, which stays on the plan/pool side of BenchGrid.
"""
