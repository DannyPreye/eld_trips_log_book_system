"""
Grid Index Mapper.
Converts timestamps to 0-95 grid indices for ELD logbook visualization.
"""
from datetime import datetime, time
from typing import List, Dict


class GridMapper:
    """
    Maps timeline events to grid indices for frontend rendering.
    Each day has 96 grid cells (24 hours × 4 increments per hour).
    Each increment represents 15 minutes.
    """

    GRID_CELLS_PER_DAY = 96  # 24 hours × 4 increments
    MINUTES_PER_INCREMENT = 15

    # Duty status to row index mapping
    STATUS_TO_ROW = {
        "OFF_DUTY": 0,
        "SLEEPER": 1,
        "DRIVING": 2,
        "ON_DUTY": 3,
    }

    @classmethod
    def time_to_index(cls, dt: datetime) -> int:
        """
        Convert a datetime to a grid index (0-95).

        Args:
            dt: Datetime object

        Returns:
            Grid index (0-95)
        """
        hour = dt.hour
        minute = dt.minute

        # Calculate index: hour * 4 + (minutes / 15)
        index = hour * 4 + (minute // cls.MINUTES_PER_INCREMENT)

        # Clamp to valid range
        return max(0, min(cls.GRID_CELLS_PER_DAY - 1, index))

    @classmethod
    def map_segments_to_grid(cls, daily_log: Dict) -> Dict:
        """
        Add grid indices to segments in a daily log.

        Args:
            daily_log: Daily log dictionary with segments

        Returns:
            Daily log dictionary with segments containing:
                - startIndex: Grid index for start time (0-95)
                - endIndex: Grid index for end time (0-95)
                - rowIndex: Row index for duty status (0-3)
        """
        mapped_segments = []

        for segment in daily_log["segments"]:
            start_time = segment["start_time"]
            end_time = segment["end_time"]
            status = segment["status"]

            start_index = cls.time_to_index(start_time)
            end_index = cls.time_to_index(end_time)
            row_index = cls.STATUS_TO_ROW.get(status, 0)

            mapped_segment = segment.copy()
            mapped_segment["startIndex"] = start_index
            mapped_segment["endIndex"] = end_index
            mapped_segment["rowIndex"] = row_index

            mapped_segments.append(mapped_segment)

        daily_log["segments"] = mapped_segments
        return daily_log

    @classmethod
    def map_all_logs(cls, daily_logs: List[Dict]) -> List[Dict]:
        """
        Map all daily logs to include grid indices.

        Args:
            daily_logs: List of daily log dictionaries

        Returns:
            List of daily logs with grid indices added
        """
        return [cls.map_segments_to_grid(log) for log in daily_logs]


