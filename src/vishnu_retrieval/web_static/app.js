const queryInput = document.querySelector("#queryInput");
const searchButton = document.querySelector("#searchButton");
const copyButton = document.querySelector("#copyButton");
const clearButton = document.querySelector("#clearButton");
const output = document.querySelector("#output");
const status = document.querySelector("#status");
const helpButton = document.querySelector("#helpButton");
const helpDialog = document.querySelector("#helpDialog");
const closeHelpButton = document.querySelector("#closeHelpButton");
const modeButtons = Array.from(document.querySelectorAll(".mode-button"));

let activeMode = "entry";
let copyText = "";

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

function hasDevanagari(text) {
  return /[\u0900-\u097F]/.test(text);
}

function looksLikeTransliteration(text) {
  const clean = text.trim();
  const englishWords = /\b(the|one|who|word|means|lord|being|because|since|therefore|where|when|which|this|that|with|from|into|everything|pervades|if|then|does|not|know|knows|himself|herself|continues|form|other|until|every|all|called|there|are|is|as|it|he|she|you|we|they|their|his|her|in|of|and|or|to|by|for|on|basis|few|verses)\b/i;
  if (englishWords.test(clean)) return false;
  const words = clean.match(/[A-Za-zāīūṛṝḷṅñṭḍṇśṣḥṃĀĪŪṚṜḶṄÑṬḌṆŚṢḤ]+/g) || [];
  if (words.length > 9) return false;
  return /[āīūṛṝḷṅñṭḍṇśṣḥṃ]/i.test(clean) && !/[.!?]$/.test(clean);
}

function makeTextNode(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  output.appendChild(node);
}

function appendParagraphs(text) {
  const clean = text.replace(/\s+/g, " ").trim();
  if (!clean) return;
  const sentences = clean.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [clean];
  let current = "";
  for (const part of sentences) {
    const sentence = part.trim();
    const candidate = current ? `${current} ${sentence}` : sentence;
    if (current && candidate.length > 520) {
      makeTextNode("p", "result-paragraph", current);
      current = sentence;
    } else {
      current = candidate;
    }
  }
  if (current) {
    makeTextNode("p", "result-paragraph", current);
  }
}

function renderOutput(text) {
  document.body.classList.toggle("has-result", Boolean(String(text || "").trim()));
  output.textContent = "";
  const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
  let paragraph = [];

  function flushParagraph() {
    const clean = paragraph.join(" ").replace(/\s+/g, " ").trim();
    paragraph = [];
    appendParagraphs(clean);
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      const last = paragraph[paragraph.length - 1] || "";
      if (last && !/[.!?।॥:'"”)]$/.test(last)) {
        continue;
      }
      flushParagraph();
      continue;
    }
    if (/^(Entry|Match)\s+\d+\b/.test(line)) {
      flushParagraph();
      makeTextNode("h2", "result-heading", line);
      continue;
    }
    if (/^(Answer|Śloka)\b/.test(line)) {
      flushParagraph();
      makeTextNode("h3", "result-subheading", line);
      continue;
    }
    if (line.startsWith("- ")) {
      flushParagraph();
      makeTextNode("p", "result-bullet", line.slice(2).trim());
      continue;
    }
    if (hasDevanagari(line)) {
      flushParagraph();
      makeTextNode("div", "script-line", line);
      continue;
    }
    if (looksLikeTransliteration(line)) {
      flushParagraph();
      makeTextNode("div", "translit-line", line);
      continue;
    }
    paragraph.push(line);
  }
  flushParagraph();
}

async function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type a nāma or phrase first");
    queryInput.focus();
    return;
  }

  setStatus("Searching...");
  renderOutput("");
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
    renderOutput(payload.display_text || "");
    copyText = payload.copy_text || "";
    setStatus("Ready");
  } catch (error) {
    renderOutput(error.message);
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
  renderOutput("");
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
