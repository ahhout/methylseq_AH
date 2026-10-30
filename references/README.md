# Production EM-seq reference

`emseq_hg38_lambda_puc19` is a symlink to the existing external bundle:

```text
/mnt/beegfs01/scratch/a_houtman/nextflow/nf-core-methylseq/references/wgbstools_hg38_lambda_puc19_v1
```

It contains the exact wgbstools hg38 human sequence (GRCh38 assembly generation)
plus unmethylated lambda (`phage_lambda`) and methylated pUC19
(`plasmid_puc19c`) controls, with a Bismark index. Keeping the exact human
sequence preserves compatibility with the original project's human CpG
coordinate namespace. Controls are for alignment/QC and must not enter human
CpG dictionaries or downstream human reference matrices.

Small original build records are copied unchanged under
[`provenance/emseq_hg38_lambda_puc19/`](provenance/emseq_hg38_lambda_puc19/).
Their historical source paths are evidence and have not been rewritten.

| Identity | Recorded SHA-256 |
| --- | --- |
| Source human `hg38.fa.gz` | `362592f9bfeda5e761db0ccf6d8fca9988e2a6a4e22071985e4c86e1a53f7b75` |
| Source control FASTA | `f0d3c9c5cdbf9b52c54192e4db1031dd6753763808491d7e4251c66145657a84` |
| Combined `BismarkIndex/genome.fa` | `ef6b38605df06546ef2a28cd4d353a7dec183d1ecc6ea7a680e890e85a0313eb` |
| Index checksum inventory | `5bbdde4ca060db0a4d6ca15b169bb64c3fb08769f1ba381eab2d84c59d803691` |

The original manifest records Bismark v0.25.1 and build time
`2026-08-21T12:03:13Z`. No FASTA, index or container payload is imported.
Integration checks compare both symlink texts/targets and the small provenance
records, without repeating a full multi-gigabyte payload checksum. These
recorded hashes identify prior build evidence, not a new payload verification.

On Flamingo, the existing authoritative target must remain accessible. A
checkout elsewhere does not recreate the reference. Do not retarget the link,
substitute a GRCh38/iGenomes bundle, rebuild the index or change control content
without explicit scientific approval. The original, broader reference registry
remains `/home/a_houtman/em_seq/references/README.md`.
