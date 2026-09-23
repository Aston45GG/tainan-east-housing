"""Import Tainan East presales from April 2026; keep these separate from sales."""
import io, json, re, zipfile
from datetime import datetime, date
from update import ROOT, BASE, PUBLIC, fetch, parse

CACHE = ROOT / 'cache' / 'presale'

def archive(path, name):
    target = CACHE / (name + '.csv')
    if target.exists(): return target.read_bytes()
    with zipfile.ZipFile(io.BytesIO(fetch(path))) as z:
        names = [n for n in z.namelist() if n.lower().split('/')[-1] == 'd_lvr_land_b.csv']
        if len(names) != 1: raise ValueError('官方下載檔未包含台南市預售屋 CSV')
        blob = z.read(names[0])
    parse(blob, name, 'presale')
    target.write_bytes(blob)
    return blob

def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    history = fetch('DownloadHistory_ajax_list').decode('utf-8')
    releases = sorted(set(re.findall(r"downloadLast\('([0-9]{8})'\)", history)))
    sources = [('115S2', archive('DownloadHistory?type=season&fileName=115S2', '115S2'))]
    for release in releases:
        if release >= '20260401':
            print('Import presale', release, flush=True)
            sources.append((release, archive('DownloadHistory?type=history&fileName='+release, release)))
    known = {s[0] for s in sources}
    for file in sorted(CACHE.glob('20*.csv')):
        if file.stem not in known: sources.append((file.stem, file.read_bytes()))
    today = date.today()
    release = today.replace(day=21 if today.day >= 21 else 11 if today.day >= 11 else 1).strftime('%Y%m%d')
    blob = fetch('Download?fileName=d_lvr_land_b.csv')
    parse(blob, release, 'presale')
    (CACHE/(release+'.csv')).write_bytes(blob)
    sources.append((release, blob))
    records = {}
    for period, blob in sorted(sources, key=lambda s: ('0' if 'S' in s[0] else '1')+s[0]):
        for row in parse(blob, period, 'presale'): records[row['id']] = row
    cancelled = [r for r in records.values() if r['termination']]
    active = [r for r in records.values() if not r['termination']]
    result = dict(updatedAt=datetime.now().astimezone().isoformat(), market='presale', start='2026-04-01', latestRelease=release, source=BASE+'DownloadOpenData', scope='臺南市東區・預售屋買賣', excludedCancellations=len(cancelled), correctionNote='依交易日期統計，與成屋分開計算；排除已下載資料中標示解約的案件。同編號新資料覆蓋舊資料，尚未另接完整解約異動清單，後續解約可能尚未反映。近期月份會隨補登調整。', records=sorted(active, key=lambda r:(r['date'], r['id']), reverse=True))
    for name, content in [('presale-data.json', json.dumps(result, ensure_ascii=False, separators=(',',':'))), ('presale-data.js', 'window.HOUSING_DATA='+json.dumps(result, ensure_ascii=False).replace('<','\\u003c')+';')]:
        tmp = PUBLIC/(name+'.tmp')
        tmp.write_text(content, encoding='utf-8')
        tmp.replace(PUBLIC/name)
    print(json.dumps({'presaleCount':len(active), 'excludedCancellations':len(cancelled)}, ensure_ascii=False))

if __name__ == '__main__': main()
