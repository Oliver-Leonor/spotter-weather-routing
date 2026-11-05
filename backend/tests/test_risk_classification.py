"""Spotter weather risk rules: exact thresholds, boundary convention and load rules.

Boundary convention (spec section 7): "X to below Y" is the half-open interval [X, Y); a value equal
to a shared boundary belongs to the more severe class; "above" thresholds are strict.
"""

import pytest

from risk.classification import (
    classify_checkpoint,
    classify_rain,
    classify_snow,
    classify_wind,
)
from risk.levels import RiskLevel

LOW, MOD, HIGH, SEV, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


# ---------------------------------------------------------------- wind ------
@pytest.mark.parametrize(
    "mph, expected",
    [
        (0.0, LOW),
        (24.99, LOW),
        (25.0, MOD),
        (34.99, MOD),
        (35.0, HIGH),
        (44.99, HIGH),
        (45.0, SEV),
        (54.99, SEV),
        (55.0, NT),
        (80.0, NT),
    ],
)
def test_wind_thresholds(mph, expected):
    assert classify_wind(mph) is expected


# ---------------------------------------------------------------- rain ------
@pytest.mark.parametrize(
    "inches_per_hour, expected",
    [
        (0.0, LOW),
        (0.099, LOW),
        (0.10, MOD),
        (0.249, MOD),
        (0.25, HIGH),
        (0.499, HIGH),
        (0.50, SEV),
        (0.75, SEV),
        (1.00, SEV),  # "0.50 through 1.00" is inclusive at 1.00
        (1.001, NT),  # "above 1.00" is strict
        (2.0, NT),
    ],
)
def test_rain_thresholds(inches_per_hour, expected):
    assert classify_rain(inches_per_hour) is expected


# ---------------------------------------------------------------- snow ------
@pytest.mark.parametrize(
    "inches_per_hour, expected",
    [
        (0.0, LOW),
        (0.49, LOW),
        (0.5, MOD),
        (0.99, MOD),
        (1.0, HIGH),
        (1.99, HIGH),
        (2.0, SEV),
        (2.5, SEV),
        (3.0, SEV),  # "2.0 through 3.0" inclusive at 3.0
        (3.001, NT),  # "above 3.0" strict
        (5.0, NT),
    ],
)
def test_snow_thresholds(inches_per_hour, expected):
    assert classify_snow(inches_per_hour) is expected


# ------------------------------------------------------- load-dependent -----
@pytest.mark.parametrize(
    "mph, load_lb, expected, rule",
    [
        # Rule 1: wind >= 55 is No Travel regardless of load
        (55.0, 0, NT, "wind_no_travel"),
        (60.0, 30000, NT, "wind_no_travel"),
        # Rule 2: 45 <= wind < 55 and load > 30,000 -> No Travel (strict >)
        (45.0, 30000, SEV, None),
        (45.0, 30001, NT, "load_rule_2"),
        (54.99, 30000, SEV, None),
        (54.99, 30001, NT, "load_rule_2"),
        (50.0, 29999, SEV, None),
        # Rule 3: 35 <= wind < 45 and load > 40,000 -> Severe (strict >)
        (35.0, 40000, HIGH, None),
        (35.0, 40001, SEV, "load_rule_3"),
        (44.99, 40000, HIGH, None),
        (44.99, 40001, SEV, "load_rule_3"),
        (40.0, 30001, HIGH, None),  # rule 2 does not apply below 45 mph
        # Load never changes wind below 35 mph
        (34.99, 200000, MOD, None),
        (24.99, 200000, LOW, None),
    ],
)
def test_load_dependent_wind_rules(mph, load_lb, expected, rule):
    result = classify_checkpoint(
        wind_mph=mph, rain_in_per_hr=0.0, snow_in_per_hr=0.0, load_lb=load_lb
    )
    assert result.level is expected
    assert result.load_rule_applied == rule


# ------------------------------------------------------------ combined ------
def test_final_level_is_highest_of_wind_rain_snow():
    result = classify_checkpoint(
        wind_mph=10.0, rain_in_per_hr=0.3, snow_in_per_hr=2.5, load_lb=1000
    )
    assert result.level is SEV
    assert result.wind_level is LOW
    assert result.rain_level is HIGH
    assert result.snow_level is SEV
    assert result.drivers == ["snow"]


def test_drivers_list_every_condition_at_the_final_level():
    result = classify_checkpoint(wind_mph=36.0, rain_in_per_hr=0.26, snow_in_per_hr=0.0, load_lb=0)
    assert result.level is HIGH
    assert result.drivers == ["wind", "rain"]


def test_load_rule_driver_named_when_it_sets_the_level():
    result = classify_checkpoint(
        wind_mph=46.0, rain_in_per_hr=0.0, snow_in_per_hr=0.0, load_lb=30001
    )
    assert result.level is NT
    assert result.drivers == ["wind", "load_rule_2"]


