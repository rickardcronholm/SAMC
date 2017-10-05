#!/usr/bin/python
# python script that identifies RP files, their corresponding RD files (field dose) and moves them to a subdirectory named according to a timestamp
#
# python script for translating DICOM RP file to BEAMnrc/DOSXYZnrc input files applying DOSXYZnrc source 20
# input is full path to a DICOM RP file
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
import glob
import sys
import dicom
import datetime
import shutil
import time
import samcUtil
import CTC_auto
import DICOM2egsinp_s20
import subprocess
import tarfile
import copy
import logging


# get current time
now = datetime.datetime.now()
newTime = now.strftime("%y%m%d%H%M%S")

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# check if lock file exists, otherwise create it
lockFile = 'Da.lock'
if os.path.isfile(lockFile):
    print 'Busy, quitting'
    sys.exit(0)
else:
    flock = open(lockFile, 'w')
    flock.write('Busy\n')
    flock.close()

# logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('daemonA')
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

# get variables from confFile
confFile = 'samc.conf'
with open(confFile) as f:
    confCont = f.readlines()
whatToGet = ['daemonA.timeFile', 'convertScript.treatmentMachineLibrary',
'common.DICOMinDir', 'daemonA.clusterFrontEnd', 'daemonA.convertScript',
'common.RPfilePrefix', 'common.RDfilePrefix', 'common.RSfilePrefix',
'common.CTfilePrefix', 'common.DICOMfileEnding', 'daemonA.samcMove',
'daemonA.keepTrack']
# generate struct
cv = samcUtil.struct()
# read variables
cv = samcUtil.getConfVars(cv, whatToGet, confCont)
'''
treatmentMachineLibrary = samcUtil.getVariable(confFile,'convertScript.treatmentMachineLibrary')
DICOMinDir = samcUtil.getVariable(confFile,'common.DICOMinDir')
timeFile = samcUtil.getVariable(confFile,'daemonA.timeFile')
clusterFE = samcUtil.getVariable(confFile,'daemonA.clusterFrontEnd')
convertScript = samcUtil.getVariable(confFile,'daemonA.convertScript')
RPfilePrefix = samcUtil.getVariable(confFile,'common.RPfilePrefix')
RDfilePrefix = samcUtil.getVariable(confFile,'common.RDfilePrefix')
RSfilePrefix = samcUtil.getVariable(confFile,'common.RSfilePrefix')
CTfilePrefix = samcUtil.getVariable(confFile,'common.CTfilePrefix')
DICOMfileEnding = samcUtil.getVariable(confFile,'common.DICOMfileEnding')
includeCouch = samcUtil.getVariable(confFile,'CTC_askAuto.includeCouch')
samcMove = samcUtil.getVariable(confFile,'daemonA.samcMove')
logFile = samcUtil.getVariable(confFile,'daemonA.logFile')
kt = samcUtil.getVariable(confFile,'daemonA.keepTrack')
'''

# check connectivity to cluster front end
clusterIP = cv.clusterFrontEnd.split(':')[0].split('@')[-1]
if not samcUtil.isOpen(clusterIP):
    with open('daemonA.log', 'a') as flock:
        flock.write('daemonA not able to connect to cluster')
    os.remove(lockFile)
    sys.exit(0)

# check if DICOMinDir exists, otherwise create it
if not os.path.exists(cv.DICOMinDir):
    os.makedirs(cv.DICOMinDir)

# check that DICOMinDir is constant
#new = glob.glob(os.path.join(cv.DICOMinDir, '*'))
new = sum(os.path.getsize(os.path.join(cv.DICOMinDir,f)) for f in os.listdir(cv.DICOMinDir) 
if os.path.isfile(os.path.join(cv.DICOMinDir,f)))
while True:
    print 'sleeping'
    time.sleep(60)
    old = copy.deepcopy(new)
    #new = glob.glob(os.path.join(cv.DICOMinDir, '*'))
    new = sum(os.path.getsize(os.path.join(cv.DICOMinDir,f)) 
    for f in os.listdir(cv.DICOMinDir) if os.path.isfile(os.path.join(cv.DICOMinDir,f)))
    if new == old:
        break

