#!/usr/bin/env bash

#OAR --array 40
#OAR -l walltime=4
#OAR -O ./log/run_config_log_%jobid%.stdout
#OAR -E ./log/run_config_log_%jobid%.stderr
#OAR -q production

TAG="fmri-confs-runner"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
DATA="$BASE/data/auditory"
RESULTS="$BASE/results/auditory"
WORK="/tmp"
CONFIGS="$BASE/configs"

CONF="config_$OAR_ARRAY_INDEX.csv"

echo "Running configuration is [$CONF]"

g5k-setup-docker -t
docker build . -t $TAG
if [ "$OAR_ARRAY_INDEX" -eq 1 ]; then
    # write ref config only for the first job
    docker run -u root -v "$DATA:/data" -v "$RESULTS:/results" -v "$WORK:/work" -v "$CONFIGS:/configs" $TAG python -u run.py --configs "/configs/$CONF" --data /data/data_desc.json --ref /configs/config_ref.csv
else
    docker run -u root -v "$DATA:/data" -v "$RESULTS:/results" -v "$WORK:/work" -v "$CONFIGS:/configs" $TAG python -u run.py --configs "/configs/$CONF" --data /data/data_desc.json
fi

sudo-g5k chown -R ymerel:empenn $RESULTS

