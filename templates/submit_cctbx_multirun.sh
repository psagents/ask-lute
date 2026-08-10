#!/bin/bash
################################################################################
# LUTE + CCTBX Multi-Run Submission Script (template)
#
# Purpose: Index + Scale a list of runs independently, then merge all of them
#          together in one combined MergeCCTBXXFEL task. Submits at most
#          MAX_CONCURRENT_INDEXING runs' Index+Scale jobs at a time, waiting
#          for each batch to finish before starting the next - needed because
#          each indexing job typically needs several nodes (verified baseline:
#          4 nodes for CCTBXIndexer + 1 for the wrapper job managing it, see
#          cctbx-sfx-workflow.md §6), and many experiments have a node/core
#          allocation budget that submitting every run at once would exceed.
#
# Fill in the CONFIGURATION section below for a specific experiment, then:
#   1. Generate one Index+Scale config per run under CONFIG_DIR (see
#      IndexCCTBXXFEL.yaml / ScaleCCTBXXFEL.yaml templates) - each with its own
#      unique phil_file and its own {work_dir}/r00XX/ output subfolder
#      (see references/cctbx-sfx-workflow.md §7 before writing these).
#   2. Generate one combined merge config (see MergeCCTBXXFEL.yaml template)
#      whose phil_parameters.input_path lists every run's cctbx_scaled/ dir.
#   3. Run this script.
#
# Prerequisites:
#   - LUTE built: cd <LUTE_PATH> && ./build.sh -e
#   - Valid Kerberos ticket: kinit <user>@SLAC.STANFORD.EDU
################################################################################

set -e

# ==============================================================================
# CONFIGURATION — fill in for this experiment
# ==============================================================================

LUTE_PATH=""                  # e.g. /sdf/data/lcls/ds/mfx/<experiment>/results/lute
BASE_DIR=""                   # work_dir shared by every run, e.g. .../results/<name>
CONFIG_DIR="${BASE_DIR}/configs"
INDEX_SCALE_WORKFLOW="${BASE_DIR}/workflows/cctbx_index_scale_only.yaml"  # Index -> Scale, no per-run Merge

EXPERIMENT=""                 # e.g. mfx101624926
RUNS=()                       # e.g. (35 36 37 38 39)
RUN_SUFFIX=""                 # e.g. "_2" for a second processing pass, kept separate from
                               # the original run's output/config so both can be compared.
                               # Must match whatever suffix the configs and their internal
                               # output_output_dir/input_path fields actually use.

MERGE_CONFIG="${CONFIG_DIR}/cctbx_merge_combined.yaml"  # single MergeCCTBXXFEL config, input_path = list of all runs

# Node budget: how many Index+Scale jobs run at once. Each CCTBXIndexer job
# needs its own nodes (verified baseline: 4) plus 1 for the wrapper managing
# it - set this from the experiment's actual node/core allocation, not just
# copied from another experiment.
MAX_CONCURRENT_INDEXING=4

PARTITION="milano"
ACCOUNT="lcls:${EXPERIMENT}"

# ==============================================================================
# VALIDATION
# ==============================================================================

