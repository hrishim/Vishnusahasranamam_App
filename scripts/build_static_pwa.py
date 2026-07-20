#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from vishnu_retrieval.canonical import load_canonical_namas
from vishnu_retrieval.desktop_app import entry_body_with_clean_heading, normalize_for_word
from vishnu_retrieval.io import INDEX_JSON, PAGES_JSONL, SLOKAS_JSON
from vishnu_retrieval.search import canonical_alias_keys, extract_entry_by_number


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "pwa"
STATIC = ROOT / "src" / "vishnu_retrieval" / "web_static"


def strip_page_refs(text: str) -> str:
    text = re.sub(r"\s*\[p\. \d+\]", "", text)
    text = re.sub(r"(?m)^.*\bPages?:\s*\d+(?:-\d+)?.*$\n?", "", text)
    return text.strip()


def dev_key(text: str) -> str:
    return re.sub(r"[^\u0900-\u097F]", "", str(text).replace(":", "ः"))


def dev_key_variants(text: str) -> list[str]:
    key = dev_key(text)
    variants = {key}
    if key.endswith("ः"):
        variants.add(key[:-1])
        variants.add(key[:-1] + "ो")
    if key.endswith("ो"):
        variants.add(key[:-1])
        variants.add(key[:-1] + "ः")
    return sorted(item for item in variants if item)


def build_entries() -> list[dict]:
    entries: list[dict] = []
    for row in load_canonical_namas():
        number = int(row["number"])
        hits = extract_entry_by_number(number, PAGES_JSONL, window_after=5)
        if not hits:
            text = f'{row["devanagari"]} {row["roman"]} ({number})'
        else:
            text = entry_body_with_clean_heading(hits[0])
        entries.append(
            {
                "number": number,
                "devanagari": row["devanagari"],
                "roman": row["roman"],
                "sourceTitle": row.get("source_title", ""),
                "devKey": dev_key(row["devanagari"]),
                "devKeys": dev_key_variants(row["devanagari"]),
                "keys": sorted(canonical_alias_keys(row)),
                "text": strip_page_refs(text),
            }
        )
    return entries


def build_slokas() -> list[dict]:
    payload = json.loads(SLOKAS_JSON.read_text(encoding="utf-8"))
    return [
        {
            "number": item["number"],
            "devanagari": normalize_for_word(item.get("devanagari", "")),
            "roman": normalize_for_word(item.get("roman", "")),
            "text": normalize_for_word("\n\n".join(part for part in (item.get("devanagari", ""), item.get("roman", "")) if part)),
        }
        for item in payload.get("slokas", [])
    ]


def build_passages() -> list[dict]:
    payload = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    passages: list[dict] = []
    for chunk in payload.get("chunks", []):
        text = normalize_for_word(chunk.get("text", ""))
        if len(text) < 80:
            continue
        passages.append(
            {
                "id": chunk.get("chunk_id", ""),
                "text": strip_page_refs(text),
            }
        )
    return passages


INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="theme-color" content="#244f7a">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="Vishnu">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <title>Vishnusahasranamam</title>
    <link rel="manifest" href="manifest.webmanifest">
    <link rel="icon" href="icon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="icon.svg">
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>
    <main class="app-shell">
      <header class="topbar">
        <div class="brand">
          <img class="brand-icon" src="icon.svg" alt="">
          <div>
            <h1>Vishnusahasranamam</h1>
            <p>Search nāmas, passages, and questions. Results stay local.</p>
          </div>
        </div>
        <button class="ghost-button" id="helpButton" type="button">Help</button>
      </header>

      <section class="search-panel" aria-label="Search">
        <div class="query-row">
          <input id="queryInput" autocomplete="off" autocapitalize="none" placeholder="प्राणदः, Madhava, or where do the three Vedas come from">
          <button class="primary-button" id="searchButton" type="button">Search</button>
        </div>

        <div class="mode-row" role="radiogroup" aria-label="Search mode">
          <button class="mode-button active" type="button" data-mode="entry" aria-pressed="true">Nāma</button>
          <button class="mode-button" type="button" data-mode="sloka" aria-pressed="false">Śloka</button>
          <button class="mode-button" type="button" data-mode="answer" aria-pressed="false">Question</button>
        </div>
      </section>

      <section class="result-panel" aria-label="Result">
        <div id="output" class="output" aria-live="polite"></div>
      </section>

      <footer class="actionbar">
        <button id="copyButton" type="button">Copy</button>
        <button id="clearButton" type="button">Clear</button>
        <span id="status" class="status">Loading...</span>
      </footer>
    </main>

    <dialog id="helpDialog" class="help-dialog">
      <h2>Search Options</h2>
      <dl>
        <dt>Nāma</dt>
        <dd>Best for one of the 1000 names. It returns the complete verified entry.</dd>
        <dt>Śloka</dt>
        <dd>Best for a śloka number from 1 to 108. Type 78 or śloka 78.</dd>
        <dt>Question</dt>
        <dd>Best for a simple question. It gives a short answer when the matching passage is strong enough.</dd>
      </dl>
      <button id="closeHelpButton" type="button">Close</button>
    </dialog>

    <script src="app.js"></script>
  </body>
</html>
"""


APP_JS = r"""const queryInput = document.querySelector("#queryInput");
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

function exactSearch(query) {
  const slokaNumber = parseSlokaNumber(query);
  if (slokaNumber !== null) {
    return slokaSearch(String(slokaNumber));
  }
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
  else if (activeMode === "sloka") result = slokaSearch(query);
  else result = answerSearch(query);
  renderOutput(result.display);
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
  renderOutput("");
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
  renderOutput(`Could not load app data: ${error.message}`);
  setStatus("Error");
});
"""


SERVICE_WORKER = """const CACHE_NAME = "vishnusahasranamam-static-pwa-v5";
const APP_SHELL = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "manifest.webmanifest",
  "icon.svg",
  "data/search-data.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
"""


MANIFEST = {
    "name": "Vishnusahasranamam",
    "short_name": "Vishnu",
    "description": "Local Vishnusahasranamam nāma search and answers.",
    "start_url": ".",
    "scope": ".",
    "display": "standalone",
    "background_color": "#f7f7f4",
    "theme_color": "#244f7a",
    "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
}


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    shutil.copy2(STATIC / "styles.css", OUT / "styles.css")
    shutil.copy2(STATIC / "icon.svg", OUT / "icon.svg")
    (OUT / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (OUT / "app.js").write_text(APP_JS, encoding="utf-8")
    (OUT / "service-worker.js").write_text(SERVICE_WORKER, encoding="utf-8")
    (OUT / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8")
    search_data = {
        "schemaVersion": 1,
        "entries": build_entries(),
        "slokas": build_slokas(),
        "passages": build_passages(),
    }
    (OUT / "data" / "search-data.json").write_text(json.dumps(search_data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(OUT)
    print(f"entries={len(search_data['entries'])} slokas={len(search_data['slokas'])} passages={len(search_data['passages'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
