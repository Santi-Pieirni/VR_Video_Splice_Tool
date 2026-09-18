import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QFileDialog
from PyQt5.QtCore import Qt

class VRSplicerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VR Video Splicer")
        self.setGeometry(100, 100, 1200, 800)
        
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
        
        # Placeholder for video player
        self.player_label = QLabel("Video player will be added here")
        self.player_label.setAlignment(Qt.AlignCenter)
        self.player_label.setStyleSheet("background-color: #333; color: white; padding: 50px;")
        layout.addWidget(self.player_label)
        
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VRSplicerApp()
    window.show()
    sys.exit(app.exec_())
