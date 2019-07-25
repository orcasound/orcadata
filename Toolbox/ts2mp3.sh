# pulls down a S3 bucket (all HLS .ts segment objects), then concatenates them and converts to mp3
aws s3 sync s3://streaming-orcasound-net/rpi_orcasound_lab/hls/1542432734/ .
printf "file '%s'\n" ./*.ts > mylist.txt
ffmpeg -f concat -safe 0 -i mylist.txt -c copy all.ts
ffmpeg -i all.ts -c:v libx264 -c:a copy -bsf:a aac_adtstoasc output.mp4
ffmpeg -i output.mp4 output.mp3
