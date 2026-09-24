from PyQt5.QtCore import QCoreApplication, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ResizeHandle(QFrame):
    """Custom resize handle for vertical resizing"""

    def __init__(self, parent_widget):
        super().__init__()
        self.parent_widget = parent_widget
        self.setFrameShape(QFrame.HLine)
        self.setStyleSheet("background-color: #555; min-height: 8px; max-height: 8px;")
        self.setCursor(Qt.SizeVerCursor)  # Set the resize cursor properly
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.resizing = False
        self.resize_start_y = 0
        self.resize_start_height = 0

    def mousePressEvent(self, event):
        """Handle mouse press on resize handle"""
        if event.button() == Qt.LeftButton:
            self.resizing = True
            self.resize_start_y = event.globalY()
            self.resize_start_height = self.parent_widget.height()
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        """Handle mouse move during resizing"""
        if self.resizing:
            delta = event.globalY() - self.resize_start_y
            new_height = self.resize_start_height + delta
            # Set minimum height to 200px
            new_height = max(200, new_height)
            self.parent_widget.setFixedHeight(new_height)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop resizing"""
        if event.button() == Qt.LeftButton:
            self.resizing = False
            event.accept()
        else:
            event.ignore()


from timestamp_manager import TimestampManager
from vlc_wrapper import VLCWrapper


class VideoPlayer(QWidget):
    in_point_set = pyqtSignal(str)  # Timestamp string when in point is set
    out_point_set = pyqtSignal(str)  # Timestamp string when out point is set
    pending_in_point_set = pyqtSignal(
        str
    )  # Timestamp string when pending in point is set
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
        layout.setContentsMargins(11, 11, 11, 0)
        self.setLayout(layout)

        # Make this widget focusable to receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)

        # Video widget container (holds video + resize handle)
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: #000; min-height: 600px;")
        self.video_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        video_container_layout = QVBoxLayout()
        video_container_layout.setContentsMargins(0, 0, 0, 0)
        video_container_layout.setSpacing(0)
        self.video_container.setLayout(video_container_layout)

        # Video widget (VLC will render here)
        self.video_widget = QWidget()
        video_container_layout.addWidget(self.video_widget)

        # Add vertical resize handle on bottom edge
        self.resize_handle = ResizeHandle(self.video_container)
        video_container_layout.addWidget(self.resize_handle)

        layout.addWidget(self.video_container)

        # Controls
        controls_layout = QHBoxLayout()

        # Jump back 15 seconds (left)
        self.jump_back_15_button = QPushButton("-15s")
        self.jump_back_15_button.setObjectName("jumpButton")
        self.jump_back_15_button.setMinimumWidth(55)
        self.jump_back_15_button.clicked.connect(self.jump_back_15)
        controls_layout.addWidget(self.jump_back_15_button)

        # Jump back 5 seconds
        self.jump_back_5_button = QPushButton("-5s")
        self.jump_back_5_button.setObjectName("jumpButton")
        self.jump_back_5_button.setMinimumWidth(55)
        self.jump_back_5_button.clicked.connect(self.jump_back_5)
        controls_layout.addWidget(self.jump_back_5_button)

        # Play/Pause button (center)
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("playButton")
        self.play_button.setToolTip("Play / Pause (Space)")
        self.play_button.setMinimumWidth(70)
        self.play_button.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_button)

        # Stop button (center)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setToolTip("Stop playback")
        self.stop_button.setMinimumWidth(70)
        self.stop_button.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.stop_button)

        # Jump forward 5 seconds
        self.jump_forward_5_button = QPushButton("+5s")
        self.jump_forward_5_button.setObjectName("jumpButton")
        self.jump_forward_5_button.setMinimumWidth(55)
        self.jump_forward_5_button.clicked.connect(self.jump_forward_5)
        controls_layout.addWidget(self.jump_forward_5_button)

        # Jump forward 15 seconds (right)
        self.jump_forward_15_button = QPushButton("+15s")
        self.jump_forward_15_button.setObjectName("jumpButton")
        self.jump_forward_15_button.setMinimumWidth(55)
        self.jump_forward_15_button.clicked.connect(self.jump_forward_15)
        controls_layout.addWidget(self.jump_forward_15_button)

        layout.addLayout(controls_layout)

        # Time label moved below the buttons so it sits above the timeline (left-aligned)
        # Container provides contrast, larger text, padding and left alignment.
        time_container_wrapper = QHBoxLayout()  # Horizontal wrapper

        self.time_container = QWidget()
        self.time_container.setObjectName("timeContainer")
        time_container_layout = QHBoxLayout()
        # Indent so the left edge of the label lines up with the timeline track (timeline has ~10px inset)
        time_container_layout.setContentsMargins(10, 6, 10, 6)
        time_container_layout.setSpacing(0)
        self.time_container.setLayout(time_container_layout)

        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setObjectName("timeLabel")
        time_container_layout.addWidget(self.time_label, alignment=Qt.AlignLeft)

        time_container_wrapper.addWidget(self.time_container)
        time_container_wrapper.addStretch()
        layout.addLayout(time_container_wrapper)

        # Button color theming: green tinted play, red tinted stop, with hover/pressed states
        # Use object names so only these buttons are affected.
        self.setStyleSheet(
            """
            #playButton {
                background-color: #2ecc71;
                color: white;
                border: 1px solid #27ae60;
                border-radius: 4px;
                padding: 6px 10px;
            }
            #playButton:hover {
                background-color: #27ae60;
            }
            #playButton:pressed {
                background-color: #1e8449;
            }

            #stopButton {
                background-color: #e74c3c;
                color: white;
                border: 1px solid #c0392b;
                border-radius: 4px;
                padding: 6px 10px;
            }
            #stopButton:hover {
                background-color: #c0392b;
            }
            #stopButton:pressed {
                background-color: #922b21;
            }

            #jumpButton {
                background-color: #5dade2;
                color: white;
                border: 1px solid #3498db;
                border-radius: 4px;
                padding: 6px 10px;
            }
            #jumpButton:hover {
                background-color: #3498db;
            }
            #jumpButton:pressed {
                background-color: #2874a6;
            }

            #timeContainer {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 6px;
            }
            #timeLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding-left: 6px;
                padding-right: 6px;
            }

            #jumpButton,
            #playButton,
            #stopButton {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            """
        )

        # Initialize VLC (still renders to the inner video_widget)
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

    def jump_back_15(self):
        """Jump back 15 seconds"""
        if self.vlc.jump_by_seconds(-15):
            QCoreApplication.processEvents()
            self.update_time_display()

            # Emit position signal for timeline UI
            current_time = self.vlc.get_current_time()
            self.position_changed.emit(current_time)

    def jump_forward_15(self):
        """Jump forward 15 seconds"""
        if self.vlc.jump_by_seconds(15):
            QCoreApplication.processEvents()
            self.update_time_display()

            # Emit position signal for timeline UI
            current_time = self.vlc.get_current_time()
            self.position_changed.emit(current_time)

    def jump_back_5(self):
        """Jump back 5 seconds"""
        if self.vlc.jump_by_seconds(-5):
            QCoreApplication.processEvents()
            self.update_time_display()

            # Emit position signal for timeline UI
            current_time = self.vlc.get_current_time()
            self.position_changed.emit(current_time)

    def jump_forward_5(self):
        """Jump forward 5 seconds"""
        if self.vlc.jump_by_seconds(5):
            QCoreApplication.processEvents()
            self.update_time_display()

            # Emit position signal for timeline UI
            current_time = self.vlc.get_current_time()
            self.position_changed.emit(current_time)

    def jump_back(self):
        """Jump back 15 seconds (for keyboard shortcut)"""
        self.jump_back_15()

    def jump_forward(self):
        """Jump forward 15 seconds (for keyboard shortcut)"""
        self.jump_forward_15()

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
        try:
            # Stop playback first
            self.stop_playback()
        except (AttributeError, RuntimeError) as e:
            print(f"Error stopping playback during cleanup: {e}")

        try:
            # Then clean up VLC
            self.vlc.cleanup()
        except (AttributeError, RuntimeError) as e:
            print(f"Error during VLC cleanup: {e}")

        # Stop timer
        self.position_timer.stop()

    def grab_focus(self):
        """Grab keyboard focus for I/O key events"""
        self.setFocus()
