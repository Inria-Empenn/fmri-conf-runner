#!/usr/bin/env bash

#OAR -l walltime=4
#OAR -O ./log/postprocess_log_%jobid%.stdout
#OAR -E ./log/postprocess_log_%jobid%.stderr
#OAR -q production

BASE="/home/ymerel/empenn_group_storage/private/ymerel"
RESULTS="$BASE/auditory_276"

pip install -r requirements.txt
python postprocess.py --results $RESULTS

