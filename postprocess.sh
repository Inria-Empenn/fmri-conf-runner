#!/usr/bin/env bash

#OAR -l walltime=4
#OAR -O /home/ymerel/empenn_group_storage/private/ymerel/results/log/postprocess_%jobname%_%jobid%.stdout
#OAR -E /home/ymerel/empenn_group_storage/private/ymerel/results/log/postprocess_%jobname%_%jobid%.stderr
#OAR -p core_count>=72
#OAR -q production

TAG="ghcr.io/inria-empenn/fmri-confs-runner:latest"

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
SUBDIR="$OAR_JOB_NAME"
RESULTS="$BASE/results/$SUBDIR"

g5k-setup-docker -t
docker run -u root -v "$RESULTS:/results" $TAG python -u postprocess.py --results "/results"

sudo-g5k chown -R ymerel:empenn "$RESULTS"