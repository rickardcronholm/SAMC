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
                                fb = open(os.path.join(timeStamp, timeStamp +
                                '.beamDir'), 'r')
                                beamDir = fb.readline().rstrip()
                                fb.close()
                                if beamDir in root:
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
lockFile = 'Dc.lock'
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
whatToGet = ['daemonC.timeFile', 'common.EGS_HOME', 'daemonC.dosxyznrc',
'daemonC.nBatch', 'daemonB.beamPegs', 'daemonC.ncaseMultiplier', 
'daemonC.dosPegs']
# generate struct
cv = samcUtil.struct()
# read variables
cv = samcUtil.getConfVars(cv, whatToGet, confCont)
# convert types
cv = samcUtil.typeCast(cv, ['nBatch'], [int])
nBatchBeam = int(samcUtil.getVariable(confFile, 'daemonB.nBatch'))
'''
timeFile = samcUtil.getVariable(confFile,'daemonC.timeFile')
EGS_HOME = samcUtil.getVariable(confFile,'common.EGS_HOME')
dosxyznrc = samcUtil.getVariable(confFile,'daemonC.dosxyznrc')
nBatch = int(samcUtil.getVariable(confFile,'daemonC.nBatch'))
dosPegs = samcUtil.getVariable(confFile,'daemonC.dosPegs')
beamPegs = samcUtil.getVariable(confFile,'daemonB.beamPegs')
ncaseMultiple = float(samcUtil.getVariable(confFile,'daemonC.ncaseMultiplier'))
logFile = samcUtil.getVariable(confFile,'daemonC.logFile')
nBatchBeam = int(samcUtil.getVariable(confFile,'daemonB.nBatch'))
'''
# get time of last run
f = open(cv.timeFile, 'r')
oldTime = f.readline().rstrip()
print 'This was last run at {0}'.format(oldTime)
f.close()

# get list of egslst files
fileList = find('*.egslst', cv.EGS_HOME, dname, cv.dosxyznrc)
egslogList = []
# get time of modification of file
for i in range(0, len(fileList)):
    try:
        fileTime = os.path.getmtime(fileList[i])
        fileTime = time.localtime(fileTime)
        fileTime = time.strftime("%y%m%d%H%M%S", fileTime)
        # if more recent than last run, append to list
        if fileTime > oldTime:
            egslogList.append(fileList[i])
    except OSError:
        pass

# quit if no egslog found
if len(egslogList) == 0:
    print 'Nothing to do, exiting'
    samcUtil.writeTimeToFile(cv.timeFile, newTime)
    os.remove(lockFile)  # remove lockFile
    sys.exit()

