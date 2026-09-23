import json, unittest
from pathlib import Path
from datetime import date
from update import roc, parse

class DataChecks(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(roc('1150601'),date(2026,6,1))
        self.assertIsNone(roc('1150230'))
        self.assertIsNone(roc(''))
    def test_real_dataset(self):
        d=json.loads((Path(__file__).parent/'public/data.json').read_text(encoding='utf-8'))
        rows=d['records']
        self.assertTrue(rows)
        self.assertEqual(len(rows),len({r['id'] for r in rows}))
        for r in rows:
            self.assertGreaterEqual(r['date'],'2026-06-01')
            self.assertLessEqual(r['date'],date.today().isoformat())
            self.assertIn('東區',r['address'])
            self.assertGreater(r['area'],0)
            self.assertGreater(r['total'],0)
            self.assertEqual(r['month'],r['date'][:7])
    def test_schema_guard(self):
        with self.assertRaises(ValueError): parse(b'<html>error</html>','test')

if __name__=='__main__': unittest.main()
