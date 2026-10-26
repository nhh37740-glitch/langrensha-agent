import Phaser from "phaser";
import skyHyperion from "./assets/kenney/sky-hyperion.webp";
import skyMist from "./assets/kenney/sky-mist.webp";
import skyThreebody from "./assets/kenney/sky-threebody.webp";
import skyTidal from "./assets/kenney/sky-tidal.webp";
import {
  ATLAS,
  atlasTextureKey,
  effectFrames,
  iconFrame,
  sceneTextureKey,
  worldAsset,
} from "./worlds/assets.js";
import { personaSlot, publicPersonas } from "./worlds/personas.js";
import PERFORMANCES from "./worlds/performances.json";

// 四套世界共用一块固定舞台，只按 state.worldbook 切换天空、建筑、地面、
// 环境动效与人物。人物只按公开席位/姓名绑定，绝不按身份着色。
const WIDTH = 840;
const HEIGHT = 570;
const FALLBACK_COLORS = [
  0xd6ba87, 0xf1c86d, 0x92cbd6, 0xb3a4d8, 0x80c3b5, 0xd7ad85, 0x9caec4,
  0xd99ab2, 0xa9c78b, 0xd6a0cf, 0xc9907e, 0x82b9b4,
];
// 人物胸像在席位框内的显示尺寸；图集按图片实际像素推导后等比裁切，不拉伸。
// 只保留最近两个世界的纹理：当前世界 + 上一个世界，切回时无需重新下载。
const TEXTURE_WORLD_LIMIT = 2;
// 昼夜真实背景交叉淡化的时长；减少动效时直接切换。
const SCENE_FADE_MS = 900;
const EFFECT_FRAME_MS = 80;
const EFFECT_DISPLAY = 104;
// 席位容器深度约为 10+486/8≈71；效果层必须在其上，否则会被头像框整个盖住。
const FX_DEPTH = 76;
const VEIL_DEPTH = 92;
const ATLAS_PARTS = Object.freeze({
  personas: ATLAS.personas,
  icons: ATLAS.icons,
  effects: ATLAS.effects,
});
const EFFECT_COLORS = {
  vision: 0x9dc4ff,
  potion: 0x9ed0a4,
  heal: 0x8fe3a4,
  harm: 0xc58bd8,
  shot: 0xffe4a1,
  oath: 0xe9cf94,
  shadow: 0xb59ad0,
};

const SKY_KEYS = {
  mist: "sky-mist",
  hyperion: "sky-hyperion",
  threebody: "sky-threebody",
  tidal_archive: "sky-tidal",
};
const TEXTURE_URLS = {
  "sky-mist": skyMist,
  "sky-hyperion": skyHyperion,
  "sky-threebody": skyThreebody,
  "sky-tidal": skyTidal,
};

const WORLD = {
  mist: {
    name: "雾钟镇",
    place: "钟楼广场",
    font: '"Songti SC", "Noto Serif CJK SC", serif',
    accent: 0xd8bd85,
    tagColor: "#c9b98e",
    flash: 0xf1e6c8,
    frame: 0xd8bd85,
    skyAlpha: (night) => (night ? 0.68 : 0.34),
    skyTint: (night) => (night ? 0xa9c2bc : 0xf6f1df),
  },
  hyperion: {
    name: "海伯利安",
    place: "光阴冢外营地",
    font: '"Kaiti SC", "STKaiti", "Noto Serif CJK SC", serif',
    accent: 0xd8a657,
    tagColor: "#d8b07a",
    flash: 0xe2a566,
    frame: 0xd8a657,
    skyAlpha: (night) => (night ? 0.62 : 0.82),
    skyTint: (night) => (night ? 0xc7987c : 0xffe2b4),
  },
  threebody: {
    name: "三体",
    place: "临海监听站",
    font: '"PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif',
    accent: 0xe2574c,
    tagColor: "#c2d1dc",
    flash: 0xbfe2f2,
    frame: 0x9fb9ca,
    skyAlpha: (night) => (night ? 0.55 : 0.4),
    skyTint: (night) => (night ? 0x8eabc4 : 0xe4f2ff),
  },
  tidal_archive: {
    name: "潮汐档案馆",
    place: "放册台",
    font: '"Songti SC", "Noto Serif CJK SC", serif',
    accent: 0xce9560,
    tagColor: "#c4d6cd",
    flash: 0xe8dfc5,
    frame: 0xce9560,
    skyAlpha: (night) => (night ? 0.78 : 0.92),
    skyTint: (night) => (night ? 0x9db7b1 : 0xfff2df),
  },
};

function pseudo(index, salt = 0) {
  const value = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return value - Math.floor(value);
}
function normalizeWorld(value) {
  return typeof value === "string" && WORLD[value] ? value : "mist";
}

class WorldScene extends Phaser.Scene {
  constructor(reducedMotion = false, onSelectSeat = () => {}) {
    super("town");
    this.people = [];
    this.motionTweens = [];
    this.idleTweens = [];
    this.failedTextures = new Set();
    this.state = null;
    this.lastEffect = 0;
    this.reducedMotion = reducedMotion;
    this.night = null;
    this.ready = false;
    this.worldId = null;
    this.previewWorld = null;
    this.profile = WORLD.mist;
    this.skyImage = null;
    this.backgroundDay = null;
    this.backgroundNight = null;
    this.backgroundTween = null;
    this.phaseIcon = null;
    this.worldAssets = new Map();
    this.loadingTextures = new Map();
    this.textureWorlds = [];
    this.effectTimers = [];
    this.destroyed = false;
    this.onSelectSeat = onSelectSeat;
    this.focusedSeat = null;
  }

  preload() {
    this.load.on("loaderror", (file) => {
      const key = file && file.key;
      if (key) this.failedTextures.add(key);
    });
    Object.entries(TEXTURE_URLS).forEach(([key, url]) => {
      this.load.image(key, url);
    });
  }

  hasTexture(key) {
    return Boolean(key) && !this.failedTextures.has(key) && this.textures.exists(key);
  }

  /* ---------- 世界资源懒加载与纹理保留 ---------- */

  // Vite 只把真实存在的素材写进 glob；这里按需加载当前世界，未交接的槽位
  // 仍为 null，不请求、不伪造，直接走 scene.js 原有兜底。
  ensureWorldAssets(worldId) {
    const id = normalizeWorld(worldId);
    if (!this.worldAssets.has(id)) {
      this.worldAssets.set(id, worldAsset(id));
    }
    const asset = this.worldAssets.get(id);
    const parts = [
      ["day", sceneTextureKey(id, false), asset.day, "scene"],
      ["night", sceneTextureKey(id, true), asset.night, "scene"],
      ["personas", atlasTextureKey(id, "personas"), asset.personas, "personas"],
      ["bodies", atlasTextureKey(id, "bodies"), asset.bodies, "bodies"],
      ["icons", atlasTextureKey(id, "icons"), asset.icons, "icons"],
      ["effects", atlasTextureKey(id, "effects"), asset.effects, "effects"],
    ];
    parts.forEach(([kind, key, url, mode]) => {
      this.loadWorldTexture(id, key, url, mode, kind);
    });
  }

  loadWorldTexture(worldId, key, url, mode, kind) {
    if (
      !url ||
      !key ||
      this.destroyed ||
      this.hasTexture(key) ||
      this.failedTextures.has(key) ||
      this.loadingTextures.has(key)
    ) {
      return;
    }
    const image = new Image();
    this.loadingTextures.set(key, image);
    image.onload = () => {
      this.loadingTextures.delete(key);
      if (this.destroyed) return;
      if (!image.naturalWidth || !image.naturalHeight) {
        this.failedTextures.add(key);
        return;
      }
      let texture = null;
      try {
        const spec = ATLAS_PARTS[mode];
        if (mode === "bodies") {
          // 清理后的全身图仍按实际透明内容取边界；不假设生成器严格等格。
          texture = this.textures.addImage(key, image);
          (PERFORMANCES.worlds[worldId] || []).forEach((frame, slot) => {
            texture.add(slot, 0, frame.x, frame.y, frame.width, frame.height);
          });
        } else if (spec) {
          // 交接图集可能不是接口示例的标称尺寸（如 1086×1448 → 362/格）；
          // 一律按实际像素推导单元格，避免硬编码切片错位。
          const frameWidth = Math.max(1, Math.floor(image.naturalWidth / spec.columns));
          const frameHeight = Math.max(1, Math.floor(image.naturalHeight / spec.rows));
          texture = this.textures.addSpriteSheet(key, image, {
            frameWidth,
            frameHeight,
          });
        } else {
          texture = this.textures.addImage(key, image);
        }
      } catch {
        texture = null;
      }
      if (!texture) {
        this.failedTextures.add(key);
        return;
      }
      // 快速切换世界时，旧世界的图片可能在淘汰后才加载完成；立刻回收，
      // 避免缓存里留下无人管理的纹理。
      if (!this.textureWorlds.includes(worldId)) {
        this.releaseWorldTextures(worldId);
        return;
      }
      this.afterWorldTexture(worldId, kind);
    };
    image.onerror = () => {
      this.loadingTextures.delete(key);
      if (!this.destroyed) this.failedTextures.add(key);
    };
    image.src = url;
  }

  afterWorldTexture(worldId, kind) {
    if (this.destroyed || !this.ready || worldId !== this.worldId) return;
    if (kind === "day" || kind === "night") {
      this.drawWorld(Boolean(this.night), false);
    } else if (["personas", "bodies"].includes(kind)) {
      this.refreshPeople();
      this.updateFocus();
    } else if (kind === "icons") {
      this.refreshPeople();
      this.updatePhaseIcon();
    }
  }

  hasWorldTexture(worldId, kind) {
    if (kind === "day" || kind === "night") {
      return this.hasTexture(sceneTextureKey(worldId, kind === "night"));
    }
    return this.hasTexture(atlasTextureKey(worldId, kind));
  }

  retainWorldTextures(worldId) {
    this.textureWorlds = [
      worldId,
      ...this.textureWorlds.filter((id) => id !== worldId),
    ];
    const evicted = this.textureWorlds.slice(TEXTURE_WORLD_LIMIT);
    this.textureWorlds = this.textureWorlds.slice(0, TEXTURE_WORLD_LIMIT);
    evicted.forEach((id) => this.releaseWorldTextures(id));
  }

  releaseWorldTextures(worldId) {
    if (!worldId || worldId === this.worldId) return;
    const keys = [
      sceneTextureKey(worldId, false),
      sceneTextureKey(worldId, true),
      atlasTextureKey(worldId, "personas"),
      atlasTextureKey(worldId, "bodies"),
      atlasTextureKey(worldId, "icons"),
      atlasTextureKey(worldId, "effects"),
    ];
    keys.forEach((key) => {
      if (this.hasTexture(key) && !this.textureInUse(key)) {
        this.textures.remove(key);
      }
    });
  }

