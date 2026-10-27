import "./themes.css";
import frameHyperion from "./assets/kenney/frame-hyperion.webp";
import frameMist from "./assets/kenney/frame-mist.webp";
import frameThreebody from "./assets/kenney/frame-threebody.webp";
import frameTidal from "./assets/kenney/frame-tidal.webp";
import skyHyperion from "./assets/kenney/sky-hyperion.webp";
import skyMist from "./assets/kenney/sky-mist.webp";
import skyThreebody from "./assets/kenney/sky-threebody.webp";
import skyTidal from "./assets/kenney/sky-tidal.webp";
import { ATLAS, iconFrame, skillIconAsset, worldAsset } from "./worlds/assets.js";
import { personaSlot, publicPersonas } from "./worlds/personas.js";

// 世界书封面与主题的唯一前端数据源。字段与 /api/worldbooks 的目录契约一致；
// 目录接口失败时，入镇页仍可用这份内置数据展示并选择四个世界。
export const FALLBACK_BOOKS = Object.freeze([
  {
    id: "mist",
    name: "雾钟镇",
    tagline: "雾夜钟声里，十二位旅人彼此试探。",
    narrator: "钟楼记事",
    summary:
      "浓雾困住钟楼广场，白昼交换证词，夜晚灯火熄灭。夜裔藏在旅人之中，铜铃只交给最值得信任的人。",
    glyph: "♜",
    motif: "bell",
    palette: {
      sky: "#0b1a21",
      mid: "#2f4a45",
      accent: "#d8bd85",
      paper: "#e9dfc6",
      ink: "#081014",
    },
    role_labels: {
      wolf: "夜裔",
      villager: "镇民",
      seer: "观星者",
      witch: "药师",
      hunter: "守林人",
      idiot: "守誓者",
    },
    public_count: 4,
    excerpt:
      "十二位旅人被浓雾困在钟楼广场。白昼交换证词，夜晚灯火熄灭。夜裔藏在人群之中。",
    scene: {
      eyebrow: "钟声之后 / CHAPTER OF THE MIST",
      title: ["有人守着灯，", "有人藏在雾里。"],
      subtitle: "听清每一句证词，再决定相信谁。",
      caption: "钟楼广场",
      chapter: "十二位旅人，一个雾夜",
      footer: "雾钟镇 · 第一卷",
      intro:
        "雾封住了出镇的路。十一位旅人已经等在广场，今夜，你会带着怎样的秘密入座？",
    },
  },
  {
    id: "hyperion",
    name: "海伯利安",
    tagline: "光阴冢外，最后一批朝圣者各怀心愿。",
    narrator: "营地纪事",
    summary:
      "边境行星海伯利安没有远距传输门，光阴冢在反熵场中缓缓移动。十二名朝圣者在冢外扎营；白天核对来历与时间，夜里有人被献祭。",
    glyph: "✶",
    motif: "tombs",
    palette: {
      sky: "#1a0f0a",
      mid: "#6b3a24",
      accent: "#d9a05b",
      paper: "#f0dfbd",
      ink: "#120b07",
    },
    role_labels: {
      wolf: "荆棘使徒",
      villager: "朝圣者",
      seer: "时隙观测者",
      witch: "随队医官",
      hunter: "霸军老兵",
      idiot: "立誓者",
    },
    public_count: 18,
    excerpt:
      "二十八世纪，霸主治下的万星网连接两百余颗行星。边境行星海伯利安没有远距传输门，只能靠飞船与漫长航程抵达。驱逐者入侵前夕，最后一批朝圣者被派往光阴冢，向伯劳提出各自的请求。本局把七人朝圣队扩为十二名在场者，这是狼人杀编制的改编。",
    scene: {
      eyebrow: "冢门将启 / CHAPTER OF THE TOMBS",
      title: ["有人向伯劳许愿，", "有人把名字藏进风里。"],
      subtitle: "在最后一支朝圣队里，分辨誓言与谎言。",
      caption: "光阴冢外营地",
      chapter: "十二名朝圣者，一个漫长的夜",
      footer: "海伯利安 · 第一卷",
      intro:
        "朝圣船停在光阴冢外，冢门尚未开启。十二名朝圣者围坐营火，今夜，你准备向伯劳许下什么愿望？",
    },
  },
  {
    id: "threebody",
    name: "三体",
    tagline: "临海监听站里，警报与沉默同时抵达。",
    narrator: "站内记录",
    summary:
      "风暴把十二名观测员困在临海监听站，三体舰队逼近的警报反复响起。站内有人替三体文明工作；白天交换证词，夜里有人被清除。",
    glyph: "◎",
    motif: "signal",
    palette: {
      sky: "#040a12",
      mid: "#17324d",
      accent: "#e2574c",
      paper: "#e8f0f6",
      ink: "#03070d",
    },
    role_labels: {
      wolf: "潜伏者",
      villager: "地球公民",
      seer: "监听员",
      witch: "面壁者",
      hunter: "执剑人",
      idiot: "冬眠者",
    },
    public_count: 24,
    excerpt:
      "十二名观测员被风暴困在临海监听站。三体舰队逼近的警报一遍遍响起，站内却有人替三体文明工作。白天众人交换证词，夜里有人被清除。",
    scene: {
      eyebrow: "信号之后 / CHAPTER OF THE SIGNAL",
      title: ["有人监听宇宙，", "有人替沉默传话。"],
      subtitle: "在舰队抵达之前，先听清频道里的每一句。",
      caption: "临海监听站",
      chapter: "十二名观测员，一次封锁",
      footer: "三体 · 第一卷",
      intro:
        "风暴封住了临海监听站的航道，舰队警报越来越近。十二名观测员守在频道前，今夜，你选择监听谁的声音？",
    },
  },
  {
    id: "tidal_archive",
    name: "潮汐档案馆",
    tagline: "潮窗之内，名字比人更先被潮水带走。",
    narrator: "馆内潮记",
    summary:
      "低潮时，十二位岛民穿过玄武岩缝进入册屿的潮汐档案馆，为校对《生民册》而来。一页名字被刮成空白；退潮只有几个时辰，下一次开门要等明天。",
    glyph: "⚓",
    motif: "tide",
    palette: {
      sky: "#06191a",
      mid: "#2d6259",
      accent: "#c98f5a",
      paper: "#f0eadb",
      ink: "#041312",
    },
    role_labels: {
      wolf: "噬名者",
      villager: "守册人",
      seer: "验潮员",
      witch: "盐药师",
      hunter: "灯守",
      idiot: "誓痕人",
    },
    public_count: 16,
    excerpt:
      "十二位来自各岛的岛民与潮册监成员在低潮时穿过玄武岩缝，进入册屿的潮汐档案馆。他们为校对《生民册》而来，却发现一页名字被刮成空白。退潮只有几个时辰，下一次开门要等明天。",
    scene: {
      eyebrow: "潮窗之内 / CHAPTER OF THE TIDE",
      title: ["有人守着名字，", "有人把名字还给海。"],
      subtitle: "趁潮水尚未合拢，核对每一页证词。",
      caption: "潮汐档案馆 · 放册台",
      chapter: "十二位岛民，一次校册",
      footer: "潮汐档案馆 · 第一卷",
      intro:
        "低潮门只开几个时辰，盐雾已经漫进册屿。十二位岛民围在放册台前，今夜，你的名字会被谁记住？",
    },
  },
]);

