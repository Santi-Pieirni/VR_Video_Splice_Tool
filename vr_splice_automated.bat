@echo off
setlocal enabledelayedexpansion

REM === FFmpeg path ===
set FF=C:\ffmpeg\bin\ffmpeg.exe

echo.
set /p INPUT=Enter input video filename (with extension): 

REM === Check if file exists ===
if not exist "%INPUT%" (
    echo ERROR: File "%INPUT%" not found!
    pause
    exit /b 1
)

REM === Extract filename without extension for output ===
for %%F in ("%INPUT%") do set "NAME=%%~nF"
set "OUTPUT=Spliced_%NAME%.mp4"

echo.
echo Starting interactive segment creator with keyframe-aligned cuts...
echo.

echo Starting interactive segment creator...
echo.

REM === Remove old concat list and segments if exists ===
if exist segments.txt del segments.txt
for %%f in (segment_*.mp4) do del "%%f"

set COUNT=0

:segment_loop
set /a COUNT+=1
echo Segment !COUNT!:

REM === Ask for timestamps - support both formats ===
set /p START=  Enter START timestamp (HH:MM:SS or HHMMSS): 
set /p END=    Enter END   timestamp (HH:MM:SS or HHMMSS): 

REM === Auto-format timestamps if no colons ===
if "!START!"==":*:*" (
    REM Already has colons, keep as is
) else if "!START:~2,1!"==":" (
    REM Already has colons, keep as is
) else (
    REM No colons, auto-insert them
    set START=!START:~0,2!:!START:~2,2!:!START:~4,2!
)

if "!END!"==":*:*" (
    REM Already has colons, keep as is
) else if "!END:~2,1!"==":" (
    REM Already has colons, keep as is
) else (
    REM No colons, auto-insert them
    set END=!END:~0,2!:!END:~2,2!:!END:~4,2!
)

echo.
echo Trimming segment !COUNT!: !START! to !END!
echo [Processing with keyframe-aligned copy...]

REM === Calculate duration in seconds ===
REM Parse HH:MM:SS format
set /a START_H=!START:~0,2!
set /a START_M=!START:~3,2!
set /a START_S=!START:~6,2!
set /a START_TOTAL=(!START_H!*3600)+(!START_M!*60)+!START_S!

set /a END_H=!END:~0,2!
set /a END_M=!END:~3,2!
set /a END_S=!END:~6,2!
set /a END_TOTAL=(!END_H!*3600)+(!END_M!*60)+!END_S!

set /a DURATION=!END_TOTAL!-!START_TOTAL!

"%FF%" -ss !START! -i "%INPUT%" -t !DURATION! -c copy -map_metadata 0 segment_!COUNT!.mp4

if not exist segment_!COUNT!.mp4 (
    echo ERROR: Failed to create segment !COUNT!
    pause
    exit /b 1
)

echo [Done] Segment !COUNT! created successfully
echo file segment_!COUNT!.mp4 >> segments.txt
echo.

set /p MORE=Do you want to add another segment? (y/n): 
if /i "!MORE!"=="y" goto segment_loop

echo.
echo Splicing all segments together...
"%FF%" -f concat -safe 0 -i segments.txt -c copy -map_metadata 0 "%OUTPUT%"

if not exist "%OUTPUT%" (
    echo ERROR: Failed to create final output
    pause
    exit /b 1
)

echo.
echo Done! Your final file is: %OUTPUT%
echo.
echo Cleanup: Removing temporary segment files...
for %%f in (segment_*.mp4) do del "%%f"
if exist segments.txt del segments.txt
echo Cleanup complete.

pause
