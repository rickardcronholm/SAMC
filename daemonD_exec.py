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


def find(pattern, path, compareDir):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                if not (fnmatch.fnmatch(name, '*w*') or fnmatch.fnmatch(name, '*egsrun*')):
                    if name.find('_') > 0:
                        timeStamp = name[0:name.find('_')]
                        if os.path.exists(compareDir + timeStamp):
                            result.append(os.path.join(root, name))
    return result


# get current time
now = datetime.datetime.now()
newTime = now.strftime("%y%m%d%H%M%S")

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# check if lock file exists, otherwise create it
lockFile = 'Dd.lock'
if os.path.isfile(lockFile):
    print 'Busy, quitting'
    sys.exit(0)
else:
    flock = open(lockFile, 'w')
    flock.write('Busy\n')
    flock.close()

# get variables from confFile
confFile = 'samc.conf'
with open(confFile) as f:
        confCont = f.readlines()
whatToGet = ['daemonD.timeFile', 'common.EGS_HOME', 'common.dosxyzDir',
'common.VCUinp', 'common.postProcessor']
# generate struct
cv = samcUtil.struct()
# read variables
cv = samcUtil.getConfVars(cv, whatToGet, confCont)
'''
timeFile = samcUtil.getVariable(confFile,'daemonD.timeFile')
EGS_HOME = samcUtil.getVariable(confFile,'common.EGS_HOME')
dosxyznrc = samcUtil.getVariable(confFile,'common.dosxyzDir')
VCUinp = samcUtil.getVariable(confFile,'common.VCUinp')
postProcessor = samcUtil.getVariable(confFile,'common.postProcessor')
logFile = samcUtil.getVariable(confFile,'daemonD.logFile')
'''

# get time of last run
f = open(cv.timeFile, 'r')
oldTime = f.readline().rstrip()
print 'This was last run at {0}'.format(oldTime)
f.close()

# get list of 3ddose files
dosefile = []
timeStamps = []
for file in [dosefileList for dosefileList in os.listdir(os.path.join(cv.EGS_HOME,cv.dosxyzDir)) if dosefileList.endswith(".3ddose")]:
        # get time of modification of file
        fileTime = os.path.getmtime(cv.dosxyzDir + file)
        fileTime = time.localtime(fileTime)
        fileTime = time.strftime("%y%m%d%H%M%S", fileTime)
        #print file
        #print fileTime
        # if more recent than last run, append to list
        if fileTime > oldTime:
            if file.find('_') > 0:
                timeStamp = file[0:file.find('_')]
                if os.path.exists(timeStamp):
                    dosefile.append(file)
                    timeStamps.append(timeStamp)
                    #print file

# quit if no 3ddose file found
if len(dosefile) == 0:
    print 'Nothing to do, exiting'
    samcUtil.writeTimeToFile(cv.timeFile, newTime)
    os.remove(lockFile)  # remove lockFile
    sys.exit()

time.sleep(60)
# in a for loop: copy to timeStamp, cleanup and scp to post processor
for i in range(0, len(dosefile)):

    shutil.copy2(cv.dosxyzDir + dosefile[i], os.path.join(dname, timeStamps[i]))

    # compare number of 3ddose and DOSXYZnrc.egsinp in timeStamp and continue if equal
    egsinp = []
    threeDdose = []
    myDir = os.path.join(dname, timeStamps[i]) + os.path.sep
    for file in [fileList for fileList in os.listdir(myDir) if fileList.endswith(".3ddose")]:
        threeDdose.append(file)
    for file in [fileList for fileList in os.listdir(myDir) if fileList.endswith("DOSXYZnrc.egsinp")]:
        egsinp.append(file)

    if len(egsinp) == len(threeDdose) and len(egsinp) > 0:
        print 'timeStamp: ', timeStamp
        sys.stdout.flush()
        print len(egsinp)
        # create tarfile
        tarfileName = os.path.join(dname,
        'postSim' + timeStamps[i] + '.tar')
        thisTar = tarfile.open(tarfileName, 'w')
        tarfiles = []
        tarTypes = [os.path.join(timeStamps[i], '*.3ddose'),
        os.path.join(timeStamps[i], '*.egslst')]
        for name in tarTypes:
            tarfiles.append(glob.glob(name))
        tarfiles = samcUtil.flatten(tarfiles)
        #tarfiles = glob.glob(os.path.join(timeStamps[i], '*.3ddose'))
        #egsTarFiles = glob.glob(os.path.join(timeStamps[i], '*.egslst'))
        #for name in egsTarFiles:
        #    tarfiles.append(name)
        for name in tarfiles:
            thisTar.add(name)
        thisTar.close()
        recipient = os.path.sep.join([cv.postProcessor, timeStamps[i] + '.tar'])
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
        print recipient
        subprocess.call(['scp', tarfileName, recipient])

        # os.system('scp %(thisTar)s %(recipient)s' % locals())

        # clean up
        # get BEAMdir
        f = open(os.path.join(dname, timeStamps[i], 
        timeStamps[i] + '.beamDir'), 'r')
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
        #theseFiles = os.path.set.join([os.path.join(cv.EGS_HOME, beamDir),
        #timeStamps[i] + '*'])
        #os.system('rm %(theseFiles)s' % locals())
        removeTypes.append(os.path.join(cv.EGS_HOME, beamDir,
        timeStamps[i] + '*'))
        #VCUinp
        #theseFiles = os.path.sep.join([cv.VCUinp, timeStamps[i] + '*'])
        #os.system('rm %(theseFiles)s' % locals())
        removeTypes.append(os.path.sep.join([cv.VCUinp, timeStamps[i] + '*']))
        #DOSXYZnrc
        #theseFiles = os.path.sep.join([cv.dosxyzDir, timeStamps[i] + '*'])
        #os.system('rm %(theseFiles)s' % locals())
        removeTypes.append(os.path.sep.join([cv.dosxyzDir, timeStamps[i] + '*']))
        #MLCdir
        if os.path.isfile(os.path.join(timeStamp, timeStamp + '.mlcDir')):
            # theseFiles = os.path.sep.join([os.path.sep.join(cv.EGS_HOME, mlcDir),
            # timeStamps[i] + '*'])
            # os.system('rm %(theseFiles)s' % locals())
            removeTypes.append(os.path.sep.join([os.path.join(cv.EGS_HOME, mlcDir),
            timeStamps[i] + '*']))
        #thisDir
        #theseFiles = os.path.sep.join([dname, timeStamps[i] + '*'])
        removeTypes.append(os.path.sep.join([dname, timeStamps[i] + '*']))
        #os.system('rm -r %(theseFiles)s' % locals())
        theseFiles = os.path.sep.join([dname, 'postSim' + timeStamps[i] + '*'])
        removeTypes.append(os.path.sep.join([dname, 'postSim' +
        timeStamps[i] + '*']))
        #os.system('rm -r %(theseFiles)s' % locals())
        for name in removeTypes:
            removeFiles.append(glob.glob(name))
        removeFiles = samcUtil.flatten(removeFiles)
        for name in removeFiles:       
            try:
                os.remove(name)
            except OSError:
                shutil.rmtree(name)

    '''
    # write to log file
    if i==0:  # overwrite existing file
        flog = open(logFile,'w')
    else:  # append to file
        flog = open(logFile,'a')
    # get currentTime
    currTime = datetime.datetime.now()
    flog.write('{0}\t{1}\n'.format(timeStamp,currTime.strftime("%y%m%d%H%M%S")))
    flog.close()
    '''

# update time of last run
samcUtil.writeTimeToFile(cv.timeFile, newTime)

os.remove(lockFile)  # remove lockFile
