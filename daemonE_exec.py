#!/usr/bin/python
# python script that identifies tar files; unpacks, converts 3ddose to DICOM and stores using new UIDs
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
import dicom
import datetime
import shutil
import time
import samcUtil
import numpy as np
import glob
import tarfile
import subprocess
import logging

# get current time
now = datetime.datetime.now()
newTime = now.strftime("%y%m%d%H%M%S")

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# sleep 60 s
time.sleep(60)

# check if lock file exists, otherwise create it
lockFile = 'De.lock'
if os.path.isfile(lockFile):
    print 'Busy, quitting'
    sys.exit(0)
else:
    flock = open(lockFile, 'w')
    flock.write('Busy\n')
    flock.close()

# logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('daemonE')
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

# get variables from confFile
confFile = 'samc.conf'
with open(confFile) as f:
        confCont = f.readlines()
whatToGet = ['daemonE.timeFile', 'common.RPfilePrefix', 'common.RDfilePrefix',
'common.DICOMfileEnding', 'daemonE.lblSuffix', 'common.DICOMoutDir',
'daemonE.windowSize']
# generate struct
cv = samcUtil.struct()
# read variables
cv = samcUtil.getConfVars(cv, whatToGet, confCont)
outsideMaterial = 'AIR700OUT'

# get time of last run
f = open(cv.timeFile, 'r')
oldTime = f.readline().rstrip()
print 'This was last run at {0}'.format(oldTime)
f.close()

# check if DICOMoutDir exists, otherwise exit
if not os.path.exists(cv.DICOMoutDir):
    print 'Not able to connect to DICOMoutDir'
    # do not update timeFile
    os.remove(lockFile)  # remove lockFile
    fid = open(lockFile.replace('.lock', '.jam'), 'w')
    fid.write('Not able to connect to DICOMoutDir\n')
    fid.close()
    sys.exit(0)

# get list of tarfiles
tarfiles = []
for file in [tarfileList for tarfileList in os.listdir(dname) if tarfileList.endswith(".tar") and not tarfileList.startswith("pre")]:
    if not file.startswith("preSim") and not file.startswith("backup"):
        # get time of modification of file
        fileTime = os.path.getmtime(os.path.sep.join([dname, file]))
        fileTime = time.localtime(fileTime)
        fileTime = time.strftime("%y%m%d%H%M%S", fileTime)
        # if more recent than last run, append to list
        if fileTime > oldTime:
            tarfiles.append(file)


print 'Found {0} tarfile(s)'.format(len(tarfiles))
# quit if no tar files found
if len(tarfiles) == 0:
    print 'Nothing to do, exiting'
    samcUtil.writeTimeToFile(cv.timeFile, newTime)
    os.remove(lockFile)  # remove lockFile
    sys.exit(0)

