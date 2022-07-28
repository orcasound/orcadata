# This shell script is Scott's quick-n-dirty way to pull down part of an Orcasound S3 bucket. 
# It uses `s3 sync` AWS CLI command to get all HLS .ts segment objects (usually 6 or 24 hours worth), 
# and then uses `ffmpeg` to concatenates them and transcode to mp3 format
# Scott Veirs, latest update 28 July 2022

# This version uses the two command line variables (1 & 2 below)
#1 node name (one string with underscores, e.g. bush_point (NOTE: no leading rpi_ !)
#2 UNIX timestamp of desired S3 folder within the nodes hls folder

# A future/improved version could take the a start and stop datetime (in local time, rather than GMT?) 
# so there isn't a need to search (manually, for Scott) for the S3 folder name within the HLS directory
#3 Start time in hours after the UNIX timestamp
#4 Stop time in hours after the UNIX timestamp

# An additional improvement could be to add some logic to skip downloading data that isn't between the desired start and stop times
# i.e. within aws sync call or in the for loop (delete some .ts segments; rename others)

echo "You provided $# arguments: $1, $2, $3, and $4"
aws s3 sync s3://streaming-orcasound-net/rpi_$1/hls/$2/ .
for file in live*; do mv "$file" "${file#live}"; done;
for i in *.ts ; do
    mv $i `printf '%04d' ${i%.ts}`.ts
done
printf "file '%s'\n" ./*.ts > mylist.txt
ffmpeg -f concat -safe 0 -i mylist.txt -c copy all.ts
ffmpeg -i all.ts -c:v libx264 -c:a copy -bsf:a aac_adtstoasc output.mp4
ffmpeg -i output.mp4 output.mp3
rm *.ts output.mp4 mylist.txt
