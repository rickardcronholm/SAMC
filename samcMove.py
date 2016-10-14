#!/usr/bin/python

import shutil, samcUtil, getpass, pwd, grp, os

# change dir to where the script is
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

# get variables form confFile
confFile = 'samc.conf'
DICOMinDir = samcUtil.getVariable(confFile,'common.DICOMinDir')
DICOMstoreDir = samcUtil.getVariable(confFile,'common.DICOMstoreDir')
DICOMfileEnding = samcUtil.getVariable(confFile,'common.DICOMfileEnding')

# move files
files = os.listdir(DICOMstoreDir)
files.sort()
for f in files:
	if f.endswith(DICOMfileEnding):
		src = DICOMstoreDir+f
		shutil.move(src,DICOMinDir)


#get current user
user = samcUtil.getVariable(confFile,'common.user')
#uid = pwd.getpwnam(user).pw_uid
#gid = grp.getgrnam(user).gr_gid

# change owner of files
allFiles = ''.join([DICOMinDir,'*'])
os.system('chown %(user)s %(allFiles)s' % locals())
os.system('chgrp %(user)s %(allFiles)s' % locals())
