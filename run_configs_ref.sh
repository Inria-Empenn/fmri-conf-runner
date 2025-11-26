#!/usr/bin/env bash

#OAR -l walltime=1
#OAR -O ./log/run_configs_ref_%jobname%_%jobid%.stdout
#OAR -E ./log/run_configs_ref_%jobname%_%jobid%.stderr
#OAR -q production

TAG="ghcr.io/inria-empenn/fmri-confs-runner:latest"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
SUBDIR="$OAR_JOB_NAME"

DATA="$BASE/data/hcp-bids"
RESULTS="$BASE/results/$SUBDIR"
WORK="/tmp"
CONFIGS="$BASE/configs/$SUBDIR"

CONF="ref"

echo "Running configuration is [$CONF]"

g5k-setup-docker -t
docker run -u root -v "$DATA:/data" -v "$RESULTS:/results" -v "$WORK:/work" -v "$CONFIGS:/configs" $TAG python -u run.py --data /configs/data_desc.json --ref /configs/config_ref.csv
sudo-g5k chown -R ymerel:empenn "$RESULTS"

