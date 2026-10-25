import "./style.css";
import "./catalog.css";
import "./debug.css";
import * as worldart from "./worldart.js";
import { makeScene } from "./scene.js";

const $ = (id) => document.getElementById(id);
const root = document.documentElement;
const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
const scene = makeScene({ reducedMotion: motionQuery.matches });
let view = null,
  auto = true,
  busy = false,
  entering = false,
  lastHint = "",
  audio = null,
  sounded = 0,
  debugEnabled = true,
  debugInitialized = false,
  debugEndpointMissing = false,
  debugTimer = null,
  debugInFlight = false,
  debugToggleBusy = false;

const ROLE_ORDER = ["villager", "wolf", "seer", "witch", "hunter", "idiot"];
// 世界词只影响界面提示，不参与规则与权限判断。
const WORLD_NIGHT = {
  mist: "雾夜",
  hyperion: "冢夜",
  threebody: "静默夜",
  tidal_archive: "潮夜",
};
const WORLD_PLACE = {
  mist: "雾中",
  hyperion: "冢影中",
  threebody: "频道中",
  tidal_archive: "潮声里",
};
const ROLE_FALLBACK = {
  wolf: "夜裔",
  villager: "镇民",
  seer: "观星者",
  witch: "药师",
  hunter: "守林人",
  idiot: "守誓者",
};
// 服务器只给公开工具名；这里映射到每世界同一顺序的 icons 图集语义。
// 未列出的工具保持纯文字，不猜图标。
const TOOL_ICON = Object.freeze({
  inspect: "inspect",
  antidote: "antidote",
  poison: "poison",
  shoot: "shoot",
  explode: "explode",
  signup: "badge",
  withdraw: "badge",
  sheriff_vote: "badge",
  transfer_badge: "badge",
  reveal: "badge",
  exile_vote: "vote",
  wolf_vote: "vote",
  speak: "speak",
  wolf_chat: "speak",
  abstain: "abstain",
});
// 目录的 scene.intro 是入镇欢迎语；内置 fallback 缺字段时用本地文案补齐。
const FALLBACK_INTROS = {
  mist: "雾封住了出镇的路。十一位旅人已经等在广场，今夜，你会带着怎样的秘密入座？",
  hyperion:
    "最后一支朝圣队抵达光阴冢。十二名在场者各怀心愿，今夜，你会向伯劳献上谁的姓名？",
  threebody:
    "风暴困住临海监听站。三体舰队逼近的警报一遍遍响起，今夜，你能听出谁的频道在说谎？",
  tidal_archive:
    "低潮只开几个时辰。十二位守册人走进潮汐档案馆，今夜，你会把谁的名字写回《生民册》？",
};

// 目录不可用时至少保证默认雾钟镇能入镇；其余世界由 worldart.js 的 FALLBACK_BOOKS 提供。
const SAFE_BOOK = {
  id: "mist",
  name: "雾钟镇",
  tagline: "雾里听证词，灯下作选择。",
  summary:
    "雾封住了出镇的路。十二位旅人围坐在钟楼广场，每个人都带着不能说的秘密。",
  excerpt: "",
  glyph: "♜",
  motif: "bell",
  palette: {
    sky: "#0b1a21",
    mid: "#2f4a45",
    accent: "#d8bd85",
    paper: "#e9dfc6",
    ink: "#081014",
  },
  role_labels: { ...ROLE_FALLBACK },
  scene: {
    eyebrow: "钟声之后 / CHAPTER OF THE MIST",
    title: ["有人守着灯，", "有人藏在雾里。"],
    subtitle: "听清每一句证词，再决定相信谁。",
    caption: "钟楼广场",
    chapter: "十二位旅人，一个雾夜",
    footer: "雾钟镇 · 第一卷",
    intro: FALLBACK_INTROS.mist,
  },
  public_count: 15,
};
let activeWorld = "mist",
  books = [],
  selectedWorld = "mist",
  serverDefaultWorld = "mist",
  catalogMode = "loading",
  catalogNote = "",
  catalogPromise = Promise.resolve();
const roleHints = new Map();
document.querySelectorAll("#role-select option").forEach((option) => {
  if (!option.value) return;
  const [, ...hint] = option.textContent.split(" · ");
  roleHints.set(option.value, hint.join(" · ").trim());
});

const asText = (value) => (typeof value === "string" ? value.trim() : "");

function normalizeBook(raw) {
  const book = raw && typeof raw === "object" ? raw : {};
  const scene =
    book.scene && typeof book.scene === "object" ? book.scene : {};
  const title = Array.isArray(scene.title)
    ? scene.title.map(asText).filter(Boolean)
    : asText(scene.title)
      ? [asText(scene.title)]
      : [];
  return {
    ...book,
    id: asText(book.id),
    name: asText(book.name) || asText(book.id),
    tagline: asText(book.tagline),
    summary: asText(book.summary),
    excerpt: asText(book.excerpt),
    glyph: asText(book.glyph) || "✦",
    palette:
      book.palette && typeof book.palette === "object" ? book.palette : {},
    role_labels:
      book.role_labels && typeof book.role_labels === "object"
        ? book.role_labels
        : {},
    scene: {
      eyebrow: asText(scene.eyebrow),
      title,
      subtitle: asText(scene.subtitle),
      caption: asText(scene.caption),
      chapter: asText(scene.chapter),
      footer: asText(scene.footer),
      intro:
        asText(scene.intro) ||
        FALLBACK_INTROS[book.id] ||
        "雾中已经备好席位，今夜，你会带着怎样的秘密入座？",
    },
    public_count: Number(book.public_count) || 0,
  };
}

// 兼容数组与以 id 为键的对象两种 fallback 形态，坏数据不阻断入镇。
function normalizeBooks(raw) {
  const list = Array.isArray(raw)
    ? raw
    : raw && typeof raw === "object"
      ? Object.entries(raw).map(([id, book]) => ({
          ...(book && typeof book === "object" ? book : {}),
          id: book?.id || id,
        }))
      : [];
  return list.map(normalizeBook).filter((book) => book.id);
}

