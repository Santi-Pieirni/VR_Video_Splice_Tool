import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, pyqtSlot
from video_player import VideoPlayer
from ffmpeg_handler import FFmpegHandler
from timeline import TimelinePanel


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
        except Exception as exc:
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

        self.init_ui()

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
        layout.addWidget(self.timeline_panel)

        # FFmpeg controls
        ffmpeg_layout = QVBoxLayout()

        # Process button
        self.process_button = QPushButton("Process Video Segments")
        self.process_button.clicked.connect(self.process_video)
        self.process_button.setEnabled(False)
        ffmpeg_layout.addWidget(self.process_button)

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
        self.video_player.position_changed.connect(self.on_position_changed)

    def select_video_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select VR Video File",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov);;All Files (*)"
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

                # Reset status label
                self.timeline_panel.point_status_label.setText("Ready")
            else:
                print(f"Failed to load video: {file_path}")

    def on_in_point_set(self, timestamp):
        """Handle in point set by video player"""
        print(f"In point recorded: {timestamp}")
        self.timeline_panel.point_status_label.setText(f"In point: {timestamp}")

    def on_out_point_set(self, timestamp):
        """Handle out point set by video player"""
        print(f"Out point recorded: {timestamp}")
        self.timeline_panel.point_status_label.setText(f"Out point: {timestamp}")

        # Update segment list and timeline when we have a complete pair
        self.update_segment_list()
        self.sync_timeline_with_current_segments()

        # Ensure video player maintains focus for I/O key events
        self.video_player.grab_focus()

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
        self.sync_timeline_with_current_segments()
        self.timeline_panel.point_status_label.setText("Ready")
        self.video_player.grab_focus()

    def on_all_segments_cleared(self):
        """Handle when all segments are cleared"""
        print("All segments cleared")
        self.video_player.clear_timestamps()
        self.timeline_panel.point_status_label.setText("Ready")
        self.video_player.grab_focus()

    def sync_timeline_with_current_segments(self):
        """Sync timeline markers with current segments in timestamp manager"""
        timestamps = self.video_player.get_timestamps()
        in_points = timestamps['in_points']
        out_points = timestamps['out_points']

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
            parts = timestamp.split(':')
            if len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
            return 0
        except Exception:
            return 0

    def on_timeline_seek(self, position):
        """Handle seek from timeline"""
        if self.current_video:
            duration = self.video_player.vlc.get_duration()
            if duration > 0:
                seek_time = position * duration
                self.video_player.seek_to_time(seek_time)

    def update_segment_list(self):
        """Update the segment list with current in/out points"""
        timestamps = self.video_player.get_timestamps()
        in_points = timestamps['in_points']
        out_points = timestamps['out_points']

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
        if success:
            QMessageBox.information(self, "Success", message)
            self.progress_label.setText("Processing complete")
            self.timeline_panel.point_status_label.setText("Processing complete")
        else:
            QMessageBox.critical(self, "Error", message)
            self.progress_label.setText(f"Error: {message}")
            self.timeline_panel.point_status_label.setText(f"Error: {message}")

        if self.process_button.isEnabled() is False:
            self.process_button.setEnabled(True)

    def process_video(self):
        """Process video with recorded segments in a background thread."""
        if not self.current_video:
            QMessageBox.warning(self, "No Video", "Please select a video file first")
            return

        timestamps = self.video_player.get_timestamps()
        in_points = timestamps['in_points']
        out_points = timestamps['out_points']

        if not in_points or not out_points:
            QMessageBox.warning(self, "No Segments", "Please set at least one in and out point using I and O keys")
            return

        if len(in_points) != len(out_points):
            QMessageBox.warning(self, "Incomplete Segments", f"Number of in points ({len(in_points)}) doesn't match out points ({len(out_points)})")
            return

        segments = list(zip(in_points, out_points))

        reply = QMessageBox.question(
            self,
            "Confirm Processing",
            f"Process {len(segments)} segments from this video?",
            QMessageBox.Yes | QMessageBox.No
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
        self.ffmpeg_thread.finished.connect(self.ffmpeg_thread.deleteLater)

        self.ffmpeg_thread.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VRSplicerApp()
    window.show()
    sys.exit(app.exec_())
