// 四世界美术资源的唯一注册表。
import SKILL_ICONS from "./skill-icons.json";
//
// 资源按世界分目录存放于 ../assets/worlds/<world>/，在构建时由 Vite 发现；
// 尚未交接的文件不会进入打包结果，世界继续使用 scene.js / worldart.js 的
// 程序化兜底，不会因为缺图而白屏。素材到位后只需把文件放进来，不需要逐个
// 改 import。
//
// 约定（详见 临时/世界书视觉Issue/完整美术包/素材接口.md）：
//   cover.webp       独立封面（选择卡与详情）
//   scene-day.webp   白昼对局场景
//   scene-night.webp 夜晚对局场景
//   personas.webp    3 列 × 4 行透明人物图集，slot 0..11 对应 seat 1..12
//   bodies.png       十二幅全身人物，实际帧矩形见 performances.json
//   expressions.png  每人三状态；6×6仅表语义顺序，显示用实际矩形
//   icons.webp       4 列 × 4 行透明技能/状态图标
//   effects.webp     6 列 × 5 行透明动效帧
const FILES = import.meta.glob("../assets/worlds/*/*.{webp,png}", {
  eager: true,
  query: "?url",
  import: "default",
});

export const WORLD_IDS = Object.freeze([
  "mist",
  "hyperion",
  "threebody",
  "tidal_archive",
]);

const SLOT_FILES = Object.freeze({
  cover: "cover",
  day: "scene-day",
  night: "scene-night",
  personas: "personas",
  bodies: "bodies",
  expressions: "expressions",
  icons: "icons",
  effects: "effects",
});

// 图集单元格的标称尺寸（按素材接口示例）。交接图集可能被生成成其他尺寸，
// 例如 1086×1448 的 3×4 图集实际为 362×362/格；scene.js 会按图片实际像素
// 推导切片，不依赖这里的标称值，避免硬编码错位。
export const ATLAS = Object.freeze({
  personas: Object.freeze({ columns: 3, rows: 4, width: 384, height: 512 }),
  expressions: Object.freeze({ columns: 6, rows: 6 }),
  icons: Object.freeze({ columns: 4, rows: 4, width: 128, height: 128 }),
  effects: Object.freeze({ columns: 6, rows: 5, width: 256, height: 256 }),
});

export const ICON_KEYS = Object.freeze([
  "inspect",
  "antidote",
  "poison",
  "shoot",
  "explode",
  "badge",
  "vote",
  "speak",
  "abstain",
  "alive",
  "dead",
  "sheriff",
  "you",
  "disconnected",
  "night",
  "day",
]);

// 每个动效 key 对应的图集行；heal 复用治疗药草行，harm 复用暗影行，
// 客户端再以颜色和粒子区分治疗与伤害，不新增图集行或素材依赖。
const EFFECT_ROWS = Object.freeze({
  vision: 0,
  potion: 1,
  shot: 2,
  oath: 3,
  shadow: 4,
  heal: 1,
  harm: 4,
});

export const EFFECT_KEYS = Object.freeze(Object.keys(EFFECT_ROWS));

const FILE_INDEX = new Map();
Object.entries(FILES).forEach(([path, url]) => {
  const match = /assets\/worlds\/([^/]+)\/([^/]+)\.(?:webp|png)$/.exec(path);
  if (!match) return;
  const [, worldId, file] = match;
  if (!WORLD_IDS.includes(worldId)) return;
  FILE_INDEX.set(`${worldId}/${file}`, url);
});

export function isWorldId(value) {
  return typeof value === "string" && WORLD_IDS.includes(value);
}

export function worldIdOr(value, fallback = "mist") {
  return isWorldId(value) ? value : fallback;
}

function urlFor(worldId, file) {
  return FILE_INDEX.get(`${worldId}/${file}`) || null;
}

/** 技能专用图集与状态图标分开：没有覆盖时由调用方使用原世界图标。 */
export function skillIconAsset(worldId, tool) {
  const id = worldIdOr(worldId, "");
  const sheet = SKILL_ICONS[id];
  const frame = sheet && Object.hasOwn(sheet.frames, tool) ? sheet.frames[tool] : null;
  const url = sheet && frame ? urlFor(id, sheet.file) : null;
  return url ? { url, width: sheet.width, height: sheet.height, frame } : null;
}

/**
 * 返回某世界的资源 URL。未交接的槽位为 null，调用方必须显式回退。
 * @returns {{cover: string|null, day: string|null, night: string|null,
 *   personas: string|null, bodies: string|null, expressions: string|null,
 *   icons: string|null, effects: string|null}}
 */
export function worldAsset(worldId) {
  const id = worldIdOr(worldId, "");
  if (!id) {
    return {
      cover: null,
      day: null,
      night: null,
      personas: null,
      bodies: null,
      expressions: null,
      icons: null,
      effects: null,
    };
  }
  const asset = {};
  Object.entries(SLOT_FILES).forEach(([key, file]) => {
    asset[key] = urlFor(id, file);
  });
  return asset;
}

/** 资源清单状态：供测试与调试面板判断哪些世界已到齐，不用占位图冒充。 */
export function assetReport() {
  return WORLD_IDS.map((id) => {
    const asset = worldAsset(id);
    const missing = Object.entries(asset)
      .filter(([, url]) => !url)
      .map(([key]) => key);
    return { id, complete: missing.length === 0, missing };
  });
}

/** 公开席位 → 人物图集帧号；越界返回 -1，由调用方回退程序化头像。 */
export function personaFrame(seat) {
  const value = Number(seat);
  if (!Number.isInteger(value) || value < 1 || value > 12) return -1;
  return value - 1;
}

/** 技能/状态 key → 图标帧号；未知 key 返回 -1。 */
export function iconFrame(key) {
  const index = ICON_KEYS.indexOf(key);
  return index >= 0 ? index : -1;
}

/** 动效 key → 该行 6 帧的帧号数组；未知 key 返回空数组。 */
export function effectFrames(key) {
  const row = EFFECT_ROWS[key];
  if (row === undefined) return [];
  return Array.from({ length: ATLAS.effects.columns }, (_, col) => row * 6 + col);
}

/** 场景纹理 key：沿用 scene.js 现有的命名空间，避免缓存串世界。 */
export function sceneTextureKey(worldId, night) {
  return `${worldIdOr(worldId)}-scene-${night ? "night" : "day"}`;
}

/**
 * 图集纹理 key：每个世界、每类图集唯一，切换世界时按 key 释放，避免串图。
 * kind: personas / icons / effects。
 */
export function atlasTextureKey(worldId, kind) {
  const id = worldIdOr(worldId, "");
  return id ? `${id}-${kind}` : "";
}
