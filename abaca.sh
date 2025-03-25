#!/usr/bin/env bash

#OAR --array 40
#OAR -l walltime=8
#OAR -O ./log/log_%jobid%.stdout
#OAR -E ./log/log_%jobid%.stderr
#OAR -q production

TAG="fmri-confs-runner"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
DATA="$BASE/data/auditory"
RESULTS="$BASE/results/auditory"
WORK="$BASE/work"
CONFIGS="$BASE/configs"

CONF="config_$OAR_ARRAY_INDEX.csv"

# Check if a parameter is provided
if [ -n "$1" ]; then
  # Override CONF with the provided parameter
  CONF=$1
fi

echo "Running configuration is [$CONF]"

g5k-setup-docker -t
docker build . -t $TAG
docker run -u root -v "$DATA:/data" -v "$RESULTS:/results" -v "$WORK:/work" -v "$CONFIGS:/data/configs" $TAG python run.py --configs "/data/configs/$CONF" --data /data/data_desc.json --ref /data/configs/config_ref.csv


