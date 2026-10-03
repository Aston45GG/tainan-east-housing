"""Refresh Tainan Yongkang sale and presale records from official MOI CSV files."""
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime

from update import BASE, PUBLIC, ROOT, fetch, number, roc

STARTS = {"sale": date(2024, 12, 1), "presale": date(2024, 10, 1)}
CACHE = ROOT / "cache"


def cache_directory(market):
    return CACHE if market == "sale" else CACHE / "presale"


def normalized_address(value):
    value = re.sub(r"[\s　]", "", str(value or ""))
    value = re.sub(r"^(?:臺南市|台南市)?永康區", "", value)
    return value.replace("臺", "台")


def transferred_floor(value):
    return re.split(r"[/／]", str(value or ""), maxsplit=1)[0].replace("，", ",").strip()


def record_key(record):
    market = record.get("market", "sale")
    return (
        record["date"], normalized_address(record["address"]),
        round(number(record["total"]), 2), round(number(record["area"]), 2),
        transferred_floor(record.get("floor", "")), record.get("layout", ""),
        record.get("unitName", "") if market == "presale" else "",
    )


def merge_record(previous, current):
    """Keep current official values while retaining richer community labels."""
    merged = dict(current)
    for field in ("project", "unitName", "note"):
        if not merged.get(field) and previous.get(field):
            merged[field] = previous[field]
    return merged


