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
    def test_presale_dataset(self):
        p=Path(__file__).parent/'public/presale-data.json'
        d=json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(d['start'],'2026-04-01')
        self.assertEqual(d['market'],'presale')
        self.assertTrue(d['records'])
        self.assertEqual(len(d['records']),len({r['id'] for r in d['records']}))
        for r in d['records']:
            self.assertGreaterEqual(r['date'],'2026-04-01')
            self.assertFalse(r['termination'])
            self.assertIsNone(r['age'])
    def test_presale_boundary(self):
        import csv,io
        fields=['鄉鎮市區','交易年月日','編號','總價元','建物移轉總面積平方公尺','交易標的','建案名稱','棟及號','解約情形']
        f=io.StringIO(); w=csv.DictWriter(f,fields); w.writeheader()
        for day,serial,termination in [('1150331','before',''),('1150401','start',''),('1150402','cancel','已解約')]:
            w.writerow(dict(zip(fields,['東區',day,serial,'10000000','100','房地(土地+建物)','測試建案','A1',termination])))
        rows=parse(f.getvalue().encode('utf-8'),'test','presale')
        self.assertEqual([r['id'] for r in rows],['start:','cancel:'])
        self.assertEqual(rows[1]['termination'],'已解約')

if __name__=='__main__': unittest.main()
