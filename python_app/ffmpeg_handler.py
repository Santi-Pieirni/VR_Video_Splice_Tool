import subprocess
import os
import glob
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal

class FFmpegHandler(QObject):
    """Handler for FFmpeg video splicing operations"""
    
    progress_updated = pyqtSignal(str)  # Progress updates
    operation_complete = pyqtSignal(bool, str)  # (success, message)
    segment_created = pyqtSignal(str)  # When a segment is created
    
    def __init__(self, ffmpeg_path="C:\\ffmpeg\\bin\\ffmpeg.exe"):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")
        
        # Verify FFmpeg is available
        if not os.path.exists(self.ffmpeg_path):
            print(f"Warning: FFmpeg not found at {self.ffmpeg_path}")
    
    def detect_codec(self, video_path):
        """Detect video codec using ffprobe"""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            codec = result.stdout.strip().lower()
            print(f"Detected codec: {codec}")
            return codec
            
        except subprocess.CalledProcessError as e:
            print(f"Error detecting codec: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def get_codec_parameters(self, codec):
        """Get FFmpeg parameters based on codec"""
        if codec == "h264":
            return {
                "vcodec": "libx264",
                "crf": "18",
                "preset": "medium",
                "tag": ""
            }
        elif codec in ["hevc", "h265"]:
            return {
                "vcodec": "libx265",
                "crf": "20",
                "preset": "medium",
                "tag": "-tag:v hvc1"
            }
        elif codec == "av1":
            return {
                "vcodec": "libaom-av1",
                "crf": "20",
                "preset": "medium",
                "tag": ""
            }
        else:
            # Default to h264
            print(f"Unknown codec {codec}, using h264")
            return {
                "vcodec": "libx264",
                "crf": "18",
                "preset": "medium",
                "tag": ""
            }
    
    def create_segment(self, input_video, start_time, end_time, output_file, codec=None):
        """Create a video segment using keyframe-aligned cutting with stream copy (matches batch script exactly)"""
        try:
            self.progress_updated.emit(f"Creating segment: {start_time} to {end_time}")
            
            # Calculate duration (matches batch script logic)
            duration = self.calculate_duration(start_time, end_time)
            
            # Build FFmpeg command matching batch script exactly:
            # -ss before -i for keyframe alignment
            # -t for duration (not -to)
            # -c copy for stream copy (no quality loss)
            # -map_metadata 0 for VR metadata preservation
            cmd = [
                self.ffmpeg_path,
                "-ss", start_time,
                "-i", input_video,
                "-t", str(duration),
                "-c", "copy",
                "-map_metadata", "0",
                output_file
            ]
            
            # Run FFmpeg command
            self.progress_updated.emit(f"Running FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.progress_updated.emit(f"Segment created: {output_file}")
                self.segment_created.emit(output_file)
                return True
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.progress_updated.emit(f"FFmpeg error: {error_msg}")
                return False
                
        except Exception as e:
            self.progress_updated.emit(f"Error creating segment: {str(e)}")
            return False
    
    def calculate_duration(self, start_time, end_time):
        """Calculate duration between two timestamps in HH:MM:SS format"""
        try:
            # Parse HH:MM:SS format
            def parse_time(time_str):
                parts = time_str.split(':')
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    return h * 3600 + m * 60 + s
                return 0
            
            start_seconds = parse_time(start_time)
            end_seconds = parse_time(end_time)
            
            duration = end_seconds - start_seconds
            return max(0, duration)
            
        except Exception as e:
            print(f"Error calculating duration: {e}")
            return 0
    
    def splice_segments(self, input_video, segments, output_file):
        """Splice multiple segments together using concat demuxer (matches batch script exactly)"""
        try:
            self.progress_updated.emit(f"Splicing {len(segments)} segments together")
            
            # Create concat list file (matches batch script)
            concat_file = "segments.txt"
            with open(concat_file, "w") as f:
                for segment_file in segments:
                    f.write(f"file {segment_file}\n")
            
            # FFmpeg concat command matching batch script exactly
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                "-map_metadata", "0",
                output_file
            ]
            
            # Run FFmpeg command
            self.progress_updated.emit(f"Running FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Check if output file was created (matches batch script error handling)
            if not os.path.exists(output_file):
                self.progress_updated.emit("ERROR: Failed to create final output")
                return False
            
            # Clean up concat file (matches batch script cleanup)
            if os.path.exists(concat_file):
                os.remove(concat_file)
            
            if result.returncode == 0:
                self.progress_updated.emit(f"Final output created: {output_file}")
                return True
            else:
                error_msg = result.stderr if result.stderr else "Unknown error"
                self.progress_updated.emit(f"FFmpeg error: {error_msg}")
                return False
                
        except Exception as e:
            self.progress_updated.emit(f"Error splicing segments: {str(e)}")
            return False
    
    def cleanup_temp_files(self, pattern="segment_*.mp4"):
        """Clean up temporary segment files"""
        try:
            temp_files = glob.glob(pattern)
            for temp_file in temp_files:
                os.remove(temp_file)
                self.progress_updated.emit(f"Cleaned up: {temp_file}")
        except Exception as e:
            print(f"Error cleaning up temp files: {e}")
    
    def process_video(self, input_video, segments, output_name):
        """Complete video processing workflow (matches batch script behavior)"""
        try:
            self.progress_updated.emit(f"Starting video processing for {input_video}")
            
            # Create output filename matching batch script
            input_name = Path(input_video).stem
            output_file = f"Spliced_{input_name}.mp4"
            
            # Create temporary segments matching batch script naming
            segment_files = []
            for i, (start, end) in enumerate(segments):
                segment_file = f"segment_{i+1}.mp4"
                segment_files.append(segment_file)
                
                if not self.create_segment(input_video, start, end, segment_file):
                    self.operation_complete.emit(False, f"Failed to create segment {i+1}")
                    return False
            
            # Splice segments together
            if not self.splice_segments(input_video, segment_files, output_file):
                self.operation_complete.emit(False, "Failed to splice segments")
                return False
            
            # Clean up temporary files (matches batch script cleanup)
            self.progress_updated.emit("Cleanup: Removing temporary segment files...")
            self.cleanup_temp_files()
            self.progress_updated.emit("Cleanup complete.")
            
            self.operation_complete.emit(True, f"Processing complete: {output_file}")
            return True
            
        except Exception as e:
            self.operation_complete.emit(False, f"Processing error: {str(e)}")
            return False