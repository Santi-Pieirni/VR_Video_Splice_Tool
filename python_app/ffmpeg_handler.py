import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal


class FFmpegHandler(QObject):
    """Handler for FFmpeg video splicing operations."""

    progress_updated = pyqtSignal(str)
    operation_complete = pyqtSignal(bool, str)
    segment_created = pyqtSignal(str)
    progress_percentage = pyqtSignal(int)

    def __init__(self, ffmpeg_path="C:\\ffmpeg\\bin\\ffmpeg.exe"):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")
        self.project_root = Path(__file__).resolve().parent.parent
        self.temp_root = self.project_root / ".splice_temp"
        self.current_operation_dir = None

        if not os.path.exists(self.ffmpeg_path):
            print(f"Warning: FFmpeg not found at {self.ffmpeg_path}")

        # Remove operation directories left by a previous crash or forced exit.
        self.cleanup_stale_temp_dirs()

    def cleanup_stale_temp_dirs(self):
        """Remove abandoned operation directories from previous runs."""
        try:
            if not self.temp_root.exists():
                return
            for operation_dir in self.temp_root.iterdir():
                if operation_dir.is_dir():
                    shutil.rmtree(operation_dir, ignore_errors=True)
            if not any(self.temp_root.iterdir()):
                self.temp_root.rmdir()
        except OSError as e:
            print(f"Warning: could not clean stale temporary files: {e}")

    def cleanup_current_operation(self):
        """Remove the temporary directory for the active operation."""
        if self.current_operation_dir is None:
            return
        try:
            shutil.rmtree(self.current_operation_dir, ignore_errors=True)
        finally:
            self.current_operation_dir = None
            try:
                if self.temp_root.exists() and not any(self.temp_root.iterdir()):
                    self.temp_root.rmdir()
            except OSError:
                pass

    def cleanup(self):
        """Clean up active and abandoned application temporary files."""
        self.cleanup_current_operation()
        self.cleanup_stale_temp_dirs()

    def detect_codec(self, video_path):
        """Detect video codec using ffprobe."""
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            codec = result.stdout.strip().lower()
            print(f"Detected codec: {codec}")
            return codec
        except subprocess.CalledProcessError as e:
            print(f"Error detecting codec: {e}")
            return None
        except OSError as e:
            # FileNotFoundError and other OS-level issues end up here
            print(f"Unexpected OS error when detecting codec: {e}")
            return None

    def extract_video_metadata(self, video_path):
        """Extract comprehensive video metadata using ffprobe and print to console."""
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-print_format",
                "json",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            import json
            metadata = json.loads(result.stdout)

            print("\n" + "="*60)
            print("VIDEO METADATA")
            print("="*60)

            # Format information
            if "format" in metadata:
                fmt = metadata["format"]
                print(f"\nFile: {fmt.get('filename', 'N/A')}")
                print(f"Format: {fmt.get('format_name', 'N/A')}")
                print(f"File Size: {self._format_bytes(int(fmt.get('size', 0)))}")

                duration = float(fmt.get('duration', 0))
                print(f"Duration: {self._format_duration(duration)}")
                print(f"Bitrate: {fmt.get('bit_rate', 'N/A')} bps")

            # Stream information
            if "streams" in metadata:
                video_streams = [s for s in metadata["streams"] if s.get("codec_type") == "video"]
                audio_streams = [s for s in metadata["streams"] if s.get("codec_type") == "audio"]

                # Video streams
                if video_streams:
                    print("\n--- VIDEO STREAM(S) ---")
                    for i, stream in enumerate(video_streams):
                        print(f"\nStream #{i}:")
                        print(f"  Codec: {stream.get('codec_name', 'N/A')} ({stream.get('codec_long_name', 'N/A')})")
                        print(f"  Resolution: {stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}")
                        print(f"  Aspect Ratio: {stream.get('display_aspect_ratio', 'N/A')}")
                        print(f"  FPS: {stream.get('r_frame_rate', 'N/A')}")
                        print(f"  Bitrate: {stream.get('bit_rate', 'N/A')} bps")
                        print(f"  Profile: {stream.get('profile', 'N/A')}")
                        print(f"  Level: {stream.get('level', 'N/A')}")
                        if "side_data_list" in stream:
                            print(f"  Side Data: {stream['side_data_list']}")

                # Audio streams
                if audio_streams:
                    print("\n--- AUDIO STREAM(S) ---")
                    for i, stream in enumerate(audio_streams):
                        print(f"\nStream #{i}:")
                        print(f"  Codec: {stream.get('codec_name', 'N/A')} ({stream.get('codec_long_name', 'N/A')})")
                        print(f"  Sample Rate: {stream.get('sample_rate', 'N/A')} Hz")
                        print(f"  Channels: {stream.get('channels', 'N/A')}")
                        print(f"  Channel Layout: {stream.get('channel_layout', 'N/A')}")
                        print(f"  Bitrate: {stream.get('bit_rate', 'N/A')} bps")
                        print(f"  Language: {stream.get('tags', {}).get('language', 'N/A')}")

            print("\n" + "="*60 + "\n")
            return metadata

        except subprocess.CalledProcessError as e:
            print(f"Error extracting metadata: {e}")
            return None
        except (OSError, json.JSONDecodeError) as e:
            print(f"Unexpected error extracting metadata: {e}")
            return None

    def _format_bytes(self, bytes_value):
        """Format bytes into human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} TB"

    def _format_duration(self, seconds):
        """Format duration in seconds to HH:MM:SS.ms format."""
        if not seconds or seconds < 0:
            return "N/A"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def get_codec_parameters(self, codec):
        """Get FFmpeg parameters based on codec."""
        if codec == "h264":
            return {"vcodec": "libx264", "crf": "18", "preset": "medium", "tag": ""}
        if codec in ["hevc", "h265"]:
            return {
                "vcodec": "libx265",
                "crf": "20",
                "preset": "medium",
                "tag": "-tag:v hvc1",
            }
        if codec == "av1":
            return {"vcodec": "libaom-av1", "crf": "20", "preset": "medium", "tag": ""}
        print(f"Unknown codec {codec}, using h264")
        return {"vcodec": "libx264", "crf": "18", "preset": "medium", "tag": ""}

    def create_segment(
        self, input_video, start_time, end_time, output_file, codec=None
    ):
        """Create a keyframe-aligned segment using stream copy."""
        try:
            self.progress_updated.emit(f"Creating segment: {start_time} to {end_time}")
            duration = self.calculate_duration(start_time, end_time)
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-ss",
                start_time,
                "-i",
                input_video,
                "-t",
                str(duration),
                "-c",
                "copy",
                "-map_metadata",
                "0",
                output_file,
            ]
            self.progress_updated.emit(f"Running FFmpeg: {' '.join(cmd)}")
            # Explicitly set check=False so failures are reported via return code
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                self.progress_updated.emit(f"Segment created: {output_file}")
                self.segment_created.emit(output_file)
                return True
            error_msg = result.stderr if result.stderr else "Unknown error"
            self.progress_updated.emit(f"FFmpeg error: {error_msg}")
            return False
        except OSError as e:
            self.progress_updated.emit(f"OS error creating segment: {e}")
            return False
        except ValueError as e:
            self.progress_updated.emit(f"Invalid timestamp: {e}")
            return False

    def calculate_duration(self, start_time, end_time):
        """Calculate a positive duration from HH:MM:SS timestamps."""
        try:

            def parse_time(time_str):
                parts = time_str.split(":")
                if len(parts) != 3:
                    raise ValueError(f"Invalid timestamp: {time_str}")
                h, m, s = map(int, parts)
                if h < 0 or not 0 <= m < 60 or not 0 <= s < 60:
                    raise ValueError(f"Invalid timestamp: {time_str}")
                return h * 3600 + m * 60 + s

            duration = parse_time(end_time) - parse_time(start_time)
            if duration <= 0:
                raise ValueError(
                    f"End time must be after start time: {start_time} -> {end_time}"
                )
            return duration
        except (AttributeError, TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid segment timestamps: {start_time} -> {end_time}"
            ) from e

    def _write_concat_file(self, concat_file, segment_files):
        """Write an FFmpeg concat manifest with safely quoted paths."""
        with open(concat_file, "w", encoding="utf-8", newline="\n") as f:
            for segment_file in segment_files:
                path = Path(segment_file).resolve().as_posix()
                # Escape single quotes while preserving valid Windows paths elsewhere.
                escaped = path.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")

    def splice_segments(self, input_video, segments, output_file):
        """Splice segments together using the FFmpeg concat demuxer."""
        try:
            self.progress_updated.emit(f"Splicing {len(segments)} segments together")
            concat_file = self.current_operation_dir / "segments.txt"
            self._write_concat_file(concat_file, segments)
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-map_metadata",
                "0",
                output_file,
            ]
            self.progress_updated.emit(f"Running FFmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0 and os.path.exists(output_file):
                self.progress_updated.emit(f"Final output created: {output_file}")
                return True
            error_msg = result.stderr if result.stderr else "Unknown error"
            self.progress_updated.emit(f"FFmpeg error: {error_msg}")
            return False
        except OSError as e:
            self.progress_updated.emit(f"OS error splicing segments: {e}")
            return False

    def cleanup_temp_files(self, pattern="segment_*.mp4"):
        """Clean up temporary segment files in the active operation only."""
        if self.current_operation_dir is None:
            return
        for temp_file in self.current_operation_dir.glob(pattern):
            try:
                temp_file.unlink()
                self.progress_updated.emit(f"Cleaned up: {temp_file}")
            except OSError as e:
                print(f"Error cleaning up {temp_file}: {e}")

    def process_video(self, input_video, segments, output_name):
        """Create, concatenate, and clean up video segments."""
        try:
            self.progress_updated.emit(f"Starting video processing for {input_video}")
            self.temp_root.mkdir(parents=True, exist_ok=True)
            self.current_operation_dir = Path(
                tempfile.mkdtemp(prefix="operation_", dir=self.temp_root)
            )

            input_name = Path(input_video).stem
            output_file = f"Spliced_{input_name}.mp4"
            segment_files = []
            total_steps = len(segments) + 1  # segments + final splice

            for i, (start, end) in enumerate(segments):
                segment_file = self.current_operation_dir / f"segment_{i + 1}.mp4"
                segment_files.append(segment_file)
                if not self.create_segment(input_video, start, end, str(segment_file)):
                    self.operation_complete.emit(
                        False, f"Failed to create segment {i + 1}"
                    )
                    return False
                # Emit progress after each segment
                progress = int((i + 1) / total_steps * 100)
                self.progress_percentage.emit(progress)

            if not self.splice_segments(input_video, segment_files, output_file):
                self.operation_complete.emit(False, "Failed to splice segments")
                return False

            # Emit 100% completion
            self.progress_percentage.emit(100)
            self.operation_complete.emit(True, f"Processing complete: {output_file}")
            return True
        except (OSError, RuntimeError, ValueError) as e:
            self.operation_complete.emit(False, f"Processing error: {e!s}")
            return False
        finally:
            self.cleanup_current_operation()
