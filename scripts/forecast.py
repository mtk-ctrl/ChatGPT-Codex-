"""Local interval model using stored OpenAI primary-source records."""
from datetime import datetime, timedelta, timezone
import math
from statistics import median

MODEL = 'interval-90d-reset-announcements-v2'
WINDOW_DAYS = 90
JST = timezone(timedelta(hours=9))


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone is required')
    return parsed.astimezone(timezone.utc)


def iso(value):
    return value.isoformat(timespec='seconds').replace('+00:00', 'Z')


def completed_times(records, now):
    times, ids = set(), set()
    for row in sorted(records, key=lambda r: r.get('reference_at', '')):
        if (row.get('kind') != 'global' or row.get('state') not in {'announced', 'reported', 'observed'}
                or row.get('date_precision') == 'day' or row.get('evidence') not in {'official', 'staff_x'}
                or row.get('id') in ids):
            continue
        try:
            moment = timestamp(row['reference_at'])
        except (KeyError, ValueError, TypeError):
            continue
        if moment <= now:
            times.add(moment)
            ids.add(row.get('id'))
    grouped = []
    for moment in sorted(times):
        if not grouped or moment - grouped[-1] >= timedelta(hours=6):
            grouped.append(moment)
    return grouped


def wilson(successes, total):
    """95% Wilson interval for the observed ratio, not a guarantee for future events."""
    if total == 0:
        return [0, 100]
    z = 1.959963984540054
    p = successes / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total)) / den
    spread = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return [max(0, math.floor(100*(center-spread))), min(100, math.ceil(100*(center+spread)))]


def predict(records, now, fresh=True):
    times = completed_times(records, now)
    result = {'model': MODEL, 'generated_at': iso(now), 'window_days': WINDOW_DAYS,
              'status': 'insufficient', 'sample_size': 0, 'eligible_size': 0,
              'all_completed': len(times), 'horizons': {}}
    if not times:
        return result
    last = times[-1]
    elapsed = (now-last).total_seconds()/3600
    cutoff = now-timedelta(days=WINDOW_DAYS)
    gaps = [(b-a).total_seconds()/3600 for a,b in zip(times,times[1:]) if a >= cutoff]
    eligible = [gap for gap in gaps if gap > elapsed]
    result.update(last_reset_at=iso(last), elapsed_hours=round(elapsed,2),
                  sample_size=len(gaps), eligible_size=len(eligible))
    if gaps:
        result.update(median_hours=round(median(gaps),2), min_hours=round(min(gaps),2), max_hours=round(max(gaps),2))
    if not fresh:
        result['status'] = 'stale'
        return result
    if len(gaps) < 6 or len(eligible) < 5:
        return result
    result['status'] = 'ok'
    for hours in [24,48]:
        count = sum(gap <= elapsed+hours for gap in eligible)
        probability = (count+1)/(len(eligible)+2)
        result['horizons'][str(hours)] = {'count':count, 'total':len(eligible),
            'probability':probability, 'display_percent':int(math.floor(probability*20+0.5))*5,
            'observed_ratio_interval':wilson(count,len(eligible)), 'until':iso(now+timedelta(hours=hours))}
    result['reference_date'] = (last+timedelta(hours=median(eligible))).astimezone(JST).strftime('%Y-%m-%d')
    return result


def update_history(history, prediction, records, now, last_success):
    """Save the first forecast each JST day; judge only after each horizon has ended."""
    entries = [dict(entry, outcomes=dict(entry.get('outcomes',{}))) for entry in history]
    day = now.astimezone(JST).strftime('%Y-%m-%d')
    if prediction['status'] == 'ok' and not any(entry['day'] == day for entry in entries):
        entries.append({'day':day, 'model':prediction['model'], 'issued_at':prediction['generated_at'],
                        'probabilities':{h:v['probability'] for h,v in prediction['horizons'].items()},
                        'until':{h:v['until'] for h,v in prediction['horizons'].items()}, 'outcomes':{}})
    times = completed_times(records, now)
    coverage = timestamp(last_success) if last_success else None
    for entry in entries:
        origin = timestamp(entry['issued_at'])
        for horizon, deadline in entry['until'].items():
            end = timestamp(deadline)
            if now < end or coverage is None or coverage < end:
                continue
            entry['outcomes'][horizon] = any(origin < event <= end for event in times)
    return sorted(entries,key=lambda entry:entry['issued_at'])


def scores(history):
    result = {}
    for horizon in ['24','48']:
        errors = [(entry['probabilities'][horizon]-int(entry['outcomes'][horizon]))**2
                  for entry in history if horizon in entry.get('outcomes',{})]
        result[horizon] = {'judged':len(errors),'brier':round(sum(errors)/len(errors),3) if errors else None}
    return result
