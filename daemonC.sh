#!/bin/bash

export EGS_HOME=/home/ricr/egsnrc/
export EGS_CONFIG=/home/ricr/HEN_HOUSE/specs/x86_64-unknown-linux-gnu-g77.conf

source /home/ricr/HEN_HOUSE/scripts/egsnrc_bashrc_additions
source /home/ricr/HEN_HOUSE/scripts/beamnrc_bashrc_additions

export EGS_BATCH_OPTIONS=pbs
export EGS_BATCH=pbs
export EGS_BATCH_SYSTEM=pbs

/usr/local/bin/python /home/ricr/MCQA/daemonC_exec.py
status=$?
if [ "$status" -gt 0 ]
then
   cat /tmp/cronjob_daemonCricr.log >> /home/ricr/MCQA/Dc.jam
fi

