from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass, field
from typing import Optional
from threading import Lock

from src.core.graph import NavigationGraph, Waypoint
from src.core.routing.strategy import RoutingStrategy

logger = logging.getLogger(__name__)

@dataclass
class RouteRequest:
    """
    A single route calculation request.

    Attributes:
        vessel_id:  Unique identifier of the vessel making the request.
        start_id:   node_id of the origin waypoint in the NavigationGraph.
        end_id:     node_id of the destination waypoint in the NavigationGraph.
        strategy:   The routing strategy to use (EcoStrategy / FastestStrategy).
    """
    vessel_id: str
    start_id: str
    end_id: str
    strategy: RoutingStrategy


@dataclass
class RouteResult:
    """
    The result of a single route calculation.

    Attributes:
        vessel_id:  Mirrors the vessel_id from the originating RouteRequest.
        waypoints:  Ordered list of Waypoint objects forming the route, or
                    ``None`` if no path could be found.
        success:    ``True`` if a path was found, ``False`` otherwise.
        error:      Exception message if the calculation raised an error.
    """
    vessel_id: str
    waypoints: Optional[list[Waypoint]] = None
    success: bool = False
    error: Optional[str] = None


class ParallelRouteCalculator:
    """
    Calculates multiple maritime routes concurrently using a thread pool.

    Each :class:`RouteRequest` is submitted as an independent task to a
    ``ThreadPoolExecutor``.  Results are collected once all tasks finish,
    meaning the total wall-clock time is bounded by the *slowest* single
    calculation rather than the sum of all calculations.

    Thread safety
    -------------
    The ``NavigationGraph`` is *read* concurrently by all worker threads.
    Because A* only reads the graph (no mutations during calculation), this
    is safe without additional locking.  If you need to block/unblock edges
    *while* calculations are running, acquire ``graph_lock`` externally
    before mutating the graph.

    Example usage::

        graph = NavigationGraph()
        # ... populate graph ...

        calculator = ParallelRouteCalculator(graph, max_workers=4)

        requests = [
            RouteRequest("VESSEL_1", "MALTA", "PIRAEUS", FastestStrategy()),
            RouteRequest("VESSEL_2", "TRIPOLI", "PIRAEUS", EcoStrategy()),
        ]

        results = calculator.calculate_routes(requests)
        for result in results:
            if result.success:
                print(f"{result.vessel_id}: {[wp.node_id for wp in result.waypoints]}")
            else:
                print(f"{result.vessel_id}: FAILED — {result.error}")
    """

    def __init__(
        self,
        graph: NavigationGraph,
        max_workers: int = 4,
    ) -> None:
        """
        Parameters:
            graph:       The shared NavigationGraph used for all calculations.
            max_workers: Maximum number of threads in the pool.  Defaults to 4
                         which is a sensible ceiling for I/O-bound A* work.
        """
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")

        self._graph = graph
        self._max_workers = max_workers
        self._graph_lock = Lock()


    def calculate_routes(self, requests: list[RouteRequest]) -> list[RouteResult]:
        """
        Calculate all requested routes in parallel and return the results.

        The method blocks until every task has either succeeded or failed.
        Results are returned in the **same order** as the input requests.

        Parameters:
            requests: List of :class:`RouteRequest` objects to process.

        Returns:
            A list of :class:`RouteResult` objects, one per request,
            preserving the original order.
        """
        if not requests:
            return []

        results: list[Optional[RouteResult]] = [None] * len(requests)

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_index: dict[Future, int] = {
                executor.submit(self._calculate_single, req): idx
                for idx, req in enumerate(requests)
            }

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                except Exception as exc:
                    vessel_id = requests[idx].vessel_id
                    logger.error(
                        "Unexpected error for vessel %s: %s", vessel_id, exc
                    )
                    results[idx] = RouteResult(
                        vessel_id=vessel_id,
                        success=False,
                        error=str(exc),
                    )

        return results

    def calculate_single_route(self, request: RouteRequest) -> RouteResult:
        """
        Calculate a single route synchronously (no thread pool).

        Useful for one-off calculations or when the caller already manages
        concurrency externally.
        """
        return self._calculate_single(request)


    def _calculate_single(self, request: RouteRequest) -> RouteResult:
        """
        Execute one route calculation inside a worker thread.

        All exceptions are caught and converted to a failed :class:`RouteResult`
        so that one bad request never cancels the remaining tasks.
        """
        logger.debug(
            "Calculating route for vessel %s: %s → %s",
            request.vessel_id,
            request.start_id,
            request.end_id,
        )
        try:
            waypoints = request.strategy.calculate_route(
                self._graph,
                request.start_id,
                request.end_id,
            )

            if waypoints is None:
                logger.warning(
                    "No path found for vessel %s (%s → %s)",
                    request.vessel_id,
                    request.start_id,
                    request.end_id,
                )
                return RouteResult(
                    vessel_id=request.vessel_id,
                    waypoints=None,
                    success=False,
                    error="No path found between the given waypoints.",
                )

            logger.info(
                "Route calculated for vessel %s: %d waypoints",
                request.vessel_id,
                len(waypoints),
            )
            return RouteResult(
                vessel_id=request.vessel_id,
                waypoints=waypoints,
                success=True,
            )

        except Exception as exc:
            logger.error(
                "Error calculating route for vessel %s: %s",
                request.vessel_id,
                exc,
                exc_info=True,
            )
            return RouteResult(
                vessel_id=request.vessel_id,
                success=False,
                error=str(exc),
            )
