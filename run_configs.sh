#!/usr/bin/env bash

#OAR --array 10
#OAR -l walltime=6
#OAR -O ./log/run_configs_%jobname%_%jobid%.stdout
#OAR -E ./log/run_configs_%jobname%_%jobid%.stderr
#OAR -q production

TAG="ghcr.io/inria-empenn/fmri-confs-runner:latest"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
SUBDIR="$OAR_JOB_NAME"

DATA="$BASE/data/hcp-bids"
RESULTS="$BASE/results/$SUBDIR"
WORK="/tmp"
CONFIGS="$BASE/configs/$SUBDIR"

CONF="config_$OAR_ARRAY_INDEX.csv"

echo "Running configuration is [$CONF]"

g5k-setup-docker -t
docker run -u root -v "$DATA:/data" -v "$RESULTS:/results" -v "$WORK:/work" -v "$CONFIGS:/configs" $TAG python -u run.py --configs "/configs/$CONF" --data /configs/data_desc.json

sudo-g5k chown -R ymerel:empenn "$RESULTS"

