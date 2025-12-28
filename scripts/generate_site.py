"""
Generate static HTML pages for each partner shop using data/shops.json.

Pages are written to the docs/ directory so they can be hosted with
GitHub Pages (project site mode).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "shops.json"
DOCS = ROOT / "docs"
SHOPS_DIR = DOCS / "shops"


def load_shops() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def render_shop_card(shop: dict) -> str:
    return f"""
    <article class="shop-card">
      <div class="pill">{html.escape(shop['category_main'])}・{html.escape(shop['category_sub'])}</div>
      <h2><a href="shops/{shop['id']}.html">{html.escape(shop['name'])}</a></h2>
      <p class="meta">{html.escape(shop['city'])} {html.escape(shop['district'])} · {html.escape(shop['phone'])}</p>
      <p class="address">{html.escape(shop['address'])}</p>
      <p class="offers">{html.escape(shop['offers'])}</p>
    </article>
    """


def render_index(shops: list[dict]) -> str:
    cards = "\n".join(render_shop_card(shop) for shop in shops)
    return BASE_TEMPLATE.replace("{{TITLE}}", "桃園捷運特約商店列表").replace(
        "{{CONTENT}}",
        f"<h1>桃園捷運特約商店</h1><p>共 {len(shops)} 間特約商店</p><div class='grid'>{cards}</div>",
    )


def render_shop_page(shop: dict) -> str:
    details = f"""
    <article class="shop-detail">
      <a class="back" href="../index.html">← 返回列表</a>
      <div class="pill">{html.escape(shop['category_main'])}・{html.escape(shop['category_sub'])}</div>
      <h1>{html.escape(shop['name'])}</h1>
      <dl>
        <div><dt>聯絡電話</dt><dd>{html.escape(shop['phone'])}</dd></div>
        <div><dt>地址</dt><dd>{html.escape(shop['city'])} {html.escape(shop['district'])} {html.escape(shop['address'])}</dd></div>
      </dl>
      <section>
        <h2>優惠內容</h2>
        <p>{html.escape(shop['offers'])}</p>
      </section>
    </article>
    """
    return BASE_TEMPLATE.replace(
        "{{TITLE}}", f"{html.escape(shop['name'])} | 桃園捷運特約商店"
    ).replace("{{CONTENT}}", details)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate() -> None:
    shops = load_shops()
    write_file(DOCS / "index.html", render_index(shops))
    for shop in shops:
        write_file(SHOPS_DIR / f"{shop['id']}.html", render_shop_page(shop))
    write_file(DOCS / "style.css", STYLE)
    print(f"Generated {len(shops)} shop pages plus index in {DOCS.relative_to(ROOT)}")


BASE_TEMPLATE = """
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{TITLE}}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="container">
    {{CONTENT}}
  </main>
</body>
</html>
"""


STYLE = """
:root {
  --bg: #f7f7fb;
  --card: #ffffff;
  --accent: #6a5acd;
  --text: #222;
  --muted: #555;
  --shadow: 0 12px 28px rgba(17, 24, 39, 0.08);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Noto Sans TC", "Microsoft JhengHei", system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
}
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 20px 72px;
}
h1, h2, h3 { margin: 0 0 12px; }
p { margin: 0 0 12px; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.shop-card, .shop-detail {
  background: var(--card);
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: var(--shadow);
}
.shop-card h2 { font-size: 18px; }
.shop-card a { color: var(--text); text-decoration: none; }
.shop-card a:hover { color: var(--accent); }
.pill {
  display: inline-block;
  background: #ece9ff;
  color: var(--accent);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  margin-bottom: 6px;
}
.meta { color: var(--muted); font-size: 13px; }
.address { color: var(--muted); font-size: 14px; }
.offers { font-size: 14px; }
.shop-detail h1 { margin-top: 6px; }
.shop-detail dl { margin: 16px 0; }
.shop-detail dt { font-weight: 700; }
.shop-detail dd { margin: 4px 0 12px; color: var(--muted); }
.shop-detail .back { color: var(--accent); text-decoration: none; font-weight: 600; }
.shop-detail section { margin-top: 16px; }
@media (max-width: 600px) {
  .grid { grid-template-columns: 1fr; }
}
"""


if __name__ == "__main__":
    generate()