if [ -z "${LUTE_PATH}" ] || [ -z "${BASE_DIR}" ] || [ -z "${EXPERIMENT}" ] || [ ${#RUNS[@]} -eq 0 ]; then
    echo "ERROR: fill in LUTE_PATH, BASE_DIR, EXPERIMENT, and RUNS before running this script."
    exit 1
fi

LAUNCH_SLURM="${LUTE_PATH}/install/bin/launch_slurm"
SUBMIT_SLURM="${LUTE_PATH}/install/bin/submit_slurm"
SUBMIT_WRAPPER="${LUTE_PATH}/install/bin/submit_launch_slurm.sh"

if [ ! -f "${LAUNCH_SLURM}" ]; then
    echo "ERROR: launch_slurm not found at ${LAUNCH_SLURM} - run ./build.sh -e in LUTE_PATH first."
    exit 1
fi

if ! klist -s 2>/dev/null; then
    echo "ERROR: No valid Kerberos ticket. Run: kinit <user>@SLAC.STANFORD.EDU"
    exit 1
fi

echo "OK: lute install found, Kerberos ticket valid"
echo "OK: batching Index+Scale submissions ${MAX_CONCURRENT_INDEXING} at a time"
echo ""

# ==============================================================================
# ACTIVATE LUTE ENVIRONMENT
# ==============================================================================

source "${LUTE_PATH}/install/bin/activate_installation"

# activate_installation computes PYTHONPATH from whatever `python3` is first on
# PATH, which can silently resolve to the wrong version (e.g. a personal conda
# env) rather than the one LUTE was built with. Pin it explicitly instead of
# trusting ambient PATH resolution - see cctbx-sfx-workflow.md §6.
LUTE_PYVER="$(basename "$(ls -d "${LUTE_PATH}"/install/lib/python*/ | head -1)")"
export PYTHONPATH="${LUTE_PATH}/install/lib/${LUTE_PYVER}/site-packages:${PYTHONPATH}"
echo "OK: LUTE environment activated, PYTHONPATH pinned to ${LUTE_PYVER}"
echo ""

# ==============================================================================
# CREATE PER-RUN OUTPUT DIRECTORIES (LUTE does not create these itself)
# ==============================================================================

for RUN in "${RUNS[@]}"; do
    RUN4=$(printf "%04d" "$RUN")
    mkdir -p "${BASE_DIR}/r${RUN4}${RUN_SUFFIX}/cctbx_indexed/logs" "${BASE_DIR}/r${RUN4}${RUN_SUFFIX}/cctbx_scaled"
done
mkdir -p "${BASE_DIR}/cctbx_merged/tmp"

# ==============================================================================
# SUBMIT INDEX + SCALE IN BATCHES OF MAX_CONCURRENT_INDEXING
# ==============================================================================

cd "${BASE_DIR}"   # so slurm-*.out / CCTBXIndexer_*.out land here, not $PWD

submit_run() {
    local RUN="$1"
    local RUN4
    RUN4=$(printf "%04d" "$RUN")
    local CONFIG="${CONFIG_DIR}/${EXPERIMENT}_r${RUN4}${RUN_SUFFIX}_cctbx.yaml"

    if [ ! -f "${CONFIG}" ]; then
        echo "ERROR: config not found for run ${RUN}: ${CONFIG} - skipping"
        return
    fi

    echo "Submitting run ${RUN}${RUN_SUFFIX}..."
    local OUT
    OUT="$(${SUBMIT_WRAPPER} "${LAUNCH_SLURM}" \
        -c "${CONFIG}" -W "${INDEX_SCALE_WORKFLOW}" \
        -e "${EXPERIMENT}" -r "${RUN}" \
        --partition="${PARTITION}" --account="${ACCOUNT}")"
    echo "${OUT}"
    echo "${OUT}" | grep -oE 'Submitted batch job [0-9]+' | grep -oE '[0-9]+'
}

wait_for_jobs() {
    # Blocks until every job ID passed in has left the queue, then checks
    # sacct to see whether each one actually COMPLETED. Leaving the queue
    # isn't enough on its own - a scancel'd or FAILED job also leaves the
    # queue, and would otherwise be silently treated the same as success,
    # letting the script march on to the next batch (or the merge) on top of
    # a cancelled/failed run. Exits the whole script if anything didn't
    # complete cleanly, rather than proceeding on bad data.
    local BAD=()
    for JOB_ID in "$@"; do
        while squeue -j "${JOB_ID}" 2>/dev/null | grep -q "${JOB_ID}"; do
            sleep 15
        done
        local STATE
        STATE="$(sacct -j "${JOB_ID}" --format=State --noheader --parsable2 2>/dev/null | head -1 | tr -d ' ')"
        if [ "${STATE}" != "COMPLETED" ]; then
            BAD+=("${JOB_ID}:${STATE:-UNKNOWN}")
        fi
    done
    if [ ${#BAD[@]} -gt 0 ]; then
        echo "" >&2
        echo "ERROR: these jobs did not complete successfully: ${BAD[*]}" >&2
        echo "Stopping here - NOT proceeding to the next batch or the merge automatically." >&2
        exit 1
    fi
}

TOTAL=${#RUNS[@]}
for (( START=0; START<TOTAL; START+=MAX_CONCURRENT_INDEXING )); do
    BATCH=("${RUNS[@]:START:MAX_CONCURRENT_INDEXING}")
    echo ""
    echo "=== Batch: runs ${BATCH[*]} ==="
    BATCH_JOB_IDS=()
    for RUN in "${BATCH[@]}"; do
        JOB_ID="$(submit_run "${RUN}")"
        [ -n "${JOB_ID}" ] && BATCH_JOB_IDS+=("${JOB_ID}")
    done
    echo "Waiting for batch to finish (${BATCH_JOB_IDS[*]}) before starting the next..."
    wait_for_jobs "${BATCH_JOB_IDS[@]}"
done

echo ""
echo "All Index+Scale jobs finished. Checking for scaled output before merging..."
for RUN in "${RUNS[@]}"; do
    RUN4=$(printf "%04d" "$RUN")
    COUNT=$(ls "${BASE_DIR}/r${RUN4}${RUN_SUFFIX}/cctbx_scaled/"*.expt 2>/dev/null | wc -l)
    echo "  run ${RUN}${RUN_SUFFIX}: ${COUNT} scaled .expt files"
    if [ "${COUNT}" -eq 0 ]; then
        echo "  WARNING: run ${RUN}${RUN_SUFFIX} produced no scaled output - check its logs before trusting the merge."
    fi
done

# ==============================================================================
# SUBMIT THE COMBINED MERGE (single task, not a DAG - see cctbx-sfx-workflow.md §7)
# ==============================================================================

if [ ! -f "${MERGE_CONFIG}" ]; then
    echo "ERROR: merge config not found at ${MERGE_CONFIG} - not submitting merge."
    exit 1
fi

echo ""
echo "Submitting combined merge..."
"${SUBMIT_SLURM}" \
    --taskname CCTBXMerger \
    --config "${MERGE_CONFIG}" \
    --psana2 -e "${EXPERIMENT}" -r "${RUNS[0]}" \
    --partition="${PARTITION}" --account="${ACCOUNT}" \
    --ntasks-per-node=60 --nodes=1 --cpus-per-task=1

echo ""
echo "Done. Check job status: squeue -u \$USER"
echo "Merge output: ${BASE_DIR}/cctbx_merged/"
