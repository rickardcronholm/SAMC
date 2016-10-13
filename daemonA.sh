#!/bin/sh

/usr/local/bin/python /home/mcqa/MCQA/daemonA_exec.py
status=$?

if [ "$status" -gt 0 ];
then
   cat /tmp/cronjob_daemonA.log >> /home/mcqa/MCQA/Da.jam
fi

