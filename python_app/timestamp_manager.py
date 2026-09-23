from PyQt5.QtCore import QObject, pyqtSignal


class TimestampManager(QObject):
    """Manager for recording and managing edit timestamps"""

    in_point_set = pyqtSignal(str)  # Signal when in point is set
    out_point_set = pyqtSignal(str)  # Signal when out point is set
    pending_in_point_set = pyqtSignal(str)  # Signal when pending in point is set
    state_changed = pyqtSignal(str)  # Signal when state changes

    def __init__(self):
        super().__init__()
        self.in_points = []
        self.out_points = []
        self.state = "waiting_for_in"  # "waiting_for_in" or "waiting_for_out"
        self.pending_in_point = None

    def set_in_point(self, timestamp):
        """Set in point at given timestamp (only accepted when waiting for in)"""
        if self.state != "waiting_for_in":
            print(f"Ignoring in point - current state: {self.state}")
            return None

        self.pending_in_point = timestamp
        self.state = "waiting_for_out"
        self.state_changed.emit(self.state)
        self.pending_in_point_set.emit(timestamp)
        print(f"Pending in point set at: {timestamp}")
        return timestamp

    def set_out_point(self, timestamp):
        """Set out point at given timestamp (only accepted when waiting for out)"""
        if self.state != "waiting_for_out":
            print(f"Ignoring out point - current state: {self.state}")
            return None

        if self.pending_in_point is None:
            print("No pending in point to pair with")
            return None

        # Create complete segment
        self.in_points.append(self.pending_in_point)
        self.out_points.append(timestamp)
        self.in_point_set.emit(self.pending_in_point)
        self.out_point_set.emit(timestamp)

        # Reset for next segment
        self.pending_in_point = None
        self.state = "waiting_for_in"
        self.state_changed.emit(self.state)

        print(f"Segment created: {self.in_points[-1]} -> {timestamp}")
        return timestamp

    def get_timestamps(self):
        """Get all recorded in/out timestamps"""
        return {"in_points": self.in_points, "out_points": self.out_points}

    def clear_timestamps(self):
        """Clear all recorded timestamps and reset state"""
        self.in_points = []
        self.out_points = []
        self.pending_in_point = None
        self.state = "waiting_for_in"
        self.state_changed.emit(self.state)
        print("Timestamps cleared")

    def reset_active_pair(self):
        """Reset the current in-progress pair without clearing completed segments"""
        self.pending_in_point = None
        self.state = "waiting_for_in"
        self.state_changed.emit(self.state)
        print("Active pair reset")

    def get_state(self):
        """Get current state"""
        return self.state

    def get_pending_in_point(self):
        """Get current pending in point"""
        return self.pending_in_point

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
