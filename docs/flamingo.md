# Flamingo pipeline source

This checkout is the development fork for nf-core/methylseq. It preserves the
4.2.0 baseline and upstream ancestry. The reorganization changes no workflows,
modules, biological parameters, or reference sequence.

CIRCALL settings and the supported project launcher live in
`/home/a_houtman/analysis/CIRCALL_methylomics`. That project pins this checkout's
full commit in `config/methylseq_pipeline.json`, owns its samplesheets and
references, and keeps future launch state under `runs/methylseq`.

Run preflight or submit from the project launcher. The submission interface
records both source commits and selects scheduler logs outside the result
bundle. A new run atomically reserves a previously nonexistent result directory;
only an exactly matched incomplete owned run can resume. Completed result
bundles cannot be reopened by the supported launcher. The project README and
`docs/methylseq_execution.md` document the actual commands and limitations.

Do not execute CIRCALL production runs directly from this pipeline checkout.
Pipeline development belongs here; project execution settings belong in the
project. Keep both checkouts clean and unchanged during execution and resume.
Future pipeline changes require a reviewed project pin update.

The original `/home/a_houtman/methylseq_AH` and `/home/a_houtman/em_seq` checkouts
remain unchanged for historical execution identities. Their old launchers and
runtime/session databases retain their historical responsibilities. They are
not copied into the new runtime. Fork integration settings are preserved in Git
and in the project's `archive/preprocessing/flamingo_fork_integration`.

The existing shared work cache and maintenance lock remain at their original
scratch locations. Cache reuse across source relocation is untested. No
production run, reference rebuilding, cleanup, or Nextflow upgrade accompanies
this reorganization. The original environment remains installed; project
execution requires Nextflow 25.10.2 and module Apptainer 1.3.6.

The [BWA-MEM3 milestone](flamingo_bwamem3_milestone.md) remains a separate design
record. No BWA-MEM3 implementation is part of this reorganization. Historical
`flamingo_import_manifest.json`, publication, and validation documents describe
the previous integration state at their recorded commits, not this new layout.
