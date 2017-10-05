# this is a file containing utility scripts for the Skane Automatic Monte Carlo
# Rickard Cronholm, 2013
# rickard.cronholm@gmail.com

import re
import math
import os
import random
import dicom
import numpy as np
import socket

# config file path goes here
confFile = 'samc.conf'


class struct:
    def __init__(self):
        pass


def rreplace(s, old, new, occurence):
    li = s.rsplit(old, occurence)
    return new.join(li)


def typeCast(cv, variables, types):
    for i in range(0, len(variables)):
        try:
            setattr(cv, variables[i], map(types[i], getattr(cv, variables[i])))
        except TypeError:
            if types[i] == int:
                setattr(cv, variables[i], int(getattr(cv, variables[i])))
        except ValueError:
            pass
        return cv


def getPartOfstringFromList(lst, lookFor, delimiter, splitIndx=False, returnType=False):
    value = lst[[i for i, s in enumerate(lst) if lookFor in s][0]]
    if splitIndx:
        value = value.split(delimiter)[splitIndx].strip()
    else:
        value = value.strip()
    if not returnType:
        return value
    else:
        return np.asarray(value).astype(returnType).tolist()


def validateRP(RTP):
    (beams, corrBeams) = getBeams(RTP)
    # get treatmentMachine hereby assuming that all beams are planned on
    # the same linac
    treatmentMachine = RTP.BeamSequence[corrBeams[0]].TreatmentMachineName
    # get nominal energy and fluence mode
    nomEnfluMod = getEnFlu(RTP, corrBeams)

    print ' '.join([treatmentMachine, nomEnfluMod[0]])
    valid = True
    # make sure that there exists a config file for the treatmentMachine
    try:
        with open(treatmentMachine, 'r') as f:
            content = f.readlines()
    except IOError:
        return False  # no config file for treatmentMachine

    # only consider unique nomEnfluMods
    nomEnfluMod = list(set(nomEnfluMod))
    for i in range(0, len(nomEnfluMod)):
        # synthesize string
        lookFor = ' '.join(['absCalib', nomEnfluMod[i]])
        # make sure that absCalib exists for the current nomEnfluMod
        if len([i for i, s in enumerate(content) if lookFor in s]) == 0:
            return False

    return valid


def getConfVars(cv, wtg, content):
    for item in wtg:  # loop over what to get
        for elem in content:  # loop over content
            if elem.startswith(item):  # if found
                name = elem.split()[0].split('.')[-1]
                val = elem.split()[1]
                try:
                    val = float(val)
                except ValueError:
                    pass
                setattr(cv, name, val)  # add to confvariables
    return cv


def flatten(seq, container=None):
    if container is None:
        container = []
    for s in seq:
        if hasattr(s, '__iter__'):
            flatten(s, container)
        else:
            container.append(s)
    return container


def writeTimeToFile(fileName, newTime):
    f = open(fileName, 'w')
    f.write('{0}\n'.format(newTime))
    f.close()


def getVariable(confFile, varName):
    with open(confFile, 'r') as f:
        content = f.readlines()
    try:
        return content[[i for i, s in enumerate(content)
        if s.startswith(varName)][0]].split(' ')[1].rstrip()
    except IndexError:
        print varName, ' not found in configuration file\n'
        return ''


def getID(RTP,timeStamp):
    try:
        ID = RTP.PatientID
    except AttributeError:
        ID = int(timeStamp)
    return ID


def getName(RTP):
    try:
        name = RTP.PatientName
    except AttributeError:
        name = 'N^N'
    return " ".join(name.split('^'))


def getBeams(RTP):
    numBeams = len(RTP.BeamSequence)
    beams = []
    corrBeams = []

    for i in range(0, numBeams):
        if RTP.BeamSequence[i].TreatmentDeliveryType == 'TREATMENT':
            beams.append(int(RTP.BeamSequence[i].BeamNumber))
            corrBeams.append(i)
    return (beams, corrBeams)


def getBeamNames(RTP, corrBeams):
    beamNames = []
    for i in range(0, len(corrBeams)):
        beamNames.append(RTP.BeamSequence[corrBeams[i]].BeamName)
    return beamNames


def getMU(RTP, beams):
    MUs = []
    for i in range(0, len(beams)):
        count = 0
        while int(RTP.FractionGroupSequence[0].ReferencedBeamSequence[count].ReferencedBeamNumber) != beams[i]:
            count += 1
        MUs.append(float(RTP.FractionGroupSequence[0].ReferencedBeamSequence[count].BeamMeterset))
    return MUs


def getEnFlu(RTP, beams):
    nomEnfluMod = []
    for i in range(0, len(beams)):
        nomE = ''.join([(RTP.BeamSequence[beams[i]].ControlPointSequence[0].NominalBeamEnergy).original_string, 'X'])
        fluMod = (RTP.BeamSequence[beams[i]].PrimaryFluenceModeSequence[0].FluenceMode)
        nomEnfluMod.append('_'.join([nomE, fluMod]).rstrip())
    return nomEnfluMod


def getAngles(RTP,beams):
    gantry = []
    couch = []
    coll = []
    for i in range(0,len(beams)):
        thisGantry = []
        thisCouch = []
        thisColl = []
        numCtrlPts = int(RTP.BeamSequence[beams[i]].NumberOfControlPoints)
        for j in range(0, numCtrlPts):
            if j == 0:  # then this information is certain to exist
                thisGantry.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].GantryAngle))
                thisCouch.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].PatientSupportAngle))
                thisColl.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDeviceAngle))
                lastGantry = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].GantryAngle)
                lastCouch = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].PatientSupportAngle)
                lastColl = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDeviceAngle)
            else:
                try:
                    thisGantry.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].GantryAngle))
                    lastGantry = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].GantryAngle)
                except AttributeError:
                    thisGantry.append(lastGantry)
                try:
                    thisCouch.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].PatientSupportAngle))
                    lastCouch = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].PatientSupportAngle)
                except AttributeError:
                    thisCouch.append(lastCouch)
                try:
                    thisColl.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDeviceAngle))
                    lastColl = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDeviceAngle)
                except AttributeError:
                    thisColl.append(lastColl)
        gantry.append(thisGantry)
        couch.append(thisCouch)
        coll.append(thisColl)
    return (gantry, couch, coll)


def getMUindx(RTP,beams,MUs):
    MUindx = []
    for i in range(0, len(beams)):
        thisMUindx = []
        numCtrlPts = int(RTP.BeamSequence[beams[i]].NumberOfControlPoints)
        for j in range(0, numCtrlPts):
            if j == 0:  # then this information is certain to exist
                thisMUindx.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight))
                lastMUindx = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight)
            else:
                try:
                    thisMUindx.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight))
                    lastMUindx = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight)
                except AttributeError:
                    thisMUindx.append(lastMUindx)
        MUindx.append(thisMUindx)
    return MUindx


def getMUindxScaled(RTP, beams, MUs):
    MUindx = []
    for i in range(0, len(beams)):
        scale = MUs[i] / math.fsum(MUs)
        addThis = 0
        if i != 0:
            for j in range(0, i):
                addThis += MUs[j]
            addThis = addThis / math.fsum(MUs)
        thisMUindx = []
        numCtrlPts = int(RTP.BeamSequence[beams[i]].NumberOfControlPoints)
        for j in range(0, numCtrlPts):
            if j == 0:  # then this information is certain to exist
                thisMUindx.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight)*scale + addThis)
                lastMUindx = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight)*scale + addThis
            else:
                try:
                    thisMUindx.append(float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight)*scale + addThis)
                    lastMUindx = float(RTP.BeamSequence[beams[i]].ControlPointSequence[j].CumulativeMetersetWeight)*scale + addThis
                except AttributeError:
                    thisMUindx.append(lastMUindx)
        MUindx.append(thisMUindx)
    return MUindx


