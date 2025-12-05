"""
Admin configuration for trips app.
"""
from django.contrib import admin
from .models import Trip, Route, TimelineEvent, DailyLog, Stop


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["id", "status", "current_cycle_used_hours", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id"]


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["trip", "distance_miles", "duration_hours", "created_at"]
    list_filter = ["created_at"]


@admin.register(TimelineEvent)
class TimelineEventAdmin(admin.ModelAdmin):
    list_display = ["trip", "status", "start_time", "end_time", "location"]
    list_filter = ["status", "start_time"]
    search_fields = ["trip__id", "location"]


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ["trip", "date", "driving_hours", "on_duty_hours"]
    list_filter = ["date"]
    search_fields = ["trip__id"]


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
    list_display = ["trip", "stop_type", "time", "location"]
    list_filter = ["stop_type", "time"]
    search_fields = ["trip__id", "location"]
