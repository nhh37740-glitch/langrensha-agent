// 正文只来自服务端阅读接口；浏览器不按隐藏角色猜测可见范围。
export function makeReader(world, api) {
  const panel = document.getElementById("reading-panel");
  let current = null;
  let lastKey = null;
  let sequence = 0;
  let chapters = [];
  const select = document.getElementById("reading-chapter");
  const paragraph = (text) => {
    const p = document.createElement("p");
    p.textContent = text;
    return p;
  };
  function show(id) {
    const chapter = chapters.find((item) => item.id === id);
    if (!chapter) return;
    current = chapter.id;
    select.value = current;
    document.getElementById("reading-title").textContent = chapter.title;
    document.getElementById("reading-meta").textContent = chapter.private
      ? "你的身份手记，仅本人可见"
      : `对局前的往事 · 人物：${chapter.cast.join("、")}`;
    document.getElementById("reading-text").replaceChildren(
      ...chapter.text.split(/\n\s*\n/).map(paragraph),
    );
  }
  select.addEventListener("change", () => show(select.value));
  async function refresh(state = null, force = false) {
    if (!world) return;
    const key = [state?.game_id, state?.round, state?.phase, state?.winner].join(":");
    if (!force && key === lastKey) return;
    lastKey = key;
    const ticket = ++sequence;
    try {
      const result = await api(`reading/${world}`);
      if (ticket !== sequence || result.worldbook !== world) return;
      chapters = result.chapters;
      select.replaceChildren(...chapters.map((chapter) => {
        const option = document.createElement("option");
        option.value = chapter.id;
        option.textContent = `${chapter.private ? "私密 · " : ""}${chapter.title}`;
        return option;
      }));
      show(chapters.some((item) => item.id === current) ? current : chapters[0]?.id);
      document.getElementById("reading-status").textContent =
        `已开放 ${chapters.length} 篇，随昼夜与终局继续展开；可随时回看。`;
      panel.hidden = !chapters.length;
    } catch {
      if (ticket !== sequence) return;
      lastKey = null;
      panel.hidden = false;
      document.getElementById("reading-status").textContent = "正文暂未取回，请重试。";
    }
  }
  document.getElementById("reading-retry").addEventListener("click", () => refresh(null, true));
  return { refresh };
}
