const statsEl = document.querySelector("#debug-stats");
const gridEl = document.querySelector("#debug-product-grid");
const filterEl = document.querySelector("#debug-product-filter");

let products = [];

async function loadDebugData() {
  const [summaryResp, productsResp] = await Promise.all([
    fetch("/api/debug/seed-summary", { cache: "no-store" }),
    fetch("/api/debug/products?limit=200", { cache: "no-store" }),
  ]);
  const summary = await summaryResp.json();
  const productsPayload = await productsResp.json();
  products = productsPayload.products || [];
  renderSummary(summary);
  renderProducts(products);
}

function renderSummary(summary) {
  const entries = [
    ["Categories", summary.categories],
    ["Products", summary.products],
    ["Media", summary.product_media],
    ["Search Docs", summary.search_docs],
    ["Text Embeddings", summary.text_embeddings],
    ["Image Embeddings", summary.image_embeddings],
  ];
  statsEl.innerHTML = entries
    .map(
      ([label, value]) => `
        <article class="debug-stat-card">
          <span class="debug-stat-label">${label}</span>
          <strong class="debug-stat-value">${value}</strong>
        </article>
      `,
    )
    .join("");
}

function renderProducts(rows) {
  if (!rows.length) {
    gridEl.innerHTML = `<div class="debug-empty">No debug products found.</div>`;
    return;
  }
  gridEl.innerHTML = rows.map(renderProductCard).join("");
}

function renderProductCard(product) {
  const searchable = [
    product.title,
    product.category_name,
    product.brand,
    product.short_description,
    product.search_text,
    ...(product.text_tags || []),
    ...(product.image_tags || []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return `
    <article class="debug-product-card" data-searchable="${escapeHtml(searchable)}">
      <div class="debug-product-top">
        <img class="debug-product-image" src="${product.primary_image_url || ""}" alt="${escapeHtml(product.title)}" />
        <div class="debug-product-copy">
          <div class="debug-product-title-row">
            <strong>${escapeHtml(product.title)}</strong>
            <span class="debug-price">${formatPrice(product.price, product.currency)}</span>
          </div>
          <div class="debug-meta-line">${escapeHtml(product.category_name)} · ${escapeHtml(product.brand || "Unknown brand")}</div>
          <div class="debug-meta-line mono">${product.product_id} · ${escapeHtml(product.sku)}</div>
          <div class="debug-meta-line">${escapeHtml(product.seller_name || "Unknown seller")} · inventory ${product.inventory_count ?? 0} · reviews ${product.review_count ?? 0}</div>
        </div>
      </div>

      <div class="debug-badges">
        <span class="debug-badge ${product.has_text_embedding ? "ok" : ""}">text embedding: ${product.has_text_embedding ? "yes" : "no"}</span>
        <span class="debug-badge ${product.has_image_embedding ? "ok" : ""}">image embedding: ${product.has_image_embedding ? "yes" : "no"}</span>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Short Description</div>
        <div class="debug-block-copy">${escapeHtml(product.short_description)}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Text Tags</div>
        <div class="debug-chip-row">${renderChips(product.text_tags || [])}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Image Tags</div>
        <div class="debug-chip-row">${renderChips(product.image_tags || [])}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Search Text</div>
        <pre class="debug-pre">${escapeHtml(product.search_text || "")}</pre>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Attributes JSON</div>
        <pre class="debug-pre">${escapeHtml(JSON.stringify(product.attributes || {}, null, 2))}</pre>
      </div>

      ${
        product.product_url
          ? `<a class="debug-product-link" href="${product.product_url}" target="_blank" rel="noreferrer">Open product URL</a>`
          : ""
      }
    </article>
  `;
}

function renderChips(values) {
  if (!values.length) {
    return `<span class="debug-chip muted">none</span>`;
  }
  return values.map((value) => `<span class="debug-chip">${escapeHtml(value)}</span>`).join("");
}

function formatPrice(price, currency) {
  if (price == null) {
    return "n/a";
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2,
  }).format(price);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

filterEl.addEventListener("input", () => {
  const needle = filterEl.value.trim().toLowerCase();
  if (!needle) {
    renderProducts(products);
    return;
  }
  renderProducts(products.filter((product) => JSON.stringify(product).toLowerCase().includes(needle)));
});

loadDebugData();