const BOOK_BY_ID = new Map(FALLBACK_BOOKS.map((book) => [book.id, book]));
const MOTIFS = new Set(["bell", "tombs", "signal", "tide"]);
const SKY = {
  mist: skyMist,
  hyperion: skyHyperion,
  threebody: skyThreebody,
  tidal_archive: skyTidal,
};
const FRAME = {
  mist: frameMist,
  hyperion: frameHyperion,
  threebody: frameThreebody,
  tidal_archive: frameTidal,
};
const THEME_COLOR = {
  mist: "#0b1a21",
  hyperion: "#1a0f0a",
  threebody: "#040a12",
  tidal_archive: "#06191a",
};

function worldIdOf(value) {
  const id = typeof value === "string" ? value.trim() : "";
  return BOOK_BY_ID.has(id) ? id : "mist";
}

function normalizeBook(book) {
  const fallback = BOOK_BY_ID.get(worldIdOf(book && book.id));
  if (!book || typeof book !== "object") return fallback;
  const scene = book.scene && typeof book.scene === "object" ? book.scene : {};
  const palette = book.palette && typeof book.palette === "object" ? book.palette : {};
  const labels =
    book.role_labels && typeof book.role_labels === "object"
      ? book.role_labels
      : {};
  const title = Array.isArray(scene.title)
    ? scene.title.filter((line) => typeof line === "string").slice(0, 2)
    : [];
  return {
    ...fallback,
    ...book,
    id: fallback.id,
    name: typeof book.name === "string" && book.name ? book.name : fallback.name,
    tagline:
      typeof book.tagline === "string" && book.tagline
        ? book.tagline
        : fallback.tagline,
    narrator:
      typeof book.narrator === "string" && book.narrator
        ? book.narrator
        : fallback.narrator,
    summary:
      typeof book.summary === "string" && book.summary
        ? book.summary
        : fallback.summary,
    glyph:
      typeof book.glyph === "string" && book.glyph ? book.glyph : fallback.glyph,
    motif: MOTIFS.has(book.motif) ? book.motif : fallback.motif,
    palette: { ...fallback.palette, ...palette },
    role_labels: { ...fallback.role_labels, ...labels },
    public_count:
      Number.isFinite(Number(book.public_count)) && Number(book.public_count) >= 0
        ? Number(book.public_count)
        : fallback.public_count,
    excerpt:
      typeof book.excerpt === "string" && book.excerpt
        ? book.excerpt
        : fallback.excerpt,
    scene: {
      ...fallback.scene,
      ...scene,
      title: title.length ? title : fallback.scene.title,
    },
  };
}

