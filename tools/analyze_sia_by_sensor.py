#!/usr/bin/env python3
"""Analizza il CSV raw e raggruppa per sensore leggibile estratto da bracket_content.
Estrae tipo (C=contatto, U=urto, ecc.) e label testuale.
Genera:
 - suggested_sensor_mapping.csv (code, ri, type, label, suggested_debounce_seconds, event_count)
 - sensor_summary.json

Uso:
    python3 tools/analyze_sia_by_sensor.py /path/to/_raw.csv
"""
import csv
import sys
from datetime import datetime
from collections import defaultdict
import statistics
import json
import re


def parse_iso(ts):
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%f")
        except Exception:
            return None


def extract_sensor_info(bracket: str):
    """Estrae tipo e label da una stringa come '#005544|Nri1UX17^C. P.CUCINA     CASA            ^'
    Ritorna (type, label) dove type è 'C' o 'U' o '' e label è pulito.
    """
    if not bracket:
        return ('', '')
    # cerca la porzione tra ^ ... ^
    m = re.search(r"\^(.*?)\^", bracket)
    segment = None
    if m:
        segment = m.group(1)
    else:
        # forse il campo è già senza ^, prova a dividere on pipe
        parts = bracket.split('|')
        segment = parts[-1] if parts else bracket
    if not segment:
        return ('', '')
    seg = segment.strip()
    # tipico: 'C. P.CUCINA     CASA            '
    # prendere prima lettera se è C o U o simile
    sensor_type = ''
    label = seg
    # match pattern: optional letter, dot, space, then label
    m2 = re.match(r"^([A-Za-z0-9])\.\s*(.+)$", seg)
    if m2:
        sensor_type = m2.group(1)
        label = m2.group(2)
    else:
        # match starting letter and not dot
        m3 = re.match(r"^([A-Za-z0-9])\s+(.+)$", seg)
        if m3:
            sensor_type = m3.group(1)
            label = m3.group(2)
        else:
            sensor_type = seg[0] if seg and seg[0].isalpha() else ''
            label = seg[1:].strip() if sensor_type else seg
    # collapse multiple spaces and trim
    label = re.sub(r"\s+", ' ', label).strip()
    return (sensor_type.upper(), label)


def analyze(path, bounce_threshold=2.0):
    events = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = parse_iso(r.get('timestamp',''))
            if ts is None:
                continue
            bracket = r.get('bracket_content','')
            sensor_type, label = extract_sensor_info(bracket)
            events.append({
                'timestamp': ts,
                'account': r.get('account',''),
                'code': r.get('code',''),
                'line': r.get('line',''),
                'receiver': r.get('receiver',''),
                'ri': r.get('ri',''),
                'raw': r.get('raw_message',''),
                'bracket': bracket,
                'sensor_type': sensor_type,
                'label': label,
            })

    events.sort(key=lambda e: e['timestamp'])

    groups = defaultdict(list)
    for ev in events:
        key = (ev['label'], ev['sensor_type'])
        groups[key].append(ev)

    summary = []
    suggested = []

    for key, evs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        label, sensor_type = key
        times = [e['timestamp'] for e in evs]
        deltas = []
        for i in range(1, len(times)):
            delta = (times[i] - times[i-1]).total_seconds()
            deltas.append(delta)
        count = len(evs)
        # burst detection using bounce_threshold
        bursts = []
        cur = [times[0]] if times else []
        for d, t in zip(deltas, times[1:]):
            if d <= bounce_threshold:
                cur.append(t)
            else:
                if cur:
                    bursts.append(cur)
                cur = [t]
        if cur:
            bursts.append(cur)
        burst_counts = [len(b) for b in bursts if len(b) > 1]
        events_in_bursts = sum(bc for bc in burst_counts)
        pct_in_bursts = (events_in_bursts / count * 100.0) if count else 0.0

        median_delta = statistics.median(deltas) if deltas else None
        mean_delta = statistics.mean(deltas) if deltas else None

        if median_delta is not None:
            suggested_debounce = max(0.5, round(median_delta * 1.5, 2))
        else:
            suggested_debounce = 2.0

        summary.append({
            'label': label,
            'sensor_type': sensor_type,
            'count': count,
            'median_delta': median_delta,
            'mean_delta': mean_delta,
            'bursts': len([b for b in bursts if len(b) > 1]),
            'events_in_bursts': events_in_bursts,
            'pct_in_bursts': round(pct_in_bursts,2),
        })

        suggested.append({
            'label': label,
            'sensor_type': sensor_type,
            'suggested_debounce_seconds': suggested_debounce,
            'event_count': count,
        })

    out_map = 'suggested_sensor_mapping.csv'
    with open(out_map, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['label','sensor_type','suggested_debounce_seconds','event_count'])
        for s in sorted(suggested, key=lambda x: (-x['event_count'], x['label'])):
            w.writerow([s['label'], s['sensor_type'], s['suggested_debounce_seconds'], s['event_count']])

    out_summary = 'sensor_summary.json'
    with open(out_summary, 'w', encoding='utf-8') as f:
        json.dump({'total_events': len(events), 'sensors': summary}, f, indent=2, default=str)

    print(f"Analizzati {len(events)} eventi in {len(groups)} sensori distinti")
    top = sorted(summary, key=lambda x: -x['count'])[:30]
    for t in top:
        print(f" - {t['label']} ({t['sensor_type']}): count={t['count']} bursts={t['bursts']} pct_in_bursts={t['pct_in_bursts']}% median_delta={t['median_delta']}")

    print(f"\nSuggerimento mapping scritto in: {out_map}")
    print(f"Summary scritto in: {out_summary}")
    return out_map, out_summary


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: analyze_sia_by_sensor.py path/to/_raw.csv")
        sys.exit(2)
    analyze(sys.argv[1])
