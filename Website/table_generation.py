# -*- coding: utf-8 -*-
"""
Created on Sat Sep 22 14:49:00 2018
@author: kmuss
Modified on Fri Dec 07 23:18:00 2018
@author: scottveirs
"""

from os import listdir
from os.path import isfile, join

#Please update this to YOUR path to orcadata
#basePath = r"C:\Users\kmuss\Desktop"
basePath = r"/Users/scott/Dropbox/Scottcoding/Orcasound/"

#plotPath = join(basePath, "orcadata", "spectrogram", "Plots")
folderpath_flac = join(basePath, "orcadata", "Sounds", "catalog", "flac")
onlyfiles = sorted([f for f in listdir(folderpath_flac) if isfile(join(join(folderpath_flac, f)))])
htmlpath = join(basePath, "orcadata", "Website")
base_URL = "http://www.orcasound.net/data/product/SRKW/call-catalog/no-narration_flac+mp3+ogg+spectrograms/"
title_text = "Sound spectrum table"

f = open(join(htmlpath, "spectrum_comparison.html"), "w")
f.write("<html>\n\n<head>\n<title>" + title_text + "</title>\n</head>\n\n<body>\n<h2>" + title_text + "</h2>\n ")
f.write("<table>\n")
for file in onlyfiles:
    file_name = file.split(".")[0]
    heading = file_name.split('-')[1]
    f.write("<tr>\n<td>\n")
    f.write("<h3>" + heading + "<h3>\n")
    f.write("<audio controls>\n")
    f.write("<source src=\"" + base_URL + "mp3/" + file_name + ".mp3\" " 'type="audio/mp3">\n')
    f.write("<source src=\"" + base_URL + "ogg/" + file_name + ".ogg\" " 'type="audio/ogg">\n')
    f.write("</audio>\n")
    f.write("</td>\n")
    f.write("<td> <img src=\"" + base_URL + "spectrogram-pngs/" + file_name + ".png\"> </td>\n")
    f.write("<td> <img src=\"" + "http://www.orcasound.net/data/raw/SRKW-Ford-Osborne-tapes/Ford89-SRKW-spectrograms/" + heading + ".png\"> </td>\n")
    f.write("</tr>\n")
f.write("</table>\n</body>\n</html>")

