# TaoyuanMetroPartnerShops

靜態 GitHub Pages 網站，涵蓋桃園捷運特約商店資料，每間店家皆有獨立頁面。

## 專案內容
- `scripts/extract_shops.py`：從官方 PDF 解析 287 家特約商店資訊並輸出 `data/shops.json`。
- `scripts/build_site.py`：讀取 JSON，產生 `docs/index.html` 與 `docs/shops/<id>/index.html`。
- `docs/`：GitHub Pages 站點原始碼與產出的 287 個店家頁面。

## 本地重建步驟
1. 解析 PDF 取得最新 JSON：
   ```bash
   python scripts/extract_shops.py
   ```
2. 重新產生靜態網站：
   ```bash
   python scripts/build_site.py
   ```

## 部署
將 GitHub Pages 的來源設定為 `docs/` 目錄，即可直接發布所有店家頁面與首頁搜尋/篩選介面。
