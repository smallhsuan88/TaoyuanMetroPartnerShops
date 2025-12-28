const state = {
  shops: [],
  search: "",
  category: "全部",
  city: "全部",
};

const selectors = {
  list: document.getElementById("shop-list"),
  empty: document.getElementById("empty-state"),
  search: document.getElementById("search"),
  category: document.getElementById("category"),
  city: document.getElementById("city"),
};

function normalize(str) {
  return str.toLowerCase().trim();
}

function renderOptions(select, values) {
  select.innerHTML = "";
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function populateFilters(shops) {
  const categories = ["全部", ...Array.from(new Set(shops.map((s) => s.category)))];
  const cities = ["全部", ...Array.from(new Set(shops.map((s) => s.city)))];
  renderOptions(selectors.category, categories);
  renderOptions(selectors.city, cities);
}

function applyFilters() {
  const { search, category, city, shops } = state;
  const keywords = normalize(search);

  return shops.filter((shop) => {
    const matchesCategory = category === "全部" || shop.category === category;
    const matchesCity = city === "全部" || shop.city === city;
    const haystack = normalize(
      `${shop.name} ${shop.address} ${shop.city} ${shop.district} ${shop.offers} ${shop.phone}`
    );
    const matchesKeyword = !keywords || haystack.includes(keywords);
    return matchesCategory && matchesCity && matchesKeyword;
  });
}

function createCard(shop) {
  const card = document.createElement("article");
  card.className = "card shop-card";
  const offers = shop.offers.length > 80 ? `${shop.offers.slice(0, 80)}…` : shop.offers;
  card.innerHTML = `
    <p class="badge">${shop.category}</p>
    <h3>${shop.name}</h3>
    <div class="meta">
      <span>${shop.city} · ${shop.district}</span>
      <span class="muted">${shop.phone || "N/A"}</span>
    </div>
    <p class="muted">${offers}</p>
    <div class="link-row">
      <a href="shops/${shop.id}/">查看店家頁面</a>
      <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
        `${shop.city}${shop.district}${shop.address}`
      )}" target="_blank" rel="noopener">地圖</a>
    </div>
  `;
  return card;
}

function renderList() {
  const results = applyFilters();
  selectors.list.innerHTML = "";
  if (results.length === 0) {
    selectors.empty.classList.remove("hidden");
    return;
  }
  selectors.empty.classList.add("hidden");
  results.forEach((shop) => selectors.list.appendChild(createCard(shop)));
}

function bindEvents() {
  selectors.search.addEventListener("input", (event) => {
    state.search = event.target.value;
    renderList();
  });

  selectors.category.addEventListener("change", (event) => {
    state.category = event.target.value;
    renderList();
  });

  selectors.city.addEventListener("change", (event) => {
    state.city = event.target.value;
    renderList();
  });
}

async function init() {
  const response = await fetch("data/shops.json");
  const shops = await response.json();
  state.shops = shops;

  populateFilters(shops);
  bindEvents();
  renderList();
}

init().catch((error) => {
  selectors.empty.textContent = `載入資料時發生錯誤：${error}`;
  selectors.empty.classList.remove("hidden");
});
