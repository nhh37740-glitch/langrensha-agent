import Phaser from "phaser";

// 雾钟镇场景：全部由 Phaser Graphics/Tween 程序化绘制，不依赖外部美术资产。
// 只读取服务器给当前玩家的可见事实；隐藏身份、私聊内容不会进入画布。
const WIDTH = 840;
const HEIGHT = 570;
const FALLBACK_COLORS = [
  0xd6ba87, 0xf1c86d, 0x92cbd6, 0xb3a4d8, 0x80c3b5, 0xd7ad85, 0x9caec4,
  0xd99ab2, 0xa9c78b, 0xd6a0cf, 0xc9907e, 0x82b9b4,
];
const EFFECT_COLORS = {
  vision: 0x9dc4ff,
  potion: 0x9ed0a4,
  shot: 0xffe4a1,
  oath: 0xe9cf94,
  shadow: 0xb59ad0,
};

function pseudo(index, salt = 0) {
  const value = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return value - Math.floor(value);
}
function colorOf(value, fallback) {
  try {
    const parsed = Phaser.Display.Color.HexStringToColor(String(value || ""));
    return parsed && parsed.color !== undefined ? parsed.color : fallback;
  } catch {
    return fallback;
  }
}
function shade(color, factor) {
  const parsed = Phaser.Display.Color.IntegerToColor(color);
  const clamp = (v) => Math.max(0, Math.min(255, Math.round(v * factor)));
  return Phaser.Display.Color.GetColor(
    clamp(parsed.red),
    clamp(parsed.green),
    clamp(parsed.blue),
  );
}

