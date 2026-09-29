"""Import Taichung Xitun sale and presale records from official MOI data."""
import csv, hashlib, io, json, re, time, unicodedata, zipfile
from datetime import date, datetime
from pathlib import Path

from update import BASE, PUBLIC, ROOT, fetch, number, roc

SALE_START = date(2025, 11, 1)
PRESALE_START = date(2026, 1, 1)
CACHE = ROOT / 'cache' / 'xitun'

EAST_SEA_NAMES = {
    '中港福家','唐盟森藏','唐盟淳靚','國聚之幸','天空之城','太子雲世紀B區','富宇新杜拜',
    '寶輝世紀莊園/寶輝VILLAGE','惠宇天空之城','攬翠山林','東海浪漫貴族','瑞聯天地T區',
    '瑞聯天地U區','總瑩愛瑪市','聖堡翰霖居','艾菲爾香榭廣場','金璟中港綠洲',
    '寶輝THE TOWER','德鑫協和','麗富HORI',
}
EAST_SEA_ADDRESS_WORDS = ('工業區一路','福科路','福雅路','西屯路三段','國際街','台灣大道四段')
PROJECT_FIXES = {'??HORI':'麗富HORI','勝美?上安':'勝美上安','國雄無?':'國雄無雙'}

def address_key(value):
    value=re.sub(r'\s+','',unicodedata.normalize('NFKC',str(value or '')).replace('臺','台'))
    return re.sub(r'^台中市','',value)

COMMUNITY_FILE = ROOT / 'xitun-community-map.json'
COMMUNITY_BY_ADDRESS = json.loads(COMMUNITY_FILE.read_text(encoding='utf-8')) if COMMUNITY_FILE.exists() else {}
COMMUNITY_ADDRESS_RULES = (
    ('西屯區西屯路三段166之100號','太子雲世紀C區'),
    ('西屯區工業區一路96之12號','總瑩愛瑪市'),
    ('西屯區工業區一路96之22號','總瑩愛瑪市'),
)

def parking_count(value):
    match = re.search(r'車位\s*[:：]?\s*(\d+)', str(value or ''))
    return int(match.group(1)) if match else 0

def room_count(value):
    value=number(value)
    return int(value) if value > 0 else None

def is_east_sea(name, address, market):
    return name in EAST_SEA_NAMES or (market == 'sale' and any(word in address for word in EAST_SEA_ADDRESS_WORDS))

