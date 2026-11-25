let products = [];
let currentQuote = null;
let editingProductId = null;

const money = (value) => `$${Number(value || 0).toLocaleString("es-AR", {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
const pencilIcon = '<svg class="h-4 w-4" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m10.75 2.75 2.5 2.5M2.5 13.5l3.25-.75L13 5.5a1.77 1.77 0 0 0-2.5-2.5L3.25 10.25 2.5 13.5Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const trashIcon = '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4.5 6.5h15m-10.5 0v-2h6v2m-8.5 0 1 13h8l1-13M10 10v6m4-6v6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function toast(message) {
  const element = document.getElementById("toast");
  element.textContent = message;
  element.classList.remove("hidden");
  setTimeout(() => element.classList.add("hidden"), 2600);
}

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab-button").forEach((tab) => tab.className = "tab-button flex-1 whitespace-nowrap rounded-md px-4 py-2 text-slate-600");
    button.className = "tab-button flex-1 whitespace-nowrap rounded-md px-4 py-2 font-semibold text-blue-700 bg-blue-50";
    document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.add("hidden"));
    document.getElementById(`tab-${button.dataset.tab}`).classList.remove("hidden");
    if (button.dataset.tab === "catalog") loadProducts();
    if (button.dataset.tab === "history") loadHistory();
  });
});

async function loadProducts(search = "") {
  const response = await fetch("/api/products");
  products = await response.json();
  const term = search.toLowerCase();
  const filtered = products.filter((product) =>
    `${product.sku} ${product.name} ${product.aliases}`.toLowerCase().includes(term)
  );
  document.getElementById("products-body").innerHTML = filtered.map((product) => `
    <tr class="border-b">
      <td class="p-2 font-mono">${escapeHtml(product.sku)}</td>
      <td class="p-2">${escapeHtml(product.name)}</td>
      <td class="p-2">${money(product.unit_price)}</td>
      <td class="p-2">${product.stock_qty} ${escapeHtml(product.unit)}</td>
      <td class="p-2 text-right">
        <div class="inline-flex items-center gap-1">
          <button type="button" class="edit-product rounded p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900" data-id="${product.id}" aria-label="Modificar producto" title="Modificar producto">${pencilIcon}</button>
          <button type="button" class="delete-product rounded p-2 text-red-700 hover:bg-red-50" data-id="${product.id}" aria-label="Eliminar producto" title="Eliminar producto">${trashIcon}</button>
        </div>
      </td>
    </tr>`).join("");
  document.querySelectorAll(".edit-product").forEach((button) => {
    button.addEventListener("click", () => {
      const product = products.find((item) => item.id === Number(button.dataset.id));
      if (!product) return;

      editingProductId = product.id;
      document.getElementById("new-product-sku").value = product.sku;
      document.getElementById("new-product-name").value = product.name;
      document.getElementById("new-product-aliases").value = product.aliases;
      document.getElementById("new-product-unit").value = product.unit;
      document.getElementById("new-product-price").value = product.unit_price;
      document.getElementById("new-product-stock").value = product.stock_qty;
      document.getElementById("product-form-title").textContent = "Modificar producto";
      document.getElementById("save-product-btn").textContent = "Guardar cambios";
      document.getElementById("cancel-product-edit").classList.remove("hidden");
      document.getElementById("product-form").scrollIntoView({behavior: "smooth", block: "center"});
      document.getElementById("new-product-name").focus();
    });
  });
  document.querySelectorAll(".delete-product").forEach((button) => {
    button.addEventListener("click", async () => {
      if (button.dataset.confirming !== "true") {
        button.dataset.confirming = "true";
        button.innerHTML = "Confirmar";
        button.setAttribute("aria-label", "Confirmar eliminación");
        button.title = "Hacé clic otra vez para confirmar";
        button.classList.add("bg-red-100");
        button.dataset.confirmationTimer = String(window.setTimeout(() => {
          button.dataset.confirming = "false";
          button.innerHTML = trashIcon;
          button.setAttribute("aria-label", "Eliminar producto");
          button.title = "Eliminar producto";
          button.classList.remove("bg-red-100");
        }, 5000));
        return;
      }

      window.clearTimeout(Number(button.dataset.confirmationTimer));
      button.disabled = true;
      const response = await fetch(`/api/products/${button.dataset.id}`, {method: "DELETE"});
      if (!response.ok) {
        const error = await response.json();
        toast(typeof error.detail === "string" ? error.detail : "No se pudo eliminar el producto");
        return;
      }
      await loadProducts(document.getElementById("product-search").value);
      toast("Producto eliminado del catálogo");
    });
  });
}

document.getElementById("product-search").addEventListener("input", (event) => loadProducts(event.target.value));

function resetProductForm() {
  document.getElementById("product-form").reset();
  editingProductId = null;
  document.getElementById("product-form-title").textContent = "Agregar producto";
  document.getElementById("save-product-btn").textContent = "Guardar producto";
  document.getElementById("cancel-product-edit").classList.add("hidden");
}

document.getElementById("cancel-product-edit").addEventListener("click", resetProductForm);

document.getElementById("product-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const wasEditing = editingProductId !== null;
  const payload = {
    sku: document.getElementById("new-product-sku").value.trim(),
    name: document.getElementById("new-product-name").value.trim(),
    aliases: document.getElementById("new-product-aliases").value.trim(),
    unit: document.getElementById("new-product-unit").value.trim() || "unidad",
    unit_price: Number(document.getElementById("new-product-price").value),
    stock_qty: Number(document.getElementById("new-product-stock").value),
  };
  let response;
  try {
    response = await fetch(wasEditing ? `/api/products/${editingProductId}` : "/api/products", {
      method: wasEditing ? "PUT" : "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
  } catch {
    toast("No se pudo conectar con el servidor");
    return;
  }
  if (!response.ok) {
    const error = await response.json();
    toast(typeof error.detail === "string" ? error.detail : "Revisá los datos del producto");
    return;
  }
  const updated = wasEditing || response.status === 200;
  resetProductForm();
  await loadProducts(document.getElementById("product-search").value);
  toast(updated ? "Producto actualizado y activado" : "Producto agregado al catálogo");
});

async function parseMessage() {
  const message = document.getElementById("message").value.trim();
  if (!message) {
    toast("Ingresá un mensaje para cotizar");
    return;
  }
  const button = document.getElementById("parse-btn");
  button.disabled = true;
  button.textContent = "Procesando...";
  try {
    const response = await fetch("/api/quotes/parse-message", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        message,
        customer_name: document.getElementById("customer-name").value || null,
        customer_phone: document.getElementById("customer-phone").value || null,
        discount_pct: Number(document.getElementById("discount").value || 0),
      }),
    });
    if (!response.ok) throw new Error(await response.text());
    currentQuote = await response.json();
    await loadProducts();
    renderQuote();
  } catch (error) {
    toast("No se pudo crear el presupuesto");
  } finally {
    button.disabled = false;
    button.textContent = "Analizar y crear presupuesto";
  }
}

document.getElementById("parse-btn").addEventListener("click", parseMessage);

function renderQuote() {
  document.getElementById("quote-editor").classList.remove("hidden");
  document.getElementById("quote-number").textContent = currentQuote.quote_number;
  document.getElementById("quote-total").textContent = money(currentQuote.total);
  const body = document.getElementById("items-body");
  body.innerHTML = "";
  currentQuote.items.forEach((item, index) => {
    const row = document.createElement("tr");
    row.className = item.needs_review ? "bg-yellow-50" : "border-b";
    row.innerHTML = `
      <td class="p-2">
        <select class="product-select w-full min-w-52 rounded border border-slate-300 p-2" data-index="${index}">
          <option value="">Seleccionar producto</option>
          ${products.map((product) => `<option value="${product.id}" ${product.id === item.product_id ? "selected" : ""}>${escapeHtml(product.name)}</option>`).join("")}
        </select>
      </td>
      <td class="p-2"><input class="item-description w-full rounded border border-slate-300 p-2" value="${escapeHtml(item.description)}" data-index="${index}"></td>
      <td class="p-2"><input type="number" min="0.01" step="0.01" class="item-quantity w-24 rounded border border-slate-300 p-2" value="${item.quantity}" data-index="${index}"></td>
      <td class="p-2"><input class="item-unit w-24 rounded border border-slate-300 p-2" value="${escapeHtml(item.unit)}" data-index="${index}"></td>
      <td class="p-2"><input type="number" min="0" step="0.01" class="item-price w-28 rounded border border-slate-300 p-2" value="${item.unit_price}" data-index="${index}"></td>
      <td class="p-2"><button type="button" class="delete-item text-red-600" data-index="${index}">Eliminar</button></td>`;
    body.appendChild(row);
  });
  bindItemEvents();
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value || "";
  return div.innerHTML.replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function bindItemEvents() {
  document.querySelectorAll(".product-select").forEach((select) => select.addEventListener("change", async (event) => {
    const index = Number(event.target.dataset.index);
    currentQuote.items[index].product_id = event.target.value ? Number(event.target.value) : null;
    if (event.target.value) {
      const product = products.find((candidate) => candidate.id === Number(event.target.value));
      if (product) {
        const row = event.target.closest("tr");
        row.querySelector(".item-description").value = product.name;
        row.querySelector(".item-unit").value = product.unit;
        row.querySelector(".item-price").value = product.unit_price;
      }
    }
    await saveQuote();
  }));
  document.querySelectorAll(".item-description,.item-quantity,.item-unit,.item-price").forEach((input) => {
    input.addEventListener("change", saveQuote);
  });
  document.querySelectorAll(".delete-item").forEach((button) => button.addEventListener("click", async (event) => {
    const index = Number(event.target.dataset.index);
    currentQuote.items[index].delete = true;
    await saveQuote();
  }));
}

async function saveQuote() {
  if (!currentQuote) return;
  const body = {
    customer_name: document.getElementById("customer-name").value || null,
    customer_phone: document.getElementById("customer-phone").value || null,
    discount_pct: Number(document.getElementById("discount").value || 0),
    items: currentQuote.items.map((item, index) => ({
      id: item.id,
      product_id: item.product_id,
      description: document.querySelector(`.item-description[data-index="${index}"]`)?.value,
      quantity: Number(document.querySelector(`.item-quantity[data-index="${index}"]`)?.value || item.quantity),
      unit: document.querySelector(`.item-unit[data-index="${index}"]`)?.value,
      unit_price: Number(document.querySelector(`.item-price[data-index="${index}"]`)?.value || item.unit_price),
      delete: Boolean(item.delete),
    })),
  };
  const response = await fetch(`/api/quotes/${currentQuote.id}`, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    toast("No se pudo guardar el presupuesto");
    return;
  }
  currentQuote = await response.json();
  await loadProducts();
  renderQuote();
}

document.getElementById("add-item").addEventListener("click", () => {
  currentQuote.items.push({
    id: null,
    product_id: null,
    description: "",
    quantity: 1,
    unit: "unidad",
    unit_price: 0,
    needs_review: true,
  });
  renderQuote();
});

document.getElementById("download-pdf").addEventListener("click", async () => {
  await saveQuote();
  window.open(`/api/quotes/${currentQuote.id}/pdf`, "_blank");
});

document.getElementById("copy-whatsapp").addEventListener("click", async () => {
  await saveQuote();
  const lines = [
    `Presupuesto ${currentQuote.quote_number}`,
    `Cliente: ${currentQuote.customer_name || "Consumidor final"}`,
    "",
    ...currentQuote.items.map((item) => `${item.quantity} ${item.unit} ${item.description} - ${money(item.subtotal)}`),
    "",
    `Subtotal: ${money(currentQuote.subtotal)}`,
    `Descuento: ${currentQuote.discount_pct}%`,
    `Total: ${money(currentQuote.total)}`,
  ];
  await navigator.clipboard.writeText(lines.join("\n"));
  toast("Mensaje copiado");
});

document.getElementById("import-btn").addEventListener("click", async () => {
  const file = document.getElementById("catalog-file").files[0];
  if (!file) {
    toast("Seleccioná un archivo");
    return;
  }
  const form = new FormData();
  form.append("file", file);
  form.append("replace_all", document.getElementById("replace-all").checked ? "true" : "false");
  const response = await fetch("/api/products/import", {method: "POST", body: form});
  if (!response.ok) {
    const error = await response.json();
    toast(error.detail || "Error al importar");
    return;
  }
  const result = await response.json();
  toast(`Importación completa: ${result.created} nuevos, ${result.updated} actualizados`);
  await loadProducts(document.getElementById("product-search").value);
});

async function loadHistory() {
  const response = await fetch("/api/quotes");
  const quotes = await response.json();
  document.getElementById("history-list").innerHTML = quotes.length ? quotes.map((quote) => `
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-4">
      <div><strong>${escapeHtml(quote.quote_number)}</strong><div class="text-sm text-slate-500">${escapeHtml(quote.customer_name || "Consumidor final")} · ${money(quote.total)} · ${escapeHtml(quote.status)}</div></div>
      <button type="button" class="history-pdf rounded-md bg-blue-700 px-3 py-2 text-sm font-semibold text-white" data-id="${quote.id}">Descargar PDF</button>
    </div>`).join("") : '<p class="text-slate-500">Todavía no hay presupuestos.</p>';
  document.querySelectorAll(".history-pdf").forEach((button) => button.addEventListener("click", () => {
    window.open(`/api/quotes/${button.dataset.id}/pdf`, "_blank");
  }));
}