# for each tar file do the loop
for i in range(0, len(tarfiles)):
    # get timeStamp
    timeStamp = os.path.splitext(tarfiles[i])[0]

    print 'timeStamp: ', timeStamp
    sys.stdout.flush()

    try:
        # untar
        thisTarFile = tarfiles[i]
        tar = tarfile.open(tarfiles[i])
        tar.extractall()
        tar.close()
        os.remove(tarfiles[i])

        # modify RP file
        # get list of RPfiles
        RPfiles = []
        for file in [RPfileList for RPfileList in os.listdir(os.path.sep.join([dname, timeStamp])) if RPfileList.endswith(cv.DICOMfileEnding) and RPfileList.startswith(cv.RPfilePrefix)]:
            RPfiles.append(file)

        # len RPfiles should be only one
        # For each RP file, get corresponding RD file(s)
        for n in range(0, len(RPfiles)):
            addDoses = 0  # set initial value
            # read DICOM RP
            RP = dicom.read_file(os.path.join(dname, timeStamp, RPfiles[n]))
            # get SOPInstanceUID
            planSOP = RP.SOPInstanceUID

            # get PatientPosition
            PatientPosition = RP.PatientSetupSequence[0].PatientPosition

            # Create modified DICOM from shell
            newRP = samcUtil.rewriteRP(RP, cv.lblSuffix)
            newSOP = newRP.SOPInstanceUID
            fileNameOut = os.path.sep.join([dname, timeStamp,
            ''.join([cv.RPfilePrefix, cv.lblSuffix, '.', timeStamp,
            cv.DICOMfileEnding])])
            newRP.save_as(fileNameOut)
            shutil.copy2(fileNameOut,cv.DICOMoutDir) # copy file to DICOMoutDir
            #subprocess.call(['sudo', cv.samcCopy, fileNameOut, cv.DICOMoutDir])
            #os.system('sudo %(samcCopy)s %(fileNameOut)s %(DICOMoutDir)s' %locals())

            # get corresponding RDs
            RDfiles = []
            for file in [fileList for fileList in os.listdir(os.path.sep.join([dname, timeStamp])) if fileList.endswith(cv.DICOMfileEnding) and fileList.startswith(cv.RDfilePrefix)]:
                RDfiles.append(file)

            myRDs = []
            fieldRDs = []
            planRDs = []
            # append to list if the RD referrs to SOPInstanceUID
            for j in range(0,len(RDfiles)):
                RD = dicom.read_file(os.path.join(dname, timeStamp, RDfiles[j]),
                stop_before_pixels=True)
                if (planSOP==RD.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID):
                    try:
                        beam = float(RD.ReferencedRTPlanSequence[0].ReferencedFractionGroupSequence[0].ReferencedBeamSequence[0].ReferencedBeamNumber)
                    except AttributeError:
                        beam = 0
                    if (beam > 0):
                        fieldRDs.append(RDfiles[j])
                    else:
                        planRDs.append(RDfiles[j])

            # if planDose found, use it otherwise use fieldDose
            if len(planRDs) == 1:
                myRDs = planRDs
            else:
                myRDs = fieldRDs

            # get correspondance list
            # get beams, that are 'TREATMENT'
            beams, corrBeams = samcUtil.getBeams(RP)
            nomEnfluMod = samcUtil.getEnFlu(RP, corrBeams)

            addDoses = 0
            # get number of 3ddose files
            MCdoses = glob.glob(os.path.sep.join([timeStamp, timeStamp +
            '*3ddose']))
            for j in range(0, len(MCdoses)):
                if len(myRDs) == 1:
                    thisRD = os.path.sep.join([dname, timeStamp, myRDs[0]])
                elif len(myRDs) == len(MCdoses):
                    thisRD = os.path.sep.join([dname, timeStamp, myRDs[j]])

                print thisRD
                RD = dicom.read_file(thisRD)
                if len(myRDs) > 1:
                    #get corrBeam of current RD
                    iamBeam = int(RD.ReferencedRTPlanSequence[0].ReferencedFractionGroupSequence[0].ReferencedBeamSequence[0].ReferencedBeamNumber)
                    ii = beams.index(iamBeam)
                    corrBeam = str(corrBeams[ii])
                    thisThreeDdose = os.path.sep.join([dname, timeStamp,
                    timeStamp + '_' + corrBeam + '_DOSXYZnrc.3ddose'])
                    print thisThreeDdose
                elif len(myRDs) == 1 and len(list(set(nomEnfluMod))) != 1:
                    corrBeam = str(corrBeams[j])
                    thisThreeDdose = os.path.sep.join([dname, timeStamp,
                    timeStamp + '_' + corrBeam + '_DOSXYZnrc.3ddose'])
                    addDoses = 1
                    print thisThreeDdose
                else:
                    thisThreeDdose = os.path.sep.join([dname, timeStamp,
                    timeStamp + '_DOSXYZnrc.3ddose'])

                # create back up file
                shutil.copy2(thisThreeDdose,''.join([thisThreeDdose, '.original']))

                # apply 3D Savitzky-Golay smooting if windowSize > 1
                if int(cv.windowSize) > 1:
                    cmd = './SGolay3d'
                    subprocess.call([cmd, thisThreeDdose, cv.windowSize])
                    #os.system('%(cmd)s %(thisThreeDdose)s %(windowSize)s' %locals())

                # read 3ddose (the order will be z,y,x)
                #xCoord, yCoord, zCoord, dose, uncert = samcUtil.readMCdose(thisThreeDdose)
                data = samcUtil.read3ddose(thisThreeDdose)
                dose = data.dose
                xCoord = data.X
                yCoord = data.Y
                zCoord = data.Z

                # convert to numpy
                dose = np.asarray(dose)

                # set dose to outside = 0.0
                # read phantom
                phantFile = os.path.sep.join([timeStamp, timeStamp + '.egs4phant'])
                if os.path.isfile(phantFile):
                    media, mediaMatrix, numElem = samcUtil.readEgs4phant(phantFile)
                    try:
                        outIndx = media.index(outsideMaterial) + 1
                        mediaMatrix = np.asarray(mediaMatrix).astype(int)
                        dose = np.where(mediaMatrix == outIndx, 0., dose)
                    except ValueError:
                        pass
            
                # crop dose if it was expanded to include couch
                if os.path.isfile(os.path.sep.join([timeStamp, timeStamp + '.doseGrid'])):
                    dose = samcUtil.crop3ddose(dose, xCoord, yCoord, zCoord,
                    os.path.sep.join([timeStamp, timeStamp + '.doseGrid']))
                    dose = np.asarray(dose)
                else:  # generate doseGrid file as we need it later on
                    samcUtil.doseGridGenerate(xCoord, yCoord, zCoord,
                    os.path.sep.join([timeStamp, timeStamp]))

                # convert dose to absolute
                # read absolute
                if len(myRDs) > 1:
                    absDoseFileName = os.path.sep.join([dname, timeStamp,
                    timeStamp + '_' + corrBeam + '.absCalib'])
                elif len(myRDs) == 1 and len(list(set(nomEnfluMod))) != 1:
                    absDoseFileName = os.path.sep.join([dname, timeStamp,
                    timeStamp + '_' + corrBeam + '.absCalib'])
                else:
                    absDoseFileName = os.path.sep.join([dname, timeStamp,
                    timeStamp + '.absCalib'])
                absDoseFile = open(absDoseFileName, 'r')
                absDoseCalib = float(absDoseFile.readline().rstrip())
                absDoseFile.close()

                # if bs file exists compute bsf
                bsfFile = ''.join([absDoseFileName[0:absDoseFileName.index('.absCalib')], '_BEAMnrc.bs'])
                if os.path.isfile(bsfFile):
                    egslstFile = ''.join([absDoseFileName[0:absDoseFileName.index('.absCalib')], '_BEAMnrc.egslst'])
                    print bsfFile, egslstFile
                    bsf = samcUtil.bsf(bsfFile, egslstFile)
                    print 'Backscatter Correction Factor of {0} applied'.format(bsf)
                    absDoseCalib = absDoseCalib * bsf

                dose = dose * absDoseCalib  # dose is now in absolute

                # Create modified DICOM from shell
                newRD = samcUtil.rewriteRD(RD, newSOP, dose, timeStamp,
                PatientPosition)
                if len(myRDs) > 1:
                    fileNameOut = os.path.sep.join([dname, timeStamp,
                    ''.join([cv.RDfilePrefix, cv.lblSuffix, '.', timeStamp,
                    '_', str(beams[j]), '_', cv.DICOMfileEnding])])
                elif len(myRDs) == 1 and len(list(set(nomEnfluMod))) != 1:
                    fileNameOut = os.path.sep.join([dname, timeStamp,
                    ''.join([cv.RDfilePrefix, cv.lblSuffix, '.', timeStamp,
                    '_', str(beams[j]), '_', cv.DICOMfileEnding])])
                else:
                    fileNameOut = os.path.sep.join([dname, timeStamp,
                    ''.join([cv.RDfilePrefix, cv.lblSuffix, '.', timeStamp,
                    cv.DICOMfileEnding])])

                print fileNameOut
                newRD.save_as(fileNameOut)
                if addDoses == 0:
                    shutil.copy2(fileNameOut, cv.DICOMoutDir)
                    #subprocess.call(['sudo', cv.samcCopy, fileNameOut, cv.DICOMoutDir])
                    #os.system('sudo %(samcCopy)s %(fileNameOut)s %(DICOMoutDir)s' %locals())

            if addDoses == 1:
                # add all RD.MC dose matrises
                doseFiles = []
                print os.path.sep.join([dname, timeStamp, ''])
                for file in [doseFileList for doseFileList in os.listdir(os.path.sep.join([dname, timeStamp, '']))
                if doseFileList.endswith(cv.DICOMfileEnding) and doseFileList.startswith(''.join([cv.RDfilePrefix, cv.lblSuffix, '.', timeStamp]))]:
                    doseFiles.append(file)

                # copy first
                print doseFiles
                fileNameOut = os.path.sep.join([dname, timeStamp,
                ''.join([cv.RDfilePrefix, cv.lblSuffix, '.', timeStamp,
                cv.DICOMfileEnding])])
                shutil.copy(os.path.sep.join([dname, timeStamp, doseFiles[0]]),
                fileNameOut)
                os.remove(os.path.sep.join([dname, timeStamp, doseFiles[0]]))
                for j in range(1, len(doseFiles)):
                    print j
                    samcUtil.addRDs(fileNameOut,
                    os.path.sep.join([dname, timeStamp, doseFiles[j]]))
                    os.remove(os.path.sep.join([dname, timeStamp, doseFiles[j]]))

                # copy to DICOMoutDir
                shutil.copy2(fileNameOut, cv.DICOMoutDir)
                #subprocess.call(['sudo', cv.samcCopy, fileNameOut, cv.DICOMoutDir])
                #os.system('sudo %(samcCopy)s %(fileNameOut)s %(DICOMoutDir)s' %locals())
            
    except Exception as exc:
        hdlr = logging.FileHandler('.'.join([timeStamp, 'log']))
        hdlr.setFormatter(formatter)
        logger.addHandler(hdlr)
        logger.exception(exc)
        logger.handlers = []

# update time of last run
samcUtil.writeTimeToFile(cv.timeFile, newTime)

os.remove(lockFile) # remove lockFile
