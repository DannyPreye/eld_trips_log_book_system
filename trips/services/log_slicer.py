"""
Daily Log Slicer.
Slices timeline events into 24-hour periods (daily log sheets).
"""
from datetime import datetime, timedelta, date
from typing import List, Dict


class DailyLogSlicer:
    """Service for slicing timeline events into daily logs."""

    @classmethod
    def slice_timeline(cls, timeline: List[Dict]) -> List[Dict]:
        """
        Slice timeline events into daily log sheets (24-hour periods).

        Args:
            timeline: List of timeline events with start_time and end_time

        Returns:
            List of daily log dictionaries with:
                - date: Date string (YYYY-MM-DD)
                - segments: List of events occurring in this day
                - driving_hours: Total driving hours for the day
                - on_duty_hours: Total on-duty hours for the day
        """
        if not timeline:
            return []

        daily_logs = {}

        for event in timeline:
            start_time = event["start_time"]
            end_time = event["end_time"]

            # Get all dates this event spans
            current_date = start_time.date()
            end_date = end_time.date()

            while current_date <= end_date:
                date_str = current_date.isoformat()

                if date_str not in daily_logs:
                    daily_logs[date_str] = {
                        "date": date_str,
                        "segments": [],
                        "driving_hours": 0.0,
                        "on_duty_hours": 0.0,
                    }

                # Calculate the portion of this event that falls within this day
                day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=start_time.tzinfo)
                day_end = day_start + timedelta(days=1)

                event_start = max(start_time, day_start)
                event_end = min(end_time, day_end)

                if event_start < event_end:
                    # Create a segment for this portion
                    segment = event.copy()
                    segment["start_time"] = event_start
                    segment["end_time"] = event_end

                    daily_logs[date_str]["segments"].append(segment)

                    # Calculate hours for this segment
                    duration_hours = (event_end - event_start).total_seconds() / 3600

                    if event["status"] == "DRIVING":
                        daily_logs[date_str]["driving_hours"] += duration_hours

                    if event["status"] in ["DRIVING", "ON_DUTY"]:
                        daily_logs[date_str]["on_duty_hours"] += duration_hours

                current_date += timedelta(days=1)

        # Convert to list and sort by date
        result = list(daily_logs.values())
        result.sort(key=lambda x: x["date"])

        return result