function shortRole(value, fallback = "") {
  const raw = asText(value) || fallback;
  if (!raw) return "";
  const cut = raw.split(/[（(。；;\n]/)[0].trim();
  return (cut || raw).slice(0, 10);
}

function roleLabel(book, role) {
  return shortRole(book?.role_labels?.[role], ROLE_FALLBACK[role]);
}

function applyBookPalette(element, book) {
  const fallback = {
    sky: "#0b1a21",
    mid: "#2f4a45",
    accent: "#d8bd85",
    paper: "#e9dfc6",
  };
  Object.entries(fallback).forEach(([key, value]) => {
    element.style.setProperty(
      `--book-${key}`,
      asText(book?.palette?.[key]) || value,
    );
  });
}

function worldNightLabel(worldId = activeWorld) {
  return WORLD_NIGHT[worldId] || WORLD_NIGHT.mist;
}

function worldPlaceLabel(worldId = activeWorld) {
  return WORLD_PLACE[worldId] || WORLD_PLACE.mist;
}

function applyWorld(worldId) {
  const id = asText(worldId) || "mist";
  activeWorld = id;
  try {
    if (typeof worldart.applyWorldTheme === "function")
      worldart.applyWorldTheme(id);
  } catch {
    /* 主题是装饰层；即使主题模块失败也必须能入镇。 */
  }
  root.dataset.world = id;
  // 入镇前让空场景跟随目录选择预览；开局后 scene.update(state) 仍以服务器状态为准。
  if (typeof scene.setWorld === "function") scene.setWorld(id);
  $("waiting-text").textContent = `旅人正在${worldPlaceLabel(id)}思索`;
}

function renderCoverInto(container, book) {
  container.replaceChildren();
  try {
    if (typeof worldart.renderCover === "function")
      worldart.renderCover(container, book, {
        reducedMotion: motionQuery.matches,
      });
  } catch {
    /* 封面绘制失败时使用 CSS 渐变兜底。 */
  }
  if (!container.childElementCount) {
    container.append(node("span", book?.glyph || "✦", "world-cover-fallback"));
  }
}

function setWorldCatalogMode(mode, note = "") {
  catalogMode = mode;
  catalogNote = note;
  renderWorldStatus();
}

function renderWorldStatus() {
  const status = $("world-status");
  const current = books.find((book) => book.id === selectedWorld);
  if (catalogMode === "loading") {
    status.dataset.state = "loading";
    status.textContent = "正在翻阅世界书目录……";
    return;
  }
  if (catalogMode === "fallback") {
    status.dataset.state = "error";
    status.textContent = `${catalogNote}；已展示内置世界，仍可直接入镇。`;
    return;
  }
  status.dataset.state = "ready";
  status.textContent = current
    ? `已选 ${current.name} · 共 ${books.length} 本世界书`
    : `共 ${books.length} 本世界书`;
}

function syncCardSelection() {
  document.querySelectorAll(".world-card").forEach((card) => {
    card.setAttribute(
      "aria-pressed",
      String(card.dataset.worldId === selectedWorld),
    );
  });
}

function fillRoleChips(container, book) {
  container.replaceChildren(
    ...ROLE_ORDER.map((role) => roleLabel(book, role))
      .filter(Boolean)
      .map((label) => node("span", label, "world-role")),
  );
}

function focusOtherCard(event, worldId) {
  const keys = [
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "ArrowDown",
    "Home",
    "End",
  ];
  if (!keys.includes(event.key)) return;
  const cards = [...document.querySelectorAll(".world-card")];
  if (!cards.length) return;
  const index = cards.findIndex((card) => card.dataset.worldId === worldId);
  let next = index < 0 ? 0 : index;
  if (event.key === "Home") next = 0;
  else if (event.key === "End") next = cards.length - 1;
  else if (event.key === "ArrowRight" || event.key === "ArrowDown")
    next = (next + 1) % cards.length;
  else next = (next - 1 + cards.length) % cards.length;
  event.preventDefault();
  cards[next].focus();
}

function renderWorldCards() {
  const list = $("world-list");
  list.replaceChildren();
  books.forEach((book) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "world-card";
    card.dataset.worldId = book.id;
    card.setAttribute("aria-pressed", "false");
    card.setAttribute(
      "aria-label",
      `${book.name}：${book.tagline || "选择这个世界"}`,
    );
    applyBookPalette(card, book);
    const cover = node("span", undefined, "world-card__cover");
    cover.setAttribute("aria-hidden", "true");
    renderCoverInto(cover, book);
    const body = node("span", undefined, "world-card__body");
    body.append(node("span", book.name, "world-card__name"));
    if (book.tagline)
      body.append(node("span", book.tagline, "world-card__tagline"));
    if (book.summary)
      body.append(node("span", book.summary, "world-card__summary"));
    if (book.excerpt)
      body.append(node("span", `“${book.excerpt}”`, "world-card__excerpt"));
    const roles = node("span", undefined, "world-card__roles world-roles");
    fillRoleChips(roles, book);
    if (roles.childElementCount) body.append(roles);
    card.append(cover, body);
    card.addEventListener("click", () =>
      selectWorld(book.id, { silent: false }),
    );
    card.addEventListener("keydown", (event) =>
      focusOtherCard(event, book.id),
    );
    list.append(card);
  });
  list.setAttribute("aria-busy", "false");
  syncCardSelection();
}

function renderDetailPersonas(detail, book) {
  const body = detail.querySelector(".world-detail__body");
  if (!body) return;
  let section = $("world-detail-personas");
  if (!section) {
    section = node("section", undefined, "world-detail__personas");
    section.id = "world-detail-personas";
    const head = node("div", undefined, "world-detail__personas-head");
    head.append(
      node("span", "公开人物名册", "eyebrow"),
      node("span", "仅公开席位与姓名", "world-detail__personas-hint"),
    );
    const grid = node("div", undefined, "world-persona-grid");
    grid.id = "world-detail-persona-grid";
    section.append(head, grid);
    body.append(section);
  }
  const grid = $("world-detail-persona-grid");
  const roster = worldart.renderPersonaRoster(grid, book.id);
  const hint = section.querySelector(".world-detail__personas-hint");
  if (hint) {
    const count = roster ? roster.childElementCount : 0;
    hint.textContent = count
      ? `仅公开席位、姓名与简介 · ${count} 位`
      : "公开名册暂缺，不影响入镇";
  }
}

