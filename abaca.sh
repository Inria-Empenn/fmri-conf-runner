#!/usr/bin/env bash

#OAR -l walltime=48
#OAR -O ./log/log_%jobid%.stdout
#OAR -E ./log/log_%jobid%.stderr
#OAR -q production

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
DATA="$BASE/data/auditory"
RESULTS="$BASE/results/auditory"
WORK="$BASE/work"
CONFIGS="$BASE/configs"

CONF="conf_test.csv"

# Check if a parameter is provided
if [ -n "$1" ]; then
  # Override CONF with the provided parameter
  CONF=$1
fi

echo "Running configuration is [$CONF]"

g5k-setup-docker -t
docker build . -t fmri-fm
docker run -u root -v "$DATA:/data" -v "$RESULTS:/results" -v "$WORK:/work" -v "$CONFIGS:/data/configs" fmri-fm python run.py --configs "/data/configs/$CONF" --data /data/data_desc.json --ref /data/configs/config_ref.csv


