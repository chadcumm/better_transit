"""Core RAPTOR routing algorithm.

Implements the Round-Based Public Transit Optimized Router algorithm.
Reference: "Round-Based Public Transit Routing" by Delling et al., 2012.
"""

from dataclasses import dataclass

from better_transit.routing.data import RaptorData, TransitRoute

INF = float("inf")
MAX_ROUNDS = 5  # Maximum number of transit legs (transfers + 1)


@dataclass
class Label:
    """Arrival label at a stop in a specific round."""

    arrival_time: int  # seconds since midnight
    trip_id: str | None = None
    board_stop: str | None = None  # where we boarded this trip
    board_time: int | None = None  # departure time at board stop (seconds)
    route_id: str | None = None
    transfer_from: str | None = None  # if arrived via walking transfer


@dataclass
class RaptorResult:
    """Result of a RAPTOR query."""

    labels: dict[int, dict[str, Label]]  # round -> stop_id -> best label
    target_stop_ids: list[str]
    source_stop_ids: list[str]


def run_raptor(
    data: RaptorData,
    source_stop_ids: list[str],
    target_stop_ids: list[str],
    departure_time: int,
    max_rounds: int = MAX_ROUNDS,
) -> RaptorResult:
    """Run the RAPTOR algorithm.

    Args:
        data: Pre-built RAPTOR data structures
        source_stop_ids: Starting stop(s) — may be multiple if walking to nearby stops
        target_stop_ids: Destination stop(s)
        departure_time: Departure time in seconds since midnight
        max_rounds: Maximum number of transit legs

    Returns:
        RaptorResult with arrival labels per round per stop.
    """
    # Initialize: best known arrival time at each stop
    # tau[k][stop] = earliest arrival time at stop using at most k trips
    tau: dict[int, dict[str, Label]] = {}

    # Global best arrival at each stop (across all rounds)
    best: dict[str, int] = {}

    # Round 0: walk to source stops
    tau[0] = {}
    for stop_id in source_stop_ids:
        tau[0][stop_id] = Label(arrival_time=departure_time)
        best[stop_id] = departure_time

    # Apply transfers from source stops (walking to nearby stops)
    _apply_transfers(data, tau[0], best, departure_time)

    # Mark stops that were improved this round
    marked: set[str] = set(tau[0].keys())

    for k in range(1, max_rounds + 1):
        tau[k] = {}

        # Collect routes to scan: routes passing through any marked stop
        routes_to_scan = _get_routes_to_scan(data, marked)
        marked = set()

        for route_id, board_stop_idx in routes_to_scan:
            route = data.routes[route_id]
            _scan_route(route, board_stop_idx, k, tau, best, marked)

        if not marked:
            break  # No improvements this round

        # Apply walking transfers from newly improved stops
        new_transfer_labels: dict[str, Label] = {}
        for stop_id in marked:
            if stop_id in tau[k]:
                new_transfer_labels[stop_id] = tau[k][stop_id]
        _apply_transfers(data, new_transfer_labels, best, None, tau[k], marked)

    return RaptorResult(
        labels=tau,
        target_stop_ids=target_stop_ids,
        source_stop_ids=source_stop_ids,
    )


def _get_routes_to_scan(
    data: RaptorData, marked: set[str]
) -> list[tuple[str, int]]:
    """Get (route_id, earliest_board_stop_index) for routes to scan."""
    route_board: dict[str, int] = {}
    for stop_id in marked:
        for route_id in data.stop_routes.get(stop_id, []):
            route = data.routes[route_id]
            try:
                idx = route.stops.index(stop_id)
            except ValueError:
                continue
            if route_id not in route_board or idx < route_board[route_id]:
                route_board[route_id] = idx
    return list(route_board.items())


def _scan_route(
    route: TransitRoute,
    board_stop_idx: int,
    k: int,
    tau: dict[int, dict[str, Label]],
    best: dict[str, int],
    marked: set[str],
) -> None:
    """Scan a route starting from board_stop_idx, looking for improvements."""
    num_stops = len(route.stops)

    for trip in route.trips:
        # Find the earliest trip we can board at any improved stop
        boarded = False
        board_stop = None
        board_departure = None

        for i in range(board_stop_idx, num_stops):
            stop_id = route.stops[i]

            # Can we board at this stop?
            if not boarded:
                prev_arrival = _best_arrival(tau, k - 1, stop_id)
                if prev_arrival <= trip.stop_times[i].departure:
                    boarded = True
                    board_stop = stop_id
                    board_departure = trip.stop_times[i].departure
                continue

            # We are on the trip — check if this improves arrival at stop
            arrival = trip.stop_times[i].arrival
            if arrival < best.get(stop_id, INF):
                tau[k][stop_id] = Label(
                    arrival_time=arrival,
                    trip_id=trip.trip_id,
                    board_stop=board_stop,
                    board_time=board_departure,
                    route_id=route.route_id,
                )
                best[stop_id] = arrival
                marked.add(stop_id)


def _best_arrival(
    tau: dict[int, dict[str, Label]], max_round: int, stop_id: str
) -> int:
    """Get the best arrival time at a stop up to round max_round."""
    result = INF
    for k in range(max_round + 1):
        if stop_id in tau.get(k, {}):
            t = tau[k][stop_id].arrival_time
            if t < result:
                result = t
    return result


def _apply_transfers(
    data: RaptorData,
    source_labels: dict[str, Label],
    best: dict[str, int],
    departure_time: int | None,
    target_labels: dict[str, Label] | None = None,
    marked: set[str] | None = None,
) -> None:
    """Apply walking transfers from stops with labels."""
    if target_labels is None:
        target_labels = source_labels
    if marked is None:
        marked = set()

    for stop_id, label in list(source_labels.items()):
        for transfer in data.transfers.get(stop_id, []):
            arrival = label.arrival_time + transfer.walk_seconds
            to_stop = transfer.to_stop_id
            if arrival < best.get(to_stop, INF):
                target_labels[to_stop] = Label(
                    arrival_time=arrival,
                    transfer_from=stop_id,
                )
                best[to_stop] = arrival
                marked.add(to_stop)
