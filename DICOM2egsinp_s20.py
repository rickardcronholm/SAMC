#!/usr/bin/python
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

import sys
import dicom
import os
from datetime import datetime
import samcUtil
import shutil
import copy
from glob import iglob
import numpy as np
import polyval2D


class struct:

    def __init__(self):
        pass

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)


def copy_files(src_glob, dst_folder):
        for fname in iglob(src_glob):
            shutil.move(fname, os.path.join(dst_folder, fname))


def main(fileName, timeStamp, singularityFlag = 0, zeroAngles = 0, changeUnit = False):

    if not os.path.exists(timeStamp):
        os.makedirs(timeStamp)

    # define variables
    confFile = 'samc.conf'
    conf = struct()

    # get variables from global confFile
    with open(confFile) as f:
        confCont = f.readlines()
    whatToGet = ['convertScript.treatmentMachineLibrary', 'common.EGS_HOME', 'common.phspDir',
     'convertScript.ncaseBeam', 'convertScript.ncaseDos', 'convertScript.egsPhant', 'convertScript.mlcLib',
     'convertScript.dSource', 'common.templateDir']
    conf = samcUtil.getConfVars(conf, whatToGet, confCont)
    # convert types
    conf = samcUtil.typeCast(conf, ['ncaseDos'], [int])

    # get relevant data from DICOM file

    # open DICOM file
    RTP = dicom.read_file(fileName)
    # get PatientPosition
    PatientPosition = RTP.PatientSetupSequence[0].PatientPosition
    # get ID
    patientID = samcUtil.getID(RTP,timeStamp)
    #get Name
    patientName = samcUtil.getName(RTP)
    # get planName
    planName = RTP.RTPlanLabel
    # get beams, that are 'TREATMENT'
    (beams, corrBeams) = samcUtil.getBeams(RTP)
    # get treatmentMachine hereby assuming that all beams are planned on the same linac
    if changeUnit:
        treatmentMachine = changeUnit
    else:
        treatmentMachine = RTP.BeamSequence[corrBeams[0]].TreatmentMachineName
    # overwrite variables from machine specific config file
    with open(treatmentMachine) as f:
        confCont = f.readlines()
    whatToGet = ['mlcLib', 'templateType', 'template', 'nLeafs', 'SCD', 'SAD',
    'leafRadius', 'physLeafOffset', 'dSource', 'ncaseBeam',
    'TreatmentMachineType']
    conf = samcUtil.getConfVars(conf, whatToGet, confCont)
    # get treatmentMachineType
    #machineType = samcUtil.machineTypeLookUp(conf.treatmentMachineLibrary,treatmentMachine)
    # get MU for each beam
    MUs = samcUtil.getMU(RTP,beams)
    # get nominal energy and fluence mode
    nomEnfluMod = samcUtil.getEnFlu(RTP,corrBeams)
    # if more than one value for nomEnfluMod exist, we can not concatenate everything into a single set of input files
    if singularityFlag == 1 and len(list(set(nomEnfluMod))) != 1:
        singularityFlag = 0
        conf.ncaseBeam = int(conf.ncaseBeam/len(nomEnfluMod))
    # get angles
    (gantry,couch,coll) = samcUtil.getAngles(RTP,corrBeams)
    if zeroAngles == 1:  # set all angles to zero if requested
        for i in range(0, len(gantry)):
            gantry[i] = [0]*len(gantry[i])
            couch[i] = [0]*len(couch[i])
            coll[i] = [0]*len(coll[i])
    # get MUindx
    if singularityFlag == 1:
        MUindx = samcUtil.getMUindxScaled(RTP,corrBeams,MUs)
    else:
        MUindx = samcUtil.getMUindx(RTP,corrBeams,MUs)
    # get ISO, we here assume no interbeam ISO shift
    ISO = samcUtil.getISO(RTP,corrBeams)
    # get BeamLimitingDevicePositions
    xJawName=[]
    xJawName.append('X')
    xJawName.append('ASYMX')
    yJawName=[]
    yJawName.append('Y')
    yJawName.append('ASYMY')
    mlcName = []
    mlcName.append('MLCX')
    xJawPos = samcUtil.getBLDPos(RTP,corrBeams,xJawName)
    yJawPos = samcUtil.getBLDPos(RTP,corrBeams,yJawName)
    leafPos = samcUtil.getBLDPos(RTP,corrBeams,mlcName)
    is_static = []
    for i in range(0, len(leafPos)):
        this_static = samcUtil.isstatic(leafPos[i])
        is_static.append([this_static] * len(leafPos[i]))

    # check for EDW
    EDW = samcUtil.isEDW(RTP,corrBeams)

    if sum(EDW) > 0:
        MUindxJaw = samcUtil.getMUindx(RTP,corrBeams,MUs)
        for i in range(0,len(EDW)):
            if EDW[i] == 1:
                # get wedgeAngle
                # get wedgeOrientation
                wedgeAngle = int(RTP.BeamSequence[corrBeams[i]].WedgeSequence[0].WedgeAngle)
                wedgeOrientation = int(RTP.BeamSequence[corrBeams[i]].WedgeSequence[0].WedgeOrientation)
                y1,y2,muindx = samcUtil.getWedgeSeq(conf.TreatmentMachineType,nomEnfluMod[i],yJawPos[i][0][0],yJawPos[i][0][1],wedgeAngle,wedgeOrientation)
                yjawpos = samcUtil.reorderJawPos(y1,y2)
                x1 = [xJawPos[corrBeams[i]][0][0]]*len(y1)
                x2 = [xJawPos[corrBeams[i]][0][1]]*len(y1)
                xjawpos = samcUtil.reorderJawPos(x1,x2)
                yJawPos[corrBeams[i]] = yjawpos
                xJawPos[corrBeams[i]] = xjawpos
                MUindxJaw[corrBeams[i]] = muindx

        if singularityFlag == 1:
            # rescale MUs
            MUindxJaw = samcUtil.rescaleMUindx(MUindxJaw,corrBeams,MUs)


    # get NumberOfPlannedFractions
    nFrac = int(RTP.FractionGroupSequence[0].NumberOfFractionsPlanned)

    # get SAD
    conf.SAD = float(RTP.BeamSequence[0].SourceAxisDistance)/10

    # all data now retrieved

    # modify types
    varName = ['ncaseBeam', 'dSource']
    varType = [int, float]
    for i in range(0, len(varName)):
        try:
            setattr(conf, varName[i], map(varType[i], getattr(conf, varName[i]))[0])
        except AttributeError:
            pass
        except TypeError:
            setattr(conf, varName[i], int(getattr(conf, varName[i])))
        except ValueError:
            if varType[i] == int:
                setattr(conf, varName[i], int(float(getattr(conf, varName[i]))))
            elif varType[i] == float:
                setattr(conf, varName[i], float(getattr(conf, varName[i])))
            else:
                pass

    # write keepTrack
    samcUtil.keeptrack(timeStamp,patientID,patientName,planName)

    if singularityFlag == 1:
        # write numBeams
        samcUtil.numBeams(timeStamp,1)

        # write absCalib
        samcUtil.absCalib(timeStamp, treatmentMachine, nomEnfluMod[0], MUs,
        nFrac)
        #os.rename(''.join([timeStamp,'destination')

        # write BEAMnrc egsinp
        #print timeStamp
        (beamDir,phspType, phspName) = samcUtil.BEAMegsinp(timeStamp,conf.templateType,conf.TreatmentMachineType,nomEnfluMod[0],conf.phspDir,conf.EGS_HOME,conf.ncaseBeam)

        if phspType == 0:
            phspEnd = '.egsphsp1'
        elif phspType == 4:
            phspEnd = '.1.IAEAphsp'


        # write SYNCJAW sequence, only implemented for TB and IX
        if conf.TreatmentMachineType == 'TB' or conf.TreatmentMachineType == 'IX':
            if sum(EDW) > 0:
                samcUtil.syncjawSeq(timeStamp,xJawPos,yJawPos,MUindxJaw)
            else:
                samcUtil.syncjawSeq(timeStamp,xJawPos,yJawPos,MUindx)
        # write SYNCMLC sequence (either SYNCVMLC or SYNCHDMLC), only implemented for TB and IX
        if conf.TreatmentMachineType == 'TB' or conf.TreatmentMachineType == 'IX':
			samcUtil.syncmlcSeq(timeStamp,leafPos,MUindx,conf.SCD,conf.SAD,conf.leafRadius, is_static, conf.physLeafOffset)

        # The concept of dividing the Linacc head simulation in two parts is abandonned as of v0.5.3
        # Everything should now be contained in on BEAMnrc.egsinp file
        '''
        if conf.mlcLib == 'particleDmlc':  # No longer preferred, no template included
            # write VCUmlc.txt
            samcUtil.vcuTXT(timeStamp,conf.TreatmentMachineType,conf.EGS_HOME,beamDir,conf.VCUinp,phspEnd)
            # write VCUmlc.mlc
            samcUtil.vcuMLC(timeStamp,leafPos,MUindx)
        elif conf.mlcLib == 'BEAM_SYNCVMLC':  # only implemented for TB and IX
            if conf.TreatmentMachineType == 'TB' or conf.TreatmentMachineType == 'IX':
                MLCseq = ''.join([conf.EGS_HOME, conf.mlcLib,'/',timeStamp,'_MLCnrc.egsinp'])
                # write SYNCMLC sequence
                samcUtil.syncmlcSeq(timeStamp,leafPos,MUindx,conf.SCD,conf.SAD,conf.leafRadius, is_static, conf.physLeafOffset)

                # write MLC BEAMegsinp
                (mlcDir, phspType) = samcUtil.BEAMegsinp(timeStamp, conf.template, beamDir+'/', '_BEAMnrc', phspEnd, conf.EGS_HOME, conf.ncaseBeam)

                # write mlcDir file
                samcUtil.beamDir(timeStamp,mlcDir,'mlcDir')

                conf.VCUinp = conf.mlcLib
        else:
            VCUinp = '0' # ''.join([EGS_HOME,mlcLib,'/',timeStamp,'_MLC']) # this is no longer a path to a VCU file, but variable name maintaned due to lazyness.
            MLCseq = ''.join([conf.EGS_HOME, conf.mlcLib,'/',timeStamp,'_BEAMnrc.mlc'])
            # write SYNCMLC sequence
            samcUtil.syncmlcSeq(timeStamp,leafPos,MUindx,conf.SCD,conf.SAD,conf.leafRadius, is_static, conf.physLeafOffset)
        '''
        # write DOSXYZnrc egsinp
        samcUtil.DOSXYZegsinp(timeStamp,conf.EGS_HOME,conf.egsPhant,conf.mlcLib,beamDir,phspName,conf.mlcLib,ISO,gantry,couch,coll,MUindx,conf.dSource,conf.ncaseDos,PatientPosition)

        # look for backscatter file and create if template exist for treatmentMachineType and nomEnflu
        if os.path.isfile(''.join(['template/',conf.TreatmentMachineType,'_',nomEnfluMod[0],'.bs'])):
            shutil.copy(''.join(['template/',conf.TreatmentMachineType,'_',nomEnfluMod[0],'.bs']), ''.join([timeStamp,'_BEAMnrc.bs']))
    else:
        # write numBeams
        samcUtil.numBeams(timeStamp,len(corrBeams))
        print corrBeams, treatmentMachine, nomEnfluMod

        for i in range(0,len(corrBeams)):

            # write absCalib
            samcUtil.absCalib(''.join([timeStamp,'_', str(corrBeams[i])]),
            treatmentMachine, nomEnfluMod[corrBeams[i]], [MUs[corrBeams[i]]],
            nFrac)
            #os.rename(''.join([timeStamp,'destination')

            # write BEAMnrc egsinp
            #print ''.join([timeStamp,'_',str(corrBeams[i])])
            (beamDir,phspType) = samcUtil.BEAMegsinp(''.join([timeStamp,'_',str(corrBeams[i])]),conf.templateType,conf.TreatmentMachineType,nomEnfluMod[corrBeams[i]],conf.phspDir,conf.EGS_HOME,conf.ncaseBeam)

            if phspType == 0:
                phspEnd = '.egsphsp1'
            elif phspType == 4:
                phspEnd = '.1.IAEAphsp'

            # write SYNCJAW sequence, only implemented for TB and IX
            if conf.TreatmentMachineType == 'TB' or conf.TreatmentMachineType == 'IX':
                if sum(EDW) > 0:
                    samcUtil.syncjawSeq(''.join([timeStamp,'_',str(corrBeams[i])]),[xJawPos[corrBeams[i]]],[yJawPos[corrBeams[i]]],[MUindxJaw[corrBeams[i]]])
                else:
                    samcUtil.syncjawSeq(''.join([timeStamp,'_',str(corrBeams[i])]),[xJawPos[corrBeams[i]]],[yJawPos[corrBeams[i]]],[MUindx[corrBeams[i]]])
            # write SYNCMLC sequence (either SYNCVMLC or SYNCHDMLC), only implemented for TB and IX
            if conf.TreatmentMachineType == 'TB' or conf.TreatmentMachineType == 'IX':
			    samcUtil.syncmlcSeq(''.join([timeStamp,'_',str(corrBeams[i])]),[leafPos[corrBeams[i]]],[MUindx[corrBeams[i]]],conf.SCD,conf.SAD,conf.leafRadius, [is_static[corrBeams[i]]], conf.physLeafOffset)

            '''
            if conf.mlcLib == 'particleDmlc':  # No longer preferred, no template included
                # write VCUmlc.txt
                samcUtil.vcuTXT(''.join([timeStamp,'_',str(corrBeams[i])]),conf.TreatmentMachineType,conf.EGS_HOME,beamDir,conf.VCUinp,conf.phspEnd)
                # write VCUmlc.mlc
                samcUtil.vcuMLC(''.join([timeStamp,'_',str(corrBeams[i])]),[leafPos[corrBeams[i]]],[MUindx[corrBeams[i]]])
            elif conf.mlcLib == 'BEAM_SYNCVMLC':  # only implemented for TB and IX
                if conf.TreatmentMachineType == 'TB' or conf.TreatmentMachineType == 'IX':
                    MLCseq = ''.join([conf.EGS_HOME,conf.mlcLib,'/',''.join([timeStamp,'_',str(corrBeams[i])]),'_MLCnrc.egsinp'])
                    # write SYNCMLC sequence
                    samcUtil.syncmlcSeq(''.join([timeStamp,'_',str(corrBeams[i])]),[leafPos[corrBeams[i]]],[MUindx[corrBeams[i]]],conf.SCD,conf.SAD,conf.leafRadius, [is_static[corrBeams[i]]], conf.physLeafOffset)

                    # write MLC BEAMegsinp
                    (mlcDir, phspType) = samcUtil.BEAMegsinp(''.join([timeStamp,'_',str(corrBeams[i])]), conf.template, beamDir+'/', '_BEAMnrc', phspEnd, conf.EGS_HOME, conf.ncaseBeam)

                    # write mlcDir file
                    samcUtil.beamDir(timeStamp,mlcDir,'mlcDir')

                    conf.VCUinp = conf.mlcLib
            else:
                #samcUtil.syncMLC(''.join([timeStamp,'_',str(corrBeams[i])]),[leafPos[corrBeams[i]]],[MUindx[corrBeams[i]]],MLCtype,effZ,templateDir,SAD)
                VCUinp = '0'
                MLCseq = ''.join([conf.EGS_HOME,conf.mlcLib,'/',''.join([timeStamp,'_',str(corrBeams[i])]),'_BEAMnrc.mlc'])
                # write SYNCMLC sequence
                samcUtil.syncmlcSeq(''.join([timeStamp,'_',str(corrBeams[i])]),[leafPos[corrBeams[i]]],[MUindx[corrBeams[i]]],conf.SCD,conf.SAD,conf.leafRadius, [is_static[corrBeams[i]]], conf.physLeafOffset)
            '''
            
            # write DOSXYZnrc egsinp
            samcUtil.DOSXYZegsinp(''.join([timeStamp,'_',str(corrBeams[i])]),conf.EGS_HOME,conf.egsPhant,conf.mlcLib,beamDir,phspEnd,conf.mlcLib,ISO[corrBeams[i]],gantry[corrBeams[i]],couch[corrBeams[i]],coll[corrBeams[i]],MUindx[corrBeams[i]],conf.dSource,conf.ncaseDos,PatientPosition)

            # look for backscatter file and create if template exist for treatmentMachineType and nomEnflu
            if os.path.isfile(''.join(['template/',conf.TreatmentMachineType,'_',nomEnfluMod[corrBeams[i]],'.bs'])):
                shutil.copy(''.join(['template/',conf.TreatmentMachineType,'_',nomEnfluMod[corrBeams[i]],'.bs']), ''.join([timeStamp,'_',str(corrBeams[i]),'_BEAMnrc.bs']))

    # write BEAMdir file
    samcUtil.beamDir(timeStamp,beamDir,'beamDir')

    # copy files to desitnation folder
    copy_files(''.join([timeStamp,'*.*']), ''.join([timeStamp,'/']))


# Function chooser
func_arg = {"-main": main}
# run specifc function as called from command line
if __name__ == "__main__":
    if sys.argv[1] == "-main":
        if len(sys.argv) < 3:
            sys.exit('Not enough input parameters')
        try:
            timeStamp = sys.argv[3]
        except IndexError:
            timeStamp = datetime.now().strftime('%Y%m%d%H%M%S')
        try:
            singularityFlag = int(sys.argv[4])
        except IndexError:
            singularityFlag = 0
        try:
            zeroAngles = int(sys.argv[5])
        except IndexError:
            zeroAngles = 0
        try:
            changeUnit = sys.argv[6]
        except IndexError:
            changeUnit = False
        func_arg[sys.argv[1]](sys.argv[2], timeStamp, singularityFlag,
            zeroAngles, changeUnit)