function renderWorldDetail(book) {
  const detail = $("world-detail");
  detail.hidden = false;
  applyBookPalette(detail, book);
  renderCoverInto($("world-detail-cover"), book);
  $("world-detail-name").textContent = book.name;
  $("world-detail-tagline").textContent = book.tagline;
  $("world-detail-summary").textContent = book.summary;
  $("world-detail-excerpt").textContent = book.excerpt
    ? `“${book.excerpt}”`
    : "";
  $("world-detail-count").textContent = book.public_count
    ? `公开条目 ${book.public_count}`
    : "世界书";
  fillRoleChips($("world-detail-roles"), book);
  renderDetailPersonas(detail, book);
  $("world-detail-note").textContent =
    `确认后点击“踏入雾中”，以 ${book.name} 的身份与称谓入镇。`;
}

function updateRoleOptions(book) {
  $("role-select").querySelectorAll("option").forEach((option) => {
    if (!option.value) return;
    const label = roleLabel(book, option.value);
    const hint = roleHints.get(option.value) || "";
    option.textContent = hint ? `${label} · ${hint}` : label;
  });
}

function englishSubtitle(book) {
  const eyebrow = book?.scene?.eyebrow || "";
  const parts = eyebrow.split(/\s*\/\s*/);
  const candidate = parts.length > 1 ? parts.slice(1).join(" / ") : "";
  return /[A-Za-z]/.test(candidate) ? candidate.toUpperCase() : "";
}

function setSceneTitle(title) {
  if (!title.length) return;
  const heading = $("scene-title");
  heading.replaceChildren();
  title.forEach((line, index) => {
    if (index) heading.append(document.createElement("br"));
    heading.append(document.createTextNode(line));
  });
}

// 只用 textContent/DOM 写入目录文案，API 文本不会进入 innerHTML。
function applyCatalogText(book, chapterOverride) {
  const scene = book?.scene || {};
  if (book?.name) {
    $("brand-name").textContent = book.name;
    document.querySelector(".brand").setAttribute(
      "aria-label",
      `${book.name}首页`,
    );
    $("intro-title").textContent = `欢迎来到${book.name}`;
    $("site-footer-note").textContent = `${book.name} · 文字对局`;
  }
  const english = englishSubtitle(book);
  if (english) $("brand-sub").textContent = english;
  if (book?.glyph) $("brand-emblem").textContent = book.glyph;
  if (scene.eyebrow) $("scene-eyebrow").textContent = scene.eyebrow;
  setSceneTitle(scene.title || []);
  if (scene.subtitle) $("scene-subtitle").textContent = scene.subtitle;
  if (scene.intro) $("intro-lead").textContent = scene.intro;
  if (scene.caption)
    $("chapter-caption").textContent = `✧ ${scene.caption}`;
  const chapter = asText(chapterOverride) || scene.chapter;
  if (chapter) $("chapter").textContent = chapter;
  if (scene.footer) {
    $("world-footer-book").textContent = scene.footer;
    $("site-footer-text").textContent = scene.footer;
  }
  if (book?.tagline) $("world-footer-text").textContent = book.tagline;
  if (!view) {
    $("day").textContent = `${book?.name || "雾钟镇"} · 初至`;
    $("story-title").textContent = chapter || "等一场雾散";
  }
  if (scene.caption)
    $("scene").setAttribute(
      "aria-label",
      `${book.name}十二位旅人的${scene.caption}，画面随昼夜、生死与技能变化`,
    );
  document.title = `${book?.name || "雾钟镇"} · ${
    scene.eyebrow ? scene.eyebrow.split("/")[0].trim() : "一场文字对局"
  }`;
}

function selectWorld(worldId, { silent = false } = {}) {
  const book =
    books.find((item) => item.id === worldId) ||
    books.find((item) => item.id === selectedWorld) ||
    books[0];
  if (!book) return;
  selectedWorld = book.id;
  syncCardSelection();
  // 390px 横向卡片带中，键盘/点选后把选中卡滚入视野，避免详情与卡片错位。
  document
    .querySelector(`.world-card[data-world-id="${book.id}"]`)
    ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  renderWorldDetail(book);
  applyWorld(book.id);
  applyCatalogText(book, view?.chapter);
  updateRoleOptions(book);
  if (!silent) renderWorldStatus();
}

async function loadWorldbooks() {
  setWorldCatalogMode("loading");
  let loaded = [];
  let defaultWorld = "mist";
  let note = "";
  try {
    const data = await api("worldbooks");
    loaded = normalizeBooks(data?.worldbooks);
    if (asText(data?.default)) defaultWorld = data.default;
    if (!loaded.length) throw new Error("世界书目录为空");
  } catch (err) {
    const message = String(err?.message || "");
    note =
      err?.status === 404
        ? "世界书目录尚未开放"
        : message.includes("为空")
          ? "世界书目录暂时为空"
          : "世界书目录暂时不可用";
    loaded = normalizeBooks(worldart.FALLBACK_BOOKS);
    defaultWorld = loaded[0]?.id || "mist";
  }
  books = loaded.length ? loaded : [normalizeBook(SAFE_BOOK)];
  if (!books.some((book) => book.id === defaultWorld))
    defaultWorld = books[0].id;
  serverDefaultWorld = defaultWorld;
  if (view?.worldbook && books.some((book) => book.id === view.worldbook))
    selectedWorld = view.worldbook;
  else if (!books.some((book) => book.id === selectedWorld))
    selectedWorld = defaultWorld;
  renderWorldCards();
  selectWorld(selectedWorld, { silent: true });
  if (note) setWorldCatalogMode("fallback", note);
  else setWorldCatalogMode("ready");
  if (view) applyGameWorld(view);
}

function applyGameWorld(state) {
  const id = asText(state?.worldbook) || serverDefaultWorld || "mist";
  applyWorld(id);
  selectedWorld = id;
  syncCardSelection();
  const book = books.find((item) => item.id === id);
  if (book) {
    applyCatalogText(book, state?.chapter);
    if (asText(state?.worldbook_name))
      $("brand-name").textContent = state.worldbook_name;
    updateRoleOptions(book);
  } else if (asText(state?.worldbook_name)) {
    $("brand-name").textContent = state.worldbook_name;
    updateRoleOptions(null);
  }
}

