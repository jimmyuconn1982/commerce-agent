const STORAGE_KEY = "commerce-agent-web-state-v3";

const defaultUsers = [
  { id: "maya", name: "Maya Chen", role: "Trend shopper" },
  { id: "daniel", name: "Daniel Park", role: "Home office upgrader" },
  { id: "sofia", name: "Sofia Rivera", role: "Outdoor gear explorer" },
];

const el = {
  userList: document.querySelector("#user-list"),
  chatList: document.querySelector("#chat-list"),
  messages: document.querySelector("#messages"),
  newChatBtn: document.querySelector("#new-chat-btn"),
  sendBtn: document.querySelector("#send-btn"),
  promptInput: document.querySelector("#prompt-input"),
  imageInput: document.querySelector("#image-input"),
  imageUrlInput: document.querySelector("#image-url-input"),
  urlChip: document.querySelector("#url-chip"),
  attachToggle: document.querySelector("#attach-toggle"),
  attachPopover: document.querySelector("#attach-popover"),
  attachImageBtn: document.querySelector("#attach-image-btn"),
  attachUrlBtn: document.querySelector("#attach-url-btn"),
  simUserToggle: document.querySelector("#sim-user-toggle"),
  debugToggle: document.querySelector("#debug-toggle"),
  userPopover: document.querySelector("#user-popover"),
  attachmentPreview: document.querySelector("#attachment-preview"),
  messageTemplate: document.querySelector("#message-template"),
};

let state = loadState();

function loadState() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    return JSON.parse(saved);
  }
  const firstChat = createChat("maya", "Welcome Session");
  return {
    users: defaultUsers,
    chatsByUser: { maya: [firstChat], daniel: [], sofia: [] },
    activeUserId: "maya",
    activeChatId: firstChat.id,
    debugEnabled: false,
  };
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function createChat(userId, title = "New Chat") {
  return {
    id: crypto.randomUUID(),
    title,
    createdAt: new Date().toISOString(),
    messages: [
      {
        id: crypto.randomUUID(),
        speaker: "assistant",
        mode: "system",
        content: "Start with chat, text search, image search, or multimodal search.",
      },
    ],
  };
}

function currentUser() {
  return state.users.find((user) => user.id === state.activeUserId);
}

function currentChats() {
  return state.chatsByUser[state.activeUserId] ?? [];
}

function currentChat() {
  return currentChats().find((chat) => chat.id === state.activeChatId) ?? null;
}

function renderUsers() {
  el.userList.innerHTML = "";
  for (const user of state.users) {
    const button = document.createElement("button");
    button.className = `user-card${user.id === state.activeUserId ? " active" : ""}`;
    button.innerHTML = `
      <span class="card-title">${user.name}</span>
      <span class="card-meta">${user.role}</span>
    `;
    button.addEventListener("click", () => {
      state.activeUserId = user.id;
      if (!currentChats().length) {
        const chat = createChat(user.id, `${user.name.split(" ")[0]}'s Chat`);
        state.chatsByUser[user.id] = [chat];
        state.activeChatId = chat.id;
      } else if (!currentChat()) {
        state.activeChatId = currentChats()[0].id;
      }
      el.userPopover.classList.add("hidden");
      persistAndRender();
    });
    el.userList.appendChild(button);
  }
}

function renderChats() {
  el.chatList.innerHTML = "";
  for (const chat of currentChats()) {
    const item = document.createElement("div");
    item.className = `chat-card${chat.id === state.activeChatId ? " active" : ""}`;

    const button = document.createElement("button");
    button.className = "chat-select";
    button.type = "button";
    button.innerHTML = `
      <span class="card-title">${chat.title}</span>
      <span class="card-meta">${chat.messages.length} messages</span>
    `;
    button.addEventListener("click", () => {
      state.activeChatId = chat.id;
      persistAndRender();
    });

    const deleteButton = document.createElement("button");
    deleteButton.className = "chat-delete";
    deleteButton.type = "button";
    deleteButton.setAttribute("aria-label", "Delete chat");
    deleteButton.textContent = "×";
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteChat(chat.id);
    });

    item.appendChild(button);
    item.appendChild(deleteButton);
    el.chatList.appendChild(item);
  }
}