class TownScene extends Phaser.Scene {
  constructor(reducedMotion = false) {
    super("town");
    this.people = [];
    this.motionTweens = [];
    this.state = null;
    this.lastEffect = 0;
    this.reducedMotion = reducedMotion;
    this.night = null;
    this.ready = false;
  }
  create() {
    this.cameras.main.setBackgroundColor("#0b161c");
    this.sky = this.add.graphics();
    this.stars = this.add.container(0, 0);
    this.moon = this.add.graphics();
    this.skyline = this.add.graphics();
    this.tower = this.add.graphics();
    this.houses = this.add.graphics();
    this.plaza = this.add.graphics();
    this.lamps = this.add.container(0, 0);
    this.fogLayer = this.add.container(0, 0);
    this.fireflies = this.add.container(0, 0);
    this.fx = this.add.container(0, 0);
    this.fx.setDepth(20);

    this.buildStars();
    this.buildPlazaPeople();
    this.buildFog();
    this.buildLamps();
    this.buildFireflies();
    this.drawWorld(false);
    this.ready = true;
    if (this.state) this.applyState(this.state);
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.motionTweens = []);
  }
  buildStars() {
    for (let i = 0; i < 54; i++) {
      const x = Math.round(pseudo(i, 1) * WIDTH);
      const y = Math.round(pseudo(i, 2) * 250) + 8;
      const size = i % 5 === 0 ? 2 : 1;
      const star = this.add.circle(x, y, size, 0xdfe7dc, 0.75);
      this.stars.add(star);
    }
  }
  buildPlazaPeople() {
    for (let i = 0; i < 12; i++) {
      const angle = -Math.PI / 2 + (i / 12) * Math.PI * 2;
      const x = 420 + Math.cos(angle) * 312;
      const y = 428 + Math.sin(angle) * 66;
      const halo = this.add.graphics();
      const body = this.add.graphics();
      const bell = this.add.graphics();
      const label = this.add
        .text(0, 40, "", {
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize: 13,
          color: "#cdbf9c",
        })
        .setOrigin(0.5);
      const container = this.add
        .container(x, y, [halo, body, bell, label])
        .setDepth(10 + i);
      container.setScale(0.94 + pseudo(i, 3) * 0.12);
      this.people.push({ container, halo, body, bell, label, seat: i + 1 });
    }
  }
  buildFog() {
    for (let i = 0; i < 3; i++) {
      const fog = this.add
        .ellipse(420, 330 + i * 70, 980 + i * 120, 120 + i * 26, 0xa9c6c2, [
          0.05, 0.07, 0.05,
        ][i])
        .setDepth(2 + i);
      this.fogLayer.add(fog);
      if (this.reducedMotion) continue;
      const tween = this.tweens.add({
        targets: fog,
        x: i % 2 === 0 ? 720 : 120,
        duration: 26000 + i * 7000,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
      this.motionTweens.push(tween);
    }
  }
  buildLamps() {
    this.lampSpots = [
      [122, 402],
      [718, 402],
    ];
    this.lampGlow = [];
    for (const [x, y] of this.lampSpots) {
      const post = this.add.graphics();
      post.lineStyle(3, 0x2f453f, 1);
      post.lineBetween(x, y, x, y - 96);
      post.fillStyle(0x2f453f, 1);
      post.fillCircle(x, y - 96, 5);
      post.fillStyle(0x1b2c2b, 1);
      post.fillRoundedRect(x - 9, y - 108, 18, 22, 4);
      post.fillStyle(0xf3d38c, 0.95);
      post.fillRoundedRect(x - 6, y - 105, 12, 16, 3);
      const glow = this.add.circle(x, y - 96, 54, 0xf3d38c, 0.16);
      glow.setBlendMode(Phaser.BlendModes.ADD);
      this.lamps.add(post);
      this.lamps.add(glow);
      this.lampGlow.push(glow);
      if (!this.reducedMotion) {
        const tween = this.tweens.add({
          targets: glow,
          alpha: 0.08,
          duration: 2400 + x,
          yoyo: true,
          repeat: -1,
          ease: "Sine.easeInOut",
        });
        this.motionTweens.push(tween);
      }
    }
  }
  buildFireflies() {
    for (let i = 0; i < 9; i++) {
      const x = 90 + pseudo(i, 7) * 660;
      const y = 300 + pseudo(i, 8) * 190;
      const fly = this.add.circle(x, y, 1.8, 0xf4d48f, 0.85);
      fly.setBlendMode(Phaser.BlendModes.ADD);
      this.fireflies.add(fly);
      if (this.reducedMotion) continue;
      const tween = this.tweens.add({
        targets: fly,
        y: y - 18 - pseudo(i, 9) * 22,
        alpha: 0.2,
        duration: 2600 + pseudo(i, 10) * 2600,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
      this.motionTweens.push(tween);
    }
  }
  drawWorld(night) {
    this.drawSky(night);
    this.drawStars(night);
    this.drawMoon(night);
    this.drawSkyline(night);
    this.drawTower(night);
    this.drawHouses(night);
    this.drawPlaza(night);
    this.fireflies.setAlpha(night ? 1 : 0.15);
    this.lamps.setAlpha(night ? 1 : 0.55);
    this.lampGlow.forEach((glow) => glow.setAlpha(night ? 0.16 : 0.05));
    this.fogLayer.setAlpha(night ? 1 : 0.6);
  }
  drawSky(night) {
    const g = this.sky;
    g.clear();
    if (night) {
      g.fillGradientStyle(0x08111a, 0x0b151f, 0x1b3038, 0x223a3e, 1);
    } else {
      g.fillGradientStyle(0x55716d, 0x647f78, 0x9bb3a4, 0xb3c5ae, 1);
    }
    g.fillRect(0, 0, WIDTH, HEIGHT);
    // 远处雾带与天光
    for (let i = 0; i < 5; i++) {
      g.fillStyle(night ? 0x33505a : 0xd7e0cd, 0.05 + i * 0.012);
      g.fillEllipse(420, 150 + i * 34, 780 - i * 60, 120 - i * 8);
    }
    g.fillStyle(night ? 0x0a1622 : 0x2f4a45, 0.5);
    g.fillRect(0, 284, WIDTH, HEIGHT - 284);
  }
  drawStars(night) {
    this.stars.setAlpha(night ? 1 : 0.12);
  }
  drawMoon(night) {
    const g = this.moon;
    g.clear();
    const alpha = night ? 1 : 0.18;
    g.fillStyle(0xe8ddb4, alpha);
    g.fillCircle(672, 88, 30);
    g.fillStyle(0xf6ecc9, alpha);
    g.fillCircle(664, 80, 24);
    for (let i = 0; i < 4; i++) {
      g.lineStyle(1, 0xf6ecc9, alpha * (0.28 - i * 0.05));
      g.strokeCircle(672, 88, 38 + i * 14);
    }
  }
  drawSkyline(night) {
    const g = this.skyline;
    g.clear();
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
  drawTower(night) {
    const g = this.tower;
    g.clear();
    const stone = night ? 0x2b3c39 : 0x5c6f63;
    const stoneDark = night ? 0x1d2c2c : 0x46594f;
    const stoneLight = night ? 0x3c524b : 0x76897a;
    const windowLight = night ? 0xf3d38c : 0xaebfa8;
    // 主体
    g.fillStyle(stoneDark, 1);
    g.fillRect(360, 176, 120, 198);
    g.fillStyle(stone, 1);
    g.fillRect(366, 186, 108, 182);
    g.fillStyle(stoneLight, 0.55);
    g.fillRect(372, 192, 10, 170);
    g.fillRect(458, 192, 8, 170);
    // 石缝
    g.lineStyle(1, stoneDark, 0.75);
    for (let row = 0; row < 8; row++) {
      const y = 200 + row * 21;
      g.lineBetween(366, y, 474, y);
    }
    // 钟楼拱门
    g.fillStyle(night ? 0x13211f : 0x33443a, 1);
    g.fillRoundedRect(398, 288, 44, 84, 22);
    g.fillRect(398, 330, 44, 42);
    g.lineStyle(2, stoneLight, 0.5);
    g.strokeRoundedRect(398, 288, 44, 84, 22);
    // 台阶
    g.fillStyle(stoneDark, 1);
    g.fillRect(386, 362, 68, 8);
    g.fillRect(376, 370, 88, 8);
    // 钟室
    g.fillStyle(stone, 1);
    g.fillRect(374, 120, 92, 60);
    g.fillStyle(stoneLight, 0.4);
    g.fillRect(380, 126, 8, 50);
    g.fillStyle(night ? 0x101d1d : 0x2f4038, 1);
    g.fillRoundedRect(394, 130, 52, 44, 22);
    // 铜铃
    g.fillStyle(0xe3c67d, night ? 0.95 : 0.75);
    g.fillRoundedRect(408, 142, 24, 18, 6);
    g.fillCircle(420, 152, 9);
    g.fillStyle(0x8a6f3e, 1);
    g.fillCircle(420, 163, 3);
    g.lineStyle(2, 0xd8bd85, 0.9);
    g.lineBetween(420, 142, 420, 134);
    g.lineBetween(402, 132, 438, 132);
    // 屋顶
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
    // 夜间窗光
    if (night) {
      g.fillStyle(windowLight, 0.85);
      g.fillRoundedRect(380, 222, 14, 26, 7);
      g.fillRoundedRect(446, 222, 14, 26, 7);
      g.fillStyle(windowLight, 0.18);
      g.fillCircle(387, 235, 26);
      g.fillCircle(453, 235, 26);
    } else {
      g.fillStyle(night ? 0x1b2b25 : 0x2f423a, 0.9);
      g.fillRoundedRect(380, 222, 14, 26, 7);
      g.fillRoundedRect(446, 222, 14, 26, 7);
    }
    // 铜铃光晕
    g.fillStyle(0xf3d38c, night ? 0.12 : 0.05);
    g.fillCircle(420, 158, 44);
  }
  drawHouses(night) {
    const g = this.houses;
    g.clear();
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
  drawPlaza(night) {
    const g = this.plaza;
    g.clear();
    // 地面
    g.fillStyle(night ? 0x10201f : 0x33483f, 1);
    g.fillEllipse(420, 430, 840, 300);
    g.fillStyle(night ? 0x0c1a1a : 0x2b3e37, 1);
    g.fillEllipse(420, 470, 900, 260);
    // 环形石纹
    for (let i = 0; i < 5; i++) {
      g.lineStyle(1, night ? 0x51695f : 0x8ba690, 0.16);
      g.strokeEllipse(420, 432, 640 - i * 96, 246 - i * 38);
    }
    // 放射石缝
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
    // 中央铜铃纹样
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
  applyNight(night, animate) {
    if (this.night === night) return;
    const first = this.night === null;
    this.night = night;
    this.drawWorld(night);
    if (first || !animate || this.reducedMotion) return;
    const veil = this.add
      .rectangle(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT, night ? 0x071019 : 0xf1e6c8, 0)
      .setDepth(30);
    this.tweens.add({
      targets: veil,
      alpha: { from: 0.42, to: 0 },
      duration: 620,
      ease: "Sine.easeOut",
      onComplete: () => veil.destroy(),
    });
  }
  drawPerson(seat, info) {
    const parts = this.people[seat - 1];
    if (!parts) return;
    const { body, halo, bell, label, container } = parts;
    const base = colorOf(info.color, FALLBACK_COLORS[(seat - 1) % 12]);
    const dark = shade(base, 0.42);
    const mid = shade(base, 0.7);
    const light = shade(base, 1.22);
    body.clear();
    halo.clear();
    bell.clear();
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
      body.lineStyle(2, light, 0.65);
      body.beginPath();
      body.moveTo(-9, -12);
      body.lineTo(0, -4);
      body.lineTo(9, -12);
      body.strokePath();
      body.fillStyle(0xe9cf94, 0.9);
      body.fillCircle(0, -2, 2.2);
      label.setColor("#d9c6a8");
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
    label.setText(String(seat));
    halo.setVisible(Boolean(info.you));
    if (info.you) {
      halo.lineStyle(2, 0xe9cf94, 0.9);
      halo.strokeCircle(0, 2, 37);
      halo.fillStyle(0xe9cf94, 0.3);
      halo.fillCircle(0, 46, 3);
    }
    bell.setVisible(Boolean(info.sheriff) && Boolean(info.alive));
    if (info.sheriff && info.alive) {
      bell.fillStyle(0xe9cf94, 0.95);
      bell.fillCircle(17, -45, 5);
      bell.lineStyle(1.5, 0xe9cf94, 0.9);
      bell.lineBetween(17, -50, 17, -53);
    }
    container.setAlpha(info.alive ? 1 : 0.48);
  }
  applyState(state) {
    if (this.state?.game_id !== state.game_id) this.lastEffect = 0;
    this.state = state;
    this.applyNight(Boolean(state.night), true);
    state.players.forEach((player) => {
      this.drawPerson(player.seat, {
        alive: player.alive,
        you: player.seat === state.seat,
        sheriff: player.seat === state.sheriff,
        color: player.color,
      });
    });
    const effects = state.story.filter((e) => e.effect && e.id > this.lastEffect);
    if (effects.length) this.playEffect(effects.at(-1));
    this.lastEffect = state.story.at(-1)?.id || 0;
  }
  playEffect(entry) {
    const actor = this.people[(entry.actor || 1) - 1];
    if (!actor) return;
    const color = EFFECT_COLORS[entry.effect] || 0xe9cf94;
    const { x, y } = actor.container;
    const ring = this.add.circle(x, y - 6, 14, color, 0).setStrokeStyle(2, color, 0.9);
    ring.setDepth(21);
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
      spark.setDepth(22);
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
      const mist = this.add.circle(x, y - 10, 22, color, 0.35).setDepth(21);
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
  setReducedMotion(reduced) {
    this.reducedMotion = reduced;
    this.motionTweens.forEach((tween) => {
      if (reduced) tween.pause();
      else tween.resume();
    });
    if (this.ready) {
      this.fireflies.setVisible(!reduced);
      if (reduced) this.fogLayer.setAlpha(0.75);
    }
  }
}

export function makeScene({ reducedMotion = false } = {}) {
  const scene = new TownScene(reducedMotion);
  const instance = new Phaser.Game({
    type: Phaser.AUTO,
    parent: "scene",
    width: WIDTH,
    height: HEIGHT,
    transparent: true,
    backgroundColor: "#0b161c",
    scene,
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    audio: { noAudio: true },
    render: { antialias: true },
  });
  return {
    update: (state) => {
      if (scene.ready && state) scene.applyState(state);
    },
    setReducedMotion: (reduced) => scene.setReducedMotion(reduced),
    destroy: () => instance.destroy(true),
  };
}
