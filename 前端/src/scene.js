import Phaser from "phaser";
import tidalArchiveBackground from "./assets/ai/tidal-archive-lowtide.webp";
import frameHyperion from "./assets/kenney/frame-hyperion.webp";
import frameMist from "./assets/kenney/frame-mist.webp";
import frameThreebody from "./assets/kenney/frame-threebody.webp";
import frameTidal from "./assets/kenney/frame-tidal.webp";
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
import { personaSlot } from "./worlds/personas.js";

// 四套世界共用一块固定舞台，只按 state.worldbook 切换天空、建筑、地面、
// 环境动效与头像框。所有人物颜色只取服务器公开的 player.color，绝不按身份着色。
const WIDTH = 840;
const HEIGHT = 570;
const FALLBACK_COLORS = [
  0xd6ba87, 0xf1c86d, 0x92cbd6, 0xb3a4d8, 0x80c3b5, 0xd7ad85, 0x9caec4,
  0xd99ab2, 0xa9c78b, 0xd6a0cf, 0xc9907e, 0x82b9b4,
];
// 人物胸像在席位框内的显示尺寸；图集按图片实际像素推导后等比裁切，不拉伸。
const PERSONA_DISPLAY = Object.freeze({ width: 50, height: 64, y: -5 });
// 只保留最近两个世界的纹理：当前世界 + 上一个世界，切回时无需重新下载。
const TEXTURE_WORLD_LIMIT = 2;
// 昼夜真实背景交叉淡化的时长；减少动效时直接切换。
const SCENE_FADE_MS = 900;
const EFFECT_FRAME_MS = 80;
const EFFECT_DISPLAY = 104;
const ATLAS_PARTS = Object.freeze({
  personas: ATLAS.personas,
  icons: ATLAS.icons,
  effects: ATLAS.effects,
});
const EFFECT_COLORS = {
  vision: 0x9dc4ff,
  potion: 0x9ed0a4,
  shot: 0xffe4a1,
  oath: 0xe9cf94,
  shadow: 0xb59ad0,
};

const SKY_KEYS = {
  mist: "sky-mist",
  hyperion: "sky-hyperion",
  threebody: "sky-threebody",
  tidal_archive: "bg-tidal",
};
const FRAME_KEYS = {
  mist: "frame-mist",
  hyperion: "frame-hyperion",
  threebody: "frame-threebody",
  tidal_archive: "frame-tidal",
};
const TEXTURE_URLS = {
  "sky-mist": skyMist,
  "sky-hyperion": skyHyperion,
  "sky-threebody": skyThreebody,
  "sky-tidal": skyTidal,
  "bg-tidal": tidalArchiveBackground,
  "frame-mist": frameMist,
  "frame-hyperion": frameHyperion,
  "frame-threebody": frameThreebody,
  "frame-tidal": frameTidal,
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
function colorOf(value, fallback) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  try {
    const parsed = Phaser.Display.Color.HexStringToColor(String(value || ""));
    return parsed && parsed.color !== undefined ? parsed.color : fallback;
  } catch {
    return fallback;
  }
}
function shade(color, factor) {
  const parsed = Phaser.Display.Color.IntegerToColor(color);
  const clamp = (value) => Math.max(0, Math.min(255, Math.round(value * factor)));
  return Phaser.Display.Color.GetColor(
    clamp(parsed.red),
    clamp(parsed.green),
    clamp(parsed.blue),
  );
}
function normalizeWorld(value) {
  return typeof value === "string" && WORLD[value] ? value : "mist";
}

