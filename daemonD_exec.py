#!/usr/bin/python
# python script that identifies 3ddose files, in a specific directory, and executes a series of commands if files are newer than the last run of the script
# The main funciton of the script is to send 3ddose files to post processing unit and perform cleanup
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
import tarfile
import glob
import subprocess
import fileinput
import logging


def find(pattern, path, compareDir):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                if not (fnmatch.fnmatch(name, '*w*') or fnmatch.fnmatch(name, '*egsrun*')):
                    if name.find('_') > 0:
                        timeStamp = name[0:name.find('_')]
                        if os.path.exists(compareDir + timeStamp):
                            result.append(os.path.sep.join(root, name))
    return result
    

def locate(pattern, compareDir, replacee, replacer):
	files = glob.glob(pattern)
	files = [x for x in files if os.path.exists(os.path.join(x.split('/')[-1].split('_')[0], 
	         x.split('/')[-1].replace(replacee, replacer)))]
        return files


# sleep 10 seconds so that Dc proceeds
time.sleep(10)

# get current time
now = datetime.datetime.now()
newTime = now.strftime("%y%m%d%H%M%S")

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# check if lock file exists, otherwise create it
lockFile = 'Dd.lock'
# in order not to clash with Dc, we also check that Dc is not running
lockCheck = [lockFile, 'Dc.lock']
lock = list(set([os.path.isfile(x) for x in lockCheck]))
if len(lock) > 1 or lock[0]:
	# print 'Busy, quitting'
	sys.exit(0)
else:
    flock = open(lockFile, 'w')
    flock.write('Busy\n')
    flock.close()

# logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('daemonD')
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

# get variables from confFile
confFile = 'samc.conf'
with open(confFile) as f:
        confCont = f.readlines()
whatToGet = ['daemonD.timeFile', 'common.EGS_HOME', 'common.dosxyzDir',
'common.postProcessor']
# generate struct
cv = samcUtil.struct()
# read variables
cv = samcUtil.getConfVars(cv, whatToGet, confCont)

# check connectivity to cluster front end
postProcessIP = cv.postProcessor.split(':')[0].split('@')[-1]
if not samcUtil.isOpen(postProcessIP):
    with open('daemonD.log', 'a') as flock:
        flock.write('daemonD not able to connect to post processer')
    os.remove(lockFile)
    sys.exit(0)

# get time of last run
f = open(cv.timeFile, 'r')
oldTime = f.readline().rstrip()
print 'This was last run at {0}'.format(oldTime)
f.close()

# get list of 3ddose files
dosefile = []
timeStamps = []
fileList = locate(os.path.join(cv.EGS_HOME, cv.dosxyzDir, '*.3ddose'), 
           dname, '.3ddose', '.egslst')
for file in fileList:
    
    # get time of modification of file
    fileTime = os.path.getmtime(file)
    fileTime = time.localtime(fileTime)
    fileTime = time.strftime("%y%m%d%H%M%S", fileTime)
    #print file
    #print fileTime
    # if more recent than last run, append to list
    if fileTime > oldTime:
        dosefile.append(os.path.basename(file))
        timeStamps.append(os.path.basename(file).split('_')[0])

# quit if no 3ddose file found
if len(dosefile) == 0:
    print 'Nothing to do, exiting'
    samcUtil.writeTimeToFile(cv.timeFile, newTime)
    os.remove(lockFile)  # remove lockFile
    sys.exit()

