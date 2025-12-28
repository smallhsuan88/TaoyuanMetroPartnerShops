const PDF_URL = encodeURI("./桃園市政府員工卡特約商店名單及優惠措施一覽表(1217更新).pdf");
const CACHE_KEY = "taoyuan-metro-partner-shops-v1";
const CACHE_TTL_MS = 1000 * 60 * 60 * 24; // one day

const COUNTY_NAMES = [
  "基隆市",
  "臺北市",
  "新北市",
  "桃園市",
  "新竹縣",
  "新竹市",
  "苗栗縣",
  "臺中市",
  "彰化縣",
  "南投縣",
  "雲林縣",
  "嘉義縣",
  "嘉義市",
  "臺南市",
  "高雄市",
  "屏東縣",
  "宜蘭縣",
  "花蓮縣",
  "臺東縣",
  "澎湖縣",
  "金門縣",
  "連江縣",
];

function loadPdfJs() {
  return new Promise((resolve, reject) => {
    if (window.pdfjsLib) {
      return resolve(window.pdfjsLib);
    }
    const script = document.createElement("script");
    script.src = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.js";
    script.onload = () => resolve(window.pdfjsLib);
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

async function getPdf() {
  const pdfjsLib = await loadPdfJs();
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.js";
  return pdfjsLib.getDocument(PDF_URL).promise;
}

function groupTextByLine(items) {
  const grouped = new Map();
  items.forEach((item) => {
    const y = Math.round(item.transform[5]);
    const x = item.transform[4];
    const bucket = grouped.get(y) || [];
    bucket.push({ x, text: item.str });
    grouped.set(y, bucket);
  });

  return Array.from(grouped.entries())
    .map(([y, texts]) => ({
      y,
      text: texts
        .sort((a, b) => a.x - b.x)
        .map((t) => t.text)
        .join(" ")
        .replace(/\s+/g, " ")
        .trim(),
    }))
    .filter((line) => line.text);
}

async function extractLines() {
  const pdf = await getPdf();
  const allLines = [];

  for (let i = 1; i <= pdf.numPages; i += 1) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const pageLines = groupTextByLine(content.items).sort((a, b) => b.y - a.y);
    allLines.push(
      ...pageLines.map((line) => ({
        page: i,
        text: line.text,
      }))
    );
  }

  return allLines;
}

function isHeaderLine(text) {
  return (
    /桃園市政府員工卡特約商店名單及優惠措施一覽表/.test(text) ||
    /^第 \d+ 頁/.test(text) ||
    text.includes("備註：詳細優惠內容請洽各特約商店") ||
    text.startsWith("編 號") ||
    text.startsWith("編號 分類 店家名稱")
  );
}

function looksLikeEntryStart(text) {
  return /^(\d{1,3})\s+[一-龯]{1,4}\s+[一-龯]{1,4}\s+/.test(text);
}

function rebuildPhone(tokens) {
  const phoneTokens = [];
  for (let i = tokens.length - 1; i >= 0; i -= 1) {
    const value = tokens[i];
    if (/[0-9()-/#]+/.test(value)) {
      phoneTokens.unshift(value);
    } else if (phoneTokens.length === 0) {
      continue;
    } else {
      break;
    }
  }
  return phoneTokens.join(" ");
}

function findCountyIndex(tokens) {
  return tokens.findIndex((token) => COUNTY_NAMES.includes(token));
}

function splitAddress(tokens) {
  if (!tokens.length) return { address: "", offer: "" };
  const triggerIndex = tokens.findIndex((token) => /優惠|折|免|贈|享/.test(token));
  if (triggerIndex === -1) {
    return { address: tokens.join(" "), offer: "" };
  }
  return {
    address: tokens.slice(0, triggerIndex).join(" "),
    offer: tokens.slice(triggerIndex).join(" "),
  };
}

function parseEntryLine(line) {
  const startMatch = line.match(/^(\d{1,3})\s+([一-龯]{1,4})\s+([一-龯]{1,4})\s+(.*)$/);
  if (!startMatch) return null;

  const [, rawIndex, categoryA, categoryB, remainder] = startMatch;
  const tokens = remainder.split(" ").filter(Boolean);

  const countyIndex = findCountyIndex(tokens);
  if (countyIndex === -1) {
    return {
      id: Number(rawIndex),
      category: `${categoryA}${categoryB}`,
      name: remainder.trim(),
      phone: "",
      county: "",
      district: "",
      address: "",
      offer: "",
    };
  }

  const preCounty = tokens.slice(0, countyIndex);
  const phone = rebuildPhone(preCounty);
  const phoneParts = phone ? phone.split(" ") : [];
  const cutIndex = phoneParts.length ? Math.max(preCounty.length - phoneParts.length, 0) : preCounty.length;
  const nameTokens = preCounty.slice(0, cutIndex);

  const county = tokens[countyIndex];
  const district = tokens[countyIndex + 1] || "";
  const { address, offer } = splitAddress(tokens.slice(countyIndex + 2));

  return {
    id: Number(rawIndex),
    category: `${categoryA}${categoryB}`,
    name: nameTokens.join(" ") || remainder.trim(),
    phone,
    county,
    district,
    address,
    offer: offer.trim(),
  };
}

function mergeOffers(entries, pendingLines) {
  if (pendingLines.length) {
    const extra = pendingLines.join(" ").trim();
    if (extra) {
      const last = entries[entries.length - 1];
      last.offer = [last.offer, extra].filter(Boolean).join(" ").trim();
    }
  }
}

function parseShopsFromLines(lines) {
  const entries = [];
  let current = null;
  let buffer = [];

  lines.forEach((line) => {
    if (isHeaderLine(line.text)) return;
    const parsed = looksLikeEntryStart(line.text) ? parseEntryLine(line.text) : null;

    if (parsed) {
      if (current) {
        mergeOffers(entries, buffer);
        buffer = [];
      }
      entries.push(parsed);
      current = parsed;
    } else if (current) {
      buffer.push(line.text);
    }
  });

  if (current) {
    mergeOffers(entries, buffer);
  }

  return entries;
}

function getCached() {
  const raw = localStorage.getItem(CACHE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (Date.now() - parsed.timestamp > CACHE_TTL_MS) return null;
    return parsed.data;
  } catch (error) {
    return null;
  }
}

function cacheData(data) {
  localStorage.setItem(
    CACHE_KEY,
    JSON.stringify({
      timestamp: Date.now(),
      data,
    })
  );
}

export async function loadShops(onProgress) {
  const cached = getCached();
  if (cached?.length) {
    return cached;
  }

  if (onProgress) onProgress("載入 PDF 中…");
  const lines = await extractLines();

  if (onProgress) onProgress("正在解析店家資料…");
  const shops = parseShopsFromLines(lines).sort((a, b) => a.id - b.id);
  cacheData(shops);
  return shops;
}

export function findShop(shops, id) {
  return shops.find((shop) => String(shop.id) === String(id));
}