def parse_yongkang(blob, release, market="sale"):
    reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig")))
    required = {"鄉鎮市區", "交易年月日", "編號", "總價元", "建物移轉總面積平方公尺"}
    if market == "presale":
        required |= {"建案名稱", "棟及號", "解約情形"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("官方 CSV 欄位已變動，保留上次永康資料")
    records = []
    for row in reader:
        if row["鄉鎮市區"] != "永康區":
            continue
        traded = roc(row["交易年月日"])
        if not traded or traded < STARTS[market] or traded > date.today():
            continue
        if "建物" not in row.get("交易標的", ""):
            continue
        area = number(row["建物移轉總面積平方公尺"])
        total = number(row["總價元"])
        if area <= 0 or total <= 0:
            continue
        park_area = number(row.get("車位移轉總面積平方公尺"))
        park_price = number(row.get("車位總價元"))
        has_park = "車位" in row.get("交易筆棟數", "") and "車位0" not in row.get("交易筆棟數", "")
        unit = number(row.get("單價元平方公尺"))
        completed = roc(row.get("建築完成年月", "")) if market == "sale" else None
        age = round((traded - completed).days / 365.2425, 1) if completed and completed <= traded else None
        serial = row["編號"].strip()
        transfer = row.get("移轉編號", "").strip()
        ident = serial + ":" + transfer if serial else hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        rooms = int(number(row.get("建物現況格局-房"))) if number(row.get("建物現況格局-房")) else None
        halls = int(number(row.get("建物現況格局-廳"))) if number(row.get("建物現況格局-廳")) else None
        baths = int(number(row.get("建物現況格局-衛"))) if number(row.get("建物現況格局-衛")) else None
        layout = "" if rooms is None else f"{rooms}房{halls or 0}廳{baths or 0}衛"
        records.append(dict(
            market=market,
            id=ident, date=traded.isoformat(), month=traded.strftime("%Y-%m"),
            address=row.get("土地位置建物門牌", ""), type=row.get("建物型態", "其他"),
            use=row.get("主要用途", ""), floor=row.get("移轉層次", ""), age=age,
            area=round(area / 3.305785, 2), total=round(total / 10000, 2),
            unit=round(unit * 3.305785 / 10000, 2) if unit > 0 else None,
            parkingPrice=round(park_price / 10000, 2), parkingArea=round(park_area / 3.305785, 2),
            parkingUnclear=has_park and not (park_area > 0 and park_price > 0),
            note=row.get("備註", ""), release=release, project=row.get("建案名稱", ""),
            unitName=row.get("棟及號", ""), termination=row.get("解約情形", "").strip(),
            rooms=rooms, halls=halls, baths=baths, layout=layout,
        ))
    return records


def archive(period, market):
    directory = cache_directory(market)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{period}.csv"
    if target.exists():
        return target.read_bytes()
    suffix = "a" if market == "sale" else "b"
    with zipfile.ZipFile(io.BytesIO(fetch("DownloadHistory?type=season&fileName=" + period))) as zipped:
        names = [name for name in zipped.namelist() if name.lower().split("/")[-1] == f"d_lvr_land_{suffix}.csv"]
        if len(names) != 1:
            raise ValueError(f"官方下載檔未包含永康 {market} CSV")
        blob = zipped.read(names[0])
    parse_yongkang(blob, period, market)
    target.write_bytes(blob)
    return blob


def current_blob(release, market):
    directory = cache_directory(market)
    directory.mkdir(parents=True, exist_ok=True)
    suffix = "a" if market == "sale" else "b"
    blob = fetch(f"Download?fileName=d_lvr_land_{suffix}.csv")
    parse_yongkang(blob, release, market)
    (directory / f"{release}.csv").write_bytes(blob)
    return blob


def history_blob(release, market):
    directory = cache_directory(market)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{release}.csv"
    if target.exists():
        return target.read_bytes()
    suffix = "a" if market == "sale" else "b"
    package = fetch("DownloadHistory?type=history&fileName=" + release)
    with zipfile.ZipFile(io.BytesIO(package)) as zipped:
        names = [name for name in zipped.namelist() if name.lower().split("/")[-1] == f"d_lvr_land_{suffix}.csv"]
        if len(names) != 1:
            raise ValueError(f"官方歷次下載檔未包含永康 {market} CSV")
        blob = zipped.read(names[0])
    parse_yongkang(blob, release, market)
    target.write_bytes(blob)
    return blob


def save_market(market, output_name, scope, download_name):
    history = fetch("DownloadHistory_ajax_list").decode("utf-8")
    recent = sorted(set(re.findall(r"downloadLast\('([0-9]{8})'\)", history)))
    # The committed local-folder snapshot preserves 2024–2025 history. Official
    # 2026 seasons and later releases refresh current data without re-downloading
    # large historical packages already represented in that snapshot.
    periods = ["115S1", "115S2"]
    sources = [(period, archive(period, market)) for period in periods]
    directory = cache_directory(market)
    known = {name for name, _ in sources}
    for release in recent:
        if release >= "20260701":
            blob = history_blob(release, market)
            sources.append((release, blob)); known.add(release)
    for path in sorted(directory.glob("20*.csv")):
        if path.stem not in known:
            sources.append((path.stem, path.read_bytes()))
    today = date.today()
    release = today.replace(day=21 if today.day >= 21 else 11 if today.day >= 11 else 1).strftime("%Y%m%d")
    sources.append((release, current_blob(release, market)))
    records = {}
    existing_path = PUBLIC / f"{output_name}.json"
    if existing_path.exists():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        for record in existing.get("records", []):
            record.setdefault("market", market)
            key = record_key(record)
            records[key] = merge_record(records[key], record) if key in records else record
    for source, blob in sorted(sources, key=lambda item: ("0" if "S" in item[0] else "1") + item[0]):
        for record in parse_yongkang(blob, source, market):
            key = record_key(record)
            records[key] = merge_record(records[key], record) if key in records else record
    cancelled = [record for record in records.values() if record["termination"]]
    active = [record for record in records.values() if not record["termination"]]
    result = dict(
        updatedAt=datetime.now().astimezone().isoformat(), market=market,
        start=STARTS[market].isoformat(), latestRelease=release,
        source=BASE + "DownloadOpenData", scope=scope, downloadName=download_name,
        excludedCancellations=len(cancelled),
        correctionNote="同編號新資料覆蓋舊資料；預售屋排除已下載資料中標示解約案件。近期月份會隨補登調整。",
        records=sorted(active, key=lambda row: (row["date"], row["id"]), reverse=True),
    )
    json_text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    for filename, content in [
        (f"{output_name}.json", json_text),
        (f"{output_name}.js", "window.HOUSING_DATA=" + json_text.replace("<", "\\u003c") + ";"),
    ]:
        temp = PUBLIC / (filename + ".tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(PUBLIC / filename)
    return {"market": market, "count": len(active), "excludedCancellations": len(cancelled)}


def main():
    result = [
        save_market("sale", "yongkang-data", "臺南市永康區・成屋買賣", "台南永康區成屋實價登錄.csv"),
        save_market("presale", "yongkang-presale-data", "臺南市永康區・預售屋買賣", "台南永康區預售屋實價登錄.csv"),
    ]
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
