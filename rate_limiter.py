"""Rate limiter for Gemini API quotas (requests/min, tokens/min, requests/day)."""
from datetime import date
from time import sleep, time

class GeminiRateLimiter:
    """Enforce Gemini API quotas using sliding windows and a daily counter."""

    # Sliding window duration in seconds for per-minute rate limits
    WINDOW_SECONDS = 60

    def __init__(
        self,
        requests_per_minute=5,
        input_tokens_per_minute=250000,
        requests_per_day=20,
    ):
        """Initialize the rate limiter with quota thresholds."""
        self.requests_per_minute = requests_per_minute
        self.input_tokens_per_minute = input_tokens_per_minute
        self.requests_per_day = requests_per_day
        # List of timestamps of recent requests for sliding window calculation
        self._request_times = []
        # List of (timestamp, token_count) tuples for token tracking in sliding window
        self._token_events = []
        # Counter for requests made so far today
        self._requests_today = 0
        # Current calendar date for daily limit rollover
        self._current_day = date.today()

    def _rollover_day(self):
        """Reset the daily counter if the calendar day has changed."""
        today = date.today()
        if today != self._current_day:
            self._current_day = today
            self._requests_today = 0

    def _remove_old_entries(self, now):
        """Remove request and token events outside the sliding window."""
        while self._request_times and (now - self._request_times[0]) > self.WINDOW_SECONDS:
            self._request_times.pop(0)

        while self._token_events and (now - self._token_events[0][0]) > self.WINDOW_SECONDS:
            self._token_events.pop(0)

    def _seconds_until_request_available(self, now):
        """Return seconds until another request is allowed."""
        if len(self._request_times) < self.requests_per_minute:
            return 0.0

        oldest = self._request_times[0]
        return max(0.0, oldest + self.WINDOW_SECONDS - now)

    def _seconds_until_tokens_available(self, now, input_tokens):
        """Return seconds until enough token budget is available."""
        current_tokens = sum(tokens for _, tokens in self._token_events)
        if current_tokens + input_tokens <= self.input_tokens_per_minute:
            return 0.0

        tokens_needed = current_tokens + input_tokens - self.input_tokens_per_minute
        running = 0
        for timestamp, tokens in self._token_events:
            running += tokens
            if running >= tokens_needed:
                return max(0.0, timestamp + self.WINDOW_SECONDS - now)

        oldest = self._token_events[0][0] if self._token_events else now
        return max(0.0, oldest + self.WINDOW_SECONDS - now)

    def wait_for_quota(self, input_tokens):
        """Block execution until per-minute and daily quotas allow the request."""
        self._rollover_day()
        if self._requests_today >= self.requests_per_day:
            raise SystemExit("Daily request limit reached.")

        while True:
            now = time()
            self._remove_old_entries(now)

            wait_for_request = self._seconds_until_request_available(now)
            wait_for_tokens = self._seconds_until_tokens_available(now, input_tokens)
            wait_seconds = max(wait_for_request, wait_for_tokens)

            if wait_seconds <= 0:
                return

            print(
                f"Limite de cuota. Esperando {wait_seconds:.2f}s "
                f"(req/min={self.requests_per_minute}, tokens/min={self.input_tokens_per_minute})."
            )
            sleep(wait_seconds)

    def record_request(self, input_tokens):
        """Record a completed request for quota tracking."""
        now = time()
        self._remove_old_entries(now)
        self._request_times.append(now)
        self._token_events.append((now, input_tokens))
        self._requests_today += 1
