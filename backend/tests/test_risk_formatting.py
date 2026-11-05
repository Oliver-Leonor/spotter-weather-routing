"""Measurements are shown with enough decimals to agree with the risk band they fall in."""

import pytest

from risk.classification import classify_rain, classify_snow, classify_wind
from risk.formatting import format_measurement


@pytest.mark.parametrize(
    "value, decimals, classify, expected",
    [
        (58.0, 1, classify_wind, "58.0"),
        (47.25, 1, classify_wind, "47.2"),
        (1.2, 2, classify_rain, "1.20"),
        (0.0, 2, classify_rain, "0.00"),
        # Rounded to two decimals these would read as a value in the lower band.
        (1.000394, 2, classify_rain, "1.0004"),  # No Travel: must not read "1.00"
        (3.003937, 2, classify_snow, "3.004"),  # No Travel: must not read "3.00"
        # Rounded to one decimal this would read as a value in the higher band.
        (54.9913, 1, classify_wind, "54.99"),  # Severe: must not read "55.0"
        (24.96, 1, classify_wind, "24.96"),  # Low: must not read "25.0"
    ],
)
def test_measurement_keeps_enough_decimals_to_match_its_band(value, decimals, classify, expected):
    assert format_measurement(value, decimals, classify) == expected
