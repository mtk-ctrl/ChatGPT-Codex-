from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from forecast import predict, update_history, scores, completed_times
import importlib.util
SPEC = importlib.util.spec_from_file_location('forecast_site', Path(__file__).resolve().parents[1] / 'scripts/site.py')
site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site)

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def records():
    last = NOW - timedelta(hours=18)
    moments = [last]
    for gap in reversed([12, 24, 36, 48, 60, 72, 84]):
        moments.append(moments[-1] - timedelta(hours=gap))
    return [dict(id=str(i), reference_at=t.isoformat(), kind='global', state='reported') for i, t in enumerate(reversed(moments))]


class ForecastTests(unittest.TestCase):
    def test_conditional_interval_ratio_and_reference_date(self):
        result = predict(records(), NOW)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['sample_size'], 7)
        self.assertEqual(result['eligible_size'], 6)
        self.assertEqual(result['horizons']['24']['count'], 2)
        self.assertEqual(result['horizons']['48']['count'], 4)
        self.assertAlmostEqual(result['horizons']['24']['probability'], 3/8)
        self.assertEqual(result['horizons']['24']['display_percent'], 40)
        self.assertEqual(result['reference_date'], '2026-10-21')

    def test_future_vouchers_announcements_and_duplicates_are_excluded(self):
        rows = records()
        rows += [dict(rows[-1]), dict(rows[-1], id='another-id'),
                 dict(rows[-1], id='voucher', kind='banked', reference_at=NOW.isoformat()),
                 dict(rows[-1], id='announcement', state='announced', reference_at=NOW.isoformat()),
                 dict(rows[-1], id='future', reference_at=(NOW + timedelta(hours=1)).isoformat())]
        self.assertEqual(len(completed_times(rows, NOW)), 8)
        self.assertEqual(predict(rows, NOW), predict(records(), NOW))

    def test_sparse_and_stale_data_do_not_produce_probabilities(self):
        self.assertEqual(predict(records()[-4:], NOW)['status'], 'insufficient')
        result = predict(records(), NOW, fresh=False)
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(result['horizons'], {})
        self.assertNotIn('reference_date', result)
        self.assertEqual(predict(records(), NOW + timedelta(days=20))['status'], 'insufficient')

    def test_saved_forecast_is_immutable_and_not_judged_early(self):
        rows = records()
        forecast = predict(rows, NOW)
        history = update_history([], forecast, rows, NOW, NOW.isoformat())
        again = predict(rows, NOW + timedelta(hours=1))
        retained = update_history(history, again, rows, NOW + timedelta(hours=1), NOW.isoformat())
        self.assertEqual(history, retained)
        self.assertEqual(history[0]['outcomes'], {})
        later = NOW + timedelta(hours=25)
        result = update_history(history, {'status':'insufficient'}, rows, later, NOW.isoformat())
        self.assertEqual(result[0]['outcomes'], {})
        event = dict(rows[-1], id='new', reference_at=(NOW+timedelta(hours=10)).isoformat())
        result = update_history(history, {'status':'insufficient'}, rows+[event], later, later.isoformat())
        self.assertTrue(result[0]['outcomes']['24'])
        self.assertNotIn('48', result[0]['outcomes'])
        self.assertEqual(history[0]['outcomes'], {})
        self.assertEqual(result[0]['probabilities'], history[0]['probabilities'])

    def test_scoring_uses_only_matured_forecasts(self):
        h = [{'probabilities':{'24':0.25,'48':0.5},'outcomes':{'24':True}},
             {'probabilities':{'24':0.5,'48':0.6},'outcomes':{}},
             {'probabilities':{'24':0.75,'48':0.8},'outcomes':{'24':False}}]
        self.assertEqual(scores(h)['24'], {'judged':2, 'brier':0.562})
        self.assertEqual(scores(h)['48'], {'judged':0, 'brier':None})

    def test_calendar_json_cannot_end_script_and_jst_dates_match(self):
        normalized, _ = site.normalize_feed({'events':[{'id':'2111492738025959922','type':'reset','confirmed':True,
            'announced_at':'2026-10-17T20:41:01Z','url':'https://x.com/thsottiaux/status/2111492738025959922'}]},
            now=NOW, editorial={'2111492738025959922':'</script><img src=x onerror=alert(1)>'})
        rendered = site.calendar_overview(normalized, predict(normalized, NOW))
        payload = rendered.split('<script id="calendar-data" type="application/json">')[1].split('</script>')[0]
        self.assertNotIn('<', payload)
        self.assertEqual(json.loads(payload)['records'][0]['day'], '2026-10-18')
        self.assertIn('2026-10-18', rendered)


if __name__ == '__main__':
    unittest.main()
