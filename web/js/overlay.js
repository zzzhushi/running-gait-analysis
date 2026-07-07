// Canvas skeleton overlay. Maps normalized pose pixels -> canvas, draws the
// color-coded skeleton, joint-angle arcs, COM/ground reference lines, and trails.

const AXIAL = "#7f8c9b", LEFTC = "#4dabf7", RIGHTC = "#f59f00";

// Don't draw joints the pose model isn't confident about. On a rear view the hands are
// occluded, so wrists come back with ~0.2 confidence at essentially guessed positions —
// drawing them made the forearm lines flail off the body ("arms don't match"). Below this
// the joint (and any bone to it) is skipped, so the skeleton shows only what's tracked.
const MIN_DRAW_CONF = 0.35;

const BONES = [
  ["nose", "neck", AXIAL], ["neck", "mid_hip", AXIAL],
  ["mid_hip", "l_hip", AXIAL], ["mid_hip", "r_hip", AXIAL],
  ["neck", "l_shoulder", LEFTC], ["l_shoulder", "l_elbow", LEFTC], ["l_elbow", "l_wrist", LEFTC],
  ["neck", "r_shoulder", RIGHTC], ["r_shoulder", "r_elbow", RIGHTC], ["r_elbow", "r_wrist", RIGHTC],
  ["l_hip", "l_knee", LEFTC], ["l_knee", "l_ankle", LEFTC], ["l_ankle", "l_heel", LEFTC],
  ["l_heel", "l_big_toe", LEFTC], ["l_ankle", "l_big_toe", LEFTC],
  ["r_hip", "r_knee", RIGHTC], ["r_knee", "r_ankle", RIGHTC], ["r_ankle", "r_heel", RIGHTC],
  ["r_heel", "r_big_toe", RIGHTC], ["r_ankle", "r_big_toe", RIGHTC],
];

export class SkeletonRenderer {
  constructor(canvas, pose, { hasVideo = false } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.pose = pose;
    this.hasVideo = hasVideo;
    this.idx = Object.fromEntries(pose.keypoint_names.map((n, i) => [n, i]));
    this.tf = null;
    this.resize();
  }

  resize() {
    const r = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.max(1, Math.round(r.width * dpr));
    this.canvas.height = Math.max(1, Math.round(r.height * dpr));
    this.cw = r.width; this.ch = r.height;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.tf = this._transform();
  }

  _bbox() {
    let minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
    for (const fr of this.pose.frames) {
      for (const p of fr) {
        if (p[2] < 0.1) continue;
        if (p[0] < minx) minx = p[0]; if (p[0] > maxx) maxx = p[0];
        if (p[1] < miny) miny = p[1]; if (p[1] > maxy) maxy = p[1];
      }
    }
    if (maxx < minx) return { x: 0, y: 0, w: this.pose.width || 1, h: this.pose.height || 1 };
    return { x: minx, y: miny, w: maxx - minx, h: maxy - miny };
  }

  _transform() {
    // hasVideo: contain the whole frame so overlay lines up with the video.
    // skeleton-only: contain the skeleton bbox with padding so the figure is large.
    const pad = this.hasVideo ? 0 : 0.12;
    const src = this.hasVideo
      ? { x: 0, y: 0, w: this.pose.width || 1, h: this.pose.height || 1 }
      : this._bbox();
    const availW = this.cw * (1 - 2 * pad), availH = this.ch * (1 - 2 * pad);
    const s = Math.min(availW / src.w, availH / src.h);
    const ox = (this.cw - s * src.w) / 2 - s * src.x;
    const oy = (this.ch - s * src.h) / 2 - s * src.y;
    return { s, ox, oy };
  }

  P(frame, name) {
    const i = this.idx[name];
    if (i == null) return null;
    const p = this.pose.frames[frame] && this.pose.frames[frame][i];
    if (!p || p[2] < MIN_DRAW_CONF) return null;
    return [p[0] * this.tf.s + this.tf.ox, p[1] * this.tf.s + this.tf.oy];
  }

  render(frame, opts = {}) {
    const { ctx } = this;
    ctx.clearRect(0, 0, this.cw, this.ch);
    frame = Math.max(0, Math.min(this.pose.frames.length - 1, frame | 0));
    if (opts.refs !== false) this._refs(frame);
    if (opts.trails) this._trails(frame);
    if (opts.skeleton !== false) this._skeleton(frame);
    if (opts.angles !== false) this._angles(frame);
  }

  _refs(frame) {
    const { ctx } = this;
    const hip = this.P(frame, "mid_hip");
    ctx.save();
    ctx.setLineDash([5, 6]); ctx.lineWidth = 1; ctx.strokeStyle = "rgba(230,237,243,.28)";
    if (hip) { ctx.beginPath(); ctx.moveTo(hip[0], 0); ctx.lineTo(hip[0], this.ch); ctx.stroke(); }
    // ground line at lowest confident foot point of this frame
    let gy = -1;
    for (const n of ["l_heel", "r_heel", "l_big_toe", "r_big_toe", "l_ankle", "r_ankle"]) {
      const p = this.P(frame, n); if (p && p[1] > gy) gy = p[1];
    }
    if (gy > 0) { ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(this.cw, gy); ctx.stroke(); }
    ctx.restore();
  }

