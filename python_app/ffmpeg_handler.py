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

    def get_video_duration(self, video_path):
        """Get the total duration of the video in seconds using ffprobe."""
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                video_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            duration = float(result.stdout.strip())
            print(f"Video duration: {duration} seconds")
            return duration
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            print(f"Error getting video duration: {e}")
            return None

    def detect_keyframes(self, video_path, start_seconds=None, end_seconds=None):
        """Detect keyframe timestamps in the video using ffprobe.

        Args:
            video_path: Path to the video file
            start_seconds: Optional start time in seconds (scans from this point)
            end_seconds: Optional end time in seconds (scans until this point)

        Returns:
            List of keyframe timestamps in seconds
        """
        try:
            cmd = [
                self.ffprobe_path,
                "-v",
                "error",
                "-skip_frame",
                "nokey",
                "-select_streams",
                "v:0",
                "-show_entries",
                "frame=pkt_pts_time,pict_type",
                "-of",
                "csv=p=0",
            ]

            # ffprobe uses a start%duration interval, not a start%end absolute offset.
            if start_seconds is not None or end_seconds is not None:
                interval_start = float(start_seconds) if start_seconds is not None else 0.0
                if end_seconds is not None:
                    interval_end = float(end_seconds)
                    if interval_end < interval_start:
                        interval_end = interval_start
                    interval_duration = max(0.0, interval_end - interval_start)
                    interval = f"{interval_start}%{interval_duration}"
                else:
                    interval = f"{interval_start}%"
                cmd.extend(["-read_intervals", interval])

            cmd.append(video_path)

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            keyframes = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) >= 2 and parts[1] == "I":
                    try:
                        keyframes.append(float(parts[0]))
                    except ValueError:
                        continue

            # Remove any duplicates while keeping the original ordering.
            seen = set()
            unique_keyframes = []
            for kf in keyframes:
                rounded = round(kf, 6)
                if rounded not in seen:
                    seen.add(rounded)
                    unique_keyframes.append(kf)

            print(f"Detected {len(unique_keyframes)} keyframes in time range")
            return unique_keyframes
        except subprocess.CalledProcessError as e:
            print(f"Error detecting keyframes: {e}")
            return []
        except OSError as e:
            print(f"OS error detecting keyframes: {e}")
            return []

    def snap_to_keyframe(self, timestamp, keyframes, direction="nearest"):
        """Snap a timestamp to the nearest keyframe.

        Args:
            timestamp: Target timestamp in seconds
            keyframes: List of keyframe timestamps
            direction: 'nearest', 'before', or 'after'

        Returns:
            Snapped timestamp in seconds
        """
        if not keyframes:
            return timestamp

        if direction == "before":
            # Find the last keyframe before or at the timestamp
            for kf in reversed(keyframes):
                if kf <= timestamp:
                    return kf
            return keyframes[0]  # Fallback to first keyframe
        elif direction == "after":
            # Find the first keyframe after or at the timestamp
            for kf in keyframes:
                if kf >= timestamp:
                    return kf
            return keyframes[-1]  # Fallback to last keyframe
        else:  # nearest
            # Find the closest keyframe
            closest = min(keyframes, key=lambda kf: abs(kf - timestamp))
            return closest

    @staticmethod
    def parse_hms_to_seconds(time_str):
        """Parse HH:MM:SS or HH:MM:SS.mmm into seconds."""
        if time_str is None:
            raise ValueError("Timestamp cannot be None")
        if isinstance(time_str, (int, float)):
            return float(time_str)

        time_str = str(time_str).strip()
        if not time_str:
            raise ValueError("Timestamp cannot be empty")

        parts = time_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid timestamp: {time_str}")

        try:
            h, m, s = parts
            hours = int(h)
            minutes = int(m)
            seconds = float(s)
        except ValueError as exc:
            raise ValueError(f"Invalid timestamp: {time_str}") from exc

        if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            raise ValueError(f"Invalid timestamp: {time_str}")

        return hours * 3600 + minutes * 60 + seconds

    def format_seconds_to_hms(self, seconds):
        """Convert seconds to HH:MM:SS.mmm format for FFmpeg timestamps."""
        total_ms = int(round(float(seconds) * 1000))
        hours, remainder = divmod(total_ms, 3600 * 1000)
        minutes, remainder = divmod(remainder, 60 * 1000)
        sec_ms = remainder
        sec_total = sec_ms / 1000.0
        return f"{hours:02d}:{minutes:02d}:{sec_total:06.3f}"

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
            duration = self.parse_hms_to_seconds(end_time) - self.parse_hms_to_seconds(
                start_time
            )
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
                "-movflags",
                "faststart",
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
        """Create, concatenate, and clean up video segments with keyframe alignment."""
        try:
            self.progress_updated.emit(f"Starting video processing for {input_video}")
            self.temp_root.mkdir(parents=True, exist_ok=True)
            self.current_operation_dir = Path(
                tempfile.mkdtemp(prefix="operation_", dir=self.temp_root)
            )

            input_name = Path(input_video).stem
            output_file = f"Spliced_{input_name}.mp4"
            segment_files = []

            # Get video duration to cap scan ranges
            video_duration = self.get_video_duration(input_video)

            total_steps = len(segments) + 1  # segments + final splice

            for i, (start, end) in enumerate(segments):
                # Parse timestamps to seconds
                start_seconds = self.parse_hms_to_seconds(start)
                end_seconds = self.parse_hms_to_seconds(end)

                # Detect keyframes only in a small window around this segment.
                # Use 20-second buffer on each side to catch nearby keyframes.
                buffer = 20
                scan_start = max(0.0, start_seconds - buffer)
                scan_end = end_seconds + buffer

                # Cap scan_end at the video duration if available.
                if video_duration is not None:
                    scan_end = min(scan_end, video_duration)

                self.progress_updated.emit(
                    f"Segment {i + 1}: Detecting keyframes in range "
                    f"{self.format_seconds_to_hms(scan_start)} to {self.format_seconds_to_hms(scan_end)}..."
                )
                keyframes = self.detect_keyframes(
                    input_video, start_seconds=scan_start, end_seconds=scan_end
                )

                # Snap to keyframes for cleaner cuts.
                if keyframes:
                    snapped_start = self.snap_to_keyframe(
                        start_seconds, keyframes, direction="before"
                    )
                    snapped_end = self.snap_to_keyframe(
                        end_seconds, keyframes, direction="after"
                    )

                    if video_duration is not None:
                        snapped_end = min(snapped_end, video_duration)

                    # Validate that snapped times are still valid (end > start)
                    if snapped_end <= snapped_start:
                        self.progress_updated.emit(
                            f"Segment {i + 1}: Keyframe snapping produced invalid range, using original timestamps"
                        )
                        start_time = start
                        end_time = end
                    else:
                        snapped_start_hms = self.format_seconds_to_hms(snapped_start)
                        snapped_end_hms = self.format_seconds_to_hms(snapped_end)

                        if abs(snapped_start - start_seconds) > 0.1 or abs(
                            snapped_end - end_seconds
                        ) > 0.1:
                            adjustment_msg = (
                                f"Segment {i + 1}: {start}→{end} adjusted to "
                                f"{snapped_start_hms}→{snapped_end_hms} for keyframe alignment"
                            )
                            self.progress_updated.emit(adjustment_msg)

                        start_time = snapped_start_hms
                        end_time = snapped_end_hms
                else:
                    self.progress_updated.emit(
                        f"Segment {i + 1}: Could not detect keyframes, using original timestamps"
                    )
                    start_time = start
                    end_time = end

                segment_file = self.current_operation_dir / f"segment_{i + 1}.mp4"
                segment_files.append(segment_file)
                if not self.create_segment(input_video, start_time, end_time, str(segment_file)):
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
