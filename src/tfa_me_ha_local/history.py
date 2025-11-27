"""TFA.me library for Home Assistant: history.py"""

from collections import deque
from datetime import datetime



class SensorHistory:
    """Class to store a history, specially for rain sensor to calculate rain of last hour & last 24 hours)."""

    def __init__(self, max_age_minutes=60) -> None:
        """Initalaize history queue."""
        self.max_age = max_age_minutes * 60
        self.data: deque[tuple[float, int]] = deque()  # Stores (value, timestamp)

    def add_measurement(self, value, ts):
        """Add new value with time stamp."""
        ts_last = 0
        val_last = 0
        length = len(self.data)
        if length != 0:
            entry_last = self.data[-1]
            ts_last = entry_last[1]
            val_last = entry_last[0]
        if (ts_last != ts) & (val_last != value):
            self.data.append((value, ts))
        self.cleanup()

    def cleanup(self):
        """Remove entries older max_age seconds."""
        utc_now = datetime.now()
        utc_now_ts = int(utc_now.timestamp())
        run = 1
        while self.data and (run == 1):
            ts1 = int(self.data[0][1])
            ts2 = utc_now_ts - self.max_age
            if ts1 < ts2:
                self.data.popleft()
            else:
                run = 0

    def get_data(self):
        """Return list with values."""
        return list(self.data)

    def get_oldest_and_newest(self):
        """Return oldest and newest measuerement tuple."""
        if not self.data:
            return None, None  # If list is empty
        return self.data[0], self.data[-1]  # First(oldest) and last(newest) entry

    def clear(self) -> None:
        """Remove all stored history values."""
        self.data.clear()

    def get_rain_amount(self) -> float:
        """Return total rain amount over the stored period.

        The history contains absolute counter values from the station.
        Normally the counter is monotonically increasing. If the counter
        overflows or is reset to zero, this is detected and handled.

        Algorithm:
        - Iterate over all consecutive values.
        - If next >= prev: add (next - prev).
        - If next < prev: counter was reset/overflowed, add 'next'
          (i.e. rain since reset).
        """
        if len(self.data) < 2:
            return 0.0

        total = 0.0
        prev_value = self.data[0][0]

        # iterate over subsequent entries
        for value, _ts in list(self.data)[1:]:
            cur = float(value)
            if cur >= prev_value:
                # normal increase
                total += cur - prev_value
            else:
                # counter reset or overflow -> assume reset to 0
                total += cur
            prev_value = cur

        # Precision 2
        return round(total, 2)   