from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=5)

def dispatch_notification(observer, zone_id, status):
    executor.submit(observer.update, zone_id, status)
