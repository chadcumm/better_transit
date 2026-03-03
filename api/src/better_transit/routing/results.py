"""Extract trip legs from RAPTOR results."""

from better_transit.routing.raptor import Label, RaptorResult


def extract_journeys(result: RaptorResult) -> list[list[dict]]:
    """Extract Pareto-optimal journeys from RAPTOR results.

    Returns a list of journeys, each journey being a list of leg dicts.
    Journeys are Pareto-optimal on (arrival_time, num_transfers).
    """
    journeys = []
    best_arrival = float("inf")

    for k in sorted(result.labels.keys()):
        # Find the best target stop in this round
        best_target = None
        best_time = float("inf")
        for target in result.target_stop_ids:
            if target in result.labels[k]:
                t = result.labels[k][target].arrival_time
                if t < best_time:
                    best_time = t
                    best_target = target

        if best_target is None:
            continue

        # Pareto check: only include if arrival is better than previous
        if best_time >= best_arrival:
            continue
        best_arrival = best_time

        # Trace back the journey
        legs = _trace_journey(result.labels, k, best_target)
        if legs:
            journeys.append(legs)

    return journeys


def _trace_journey(
    tau: dict[int, dict[str, Label]],
    round_k: int,
    target_stop: str,
) -> list[dict]:
    """Trace back from a target stop to reconstruct journey legs."""
    legs = []
    current_stop = target_stop
    k = round_k

    while k >= 0:
        if current_stop not in tau.get(k, {}):
            break
        label = tau[k][current_stop]

        if label.transfer_from:
            # Walking transfer
            legs.append({
                "mode": "walk",
                "from_stop_id": label.transfer_from,
                "to_stop_id": current_stop,
                "arrival_time": label.arrival_time,
            })
            current_stop = label.transfer_from
            continue

        if label.trip_id:
            # Transit leg
            legs.append({
                "mode": "transit",
                "from_stop_id": label.board_stop,
                "to_stop_id": current_stop,
                "route_id": label.route_id,
                "trip_id": label.trip_id,
                "departure_time": label.board_time,
                "arrival_time": label.arrival_time,
            })
            current_stop = label.board_stop
            k -= 1
            continue

        # Source stop (no trip, no transfer) — we're done
        break

    legs.reverse()
    return legs
