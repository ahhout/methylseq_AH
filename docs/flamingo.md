# Flamingo bulk EM-seq

This checkout combines the nf-core/methylseq pipeline with the reviewed
Flamingo setup for bulk enzymatic methylation sequencing (EM-seq). Human reads
and spike-in controls align competitively to the exact wgbstools hg38 sequence
(GRCh38 assembly generation), lambda and pUC19. The controls measure conversion
of unmethylated cytosines and retention of methylated cytosines. Their results
are quality-control summaries, not human methylation measurements.

The production aligner remains Bismark. This integration does not implement
BWA-MEM3 or change biological processing. The original project, downstream
analyses and historical run manifests remain in `/home/a_houtman/em_seq`.

## Source and runtime locations

| Location | Purpose |
| --- | --- |
| `/home/a_houtman/methylseq_AH` | Committed pipeline source, launcher, params, samplesheets and helper scripts |
| `/home/a_houtman/em_seq` | Existing Nextflow execution directory, `.nextflow` cache/history, Slurm logs and result-navigation links |
| `/mnt/beegfs01/scratch/a_houtman/tmp/em_seq/work_emseq_integrated` | One shared work cache; retain task directories for resume |
| `/mnt/beegfs01/scratch/a_houtman/tmp/em_seq/.methylseq-cache-maintenance.lock` | Existing maintenance/launcher lock, held for the whole run |
| `/mnt/beegfs01/scratch/a_houtman/nextflow/nf-core-methylseq/results/bulk` | Existing output root; each analysis uses its own immutable run name |

The shared session is explicitly selected in
[`config/methylseq_cache_session.json`](../config/methylseq_cache_session.json):
`17da6065-5303-40ef-8047-5c8ff69a052d`. The helper reads this checkout's
configuration and the original execution directory's cache/history. A later,
unrelated Nextflow launch cannot silently change session selection. The
maintenance lock also coordinates with the unchanged original launcher.

## Scientific settings

These are retained decisions, not new recommendations. Parameters live in
[`config/params.emseq.integrated.yml`](../config/params.emseq.integrated.yml);
Slurm resources and container runtime settings live in
[`config/nextflow.config`](../config/nextflow.config). Defaults below come from
the pinned pipeline's `nextflow.config` and `conf/modules/` files.

| Rule / effective value | Reason and source |
| --- | --- |
| Pipeline 4.2.0; release commit `5aa56467a85a5e2d6795ea72dfa5a5f0c9babc23` | Original production baseline. Fork master `b6aa88ef5399cb2992f12d8072e2c8fedf39d003` is four commits ahead, changing only GitHub workflows and nf-core metadata. |
| Exact wgbstools hg38 + `phage_lambda` + `plasmid_puc19c`; `igenomes_ignore: true` | Preserve the human sequence/CpG namespace and both control measurements. See [reference provenance](../references/README.md). No iGenomes reference substitution. |
| `aligner: bismark`, `em_seq: true`; directional, end-to-end alignment | Existing production library mode; retained pipeline defaults `non_directional: false`, `local_alignment: false`, `relax_mismatches: false`. |
| Paired-end Bismark `--maxins 1000` | Existing EM-seq pipeline rule when `maxins` is unset; not a new pair filter. |
| Trimming enabled; `skip_trimming_presets: true`; R1/R2 5′ clips 8/3 bp and 3′ clips 3/10 bp | Project adaptation based on the original eight-sample end-bias comparison, as recorded in the imported params comments. Disables hidden chemistry presets while preserving selected clipping. |
| Positional Bismark deduplication enabled (`skip_deduplication: false`, `rrbs: false`) | Retained pipeline defaults; no duplicate policy change. |
| Extractor `--no_overlap --ignore_r2 2 --ignore_3prime_r2 2`; R1 ignores 0/0; `comprehensive: false`, `meth_cutoff: null` | Existing pipeline defaults prevent double counting overlapping mates and retain the current R2 end exclusions. No additional filtering introduced. |
| `cytosine_report: true` | Existing project requirement for genome-wide site-level downstream analysis; no target restriction. |
| `run_qualimap: true`, `run_preseq: false`; FastQC/MultiQC enabled | Existing project QC choice; retain mapping/coverage summaries and skip unused complexity extrapolation. |
| Lambda methylation ≤0.5%; pUC19 methylation ≥95%; otherwise `WARN`; no observations → `NO_DATA` | Existing project reporting heuristics in `summarize_emseq_controls.py`, not newly validated biological acceptance thresholds. Weighted percentages use summed methylated/unmethylated counts. |
| TAPS/PBAT/RRBS, GPU and targeted sequencing disabled; no sample merges or identifier changes | Preserve the production workflow and reviewed samplesheet structure. |

The canonical sheet contains four samples; the historical
`samplesheets/samplesheet.2026-08-31-8samples.csv` contains eight. Both are
published byte-for-byte with the user's explicit authorization, including
pseudonymous identifiers and absolute FASTQ paths. Their four columns contain
no accompanying clinical metadata. Publication does not establish anonymity.
The historical sheet is retained as provenance; it is not automatically selected.

## Submit and resume

Log in with `ssh a_houtman@flamingo`. The existing Conda environment is
`nextflow`. Its unchanged [`environment.yml`](../environment.yml) records
Nextflow 25.10.2 and additional historical dependencies; this integration
installs nothing. The launcher activates that environment, then loads
`containers/apptainer/1.3.6` and checks the executable reports version 1.3.6.
The Conda Apptainer 1.5.0 entry must not supply the production executable.

