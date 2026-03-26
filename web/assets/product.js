const detailEl = document.querySelector("#product-detail");

const productId = decodeURIComponent(window.location.pathname.split("/").filter(Boolean).at(-1) || "");

void loadProduct(productId);

async function loadProduct(id) {
  const response = await fetch(`/api/products/${id}`, { cache: "no-store" });
  if (!response.ok) {
    detailEl.innerHTML = `<div class="debug-empty">Product not found.</div>`;
    return;
  }
  const payload = await response.json();
  detailEl.innerHTML = renderProduct(payload);
}

function renderProduct(payload) {
  const product = payload.product;
  const hero = payload.media?.find((media) => media.is_primary) || payload.media?.[0];
  const offer = payload.offers?.find((item) => item.is_active) || payload.offers?.[0];

  return `
    <div class="product-grid">
      <section class="product-media-panel">
        <img class="product-hero-image" src="${escapeHtml(hero?.url || "")}" alt="${escapeHtml(hero?.alt_text || product.title)}" />
        <div class="product-thumb-row">
          ${(payload.media || [])
            .slice(0, 4)
            .map(
              (media) => `
                <img class="product-thumb" src="${escapeHtml(media.thumbnail_url || media.url || "")}" alt="${escapeHtml(media.alt_text || product.title)}" />
              `,
            )
            .join("")}
        </div>
      </section>

      <section class="product-info-panel">
        <div class="debug-eyebrow">${escapeHtml(product.category_name || "")}</div>
        <h1 class="product-title">${escapeHtml(product.title)}</h1>
        <div class="product-subline">${escapeHtml(product.brand || "Unknown brand")} · ${escapeHtml(product.sku || "")}</div>
        <div class="product-price-row">
          <span class="product-price">${formatPrice(offer?.price, offer?.currency)}</span>
          <span class="product-stock">Inventory ${offer?.inventory_count ?? 0}</span>
        </div>
        <div class="product-seller-row">
          Sold by <strong>${escapeHtml(offer?.seller_name || "Unknown seller")}</strong>
          <span>· seller ${Number(offer?.seller_rating || 0).toFixed(1)}</span>
          <span>· ${product.review_count ?? 0} reviews</span>
        </div>
        <p class="product-description">${escapeHtml(product.long_description || product.short_description || "")}</p>

        <div class="product-actions">
          <button class="product-primary-action" type="button">Add to cart</button>
          ${
            offer?.product_url
              ? `<a class="product-secondary-link" href="${escapeHtml(offer.product_url)}" target="_blank" rel="noreferrer">Original source</a>`
              : ""
          }
        </div>

        <div class="product-section">
          <div class="debug-block-label">Search Terms</div>
          <div class="debug-chip-row">${renderChips(product.search_terms || [])}</div>
        </div>

        <div class="product-section">
          <div class="debug-block-label">Image Tags</div>
          <div class="debug-chip-row">${renderChips(product.image_tags || [])}</div>
        </div>
      </section>
    </div>
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
