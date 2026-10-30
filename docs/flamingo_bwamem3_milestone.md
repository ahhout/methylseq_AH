# Follow-up milestone: feature/bwamem3

Create `feature/bwamem3` from the accepted `integration/flamingo-emseq` commit
when experimental development is authorized. Record that exact parent in the
milestone implementation. This document defines the review boundary; this
integration creates no experimental branch or aligner code. Bismark remains
the production default.

The existing pilot is implementation evidence in the separate original project,
`/home/a_houtman/em_seq`, at checkpoint
`c86141ab948d2c338dcc38eec7caded269134584`. Do not import its whole downstream
project. Relevant source and evidence locations are:

| Evidence | Original-project relative path / identity |
| --- | --- |
| Runtime and settings | `downstream/projects/bwamem3_pilot/runtime.json`, `environment.yml`, `settings.json` |
| Corrected processing contract | `downstream/projects/bwamem3_pilot/CORRECTED_PILOT.md`, `revision_core.py` |
| Read-2 soft-clip patch | `downstream/projects/bwamem3_pilot/patches/bismark-0.25.1-r2-softclip.patch` |
| Defect investigation | `docs/audits/2026-10-27_08-26-bwamem3-coordinate-plasma-investigation-v1/`; commit `d002bb81b691c7def77dc3b79e90d6cb31f34479` |
| Bounded corrected validation | `docs/audits/2026-10-27_09-02-bwamem3-corrected-benchmark-validation-v1/`; correction commit `77c256ee52ee8594c24402810aadfcc88c10fbdb` |

## Evidence to carry forward

| Existing pilot rule / identity | Meaning for the proposed milestone |
| --- | --- |
| BWA-MEM3 0.13.0; image SHA-256 `d9d8392c118d11028de1315c04068f0b859bc6dc70328a1b5145066e589942d3` | Reuse the recorded immutable runtime as implementation evidence; approve exact packaging before porting. Bismark 0.25.1, samtools 1.22.1 and module Apptainer 1.3.6 are also recorded. |
| `--meth=emseq --meth-scoring collapsed --meth-seed-prune=spec30 --meth-tags all` | Existing pilot options; supported experimental interface and library modes still require agreement. |
| `Bismark0.25.1+local-r2-softclip-v1` | Two read-2 extractor conditions treat ignored soft clips like insertions because neither consumes reference bases. Generation checks the expected upstream checksum. |
| Original extractor SHA-256 `b0fc6815230ffbaed32c9b8b2df04c4682d3cf1c78fa651ed81d993763fe1109`; corrected `75d0e3f90e12d206d00722c98758825c04d5493e3bf26ef8ca80b92623622b34` | Preserve source/patch identity and independent coordinate tests. Do not inject shell prologues into nf-core tasks or overwrite an upstream runtime silently. |
| `inward-span1000-v1`: exactly one primary mapped R1/R2; MAPQ >0; QC-pass; matching directional tags; reciprocal mate metadata; compatible inward orientation; outer aligned reference span >0 and ≤1,000 bp, excluding soft clips | This approved pilot policy avoids requiring the learned proper-pair flag. Original flags, names, coordinates and tags remain unchanged. Its use in the fork must be reviewed explicitly. |
| Paired positional deduplication; `--no_overlap --ignore_r2 2 --ignore_3prime_r2 2` | Preserve the pilot's recorded processing semantics when designing the comparison; no production-policy change is authorized by this document. |

Retained validation reports 54 unit tests, 28 synthetic geometries plus a
duplicate, and 11 synthetic/control/prefix extractions matching 2,292,175
independently projected context-labelled observations with zero missing or
excess calls. The original extractor produced 105 excess and 105 missing
synthetic observations. These results establish correctness within those
tested bounds; they do not establish biological truth or production equivalence.

Existing runtime manifests inspected during this reconciliation show all three
corrected sample completion markers in
`/mnt/beegfs01/scratch/a_houtman/tmp/em_seq/bwamem3_pilot/2026-10-27_09-26-bwamem3-corrected-three-samples-v2/`.
Plasma completed `2026-10-30T05:51:31Z`. The combined `completed/compare.json`
is absent and top-level provenance still says `postprocessing`. Combined
comparative validation therefore remains unconfirmed. No pilot analysis was
executed during reconciliation.

## Approval and implementation sequence

1. Specify and approve an explicit experimental aligner interface, supported
   library modes and reference/index contract. Do not reuse an existing
   `bwamem`/TAPS route without reviewing its chemistry semantics.
2. Approve exact containers, directional tags, pair eligibility, duplicate
   handling, extraction and corrected-extractor packaging.
3. Port only necessary modules/helpers, retaining immutable identities,
   independent coordinate tests and original-flag preservation checks.
4. Validate the Nextflow implementation against existing synthetic/control
   evidence, then approve bounded biological comparisons and full-run acceptance
   criteria, including runtime/resource measurements and reproducible outputs.
5. Review the resulting evidence before any decision to change production defaults.

Prior pilot approval supplies evidence for design review. It does not approve
new processing choices or production-default changes in this fork.