def getISO(RTP, beams):
    ISO = []
    for i in range(0, len(beams)):
        thisISO = []
        thisISO = RTP.BeamSequence[beams[i]].ControlPointSequence[0].IsocenterPosition
        thisISO = [float(thisISO) / 10 for thisISO in thisISO]  # mm to cm
        beamISO = []
        numCtrlPts = int(RTP.BeamSequence[beams[i]].NumberOfControlPoints)
        for j in range(0,numCtrlPts):
            beamISO.append(thisISO)
        ISO.append(beamISO)
    return ISO


def isEDW(RTP, beams):
    EDW = []
    for i in range(0, len(beams)):
        try:
            len(RTP.BeamSequence[beams[i]].WedgeSequence)
            EDW.append(1)
        except AttributeError:
            EDW.append(0)
    return EDW


def getBLDPos(RTP, beams, limiter):
    nLeafPair = 60  # hard coded the number of leaf pairs
    parkPos = 20  # hard coded the half field opening for parked MLC
    limiterPos = []
    for i in range(0, len(beams)):
        thisLimPos = []
        numCtrlPts = int(RTP.BeamSequence[beams[i]].NumberOfControlPoints)
        lastLimPos = []
        for j in range(0, numCtrlPts):
            try:
                len(RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDevicePositionSequence)
                doGo = True
            except AttributeError:
                lastLimPos = leafPos
                doGo = False
            if doGo:
                leafPos = []
                # look for the current limiter
                iamLimiter = -1
                for k in range(0, len(RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDevicePositionSequence)):
                    for l in range(0, len(limiter)):
                        if limiter[l] == RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDevicePositionSequence[k].RTBeamLimitingDeviceType:
                            iamLimiter = k
                if iamLimiter < 0 and j == 0:
                    for n in range(0, nLeafPair):
                        lastLimPos.append(-parkPos)
                    for n in range(0, nLeafPair):
                        lastLimPos.append(parkPos)
                if iamLimiter >= 0:
                    leafPos = RTP.BeamSequence[beams[i]].ControlPointSequence[j].BeamLimitingDevicePositionSequence[iamLimiter][0x300a,0x11c].value
                    leafPos = [float(leafPos) / 10 for leafPos in leafPos]  # mm to cm
                    lastLimPos = leafPos
                else:
                    leafPos = lastLimPos
            thisLimPos.append(leafPos)
        limiterPos.append(thisLimPos)
    return limiterPos


def machineTypeLookUp(fileName, machineName):
    f = open(fileName, "r")
    # add a trailing white character
    machineName = ' '.join([machineName, ''])
    for line in f:
        if re.search(machineName, line):
            thisLine = line
            break
    return thisLine[thisLine.find(":",
    thisLine.find("TreatmentMachineType")) + 1:len(thisLine) - 1].rstrip()


def keeptrack(timeStamp, patID, patName, planLabel):
    fileName = ''.join([timeStamp, '.keepTrack'])
    f = open(fileName, 'w')
    ktstr = '{tS}\t{pID}\t{pN}\t{plL}\n'.format(tS=timeStamp,
    pID=patID, pN=patName, plL=planLabel)
    f.write(ktstr)
    f.close()
    return


def numBeams(timeStamp, numBeams):
    fileName = ''.join([timeStamp, '.numBeams'])
    f = open(fileName, 'w')
    f.write(str(numBeams))
    f.close()
    return


def beamDir(timeStamp, beamDir, suffix):
    fileName = '.'.join([timeStamp, suffix])
    f = open(fileName, 'w')
    f.write(str(beamDir))
    f.close()
    return


def absCalib(timeStamp, machineName, eflu, MUs, nFrac):
    fileName = ''.join([timeStamp, '.absCalib'])
    fout = open(fileName, 'w')
    with open(machineName, 'r') as fmachine:
        cont = fmachine.readlines()
    lookFor = ' '.join(['absCalib', eflu])
    try:
        absCalib = float(cont[[i for i, s in enumerate(cont)
        if s.startswith(lookFor)][0]].split(' ')[-1].rstrip())
    except IndexError:
        absCalib = 1.0  # set to unity if no matched found
    fout.write(str(absCalib * math.fsum(MUs) * nFrac))
    fout.close()
    return


def BEAMegsinp(timeStamp, templateType, machineType, nomEnfluMod, phspDir, EGS_HOME, ncase):
    confFile = 'samc.conf'
    # get templateDir
    templateDir = getVariable(confFile, 'common.templateDir')
    phspInType = getVariable(confFile, 'daemonA.phspInType')
    fileNameIn = ''.join([templateDir, templateType,
    '_BEAMnrc_template.egsinp'])
    fIn = open(fileNameIn, 'r')
    if nomEnfluMod == '_BEAMnrc':
        fileName = ''.join([timeStamp, '_MLCnrc.egsinp'])
    else:
        fileName = ''.join([timeStamp, '_BEAMnrc.egsinp'])
    fOut = open(fileName, 'w')

    # the first line in the template file is the BEAMnrc directory
    beamDir = (fIn.readline()).rstrip()

    # write title
    fOut.write('{0}\n'.format(timeStamp))

    # Change the stuff below to simple search replace
    while True:
        thisLine = fIn.readline()
        if not thisLine:
            break
        if thisLine.find('{phsp}') >= 0:
	    phspName = ''.join([phspDir,
            machineType, '_', nomEnfluMod, phspInType])
            thisLine = thisLine.format(phsp=phspName)
        if thisLine.find('phspType=') > 0:
            phspType = int(thisLine[thisLine.rindex('phspType=') + len('phspType=')])
            thisLine = thisLine.format(phspType=phspType)
        if thisLine.rstrip() == 'syncjawSequence':
            thisLine = ''.join([EGS_HOME, beamDir, os.path.sep,
            timeStamp, '_BEAMnrc.jaw\n'])
        if thisLine.rstrip() == 'syncmlcSequence':
            if nomEnfluMod == '_BEAMnrc':
                thisLine = ''.join([EGS_HOME, beamDir, os.path.sep,
                timeStamp, '_MLCnrc.mlc\n'])
            else:
                thisLine = ''.join([EGS_HOME, beamDir, os.path.sep,
                timeStamp, '_BEAMnrc.mlc\n'])
        if thisLine.startswith('{NCASE}'):
            thisLine = thisLine.format(NCASE=ncase,
            IXXIN=str(random.randint(1, 31328)),
            JXXIN=str(random.randint(1, 30081)))
        if thisLine.find('{myPhsp}') >= 0:
            thisLine = thisLine.format(myPhsp=''.join([EGS_HOME, machineType,
            timeStamp, nomEnfluMod, phspDir]))
        fOut.write(thisLine)
    fOut.close()
    fIn.close()
    return (beamDir, phspType, phspName)


