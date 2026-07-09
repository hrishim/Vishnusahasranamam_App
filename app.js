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
let data = null;
let devMap = new Map();
let romanMap = new Map();

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

async function loadData() {
  const response = await fetch("data/search-data.json");
  data = await response.json();
  buildMaps();
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

function entrySearch(query) {
  const dk = devKey(query);
  const rk = romanKey(query);
  let hits = [];
  if (dk && devMap.has(dk)) hits = devMap.get(dk);
  else if (rk && romanMap.has(rk)) hits = romanMap.get(rk);
  else if (rk) {
    hits = data.entries.filter((entry) => entry.keys.some((key) => key.startsWith(rk)));
  }
  if (!hits.length) return { display: "No nāma entry found.", copy: "" };
  const sections = hits.slice(0, 10).map((entry, index) => `Entry ${index + 1} - Nama: ${entry.number}\n\n${entry.text}`);
  const copies = hits.slice(0, 10).map((entry) => entry.text);
  return { display: sections.join("\n\n"), copy: copies.join("\n\n") };
}

function exactSearch(query) {
  const needle = query.trim().toLowerCase();
  const foldedNeedle = latinFold(query.trim());
  const sections = [];
  const copies = [];
  for (const entry of data.entries) {
    if (entry.text.toLowerCase().includes(needle) || latinFold(entry.text).includes(foldedNeedle)) {
      sections.push(`Match ${sections.length + 1} - Nama: ${entry.number}\n\n${entry.text}`);
      copies.push(entry.text);
    }
    if (sections.length >= 10) break;
  }
  if (sections.length < 10) {
    for (const sloka of data.slokas) {
      if (sloka.text.toLowerCase().includes(needle) || latinFold(sloka.text).includes(foldedNeedle)) {
        sections.push(`Match ${sections.length + 1} - Śloka ${sloka.number}\n\n${sloka.text}`);
        copies.push(sloka.text);
      }
      if (sections.length >= 10) break;
    }
  }
  if (!sections.length) return { display: "No exact matches found.", copy: "" };
  return { display: sections.join("\n\n"), copy: copies.join("\n\n") };
}

const instructionWords = new Set(["a", "an", "and", "are", "come", "comes", "define", "describe", "do", "does", "explain", "for", "from", "give", "how", "in", "is", "meaning", "of", "on", "please", "show", "tell", "the", "this", "to", "what", "where"]);
const expansions = { bagha: ["bhaga", "virtues", "six", "fold"], bhaga: ["virtues", "six", "fold"], vedas: ["veda", "trayi", "pranava"] };

function queryTerms(query) {
  const terms = [];
  for (const token of tokens(query)) {
    if (instructionWords.has(token)) continue;
    terms.push(token);
    if (expansions[token]) terms.push(...expansions[token]);
  }
  return [...new Set(terms)];
}

function answerSearch(query) {
  const terms = queryTerms(query);
  if (!terms.length) return { display: "No clear answer found in this text.", copy: "No clear answer found in this text." };
  const scored = data.passages.map((passage) => {
    const text = latinFold(passage.text);
    let score = 0;
    for (const term of terms) {
      if (text.includes(term)) score += term.length > 4 ? 2 : 1;
    }
    return { passage, score };
  }).filter((item) => item.score > 0).sort((a, b) => b.score - a.score).slice(0, 3);
  if (!scored.length || scored[0].score < 2) {
    const message = "No clear answer found in this text.";
    return { display: message, copy: message };
  }
  const bullets = [];
  const seen = new Set();
  for (const item of scored) {
    const parts = item.passage.text.replace(/(?<!\n)\n(?!\n)/g, " ").split(/(?<=[.!?।॥])\s+|\n{2,}/);
    const ranked = parts.map((sentence) => {
      const clean = sentence.trim();
      const folded = latinFold(clean);
      let overlap = 0;
      for (const term of terms) if (folded.includes(term)) overlap += 1;
      return { clean, overlap };
    }).filter((item) => item.clean.length > 30 && item.overlap > 0 && !seen.has(item.clean)).sort((a, b) => b.overlap - a.overlap);
    for (const sentence of ranked.slice(0, 2)) {
      seen.add(sentence.clean);
      bullets.push(`- ${sentence.clean}`);
      if (bullets.length >= 5) break;
    }
    if (bullets.length >= 5) break;
  }
  if (!bullets.length) {
    const message = "No clear answer found in this text.";
    return { display: message, copy: message };
  }
  const answer = `Answer:\n${bullets.join("\n")}`;
  return { display: answer, copy: answer };
}

function runSearch() {
  const query = queryInput.value.trim();
  if (!query) {
    setStatus("Type a nāma, exact phrase, or question first");
    queryInput.focus();
    return;
  }
  if (!data) {
    setStatus("Still loading...");
    return;
  }
  let result;
  if (activeMode === "entry") result = entrySearch(query);
  else if (activeMode === "exact") result = exactSearch(query);
  else result = answerSearch(query);
  output.textContent = result.display;
  copyText = result.copy;
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
  output.textContent = "";
  copyText = "";
  setStatus("Ready");
  queryInput.focus();
}

modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
searchButton.addEventListener("click", runSearch);
queryInput.addEventListener("keydown", (event) => { if (event.key === "Enter") runSearch(); });
copyButton.addEventListener("click", copyOutput);
clearButton.addEventListener("click", clearAll);
helpButton.addEventListener("click", () => helpDialog.showModal());
closeHelpButton.addEventListener("click", () => helpDialog.close());

if ("serviceWorker" in navigator) navigator.serviceWorker.register("service-worker.js").catch(() => {});
loadData().catch((error) => {
  output.textContent = `Could not load app data: ${error.message}`;
  setStatus("Error");
});