// 场景只画服务器给当前玩家的可见事实；动效偏好同时交给 CSS 与 Phaser。
function syncMotionPreference() {
  const reduced = motionQuery.matches;
  root.dataset.motion = reduced ? "reduced" : "full";
  if (typeof scene.setReducedMotion === "function")
    scene.setReducedMotion(reduced);
}
syncMotionPreference();
if (typeof motionQuery.addEventListener === "function")
  motionQuery.addEventListener("change", syncMotionPreference);

function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function error(message, kind = "") {
  const box = $("error");
  box.textContent = message;
  box.hidden = !message;
  box.classList.toggle("is-network", Boolean(message) && kind === "network");
  if (message) root.dataset.error = kind || "app";
  else delete root.dataset.error;
}
function setBusy(value) {
  busy = value;
  root.dataset.busy = value ? "yes" : "no";
  $("submit-action").disabled = value;
  document.querySelectorAll(".choice-chip").forEach((chip) => {
    chip.disabled = value;
  });
  syncWaiting();
}
// 等待指示跟随「自动推进中且没有轮到我」，不因请求忙而隐藏；忙碌结束后再同步一次。
function syncWaiting() {
  const waiting = $("waiting");
  const pendingAdvance = Boolean(view) && !view.winner && view.choices.length === 0;
  waiting.hidden = !(auto && pendingAdvance);
}
function applyUiState(state) {
  const badge = $("turn-badge");
  if (!state) {
    root.dataset.mode = "entering";
    delete root.dataset.phase;
    delete root.dataset.turn;
    delete root.dataset.alive;
    delete root.dataset.round;
    badge.hidden = true;
    $("waiting").hidden = true;
    $("phase-chip").hidden = true;
    $("ending").hidden = true;
    return;
  }
  root.dataset.mode = state.winner ? "ended" : "playing";
  root.dataset.phase = state.night ? "night" : "day";
  root.dataset.turn = state.choices.length ? "you" : "waiting";
  root.dataset.alive = state.alive ? "yes" : "no";
  root.dataset.round = String(state.round);
  $("phase-chip").hidden = false;
  $("phase-label").textContent = state.winner
    ? state.chapter
    : `${state.night ? worldNightLabel() : "白昼"} · 第 ${state.round} 日`;
  badge.hidden = Boolean(state.winner) || !state.choices.length;
  badge.textContent = state.night ? "轮到你 · 夜色之下" : "轮到你 · 从容选择";
  syncWaiting();
  $("ending").hidden = !state.winner;
  if (state.winner)
    $("ending").textContent = state.story.at(-1)?.text || "故事结束。";
}
async function api(path, data) {
  const options =
    data === undefined
      ? {}
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Mist-Request": "1",
          },
          body: JSON.stringify(data),
        };
  const response = await fetch("/api/" + path, options);
  if (!response.ok) {
    let message = "故事暂时停顿，请稍后再试。";
    try {
      message = (await response.json()).detail || message;
    } catch {
      /* Use the safe generic message. */
    }
    throw Object.assign(
      new Error(typeof message === "string" ? message : "请检查填写的内容。"),
      { status: response.status },
    );
  }
  return response.json();
}
/* ---------- Issue #64 调试观察 ----------
   面板只读取 /api/debug 的审计结果；所有文本用 textContent/DOM 写入。
   不把调试数据发往 AI，也不改变对局请求。 */
const DEBUG_POLL_MS = 1500;

function debugTime(value) {
  const raw = asText(value);
  if (!raw) return "";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleTimeString("zh-CN", { hour12: false });
}