function renderMessages() {
  const chat = currentChat();
  el.messages.innerHTML = "";
  el.debugToggle.checked = Boolean(state.debugEnabled);

  if (!chat) {
    return;
  }

  const hasOnlySystem = chat.messages.length === 1 && chat.messages[0].mode === "system";
  if (hasOnlySystem) {
    const emptyState = document.createElement("section");
    emptyState.className = "empty-state";
    emptyState.innerHTML = `
      <div>
        <h1>How can I help?</h1>
        <p>Chat, search by text, image, or both.</p>
      </div>
    `;
    el.messages.appendChild(emptyState);
  }

  for (const message of chat.messages) {
    if (hasOnlySystem && message.mode === "system") {
      continue;
    }
    const node = el.messageTemplate.content.firstElementChild.cloneNode(true);
    node.classList.add(message.speaker);
    renderMessageBody(node.querySelector(".message-body"), message);
    el.messages.appendChild(node);
  }
  el.messages.scrollTop = el.messages.scrollHeight;
}

function renderMessageBody(container, message) {
  container.innerHTML = "";
  if (message.content) {
    const text = document.createElement("div");
    text.textContent = message.content;
    container.appendChild(text);
  }

  if (message.attachments?.length) {
    const stack = document.createElement("div");
    stack.className = "attachment-stack";
    for (const attachment of message.attachments) {
      const tile = document.createElement("div");
      tile.className = "attachment-tile";
      tile.innerHTML = `
        <img src="${attachment.previewUrl}" alt="${attachment.label}" />
        <span class="attachment-caption">${attachment.label}</span>
      `;
      stack.appendChild(tile);
    }
    container.appendChild(stack);
  }

  if (message.analysis) {
    const analysis = document.createElement("div");
    analysis.className = "analysis-strip";
    analysis.innerHTML = `
      <div class="analysis-chip">
        <strong>Image Summary</strong>
        <span>${message.analysis.summary}</span>
      </div>
      <div class="analysis-chip">
        <strong>Image Tags</strong>
        <span>${(message.analysis.tags || []).join(", ") || "None"}</span>
      </div>
    `;
    container.appendChild(analysis);
  }

  if (message.matches?.length) {
    const results = document.createElement("div");
    results.className = "search-results";
    for (const product of message.matches) {
      const card = document.createElement("div");
      card.className = "result-card";
      card.innerHTML = `
        <div class="result-top">
          <img class="result-image" src="${product.image_url}" alt="${product.name}" />
          <div class="result-copy">
            <div class="result-row">
              <strong>${product.name}</strong>
              <span class="result-price">${formatPrice(product.price, product.currency)}</span>
            </div>
            <div class="result-meta-row">
              <span class="result-meta">${product.category}</span>
              <span class="result-meta">${product.seller_name || "Unknown seller"}</span>
              <span class="result-meta">${formatReview(product.review_count, product.seller_rating)}</span>
              <span class="result-meta">inventory ${product.inventory_count ?? 0}</span>
            </div>
          </div>
        </div>
        <div class="result-desc">${product.description}</div>
        ${product.product_url ? `<a class="result-link" href="${product.product_url}" target="_blank" rel="noreferrer">Open product</a>` : ""}
      `;
      results.appendChild(card);
    }
    container.appendChild(results);
  }

  if (message.trace && state.debugEnabled) {
    const debug = document.createElement("section");
    debug.className = "debug-trace";
    const steps = (message.trace.react?.steps || [])
      .map(
        (step) => `
          <div class="debug-step">
            <div class="debug-step-head">
              <span class="debug-step-title">${step.tool_name}</span>
            </div>
            <div class="debug-step-copy">${step.thought}</div>
            <div class="debug-step-copy"><strong>In:</strong> ${step.input_summary}</div>
            <div class="debug-step-copy"><strong>Out:</strong> ${step.observation_summary}</div>
          </div>
        `,
      )
      .join("");

    const retrievalRows = (message.trace.retrieval?.candidates || [])
      .slice(0, 5)
      .map(
        (candidate) => `
          <tr>
            <td>${candidate.product.name}</td>
            <td>${Number(candidate.score).toFixed(4)}</td>
            <td>${Number(candidate.text_score).toFixed(4)}</td>
            <td>${Number(candidate.image_score).toFixed(4)}</td>
          </tr>
        `,
      )
      .join("");

    debug.innerHTML = `
      <div class="debug-head">Pipeline trace</div>
      <div class="debug-inline">
        <span class="debug-pill"><strong>Intent:</strong> ${message.trace.router?.intent || "unknown"}</span>
        <span class="debug-pill"><strong>Router:</strong> ${message.trace.router?.rationale || "n/a"}</span>
      </div>
      <div class="debug-section">
        <div class="debug-label">Steps</div>
        ${steps || '<div class="debug-step-copy">No steps recorded.</div>'}
      </div>
      <div class="debug-section">
        <div class="debug-label">Top Candidates</div>
        ${
          retrievalRows
            ? `<table class="debug-table"><thead><tr><th>Product</th><th>Score</th><th>Text</th><th>Image</th></tr></thead><tbody>${retrievalRows}</tbody></table>`
            : '<div class="debug-step-copy">No retrieval candidates.</div>'
        }
      </div>
    `;
    container.appendChild(debug);
  }
}