def DOSXYZegsinp(timeStamp, EGS_HOME, egsPhant, mlcLib, beamDir, phspName, VCUinp, ISO, gantry, couch, coll, MUindx, dSource, ncase, PatientPosition):
    numCtrlPts = len(flatten(MUindx))
    ISO = flatten(ISO)
    gantry = flatten(gantry)
    couch = flatten(couch)
    coll = flatten(coll)
    MUindx = flatten(MUindx)

    # convert angels in DICOM format to EGSnrc format (in a nasty for loop)
    theta = []
    phi = []
    phiCol = []
    for i in range(0, numCtrlPts):
        (thisTheta, thisPhi, thisPhiCol) = dcm2dosxyz(gantry[i], couch[i], coll[i], PatientPosition)
        theta.append(thisTheta)
        phi.append(thisPhi)
        phiCol.append(thisPhiCol)

    confFile = 'samc.conf'
    # get templateDir
    templateDir = getVariable(confFile, 'common.templateDir')
    if numCtrlPts > 0:
        fileNameIn = ''.join([templateDir, 'DOSXYZnrc_template.egsinp'])
        fileName = ''.join([timeStamp, '_DOSXYZnrc.egsinp'])
    else:
        fileNameIn = ''.join([templateDir, mlcLib, '_template.egsinp'])
        fileName = ''.join([timeStamp, '_MLC.egsinp'])
    fIn = open(fileNameIn, 'r')
    fOut = open(fileName, 'w')

    # the first line in the template file is the DOSXYZnrc directory
    dosDir = (fIn.readline()).rstrip()
    # write title
    fOut.write('{0}\n'.format(timeStamp))
    # Change the stuff below to simple search replace
    while True:
        loopNow = False
        thisLine = fIn.readline()
        if not thisLine:
            break
        if thisLine.find('{myEgsphant}') >= 0:
            thisLine = thisLine.format(myEgsphant=''.join([EGS_HOME, dosDir,
            os.path.sep, egsPhant]))
        if thisLine.find('{myMlcLib}') >= 0:
            if VCUinp == '0':
                thisLine = thisLine.format(myMlcLib=VCUinp,
                myPhsp = phspName,
                myVcuTxt=VCUinp)
            elif VCUinp == mlcLib:
                thisLine = thisLine.format(myMlcLib=mlcLib,
                myPhsp = phspName,
                myVcuTxt=''.join([timeStamp, '_BEAMnrc']))
            else:
                thisLine = thisLine.format(myMlcLib=mlcLib,
                myPhsp = phspName,
                myVcuTxt=''.join([VCUinp, timeStamp, '_vcu.txt']))
        if thisLine.find('{NCASE}') >= 0:
            thisLine = thisLine.format(NCASE=ncase,
            IXXIN=str(random.randint(1, 31328)),
            JXXIN=str(random.randint(1, 30081)))
        if thisLine.find('{myNumCtrlPts}') > 0:
            thisLine = thisLine.format(myNumCtrlPts=numCtrlPts)
            loopNow = True
        if thisLine.startswith('{myPhsp}'):
            thisLine = thisLine.format(myPhsp=''.join([EGS_HOME, beamDir,
            os.path.sep, timeStamp, '_BEAMnrc', phspEnd]))
        if thisLine.startswith('{MLCseq}'):
            thisLine = thisLine.format(MLCseq=VCUinp)
        fOut.write(thisLine)
        if loopNow:
            # loop over numCtrlPts and write:
            # ISO(x), ISO(y), ISO(z), theta, phi, phiCol, dSource, MUindx
            for i in range(0, numCtrlPts):
                fOut.write('{isox:.4f}, {isoy:.4f}, {isoz:.4f}, {th:.4f}, {ph:.4f}, {phC:.4f}, {dS:.4f}, {MUi:.4f}\n'.format(isox=ISO[3*i], isoy=ISO[3*i+1], isoz=ISO[3*i+2], th=theta[i], ph=phi[i], phC=phiCol[i], dS=dSource, MUi=MUindx[i]))
    fOut.close()
    fIn.close()
    return


def syncjawSeq(timeStamp, xJawPos, yJawPos, MUindx):
    # syncjawSeq for Varian TrueBeam and Clinac iX, valid for the BEAMnrc CM SYNCJAWS
    numCtrlPts = len(flatten(MUindx))
    fileName = ''.join([timeStamp, '_BEAMnrc.jaw'])
    f = open(fileName, 'w')
    # write title
    f.write('{0}\n'.format(timeStamp))
    # write numCtrlPts
    f.write('{0}\n'.format(str(numCtrlPts)))
    for i in range(0, len(MUindx)):
        for j in range(0, len(MUindx[i])):
            # write MUindx[i][j]
            f.write('{0:.4f}\n'.format(MUindx[i][j]))
            # calculate BEAMnrc SYNCJAW parameters
            thisJawPos = calcSyncjawPos(xJawPos[i][j], yJawPos[i][j])
            # write SYNCJAW parameters
            f.write('{0:.4f}, {1:.4f}, {2:.4f}, {3:.4f}, {4:.4f}, {5:.4f}, \n{6:.4f}, {7:.4f}, {8:.4f}, {9:.4f}, {10:.4f}, {11:.4f}, \n'.format(thisJawPos[0][0], thisJawPos[0][1], thisJawPos[0][2], thisJawPos[0][3], thisJawPos[0][4], thisJawPos[0][5], thisJawPos[1][0], thisJawPos[1][1], thisJawPos[1][2], thisJawPos[1][3], thisJawPos[1][4], thisJawPos[1][5]))
    f.close()
    return


def syncmlcSeq(timeStamp, leafPos, MUindx, SCD, SAD, leafRadius, is_static, physicalLeafOffset):
    # syncmlcSeq for Varian TrueBeam and Clinac iX, valid for the BEAMnrc CMs SYNCVMLC andde SYNCHDMLC
    numCtrlPts = len(flatten(MUindx))
    bankA, bankB = calcMLCphysPos(leafPos, SAD, SCD, leafRadius, is_static,
    physicalLeafOffset, numCtrlPts)
    # reshape MUindx according to numCtrlPts
    MUindx = np.asarray(flatten(MUindx)).reshape((1, numCtrlPts)).tolist()
    fileName = ''.join([timeStamp, '_BEAMnrc.mlc'])
    f = open(fileName, 'w')

    # write title
    f.write('{0}\n'.format(timeStamp))
    # write numCtrlPts
    f.write('{0}\n'.format(str(numCtrlPts)))

    for i in range(0, len(MUindx)):
        for j in range(0, len(MUindx[i])):
            # write MUindx[i][j]
            f.write('{0:.4f}\n'.format(MUindx[i][j]))
            for k in range(0, len(bankA[i][j])):
                f.write('{0:.4f}, {1:.4f}, 1\n'.format(bankA[i][j][-(k + 1)],
                bankB[i][j][-(k + 1)]))  # invert leaf order
    f.close()
    return


def vcuMLC(timeStamp, leafPos, MUindx):
    numCtrlPts = len(flatten(MUindx))
    numLeafs = len(leafPos[0][0])
    fileName = ''.join([timeStamp, '_vcu.mlc'])
    f = open(fileName, 'w')
    # write title and base information
    f.write('File Rev = G\nTreatment = Dynamic Dose\nLast Name = {tS}\nFirst Name = {tS}\nPatient ID = {tS}\nNumber of Fields = {nF}\nNumber of Leaves = {nL}\nTolerance = 0.2000\n\n'.format(tS=timeStamp, nF=str(numCtrlPts), nL=str(numLeafs)))
    counter = 0
    for i in range(0, len(MUindx)):
        for j in range(0, len(MUindx[i])):
            # write controlpoint header
            f.write('Field = 0-{cnt}\nIndex = {indx:.4f}\nCarriage Group = 1\nOperator = \nCollimator = 0.00\n'.format(cnt=str(counter),indx=MUindx[i][j]))

            # write leaf positions, bank A
            for k in range(0, numLeafs / 2):
                if k < 9:
                    f.write('Leaf  ')
                else:
                    f.write('Leaf ')
                f.write('{n}A = {i:6.2f}\n'.format(n=str(k + 1),
                i=leafPos[i][j][k + numLeafs / 2]))

            # write leaf positions, bank B
            for k in range(0, numLeafs / 2):
                if k < 9:
                    f.write('Leaf  ')
                else:
                    f.write('Leaf ')
                f.write('{n}B = {i:6.2f}\n'.format(n=str(k + 1),
                i=-leafPos[i][j][k]))  # note sign shift for bank B

            # write control point footer
            f.write('Note = 0\nShape = 0\nMagnification = 1.0\n\n')
            counter += 1

    # write checksum
    f.write('CRC = 8415')  # just use a static checksum
    f.close()
    return


