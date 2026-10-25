// 公开人物绑定：只使用主线世界书的公开 personas（席位、姓名、公开描述、色标）。
// 头像图集按 seat 1..12 取帧；未知姓名或越界席位返回 null，由场景回退到
// 程序化头像。这里不读取 identity、阵营、角色或任何暗牌字段。
import DATA from "./personas.json";

export const PUBLIC_PERSONA_WORLDS = Object.freeze(
  Object.keys(DATA.worlds || {}),
);

export function publicPersonas(worldId) {
  const world = DATA.worlds?.[worldId];
  return Array.isArray(world?.personas) ? world.personas : [];
}

export function publicWorldName(worldId) {
  return DATA.worlds?.[worldId]?.name || "";
}

/**
 * 按公开席位取人物。seat 越界返回 null。
 * @returns {{seat:number, slot:number, name:string, description:string, color:string}|null}
 */
export function personaForSeat(worldId, seat) {
  const value = Number(seat);
  if (!Number.isInteger(value) || value < 1) return null;
  return publicPersonas(worldId).find((item) => item.seat === value) || null;
}

/**
 * 绑定服务器公开的玩家姓名与席位：姓名一致才返回图集 slot，否则 null。
 * 空姓名（尚未开局）只在按席位预览时使用 allowSeatOnly。
 */
export function personaSlot(worldId, seat, name, { allowSeatOnly = false } = {}) {
  const persona = personaForSeat(worldId, seat);
  if (!persona) return null;
  const known = typeof name === "string" ? name.trim() : "";
  if (!known) return allowSeatOnly ? persona.slot : null;
  return known === persona.name ? persona.slot : null;
}

/** 公开姓名 → 席位；仅用于展示映射，不参与规则或身份判断。 */
export function seatOfPersona(worldId, name) {
  const known = typeof name === "string" ? name.trim() : "";
  if (!known) return null;
  const persona = publicPersonas(worldId).find((item) => item.name === known);
  return persona ? persona.seat : null;
}
