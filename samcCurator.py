import sys
import samcUtil
import os
import time
import glob
from pathlib import Path
import arrow
from subprocess import check_output, call
import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
import tarfile
import shutil
import socket


def getIP():
    return socket.gethostbyname(socket.getfqdn())
    
    
def get_capacity(drive):
    data = check_output(['df', '-P', drive[1]])
    return int(data.split('%')[0].split()[-1])


def send_mail(send_from, send_to, subject, text, files=None,
              server="127.0.0.1"):
    assert isinstance(send_to, list)

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    for f in files or []:
        with open(f, "rb") as fil:
            part = MIMEApplication(
                fil.read(),
                Name=basename(f)
            )
            part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
            msg.attach(part)


    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()



def unlock(file_identifier, timeDelay=0):
    cutoff = arrow.now().shift(hours=-timeDelay)
    for item in Path().glob(file_identifier):
        if item.is_file() and arrow.get(item.stat().st_mtime) < cutoff:
            os.remove(str(item.absolute()))


def queue_empty():
    usr = os.getenv('USER')
    try:
        return not check_output(['qstat', '-u', usr])
    except Exception:
        return False
    
def job_recycle(job, cv):
    # clean up auxillary files
    removeFiles = glob.glob(os.path.join(cv.EGS_HOME, cv.dosxyznrc,
    job) + '*')
    removeFiles = [x for x in removeFiles if not x.endswith('.egsinp')]
    for name in removeFiles:
        os.remove(name)

    # initialize DOSXYZnrc simulation
    HEN_HOUSE = os.environ.get('HEN_HOUSE')
    exb = 'scripts/run_user_code_batch'
    exbCall = ''.join([HEN_HOUSE, exb])
    call([exbCall, cv.dosxyznrc, job, cv.dosPegs,
        '='.join(['p', str(int(cv.nBatch))])])


def main():
    # change dir to where the script is
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)
    
    # get variables from confFile
    confFile = 'samc.conf'
    with open(confFile) as f:
        confCont = f.readlines()
    whatToGet = ['common.smtpserver', 'common.mailTo', 
        'common.mailFrom', 'common.dosxyzDir', 'daemonC.dosxyznrc',
        'daemonC.dosPegs', 'daemonC.nBatch', 'common.EGS_HOME',
        'common.DICOMinDir', 'common.DICOMoutDir']
    # generate struct
    cv = samcUtil.struct()
    # read variables
    cv = samcUtil.getConfVars(cv, whatToGet, confCont)
    
    #---mail jam/log files---
    jamlogs = ['*.jam', '*.log']
    for jl in jamlogs:
	    jls = glob.glob(jl)
	    if jls:
                send_mail(cv.mailFrom, [cv.mailTo], 'SAMC jammed', 
                'jam files attached\n', files=glob.glob(jl), 
                server=cv.smtpserver)
            unlock(jl)
    
    #---unlock---
    timeDelayLock = 4
    unlock('*.lock', timeDelay=timeDelayLock)
        
    #---recycle jobs---
    # ***** base this on pardose files, with a time offset of 4 hours!!!
    if queue_empty():
        cutoff = arrow.now().shift(hours=-timeDelayLock)
        lockList = [x for x in Path(cv.dosxyzDir).glob('*.egsinp') if x.is_file() and arrow.get(x.stat().st_mtime) < cutoff]
        lockList = [str(x.absolute()) for x in lockList]
        lockList = [os.path.basename(x).split('_')[0] for x in lockList if os.path.isdir(os.path.join(dname,
            os.path.basename(x).split('_')[0]))]
        lockList = list(set(lockList))
        #print lockList, len(lockList)
        for lock in lockList:
            try:
                job_recycle(os.path.splitext(os.path.basename(lock))[0], cv)
                pass
            except Exception:
                pass
                
    #---back up to USB disk and delete old---
    backDir = '/home/mcqa/usb-backup/MCQA/'
    backTypes = ['*dcm', '*keepTrack']
    deleteDelay = 10
    cutoff = arrow.now().shift(days=-deleteDelay)
    directories = [str(x) for x in Path().glob('*') if os.path.isdir(str(x)) and arrow.get(x.stat().st_mtime) < cutoff and len(glob.glob(os.path.join(str(x), '*keepTrack'))) > 0]
    for directory in directories:
        try:
            with tarfile.open(os.path.join(backDir, directory + '.tar.gz'), "w:gz") as tar:
                for fileType in backTypes:
                    fileList = glob.glob(os.path.join(directory, fileType))
                    for name in fileList:
                        tar.add(name)
            for item in glob.glob(directory + '*'):
                if os.path.isdir(item):
                    shutil.rmtree(item)
                elif os.path.isfile(item):
                    os.remove(item)
        except Exception:
            pass
            
    #---delete files from DICOMinDir/DICOMoutDir---
    for directory in [cv.DICOMinDir, cv.DICOMoutDir]:
        for item in Path(directory).glob('*'):
            if item.is_file() and arrow.get(item.stat().st_mtime) < cutoff:
                os.remove(str(item.absolute()))
                
                
    #---check available disk space---
    drives = [('home', '/dev/sdb5'), ('external', '/mnt/2261d663-d545-4215-b191-97451c7e9979')]
    mail_at_capacity = 80
    for d in drives:
        capacity = get_capacity(d)
        if capacity > mail_at_capacity:
            send_mail(cv.mailFrom, [cv.mailTo], 
            'SAMC {:s} low disk space'.format(d[0]), 
            'The available disk space of {:s} ({:s}) on {:s} is low.\nThe disk is {:d}% full.'.format(d[0], d[1], getIP(), capacity),
            server=cv.smtpserver)

# Function chooser
func_arg = {"-main": main}
# run specifc function as called from command line
if __name__ == "__main__":
    if sys.argv[1] == "-main":
        func_arg[sys.argv[1]]()