def calcMLCphysPos(leafPos, SAD, SCD, R, is_static, physicalLeafOffset, numCtrlPts):
    SAD = float(SAD)
    SCD = float(SCD)
    R = float(R)
    # get nLeafs per bank
    nLeafs = len(leafPos[0][0]) / 2
    # convert to np.array
    leafPos = flatten(leafPos)
    leafPos = np.asarray(leafPos).reshape((1, numCtrlPts, nLeafs * 2))
    bankA = leafPos[:, :, 0:nLeafs]
    bankB = leafPos[:, :, nLeafs:2 * nLeafs]
    # adjust for physical Leaf Offset in non-nice loop fashion
    #for n in range(0, bankA.shape[0]):
    #    for i in range(0, bankA.shape[-2]):
    #        for j in range(0, bankA.shape[-1]):
    #            if not is_static[n][i][j] and bankB[n][i][j] - bankA[n][i][j] < physicalLeafOffset:
    #                midpoint = np.mean([bankB[n][i][j], bankA[n][i][j]])
    #                bankA[n][i][j] = midpoint - physicalLeafOffset/2.
    #                bankB[n][i][j] = midpoint + physicalLeafOffset/2.
    bankA = computeMLCphysPos(-bankA, SAD, SCD, R) * -1
    bankB = computeMLCphysPos(bankB, SAD, SCD, R)
    return bankA.tolist(), bankB.tolist()


def computeMLCphysPos(bank, SAD, SCD, R):
    # compute theta
    theta = np.arctan(bank / SAD)
    # comnpute light field/MLC cross point
    bank = bank / SAD * (SCD + R * np.sin(theta))
    # compute physical position
    bank = bank - R + R * np.cos(theta)
    return bank


def syncMLC(timeStamp, leafPos, MUindx, MLCtype, MLCeffZ, templateDir, SAD):
    numCtrlPts = len(flatten(MUindx))
    # numLeafs = len(leafPos[0][0])
    fileName = ''.join([timeStamp, '_MLCnrc.mlc'])
    f = open(fileName, 'w')
    # write title
    f.write('{0}\n'.format(timeStamp))
    # write numCtrlPts
    f.write('{0}\n'.format(str(numCtrlPts)))
    for i in range(0, len(MUindx)):
        for j in range(0, len(MUindx[i])):
            # write MUindx[i][j]
            f.write('{0:.4f}\n'.format(MUindx[i][j]))
            # calculate BEAMnrc SYNCJAW parameters
            bankA, bankB = computePhysMLCpos(leafPos[i][j], MLCtype, MLCeffZ,
            templateDir, SAD)
            for k in range(0, len(bankA)):
                # write leafPosition
                f.write('{0:.6f}, {1:.6f}, \n'.format(bankB[k], bankA[k]))
    f.close()
    return


def vcuTXT(timeStamp, machineType, EGS_HOME, beamDir, VCUinp, phspEnd):
    confFile = 'samc.conf'
    # get templateDir
    templateDir = getVariable(confFile, 'common.templateDir')
    fileNameIn = ''.join([templateDir, machineType, '_vcuMLC_template.txt'])
    fIn = open(fileNameIn, 'r')
    fileName = ''.join([timeStamp, '_vcu.txt'])
    fOut = open(fileName, 'w')
    # Possibly change below to simple search replace.
    # Not sure if I can be bothered though, since vcu mlc is kinda outdated
    while True:
        thisLine = fIn.readline()
        if not thisLine:
            break
        if thisLine.find('{title}') >= 0:
            thisLine = thisLine.format(title=timeStamp)
        if thisLine.find('{mlcPosFile}') >= 0:
            thisLine = thisLine.format(mlcPosFile=''.join([VCUinp,
            timeStamp, '_vcu.mlc']))
        if thisLine.find('{phspFile}') >= 0:
            thisLine = thisLine.format(phspFile=''.join([EGS_HOME, beamDir,
            os.path.sep, timeStamp, phspEnd]))
        if thisLine.find('{bin}') >= 0:
            thisLine = thisLine.format(bin=''.join([EGS_HOME, 'bin']))
        fOut.write(thisLine)
    fOut.close()
    fIn.close()
    return


def calcSyncjawPos(xJawPos, yJawPos):
    # define static defaults.
    # borrowed (with permission) from T.Popescu and C.Shaw
    # Applies to both Varian iX and TB
    SAD = 100.0
    fieldfocus = 0.0
    wjaws = 7.873769
    zrady = 27.9389
    x1 = xJawPos[0]
    x2 = xJawPos[1]
    y1 = yJawPos[0]
    y2 = yJawPos[1]
    htY2 = zrady * SAD / math.sqrt(pow(y2, 2) + pow(SAD, 2))
    htY1 = zrady * SAD / math.sqrt(pow(y1, 2) + pow(SAD, 2))
    htY = (htY2 + htY1) / 2
    hbY2 = htY2 + wjaws * SAD / math.sqrt(pow(y2, 2) + pow(SAD, 2))
    hbY1 = htY1 + wjaws * SAD / math.sqrt(pow(y1, 2) + pow(SAD, 2))
    hbY = (hbY2 + hbY1) / 2
    tfY2 = (-1) * (htY - fieldfocus) * y2 / SAD
    tbY2 = (-1) * (hbY - fieldfocus) * y2 / SAD
    tfY1 = (htY - fieldfocus) * y1 / SAD
    tbY1 = (hbY - fieldfocus) * y1 / SAD
    htX2 = 36.82855 - wjaws * 20 / math.sqrt(pow(20.0, 2) + pow(SAD, 2))
    htX1 = 36.82855
    htX = (htX2 + htX1) / 2
    hbX2 = htX + wjaws * SAD / math.sqrt(pow(x2, 2) + pow(SAD, 2))
    hbX1 = htX + wjaws * SAD / math.sqrt(pow(x1, 2) + pow(SAD, 2))
    hbX = (hbX2 + hbX1) / 2
    tfX2 = (htX - fieldfocus) * x2 / SAD
    tbX2 = (hbX - fieldfocus) * x2 / SAD
    tfX1 = (-1) * (htX - fieldfocus) * x1 / SAD
    tbX1 = (-1) * (hbX - fieldfocus) * x1 / SAD
    jawParams = []
    jawParams.append([htY, hbY, -tfY1, -tbY1, tfY2, tbY2])
    jawParams.append([htX, hbX, tfX2, tbX2, -tfX1, -tbX1])
    return jawParams


def returnAngle(angle, lowBound, upBound):
    while angle < lowBound:
        angle += upBound
    while angle >= upBound:
        angle -= upBound
    return angle


def rewriteRP(RP, prefix):
    # Need to change
    # SOPInstanceUID, RTPlanLabel, RTPlanDescription

    # Add ReferencedRTPlanSequence
    dataset = dicom.dataset.Dataset()
    dataset.add_new(0x81150, 'UI', RP.SOPClassUID)
    dataset.add_new(0x81155, 'UI', RP.SOPInstanceUID)
    dataset.add_new(0x300a0055, 'CS', 'VERIFIED_PLAN')
    sequence = dicom.sequence.Sequence()
    sequence.append(dataset)
    RP.ReferencedRTPlanSequence = sequence

    # SOPInstanceUID
    RP.SOPInstanceUID = dicom.UID.generate_uid()
    # RTPlanLabel - just add _suffix
    s = '_'.join([prefix, RP.RTPlanLabel])
    s = s.split(':')
    if len(s[0]) > 13:  # Eclipse has a limit of 13 chars
        s[0] = s[0][0:13]
    s = ':'.join(s)
    RP.RTPlanLabel = s

    # RTPlanDescription
    if prefix == 'gamma':
        RP.RTPlanDescription = '3D gamma distribution'
    else:
        RP.RTPlanDescription = 'Monte Carlo simulation; Not for clinical use'
    RP.ApprovalStatus = 'REJECTED'
    return RP


