import os
import sys

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ffmpeg_handler import FFmpegHandler
from timeline import TimelinePanel
from video_player import VideoPlayer


class FFmpegWorker(QObject):
    """Runs FFmpeg processing in a background thread."""

    progress_updated = pyqtSignal(str)
    operation_complete = pyqtSignal(bool, str)
    finished = pyqtSignal()

    def __init__(self, input_video, segments):
        super().__init__()
        self.input_video = input_video
        self.segments = segments

    @pyqtSlot()
    def run(self):
        try:
            handler = FFmpegHandler()
            handler.progress_updated.connect(self.progress_updated)
            handler.operation_complete.connect(self.operation_complete)
            handler.process_video(self.input_video, self.segments, "output")
        except (RuntimeError, OSError, ValueError) as exc:
            # Narrow exceptions to expected types; report back to UI
            self.operation_complete.emit(False, str(exc))
        finally:
            self.finished.emit()


class VRSplicerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VR Video Splicer")
        self.setGeometry(100, 100, 1200, 800)

        self.current_video = None
        self.ffmpeg_handler = FFmpegHandler()
        self.ffmpeg_thread = None
        self.ffmpeg_worker = None
        self.close_requested = False
        self.was_playing_before_drag = False
        self.is_dragging = False

        self.init_ui()

    def ffmpeg_installation_is_available(self):
        """Return whether both required FFmpeg executables are installed."""
        return all(
            os.path.isfile(path)
            for path in (
                self.ffmpeg_handler.ffmpeg_path,
                self.ffmpeg_handler.ffprobe_path,
            )
        )

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Title
        title_label = QLabel("VR Video Splicer - 180° Stereoscopic 3D")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # File selection
        self.file_label = QLabel("No video file selected")
        self.file_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.file_label)

        select_button = QPushButton("Select Video File")
        select_button.clicked.connect(self.select_video_file)
        layout.addWidget(select_button)

        # Video player
        self.video_player = VideoPlayer()
        layout.addWidget(self.video_player)

        # Timeline panel (under video player controls)
        self.timeline_panel = TimelinePanel()
        self.timeline_panel.segment_selected.connect(self.on_segment_selected)
        self.timeline_panel.segment_deleted.connect(self.on_segment_deleted)
        self.timeline_panel.seek_to_position.connect(self.on_timeline_seek)
        self.timeline_panel.all_segments_cleared.connect(self.on_all_segments_cleared)
        self.timeline_panel.drag_started.connect(self.on_drag_started)
        self.timeline_panel.drag_ended.connect(self.on_drag_ended)
        layout.addWidget(self.timeline_panel)

        # FFmpeg controls
        ffmpeg_layout = QVBoxLayout()

        # Process button
        self.process_button = QPushButton("Process Video Segments")
        self.process_button.setObjectName("processButton")
        self.process_button.setMinimumHeight(34)
        self.process_button.clicked.connect(self.process_video)
        self.process_button.setEnabled(False)
        ffmpeg_layout.addWidget(self.process_button)

        self.process_button.setStyleSheet(
            """
            #processButton {
                background-color: #6c5ce7;
                color: white;
                border: 1px solid #5849c7;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 14px;
                font-weight: bold;
            }
            #processButton:hover {
                background-color: #5849c7;
            }
            #processButton:pressed {
                background-color: #4637a9;
            }
            #processButton:disabled {
                background-color: #697586;
                border-color: #5b6675;
                color: #cfd4d5;
            }
            """
        )

        # Progress display
        self.progress_label = QLabel("Ready")
        self.progress_label.setStyleSheet("color: gray; font-size: 10px;")
        ffmpeg_layout.addWidget(self.progress_label)

        layout.addLayout(ffmpeg_layout)

        # Connect FFmpeg signals
        self.ffmpeg_handler.progress_updated.connect(self.on_progress_updated)
        self.ffmpeg_handler.operation_complete.connect(self.on_operation_complete)

        # Connect video player signals for timestamp tracking
        self.video_player.in_point_set.connect(self.on_in_point_set)
        self.video_player.out_point_set.connect(self.on_out_point_set)
        self.video_player.pending_in_point_set.connect(self.on_pending_in_point_set)
        self.video_player.state_changed.connect(self.on_state_changed)
        self.video_player.position_changed.connect(self.on_position_changed)

    def select_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select VR Video File",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)",
        )

        if file_path:
            self.file_label.setText(f"Selected: {file_path}")
            self.current_video = file_path

            # Load video into player
            if self.video_player.load_video(file_path):
                print(f"Video loaded successfully: {file_path}")
                self.process_button.setEnabled(True)

                # Set timeline duration
                duration = self.video_player.vlc.get_duration()
                self.timeline_panel.set_duration(duration)

                # Clear previous timeline data
                self.timeline_panel.clear_all()

                # Clear timestamps
                self.video_player.clear_timestamps()

                # Clear pending markers
                self.timeline_panel.clear_pending_marker()

                # Reset status label
                self.timeline_panel.point_status_label.setText("Ready")
            else:
                print(f"Failed to load video: {file_path}")

    def on_in_point_set(self, timestamp):
        """Handle in point set by video player (when segment is completed)"""
        print(f"In point recorded: {timestamp}")
        self.timeline_panel.point_status_label.setText(f"In point: {timestamp}")

    def on_out_point_set(self, timestamp):
        """Handle out point set by video player (when segment is completed)"""
        print(f"Out point recorded: {timestamp}")
        self.timeline_panel.point_status_label.setText(f"Out point: {timestamp}")

        # Update segment list and timeline when we have a complete pair
        self.update_segment_list()
        self.sync_timeline_with_current_segments()

        # Ensure video player maintains focus for I/O key events
        self.video_player.grab_focus()

    def on_pending_in_point_set(self, timestamp):
        """Handle pending in point set by video player"""
        print(f"Pending in point set: {timestamp}")
        self.timeline_panel.point_status_label.setText(f"Pending in: {timestamp}")

        # Show pending marker on timeline
        duration = self.video_player.vlc.get_duration()
        if duration > 0:
            in_time = self.parse_timestamp_to_seconds(timestamp)
            in_position = in_time / duration
            self.timeline_panel.set_pending_marker(in_position)

    def on_state_changed(self, state):
        """Handle state change from timestamp manager"""
        if state == "waiting_for_in":
            self.timeline_panel.point_status_label.setText("Waiting for in point")
        elif state == "waiting_for_out":
            self.timeline_panel.point_status_label.setText("Waiting for out point")

    def on_position_changed(self, position):
        """Handle position change from video player"""
        duration = self.video_player.vlc.get_duration()
        if duration > 0:
            relative_position = position / duration
            self.timeline_panel.update_current_position(relative_position)

    def on_segment_selected(self, index):
        """Handle segment selection from timeline"""
        print(f"Segment {index} selected")
        self.video_player.grab_focus()

    def on_segment_deleted(self, index):
        """Handle segment deletion from timeline"""
        print(f"Segment {index} deleted")
        self.video_player.timestamp_manager.delete_segment(index)
        self.video_player.reset_active_pair()
        self.sync_timeline_with_current_segments()
        self.timeline_panel.clear_pending_marker()
        self.timeline_panel.point_status_label.setText("Ready")
        self.video_player.grab_focus()

    def on_all_segments_cleared(self):
        """Handle when all segments are cleared"""
        print("All segments cleared")
        self.video_player.clear_timestamps()
        self.timeline_panel.clear_pending_marker()
        self.timeline_panel.point_status_label.setText("Ready")
        self.video_player.grab_focus()

    def sync_timeline_with_current_segments(self):
        """Sync timeline markers with current segments in timestamp manager"""
        timestamps = self.video_player.get_timestamps()
        in_points = timestamps["in_points"]
        out_points = timestamps["out_points"]

        segment_positions = []
        duration = self.video_player.vlc.get_duration()

        if duration > 0:
            for i in range(min(len(in_points), len(out_points))):
                in_time = self.parse_timestamp_to_seconds(in_points[i])
                out_time = self.parse_timestamp_to_seconds(out_points[i])
                in_position = in_time / duration
                out_position = out_time / duration
                segment_positions.append((in_position, out_position))

        self.timeline_panel.sync_timeline_with_segments(segment_positions)
        self.update_segment_list()

    def parse_timestamp_to_seconds(self, timestamp):
        """Parse HH:MM:SS timestamp to seconds"""
        try:
            parts = timestamp.split(":")
            if len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
            return 0
        except (AttributeError, ValueError):
            return 0

    def on_timeline_seek(self, position):
        """Handle seek from timeline"""
        if self.current_video:
            duration = self.video_player.vlc.get_duration()
            if duration > 0:
                seek_time = position * duration
                self.video_player.seek_to_time(seek_time)

                # Pause during drag to prevent VLC from resuming playback when mouse stops
                if self.is_dragging:
                    self.video_player.pause_playback()

    def on_drag_started(self):
        """Handle timeline drag start - store playback state"""
        self.was_playing_before_drag = self.video_player.vlc.is_playing
        self.is_dragging = True

    def on_drag_ended(self):
        """Handle timeline drag end - restore playback state"""
        self.is_dragging = False
        # Remember the previous playback state.
        was_playing_before_drag = self.was_playing_before_drag
        # Clear the saved state so it cannot affect a later drag.
        self.was_playing_before_drag = False
        # Resume playback only if it was playing before the drag.
        if was_playing_before_drag:
            self.video_player.start_playback()

    def update_segment_list(self):
        """Update the segment list with current in/out points"""
        timestamps = self.video_player.get_timestamps()
        in_points = timestamps["in_points"]
        out_points = timestamps["out_points"]

        segments = []
        for i in range(min(len(in_points), len(out_points))):
            segments.append((in_points[i], out_points[i]))

        self.timeline_panel.update_segment_list(segments)

    def on_progress_updated(self, message):
        """Handle FFmpeg progress updates"""
        print(f"Progress: {message}")
        self.progress_label.setText(message)
        self.timeline_panel.point_status_label.setText(message)

    def on_operation_complete(self, success, message):
        """Handle FFmpeg operation completion"""
        if self.close_requested:
            return

        if success:
            QMessageBox.information(self, "Success", message)
            self.progress_label.setText("Processing complete")
            self.timeline_panel.point_status_label.setText("Processing complete")
        else:
            QMessageBox.critical(self, "Error", message)
            self.progress_label.setText(f"Error: {message}")
            self.timeline_panel.point_status_label.setText(f"Error: {message}")

        self.process_button.setEnabled(True)

    def process_video(self):
        """Process video with recorded segments in a background thread."""
        if not self.current_video:
            QMessageBox.warning(self, "No Video", "Please select a video file first")
            return

        timestamps = self.video_player.get_timestamps()
        in_points = timestamps["in_points"]
        out_points = timestamps["out_points"]

        if not in_points or not out_points:
            QMessageBox.warning(
                self,
                "No Segments",
                "Please set at least one in and out point using I and O keys",
            )
            return

        if len(in_points) != len(out_points):
            QMessageBox.warning(
                self,
                "Incomplete Segments",
                f"Number of in points ({len(in_points)}) doesn't match out points ({len(out_points)})",
            )
            return

        segments = list(zip(in_points, out_points))

        # Stop video playback first (same as clicking stop button)
        self.video_player.stop_playback()
        
        reply = QMessageBox.question(
            self,
            "Confirm Processing",
            f"Process {len(segments)} segments from this video?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        self.process_button.setEnabled(False)
        self.progress_label.setText("Starting processing...")

        self.ffmpeg_thread = QThread()
        self.ffmpeg_worker = FFmpegWorker(self.current_video, segments)
        self.ffmpeg_worker.moveToThread(self.ffmpeg_thread)

        self.ffmpeg_thread.started.connect(self.ffmpeg_worker.run)
        self.ffmpeg_worker.progress_updated.connect(self.on_progress_updated)
        self.ffmpeg_worker.operation_complete.connect(self.on_operation_complete)
        self.ffmpeg_worker.finished.connect(self.ffmpeg_thread.quit)
        self.ffmpeg_worker.finished.connect(self.ffmpeg_worker.deleteLater)

        # Ensure we clear Python references when the thread actually finishes to avoid
        # accessing a deleted C++ QThread wrapper later (which caused the reported error).
        self.ffmpeg_thread.finished.connect(self.on_ffmpeg_thread_finished)

        # Keep deleteLater so the QThread/C++ object is cleaned up by Qt's event loop.
        self.ffmpeg_thread.finished.connect(self.ffmpeg_worker.deleteLater)
        self.ffmpeg_thread.finished.connect(self.ffmpeg_thread.deleteLater)
        self.ffmpeg_thread.finished.connect(self.finalize_close)

        self.ffmpeg_thread.start()

    def closeEvent(self, event):
        """Wait for active FFmpeg processing before allowing the app to close."""
        # Guard calls to the underlying C++ object — isRunning() can raise
        # if the C++ QThread has already been deleted; treat that as not running.
        try:
            running = self.ffmpeg_thread is not None and self.ffmpeg_thread.isRunning()
        except RuntimeError:
            running = False

        if running:
            if not self.close_requested:
                reply = QMessageBox.question(
                    self,
                    "Processing in Progress",
                    "FFmpeg is still processing. Close the application after processing finishes?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    event.ignore()
                    return

                self.close_requested = True
                self.process_button.setEnabled(False)
                self.progress_label.setText("Finishing processing before closing...")
                event.ignore()
                return

            event.ignore()
            return

        # Stop video playback before cleanup
        self.video_player.stop_playback()
        
        self.ffmpeg_handler.cleanup()
        self.video_player.cleanup()
        event.accept()

    def on_ffmpeg_thread_finished(self):
        """Clear Python references to the QThread and worker after the thread finishes.

        This avoids later attempts to call methods on a wrapped C++ object that has
        already been deleted by Qt (which raises RuntimeError: wrapped C/C++ object ...).
        """
        self.ffmpeg_thread = None
        self.ffmpeg_worker = None

    def finalize_close(self):
        """Close the window once the FFmpeg worker thread has stopped."""
        if self.close_requested and (
            self.ffmpeg_thread is None or not self.ffmpeg_thread.isRunning()
        ):
            self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QMainWindow,
        QMainWindow > QWidget {
            background-color: #304b61;
            color: #eef4f8;
        }

        QLabel {
            color: #eef4f8;
        }
        """
    )

    window = VRSplicerApp()

    if not window.ffmpeg_installation_is_available():
        required_location = "C:\\ffmpeg\\bin\\"
        QMessageBox.critical(
            window,
            "FFmpeg Required",
            "FFmpeg is not installed in the required location.\n\n"
            f"Please install FFmpeg so both ffmpeg.exe and ffprobe.exe are located in:\n"
            f"{required_location}\n\n"
            "The application will now close.",
        )
        window.close()
        app.quit()
        sys.exit(1)

    window.show()
    sys.exit(app.exec_())
