import vlc
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QCoreApplication, QMetaObject

class VideoPlayer(QWidget):
    in_point_set = pyqtSignal(str)  # Timestamp string when in point is set
    out_point_set = pyqtSignal(str)  # Timestamp string when out point is set
    position_changed = pyqtSignal(float)  # Current position in seconds
    video_ended = pyqtSignal()  # Signal when video ends
    
    def __init__(self):
        super().__init__()
        self.instance = None
        self.player = None
        self.media = None
        self.current_file = None
        self.is_playing = False
        self.duration = 0
        
        # Timestamps for editing
        self.in_points = []
        self.out_points = []
        
        # Timer for position updates
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
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
        
        # Initialize VLC instance
        self.init_vlc()
        
        # Connect signals
        self.video_ended.connect(self.reset_player_state)
    
    def init_vlc(self):
        """Initialize VLC instance"""
        try:
            # Create VLC instance
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            
            # Set the video widget to render to
            # This works on Windows with VLC's Qt support
            self.player.set_hwnd(self.video_widget.winId())
            
            # Connect event callbacks (use thread-safe approach)
            events = self.player.event_manager()
            events.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_end_reached)
            # Don't attach time changed event - it causes threading issues
            # We use our own timer for position updates instead
            
            print("VLC initialized successfully")
            
        except Exception as e:
            print(f"Error initializing VLC: {e}")
            self.status_label.setText(f"VLC Error: {str(e)}")
    
    def load_video(self, file_path):
        """Load a video file using VLC"""
        self.current_file = file_path
        
        try:
            # Create media from file
            self.media = self.instance.media_new(file_path)
            self.player.set_media(self.media)
            
            # Parse the media to get duration
            self.media.parse()
            self.duration = self.player.get_length()
            
            # Handle VLC error case (-1 means unknown duration)
            if self.duration <= 0:
                print(f"Player returned invalid duration: {self.duration}s")
                # Try getting duration from media object (returns milliseconds)
                media_duration = self.media.get_duration()
                print(f"Media duration: {media_duration}ms")
                
                if media_duration > 0:
                    self.duration = media_duration / 1000  # Convert to seconds
                else:
                    print("Could not determine duration, using fallback")
                    self.duration = 3600  # 1 hour fallback
            
            # Update UI
            self.video_widget.setStyleSheet("background-color: #000; min-height: 400px;")  # Clear any text
            self.status_label.setText(f"Duration: {self.duration:.1f}s")
            
            print(f"Video loaded: {file_path}")
            print(f"Duration: {self.duration:.2f}s")
            
            return True
            
        except Exception as e:
            print(f"Error loading video: {e}")
            self.status_label.setText(f"Failed to load video: {str(e)}")
            return False
    
    def toggle_playback(self):
        """Toggle between play and pause"""
        if self.player is None:
            return
            
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
    def start_playback(self):
        """Start video playback"""
        if self.player is None:
            return
            
        self.player.play()
        self.is_playing = True
        self.play_button.setText("Pause")
        
        # Start position update timer
        self.position_timer.start(100)  # Update every 100ms
    
    def pause_playback(self):
        """Pause video playback"""
        if self.player is None:
            return
            
        self.player.pause()
        self.is_playing = False
        self.play_button.setText("Play")
        self.position_timer.stop()
    
    def stop_playback(self):
        """Stop video playback and reset to beginning"""
        self.pause_playback()
        if self.player is not None:
            self.player.stop()
            self.update_time_display()
            self.seek_slider.setValue(0)
    
    def update_position(self):
        """Update position display and slider"""
        if self.player is None:
            return
            
        try:
            # Get current position in milliseconds
            current_time = self.player.get_time() / 1000  # Convert to seconds
            
            # Update time display
            self.update_time_display()
            
            # Update slider
            if self.duration > 0:
                position = int((current_time / self.duration) * 1000)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(position)
                self.seek_slider.blockSignals(False)
            
            # Emit position signal
            self.position_changed.emit(current_time)
            
        except Exception as e:
            print(f"Error updating position: {e}")
    
    def update_time_display(self):
        """Update the time display label"""
        if self.player is None:
            return
            
        try:
            current_time = self.player.get_time() / 1000  # Convert to seconds
            
            # Handle VLC returning -1 for current time (error state)
            if current_time < 0:
                current_time = 0
            
            current_str = self.format_time(current_time)
            total_str = self.format_time(self.duration)
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
        self.was_playing = self.is_playing
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
        """Seek to the position indicated by the slider using position (0.0-1.0)"""
        if self.player is None:
            return
            
        try:
            position = self.seek_slider.value()
            # Convert slider (0-1000) to VLC position (0.0-1.0)
            vlc_position = position / 1000.0
            
            # Use set_position instead of set_time - often more reliable
            self.player.set_position(vlc_position)
            
            # Small delay to let VLC process the seek
            QCoreApplication.processEvents()
            
            self.update_time_display()
            
        except Exception as e:
            print(f"Seek error: {e}")
            # If seek fails, just update the display without actually seeking
    
    def seek_to_time(self, seconds):
        """Seek to a specific time in seconds"""
        if self.player is None:
            return
            
        try:
            # VLC uses milliseconds
            self.player.set_time(int(seconds * 1000))
            self.update_time_display()
            
            # Update slider
            if self.duration > 0:
                position = int((seconds / self.duration) * 1000)
                self.seek_slider.blockSignals(True)
                self.seek_slider.setValue(position)
                self.seek_slider.blockSignals(False)
                
        except Exception as e:
            print(f"Time seek error: {e}")
    
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
        if self.player is None:
            return
        self.jump_by_seconds(-15)
    
    def jump_forward(self):
        """Jump forward 15 seconds"""
        if self.player is None:
            return
        self.jump_by_seconds(15)
    
    def jump_by_seconds(self, seconds):
        """Jump by a specific number of seconds with pause-first approach"""
        if self.player is None:
            return
            
        try:
            length = self.player.get_length()
            current = self.player.get_time()
            
            print(f"Current={current} Length={length}")
            
            if current < 0 or length <= 0:
                return

            new_time = max(0, min(length, current + seconds * 1000))
            print(f"Seeking to {new_time}")

            self.player.set_time(int(new_time))

            # Update display
            QCoreApplication.processEvents()
            self.update_time_display()
            
            # Update slider (convert milliseconds to 0-1000 range)
            slider_position = int((new_time / length) * 1000) if length > 0 else 0
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(slider_position)
            self.seek_slider.blockSignals(False)
            
            # Resume if it was playing
            if self.was_playing:
                self.player.play()
            
        except Exception as e:
            print(f"Jump error: {e}")
    
    def set_in_point(self):
        """Set in point at current position"""
        if self.player is None:
            return
            
        current_time = self.player.get_time() / 1000  # Convert to seconds
        timestamp = self.format_time(current_time)
        
        self.in_points.append(timestamp)
        self.in_point_set.emit(timestamp)
        
        print(f"In point set at: {timestamp}")
        self.status_label.setText(f"In point: {timestamp}")
    
    def set_out_point(self):
        """Set out point at current position"""
        if self.player is None:
            return
            
        current_time = self.player.get_time() / 1000  # Convert to seconds
        timestamp = self.format_time(current_time)
        
        self.out_points.append(timestamp)
        self.out_point_set.emit(timestamp)
        
        print(f"Out point set at: {timestamp}")
        self.status_label.setText(f"Out point: {timestamp}")
    
    def on_end_reached(self, event):
        """Handle video end reached (thread-safe)"""
        print("Video ended")
        # Emit signal to trigger reset in main thread
        self.video_ended.emit()
    
    def reset_player_state(self):
        """Reset player state after end (call from main thread)"""
        print("Resetting player state")
        self.pause_playback()
        if self.player is not None:
            self.player.stop()
            # Reset to beginning
            self.player.set_time(0)
            self.current_frame = 0
            self.update_time_display()
            self.seek_slider.setValue(0)
    
    def get_timestamps(self):
        """Get all recorded in/out timestamps"""
        return {
            'in_points': self.in_points,
            'out_points': self.out_points
        }
    
    def clear_timestamps(self):
        """Clear all recorded timestamps"""
        self.in_points = []
        self.out_points = []
        print("Timestamps cleared")
    
    def cleanup(self):
        """Clean up VLC resources"""
        if self.player is not None:
            self.player.stop()
        self.position_timer.stop()
