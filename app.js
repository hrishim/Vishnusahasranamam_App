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
const namaList = document.querySelector("#namaList");
const namaCount = document.querySelector("#namaCount");
const namaFilter = document.querySelector("#namaFilter");
const APP_VERSION = "v15";

let activeMode = "entry";
let copyText = "";
let data = null;
let devMap = new Map();
let romanMap = new Map();
let selectedNamaNumber = null;

function setStatus(text, copied = false) {
  status.textContent = text;
  status.classList.toggle("copied", copied);
}

function latinFold(text) {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function romanKey(text) {
  let folded = latinFold(text);
  folded = folded.replaceAll("sh", "s").replaceAll("si", "shi").replaceAll("sri", "shri");
  folded = folded.replace(/[^a-z]/g, "");
  return folded.endsWith("h") ? folded.slice(0, -1) : folded;
}

function devKey(text) {
  return text.replaceAll(":", "ः").replace(/[^\u0900-\u097F]/g, "");
}

function tokens(text) {
  return latinFold(text).match(/[a-z0-9\u0900-\u097F]+/g) || [];
}

function parseSlokaNumber(query) {
  const devanagariDigits = "०१२३४५६७८९";
  const normalized = query.trim().replace(/[०-९]/g, (digit) => String(devanagariDigits.indexOf(digit)));
  const patterns = [
    /^([0-9]{1,3})$/,
    /^(?:sloka|shloka|śloka|verse|श्लोक|श्लोका)\s*[:#.\-]?\s*([0-9]{1,3})$/i,
    /^([0-9]{1,3})\s*(?:sloka|shloka|śloka|verse|श्लोक|श्लोका)$/i,
  ];
  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match) {
      const number = Number(match[1]);
      if (Number.isInteger(number) && number >= 1 && number <= 108) {
        return number;
      }
    }
  }
  return null;
}

function parseNamaNumber(query) {
  const devanagariDigits = "०१२३४५६७८९";
  const normalized = query.trim().replace(/[०-९]/g, (digit) => String(devanagariDigits.indexOf(digit)));
  const patterns = [
    /^([0-9]{1,4})$/,
    /^(?:nama|naama|nāma|name|नाम|नामा)\s*[:#.\-]?\s*([0-9]{1,4})$/i,
    /^([0-9]{1,4})\s*(?:nama|naama|nāma|name|नाम|नामा)$/i,
  ];
  for (const pattern of patterns) {
    const match = normalized.match(pattern);
    if (match) {
      const number = Number(match[1]);
      if (Number.isInteger(number) && number >= 1 && number <= 1000) {
        return number;
      }
    }
  }
  return null;
}

function buildMaps() {
  devMap = new Map();
  romanMap = new Map();
  for (const entry of data.entries) {
    for (const key of entry.devKeys || [entry.devKey]) {
      if (!devMap.has(key)) devMap.set(key, []);
      devMap.get(key).push(entry);
    }
    for (const key of entry.keys || []) {
      if (!romanMap.has(key)) romanMap.set(key, []);
      romanMap.get(key).push(entry);
    }
  }
}

function setSelectedNama(number) {
  selectedNamaNumber = number;
  if (!namaList) return;
  for (const button of namaList.querySelectorAll(".nama-list-item")) {
    const selected = Number(button.dataset.number) === number;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  }
}

function renderNamaList() {
  if (!namaList || !data) return;
  namaList.textContent = "";
  const filterText = namaFilter ? namaFilter.value.trim() : "";
  const filterNumber = filterText.replace(/\D+/g, "");
  const filterDevanagari = devKey(filterText);
  const entries = [...data.entries].sort((left, right) => left.number - right.number);
  const visibleEntries = entries.filter((entry) => {
    if (filterNumber && !String(entry.number).startsWith(filterNumber)) return false;
    if (filterDevanagari && !entry.devanagari.includes(filterDevanagari)) return false;
    return true;
  });
  for (const entry of visibleEntries) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "nama-list-item";
    button.dataset.number = String(entry.number);
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", "false");

    const number = document.createElement("span");
    number.className = "nama-number";
    number.textContent = String(entry.number);

    const name = document.createElement("span");
    name.className = "nama-name";
    name.textContent = entry.devanagari;

    button.append(number, name);
    button.addEventListener("click", () => openNama(entry.number));
    namaList.appendChild(button);
  }
  namaCount.textContent = filterText ? `${visibleEntries.length}/1000` : `${entries.length}/1000`;
  if (entries.length !== 1000) {
    namaCount.classList.add("warning");
    setStatus("Nāma list incomplete");
  }
  setSelectedNama(selectedNamaNumber);
}

