#!/usr/bin/python
# python script that identifies egslog, in a specific directory, and executes a series of commands if the tarfile is newer than the last run of the script
# The main funcitonof the script is to initiate Monte Carlo simulations using DOSXYZnrc
#
#    Copyright [2016] [Rickard Cronholm] Licensed under the
#    Educational Community License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may
#    obtain a copy of the License at
#
#http://www.osedu.org/licenses/ECL-2.0
#
#    Unless required by applicable law or agreed to in writing,
#    software distributed under the License is distributed on an "AS IS"
#    BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#    or implied. See the License for the specific language governing
#    permissions and limitations under the License.
#

import os
import sys
import datetime
import shutil
import fnmatch
import time
import samcUtil
import re
import fileinput
import glob
import subprocess
import logging


def find(pattern, path, compareDir, exclude):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                if not (fnmatch.fnmatch(name, '*w*') or fnmatch.fnmatch(name, '*egsrun*')):
                    if name.find('_') > 0:
                        timeStamp = name[0:name.find('_')]
                        if os.path.exists(os.path.join(compareDir, timeStamp)):
                            if not exclude in root:
                                # check consistensy with beamDir
                                # get BEAMDIR
                                fb = open(os.path.join(timeStamp, timeStamp + '.beamDir'), 'r')
                                beamDir = fb.readline().rstrip()
                                fb.close()
                                if beamDir in root:
                                    result.append(os.path.join(root, name))
    return result
    
    
def locate(pattern, compareDir, replacee, replacer):
	files = glob.glob(pattern)
	files = [x for x in files if os.path.exists(os.path.join(x.split('/')[-1].split('_')[0], 
	         x.split('/')[-1].replace(replacee, replacer))) and not os.path.exists(os.path.join(x.split('/')[-1].split('_')[0],
	         x.split('/')[-1]))]
        return files
	

# get current time
now = datetime.datetime.now()
newTime = now.strftime("%y%m%d%H%M%S")

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# check if lock file exists, otherwise create it
lockFile = 'Dc.lock'
if os.path.isfile(lockFile):
    print 'Busy, quitting'
    sys.exit(0)
else:
    flock = open(lockFile, 'w')
    flock.write('Busy\n')
    flock.close()
    
# logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('daemonC')
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

# get variables from confFile
confFile = 'samc.conf'
with open(confFile) as f:
    confCont = f.readlines()
whatToGet = ['daemonC.timeFile', 'common.EGS_HOME', 'daemonC.dosxyznrc']
# generate struct
cv = samcUtil.struct()
# read variables
cv = samcUtil.getConfVars(cv, whatToGet, confCont)


# get time of last run
f = open(cv.timeFile, 'r')
oldTime = f.readline().rstrip()
print 'This was last run at {0}'.format(oldTime)
f.close()

# get list of egslst files
#fileList = find('*.egslst', cv.EGS_HOME, dname, cv.dosxyznrc)
fileList = locate(os.path.join(cv.EGS_HOME, cv.dosxyznrc, '*.egslst'), 
           dname, '.egslst', '.egsinp')
egslsts = []
# get time of modification of file
for i in range(0, len(fileList)):
    fileTime = os.path.getmtime(fileList[i])
    fileTime = time.localtime(fileTime)
    fileTime = time.strftime("%y%m%d%H%M%S", fileTime)
    # if more recent than last run, append to list
    if fileTime > oldTime:
        egslsts.append(fileList[i])

# quit if no egslst found
if len(egslsts) == 0:
    print 'Nothing to do, exiting'
    samcUtil.writeTimeToFile(cv.timeFile, newTime)
    os.remove(lockFile)  # remove lockFile
    sys.exit()

# in a for loop: addphsp, cleanup and initiate DOSXYZnrc simulation
for i in range(0, len(egslsts)):
    thisDir, thisFile = os.path.split(egslsts[i])
    thisSimulation, fileExtension = os.path.splitext(thisFile)
    timeStamp = thisSimulation[0:thisSimulation.find('_')]
    print 'timeStamp: ', timeStamp
    sys.stdout.flush()
    
    try:
        # get varaibles from local conf file
        confFile = os.path.join(timeStamp, timeStamp + '.conf')
        with open(confFile) as f:
            confCont = f.readlines()
        whatToGet = ['daemonC.nBatch', 'daemonC.dosPegs', 
        'daemonC.desiredUnc']
        # read variables
        cv = samcUtil.getConfVars(cv, whatToGet, confCont)
        # convert types
        cv = samcUtil.typeCast(cv, ['nBatch'], [int])
    
        # recompute ncase needed to reach uncert
        with open(egslsts[i]) as flst:
	        lst = flst.readlines()
        lookFor = 'average % error of doses >  0.500 of max dose ='
        unc = float([x for x in lst if x.strip().startswith(lookFor)][0].split('=')[-1].strip().strip('%\n'))
        # read original NCASE
        with open(egslsts[i].replace('.egslst', '.egsinp')) as finp:
	        inp = finp.readlines()
        ncaseLine = [x for x in inp if x.strip().endswith('NCASE etc')][0]
        ncaseOrig = float(ncaseLine.split(',')[0])
        ncase = (unc / cv.desiredUnc)**2 * ncaseOrig
        replaceLine = ','.join([str(int(ncase))] + [x for j, x in enumerate(ncaseLine.split(',')) if j > 0])
        # rewrite it
        for line in fileinput.input(egslsts[i].replace('.egslst', '.egsinp'), inplace=1):
            # set zeroairdose to 0 = off
            if line.rstrip().endswith(', zeroairdose etc'):
                line = '0' + line[1:]
            print line.replace(ncaseLine, replaceLine).rstrip()
        
        # move egslst to timeStampDir
        shutil.move(egslsts[i], os.path.join(dname, timeStamp))
    
        # clean up auxillary files
        removeFiles = glob.glob(os.path.join(cv.EGS_HOME, cv.dosxyznrc, 
        thisSimulation) + '*')
        removeFiles = [x for x in removeFiles if not x.endswith('.egsinp')]
        for name in removeFiles:
            os.remove(name)
    
        # initialize DOSXYZnrc simulation
        HEN_HOUSE = os.environ.get('HEN_HOUSE')
        exb = 'scripts/run_user_code_batch'
        exbCall = ''.join([HEN_HOUSE, exb])
        subprocess.call([exbCall, cv.dosxyznrc, thisSimulation, cv.dosPegs,
        '='.join(['p', str(cv.nBatch)])])
        #os.system('%(exbCall)s %(cv.dosxyznrc)s %(dosxyzFile)s %(cv.dosPegs)s p=%(str(cv.nBatch))s' % locals())
        
    except Exception as exc:
        hdlr = logging.FileHandler('.'.join([timeStamp, 'log']))
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.exception(exc)
        logger.handlers = []

# update time of last run
samcUtil.writeTimeToFile(cv.timeFile, newTime)

os.remove(lockFile)  # remove lockFile
