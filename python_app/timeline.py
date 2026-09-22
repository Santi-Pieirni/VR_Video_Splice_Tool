from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QListWidgetItem, QPushButton, QLabel, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPolygonF

class TimelineWidget(QWidget):
    """Visual timeline widget showing video duration and segment markers"""
    
    marker_clicked = pyqtSignal(int, str)  # marker_index, marker_type (in/out)
    position_clicked = pyqtSignal(float)  # position 0.0-1.0 when timeline is clicked
    
    def __init__(self):
        super().__init__()
        self.duration = 0
        self.markers = []  # List of (position, type) tuples, type is 'in' or 'out'
        self.current_position = 0
        self.setMinimumHeight(80)
        self.setStyleSheet("background-color: #2a2a2a; border: 1px solid #444;")
    
    def set_duration(self, duration):
        """Set total video duration in seconds"""
        self.duration = duration
        self.update()
    
    def add_marker(self, position, marker_type):
        """Add a marker at the given position (0.0-1.0)"""
        self.markers.append((position, marker_type))
        self.update()
    
    def clear_markers(self):
        """Clear all markers"""
        self.markers = []
        self.update()
    
    def rebuild_markers_from_segments(self, segments):
        """Rebuild markers from current segments (syncs timeline with segment state)"""
        self.markers = []
        for in_point, out_point in segments:
            # Convert timestamp strings to positions if possible
            # For now, we'll need to handle this differently
            # This method will be called with actual positions from the main app
            pass
    
    def sync_markers_with_segments(self, segment_positions):
        """Sync markers with segment positions (list of (in_position, out_position) tuples)"""
        self.markers = []
        for in_pos, out_pos in segment_positions:
            self.markers.append((in_pos, 'in'))
            self.markers.append((out_pos, 'out'))
        self.update()
    
    def set_current_position(self, position):
        """Set current playback position (0.0-1.0)"""
        self.current_position = position
        self.update()
    
    def paintEvent(self, event):
        """Draw the timeline with markers"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.fillRect(self.rect(), QColor(42, 42, 42))
        
        # Draw timeline track
        track_height = 30
        track_y = (self.height() - track_height) // 2
        track_rect = QRectF(10, track_y, self.width() - 20, track_height)
        
        # Track background
        painter.setBrush(QBrush(QColor(60, 60, 60)))
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRoundedRect(track_rect, 5, 5)
        
        # Draw time markers (every 10%)
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        for i in range(0, 11):
            x = 10 + (self.width() - 20) * (i / 10)
            painter.drawLine(int(x), int(track_y), int(x), int(track_y + track_height))
            
            # Draw time labels
            if self.duration > 0:
                time_label = f"{int(self.duration * i / 10)}s"
                painter.setFont(QFont("Arial", 8))
                painter.drawText(int(x) - 10, int(track_y - 5), time_label)
        
        # Draw segment markers
        for i, (position, marker_type) in enumerate(self.markers):
            x = 10 + (self.width() - 20) * position
            
            if marker_type == 'in':
                # In point marker (green triangle pointing up)
                color = QColor(0, 200, 100)
                points = [
                    (x, track_y - 10),
                    (x - 8, track_y - 20),
                    (x + 8, track_y - 20)
                ]
            else:
                # Out point marker (red triangle pointing down)
                color = QColor(200, 50, 50)
                points = [
                    (x, track_y + track_height + 10),
                    (x - 8, track_y + track_height + 20),
                    (x + 8, track_y + track_height + 20)
                ]
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            polygon = QPolygonF([QPointF(px, py) for px, py in points])
            painter.drawPolygon(polygon)
        
        # Draw current position indicator
        if self.current_position > 0:
            x = 10 + (self.width() - 20) * self.current_position
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawLine(int(x), int(track_y - 5), int(x), int(track_y + track_height + 5))
    
    def mousePressEvent(self, event):
        """Handle mouse clicks on timeline"""
        x = event.x()
        track_width = self.width() - 20
        position = (x - 10) / track_width
        
        # Check if clicked on a marker
        for i, (marker_pos, marker_type) in enumerate(self.markers):
            marker_x = 10 + track_width * marker_pos
            if abs(x - marker_x) < 10:
                self.marker_clicked.emit(i, marker_type)
                return
        
        # If no marker clicked, emit position for seeking
        position = max(0, min(1, position))
        self.position_clicked.emit(position)


class SegmentListWidget(QWidget):
    """Widget to display and manage video segments"""
    
    segment_selected = pyqtSignal(int)  # Segment index
    segment_deleted = pyqtSignal(int)  # Segment index
    segment_moved = pyqtSignal(int, int)  # from_index, to_index
    all_segments_cleared = pyqtSignal()  # All segments cleared
    
    def __init__(self):
        super().__init__()
        self.segments = []  # List of (in_point, out_point) tuples
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header
        header = QLabel("Segments")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)
        
        # Segment list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2a2a2a;
                border: 1px solid #444;
                color: white;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #3a3a3a;
            }
        """)
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        layout.addWidget(self.list_widget)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_segment)
        controls_layout.addWidget(self.delete_button)
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_all_segments)
        controls_layout.addWidget(self.clear_button)
        
        layout.addLayout(controls_layout)
    
    def add_segment(self, in_point, out_point):
        """Add a segment to the list"""
        self.segments.append((in_point, out_point))
        self.update_list()
    
    def remove_segment(self, index):
        """Remove segment at index"""
        if 0 <= index < len(self.segments):
            self.segments.pop(index)
            self.update_list()
    
    def _clear_segments_internal(self):
        """Internal clear without emitting signal (for programmatic updates)"""
        self.segments = []
        self.update_list()
    
    def clear_all_segments(self):
        """Clear all segments (user-initiated, emits signal)"""
        self._clear_segments_internal()
        self.all_segments_cleared.emit()
    
    def update_list(self):
        """Update the list widget with current segments"""
        self.list_widget.clear()
        
        for i, (in_point, out_point) in enumerate(self.segments):
            item_text = f"Segment {i + 1}: {in_point} → {out_point}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)
            self.list_widget.addItem(item)
        
        self.delete_button.setEnabled(len(self.segments) > 0)
    
    def on_item_clicked(self, item):
        """Handle segment selection"""
        index = item.data(Qt.UserRole)
        self.segment_selected.emit(index)
        self.delete_button.setEnabled(True)
    
    def delete_selected_segment(self):
        """Delete the currently selected segment"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.remove_segment(current_row)
            self.segment_deleted.emit(current_row)
            self.delete_button.setEnabled(self.list_widget.count() > 0)
    
    def get_segments(self):
        """Get all segments"""
        return self.segments


class TimelinePanel(QWidget):
    """Combined timeline and segment list panel"""
    
    segment_deleted = pyqtSignal(int)  # Segment index
    segment_selected = pyqtSignal(int)  # Segment index
    seek_to_position = pyqtSignal(float)  # Position 0.0-1.0
    all_segments_cleared = pyqtSignal()  # All segments cleared
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Timeline
        self.timeline = TimelineWidget()
        self.timeline.marker_clicked.connect(self.on_marker_clicked)
        self.timeline.position_clicked.connect(self.on_position_clicked)
        layout.addWidget(self.timeline)
        
        # Point status display
        self.point_status_label = QLabel("Ready")
        self.point_status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.point_status_label)
        
        # Keyboard shortcuts info
        shortcuts_label = QLabel("Shortcuts: Space=Play/Pause, I=Set In Point, O=Set Out Point")
        shortcuts_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(shortcuts_label)
        
        # Segment list
        self.segment_list = SegmentListWidget()
        self.segment_list.segment_selected.connect(self.segment_selected)
        self.segment_list.segment_deleted.connect(self.segment_deleted)
        self.segment_list.all_segments_cleared.connect(self.on_all_segments_cleared)
        layout.addWidget(self.segment_list)
    
    def set_duration(self, duration):
        """Set video duration"""
        self.timeline.set_duration(duration)
    
    def add_segment_marker(self, in_position, out_position):
        """Add in/out markers to timeline"""
        self.timeline.add_marker(in_position, 'in')
        self.timeline.add_marker(out_position, 'out')
    
    def update_segment_list(self, segments):
        """Update segment list with new segments"""
        self.segment_list._clear_segments_internal()
        for in_point, out_point in segments:
            self.segment_list.add_segment(in_point, out_point)
    
    def clear_all(self):
        """Clear timeline markers and segment list"""
        self.timeline.clear_markers()
        self.segment_list._clear_segments_internal()
        self.point_status_label.setText("Ready")
    
    def update_current_position(self, position):
        """Update current position indicator on timeline"""
        self.timeline.set_current_position(position)
    
    def on_marker_clicked(self, marker_index, marker_type):
        """Handle marker click - could be used to jump to that position"""
        # Future enhancement: seek to marker position
        pass
    
    def on_position_clicked(self, position):
        """Handle position click on timeline"""
        self.seek_to_position.emit(position)
    
    def on_all_segments_cleared(self):
        """Handle when all segments are cleared"""
        self.timeline.clear_markers()
        self.point_status_label.setText("Ready")
        self.all_segments_cleared.emit()
    
    def get_segments(self):
        """Get all segments from segment list"""
        return self.segment_list.get_segments()
    
    def sync_timeline_with_segments(self, segment_positions):
        """Sync timeline markers with current segment positions"""
        self.timeline.sync_markers_with_segments(segment_positions)