# in a for loop: addphsp, cleanup and initiate DOSXYZnrc simulation
for i in range(0, len(egslogList)):
    thisBeamDir, thisFile = os.path.split(egslogList[i])
    thisFile, fileExtension = os.path.splitext(thisFile)
    timeStamp = thisFile[0:thisFile.find('_')]
    print 'timeStamp: ', timeStamp
    sys.stdout.flush()

    # get number of batchJobs for thisFile
    dirList = os.listdir(thisBeamDir)
    batchJobs = 0
    for file1 in dirList:  # file the files
        if fnmatch.fnmatch(file1, thisFile + '*.IAEAphsp'):  # match the wildcard
            batchJobs += 1

    # addphsp
    addFile = os.path.join(thisBeamDir, thisFile)
    subprocess.call(['addphsp', addFile, addFile, str(batchJobs), '1', '1', '1'])
    #os.system('addphsp %(addFile)s %(addFile)s %(batchJobs)s 1 1 1' % locals())

    # check consistensy of checksum
    chksum = os.popen("./checksumTest.py %(addFile)s" % locals()).read().rstrip()
    if chksum == 'False':  #  rerun BEAM simulation
        removeFiles = []
        removeTypes = [addFile + '*_w*', addFile + '*phsp*',
        addFile + '*header']
        for name in removeTypes:
            removeFiles.append(glob.glob(name))
        for name in removeFiles:
            os.remove(name)
        '''
        removeFiles = addFile+'*_w*' # remove tempFiles
        os.system('rm %(removeFiles)s' % locals()) # cleanup
        removeFiles = addFile+'*phsp*' # remove phsp
        os.system('rm %(removeFiles)s' % locals()) # cleanup
        removeFiles = addFile+'*header' # remove header
        os.system('rm %(removeFiles)s' % locals()) # cleanup
        '''

        # get BEAMDIR
        fb = open(os.path.join(timeStamp, timeStamp + '.beamDir'), 'r')
        beamDir = fb.readline().rstrip()
        HEN_HOUSE = os.environ.get('HEN_HOUSE')
        exb = 'scripts/run_user_code_batch'
        exbCall = ''.join([HEN_HOUSE, exb])
        subprocess.call([exbCall, beamDir, thisFile, cv.beamPegs,
        '='.join(['p', str(cv.nBatchBeam)])])
        #os.system('%(exbCall)s %(beamDir)s %(thisFile)s %(cv.beamPegs)s p=%(cv.nBatchBeam)s' % locals())

        # log files for which checksum != filesize
        fchksum = open('chksum.log', 'a')
        fchksum.write('{0}\n'.format(timeStamp))
        fchksum.close()

        continue  # skip to next


    # if bs file found
    if os.path.isfile('/'.join([dname,timeStamp,thisFile+'.bs'])):
        # if phspType = 4 modify egsinp and rerun to get egs mode egslst
        with open('.'.join([addFile, 'egsinp'])) as inF:
            for line in inF:
                if 'phspType=4' in line:
                    oldWATCH = line.rstrip()
                    # syntesize new IWATCH line
                    newWATCH = '0, 0, 4, 1' + oldWATCH[oldWATCH.index('4')
                    + 1:len(oldWATCH)]
                    for line in fileinput.input('.'.join([addFile, 'egsinp']), inplace=1):
                        print line.replace(oldWATCH, newWATCH).rstrip()

                    # rerun simulation
                    # get BEAMDIR
                    fb = open(os.path.join(timeStamp, timeStamp +
                    '.beamDir'), 'r')
                    beamDir = fb.readline().rstrip()
                    HEN_HOUSE = os.environ.get('HEN_HOUSE')
                    ex = 'scripts/run_user_code'
                    exCall = ''.join([HEN_HOUSE, ex])
                    subprocess.call([exCall, beamDir, thisFile, cv.beamPegs])
                    #os.system('%(exCall)s %(beamDir)s %(thisFile)s %(cv.beamPegs)s' % locals())
                    break
        shutil.move('.'.join([addFile, 'egslst']),
        os.path.join(dname, timeStamp, ''))

    removeFiles = glob.glob(addFile + '*_w*')
    for name in removeFiles:
        os.remove(name)

    # initate DOSXYZnrc simulation
    dosxyzFile = thisFile[0:thisFile.rfind('_')] + '_DOSXYZnrc'
    # set medSurr to AIR
    lookup = 'AIR'
    f = open(os.path.sep.join([cv.EGS_HOME, cv.dosxyznrc, dosxyzFile + '.egsinp']),
    'r')
    for line in f:
        if re.search('phant', line):
            phant = line.rstrip()
            break
    f.close()

    with open(phant) as myPhant:
        for num, line in enumerate(myPhant, 1):
            if lookup in line:
                thisMed = num - 1

    for line in fileinput.input(os.path.sep.join([cv.EGS_HOME, cv.dosxyznrc,
    dosxyzFile + '.egsinp']), inplace=1):
        print line.replace("_medSurr_", str(thisMed)).rstrip()

    # multiply nCase
    print ''.join([addFile, '.1.IAEAheader'])
    lookup = 'PARTICLES:'
    breakNext = False
    f = open(''.join([addFile, '.1.IAEAheader']), 'r')
    for line in f:
        if breakNext:
            nPart = float(line.rstrip().lstrip())
            break
        if re.search(lookup, line):
            breakNext = True
    f.close()
    nCase = int(cv.ncaseMultiplier * nPart)
    for line in fileinput.input('/'.join([cv.EGS_HOME, cv.dosxyznrc,
    dosxyzFile + '.egsinp']), inplace=1):
        print line.replace("_ncase_", str(nCase)).rstrip()

    # initialize DOSXYZnrc simulation
    HEN_HOUSE = os.environ.get('HEN_HOUSE')
    exb = 'scripts/run_user_code_batch'
    exbCall = ''.join([HEN_HOUSE, exb])
    subprocess.call([exbCall, cv.dosxyznrc, dosxyzFile, cv.dosPegs,
    '='.join(['p', str(cv.nBatch)])])
    #os.system('%(exbCall)s %(cv.dosxyznrc)s %(dosxyzFile)s %(cv.dosPegs)s p=%(cv.nBatch)s' % locals())

# update time of last run
samcUtil.writeTimeToFile(cv.timeFile, newTime)

os.remove(lockFile)  # remove lockFile
