"""Unit conversion for provider measurements.

The forecast is requested in mph, inches and Fahrenheit. The units the provider actually reports
are still checked on every response, so a silent change of defaults cannot shift a value across a
risk threshold. Each table maps a reported unit label to a converter into the unit the rules use.
"""

from __future__ import annotations

from collections.abc import Callable

Converter = Callable[[float], float]


def _scale(factor: float) -> Converter:
    return lambda value: value * factor


WIND_TO_MPH: dict[str, Converter] = {
    "mp/h": _scale(1.0),
    "mph": _scale(1.0),
    "km/h": _scale(1 / 1.609344),
    "m/s": _scale(3600 / 1609.344),
    "kn": _scale(1852 / 1609.344),
}
RAIN_TO_INCHES: dict[str, Converter] = {"inch": _scale(1.0), "mm": _scale(1 / 25.4)}
SNOW_TO_INCHES: dict[str, Converter] = {"inch": _scale(1.0), "cm": _scale(1 / 2.54)}
TEMPERATURE_TO_F: dict[str, Converter] = {
    "°F": _scale(1.0),
    "°C": lambda celsius: celsius * 9 / 5 + 32,
}