function persistAndRender() {
  saveState();
  renderUsers();
  renderChats();
  renderMessages();
}

function deleteChat(chatId) {
  const chats = currentChats();
  const index = chats.findIndex((chat) => chat.id === chatId);
  if (index === -1) {
    return;
  }

  chats.splice(index, 1);

  if (!chats.length) {
    const replacement = createChat(state.activeUserId, "New Chat");
    state.chatsByUser[state.activeUserId] = [replacement];
    state.activeChatId = replacement.id;
    persistAndRender();
    return;
  }

  if (state.activeChatId === chatId) {
    const fallback = chats[Math.max(0, index - 1)] ?? chats[0];
    state.activeChatId = fallback.id;
  }

  persistAndRender();
}

function appendMessage(message) {
  const chat = currentChat();
  if (!chat) {
    return;
  }
  chat.messages.push({ id: crypto.randomUUID(), ...message });
  if (chat.title === "New Chat" || chat.title === "Welcome Session") {
    chat.title = message.content.slice(0, 28) || "Untitled Chat";
  }
  persistAndRender();
}

async function sendCurrentMessage() {
  const prompt = el.promptInput.value.trim();
  const file = el.imageInput.files[0] ?? null;
  const imageUrl = el.imageUrlInput.value.trim();

  if (!prompt && !file && !imageUrl) {
    return;
  }

  const attachments = buildAttachments(file, imageUrl);

  appendMessage({
    speaker: "user",
    mode: "user",
    content: prompt,
    attachments,
  });

  el.promptInput.value = "";
  el.imageInput.value = "";
  el.imageUrlInput.value = "";
  renderAttachmentPreview();
  autoResizePrompt();

  el.sendBtn.disabled = true;

  try {
    const response = await invokeMessage(prompt, file, imageUrl);
    appendMessage({
      speaker: "assistant",
      mode: response.intent,
      content: response.content,
      analysis: response.analysis,
      matches: response.matches,
      trace: response.trace,
    });
  } catch (error) {
    appendMessage({
      speaker: "assistant",
      mode: "error",
      content: error.message,
    });
  } finally {
    el.sendBtn.disabled = false;
  }
}

