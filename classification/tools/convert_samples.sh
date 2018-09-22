#!/bin/bash
# This script was made to convert flacs from a spot on the website onto web-friendly format.
# It is saved because cut is complicated and I don't have the heart to delete it.
curl http://orcasound.net/data/product/SRKW/call-catalog/Ford-osborne-tape-analysis+flac-no-narration/Archive-ford-osborne-SRKW-calls-no-narration-flac.zip > soundsofthe80s.zip
unzip soundsofthe80s.zip
mkdir -p converted_samples_ogg
mkdir -p converted_samples_mp3
for i in $(seq -f "%02g" 1 46); do
	classstring+=" converted_samples/call$i"
	j=0
	for fn in FordOsborneTape-analysis/FO-S$i*.flac; do
		ffmpeg -i $fn converted_samples_ogg/$(echo $fn | cut --complement -c '-25' | rev | cut -c "6-" | rev).ogg
		ffmpeg -i $fn converted_samples_mp3/$(echo $fn | cut --complement -c '-25' | rev | cut -c "6-" | rev).mp3
		j=$(expr $j + 1)
		#mv $fn converted_samples/call$i
	done
done

zip -r converted_samples.zip converted_samples_ogg converted_samples_mp3
rm -rf soundsofthe80s.zip
rm -rf FordOsborneTape-analysis
rm -rf converted_samples_ogg
#rm -rf converted_samples_mp3
