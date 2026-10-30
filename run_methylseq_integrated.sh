#!/bin/bash
#SBATCH --job-name=nf_core_methylseq_integrated
#SBATCH --output=/home/a_houtman/em_seq/logs/nf_core_methylseq_integrated_%j.out
#SBATCH --error=/home/a_houtman/em_seq/logs/nf_core_methylseq_integrated_%j.err
#SBATCH --time=7-00:00:00
#SBATCH --partition=longq
#SBATCH --mem=8G
#SBATCH --cpus-per-task=2

# Integrated production launcher. It aligns reads competitively to the exact
# wgbstools hg38 human sequence, lambda, and pUC19, emits genome-wide cytosine
# reports, and summarizes the EM-seq controls. Historical 2026-07-20 outputs
# used the legacy iGenomes-derived bundle documented under references/.

set -euo pipefail
readonly ATTEMPT_STARTED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

SCRIPT_DIR="/home/a_houtman/em_seq"
cd "$SCRIPT_DIR"

CONFIG="$SCRIPT_DIR/config/nextflow.config"
PARAMS="$SCRIPT_DIR/config/params.emseq.integrated.yml"
SAMPLESHEET="$SCRIPT_DIR/samplesheets/samplesheet.csv"
CONTROL_REPORTER="$SCRIPT_DIR/scripts/summarize_emseq_controls.py"
REFERENCE_ROOT="$SCRIPT_DIR/references/emseq_hg38_lambda_puc19"
BISMARK_INDEX="$REFERENCE_ROOT/BismarkIndex"
REFERENCE="$BISMARK_INDEX/genome.fa"

SCRATCH_BASE="/mnt/beegfs01/scratch/a_houtman/tmp/em_seq"
SESSION_HELPER="$SCRIPT_DIR/scripts/methylseq_cache_session.py"
MAINTENANCE_LOCK="$SCRATCH_BASE/.methylseq-cache-maintenance.lock"
RESULTS_BASE="/mnt/beegfs01/scratch/a_houtman/nextflow/nf-core-methylseq/results"
RUN_NAME="${RUN_NAME:-}"
RESUME_EXISTING="${RESUME_EXISTING:-false}"

WORKDIR="$SCRATCH_BASE/work_emseq_integrated"
OUTPUT="$RESULTS_BASE/bulk/$RUN_NAME"
PIPELINE_INFO="$OUTPUT/pipeline_info"
SUBMITTED_DIR="$PIPELINE_INFO/submitted"
COVERAGE_DIR="$OUTPUT/bismark/methylation_calls/methylation_coverage"
CONTROL_QC="$OUTPUT/control_qc/control_qc.tsv"
RUN_LINK="$SCRIPT_DIR/outputs/$RUN_NAME"

[[ -d "$SCRIPT_DIR" ]] || { echo "Missing script directory: $SCRIPT_DIR" >&2; exit 1; }
[[ -f "$CONFIG" ]] || { echo "Missing Nextflow config: $CONFIG" >&2; exit 1; }
[[ -f "$PARAMS" ]] || { echo "Missing integrated params file: $PARAMS" >&2; exit 1; }
[[ -f "$SAMPLESHEET" ]] || { echo "Missing EM-seq samplesheet: $SAMPLESHEET" >&2; exit 1; }
[[ -x "$CONTROL_REPORTER" ]] || { echo "Missing or non-executable control reporter: $CONTROL_REPORTER" >&2; exit 1; }
[[ -n "$RUN_NAME" ]] || { echo "RUN_NAME is required; submit with sbatch --export=ALL,RUN_NAME=..." >&2; exit 1; }
[[ "$RUN_NAME" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}(_([01][0-9]|2[0-3])-([0-5][0-9]))?-emseq-integrated-[a-z0-9]+(-[a-z0-9]+)*-v[1-9][0-9]*$ ]] || {
    echo "RUN_NAME must match YYYY-MM-DD_HH-MM-emseq-integrated-<cohort-purpose>-vN (UTC): $RUN_NAME" >&2
    exit 1
}
if [[ "$RUN_NAME" != ????-??-??_??-??-* ]] && ! [[ "$RESUME_EXISTING" == true && -d "$OUTPUT" ]]; then
    echo "New outputs require hours and minutes (UTC): YYYY-MM-DD_HH-MM-emseq-integrated-<cohort-purpose>-vN" >&2
    exit 1
fi
RUN_DATE="${RUN_NAME:0:10}"
if ! NORMALIZED_RUN_DATE="$(date -d "$RUN_DATE" +%F 2>/dev/null)" || [[ "$NORMALIZED_RUN_DATE" != "$RUN_DATE" ]]; then
    echo "RUN_NAME begins with an invalid calendar date: $RUN_DATE" >&2
    exit 1
