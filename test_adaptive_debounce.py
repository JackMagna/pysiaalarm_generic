import time
from adaptive_debounce import AdaptiveDebounce

def test_adaptive_debounce():
    print("Initializing AdaptiveDebounce with 1.0s window...")
    debouncer = AdaptiveDebounce(initial_window=1.0, safe_gap=0.5)
    
    # Simulation parameters
    burst_duration = 3.0
    event_interval = 0.2
    
    print(f"\n--- Simulating Burst 1 (Duration: {burst_duration}s) ---")
    start_time = 0.0
    current_time = start_time
    
    triggers = 0
    events_sent = 0
    
    # Simulate events for the burst duration
    while current_time <= start_time + burst_duration:
        result = debouncer.process_event(timestamp=current_time)
        status = "TRIGGER" if result else "Ignored"
        print(f"T={current_time:.2f}: {status} (Window: {debouncer.debounce_window:.2f})")
        
        if result:
            triggers += 1
        
        events_sent += 1
        current_time += event_interval

    print(f"Burst 1 Summary: Sent {events_sent} events. Triggers: {triggers}")
    if triggers == 1:
        print("SUCCESS: Burst 1 filtered to single action.")
    else:
        print("FAILURE: Burst 1 resulted in multiple actions.")

    # Simulate a gap (Silence)
    print("\n--- Waiting 10 seconds ---")
    current_time += 10.0
    
    print(f"\n--- Simulating Burst 2 (Duration: {burst_duration}s) ---")
    # This should trigger a new action
    start_time_2 = current_time
    triggers_2 = 0
    
    while current_time <= start_time_2 + burst_duration:
        result = debouncer.process_event(timestamp=current_time)
        status = "TRIGGER" if result else "Ignored"
        print(f"T={current_time:.2f}: {status} (Window: {debouncer.debounce_window:.2f})")
        
        if result:
            triggers_2 += 1
            
        current_time += event_interval

    print(f"Burst 2 Summary: Triggers: {triggers_2}")
    print(f"Final Stats: {debouncer.get_stats()}")

    if triggers_2 == 1:
        print("SUCCESS: Burst 2 filtered to single action.")
    else:
        print("FAILURE: Burst 2 resulted in multiple actions.")

if __name__ == "__main__":
    test_adaptive_debounce()