/** 把世界主题写到 <html>，并同步浏览器地址栏/移动端主题色。 */
export function applyWorldTheme(worldId) {
  const id = worldIdOf(worldId);
  if (typeof document === "undefined") return id;
  document.documentElement.dataset.world = id;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", THEME_COLOR[id]);
  return id;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) =>
    node.setAttribute(key, String(value)),
  );
  return node;
}

function addSvg(parent, tag, attrs = {}) {
  const node = svgEl(tag, attrs);
  parent.append(node);
  return node;
}

function coverSvg() {
  const svg = svgEl("svg", {
    class: "world-cover__motif",
    viewBox: "0 0 320 200",
    preserveAspectRatio: "xMidYMax slice",
    "aria-hidden": "true",
    focusable: "false",
  });
  return svg;
}

function soundlessImage(src, className) {
  const image = el("img", className);
  image.alt = "";
  image.decoding = "async";
  image.loading = "lazy";
  image.draggable = false;
  image.addEventListener("error", () => image.classList.add("is-missing"), {
    once: true,
  });
  image.src = src;
  return image;
}

// 封面优先使用每世界独立 cover.webp；失败时退回既有 sky-* 主题封面。
// 不用占位图冒充真实封面：两次都失败时只保留 CSS/SVG 兜底。
function coverPhoto(src, fallback, figure) {
  const image = el("img", "world-cover__photo");
  image.alt = "";
  image.decoding = "async";
  image.loading = "lazy";
  image.draggable = false;
  let attempt = src ? "art" : "sky";
  image.addEventListener("error", () => {
    if (attempt === "art") {
      attempt = "sky";
      figure.dataset.cover = "fallback";
      image.classList.remove("is-missing");
      image.src = fallback;
      return;
    }
    image.classList.add("is-missing");
  });
  image.src = src || fallback;
  return image;
}

// 图集图片按 URL 只探测一次；透明 PNG 可能迟到或被截断，探测失败时
// 调用方保留姓名首字/纯文字回退，不显示破图方块。
const imageProbe = new Map();

function probeImage(url, callback) {
  const cached = imageProbe.get(url);
  if (cached === true || cached === false) {
    callback(cached);
    return;
  }
  if (cached) {
    cached.then(callback);
    return;
  }
  const image = new Image();
  const promise = new Promise((resolve) => {
    image.onload = () =>
      resolve(image.naturalWidth > 0 && image.naturalHeight > 0);
    image.onerror = () => resolve(false);
  });
  image.decoding = "async";
  image.src = url;
  imageProbe.set(url, promise);
  promise.then((ok) => {
    imageProbe.set(url, ok);
    callback(ok);
  });
}

// 图集按列优先铺满元素；3×4 人物即 background-size:300% 400%。
function atlasSlice(slot, atlas) {
  const columns = Math.max(1, Number(atlas?.columns) || 1);
  const rows = Math.max(1, Number(atlas?.rows) || 1);
  const col = slot % columns;
  const row = Math.floor(slot / columns);
  return {
    size: `${columns * 100}% ${rows * 100}%`,
    position: `${columns > 1 ? (col / (columns - 1)) * 100 : 0}% ${
      rows > 1 ? (row / (rows - 1)) * 100 : 0
    }%`,
  };
}