  textureInUse(key) {
    if (!key) return false;
    const images = [
      this.skyImage,
      this.backgroundDay,
      this.backgroundNight,
      this.phaseIcon,
    ];
    this.people.forEach((person) => {
      [
        person.portrait,
        person.figure,
        person.statusIcon,
        person.youIcon,
        person.sheriffIcon,
      ].forEach((image) => {
        if (image) images.push(image);
      });
    });
    return images.some((image) => image.texture && image.texture.key === key);
  }

  create() {
    this.cameras.main.setBackgroundColor("#050b10");
    this.buildLayers();
    this.buildPeople();
    this.buildFocus();
    this.ready = true;
    this.setWorld(
      normalizeWorld(this.previewWorld || this.state?.worldbook),
      false,
    );
    this.applyNight(Boolean(this.state?.night), false);
    if (this.state) this.applyState(this.state);
    else this.drawEmptyPeople();
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.destroyed = true;
      this.motionTweens.forEach((tween) => tween.stop());
      this.motionTweens = [];
      this.idleTweens.forEach((tween) => tween.stop());
      this.idleTweens = [];
      this.effectTimers.forEach((timer) => timer.remove(false));
      this.effectTimers = [];
      this.loadingTextures.forEach((image) => {
        image.onload = null;
        image.onerror = null;
      });
      this.loadingTextures.clear();
      if (this.backgroundTween) this.backgroundTween.stop();
      this.focusPanel?.remove();
      this.focusObserver?.disconnect();
    });
  }

  buildLayers() {
    this.skyG = this.add.graphics().setDepth(0);
    this.skyImage = null;
    const initialSky = Object.values(SKY_KEYS).find((key) => this.hasTexture(key));
    if (initialSky) {
      this.skyImage = this.add
        .image(WIDTH / 2, HEIGHT / 2, initialSky)
        .setDepth(0.8)
        .setVisible(false);
    }
    // 真实昼夜背景分两层叠放：稳定在底层，上层只做透明度交叉淡化。
    this.backgroundDay = this.add
      .image(WIDTH / 2, HEIGHT / 2)
      .setDepth(1)
      .setVisible(false);
    this.backgroundNight = this.add
      .image(WIDTH / 2, HEIGHT / 2)
      .setDepth(1.05)
      .setVisible(false);
    this.tintG = this.add.graphics().setDepth(1.2);
    this.celestialG = this.add.graphics().setDepth(2);
    this.farG = this.add.graphics().setDepth(3);
    this.midG = this.add.graphics().setDepth(4);
    this.nearG = this.add.graphics().setDepth(5);
    this.groundG = this.add.graphics().setDepth(6);
    this.detailG = this.add.graphics().setDepth(7);
    this.ambient = this.add.container(0, 0).setDepth(8);
    this.fx = this.add.container(0, 0).setDepth(FX_DEPTH);
    this.worldTag = this.add
      .text(WIDTH - 20, 40, "", {
        fontFamily: '"Songti SC", "Noto Serif CJK SC", serif',
        fontSize: "9px",
        color: "#c9b98e",
        letterSpacing: 1.4,
      })
      .setOrigin(1, 0)
      .setDepth(31)
      .setAlpha(0.82);
    this.phaseIcon = this.add
      .image(WIDTH - 28, 66)
      .setDepth(31)
      .setAlpha(0.9)
      .setVisible(false);
    this.veil = this.add
      .rectangle(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT, 0x000000, 0)
      .setDepth(VEIL_DEPTH);
  }

  buildPeople() {
    for (let index = 0; index < 12; index++) {
      const aura = this.add.graphics();
      const shadow = this.add.graphics();
      const figure = this.add.image(0, 0).setOrigin(0.5, 1).setVisible(false);
      const portrait = this.add.image(0, -32).setVisible(false);
      const rig = this.add.container(0, 0, [figure, portrait]);
      const statusIcon = this.add.image(-25, 10).setVisible(false);
      const youIcon = this.add.image(0, -150).setVisible(false);
      const sheriffIcon = this.add.image(20, 10).setVisible(false);
      const label = this.add.text(0, 14, "", {
        fontFamily: '"Songti SC", "Noto Serif CJK SC", serif',
        fontSize: 11,
        color: "#efe6d4",
        backgroundColor: "#0b171bcf",
        padding: { x: 4, y: 3 },
      }).setOrigin(0.5, 0).setDepth(85);
      label.setInteractive({ useHandCursor: true });
      label.on("pointerdown", (_pointer, _x, _y, event) => {
        event.stopPropagation();
        this.selectSeat(index + 1);
      });
      const container = this.add.container(0, 0, [shadow, aura, rig, statusIcon, youIcon, sheriffIcon]);
      container.setSize(80, 150);
      container.setInteractive(new Phaser.Geom.Rectangle(-40, -140, 80, 172), Phaser.Geom.Rectangle.Contains);
      container.input.cursor = "pointer";
      container.on("pointerdown", () => this.selectSeat(index + 1));
      this.people.push({ container, aura, shadow, rig, figure, portrait,
        statusIcon, youIcon, sheriffIcon, label, seat: index + 1,
        idleTween: null, spot: null, state: "neutral" });
    }
  }

  buildFocus() {
    const wrap = document.getElementById("scene-wrap");
    if (!wrap) return;
    const panel = document.createElement("section");
    panel.id = "scene-focus";
    panel.className = "scene-focus";
    panel.setAttribute("aria-label", "人物神态特写");
    panel.hidden = true;
    const face = document.createElement("div");
    face.className = "scene-focus__face";
    face.setAttribute("aria-hidden", "true");
    const clip = document.createElement("div");
    clip.className = "scene-focus__clip";
    const portrait = document.createElement("img");
    portrait.alt = "";
    clip.append(portrait);
    face.append(clip);
    const copy = document.createElement("div");
    copy.className = "scene-focus__copy";
    const title = document.createElement("strong");
    title.id = "scene-focus-name";
    const state = document.createElement("span");
    state.id = "scene-focus-state";
    const description = document.createElement("p");
    description.id = "scene-focus-description";
    const controls = document.createElement("nav");
    controls.setAttribute("aria-label", "查看人物");
    for (const [text, action] of [
      ["上一位", () => this.selectSeat(((this.focusSeatValue || 1) + 10) % 12 + 1)],
      ["下一位", () => this.selectSeat((this.focusSeatValue || 1) % 12 + 1)],
      ["跟随发言", () => { this.focusedSeat = null; this.updateFocus(); }],
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "quiet";
      button.textContent = text;
      button.addEventListener("click", action);
      controls.append(button);
    }
    copy.append(title, state, description, controls);
    panel.append(face, copy);
    wrap.insertAdjacentElement("afterend", panel);
    this.focusPanel = panel;
    this.focusFace = face;
    this.focusClip = clip;
    this.focusPortrait = portrait;
    this.focusTitle = title;
    this.focusState = state;
    this.focusDescription = description;
    this.focusObserver = new ResizeObserver(() => this.updateFocus());
    this.focusObserver.observe(face);
  }

  selectSeat(seat) {
    if (!Number.isInteger(seat) || seat < 1 || seat > 12) return;
    this.focusedSeat = seat;
    this.updateFocus();
    this.onSelectSeat(seat);
  }

  updateFocus() {
    if (!this.focusPanel) return;
    const players = this.state?.players;
    const mood = this.peopleState(this.state);
    const seat = this.focusedSeat || mood.speakingSeat || this.state?.seat || 1;
    const player = players?.find((item) => item.seat === seat);
    if (!player || this.worldId !== this.state?.worldbook) {
      this.focusPanel.hidden = true;
      return;
    }
    const slot = personaSlot(this.worldId, seat, player.name);
    const state = !player.alive ? "neutral" : seat === mood.speakingSeat ? "speaking" : mood.waiting || mood.voting ? "thinking" : "neutral";
    const stateIndex = { neutral: 0, speaking: 1, thinking: 2 }[state];
    const frame = slot === null ? -1 : slot * 3 + stateIndex;
    const url = worldAsset(this.worldId).expressions;
    this.focusPanel.hidden = false;
    this.focusPanel.dataset.world = this.worldId;
    this.focusPanel.dataset.seat = String(seat);
    this.focusPanel.dataset.expression = state;
    this.focusPanel.dataset.frame = String(frame);
    // 生成图的行基线不等距；按逐格复核的主轮廓边界展示，避免上一行肩衣碎条。
    const sheet = PERFORMANCES.expressions[this.worldId];
    const rect = sheet?.frames[frame];
    this.focusPortrait.hidden = !url || !rect;
    if (url && rect) {
      this.focusPortrait.src = url;
      const width = this.focusFace.clientWidth;
      const height = this.focusFace.clientHeight;
      const scale = Math.min(width / rect.width, height / rect.height);
      Object.assign(this.focusClip.style, {
        width: `${rect.width * scale}px`, height: `${rect.height * scale}px`,
        left: `${(width - rect.width * scale) / 2}px`,
        top: `${(height - rect.height * scale) / 2}px`,
      });
      Object.assign(this.focusPortrait.style, {
        width: `${sheet.width * scale}px`, height: `${sheet.height * scale}px`,
        left: `${-rect.x * scale}px`,
        top: `${-rect.y * scale}px`,
      });
    }
    this.focusFace.classList.toggle("departed", !player.alive);
    this.focusTitle.textContent = `${seat}号 · ${player.name}`;
    this.focusState.textContent = !player.alive ? "已经离场" : state === "speaking" ? "正在发言" : mood.voting ? "表决中的思索" : state === "thinking" ? "凝神思索" : "静候下一句证词";
    this.focusDescription.textContent = player.description || "";
    this.focusSeatValue = seat;
  }

  clearGraphics() {
    [
      this.skyG,
      this.tintG,
      this.celestialG,
      this.farG,
      this.midG,
      this.nearG,
      this.groundG,
      this.detailG,
    ].forEach((graphics) => graphics.clear());
  }

  fitCover(image, key, alpha, tint) {
    const source = this.textures.get(key).getSourceImage();
    if (!source || !source.width || !source.height) return;
    const scale = Math.max(WIDTH / source.width, HEIGHT / source.height);
    image
      .setTexture(key)
      .setScale(scale)
      .setPosition(WIDTH / 2, HEIGHT / 2)
      .setAlpha(alpha)
      .setTint(tint)
      .setVisible(true);
  }

  fitBackground(image, key) {
    const source = this.textures.get(key)?.getSourceImage();
    if (!source || !source.width || !source.height) return false;
    const scale = Math.max(WIDTH / source.width, HEIGHT / source.height);
    image
      .setTexture(key)
      .setScale(scale)
      .setPosition(WIDTH / 2, HEIGHT / 2)
      .clearTint()
      .setVisible(true);
    return true;
  }

  // 隐藏时同时清掉纹理引用，否则被淘汰世界的纹理会被隐藏图片“占用”而无法释放。
  clearImageTexture(image) {
    if (!image) return;
    image.setVisible(false);
    if (image.texture && image.texture.key !== "__DEFAULT") {
      image.setTexture("__DEFAULT");
    }
  }

  hideBackgrounds() {
    if (this.backgroundTween) {
      this.backgroundTween.stop();
      this.backgroundTween = null;
    }
    if (this.backgroundDay) {
      this.backgroundDay.setAlpha(0);
      this.clearImageTexture(this.backgroundDay);
    }
    if (this.backgroundNight) {
      this.backgroundNight.setAlpha(0);
      this.clearImageTexture(this.backgroundNight);
    }
  }

  // 返回 true 表示当前世界已用真实场景图，程序化绘制整体让位；
  // 只有单张时复用该图并用明暗色偏表现另一时段，不混用照片与画笔。
  updateSceneBackground(night, animate = true) {
    if (!this.backgroundDay || !this.backgroundNight) return false;
    const dayKey = sceneTextureKey(this.worldId, false);
    const nightKey = sceneTextureKey(this.worldId, true);
    const dayReady = this.hasTexture(dayKey);
    const nightReady = this.hasTexture(nightKey);
    if (!dayReady && !nightReady) {
      this.hideBackgrounds();
      return false;
    }
    if (this.skyImage) this.skyImage.setVisible(false);
    if (dayReady && nightReady) {
      if (!this.fitBackground(this.backgroundDay, dayKey)) return false;
      if (!this.fitBackground(this.backgroundNight, nightKey)) return false;
      this.backgroundDay.setVisible(true);
      this.backgroundNight.setVisible(true);
      if (this.backgroundTween) {
        this.backgroundTween.stop();
        this.backgroundTween = null;
      }
      if (!animate || this.reducedMotion) {
        this.backgroundDay.setAlpha(night ? 0 : 1);
        this.backgroundNight.setAlpha(night ? 1 : 0);
        return true;
      }
      // 用代理值同时驱动两层 alpha：上层淡入多少，底层就淡出多少。
      const state = { value: this.backgroundNight.alpha };
      const day = this.backgroundDay;
      const nightLayer = this.backgroundNight;
      this.backgroundTween = this.tweens.add({
        targets: state,
        value: night ? 1 : 0,
        duration: SCENE_FADE_MS,
        ease: "Sine.easeInOut",
        onUpdate: () => {
          day.setAlpha(1 - state.value);
          nightLayer.setAlpha(state.value);
        },
        onComplete: () => {
          this.backgroundTween = null;
        },
      });
      return true;
    }
    const onlyDay = dayReady;
    const key = onlyDay ? dayKey : nightKey;
    const image = onlyDay ? this.backgroundDay : this.backgroundNight;
    const other = onlyDay ? this.backgroundNight : this.backgroundDay;
    if (this.backgroundTween) {
      this.backgroundTween.stop();
      this.backgroundTween = null;
    }
    other.setAlpha(0);
    this.clearImageTexture(other);
    if (!this.fitBackground(image, key)) return false;
    image.setAlpha(1);
    if (night && onlyDay) {
      image.setTint(0x8290a6);
      this.tintG.fillStyle(0x06121a, 0.18);
      this.tintG.fillRect(0, 0, WIDTH, HEIGHT);
    } else if (!night && !onlyDay) {
      image.setTint(0xffe3bd);
      this.tintG.fillStyle(0xffe9c8, 0.16);
      this.tintG.fillRect(0, 0, WIDTH, HEIGHT);
    }
    return true;
  }

  updateSkyImage(night) {
    if (!this.skyImage) return;
    const key = SKY_KEYS[this.worldId];
    const visibleKey = this.hasTexture(key) ? key : null;
    if (!visibleKey) {
      this.skyImage.setVisible(false);
      return;
    }
    this.fitCover(
      this.skyImage,
      visibleKey,
      this.profile.skyAlpha(night),
      this.profile.skyTint(night),
    );
  }

  setWorld(worldId, animate = true) {
    const id = normalizeWorld(worldId);
    if (this.worldId === id) {
      this.ensureWorldAssets(id);
      return;
    }
    const previous = this.worldId;
    this.worldId = id;
    this.profile = WORLD[id];
    this.focusedSeat = null;
    this.ensureWorldAssets(id);
    this.drawWorld(Boolean(this.night), false);
    this.positionPeople();
    this.buildAmbient(id);
    this.refreshPeople();
    this.updateWorldTag();
    this.updatePhaseIcon();
    this.updateFocus();
    this.retainWorldTextures(id);
    if (this.ready && previous && animate && !this.reducedMotion) {
      this.flash(this.profile.flash, 0.26);
    }
  }

  drawWorld(night, animateBackground = true) {
    this.clearGraphics();
    if (this.updateSceneBackground(night, animateBackground)) return;
    this.updateSkyImage(night);
    const painter = {
      mist: this.drawMist,
      hyperion: this.drawHyperion,
      threebody: this.drawThreebody,
      tidal_archive: this.drawTidal,
    }[this.worldId];
    if (painter) painter.call(this, night);
  }

  drawStars(count, alpha, salt = 0) {
    const g = this.celestialG;
    for (let i = 0; i < count; i++) {
      const x = Math.round(pseudo(i, 1 + salt) * WIDTH);
      const y = Math.round(pseudo(i, 2 + salt) * 255) + 8;
      const radius = i % 7 === 0 ? 1.8 : 0.9;
      g.fillStyle(0xdfe7dc, alpha * (0.5 + pseudo(i, 3 + salt) * 0.5));
      g.fillCircle(x, y, radius);
    }
  }

  drawMoon(x, y, radius, color, alpha) {
    const g = this.celestialG;
    g.fillStyle(color, alpha * 0.1);
    g.fillCircle(x, y, radius * 2.6);
    g.fillStyle(color, alpha * 0.18);
    g.fillCircle(x, y, radius * 1.7);
    g.fillStyle(color, alpha);
    g.fillCircle(x, y, radius);
    g.fillStyle(0xfffbeb, alpha * 0.72);
    g.fillCircle(x - radius * 0.22, y - radius * 0.24, radius * 0.62);
  }

  drawEmptyPeople() {
    this.people.forEach((person, index) => {
      this.drawPerson(person.seat, {
        alive: true,
        you: false,
        sheriff: false,
        color: FALLBACK_COLORS[index],
        name: "",
        // 尚未开局时按公开席位预览本世界人物；只有素材存在时才显示。
        preview: true,
      });
    });
  }

  refreshPeople() {
    const players = this.state?.players;
    if (!Array.isArray(players) || !players.length) {
      this.drawEmptyPeople();
      return;
    }
    const mood = this.peopleState(this.state);
    players.forEach((player) => {
      this.drawPerson(player.seat, {
        alive: player.alive,
        you: player.seat === this.state.seat,
        sheriff: Boolean(player.sheriff),
        color: player.color,
        name: player.name,
        description: player.description,
        speaking: player.seat === mood.speakingSeat,
        thinking: mood.waiting && player.seat !== this.state.seat,
        voting: mood.voting,
      });
    });
  }

  positionPeople() {
    const spots = this.layoutFor(this.worldId);
    this.people.forEach((person, index) => {
      person.spot = spots[index];
      person.container.setPosition(person.spot.x, person.spot.y).setScale(1).setRotation(0);
      person.container.setDepth(10 + person.spot.y / 8);
      this.startIdle(person);
    });
    const host = document.getElementById("scene");
    if (host) host.dataset.layout = this.worldId;
  }

  startIdle(person) {
    if (person.idleTween) {
      const old = person.idleTween;
      old.stop();
      this.idleTweens = this.idleTweens.filter((tween) => tween !== old);
      person.idleTween = null;
    }
    person.rig.setScale(1);
    if (this.reducedMotion) return;
    // 只对人物上身作轻微呼吸形变；脚底和姓名不随动画漂移。
    const tween = this.tweens.add({
      targets: person.rig, scaleY: { from: 1, to: 1.007 + person.seat % 3 * 0.002 },
      duration: 2200 + person.seat % 5 * 280, yoyo: true, repeat: -1, ease: "Sine.easeInOut",
    });
    person.idleTween = tween;
    this.idleTweens.push(tween);
  }

  layoutFor(worldId) {
    // 坐标是完整人物的脚底；按场景地面/台阶/石径分组，不再按4×3人墙排列。
    // 最低脚底512 + 姓名32 < 550，且给底部场景说明留出空间。
    const layouts = {
      mist: [
        [124, 471, 134], [226, 397, 116], [659, 465, 135], [567, 391, 112],
        [710, 531, 151], [436, 530, 153], [94, 547-32, 145], [302, 478, 138],
        [373, 387, 112], [537, 493, 140], [731, 388, 108], [262, 535-14, 148],
      ],
      hyperion: [
        [129, 443, 132], [246, 392, 116], [690, 445, 135], [342, 491, 142],
        [555, 391, 112], [701, 526, 151], [744, 367, 106], [129, 527, 148],
        [434, 419, 120], [310, 357, 106], [537, 525, 148], [345, 544-23, 146],
      ],
      threebody: [
        [110, 475, 130], [244, 414, 120], [397, 383, 110], [526, 485, 142],
        [719, 424, 124], [310, 519, 150], [594, 371, 106], [699, 524, 151],
        [111, 380, 110], [436, 532-12, 150], [606, 444, 129], [187, 529-5, 145],
      ],
      tidal_archive: [
        [496, 515, 142], [652, 484, 130], [366, 523, 143], [485, 411, 114],
        [588, 365, 100], [701, 528, 145], [124, 508, 134], [276, 445, 124],
        [386, 359, 101], [709, 402, 115], [231, 526, 144], [505, 325, 91],
      ],
    };
    return (layouts[worldId] || layouts.mist).map(([x, y, height]) => ({ x, y: Math.min(512, y), height }));
  }

  updateWorldTag() {
    if (!this.worldTag) return;
    const ending = this.state?.winner ? " · 故事已落幕" : "";
    this.worldTag.setText(`${this.profile.name} · ${this.profile.place}${ending}`);
    this.worldTag.setColor(this.profile.tagColor);
    this.worldTag.setFontFamily(this.profile.font);
  }

  // 昼夜图标只用公开 phase；素材缺失时不画，页面原有的 phase-chip 仍是兜底。
  updatePhaseIcon() {
    if (!this.phaseIcon) return;
    const key = this.hasWorldTexture(this.worldId, "icons")
      ? atlasTextureKey(this.worldId, "icons")
      : null;
    const frame = iconFrame(this.night ? "night" : "day");
    if (!key || frame < 0) {
      this.clearImageTexture(this.phaseIcon);
      return;
    }
    this.phaseIcon
      .setTexture(key, frame)
      .setDisplaySize(20, 20)
      .setAlpha(0.9)
      .setVisible(true);
  }

  /* ---------- 雾钟镇 ---------- */
  drawMist(night) {
    const g = this.skyG;
    if (night) g.fillGradientStyle(0x08111a, 0x0b151f, 0x1b3038, 0x223a3e, 1);
    else g.fillGradientStyle(0x55716d, 0x647f78, 0x9bb3a4, 0xb3c5ae, 1);
    g.fillRect(0, 0, WIDTH, HEIGHT);
    for (let i = 0; i < 5; i++) {
      g.fillStyle(night ? 0x33505a : 0xd7e0cd, 0.05 + i * 0.012);
      g.fillEllipse(420, 150 + i * 34, 780 - i * 60, 120 - i * 8);
    }
    g.fillStyle(night ? 0x0a1622 : 0x2f4a45, 0.5);
    g.fillRect(0, 284, WIDTH, HEIGHT - 284);

    this.drawStars(54, night ? 0.75 : 0.08, 2);
    this.drawMoon(672, 88, 30, 0xe8ddb4, night ? 1 : 0.18);
    this.drawMistFar(night);
    this.drawMistTower(night);
    this.drawMistHouses(night);
    this.drawMistPlaza(night);
    this.drawMistLamps(night);
  }

  drawMistFar(night) {
    const g = this.farG;
    const far = night ? 0x142329 : 0x44605a;
    const near = night ? 0x0f1c22 : 0x3a544d;
    g.fillStyle(far, 1);
    g.fillPoints(
      [
        { x: -20, y: 300 },
        { x: 120, y: 214 },
        { x: 250, y: 286 },
        { x: 398, y: 196 },
        { x: 520, y: 286 },
        { x: 690, y: 222 },
        { x: 860, y: 300 },
        { x: 860, y: 340 },
        { x: -20, y: 340 },
      ],
      true,
    );
    g.fillStyle(near, 1);
    g.fillPoints(
      [
        { x: -20, y: 312 },
        { x: 96, y: 268 },
        { x: 206, y: 308 },
        { x: 360, y: 250 },
        { x: 512, y: 308 },
        { x: 662, y: 258 },
        { x: 860, y: 312 },
        { x: 860, y: 352 },
        { x: -20, y: 352 },
      ],
      true,
    );
  }

  drawMistTower(night) {
    const g = this.midG;
    const stone = night ? 0x2b3c39 : 0x5c6f63;
    const stoneDark = night ? 0x1d2c2c : 0x46594f;
    const stoneLight = night ? 0x3c524b : 0x76897a;
    const windowLight = night ? 0xf3d38c : 0xaebfa8;
    g.fillStyle(stoneDark, 1);
    g.fillRect(360, 176, 120, 198);
    g.fillStyle(stone, 1);
    g.fillRect(366, 186, 108, 182);
    g.fillStyle(stoneLight, 0.55);
    g.fillRect(372, 192, 10, 170);
    g.fillRect(458, 192, 8, 170);
    g.lineStyle(1, stoneDark, 0.75);
    for (let row = 0; row < 8; row++) {
      const y = 200 + row * 21;
      g.lineBetween(366, y, 474, y);
    }
    g.fillStyle(night ? 0x13211f : 0x33443a, 1);
    g.fillRoundedRect(398, 288, 44, 84, 22);
    g.fillRect(398, 330, 44, 42);
    g.lineStyle(2, stoneLight, 0.5);
    g.strokeRoundedRect(398, 288, 44, 84, 22);
    g.fillStyle(stoneDark, 1);
    g.fillRect(386, 362, 68, 8);
    g.fillRect(376, 370, 88, 8);
    g.fillStyle(stone, 1);
    g.fillRect(374, 120, 92, 60);
    g.fillStyle(stoneLight, 0.4);
    g.fillRect(380, 126, 8, 50);
    g.fillStyle(night ? 0x101d1d : 0x2f4038, 1);
    g.fillRoundedRect(394, 130, 52, 44, 22);
    g.fillStyle(0xe3c67d, night ? 0.95 : 0.75);
    g.fillRoundedRect(408, 142, 24, 18, 6);
    g.fillCircle(420, 152, 9);
    g.fillStyle(0x8a6f3e, 1);
    g.fillCircle(420, 163, 3);
    g.lineStyle(2, 0xd8bd85, 0.9);
    g.lineBetween(420, 142, 420, 134);
    g.lineBetween(402, 132, 438, 132);
    g.fillStyle(night ? 0x1a2a2c : 0x3b4f47, 1);
    g.fillPoints(
      [
        { x: 348, y: 124 },
        { x: 420, y: 54 },
        { x: 492, y: 124 },
      ],
      true,
    );
    g.fillStyle(stoneLight, 0.35);
    g.fillPoints(
      [
        { x: 360, y: 121 },
        { x: 420, y: 66 },
        { x: 438, y: 84 },
      ],
      true,
    );
    g.lineStyle(3, 0xd8bd85, 0.8);
    g.lineBetween(420, 54, 420, 32);
    g.fillStyle(0xe3c67d, 0.95);
    g.fillCircle(420, 30, 3.5);
    if (night) {
      g.fillStyle(windowLight, 0.85);
      g.fillRoundedRect(380, 222, 14, 26, 7);
      g.fillRoundedRect(446, 222, 14, 26, 7);
      g.fillStyle(windowLight, 0.18);
      g.fillCircle(387, 235, 26);
      g.fillCircle(453, 235, 26);
    } else {
      g.fillStyle(0x2f423a, 0.9);
      g.fillRoundedRect(380, 222, 14, 26, 7);
      g.fillRoundedRect(446, 222, 14, 26, 7);
    }
    g.fillStyle(0xf3d38c, night ? 0.12 : 0.05);
    g.fillCircle(420, 158, 44);
  }

  drawMistHouses(night) {
    const g = this.midG;
    const wall = night ? 0x1c2b2d : 0x45594e;
    const roof = night ? 0x142124 : 0x35463f;
    const light = night ? 0xf3d38c : 0x9fb29c;
    const spots = [
      [24, 226, 92, 124, 0],
      [130, 210, 78, 140, 1],
      [222, 238, 104, 112, 2],
      [516, 232, 96, 118, 1],
      [626, 210, 84, 140, 2],
      [722, 240, 96, 110, 0],
    ];
    for (const [x, top, width, height, variant] of spots) {
      g.fillStyle(wall, 1);
      g.fillRect(x, top, width, height);
      g.fillStyle(roof, 1);
      if (variant === 0) {
        g.fillPoints(
          [
            { x: x - 8, y: top + 2 },
            { x: x + width / 2, y: top - 34 },
            { x: x + width + 8, y: top + 2 },
          ],
          true,
        );
      } else if (variant === 1) {
        g.fillPoints(
          [
            { x: x - 6, y: top + 4 },
            { x: x + width * 0.38, y: top - 26 },
            { x: x + width * 0.62, y: top - 26 },
            { x: x + width + 6, y: top + 4 },
          ],
          true,
        );
      } else {
        g.fillRect(x - 6, top, width + 12, 8);
        g.fillPoints(
          [
            { x: x - 6, y: top + 2 },
            { x: x + width / 2, y: top - 24 },
            { x: x + width + 6, y: top + 2 },
          ],
          true,
        );
      }
      const bottom = top + height;
      g.fillStyle(night ? 0x0e1a1a : 0x2b3c34, 1);
      g.fillRoundedRect(x + width / 2 - 10, bottom - 44, 20, 44, 9);
      const windowAlpha = night ? 0.9 : 0.5;
      g.fillStyle(light, windowAlpha);
      g.fillRect(x + 14, top + 26, 12, 16);
      g.fillRect(x + width - 26, top + 26, 12, 16);
      if (night) {
        g.fillStyle(light, 0.14);
        g.fillCircle(x + 20, top + 34, 18);
        g.fillCircle(x + width - 20, top + 34, 18);
      }
    }
  }

  drawMistPlaza(night) {
    const g = this.groundG;
    g.fillStyle(night ? 0x10201f : 0x33483f, 1);
    g.fillEllipse(420, 430, 840, 300);
    g.fillStyle(night ? 0x0c1a1a : 0x2b3e37, 1);
    g.fillEllipse(420, 470, 900, 260);
    for (let i = 0; i < 5; i++) {
      g.lineStyle(1, night ? 0x51695f : 0x8ba690, 0.16);
      g.strokeEllipse(420, 432, 640 - i * 96, 246 - i * 38);
    }
    g.lineStyle(1, night ? 0x3a524b : 0x6d8574, 0.2);
    for (let i = 0; i < 24; i++) {
      const angle = (i / 24) * Math.PI * 2;
      g.lineBetween(
        420 + Math.cos(angle) * 96,
        432 + Math.sin(angle) * 40,
        420 + Math.cos(angle) * 330,
        432 + Math.sin(angle) * 130,
      );
    }
    g.lineStyle(1.5, night ? 0xc7ab72 : 0x8f7f55, 0.5);
    g.strokeCircle(420, 432, 54);
    g.strokeCircle(420, 432, 40);
    g.fillStyle(night ? 0xc7ab72 : 0x8f7f55, 0.32);
    g.fillCircle(420, 432, 26);
    g.fillStyle(night ? 0xf0d79b : 0xd6c8a3, 0.7);
    g.fillRoundedRect(408, 424, 24, 16, 5);
    g.fillCircle(420, 432, 7);
    g.lineStyle(1.5, night ? 0xf0d79b : 0xd6c8a3, 0.6);
    g.lineBetween(420, 424, 420, 418);
  }

  drawMistLamps(night) {
    const g = this.detailG;
    this.lampSpots = [
      [122, 402],
      [718, 402],
    ];
    for (const [x, y] of this.lampSpots) {
      g.lineStyle(3, 0x2f453f, 1);
      g.lineBetween(x, y, x, y - 96);
      g.fillStyle(0x2f453f, 1);
      g.fillCircle(x, y - 96, 5);
      g.fillStyle(0x1b2c2b, 1);
      g.fillRoundedRect(x - 9, y - 108, 18, 22, 4);
      g.fillStyle(0xf3d38c, night ? 0.95 : 0.62);
      g.fillRoundedRect(x - 6, y - 105, 12, 16, 3);
    }
    g.lineStyle(1, night ? 0x6b7f70 : 0x8ba690, 0.3);
    g.strokeEllipse(420, 448, 300, 74);
  }

  buildMistAmbient() {
    for (let i = 0; i < 3; i++) {
      const fog = this.add
        .ellipse(420, 330 + i * 70, 980 + i * 120, 120 + i * 26, 0xa9c6c2, [
          0.05, 0.07, 0.05,
        ][i])
        .setDepth(2 + i);
      this.ambient.add(fog);
      this.trackTween({
        targets: fog,
        x: i % 2 === 0 ? 720 : 120,
        duration: 26000 + i * 7000,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
    for (const [x, y] of this.lampSpots || []) {
      const glow = this.add.circle(x, y - 96, 54, 0xf3d38c, 0.16);
      glow.setBlendMode(Phaser.BlendModes.ADD);
      this.ambient.add(glow);
      this.trackTween({
        targets: glow,
        alpha: 0.07,
        duration: 2400 + x,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
    for (let i = 0; i < 9; i++) {
      const x = 90 + pseudo(i, 7) * 660;
      const y = 300 + pseudo(i, 8) * 190;
      const fly = this.add.circle(x, y, 1.8, 0xf4d48f, 0.85);
      fly.setBlendMode(Phaser.BlendModes.ADD);
      this.ambient.add(fly);
      this.trackTween({
        targets: fly,
        y: y - 18 - pseudo(i, 9) * 22,
        alpha: 0.2,
        duration: 2600 + pseudo(i, 10) * 2600,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
  }

  /* ---------- 海伯利安 ---------- */
  drawHyperion(night) {
    const g = this.skyG;
    if (night) g.fillGradientStyle(0x100a12, 0x1b1018, 0x4a2a22, 0x5a3220, 1);
    else g.fillGradientStyle(0x4a2a1e, 0x6b3a24, 0xc88a4e, 0xb97a45, 1);
    g.fillRect(0, 0, WIDTH, HEIGHT);
    for (let i = 0; i < 4; i++) {
      g.fillStyle(night ? 0x8a4a32 : 0xf0c987, 0.04 + i * 0.012);
      g.fillEllipse(520 - i * 40, 180 + i * 28, 720 - i * 90, 72 + i * 18);
    }
    this.drawStars(64, night ? 0.85 : 0.08, 7);
    this.drawHyperionPlanet(night);
    this.drawHyperionDunes(night);
    this.drawHyperionTombs(night);
    this.drawHyperionGround(night);
  }

  drawHyperionPlanet(night) {
    const g = this.celestialG;
    const body = night ? 0xb87347 : 0xe0a45e;
    const rim = night ? 0xf0c987 : 0xffedc7;
    g.fillStyle(body, 0.14);
    g.fillCircle(660, 94, 92);
    g.fillStyle(body, night ? 0.88 : 0.78);
    g.fillCircle(660, 94, 47);
    g.fillStyle(rim, night ? 0.38 : 0.52);
    g.fillCircle(648, 82, 39);
    g.fillStyle(night ? 0x421b0e : 0x8a4a26, 0.35);
    g.fillCircle(676, 104, 33);
    g.lineStyle(2, rim, 0.45);
    g.strokeEllipse(660, 94, 168, 42);
    g.lineStyle(1, rim, 0.24);
    g.strokeEllipse(660, 94, 192, 52);
    g.fillStyle(rim, 0.7);
    g.fillCircle(742, 62, 3);
    g.fillCircle(592, 142, 2);
  }

  drawHyperionDunes(night) {
    const far = this.farG;
    const ridgeFar = night ? 0x2a1712 : 0x6b3a24;
    const ridgeMid = night ? 0x3b2117 : 0x8a4a26;
    far.fillStyle(ridgeFar, 1);
    far.fillPoints(
      [
        { x: -30, y: 310 },
        { x: 92, y: 268 },
        { x: 196, y: 302 },
        { x: 320, y: 262 },
        { x: 462, y: 304 },
        { x: 600, y: 258 },
        { x: 730, y: 300 },
        { x: 880, y: 276 },
        { x: 880, y: 360 },
        { x: -30, y: 360 },
      ],
      true,
    );
    far.fillStyle(ridgeMid, 1);
    far.fillPoints(
      [
        { x: -30, y: 340 },
        { x: 110, y: 306 },
        { x: 230, y: 336 },
        { x: 380, y: 300 },
        { x: 520, y: 338 },
        { x: 670, y: 306 },
        { x: 880, y: 338 },
        { x: 880, y: 382 },
        { x: -30, y: 382 },
      ],
      true,
    );
    far.lineStyle(1, night ? 0xd8a657 : 0xf0c987, 0.18);
    far.lineBetween(0, 336, 880, 318);
    for (let i = 0; i < 6; i++) {
      const x = 70 + i * 138;
      far.fillStyle(night ? 0x1b0d08 : 0x4a2718, 0.8);
      far.fillPoints(
        [
          { x: x - 18, y: 328 },
          { x: x, y: 300 - pseudo(i, 2) * 24 },
          { x: x + 15, y: 328 },
        ],
        true,
      );
      far.lineStyle(1, 0xd8a657, 0.2);
      far.lineBetween(x, 301, x, 328);
    }
  }

  drawHyperionTombs(night) {
    const g = this.midG;
    const body = night ? 0x24130d : 0x5a3420;
    const dark = night ? 0x120a07 : 0x2a1810;
    const cap = night ? 0xb87347 : 0xd8a657;
    const doorColor = night ? 0x050302 : 0x160c07;
    const tombs = [
      [148, 392, 88, 134],
      [310, 398, 104, 158],
      [548, 390, 82, 126],
    ];
    for (const [x, baseY, width, height] of tombs) {
      const topY = baseY - height;
      g.fillStyle(dark, 0.55);
      g.fillPoints(
        [
          { x: x + width * 0.2, y: baseY },
          { x: x + width * 0.44, y: topY + 18 },
          { x: x + width * 1.4, y: topY + 52 },
          { x: x + width * 1.2, y: baseY },
        ],
        true,
      );
      g.fillStyle(body, 1);
      g.fillPoints(
        [
          { x: x - width / 2, y: baseY },
          { x: x - width * 0.34, y: topY },
          { x: x + width * 0.34, y: topY },
          { x: x + width / 2, y: baseY },
        ],
        true,
      );
      g.fillStyle(cap, 0.8);
      g.fillRect(x - width * 0.38, topY - 4, width * 0.76, 5);
      g.lineStyle(1, cap, 0.35);
      g.lineBetween(x - width * 0.28, topY + 18, x + width * 0.28, topY + 18);
      g.fillStyle(doorColor, 1);
      g.fillRoundedRect(
        x - 10,
        baseY - height * 0.54,
        20,
        height * 0.54,
        10,
      );
      g.fillStyle(cap, 0.65);
      g.fillCircle(x, topY + 30, 2.4);
    }
    this.drawTeslaTree(g, 704, 398, 172, night);
    this.drawTeslaTree(g, 84, 384, 116, night);
  }

  drawTeslaTree(g, x, baseY, height, night) {
    const trunk = night ? 0x3d1d11 : 0x6b3a24;
    const branch = night ? 0x7d3c22 : 0x9a5530;
    g.lineStyle(5, trunk, 1);
    g.lineBetween(x, baseY, x, baseY - height);
    g.lineStyle(2, branch, 0.9);
    g.lineBetween(x, baseY - height * 0.28, x - 34, baseY - height * 0.54);
    g.lineBetween(x, baseY - height * 0.38, x + 38, baseY - height * 0.62);
    g.lineBetween(x, baseY - height * 0.56, x - 26, baseY - height * 0.78);
    g.lineBetween(x, baseY - height * 0.68, x + 28, baseY - height * 0.9);
    g.lineBetween(x, baseY - height * 0.8, x - 18, baseY - height * 0.98);
    g.lineStyle(1.2, night ? 0xf0c987 : 0xffe6b0, 0.68);
    for (let i = 0; i < 3; i++) {
      const y = baseY - height * (0.5 + i * 0.13);
      g.beginPath();
      g.moveTo(x, y);
      g.lineTo(x - 12, y - 8);
      g.lineTo(x - 4, y - 14);
      g.lineTo(x - 18, y - 22);
      g.strokePath();
      g.beginPath();
      g.moveTo(x, y - 6);
      g.lineTo(x + 14, y - 14);
      g.lineTo(x + 6, y - 20);
      g.lineTo(x + 22, y - 28);
      g.strokePath();
    }
    g.fillStyle(night ? 0xf0c987 : 0xffe6b0, 0.65);
    g.fillCircle(x, baseY - height, 3);
  }

  drawHyperionGround(night) {
    const g = this.groundG;
    g.fillStyle(night ? 0x2a1710 : 0x8a4a26, 1);
    g.fillEllipse(420, 500, 1120, 330);
    g.fillStyle(night ? 0x1a0d09 : 0x6b3a24, 1);
    g.fillEllipse(420, 548, 1200, 230);
    for (let i = 0; i < 6; i++) {
      g.lineStyle(1, night ? 0xd8a657 : 0xf0c987, 0.12);
      g.strokeEllipse(420, 486, 660 - i * 88, 220 - i * 28);
    }
    g.lineStyle(1, night ? 0xd8a657 : 0xf0c987, 0.2);
    for (let i = 0; i < 20; i++) {
      const angle = (i / 20) * Math.PI;
      g.lineBetween(
        420 + Math.cos(angle) * 90,
        486 + Math.sin(angle) * 32,
        420 + Math.cos(angle) * 360,
        486 + Math.sin(angle) * 112,
      );
    }
    const near = this.nearG;
    near.fillStyle(night ? 0x120a07 : 0x4a2718, 1);
    near.fillPoints(
      [
        { x: -20, y: 570 },
        { x: -20, y: 512 },
        { x: 110, y: 492 },
        { x: 250, y: 526 },
        { x: 410, y: 508 },
        { x: 570, y: 536 },
        { x: 720, y: 504 },
        { x: 860, y: 526 },
        { x: 860, y: 570 },
      ],
      true,
    );
    near.lineStyle(1, night ? 0xd8a657 : 0xf0c987, 0.22);
    for (let i = 0; i < 12; i++) {
      const x = 50 + i * 68;
      near.lineBetween(x, 552, x - 6, 534 - pseudo(i, 4) * 8);
      near.lineBetween(x + 4, 552, x + 10, 538);
    }
  }

  buildHyperionAmbient() {
    const accent = 0xd8a657;
    for (let i = 0; i < 4; i++) {
      const ring = this.add
        .circle(220 + i * 128, 250 + pseudo(i, 1) * 40, 10, 0x000000, 0)
        .setStrokeStyle(1, accent, 0.45);
      this.ambient.add(ring);
      this.trackTween({
        targets: ring,
        scale: 4.2,
        alpha: 0,
        duration: 6200 + i * 900,
        delay: i * 1500,
        repeat: -1,
        ease: "Sine.easeOut",
      });
    }
    for (let i = 0; i < 12; i++) {
      const dot = this.add.circle(
        80 + pseudo(i, 5) * 680,
        240 + pseudo(i, 6) * 220,
        1.2,
        0xf0c987,
        0.55,
      );
      this.ambient.add(dot);
      this.trackTween({
        targets: dot,
        y: dot.y - 30 - pseudo(i, 7) * 26,
        x: dot.x + 10,
        alpha: 0.08,
        duration: 4200 + pseudo(i, 8) * 3600,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
    [704, 84].forEach((x, index) => {
      const glow = this.add.circle(
        x,
        268 - index * 84,
        8,
        0xffe6b0,
        0.28,
      );
      glow.setBlendMode(Phaser.BlendModes.ADD);
      this.ambient.add(glow);
      this.trackTween({
        targets: glow,
        alpha: 0.04,
        scale: 1.8,
        duration: 1800 + index * 480,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    });
  }

  /* ---------- 三体 ---------- */
  drawThreebody(night) {
    const g = this.skyG;
    if (night) g.fillGradientStyle(0x02060d, 0x07111c, 0x0b1c2a, 0x123243, 1);
    else g.fillGradientStyle(0x10354c, 0x24506b, 0x6e9eb4, 0x8db4c8, 1);
    g.fillRect(0, 0, WIDTH, HEIGHT);
    for (let i = 0; i < 6; i++) {
      g.fillStyle(night ? 0x1b3a52 : 0xddeef5, 0.04 + i * 0.012);
      g.fillEllipse(330 + i * 46, 120 + i * 26, 620 - i * 54, 64 + i * 12);
    }
    g.fillStyle(night ? 0x071520 : 0x1d4b63, 1);
    g.fillRect(0, 300, WIDTH, HEIGHT - 300);
    this.drawStars(78, night ? 0.9 : 0.06, 11);
    this.drawThreebodySuns(night);
    this.drawThreebodyCoast(night);
    this.drawThreebodyStation(night);
    this.drawThreebodyGround(night);
  }

  drawThreebodySuns(night) {
    const g = this.celestialG;
    const alpha = night ? 0.85 : 0.95;
    g.fillStyle(0xe2574c, 0.12);
    g.fillCircle(678, 104, 108);
    g.fillStyle(0xe2574c, 0.2);
    g.fillCircle(678, 104, 68);
    g.fillStyle(night ? 0xb93e36 : 0xe2574c, alpha);
    g.fillCircle(678, 104, 36);
    g.fillStyle(night ? 0xff8a72 : 0xffd0b8, alpha * 0.65);
    g.fillCircle(668, 94, 27);
    g.lineStyle(1, 0xe2574c, 0.55);
    g.strokeCircle(678, 104, 52);
    g.lineStyle(1, 0xe2574c, 0.32);
    g.strokeCircle(678, 104, 68);
    const small = [
      [756, 58, 13, 0xcfe3f0],
      [604, 54, 9, 0xa9cddf],
    ];
    for (const [x, y, radius, color] of small) {
      g.fillStyle(color, 0.16);
      g.fillCircle(x, y, radius * 2.3);
      g.fillStyle(color, night ? 0.8 : 0.95);
      g.fillCircle(x, y, radius);
    }
  }

  drawThreebodyCoast(night) {
    const g = this.farG;
    g.fillStyle(night ? 0x06131d : 0x2b5d75, 1);
    g.fillRect(0, 300, WIDTH, 26);
    g.lineStyle(1, night ? 0x5c849d : 0xd8eaf2, 0.24);
    for (let i = 0; i < 7; i++) {
      const y = 306 + i * 3;
      g.lineBetween(40 + i * 18, y, 800 - i * 26, y);
    }
    g.fillStyle(night ? 0x040d15 : 0x173a4e, 1);
    g.fillPoints(
      [
        { x: -20, y: 300 },
        { x: 90, y: 286 },
        { x: 180, y: 296 },
        { x: 330, y: 278 },
        { x: 470, y: 298 },
        { x: 640, y: 280 },
        { x: 860, y: 296 },
        { x: 860, y: 314 },
        { x: -20, y: 314 },
      ],
      true,
    );
    g.lineStyle(1, night ? 0x3c5e78 : 0x9fc5d7, 0.22);
    for (let i = 0; i < 4; i++) {
      g.lineBetween(500 + i * 42, 306, 470 + i * 42, 300);
    }
  }

  drawThreebodyStation(night) {
    const g = this.midG;
    const wall = night ? 0x0e2233 : 0x24465b;
    const wallDark = night ? 0x081724 : 0x183346;
    const roof = night ? 0x11293b : 0x315a70;
    const light = night ? 0x6fd3e8 : 0xdff4fa;
    const red = 0xe2574c;
    g.fillStyle(wallDark, 1);
    g.fillRect(54, 246, 300, 142);
    g.fillStyle(wall, 1);
    g.fillRect(64, 252, 280, 128);
    g.fillStyle(roof, 1);
    g.fillRect(48, 240, 312, 14);
    g.fillRect(54, 376, 300, 12);
    for (let i = 0; i < 4; i++) {
      g.fillStyle(light, night ? 0.75 : 0.55);
      g.fillRect(86 + i * 62, 276, 36, 16);
      g.fillStyle(night ? 0x07111c : 0x163243, 1);
      g.fillRect(88 + i * 62, 278, 32, 12);
    }
    g.fillStyle(night ? 0x07111c : 0x163243, 1);
    g.fillRoundedRect(176, 324, 48, 56, 4);
    g.fillStyle(light, night ? 0.85 : 0.6);
    g.fillRect(190, 336, 20, 3);
    g.fillStyle(red, night ? 0.95 : 0.85);
    g.fillCircle(72, 248, 3);
    g.fillCircle(338, 248, 3);
    // 监视塔/格构天线
    const mastX = 620;
    g.lineStyle(4, wallDark, 1);
    g.lineBetween(mastX, 386, mastX, 92);
    g.lineStyle(1.4, night ? 0x517a94 : 0x8fb4c7, 0.55);
    for (let i = 0; i < 6; i++) {
      const y = 120 + i * 44;
      g.lineBetween(mastX - 24, y, mastX + 24, y - 22);
      g.lineBetween(mastX + 24, y, mastX - 24, y - 22);
    }
    g.lineBetween(mastX - 30, 386, mastX, 92);
    g.lineBetween(mastX + 30, 386, mastX, 92);
    // 碟形天线
    g.fillStyle(night ? 0x1d3a4d : 0x5b7f93, 1);
    g.fillEllipse(mastX, 104, 86, 34);
    g.fillStyle(night ? 0x07151e : 0x1b3a4c, 1);
    g.fillEllipse(mastX, 106, 54, 18);
    g.lineStyle(1, light, 0.55);
    g.lineBetween(mastX, 104, mastX + 30, 92);
    g.fillStyle(red, 0.95);
    g.fillCircle(mastX + 31, 91, 3);
    g.lineStyle(1, light, 0.3);
    for (let i = 0; i < 3; i++) {
      g.beginPath();
      g.arc(mastX, 104, 60 + i * 18, -0.55, 0.5, false);
      g.strokePath();
    }
    // 左侧小天线与电缆
    g.lineStyle(2, wallDark, 1);
    g.lineBetween(388, 386, 388, 286);
    g.lineStyle(1, light, 0.4);
    g.lineBetween(388, 286, 404, 266);
    g.lineBetween(388, 286, 372, 266);
  }

  drawThreebodyGround(night) {
    const g = this.groundG;
    g.fillStyle(night ? 0x06131d : 0x1b4055, 1);
    g.fillRect(0, 386, WIDTH, HEIGHT - 386);
    g.fillStyle(night ? 0x091b29 : 0x24506a, 1);
    g.fillRect(30, 396, 780, 174);
    g.lineStyle(1, night ? 0x3c5e78 : 0x8fb4c7, 0.2);
    for (let i = 0; i < 9; i++) {
      g.lineBetween(30, 410 + i * 20, 810, 410 + i * 20);
    }
    for (let i = 0; i < 13; i++) {
      g.lineBetween(40 + i * 62, 396, 40 + i * 62, 570);
    }
    g.fillStyle(0xe2574c, 0.25);
    g.fillRect(40, 420, 200, 3);
    g.fillRect(40, 440, 120, 3);
    g.fillStyle(0x6fd3e8, 0.18);
    g.fillRect(560, 430, 190, 3);
    g.fillRect(620, 452, 120, 2);
    const near = this.nearG;
    near.lineStyle(3, night ? 0x0c2232 : 0x315a70, 1);
    near.lineBetween(0, 548, 840, 548);
    near.lineBetween(40, 548, 40, 522);
    near.lineBetween(260, 548, 260, 522);
    near.lineBetween(560, 548, 560, 522);
    near.lineBetween(800, 548, 800, 522);
    near.lineStyle(1, night ? 0x3c5e78 : 0x8fb4c7, 0.35);
    near.lineBetween(0, 536, 840, 536);
  }

  buildThreebodyAmbient() {
    const accent = 0xe2574c;
    const scan = this.add
      .rectangle(620, 104, 138, 2, 0x6fd3e8, 0.35)
      .setOrigin(0, 0.5);
    this.ambient.add(scan);
    this.trackTween({
      targets: scan,
      angle: 360,
      duration: 9000,
      repeat: -1,
      ease: "Linear",
    });
    for (let i = 0; i < 2; i++) {
      const ring = this.add
        .circle(620, 104, 18, 0x000000, 0)
        .setStrokeStyle(1, 0x6fd3e8, 0.45);
      this.ambient.add(ring);
      this.trackTween({
        targets: ring,
        scale: 4.6,
        alpha: 0,
        duration: 3600,
        delay: i * 1800,
        repeat: -1,
        ease: "Sine.easeOut",
      });
    }
    [
      [72, 248],
      [338, 248],
      [651, 91],
    ].forEach(([x, y], index) => {
      const light = this.add.circle(x, y, 4, accent, 0.9);
      light.setBlendMode(Phaser.BlendModes.ADD);
      this.ambient.add(light);
      this.trackTween({
        targets: light,
        alpha: 0.15,
        scale: 1.5,
        duration: 1100 + index * 260,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    });
    for (let i = 0; i < 16; i++) {
      const drop = this.add
        .rectangle(
          20 + pseudo(i, 12) * 800,
          -20 + pseudo(i, 13) * 560,
          1,
          16,
          0xa9c9dd,
          0.15,
        )
        .setAngle(12);
      this.ambient.add(drop);
      this.trackTween({
        targets: drop,
        y: 590,
        duration: 1400 + pseudo(i, 14) * 1700,
        repeat: -1,
        delay: pseudo(i, 15) * 1800,
        ease: "Linear",
      });
    }
  }

  /* ---------- 潮汐档案馆 ---------- */
  drawTidal(night) {
    const g = this.skyG;
    if (night) g.fillGradientStyle(0x041616, 0x071d1e, 0x123a37, 0x1f4a50, 1);
    else g.fillGradientStyle(0x2f6b65, 0x46877d, 0x8fb6a6, 0xa9c8b8, 1);
    g.fillRect(0, 0, WIDTH, HEIGHT);
    this.drawStars(34, night ? 0.55 : 0.04, 17);
    this.drawTidalMoon(night, false);
    this.drawTidalFallback(night);
    this.drawTidalWater(night, false);
    this.drawTidalForeground(night);
  }

  drawTidalMoon(night, photo) {
    const g = this.celestialG;
    const x = photo ? 150 : 188;
    const y = photo ? 92 : 96;
    g.fillStyle(0xe6e2d0, night ? 0.08 : 0.12);
    g.fillCircle(x, y, 62);
    g.fillStyle(0xe6e2d0, night ? 0.16 : 0.22);
    g.fillCircle(x, y, 38);
    g.fillStyle(0xf2ecdc, night ? 0.72 : 0.26);
    g.fillCircle(x, y, 21);
    g.lineStyle(1, 0xce9560, 0.22);
    g.strokeCircle(x, y, 46);
  }

  drawTidalFallback(night) {
    const far = this.farG;
    const island = night ? 0x0b2a2a : 0x2d6259;
    const islandDeep = night ? 0x061b1b : 0x1f4a50;
    far.fillStyle(islandDeep, 0.9);
    far.fillPoints(
      [
        { x: -20, y: 322 },
        { x: 80, y: 294 },
        { x: 168, y: 316 },
        { x: 258, y: 282 },
        { x: 352, y: 318 },
        { x: 468, y: 292 },
        { x: 588, y: 320 },
        { x: 716, y: 286 },
        { x: 860, y: 312 },
        { x: 860, y: 360 },
        { x: -20, y: 360 },
      ],
      true,
    );
    far.fillStyle(island, 1);
    far.fillPoints(
      [
        { x: -20, y: 346 },
        { x: 118, y: 326 },
        { x: 230, y: 348 },
        { x: 380, y: 330 },
        { x: 520, y: 352 },
        { x: 690, y: 328 },
        { x: 860, y: 348 },
        { x: 860, y: 382 },
        { x: -20, y: 382 },
      ],
      true,
    );
    // 档案馆主体：铜绿穹顶、柱廊、台基
    const g = this.midG;
    const stone = night ? 0x123b39 : 0x2d6259;
    const copper = night ? 0x3f766c : 0x5f8f7d;
    const lamp = night ? 0xd9a441 : 0xe3b782;
    g.fillStyle(stone, 1);
    g.fillRect(248, 300, 330, 96);
    g.fillStyle(night ? 0x0e302c : 0x24544d, 1);
    g.fillRect(238, 388, 350, 16);
    g.fillPoints(
      [
        { x: 238, y: 310 },
        { x: 300, y: 244 },
        { x: 356, y: 310 },
      ],
      true,
    );
    g.fillPoints(
      [
        { x: 356, y: 310 },
        { x: 418, y: 232 },
        { x: 480, y: 310 },
      ],
      true,
    );
    g.fillPoints(
      [
        { x: 480, y: 310 },
        { x: 540, y: 252 },
        { x: 596, y: 310 },
      ],
      true,
    );
    g.fillStyle(copper, 0.9);
    g.fillEllipse(418, 238, 96, 18);
    for (let i = 0; i < 7; i++) {
      g.fillStyle(stone, 1);
      g.fillRect(284 + i * 38, 326, 14, 64);
      g.fillStyle(lamp, i % 2 ? 0.5 : 0.8);
      g.fillRect(286 + i * 38, 344, 10, 14);
    }
    g.fillStyle(night ? 0x071d1e : 0x1f4a50, 1);
    g.fillRoundedRect(398, 352, 40, 38, 18);
    // 灯塔与堤道
    g.fillStyle(stone, 1);
    g.fillRect(722, 306, 22, 84);
    g.fillStyle(copper, 1);
    g.fillRect(716, 298, 34, 12);
    g.fillStyle(lamp, 0.9);
    g.fillRect(727, 284, 12, 14);
    g.fillStyle(night ? 0x0b2a2a : 0x396e63, 1);
    g.fillPoints(
      [
        { x: -20, y: 548 },
        { x: 88, y: 500 },
        { x: 178, y: 468 },
        { x: 244, y: 460 },
        { x: 244, y: 494 },
        { x: 162, y: 508 },
        { x: 76, y: 548 },
      ],
      true,
    );
  }

  drawTidalWater(night, photo) {
    const g = this.groundG;
    g.fillStyle(night ? 0x071d1e : 0x2f6b65, photo ? 0.16 : 1);
    g.fillEllipse(420, 500, 1120, 300);
    g.fillStyle(night ? 0xd9c8a3 : 0xf0eadb, 0.03);
    g.fillEllipse(420, 540, 960, 200);
    for (let i = 0; i < 9; i++) {
      g.lineStyle(1, 0xce9560, 0.1 + i * 0.012);
      g.lineBetween(20 + i * 18, 470 + i * 9, 820 - i * 22, 470 + i * 9);
    }
    for (let i = 0; i < 5; i++) {
      const y = 430 + i * 24;
      g.lineStyle(1, night ? 0xa9c8b8 : 0xf2ecdc, 0.16 - i * 0.02);
      g.strokeEllipse(300 + i * 70, y, 240 + i * 40, 18 + i * 4);
    }
    g.lineStyle(2, 0xd9a441, 0.16);
    g.lineBetween(148, 112, 154, 340);
  }

  drawTidalForeground(night) {
    const g = this.nearG;
    const rock = night ? 0x041312 : 0x1b403c;
    const rockLight = night ? 0x0b2928 : 0x2d6259;
    const rocks = [
      [0, 570, 0, 500, 76, 470, 150, 520, 178, 570],
      [860, 570, 860, 486, 782, 470, 710, 510, 690, 570],
      [350, 570, 390, 534, 470, 540, 510, 570],
    ];
    for (const [x0, y0, ...rest] of rocks) {
      const points = [{ x: x0, y: y0 }];
      for (let i = 0; i < rest.length; i += 2) {
        points.push({ x: rest[i], y: rest[i + 1] });
      }
      g.fillStyle(rock, 0.86);
      g.fillPoints(points, true);
    }
    g.fillStyle(rockLight, 0.7);
    for (let i = 0; i < 10; i++) {
      const x = 20 + i * 82;
      g.fillEllipse(x, 546 + pseudo(i, 18) * 16, 26, 8);
    }
    g.lineStyle(1, 0xd9a441, 0.2);
    g.lineBetween(690, 480, 650, 540);
  }

  buildTidalAmbient() {
    const paper = 0xf0eadb;
    const copper = 0xce9560;
    for (let i = 0; i < 7; i++) {
      const page = this.add
        .rectangle(
          70 + pseudo(i, 21) * 700,
          300 + pseudo(i, 22) * 220,
          8 + pseudo(i, 23) * 5,
          11 + pseudo(i, 24) * 6,
          i % 2 ? paper : copper,
          0.42,
        )
        .setStrokeStyle(1, paper, 0.35)
        .setAngle(-18 + pseudo(i, 25) * 36);
      this.ambient.add(page);
      this.trackTween({
        targets: page,
        y: page.y - 70 - pseudo(i, 26) * 60,
        x: page.x + 18 + pseudo(i, 27) * 20,
        angle: page.angle + 18,
        alpha: 0,
        duration: 8000 + pseudo(i, 28) * 5200,
        delay: pseudo(i, 29) * 3000,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
    for (let i = 0; i < 3; i++) {
      const glow = this.add.circle(
        280 + i * 160,
        320 + i * 24,
        34,
        0xd9a441,
        0.1,
      );
      glow.setBlendMode(Phaser.BlendModes.ADD);
      this.ambient.add(glow);
      this.trackTween({
        targets: glow,
        alpha: 0.04,
        duration: 2300 + i * 520,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
    for (let i = 0; i < 4; i++) {
      const shimmer = this.add
        .rectangle(250 + i * 110, 484 + i * 12, 140, 1, 0xa9c8b8, 0.2)
        .setOrigin(0.5);
      this.ambient.add(shimmer);
      this.trackTween({
        targets: shimmer,
        alpha: 0.04,
        scaleX: 0.7,
        duration: 2600 + i * 430,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
    }
  }

  buildAmbient(worldId) {
    this.clearAmbient();
    const builder = {
      mist: this.buildMistAmbient,
      hyperion: this.buildHyperionAmbient,
      threebody: this.buildThreebodyAmbient,
      tidal_archive: this.buildTidalAmbient,
    }[worldId];
    if (builder) builder.call(this);
  }

  clearAmbient() {
    this.motionTweens.forEach((tween) => tween.stop());
    this.motionTweens = [];
    this.ambient.removeAll(true);
  }

  trackTween(config) {
    const tween = this.tweens.add(config);
    if (this.reducedMotion) tween.pause();
    this.motionTweens.push(tween);
    return tween;
  }

  flash(color, alpha) {
    if (!this.veil) return;
    this.tweens.killTweensOf(this.veil);
    this.veil.setFillStyle(color, 1).setAlpha(alpha);
    this.tweens.add({
      targets: this.veil,
      alpha: 0,
      duration: 620,
      ease: "Sine.easeOut",
    });
  }

  applyNight(night, animate) {
    if (this.night === night) return;
    const first = this.night === null;
    this.night = night;
    this.drawWorld(night, animate && !first);
    this.updatePhaseIcon();
    if (first || !animate || this.reducedMotion) return;
    this.flash(night ? this.profile.flash : 0xf1e6c8, 0.3);
  }

  drawPerson(seat, info) {
    const person = this.people[seat - 1];
    if (!person) return;
    const { container, figure, portrait, shadow, aura, label, rig } = person;
    const spot = person.spot || { x: 0, y: 450, height: 120 };
    const name = typeof info.name === "string" ? info.name : "";
    const slot = personaSlot(this.worldId, seat, name, { allowSeatOnly: Boolean(info.preview) });
    const key = atlasTextureKey(this.worldId, "bodies");
    const speaking = Boolean(info.speaking && info.alive);
    const thinking = Boolean(info.thinking && info.alive && !speaking);
    const state = speaking ? "speaking" : thinking ? "thinking" : "neutral";
    shadow.clear().fillStyle(0x071012, info.alive ? 0.38 : 0.16).fillEllipse(0, 2, 44, 9);
    aura.clear();
    if (speaking || info.you) {
      aura.lineStyle(speaking ? 2 : 1, this.profile.accent, speaking ? 0.95 : 0.65);
      aura.strokeEllipse(0, 3, speaking ? 58 : 50, 12);
    }
    const ready = slot !== null && this.hasTexture(key) && this.textures.get(key).has(slot);
    if (ready) {
      const frame = this.textures.get(key).get(slot);
      const scale = Math.min(spot.height / frame.height, 113 / frame.width);
      figure.setTexture(key, slot).setScale(scale).setPosition(0, 0).setVisible(true);
      this.clearImageTexture(portrait);
      if (info.alive) figure.clearTint(); else figure.setTint(0x71858d);
    } else {
      this.clearImageTexture(figure);
      const fallback = atlasTextureKey(this.worldId, "personas");
      if (slot !== null && this.hasTexture(fallback)) {
        portrait.setTexture(fallback, slot).setDisplaySize(44, 60).setPosition(0, -34).setVisible(true);
      } else this.clearImageTexture(portrait);
    }
    const publicName = name || publicPersonas(this.worldId)[slot]?.name || "旅人";
    label.setText(`${seat} ${publicName}`).setFontFamily(this.profile.font);
    label.setPosition(spot.x, spot.y + 12).setAlpha(info.alive ? 1 : 0.65);
    label.setColor(speaking ? "#fff0c9" : info.alive ? "#e4e1d7" : "#9baaad");
    label.setFontStyle(speaking ? "bold" : "normal");
    // 状态只控制公开演出，不按角色/阵营选择素材。减少动效下仍保留姿态差别。
    rig.setAngle(speaking ? (seat % 2 ? -1.5 : 1.5) : thinking ? 0.65 : 0);
    if (person.state !== state && !this.reducedMotion && info.alive) {
      this.tweens.add({ targets: rig, angle: rig.angle + (speaking ? 1.4 : -0.4), duration: 460, yoyo: true, ease: "Sine.easeInOut" });
    }
    person.state = state;
    const iconKey = this.hasWorldTexture(this.worldId, "icons") ? atlasTextureKey(this.worldId, "icons") : "";
    this.setSeatIcon(person.youIcon, iconKey, "you", -29, -spot.height + 12, 15, Boolean(info.you));
    this.setSeatIcon(person.sheriffIcon, iconKey, "sheriff", 27, 7, 14, Boolean(info.sheriff));
    this.setSeatIcon(person.statusIcon, iconKey, "dead", -27, 7, 14, !info.alive);
    container.setPosition(spot.x, spot.y).setAlpha(info.alive ? 1 : 0.42);
    container.setDepth(10 + spot.y / 8);
    const frameWidth = ready ? Math.min(113, figure.displayWidth) : 60;
    container.input.hitArea.setTo(-frameWidth / 2, -spot.height, frameWidth, spot.height + 34);
  }

  setSeatIcon(image, key, frameName, x, y, size, visible) {
    const frame = iconFrame(frameName);
    if (!visible || !key || frame < 0 || !this.hasTexture(key)) {
      this.clearImageTexture(image);
      return false;
    }
    image.setTexture(key, frame).setDisplaySize(size, size).setPosition(x, y).setVisible(true);
    return true;
  }

  peopleState(state) {
    const story = Array.isArray(state?.story) ? state.story : [];
    const last = [...story]
      .reverse()
      .find((entry) => entry.is_speech && entry.phase_id === state.phase_id && Number.isInteger(entry.actor) && entry.actor > 0);
    const phase = typeof state?.phase === "string" ? state.phase : "";
    const waiting = Boolean(
      state &&
        !state.winner &&
        Array.isArray(state.choices) &&
        state.choices.length === 0,
    );
    return {
      speakingSeat: last?.actor || 0,
      waiting,
      voting: /vote|ballot/.test(phase),
    };
  }

  applyState(state) {
    if (!state) return;
    if (this.state?.game_id !== state.game_id) this.lastEffect = 0;
    this.state = state;
    const mood = this.peopleState(state);
    const host = document.getElementById("scene");
    if (host) {
      host.dataset.phase = state.phase || "";
      host.dataset.speaking = String(mood.speakingSeat || "");
      host.dataset.layout = this.worldId;
    }
    const world = normalizeWorld(state.worldbook);
    const worldChanged = world !== this.worldId;
    this.setWorld(world, false);
    this.applyNight(Boolean(state.night), !worldChanged);
    if (worldChanged && this.ready && !this.reducedMotion) {
      this.flash(this.profile.flash, 0.26);
    }
    (state.players || []).forEach((player) => {
      this.drawPerson(player.seat, {
        alive: player.alive,
        you: player.seat === state.seat,
        sheriff: Boolean(player.sheriff),
        color: player.color,
        name: player.name,
        description: player.description,
        speaking: player.seat === mood.speakingSeat,
        thinking: mood.waiting && player.seat !== state.seat,
        voting: mood.voting,
      });
    });
    const story = Array.isArray(state.story) ? state.story : [];
    const effects = story.filter((entry) => entry.effect && entry.id > this.lastEffect);
    if (effects.length) this.playEffect(effects.at(-1));
    this.lastEffect = story.at(-1)?.id || 0;
    this.updateWorldTag();
    this.updateFocus();
  }

  playEffect(entry) {
    const actor = this.people[(entry.actor || 1) - 1];
    if (!actor) return;
    const effectKey = this.hasWorldTexture(this.worldId, "effects")
      ? atlasTextureKey(this.worldId, "effects")
      : "";
    const frames = effectFrames(entry.effect);
    const color = EFFECT_COLORS[entry.effect] || this.profile.accent;
    if (effectKey && frames.length) {
      this.playAtlasEffect(
        actor,
        effectKey,
        frames,
        entry.effect === "harm" ? 0xd8b0ff : 0,
      );
      return;
    }
    // 动效图集未交接时保留原有圆环 + 粒子的程序化反馈。
    const { x, y } = actor.container;
    const ring = this.add.circle(x, y - 6, 14, color, 0).setStrokeStyle(2, color, 0.9);
    ring.setDepth(31);
    this.fx.add(ring);
    if (this.reducedMotion) {
      this.time.delayedCall(240, () => ring.destroy());
      return;
    }
    const isHarm = entry.effect === "harm";
    this.tweens.add({
      targets: ring,
      scale: isHarm ? 3.4 : 5.6,
      alpha: { from: 1, to: 0 },
      duration: 1100,
      ease: "Cubic.easeOut",
      onComplete: () => ring.destroy(),
    });
    const sparkCount = entry.effect === "shot" ? 10 : 6;
    for (let i = 0; i < sparkCount; i++) {
      const angle = (i / sparkCount) * Math.PI * 2;
      const spark = this.add.circle(x, y - 20, 2.4, color, 0.95);
      spark.setDepth(32);
      this.fx.add(spark);
      this.tweens.add({
        targets: spark,
        x: x + Math.cos(angle) * (54 + pseudo(i, 4) * 30),
        y: y - 20 + Math.sin(angle) * (44 + pseudo(i, 5) * 26),
        alpha: 0,
        duration: 900,
        ease: "Cubic.easeOut",
        onComplete: () => spark.destroy(),
      });
    }
    if (["potion", "heal", "harm"].includes(entry.effect)) {
      const mist = this.add.circle(x, y - 10, 22, color, 0.35).setDepth(31);
      this.fx.add(mist);
      this.tweens.add({
        targets: mist,
        scale: isHarm ? 2.2 : 3.4,
        alpha: 0,
        duration: 1100,
        ease: "Sine.easeOut",
        onComplete: () => mist.destroy(),
      });
    }
  }

  playAtlasEffect(actor, key, frames, tint = 0) {
    const { x, y } = actor.container;
    const sprite = this.add
      .image(x, y - 10, key, frames[0])
      .setDepth(31)
      .setDisplaySize(EFFECT_DISPLAY, EFFECT_DISPLAY);
    if (tint) sprite.setTint(tint);
    this.fx.add(sprite);
    if (this.reducedMotion) {
      // 减少动效：只显示一帧静态反馈，不做缩放、位移或逐帧播放。
      sprite
        .setFrame(frames[Math.floor(frames.length / 2)])
        .setAlpha(0.9);
      const timer = this.time.delayedCall(700, () => {
        if (sprite.active) sprite.destroy();
        this.effectTimers = this.effectTimers.filter((item) => item !== timer);
      });
      this.effectTimers.push(timer);
      return;
    }
    let index = 0;
    const timer = this.time.addEvent({
      delay: EFFECT_FRAME_MS,
      repeat: frames.length - 1,
      callback: () => {
        if (!sprite.active) return;
        index = Math.min(index + 1, frames.length - 1);
        sprite.setFrame(frames[index]);
      },
    });
    this.effectTimers.push(timer);
    this.tweens.add({
      targets: sprite,
      alpha: 0,
      delay: EFFECT_FRAME_MS * frames.length + 120,
      duration: 240,
      ease: "Sine.easeIn",
      onComplete: () => {
        timer.remove(false);
        this.effectTimers = this.effectTimers.filter((item) => item !== timer);
        if (sprite.active) sprite.destroy();
      },
    });
  }

  setReducedMotion(reduced) {
    this.reducedMotion = reduced;
    this.motionTweens.forEach((tween) => {
      if (reduced) tween.pause();
      else tween.resume();
    });
    if (this.ready && this.ambient) {
      this.ambient.setAlpha(reduced ? 0.85 : 1);
    }
    this.people.forEach((person) => this.startIdle(person));
  }
}

export function makeScene({ reducedMotion = false, onSelectSeat = () => {} } = {}) {
  const scene = new WorldScene(reducedMotion, onSelectSeat);
  const instance = new Phaser.Game({
    type: Phaser.AUTO,
    parent: "scene",
    width: WIDTH,
    height: HEIGHT,
    transparent: true,
    backgroundColor: "#050b10",
    scene,
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    audio: { noAudio: true },
    render: { antialias: true },
  });
  let previewWorld = null;
  return {
    update: (state) => {
      if (!state) return;
      // 画布可能晚于首个 /api/state 就绪；先保存状态，create() 完成后补画。
      scene.state = state;
      if (scene.ready) scene.applyState(state);
    },
    // 入镇页选世界时还没有对局 state；先预览该世界的空场景。
    setWorld: (worldId) => {
      previewWorld = normalizeWorld(worldId);
      scene.previewWorld = previewWorld;
      if (scene.ready) scene.setWorld(previewWorld, false);
    },
    focusSeat: (seat) => scene.selectSeat(seat),
    setReducedMotion: (reduced) => scene.setReducedMotion(reduced),
    destroy: () => instance.destroy(true),
  };
}
