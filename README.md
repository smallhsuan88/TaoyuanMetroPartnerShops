# TaoyuanMetroPartnerShops

這個專案會直接在瀏覽器端解析《桃園市政府員工卡特約商店名單及優惠措施一覽表(1217更新).pdf》，並建立每家特約商店的獨立頁面，方便透過 GitHub Pages 發佈。

## 使用方式

1. 將此 repo 推到 GitHub，開啟 GitHub Pages（建議 branch：`main`，資料夾：`/`）。
2. 部署完成後，造訪 Pages 網址（例如 `https://<your-name>.github.io/TaoyuanMetroPartnerShops/`）。
3. 首頁 (`index.html`) 會解析 PDF 並建立店家清單；點擊任一店家即可開啟 `shop.html?id=<編號>` 專頁。

> 若要在本機預覽，可直接用瀏覽器開啟 `index.html`。第一次載入會讀取並解析 PDF，結果會快取一天。

## 技術重點

- 前端使用 [PDF.js CDN 版](https://mozilla.github.io/pdf.js/) 解析 PDF 文字並轉成店家清單。
- 解析結果快取在 `localStorage`，減少重複讀取 PDF。
- 所有頁面與資源皆為靜態檔案，適合 GitHub Pages。
