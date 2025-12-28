"""
Generate static HTML pages for each partner shop using data/shops.json.

Pages are written to the docs/ directory so they can be hosted with
GitHub Pages (project site mode).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "shops.json"
DOCS = ROOT / "docs"
SHOPS_DIR = DOCS / "shops"


def load_shops() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def render_template(title: str, content: str, *, base_path: str) -> str:
    return (
        BASE_TEMPLATE.replace("{{TITLE}}", title)
        .replace("{{CONTENT}}", content)
        .replace("{{BASE_PATH}}", base_path)
    )


def render_shop_card(shop: dict) -> str:
    category = f"{shop['category_main']}・{shop['category_sub']}"
    return f"""
    <article class="shop-card"
      data-name="{html.escape(shop['name'])}"
      data-offers="{html.escape(shop['offers'])}"
      data-city="{html.escape(shop['city'])}"
      data-category="{html.escape(category)}"
    >
      <div class="pill">{html.escape(category)}</div>
      <h2>{html.escape(shop['name'])}</h2>
      <p class="meta">{html.escape(shop['city'])} {html.escape(shop['district'])} · {html.escape(shop['phone'])}</p>
      <p class="address">{html.escape(shop['address'])}</p>
      <p class="offers">{html.escape(shop['offers'])}</p>
      <div class="card-actions">
        <a class="button" href="shops/{shop['id']}.html">查看詳情</a>
      </div>
    </article>
    """


def render_index(shops: list[dict]) -> str:
    categories = sorted({f"{s['category_main']}・{s['category_sub']}" for s in shops})
    cities = sorted({s["city"] for s in shops})
    cards = "\n".join(render_shop_card(shop) for shop in shops)
    filter_ui = f"""
    <section class="filters">
      <div class="filter-group">
        <label for="search">搜尋商店</label>
        <input id="search" type="search" placeholder="輸入名稱、優惠或地址關鍵字…" />
      </div>
      <div class="filter-row">
        <div class="filter-group">
          <label for="city">縣市</label>
          <select id="city">
            <option value="">全部縣市</option>
            {''.join(f'<option value="{html.escape(city)}">{html.escape(city)}</option>' for city in cities)}
          </select>
        </div>
        <div class="filter-group">
          <label for="category">類別</label>
          <select id="category">
            <option value="">全部類別</option>
            {''.join(f'<option value="{html.escape(cat)}">{html.escape(cat)}</option>' for cat in categories)}
          </select>
        </div>
      </div>
      <p class="result-count">共 <strong id="shop-count">{len(shops)}</strong> 間特約商店</p>
    </section>
    """
    content = f"<h1>桃園捷運特約商店</h1>{filter_ui}<div class='grid' id='shop-grid'>{cards}</div>"
    return render_template("桃園捷運特約商店列表", content, base_path="")


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
    return render_template(
        f"{html.escape(shop['name'])} | 桃園捷運特約商店",
        details,
        base_path="../",
    )


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
  <link rel="stylesheet" href="{{BASE_PATH}}style.css">
</head>
<body>
  <main class="container">
    {{CONTENT}}
  </main>
  <script>
  const grid = document.getElementById('shop-grid');
  const searchInput = document.getElementById('search');
  const citySelect = document.getElementById('city');
  const categorySelect = document.getElementById('category');
  const countEl = document.getElementById('shop-count');

  function matchesFilters(card) {
    const text = (card.dataset.name + card.dataset.offers + card.dataset.city + (card.querySelector('.address')?.textContent || '')).toLowerCase();
    const keyword = (searchInput?.value || '').toLowerCase();
    const city = citySelect?.value || '';
    const category = categorySelect?.value || '';
    const cityOk = !city || card.dataset.city === city;
    const categoryOk = !category || card.dataset.category === category;
    const keywordOk = !keyword || text.includes(keyword);
    return cityOk && categoryOk && keywordOk;
  }

  function filterCards() {
    if (!grid) return;
    const cards = Array.from(grid.querySelectorAll('.shop-card'));
    let visible = 0;
    cards.forEach(card => {
      if (matchesFilters(card)) {
        card.hidden = false;
        visible += 1;
      } else {
        card.hidden = true;
      }
    });
    if (countEl) countEl.textContent = visible.toString();
  }

  [searchInput, citySelect, categorySelect].forEach(el => {
    if (el) el.addEventListener('input', filterCards);
    if (el) el.addEventListener('change', filterCards);
  });
  </script>
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
  --border: #e5e7eb;
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
.filters {
  background: var(--card);
  border-radius: 16px;
  padding: 16px;
  box-shadow: var(--shadow);
  margin: 12px 0 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.filter-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.filter-group label {
  font-weight: 600;
  color: var(--muted);
}
.filters input,
.filters select {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  font-size: 14px;
}
.result-count {
  color: var(--muted);
  font-size: 14px;
}
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
.card-actions { margin-top: 10px; }
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 12px;
  background: var(--accent);
  color: #fff;
  border-radius: 12px;
  text-decoration: none;
  font-weight: 600;
  font-size: 14px;
  transition: transform 120ms ease, box-shadow 120ms ease;
  box-shadow: 0 8px 16px rgba(106, 90, 205, 0.2);
}
.button:hover { transform: translateY(-1px); }
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