fi
[[ -s "$REFERENCE_ROOT/manifest.tsv" ]] || { echo "Missing integrated reference manifest: $REFERENCE_ROOT/manifest.tsv" >&2; exit 1; }
[[ -s "$REFERENCE" ]] || { echo "Missing combined reference FASTA: $REFERENCE" >&2; exit 1; }
[[ -d "$BISMARK_INDEX/Bisulfite_Genome/CT_conversion" ]] || { echo "Missing Bismark CT index: $BISMARK_INDEX" >&2; exit 1; }
[[ -d "$BISMARK_INDEX/Bisulfite_Genome/GA_conversion" ]] || { echo "Missing Bismark GA index: $BISMARK_INDEX" >&2; exit 1; }
find "$BISMARK_INDEX/Bisulfite_Genome" -type f \( -name '*.bt2' -o -name '*.bt2l' \) | grep -q . || {
    echo "No Bowtie2 index files found under: $BISMARK_INDEX" >&2
    exit 1
}
[[ "$(awk '/^>phage_lambda$/{count++} END{print count+0}' "$REFERENCE")" -eq 1 ]] || {
    echo "Combined FASTA must contain exactly one phage_lambda contig" >&2
    exit 1
}
[[ "$(awk '/^>plasmid_puc19c$/{count++} END{print count+0}' "$REFERENCE")" -eq 1 ]] || {
    echo "Combined FASTA must contain exactly one plasmid_puc19c contig" >&2
    exit 1
}
[[ -n "${SLURM_JOB_ID:-}" ]] || { echo "SLURM_JOB_ID is unset; submit this launcher with sbatch" >&2; exit 1; }
[[ "$RESUME_EXISTING" == "true" || "$RESUME_EXISTING" == "false" ]] || {
    echo "RESUME_EXISTING must be true or false: $RESUME_EXISTING" >&2
    exit 1
}
OUTPUT_HAS_CONTENT="false"
if [[ -e "$OUTPUT" ]]; then
    [[ -d "$OUTPUT" ]] || { echo "Output path exists but is not a directory: $OUTPUT" >&2; exit 1; }
    if [[ -n "$(find "$OUTPUT" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
        OUTPUT_HAS_CONTENT="true"
        if [[ "$RESUME_EXISTING" != "true" ]]; then
            echo "Output directory is not empty: $OUTPUT" >&2
            echo "Set RESUME_EXISTING=true only to resume this exact named run." >&2
            exit 1
        fi
    fi
elif [[ "$RESUME_EXISTING" == "true" ]]; then
    echo "Cannot resume because the named output directory does not exist: $OUTPUT" >&2
    exit 1
fi
if [[ -e "$RUN_LINK" || -L "$RUN_LINK" ]]; then
    [[ "$(readlink -f "$RUN_LINK")" == "$OUTPUT" ]] || {
        echo "Run link already exists with a different target: $RUN_LINK" >&2
        exit 1
    }
fi

readonly NEXTFLOW_LOG="$PIPELINE_INFO/nextflow_${SLURM_JOB_ID}.log"

while IFS=, read -r sample fastq_1 fastq_2 genome extra; do
    [[ -n "$sample" ]] || { echo "Samplesheet contains a blank sample identifier" >&2; exit 1; }
    [[ -s "$fastq_1" ]] || { echo "Missing or empty FASTQ for $sample: $fastq_1" >&2; exit 1; }
    if [[ -n "$fastq_2" ]]; then
        [[ -s "$fastq_2" ]] || { echo "Missing or empty FASTQ for $sample: $fastq_2" >&2; exit 1; }
    fi
    [[ -z "${extra:-}" ]] || { echo "Unexpected extra samplesheet column for $sample" >&2; exit 1; }
done < <(tail -n +2 "$SAMPLESHEET")

if [[ "$OUTPUT_HAS_CONTENT" == "true" && ! -d "$SUBMITTED_DIR" ]]; then
    echo "Cannot safely resume: submitted input snapshot directory is missing: $SUBMITTED_DIR" >&2
    exit 1
fi
# Hold the lock for the entire pipeline. Cleanup and other canonical launches
# must not overlap this shared-session writer. Legacy writers are also checked
# by cleanup through Slurm; they do not participate in this new lock.
command -v flock >/dev/null 2>&1 || { echo "flock is unavailable" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is unavailable" >&2; exit 1; }
exec 9>"$MAINTENANCE_LOCK"
flock -n 9 || { echo "Shared cache is in use or under maintenance" >&2; exit 1; }
SESSION_ID="$(python3 "$SESSION_HELPER" validate)"

mkdir -p "$WORKDIR" "$SUBMITTED_DIR" "$SCRIPT_DIR/.nextflow" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/outputs"
[[ -d "$WORKDIR" ]] || { echo "Missing work directory: $WORKDIR" >&2; exit 1; }
[[ -d "$OUTPUT" ]] || { echo "Missing output directory: $OUTPUT" >&2; exit 1; }


if [[ "$OUTPUT_HAS_CONTENT" == "true" ]]; then
    # Checks original snapshot integrity and unchanged scientific inputs.
    # Launcher revisions are preserved separately for each attempt.
    python3 "$SESSION_HELPER" begin --output "$OUTPUT" --job "$SLURM_JOB_ID" --started-utc "$ATTEMPT_STARTED_UTC" --existing
else
    install -m 0755 "$SCRIPT_DIR/run_methylseq_integrated.sh" "$SUBMITTED_DIR/run_methylseq_integrated.sh"
    install -m 0644 "$PARAMS" "$SUBMITTED_DIR/params.emseq.integrated.yml"
    install -m 0644 "$CONFIG" "$SUBMITTED_DIR/nextflow.config"
    install -m 0644 "$SAMPLESHEET" "$SUBMITTED_DIR/samplesheet.csv"
    install -m 0644 "$REFERENCE_ROOT/manifest.tsv" "$SUBMITTED_DIR/reference_manifest.tsv"
    (
        cd "$SUBMITTED_DIR"
        sha256sum \
            run_methylseq_integrated.sh \
            params.emseq.integrated.yml \
            nextflow.config \
            samplesheet.csv \
            reference_manifest.tsv > SHA256SUMS
    )

    {
        printf 'field\tvalue\n'
        printf 'run_name\t%s\n' "$RUN_NAME"
        printf 'started_utc\t%s\n' "$ATTEMPT_STARTED_UTC"
        printf 'slurm_job_id\t%s\n' "$SLURM_JOB_ID"
        printf 'output\t%s\n' "$OUTPUT"
        printf 'work_dir\t%s\n' "$WORKDIR"
        printf 'pipeline\tnf-core/methylseq\n'
        printf 'pipeline_version\t4.2.0\n'
        printf 'resume_existing\t%s\n' "$RESUME_EXISTING"
    } > "$SUBMITTED_DIR/run_manifest.tsv"
fi

if [[ "$OUTPUT_HAS_CONTENT" != "true" ]]; then
    python3 "$SESSION_HELPER" begin --output "$OUTPUT" --job "$SLURM_JOB_ID" --started-utc "$ATTEMPT_STARTED_UTC"
fi
record_attempt_exit() {
    local status=$?
    trap - EXIT
    python3 "$SESSION_HELPER" finish --output "$OUTPUT" --job "$SLURM_JOB_ID" --exit-status "$status" || {
        echo "Failed to record attempt completion; treat provenance as incomplete" >&2
        [[ "$status" -ne 0 ]] || status=1
    }
    exit "$status"
}
trap record_attempt_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

command -v conda >/dev/null 2>&1 || { echo "conda command is not available" >&2; exit 1; }
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate nextflow
command -v nextflow >/dev/null 2>&1 || { echo "nextflow is unavailable after activating the nextflow environment" >&2; exit 1; }

module load containers/apptainer/1.3.6
command -v apptainer >/dev/null 2>&1 || { echo "apptainer is unavailable after loading its module" >&2; exit 1; }

NEXTFLOW_COMMAND=(
    nextflow -log "$NEXTFLOW_LOG" run nf-core/methylseq
    -r 4.2.0
    -config "$CONFIG"
    -params-file "$PARAMS"
    -work-dir "$WORKDIR"
    -profile apptainer
    --outdir "$OUTPUT"
    -resume "$SESSION_ID"
)
if [[ "$OUTPUT_HAS_CONTENT" == "true" ]]; then
    COMMAND_RECORD="$SUBMITTED_DIR/command.resume-${SLURM_JOB_ID}.sh"
else
    COMMAND_RECORD="$SUBMITTED_DIR/command.sh"
fi
printf '%q ' "${NEXTFLOW_COMMAND[@]}" > "$COMMAND_RECORD"
printf '\n' >> "$COMMAND_RECORD"
cp "$COMMAND_RECORD" "$SUBMITTED_DIR/attempts/$SLURM_JOB_ID/command.sh"

"${NEXTFLOW_COMMAND[@]}"

python3 "$CONTROL_REPORTER" \
    --coverage-dir "$COVERAGE_DIR" \
    --samplesheet "$SAMPLESHEET" \
    --output "$CONTROL_QC"

if [[ ! -e "$RUN_LINK" && ! -L "$RUN_LINK" ]]; then
    ln -s "$OUTPUT" "$RUN_LINK"
fi

echo "Integrated methylseq results: $OUTPUT"
echo "Control-QC report: $CONTROL_QC"
echo "Repository run link: $RUN_LINK"
