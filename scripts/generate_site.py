import html
import json
import re
import unicodedata
import zlib
from pathlib import Path

PDF_PATH = Path("桃園市政府員工卡特約商店名單及優惠措施一覽表(1217更新).pdf")
DATA_DIR = Path("data")
DOCS_DIR = Path("docs")


def extract_cmap(raw_pdf: bytes) -> dict[int, str]:
    stream_pattern = re.compile(rb"stream\r?\n(.*?)endstream", re.S)
    cmap: dict[int, str] = {}

    for match in stream_pattern.finditer(raw_pdf):
        stream = match.group(1)
        try:
            decompressed = zlib.decompress(stream)
        except Exception:
            continue

        if b"beginbfchar" not in decompressed and b"beginbfrange" not in decompressed:
            continue

        lines = decompressed.decode("latin-1").split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.endswith("beginbfchar"):
                count = int(line.split()[0])
                for offset in range(1, count + 1):
                    parts = lines[i + offset].strip().split()
                    if len(parts) < 2:
                        continue
                    source = int(parts[0][1:-1], 16)
                    dest = parts[1][1:-1]
                    text = "".join(chr(int(dest[j : j + 4], 16)) for j in range(0, len(dest), 4))
                    cmap[source] = text
                i += count + 1
                continue

            if line.endswith("beginbfrange"):
                count = int(line.split()[0])
                for offset in range(1, count + 1):
                    parts = lines[i + offset].strip().split()
                    if len(parts) < 3:
                        continue
                    start = int(parts[0][1:-1], 16)
                    end = int(parts[1][1:-1], 16)
                    mapping = parts[2]
                    if mapping.startswith("<") and mapping.endswith(">"):
                        base = int(mapping[1:-1], 16)
                        for code, value in enumerate(range(start, end + 1)):
                            cmap[value] = chr(base + code)
                    elif mapping.startswith("["):
                        inside = " ".join(parts[2:])[1:-1]
                        hex_values = re.findall(r"<([0-9A-F]+)>", inside)
                        for code, hex_value in enumerate(hex_values, start=start):
                            text = "".join(
                                chr(int(hex_value[j : j + 4], 16)) for j in range(0, len(hex_value), 4)
                            )
                            cmap[code] = text
                i += count + 1
                continue

            i += 1

    return cmap


def decode_hex_string(hex_string: str, cmap: dict[int, str]) -> str:
    chars: list[str] = []
    for i in range(0, len(hex_string), 4):
        chars.append(cmap.get(int(hex_string[i : i + 4], 16), ""))
    return "".join(chars)


def decode_token(token: bytes, cmap: dict[int, str]) -> str:
    token = token.strip()
    if token.startswith(b"<") and token.endswith(b">"):
        return decode_hex_string(token[1:-1].decode(), cmap)
    if token.startswith(b"(") and token.endswith(b")"):
        return token[1:-1].decode("latin-1")
    return ""


def read_content_streams(raw_pdf: bytes) -> list[bytes]:
    stream_pattern = re.compile(rb"stream\r?\n(.*?)endstream", re.S)
    streams: list[bytes] = []
    for match in stream_pattern.finditer(raw_pdf):
        stream = match.group(1)
        try:
            decompressed = zlib.decompress(stream)
        except Exception:
            continue
        if b"Tm" in decompressed and (b"TJ" in decompressed or b"Tj" in decompressed):
            streams.append(decompressed)
    return streams


