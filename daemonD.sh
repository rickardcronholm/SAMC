#!/bin/bash

/usr/local/bin/python /home/ricr/MCQA/daemonD_exec.py
status=$?
if [ "$status" -gt 0 ]
then
   cat /tmp/cronjob_daemonDricr.log >> /home/ricr/MCQA/Dd.jam
fi