/**
 * 给技能/状态元素贴 icons 图集帧。图集缺失或 key 未知返回 false，调用方
 * 不创建图标元素，退回纯文字。图标异步解码失败时隐藏，不留空方块。
 */
export function paintWorldIcon(element, worldId, key) {
  if (!element) return false;
  const iconKey = typeof key === "string" ? key : "";
  const frame = iconFrame(iconKey);
  if (frame < 0) return false;
  const icons = worldAsset(worldId).icons;
  if (!icons) return false;
  const slice = atlasSlice(frame, ATLAS.icons);
  element.dataset.icon = iconKey;
  element.dataset.iconToken = `${icons}|${frame}`;
  element.classList.add("world-icon");
  element.style.backgroundImage = `url("${icons}")`;
  element.style.backgroundSize = slice.size;
  element.style.backgroundPosition = slice.position;
  probeImage(icons, (ok) => {
    // 缓存命中时回调会同步执行，此时元素可能尚未 append；只比对 token，
    // 不依赖 isConnected。回调闭包只改自己这一枚元素，不会误改新节点。
    if (element.dataset.iconToken !== `${icons}|${frame}`) return;
    if (ok) return;
    element.hidden = true;
    element.classList.add("is-missing");
  });
  return true;
}

/** 技能按实际工具名取专用图，不把冬眠舱覆盖到普通 badge 状态。 */
export function paintWorldSkillIcon(element, worldId, tool, fallbackKey) {
  if (!element) return false;
  const asset = skillIconAsset(worldId, tool);
  if (!asset) return paintWorldIcon(element, worldId, fallbackKey);
  const { url, width, height, frame } = asset;
  const edge = Math.max(frame.width, frame.height);
  const clip = document.createElement("span");
  clip.className = "world-icon__clip";
  Object.assign(clip.style, {
    width: `${frame.width / edge * 100}%`, height: `${frame.height / edge * 100}%`,
    left: `${(1 - frame.width / edge) * 50}%`, top: `${(1 - frame.height / edge) * 50}%`,
  });
  const image = document.createElement("img");
  image.alt = "";
  image.src = url;
  Object.assign(image.style, {
    width: `${width / frame.width * 100}%`, height: `${height / frame.height * 100}%`,
    left: `${-frame.x / frame.width * 100}%`, top: `${-frame.y / frame.height * 100}%`,
  });
  clip.append(image);
  element.replaceChildren(clip);
  element.classList.add("world-icon", "world-icon--skill");
  element.dataset.skillIcon = tool;
  element.dataset.iconToken = `${url}|${tool}`;
  element.setAttribute("aria-hidden", "true");
  probeImage(url, (ok) => {
    if (element.dataset.iconToken !== `${url}|${tool}` || ok) return;
    element.hidden = true;
    element.classList.add("is-missing");
  });
  return true;
}

/**
 * 把公开席位/姓名绑定到 personas 图集 slot。未知姓名或图集缺失时显示
 * 姓名首字色块；图集解码成功后才移除首字，避免破图或伪造画像。
 */
export function paintPersonaPortrait(
  element,
  worldId,
  seat,
  name,
  { allowSeatOnly = false } = {},
) {
  if (!element) return false;
  const atlas = worldAsset(worldId).personas;
  const slot = personaSlot(worldId, seat, name, { allowSeatOnly });
  const label =
    typeof name === "string" && name.trim() ? name.trim().slice(0, 1) : "";
  element.classList.remove("has-atlas");
  element.classList.add("is-placeholder");
  element.style.removeProperty("background-image");
  element.style.removeProperty("background-size");
  element.style.removeProperty("background-position");
  element.textContent = label;
  element.dataset.personaState = "missing";
  if (!atlas || slot === null) return false;
  const slice = atlasSlice(slot, ATLAS.personas);
  const token = `${atlas}|${slot}`;
  element.dataset.personaToken = token;
  element.dataset.personaState = "loading";
  element.style.backgroundImage = `url("${atlas}")`;
  element.style.backgroundSize = slice.size;
  element.style.backgroundPosition = slice.position;
  probeImage(atlas, (ok) => {
    // 图集缓存命中时回调同步执行，元素可能还在 fragment 中未 append；
    // 因此只按 token 判断，不能要求 isConnected，否则会永远停在 loading。
    if (element.dataset.personaToken !== token) return;
    if (!ok) {
      element.classList.remove("has-atlas");
      element.classList.add("is-placeholder");
      element.style.removeProperty("background-image");
      element.style.removeProperty("background-size");
      element.style.removeProperty("background-position");
      element.textContent = label;
      element.dataset.personaState = "missing";
      return;
    }
    element.classList.remove("is-placeholder");
    element.classList.add("has-atlas");
    element.textContent = "";
    element.dataset.personaState = "ready";
  });
  return true;
}