function compactValue(value, limit = 180) {
  if (value === undefined || value === null) return "";
  let text;
  if (typeof value === "string") text = value;
  else {
    try {
      text = JSON.stringify(value);
    } catch {
      text = String(value);
    }
  }
  if (text === undefined) return "";
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

function debugEmptyMessage(text) {
  return node("p", text, "debug-empty");
}

function debugMissingText(item) {
  const label = asText(item?.label);
  const reason = asText(item?.reason);
  if (label) return label;
  if (reason) return `缺失原因：${reason}`;
  return "未记录显式说明";
}

function debugToolCallNode(call) {
  const tool = asText(call?.name) || asText(call?.tool) || "未知工具";
  const entry = node("div", undefined, "debug-tool-call");
  entry.append(node("b", tool));
  if (call?.args !== undefined)
    entry.append(document.createTextNode(` · 参数 ${compactValue(call.args)}`));
  if (call?.result !== undefined)
    entry.append(
      document.createTextNode(` · 结果 ${compactValue(call.result)}`),
    );
  return entry;
}

function debugThinkingStepNode(step, index) {
  const content = asText(step?.content);
  const hasContent = step?.has_content === true && content !== "";
  const wrap = node("div", undefined, "debug-thinking-step");
  wrap.dataset.hasContent = String(hasContent);
  wrap.append(
    node(
      "div",
      `显式说明 · 第 ${Number(step?.step) || index + 1} 步`,
      "debug-thinking-step__head",
    ),
  );
  if (hasContent) wrap.append(node("p", content, "debug-thinking-content"));
  else
    wrap.append(
      node(
        "p",
        "模型未返回显式说明（has_content=false，未补写）。",
        "debug-thinking-missing",
      ),
    );
  const calls = Array.isArray(step?.tool_calls) ? step.tool_calls : [];
  if (calls.length) {
    const list = node("div", undefined, "debug-tool-calls");
    calls.forEach((call) => list.append(debugToolCallNode(call)));
    wrap.append(list);
  }
  return wrap;
}

function debugDecisionNode(decision) {
  const card = node("article", undefined, "debug-decision");
  const reason = asText(decision?.reason) || "未记录";
  const meta = node("div", undefined, "debug-decision__meta");
  meta.append(node("span", `原因 ${reason}`));
  meta.append(node("span", decision?.acted ? "已行动" : "未行动"));
  if (asText(decision?.time)) meta.append(node("span", debugTime(decision.time)));
  card.append(meta);

  const thinking = Array.isArray(decision?.thinking) ? decision.thinking : [];
  const thinkingBox = node("div", undefined, "debug-thinking");
  if (thinking.length) {
    thinking.forEach((step, index) =>
      thinkingBox.append(debugThinkingStepNode(step, index)),
    );
  } else {
    const missing = Array.isArray(decision?.missing)
      ? decision.missing.map(debugMissingText).filter(Boolean)
      : [];
    thinkingBox.append(
      node(
        "p",
        missing.length
          ? `缺失显式说明：${missing.join("；")}`
          : "无模型显式说明记录（人类操作或模型未提供，未补写）。",
        "debug-thinking-missing",
      ),
    );
  }
  card.append(thinkingBox);

  const calls = Array.isArray(decision?.calls) ? decision.calls : [];
  if (calls.length) {
    const callList = node("div", undefined, "debug-tool-calls");
    calls.forEach((call) => callList.append(debugToolCallNode(call)));
    card.append(callList);
  }

  const missing = Array.isArray(decision?.missing) ? decision.missing : [];
  if (missing.length && thinking.length) {
    const list = node("ul", undefined, "debug-decision__missing");
    missing.forEach((item) =>
      list.append(node("li", debugMissingText(item))),
    );
    card.append(list);
  }
  return card;
}

function debugPlayerNode(player) {
  const card = node("article", undefined, "debug-player");
  card.dataset.seat = String(player?.seat ?? "");
  const head = node("div", undefined, "debug-player__head");
  head.append(
    node("span", String(player?.seat ?? "?").padStart(2, "0"), "debug-seat"),
    node("strong", asText(player?.name) || "姓名未记录", "debug-player__name"),
    node(
      "span",
      `角色：${asText(player?.role) || "未记录"}（调试可见）`,
      "debug-role",
    ),
  );
  const alive = node("span", player?.alive ? "在场" : "离场", "debug-alive");
  alive.dataset.alive = String(Boolean(player?.alive));
  head.append(alive);
  card.append(head);

  const decisions = Array.isArray(player?.decisions) ? player.decisions : [];
  const box = node("div", undefined, "debug-decisions");
  if (decisions.length)
    decisions.forEach((decision) => box.append(debugDecisionNode(decision)));
  else box.append(debugEmptyMessage("本阶段无决策记录。"));
  card.append(box);
  return card;
}

function debugPhaseNode(phase, index) {
  const section = node("section", undefined, "debug-phase");
  section.dataset.phase = asText(phase?.phase) || `phase-${index + 1}`;
  if (asText(phase?.phase_id)) section.dataset.phaseId = phase.phase_id;
  const head = node("div", undefined, "debug-phase__head");
  head.append(
    node("h4", asText(phase?.label) || asText(phase?.phase) || "未命名阶段"),
    node("span", asText(phase?.phase) || "phase?", "debug-phase__code"),
  );
  if (asText(phase?.phase_id))
    head.append(node("span", `id ${phase.phase_id}`, "debug-phase__id"));
  section.append(head);

  const players = Array.isArray(phase?.players) ? phase.players : [];
  const box = node("div", undefined, "debug-players");
  if (players.length)
    players.forEach((player) => box.append(debugPlayerNode(player)));
  else box.append(debugEmptyMessage("本阶段无玩家决策。"));
  section.append(box);
  return section;
}

function debugRoundNode(round) {
  const section = node("section", undefined, "debug-round");
  const raw = Number(round?.round);
  const known = Number.isInteger(raw) && raw > 0;
  const number = known ? raw : null;
  section.dataset.round = known ? String(number) : "unknown";
  const head = node("div", undefined, "debug-round__head");
  head.append(
    node("h3", known ? `第 ${number} 轮` : "轮次未知（历史审计）"),
    node(
      "span",
      known ? `ROUND ${String(number).padStart(2, "0")}` : "ROUND ?",
      "debug-round__code",
    ),
  );
  section.append(head);

  const phases = Array.isArray(round?.phases) ? round.phases : [];
  const box = node("div", undefined, "debug-phases");
  if (phases.length)
    phases.forEach((phase, phaseIndex) =>
      box.append(debugPhaseNode(phase, phaseIndex)),
    );
  else box.append(debugEmptyMessage("本轮暂无阶段记录。"));
  section.append(box);
  return section;
}

function debugWolfChatNode(item, phaseLabels) {
  const card = node("article", undefined, "debug-chat-item");
  if (view && Number(item?.seat) === Number(view.seat))
    card.dataset.human = "true";
  const phase = asText(item?.phase);
  const meta = [
    `第 ${Number(item?.round) || "?"} 轮`,
    phaseLabels?.get(phase) || phase || "阶段未记录",
    `${item?.seat ?? "?"}号 ${asText(item?.name) || "未记录"}`,
  ];
  if (asText(item?.time)) meta.push(debugTime(item.time));
  card.append(node("div", meta.join(" · "), "debug-chat-item__meta"));
  card.append(node("p", asText(item?.text) || "（空对话）"));
  return card;
}

function debugMissingNode(item, phaseLabels) {
  const card = node("article", undefined, "debug-missing-item");
  const phase = asText(item?.phase);
  const meta = [
    `第 ${Number(item?.round) || "?"} 轮`,
    phaseLabels?.get(phase) || phase || "阶段未记录",
    `${item?.seat ?? "?"}号`,
  ];
  card.append(node("div", meta.join(" · "), "debug-missing-item__meta"));
  const reason = asText(item?.reason);
  const text = debugMissingText(item);
  card.append(
    node(
      "p",
      reason && !text.includes(reason) ? `${text}（${reason}）` : text,
    ),
  );
  return card;
}

function hideDebugNotice() {
  const notice = $("debug-notice");
  notice.hidden = true;
  notice.textContent = "";
  notice.dataset.kind = "";
}

function showDebugNotice(message, kind = "error") {
  const notice = $("debug-notice");
  notice.textContent = message;
  notice.dataset.kind = kind;
  notice.hidden = false;
}

function emptyDebugView() {
  $("debug-rounds").replaceChildren();
  $("debug-wolf-chat").replaceChildren();
  $("debug-missing").replaceChildren();
  $("debug-status").textContent = "";
  $("debug-updated").textContent = "";
  hideDebugNotice();
}

function clearDebugView(message = "等待入镇") {
  $("debug-rounds").replaceChildren(debugEmptyMessage(message));
  $("debug-wolf-chat").replaceChildren(
    debugEmptyMessage("本局尚未记录狼队内部对话。这里只显示真实发生的事件。"),
  );
  $("debug-missing").replaceChildren(
    debugEmptyMessage("未记录缺失说明。"),
  );
  $("debug-status").textContent = message;
  $("debug-updated").textContent = "";
  hideDebugNotice();
}

function renderDebug(data) {
  if (!data || data.enabled === false) {
    if (data?.enabled === false) applyDebugEnabled(false);
    return;
  }
  hideDebugNotice();
  const rounds = Array.isArray(data.rounds) ? data.rounds : [];
  const wolfChat = Array.isArray(data.wolf_chat) ? data.wolf_chat : [];
  const missing = Array.isArray(data.missing) ? data.missing : [];
  const phaseLabels = new Map();
  rounds.forEach((round) => {
    (Array.isArray(round?.phases) ? round.phases : []).forEach((phase) => {
      if (asText(phase?.phase))
        phaseLabels.set(phase.phase, asText(phase.label) || phase.phase);
    });
  });

  $("debug-rounds").replaceChildren(
    ...(rounds.length
      ? rounds.map((round) => debugRoundNode(round))
      : [
          debugEmptyMessage(
            "暂无模型决策记录。入镇并推进对局后，会按轮次、阶段和玩家显示。",
          ),
        ]),
  );
  $("debug-wolf-chat").replaceChildren(
    ...(wolfChat.length
      ? wolfChat.map((item) => debugWolfChatNode(item, phaseLabels))
      : [
          debugEmptyMessage(
            "本局尚未记录狼队内部对话。这里只显示真实发生的事件。",
          ),
        ]),
  );
  $("debug-missing").replaceChildren(
    ...(missing.length
      ? missing.map((item) => debugMissingNode(item, phaseLabels))
      : [debugEmptyMessage("未记录缺失说明。")]),
  );

  const gameId = asText(data.game_id);
  $("debug-status").textContent = gameId
    ? `对局 ${gameId.slice(0, 8)} · ${rounds.length} 轮`
    : "等待入镇";
  $("debug-updated").textContent =
    `更新 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
}

function stopDebugPolling() {
  if (debugTimer !== null) {
    clearInterval(debugTimer);
    debugTimer = null;
  }
}

function syncDebugPolling() {
  const active =
    debugEnabled &&
    debugInitialized &&
    Boolean(view) &&
    !debugEndpointMissing;
  if (!active) {
    stopDebugPolling();
    return;
  }
  if (debugTimer === null) {
    debugTimer = setInterval(refreshDebug, DEBUG_POLL_MS);
    refreshDebug();
  }
}

function applyDebugEnabled(enabled) {
  debugEnabled = Boolean(enabled);
  const toggle = $("debug-toggle");
  toggle.setAttribute("aria-pressed", String(debugEnabled));
  $("debug-toggle-state").textContent = debugEnabled ? "开" : "关";
  $("debug-panel").hidden = !debugEnabled || !view;
  root.dataset.debug = debugEnabled ? "on" : "off";
  if (!debugEnabled) {
    stopDebugPolling();
    emptyDebugView();
  } else if (debugInitialized) {
    syncDebugPolling();
  }
}

async function refreshDebug() {
  if (!debugEnabled || !view || debugInFlight || debugEndpointMissing) return;
  debugInFlight = true;
  try {
    const data = await api("debug");
    if (!debugEnabled) return;
    if (data?.enabled === false) {
      applyDebugEnabled(false);
      return;
    }
    renderDebug(data);
  } catch (err) {
    if (err?.status === 401) {
      stopDebugPolling();
      showDebugNotice("登录状态已失效，调试数据暂停；对局界面会按服务端状态恢复。", "info");
    } else if (err?.status === 404) {
      debugEndpointMissing = true;
      stopDebugPolling();
      showDebugNotice("调试接口尚未开放，对局不受影响。", "info");
    } else {
      showDebugNotice("调试数据暂时不可用，对局继续；面板会在下次轮询时重试。");
    }
  } finally {
    debugInFlight = false;
  }
}

async function bootDebug() {
  try {
    const data = await api("debug");
    debugEndpointMissing = false;
    applyDebugEnabled(data?.enabled !== false);
    if (data?.enabled !== false) renderDebug(data);
  } catch (err) {
    if (err?.status === 404) {
      debugEndpointMissing = true;
      showDebugNotice("调试接口尚未开放，对局不受影响。", "info");
    } else if (err?.status !== 401) {
      showDebugNotice("暂时无法读取调试状态，默认保持开启。", "info");
    }
  } finally {
    debugInitialized = true;
    syncDebugPolling();
  }
}

async function toggleDebug() {
  if (debugToggleBusy) return;
  const next = !debugEnabled;
  debugToggleBusy = true;
  $("debug-toggle").disabled = true;
  debugEndpointMissing = false;
  try {
    if (!next) applyDebugEnabled(false);
    else clearDebugView("正在读取调试记录……");
    const result = await api("debug", { enabled: next });
    debugEndpointMissing = false;
    applyDebugEnabled(result?.enabled !== false);
    if (debugEnabled) {
      clearDebugView("正在读取调试记录……");
      syncDebugPolling();
      refreshDebug();
    }
  } catch (err) {
    applyDebugEnabled(!next);
    showDebugNotice(`调试开关未能保存：${err.message}`, "error");
    if (debugEnabled) refreshDebug();
  } finally {
    debugToggleBusy = false;
    $("debug-toggle").disabled = false;
  }
}

function bell() {
  if (!audio) return;
  const oscillator = audio.createOscillator(),
    gain = audio.createGain();
  oscillator.connect(gain);
  gain.connect(audio.destination);
  oscillator.frequency.value = 440;
  gain.gain.setValueAtTime(0.07, audio.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + 1.4);
  oscillator.start();
  oscillator.stop(audio.currentTime + 1.4);
}
function render(state) {
  const oldVersion = view?.version;
  view = state;
  if (debugEnabled) $("debug-panel").hidden = false;
  applyGameWorld(state);
  scene.update(state);
  $("intro").hidden = true;
  $("world-picker").hidden = true;
  ["identity", "story", "reset", "auto", "assistant"].forEach(
    (id) => ($(id).hidden = false),
  );
  $("chapter").textContent = state.chapter;
  $("story-title").textContent = state.chapter;
  const day = $("day");
  day.replaceChildren();
  const dayIcon = node("i", undefined, "day-icon");
  if (
    worldart.paintWorldIcon(dayIcon, activeWorld, state.night ? "night" : "day")
  )
    day.append(dayIcon);
  day.append(
    document.createTextNode(
      `第 ${state.round} 日 · ${state.night ? worldNightLabel() : "白昼"}`,
    ),
  );
  $("role-title").textContent = `${state.identity} · ${state.seat}号`;
  $("role-note").textContent =
    state.note ||
    (state.alive
      ? "秘密只属于你。留心每一位旅人的证词。"
      : "你的席位已空，仍可旁听公开的故事。");
  $("resources").textContent = Object.entries(state.resources)
    .map(([k, v]) => `${k} ${v ? "●" : "○"}`)
    .join(" / ");
  $("alive-count").textContent = `${
    state.players.filter((p) => p.alive).length
  } 位仍在场`;
  $("roster").replaceChildren(
    ...state.players.map((p) => {
      const n = node(
        "div",
        undefined,
        "person" +
          (!p.alive ? " departed" : "") +
          (p.seat === state.seat ? " you" : ""),
      );
      const portrait = node("span", undefined, "portrait");
      portrait.style.setProperty("--person", p.color);
      worldart.paintPersonaPortrait(portrait, activeWorld, p.seat, p.name);
      const stateLine = node("small", undefined, "person__state");
      [
        p.alive ? "alive" : "dead",
        p.sheriff ? "sheriff" : "",
        p.seat === state.seat ? "you" : "",
      ].forEach((key) => {
        if (!key) return;
        const icon = node("i", undefined, "person__icon");
        if (worldart.paintWorldIcon(icon, activeWorld, key))
          stateLine.append(icon);
      });
      stateLine.append(
        document.createTextNode(
          p.sheriff ? "执铃人" : p.role || (p.alive ? "身份未明" : "已离场"),
        ),
      );
      n.append(
        portrait,
        node("span", `${String(p.seat).padStart(2, "0")} ${p.name}`, "person__name"),
        stateLine,
      );
      n.title = p.description;
      return n;
    }),
  );
  if (oldVersion !== state.version) {
    const story = $("story"),
      atEnd = story.scrollHeight - story.scrollTop - story.clientHeight < 100;
    story.replaceChildren(
      ...state.story.map((e) => {
        const n = node(
          "article",
          undefined,
          "entry" + (e.private ? " private" : ""),
        );
        n.append(
          node(
            "div",
            `${e.speaker} · 第${e.round}日${e.private ? " · 私密记录" : ""}`,
            "entry-meta",
          ),
          node("p", e.text),
        );
        return n;
      }),
    );
    if (atEnd) story.scrollTop = story.scrollHeight;
  }
  const selected = $("choice").value;
  $("choice").replaceChildren(
    ...state.choices.map((c) => {
      const o = node("option", c.label);
      o.value = c.tool;
      return o;
    }),
  );
  if (state.choices.some((c) => c.tool === selected))
    $("choice").value = selected;
  const choiceGrid = ensureChoiceGrid();
  choiceGrid.replaceChildren(...state.choices.map(buildChoiceChip));
  $("action-form").hidden = !state.choices.length;
  choiceChanged();
  $("status").textContent = state.winner
    ? ""
    : state.choices.length
      ? "你可以从容决定，没有倒数。"
      : auto
        ? `旅人在${worldPlaceLabel()}思索，请稍候……`
        : "旅人暂歇。你仍可翻阅札记。";
  const chosenSeat = $("query-seat").value;
  $("query-seat").replaceChildren(
    ...state.players.map((p) => {
      const o = node("option", `${p.seat}号 · ${p.name}`);
      o.value = p.seat;
      return o;
    }),
  );
  if (chosenSeat) $("query-seat").value = chosenSeat;
  if (!state.night && state.round !== sounded) {
    sounded = state.round;
    bell();
  }
  applyUiState(state);
  syncDebugPolling();
}
function ensureChoiceGrid() {
  const existing = $("choice-grid");
  if (existing) return existing;
  const select = $("choice");
  const grid = node("div", undefined, "choice-grid");
  grid.id = "choice-grid";
  grid.setAttribute("role", "group");
  grid.setAttribute("aria-label", "技能与动作");
  // 插到 .action-top 之后而不是 select 之后，避免成为 flex 行里的窄列。
  const top = select.closest(".action-top");
  if (top) top.after(grid);
  else select.after(grid);
  // 原生 select 仍是表单取值与既有测试的稳定来源，仅视觉隐藏；
  // 可见选项由带图标的按钮承担，键盘可用 Tab/Enter 操作。
  select.classList.add("choice-native");
  select.tabIndex = -1;
  select.setAttribute("aria-hidden", "true");
  return grid;
}

function buildChoiceChip(choice) {
  const chip = node("button", undefined, "choice-chip");
  chip.type = "button";
  chip.dataset.tool = choice.tool;
  chip.setAttribute("aria-pressed", "false");
  const iconKey = TOOL_ICON[choice.tool];
  if (iconKey) {
    const icon = node("span", undefined, "choice-chip__icon");
    if (worldart.paintWorldIcon(icon, activeWorld, iconKey)) chip.append(icon);
  }
  chip.append(
    node("span", choice.label || choice.tool, "choice-chip__label"),
  );
  chip.addEventListener("click", () => {
    const select = $("choice");
    if (select.value === choice.tool) return;
    select.value = choice.tool;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  return chip;
}

function syncChoiceChips() {
  const current = $("choice").value;
  document.querySelectorAll(".choice-chip").forEach((chip) => {
    chip.setAttribute("aria-pressed", String(chip.dataset.tool === current));
  });
}

function choiceChanged() {
  const c = view?.choices.find((c) => c.tool === $("choice").value);
  $("speech-wrap").hidden = !c?.text;
  $("target-wrap").hidden = !c?.targets;
  const selected = $("target").value;
  $("target").replaceChildren(
    ...(c?.targets || []).map((s) => {
      const o = node("option", `${s}号 · ${view.players[s - 1].name}`);
      o.value = s;
      return o;
    }),
  );
  if ((c?.targets || []).includes(Number(selected)))
    $("target").value = selected;
  syncChoiceChips();
  $("submit-action").disabled = busy;
}
$("choice").addEventListener("change", choiceChanged);
$("enter-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (entering) return;
  entering = true;
  error("");
  try {
    // 目录加载慢时不阻塞入镇：超时后退回默认世界。
    await Promise.race([
      catalogPromise.catch(() => {}),
      new Promise((resolve) => setTimeout(resolve, 3500)),
    ]);
    const worldbook = selectedWorld || serverDefaultWorld || "mist";
    await api("enter", { password: $("password").value });
    auto = true;
    $("auto").textContent = "暂停旅人";
    render(
      await api("game", {
        role: $("role-select").value || null,
        worldbook,
      }),
    );
    $("password").value = "";
  } catch (err) {
    error(err.message, err.status ? "app" : "network");
  } finally {
    entering = false;
  }
});
$("action-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (busy) return;
  const c = view.choices.find((c) => c.tool === $("choice").value);
  if (!c) return;
  const payload = c.text
    ? { text: $("speech").value }
    : c.targets
      ? { target: Number($("target").value) }
      : {};
  const command = {
    request_id: crypto.randomUUID(),
    phase_id: view.phase_id,
    expected_version: view.version,
    tool: c.tool,
    payload,
  };
  setBusy(true);
  error("");
  try {
    render(await api("action", command));
    $("speech").value = "";
  } catch (err) {
    error(err.message, err.status ? "app" : "network");
    try {
      render(await api("state"));
    } catch {
      /* Keep current draft if offline. */
    }
  } finally {
    setBusy(false);
    choiceChanged();
  }
});
$("auto").addEventListener("click", () => {
  auto = !auto;
  $("auto").textContent = auto ? "暂停旅人" : "继续旅人";
  $("auto").setAttribute("aria-pressed", String(auto));
  if (view) render(view);
});
$("reset").addEventListener("click", () => {
  if (busy) {
    error("请等眼前这位旅人的思绪结束，再重新启程。");
    return;
  }
  if (!confirm("结束眼前的故事，重新入镇吗？")) return;
  auto = false;
  view = null;
  $("debug-panel").hidden = true;
  $("intro").hidden = false;
  $("world-picker").hidden = false;
  [
    "identity",
    "story",
    "action-form",
    "ending",
    "assistant",
    "auto",
    "reset",
  ].forEach((id) => ($(id).hidden = true));
  $("status").textContent = "";
  error("");
  applyUiState(null);
  syncDebugPolling();
  clearDebugView(debugEnabled ? "等待入镇" : "调试已关闭");
  selectWorld(selectedWorld, { silent: true });
});
$("assistant-toggle").addEventListener("click", () => {
  const hidden = !$("assistant-body").hidden;
  $("assistant-body").hidden = hidden;
  $("assistant-toggle").setAttribute("aria-expanded", String(!hidden));
});
$("query-kind").addEventListener("change", () => {
  $("query-seat").hidden = $("query-kind").value !== "summarize_player";
  $("query-text").hidden = ["self_info", "summarize_player"].includes(
    $("query-kind").value,
  );
});
$("query-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  error("");
  $("query-warning").hidden = true;
  $("query-warning").textContent = "";
  const name = $("query-kind").value,
    text = $("query-text").value;
  const payload =
    name === "ask_world"
      ? { question: text }
      : name === "search_history"
        ? { query: text }
        : name === "summarize_player"
          ? { seat: Number($("query-seat").value) }
          : name === "speech_hint"
            ? { focus: text }
            : {};
  try {
    const result = await api("query", { name, payload });
    const degraded = result.warning ? "语义检索暂不可用，已改用关键词检索。" : "";
    $("query-warning").textContent = degraded;
    $("query-warning").hidden = !degraded;
    $("answer").textContent = result.answer;
    $("sources").replaceChildren(
      ...result.sources.map((s) => {
        const d = node("details");
        d.append(
          node(
            "summary",
            s.title || `${s.source}${s.round ? " · 第" + s.round + "日" : ""}`,
          ),
          node("p", s.text),
        );
        return d;
      }),
    );
    lastHint = name === "speech_hint" ? result.answer : "";
    $("use-hint").hidden = !lastHint;
  } catch (err) {
    error(err.message, err.status ? "app" : "network");
  }
});
$("use-hint").addEventListener("click", () => {
  const speaking = view.choices.find((c) => c.tool === "speak");
  if (!speaking) {
    error("请等轮到你陈述，再把札记放入证词。");
    return;
  }
  $("choice").value = "speak";
  choiceChanged();
  $("speech").value = lastHint;
  $("speech").focus();
});
$("debug-toggle").addEventListener("click", toggleDebug);
$("sound").addEventListener("click", async () => {
  if (audio) {
    await audio.close();
    audio = null;
  } else {
    audio = new AudioContext();
    bell();
  }
  $("sound").textContent = audio ? "关闭钟声" : "开启钟声";
  $("sound").setAttribute("aria-pressed", String(!!audio));
});
async function advance() {
  if (
    !view ||
    busy ||
    !auto ||
    view.winner ||
    view.choices.some((c) => c.tool !== "explode")
  )
    return;
  setBusy(true);
  try {
    render(await api("advance", {}));
    error("");
  } catch (err) {
    error(err.message, err.status ? "app" : "network");
    if (err.status !== 409) {
      auto = false;
      $("auto").textContent = "继续旅人";
      $("auto").setAttribute("aria-pressed", "false");
    }
  } finally {
    setBusy(false);
    choiceChanged();
  }
}
window.addEventListener("offline", () =>
  error("与钟楼的联系中断了。网络恢复后会自动重试。", "network"),
);
window.addEventListener("online", () => error(""));
setInterval(advance, 1200);
root.dataset.mode = "entering";
root.dataset.busy = "no";
applyWorld("mist");
applyUiState(null);
applyDebugEnabled(true);
clearDebugView("等待入镇");
catalogPromise = loadWorldbooks();
bootDebug();
api("state")
  .then(render)
  .catch((err) => {
    if (![401, 404].includes(err.status))
      error(err.message, err.status ? "app" : "network");
  });
