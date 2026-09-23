from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class TimelineWidget(QWidget):
    """Visual timeline widget showing video duration and segment markers"""

    marker_clicked = pyqtSignal(int, str)  # marker_index, marker_type (in/out)
    position_clicked = pyqtSignal(float)  # position 0.0-1.0 when timeline is clicked

    def __init__(self):
        super().__init__()
        self.duration = 0
        self.markers = []  # List of (position, type) tuples, type is 'in' or 'out'
        self.pending_marker = None  # (position, type) for pending marker, type is 'pending_in'
        self.current_position = 0
        self.is_dragging = False
        self.drag_start_position = 0
        self.drag_start_x = 0
        self.setMinimumHeight(80)
        self.setStyleSheet("background-color: #2a2a2a; border: 1px solid #444;")

        # Create drag position label (hidden by default)
        self.drag_label = QLabel(self)
        self.drag_label.setStyleSheet("background-color: #333; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px;")
        self.drag_label.hide()

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
        self.pending_marker = None
        self.update()

    def set_pending_marker(self, position):
        """Set a pending in marker"""
        self.pending_marker = (position, "pending_in")
        self.update()

    def clear_pending_marker(self):
        """Clear pending marker"""
        self.pending_marker = None
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
            self.markers.append((in_pos, "in"))
            self.markers.append((out_pos, "out"))
        self.update()

    def set_current_position(self, position):
        """Set current playback position (0.0-1.0)"""
        self.current_position = position
        self.update()

    def format_time(self, seconds):
        """Format time in HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def get_major_interval(self, duration):
        """Calculate optimal major tick interval based on video duration"""
        if duration < 60:  # < 1 minute
            return 10  # 10 seconds
        elif duration < 300:  # 1-5 minutes
            return 30  # 30 seconds
        elif duration < 900:  # 5-15 minutes
            return 60  # 1 minute
        elif duration < 1800:  # 15-30 minutes
            return 120  # 2 minutes
        elif duration < 3600:  # 30-60 minutes
            return 300  # 5 minutes
        else:  # > 1 hour
            return 600  # 10 minutes

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

        # Draw time markers with major/minor ticks
        if self.duration > 0:
            major_interval = self.get_major_interval(self.duration)
            minor_interval = major_interval / 5  # 5 minor ticks between major ticks

            # Draw minor ticks
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            current_time = 0
            while current_time <= self.duration:
                x = 10 + (self.width() - 20) * (current_time / self.duration)
                painter.drawLine(
                    int(x), int(track_y + 10), int(x), int(track_y + track_height - 10)
                )
                current_time += minor_interval

            # Draw major ticks with labels
            painter.setPen(QPen(QColor(150, 150, 150), 1))
            current_time = 0
            while current_time <= self.duration:
                x = 10 + (self.width() - 20) * (current_time / self.duration)
                painter.drawLine(
                    int(x), int(track_y), int(x), int(track_y + track_height)
                )

                # Draw time label
                time_label = self.format_time(current_time)
                painter.setFont(QFont("Arial", 8))
                painter.drawText(int(x) - 10, int(track_y - 5), time_label)

                current_time += major_interval

        # Draw segment markers
        for i, (position, marker_type) in enumerate(self.markers):
            x = 10 + (self.width() - 20) * position

            if marker_type == "in":
                # In point marker (green triangle pointing up)
                color = QColor(0, 200, 100)
                points = [
                    (x, track_y - 10),
                    (x - 8, track_y - 20),
                    (x + 8, track_y - 20),
                ]
            else:
                # Out point marker (red triangle pointing down)
                color = QColor(200, 50, 50)
                points = [
                    (x, track_y + track_height + 10),
                    (x - 8, track_y + track_height + 20),
                    (x + 8, track_y + track_height + 20),
                ]

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            polygon = QPolygonF([QPointF(px, py) for px, py in points])
            painter.drawPolygon(polygon)

        # Draw pending marker (if any)
        if self.pending_marker:
            position, marker_type = self.pending_marker
            x = 10 + (self.width() - 20) * position

            if marker_type == "pending_in":
                # Pending in point marker (yellow triangle pointing up, outlined)
                color = QColor(255, 200, 0)
                points = [
                    (x, track_y - 10),
                    (x - 8, track_y - 20),
                    (x + 8, track_y - 20),
                ]

                painter.setBrush(QBrush(QColor(255, 200, 0, 100)))  # Semi-transparent
                painter.setPen(QPen(color, 2))  # Thicker outline
                polygon = QPolygonF([QPointF(px, py) for px, py in points])
                painter.drawPolygon(polygon)

        # Draw current position indicator
        if self.current_position > 0:
            x = 10 + (self.width() - 20) * self.current_position
            painter.setPen(QPen(QColor(255, 255, 0), 2))
            painter.drawLine(
                int(x), int(track_y - 5), int(x), int(track_y + track_height + 5)
            )

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

        # Check if clicked on pending marker
        if self.pending_marker:
            pending_pos, pending_type = self.pending_marker
            pending_x = 10 + track_width * pending_pos
            if abs(x - pending_x) < 10:
                self.marker_clicked.emit(-1, pending_type)  # -1 indicates pending marker

        # Start dragging
        self.is_dragging = True
        self.drag_start_position = position
        self.drag_start_x = x

        # Always emit position for seeking
        position = max(0, min(1, position))
        self.position_clicked.emit(position)

        # Show drag label with current time
        if self.duration > 0:
            current_time = position * self.duration
            time_str = self.format_time(current_time)
            self.drag_label.setText(time_str)
            self.drag_label.adjustSize()
            # Position label above the timeline track
            track_height = 30
            track_y = (self.height() - track_height) // 2
            label_x = x - self.drag_label.width() // 2
            label_y = track_y - 25
            self.drag_label.move(label_x, label_y)
            self.drag_label.show()

    def mouseMoveEvent(self, event):
        """Handle mouse dragging on timeline"""
        if self.is_dragging:
            x = event.x()
            track_width = self.width() - 20

            # Calculate the delta from the start position
            delta_x = x - self.drag_start_x
            delta_position = delta_x / track_width

            new_position = self.drag_start_position + delta_position

            # Clamp to valid range
            new_position = max(0, min(1, new_position))

            # Emit position for seeking
            self.position_clicked.emit(new_position)

            # Update drag label position and text
            if self.duration > 0:
                current_time = new_position * self.duration
                time_str = self.format_time(current_time)
                self.drag_label.setText(time_str)
                self.drag_label.adjustSize()
                # Position label above the timeline track
                track_height = 30
                track_y = (self.height() - track_height) // 2
                label_x = x - self.drag_label.width() // 2
                label_y = track_y - 25
                self.drag_label.move(label_x, label_y)

    def mouseReleaseEvent(self, event):
        """Handle mouse release on timeline"""
        self.is_dragging = False
        self.drag_label.hide()


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
        shortcuts_label = QLabel(
            "Shortcuts: Space=Play/Pause, I=Set In Point, O=Set Out Point"
        )
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
        self.timeline.add_marker(in_position, "in")
        self.timeline.add_marker(out_position, "out")

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

    def set_pending_marker(self, position):
        """Set pending marker on timeline"""
        self.timeline.set_pending_marker(position)

    def clear_pending_marker(self):
        """Clear pending marker from timeline"""
        self.timeline.clear_pending_marker()

    def update_current_position(self, position):
        """Update current position indicator on timeline"""
        self.timeline.set_current_position(position)

    def on_marker_clicked(self, marker_index, marker_type):
        """Handle marker click - could be used to jump to that position"""
        # Future enhancement: seek to marker position

    def on_position_clicked(self, position):
        """Handle position click on timeline"""
        self.seek_to_position.emit(position)

    def on_all_segments_cleared(self):
        """Handle when all segments are cleared"""
        self.timeline.clear_markers()
        self.timeline.clear_pending_marker()
        self.point_status_label.setText("Ready")
        self.all_segments_cleared.emit()

    def get_segments(self):
        """Get all segments from segment list"""
        return self.segment_list.get_segments()

    def sync_timeline_with_segments(self, segment_positions):
        """Sync timeline markers with current segment positions"""
        self.timeline.sync_markers_with_segments(segment_positions)
        self.timeline.clear_pending_marker()  # Clear pending marker when segment is completed
