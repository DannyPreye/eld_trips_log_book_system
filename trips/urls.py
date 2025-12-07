"""
URL configuration for trips app.
"""
from django.urls import path
from . import views

app_name = "trips"

urlpatterns = [
    path("trip/plan", views.TripPlanView.as_view(), name="trip-plan"),
    path("trip/<int:trip_id>", views.TripDetailView.as_view(), name="trip-detail"),
    path("trip/<int:trip_id>/logs", views.TripLogsView.as_view(), name="trip-logs"),
    path("healthcheck", views.health_check, name="health-check"),
]



