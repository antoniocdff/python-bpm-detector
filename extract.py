# coding: utf-8
import os
import zipfile

mypath = os.getcwd()
f = []
for (dirpath, dirnames, filenames) in os.walk(mypath):
    f.extend(filenames)
    break
for file in f:
    filearray = file.split('.zip')
    if len(filearray) > 1:
        filename = mypath+'/'+file
        zip_ref = zipfile.ZipFile(unicode(file), "r")
        folder = unicode(mypath, "utf-8", errors="ignore")+'/'+filearray[0]
        if not os.path.isdir(folder):
            os.makedirs(folder)
        zip_ref.extractall(folder)
