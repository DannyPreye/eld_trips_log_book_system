"""
Hours-of-Service (HOS) Compliance Engine.
Implements US FMCSA rules for property-carrying drivers.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class HOSEngine:
    """
    HOS Compliance Engine implementing FMCSA rules:
    - 11-hour driving limit (max 11 hours before 10-hour break)
    - 14-hour workday rule (max 14 hours on-duty before 10-hour break)
    - 30-minute break requirement (after 8 cumulative driving hours)
    - 70-hour cycle tracking (rolling 8-day window)
    - Fuel stop insertion (every 1,000 miles)
    """

    # HOS Constants
    MAX_DRIVING_HOURS = 11.0  # Maximum driving hours before break
    MAX_ON_DUTY_HOURS = 14.0  # Maximum on-duty hours before break
    REQUIRED_BREAK_HOURS = 10.0  # Required break duration
    BREAK_REQUIRED_AFTER_DRIVING = 8.0  # Break required after 8 hours driving
    BREAK_DURATION_MINUTES = 30  # Minimum break duration
    FUEL_STOP_INTERVAL_MILES = 1000.0  # Fuel stop every 1000 miles
    MAX_CYCLE_HOURS = 70.0  # Maximum hours in 8-day cycle
    CYCLE_WINDOW_DAYS = 8  # Rolling window for cycle

    # Pickup and dropoff durations
    PICKUP_DURATION_HOURS = 1.0
    DROPOFF_DURATION_HOURS = 1.0

    @classmethod
    def process_trip(
        cls,
        route_segments: List[Dict],
        start_time: datetime,
        current_cycle_hours: float,
        pickup_location: str = "",
        dropoff_location: str = ""
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Process route segments and generate HOS-compliant timeline.

        Args:
            route_segments: List of route segments with distance_miles and duration_hours
            start_time: Start time for the trip
            current_cycle_hours: Hours already used in current 70-hour cycle
            pickup_location: Location name for pickup
            dropoff_location: Location name for dropoff

        Returns:
            Tuple of (timeline_events, stops)
            timeline_events: List of events with start_time, end_time, status, location, remarks
            stops: List of stops (breaks, fuel stops, etc.)
        """
        timeline = []
        stops = []
        current_time = start_time

        # State tracking
        cumulative_driving_hours = 0.0
        cumulative_on_duty_hours = 0.0
        last_break_time = None
        last_fuel_miles = 0.0
        total_distance = 0.0

        # Add pickup (ON_DUTY) - 1 hour assumption
        pickup_end = current_time + timedelta(hours=cls.PICKUP_DURATION_HOURS)
        timeline.append({
            "start_time": current_time,
            "end_time": pickup_end,
            "status": "ON_DUTY",
            "location": pickup_location or "Pickup Location",
            "remarks": f"Pickup - On Duty Not Driving (1 hour - Property-carrying driver assumption)"
        })
        cumulative_on_duty_hours += cls.PICKUP_DURATION_HOURS
        current_time = pickup_end

        # Process route segments
        for segment in route_segments:
            segment_distance = segment.get("distance_miles", 0.0)
            segment_duration = segment.get("duration_hours", 0.0)

            if segment_distance <= 0 or segment_duration <= 0:
                continue

            # Check for fuel stop needed (every 1,000 miles assumption)
            # Check if we've accumulated 1000 miles since last fuel stop
            miles_since_last_fuel = total_distance - last_fuel_miles

            # If adding this segment would exceed 1000 miles, insert fuel stop before it
            if miles_since_last_fuel + segment_distance >= cls.FUEL_STOP_INTERVAL_MILES:
                # Insert fuel stop before this segment
                fuel_stop_time = current_time
                fuel_stop_end = fuel_stop_time + timedelta(hours=0.5)  # 30 min fuel stop
                actual_miles_since_fuel = miles_since_last_fuel

                timeline.append({
                    "start_time": fuel_stop_time,
                    "end_time": fuel_stop_end,
                    "status": "ON_DUTY",
                    "location": "Fuel Stop",
                    "remarks": f"Fuel Stop - Required every 1,000 miles (Property-carrying driver assumption). ~{actual_miles_since_fuel:.0f} miles since last fuel."
                })
                stops.append({
                    "type": "FUEL",
                    "time": fuel_stop_time,
                    "location": "Fuel Stop",
                    "remarks": f"Fuel stop - Required every 1,000 miles (~{actual_miles_since_fuel:.0f} miles)"
                })

                cumulative_on_duty_hours += 0.5
                current_time = fuel_stop_end
                last_fuel_miles = total_distance  # Update to current total distance before adding segment

            # Check 30-minute break requirement (after 8 hours cumulative driving)
            # This should be checked independently before 10-hour break checks
            if cumulative_driving_hours >= cls.BREAK_REQUIRED_AFTER_DRIVING:
                # Check if we've had a break recently
                needs_30min_break = False
                if last_break_time is None:
                    needs_30min_break = True
                else:
                    # Check if 8 hours have passed since last break
                    hours_since_break = (current_time - last_break_time).total_seconds() / 3600
                    if hours_since_break >= cls.BREAK_REQUIRED_AFTER_DRIVING:
                        needs_30min_break = True

                if needs_30min_break:
                    # Need 30-minute break before continuing
                    break_start = current_time
                    break_end = break_start + timedelta(minutes=cls.BREAK_DURATION_MINUTES)

                    timeline.append({
                        "start_time": break_start,
                        "end_time": break_end,
                        "status": "OFF_DUTY",
                        "location": "Rest Stop",
                        "remarks": "30-minute break required"
                    })
                    stops.append({
                        "type": "BREAK",
                        "time": break_start,
                        "location": "Rest Stop",
                        "remarks": "30-minute break"
                    })

                    current_time = break_end
                    last_break_time = break_start
                    # Reset driving hours after break
                    cumulative_driving_hours = 0.0
                    # On-duty hours continue

            # Check if we need a 10-hour break before driving
            needs_break = False
            break_reason = ""

            # Check 11-hour driving limit
            if cumulative_driving_hours >= cls.MAX_DRIVING_HOURS:
                needs_break = True
                break_reason = "11-hour driving limit reached"

            # Check 14-hour workday rule
            elif cumulative_on_duty_hours >= cls.MAX_ON_DUTY_HOURS:
                needs_break = True
                break_reason = "14-hour workday limit reached"

            # Insert 10-hour break if needed
            if needs_break:
                break_start = current_time
                break_end = break_start + timedelta(hours=cls.REQUIRED_BREAK_HOURS)

                timeline.append({
                    "start_time": break_start,
                    "end_time": break_end,
                    "status": "SLEEPER",
                    "location": "Rest Area",
                    "remarks": f"10-hour break - {break_reason} (Property-carrying driver, 70hrs/8days cycle)"
                })
                stops.append({
                    "type": "REST",
                    "time": break_start,
                    "location": "Rest Area",
                    "remarks": break_reason
                })

                current_time = break_end
                last_break_time = break_start
                # Reset both counters after 10-hour break
                cumulative_driving_hours = 0.0
                cumulative_on_duty_hours = 0.0

            # Add driving segment
            segment_end = current_time + timedelta(hours=segment_duration)
            timeline.append({
                "start_time": current_time,
                "end_time": segment_end,
                "status": "DRIVING",
                "location": segment.get("location", "Route Segment"),
                "remarks": segment.get("remarks", f"Route segment - {segment_distance:.2f} miles (Property-carrying driver)")
            })

            cumulative_driving_hours += segment_duration
            cumulative_on_duty_hours += segment_duration
            total_distance += segment_distance
            current_time = segment_end

        # Add dropoff (ON_DUTY) - 1 hour assumption
        dropoff_end = current_time + timedelta(hours=cls.DROPOFF_DURATION_HOURS)
        timeline.append({
            "start_time": current_time,
            "end_time": dropoff_end,
            "status": "ON_DUTY",
            "location": dropoff_location or "Dropoff Location",
            "remarks": f"Dropoff - On Duty Not Driving (1 hour - Property-carrying driver assumption)"
        })
        cumulative_on_duty_hours += cls.DROPOFF_DURATION_HOURS

        return timeline, stops

    @classmethod
    def check_70_hour_cycle(cls, timeline: List[Dict], current_cycle_hours: float) -> bool:
        """
        Check if timeline complies with 70-hour cycle rule.
        This is a simplified check - full implementation would track rolling 8-day window.

        Args:
            timeline: List of timeline events
            current_cycle_hours: Hours already used in current cycle

        Returns:
            True if compliant, False otherwise
        """
        total_on_duty_hours = current_cycle_hours

        for event in timeline:
            if event["status"] in ["DRIVING", "ON_DUTY"]:
                duration = (event["end_time"] - event["start_time"]).total_seconds() / 3600
                total_on_duty_hours += duration

        return total_on_duty_hours <= cls.MAX_CYCLE_HOURS

