"""Official MOI sale data importer; Python standard library only."""
import csv, io, json, re, sys, time, zipfile, hashlib
from pathlib import Path
from datetime import datetime, date
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
BASE = 'https://plvr.land.moi.gov.tw/'
START = date(2026, 6, 1)
CACHE = ROOT / 'cache'
PUBLIC = ROOT / 'public'

def fetch(path):
    for attempt in range(3):
        try:
            with urlopen(Request(BASE + path, headers={'User-Agent': 'TainanEastHousing/1.0'}), timeout=90) as r:
                return r.read()
        except Exception:
            if attempt == 2: raise
            time.sleep(2 ** attempt)

def roc(value):
    value = str(value).strip()
    if not value.isdigit() or len(value) not in (5, 7): return None
    try: return date(int(value[:3]) + 1911, int(value[3:5]), int(value[5:7]) if len(value) == 7 else 1)
    except ValueError: return None

def number(value):
    try: return float(value or 0)
    except (ValueError, TypeError): return 0

def parse(blob, release):
    reader = csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
    required = {'鄉鎮市區', '交易年月日', '編號', '總價元', '建物移轉總面積平方公尺'}
    if not required.issubset(reader.fieldnames or []): raise ValueError('官方 CSV 欄位已變動，保留上次資料')
    rows = []
    for r in reader:
        if r['鄉鎮市區'] != '東區': continue
        dt = roc(r['交易年月日'])
        if not dt or dt < START or dt > date.today(): continue
        if '建物' not in r.get('交易標的', ''): continue
        area = number(r['建物移轉總面積平方公尺'])
        total = number(r['總價元'])
        if area <= 0 or total <= 0: continue
        park_area = number(r.get('車位移轉總面積平方公尺'))
        park_price = number(r.get('車位總價元'))
        has_park = '車位0' not in r.get('交易筆棟數', '') and ('車位' in r.get('交易筆棟數', ''))
        unit = number(r.get('單價元平方公尺'))
        # Official unit price is retained; do not guess parking allocation.
        completed = roc(r.get('建築完成年月', ''))
        age = round((dt - completed).days / 365.2425, 1) if completed and completed <= dt else None
        serial = r['編號'].strip()
        transfer = r.get('移轉編號', '').strip()
        ident = serial + ':' + transfer if serial else hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
        rows.append(dict(id=ident, date=dt.isoformat(), month=dt.strftime('%Y-%m'), address=r.get('土地位置建物門牌',''), type=r.get('建物型態','其他'), use=r.get('主要用途',''), floor=r.get('移轉層次',''), age=age, area=round(area/3.305785,2), total=round(total/10000,2), unit=round(unit*3.305785/10000,2) if unit>0 else None, parkingPrice=round(park_price/10000,2), parkingArea=round(park_area/3.305785,2), parkingUnclear=has_park and not (park_area>0 and park_price>0), note=r.get('備註',''), release=release))
    return rows

def archive(path, name):
    target = CACHE / (name + '.csv')
    if target.exists(): return target.read_bytes()
    blob = fetch(path)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().split('/')[-1] == 'd_lvr_land_a.csv']
        if len(names) != 1: raise ValueError('下載檔未包含台南市買賣 CSV')
        result = z.read(names[0])
    parse(result, name)
    target.write_bytes(result)
    return result

def main():
    CACHE.mkdir(exist_ok=True); PUBLIC.mkdir(exist_ok=True)
    history = fetch('DownloadHistory_ajax_list').decode('utf-8')
    releases = sorted(set(re.findall(r"downloadLast\('([0-9]{8})'\)", history)))
    # 115S2 includes registrations through June 10, including early June trades.
    sources = [('115S2', archive('DownloadHistory?type=season&fileName=115S2','115S2'))]
    for release in releases:
        if release >= '20260601':
            print('Import',release,flush=True)
            sources.append((release, archive('DownloadHistory?type=history&fileName='+release,release)))
    # Retain previously downloaded periods when they leave the official recent list.
    known = {s[0] for s in sources}
    for file in sorted(CACHE.glob('20*.csv')):
        if file.stem not in known: sources.append((file.stem,file.read_bytes()))
    today = date.today()
    day = 21 if today.day >= 21 else 11 if today.day >= 11 else 1
    current_release = today.replace(day=day).strftime('%Y%m%d')
    current = fetch('Download?fileName=d_lvr_land_a.csv')
    parse(current,current_release)
    (CACHE / (current_release+'.csv')).write_bytes(current)
    sources.append((current_release,current))
    records = {}
    for release,blob in sorted(sources,key=lambda s:('0' if 'S' in s[0] else '1')+s[0]):
        for row in parse(blob,release): records[row['id']] = row
    result = dict(updatedAt=datetime.now().astimezone().isoformat(), start='2026-06-01', latestRelease=current_release, source=BASE+'DownloadOpenData', scope='臺南市東區・成屋買賣', correctionNote='同編號新資料覆蓋舊資料；官方撤銷案件尚未自動核對。近期月份會隨補登調整。', records=sorted(records.values(), key=lambda r:(r['date'],r['id']),reverse=True))
    temp = PUBLIC/'data.json.tmp'
    temp.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    temp.replace(PUBLIC/'data.json')
    # A JS data bundle also permits double-clicking the site without a server.
    js = PUBLIC/'data.js.tmp'
    js.write_text('window.HOUSING_DATA='+json.dumps(result,ensure_ascii=False).replace('<','\\u003c')+';',encoding='utf-8')
    js.replace(PUBLIC/'data.js')
    print(json.dumps({'count':len(records),'latestRelease':current_release},ensure_ascii=False))

if __name__ == '__main__': main()
