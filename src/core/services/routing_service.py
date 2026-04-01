from concurrent.futures import ThreadPoolExecutor


class RoutingService:
    def __init__(self, strategy):
        self.strategy = strategy
        self.executor = ThreadPoolExecutor(max_workers=5)

    def calculate_route(self, request):
        return self.strategy.calculate(request)

    def calculate_routes_parallel(self, requests):
        return list(self.executor.map(self.calculate_route, requests))