def rotateByOrientation(matrix, orientation):
    # rotate matrix, depending on PatientOrientation
    if orientation == 'FFS':
        # flip about x and z
        matrix = matrix[::-1, ::, ::-1]
    elif orientation == 'HFP':
        # flip about y and z
        matrix = matrix[::, ::-1, ::-1]
    elif orientation == 'FFP':
        # flip about x and z
        matrix = matrix[::-1, ::, ::-1]
        # flip about y and z
        matrix = matrix[::, ::-1, ::-1]
    elif orientation == 'HFDL':
        # transpose
        matrix = np.transpose(matrix, (0, 2, 1))
        # flip about z
        matrix = matrix[::, ::, ::-1]
    elif orientation == 'FFDL':
        # transpose
        matrix = np.transpose(matrix, (0, 2, 1))
        # flip about z
        matrix = matrix[::, ::, ::-1]
        # flip about x and z
        matrix = matrix[::-1, ::, ::-1]
    elif orientation == 'HFDR':
        # transpose
        matrix = np.transpose(matrix, (0, 2, 1))
        # flip about z
        matrix = matrix[::, ::, ::-1]
        # flip about y and z
        matrix = matrix[::, ::-1, ::-1]
    elif orientation == 'FFDR':
        # transpose
        matrix = np.transpose(matrix, (0, 2, 1))
        # flip about z
        matrix = matrix[::, ::, ::-1]
        # flip about y and z
        matrix = matrix[::, ::-1, ::-1]
        # flip about x and z
        matrix = matrix[::-1, ::, ::-1]
    return matrix


def rewriteRD(RD, RefSOPuid, doseDist, timeStamp, PatientPosition):
    # Need to change
    # SOPInstanceUID, ReferencedSOPInstanceUD, DoseGridScaling, PixelData

    # SOPInstanceUID
    RD.SOPInstanceUID = dicom.UID.generate_uid()

    # ReferencedSOPInstanceUID
    RD.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID = RefSOPuid

    # rotate matrix, depending on PatientPosition
    doseDist = rotateByOrientation(doseDist, PatientPosition)
    '''
    if PatientPosition == 'FFS':
        # flip about x and z
        doseDist = doseDist[::-1,::,::-1]
    if PatientPosition == 'HFP':
        # flip about y and z
        doseDist = doseDist[::,::-1,::-1]
    if PatientPosition == 'FFP':
        # flip about x and z
        doseDist = doseDist[::-1,::,::-1]
        # flip about y and z
        doseDist = doseDist[::,::-1,::-1]
    if PatientPosition == 'HFDL':
        # transpose
        doseDist = np.transpose(doseDist, (0, 2, 1))
        # flip about z
        doseDist = doseDist[::,::,::-1]
    if PatientPosition == 'FFDL':
        # transpose
        doseDist = np.transpose(doseDist, (0, 2, 1))
        # flip about z
        doseDist = doseDist[::,::,::-1]
        # flip about x and z
        doseDist = doseDist[::-1,::,::-1]
    if PatientPosition == 'HFDR':
        # transpose
        doseDist = np.transpose(doseDist, (0, 2, 1))
        # flip about z
        doseDist = doseDist[::,::,::-1]
        # flip about y and z
        doseDist = doseDist[::,::-1,::-1]
    if PatientPosition == 'FFDR':
        # transpose
        doseDist = np.transpose(doseDist, (0, 2, 1))
        # flip about z
        doseDist = doseDist[::,::,::-1]
        # flip about y and z
        doseDist = doseDist[::,::-1,::-1]
        # flip about x and z
        doseDist = doseDist[::-1,::,::-1]
    '''

    if int(RD.Rows) != int(doseDist.shape[1]) or int(RD.Columns) != int(doseDist.shape[2]) or int(RD.NumberOfFrames) != int(doseDist.shape[0]):
        ImagePositionPatient = []
        GridFrameOffsetVector = []
        Rows = doseDist.shape[1]
        Columns = doseDist.shape[2]
        nof = doseDist.shape[0]
        with open(os.path.join(timeStamp, timeStamp + '.doseGrid')) as f:
            lines = f.read().splitlines()
        for i in range(0, len(lines)):
            data = lines[i].split()
            val = str(float(data[0]) * 10)  # cm to mm
            ImagePositionPatient.append(val)
        dist = float(RD.GridFrameOffsetVector[1]) - float(RD.GridFrameOffsetVector[0])
        GridFrameOffsetVector.append('0.0')
        for i in range(1, int(data[2])):
            GridFrameOffsetVector.append(str(float(GridFrameOffsetVector[i - 1]) + dist))
        RD.Rows = Rows
        RD.Columns = Columns
        RD.NumberOfFrames = nof
        RD.ImagePositionPatient = ImagePositionPatient
        RD.GridFrameOffsetVector = GridFrameOffsetVector

    # set DoseGridScaling to 1e-6
    RD.DoseGridScaling = str(1e-6)
    # convert to uint32 using RD.DoseGridScaling
    doseDist[doseDist < 0] = 0  # get rid of negative doses.
    doseDist = (doseDist / float(RD.DoseGridScaling)).astype('uint32')
    # PixelData
    RD.PixelData = doseDist.tostring()
    return RD


def addRDs(fileA, fileB):
    # read fileA
    A = dicom.read_file(fileA)
    # read fileB
    B = dicom.read_file(fileB)
    # add doses, assuming that they have the same grid
    totDose = A.pixel_array * float(A.DoseGridScaling) + B.pixel_array * float(B.DoseGridScaling)
    # convert to uint32 using RD.DoseGridScaling
    totDose = (totDose / float(A.DoseGridScaling)).astype('uint32')
    # PixelData
    A.PixelData = totDose.tostring()
    # save as fileA
    A.save_as(fileA)
    return


def addTPSRDs(fileA, fileB):
    # read files
    A, Adose, Ax, Ay, Az = readRD(fileA)
    B, Bdose, Bx, By, Bz = readRD(fileB)

    # check which of the A and B that is most extreme
    if (min(Ax) < min(Bx)):
        minX = min(Bx)
    else:
        minX = min(Ax)
    if (max(Ax) > max(Bx)):
        maxX = max(Bx)
    else:
        maxX = max(Ax)
    if (min(Ay) < min(By)):
        minY = min(By)
    else:
        minY = min(Ay)
    if (max(Ay) > max(By)):
        maxY = max(By)
    else:
        maxY = max(Ay)
    if (min(Az) < min(Bz)):
        minZ = min(Bz)
    else:
        minZ = min(Az)
    if (max(Az) > max(Bz)):
        maxZ = max(Bz)
    else:
        maxZ = max(Az)

    # find start and stop indices
    iA = []
    iA.append(find_nearest_indx(Ax, minX))
    iA.append(find_nearest_indx(Ax, maxX))
    jA = []
    jA.append(find_nearest_indx(Ay, minY))
    jA.append(find_nearest_indx(Ay, maxY))
    kA = []
    kA.append(find_nearest_indx(Az, minZ))
    kA.append(find_nearest_indx(Az, maxZ))
    iB = []
    iB.append(find_nearest_indx(Bx, minX))
    iB.append(find_nearest_indx(Bx, maxX))
    jB = []
    jB.append(find_nearest_indx(By, minY))
    jB.append(find_nearest_indx(By, maxY))
    kB = []
    kB.append(find_nearest_indx(Bz, minZ))
    kB.append(find_nearest_indx(Bz, maxZ))

    change = False
    if len(Adose) * len(Adose[0]) * len(Adose[0][0]) > len(Bdose) * len(Bdose[0]) * len(Bdose[0][0]):
        change = True

    # crop dose ndarrays
    Adose = Adose[kA[0]:kA[1] + 1, jA[0]:jA[1] + 1, iA[0]:iA[1] + 1]
    Bdose = Bdose[kA[0]:kA[1] + 1, jA[0]:jA[1] + 1, iA[0]:iA[1] + 1]
    # add doses
    totDose = Adose + Bdose
    #check which is smaller A or B
    if change:
        # convert to uint32 using RD.DoseGridScaling
        totDose = (totDose / float(B.DoseGridScaling)).astype('uint32')
        A = B
    else:
        # convert to uint32 using RD.DoseGridScaling
        totDose = (totDose / float(A.DoseGridScaling)).astype('uint32')

    # PixelData
    A.PixelData = totDose.tostring()

    # save as fileA
    A.save_as(fileA)
    return


def readRD(fileName):
    rd = dicom.read_file(fileName)
    dose = rd.pixel_array * rd.DoseGridScaling
    rows = rd.Rows
    columns = rd.Columns
    pixel_spacing = rd.PixelSpacing
    image_position = rd.ImagePositionPatient
    x = np.arange(columns) * pixel_spacing[0] + image_position[0]
    y = np.arange(rows) * pixel_spacing[1] + image_position[1]
    z = np.array(rd.GridFrameOffsetVector) + image_position[2]
    return rd, dose, x, y, z


