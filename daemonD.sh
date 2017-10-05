#!/bin/bash

/usr/bin/python /home/mcqa/MCQA/daemonD_exec.py
status=$?
if [ "$status" -gt 0 ]
then
   cat /tmp/cronjob_daemonDricr.log >> /home/mcqa/MCQA/Dd.jam
fi

