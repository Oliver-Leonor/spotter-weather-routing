"""Route recommendation: fixed priority order and explanations (spec section 8)."""

from risk.recommendation import RouteCandidate, recommend

HOUR = 3600.0


def route(
    name: str,
    *,
    severe: float = 0.0,
    high: float = 0.0,
    average: float | None = 0.0,
    hours: float = 9.0,
    status: str = "ok",
    issue: str | None = None,
) -> RouteCandidate:
    letter = name[-1]
    return RouteCandidate(
        route_id=f"route-{'ABC'.index(letter) + 1}",
        name=name,
        status=status,
        severe_miles=severe,
        high_miles=high,
        average_risk=average,
        duration_seconds=hours * HOUR,
        issue=issue,
    )


# ------------------------------------------------------- priority order ------
def test_fewest_severe_miles_wins_over_everything_else():
    a = route("Route A", severe=5.0, high=0.0, average=0.1, hours=8.0)
    b = route("Route B", severe=0.0, high=50.0, average=0.9, hours=10.0)
    assert recommend([a, b]).route_id == "route-2"


def test_fewest_high_miles_wins_when_severe_miles_tie():
    a = route("Route A", severe=5.0, high=3.0, average=0.1, hours=8.0)
    b = route("Route B", severe=5.0, high=0.0, average=0.9, hours=10.0)
    assert recommend([a, b]).route_id == "route-2"


def test_lowest_average_risk_wins_when_severe_and_high_miles_tie():
    a = route("Route A", severe=5.0, high=3.0, average=0.30, hours=8.0)
    b = route("Route B", severe=5.0, high=3.0, average=0.20, hours=10.0)
    assert recommend([a, b]).route_id == "route-2"


def test_shortest_duration_wins_when_all_risk_measures_tie():
    a = route("Route A", severe=5.0, high=3.0, average=0.2, hours=9.5)
    b = route("Route B", severe=5.0, high=3.0, average=0.2, hours=9.0)
    assert recommend([a, b]).route_id == "route-2"


def test_complete_tie_is_broken_by_route_order():
    a = route("Route A")
    b = route("Route B")
    assert recommend([b, a]).route_id == "route-1"


def test_ranking_lists_every_eligible_route_best_first():
    a = route("Route A", severe=5.0)
    b = route("Route B", severe=0.0, high=4.0)
    c = route("Route C", severe=0.0, high=1.0)
    assert recommend([a, b, c]).ranking == ("route-3", "route-2", "route-1")


def test_differences_below_the_rounding_step_do_not_decide():
    # 10.04 and 10.01 severe miles are both 10.0; 0.2004 and 0.2001 average risk are both 0.200.
    a = route("Route A", severe=10.04, high=2.0, average=0.2004, hours=9.5)
    b = route("Route B", severe=10.01, high=2.0, average=0.2001, hours=9.4)
    c = route("Route C", severe=10.01, high=2.0, average=0.2001, hours=9.6)
    assert recommend([a, b, c]).ranking == ("route-2", "route-1", "route-3")


# ----------------------------------------------- blocked and unverified ------
def test_blocked_route_is_never_recommended_even_if_it_scores_best():
    a = route("Route A", status="blocked", issue="No Travel at checkpoint 7 (wind 58.0 mph)")
    b = route("Route B", severe=40.0, high=80.0, average=2.1, hours=12.0)
    result = recommend([a, b])
    assert result.route_id == "route-2"
    assert result.ranking == ("route-2",)
    assert result.blocked_route_ids == ("route-1",)


def test_unverified_route_is_never_recommended():
    a = route("Route A", status="unverified", average=None, issue="forecast unavailable")
    b = route("Route B", severe=40.0)
    result = recommend([a, b])
    assert result.route_id == "route-2"
    assert result.unverified_route_ids == ("route-1",)


def test_no_route_is_recommended_when_all_are_blocked_or_unverified():
    a = route(
        "Route A",
        status="blocked",
        issue="No Travel at checkpoint 7 near 39.41, -102.33 at 18:00 MST (wind 58.0 mph)",
    )
    c = route(
        "Route C",
        status="unverified",
        average=None,
        issue="forecast unavailable for 3 checkpoints",
    )
    result = recommend([a, c])
    assert result.route_id is None
    assert result.ranking == ()
    assert result.blocked_route_ids == ("route-1",)
    assert result.unverified_route_ids == ("route-3",)
    assert result.explanation == (
        "No safe route is currently recommended. "
        "Route A: No Travel at checkpoint 7 near 39.41, -102.33 at 18:00 MST (wind 58.0 mph). "
        "Route C could not be verified: forecast unavailable for 3 checkpoints."
    )


# ---------------------------------------------------------- explanations ------
def test_explains_avoided_severe_miles_and_the_added_travel_time():
    a = route("Route A", severe=18.0, hours=8.8)
    b = route("Route B", severe=0.0, hours=9.2)
    assert recommend([a, b]).explanation == (
        "Route B is recommended because it avoids 18.0 miles of severe weather encountered on "
        "Route A, despite adding 24 minutes of travel time."
    )


