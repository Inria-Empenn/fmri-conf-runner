#!/usr/bin/env bash

#OAR -l walltime=24
#OAR -O ./log/postprocess_log_%jobid%.stdout
#OAR -E ./log/postprocess_log_%jobid%.stderr
#OAR -q production

TAG="fmri-confs-runner"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
RESULTS="$BASE/results/auditory"

g5k-setup-docker -t
docker build . -t $TAG
docker run -u root -v "$RESULTS:/results" $TAG python -u postprocess.py --results "/results"