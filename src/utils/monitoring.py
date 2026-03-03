from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
import logging

logger = logging.getLogger(__name__)

class PrometheusMetrics:
    def __init__(self, port: int = 9090):
        self.port = port
        
        # Counters
        self.analysis_requests = Counter(
            'analysis_requests_total',
            'Total analysis requests'
        )
        self.analysis_errors = Counter(
            'analysis_errors_total',
            'Total analysis errors'
        )
        self.alerts_generated = Counter(
            'alerts_generated_total',
            'Total alerts generated',
            ['severity']
        )
        
        # Histograms
        self.analysis_duration = Histogram(
            'analysis_duration_seconds',
            'Time spent on analysis',
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        # Gauges
        self.queue_size = Gauge(
            'analysis_queue_size',
            'Current size of analysis queue'
        )
        self.model_accuracy = Gauge(
            'model_accuracy',
            'Current model accuracy'
        )
        
        # Start server
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.warning(f"Could not start metrics server: {e}")
            
    def increment_counter(self, name: str, labels: dict = None):
        if name == 'analysis_requests_total':
            self.analysis_requests.inc()
        elif name == 'analysis_errors_total':
            self.analysis_errors.inc()
            
    def observe_histogram(self, name: str, value: float):
        if name == 'analysis_duration_seconds':
            self.analysis_duration.observe(value)
            
    def set_gauge(self, name: str, value: float):
        if name == 'analysis_queue_size':
            self.queue_size.set(value)
        elif name == 'model_accuracy':
            self.model_accuracy.set(value)