/**
 * 详情页公开人物名册：只用 personas 数据里的 seat/slot/姓名/公开简介/色标，
 * 不读取角色、阵营或暗牌字段。返回容器，便于调用方标记状态。
 */
export function renderPersonaRoster(container, worldId) {
  if (!container || typeof container.replaceChildren !== "function")
    return null;
  const personas = publicPersonas(worldId);
  container.dataset.world = worldId;
  container.replaceChildren(
    ...personas.map((persona) => {
      const card = el("article", "world-persona");
      card.dataset.slot = String(persona.slot);
      card.dataset.seat = String(persona.seat);
      card.style.setProperty(
        "--persona-color",
        persona.color || "#b9c8bf",
      );
      const portrait = el("span", "world-persona__portrait");
      portrait.setAttribute("aria-hidden", "true");
      paintPersonaPortrait(portrait, worldId, persona.seat, persona.name, {
        allowSeatOnly: true,
      });
      const meta = el("span", "world-persona__meta");
      const name = el("span", "world-persona__name", persona.name);
      const seat = el("span", "world-persona__seat");
      const dot = el("i", "world-persona__dot");
      dot.setAttribute("aria-hidden", "true");
      seat.append(dot, document.createTextNode(`${persona.seat}号`));
      meta.append(name, seat);
      const desc = el(
        "p",
        "world-persona__desc",
        persona.description || "公开简介暂缺。",
      );
      card.append(portrait, meta, desc);
      return card;
    }),
  );
  return container;
}

function drawBell(svg) {
  addSvg(svg, "path", {
    class: "motif-deep",
    d: "M0 154 L36 132 L70 148 L108 118 L142 150 L188 122 L226 150 L268 128 L320 150 L320 200 L0 200 Z",
    opacity: ".55",
  });
  addSvg(svg, "path", {
    class: "motif-deep",
    d: "M0 176 L320 176 L320 200 L0 200 Z",
  });
  // 钟楼：塔身、钟室、尖顶与拱门
  addSvg(svg, "rect", { class: "motif-fill", x: 128, y: 78, width: 64, height: 96 });
  addSvg(svg, "rect", { class: "motif-deep", x: 136, y: 86, width: 8, height: 88, opacity: ".45" });
  addSvg(svg, "path", { class: "motif-fill", d: "M118 80 L160 38 L202 80 Z" });
  addSvg(svg, "path", { class: "motif-deep", d: "M146 80 L160 58 L174 80 Z", opacity: ".65" });
  addSvg(svg, "rect", { class: "motif-deep", x: 146, y: 118, width: 28, height: 56, rx: 13 });
  addSvg(svg, "rect", { class: "motif-fill", x: 148, y: 94, width: 24, height: 22, rx: 4 });
  addSvg(svg, "circle", { class: "motif-accent", cx: 160, cy: 105, r: 7 });
  addSvg(svg, "line", { class: "motif-line", x1: 160, y1: 38, x2: 160, y2: 24 });
  addSvg(svg, "circle", { class: "motif-accent", cx: 160, cy: 21, r: 2.5 });
  // 两侧屋顶与窗灯
  const houses = [
    [28, 138, 48, 38],
    [76, 146, 40, 30],
    [202, 142, 42, 34],
    [246, 150, 46, 26],
  ];
  houses.forEach(([x, y, w, h], index) => {
    addSvg(svg, "rect", { class: "motif-deep", x, y, width: w, height: h });
    addSvg(svg, "path", {
      class: "motif-fill",
      d: `M${x - 6} ${y + 1} L${x + w / 2} ${y - 22 - (index % 2) * 6} L${x + w + 6} ${y + 1} Z`,
    });
    addSvg(svg, "rect", { class: "motif-accent", x: x + 10, y: y + 12, width: 5, height: 7, opacity: ".85" });
    addSvg(svg, "rect", { class: "motif-accent", x: x + w - 15, y: y + 12, width: 5, height: 7, opacity: ".65" });
  });
  // 广场石纹与月光
  addSvg(svg, "ellipse", { class: "motif-line", cx: 160, cy: 184, rx: 96, ry: 12, opacity: ".5", fill: "none" });
  addSvg(svg, "ellipse", { class: "motif-line", cx: 160, cy: 184, rx: 62, ry: 7, opacity: ".35", fill: "none" });
  addSvg(svg, "circle", { class: "motif-accent", cx: 160, cy: 183, r: 4 });
}

