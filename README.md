# TaoyuanMetroPartnerShops

## 如何重新產生 GitHub Pages 網站

1. 確認專案根目錄下有原始 PDF：`桃園市政府員工卡特約商店名單及優惠措施一覽表(1217更新).pdf`。
2. 執行產生器：

   ```bash
   python scripts/generate_site.py
   ```

   指令會：

   - 解析 PDF，匯出整理過的 JSON 至 `data/shops.json`。
   - 以 `docs/` 目錄生成靜態頁面（首頁與每間特約商店的獨立頁面）。
   - 同步輸出樣式檔 `docs/styles.css`。

3. 將 GitHub Pages 指定到 `docs/` 目錄，網站即可於 Pages 網域直接瀏覽。
