@echo off
setlocal enabledelayedexpansion

REM === FFmpeg path ===
set FF=C:\Users\Santi Pierini\Downloads\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe

echo.
set /p INPUT=Enter input video filename (with extension): 

echo.
echo Starting interactive segment creator...
echo.

REM === Remove old concat list if exists ===
if exist segments.txt del segments.txt

set COUNT=0

:segment_loop
set /a COUNT+=1
echo Segment !COUNT!:

REM === Ask for timestamps WITHOUT colons ===
set /p RAWSTART=  Enter START timestamp as 6 digits (hhmmss): 
set /p RAWEND=    Enter END   timestamp as 6 digits (hhmmss): 

REM === Auto-insert colons ===
set START=!RAWSTART:~0,2!:!RAWSTART:~2,2!:!RAWSTART:~4,2!
set END=!RAWEND:~0,2!:!RAWEND:~2,2!:!RAWEND:~4,2!

echo.
echo Trimming segment !COUNT!: !START! to !END!
"%FF%" -i "%INPUT%" -ss !START! -to !END! -c copy -map_metadata 0 segment_!COUNT!.mp4

echo file segment_!COUNT!.mp4 >> segments.txt
echo.

set /p MORE=Do you want to add another segment? (y/n): 
if /i "!MORE!"=="y" goto segment_loop

echo.
echo Splicing all segments together...
"%FF%" -f concat -safe 0 -i segments.txt -c copy -map_metadata 0 final_spliced_output.mp4

echo.
echo Done! Your final file is: final_spliced_output.mp4
pause