async function invokeMessage(prompt, file, imageUrl) {
  const form = new FormData();
  form.append("text", prompt);
  form.append("limit", "5");
  if (file) {
    form.append("file", file);
  }
  if (imageUrl) {
    form.append("image_url", imageUrl);
  }
  return fetchJson("/api/message", { method: "POST", body: form });
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function buildAttachments(file, imageUrl) {
  const attachments = [];
  if (file) {
    attachments.push({
      kind: "file",
      label: file.name,
      previewUrl: URL.createObjectURL(file),
    });
  }
  if (imageUrl) {
    attachments.push({
      kind: "url",
      label: imageUrl,
      previewUrl: imageUrl,
    });
  }
  return attachments;
}

function renderAttachmentPreview() {
  const file = el.imageInput.files[0] ?? null;
  const imageUrl = el.imageUrlInput.value.trim();
  const attachments = buildAttachments(file, imageUrl);
  el.attachmentPreview.innerHTML = "";
  el.urlChip.classList.toggle("hidden", !imageUrl);

  if (!attachments.length) {
    el.attachmentPreview.classList.add("hidden");
    return;
  }

  for (const attachment of attachments) {
    const node = document.createElement("div");
    node.className = "preview-card";
    node.innerHTML = `
      <img src="${attachment.previewUrl}" alt="${attachment.label}" />
      <div class="preview-copy">
        <div class="preview-title">${attachment.kind === "url" ? "Image URL" : "Local image"}</div>
        <div class="preview-subtitle">${attachment.label}</div>
      </div>
      <button class="clear-preview" type="button" aria-label="Remove">×</button>
    `;
    node.querySelector(".clear-preview").addEventListener("click", () => {
      if (attachment.kind === "file") {
        el.imageInput.value = "";
      } else {
        el.imageUrlInput.value = "";
      }
      renderAttachmentPreview();
    });
    el.attachmentPreview.appendChild(node);
  }
  el.attachmentPreview.classList.remove("hidden");
}

function formatPrice(price, currency) {
  if (price == null) {
    return "";
  }
  const amount = Number(price);
  if (Number.isNaN(amount)) {
    return `${price} ${currency || ""}`.trim();
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatReview(reviewCount, sellerRating) {
  const parts = [];
  if (sellerRating != null) {
    parts.push(`seller ${Number(sellerRating).toFixed(1)}`);
  }
  if (reviewCount != null) {
    parts.push(`${reviewCount} reviews`);
  }
  return parts.join(" · ");
}

function autoResizePrompt() {
  el.promptInput.style.height = "auto";
  el.promptInput.style.height = `${Math.min(el.promptInput.scrollHeight, 220)}px`;
}

el.newChatBtn.addEventListener("click", () => {
  const user = currentUser();
  const chat = createChat(user.id, "New Chat");
  state.chatsByUser[user.id].unshift(chat);
  state.activeChatId = chat.id;
  persistAndRender();
});

el.sendBtn.addEventListener("click", () => {
  void sendCurrentMessage();
});

el.promptInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent?.isComposing) {
    event.preventDefault();
    void sendCurrentMessage();
  }
});

el.promptInput.addEventListener("input", () => {
  autoResizePrompt();
});

el.imageInput.addEventListener("change", () => {
  renderAttachmentPreview();
});

el.imageUrlInput.addEventListener("input", () => {
  renderAttachmentPreview();
});

el.attachToggle.addEventListener("click", () => {
  el.attachPopover.classList.toggle("hidden");
});

el.attachImageBtn.addEventListener("click", () => {
  el.attachPopover.classList.add("hidden");
  el.imageInput.click();
});

el.attachUrlBtn.addEventListener("click", () => {
  el.attachPopover.classList.add("hidden");
  el.urlChip.classList.remove("hidden");
  el.imageUrlInput.focus();
});

el.simUserToggle.addEventListener("click", () => {
  el.userPopover.classList.toggle("hidden");
});

el.debugToggle.addEventListener("change", () => {
  state.debugEnabled = el.debugToggle.checked;
  persistAndRender();
});

document.addEventListener("click", (event) => {
  if (!el.attachPopover.contains(event.target) && !el.attachToggle.contains(event.target)) {
    el.attachPopover.classList.add("hidden");
  }
  if (!el.userPopover.contains(event.target) && !el.simUserToggle.contains(event.target)) {
    el.userPopover.classList.add("hidden");
  }
});

persistAndRender();
autoResizePrompt();
renderAttachmentPreview();
