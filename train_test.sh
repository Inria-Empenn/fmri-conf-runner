#!/usr/bin/env bash

#OAR -l walltime=5
#OAR -O ./log/train_test_log_%jobid%.stdout
#OAR -E ./log/train_test_log_%jobid%.stderr
#OAR -q production

TAG="fmri-confs-runner"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
RESULTS="$BASE/results/auditory"

g5k-setup-docker -t
docker build . -t $TAG
docker run -u root -v "$RESULTS:/results" $TAG python -u train_test.py --results "/results" --iter 3

sudo-g5k chown -R ymerel:empenn $RESULTS/*.csv