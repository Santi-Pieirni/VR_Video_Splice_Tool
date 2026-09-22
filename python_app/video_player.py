from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QCoreApplication
from vlc_wrapper import VLCWrapper
from timestamp_manager import TimestampManager

class VideoPlayer(QWidget):
    in_point_set = pyqtSignal(str)  # Timestamp string when in point is set
    out_point_set = pyqtSignal(str)  # Timestamp string when out point is set
    position_changed = pyqtSignal(float)  # Current position in seconds
    
    def __init__(self):
        super().__init__()
        
        # Initialize components
        self.vlc = VLCWrapper()
        self.timestamp_manager = TimestampManager()
        
        # State variables
        self.was_playing = False
        
        # Timer for position updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        
        self.init_ui()
        
        # Connect VLC signals
        self.vlc.video_ended.connect(self.reset_player_state)
        
        # Connect timestamp manager signals
        self.timestamp_manager.in_point_set.connect(self.in_point_set)
        self.timestamp_manager.out_point_set.connect(self.out_point_set)
    
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
        
        # Seek slider
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderPressed.connect(self.on_seek_start)
        self.seek_slider.sliderReleased.connect(self.on_seek_end)
        self.seek_slider.valueChanged.connect(self.on_seek)
        layout.addWidget(self.seek_slider)
        
        # Status info
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)
        
        # Keyboard shortcuts info
        shortcuts_label = QLabel("Shortcuts: Space=Play/Pause, I=Set In Point, O=Set Out Point")
        shortcuts_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(shortcuts_label)
        
        # Initialize VLC
        self.vlc.init_vlc(self.video_widget)
    
    def load_video(self, file_path):
        """Load a video file"""
        success = self.vlc.load_video(file_path)
        
        if success:
            self.video_widget.setStyleSheet("background-color: #000; min-height: 400px;")
            self.status_label.setText(f"Duration: {self.vlc.get_duration():.1f}s")
        else:
            self.status_label.setText("Failed to load video")
        
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
        self.seek_slider.setValue(0)
    
    def update_playback_button(self):
        """Update play/pause button text based on state"""
        if self.vlc.is_playing:
            self.play_button.setText("Pause")
        else:
            self.play_button.setText("Play")
    
    def update_position(self):
        """Update position display and slider"""
        try:
            current_time = self.vlc.get_current_time()
            
            # Update time display
            self.update_time_display()
            
            # Update slider
            duration = self.vlc.get_duration()
            if duration > 0:
                position = int((current_time / duration) * 1000)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(position)
                self.seek_slider.blockSignals(False)
            
            # Emit position signal
            self.position_changed.emit(current_time)
            
        except Exception as e:
            print(f"Error updating position: {e}")
    
    def update_time_display(self):
        """Update the time display label"""
        try:
            current_time = self.vlc.get_current_time()
            duration = self.vlc.get_duration()
            
            current_str = self.format_time(current_time)
            total_str = self.format_time(duration)
            self.time_label.setText(f"{current_str} / {total_str}")
        except:
            pass
    
    def format_time(self, seconds):
        """Format time in HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def on_seek_start(self):
        """Called when user starts dragging the slider"""
        self.was_playing = self.vlc.is_playing
        self.pause_playback()
    
    def on_seek_end(self):
        """Called when user releases the slider"""
        self.seek_to_slider()
        if self.was_playing:
            self.start_playback()
    
    def on_seek(self, value):
        """Called when slider value changes"""
        if not self.seek_slider.isSliderDown():
            self.seek_to_slider()
    
    def seek_to_slider(self):
        """Seek to the position indicated by the slider"""
        try:
            position = self.seek_slider.value()
            # Convert slider (0-1000) to VLC position (0.0-1.0)
            vlc_position = position / 1000.0
            
            self.vlc.seek_to_position(vlc_position)
            self.update_time_display()
            
        except Exception as e:
            print(f"Seek error: {e}")
    
    def seek_to_time(self, seconds):
        """Seek to a specific time in seconds"""
        if self.vlc.seek_to_time(seconds):
            self.update_time_display()
            
            # Update slider
            duration = self.vlc.get_duration()
            if duration > 0:
                position = int((seconds / duration) * 1000)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(position)
                self.seek_slider.blockSignals(False)
    
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
        self.was_playing = self.vlc.is_playing
        self.pause_playback()
        
        if self.vlc.jump_by_seconds(-15):
            QCoreApplication.processEvents()
            self.update_time_display()
            
            # Update slider
            current_time = self.vlc.get_current_time()
            duration = self.vlc.get_duration()
            if duration > 0:
                position = int((current_time / duration) * 1000)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(position)
                self.seek_slider.blockSignals(False)
        
        if self.was_playing:
            self.vlc.start_playback()
    
    def jump_forward(self):
        """Jump forward 15 seconds"""
        self.was_playing = self.vlc.is_playing
        self.pause_playback()
        
        if self.vlc.jump_by_seconds(15):
            QCoreApplication.processEvents()
            self.update_time_display()
            
            # Update slider
            current_time = self.vlc.get_current_time()
            duration = self.vlc.get_duration()
            if duration > 0:
                position = int((current_time / duration) * 1000)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(position)
                self.seek_slider.blockSignals(False)
        
        if self.was_playing:
            self.vlc.start_playback()
    
    def set_in_point(self):
        """Set in point at current position"""
        current_time = self.vlc.get_current_time()
        timestamp = self.format_time(current_time)
        
        self.timestamp_manager.set_in_point(timestamp)
        self.status_label.setText(f"In point: {timestamp}")
    
    def set_out_point(self):
        """Set out point at current position"""
        current_time = self.vlc.get_current_time()
        timestamp = self.format_time(current_time)
        
        self.timestamp_manager.set_out_point(timestamp)
        self.status_label.setText(f"Out point: {timestamp}")
    
    def reset_player_state(self):
        """Reset player state after end"""
        print("Resetting player state")
        self.pause_playback()
        self.vlc.reset_player_state()
        self.update_time_display()
        self.seek_slider.setValue(0)
    
    def get_timestamps(self):
        """Get all recorded in/out timestamps"""
        return self.timestamp_manager.get_timestamps()
    
    def clear_timestamps(self):
        """Clear all recorded timestamps"""
        self.timestamp_manager.clear_timestamps()
    
    def cleanup(self):
        """Clean up resources"""
        self.vlc.cleanup()
        self.position_timer.stop()
    
    def grab_focus(self):
        """Grab keyboard focus for I/O key events"""
        self.setFocus()