def rows_from_stream(stream: bytes, cmap: dict[int, str]) -> list[dict]:
    tm_pattern = re.compile(rb"([0-9.-]+) [0-9.-]+ [0-9.-]+ [0-9.-]+ ([0-9.-]+) ([0-9.-]+) Tm")
    entries: list[tuple[float, float, str]] = []

    for match in tm_pattern.finditer(stream):
        x = float(match.group(2))
        y = float(match.group(3))
        start = match.end()
        next_tm = tm_pattern.search(stream, start)
        chunk = stream[start : next_tm.start()] if next_tm else stream[start:]

        texts: list[str] = []
        for text_match in re.finditer(rb"(\[(.*?)\]\s*TJ|<[^>]+>\s*Tj|\([^\)]*\)\s*Tj)", chunk, re.S):
            token = text_match.group(0)
            if token.startswith(b"["):
                inner = text_match.group(2)
                for hex_part in re.findall(rb"<([0-9A-F]+)>", inner):
                    texts.append(decode_hex_string(hex_part.decode(), cmap))
                for str_part in re.findall(rb"\(([^\)]*)\)", inner):
                    texts.append(str_part.decode("latin-1"))
            else:
                value = token.split()[0]
                texts.append(decode_token(value, cmap))

        text_value = "".join(texts).strip()
        if text_value:
            entries.append((y, x, text_value))

    rows: list[dict] = []
    for y, x, text in entries:
        for row in rows:
            if abs(row["y"] - y) < 2:
                row["items"].append((x, text))
                break
        else:
            rows.append({"y": y, "items": [(x, text)]})

    rows.sort(key=lambda row: -row["y"])
    return rows


def extract_records(rows: list[dict]) -> list[dict]:
    columns = [
        ("index", 40),
        ("category", 60),
        ("name", 240),
        ("phone", 310),
        ("city", 340),
        ("district", 370),
        ("address", 520),
        ("offer", 9999),
    ]
    header_keywords = {
        "編",
        "分",
        "店家名稱",
        "聯絡電話",
        "縣市",
        "區域",
        "地址",
        "提供之優惠",
        "備註：詳細優惠內容請洽各特約商店",
    }

    records: list[dict] = []
    current: dict | None = None

    for row in rows:
        items = sorted(row["items"], key=lambda item: item[0])
        buckets = {key: [] for key, _ in columns}
        for x, text in items:
            for column, limit in columns:
                if x < limit:
                    buckets[column].append(text)
                    break

        index_text = "".join(buckets["index"]).strip()
        category_text = "".join(buckets["category"]).strip()
        name_text = "".join(buckets["name"]).strip()
        phone_text = " ".join(buckets["phone"]).strip()
        city_text = "".join(buckets["city"]).strip()
        district_text = "".join(buckets["district"]).strip()
        address_text = " ".join(buckets["address"]).strip()
        location_text = " ".join(filter(None, [city_text, district_text, address_text])).strip()
        offer_text = " ".join(buckets["offer"]).strip()

        line_text = " ".join(
            filter(None, [index_text, category_text, name_text, phone_text, city_text, district_text, address_text])
        )
        if row["y"] > 520 or any(keyword in line_text for keyword in header_keywords):
            continue

        if category_text and name_text:
            if current and current.get("index"):
                records.append(current)
            current = {
                "index": index_text or None,
                "category": category_text,
                "name": name_text,
                "phones": [],
                "locations": [],
                "offers": [],
            }
        elif index_text and current:
            current["index"] = index_text

        if current:
            if phone_text:
                current["phones"].append(phone_text)
            if location_text:
                current["locations"].append(location_text)
            if offer_text:
                current["offers"].append(offer_text)

    if current:
        records.append(current)

    cleaned: list[dict] = []
    for number, record in enumerate(records, start=1):
        name = record.get("name") or record.get("category") or f"商店 {number}"
        cleaned.append(
            {
                "id": number,
                "index": record.get("index") or str(number),
                "category": record.get("category") or "未分類",
                "name": name,
                "phones": list(dict.fromkeys(record.get("phones", []))),
                "locations": list(dict.fromkeys(record.get("locations", []))),
                "offers": [offer for offer in record.get("offers", []) if offer],
            }
        )
    return cleaned


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    safe = re.sub(r"[^a-zA-Z0-9一-龯]+", "-", ascii_text).strip("-")
    return safe or "shop"