def test_no_travel_from_rain_overrides_low_wind_even_with_light_load():
    result = classify_checkpoint(wind_mph=5.0, rain_in_per_hr=1.5, snow_in_per_hr=0.0, load_lb=0)
    assert result.level is NT
    assert result.drivers == ["rain"]


def test_severity_order_is_low_moderate_high_severe_no_travel():
    assert LOW < MOD < HIGH < SEV < NT
    assert [lvl.value for lvl in (LOW, MOD, HIGH, SEV, NT)] == [0, 1, 2, 3, 4]
    assert NT.label == "No Travel" and LOW.slug == "low" and NT.slug == "no_travel"


# ------------------------------------------------------------ missing -------
@pytest.mark.parametrize(
    "wind, rain, snow",
    [(None, 0.0, 0.0), (10.0, None, 0.0), (10.0, 0.0, None), (None, None, None)],
)
def test_missing_measurement_yields_unknown_not_low(wind, rain, snow):
    result = classify_checkpoint(wind_mph=wind, rain_in_per_hr=rain, snow_in_per_hr=snow, load_lb=0)
    assert result.level is None
    assert result.is_unknown is True
    assert result.drivers == []


# ------------------------------------------ conclusive No Travel with gaps ---
@pytest.mark.parametrize(
    "wind, rain, snow, load_lb, drivers, missing",
    [
        # Rule 1: wind >= 55 mph is No Travel regardless of load; missing rain cannot soften it
        (55.0, None, 0.0, 30000, ["wind"], ["rain"]),
        (60.0, None, None, 0, ["wind"], ["rain", "snow"]),
        # Rule 2: 45 <= wind < 55 with load > 30,000 lb
        (50.0, None, 0.0, 30001, ["wind", "load_rule_2"], ["rain"]),
        # Rain above 1.00 in/h is conclusive even with wind and snow missing
        (None, 1.01, None, 0, ["rain"], ["wind", "snow"]),
        # Snow above 3.0 in/h is conclusive even with wind missing
        (None, 0.0, 3.01, 0, ["snow"], ["wind"]),
    ],
)
def test_conclusive_no_travel_survives_missing_measurements(
    wind, rain, snow, load_lb, drivers, missing
):
    result = classify_checkpoint(
        wind_mph=wind, rain_in_per_hr=rain, snow_in_per_hr=snow, load_lb=load_lb
    )
    assert result.level is NT
    assert result.is_unknown is False
    assert result.drivers == drivers
    assert result.missing == missing
    assert result.is_complete is False


def test_non_conclusive_known_levels_stay_unknown_when_a_measurement_is_missing():
    # Severe wind is known, but missing rain could still raise the level, so it is not conclusive
    result = classify_checkpoint(wind_mph=50.0, rain_in_per_hr=None, snow_in_per_hr=0.0, load_lb=0)
    assert result.level is None
    assert result.is_unknown is True
    assert result.wind_level is SEV
    assert result.missing == ["rain"]


def test_complete_measurements_report_no_missing_fields():
    result = classify_checkpoint(wind_mph=10.0, rain_in_per_hr=0.0, snow_in_per_hr=0.0, load_lb=0)
    assert result.missing == []
    assert result.is_complete is True


def test_to_dict_exposes_missing_measurements_and_unknown_level():
    result = classify_checkpoint(wind_mph=None, rain_in_per_hr=0.0, snow_in_per_hr=0.0, load_lb=0)
    payload = result.to_dict()
    assert payload["level"] == "unknown"
    assert payload["value"] is None
    assert payload["missing"] == ["wind"]
    payload = classify_checkpoint(
        wind_mph=55.0, rain_in_per_hr=None, snow_in_per_hr=0.0, load_lb=0
    ).to_dict()
    assert payload["level"] == "no_travel" and payload["value"] == 4
    assert payload["missing"] == ["rain"]


def test_negative_or_nan_values_are_treated_as_missing():
    import math

    result = classify_checkpoint(
        wind_mph=math.nan, rain_in_per_hr=0.0, snow_in_per_hr=0.0, load_lb=0
    )
    assert result.is_unknown
    result = classify_checkpoint(wind_mph=10.0, rain_in_per_hr=-0.1, snow_in_per_hr=0.0, load_lb=0)
    assert result.is_unknown


def test_classification_is_deterministic_and_pure():
    a = classify_checkpoint(wind_mph=45.0, rain_in_per_hr=0.5, snow_in_per_hr=2.0, load_lb=30001)
    b = classify_checkpoint(wind_mph=45.0, rain_in_per_hr=0.5, snow_in_per_hr=2.0, load_lb=30001)
    assert a == b
