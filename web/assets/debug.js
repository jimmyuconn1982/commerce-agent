const statsEl = document.querySelector("#debug-stats");
const gridEl = document.querySelector("#debug-product-grid");
const filterEl = document.querySelector("#debug-product-filter");
const detailEl = document.querySelector("#debug-product-detail");
const runForm = document.querySelector("#debug-run-form");
const runOutputEl = document.querySelector("#debug-run-output");
const runTextEl = document.querySelector("#debug-run-text");
const runImageUrlEl = document.querySelector("#debug-run-image-url");
const runFileEl = document.querySelector("#debug-run-file");
const runLimitEl = document.querySelector("#debug-run-limit");

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
    ["Multimodal Embeddings", summary.multimodal_embeddings],
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
  for (const button of gridEl.querySelectorAll("[data-product-id]")) {
    button.addEventListener("click", () => loadProductDetail(button.dataset.productId));
  }
}

function renderProductCard(product) {
  return `
    <button class="debug-product-card" type="button" data-product-id="${product.product_id}">
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
        <span class="debug-badge ${product.has_multimodal_embedding ? "ok" : ""}">multimodal embedding: ${product.has_multimodal_embedding ? "yes" : "no"}</span>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Text Tags</div>
        <div class="debug-chip-row">${renderChips(product.text_tags || [])}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Search Terms</div>
        <div class="debug-chip-row">${renderChips(product.search_terms || [])}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Cooking Uses</div>
        <div class="debug-chip-row">${renderChips(product.cooking_uses || [])}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Audience Terms</div>
        <div class="debug-chip-row">${renderChips(product.audience_terms || [])}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Image Tags</div>
        <div class="debug-chip-row">${renderChips(product.image_tags || [])}</div>
      </div>
    </button>
  `;
}

async function loadProductDetail(productId) {
  detailEl.innerHTML = `<div class="debug-empty">Loading product ${productId}...</div>`;
  const response = await fetch(`/api/debug/products/${productId}`, { cache: "no-store" });
  const payload = await response.json();
  detailEl.innerHTML = renderProductDetail(payload);
}

function renderProductDetail(payload) {
  const product = payload.product;
  return `
    <div class="debug-detail-head">
      <div>
        <div class="debug-eyebrow">Product</div>
        <h3>${escapeHtml(product.title)}</h3>
        <div class="debug-meta-line">${escapeHtml(product.category_name)} · ${escapeHtml(product.brand || "Unknown brand")} · ${escapeHtml(product.sku)}</div>
      </div>
    </div>

    <div class="debug-section-block">
      <div class="debug-block-label">Search Text</div>
      <pre class="debug-pre">${escapeHtml(product.search_text || "")}</pre>
    </div>

    <div class="debug-two-col">
      <div class="debug-section-block">
        <div class="debug-block-label">Text Tags</div>
        <div class="debug-chip-row">${renderChips(product.text_tags || [])}</div>
      </div>
      <div class="debug-section-block">
        <div class="debug-block-label">Search Terms</div>
        <div class="debug-chip-row">${renderChips(product.search_terms || [])}</div>
      </div>
    </div>

    <div class="debug-two-col">
      <div class="debug-section-block">
        <div class="debug-block-label">Image Tags</div>
        <div class="debug-chip-row">${renderChips(product.image_tags || [])}</div>
      </div>
      <div class="debug-section-block">
        <div class="debug-block-label">Cooking Uses</div>
        <div class="debug-chip-row">${renderChips(product.cooking_uses || [])}</div>
      </div>
    </div>

    <div class="debug-section-block">
      <div class="debug-block-label">Audience Terms</div>
      <div class="debug-chip-row">${renderChips(product.audience_terms || [])}</div>
    </div>

    <div class="debug-section-block">
      <div class="debug-block-label">Media</div>
      <div class="debug-media-list">
        ${payload.media
          .map(
            (media) => `
              <div class="debug-media-card">
                <img src="${media.url}" alt="${escapeHtml(media.alt_text || product.title)}" />
                <div class="debug-meta-line">${escapeHtml(media.alt_text || "No alt text")}</div>
                <div class="debug-meta-line mono">${media.media_type} · primary=${media.is_primary}</div>
              </div>
            `,
          )
          .join("")}
      </div>
    </div>

    <div class="debug-section-block">
      <div class="debug-block-label">Offers</div>
      <div class="debug-offer-list">
        ${payload.offers
          .map(
            (offer) => `
              <div class="debug-offer-card">
                <div><strong>${escapeHtml(offer.seller_name)}</strong> · ${formatPrice(offer.price, offer.currency)}</div>
                <div class="debug-meta-line">inventory ${offer.inventory_count ?? 0} · seller rating ${offer.seller_rating ?? 0}</div>
                <div class="debug-meta-line mono">${escapeHtml(offer.product_url || "")}</div>
              </div>
            `,
          )
          .join("")}
      </div>
    </div>

    <div class="debug-section-block">
      <div class="debug-block-label">Embeddings</div>
      <div class="debug-embedding-list">
        ${payload.embeddings
          .map(
            (embedding) => `
              <div class="debug-embedding-card">
                <div><strong>${embedding.embedding_type}</strong> · ${escapeHtml(embedding.model_name)}</div>
                <div class="debug-meta-line">${escapeHtml(embedding.model_version || "")}</div>
                ${embedding.source_text ? `<pre class="debug-pre">${escapeHtml(embedding.source_text)}</pre>` : ""}
                ${embedding.source_image_url ? `<div class="debug-meta-line mono">${escapeHtml(embedding.source_image_url)}</div>` : ""}
                <pre class="debug-pre">${escapeHtml(embedding.embedding_preview || "")}</pre>
              </div>
            `,
          )
          .join("")}
      </div>
    </div>

    <div class="debug-section-block">
      <div class="debug-block-label">Attributes JSON</div>
      <pre class="debug-pre">${escapeHtml(JSON.stringify(product.attributes || {}, null, 2))}</pre>
    </div>
  `;
}

runForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  runOutputEl.innerHTML = `<div class="debug-empty">Running debug request...</div>`;
  const form = new FormData();
  form.set("text", runTextEl.value);
  form.set("image_url", runImageUrlEl.value);
  form.set("limit", runLimitEl.value || "5");
  if (runFileEl.files[0]) {
    form.set("file", runFileEl.files[0]);
  }
  const response = await fetch("/api/debug/run", {
    method: "POST",
    body: form,
  });
  const payload = await response.json();
  runOutputEl.innerHTML = renderRunOutput(payload);
});

function renderRunOutput(payload) {
  const matches = (payload.matches || [])
    .map(
      (product) => `
        <div class="debug-offer-card">
          <div><strong>${escapeHtml(product.name)}</strong> · ${formatPrice(product.price, product.currency)}</div>
          <div class="debug-meta-line">${escapeHtml(product.category)} · ${escapeHtml(product.seller_name || "Unknown seller")}</div>
          <div class="debug-meta-line">${escapeHtml(product.description || "")}</div>
        </div>
      `,
    )
    .join("");

  const steps = (payload.trace?.react?.steps || [])
    .map(
      (step) => `
        <div class="debug-step">
          <div class="debug-step-title">${escapeHtml(step.tool_name)}</div>
          <div class="debug-step-copy">${escapeHtml(step.thought)}</div>
          <div class="debug-step-copy"><strong>In:</strong> ${escapeHtml(step.input_summary)}</div>
          <div class="debug-step-copy"><strong>Out:</strong> ${escapeHtml(step.observation_summary)}</div>
        </div>
      `,
    )
    .join("");

  const candidates = (payload.trace?.retrieval?.candidates || [])
    .slice(0, 8)
    .map(
      (candidate) => `
        <tr>
          <td>${escapeHtml(candidate.product.name)}</td>
          <td>${Number(candidate.text_score).toFixed(4)}</td>
          <td>${Number(candidate.image_score).toFixed(4)}</td>
          <td>${Number(candidate.multimodal_score ?? 0).toFixed(4)}</td>
          <td><strong>${Number(candidate.score).toFixed(4)}</strong></td>
        </tr>
      `,
    )
    .join("");

  return `
    <div class="debug-run-card">
      <div class="debug-inline">
        <span class="debug-pill"><strong>Intent:</strong> ${escapeHtml(payload.intent || "unknown")}</span>
        <span class="debug-pill"><strong>Router:</strong> ${escapeHtml(payload.trace?.router?.rationale || "n/a")}</span>
        <span class="debug-pill"><strong>Selected:</strong> ${escapeHtml((payload.trace?.generation?.selected_product_ids || []).join(", ") || "none")}</span>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Assistant Output</div>
        <div class="debug-block-copy">${escapeHtml(payload.content || "")}</div>
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Matches</div>
        ${matches || `<div class="debug-empty">No matches.</div>`}
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">LLM Context</div>
        ${
          payload.trace?.generation?.prompt_context
            ? `<pre class="debug-prompt">${escapeHtml(payload.trace.generation.prompt_context)}</pre>`
            : `<div class="debug-empty">No prompt context captured.</div>`
        }
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Steps</div>
        ${steps || `<div class="debug-empty">No steps recorded.</div>`}
      </div>

      <div class="debug-section-block">
        <div class="debug-block-label">Top Candidates</div>
        ${
          candidates
            ? `<table class="debug-table"><thead><tr><th>Product</th><th>Text semantic</th><th>Image semantic</th><th>Multimodal semantic</th><th>Fused</th></tr></thead><tbody>${candidates}</tbody></table>`
            : `<div class="debug-empty">No retrieval candidates.</div>`
        }
      </div>
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

filterEl.addEventListener("input", () => {
  const needle = filterEl.value.trim().toLowerCase();
  if (!needle) {
    renderProducts(products);
    return;
  }
  renderProducts(products.filter((product) => JSON.stringify(product).toLowerCase().includes(needle)));
});

loadDebugData();