def parse_xitun(blob, release, market):
    reader = csv.DictReader(io.StringIO(blob.decode('utf-8-sig')))
    required = {'鄉鎮市區','交易年月日','編號','總價元','建物移轉總面積平方公尺'}
    if market == 'presale': required |= {'建案名稱','棟及號','解約情形'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('官方台中 CSV 欄位已變動，保留上次資料')
    rows=[]
    start = PRESALE_START if market == 'presale' else SALE_START
    for r in reader:
        if r.get('鄉鎮市區') != '西屯區': continue
        dt=roc(r.get('交易年月日',''))
        if not dt or dt < start or dt > date.today(): continue
        if '建物' not in r.get('交易標的',''): continue
        area=number(r.get('建物移轉總面積平方公尺'))
        total=number(r.get('總價元'))
        if area <= 0 or total <= 0: continue
        use=r.get('主要用途','').strip()
        if use != '住家用': continue
        park_area=number(r.get('車位移轉總面積平方公尺'))
        park_price=number(r.get('車位總價元'))
        parks=parking_count(r.get('交易筆棟數'))
        unit=number(r.get('單價元平方公尺'))
        completed=roc(r.get('建築完成年月','')) if market == 'sale' else None
        age=round((dt-completed).days/365.2425,1) if completed and completed <= dt else None
        raw_project=(r.get('建案名稱','') or '').strip()
        project=PROJECT_FIXES.get(raw_project,raw_project)
        community=(r.get('社區名稱','') or r.get('社區簡稱','') or '').strip()
        name=project if market == 'presale' else community
        address=(r.get('土地位置建物門牌','') or '').strip()
        if market == 'sale' and not community:
            key=address_key(address)
            community=COMMUNITY_BY_ADDRESS.get(key,'')
            if not community:
                community=next((name for prefix,name in COMMUNITY_ADDRESS_RULES if prefix in key),'')
        name=project if market == 'presale' else community
        serial=(r.get('編號','') or '').strip(); transfer=(r.get('移轉編號','') or '').strip()
        ident=serial+':'+transfer if serial else hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        rows.append(dict(
            id=ident,date=dt.isoformat(),month=dt.strftime('%Y-%m'),address=address,
            type=r.get('建物型態','其他'),use=use,floor=r.get('移轉層次',''),age=age,
            area=round(area/3.305785,2),total=round(total/10000,2),
            unit=round(unit*3.305785/10000,2) if unit>0 else None,
            parkingPrice=round(park_price/10000,2),parkingArea=round(park_area/3.305785,2),
            parkingCount=parks,parkingUnclear=parks>0 and not (park_area>0 and park_price>0),
            note=r.get('備註',''),release=release,project=name,
            rooms=room_count(r.get('建物現況格局-房')),layout='{}房{}廳{}衛'.format(
                int(number(r.get('建物現況格局-房'))),int(number(r.get('建物現況格局-廳'))),int(number(r.get('建物現況格局-衛')))),
            unitName=(r.get('棟及號','') or '').strip(),termination=(r.get('解約情形','') or '').strip(),
            marketArea='東海商圈' if is_east_sea(name,address,market) else ''
        ))
    return rows

def archive(period, suffix, market):
    folder=CACHE/market; folder.mkdir(parents=True,exist_ok=True)
    target=folder/(period+'.csv')
    if target.exists(): return target.read_bytes()
    with zipfile.ZipFile(io.BytesIO(fetch('DownloadHistory?type=season&fileName='+period))) as z:
        wanted='b_lvr_land_'+suffix+'.csv'
        names=[n for n in z.namelist() if n.lower().split('/')[-1] == wanted]
        if len(names)!=1: raise ValueError('官方下載檔未包含台中市 '+market+' CSV')
        blob=z.read(names[0])
    parse_xitun(blob,period,market); target.write_bytes(blob)
    return blob

def recent_archive(release, suffix, market):
    folder=CACHE/market; folder.mkdir(parents=True,exist_ok=True)
    target=folder/(release+'.csv')
    if target.exists(): return target.read_bytes()
    with zipfile.ZipFile(io.BytesIO(fetch('DownloadHistory?type=history&fileName='+release))) as z:
        wanted='b_lvr_land_'+suffix+'.csv'
        names=[n for n in z.namelist() if n.lower().split('/')[-1] == wanted]
        if len(names)!=1: raise ValueError('官方逐期檔未包含台中市 '+market+' CSV')
        blob=z.read(names[0])
    parse_xitun(blob,release,market); target.write_bytes(blob)
    return blob

def write_market(market, releases):
    suffix='b' if market=='presale' else 'a'
    periods=('114S4','115S1','115S2') if market=='sale' else ('115S1','115S2')
    sources=[(p,archive(p,suffix,market)) for p in periods]
    for release in releases:
        if release >= ('20260101' if market=='presale' else '20251101'):
            sources.append((release,recent_archive(release,suffix,market)))
    folder=CACHE/market
    known={x[0] for x in sources}
    for file in sorted(folder.glob('20*.csv')):
        if file.stem not in known: sources.append((file.stem,file.read_bytes()))
    today=date.today(); day=21 if today.day>=21 else 11 if today.day>=11 else 1
    release=today.replace(day=day).strftime('%Y%m%d')
    blob=fetch('Download?fileName=b_lvr_land_'+suffix+'.csv')
    parse_xitun(blob,release,market); (folder/(release+'.csv')).write_bytes(blob); sources.append((release,blob))
    records={}
    for period,source in sorted(sources,key=lambda x:('0' if 'S' in x[0] else '1')+x[0]):
        for row in parse_xitun(source,period,market): records[row['id']]=row
    cancelled=sum(bool(r['termination']) for r in records.values())
    rows=[r for r in records.values() if not r['termination']]
    rows.sort(key=lambda r:(r['date'],r['id']),reverse=True)
    start=PRESALE_START if market=='presale' else SALE_START
    label='預售屋' if market=='presale' else '成屋'
    result=dict(updatedAt=datetime.now().astimezone().isoformat(),market=market,start=start.isoformat(),
        latestRelease=release,source=BASE+'DownloadOpenData',scope='臺中市西屯區・'+label+'買賣',
        excludedCancellations=cancelled,downloadName='台中西屯區'+label+'實價登錄.csv',
        correctionNote='同編號新資料覆蓋舊資料；近期月份會隨補登調整。東海商圈依已確認社區／建案名稱及鄰近道路標註。',records=rows)
    stem='xitun-presale-data' if market=='presale' else 'xitun-data'
    variable='XITUN_PRESALE_DATA' if market=='presale' else 'XITUN_SALE_DATA'
    content=json.dumps(result,ensure_ascii=False,separators=(',',':'))
    for name,text in [(stem+'.json',content),(stem+'.js','window.'+variable+'=window.HOUSING_DATA='+content.replace('<','\\u003c')+';')]:
        tmp=PUBLIC/(name+'.tmp'); tmp.write_text(text,encoding='utf-8'); tmp.replace(PUBLIC/name)
    print(json.dumps({'market':market,'count':len(rows),'eastSea':sum(r['marketArea']=='東海商圈' for r in rows)},ensure_ascii=False))

def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    history=fetch('DownloadHistory_ajax_list').decode('utf-8')
    releases=sorted(set(re.findall(r"downloadLast\('([0-9]{8})'\)",history)))
    write_market('sale',releases)
    write_market('presale',releases)

if __name__=='__main__': main()
