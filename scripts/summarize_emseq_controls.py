#!/usr/bin/env python3
"""Summarize EM-seq control methylation from Bismark coverage files."""

from __future__ import annotations

import argparse
import csv
import gzip
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


CONTROLS = ("phage_lambda", "plasmid_puc19c")


@dataclass
class Counts:
    covered_cpgs: int = 0
    methylated: int = 0
    unmethylated: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a per-sample QC table for lambda and pUC19 controls."
    )
    parser.add_argument(
        "--coverage-dir",
        type=Path,
        required=True,
        help="Directory containing one Bismark .cov.gz file per sample.",
    )
    parser.add_argument(
        "--samplesheet",
        type=Path,
        required=True,
        help="nf-core/methylseq samplesheet containing a sample column.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV path.",
    )
    return parser.parse_args()


def read_samples(samplesheet: Path) -> list[str]:
    if not samplesheet.is_file():
        raise ValueError(f"samplesheet does not exist: {samplesheet}")
    with samplesheet.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "sample" not in reader.fieldnames:
            raise ValueError(f"samplesheet has no 'sample' column: {samplesheet}")
        samples = [row["sample"].strip() for row in reader]
    if not samples or any(not sample for sample in samples):
        raise ValueError(f"samplesheet contains no samples or a blank sample: {samplesheet}")
    if len(samples) != len(set(samples)):
        raise ValueError(f"samplesheet contains duplicate sample identifiers: {samplesheet}")
    return samples


def assign_coverage_files(coverage_dir: Path, samples: list[str]) -> dict[str, Path]:
    if not coverage_dir.is_dir():
        raise ValueError(f"coverage directory does not exist: {coverage_dir}")
    files = sorted(coverage_dir.glob("*.cov.gz"))
    assignments: dict[str, Path] = {}
    for path in files:
        matches = [
            sample
            for sample in samples
            if path.name.startswith(f"{sample}_") or path.name.startswith(f"{sample}.")
        ]
        if not matches:
            continue
        sample = max(matches, key=len)
        if sample in assignments:
            raise ValueError(
                f"multiple coverage files match sample {sample}: "
                f"{assignments[sample]} and {path}"
            )
        assignments[sample] = path
    missing = [sample for sample in samples if sample not in assignments]
    if missing:
        raise ValueError("missing coverage files for samples: " + ", ".join(missing))
    return assignments


def summarize_file(path: Path) -> dict[str, Counts]:
    counts = {control: Counts() for control in CONTROLS}
    try:
        with gzip.open(path, mode="rt", encoding="utf-8", newline="") as handle:
            for line_number, line in enumerate(handle, start=1):
                fields = line.rstrip("\n").split("\t")
                if len(fields) < 6:
                    raise ValueError(f"{path}:{line_number}: expected at least 6 columns")
                control = fields[0]
                if control not in counts:
                    continue
                try:
                    start = int(fields[1])
                    end = int(fields[2])
                    float(fields[3])
                    methylated = int(fields[4])
                    unmethylated = int(fields[5])
                except ValueError as exc:
                    raise ValueError(f"{path}:{line_number}: malformed numeric value") from exc
                if start < 1 or end < start or methylated < 0 or unmethylated < 0:
                    raise ValueError(f"{path}:{line_number}: invalid coordinate or count")
                target = counts[control]
                total = methylated + unmethylated
                if total > 0:
                    target.covered_cpgs += 1
                target.methylated += methylated
                target.unmethylated += unmethylated
    except (OSError, EOFError) as exc:
        raise ValueError(f"cannot read gzip coverage file {path}: {exc}") from exc
    return counts


def metrics(control: str, counts: Counts) -> tuple[str, str, str]:
    total = counts.methylated + counts.unmethylated
    if total == 0:
        return "NA", "NA", "NO_DATA"
    methylation = 100.0 * counts.methylated / total
    if control == "phage_lambda":
        conversion = 100.0 - methylation
        status = "PASS" if methylation <= 0.5 else "WARN"
        return f"{methylation:.6f}", f"{conversion:.6f}", status
    status = "PASS" if methylation >= 95.0 else "WARN"
    return f"{methylation:.6f}", "NA", status


def write_output(
    output: Path,
    samples: list[str],
    summaries: dict[str, dict[str, Counts]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, text=True
    )
    try:
        with os.fdopen(fd, mode="w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(
                [
                    "sample",
                    "control",
                    "covered_cpgs",
                    "methylated_calls",
                    "unmethylated_calls",
                    "weighted_cpg_methylation_percent",
                    "lambda_conversion_efficiency_percent",
                    "status",
                ]
            )
            for sample in samples:
                for control in CONTROLS:
                    counts = summaries[sample][control]
                    methylation, conversion, status = metrics(control, counts)
                    writer.writerow(
                        [
                            sample,
                            control,
                            counts.covered_cpgs,
                            counts.methylated,
                            counts.unmethylated,
                            methylation,
                            conversion,
                            status,
                        ]
                    )
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    args = parse_args()
    try:
        samples = read_samples(args.samplesheet)
        assignments = assign_coverage_files(args.coverage_dir, samples)
        summaries = {sample: summarize_file(assignments[sample]) for sample in samples}
        write_output(args.output, samples, summaries)
    except ValueError as exc:
        print(
            f"Control-QC reporting failed: {exc}. "
            "Any completed methylseq outputs remain intact.",
            file=sys.stderr,
        )
        return 1
    print(f"Control-QC report written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
