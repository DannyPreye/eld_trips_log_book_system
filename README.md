# ELD Trip Planner Backend

Django REST API backend for ELD Trip Planner & Logbook system. Processes trip inputs, computes routes via OpenRouteService, applies FMCSA Hours-of-Service rules, and generates structured ELD logbook data for React frontend rendering.

## Features

- **Trip Planning**: Accepts trip inputs and processes them through the full pipeline
- **Routing Integration**: Uses OpenRouteService for route computation and geocoding
- **HOS Compliance**: Enforces US FMCSA Hours-of-Service rules:
  - 11-hour driving limit
  - 14-hour workday rule
  - 30-minute break requirement
  - 70-hour cycle tracking
  - Fuel stop insertion (every 1,000 miles)
- **Daily Log Generation**: Slices trips into 24-hour log sheets
- **Grid Mapping**: Converts timeline events to grid indices for frontend visualization

## Tech Stack

- Django 6.0
- Django REST Framework
- PostgreSQL
- OpenRouteService API

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Virtual environment (`.venv`)

### Installation

1. **Activate virtual environment**:
   ```bash
   source .venv/Scripts/activate  # Windows Git Bash
   # or
   .venv/Scripts/activate  # Windows CMD
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your database and API credentials
   ```

4. **Set up PostgreSQL database**:
   ```bash
   createdb eld_trip_planner
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Create superuser** (optional):
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**:
   ```bash
   python manage.py runserver
   ```

## API Endpoints

### POST /api/trip/plan

Main endpoint for trip planning. Accepts trip input and returns structured logbook data.

**Request Body**:
```json
{
  "current_location": {"lat": 40.7128, "lng": -74.0060},
  "pickup_location": {"lat": 40.7580, "lng": -73.9855},
  "dropoff_location": {"lat": 34.0522, "lng": -118.2437},
  "current_cycle_used_hours": 0.0
}
```

**Response**:
```json
{
  "tripId": 1,
  "route": {
    "polyline": "...",
    "distanceMiles": 1430.2,
    "durationHours": 27.5,
    "segments": [...]
  },
  "logs": [
    {
      "date": "2025-10-14",
      "segments": [
        {
          "startTime": "2025-10-14T06:00:00Z",
          "endTime": "2025-10-14T10:30:00Z",
          "startIndex": 24,
          "endIndex": 42,
          "rowIndex": 2,
          "status": "DRIVING",
          "location": "Route Segment",
          "remarks": "Route segment"
        }
      ],
      "totals": {
        "drivingHours": 6.5,
        "onDutyHours": 7.75
      }
    }
  ],
  "stops": [
    {
      "type": "BREAK",
      "time": "2025-10-14T10:30:00Z",
      "location": "Rest Stop",
      "remarks": "30-minute break"
    }
  ],
  "meta": {
    "totalDays": 3,
    "totalDistanceMiles": 1430.2
  }
}
```

### GET /api/trip/{id}

Fetch complete trip details.

### GET /api/trip/{id}/logs

Fetch logs for frontend rendering (same as trip detail).

### GET /api/healthcheck

Health check endpoint.

## Project Structure

```
backend/
├── config/           # Django project settings
├── trips/            # Main application
│   ├── models.py     # Database models
│   ├── serializers.py # DRF serializers
│   ├── views.py      # API views
│   ├── urls.py       # URL routing
│   └── services/     # Business logic services
│       ├── geocoding.py
│       ├── routing.py
│       ├── hos_engine.py
│       ├── log_slicer.py
│       └── grid_mapper.py
├── requirements.txt
└── manage.py
```

## Testing

Run tests:
```bash
python manage.py test trips
```

## License

MIT


