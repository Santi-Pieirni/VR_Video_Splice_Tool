from PyQt5.QtCore import QCoreApplication, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from timestamp_manager import TimestampManager
from vlc_wrapper import VLCWrapper


class VideoPlayer(QWidget):
    in_point_set = pyqtSignal(str)  # Timestamp string when in point is set
    out_point_set = pyqtSignal(str)  # Timestamp string when out point is set
    pending_in_point_set = pyqtSignal(str)  # Timestamp string when pending in point is set
    state_changed = pyqtSignal(str)  # State change from timestamp manager
    position_changed = pyqtSignal(float)  # Current position in seconds

    def __init__(self):
        super().__init__()

        # Initialize components
        self.vlc = VLCWrapper()
        self.timestamp_manager = TimestampManager()

        # Timer for position updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)

        self.init_ui()

        # Connect VLC signals
        self.vlc.video_ended.connect(self.reset_player_state)

        # Connect timestamp manager signals
        self.timestamp_manager.in_point_set.connect(self.in_point_set)
        self.timestamp_manager.out_point_set.connect(self.out_point_set)
        self.timestamp_manager.pending_in_point_set.connect(self.pending_in_point_set)
        self.timestamp_manager.state_changed.connect(self.state_changed)

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Make this widget focusable to receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)

        # Video widget (VLC will render here)
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: #000; min-height: 400px;")
        layout.addWidget(self.video_widget)

        # Controls
        controls_layout = QHBoxLayout()

        # Play/Pause button
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_button)

        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.stop_button)

        # Jump back 15 seconds
        self.jump_back_button = QPushButton("-15s")
        self.jump_back_button.clicked.connect(self.jump_back)
        controls_layout.addWidget(self.jump_back_button)

        # Jump forward 15 seconds
        self.jump_forward_button = QPushButton("+15s")
        self.jump_forward_button.clicked.connect(self.jump_forward)
        controls_layout.addWidget(self.jump_forward_button)

        # Time display
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setMinimumWidth(150)
        controls_layout.addWidget(self.time_label)

        layout.addLayout(controls_layout)

        # Initialize VLC
        self.vlc.init_vlc(self.video_widget)

    def load_video(self, file_path):
        """Load a video file"""
        success = self.vlc.load_video(file_path)

        if success:
            self.video_widget.setStyleSheet(
                "background-color: #000; min-height: 400px;"
            )
        else:
            print("Failed to load video")

        return success

    def toggle_playback(self):
        """Toggle between play and pause"""
        if self.vlc.is_playing:
            self.pause_playback()
        else:
            self.start_playback()

    def start_playback(self):
        """Start video playback"""
        if self.vlc.start_playback():
            self.play_button.setText("Pause")
            self.position_timer.start(100)  # Update every 100ms

    def pause_playback(self):
        """Pause video playback"""
        if self.vlc.pause_playback():
            self.play_button.setText("Play")
            self.position_timer.stop()

    def stop_playback(self):
        """Stop video playback and reset to beginning"""
        self.pause_playback()
        self.vlc.stop_playback()
        self.update_time_display()

    def update_playback_button(self):
        """Update play/pause button text based on state"""
        if self.vlc.is_playing:
            self.play_button.setText("Pause")
        else:
            self.play_button.setText("Play")

    def update_position(self):
        """Update position display"""
        try:
            current_time = self.vlc.get_current_time()

            # Update time display
            self.update_time_display()

            # Emit position signal for timeline UI
            self.position_changed.emit(current_time)

        except (RuntimeError, OSError) as e:
            print(f"Error updating position: {e}")

    def update_time_display(self):
        """Update the time display label"""
        try:
            current_time = self.vlc.get_current_time()
            duration = self.vlc.get_duration()

            current_str = self.format_time(current_time)
            total_str = self.format_time(duration)
            self.time_label.setText(f"{current_str} / {total_str}")
        except (RuntimeError, OSError) as e:
            print(f"Error updating time display: {e}")

    def format_time(self, seconds):
        """Format time in HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def seek_to_time(self, seconds):
        """Seek to a specific time in seconds"""
        if self.vlc.seek_to_time(seconds):
            self.update_time_display()

            # Emit position signal for timeline UI
            self.position_changed.emit(seconds)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Space:
            self.toggle_playback()
        elif event.key() == Qt.Key_I:
            self.set_in_point()
        elif event.key() == Qt.Key_O:
            self.set_out_point()
        elif event.key() == Qt.Key_Left:
            self.jump_back()
        elif event.key() == Qt.Key_Right:
            self.jump_forward()
        else:
            super().keyPressEvent(event)

    def jump_back(self):
        """Jump back 15 seconds"""
        if self.vlc.jump_by_seconds(-15):
            QCoreApplication.processEvents()
            self.update_time_display()

            # Emit position signal for timeline UI
            current_time = self.vlc.get_current_time()
            self.position_changed.emit(current_time)

    def jump_forward(self):
        """Jump forward 15 seconds"""
        if self.vlc.jump_by_seconds(15):
            QCoreApplication.processEvents()
            self.update_time_display()

            # Emit position signal for timeline UI
            current_time = self.vlc.get_current_time()
            self.position_changed.emit(current_time)

    def set_in_point(self):
        """Set in point at current position"""
        current_time = self.vlc.get_current_time()
        timestamp = self.format_time(current_time)

        self.timestamp_manager.set_in_point(timestamp)

    def set_out_point(self):
        """Set out point at current position"""
        current_time = self.vlc.get_current_time()
        timestamp = self.format_time(current_time)

        self.timestamp_manager.set_out_point(timestamp)

    def reset_player_state(self):
        """Reset player state after end"""
        print("Resetting player state")
        self.pause_playback()
        self.vlc.reset_player_state()
        self.update_time_display()

    def get_timestamps(self):
        """Get all recorded in/out timestamps"""
        return self.timestamp_manager.get_timestamps()

    def clear_timestamps(self):
        """Clear all recorded timestamps"""
        self.timestamp_manager.clear_timestamps()

    def get_state(self):
        """Get current timestamp manager state"""
        return self.timestamp_manager.get_state()

    def get_pending_in_point(self):
        """Get current pending in point"""
        return self.timestamp_manager.get_pending_in_point()

    def reset_active_pair(self):
        """Reset the current in-progress pair"""
        self.timestamp_manager.reset_active_pair()

    def cleanup(self):
        """Clean up resources"""
        self.vlc.cleanup()
        self.position_timer.stop()

    def grab_focus(self):
        """Grab keyboard focus for I/O key events"""
        self.setFocus()