function drawTombs(svg) {
  addSvg(svg, "path", {
    class: "motif-deep",
    d: "M0 138 Q46 102 96 132 T190 122 T284 132 T320 118 L320 200 L0 200 Z",
    opacity: ".65",
  });
  addSvg(svg, "path", {
    class: "motif-fill",
    d: "M0 158 Q58 128 118 152 T230 144 T320 152 L320 200 L0 200 Z",
  });
  // 三座光阴冢与拉长的影子
  const tombs = [
    [54, 120, 52],
    [132, 106, 64],
    [226, 116, 48],
  ];
  tombs.forEach(([x, y, w], index) => {
    addSvg(svg, "path", {
      class: "motif-deep",
      d: `M${x - 22} 174 L${x - 8} ${y + 8} L${x + w + 8} ${y + 8} L${x + w + 22} 174 Z`,
      opacity: ".5",
    });
    addSvg(svg, "path", {
      class: "motif-fill",
      d: `M${x} 174 L${x + 9} ${y} L${x + w - 9} ${y} L${x + w} 174 Z`,
    });
    addSvg(svg, "path", {
      class: "motif-deep",
      d: `M${x + w / 2 - 8} 174 L${x + w / 2 - 8} ${y + 48} Q${x + w / 2} ${y + 38} ${x + w / 2 + 8} ${y + 48} L${x + w / 2 + 8} 174 Z`,
    });
    addSvg(svg, "line", {
      class: "motif-line",
      x1: x + 5,
      y1: y + 5,
      x2: x + w - 5,
      y2: y + 5,
      opacity: ".5",
    });
    if (index === 1) {
      addSvg(svg, "circle", { class: "motif-accent", cx: x + w / 2, cy: y + 26, r: 3 });
      addSvg(svg, "circle", { class: "motif-line", cx: x + w / 2, cy: y + 26, r: 8, fill: "none", opacity: ".5" });
    }
  });
  // 泰斯拉树
  addSvg(svg, "path", {
    class: "motif-fill",
    d: "M286 178 L291 104 L296 178 Z",
  });
  addSvg(svg, "path", {
    class: "motif-line",
    d: "M293 140 L270 118 M294 128 L316 102 M292 116 L278 92 M294 108 L306 82 M293 96 L286 70",
    fill: "none",
  });
  addSvg(svg, "path", {
    class: "motif-line",
    d: "M282 92 Q270 74 286 62 M306 82 Q320 66 306 54",
    fill: "none",
    opacity: ".75",
  });
  addSvg(svg, "path", {
    class: "motif-accent",
    d: "M293 150 Q274 128 282 116 Q294 132 293 150 Z M294 142 Q312 122 304 108 Q292 124 294 142 Z",
    opacity: ".55",
  });
  // 时间波纹与星屑
  [44, 70].forEach((radius, index) => {
    addSvg(svg, "circle", {
      class: "motif-line",
      cx: 160,
      cy: 74,
      r: radius,
      fill: "none",
      opacity: String(0.28 - index * 0.08),
    });
  });
  [
    [32, 44],
    [66, 28],
    [104, 48],
    [246, 36],
    [302, 58],
  ].forEach(([cx, cy]) => {
    addSvg(svg, "circle", { class: "motif-accent", cx, cy, r: 1.2, opacity: ".8" });
  });
}