def render_index(shops: list[dict]) -> str:
    items = []
    for shop in shops:
        items.append(
            f"""
            <article class="card">
              <header>
                <p class="pill">{html.escape(shop["category"])}</p>
                <h2><a href="shops/{html.escape(slugify(shop['name']))}/">{html.escape(shop["name"])}</a></h2>
                <p class="muted">編號：{html.escape(str(shop["index"]))}</p>
              </header>
              <p class="muted">電話：{html.escape("、".join(shop["phones"]) or "未提供")}<br>
              地址：{html.escape(" / ".join(shop["locations"]) or "未提供")}</p>
            </article>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>桃園捷運特約商店列表</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="container">
    <h1>桃園捷運特約商店列表</h1>
    <p class="muted">依據「桃園市政府員工卡特約商店名單及優惠措施一覽表」自動產生。</p>
    <div class="grid">
      {''.join(items)}
    </div>
  </main>
</body>
</html>
"""


def render_shop_page(shop: dict) -> str:
    offers = "".join(f"<li>{html.escape(offer)}</li>" for offer in shop["offers"]) or "<li>尚未整理</li>"
    phones = html.escape("、".join(shop["phones"]) or "未提供")
    locations = "".join(f"<li>{html.escape(line)}</li>" for line in shop["locations"]) or "<li>未提供</li>"

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(shop["name"])} | 桃園捷運特約商店</title>
  <link rel="stylesheet" href="../../styles.css">
</head>
<body>
  <main class="container">
    <a href="../../" class="back-link">← 回到列表</a>
    <p class="pill">{html.escape(shop["category"])}</p>
    <h1>{html.escape(shop["name"])}</h1>
    <p class="muted">編號：{html.escape(str(shop["index"]))}</p>
    <section>
      <h2>聯絡資訊</h2>
      <p>電話：{phones}</p>
      <ul>{locations}</ul>
    </section>
    <section>
      <h2>優惠內容</h2>
      <ul>{offers}</ul>
    </section>
  </main>
</body>
</html>
"""


def render_styles() -> str:
    return """*{box-sizing:border-box;}body{font-family:"Noto Sans TC",system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#f6f7fb;color:#1f2933;}a{color:#1f71d2;text-decoration:none;}a:hover{text-decoration:underline;}main.container{max-width:1100px;margin:0 auto;padding:24px;}h1{margin-bottom:8px;}p.muted{color:#52606d;margin:4px 0 12px;} .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;} .card{background:#fff;border:1px solid #e0e7ef;border-radius:12px;padding:16px;box-shadow:0 10px 25px rgba(15,23,42,0.05);} .pill{display:inline-block;padding:4px 10px;border-radius:999px;background:#e5edff;color:#1f71d2;font-size:14px;margin:0 0 6px 0;} .back-link{display:inline-block;margin-bottom:12px;} section{margin-top:16px;} ul{padding-left:18px;}"""


def write_site(shops: list[dict]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    styles_path = DOCS_DIR / "styles.css"
    styles_path.write_text(render_styles(), encoding="utf-8")

    index_html = render_index(shops)
    (DOCS_DIR / "index.html").write_text(index_html, encoding="utf-8")

    shops_dir = DOCS_DIR / "shops"
    shops_dir.mkdir(parents=True, exist_ok=True)
    for shop in shops:
        shop_dir = shops_dir / slugify(shop["name"])
        shop_dir.mkdir(parents=True, exist_ok=True)
        (shop_dir / "index.html").write_text(render_shop_page(shop), encoding="utf-8")


def main() -> None:
    raw_pdf = PDF_PATH.read_bytes()
    cmap = extract_cmap(raw_pdf)
    rows: list[dict] = []
    for stream in read_content_streams(raw_pdf):
        rows.extend(rows_from_stream(stream, cmap))

    shops = extract_records(rows)
    shops_path = DATA_DIR / "shops.json"
    shops_path.parent.mkdir(parents=True, exist_ok=True)
    shops_path.write_text(json.dumps(shops, ensure_ascii=False, indent=2), encoding="utf-8")
    write_site(shops)
    print(f"共匯出 {len(shops)} 家特約商店。")


if __name__ == "__main__":
    main()
