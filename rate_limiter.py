"""Rate limiter for managing API quota constraints when using Google's Gemini API.

Tracks and enforces limits on:
- Requests per minute
- Input tokens per minute 
- Requests per day

Uses a sliding window algorithm for per-minute limits and daily counter reset.
"""
from datetime import date
from time import sleep, time


class GeminiRateLimiter:
    """Manages rate limiting for Gemini API to stay within quota constraints.
    
    Implements three types of limits:
    - Per-minute request limit (sliding window)
    - Per-minute token consumption limit (sliding window)
    - Per-day request limit (resets at midnight)
    
    The class blocks execution via wait_for_quota() until constraints are satisfied,
    using sleep() to avoid exceeding any limit.
    """
    
    # Sliding window duration in seconds for per-minute rate limits
    WINDOW_SECONDS = 60

    def __init__(
        self,
        requests_per_minute=5,
        input_tokens_per_minute=250000,
        requests_per_day=20,
    ):
        """Initialize the rate limiter with quota thresholds.
        
        Args:
            requests_per_minute (int): Max API calls allowed per minute
            input_tokens_per_minute (int): Max input tokens allowed per minute
            requests_per_day (int): Max API calls allowed per calendar day
        """
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

    # Reset the daily counter when the calendar day changes.
    def _rollover_day(self):
        """Reset daily request counter when calendar day changes.
        
        Automatically called by wait_for_quota() before checking limits.
        """
        today = date.today()
        if today != self._current_day:
            self._current_day = today
            self._requests_today = 0

    # Drop request and token events that are older than the current window.
    def _remove_old_entries(self, now):
        """Remove outdated request and token entries outside the current window.
        
        Maintains sliding window by removing entries older than WINDOW_SECONDS.
        Called frequently to keep counters accurate without processing old data.
        
        Args:
            now (float): Current time from time.time()
        """
        while self._request_times and (now - self._request_times[0]) > self.WINDOW_SECONDS:
            self._request_times.pop(0)

        while self._token_events and (now - self._token_events[0][0]) > self.WINDOW_SECONDS:
            self._token_events.pop(0)

    # Compute wait time until one more request is allowed.
    def _seconds_until_request_available(self, now):
        """Calculate seconds to wait before another request is allowed.
        
        Checks if current request count is at the per-minute limit and
        calculates how long to wait until the oldest request falls out
        of the sliding window.
        
        Args:
            now (float): Current time from time.time()
        
        Returns:
            float: Seconds to wait (0.0 if request allowed immediately)
        """
        if len(self._request_times) < self.requests_per_minute:
            return 0.0

        oldest = self._request_times[0]
        return max(0.0, oldest + self.WINDOW_SECONDS - now)

    # Compute wait time until enough token budget is available.
    def _seconds_until_tokens_available(self, now, input_tokens):
        """Calculate seconds to wait for sufficient token budget.
        
        Sums token consumption in the current window and determines
        how many tokens must be freed by waiting for entries to exit
        the sliding window.
        
        Args:
            now (float): Current time from time.time()
            input_tokens (int): Number of tokens the next request needs
        
        Returns:
            float: Seconds to wait (0.0 if tokens available immediately)
        """
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

    # Block execution until request and token quotas are available.
    def wait_for_quota(self, input_tokens):
        """Block until all rate limit quotas are satisfied.
        
        Checks per-minute request limit, per-minute token limit, and
        per-day request limit. Sleeps as needed to wait for quota availability.
        Should be called before each API request.
        
        Args:
            input_tokens (int): Number of tokens the planned request will use
        
        Raises:
            SystemExit: If daily request limit has been reached
        """
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

    # Store one completed request and its consumed input tokens.
    def record_request(self, input_tokens):
        """Record a completed API request for quota tracking.
        
        Adds the request timestamp and token count to the sliding window
        and increments the daily request counter. Should be called after
        each successful API call.
        
        Args:
            input_tokens (int): Number of input tokens consumed by the request
        """
        now = time()
        self._remove_old_entries(now)
        self._request_times.append(now)
        self._token_events.append((now, input_tokens))
        self._requests_today += 1
