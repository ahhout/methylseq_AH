# Pipeline repository instructions

This is the staged development checkout of `ahhout/methylseq_AH`. Preserve the
upstream pipeline, licence, documentation, release tags, and ancestry. The
baseline is nf-core/methylseq 4.2.0, release commit
`5aa56467a85a5e2d6795ea72dfa5a5f0c9babc23`, plus fork master
`b6aa88ef5399cb2992f12d8072e2c8fedf39d003` (four metadata/CI commits). Do not
implicitly upgrade this baseline or implement BWA-MEM3.

CIRCALL-specific settings and launchers belong to
`/home/a_houtman/analysis/CIRCALL_methylomics`. Read that project's `AGENTS.md`,
`environment.yml`, `references/README.md`, and `docs/methylseq_execution.md`
before changing its execution setup. Read `docs/flamingo.md` here for ownership.
The project pins this checkout's full commit. Both checkouts must remain clean
and unchanged throughout execution and resume; develop elsewhere while a run
uses a revision. Historical checkouts at `/home/a_houtman/methylseq_AH` and
`/home/a_houtman/em_seq` retain their original launchers and runtime state.

Full pipelines require Slurm submission. Small checks using no more than 16 GB
memory and 8 CPUs can run directly. Use the installed Conda `nextflow`
environment and module `containers/apptainer/1.3.6`, not Conda's Apptainer 1.5.0.
Do not create virtualenvs, install unnecessary dependencies, or mutate caches.

Do not change genome/reference, aligner/library mode, sample identifiers,
merging, trimming, methylation extraction, deduplication, filtering, or
GPU/TAPS/PBAT/RRBS/targeted sequencing modes without explicit authorization.
Production remains Bismark with `em_seq: true` and exact wgbstools hg38 plus
lambda and pUC19. Never delete or overwrite data without authorization. Keep
one existing shared work cache; do not edit individual resumable task files.

Bash helpers use `set -euo pipefail`; never inject shell prologues into upstream
processes or generated task commands. Python helpers expose argparse CLIs.
Preserve explicit UTC run/attempt timestamps and provenance. New run/figure
bundles use `YYYY-MM-DD_HH-MM-<analysis>-<purpose>-vN` and exclusive reservation;
completed bundles remain immutable through supported launchers.

Before significant reorganization or moving/deleting home files, record a clean
HEAD or checkpoint reviewed tracked changes locally. Verify staged paths and
ignore rules. Keep payloads, nested downloaded software, credentials, runtime
state and generated outputs out of Git. Preserve untracked/ignored exceptions
separately. Do not push unless requested. Keep concise imperative commit titles.
