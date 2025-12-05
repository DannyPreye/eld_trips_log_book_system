from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Trip(models.Model):
    """Stores trip metadata and input values."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    # Input fields
    current_location_lat = models.FloatField()
    current_location_lng = models.FloatField()
    pickup_location_lat = models.FloatField()
    pickup_location_lng = models.FloatField()
    dropoff_location_lat = models.FloatField()
    dropoff_location_lng = models.FloatField()
    current_cycle_used_hours = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(70)],
        help_text="Hours used in current 70-hour cycle"
    )

    # Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Trip {self.id} - {self.status}"


class Route(models.Model):
    """Stores route data from routing service."""

    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="route")
    polyline = models.TextField(help_text="Encoded polyline string")
    distance_miles = models.FloatField(help_text="Total distance in miles")
    duration_hours = models.FloatField(help_text="Total driving duration in hours")
    segments = models.JSONField(default=list, help_text="Route segments with geometry and instructions")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Route for Trip {self.trip.id} - {self.distance_miles:.2f} miles"


class TimelineEvent(models.Model):
    """Stores HOS compliance events."""

    STATUS_CHOICES = [
        ("DRIVING", "Driving"),
        ("OFF_DUTY", "Off Duty"),
        ("ON_DUTY", "On Duty"),
        ("SLEEPER", "Sleeper Berth"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="timeline_events")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    location = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["trip", "start_time"]),
        ]

    def __str__(self):
        return f"{self.status} - {self.start_time} to {self.end_time}"


class DailyLog(models.Model):
    """Stores daily log sheets (24-hour periods)."""

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="daily_logs")
    date = models.DateField(help_text="Date of the log sheet (YYYY-MM-DD)")
    driving_hours = models.FloatField(default=0, help_text="Total driving hours for this day")
    on_duty_hours = models.FloatField(default=0, help_text="Total on-duty hours for this day")
    segments = models.JSONField(default=list, help_text="Segments with grid indices for this day")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        unique_together = [["trip", "date"]]
        indexes = [
            models.Index(fields=["trip", "date"]),
        ]

    def __str__(self):
        return f"Daily Log - Trip {self.trip.id} - {self.date}"


class Stop(models.Model):
    """Stores stops (fuel, breaks, rest stops)."""

    STOP_TYPE_CHOICES = [
        ("BREAK", "Break"),
        ("FUEL", "Fuel Stop"),
        ("REST", "Rest Stop"),
        ("PICKUP", "Pickup"),
        ("DROPOFF", "Dropoff"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    stop_type = models.CharField(max_length=20, choices=STOP_TYPE_CHOICES)
    time = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["time"]
        indexes = [
            models.Index(fields=["trip", "time"]),
        ]

    def __str__(self):
        return f"{self.stop_type} - {self.time}"
