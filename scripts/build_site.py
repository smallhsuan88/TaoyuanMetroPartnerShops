#!/usr/bin/env python3
"""
Generate the static GitHub Pages site for Taoyuan Metro partner shops.

Usage:
    python scripts/build_site.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Dict, List


DATA_PATH = Path("data/shops.json")
DOCS_DIR = Path("docs")
DATA_OUT = DOCS_DIR / "data" / "shops.json"
DETAIL_DIR = DOCS_DIR / "shops"


def _split_offers(offers: str) -> str:
    """Convert offers into a HTML-friendly string with manual breaks."""

    parts = [part.strip() for part in re.split(r"\s+(?=\d+[\.、])", offers) if part.strip()]
    if not parts:
        parts = [offers.strip()]
    return "<br>".join(html.escape(part) for part in parts)


def _render_detail(shop: Dict[str, str]) -> str:
    offers_html = _split_offers(shop["offers"])
    address_display = f"{shop['city']}{shop['district']}{shop['address']}"
    map_query = html.escape(address_display)
    phone_link = html.escape(shop["phone"]) if shop["phone"] else "N/A"

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(shop['name'])} ｜ 桃園捷運特約商店</title>
  <link rel="stylesheet" href="../assets/style.css">
  <meta name="description" content="桃園捷運特約商店：{html.escape(shop['name'])} 優惠資訊">
</head>
<body class="page">
  <header class="site-header">
    <div class="logo">桃園捷運特約商店</div>
    <nav><a href="../index.html">回首頁</a></nav>
  </header>
  <main class="detail">
    <section class="card detail-card">
      <div class="detail-heading">
        <p class="badge">{html.escape(shop['category'])}</p>
        <h1>{html.escape(shop['name'])}</h1>
        <p class="location">{html.escape(shop['city'])} · {html.escape(shop['district'])}</p>
      </div>
      <dl class="detail-grid">
        <div>
          <dt>聯絡電話</dt>
          <dd>{phone_link}</dd>
        </div>
        <div>
          <dt>地址</dt>
          <dd>{html.escape(shop['address'])}</dd>
        </div>
        <div>
          <dt>地圖</dt>
          <dd><a href="https://www.google.com/maps/search/?api=1&query={map_query}" target="_blank" rel="noopener">在地圖中開啟</a></dd>
        </div>
      </dl>
      <div class="offers">
        <h2>優惠內容</h2>
        <p>{offers_html}</p>
      </div>
    </section>
  </main>
  <footer class="site-footer">
    <p>資料來源：桃園市政府員工卡特約商店名單（2024/12/17 更新）</p>
    <a href="../index.html">回到全部商店</a>
  </footer>
</body>
</html>
"""


def _render_index() -> str:
    return """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>桃園捷運特約商店地圖 | GitHub Pages</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <header class="hero">
    <div>
      <p class="eyebrow">Taoyuan Metro Partner Shops</p>
      <h1>桃園捷運特約商店網站</h1>
      <p class="lede">瀏覽 287 家特約商店，查看各店優惠、地址與聯絡方式。每間店家都有專屬的靜態頁面，直接部署在 GitHub Pages。</p>
      <div class="actions">
        <a class="button" href="#shops">開始瀏覽</a>
        <a class="button ghost" href="data/shops.json">下載 JSON 資料</a>
      </div>
    </div>
    <div class="hero-card card">
      <p>搜尋 & 篩選</p>
      <ul>
        <li>以店名、地址或優惠關鍵字即時搜尋</li>
        <li>依分類與縣市篩選，快速定位</li>
        <li>每間店都有專屬連結，可直接分享</li>
      </ul>
    </div>
  </header>

  <main id="shops" class="content">
    <section class="filters card">
      <div class="input-group">
        <label for="search">搜尋</label>
        <input id="search" type="search" placeholder="輸入店名、地址或優惠關鍵字">
      </div>
      <div class="filter-grid">
        <div class="input-group">
          <label for="category">分類</label>
          <select id="category"></select>
        </div>
        <div class="input-group">
          <label for="city">縣市</label>
          <select id="city"></select>
        </div>
      </div>
    </section>

    <section id="shop-list" class="grid"></section>
    <div id="empty-state" class="card empty hidden">找不到符合條件的商店，請調整搜尋或篩選條件。</div>
  </main>

  <footer class="site-footer">
    <p>資料來源：桃園市政府員工卡特約商店名單（2024/12/17 更新）。</p>
    <p>此網站為靜態 GitHub Pages，所有內容來自倉庫內的 PDF 與 JSON。</p>
  </footer>

  <script src="assets/main.js" type="module"></script>
</body>
</html>
"""


def main() -> None:
    if not DATA_PATH.exists():
        raise SystemExit(f"Missing data file: {DATA_PATH}")

    shops: List[Dict[str, str]] = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(shops, ensure_ascii=False, indent=2), encoding="utf-8")

    DETAIL_DIR.mkdir(parents=True, exist_ok=True)
    for shop in shops:
        detail_path = DETAIL_DIR / str(shop["id"]) / "index.html"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(_render_detail(shop), encoding="utf-8")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "index.html").write_text(_render_index(), encoding="utf-8")

    print(f"Generated {len(shops)} detail pages and index at {DOCS_DIR}")


if __name__ == "__main__":
    main()