  _skeleton(frame) {
    const { ctx } = this;
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    for (const [a, b, color] of BONES) {
      const pa = this.P(frame, a), pb = this.P(frame, b);
      if (!pa || !pb) continue;
      ctx.strokeStyle = color; ctx.lineWidth = color === AXIAL ? 5 : 4;
      ctx.beginPath(); ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); ctx.stroke();
    }
    for (const name of this.pose.keypoint_names) {
      const p = this.P(frame, name); if (!p) continue;
      const left = name.startsWith("l_"), right = name.startsWith("r_");
      ctx.fillStyle = left ? LEFTC : right ? RIGHTC : "#cdd6e0";
      ctx.beginPath(); ctx.arc(p[0], p[1], 3.2, 0, 7); ctx.fill();
    }
  }

  _angles(frame) {
    const { ctx } = this;
    // knee flexion arcs
    for (const side of ["l", "r"]) {
      const hip = this.P(frame, side + "_hip");
      const knee = this.P(frame, side + "_knee");
      const ankle = this.P(frame, side + "_ankle");
      if (!hip || !knee || !ankle) continue;
      const a1 = Math.atan2(hip[1] - knee[1], hip[0] - knee[0]);
      const a2 = Math.atan2(ankle[1] - knee[1], ankle[0] - knee[0]);
      const interior = Math.abs(((a2 - a1) * 180) / Math.PI);
      const flex = 180 - Math.min(interior, 360 - interior);
      ctx.strokeStyle = side === "l" ? LEFTC : RIGHTC;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(knee[0], knee[1], 18, a1, a2); ctx.stroke();
      this._tag(knee[0] + 14, knee[1] - 8, Math.round(flex) + "°", side === "l" ? LEFTC : RIGHTC);
    }
    // trunk lean
    const hip = this.P(frame, "mid_hip"), neck = this.P(frame, "neck");
    if (hip && neck) {
      ctx.save();
      ctx.setLineDash([3, 4]); ctx.strokeStyle = "rgba(230,237,243,.45)"; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(hip[0], hip[1]); ctx.lineTo(hip[0], hip[1] - 70); ctx.stroke();
      ctx.restore();
      const lean = Math.abs((Math.atan2(neck[0] - hip[0], hip[1] - neck[1]) * 180) / Math.PI);
      this._tag(hip[0] + 10, hip[1] - 40, Math.round(lean) + "°", "#cdd6e0");
    }
  }

  _trails(frame) {
    const { ctx } = this;
    const K = 16;
    for (const [name, color] of [["l_ankle", LEFTC], ["r_ankle", RIGHTC], ["l_wrist", LEFTC], ["r_wrist", RIGHTC]]) {
      ctx.lineWidth = 2.5;
      for (let f = Math.max(1, frame - K); f <= frame; f++) {
        const p0 = this.P(f - 1, name), p1 = this.P(f, name);
        if (!p0 || !p1) continue;
        ctx.globalAlpha = (f - (frame - K)) / K * 0.6;
        ctx.strokeStyle = color;
        ctx.beginPath(); ctx.moveTo(p0[0], p0[1]); ctx.lineTo(p1[0], p1[1]); ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }

  _tag(x, y, text, color) {
    const { ctx } = this;
    ctx.font = "600 12px -apple-system, system-ui, sans-serif";
    const w = ctx.measureText(text).width + 8;
    ctx.fillStyle = "rgba(7,9,13,.7)";
    ctx.fillRect(x - 2, y - 12, w, 16);
    ctx.fillStyle = color; ctx.fillText(text, x + 2, y);
  }
}

// Draw the gait-cycle phase ribbon (stance bands per side + strike ticks).
export function drawTimeline(canvas, result) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const r = canvas.getBoundingClientRect();
  canvas.width = r.width * dpr; canvas.height = r.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const W = r.width, H = r.height, n = result.summary.n_frames;
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#0b0f14"; ctx.fillRect(0, 0, W, H);
  const lanes = { l: { y: 3, c: "#4dabf7" }, r: { y: H / 2 + 1, c: "#f59f00" } };
  const lh = H / 2 - 4;
  for (const side of ["l", "r"]) {
    const lane = lanes[side];
    for (const [s, e] of result.events.stance[side] || []) {
      const x = (s / n) * W, w = Math.max(2, ((e - s) / n) * W);
      ctx.fillStyle = lane.c + "cc"; ctx.fillRect(x, lane.y, w, lh);
    }
    ctx.fillStyle = "#fff";
    for (const s of result.events.strikes[side] || []) {
      ctx.fillRect((s / n) * W - 0.5, lane.y, 1.5, lh);
    }
  }
}
