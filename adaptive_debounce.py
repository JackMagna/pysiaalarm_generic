import time
import statistics

class AdaptiveDebounce:
    """
    A class to handle 'bursts' of identical events and filter them down to a single action,
    adapting the debounce window based on observed burst durations.
    """

    def __init__(self, initial_window: float = 1.0, safe_gap: float = 0.5, adaptation_factor: float = 1.2):
        """
        Initialize the AdaptiveDebounce filter.

        Args:
            initial_window (float): Initial debounce time in seconds. 
                                    Events within this window after a trigger are ignored.
            safe_gap (float): Maximum time (in seconds) between events to consider them part of the same burst 
                              even if the window has expired (Leak detection).
            adaptation_factor (float): Multiplier to apply to observed burst duration when updating the window.
        """
        self.debounce_window = initial_window
        self.safe_gap = safe_gap
        self.adaptation_factor = adaptation_factor
        
        self.last_trigger_time = None
        self.last_event_time = 0.0
        self.burst_history = []
        self.max_history_len = 10

    def process_event(self, timestamp: float = None) -> bool:
        """
        Process a new event.

        Args:
            timestamp (float): The time of the event. Defaults to time.time().

        Returns:
            bool: True if this event should trigger an action (Start of new burst),
                  False if it should be ignored (Part of current burst).
        """
        if timestamp is None:
            timestamp = time.time()

        # Handle the very first event
        if self.last_trigger_time is None:
            self.last_trigger_time = timestamp
            self.last_event_time = timestamp
            return True

        # Time since the last accepted trigger
        dt_trigger = timestamp - self.last_trigger_time
        
        # Time since the very last message received (ignored or not)
        dt_last = timestamp - self.last_event_time

        # 1. Check if we are inside the current debounce window
        if dt_trigger < self.debounce_window:
            # We are still in the known burst window. Ignore.
            self.last_event_time = timestamp
            return False

        # 2. We are outside the window. Check for "Leakage".
        # If this event is very close to the last ignored event, it's likely 
        # a continuation of the burst that exceeded our window.
        if dt_last < self.safe_gap and self.last_event_time != 0:
            # Leak detected! The burst is longer than expected.
            # Extend the window to cover this new duration + margin
            current_burst_duration = timestamp - self.last_trigger_time
            new_suggested_window = current_burst_duration * self.adaptation_factor
            
            # Update window immediately to suppress further leaks in this burst
            self.debounce_window = max(self.debounce_window, new_suggested_window)
            
            # Treat this as part of the burst (Ignore)
            self.last_event_time = timestamp
            return False

        # 3. It's a genuine new event (New Burst)
        # Record stats from the PREVIOUS burst before resetting
        if self.last_trigger_time != 0:
            prev_burst_duration = self.last_event_time - self.last_trigger_time
            # Only record significant bursts (e.g., > 0)
            if prev_burst_duration > 0:
                self._update_history(prev_burst_duration)
                self._recalculate_window()

        # Trigger the new action
        self.last_trigger_time = timestamp
        self.last_event_time = timestamp
        return True

    def _update_history(self, duration: float):
        self.burst_history.append(duration)
        if len(self.burst_history) > self.max_history_len:
            self.burst_history.pop(0)

    def _recalculate_window(self):
        if not self.burst_history:
            return
        
        # Strategy: Use the maximum observed burst duration * factor
        # This is conservative to avoid double-toggles.
        max_burst = max(self.burst_history)
        
        # Optional: You could use mean + 2*std_dev for a statistical approach
        # mean = statistics.mean(self.burst_history)
        # stdev = statistics.stdev(self.burst_history) if len(self.burst_history) > 1 else 0
        # target = mean + 2 * stdev
        
        target = max_burst * self.adaptation_factor
        
        # Ensure we don't shrink the window below the initial setting (or some safe minimum)
        # assuming the user's initial setting implies a physical constraint.
        # However, if bursts are consistently short, we might want to shrink?
        # For safety against "multiple toggles", growing is more important.
        
        self.debounce_window = max(self.debounce_window, target)

    def get_stats(self):
        return {
            "debounce_window": self.debounce_window,
            "history": self.burst_history
        }
