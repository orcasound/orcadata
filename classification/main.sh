#!/bin/bash
# Requires:
# ffmpeg
# Installation of pyAudioAnalysis and dependencies on python2
# Basic linux toolchain (zip, cut, etc.)

if [ ! "$1" = "s" ]; then
	# Get the data
	mkdir -p data
	curl http://orcasound.net/data/product/SRKW/call-catalog/Ford-osborne-tape-analysis+flac-no-narration/Archive-ford-osborne-SRKW-calls-no-narration-flac.zip > data/soundsofthe80s.zip
	unzip data/soundsofthe80s.zip -d data/
	rm data/soundsofthe80s.zip

	# We need some scripts from the github repo so we just clone it because this is a hackathon
	if [ ! -d "pyAudioAnalysis" ]; then
		git clone https://github.com/tyiannak/pyAudioAnalysis.git
	fi

	# Separate each class into its own subdir so pyAudioAnalysis can eat it.
	classstring=""
	mkdir -p data/sorted_samples
	for i in $(seq -f "%02g" 1 46); do
		mkdir -p data/sorted_samples/call$i
		classstring+=" data/sorted_samples/call$i"
		j=0
		for fn in data/FordOsborneTape-analysis/FO-S$i*.flac; do
			ffmpeg -i $fn data/sorted_samples/call$i/$j.wav
			j=$(expr $j + 1)
			#mv $fn sorted_samples/call$i
		done
	done
fi

python2 pyAudioAnalysis/pyAudioAnalysis/audioAnalysis.py trainClassifier -i $classstring --method knn -o model.arff
# Test it on other data
python2 pyAudioAnalysis/pyAudioAnalysis/audioAnalysis.py segmentClassifyFile -i greatest_hits_01.ogg --model knn --modelName model.arff
