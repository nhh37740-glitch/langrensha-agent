import Phaser from "phaser";

// 场景、人物、能力分别渲染；只接受服务器给当前玩家的可见事实。
class TownScene extends Phaser.Scene {
  constructor() {
    super("town");
    this.people = [];
    this.state = null;
    this.lastEffect = 0;
  }
  create() {
    this.art = this.add.graphics();
    this.fog = this.add.graphics();
    this.drawTown(false);
    for (let i = 0; i < 12; i++) {
      const angle = (i / 12) * Math.PI * 2 - Math.PI / 2;
      const x = 420 + Math.cos(angle) * 300,
        y = 385 + Math.sin(angle) * 110;
      const color = Phaser.Display.Color.HexStringToColor(
        [
          "#d6ba87",
          "#f1c86d",
          "#92cbd6",
          "#b3a4d8",
          "#80c3b5",
          "#d7ad85",
          "#9caec4",
          "#d99ab2",
          "#a9c78b",
          "#d6a0cf",
          "#c9907e",
          "#82b9b4",
        ][i],
      ).color;
      const body = this.add.graphics();
      body.fillStyle(color, 0.9);
      body.fillRoundedRect(-12, -8, 24, 30, 8);
      body.fillCircle(0, -16, 9);
      body.lineStyle(2, 0x23373a, 0.8);
      body.lineBetween(-7, 3, 7, 3);
      const label = this.add
        .text(0, 31, `${i + 1}`, {
          fontFamily: "sans-serif",
          fontSize: 14,
          color: "#cad2ca",
        })
        .setOrigin(0.5);
      const container = this.add.container(x, y, [body, label]);
      this.tweens.add({
        targets: body,
        y: { from: 0, to: -3 - (i % 3) },
        angle: { from: -1, to: 1 },
        duration: 1900 + i * 137,
        yoyo: true,
        repeat: -1,
        ease: "Sine.easeInOut",
      });
      this.people.push(container);
    }
    this.mist = this.add.ellipse(200, 480, 650, 130, 0xa1c5c0, 0.055);
    this.tweens.add({
      targets: this.mist,
      x: 680,
      duration: 19000,
      yoyo: true,
      repeat: -1,
      ease: "Sine.easeInOut",
    });
    if (this.state) this.updateState(this.state);
  }
  drawTown(night) {
    const g = this.art;
    g.clear();
    g.fillStyle(night ? 0x111f2c : 0x293e42);
    g.fillRect(0, 0, 840, 570);
    g.fillStyle(0x78958c, 0.06);
    for (let i = 0; i < 12; i++) g.fillCircle(420, 210, 290 - i * 17);
    g.fillStyle(0xe5d5a3, night ? 0.8 : 0.25);
    g.fillCircle(664, 90, 27);
    g.fillStyle(0x172b30);
    g.fillTriangle(0, 300, 130, 170, 260, 300);
    g.fillTriangle(585, 300, 730, 165, 875, 300);
    for (let i = 0; i < 10; i++) {
      const x = i * 95 - 30;
      g.fillStyle(i % 2 ? 0x1c3034 : 0x20383b);
      g.fillRect(x, 235 + (i % 3) * 17, 80, 150);
      g.fillTriangle(
        x - 8,
        235 + (i % 3) * 17,
        x + 40,
        195 + (i % 3) * 17,
        x + 88,
        235 + (i % 3) * 17,
      );
      g.fillStyle(0xc6ad6e, 0.5);
      g.fillRect(x + 23, 270 + (i % 3) * 17, 8, 13);
    }
    g.fillStyle(0x23383a);
    g.fillRect(371, 135, 98, 235);
    g.fillStyle(0x10292d);
    g.fillTriangle(351, 143, 420, 64, 489, 143);
    g.lineStyle(1, 0x93a79b, 0.22);
    g.strokeRect(381, 149, 78, 215);
    g.fillStyle(0x13272b);
    g.fillCircle(420, 177, 29);
    g.lineStyle(1, 0xcab879, 0.85);
    g.strokeCircle(420, 177, 24);
    g.lineBetween(420, 177, 420, 158);
    g.lineBetween(420, 177, 435, 184);
    g.fillStyle(0xe3c67d, 0.75);
    g.fillRoundedRect(405, 256, 30, 50, 15);
    g.fillStyle(0x101f23);
    g.fillRect(408, 278, 24, 28);
    g.fillStyle(0x192b2c);
    g.fillEllipse(420, 403, 630, 196);
    g.lineStyle(1, 0x6b8981, 0.18);
    for (let i = 0; i < 4; i++)
      g.strokeEllipse(420, 403, 630 - i * 90, 196 - i * 25);
    g.fillStyle(0x7e9283, 0.12);
    g.fillEllipse(420, 403, 140, 55);
    g.fillStyle(0x8a9b88, 0.25);
    g.fillRect(405, 359, 30, 44);
    g.fillEllipse(420, 359, 62, 20);
  }
  updateState(state) {
    if (this.state?.game_id !== state.game_id) this.lastEffect = 0;
    this.state = state;
    if (!this.art) return;
    this.drawTown(state.night);
    state.players.forEach((p, i) =>
      this.people[i].setAlpha(p.alive ? 1 : 0.22),
    );
    const effects = state.story.filter(
      (e) => e.effect && e.id > this.lastEffect,
    );
    if (effects.length) {
      const e = effects.at(-1);
      const at = this.people[(e.actor || 1) - 1];
      const colors = {
        vision: 0x93b8ff,
        potion: 0x9ed0a4,
        shot: 0xffe4a1,
        oath: 0xd7ba73,
        shadow: 0xad90c8,
      };
      const ring = this.add
        .circle(at.x, at.y, 12)
        .setStrokeStyle(2, colors[e.effect]);
      this.tweens.add({
        targets: ring,
        radius: 90,
        alpha: 0,
        duration: 1300,
        onComplete: () => ring.destroy(),
      });
    }
    this.lastEffect = state.story.at(-1)?.id || 0;
  }
}
export function makeScene() {
  const scene = new TownScene();
  const instance = new Phaser.Game({
    type: Phaser.AUTO,
    parent: "scene",
    width: 840,
    height: 570,
    backgroundColor: "#17292e",
    scene,
    scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    audio: { noAudio: true },
    render: { antialias: true },
  });
  return {
    update: (state) => scene.updateState(state),
    destroy: () => instance.destroy(true),
  };
}
