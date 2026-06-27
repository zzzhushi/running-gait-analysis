// Tiny dependency-free SVG charts (return markup strings).

export function lineChart(values, opts = {}) {
  const { w = 320, h = 150, color = "#4dabf7", band = null, dp = 0, labels = null } = opts;
  const pad = { l: 32, r: 12, t: 12, b: labels ? 22 : 12 };
  const present = values.filter((v) => v != null && !Number.isNaN(v));
  if (!present.length) return `<svg class="chart-svg" viewBox="0 0 ${w} ${h}"></svg>`;
  let min = Math.min(...present), max = Math.max(...present);
  if (band) { if (band.lo != null) min = Math.min(min, band.lo); if (band.hi != null) max = Math.max(max, band.hi); }
  if (min === max) { min -= 1; max += 1; }
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const X = (i) => pad.l + (values.length <= 1 ? iw / 2 : (i / (values.length - 1)) * iw);
  const Y = (v) => pad.t + (1 - (v - min) / (max - min)) * ih;

  let bandRect = "";
  if (band) {
    const y1 = Y(band.hi != null ? band.hi : max), y2 = Y(band.lo != null ? band.lo : min);
    bandRect = `<rect x="${pad.l}" y="${y1.toFixed(1)}" width="${iw}" height="${(y2 - y1).toFixed(1)}" fill="#2fbf71" opacity="0.10"/>`;
  }
  let d = "", started = false, dots = "";
  values.forEach((v, i) => {
    if (v == null || Number.isNaN(v)) { started = false; return; }
    d += (started ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1) + " ";
    started = true;
    dots += `<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="2.6" fill="${color}"/>`;
  });
  let xlab = "";
  if (labels) {
    labels.forEach((t, i) => {
      if (t == null) return;
      xlab += `<text x="${X(i).toFixed(1)}" y="${h - 6}" fill="#8b97a7" font-size="9" text-anchor="middle">${t}</text>`;
    });
  }
  return `<svg class="chart-svg" viewBox="0 0 ${w} ${h}">
    ${bandRect}
    <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${h - pad.b}" stroke="#2a323d"/>
    <line x1="${pad.l}" y1="${h - pad.b}" x2="${w - pad.r}" y2="${h - pad.b}" stroke="#2a323d"/>
    <text x="${pad.l - 5}" y="${Y(max) + 3}" fill="#8b97a7" font-size="9" text-anchor="end">${max.toFixed(dp)}</text>
    <text x="${pad.l - 5}" y="${Y(min) + 3}" fill="#8b97a7" font-size="9" text-anchor="end">${min.toFixed(dp)}</text>
    <path d="${d}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round"/>
    ${dots}${xlab}
  </svg>`;
}

export function sparkline(values, opts = {}) {
  const { w = 120, h = 30, color = "#4dabf7" } = opts;
  const present = values.filter((v) => v != null && !Number.isNaN(v));
  if (present.length < 2) return `<svg viewBox="0 0 ${w} ${h}"></svg>`;
  const min = Math.min(...present), max = Math.max(...present) || 1;
  const X = (i) => (i / (values.length - 1)) * w;
  const Y = (v) => h - 2 - (max === min ? h / 2 : ((v - min) / (max - min)) * (h - 4));
  let d = "";
  values.forEach((v, i) => { d += (i ? "L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1) + " "; });
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><path d="${d}" fill="none" stroke="${color}" stroke-width="2"/></svg>`;
}
