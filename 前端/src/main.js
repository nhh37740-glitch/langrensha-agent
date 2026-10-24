import "./style.css";
import { makeScene } from "./scene.js";
const $ = (id) => document.getElementById(id);
const scene = makeScene();
let view = null,
  auto = true,
  busy = false,
  entering = false,
  lastHint = "",
  audio = null,
  sounded = 0;
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function error(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
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
  scene.update(state);
  $("intro").hidden = true;
  ["identity", "story", "reset", "auto", "assistant"].forEach(
    (id) => ($(id).hidden = false),
  );
  $("chapter").textContent = state.chapter;
  $("story-title").textContent = state.chapter;
  $("day").textContent =
    `第 ${state.round} 日 · ${state.night ? "夜雾" : "晨光"}`;
  $("role-title").textContent = `${state.identity} · ${state.seat}号`;
  $("role-note").textContent =
    state.note ||
    (state.alive
      ? "秘密只属于你。留心每一位旅人的证词。"
      : "你的席位已空，仍可旁听公开的故事。");
  $("resources").textContent = Object.entries(state.resources)
    .map(([k, v]) => `${k} ${v ? "●" : "○"}`)
    .join(" / ");
  $("alive-count").textContent =
    `${state.players.filter((p) => p.alive).length} 位仍在场`;
  $("roster").replaceChildren(
    ...state.players.map((p) => {
      const n = node(
        "div",
        undefined,
        "person" +
          (!p.alive ? " departed" : "") +
          (p.seat === state.seat ? " you" : ""),
      );
      const portrait = node("span", p.name[0], "portrait");
      portrait.style.setProperty("--person", p.color);
      n.append(
        portrait,
        node("span", `${String(p.seat).padStart(2, "0")} ${p.name}`),
        node(
          "small",
          p.sheriff ? "执铃人" : p.role || (p.alive ? "身份未明" : "已离场"),
        ),
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
  $("action-form").hidden = !state.choices.length;
  choiceChanged();
  $("status").textContent = state.winner
    ? ""
    : state.choices.length
      ? "你可以从容决定，没有倒数。"
      : auto
        ? "旅人在雾中思索，请稍候……"
        : "旅人暂歇。你仍可翻阅札记。";
  $("ending").hidden = !state.winner;
  if (state.winner)
    $("ending").textContent = state.story.at(-1)?.text || "故事结束。";
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
}
function choiceChanged() {
  const c = view?.choices.find((c) => c.tool === $("choice").value);
  $("speech").hidden = !c?.text;
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
  $("submit-action").disabled = busy;
}
$("choice").addEventListener("change", choiceChanged);
$("enter-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (entering) return;
  entering = true;
  error("");
  try {
    await api("enter", { password: $("password").value });
    auto = true;
    $("auto").textContent = "暂停旅人";
    render(await api("game", { role: $("role-select").value || null }));
    $("password").value = "";
  } catch (e) {
    error(e.message);
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
  busy = true;
  error("");
  try {
    render(await api("action", command));
    $("speech").value = "";
  } catch (e) {
    error(e.message);
    try {
      render(await api("state"));
    } catch {
      /* Keep current draft if offline. */
    }
  } finally {
    busy = false;
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
  $("intro").hidden = false;
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
  } catch (e) {
    error(e.message);
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
  busy = true;
  try {
    render(await api("advance", {}));
    error("");
  } catch (e) {
    error(e.message);
    if (e.status !== 409) {
      auto = false;
      $("auto").textContent = "继续旅人";
      $("auto").setAttribute("aria-pressed", "false");
    }
  } finally {
    busy = false;
    choiceChanged();
  }
}
setInterval(advance, 1200);
api("state")
  .then(render)
  .catch((e) => {
    if (![401, 404].includes(e.status)) error(e.message);
  });