def find_nearest_indx(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx


def readNlist(fileID, n, a):
    thisList = []
    thatList = []
    while len(thisList) < n:
        b = fileID.readline().rstrip() + ' '
        a = a + b
        thisList = a.split()
    if len(thisList) > n:
        thatList = thisList[n:len(thisList)]
        thisList = thisList[0:n]
    return map(float, thisList), ' '.join(thatList), fileID


# replace this function
def readMCdose(fileName):
    f = open(fileName, 'r')
    # get number of elements in each dimension
    numElem = map(int, f.readline().rstrip().lstrip().split())

    # get arrays with coordinates for each dimension
    xCoord, startOfNext, f = readNlist(f, numElem[0] + 1,'')
    yCoord, startOfNext, f = readNlist(f, numElem[1] + 1, startOfNext)
    zCoord, startOfNext, f = readNlist(f, numElem[2] + 1, startOfNext)

    # start retreiving dose
    # dose gets stored in reverse dimension: i.e z,y,x
    dose = []
    planeDose = []
    for i in range(0, numElem[2]):
        planeDose = []
        for j in range(0, numElem[1]):
            lineDose, startOfNext, f = readNlist(f, numElem[0],
            ' '.join([startOfNext, '']))
            planeDose.append(lineDose)
        dose.append(planeDose)

    uncert = []
    planeUncert = []
    for i in range(0, numElem[2]):
        planeUncert = []
        for j in range(0, numElem[1]):
            lineUncert, startOfNext, f = readNlist(f, numElem[0],
            ' '.join([startOfNext, '']))
            planeUncert.append(lineUncert)
        uncert.append(planeUncert)

    f.close()
    return xCoord, yCoord, zCoord, dose, uncert


# replace this function
def crop3ddose(doseIn, xCoord, yCoord, zCoord, cropFile):
    # construct voxel-center-coordinate arrays
    x = []
    y = []
    z = []
    for i in range(0, len(xCoord) - 1):
        x.append(0.5 * (xCoord[i] + xCoord[i + 1]))
    for i in range(0, len(yCoord) - 1):
        y.append(0.5 * (yCoord[i] + yCoord[i + 1]))
    for i in range(0, len(zCoord)-1):
        z.append(0.5 * (zCoord[i] + zCoord[i + 1]))

    # read cropFile
    f = open(cropFile, 'r')
    xCrop = map(float, f.readline().rstrip().lstrip().split())
    yCrop = map(float, f.readline().rstrip().lstrip().split())
    zCrop = map(float, f.readline().rstrip().lstrip().split())
    f.close()

    xIndx = []
    xIndx.append(min(range(len(x)), key=lambda i: abs(x[i] - xCrop[0])))
    xIndx.append(min(range(len(x)), key=lambda i: abs(x[i] - xCrop[1])))
    yIndx = []
    yIndx.append(min(range(len(y)), key=lambda i: abs(y[i] - yCrop[0])))
    yIndx.append(min(range(len(y)), key=lambda i: abs(y[i] - yCrop[1])))
    zIndx = []
    zIndx.append(min(range(len(z)), key=lambda i: abs(z[i] - zCrop[0])))
    zIndx.append(min(range(len(z)), key=lambda i: abs(z[i] - zCrop[1])))

    doseOut = []
    for i in range(zIndx[0], zIndx[1] + 1):
        dosePlane = []
        for j in range(yIndx[0], yIndx[1] + 1):
            doseLine = doseIn[i][j][xIndx[0]:xIndx[1] + 1]
            dosePlane.append(doseLine)
        doseOut.append(dosePlane)

    return doseOut


# replace this function
def readEgs4phant(fileName):
    f = open(fileName, 'r')
    # get number of media to read
    numMed = int(f.readline().rstrip().lstrip())

    # read media names
    media = []
    for i in range(0, numMed):
        media.append(f.readline().rstrip().lstrip())

    # read numMed ESTEPE values
    estepe, startOfNext, f = readNlist(f, numMed, '')

    # get number of elements in each dimension
    numElem = map(int, f.readline().rstrip().lstrip().split())

    # get arrays with coordinates for each dimension
    xCoord, startOfNext, f = readNlist(f, numElem[0] + 1, '')
    yCoord, startOfNext, f = readNlist(f, numElem[1] + 1, startOfNext)
    zCoord, startOfNext, f = readNlist(f, numElem[2] + 1, startOfNext)

    mediaMatrix = []
    for i in range(0, numElem[2]):
        mediaPlane = []
        for j in range(0, numElem[1]):
            mediaLine, startofNext, f = readEgsphantLine(f, numElem[0],
            startOfNext)
            mediaPlane.append(mediaLine)
        mediaMatrix.append(mediaPlane)
    f.close()
    return media, mediaMatrix, numElem


# this function will become defunced
def readEgsphantLine(fileID, n, a):
    thisList = []
    thatList = []
    while len(thisList) < n:
        b = fileID.readline().rstrip()  # .split(' ')#.replace(' ','')
        a = a + b
        for c in a:
            thisList.append(c)

    thisList = ''.join(thisList).rstrip().split(' ')
    #print n
    #print len(thisList)
    #print thisList
    if len(thisList) > n:
        thatList = thisList[n:len(thisList)]
        thisList = thisList[0:n]
    #print ''.join(thisList).rstrip().split(' ')
    #return map(int, thisList), ''.join(thatList), fileID
    return thisList, ' '.join(thatList), fileID


def dcm2dosxyz(gantry, table, collimator, PatientPosition):
    # convert from degrees to radians
    gantry = np.deg2rad(gantry)
    table = np.deg2rad(table)
    collimator = np.deg2rad(collimator)
    # get dosxyzVector transformation matrix, PatientPosition depending
    dosV = getdosV(gantry, table, collimator, PatientPosition)

    # theta
    theta = np.arccos(-float(dosV[2]))
    # phi
    if float(dosV[1]) == 0 and float(dosV[0]) == 0:
        # very special case where the solution of arctan2(y/x) is undefined
        dosV = getdosV(gantry * 0.999999, table * 0.999999,
        collimator, PatientPosition) # slightly offset and recompute dosV
    phi = np.arctan2(-float(dosV[1]), -float(dosV[0]))

    #phiCol
    if PatientPosition[0] == 'H':
        phiCol = 3 * np.pi / 2 - collimator - np.arctan2((-np.sin(table) * np.cos(gantry)) , np.cos(table))
    elif PatientPosition[0] == 'D':
        phiCol = 3 * np.pi / 2 - collimator + np.arctan2((-np.sin(table) * np.cos(-gantry)) , -np.cos(table))
    elif PatientPosition[0] == 'A':
        phiCol = np.pi / 2 - collimator - np.arctan2((-np.sin(table) * np.cos(gantry)) , np.cos(table))
    else:
        phiCol = 3 * np.pi / 2 - collimator - np.arctan2((np.sin(table) * np.cos(gantry)) , -np.cos(table))
    return np.rad2deg(theta), np.mod(np.rad2deg(phi), 360), np.mod(np.rad2deg(phiCol), 360)

def getdosV(gantry, table, collimator, PatientPosition):
    # transformation matrix, PatientPosition depending
    if PatientPosition == 'HFS':
        T = Ry(table).dot(Rz(gantry)).dot(Ry(-collimator)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'FFS':
    #    T = Ry(table + np.pi).dot(Rz(gantry)).dot(Ry(np.pi/2 - collimator)).dot(Rx(np.pi/2))
    elif PatientPosition == 'FFS':
        T = Ry(table).dot(Rz(-gantry)).dot(Ry(-collimator)).dot(Ry(np.pi)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    elif PatientPosition == 'DFS':
        T = Ry(table).dot(Rz(-gantry)).dot(Ry(-collimator)).dot(Ry(np.pi)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    elif PatientPosition == 'AFS':
        T = Ry(table).dot(Rz(-gantry)).dot(Ry(-collimator)).dot(Ry(np.pi)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'HFP':
    #    T = Ry(-table).dot(Rz(gantry + np.pi)).dot(Ry(np.pi/2 - collimator)).dot(Rx(np.pi/2))
    elif PatientPosition == 'HFP':
        T = Ry(-table).dot(Rz(gantry)).dot(Ry(collimator)).dot(Rz(np.pi)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'FFP':
    #    T = Ry(-table + np.pi).dot(Rz(gantry + np.pi)).dot(Ry(np.pi/2 - collimator)).dot(Rx(np.pi/2))
    elif PatientPosition == 'FFP':
        T = Ry(-table).dot(Rz(-gantry)).dot(Ry(collimator)).dot(Ry(np.pi)).dot(Rz(np.pi)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'HFDR':
    #    T = Rx(table).dot(Rz(gantry)).dot(Rx(np.pi/2 - collimator)).dot(Rz(np.pi/2)).dot(Rx(np.pi/2))
    elif PatientPosition == 'HFDR':
        T = Rx(-table).dot(Rz(gantry)).dot(Rx(collimator)).dot(Rz(np.pi/2)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'HFDL':
    #    T = Rx(table).dot(Rz(gantry)).dot(Rx(np.pi/2 - collimator)).dot(Rz(-np.pi/2)).dot(Rx(np.pi/2))
    elif PatientPosition == 'HFDL':
        T = Rx(table).dot(Rz(gantry)).dot(Rx(-collimator)).dot(Rz(-np.pi/2)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'FFDR':
    #    T = Rx(table + np.pi).dot(Rz(gantry)).dot(Rx(np.pi/2 - collimator)).dot(Rz(np.pi/2)).dot(Rx(np.pi/2))
    elif PatientPosition == 'FFDR':
        T = Rx(-table).dot(Rz(-gantry)).dot(Rx(collimator)).dot(Rx(np.pi)).dot(Rz(np.pi/2)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    #elif PatientPosition == 'FFDL':
    #    T = Rx(table + np.pi).dot(Rz(gantry)).dot(Rx(np.pi/2 - collimator)).dot(Rz(-np.pi/2)).dot(Rx(np.pi/2))
    elif PatientPosition == 'FFDL':
        T = Rx(table).dot(Rz(-gantry)).dot(Rx(-collimator)).dot(Rx(np.pi)).dot(Rz(-np.pi/2)).dot(Ry(np.pi/2)).dot(Rx(np.pi/2))
    # The beam vector is 0;0;-1 as the phsp is incident along the -Z axis
    beamVector = np.matrix('0; 0; -1')
    return (T * beamVector).round(decimals=7, out=None)


def Rx(angle):
    return np.matrix([[1, 0, 0], [0, np.cos(angle), -np.sin(angle)],
    [0, np.sin(angle), np.cos(angle)]])


def Ry(angle):
    return np.matrix([[np.cos(angle), 0, np.sin(angle)],
    [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])


def Rz(angle):
    return np.matrix([[np.cos(angle), -np.sin(angle), 0],
    [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])


def doseGridGenerate(xCoord, yCoord, zCoord, fileName):
    fileName = '.'.join([fileName, 'doseGrid'])
    f = open(fileName, 'w')
    f.write('{0:.8f} {1:.8f} {2:d}\n'.format((float(xCoord[0]) + float(xCoord[1])) / 2, (float(xCoord[len(xCoord) - 1]) + float(xCoord[len(xCoord) - 2])) / 2, int(len(xCoord))-1))
    f.write('{0:.8f} {1:.8f} {2:d}\n'.format((float(yCoord[0]) + float(yCoord[1])) / 2, (float(yCoord[len(yCoord) - 1]) + float(yCoord[len(yCoord) - 2])) / 2, int(len(yCoord))-1))
    f.write('{0:.8f} {1:.8f} {2:d}\n'.format((float(zCoord[0]) + float(zCoord[1])) / 2, (float(zCoord[len(zCoord) - 1]) + float(zCoord[len(zCoord) - 2])) / 2, int(len(zCoord))-1))
    f.close()
    return


def recycleCTandRS(FoRUID, path, RPs):
    # loop through RPs and search for FoRUID
    recycle = 0
    for i in range(0, len(RPs)):
        RP = dicom.read_file(path + RPs[i])
        if RP.FrameOfReferenceUID == FoRUID:
            recycle = 1
            break
    return recycle


def getSTT(fileName):
    # reads STT table and returns Dose and Position data as lists
    # find the row where the data begins
    for skprow, line in enumerate(open(fileName)):
        if "Position" in line:
            break

    # read Dose and Position
    data = np.loadtxt(fileName, skiprows=skprow + 1)
    # transpose
    data = np.transpose(data)
    return data[0, :], data[1, :]


def compEffWedgeAngle(theta):
    # get tangent of 60 degrees
    tan60 = np.tan(np.deg2rad(60))
    # return W0 and W60
    return np.round((tan60 - np.tan(np.deg2rad(theta))) / tan60, decimals=5),
    np.round(np.tan(np.deg2rad(theta)) / tan60, decimals=5)


def getSTTforEffWedgeAngle(Dose, Position, theta):
    # get EffWedgeAngle
    W0, W60 = compEffWedgeAngle(theta)
    # find CAX Position and get Dose value
    i = np.where(Position == 0.0)
    DoseCAX = Dose[i].item(0)
    # compute and return STT for the effective wedge angle
    return np.round(DoseCAX * W0 + Dose*W60, decimals=6)


def getTruncSTT(Dose, Position, Ystart, Ystop):
    # compute additional values for Ystart and Ystop if not in array
    if not Ystart in Position:
        Dose = np.sort(np.append(Dose, np.interp(Ystart, Position, Dose)))
        Position = np.sort(np.append(Position, Ystart))
    if not Ystop in Position:
        Dose = np.sort(np.append(Dose, np.interp(Ystop, Position, Dose)))
        Position = np.sort(np.append(Position, Ystop))
    # find lower and upper values
    low = np.where(Position == Ystart)
    upp = np.where(Position == Ystop)
    return Dose[low[0].item(0):upp[0].item(0) + 1], Position[low[0].item(0):upp[0].item(0) + 1]


def getNormSTT(Dose):
    return np.round(Dose / Dose.max(), decimals=5)


def getYstop(oppJawPos, wedgeOrient):
    # the min allowed gap between jaws in cm
    gap = 0.5  # Applies to both Varian iX and TB
    if wedgeOrient == 0:
        Ystop = oppJawPos - gap
    else:
        Ystop = oppJawPos + gap
    return Ystop


def getWedgeSeq(machineType, nomEnFluMod, Y1, Y2, wedgeAngle, wedgeOrientation):
    # synthesize STT fileName
    fileName = ''.join(['template', os.path.sep, machineType, '_',
    nomEnFluMod, '.STT'])
    # get Golden STT
    Dose, Position = getSTT(fileName)
    # negate Position if wedgeOrientation is 180
    if wedgeOrientation == 180:
        Position = -Position

    # get Effective Wedge Angle STT
    Dose = getSTTforEffWedgeAngle(Dose, Position, wedgeAngle)

    # getYstop and truncated STT
    if wedgeOrientation == 0:
        Ystop = getYstop(Y2, wedgeOrientation)
        Dose, Position = getTruncSTT(Dose, Position, Y1, Ystop)
    else:
        Ystop = getYstop(Y1, wedgeOrientation)
        Dose, Position = getTruncSTT(Dose, -Position, -Y2, -Ystop)
    # get normalized STT
    Dose = getNormSTT(Dose)
    # append open part of beam
    Dose = np.sort(np.append(Dose, Dose.min()))
    Position = np.sort(np.append(Position, Position.min()))
    Dose = np.sort(np.append(Dose, 0))
    Position = np.sort(np.append(Position, Position.min()))

    # negate Position if wedgeOrientation is 180
    if wedgeOrientation == 180:
        Position = -Position
    if wedgeOrientation == 0:
        y1 = Position
        y2 = np.empty(len(y1))
        y2.fill(Y2)
    else:
        y2 = Position
        y1 = np.empty(len(y2))
        y1.fill(Y1)
    return y1.tolist(), y2.tolist(), Dose.tolist()


def reorderJawPos(jaw1, jaw2):
    jaw = []
    for i in range(0, len(jaw1)):
        currJaw = []
        currJaw.append(jaw1[i])
        currJaw.append(jaw2[i])
        jaw.append(currJaw)
    return jaw


def rescaleMUindx(MUindx, corrBeams, MUs):
    MUindx2 = MUindx
    for i in range(0, len(corrBeams)):
        # get the cummulative max MUindx
        #maxMU = sum(MUs[corrBeams[0]:corrBeams[i+1]])
        #maxIndx = maxMU/sum(MUs)
        # get the cummulative min MUindx
        #if i == 0:
        #    minMU = 0
        #else:
        #    minMU = MUindx[corrBeams[i-1]][len(MUindx[corrBeams[i-1]])-1]
        # renormalize
        scale = MUs[corrBeams[i]] / math.fsum(MUs)
        addThis = 0
        if corrBeams[i] != 0:
            for j in range(corrBeams[0], corrBeams[i]):
                addThis += MUs[corrBeams[j]]
            addThis = addThis / math.fsum(MUs)
        for j in range(0, len(MUindx[corrBeams[i]])):
            MUindx2[corrBeams[i]][j] = MUindx[corrBeams[i]][j] * scale + addThis
    return MUindx2


def bsf(refFile, fieldFile):
    # open refFile
    f = open(refFile, 'r')
    data = f.read().rstrip().split('\n')
    Dforw = data[0].split()
    Dforw = float(Dforw[1])
    Dbackref = data[1].split()
    Dbackref = float(Dbackref[1])
    doseZone = data[2]
    # close ref file
    f.close()

    # search for doseZone in file, in a sequence
    with open(fieldFile) as ff:
        for line in ff:
            if 'ENERGY DEPOSITED' in line:
                for line in ff:
                    if line.lstrip().startswith(doseZone + ' '):
                        Dback = line.lstrip().rstrip().split()
                        break
    Dback = Dback[2].split('+/-')
    Dback = float(Dback[0])
    return (Dforw + Dbackref) / (Dforw + Dback)


# I think this is no longer used?
def getMachineSpecific(fIn):
    with open(fIn) as ff:
        for line in ff:
            if line.startswith('mlcLib'):
                mlc = mlcLib(cropline(line, 1))
                #setattr(mlc,line.rstrip().split()[0],line.rstrip().split()[1])
            if line.startswith('template'):
                setattr(mlc,line.rstrip().split()[0],line.rstrip().split()[1])
            if line.startswith('templateType'):
                setattr(mlc,line.rstrip().split()[0],line.rstrip().split()[1])
            #    templateType = cropline(line,1)
            if line.startswith('MLCtype'):
                setattr(mlc,line.rstrip().split()[0],line.rstrip().split()[1])
            if line.startswith('nLeafs'):
                setattr(mlc,line.rstrip().split()[0],int(line.rstrip().split()[1]))
            #    MLCtype = cropline(line,1)
            if line.startswith('SCD'):
                setattr(mlc,line.rstrip().split()[0],float(line.rstrip().split()[1]))
            if line.startswith('SAD'):
                setattr(mlc,line.rstrip().split()[0],float(line.rstrip().split()[1]))
            if line.startswith('leafRadius'):
                setattr(mlc,line.rstrip().split()[0],float(line.rstrip().split()[1]))
            #    MLCeffZ = cropline(line,1)
            if line.startswith('physLeafOffset'):
                setattr(mlc,line.rstrip().split()[0],float(line.rstrip().split()[1]))
    #return mlcLib, templateType, MLCtype, float(MLCeffZ)
    return mlc


# I dont think this is in use
class mlcLib:
    def __init__(self, MLClib):
        self.mlcLib = MLClib


def cropline(lineIn, item):
    data = lineIn.rstrip().split()
    return data[item]


def getMatrix(raw, shape):
    # read numel elements from raw
    return np.reshape(raw, ((shape[2], shape[1], shape[0])))


class doseInstance:

    def __init__(self):
        pass

    def getShape(self, raw):
        self.shape = np.asarray(map(int, raw[0].split()))
        self.numel = np.sum(self.shape)

    def getCoords(self, raw):
        # get X
        self.X = raw[0:self.shape[0] + 1]
        raw = np.delete(raw, np.arange(self.shape[0] + 1))
        # get Y
        self.Y = raw[0:self.shape[1] + 1]
        raw = np.delete(raw, np.arange(self.shape[1] + 1))
        # get Z
        self.Z = raw[0:self.shape[2] + 1]

    def getDose(self, raw):
        self.dose = getMatrix(raw, self.shape)

    def getUnc(self, raw):
        self.unc = getMatrix(raw, self.shape)


def read3ddose(filename):
    # start by reading the raw data
    with open(filename) as f:
        raw = f.readlines()
    raw = map(str.strip, raw)  # strip
    # initialize instance
    data = doseInstance()
    # get shape
    data.getShape(raw)
    raw.remove(raw[0])  # remove used info
    # pad with whitespace
    raw = ['{0} '.format(elem) for elem in raw]
    # flatten list
    raw = [item for sublist in raw for item in sublist]
    # convert to float
    raw = ''.join(raw).split(' ')
    raw = filter(None, raw)
    raw = map(float, raw)
    # convert to numpy array
    raw = np.asarray(raw)
    # get coords
    data.getCoords(raw[0:data.numel + 3])
    raw = np.delete(raw, np.arange(data.numel + 3))  # removed used info
    # read dose
    data.getDose(raw[0:np.prod(data.shape)])
    raw = np.delete(raw, np.arange(np.prod(data.shape)))  # removed used info
    # read uncertainty
    data.getUnc(raw)

    return data


def writeBound(f, grid, num, decimal):
    for i in range(0, len(grid)):
        if np.mod(i, num) == 0:
            f.write('\n  ')
        if decimal:
            f.write('{0:12.8f} '.format(grid[i]))
        else:
            f.write('{0:12.8e} '.format(grid[i]))


def write3ddose(filename, data):
    f = open(filename, 'w')
    # write num elements and their boundaries
    f.write(' {0:d} {1:d} {2:d}'.format(data.shape[0], data.shape[1], data.shape[2]))
    # write x bound
    writeBound(f, data.X, 6, True)
    # write y bound
    writeBound(f, data.Y, 6, True)
    # write z bound
    writeBound(f, data.Z, 6, True)
    # write dose matrix
    for i in range(0, len(data.dose)):
        for j in range(0, len(data.dose[i])):
            writeBound(f, data.dose[i][j][:], 5, False)
    # write uncerntainty matrix
    for i in range(0, len(data.unc)):
        for j in range(0, len(data.unc[i])):
            writeBound(f, data.unc[i][j][:], 5, True)
    f.write('\n')
    f.close()
    pass


def isstatic(leafPos):
    leafPos = np.asarray(leafPos).transpose().tolist()
    static = []
    for i in range(0, len(leafPos)):
        if len(set(leafPos[i])) == 1:
            static.append(True)
        else:
            static.append(False)
    return np.multiply(static[:len(static) / 2], static[len(static) / 2:])


def remove(baseDir, fileList):
    if type(fileList) != list:  # just one file
        fileList = [fileList]
    fileList = [os.path.join(baseDir, x) for x in fileList]
    for name in fileList:
        try:
            os.remove(name)
        except OSError:
            pass
        except IOError:
            pass


def estUncFromDose(dose, presc, lvl=0.707):
    unc =  np.sqrt(presc) / np.sqrt(dose) * lvl
    unc = np.where(dose > presc, lvl, unc)
    return unc

    
def isOpen(ip, port=22):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        s.shutdown(2)
        return True
    except:
        return False