Commit reviewed source changes before submission. The launcher requires a
clean checkout, including no nonignored untracked source files. **Keep this
checkout at the same commit and unchanged for the entire execution and any
resume.** A queued job also checks that its Slurm-spooled launcher matches
the current source; resubmit if the launcher changed while queued. Use another checkout for concurrent development. Do not change
scientific parameters to get past a resume guard.

For a new fork-origin analysis, create and retain the UTC name once:

```bash
cd /home/a_houtman/methylseq_AH
RUN_NAME="$(date -u +%F_%H-%M)-emseq-integrated-heh-4new-trim-8-3-3-10-v1"
printf '%s\n' "$RUN_NAME"  # retain this exact submission name
sbatch --export=ALL,RUN_NAME="$RUN_NAME",RESUME_EXISTING=false \
  /home/a_houtman/methylseq_AH/run_methylseq_integrated.sh
```

The expected inputs are the existing nonempty FASTQs in the canonical sheet
and the external reference/index exposed by the repository symlink. Results
go to the existing bulk root above, under the exact `RUN_NAME`. After both
methylseq and control QC succeed, `em_seq/outputs/$RUN_NAME` links there.
Control summaries are in `control_qc/control_qc.tsv`; pipeline reports,
resolved params and execution logs are under `pipeline_info/`.

To resume that same fork-origin run, reuse the saved name and the same commit:

```bash
cd /home/a_houtman/methylseq_AH
# RUN_NAME must still be the exact name retained from the submission above.
: "${RUN_NAME:?Set RUN_NAME to the saved submission name}"
sbatch --export=ALL,RUN_NAME="$RUN_NAME",RESUME_EXISTING=true \
  /home/a_houtman/methylseq_AH/run_methylseq_integrated.sh
```

The effective command is recorded exactly as shell-escaped argv. Its form is:

```text
nextflow -log <output>/pipeline_info/nextflow_<job>.log run /home/a_houtman/methylseq_AH -config /home/a_houtman/methylseq_AH/config/nextflow.config -params-file /home/a_houtman/methylseq_AH/config/params.emseq.integrated.yml -work-dir /mnt/beegfs01/scratch/a_houtman/tmp/em_seq/work_emseq_integrated -profile apptainer --outdir <output> -resume 17da6065-5303-40ef-8047-5c8ff69a052d
```

Nextflow runs with working directory `/home/a_houtman/em_seq`. The pipeline
source is the absolute checkout path; no remote pipeline download or `-r`
selection occurs. Reusing a session/work directory does **not** guarantee cache
reuse after moving pipeline source; Nextflow still determines task identities.

Older remote-origin runs use the original launcher, their original names and
their existing snapshot requirements:

```bash
cd /home/a_houtman/em_seq
: "${RUN_NAME:?Set RUN_NAME to the exact historical run name}"
sbatch --export=ALL,RUN_NAME="$RUN_NAME",RESUME_EXISTING=true \
  /home/a_houtman/em_seq/run_methylseq_integrated.sh
```

Do not adopt an old output through the fork launcher. Original runs lacking
required submission snapshots still fail the original launcher's gate; this
integration neither reconstructs nor edits their manifests. Both launchers
share the same lock, so they must run sequentially. Full pipeline executions
always use `sbatch`.

## Output and result folder names

New run-level outputs use
`YYYY-MM-DD_HH-MM-emseq-integrated-<cohort-or-purpose>-vN` in UTC, with a real
calendar date and 24-hour time. Invalid names fail before output creation.
Run names reflect submission/naming time; actual execution starts when Slurm
runs the script. These are recorded separately. Retain the original name and
`started_utc` on resume, and append attempt timestamps. Never derive a latest
result from filesystem modification time. Historical date-only names remain
with the original project; do not invent missing historical times.

Every downstream analysis or figure/export bundle must follow the general
`YYYY-MM-DD_HH-MM-<analysis>-<cohort-or-purpose>-vN` contract and record explicit
UTC start/completion times. Collection roots, reference directories and
internal sections are not run names.

## Submission evidence and bounded checks

`pipeline_info/submitted/` retains the original launcher/config/params/sheet/
reference-manifest snapshots, `SHA256SUMS`, immutable `run_manifest.tsv`,
`cache-session.json` and `pipeline-identity.json`. Identity records the fork
commit, both upstream baselines, absolute source/runtime roots, support-script
checksums and any runtime-directory `nextflow.config` checksum. Resume checks
the original snapshots, current scientific inputs and pipeline identity.
Each numeric Slurm job gets a separate `attempts/<job>/` launcher, exact command,
input checksums, identity and `started_utc`. All recorded exits receive
`ended_utc` and exit status; success also receives `completed_utc`. Failed or
interrupted attempts explicitly have incomplete task membership. SIGKILL or
node loss may prevent the exit handler from running; a remaining `started`
record is incomplete evidence. External reference payloads and site-wide
configuration are not frozen by Git.

The import inventory and adaptations are in
[`flamingo_import_manifest.json`](flamingo_import_manifest.json). Exact bounded
checks and their limits are in [`flamingo_validation.md`](flamingo_validation.md).
No production sample was rerun for this integration. Full pipeline execution
and cache-reuse efficiency remain untested. The separate
[`feature/bwamem3` milestone](flamingo_bwamem3_milestone.md) requires review
before experimental interface or processing changes.
