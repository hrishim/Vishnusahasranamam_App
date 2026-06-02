const queryInput = document.querySelector("#queryInput");
const searchButton = document.querySelector("#searchButton");
const copyButton = document.querySelector("#copyButton");
const clearButton = document.querySelector("#clearButton");
const output = document.querySelector("#output");
const meta = document.querySelector("#meta");
const status = document.querySelector("#status");
const helpButton = document.querySelector("#helpButton");
const helpDialog = document.querySelector("#helpDialog");
const closeHelpButton = document.querySelector("#closeHelpButton");
const modeButtons = Array.from(document.querySelectorAll(".mode-button"));

let activeMode = "entry";
let copyText = "";

function splitMetaLine(line) {
  const entryMatch = line.match(/^(Entry|Result|Sloka|Match)\s+\d+:\s*/);
  const label = entryMatch ? entryMatch[0].replace(/:\s*$/, "") : "";
  const rest = entryMatch ? line.slice(entryMatch[0].length) : line;
  return {
    label,
    parts: rest.split("|").map((part) => part.trim()).filter(Boolean),
  };
}

function renderMeta(text) {
  meta.replaceChildren();
  const lines = text.split(/\n+/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) {
    return;
  }

  const fragment = document.createDocumentFragment();
  lines.forEach((line) => {
    const row = document.createElement("div");
    row.className = "meta-row";
    const { label, parts } = splitMetaLine(line);
    if (label) {
      const labelChip = document.createElement("span");
      labelChip.className = "meta-label";
      labelChip.textContent = label;
      row.append(labelChip);
    }
    parts.forEach((part) => {
      const chip = document.createElement("span");
      const key = part.split(":")[0].trim().toLowerCase();
      chip.className = `meta-chip ${key === "ocr" ? "ocr-chip" : ""}`.trim();
      chip.textContent = part;
      row.append(chip);
    });
    fragment.append(row);
  });
  meta.append(fragment);
}

function setStatus(text, copied = false) {
  status.textContent = text;
  status.classList.toggle("copied", copied);
}

function setMode(mode) {
  activeMode = mode;
  modeButtons.forEach((button) => {
    const selected = button.dataset.mode === mode;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
  });
}

async function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type a nāma or phrase first");
    queryInput.focus();
    return;
  }

  setStatus("Searching...");
  output.textContent = "";
  meta.replaceChildren();
  copyText = "";

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, mode: activeMode }),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Search failed");
    }
    output.textContent = payload.display_text || "";
    renderMeta(payload.meta_text || "");
    copyText = payload.copy_text || "";
    setStatus("Ready");
  } catch (error) {
    output.textContent = error.message;
    setStatus("Error");
  }
}

async function copyOutput() {
  const text = copyText.trim();
  if (!text) {
    return;
  }
  await navigator.clipboard.writeText(text);
  const previous = copyButton.textContent;
  copyButton.textContent = "Copied";
  setStatus("Copied to clipboard", true);
  setTimeout(() => {
    copyButton.textContent = previous;
    setStatus("Ready");
  }, 1400);
}

function clearAll() {
  queryInput.value = "";
  output.textContent = "";
  meta.replaceChildren();
  copyText = "";
  setStatus("Ready");
  queryInput.focus();
}

modeButtons.forEach((button) => {
  button.addEventListener("click", () => setMode(button.dataset.mode));
});

searchButton.addEventListener("click", runSearch);
queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    runSearch();
  }
});
copyButton.addEventListener("click", copyOutput);
clearButton.addEventListener("click", clearAll);
helpButton.addEventListener("click", () => helpDialog.showModal());
closeHelpButton.addEventListener("click", () => helpDialog.close());

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js").catch(() => {});
}