function openNama(number) {
  if (!data) return;
  setMode("entry");
  queryInput.value = `nāma ${number}`;
  const result = entrySearch(String(number));
  renderOutput(result.display);
  copyText = result.copy;
  setSelectedNama(number);
  setStatus(`Nāma ${number}`);
}

async function loadData() {
  const response = await fetch(`data/search-data.json?${APP_VERSION}`, { cache: "reload" });
  data = await response.json();
  buildMaps();
  renderNamaList();
  setStatus("Ready");
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

function entrySearch(query) {
  const number = parseNamaNumber(query);
  if (number !== null) {
    const entry = data.entries.find((item) => item.number === number);
    if (!entry) return { display: "No nāma entry found.", copy: "" };
    return { display: `Nama: ${entry.number}\n\n${entry.text}`, copy: entry.text };
  }
  const dk = devKey(query);
  const rk = romanKey(query);
  let hits = [];
  if (dk && devMap.has(dk)) hits = devMap.get(dk);
  else if (rk && romanMap.has(rk)) hits = romanMap.get(rk);
  else if (rk) {
    hits = data.entries.filter((entry) => entry.keys.some((key) => key.startsWith(rk)));
  }
  if (!hits.length) return { display: "No nāma entry found.", copy: "" };
  const selected = hits.slice(0, 10);
  const sections = selected.map((entry) => `Nama: ${entry.number}\n\n${entry.text}`);
  const copies = selected.map((entry) => entry.text);
  return { display: sections.join("\n\n"), copy: copies.join("\n\n") };
}

function slokaSearch(query) {
  const number = parseSlokaNumber(query);
  if (number !== null) {
    const sloka = data.slokas.find((item) => item.number === number);
    if (!sloka) return { display: "No śloka found.", copy: "" };
    return { display: `Śloka ${sloka.number}\n\n${sloka.text}`, copy: sloka.text };
  }
  const needle = query.trim().toLowerCase();
  const foldedNeedle = latinFold(query.trim());
  const hits = [];
  for (const sloka of data.slokas) {
    if (sloka.text.toLowerCase().includes(needle) || latinFold(sloka.text).includes(foldedNeedle)) {
      hits.push(sloka);
    }
    if (hits.length >= 10) break;
  }
  if (!hits.length) return { display: "No śloka found.", copy: "" };
  return {
    display: hits.map((sloka) => `Śloka ${sloka.number}\n\n${sloka.text}`).join("\n\n"),
    copy: hits.map((sloka) => sloka.text).join("\n\n"),
  };
}

function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type a nāma or śloka first");
    queryInput.focus();
    return;
  }
  if (!data) {
    setStatus("Still loading...");
    return;
  }
  let result;
  if (activeMode === "sloka") result = slokaSearch(query);
  else result = entrySearch(query);
  renderOutput(result.display);
  copyText = result.copy;
  setSelectedNama(activeMode === "entry" ? parseNamaNumber(query) : null);
  setStatus("Ready");
}

async function copyOutput() {
  const text = copyText.trim();
  if (!text) return;
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
  setSelectedNama(null);
  setStatus("Ready");
  queryInput.focus();
}

modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
searchButton.addEventListener("click", runSearch);
queryInput.addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
if (namaFilter) namaFilter.addEventListener("input", renderNamaList);
copyButton.addEventListener("click", copyOutput);
clearButton.addEventListener("click", clearAll);
helpButton.addEventListener("click", () => helpDialog.showModal());
closeHelpButton.addEventListener("click", () => helpDialog.close());

if ("serviceWorker" in navigator) navigator.serviceWorker.register(`service-worker.js?${APP_VERSION}`).catch(() => {});
loadData().catch((error) => {
  renderOutput(`Could not load app data: ${error.message}`);
  setStatus("Error");
});
