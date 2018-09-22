# -*- coding: utf-8 -*-
"""
Created on Sat Sep 22 14:49:00 2018

@author: kmuss
"""
from os import listdir
from os.path import isfile, join

#Please update this to YOUR path to orcadata
basePath = r"C:\Users\kmuss\Desktop"

#plotPath = join(basePath, "orcadata", "spectrogram", "Plots")
folderpath_flac = join(basePath, "orcadata", "Sounds", "catalog", "flac")
onlyfiles = [f for f in listdir(folderpath_flac) if isfile(join(join(folderpath_flac, f)))]
#folderpath_mp3 = join(basePath, "orcadata", "Sounds", "catalog", "mp3")
#folderpath_ogg = join(basePath, "orcadata", "Sounds", "catalog", "ogg")
htmlpath = join(basePath, "orcadata", "Website")
github_link = "https://github.com/orcasound/orcadata/Sounds/catalog/"


f = open(join(htmlpath, "spectrum_comparison.html"), "w")
f.write("<table>\n")
for file in onlyfiles:
    file_name = file.split(".")[0]
    heading = file_name.split('-')[1]
    f.write("<tr>\n")
    f.write("<h3>" + heading + "<h3>")
    f.write("<audio controls> <source src=" + github_link + "/mp3/" + file_name + ".mp3"
            'type="audio/mp3">')
    f.write("<source src=" + github_link + "/ogg/" + file_name + ".ogg"
            'type="audio/ogg">'))
 
    """
Still need to add 
new spectrum 
old spectrum 
close <tr>
close table 

"""   