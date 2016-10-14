#!/usr/bin/python

import sys
import os
import shutil

fileNameOut = sys.argv[1]
DICOMoutDir = sys.argv[2]

shutil.copy2(fileNameOut,DICOMoutDir)
