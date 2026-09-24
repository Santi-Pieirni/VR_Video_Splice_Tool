import vlc
from PyQt5.QtCore import QCoreApplication, QObject, pyqtSignal


class VLCWrapper(QObject):
    """Wrapper for VLC media player operations"""

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
        self.video_widget = None

    def init_vlc(self, video_widget):
        """Initialize VLC instance with video widget"""
        self.video_widget = video_widget

        try:
            # Create VLC instance
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()

            # Set the video widget to render to
            self.player.set_hwnd(self.video_widget.winId())

            # Connect event callbacks (use thread-safe approach)
            events = self.player.event_manager()
            events.event_attach(
                vlc.EventType.MediaPlayerEndReached, self.on_end_reached
            )

            print("VLC initialized successfully")
            return True

        except (AttributeError, OSError) as e:
            print(f"Error initializing VLC: {e}")
            return False

    def load_video(self, file_path):
        """Load a video file using VLC"""
        self.current_file = file_path

        try:
            # Create media from file
            self.media = self.instance.media_new(file_path)
            self.player.set_media(self.media)

            # Parse the media first to get video info
            self.media.parse()
            self.duration = self.player.get_length() / 1000

            # Apply crop filter for single-eye preview (left half of side-by-side video)
            # Get video dimensions for explicit pixel cropping
            # Format: "WIDTHxHEIGHT+X+Y" 
            video_width, video_height = self.player.video_get_size()
            print(f"Video dimensions: {video_width}x{video_height}")
            
            if video_width > 0 and video_height > 0:
                # Crop to left half: width/2 x full height, starting at 0,0
                crop_width = video_width // 2
                crop_geometry = f"{crop_width}x{video_height}+0+0"
                self.player.video_set_crop_geometry(crop_geometry)
                print(f"Crop geometry set to: {crop_geometry}")
            else:
                print("Could not get video dimensions, skipping crop")

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

            print(f"Video loaded: {file_path}")
            print(f"Duration: {self.duration:.2f}s")

            return True

        except (AttributeError, OSError) as e:
            print(f"Error loading video: {e}")
            return False

    def toggle_playback(self):
        """Toggle between play and pause"""
        if self.player is None:
            return False

        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
            return True
        return False

    def start_playback(self):
        """Start video playback"""
        if self.player is None:
            return False

        self.player.play()
        self.is_playing = True
        return True

    def pause_playback(self):
        """Pause video playback"""
        if self.player is None:
            return False

        self.player.pause()
        self.is_playing = False
        return True

    def stop_playback(self):
        """Stop video playback and reset to beginning"""
        self.pause_playback()
        if self.player is not None:
            try:
                self.player.stop()
                self.player.set_time(0)
            except (AttributeError, RuntimeError) as e:
                print(f"Error stopping playback: {e}")

    def get_current_time(self):
        """Get current playback position in seconds"""
        if self.player is None:
            return 0
        try:
            current_time = self.player.get_time() / 1000  # Convert to seconds
            # Handle VLC returning -1 for current time (error state)
            current_time = max(current_time, 0)
            return current_time
        except (AttributeError, TypeError):
            return 0

    def get_time(self):
        """Get current playback position in milliseconds"""
        if self.player is None:
            return 0
        try:
            return self.player.get_time()
        except (AttributeError, TypeError):
            return 0

    def get_length(self):
        """Get video duration in milliseconds"""
        if self.player is None:
            return 0
        try:
            return self.player.get_length()
        except (AttributeError, TypeError):
            return 0

    def get_duration(self):
        """Get video duration in seconds"""
        return self.duration

    def seek_to_position(self, position):
        """Seek to position (0.0-1.0)"""
        if self.player is None:
            return False

        try:
            self.player.set_position(position)
            QCoreApplication.processEvents()
            return True
        except (AttributeError, OSError) as e:
            print(f"Seek error: {e}")
            return False

    def seek_to_time(self, seconds):
        """Seek to a specific time in seconds"""
        if self.player is None:
            return False

        try:
            # VLC uses milliseconds
            self.player.set_time(int(seconds * 1000))
            return True
        except (AttributeError, OSError) as e:
            print(f"Time seek error: {e}")
            return False

    def jump_by_seconds(self, seconds):
        """Jump by a specific number of seconds"""
        if self.player is None:
            return False

        try:
            length = self.player.get_length()
            current = self.player.get_time()

            if current < 0 or length <= 0:
                return False

            new_time = max(0, min(length, current + seconds * 1000))
            self.player.set_time(int(new_time))
            return True

        except (AttributeError, OSError) as e:
            print(f"Jump error: {e}")
            return False

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
            self.player.set_time(0)

    def cleanup(self):
        """Clean up VLC resources"""
        if self.player is not None:
            try:
                # Stop playback if playing
                if self.is_playing:
                    self.player.stop()
                # Release the media
                if self.media is not None:
                    self.media.release()
                # Release the player
                self.player.release()
                # Release the instance
                if self.instance is not None:
                    self.instance.release()
            except (AttributeError, RuntimeError) as e:
                print(f"Error during VLC cleanup: {e}")
