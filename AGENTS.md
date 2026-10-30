# Repository instructions

This is `ahhout/methylseq_AH`, an nf-core/methylseq fork. Preserve upstream
pipeline files, licence and documentation. The integration baseline is release
4.2.0 (`5aa56467a85a5e2d6795ea72dfa5a5f0c9babc23`) plus fork master
`b6aa88ef5399cb2992f12d8072e2c8fedf39d003`, whose four later commits affect only
GitHub workflows and nf-core metadata. Do not upgrade this baseline implicitly.

## Flamingo production

- Read `docs/flamingo.md`, `references/README.md` and `environment.yml` before
  changing the setup. Install no dependencies without need; update the existing
  environment definition for approved additions. Do not create or reference
  virtualenv/venv or `.venv` environments.
- `run_methylseq_integrated.sh` is the supported Flamingo launcher;
  `config/params.emseq.integrated.yml` owns scientific params,
  `config/nextflow.config` owns cluster/runtime settings, and
  `samplesheets/samplesheet.csv` is the canonical input.
- Source lives at `/home/a_houtman/methylseq_AH`. Runtime state lives at
  `/home/a_houtman/em_seq`; keep its existing session, shared work/output roots,
  lock and history unchanged. The original project's launcher owns historical
  remote-origin resumes. Do not rewrite historical manifests or bypass guards.
- Full pipelines run only with `sbatch`. Small checks requiring at most 16 GB
  RAM and 8 CPUs run directly; request resources only above those bounds.
- Use Conda `nextflow` and module `containers/apptainer/1.3.6`. The launcher's
  executable must be the module-provided Apptainer 1.3.6, despite the unchanged
  Conda environment's historical Apptainer entry.
- Require a clean committed source checkout at launch. Keep it unchanged for
  execution/resume. Use separate checkouts for concurrent development.

## Scientific and data safeguards

- Production remains Bismark with `em_seq: true`, exact wgbstools hg38 plus
  lambda/pUC19, and the imported clipping/extraction/deduplication/QC policy.
- Confirm before changing genome/reference, aligner/library mode, samplesheet
  structure or identifiers, sample merging, trimming, extraction, deduplication,
  filtering, target restrictions, GPU/Parabricks, TAPS/PBAT/RRBS, or production
  work/output directories. Explicit authorization in the current conversation
  satisfies that requirement for its stated scope; do not ask again.
- `docs/flamingo_bwamem3_milestone.md` describes a separate design/approval
  milestone. It authorizes no BWA-MEM3 implementation or production change.
- Confirm before deleting or overwriting data. Do not delete individual files
  from resumable Nextflow task directories. Do not duplicate large FASTQ/BAM/PAT
  or reference payloads where authoritative paths/symlinks suffice.
- Stream large inputs and preserve headers/coordinate conventions. Clinical
  metadata, credentials, containers, caches and generated outputs stay out of Git.
  The two imported real samplesheets were explicitly approved for unchanged
  publication; that approval does not cover unrelated metadata.

## Scripts, provenance and documentation

- Bash launchers/helpers use `set -euo pipefail`, quote variables and fail early
  with meaningful missing-path/command errors. Never inject shell prologues into
  nf-core internals, generated `.command.sh` files or process definitions.
- Python helpers expose `argparse` CLIs. Cache helper calls require explicit
  `--runtime-root`; source configuration and runtime metadata are separate.
- New run-level results and figure/export bundles start with
  `YYYY-MM-DD_HH-MM-<analysis>-<cohort-or-purpose>-vN` in UTC. Validate calendar
  date and 24-hour time before creating outputs. Methylseq uses the stricter
  name in `docs/flamingo.md`. Preserve historical names/timestamps and exact
  old/new path maps when explicitly authorized to rename.
- Record actual `started_utc` and successful `completed_utc` in run provenance.
  Distinguish naming/submission time. Retain original timestamps on resume and
  append attempt records. Do not infer latest runs from mtime.
- Document scientific questions, terms, thresholds, rationale and sources in
  plain language. Separate published methods from project adaptations. Give
  runnable input/output examples and exact validation limits. Document pipeline
  identity, params, config, samplesheet, output and `-resume` for every run.
- Let the built-in `-profile test` provide its own inputs/params when used.
  No full production rerun is required for this integration.

## Git and reviews

- Before significant docs/reorganization or moving/deleting any files under
  `/home/a_houtman`, checkpoint the reviewed tracked state locally. A clean
  verified HEAD is sufficient; otherwise review ignore rules and staged paths,
  commit reviewed changes and verify success before dependent changes.
- Check representative payload rules with `git check-ignore`. Keep code,
  configuration, environment definitions and small provenance manifests tracked;
  never force-add payloads or nested software. Git checkpoints protect only
  tracked files and do not replace deletion/overwrite approval.
- Keep checkpoints local unless publication is authorized. The reconciliation
  authorizes publishing only `integration/flamingo-emseq`; leave master and the
  default branch unchanged. Use concise imperative commit subjects.
- Review staged diffs and all new reachable commits before publication. PRs
  explain the problem/change, files, exact validation commands, reproducibility
  effects and limitations. Do not claim unperformed tests or biological validation.
