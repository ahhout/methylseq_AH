# Flamingo integration validation

**Publication status:** the integration is prepared and committed locally but
was not published. HTTPS Git lacks credentials, SSH port 22 timed out, and the
connected GitHub app rejected writes with HTTP 403. Automatic approval review
also denied uploading the import manifest because it contains internal paths
and provenance metadata. See [publication evidence](flamingo_publication.json).
The public branch therefore does not yet meet the publication acceptance gate.

The reconciliation used bounded local checks, without submitting Slurm jobs or
rerunning production samples. Bismark, the scientific params and dependencies
were preserved. Results below describe the preparation on 30 October 2026.
[`flamingo_validation.json`](flamingo_validation.json) retains explicit UTC
start/completion timestamps for the initial local import comparison. That report
retains the local checkpoint ID; the public import has the identical verified
tree, with GitHub-assigned commit metadata.

## Checks and results

| Check | Result and scope |
| --- | --- |
| Original Git checkpoint | Clean tracked HEAD `c86141ab948d2c338dcc38eec7caded269134584`; unrelated untracked files left in place. No original-project commit, file edit, data move or runtime cleanup. |
| Fork baseline | Master `b6aa88ef5399cb2992f12d8072e2c8fedf39d003`; 4.2.0 `5aa56467a85a5e2d6795ea72dfa5a5f0c9babc23`; four later commits affect nine workflow/metadata paths only. The original cached production pipeline also has the release commit. |
| Initial import | `c84c02c2987caa7eac0f6e15e506a28974528a8d`: exact raw-import tree of local checkpoint `e390b6f595f7fbbcb10493b196d7db0f61d64c3f`; all 17 source entries match original checksums, including symlink text and six small reference records. No original history merged. |
| Upstream preservation | All 426 fork-baseline files preserved; root README and ignore file retain their exact upstream prefixes and have additions. Licence, pipeline modules, workflow fixes and upstream docs remain intact. |
| Samplesheets | Current four-row and historical eight-row sheets match originals byte-for-byte, with identifiers, FASTQ paths, ordering and four-column structure retained. Publication explicitly authorized; no clinical metadata columns imported. |
| Reference | Both links resolve to the same existing bundle. Build manifest and checksum inventories copied unchanged; no reference payload copied or rehashed. |
| Scientific/runtime configuration | Params match exact original text after reversing only three approved repository prefixes (`input`, `fasta`, `bismark_index`). Environment, Slurm config, session record and control reporter match original bytes. Identical pipeline code/defaults preserve effective scientific choices. This is a source/input comparison, not a Nextflow config-evaluation or production run. |
| Shell syntax | `bash -n` passed. |
| Mocked launcher/session suite | 27 tests passed in 24.133 seconds. Uses temporary source/runtime/work/reference fixtures and mock Nextflow, Conda, module and Apptainer commands. |
| Resume/session and attempts | Tests verify local absolute pipeline path, original runtime cwd, explicit UUID/work selection, source/input/snapshot/identity guards, missing-path failures, maintenance-lock contention, successful/failed timestamps and exact command/checksum evidence. |
| UTC names | Invalid calendar dates, hour 24, minute 60 and missing time fail before output creation. |
| Queued launcher | A stale Slurm-spool copy is rejected before outputs, even when the changed source checkout is clean. |
| Publication review | Review staged diffs and every new reachable integration blob; only selected source/config/docs/sheets/small provenance are included. No sequencing/reference payloads, containers, credentials or unrelated clinical metadata. Preserve raw version-output whitespace as historical evidence. |

## Reproduce the bounded checks

From the fork checkout:

```bash
cd /home/a_houtman/methylseq_AH
bash -n run_methylseq_integrated.sh
python3 -B -m unittest discover -s tests -p test_methylseq_cache_session.py -v
python3 -B scripts/validate_flamingo_import.py --original-repo /home/a_houtman/em_seq
python3 -B scripts/methylseq_cache_session.py validate --runtime-root /home/a_houtman/em_seq
```

The 27-test suite was executed during preparation from the temporary staging
workspace with `python3 -m unittest discover -s tests -p test_methylseq_cache_session.py -v`.
Installed source/test checksums match those tested bytes. The import comparison,
shell syntax, byte comparisons and actual session lookup were run against the
requested sibling checkout. Expected helper output is
`17da6065-5303-40ef-8047-5c8ff69a052d`. The import script prints a JSON report to
stdout and makes no changes. Its source-comparison check requires access to
the unchanged original project and existing external reference target.

Direct comparisons performed were:

```bash
cmp /home/a_houtman/em_seq/samplesheets/samplesheet.csv /home/a_houtman/methylseq_AH/samplesheets/samplesheet.csv
cmp /home/a_houtman/em_seq/samplesheets/samplesheet.2026-08-31-8samples.csv /home/a_houtman/methylseq_AH/samplesheets/samplesheet.2026-08-31-8samples.csv
cmp /home/a_houtman/em_seq/config/nextflow.config /home/a_houtman/methylseq_AH/config/nextflow.config
cmp /home/a_houtman/em_seq/environment.yml /home/a_houtman/methylseq_AH/environment.yml
readlink -f /home/a_houtman/em_seq/references/emseq_hg38_lambda_puc19
readlink -f /home/a_houtman/methylseq_AH/references/emseq_hg38_lambda_puc19
```

Before commit/publication, inspect:

```bash
git diff --cached --check
git diff --cached --stat
git diff --cached
git log --oneline b6aa88ef5399cb2992f12d8072e2c8fedf39d003..HEAD
git rev-list --objects b6aa88ef5399cb2992f12d8072e2c8fedf39d003..HEAD
git check-ignore -v .nextflow/history outputs/example/report.html example.fastq.gz example.pat.gz example.bam reference.fa metadata/private.tsv example.sif
```

The adaptation's staged whitespace check passes. The original imported
`bismark.version.txt` contains trailing whitespace and a final blank line;
those bytes are deliberately retained with their source checksum. Ignore rules
were reviewed before the import checkpoint and adaptation commit. Public
samplesheet review is limited to the actual imported columns/content; it does
not establish anonymity or authorize publication of additional metadata.

## Limits and publication scope

The launcher's environment/module interaction, container binding and complete
Nextflow execution were simulated by bounded mocks. No actual job or full
pipeline test was launched. Multi-gigabyte references/FASTQs were not duplicated
or revalidated. Task cache reuse after switching to a local pipeline source
remains untested. Resolved Nextflow runtime reports will be produced by future
authorized runs; none were fabricated here.

Only `integration/flamingo-emseq` is authorized for publication. Leave master
and the repository default branch unchanged. The original checkout, history,
downstream analyses and runtime remain the historical authority.
