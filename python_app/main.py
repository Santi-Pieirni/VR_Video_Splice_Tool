import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt
from video_player import VideoPlayer
from ffmpeg_handler import FFmpegHandler

class VRSplicerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VR Video Splicer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.current_video = None
        self.ffmpeg_handler = FFmpegHandler()
        
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
        
        # Placeholder for timeline
        self.timeline_label = QLabel("Timeline will be added here")
        self.timeline_label.setAlignment(Qt.AlignCenter)
        self.timeline_label.setStyleSheet("background-color: #444; color: white; padding: 30px;")
        layout.addWidget(self.timeline_label)
        
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
            else:
                print(f"Failed to load video: {file_path}")
    
    def on_in_point_set(self, timestamp):
        """Handle in point set by video player"""
        print(f"In point recorded: {timestamp}")
        self.progress_label.setText(f"In point: {timestamp}")
    
    def on_out_point_set(self, timestamp):
        """Handle out point set by video player"""
        print(f"Out point recorded: {timestamp}")
        self.progress_label.setText(f"Out point: {timestamp}")
    
    def on_progress_updated(self, message):
        """Handle FFmpeg progress updates"""
        print(f"Progress: {message}")
        self.progress_label.setText(message)
    
    def on_operation_complete(self, success, message):
        """Handle FFmpeg operation completion"""
        if success:
            QMessageBox.information(self, "Success", message)
            self.progress_label.setText("Processing complete")
        else:
            QMessageBox.critical(self, "Error", message)
            self.progress_label.setText(f"Error: {message}")
    
    def process_video(self):
        """Process video with recorded segments"""
        if not self.current_video:
            QMessageBox.warning(self, "No Video", "Please select a video file first")
            return
        
        # Get timestamps from video player
        timestamps = self.video_player.get_timestamps()
        in_points = timestamps['in_points']
        out_points = timestamps['out_points']
        
        if not in_points or not out_points:
            QMessageBox.warning(self, "No Segments", "Please set at least one in and out point using I and O keys")
            return
        
        if len(in_points) != len(out_points):
            QMessageBox.warning(self, "Incomplete Segments", f"Number of in points ({len(in_points)}) doesn't match out points ({len(out_points)})")
            return
        
        # Create segment pairs
        segments = list(zip(in_points, out_points))
        
        # Confirm processing
        reply = QMessageBox.question(
            self, 
            "Confirm Processing",
            f"Process {len(segments)} segments from this video?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.process_button.setEnabled(False)
            self.progress_label.setText("Starting processing...")
            
            # Run FFmpeg processing
            success = self.ffmpeg_handler.process_video(
                self.current_video, 
                segments, 
                "output"
            )
            
            self.process_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VRSplicerApp()
    window.show()
    sys.exit(app.exec_())
