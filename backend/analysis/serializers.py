"""Request validation for the API (spec section 6)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from django.conf import settings
from rest_framework import serializers

from routing.geometry import haversine_miles

from .service import MODE_FIXTURE, MODE_LIVE, Place, TripRequest

INTERVAL_CHOICES = (10, 25, 50)
MAX_LOAD_LB = 200_000
MAX_PAST = timedelta(hours=1)  # a driver may be analyzing a trip that has just started
MAX_AHEAD = timedelta(days=14)  # forecast coverage, with margin
MIN_TRIP_MILES = 0.1


class PlaceSerializer(serializers.Serializer):
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)
    label = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")

    def validate(self, attrs):
        # "nan" parses as a float and slips past the range checks, so reject it explicitly.
        if not (math.isfinite(attrs["lat"]) and math.isfinite(attrs["lon"])):
            raise serializers.ValidationError("Latitude and longitude must be finite numbers.")
        return attrs


class AnalyzeRequestSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure_time = serializers.CharField(max_length=40)
    load_weight_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)
    checkpoint_interval_miles = serializers.ChoiceField(choices=INTERVAL_CHOICES, default=25)
    mode = serializers.ChoiceField(choices=(MODE_LIVE, MODE_FIXTURE), default=MODE_LIVE)

    def validate_departure_time(self, value: str) -> datetime:
        try:
            departure = datetime.fromisoformat(value)
        except ValueError as exc:
            raise serializers.ValidationError(
                "Use an ISO 8601 date and time, for example 2026-11-06T08:00:00-07:00."
            ) from exc
        if departure.tzinfo is None:
            raise serializers.ValidationError(
                "Include a UTC offset or Z, for example 2026-11-06T08:00:00-07:00."
            )
        now = datetime.now(UTC)
        if departure < now - MAX_PAST:
            raise serializers.ValidationError(
                "Departure time cannot be more than 1 hour in the past."
            )
        if departure > now + MAX_AHEAD:
            raise serializers.ValidationError(
                "Departure time must be within the next 14 days (weather forecast coverage)."
            )
        return departure

    def validate_mode(self, value: str) -> str:
        if value == MODE_FIXTURE and not settings.ALLOW_FIXTURE_MODE:
            raise serializers.ValidationError("Demo mode is not enabled on this server.")
        return value

    def validate(self, attrs):
        origin, destination = attrs["origin"], attrs["destination"]
        apart = haversine_miles(
            origin["lat"], origin["lon"], destination["lat"], destination["lon"]
        )
        if apart < MIN_TRIP_MILES:
            raise serializers.ValidationError(
                {"destination": ["Origin and destination must be different places."]}
            )
        return attrs

    def to_trip(self) -> TripRequest:
        data = self.validated_data
        return TripRequest(
            origin=Place(**data["origin"]),
            destination=Place(**data["destination"]),
            departure=data["departure_time"],
            load_weight_lb=data["load_weight_lb"],
            interval_miles=data["checkpoint_interval_miles"],
            mode=data["mode"],
        )


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=2, max_length=100)
    limit = serializers.IntegerField(min_value=1, max_value=10, default=5)