class WorldScene extends Phaser.Scene {
  constructor(reducedMotion = false) {
    super("town");
    this.people = [];
    this.motionTweens = [];
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
        if (spec) {
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
    } else if (kind === "personas") {
      this.refreshPeople();
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
      this.effectTimers.forEach((timer) => timer.remove(false));
      this.effectTimers = [];
      this.loadingTextures.forEach((image) => {
        image.onload = null;
        image.onerror = null;
      });
      this.loadingTextures.clear();
      if (this.backgroundTween) this.backgroundTween.stop();
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
    this.fx = this.add.container(0, 0).setDepth(30);
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
      .setDepth(40);
  }

  buildPeople() {
    const anyFrame = Object.values(FRAME_KEYS).find((key) => this.hasTexture(key));
    for (let i = 0; i < 12; i++) {
      const halo = this.add.graphics();
      const body = this.add.graphics();
      // 人物图集是懒加载的，先建占位 Image（默认纹理隐藏）；加载完成或切世界
      // 时由 drawPerson 按公开席位/姓名换成对应帧。
      const portrait = this.add.image(0, 0).setVisible(false);
      let frame = null;
      if (anyFrame) {
        frame = this.add
          .image(0, -5, anyFrame)
          .setDisplaySize(50, 68)
          .setVisible(false);
      }
      const frameG = this.add.graphics();
      const badge = this.add.graphics();
      const statusIcon = this.add.image(0, 0).setVisible(false);
      const youIcon = this.add.image(0, 0).setVisible(false);
      const sheriffIcon = this.add.image(0, 0).setVisible(false);
      const label = this.add
        .text(0, 40, "", {
          fontFamily: '"Songti SC", "Noto Serif CJK SC", serif',
          fontSize: 11,
          color: "#cdbf9c",
        })
        .setOrigin(0.5);
      const children = [halo, body, portrait];
      if (frame) children.push(frame);
      children.push(
        frameG,
        badge,
        statusIcon,
        youIcon,
        sheriffIcon,
        label,
      );
      const container = this.add.container(0, 0, children);
      this.people.push({
        container,
        halo,
        body,
        portrait,
        frame,
        frameG,
        badge,
        statusIcon,
        youIcon,
        sheriffIcon,
        label,
        seat: i + 1,
      });
    }
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
    const fallbackKey = this.worldId === "tidal_archive" ? "sky-tidal" : null;
    const visibleKey = this.hasTexture(key)
      ? key
      : fallbackKey && this.hasTexture(fallbackKey)
        ? fallbackKey
        : null;
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
    this.ensureWorldAssets(id);
    this.drawWorld(Boolean(this.night), false);
    this.positionPeople();
    this.buildAmbient(id);
    this.applyFrames();
    this.refreshPeople();
    this.updateWorldTag();
    this.updatePhaseIcon();
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
    players.forEach((player) => {
      this.drawPerson(player.seat, {
        alive: player.alive,
        you: player.seat === this.state.seat,
        sheriff: Boolean(player.sheriff),
        color: player.color,
        name: player.name,
      });
    });
  }

  positionPeople() {
    const spots = this.layoutFor(this.worldId);
    this.people.forEach((person, index) => {
      const spot = spots[index] || spots[0];
      person.container.setPosition(spot.x, spot.y);
      const baseScale = this.worldId === "tidal_archive" ? 0.84 : 0.9;
      person.container.setScale(baseScale + pseudo(index, 3) * 0.08);
      person.container.setDepth(10 + Math.round(spot.y / 8));
    });
  }

  layoutFor(worldId) {
    if (worldId === "mist") {
      return Array.from({ length: 12 }, (_, index) => {
        const row = index < 6 ? 0 : 1;
        return {
          x: 168 + (index % 6) * 100 + (row ? 20 : 0),
          y: row ? 486 : 400,
        };
      });
    }
    if (worldId === "threebody") {
      return Array.from({ length: 12 }, (_, index) => {
        const row = index < 6 ? 0 : 1;
        return {
          x: 146 + (index % 6) * 104 + (row ? 16 : 0),
          y: row ? 488 : 400,
        };
      });
    }
    if (worldId === "hyperion") {
      return Array.from({ length: 12 }, (_, index) => {
        const angle = Math.PI * (0.12 + (index / 11) * 0.76);
        return {
          x: 420 + Math.cos(angle) * 300,
          y: 386 + Math.sin(angle) * 108,
        };
      });
    }
    const centerY = worldId === "tidal_archive" ? 438 : 430;
    return Array.from({ length: 12 }, (_, index) => {
      const angle = -Math.PI / 2 + (index / 12) * Math.PI * 2;
      return {
        x: 420 + Math.cos(angle) * 304,
        y: centerY + Math.sin(angle) * 64,
      };
    });
  }

  applyFrames() {
    const key = FRAME_KEYS[this.worldId];
    this.people.forEach((person) => {
      if (person.frame) {
        if (this.hasTexture(key)) {
          person.frame
            .setTexture(key)
            .setVisible(true)
            .clearTint()
            .setAlpha(1);
        } else {
          person.frame.setVisible(false);
        }
      }
      person.frameG.clear();
      if (!this.hasTexture(key)) this.drawFrameFallback(person.frameG);
    });
  }

  drawFrameFallback(g) {
    const color = this.profile.frame;
    g.lineStyle(2, color, 0.82);
    g.strokeRoundedRect(-31, -43, 62, 78, 9);
    g.lineStyle(1, color, 0.42);
    g.strokeRoundedRect(-26, -38, 52, 68, 7);
    g.lineBetween(-31, -30, -31, -20);
    g.lineBetween(31, -30, 31, -20);
    g.lineBetween(-31, 25, -31, 35);
    g.lineBetween(31, 25, 31, 35);
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
    const photo = this.hasTexture("bg-tidal");
    if (photo) {
      this.tintG.fillStyle(night ? 0x041a1c : 0xffefd0, night ? 0.18 : 0.06);
      this.tintG.fillRect(0, 0, WIDTH, HEIGHT);
    }
    this.drawStars(34, night ? 0.55 : 0.04, 17);
    this.drawTidalMoon(night, photo);
    if (!photo) this.drawTidalFallback(night);
    this.drawTidalWater(night, photo);
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
    const parts = this.people[seat - 1];
    if (!parts) return;
    const {
      body,
      halo,
      badge,
      label,
      container,
      frame,
      frameG,
      portrait,
      statusIcon,
      youIcon,
      sheriffIcon,
    } = parts;
    const base = colorOf(info.color, FALLBACK_COLORS[(seat - 1) % 12]);
    const dark = shade(base, 0.42);
    const mid = shade(base, 0.7);
    const light = shade(base, 1.22);
    body.clear();
    halo.clear();
    badge.clear();

    body.fillStyle(0x06100f, 0.45);
    body.fillEllipse(0, 34, 50, 14);
    if (info.alive) {
      body.fillStyle(dark, 0.98);
      body.fillPoints(
        [
          { x: -17, y: -4 },
          { x: -24, y: 20 },
          { x: -12, y: 31 },
          { x: 12, y: 31 },
          { x: 24, y: 20 },
          { x: 17, y: -4 },
        ],
        true,
      );
      body.fillStyle(mid, 0.75);
      body.fillPoints(
        [
          { x: -13, y: -2 },
          { x: -17, y: 22 },
          { x: 0, y: 29 },
          { x: 17, y: 22 },
          { x: 13, y: -2 },
        ],
        true,
      );
      body.fillStyle(light, 0.3);
      body.fillPoints(
        [
          { x: -5, y: -2 },
          { x: -3, y: 27 },
          { x: 3, y: 27 },
          { x: 5, y: -2 },
        ],
        true,
      );
      body.fillStyle(mid, 1);
      body.fillEllipse(0, -8, 38, 18);
      body.fillStyle(0xd9c6a8, 1);
      body.fillCircle(0, -25, 11);
      body.fillStyle(0xb99f81, 0.32);
      body.fillCircle(3, -22, 8);
      this.drawCostume(seat, dark, mid);
      body.lineStyle(2, light, 0.65);
      body.beginPath();
      body.moveTo(-9, -12);
      body.lineTo(0, -4);
      body.lineTo(9, -12);
      body.strokePath();
      body.fillStyle(0xe9cf94, 0.9);
      body.fillCircle(0, -2, 2.2);
      label.setColor(this.profile.tagColor);
    } else {
      body.fillStyle(0x657b73, 0.92);
      body.fillPoints(
        [
          { x: -15, y: -4 },
          { x: -21, y: 20 },
          { x: -11, y: 30 },
          { x: 11, y: 30 },
          { x: 21, y: 20 },
          { x: 15, y: -4 },
        ],
        true,
      );
      body.fillStyle(0x8ca79b, 0.82);
      body.fillEllipse(0, -9, 32, 16);
      body.fillStyle(0xb9c6ba, 0.92);
      body.fillCircle(0, -25, 11);
      body.lineStyle(1, 0xd6e2d8, 0.38);
      body.strokeCircle(0, -25, 16);
      label.setColor("#8ca39a");
    }

    const personName = typeof info.name === "string" ? info.name : "";
    const personaKey = atlasTextureKey(this.worldId, "personas");
    // 只按服务器公开的 seat + 姓名绑定；姓名不匹配或素材缺失都回退程序化头像。
    const slot = personaSlot(this.worldId, seat, personName, {
      allowSeatOnly: Boolean(info.preview),
    });
    if (slot !== null && this.hasTexture(personaKey)) {
      this.fitPersonaPortrait(portrait, personaKey, slot, info.alive);
    } else {
      // 姓名未知或图集缺失：直接回退到既有程序化头像，不保留旧版单张立绘。
      this.clearImageTexture(portrait);
    }

    const frameAvailable = this.hasTexture(FRAME_KEYS[this.worldId]);
    frameG.clear();
    if (frame) {
      frame.setVisible(frameAvailable);
      if (frameAvailable) {
        frame
          .setAlpha(info.alive ? 1 : 0.46)
          .setTint(info.alive ? 0xffffff : 0x7e8a86);
      }
    }
    if (!frameAvailable) this.drawFrameFallback(frameG);

    label.setText(String(seat));
    label.setFontFamily(this.profile.font);
    const iconKey = this.hasWorldTexture(this.worldId, "icons")
      ? atlasTextureKey(this.worldId, "icons")
      : "";
    const hasYouIcon = this.setSeatIcon(
      youIcon,
      iconKey,
      "you",
      -21,
      -44,
      17,
      Boolean(info.you),
    );
    const hasSheriffIcon = this.setSeatIcon(
      sheriffIcon,
      iconKey,
      "sheriff",
      21,
      -44,
      17,
      Boolean(info.sheriff),
    );
    const hasStatusIcon = this.setSeatIcon(
      statusIcon,
      iconKey,
      info.alive ? "alive" : "dead",
      -20,
      22,
      13,
      true,
    );
    if (hasStatusIcon) {
      statusIcon.setAlpha(info.alive ? 0.82 : 0.68);
    }
    // 图标未命中时才用原有的光环/圆点，保证缺图世界仍能看出本人与执铃人。
    halo.setVisible(Boolean(info.you) && Boolean(info.alive) && !hasYouIcon);
    if (info.you && info.alive && !hasYouIcon) {
      const accent = this.profile.accent;
      halo.lineStyle(2, accent, 0.9);
      halo.strokeCircle(0, 2, 38);
      halo.fillStyle(accent, 0.3);
      halo.fillCircle(0, 48, 3);
    }
    badge.setVisible(
      Boolean(info.sheriff) && Boolean(info.alive) && !hasSheriffIcon,
    );
    if (info.sheriff && info.alive && !hasSheriffIcon) {
      const accent = this.profile.accent;
      badge.fillStyle(accent, 0.95);
      badge.fillCircle(19, -45, 5);
      badge.lineStyle(1.5, accent, 0.9);
      badge.lineBetween(19, -50, 19, -53);
    }
    container.setAlpha(info.alive ? 1 : 0.48);
  }

  // 图集实际尺寸由图片推导；这里按单元格等比 cover 到席位框，避免拉伸。
  fitPersonaPortrait(image, key, frameIndex, alive) {
    const texture = this.textures.get(key);
    if (!texture || !texture.has(frameIndex)) {
      this.clearImageTexture(image);
      return;
    }
    image.setTexture(key, frameIndex);
    const frame = image.frame;
    if (!frame || !frame.width || !frame.height) {
      this.clearImageTexture(image);
      return;
    }
    const scale = Math.max(
      PERSONA_DISPLAY.width / frame.width,
      PERSONA_DISPLAY.height / frame.height,
    );
    image
      .setScale(scale)
      .setPosition(0, PERSONA_DISPLAY.y)
      .setAlpha(alive ? 1 : 0.5)
      .setVisible(true);
    if (alive) image.clearTint();
    else image.setTint(0x77837e);
  }

  setSeatIcon(image, key, frameName, x, y, size, visible) {
    const frame = iconFrame(frameName);
    if (!visible || !key || frame < 0 || !this.hasTexture(key)) {
      this.clearImageTexture(image);
      return false;
    }
    image
      .setTexture(key, frame)
      .setDisplaySize(size, size)
      .setPosition(x, y)
      .setVisible(true);
    return true;
  }

  drawCostume(seat, dark, mid) {
    const body = this.people[seat - 1]?.body;
    if (!body) return;
    if (this.worldId === "mist") {
      const variant = seat % 4;
      if (variant === 0) {
        body.fillStyle(dark, 1);
        body.fillTriangle(-13, -27, 13, -27, 0, -47);
        body.fillStyle(mid, 1);
        body.fillCircle(0, -40, 5);
      } else if (variant === 1) {
        body.fillStyle(dark, 1);
        body.fillEllipse(0, -38, 34, 9);
        body.fillCircle(0, -31, 9);
      } else if (variant === 2) {
        body.fillStyle(dark, 1);
        body.fillCircle(0, -33, 8);
        body.fillCircle(-7, -31, 5);
      } else {
        body.fillStyle(dark, 1);
        body.fillPoints(
          [
            { x: -12, y: -8 },
            { x: 0, y: 4 },
            { x: 12, y: -8 },
            { x: 0, y: -2 },
          ],
          true,
        );
      }
      body.fillStyle(0xe9cf94, 0.7);
      body.fillCircle(0, -2, 2.2);
      return;
    }
    if (this.worldId === "hyperion") {
      body.fillStyle(dark, 0.95);
      body.fillRect(-15, -15, 30, 5);
      body.fillPoints(
        [
          { x: -13, y: -8 },
          { x: -2, y: 2 },
          { x: 7, y: -12 },
          { x: 15, y: -8 },
          { x: 16, y: 16 },
          { x: 4, y: 20 },
          { x: -10, y: 17 },
        ],
        true,
      );
      body.fillStyle(0xd8a657, 0.42);
      body.fillRect(-12, -21, 24, 3);
      body.lineStyle(1, 0xf0c987, 0.4);
      body.lineBetween(-13, -16, 13, -16);
      return;
    }
    if (this.worldId === "threebody") {
      body.fillStyle(dark, 1);
      body.fillRect(-14, -13, 28, 6);
      body.fillRect(-19, -8, 6, 13);
      body.fillRect(13, -8, 6, 13);
      body.fillStyle(0x6fd3e8, 0.55);
      body.fillRect(-9, -12, 18, 2);
      body.lineStyle(1, 0x9fd8e8, 0.65);
      body.lineBetween(-12, -28, -17, -20);
      body.fillCircle(-17, -19, 2.2);
      body.fillStyle(0xe2574c, 0.85);
      body.fillCircle(11, 8, 1.8);
      return;
    }
    // 潮汐档案馆：雨披领口、铜扣与纸签
    body.fillStyle(dark, 0.95);
    body.fillPoints(
      [
        { x: -16, y: -10 },
        { x: -8, y: -2 },
        { x: 0, y: -9 },
        { x: 8, y: -2 },
        { x: 16, y: -10 },
        { x: 15, y: 17 },
        { x: -15, y: 17 },
      ],
      true,
    );
    body.fillStyle(0xce9560, 0.85);
    body.fillCircle(0, 1, 3);
    body.fillStyle(0xf0eadb, 0.62);
    body.fillRect(9, 6, 8, 11);
    body.lineStyle(1, 0xce9560, 0.55);
    body.lineBetween(10, 10, 15, 10);
  }

  applyState(state) {
    if (!state) return;
    if (this.state?.game_id !== state.game_id) this.lastEffect = 0;
    this.state = state;
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
      });
    });
    const story = Array.isArray(state.story) ? state.story : [];
    const effects = story.filter((entry) => entry.effect && entry.id > this.lastEffect);
    if (effects.length) this.playEffect(effects.at(-1));
    this.lastEffect = story.at(-1)?.id || 0;
    this.updateWorldTag();
  }

  playEffect(entry) {
    const actor = this.people[(entry.actor || 1) - 1];
    if (!actor) return;
    const effectKey = this.hasWorldTexture(this.worldId, "effects")
      ? atlasTextureKey(this.worldId, "effects")
      : "";
    const frames = effectFrames(entry.effect);
    if (effectKey && frames.length) {
      this.playAtlasEffect(actor, effectKey, frames);
      return;
    }
    // 动效图集未交接时保留原有圆环 + 粒子的程序化反馈。
    const color = EFFECT_COLORS[entry.effect] || this.profile.accent;
    const { x, y } = actor.container;
    const ring = this.add.circle(x, y - 6, 14, color, 0).setStrokeStyle(2, color, 0.9);
    ring.setDepth(31);
    this.fx.add(ring);
    if (this.reducedMotion) {
      this.time.delayedCall(240, () => ring.destroy());
      return;
    }
    this.tweens.add({
      targets: ring,
      scale: 5.6,
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
    if (entry.effect === "potion") {
      const mist = this.add.circle(x, y - 10, 22, color, 0.35).setDepth(31);
      this.fx.add(mist);
      this.tweens.add({
        targets: mist,
        scale: 3.4,
        alpha: 0,
        duration: 1100,
        ease: "Sine.easeOut",
        onComplete: () => mist.destroy(),
      });
    }
  }

  playAtlasEffect(actor, key, frames) {
    const { x, y } = actor.container;
    const sprite = this.add
      .image(x, y - 10, key, frames[0])
      .setDepth(31)
      .setDisplaySize(EFFECT_DISPLAY, EFFECT_DISPLAY);
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
  }
}

export function makeScene({ reducedMotion = false } = {}) {
  const scene = new WorldScene(reducedMotion);
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
    setReducedMotion: (reduced) => scene.setReducedMotion(reduced),
    destroy: () => instance.destroy(true),
  };
}
