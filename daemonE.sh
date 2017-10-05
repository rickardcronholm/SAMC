#!/bin/sh

/usr/bin/python /home/mcqa/MCQA/daemonE_exec.py
status=$?

if [ "$status" -gt 0 ];
then
   cat /tmp/cronjob_daemonE.log >> /home/mcqa/MCQA/De.jam
fi

