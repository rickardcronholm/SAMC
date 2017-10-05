#!/bin/bash

export EGS_HOME=/home/mcqa/EGSnrc/EGS_HOME/
export EGS_CONFIG=/home/mcqa/EGSnrc/HEN_HOUSE/specs/linux64.conf

source /home/mcqa/EGSnrc/HEN_HOUSE/scripts/egsnrc_bashrc_additions

export EGS_BATCH_OPTIONS=pbs
export EGS_BATCH=pbs
export EGS_BATCH_SYSTEM=pbs


/usr/bin/python /home/mcqa/MCQA/daemonC_exec.py
status=$?
if [ "$status" -gt 0 ]
then
   cat /tmp/cronjob_daemonCricr.log >> /home/mcqa/MCQA/Dc.jam
fi