function drawSignal(svg) {
  addSvg(svg, "rect", { class: "motif-deep", x: 0, y: 148, width: 320, height: 52, opacity: ".7" });
  addSvg(svg, "line", { class: "motif-line", x1: 0, y1: 148, x2: 320, y2: 148, opacity: ".65" });
  // 临海监听站
  addSvg(svg, "path", { class: "motif-fill", d: "M28 148 L28 104 L182 96 L182 148 Z" });
  addSvg(svg, "path", { class: "motif-deep", d: "M22 104 L190 96 L190 88 L22 96 Z" });
  addSvg(svg, "rect", { class: "motif-deep", x: 44, y: 116, width: 22, height: 12 });
  addSvg(svg, "rect", { class: "motif-deep", x: 78, y: 114, width: 22, height: 12 });
  addSvg(svg, "rect", { class: "motif-deep", x: 112, y: 112, width: 22, height: 12 });
  addSvg(svg, "rect", { class: "motif-accent", x: 146, y: 110, width: 14, height: 8, opacity: ".9" });
  // 碟形天线与格构塔
  addSvg(svg, "line", { class: "motif-fill", x1: 214, y1: 150, x2: 214, y2: 62 });
  addSvg(svg, "path", {
    class: "motif-line",
    d: "M206 150 L214 62 L222 150 M206 132 L222 132 M208 114 L220 114 M210 96 L218 96 M211 80 L217 80",
    fill: "none",
  });
  addSvg(svg, "ellipse", {
    class: "motif-fill",
    cx: 242,
    cy: 62,
    rx: 31,
    ry: 18,
    transform: "rotate(-22 242 62)",
  });
  addSvg(svg, "ellipse", {
    class: "motif-deep",
    cx: 244,
    cy: 65,
    rx: 17,
    ry: 8,
    transform: "rotate(-22 244 65)",
  });
  addSvg(svg, "line", { class: "motif-line", x1: 242, y1: 62, x2: 258, y2: 58 });
  addSvg(svg, "circle", { class: "motif-accent", cx: 259, cy: 57, r: 3 });
  // 扫描弧与三颗太阳的刻度
  [38, 58, 78].forEach((radius, index) => {
    addSvg(svg, "path", {
      class: "motif-line",
      d: `M${242 + radius} 62 A${radius} ${radius} 0 0 1 ${242 + radius * 0.2} ${62 + radius}`,
      fill: "none",
      opacity: String(0.42 - index * 0.1),
    });
  });
  addSvg(svg, "rect", { class: "motif-accent", x: 26, y: 172, width: 30, height: 3, opacity: ".75" });
  addSvg(svg, "rect", { class: "motif-accent", x: 64, y: 172, width: 8, height: 3, opacity: ".45" });
  addSvg(svg, "line", { class: "motif-line", x1: 198, y1: 148, x2: 198, y2: 196, opacity: ".5" });
  addSvg(svg, "line", { class: "motif-line", x1: 258, y1: 148, x2: 258, y2: 196, opacity: ".35" });
}

function drawTide(svg) {
  // 群岛与海面
  addSvg(svg, "path", {
    class: "motif-deep motif-archive",
    d: "M0 132 Q36 112 70 128 T142 126 T218 132 T286 120 L320 128 L320 200 L0 200 Z",
    opacity: ".72",
  });
  addSvg(svg, "path", {
    class: "motif-fill motif-archive",
    d: "M0 158 Q48 144 96 156 T190 152 T288 160 L320 156 L320 200 L0 200 Z",
  });
  // 通往档案馆的玄武岩堤道
  addSvg(svg, "path", {
    class: "motif-deep motif-archive",
    d: "M0 184 L98 166 L112 172 L12 196 Z",
    opacity: ".85",
  });
  // 档案馆：台基、柱廊、圆顶与潮痕（AI 背景已含建筑时由 CSS 隐藏）
  addSvg(svg, "rect", { class: "motif-fill motif-archive", x: 92, y: 110, width: 136, height: 56 });
  addSvg(svg, "path", { class: "motif-fill motif-archive", d: "M84 112 Q160 60 236 112 Z" });
  addSvg(svg, "path", { class: "motif-deep motif-archive", d: "M104 112 Q160 74 216 112 Z", opacity: ".55" });
  addSvg(svg, "rect", { class: "motif-deep motif-archive", x: 82, y: 166, width: 156, height: 8 });
  for (let i = 0; i < 5; i += 1) {
    addSvg(svg, "rect", { class: "motif-deep motif-archive", x: 108 + i * 23, y: 122, width: 9, height: 42 });
  }
  addSvg(svg, "rect", { class: "motif-deep motif-archive", x: 150, y: 132, width: 20, height: 34, rx: 10 });
  addSvg(svg, "circle", { class: "motif-accent motif-archive", cx: 160, cy: 92, r: 4 });
  addSvg(svg, "line", { class: "motif-line motif-archive", x1: 160, y1: 60, x2: 160, y2: 48 });
  // 潮线
  [180, 188, 196].forEach((y, index) => {
    addSvg(svg, "path", {
      class: "motif-line",
      d: `M${8 + index * 12} ${y} Q${78 + index * 20} ${y - 8} ${150 + index * 26} ${y} T${316 - index * 8} ${y}`,
      fill: "none",
      opacity: String(0.36 - index * 0.08),
    });
  });
  // 漂动纸页
  [
    [42, 96, -16],
    [268, 106, 12],
    [288, 142, -8],
  ].forEach(([x, y, rotate]) => {
    addSvg(svg, "rect", {
      class: "motif-paper",
      x,
      y,
      width: 15,
      height: 20,
      transform: `rotate(${rotate} ${x + 7} ${y + 10})`,
      opacity: ".7",
    });
    addSvg(svg, "line", {
      class: "motif-line",
      x1: x + 3,
      y1: y + 6,
      x2: x + 12,
      y2: y + 6,
      opacity: ".5",
    });
    addSvg(svg, "line", {
      class: "motif-line",
      x1: x + 3,
      y1: y + 10,
      x2: x + 10,
      y2: y + 10,
      opacity: ".5",
    });
  });
}