time.sleep(15)
# in a for loop: copy to timeStamp, cleanup and scp to post processor
for i in range(0, len(dosefile)):

    timeStamp = timeStamps[i]
    try:
        shutil.copy2(cv.dosxyzDir + dosefile[i], os.path.join(dname, timeStamp))
    
        # if bs file found
        if os.path.isfile('/'.join([dname,timeStamp,
        dosefile[i].replace('DOSXYZnrc', 'BEAMnrc').replace('3ddose', 'bs')])):
            # get BEAMdir
            f = open(os.path.join(timeStamp, timeStamp + '.beamDir'), 'r')
            beamDir = f.readline().rstrip()
            f.close()
            # locate corresponding BEAM simulation
            beamSimulation = os.path.splitext(dosefile[i])[0].replace('DOSXYZnrc', 'BEAMnrc')
            if not os.path.isfile(os.path.join(dname, timeStamp, 
            beamSimulation + '.egslst')):
                for line in fileinput.input(os.path.join(cv.EGS_HOME, beamDir,
                beamSimulation + '.egsinp'), inplace=1):
                    if line.find('IWATCH') > 0:
                        lineData = line.split(',')
                        lineData[2] = ' 4'
                        line = ','.join(lineData)
                    print line.rstrip()
                # get varaibles from local conf file
                confFile = os.path.join(timeStamp, timeStamp + '.conf')
                with open(confFile) as f:
                    confCont = f.readlines()
                whatToGet = ['daemonC.beamPegs']
                # read variables
                cv = samcUtil.getConfVars(cv, whatToGet, confCont)
                # restart simulation
                HEN_HOUSE = os.environ.get('HEN_HOUSE')
                ex = 'scripts/run_user_code'
                exCall = ''.join([HEN_HOUSE, ex])
                print beamSimulation
                subprocess.call([exCall, beamDir, beamSimulation, cv.beamPegs])
                # copy BEAM simulation to timeStamp
                shutil.copy(os.path.join(cv.EGS_HOME, beamDir,
                beamSimulation + '.egslst'), os.path.join(dname, timeStamp))
 

        # compare number of 3ddose and DOSXYZnrc.egsinp in timeStamp and continue if equal
        egsinp = []
        threeDdose = []
        myDir = os.path.join(dname, timeStamp) + os.path.sep
        for file in [fileList for fileList in os.listdir(myDir) if fileList.endswith(".3ddose")]:
            threeDdose.append(file)
        for file in [fileList for fileList in os.listdir(myDir) if fileList.endswith("DOSXYZnrc.egsinp")]:
            egsinp.append(file)

        if len(egsinp) == len(threeDdose) and len(egsinp) > 0:
            print 'timeStamp: ', timeStamp
            sys.stdout.flush()
            print len(egsinp)
            thisTarFile = os.path.join(dname,
            'postSim' + timeStamp + '.tar')
            # create tarfile
            thisTar = tarfile.open(thisTarFile, 'w')
            tarfiles = []
            tarTypes = ['*'.join([timeStamp + os.path.sep, '.3ddose']),
            '*'.join([timeStamp + os.path.sep , '*BEAM*.egslst'])]
            print tarTypes
            for name in tarTypes:
                tarfiles.append(glob.glob(name))
            #tarfiles = glob.glob(os.path.sep.join(timeStamps[i], '*.3ddose'))
            #egsTarFiles = glob.glob(os.path.sep.join(timeStamps[i], '*.egslst'))
            #for name in egsTarFiles:
            #    tarfiles.append(name)
            tarfiles = samcUtil.flatten(tarfiles)
            for name in tarfiles:
                thisTar.add(name)
            thisTar.close()
            recipient = os.path.join(cv.postProcessor, timeStamp + '.tar')
            '''
            thisTar = dname+'/postSim'+timeStamps[i]+'.tar'
            recipient = ''.join([cv.postProcessor,'/',timeStamps[i],'.tar'])
            theseFiles = timeStamps[i]+'/*.3ddose'
            theseEgslst = timeStamps[i]+'/*.egslst'
            tarCheck = os.system('tar cf %(thisTar)s %(theseFiles)s %(theseEgslst)s' % locals())
            if not tarCheck == 0:
                os.system('tar cf %(thisTar)s %(theseFiles)s' % locals())
            '''

            # scp
            subprocess.call(['scp', thisTarFile, recipient])
            # os.system('scp %(thisTar)s %(recipient)s' % locals())

            # clean up
            # get BEAMdir
            f = open(os.path.join(dname, timeStamp, timeStamp +
            '.beamDir'), 'r')
            beamDir = f.readline().rstrip()
            f.close()

            # get MLCdir
            if os.path.isfile(os.path.join(timeStamp, timeStamp + '.mlcDir')):
                f = open(os.path.join(timeStamp, timeStamp + '.mlcDir'), 'r')
                mlcDir = f.readline().rstrip()
                f.close()

            removeFiles = []
            removeTypes = []
            #BEAMdir
            #theseFiles = os.path.sep.join([os.path.sep.join(cv.EGS_HOME, beamDir),
            #timeStamps[i] + '*'])
            #os.system('rm %(theseFiles)s' % locals())
            removeTypes.append(os.path.sep.join([cv.EGS_HOME, beamDir,
            timeStamp + '*']))
            #DOSXYZnrc
            #theseFiles = os.path.sep.join([cv.dosxyzDir, timeStamps[i] + '*'])
            #os.system('rm %(theseFiles)s' % locals())
            removeTypes.append(os.path.sep.join([cv.dosxyzDir, timeStamp + '*']))
            #MLCdir
            if os.path.isfile(os.path.join(timeStamp, timeStamp + '.mlcDir')):
                # theseFiles = os.path.sep.join([os.path.sep.join(cv.EGS_HOME, mlcDir),
                # timeStamps[i] + '*'])
                # os.system('rm %(theseFiles)s' % locals())
                removeTypes.append(os.path.sep.join([os.path.join(cv.EGS_HOME, mlcDir),
                timeStamp + '*']))
            #thisDir
            #theseFiles = os.path.sep.join([dname, timeStamps[i] + '*'])
            removeTypes.append(os.path.sep.join([dname, timeStamp + '*']))
            #os.system('rm -r %(theseFiles)s' % locals())
            #theseFiles = os.path.sep.join([dname, 'postSim' + timeStamps[i] + '*'])
            removeTypes.append(os.path.sep.join([dname, 'postSim' +
            timeStamp + '*']))
            #os.system('rm -r %(theseFiles)s' % locals())
            for name in removeTypes:
                removeFiles.append(glob.glob(name))
            for name in samcUtil.flatten(removeFiles):
                try:
                    os.remove(name)
                except OSError:
                    shutil.rmtree(name)
                
    except Exception as exc:
        hdlr = logging.FileHandler('.'.join([timeStamp, 'log']))
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.exception(exc)
        logger.handlers = []

# update time of last run
samcUtil.writeTimeToFile(cv.timeFile, newTime)

os.remove(lockFile)  # remove lockFile
