#!/usr/bin/env python3
"""Analizza un file CSV raw esportato dall'integrazione pysiaalarm.
Produce:
- statistica per codice/ri
- analisi dei bounce (ripetizioni entro soglia)
- file suggerito di mapping con debounce consigliato

Uso:
    python tools/analyze_sia_raw.py /path/to/pysiaalarm_codes_..._raw.csv

"""
import csv
import sys
from datetime import datetime
from collections import defaultdict
import statistics
import json


def parse_iso(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        # rimuovi eventuale microsecondi malformati
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
        except Exception:
            return None


def analyze(path, bounce_threshold=2.0):
    events = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = parse_iso(r.get('timestamp',''))
            if ts is None:
                continue
            events.append({
                'timestamp': ts,
                'account': r.get('account',''),
                'code': r.get('code',''),
                'line': r.get('line',''),
                'receiver': r.get('receiver',''),
                'ri': r.get('ri',''),
                'raw': r.get('raw_message',''),
                'bracket': r.get('bracket_content','')
            })

    events.sort(key=lambda e: e['timestamp'])

    # aggregate by (code, ri)
    groups = defaultdict(list)
    for ev in events:
        key = (ev['code'], ev['ri'])
        groups[key].append(ev)

    summary = []
    suggested = []

    for key, evs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        code, ri = key
        times = [e['timestamp'] for e in evs]
        deltas = []
        for i in range(1, len(times)):
            delta = (times[i] - times[i-1]).total_seconds()
            deltas.append(delta)
        count = len(evs)
        unique_brackets = set(e['bracket'] for e in evs if e['bracket'])
        # bounce detection: sequences of consecutive events separated by <= bounce_threshold
        bursts = []
        cur_burst = [times[0]] if times else []
        for d, t in zip(deltas, times[1:]):
            if d <= bounce_threshold:
                cur_burst.append(t)
            else:
                if cur_burst:
                    bursts.append(cur_burst)
                cur_burst = [t]
        if cur_burst:
            bursts.append(cur_burst)
        burst_counts = [len(b) for b in bursts if len(b) > 1]
        events_in_bursts = sum(bc for bc in burst_counts)
        pct_in_bursts = (events_in_bursts / count * 100.0) if count else 0.0

        median_delta = statistics.median(deltas) if deltas else None
        mean_delta = statistics.mean(deltas) if deltas else None

        # suggest debounce: if many bursts -> set debounce to max(1.0, median_delta*1.5)
        if median_delta is not None:
            suggested_debounce = max(1.0, round(median_delta * 1.5, 2))
        else:
            suggested_debounce = 2.0

        # cap suggested debounce to reasonable bounds
        if suggested_debounce < 0.5:
            suggested_debounce = 0.5
        if suggested_debounce > 3600:
            suggested_debounce = 3600

        summary.append({
            'code': code,
            'ri': ri,
            'count': count,
            'unique_bracket_samples': len(unique_brackets),
            'median_delta': median_delta,
            'mean_delta': mean_delta,
            'bursts': len([b for b in bursts if len(b) > 1]),
            'events_in_bursts': events_in_bursts,
            'pct_in_bursts': round(pct_in_bursts,2),
            'sample_bracket': next(iter(unique_brackets)) if unique_brackets else '',
        })

        suggested.append({
            'code': code,
            'ri': ri,
            'suggested_debounce_seconds': suggested_debounce,
            'event_count': count,
            'sample_bracket': next(iter(unique_brackets)) if unique_brackets else ''
        })

    # write suggested mapping CSV
    out_map = 'suggested_mapping.csv'
    with open(out_map, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['code','ri','suggested_debounce_seconds','event_count','sample_bracket','friendly_name'])
        for s in sorted(suggested, key=lambda x: (-x['event_count'], x['code'])):
            w.writerow([s['code'], s['ri'], s['suggested_debounce_seconds'], s['event_count'], s['sample_bracket'], ''])

    # write summary JSON
    out_summary = 'analysis_summary.json'
    with open(out_summary, 'w', encoding='utf-8') as f:
        json.dump({'total_events': len(events), 'groups': summary}, f, indent=2, default=str)

    # print quick stats
    print(f"Analizzati {len(events)} eventi in {len(groups)} gruppi (code,ri)")
    top = sorted(summary, key=lambda x: -x['count'])[:20]
    print("Top gruppi:")
    for t in top:
        print(f" - code={t['code']} ri={t['ri']} count={t['count']} bursts={t['bursts']} pct_in_bursts={t['pct_in_bursts']}% median_delta={t['median_delta']}")

    print(f"\nSuggerimento mapping scritto in: {out_map}")
    print(f"Summary JSON scritto in: {out_summary}")

    return out_map, out_summary


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: analyze_sia_raw.py path/to/_raw.csv")
        sys.exit(2)
    path = sys.argv[1]
    analyze(path)