# get time of last run
f = open(cv.timeFile, 'r')
oldTime = f.readline().rstrip()
print 'This was last run at {0}'.format(oldTime)
f.close()


# get list of RPfiles
RPfiles = []
for file in [RPfileList for RPfileList in os.listdir(cv.DICOMinDir) if RPfileList.endswith(cv.DICOMfileEnding) and RPfileList.startswith(cv.RPfilePrefix)]:
    # get time of modification of file
    fileTime = os.path.getmtime(cv.DICOMinDir + file)
    fileTime = time.localtime(fileTime)
    fileTime = time.strftime("%y%m%d%H%M%S", fileTime)
    # if more recent than last run, append to list
    if fileTime > oldTime:
        RPfiles.append(file)

print 'Found {0} RPfile(s)'.format(len(RPfiles))
# quit if no RP files found
if len(RPfiles) == 0:
    print 'Nothing to do, exiting'
    samcUtil.writeTimeToFile(cv.timeFile, newTime)
    # clear DICOMinDir
    #delStr = DICOMinDir+'/*'+DICOMfileEnding
    #os.system('rm %(delStr)s' %locals())
    os.remove(lockFile)  # remove lockFile
    sys.exit(0)

# For each RP file, get corresponding RD file(s)
for i in range(0, len(RPfiles)):
    time.sleep(3) # just to ensure unique timestamps
    # get timestamp
    now = datetime.datetime.now()
    timeStamp = now.strftime("%y%m%d%H%M%S")
    print 'timeStamp: ',timeStamp
    sys.stdout.flush()

    try:

        RP = dicom.read_file(cv.DICOMinDir + RPfiles[i])
        # get SOPInstanceUID
        planSOP = RP.SOPInstanceUID

        # validate plan
        valid = samcUtil.validateRP(RP)
        if not valid:
            print 'Invalid RP'
            #continue # skip to next RP
        else:
            print 'Valid RP'

        # find RDs for the current RP
        RDfiles = []
        for file in [fileList for fileList in os.listdir(cv.DICOMinDir) if fileList.endswith(cv.DICOMfileEnding) and fileList.startswith(cv.RDfilePrefix)]:
            RDfiles.append(file)
        myRDs = []
        fieldRDs = []
        planRDs = []
        # append to list if the RD referrs to SOPInstanceUID
        for j in range(0, len(RDfiles)):
            RD = dicom.read_file(cv.DICOMinDir + RDfiles[j],
                 stop_before_pixels=True)
            if (planSOP == RD.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID):
                try:
                    beam = float(RD.ReferencedRTPlanSequence[0].ReferencedFractionGroupSequence[0].ReferencedBeamSequence[0].ReferencedBeamNumber)
                except AttributeError:
                    beam = 0
                if (beam > 0):
                    fieldRDs.append(RDfiles[j])
                else:
                    planRDs.append(RDfiles[j])

        if len(planRDs) == 0 and len(fieldRDs) == 0:
            print 'No RD file found, skipping RP'
            valid = False

        # if planDose found, use it otherwise use fieldDose and remove others
        if len(planRDs) == 1:
            myRDs = planRDs
            for j in range(0, len(fieldRDs)):
                os.remove(cv.DICOMinDir + fieldRDs[j])
        else:
            myRDs = fieldRDs
            for j in range(0, len(planRDs)):
                os.remove(cv.DICOMinDir + planRDs[j])

        # check if CTs and RS correlated to the RP exists, if so create egsphant
        createPhant = False # flag determining weather to generate an egsphant or not
        CTfiles = []
        for file in [fileList for fileList in os.listdir(cv.DICOMinDir) if fileList.endswith(cv.DICOMfileEnding) and fileList.startswith(cv.CTfilePrefix)]:
            CTfiles.append(file)
        myCTs = []
        # append to list if the CT referrs to RP.StudyInstanceUID
        for j in range(0, len(CTfiles)):
            CT = dicom.read_file(cv.DICOMinDir + CTfiles[j],
            stop_before_pixels=True)
            if (RP.FrameOfReferenceUID == CT.FrameOfReferenceUID):
                myCTs.append(CTfiles[j])
        CTfiles = myCTs
        if len(CTfiles) > 0:
            createPhant = True
        else:
            myRSs = []

        recycle = 0
        if createPhant:
            CT = dicom.read_file(cv.DICOMinDir + CTfiles[0])
            RPRDfile = cv.DICOMinDir + timeStamp + 'RPRD.txt'
            RSfileOut = cv.DICOMinDir + timeStamp + 'RS.txt'
            CTsliceListFile = cv.DICOMinDir + timeStamp + 'CTs.txt'
            # generate the RPRDfile
            f = open(RPRDfile, 'w')
            f.write('{0}{1}\n'.format(cv.DICOMinDir, RPfiles[i]))
            try:
                f.write('{0}{1}\n'.format(cv.DICOMinDir, myRDs[0]))
            except IndexError:
                pass
            f.close()

            # get RS file that corresponds to the RP
            RSfiles = []
            for file in [fileList for fileList in os.listdir(cv.DICOMinDir) if fileList.endswith(cv.DICOMfileEnding) and fileList.startswith(cv.RSfilePrefix)]:
                RSfiles.append(file)
            myRSs = []
            # append to list if the RP referrs to RS
            for j in range(0, len(RSfiles)):
                RS = dicom.read_file(cv.DICOMinDir + RSfiles[j],
                stop_before_pixels=True)
                if (RP.ReferencedStructureSetSequence[0].ReferencedSOPInstanceUID == RS.SOPInstanceUID):
                    myRSs.append(RSfiles[j])
            try:
                RSfile = myRSs[0]
            except IndexError:
                RSfile = ''

            # generate the RSfile
            f = open(RSfileOut, 'w')
            f.write('{0}{1}\n'.format(cv.DICOMinDir, RSfile))
            f.close()
            # generate the CTsliceListFile
            f = open(CTsliceListFile, 'w')
            for j in range(0,len(CTfiles)):
                f.write('{0}{1}\n'.format(cv.DICOMinDir, CTfiles[j]))
            f.close()

            # generate the phanton
            if len(myRSs) > 0 and valid:
                CTC_auto.main(RPRDfile, RSfileOut, CTsliceListFile, timeStamp, [
                    'BOLUS', 'NONE', 'CAVITY', 'CONTROL', 'AVOIDANCE', 'CONTRAST AGENT', 'DOSE_REGION', 'CTV'],
                    ['onlyWater.dat', '21media+TIT.dat', '21media+TIT.dat',
                    '21mediaNoCouch+AU.dat', '21media+TIT.dat', '21media+TIT.dat', '21media+TIT.dat',
                    '21mediaNoCouch+AU.dat'])

                # cleanup
                # check for recycling here and delete iff recycling not called for
                if i + 1 < len(RPfiles):
                    recycle = samcUtil.recycleCTandRS(CT.FrameOfReferenceUID,
                    cv.DICOMinDir, RPfiles[i + 1:len(RPfiles)])
                else:
                    recycle = 0
                if recycle == 0:
                    # os.remove(DICOMinDir+RSfile)
                    samcUtil.remove(cv.DICOMinDir, CTfiles)

            # remove textfiles used by CTC_ask
            for fl in glob.glob(cv.DICOMinDir + timeStamp + "*"):
                os.remove(fl)

        # remove files if failed during phantom creation
        if createPhant and not os.path.isfile(timeStamp+'.egs4phant'):
            print 'Failed during phantom generation. Quitting'    
            valid = False

        # remove all DICOM files if invalid
        # (invalid plan, missing dose, failed phantom creation)
        if not valid:
            samcUtil.remove(cv.DICOMinDir, RPfiles[i])  # RP
            samcUtil.remove(cv.DICOMinDir, myRDs)  # RD
            samcUtil.remove(cv.DICOMinDir, myRSs)  # RS
            samcUtil.remove(cv.DICOMinDir, myCTs)  # CT    
            continue  # skip to next RP

        # create directory
        if not os.path.exists(timeStamp):
            os.makedirs(timeStamp)

        # move files to $timeStamp directory
        # shutil.copy2(thisDir + RPfiles[i], timeStamp)
        shutil.move(cv.DICOMinDir + RPfiles[i], timeStamp)
        for j in range(len(myRDs)):
            shutil.move(cv.DICOMinDir + myRDs[j], timeStamp)
        if createPhant and len(myRSs) > 0:
            shutil.copy(cv.DICOMinDir + myRSs[0], timeStamp)

        # initiate conversion to MC input files + utility files
        currRPfile = os.path.sep.join([timeStamp, RPfiles[i]])
        numDoseFiles = len(myRDs)
        DICOM2egsinp_s20.main(currRPfile, timeStamp, numDoseFiles)

        # change referenced egs4phant if phantom was created
        if createPhant:
            defaultPhant = samcUtil.getVariable(confFile, 'convertScript.egsPhant')
            specificPhant = timeStamp + '.egs4phant'
            cmd = "sed -i 's/"+defaultPhant+"/"+specificPhant+"/g' "+timeStamp+"/"+timeStamp+"*DOSXYZnrc.egsinp"
            os.system(str(cmd))

        '''
        if os.path.isfile(''.join([timeStamp,'/',timeStamp,'.keepTrack'])):
            thisKT = ''.join([timeStamp,'/',timeStamp,'.keepTrack'])
            if i == 0:  # overwrite existing file
                os.remove(cv.keepTrack)
            os.system('cat %(thisKT)s >> %(kt)s' %locals())
        '''
        # Copy samc.conf to instance specific conf
        shutil.copy(confFile, os.path.join(timeStamp,timeStamp+'.conf'))

        # tar files
        tarTypes = [os.path.sep.join([timeStamp, timeStamp + '*'])]
        tarFiles = []
        for name in tarTypes:
            tarFiles.append(glob.glob(name))
        tarFiles = samcUtil.flatten(tarFiles)
        tarFileName = ''.join(['preSim', timeStamp, '.tar'])
        tar = tarfile.open(tarFileName, 'w')
        for name in tarFiles:
            tar.add(name)
        tar.close()
        recipient = os.path.sep.join([cv.clusterFrontEnd, timeStamp + '.tar'])
        #os.system('tar cf %(tarFileName)s %(tarFiles)s' %locals())

        # scp to cluster front end
        # os.system('scp %(tarFileName)s %(recipient)s' %locals())
        subprocess.call(['scp', tarFileName, recipient])
        # delete tar file
        os.remove(tarFileName)

        # remove DICOM files from DICOMinDir
        samcUtil.remove(cv.DICOMinDir, RPfiles[i])  # RP
        samcUtil.remove(cv.DICOMinDir, myRDs)  # RD
        if recycle == 0:
            samcUtil.remove(cv.DICOMinDir, myRSs)  # RS
            samcUtil.remove(cv.DICOMinDir, myCTs)  # CT
        else:
            print 'Not removing CT+RS due to recycling'

    except Exception as exc:
        hdlr = logging.FileHandler('.'.join([timeStamp, 'log']))
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.exception(exc)
        logger.handlers = []

# update time of last run
samcUtil.writeTimeToFile(cv.timeFile, newTime)

# remove lockFile
os.remove(lockFile)