const MOTIF_DRAW = {
  bell: drawBell,
  tombs: drawTombs,
  signal: drawSignal,
  tide: drawTide,
};

function buildSeal(book) {
  const seal = el("span", "world-cover__seal");
  seal.setAttribute("aria-hidden", "true");
  const frame = soundlessImage(FRAME[book.id], "world-cover__frame");
  const glyph = el("span", "world-cover__glyph", book.glyph);
  seal.append(frame, glyph);
  return seal;
}

function buildPlate(book) {
  const plate = el("figcaption", "world-cover__plate");
  plate.append(
    el("span", "world-cover__volume", book.scene.footer),
    el("span", "world-cover__name", book.name),
    el("span", "world-cover__tagline", book.tagline),
  );
  const foot = el("span", "world-cover__foot");
  const caption = el("span", "world-cover__caption");
  const dot = el("i", "world-cover__dot");
  dot.setAttribute("aria-hidden", "true");
  caption.append(dot, el("span", undefined, book.scene.caption));
  foot.append(caption);
  if (book.public_count > 0) {
    foot.append(
      el(
        "span",
        "world-cover__count",
        `${book.public_count} 则公开档案`,
      ),
    );
  }
  plate.append(foot);
  return plate;
}

function addWeather(figure, book) {
  const weatherA = el("span", "world-cover__weather world-cover__weather--a");
  const weatherB = el("span", "world-cover__weather world-cover__weather--b");
  weatherA.setAttribute("aria-hidden", "true");
  weatherB.setAttribute("aria-hidden", "true");
  figure.append(weatherA, weatherB);
  if (book.motif === "tide") {
    [
      ["8%", "0s"],
      ["46%", "-5.5s"],
      ["74%", "-11s"],
    ].forEach(([x, delay]) => {
      const page = el("span", "world-cover__page");
      page.setAttribute("aria-hidden", "true");
      page.style.setProperty("--page-x", x);
      page.style.setProperty("--page-delay", delay);
      figure.append(page);
    });
  }
}

/**
 * 在给定容器内绘制世界书封面。只清空容器并创建本模块生成的 DOM/SVG；
 * 所有书名、说明与 API 文本都通过 textContent 写入，不使用 innerHTML。
 */
export function renderCover(container, book, { reducedMotion = false } = {}) {
  if (!container || typeof container.replaceChildren !== "function")
    return null;
  const data = normalizeBook(book);
  const figure = el("figure", "world-cover");
  figure.dataset.world = data.id;
  figure.dataset.motif = data.motif;
  figure.dataset.motion = reducedMotion ? "reduced" : "full";
  const cover = worldAsset(data.id).cover;
  figure.dataset.cover = cover ? "art" : "fallback";
  figure.setAttribute(
    "aria-label",
    `${data.name}：${data.tagline}。${data.scene.caption}。`,
  );

  const sceneLayer = el("div", "world-cover__scene");
  sceneLayer.setAttribute("aria-hidden", "true");
  sceneLayer.append(
    coverPhoto(cover, SKY[data.id], figure),
    el("span", "world-cover__wash"),
    el("span", "world-cover__orb"),
  );

  const svg = coverSvg();
  MOTIF_DRAW[data.motif](svg);
  sceneLayer.append(svg, el("span", "world-cover__grain"));

  figure.append(sceneLayer, buildSeal(data), buildPlate(data));
  addWeather(figure, data);
  container.replaceChildren(figure);
  return figure;
}

// 模块加载即给出雾钟镇兜底主题，避免首屏在目录请求返回前闪回默认灰。
if (typeof document !== "undefined")
  applyWorldTheme(document.documentElement.dataset.world || "mist");
