from django.conf import settings
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from weather.geocoding import search_places

from .serializers import AnalyzeRequestSerializer, GeocodeQuerySerializer
from .service import analyze


class AnalyzeRateThrottle(AnonRateThrottle):
    """Each analysis calls the public routing and weather services, so it is limited per client."""

    scope = "analyze"


class GeocodeRateThrottle(AnonRateThrottle):
    scope = "geocode"


@api_view(["GET"])
@throttle_classes([])
def health(request: Request) -> Response:
    return Response(
        {
            "status": "ok",
            "version": settings.APP_VERSION,
            "providers": {"routing": settings.ROUTING_PROVIDER, "weather": "open-meteo"},
        }
    )


@api_view(["GET"])
@throttle_classes([GeocodeRateThrottle])
def geocode(request: Request) -> Response:
    query = GeocodeQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    places = search_places(query.validated_data["q"], query.validated_data["limit"])
    return Response({"results": places})


@api_view(["POST"])
@throttle_classes([AnalyzeRateThrottle])
def analyze_routes(request: Request) -> Response:
    serializer = AnalyzeRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(analyze(serializer.to_trip()))
