from PyQt5.QtCore import QObject, pyqtSignal


class TimestampManager(QObject):
    """Manager for recording and managing edit timestamps"""

    in_point_set = pyqtSignal(str)  # Signal when in point is set
    out_point_set = pyqtSignal(str)  # Signal when out point is set

    def __init__(self):
        super().__init__()
        self.in_points = []
        self.out_points = []

    def set_in_point(self, timestamp):
        """Set in point at given timestamp"""
        self.in_points.append(timestamp)
        self.in_point_set.emit(timestamp)
        print(f"In point set at: {timestamp}")
        return timestamp

    def set_out_point(self, timestamp):
        """Set out point at given timestamp"""
        self.out_points.append(timestamp)
        self.out_point_set.emit(timestamp)
        print(f"Out point set at: {timestamp}")
        return timestamp

    def get_timestamps(self):
        """Get all recorded in/out timestamps"""
        return {"in_points": self.in_points, "out_points": self.out_points}

    def clear_timestamps(self):
        """Clear all recorded timestamps"""
        self.in_points = []
        self.out_points = []
        print("Timestamps cleared")

    def get_segment_count(self):
        """Get number of complete segments (pairs of in/out points)"""
        return min(len(self.in_points), len(self.out_points))

    def get_segments(self):
        """Get list of segment tuples (in_point, out_point)"""
        segments = []
        for i in range(min(len(self.in_points), len(self.out_points))):
            segments.append((self.in_points[i], self.out_points[i]))
        return segments

    def delete_segment(self, index):
        """Delete segment at given index (removes both in and out points)"""
        if 0 <= index < len(self.in_points) and 0 <= index < len(self.out_points):
            self.in_points.pop(index)
            self.out_points.pop(index)
            print(f"Segment {index} deleted")
            return True
        return False