def test_explains_fewer_severe_miles_when_the_winner_still_has_some():
    a = route("Route A", severe=23.0, hours=9.0)
    b = route("Route B", severe=5.0, hours=8.5)
    assert recommend([a, b]).explanation == (
        "Route B is recommended because it has 18.0 fewer miles of severe weather than Route A "
        "(5.0 vs 23.0 miles), and it is also 30 minutes faster."
    )


def test_explains_avoided_high_risk_miles():
    a = route("Route A", severe=2.0, high=12.5, hours=9.0)
    b = route("Route B", severe=2.0, high=0.0, hours=9.0)
    assert recommend([a, b]).explanation == (
        "Route B is recommended because it avoids 12.5 miles of high-risk weather encountered on "
        "Route A, with the same travel time. Severe-weather miles are tied at 2.0."
    )


def test_explains_lower_average_risk():
    a = route("Route A", average=0.412, hours=9.0)
    b = route("Route B", average=0.26, hours=9.02)
    assert recommend([a, b]).explanation == (
        "Route B is recommended because it has the lower average weather risk (0.260 vs 0.412 "
        "for Route A), despite adding 1 minute of travel time. Severe and high-risk miles are tied."
    )


def test_explains_a_win_on_travel_time_alone():
    a = route("Route A", hours=8.78)
    b = route("Route B", hours=9.53)
    assert recommend([a, b]).explanation == (
        "Route A is recommended because it is 45 minutes faster than Route B. "
        "Severe miles, high-risk miles and average risk are tied."
    )


def test_explains_why_the_winner_also_beats_the_third_route():
    # Route A is the quickest of all, but it is only third because of its severe miles. The
    # explanation must not call the winner "the fastest" and must say why Route A lost.
    a = route("Route A", severe=50.0, hours=2.0)
    b = route("Route B", hours=2.5)
    c = route("Route C", hours=3.0)
    assert recommend([a, b, c]).explanation == (
        "Route B is recommended because it is 30 minutes faster than Route C. "
        "Severe miles, high-risk miles and average risk are tied. "
        "It also has 50.0 fewer miles of severe weather than Route A."
    )


def test_third_route_comparison_names_the_criterion_that_separates_it():
    def third_route_sentence(*routes):
        return recommend(list(routes)).explanation.rsplit(". ", 1)[-1]

    assert (
        third_route_sentence(
            route("Route A", hours=9.0),
            route("Route B", high=3.0, hours=8.0),
            route("Route C", high=7.5, hours=8.0),
        )
        == "It also has 7.5 fewer miles of high-risk weather than Route C."
    )
    assert (
        third_route_sentence(
            route("Route A", average=0.0, hours=9.0),
            route("Route B", average=0.2, hours=8.0),
            route("Route C", average=0.4, hours=7.0),
        )
        == "It also has a lower average weather risk than Route C (0.000 vs 0.400)."
    )
    assert (
        third_route_sentence(
            route("Route A", hours=8.0),
            route("Route B", hours=8.5),
            route("Route C", hours=9.0),
        )
        == "It is also 60 minutes faster than Route C."
    )
    assert (
        third_route_sentence(
            route("Route A"),
            route("Route B"),
            route("Route C"),
        )
        == "It also ties with Route C."
    )


def test_explains_a_complete_tie():
    assert recommend([route("Route A"), route("Route B")]).explanation == (
        "Route A is recommended. It ties with Route B on weather risk and travel time, so the "
        "routing provider's order decides."
    )


def test_explains_when_every_other_route_is_excluded():
    a = route("Route A", status="blocked", issue="No Travel at checkpoint 15 (wind 48.2 mph)")
    b = route(
        "Route B", status="unverified", average=None, issue="forecast unavailable for 2 checkpoints"
    )
    c = route("Route C", severe=25.0)
    assert recommend([a, b, c]).explanation == (
        "Route C is recommended because it is the only route that is neither blocked nor "
        "unverified. Route A: No Travel at checkpoint 15 (wind 48.2 mph). "
        "Route B could not be verified: forecast unavailable for 2 checkpoints."
    )


def test_excluded_routes_are_named_after_the_comparison():
    a = route("Route A", status="blocked", issue="No Travel at checkpoint 15 (wind 48.2 mph)")
    b = route("Route B", severe=10.0, hours=9.0)
    c = route("Route C", severe=0.0, hours=9.5)
    assert recommend([a, b, c]).explanation == (
        "Route C is recommended because it avoids 10.0 miles of severe weather encountered on "
        "Route B, despite adding 30 minutes of travel time. "
        "Route A: No Travel at checkpoint 15 (wind 48.2 mph)."
    )


def test_explains_a_single_returned_route():
    assert recommend([route("Route A", high=4.0)]).explanation == (
        "Route A is the only route the routing provider returned, and it has no No Travel "
        "conditions or unverified weather."
    )
