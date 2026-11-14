// Tiny pixel-art icons drawn as inline SVG (one rect per horizontal run), so they stay crisp at
// any scale and need no image files. Owner: agent E (HUD).

const PALETTE: Record<string, string> = {
  r: "#e5484d",
  R: "#8c1d22",
  w: "#f0f0f8",
  k: "#14141c",
  y: "#ffc53d",
  Y: "#b3800f",
  g: "#46a758",
  G: "#2b5a35",
  b: "#3e63dd",
  c: "#7ee0ff",
  o: "#f76b15",
  p: "#b07ce8",
  s: "#9090a8",
  S: "#4a4a60",
  n: "#a0662e",
  N: "#5a3a17",
  x: "currentColor",
};

const ART: Record<string, string[]> = {
  heart: [".rr.rr..", "rwrrrrr.", "rrrrrrr.", "rrrrrrr.", ".rrrrr..", "..rrr...", "...r...."],
  coin: ["..YYYY..", ".YyyyyY.", "YyywyyyY", "YyywyyyY", "YyywyyyY", "YyyyyyyY", ".YyyyyY.", "..YYYY.."],
  skull: [".wwwwww.", "wwwwwwww", "wkkwwkkw", "wkkwwkkw", "wwwwwwww", ".wwkkww.", ".wwwwww.", ".w.w.w.."],
  cross: ["..rrr..", "..rrr..", "rrrrrrr", "rrrrrrr", "rrrrrrr", "..rrr..", "..rrr.."],
  clock: ["..cccc..", ".cwwwwc.", "cwwkwwwc", "cwwkwwwc", "cwwkkkwc", "cwwwwwwc", ".cwwwwc.", "..cccc.."],
  bed: ["........", "s.......", "sww.....", "swwbbbbb", "ssssssss", "s......s"],
  ct: ["..ssss..", ".s....s.", "s..cc..s", "wwwwwwww", "s......s", ".s....s.", "..ssss.."],
  bolt: ["....yy..", "...yy...", "..yy....", ".yyyyy..", "...yy...", "..yy....", ".yy.....", ".y......"],
  arrow: ["....c...", "....cc..", "ccccccc.", "cccccccc", "ccccccc.", "....cc..", "....c..."],
  zzz: ["....cccc", "......c.", ".....c..", "....cccc", "cccc....", "..c.....", ".c......", "cccc...."],
  agency: ["..NNNN..", "..N..N..", "nnnnnnnn", "nnnnnnnn", "NNNyyNNN", "nnnnnnnn", "nnnnnnnn"],
  wrench: [".s...s..", ".ss.ss..", "..sss...", "...s....", "...ss...", "....ss..", ".....ss.", "......s."],
  siren: ["...rr...", "..rwrr..", ".rrrrrr.", ".rrrrrr.", "ssssssss", "SSSSSSSS"],
  check: [".......g", "......gg", ".....gg.", "g...gg..", "gg.gg...", ".ggg....", "..g....."],
  x: ["rr....rr", ".rr..rr.", "..rrrr..", "...rr...", "..rrrr..", ".rr..rr.", "rr....rr"],
  warn: ["...yy...", "..yyyy..", "..ykky..", ".yykkyy.", ".yykkyy.", "yyyyyyyy", "yyykkyyy", "yyyyyyyy"],
  door: [".nnnnnn.", ".nNNNNn.", ".nNNNNn.", ".nNNNyn.", ".nNNNNn.", ".nNNNNn.", ".nnnnnn."],
  person: ["...ww...", "...ww...", "..bbbb..", ".b.bb.b.", "...bb...", "..b..b..", "..b..b.."],
  dizzy: [".pppp...", "p....p..", "p.pp.p..", "p.p..p..", "p.pppp..", "p.......", ".ppppp.."],
  up: ["...oo...", "..oooo..", ".oooooo.", "oooooooo", "...oo...", "...oo...", "...oo..."],
  tired: ["ssssss..", "s....ss.", "soo..ss.", "soo..ss.", "s....ss.", "ssssss.."],
  flag: ["s.......", "swkwk...", "skwkw...", "swkwk...", "s.......", "s.......", "s......."],
  sick: ["...ww...", "..wrrw..", "..wrrw..", "..wrrw..", ".wrrrrw.", ".wrrrrw.", "..wwww.."],
  dot: ["...", ".s.", "..."],
  play: [".x.....", ".xx....", ".xxx...", ".xxxx..", ".xxx...", ".xx....", ".x....."],
  pause: [".xx.xx.", ".xx.xx.", ".xx.xx.", ".xx.xx.", ".xx.xx.", ".xx.xx.", ".xx.xx."],
  stepf: [".x...x.", ".xx..x.", ".xxx.x.", ".xxxxx.", ".xxx.x.", ".xx..x.", ".x...x."],
  stepb: [".x...x.", ".x..xx.", ".x.xxx.", ".xxxxx.", ".x.xxx.", ".x..xx.", ".x...x."],
  start: ["x...x..x", "x..xx.xx", "x.xxxxxx", "xxxxxxxx", "x.xxxxxx", "x..xx.xx", "x...x..x"],
  end: ["x..x...x", "xx.xx..x", "xxxxxx.x", "xxxxxxxx", "xxxxxx.x", "xx.xx..x", "x..x...x"],
};

const cache = new Map<string, string>();

function svgFor(name: string): string {
  const hit = cache.get(name);
  if (hit) return hit;
  const rows = ART[name] ?? ART.dot;
  const w = Math.max(...rows.map((r) => r.length));
  const h = rows.length;
  const size = Math.max(w, h);
  const ox = Math.floor((size - w) / 2);
  const oy = Math.floor((size - h) / 2);
  let rects = "";
  rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const ch = row[x];
      let end = x + 1;
      while (end < row.length && row[end] === ch) end++;
      if (PALETTE[ch]) {
        rects += `<rect x="${x + ox}" y="${y + oy}" width="${end - x}" height="1" fill="${PALETTE[ch]}"/>`;
      }
      x = end;
    }
  });
  const svg = `<svg viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges" aria-hidden="true">${rects}</svg>`;
  cache.set(name, svg);
  return svg;
}

export function hasIcon(name: string): boolean {
  return name in ART;
}

export function icon(name: string, cls = ""): HTMLElement {
  const span = document.createElement("span");
  span.className = `px-icon ${cls}`.trim();
  // The SVG markup is built only from the fixed ART table above, never from replay data.
  span.innerHTML = svgFor(hasIcon(name) ? name : "dot");
  return span;
}
