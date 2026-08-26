var RR = Object.defineProperty;
var ES = (n) => {
  throw TypeError(n);
};
var OR = (n, t, i) => t in n ? RR(n, t, { enumerable: !0, configurable: !0, writable: !0, value: i }) : n[t] = i;
var w = (n, t, i) => OR(n, typeof t != "symbol" ? t + "" : t, i), Kp = (n, t, i) => t.has(n) || ES("Cannot " + i);
var v = (n, t, i) => (Kp(n, t, "read from private field"), i ? i.call(n) : t.get(n)), k = (n, t, i) => t.has(n) ? ES("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(n) : t.set(n, i), A = (n, t, i, a) => (Kp(n, t, "write to private field"), a ? a.call(n, i) : t.set(n, i), i), L = (n, t, i) => (Kp(n, t, "access private method"), i);
var vh = (n, t, i, a) => ({
  set _(r) {
    A(n, t, r, i);
  },
  get _() {
    return v(n, t, a);
  }
});
function zR(n) {
  return n && n.__esModule && Object.prototype.hasOwnProperty.call(n, "default") ? n.default : n;
}
var Ip = { exports: {} }, Lu = {};
/**
 * @license React
 * react-jsx-runtime.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var AS;
function kR() {
  if (AS) return Lu;
  AS = 1;
  var n = Symbol.for("react.transitional.element"), t = Symbol.for("react.fragment");
  function i(a, r, u) {
    var c = null;
    if (u !== void 0 && (c = "" + u), r.key !== void 0 && (c = "" + r.key), "key" in r) {
      u = {};
      for (var f in r)
        f !== "key" && (u[f] = r[f]);
    } else u = r;
    return r = u.ref, {
      $$typeof: n,
      type: a,
      key: c,
      ref: r !== void 0 ? r : null,
      props: u
    };
  }
  return Lu.Fragment = t, Lu.jsx = i, Lu.jsxs = i, Lu;
}
var DS;
function VR() {
  return DS || (DS = 1, Ip.exports = kR()), Ip.exports;
}
var Z = VR();
const Ds = "generated", dM = "source-over", PR = "resize", mM = "visibilitychange", sa = 100, bt = 0.5, Ae = 1e3, Dt = {
  x: 0,
  y: 0,
  z: 0
}, bh = {
  a: 1,
  b: 0,
  c: 0,
  d: 1
}, Dl = "random", Nh = "mid", Bt = 2, oa = Math.PI * Bt, $p = 60, LR = 1, Ug = "true", RS = "false", Wp = "canvas", _R = 0, ra = 2, OS = 100, BR = 1, jg = 1, zS = 1, NR = 1, fe = 255, yn = 360, To = 100, Co = 100, $h = 0, Eo = 0, UR = 60, jR = 0, Hg = 0.25, kS = bt + Hg, Wt = 0, xh = 0, pM = 0, HR = 1, qR = 0, gM = 1, Di = 1, VS = 1, GR = 0, YR = 120, XR = 0, FR = 0, ZR = 1e4, QR = 0, qu = 1, yM = 0, vM = 1, KR = 1, IR = 0, PS = 0, $R = 1, WR = 0, fi = 0, JR = 1, LS = 1, Iu = 1, hi = 0, De = 1, _S = 0, BS = 1, Sd = 0, bM = 400, ic = 3, Jp = 6, xM = 1, SM = 1, t2 = 0, e2 = 0, n2 = 0, i2 = 0, wM = 1;
var Pe;
(function(n) {
  n.bottom = "bottom", n.bottomLeft = "bottom-left", n.bottomRight = "bottom-right", n.left = "left", n.none = "none", n.right = "right", n.top = "top", n.topLeft = "top-left", n.topRight = "top-right", n.outside = "outside", n.inside = "inside";
})(Pe || (Pe = {}));
function Oa(n) {
  return "z" in n ? n.z : Dt.z;
}
var dc, qg;
const On = class On {
  constructor(t = Dt.x, i = Dt.y, a = Dt.z) {
    k(this, dc);
    w(this, "x");
    w(this, "y");
    w(this, "z");
    this.x = t, this.y = i, this.z = a;
  }
  static get origin() {
    return On.create(Dt.x, Dt.y, Dt.z);
  }
  get angle() {
    return Math.atan2(this.y, this.x);
  }
  set angle(t) {
    L(this, dc, qg).call(this, t, this.length);
  }
  get length() {
    return Math.sqrt(this.getLengthSq());
  }
  set length(t) {
    L(this, dc, qg).call(this, this.angle, t);
  }
  static clone(t) {
    return On.create(t.x, t.y, Oa(t));
  }
  static create(t, i, a) {
    return typeof t == "number" ? new On(t, i ?? Dt.y, a ?? Dt.z) : new On(t.x, t.y, Oa(t));
  }
  add(t) {
    return On.create(this.x + t.x, this.y + t.y, this.z + Oa(t));
  }
  addTo(t) {
    this.x += t.x, this.y += t.y, this.z += Oa(t);
  }
  copy() {
    return On.clone(this);
  }
  div(t) {
    return On.create(this.x / t, this.y / t, this.z / t);
  }
  getLengthSq() {
    return this.x ** ra + this.y ** ra;
  }
  mult(t) {
    return On.create(this.x * t, this.y * t, this.z * t);
  }
  multTo(t) {
    this.x *= t, this.y *= t, this.z *= t;
  }
  normalize() {
    const t = this.length;
    t != yM && this.multTo(NR / t);
  }
  rotate(t) {
    return On.create(this.x * Math.cos(t) - this.y * Math.sin(t), this.x * Math.sin(t) + this.y * Math.cos(t), Dt.z);
  }
  setTo(t) {
    this.x = t.x, this.y = t.y, this.z = Oa(t);
  }
  sub(t) {
    return On.create(this.x - t.x, this.y - t.y, this.z - Oa(t));
  }
  subFrom(t) {
    this.x -= t.x, this.y -= t.y, this.z -= Oa(t);
  }
};
dc = new WeakSet(), qg = function(t, i) {
  this.x = Math.cos(t) * i, this.y = Math.sin(t) * i;
};
let Ba = On;
class Qe extends Ba {
  constructor(t = Dt.x, i = Dt.y) {
    super(t, i, Dt.z);
  }
  static get origin() {
    return Qe.create(Dt.x, Dt.y);
  }
  static clone(t) {
    return Qe.create(t.x, t.y);
  }
  static create(t, i) {
    return typeof t == "number" ? new Qe(t, i ?? Dt.y) : new Qe(t.x, t.y);
  }
}
function MM(n) {
  return typeof n == "boolean";
}
function Ao(n) {
  return typeof n == "string";
}
function Do(n) {
  return typeof n == "number";
}
function $u(n) {
  return typeof n == "object" && n !== null;
}
function vn(n) {
  return Array.isArray(n);
}
function gt(n) {
  return n == null;
}
const s2 = 180, a2 = Math.PI / s2;
let o2 = Math.random;
const TM = {
  nextFrame: (n) => requestAnimationFrame(n),
  cancel: (n) => {
    cancelAnimationFrame(n);
  }
};
function Yt() {
  return Nn(o2(), 0, 1 - Number.EPSILON);
}
function CM(n, t) {
  return Yt() * (t - n) + n;
}
function r2(n) {
  return TM.nextFrame(n);
}
function l2(n) {
  TM.cancel(n);
}
function Nn(n, t, i) {
  return Math.min(Math.max(n, t), i);
}
function tg(n, t, i, a) {
  return Math.floor((n * i + t * a) / (i + a));
}
function Oi(n) {
  const t = wd(n), i = 0;
  let a = Qy(n);
  return t === a && (a = i), CM(a, t);
}
function ht(n) {
  return Do(n) ? n : Oi(n);
}
function Qy(n) {
  return Do(n) ? n : n.min;
}
function wd(n) {
  return Do(n) ? n : n.max;
}
function Ro(n, t) {
  if (n === t || t === void 0 && Do(n))
    return n;
  const i = Qy(n), a = wd(n);
  return t !== void 0 ? {
    min: Math.min(i, t),
    max: Math.max(a, t)
  } : Ro(i, a);
}
function _n(n, t) {
  const i = n.x - t.x, a = n.y - t.y;
  return { dx: i, dy: a, distance: Math.hypot(i, a) };
}
function EM(n, t) {
  const i = n.x - t.x, a = n.y - t.y;
  return i * i + a * a;
}
function Oo(n, t) {
  return Math.sqrt(EM(n, t));
}
function u2(n, t, i) {
  return EM(n, t) <= i * i;
}
function So(n) {
  return n * a2;
}
function c2(n, t, i) {
  if (Do(n))
    return So(n);
  switch (n) {
    case Pe.top:
      return -Math.PI * bt;
    case Pe.topRight:
      return -Math.PI * Hg;
    case Pe.right:
      return jR;
    case Pe.bottomRight:
      return Math.PI * Hg;
    case Pe.bottom:
      return Math.PI * bt;
    case Pe.bottomLeft:
      return Math.PI * kS;
    case Pe.left:
      return Math.PI;
    case Pe.topLeft:
      return -Math.PI * kS;
    case Pe.inside:
      return Math.atan2(i.y - t.y, i.x - t.x);
    case Pe.outside:
      return Math.atan2(t.y - i.y, t.x - i.x);
    default:
      return Yt() * oa;
  }
}
function f2(n) {
  const t = Qe.origin;
  return t.length = 1, t.angle = n, t;
}
function NS(n, t, i, a) {
  return Qe.create(n.x * (i - a) / (i + a) + t.x * Bt * a / (i + a), n.y);
}
function h2(n) {
  const { position: t, size: i } = n;
  return {
    x: (t == null ? void 0 : t.x) ?? Yt() * i.width,
    y: (t == null ? void 0 : t.y) ?? Yt() * i.height
  };
}
function AM(n) {
  return n ? n.endsWith("%") ? parseFloat(n) / sa : parseFloat(n) : 1;
}
var Mt;
(function(n) {
  n.bottom = "bottom", n.left = "left", n.right = "right", n.top = "top";
})(Mt || (Mt = {}));
var Wh;
(function(n) {
  n.precise = "precise", n.percent = "percent";
})(Wh || (Wh = {}));
const d2 = 0;
function US(n) {
  return n === "__proto__" || n === "constructor" || n === "prototype";
}
function m2() {
  return typeof matchMedia < "u";
}
function Un() {
  return globalThis.document;
}
function jS(n) {
  if (m2())
    return matchMedia(n);
}
function p2(n) {
  if (!(typeof MutationObserver > "u"))
    return new MutationObserver(n);
}
function Zt(n, t) {
  return n === t || vn(t) && t.includes(n);
}
function Md(n, t, i = !0) {
  return n[t !== void 0 && i ? t % n.length : Math.floor(Yt() * n.length)];
}
function g2(n, t, i, a, r) {
  return y2(Zc(n, a ?? d2), t, i, r);
}
function y2(n, t, i, a) {
  let r = !0;
  return (!a || a === Mt.bottom) && (r = n.top < t.height + i.x), r && (!a || a === Mt.left) && (r = n.right > i.x), r && (!a || a === Mt.right) && (r = n.left < t.width + i.y), r && (!a || a === Mt.top) && (r = n.bottom > i.y), r;
}
function Zc(n, t) {
  return {
    bottom: n.y + t,
    left: n.x - t,
    right: n.x + t,
    top: n.y - t
  };
}
function bn(n, ...t) {
  for (const i of t) {
    if (gt(i))
      continue;
    if (!$u(i)) {
      n = i;
      continue;
    }
    Array.isArray(i) ? Array.isArray(n) || (n = []) : (!$u(n) || Array.isArray(n)) && (n = /* @__PURE__ */ Object.create(null));
    const a = Object.keys(i);
    if (!a.some((u) => {
      const c = i[u];
      return $u(c) || Array.isArray(c);
    })) {
      const u = i, c = n;
      for (const f of a) {
        if (US(f))
          continue;
        const m = u[f];
        m !== void 0 && (c[f] = m);
      }
      continue;
    }
    for (const u of a) {
      if (US(u))
        continue;
      const c = i, f = n, m = c[u];
      f[u] = Array.isArray(m) ? m.map((p) => bn(void 0, p)) : bn(f[u], m);
    }
  }
  return n;
}
function Gg(n) {
  return {
    position: n.getPosition(),
    radius: n.getRadius(),
    mass: n.getMass(),
    velocity: n.velocity,
    factor: Qe.create(ht(n.options.bounce.horizontal.value), ht(n.options.bounce.vertical.value))
  };
}
function DM(n, t) {
  const { x: i, y: a } = n.velocity.sub(t.velocity), [r, u] = [n.position, t.position], { dx: c, dy: f } = _n(u, r);
  if (i * c + a * f < 0)
    return;
  const p = -Math.atan2(f, c), g = n.mass, y = t.mass, b = n.velocity.rotate(p), S = t.velocity.rotate(p), T = NS(b, S, g, y), C = NS(S, b, g, y), R = T.rotate(-p), z = C.rotate(-p);
  n.velocity.x = R.x * n.factor.x, n.velocity.y = R.y * n.factor.y, t.velocity.x = z.x * t.factor.x, t.velocity.y = z.y * t.factor.y;
}
function Gn(n, t) {
  return vn(n) ? n.map((a, r) => t(a, r)) : t(n, 0);
}
function Vn(n, t, i) {
  return vn(n) ? Md(n, t, i) : n;
}
function v2(n, t) {
  if (!(n.mode === Wh.percent)) {
    const { mode: r, ...u } = n;
    return u;
  }
  return "x" in n ? {
    x: n.x / sa * t.width,
    y: n.y / sa * t.height
  } : {
    width: n.width / sa * t.width,
    height: n.height / sa * t.height
  };
}
function b2(n, t) {
  return v2(n, t);
}
function x2(n) {
  var i, a;
  const t = Un().createElement("div").style;
  for (const r in n) {
    const u = n[r];
    if (!(r in n) || gt(u))
      continue;
    const c = (i = n.getPropertyValue) == null ? void 0 : i.call(n, u);
    if (!c)
      continue;
    const f = (a = n.getPropertyPriority) == null ? void 0 : a.call(n, u);
    f ? t.setProperty(u, c, f) : t.setProperty(u, c);
  }
  return t;
}
let HS, eg;
function S2(n) {
  if (HS !== n || !eg) {
    HS = n;
    const t = Un().createElement("div").style, i = 10, a = {
      width: "100%",
      height: "100%",
      margin: "0",
      padding: "0",
      borderWidth: "0",
      position: "fixed",
      zIndex: n.toString(i),
      "z-index": n.toString(i),
      top: "0",
      left: "0",
      "pointer-events": "none"
    };
    for (const r in a) {
      const u = a[r];
      u !== void 0 && t.setProperty(r, u);
    }
    eg = t;
  }
  return eg;
}
function Ne(n, t, i, a, r) {
  if (a) {
    let u = { passive: !0 };
    MM(r) ? u.capture = r : r !== void 0 && (u = r), n.addEventListener(t, i, u);
  } else {
    const u = r;
    n.removeEventListener(t, i, u);
  }
}
async function RM(n, t, i, a = !1) {
  let r = t.get(n);
  return (!r || a) && (r = await Promise.all([...i.values()].map((u) => u(n))), t.set(n, r)), r;
}
async function Yg(n, t, i, a = !1) {
  let r = t.get(n);
  if (!r || a) {
    const u = await Promise.all([...i.entries()].map(([c, f]) => f(n).then((m) => [c, m])));
    r = new Map(u), t.set(n, r);
  }
  return r;
}
var zn;
class w2 {
  constructor() {
    k(this, zn);
    A(this, zn, /* @__PURE__ */ new Map());
  }
  addEventListener(t, i) {
    this.removeEventListener(t, i);
    let a = v(this, zn).get(t);
    a || (a = [], v(this, zn).set(t, a)), a.push(i);
  }
  dispatchEvent(t, i) {
    const a = v(this, zn).get(t);
    a == null || a.forEach((r) => {
      r(i);
    });
  }
  hasEventListener(t) {
    return !!v(this, zn).get(t);
  }
  removeAllEventListeners(t) {
    t ? v(this, zn).delete(t) : A(this, zn, /* @__PURE__ */ new Map());
  }
  removeEventListener(t, i) {
    const a = v(this, zn).get(t);
    if (!a)
      return;
    const r = a.length, u = a.indexOf(i);
    u < fi || (r === Iu ? v(this, zn).delete(t) : a.splice(u, Iu));
  }
}
zn = new WeakMap();
var on;
(function(n) {
  n.configAdded = "configAdded", n.containerInit = "containerInit", n.particlesSetup = "particlesSetup", n.containerStarted = "containerStarted", n.containerStopped = "containerStopped", n.containerDestroyed = "containerDestroyed", n.containerPaused = "containerPaused", n.containerPlay = "containerPlay", n.containerBuilt = "containerBuilt", n.particleAdded = "particleAdded", n.particleDestroyed = "particleDestroyed", n.particleRemoved = "particleRemoved";
})(on || (on = {}));
var Ha, mc, Hr, qr, Gr, qa, Yr, pc, Xg;
class M2 {
  constructor(t) {
    k(this, pc);
    w(this, "colorManagers", /* @__PURE__ */ new Map());
    w(this, "easingFunctions", /* @__PURE__ */ new Map());
    w(this, "effectDrawers", /* @__PURE__ */ new Map());
    w(this, "initializers", {
      effects: /* @__PURE__ */ new Map(),
      shapes: /* @__PURE__ */ new Map(),
      updaters: /* @__PURE__ */ new Map()
    });
    w(this, "palettes", /* @__PURE__ */ new Map());
    w(this, "plugins", []);
    w(this, "presets", /* @__PURE__ */ new Map());
    w(this, "shapeDrawers", /* @__PURE__ */ new Map());
    w(this, "updaters", /* @__PURE__ */ new Map());
    k(this, Ha, /* @__PURE__ */ new Set());
    k(this, mc, /* @__PURE__ */ new Map());
    k(this, Hr);
    k(this, qr, /* @__PURE__ */ new Set());
    k(this, Gr, !1);
    k(this, qa, !1);
    k(this, Yr, /* @__PURE__ */ new Set());
    A(this, Hr, t);
  }
  get configs() {
    const t = {};
    for (const [i, a] of v(this, mc))
      t[i] = a;
    return t;
  }
  addColorManager(t, i) {
    this.colorManagers.set(t, i);
  }
  addConfig(t) {
    const i = t.key ?? t.name ?? "default";
    v(this, mc).set(i, t), v(this, Hr).dispatchEvent(on.configAdded, { data: { name: i, config: t } });
  }
  addEasing(t, i) {
    this.easingFunctions.get(t) || this.easingFunctions.set(t, i);
  }
  addEffect(t, i) {
    this.initializers.effects.set(t, i);
  }
  addPalette(t, i) {
    this.palettes.set(t, i);
  }
  addParticleUpdater(t, i) {
    this.initializers.updaters.set(t, i);
  }
  addPlugin(t) {
    this.getPlugin(t.id) || this.plugins.push(t);
  }
  addPreset(t, i, a = !1) {
    (a || !this.getPreset(t)) && this.presets.set(t, i);
  }
  addShape(t, i) {
    for (const a of t)
      this.initializers.shapes.set(a, i);
  }
  clearPlugins(t) {
    this.effectDrawers.delete(t), this.shapeDrawers.delete(t), this.updaters.delete(t);
  }
  getEasing(t) {
    return this.easingFunctions.get(t) ?? ((i) => i);
  }
  getEffectDrawers(t, i = !1) {
    return Yg(t, this.effectDrawers, this.initializers.effects, i);
  }
  getPalette(t) {
    return this.palettes.get(t);
  }
  getPlugin(t) {
    return this.plugins.find((i) => i.id === t);
  }
  getPreset(t) {
    return this.presets.get(t);
  }
  async getShapeDrawers(t, i = !1) {
    return Yg(t, this.shapeDrawers, this.initializers.shapes, i);
  }
  async getUpdaters(t, i = !1) {
    return RM(t, this.updaters, this.initializers.updaters, i);
  }
  async init() {
    if (!(v(this, Gr) || v(this, qa))) {
      A(this, qa, !0), A(this, qr, /* @__PURE__ */ new Set()), A(this, Ha, new Set(v(this, Yr)));
      try {
        for (const t of v(this, Ha))
          await L(this, pc, Xg).call(this, t, v(this, qr), v(this, Ha));
      } finally {
        v(this, Yr).clear(), A(this, qa, !1), A(this, Gr, !0);
      }
    }
  }
  loadParticlesOptions(t, i, ...a) {
    const r = this.updaters.get(t);
    r && r.forEach((u) => {
      var c;
      return (c = u.loadOptions) == null ? void 0 : c.call(u, i, ...a);
    });
  }
  async register(...t) {
    if (v(this, Gr))
      throw new Error("Register plugins can only be done before calling tsParticles.load()");
    for (const i of t)
      v(this, qa) ? await L(this, pc, Xg).call(this, i, v(this, qr), v(this, Ha)) : v(this, Yr).add(i);
  }
}
Ha = new WeakMap(), mc = new WeakMap(), Hr = new WeakMap(), qr = new WeakMap(), Gr = new WeakMap(), qa = new WeakMap(), Yr = new WeakMap(), pc = new WeakSet(), Xg = async function(t, i, a) {
  i.has(t) || (i.add(t), a.add(t), await t(v(this, Hr)));
};
const T2 = "tsParticles - Error", Mr = (n) => (...t) => {
  n(...t);
}, C2 = {
  debug: Mr(console.debug),
  error: (n, ...t) => {
    console.error(`${T2} - ${n}`, ...t);
  },
  info: Mr(console.info),
  log: Mr(console.log),
  trace: Mr(console.trace),
  verbose: Mr(console.log),
  warning: Mr(console.warn)
};
function zo() {
  return C2;
}
const Sh = "100%";
async function E2(n) {
  const t = Vn(n.url, n.index);
  if (!t)
    return n.fallback;
  const i = await fetch(t);
  return i.ok ? await i.json() : (zo().error(`${i.status.toString()} while retrieving config file`), n.fallback);
}
const A2 = (n) => {
  var r, u, c, f, m;
  const t = Un();
  let i;
  if (n instanceof HTMLCanvasElement || n.tagName.toLowerCase() === Wp)
    i = n, (r = i.dataset)[Ds] ?? (r[Ds] = RS), i.dataset[Ds] === Ug && ((u = i.style).width || (u.width = Sh), (c = i.style).height || (c.height = Sh), i.style.pointerEvents = "none", i.style.setProperty("pointer-events", "none"));
  else {
    const p = n.getElementsByTagName(Wp), g = p.item(FR);
    g ? (i = g, i.dataset[Ds] = RS) : (i = t.createElement(Wp), i.dataset[Ds] = Ug, n.appendChild(i)), (f = i.style).width || (f.width = Sh), (m = i.style).height || (m.height = Sh), i.style.pointerEvents = "none", i.style.setProperty("pointer-events", "none");
  }
  return i;
}, D2 = (n, t) => {
  const i = Un();
  let a = t ?? i.getElementById(n);
  return a || (a = i.createElement("canvas"), a.id = n, a.dataset[Ds] = Ug, i.body.append(a), a);
};
var cd, Xr, gc;
class R2 {
  constructor() {
    w(this, "pluginManager", new M2(this));
    k(this, cd, []);
    k(this, Xr, new w2());
    k(this, gc, !1);
  }
  get items() {
    return v(this, cd);
  }
  get version() {
    return "4.3.2";
  }
  addEventListener(t, i) {
    v(this, Xr).addEventListener(t, i);
  }
  checkVersion(t) {
    if (this.version !== t)
      throw new Error(`The tsParticles version is different from the loaded plugins version. Engine version: ${this.version}. Plugin version: ${t}`);
  }
  dispatchEvent(t, i) {
    v(this, Xr).dispatchEvent(t, i);
  }
  async init() {
    v(this, gc) || (await this.pluginManager.init(), A(this, gc, !0));
  }
  item(t) {
    const i = this.items, a = i[t];
    if (a != null && a.destroyed) {
      i.splice(t, VS);
      return;
    }
    return a;
  }
  async load(t) {
    await this.init();
    let i;
    typeof HTMLElement < "u" && t.element instanceof HTMLElement && (i = t.element);
    const { Container: a } = await Promise.resolve().then(() => f6), r = t.id ?? (i == null ? void 0 : i.id) ?? `tsparticles${Math.floor(Yt() * ZR).toString()}`, { index: u, url: c } = t, f = c ? await E2({ fallback: t.options, url: c, index: u }) : t.options, m = Vn(f, u), { items: p } = this, g = p.findIndex((S) => S.id.description === r), y = new a({
      dispatchCallback: (S, T) => {
        this.dispatchEvent(S, T);
      },
      id: r,
      onDestroy: (S) => {
        if (!S)
          return;
        const T = this.items, C = T.indexOf(y);
        C >= GR && T.splice(C, VS);
      },
      pluginManager: this.pluginManager,
      sourceOptions: m
    });
    if (g >= QR) {
      const S = this.item(g), T = S ? qu : yM;
      S && !S.destroyed && S.destroy(!1), p.splice(g, T, y);
    } else
      p.push(y);
    const b = typeof OffscreenCanvas < "u" && t.element instanceof OffscreenCanvas ? t.element : A2(D2(r, i));
    return y.canvas.loadCanvas(b), await y.start(), y;
  }
  async refresh(t = !0) {
    t && await Promise.all(this.items.map((i) => i.refresh()));
  }
  removeEventListener(t, i) {
    v(this, Xr).removeEventListener(t, i);
  }
}
cd = new WeakMap(), Xr = new WeakMap(), gc = new WeakMap();
function O2() {
  return new R2();
}
var Lr;
(function(n) {
  n.circle = "circle", n.rectangle = "rectangle";
})(Lr || (Lr = {}));
class OM {
  constructor(t, i, a) {
    w(this, "position");
    w(this, "type");
    this.position = {
      x: t,
      y: i
    }, this.type = a;
  }
  _resetPosition(t, i) {
    this.position.x = t, this.position.y = i;
  }
}
class be extends OM {
  constructor(i, a, r) {
    super(i, a, Lr.circle);
    w(this, "radius");
    this.radius = r;
  }
  contains(i) {
    return u2(i, this.position, this.radius);
  }
  intersects(i) {
    const a = this.position, r = i.position, u = this.radius, c = Math.abs(r.x - a.x), f = Math.abs(r.y - a.y);
    if (i instanceof be || i.type === Lr.circle) {
      const m = i, p = u + m.radius, g = Math.hypot(c, f);
      return p > g;
    } else if (i instanceof ni || i.type === Lr.rectangle) {
      const m = i, { width: p, height: g } = m.size;
      return Math.pow(c - p, ra) + Math.pow(f - g, ra) <= u ** ra || c <= u + p && f <= u + g || c <= p || f <= g;
    }
    return !1;
  }
  reset(i, a, r) {
    return this._resetPosition(i, a), this.radius = r, this;
  }
}
class ni extends OM {
  constructor(i, a, r, u) {
    super(i, a, Lr.rectangle);
    w(this, "size");
    this.size = {
      height: u,
      width: r
    };
  }
  contains(i) {
    const a = this.size.width, r = this.size.height, u = this.position;
    return i.x >= u.x && i.x <= u.x + a && i.y >= u.y && i.y <= u.y + r;
  }
  intersects(i) {
    if (i instanceof be)
      return i.intersects(this);
    if (!(i instanceof ni))
      return !1;
    const a = this.size.width, r = this.size.height, u = this.position, c = i.position, f = i.size, m = f.width, p = f.height;
    return c.x < u.x + a && c.x + m > u.x && c.y < u.y + r && c.y + p > u.y;
  }
  reset(i, a, r, u) {
    return this._resetPosition(i, a), this.size.width = r, this.size.height = u, this;
  }
}
var Jn;
(function(n) {
  n.clockwise = "clockwise", n.counterClockwise = "counter-clockwise", n.random = "random";
})(Jn || (Jn = {}));
var Na;
(function(n) {
  n.auto = "auto", n.increase = "increase", n.decrease = "decrease", n.random = "random";
})(Na || (Na = {}));
var sc;
(function(n) {
  n.delete = "delete", n.wait = "wait";
})(sc || (sc = {}));
var he;
(function(n) {
  n.bounce = "bounce", n.none = "none", n.out = "out", n.destroy = "destroy", n.split = "split";
})(he || (he = {}));
var Fg;
(function(n) {
  n.darken = "darken", n.enlighten = "enlighten";
})(Fg || (Fg = {}));
var ko;
(function(n) {
  n.none = "none", n.max = "max", n.min = "min";
})(ko || (ko = {}));
var qS;
(function(n) {
  n.linear = "linear", n.radial = "radial", n.random = "random";
})(qS || (qS = {}));
var ti;
(function(n) {
  n.normal = "normal", n.inside = "inside", n.outside = "outside";
})(ti || (ti = {}));
var _r;
(function(n) {
  n.max = "max", n.min = "min", n.random = "random";
})(_r || (_r = {}));
var le;
(function(n) {
  n.increasing = "increasing", n.decreasing = "decreasing";
})(le || (le = {}));
var Ye;
(function(n) {
  n[n.BackgroundElement = 0] = "BackgroundElement", n[n.BackgroundDraw = 1] = "BackgroundDraw", n[n.BackgroundMask = 2] = "BackgroundMask", n[n.CanvasSetup = 3] = "CanvasSetup", n[n.PluginContent = 4] = "PluginContent", n[n.Particles = 5] = "Particles", n[n.CanvasCleanup = 6] = "CanvasCleanup", n[n.Foreground = 7] = "Foreground";
})(Ye || (Ye = {}));
class ee {
  load(t) {
    gt(t) || this.doLoad(t);
  }
}
function zM(n, ...t) {
  for (const i of t)
    n.load(i);
}
function q(n, t, i) {
  i !== void 0 && (n[t] = i);
}
function Qt(n, t, i) {
  i !== void 0 && (n[t] = Ro(i));
}
function z2(n, t, i) {
  i !== void 0 && n[t].load(i);
}
function GS(n, t, i, a) {
  if (i !== void 0) {
    const r = n;
    r[t] ?? (r[t] = a()), r[t].load(i);
  }
}
function Re(n, t, i, ...a) {
  const r = n;
  r[t] ?? (r[t] = new i());
  const u = r[t];
  for (const c of a)
    u.load(c == null ? void 0 : c[t]);
}
class Ky extends ee {
  constructor() {
    super(...arguments);
    w(this, "count", 0);
    w(this, "decay", 0);
    w(this, "delay", 0);
    w(this, "enable", !1);
    w(this, "speed", 1);
    w(this, "sync", !1);
  }
  doLoad(i) {
    Qt(this, "count", i.count), q(this, "enable", i.enable), Qt(this, "speed", i.speed), Qt(this, "decay", i.decay), Qt(this, "delay", i.delay), q(this, "sync", i.sync);
  }
}
class Iy extends Ky {
  constructor() {
    super(...arguments);
    w(this, "mode", Na.auto);
    w(this, "startValue", _r.random);
  }
  doLoad(i) {
    super.doLoad(i), q(this, "mode", i.mode), q(this, "startValue", i.startValue);
  }
}
class ng extends Ky {
  constructor(i, a) {
    super();
    w(this, "max");
    w(this, "min");
    w(this, "offset", 0);
    w(this, "sync", !0);
    this.min = i, this.max = a;
  }
  doLoad(i) {
    super.doLoad(i), q(this, "max", i.max), q(this, "min", i.min), Qt(this, "offset", i.offset);
  }
}
class k2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "h", new ng($h, yn));
    w(this, "l", new ng(Sd, Co));
    w(this, "s", new ng(Eo, To));
  }
  doLoad(i) {
    this.h.load(i.h), this.s.load(i.s), this.l.load(i.l);
  }
}
class jn extends ee {
  constructor() {
    super(...arguments);
    w(this, "value", "");
  }
  static create(i, a) {
    const r = new jn();
    return r.load(i), a !== void 0 && (Ao(a) || vn(a) ? r.load({ value: a }) : r.load(a)), r;
  }
  doLoad(i) {
    gt(i.value) || (this.value = i.value);
  }
}
class zi extends jn {
  constructor() {
    super(...arguments);
    w(this, "animation", new k2());
  }
  static create(i, a) {
    const r = new zi();
    return r.load(i), a !== void 0 && (Ao(a) || vn(a) ? r.load({ value: a }) : r.load(a)), r;
  }
  doLoad(i) {
    super.doLoad(i);
    const a = i.animation;
    a !== void 0 && (a.enable === void 0 ? this.animation.load(i.animation) : this.animation.h.load(a));
  }
}
class V2 extends ee {
  constructor() {
    super();
    w(this, "color");
    w(this, "draw");
    w(this, "element");
    w(this, "image", "");
    w(this, "opacity", 1);
    w(this, "position", "");
    w(this, "repeat", "");
    w(this, "size", "");
    this.color = new jn(), this.color.value = "";
  }
  doLoad(i) {
    i.color !== void 0 && (this.color = jn.create(this.color, i.color)), q(this, "element", i.element), q(this, "draw", i.draw), q(this, "image", i.image), q(this, "position", i.position), q(this, "repeat", i.repeat), q(this, "size", i.size), q(this, "opacity", i.opacity);
  }
}
class P2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "enable", !0);
    w(this, "zIndex", 0);
  }
  doLoad(i) {
    q(this, "enable", i.enable), q(this, "zIndex", i.zIndex);
  }
}
class L2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "delay", 0.5);
    w(this, "enable", !0);
  }
  doLoad(i) {
    q(this, "delay", i.delay), q(this, "enable", i.enable);
  }
}
class _2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "close", !0);
    w(this, "options", {});
    w(this, "type", []);
  }
  doLoad(i) {
    const a = i.options;
    if (a !== void 0)
      for (const r in a) {
        const u = a[r];
        u && (this.options[r] = bn(this.options[r] ?? {}, u));
      }
    q(this, "close", i.close), q(this, "type", i.type);
  }
}
class kM extends ee {
  constructor() {
    super(...arguments);
    w(this, "color");
    w(this, "enable", !0);
    w(this, "opacity", 1);
  }
  doLoad(i) {
    i.color !== void 0 && (this.color = zi.create(this.color, i.color)), q(this, "enable", i.enable), Qt(this, "opacity", i.opacity);
  }
}
class B2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "offset", 0);
    w(this, "value", 90);
  }
  doLoad(i) {
    Qt(this, "offset", i.offset), Qt(this, "value", i.value);
  }
}
class N2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "mode", Wh.percent);
    w(this, "radius", 0);
    w(this, "x", 50);
    w(this, "y", 50);
  }
  doLoad(i) {
    q(this, "x", i.x), q(this, "y", i.y), q(this, "mode", i.mode), q(this, "radius", i.radius);
  }
}
class U2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "acceleration", 9.81);
    w(this, "enable", !1);
    w(this, "inverse", !1);
    w(this, "maxSpeed", 50);
  }
  doLoad(i) {
    Qt(this, "acceleration", i.acceleration), q(this, "enable", i.enable), q(this, "inverse", i.inverse), Qt(this, "maxSpeed", i.maxSpeed);
  }
}
class Bo extends ee {
  constructor() {
    super(...arguments);
    w(this, "value", 0);
  }
  doLoad(i) {
    gt(i.value) || (this.value = Ro(i.value));
  }
}
class j2 extends Bo {
  constructor() {
    super(...arguments);
    w(this, "animation", new Ky());
  }
  doLoad(i) {
    super.doLoad(i), z2(this, "animation", i.animation);
  }
}
class VM extends j2 {
  constructor() {
    super(...arguments);
    w(this, "animation", new Iy());
  }
}
class H2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "clamp", !0);
    w(this, "delay", new Bo());
    w(this, "enable", !1);
    w(this, "generator");
    w(this, "options", {});
  }
  doLoad(i) {
    q(this, "clamp", i.clamp), this.delay.load(i.delay), q(this, "enable", i.enable), this.generator = i.generator, i.options && (this.options = bn(this.options, i.options));
  }
}
class q2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "bottom");
    w(this, "default", he.out);
    w(this, "left");
    w(this, "right");
    w(this, "top");
  }
  doLoad(i) {
    i.default !== void 0 && (this.default = i.default), this.bottom = i.bottom ?? i.default, this.left = i.left ?? i.default, this.right = i.right ?? i.default, this.top = i.top ?? i.default;
  }
}
class G2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "acceleration", 0);
    w(this, "enable", !1);
    w(this, "position");
  }
  doLoad(i) {
    Qt(this, "acceleration", i.acceleration), q(this, "enable", i.enable), i.position && (this.position = bn({}, i.position));
  }
}
class Y2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "angle", new B2());
    w(this, "center", new N2());
    w(this, "decay", 0);
    w(this, "direction", Pe.none);
    w(this, "distance", {});
    w(this, "drift", 0);
    w(this, "enable", !1);
    w(this, "gravity", new U2());
    w(this, "outModes", new q2());
    w(this, "path", new H2());
    w(this, "random", !1);
    w(this, "size", !1);
    w(this, "speed", 2);
    w(this, "spin", new G2());
    w(this, "straight", !1);
    w(this, "vibrate", !1);
    w(this, "warp", !1);
  }
  doLoad(i) {
    this.angle.load(Do(i.angle) ? { value: i.angle } : i.angle), this.center.load(i.center), Qt(this, "decay", i.decay), q(this, "direction", i.direction), i.distance !== void 0 && (this.distance = Do(i.distance) ? {
      horizontal: i.distance,
      vertical: i.distance
    } : { ...i.distance }), Qt(this, "drift", i.drift), q(this, "enable", i.enable), this.gravity.load(i.gravity);
    const a = i.outModes;
    a !== void 0 && ($u(a) ? this.outModes.load(a) : this.outModes.load({
      default: a
    })), this.path.load(i.path), q(this, "random", i.random), q(this, "size", i.size), Qt(this, "speed", i.speed), this.spin.load(i.spin), q(this, "straight", i.straight), q(this, "vibrate", i.vibrate), q(this, "warp", i.warp);
  }
}
class X2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "color");
    w(this, "opacity");
    w(this, "width", 0);
  }
  doLoad(i) {
    i.color !== void 0 && (this.color = zi.create(this.color, i.color)), Qt(this, "width", i.width), Qt(this, "opacity", i.opacity);
  }
}
class ig extends ee {
  constructor() {
    super(...arguments);
    w(this, "color");
    w(this, "fill");
    w(this, "stroke");
  }
  doLoad(i) {
    i.color !== void 0 && (this.color = zi.create(this.color, i.color)), GS(this, "fill", i.fill, () => new kM()), GS(this, "stroke", i.stroke, () => new X2());
  }
}
class YS extends Bo {
  constructor() {
    super(...arguments);
    w(this, "value", 1);
  }
}
class PM extends ee {
  constructor() {
    super(...arguments);
    w(this, "horizontal", new YS());
    w(this, "vertical", new YS());
  }
  doLoad(i) {
    this.horizontal.load(i.horizontal), this.vertical.load(i.vertical);
  }
}
class F2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "enable", !1);
    w(this, "height", 1080);
    w(this, "width", 1920);
  }
  doLoad(i) {
    q(this, "enable", i.enable), q(this, "width", i.width), q(this, "height", i.height);
  }
}
class Z2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "mode", sc.delete);
    w(this, "value", 0);
  }
  doLoad(i) {
    q(this, "mode", i.mode), q(this, "value", i.value);
  }
}
class Q2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "density", new F2());
    w(this, "limit", new Z2());
    w(this, "value", 0);
  }
  doLoad(i) {
    this.density.load(i.density), this.limit.load(i.limit), q(this, "value", i.value);
  }
}
class K2 extends ee {
  constructor() {
    super(...arguments);
    w(this, "close", !0);
    w(this, "options", {});
    w(this, "type", "circle");
  }
  doLoad(i) {
    const a = i.options;
    if (a !== void 0)
      for (const r in a) {
        const u = a[r];
        u && (this.options[r] = bn(this.options[r] ?? {}, u));
      }
    q(this, "close", i.close), q(this, "type", i.type);
  }
}
class I2 extends Bo {
  constructor() {
    super(...arguments);
    w(this, "opacityRate", 1);
    w(this, "sizeRate", 1);
    w(this, "velocityRate", 1);
  }
  doLoad(i) {
    super.doLoad(i), q(this, "opacityRate", i.opacityRate), q(this, "sizeRate", i.sizeRate), q(this, "velocityRate", i.velocityRate);
  }
}
var Ga, Ya, fd, LM;
class $2 extends ee {
  constructor(i, a) {
    super();
    k(this, fd);
    w(this, "bounce", new PM());
    w(this, "effect", new _2());
    w(this, "groups", {});
    w(this, "move", new Y2());
    w(this, "number", new Q2());
    w(this, "paint");
    w(this, "palette");
    w(this, "reduceDuplicates", !1);
    w(this, "shape", new K2());
    w(this, "zIndex", new I2());
    k(this, Ga);
    k(this, Ya);
    A(this, Ya, i), A(this, Ga, a), this.paint = new ig(), this.paint.color = new zi(), this.paint.color.value = "#fff", this.paint.fill = new kM(), this.paint.fill.enable = !0;
  }
  doLoad(i) {
    if (i.palette && (this.palette = i.palette, L(this, fd, LM).call(this, this.palette)), i.groups !== void 0)
      for (const r of Object.keys(i.groups)) {
        if (!(r in i.groups))
          continue;
        const u = i.groups[r];
        u !== void 0 && (this.groups[r] = bn(this.groups[r] ?? {}, u));
      }
    i.reduceDuplicates !== void 0 && (this.reduceDuplicates = i.reduceDuplicates), this.bounce.load(i.bounce), this.effect.load(i.effect), this.move.load(i.move), this.number.load(i.number);
    const a = i.paint;
    if (a && (vn(a) ? this.paint = Gn(a, (r) => {
      const u = new ig();
      return u.load(r), u;
    }) : vn(this.paint) ? (this.paint = new ig(), this.paint.load(a)) : this.paint.load(a)), this.shape.load(i.shape), this.zIndex.load(i.zIndex), v(this, Ga)) {
      for (const u of v(this, Ya).plugins)
        u.loadParticlesOptions && u.loadParticlesOptions(v(this, Ga), this, i);
      const r = v(this, Ya).updaters.get(v(this, Ga));
      if (r)
        for (const u of r)
          u.loadOptions && u.loadOptions(this, i);
    }
  }
}
Ga = new WeakMap(), Ya = new WeakMap(), fd = new WeakSet(), LM = function(i) {
  const a = v(this, Ya).getPalette(i);
  if (!a)
    return;
  const r = a.colors, u = 0, c = 1, f = 0, m = {}, p = vn(r) ? r : [r], g = p.flatMap((b) => {
    const S = b.fill, T = b.stroke, C = S ? {
      color: {
        value: S.value
      },
      enable: S.enable,
      opacity: S.opacity
    } : void 0;
    return T ? [
      {
        fill: C,
        stroke: {
          color: {
            value: T.value
          },
          opacity: T.opacity,
          width: T.width || u
        }
      }
    ] : [
      {
        fill: C
      }
    ];
  }), y = g.length > c ? g : g[f] ?? m;
  this.load({
    paint: y,
    blend: {
      enable: !0,
      mode: a.blendMode
    }
  });
};
function $y(n, t, ...i) {
  const a = new $2(n, t);
  return zM(a, ...i), a;
}
var Fr, Rs, kl, _M, BM;
class W2 extends ee {
  constructor(i, a) {
    super();
    k(this, kl);
    w(this, "autoPlay", !0);
    w(this, "background");
    w(this, "clear", !0);
    w(this, "defaultThemes", {});
    w(this, "delay", 0);
    w(this, "detectRetina", !0);
    w(this, "duration", 0);
    w(this, "fpsLimit", 120);
    w(this, "fullScreen");
    w(this, "hdr", !0);
    w(this, "key");
    w(this, "name");
    w(this, "palette");
    w(this, "particles");
    w(this, "pauseOnBlur", !0);
    w(this, "pauseOnOutsideViewport", !0);
    w(this, "preset");
    w(this, "resize");
    w(this, "smooth", !1);
    w(this, "style", {});
    w(this, "zLayers", 100);
    k(this, Fr);
    k(this, Rs);
    A(this, Rs, i), A(this, Fr, a), this.background = new V2(), this.fullScreen = new P2(), this.particles = $y(v(this, Rs), v(this, Fr)), this.resize = new L2();
  }
  doLoad(i) {
    i.preset !== void 0 && (this.preset = i.preset, Gn(this.preset, (r) => {
      L(this, kl, BM).call(this, r);
    })), i.palette !== void 0 && (this.palette = i.palette, L(this, kl, _M).call(this, this.palette)), q(this, "autoPlay", i.autoPlay), q(this, "clear", i.clear), q(this, "key", i.key), q(this, "name", i.name), Qt(this, "delay", i.delay), q(this, "detectRetina", i.detectRetina), Qt(this, "duration", i.duration), q(this, "fpsLimit", i.fpsLimit), q(this, "hdr", i.hdr), q(this, "pauseOnBlur", i.pauseOnBlur), q(this, "pauseOnOutsideViewport", i.pauseOnOutsideViewport), q(this, "zLayers", i.zLayers), this.background.load(i.background);
    const a = i.fullScreen;
    MM(a) ? this.fullScreen.enable = a : this.fullScreen.load(a), this.particles.load(i.particles), this.resize.load(i.resize), this.style = bn(this.style, i.style), q(this, "smooth", i.smooth), v(this, Rs).plugins.forEach((r) => {
      r.loadOptions(v(this, Fr), this, i);
    });
  }
}
Fr = new WeakMap(), Rs = new WeakMap(), kl = new WeakSet(), _M = function(i) {
  const a = v(this, Rs).getPalette(i);
  a && this.load({
    background: {
      color: a.background
    },
    blend: {
      enable: !0,
      mode: a.blendMode
    },
    particles: {
      palette: i
    }
  });
}, BM = function(i) {
  this.load(v(this, Rs).getPreset(i));
};
const wh = /* @__PURE__ */ new Map(), J2 = 2e3, tO = 2, eO = 2, nO = 4, iO = 4, NM = 203, sO = NM / bM;
function UM(n, t) {
  let i = wh.get(n);
  return i || (i = t(), wh.size > J2 && wh.clear(), wh.set(n, i)), i;
}
function aO(n, t) {
  if (t) {
    for (const i of n.colorManagers.values())
      if (i.accepts(t))
        return i.parseString(t);
  }
}
function Vo(n, t, i, a = !0) {
  if (!t)
    return;
  const r = Ao(t) ? { value: t } : t;
  if (Ao(r.value))
    return jM(n, r.value, i, a);
  if (vn(r.value)) {
    const u = Md(r.value, i, a);
    return u ? Vo(n, {
      value: u
    }) : void 0;
  }
  for (const u of n.colorManagers.values()) {
    const c = u.handleRangeColor(r);
    if (c)
      return c;
  }
}
function jM(n, t, i, a = !0) {
  if (!t)
    return;
  const r = Ao(t) ? { value: t } : t;
  if (Ao(r.value))
    return r.value === Dl ? qM() : oO(n, r.value);
  if (vn(r.value)) {
    const u = Md(r.value, i, a);
    return u ? jM(n, {
      value: u
    }) : void 0;
  }
  for (const u of n.colorManagers.values()) {
    const c = u.handleColor(r);
    if (c)
      return c;
  }
}
function ac(n, t, i, a = !0) {
  const r = Vo(n, t, i, a);
  return r ? HM(r) : void 0;
}
function HM(n) {
  const t = n.r / fe, i = n.g / fe, a = n.b / fe, r = Math.max(t, i, a), u = Math.min(t, i, a), c = {
    h: $h,
    l: (r + u) * bt,
    s: Eo
  };
  return r !== u && (c.s = c.l < bt ? (r - u) / (r + u) : (r - u) / (Bt - r - u), t === r ? c.h = (i - a) / (r - u) : i === r ? c.h = Bt + (a - t) / (r - u) : c.h = Bt * Bt + (t - i) / (r - u)), c.l *= Co, c.s *= To, c.h *= UR, c.h < $h && (c.h += yn), c.h >= yn && (c.h -= yn), c;
}
function oO(n, t) {
  return aO(n, t);
}
function Br(n, t, i) {
  if (i < 0 && i++, i > 1 && i--, i * Jp < 1)
    return n + (t - n) * Jp * i;
  if (i * Bt < 1)
    return t;
  if (i * ic < 1 * Bt) {
    const u = Bt / ic;
    return n + (t - n) * (u - i) * Jp;
  }
  return n;
}
function Rl(n) {
  const t = (n.h % yn + yn) % yn, i = Math.max(Eo, Math.min(To, n.s)), a = Math.max(Sd, Math.min(Co, n.l)), r = t / yn, u = i / To, c = a / Co;
  if (i === Eo) {
    const S = Math.round(c * fe);
    return { r: S, g: S, b: S };
  }
  const f = c < bt ? c * (xM + u) : c + u - c * u, m = Bt * c - f, p = SM / ic, g = Math.min(fe, fe * Br(m, f, r + p)), y = Math.min(fe, fe * Br(m, f, r)), b = Math.min(fe, fe * Br(m, f, r - p));
  return { r: Math.round(g), g: Math.round(y), b: Math.round(b) };
}
function rO(n) {
  const t = (n.h % yn + yn) % yn, i = Math.max(Eo, Math.min(To, n.s)), a = Math.max(Sd, Math.min(Co, n.l)), r = t / yn, u = i / To, c = a / Co;
  if (i === Eo) {
    const S = c * fe;
    return { r: S, g: S, b: S };
  }
  const f = c < bt ? c * (xM + u) : c + u - c * u, m = Bt * c - f, p = SM / ic, g = Math.min(fe, fe * Br(m, f, r + p)), y = Math.min(fe, fe * Br(m, f, r)), b = Math.min(fe, fe * Br(m, f, r - p));
  return { r: g, g: y, b };
}
function lO(n) {
  const t = Rl(n);
  return {
    a: n.a,
    b: t.b,
    g: t.g,
    r: t.r
  };
}
function qM(n, t) {
  const i = t2, a = fe + De, r = () => Math.floor(CM(i, a));
  return {
    b: r(),
    g: r(),
    r: r()
  };
}
function Qc(n, t, i) {
  const a = t ? nO : tO, r = i ?? Di, u = `rgb-${n.r.toFixed(a)}-${n.g.toFixed(a)}-${n.b.toFixed(a)}-${t ? "hdr" : "sdr"}-${r.toString()}`;
  return UM(u, () => t ? uO(n, i) : cO(n, i));
}
function uO(n, t, i = bM) {
  const a = i / NM;
  return `color(display-p3 ${(n.r / fe * a).toString()} ${(n.g / fe * a).toString()} ${(n.b / fe * a).toString()} / ${(t ?? Di).toString()})`;
}
function cO(n, t) {
  return `rgba(${n.r.toString()}, ${n.g.toString()}, ${n.b.toString()}, ${(t ?? Di).toString()})`;
}
function oc(n, t, i) {
  const a = t ? iO : eO, r = i ?? Di, u = `hsl-${n.h.toFixed(a)}-${n.s.toFixed(a)}-${n.l.toFixed(a)}-${t ? "hdr" : "sdr"}-${r.toString()}`;
  return UM(u, () => t ? Qc(rO(n), !0, i) : `hsla(${n.h.toString()}, ${n.s.toString()}%, ${n.l.toString()}%, ${r.toString()})`);
}
function Wy(n, t, i, a) {
  let r = n, u = t;
  return "r" in r || (r = Rl(n)), "r" in u || (u = Rl(t)), {
    b: tg(r.b, u.b, i, a),
    g: tg(r.g, u.g, i, a),
    r: tg(r.r, u.r, i, a)
  };
}
function Jy(n, t, i) {
  if (i === Dl)
    return qM();
  if (i === Nh) {
    const a = n.getFillColor() ?? n.getStrokeColor(), r = (t == null ? void 0 : t.getFillColor()) ?? (t == null ? void 0 : t.getStrokeColor());
    if (a && r && t)
      return Wy(a, r, n.getRadius(), t.getRadius());
    {
      const u = a ?? r;
      if (u)
        return Rl(u);
    }
  } else
    return i;
}
function GM(n, t, i, a) {
  const r = Ao(t) ? t : t.value;
  return r === Dl ? a ? Vo(n, {
    value: r
  }) : i ? Dl : Nh : r === Nh ? Nh : Vo(n, {
    value: r
  });
}
function XS(n) {
  return n === void 0 ? void 0 : {
    h: n.h.value,
    s: n.s.value,
    l: n.l.value
  };
}
function FS(n, t, i) {
  const a = {
    h: {
      enable: !1,
      value: n.h,
      min: $h,
      max: yn
    },
    s: {
      enable: !1,
      value: n.s,
      min: Eo,
      max: To
    },
    l: {
      enable: !1,
      value: n.l,
      min: Sd,
      max: Co
    }
  };
  return t && (sg(a.h, t.h, i), sg(a.s, t.s, i), sg(a.l, t.l, i)), a;
}
function sg(n, t, i) {
  n.enable = t.enable, n.min = t.min, n.max = t.max, n.enable ? (n.velocity = ht(t.speed) / sa * i, n.decay = vM - ht(t.decay), n.status = le.increasing, n.loops = n2, n.maxLoops = ht(t.count), n.time = i2, n.delayTime = ht(t.delay) * Ae, t.sync || (n.velocity *= Yt(), n.value *= Yt()), n.initialValue = n.value, n.offset = Ro(t.offset)) : n.velocity = e2;
}
function ag(n, t, i, a) {
  if (!n.enable || (n.maxLoops ?? 0) > 0 && (n.loops ?? 0) > (n.maxLoops ?? 0) || (n.time ?? (n.time = 0), (n.delayTime ?? 0) > 0 && n.time < (n.delayTime ?? 0) && (n.time += i.value), (n.delayTime ?? 0) > 0 && n.time < (n.delayTime ?? 0)))
    return;
  const g = n.offset ? Oi(n.offset) : 0, y = ((n.velocity ?? 0) * i.factor + g * 3.6) * (a ? sO : 1), b = n.decay ?? 1, S = n.max, T = n.min;
  !t || n.status === le.increasing ? (n.value += y, n.value > S && (n.loops ?? (n.loops = 0), n.loops++, t ? n.status = le.decreasing : n.value -= S)) : (n.value -= y, n.value < T && (n.loops ?? (n.loops = 0), n.loops++, n.status = le.increasing)), n.velocity && b !== 1 && (n.velocity *= b), n.value = Nn(n.value, T, S);
}
function ZS(n, t, i) {
  if (!n)
    return;
  const { h: a, s: r, l: u } = n;
  ag(a, !1, t, i), ag(r, !0, t, i), ag(u, !0, t, i);
}
function fO(n, t, i) {
  return {
    h: n.h,
    s: n.s,
    l: n.l + (t === Fg.darken ? -BS : BS) * i
  };
}
const YM = O2();
class QS {
  constructor() {
    w(this, "enable", !1);
    w(this, "mode", "destination-out");
  }
  load(t) {
    gt(t) || (q(this, "mode", t.mode), q(this, "enable", t.enable));
  }
}
class hO {
  constructor() {
    w(this, "id", "blend");
  }
  async getPlugin(t) {
    const { BlendPluginInstance: i } = await Promise.resolve().then(() => d6);
    return new i(t);
  }
  loadOptions(t, i, a) {
    if (!this.needsPlugin(i) && !this.needsPlugin(a))
      return;
    let r = i.blend;
    r != null && r.load || (i.blend = r = new QS()), r.load(a == null ? void 0 : a.blend);
  }
  loadParticlesOptions(t, i, a) {
    i.blend ?? (i.blend = new QS()), i.blend.load(a == null ? void 0 : a.blend);
  }
  needsPlugin(t) {
    var i, a, r;
    return !!((i = t == null ? void 0 : t.blend) != null && i.enable) || !!((r = (a = t == null ? void 0 : t.particles) == null ? void 0 : a.blend) != null && r.enable);
  }
}
async function dO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addPlugin(new hO());
  });
}
const mO = 0;
function pO(n) {
  const { context: t, particle: i, radius: a } = n;
  i.circleRange ?? (i.circleRange = { min: mO, max: oa });
  const r = i.circleRange;
  t.arc(Dt.x, Dt.y, a, r.min, r.max, !1);
}
const gO = 12, yO = 360, KS = 0;
class vO {
  draw(t) {
    pO(t);
  }
  getSidesCount() {
    return gO;
  }
  particleInit(t, i) {
    const a = i.shapeData, r = (a == null ? void 0 : a.angle) ?? {
      max: yO,
      min: KS
    };
    i.circleRange = $u(r) ? { min: So(r.min), max: So(r.max) } : {
      min: KS,
      max: So(r)
    };
  }
}
async function bO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(["circle"], () => Promise.resolve(new vO()));
  });
}
var La;
(function(n) {
  n[n.r = 1] = "r", n[n.g = 2] = "g", n[n.b = 3] = "b", n[n.a = 4] = "a";
})(La || (La = {}));
const xO = /^#?([a-f\d])([a-f\d])([a-f\d])([a-f\d])?$/i, SO = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})?$/i, Mh = 16, wO = 1, MO = 255;
var Zr, Uh;
class TO {
  constructor() {
    k(this, Zr);
  }
  accepts(t) {
    return t.startsWith("#");
  }
  handleColor(t) {
    return L(this, Zr, Uh).call(this, t.value);
  }
  handleRangeColor(t) {
    return L(this, Zr, Uh).call(this, t.value);
  }
  parseString(t) {
    return L(this, Zr, Uh).call(this, t);
  }
}
Zr = new WeakSet(), Uh = function(t) {
  if (typeof t != "string" || !this.accepts(t))
    return;
  const i = t.replace(xO, (r, u, c, f, m) => u + u + c + c + f + f + (m === void 0 ? "" : m + m)), a = SO.exec(i);
  return a ? {
    a: a[La.a] ? Number.parseInt(a[La.a], Mh) / MO : wO,
    b: Number.parseInt(a[La.b] ?? "0", Mh),
    g: Number.parseInt(a[La.g] ?? "0", Mh),
    r: Number.parseInt(a[La.r] ?? "0", Mh)
  } : void 0;
};
async function CO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addColorManager("hex", new TO());
  });
}
var Or;
(function(n) {
  n[n.h = 1] = "h", n[n.s = 2] = "s", n[n.l = 3] = "l", n[n.a = 5] = "a";
})(Or || (Or = {}));
const EO = /hsla?\(\s*(\d+)\s*[\s,]\s*(\d+)%\s*[\s,]\s*(\d+)%\s*([\s,]\s*(0|1|0?\.\d+|(\d{1,3})%)\s*)?\)/i;
class AO {
  accepts(t) {
    return t.startsWith("hsl");
  }
  handleColor(t) {
    const i = t.value, a = i.hsl ?? t.value;
    if (!(!("h" in a) || !("s" in a) || !("l" in a)))
      return Rl(a);
  }
  handleRangeColor(t) {
    const i = t.value, a = i.hsl ?? t.value;
    if (!(!("h" in a) || !("s" in a) || !("l" in a)))
      return Rl({
        h: ht(a.h),
        l: ht(a.l),
        s: ht(a.s)
      });
  }
  parseString(t) {
    if (!this.accepts(t))
      return;
    const i = EO.exec(t), a = 4, r = 1, u = 10;
    return i ? lO({
      a: i.length > a ? AM(i[Or.a]) : r,
      h: Number.parseInt(i[Or.h] ?? "0", u),
      l: Number.parseInt(i[Or.l] ?? "0", u),
      s: Number.parseInt(i[Or.s] ?? "0", u)
    }) : void 0;
  }
}
async function DO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addColorManager("hsl", new AO());
  });
}
var yc;
class RO {
  constructor(t) {
    w(this, "id", "move");
    k(this, yc);
    A(this, yc, t);
  }
  async getPlugin(t) {
    const { MovePluginInstance: i } = await Promise.resolve().then(() => E6);
    return new i(v(this, yc), t);
  }
  loadOptions() {
  }
  needsPlugin() {
    return !0;
  }
}
yc = new WeakMap();
async function OO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var r;
    const i = t, a = i.pluginManager;
    (r = a.initializers).pathGenerators ?? (r.pathGenerators = /* @__PURE__ */ new Map()), a.pathGenerators ?? (a.pathGenerators = /* @__PURE__ */ new Map()), a.addPathGenerator = (u, c) => {
      var f;
      (f = a.initializers).pathGenerators ?? (f.pathGenerators = /* @__PURE__ */ new Map()), a.initializers.pathGenerators.set(u, c);
    }, a.getPathGenerators = async (u, c = !1) => {
      var f;
      return (f = a.initializers).pathGenerators ?? (f.pathGenerators = /* @__PURE__ */ new Map()), a.pathGenerators ?? (a.pathGenerators = /* @__PURE__ */ new Map()), Yg(u, a.pathGenerators, a.initializers.pathGenerators, c);
    }, t.pluginManager.addPlugin(new RO(t.pluginManager));
  });
}
function zO(n, t, i, a, r) {
  switch (t) {
    case ko.max:
      i >= r && n.destroy();
      break;
    case ko.min:
      i <= a && n.destroy();
      break;
  }
}
function XM(n, t) {
  const i = n.value, a = n.animation, r = {
    delayTime: ht(a.delay) * Ae,
    enable: a.enable,
    value: ht(n.value) * t,
    max: wd(i) * t,
    min: Qy(i) * t,
    loops: 0,
    maxLoops: ht(a.count),
    time: 0
  }, u = 1;
  if (a.enable) {
    switch (r.decay = u - ht(a.decay), a.mode) {
      case Na.increase:
        r.status = le.increasing;
        break;
      case Na.decrease:
        r.status = le.decreasing;
        break;
      case Na.random:
        r.status = Yt() >= bt ? le.increasing : le.decreasing;
        break;
    }
    const c = a.mode === Na.auto;
    switch (a.startValue) {
      case _r.min:
        r.value = r.min, c && (r.status = le.increasing);
        break;
      case _r.max:
        r.value = r.max, c && (r.status = le.decreasing);
        break;
      case _r.random:
      default:
        r.value = Oi(r), c && (r.status = Yt() >= bt ? le.increasing : le.decreasing);
        break;
    }
  }
  return r.initialValue = r.value, r;
}
function tv(n, t, i, a, r) {
  if (n.destroyed || !t.enable || (t.maxLoops ?? 0) > 0 && (t.loops ?? 0) > (t.maxLoops ?? 0))
    return;
  const g = (t.velocity ?? 0) * r.factor, y = t.min, b = t.max, S = t.decay ?? 1;
  t.time ?? (t.time = 0);
  const T = t.delayTime ?? 0;
  if (!(T > 0 && t.time < T && (t.time += r.value, t.time < T))) {
    switch (t.status) {
      case le.increasing:
        t.value += g;
        break;
      case le.decreasing:
        t.value -= g;
        break;
    }
    switch (t.velocity && S !== 1 && (t.velocity *= S), t.status) {
      case le.increasing:
        t.value >= b && (i ? t.status = le.decreasing : t.value -= b, t.loops ?? (t.loops = 0), t.loops++);
        break;
      case le.decreasing:
        t.value <= y && (i ? t.status = le.increasing : t.value += b, t.loops ?? (t.loops = 0), t.loops++);
        break;
    }
    zO(n, a, t.value, y, b), n.destroyed || (t.value = Nn(t.value, y, b));
  }
}
class kO extends Iy {
  constructor() {
    super(...arguments);
    w(this, "destroy", ko.none);
  }
  load(i) {
    super.load(i), !gt(i) && q(this, "destroy", i.destroy);
  }
}
class VO extends VM {
  constructor() {
    super(...arguments);
    w(this, "animation", new kO());
    w(this, "value", 1);
  }
  load(i) {
    if (gt(i))
      return;
    super.load(i);
    const a = i.animation;
    a !== void 0 && this.animation.load(a);
  }
}
var vc;
class PO {
  constructor(t) {
    k(this, vc);
    A(this, vc, t);
  }
  init(t) {
    const i = t.options.opacity, a = 1;
    if (!i)
      return;
    t.opacity = XM(i, a);
    const r = i.animation;
    r.enable && (t.opacity.velocity = ht(r.speed) / sa * v(this, vc).retina.reduceFactor, r.sync || (t.opacity.velocity *= Yt()));
  }
  isEnabled(t) {
    return !t.destroyed && !t.spawning && !!t.opacity && t.opacity.enable && ((t.opacity.maxLoops ?? 0) <= 0 || (t.opacity.maxLoops ?? 0) > 0 && (t.opacity.loops ?? 0) < (t.opacity.maxLoops ?? 0));
  }
  loadOptions(t, ...i) {
    Re(t, "opacity", VO, ...i);
  }
  reset(t) {
    t.opacity && (t.opacity.time = 0, t.opacity.loops = 0);
  }
  update(t, i) {
    !this.isEnabled(t) || !t.opacity || !t.options.opacity || tv(t, t.opacity, !0, t.options.opacity.animation.destroy, i);
  }
}
vc = new WeakMap();
async function LO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addParticleUpdater("opacity", (i) => Promise.resolve(new PO(i)));
  });
}
const FM = 0;
function _O(n) {
  if (n.outMode !== he.bounce && n.outMode !== he.split || n.direction !== Mt.left && n.direction !== Mt.right)
    return;
  n.bounds.right < FM && n.direction === Mt.left ? n.particle.position.x = n.size + n.offset.x : n.bounds.left > n.canvasSize.width && n.direction === Mt.right && (n.particle.position.x = n.canvasSize.width - n.size - n.offset.x);
  const t = n.particle.velocity.x;
  let i = !1;
  if (n.outOfCanvas && (n.direction === Mt.right && t > Wt || n.direction === Mt.left && t < Wt)) {
    const r = ht(n.particle.options.bounce.horizontal.value);
    n.particle.velocity.x *= -r, i = !0;
  }
  if (!i)
    return;
  const a = n.offset.x + n.size;
  n.outOfCanvas && n.direction === Mt.right ? n.particle.position.x = n.canvasSize.width - a : n.outOfCanvas && n.direction === Mt.left && (n.particle.position.x = a), n.outMode === he.split && n.particle.destroy();
}
function BO(n) {
  if (n.outMode !== he.bounce && n.outMode !== he.split || n.direction !== Mt.bottom && n.direction !== Mt.top)
    return;
  n.bounds.bottom < FM && n.direction === Mt.top ? n.particle.position.y = n.size + n.offset.y : n.bounds.top > n.canvasSize.height && n.direction === Mt.bottom && (n.particle.position.y = n.canvasSize.height - n.size - n.offset.y);
  const t = n.particle.velocity.y;
  let i = !1;
  if (n.outOfCanvas && (n.direction === Mt.bottom && t > Wt || n.direction === Mt.top && t < Wt)) {
    const r = ht(n.particle.options.bounce.vertical.value);
    n.particle.velocity.y *= -r, i = !0;
  }
  if (!i)
    return;
  const a = n.offset.y + n.size;
  n.outOfCanvas && n.direction === Mt.bottom ? n.particle.position.y = n.canvasSize.height - a : n.outOfCanvas && n.direction === Mt.top && (n.particle.position.y = a), n.outMode === he.split && n.particle.destroy();
}
var bc, xc;
class NO {
  constructor(t) {
    w(this, "modes");
    k(this, bc);
    k(this, xc);
    A(this, bc, t), this.modes = [
      he.bounce,
      he.split
    ], A(this, xc, t.plugins.filter((i) => i.particleBounce !== void 0));
  }
  update(t, i, a, r) {
    var S;
    if (!this.modes.includes(r))
      return;
    const u = v(this, bc);
    let c = !1;
    for (const T of v(this, xc))
      if (c = ((S = T.particleBounce) == null ? void 0 : S.call(T, t, a, i)) ?? !1, c)
        break;
    if (c)
      return;
    const f = t.getPosition(), m = t.offset, p = t.getRadius(), g = Zc(f, p), y = u.canvas.size, b = !t.isInsideCanvasForOutMode(r, i);
    _O({ particle: t, outMode: r, direction: i, bounds: g, canvasSize: y, offset: m, outOfCanvas: b, size: p }), BO({ particle: t, outMode: r, direction: i, bounds: g, canvasSize: y, offset: m, outOfCanvas: b, size: p });
  }
}
bc = new WeakMap(), xc = new WeakMap();
class UO {
  constructor(t) {
    w(this, "modes");
    this.modes = [he.destroy];
  }
  update(t, i, a, r) {
    if (this.modes.includes(r)) {
      switch (t.outType) {
        case ti.normal:
        case ti.outside:
          if (t.isInsideCanvasForOutMode(r, i))
            return;
          break;
        case ti.inside: {
          const { dx: u, dy: c } = _n(t.position, t.moveCenter), { x: f, y: m } = t.velocity;
          if (f < Wt && u > t.moveCenter.radius || m < Wt && c > t.moveCenter.radius || f >= Wt && u < -t.moveCenter.radius || m >= Wt && c < -t.moveCenter.radius)
            return;
          break;
        }
      }
      t.destroy(!0);
    }
  }
}
var Sc;
class jO {
  constructor(t) {
    w(this, "modes");
    k(this, Sc);
    A(this, Sc, t), this.modes = [he.none];
  }
  update(t, i, a, r) {
    if (!this.modes.includes(r) || ((t.options.move.distance.horizontal && (i === Mt.left || i === Mt.right)) ?? (t.options.move.distance.vertical && (i === Mt.top || i === Mt.bottom))))
      return;
    const u = t.options.move.gravity, c = v(this, Sc), f = c.canvas.size, m = t.getRadius();
    if (u.enable) {
      const p = t.position;
      (!u.inverse && p.y > f.height + m && i === Mt.bottom || u.inverse && p.y < -m && i === Mt.top) && t.destroy();
    } else {
      if (t.velocity.y > Wt && t.position.y <= f.height + m || t.velocity.y < Wt && t.position.y >= -m || t.velocity.x > Wt && t.position.x <= f.width + m || t.velocity.x < Wt && t.position.x >= -m)
        return;
      g2(t.position, c.canvas.size, Dt, m, i) || t.destroy();
    }
  }
}
Sc = new WeakMap();
const _u = Qe.origin;
var wc;
class HO {
  constructor(t) {
    w(this, "modes");
    k(this, wc);
    A(this, wc, t), this.modes = [he.out];
  }
  update(t, i, a, r) {
    if (!this.modes.includes(r))
      return;
    const u = v(this, wc);
    switch (t.outType) {
      case ti.inside: {
        const { x: c, y: f } = t.velocity;
        _u.setTo(Dt), _u.length = t.moveCenter.radius, _u.angle = t.velocity.angle + Math.PI, _u.addTo(t.moveCenter);
        const { dx: m, dy: p } = _n(t.position, _u);
        if (c <= Wt && m >= xh || f <= Wt && p >= xh || c >= Wt && m <= xh || f >= Wt && p <= xh)
          return;
        t.position.x = Math.floor(Oi({
          min: 0,
          max: u.canvas.size.width
        })), t.position.y = Math.floor(Oi({
          min: 0,
          max: u.canvas.size.height
        }));
        const { dx: g, dy: y } = _n(t.position, t.moveCenter);
        t.direction = Math.atan2(-y, -g), t.velocity.angle = t.direction, t.justWarped = !0;
        break;
      }
      default: {
        if (t.isInsideCanvasForOutMode(r, i))
          return;
        switch (t.outType) {
          case ti.outside: {
            t.position.x = Math.floor(Oi({
              min: -t.moveCenter.radius,
              max: t.moveCenter.radius
            })) + t.moveCenter.x, t.position.y = Math.floor(Oi({
              min: -t.moveCenter.radius,
              max: t.moveCenter.radius
            })) + t.moveCenter.y;
            const { dx: c, dy: f } = _n(t.position, t.moveCenter);
            t.moveCenter.radius && (t.direction = Math.atan2(f, c), t.velocity.angle = t.direction), t.justWarped = !0;
            break;
          }
          case ti.normal: {
            const c = t.options.move.warp, f = u.canvas.size, m = {
              bottom: f.height + t.getRadius() + t.offset.y,
              left: -t.getRadius() - t.offset.x,
              right: f.width + t.getRadius() + t.offset.x,
              top: -t.getRadius() - t.offset.y
            }, p = t.getRadius(), g = Zc(t.position, p);
            i === Mt.right && g.left > f.width + t.offset.x ? (t.position.x = m.left, t.initialPosition.x = t.position.x, c || (t.position.y = Yt() * f.height, t.initialPosition.y = t.position.y), t.justWarped = !0) : i === Mt.left && g.right < -t.offset.x && (t.position.x = m.right, t.initialPosition.x = t.position.x, c || (t.position.y = Yt() * f.height, t.initialPosition.y = t.position.y), t.justWarped = !0), i === Mt.bottom && g.top > f.height + t.offset.y ? (c || (t.position.x = Yt() * f.width, t.initialPosition.x = t.position.x), t.position.y = m.top, t.initialPosition.y = t.position.y, t.justWarped = !0) : i === Mt.top && g.bottom < -t.offset.y && (c || (t.position.x = Yt() * f.width, t.initialPosition.x = t.position.x), t.position.y = m.bottom, t.initialPosition.y = t.position.y, t.justWarped = !0);
            break;
          }
        }
        break;
      }
    }
  }
}
wc = new WeakMap();
const qO = (n, t) => n.default === t || n.bottom === t || n.left === t || n.right === t || n.top === t;
var Mc, Ln, Gu, Yu;
class GO {
  constructor(t) {
    k(this, Ln);
    w(this, "updaters");
    k(this, Mc);
    A(this, Mc, t), this.updaters = /* @__PURE__ */ new Map();
  }
  init(t) {
    L(this, Ln, Gu).call(this, t, he.bounce, (i) => new NO(i)), L(this, Ln, Gu).call(this, t, he.out, (i) => new HO(i)), L(this, Ln, Gu).call(this, t, he.destroy, (i) => new UO(i)), L(this, Ln, Gu).call(this, t, he.none, (i) => new jO(i));
  }
  isEnabled(t) {
    return !t.destroyed && !t.spawning;
  }
  update(t, i) {
    const a = t.options.move.outModes;
    t.justWarped = !1, L(this, Ln, Yu).call(this, t, i, a.bottom ?? a.default, Mt.bottom), L(this, Ln, Yu).call(this, t, i, a.left ?? a.default, Mt.left), L(this, Ln, Yu).call(this, t, i, a.right ?? a.default, Mt.right), L(this, Ln, Yu).call(this, t, i, a.top ?? a.default, Mt.top);
  }
}
Mc = new WeakMap(), Ln = new WeakSet(), Gu = function(t, i, a) {
  const r = t.options.move.outModes;
  !this.updaters.has(i) && qO(r, i) && this.updaters.set(i, a(v(this, Mc)));
}, Yu = function(t, i, a, r) {
  for (const u of this.updaters.values())
    u.update(t, r, i, a);
};
async function YO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addParticleUpdater("outModes", (i) => Promise.resolve(new GO(i)));
  });
}
const og = 1;
var Xa, Qr;
class XO {
  constructor(t, i) {
    k(this, Xa);
    k(this, Qr);
    A(this, Xa, i), A(this, Qr, t);
  }
  init(t) {
    const i = v(this, Xa), a = t.options, r = Vn(a.paint, t.id, a.reduceDuplicates), u = r == null ? void 0 : r.color, c = u ?? void 0, f = r == null ? void 0 : r.fill, m = r == null ? void 0 : r.stroke;
    if (f) {
      const p = zi.create(c === void 0 ? void 0 : zi.create(void 0, c), f.color);
      t.fillEnabled = f.enable, t.fillOpacity = ht(f.opacity), t.fillAnimation = p.animation;
      const g = ac(v(this, Qr), p);
      g && (t.fillColor = FS(g, t.fillAnimation, i.retina.reduceFactor));
    } else
      t.fillEnabled = !1, t.fillAnimation = void 0, t.fillColor = void 0, t.fillOpacity = og;
    if (m) {
      const p = zi.create(c === void 0 ? void 0 : zi.create(void 0, c), m.color);
      t.strokeWidth = ht(m.width) * i.retina.pixelRatio, t.strokeOpacity = ht(m.opacity ?? og), t.strokeAnimation = p.animation;
      const g = ac(v(this, Qr), p) ?? t.getFillColor();
      g && (t.strokeColor = FS(g, t.strokeAnimation, i.retina.reduceFactor));
    } else
      t.strokeAnimation = void 0, t.strokeColor = void 0, t.strokeOpacity = og, t.strokeWidth = 0;
  }
  isEnabled(t) {
    const { fillAnimation: i, fillColor: a, strokeAnimation: r, strokeColor: u } = t, c = !!i && ((a == null ? void 0 : a.h.value) !== void 0 && a.h.enable || (a == null ? void 0 : a.s.value) !== void 0 && a.s.enable || (a == null ? void 0 : a.l.value) !== void 0 && a.l.enable), f = !!r && ((u == null ? void 0 : u.h.value) !== void 0 && u.h.enable || (u == null ? void 0 : u.s.value) !== void 0 && u.s.enable || (u == null ? void 0 : u.l.value) !== void 0 && u.l.enable);
    return !t.destroyed && !t.spawning && (c || f);
  }
  update(t, i) {
    this.isEnabled(t) && (ZS(t.fillColor, i, v(this, Xa).hdr), ZS(t.strokeColor, i, v(this, Xa).hdr));
  }
}
Xa = new WeakMap(), Qr = new WeakMap();
async function ZM(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addParticleUpdater("paint", (i) => Promise.resolve(new XO(t.pluginManager, i)));
  });
}
var zr;
(function(n) {
  n[n.r = 1] = "r", n[n.g = 2] = "g", n[n.b = 3] = "b", n[n.a = 5] = "a";
})(zr || (zr = {}));
const FO = /rgba?\(\s*(\d{1,3})\s*[\s,]\s*(\d{1,3})\s*[\s,]\s*(\d{1,3})\s*([\s,]\s*(0|1|0?\.\d+|(\d{1,3})%)\s*)?\)/i;
class ZO {
  accepts(t) {
    return t.startsWith("rgb");
  }
  handleColor(t) {
    const i = t.value, a = i.rgb ?? t.value;
    if (!(!("r" in a) || !("g" in a) || !("b" in a)))
      return a;
  }
  handleRangeColor(t) {
    const i = t.value, a = i.rgb ?? t.value;
    if (!(!("r" in a) || !("g" in a) || !("b" in a)))
      return {
        r: ht(a.r),
        g: ht(a.g),
        b: ht(a.b)
      };
  }
  parseString(t) {
    if (!this.accepts(t))
      return;
    const i = FO.exec(t), a = 10;
    return i ? {
      a: i.length > 4 ? AM(i[zr.a]) : 1,
      b: parseInt(i[zr.b] ?? "0", a),
      g: parseInt(i[zr.g] ?? "0", a),
      r: parseInt(i[zr.r] ?? "0", a)
    } : void 0;
  }
}
async function QO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addColorManager("rgb", new ZO());
  });
}
class KO extends Iy {
  constructor() {
    super(...arguments);
    w(this, "destroy", ko.none);
  }
  load(i) {
    super.load(i), !gt(i) && q(this, "destroy", i.destroy);
  }
}
class IO extends VM {
  constructor() {
    super(...arguments);
    w(this, "animation", new KO());
    w(this, "value", 3);
  }
  load(i) {
    if (super.load(i), gt(i))
      return;
    const a = i.animation;
    a !== void 0 && this.animation.load(a);
  }
}
const Tr = 0;
var Kr;
class $O {
  constructor(t) {
    k(this, Kr);
    A(this, Kr, t);
  }
  init(t) {
    const i = v(this, Kr), a = t.options.size;
    if (!a)
      return;
    const r = a.animation;
    r.enable && (t.size.velocity = t.retina.sizeAnimationSpeed / sa * i.retina.reduceFactor, !r.sync && (t.size.velocity *= Yt()));
  }
  isEnabled(t) {
    return !t.destroyed && !t.spawning && t.size.enable && ((t.size.maxLoops ?? Tr) <= Tr || (t.size.maxLoops ?? Tr) > Tr && (t.size.loops ?? Tr) < (t.size.maxLoops ?? Tr));
  }
  loadOptions(t, ...i) {
    Re(t, "size", IO, ...i);
  }
  preInit(t) {
    const i = v(this, Kr).retina.pixelRatio, a = t.options, r = a.size;
    r && (t.size = XM(r, i), t.retina.sizeAnimationSpeed = ht(r.animation.speed) * i);
  }
  reset(t) {
    t.size.time = 0, t.size.loops = 0;
  }
  update(t, i) {
    !this.isEnabled(t) || !t.options.size || tv(t, t.size, !0, t.options.size.animation.destroy, i);
  }
}
Kr = new WeakMap();
async function WO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addParticleUpdater("size", (i) => Promise.resolve(new $O(i)));
  });
}
async function JO(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register(async (t) => {
    await Promise.all([
      dO(t),
      CO(t),
      DO(t),
      QO(t),
      OO(t),
      bO(t),
      ZM(t),
      LO(t),
      YO(t),
      WO(t)
    ]);
  });
}
const Td = /* @__PURE__ */ new Map();
Td.set("ease-in-quad", (n) => n ** 2);
Td.set("ease-out-quad", (n) => 1 - (1 - n) ** 2);
Td.set("ease-in-out-quad", (n) => n < 0.5 ? 2 * n ** 2 : 1 - (-2 * n + 2) ** 2 / 2);
async function tz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    for (const [i, a] of Td)
      t.pluginManager.addEasing(i, a);
  });
}
const Zg = ["emoji"];
function ez(n, t) {
  const { context: i, opacity: a } = n, r = i.globalAlpha, u = t.width, c = u * bt;
  i.globalAlpha = a, i.drawImage(t, -c, -c, u, u), i.globalAlpha = r;
}
function QM(n, t, i) {
  n.beginPath(), n.moveTo(t.x, t.y), n.lineTo(i.x, i.y), n.closePath();
}
async function IS(n, t) {
  try {
    await Un().fonts.load(`${t ?? "400"} 36px '${n ?? "Verdana"}'`);
  } catch {
  }
}
const rg = '"Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif', $S = 0, nz = 0;
var Os;
class iz {
  constructor() {
    k(this, Os, /* @__PURE__ */ new Map());
  }
  destroy() {
    for (const [t, i] of v(this, Os))
      i instanceof ImageBitmap && i.close(), v(this, Os).delete(t);
  }
  draw(t) {
    const i = t.particle.emojiDataKey;
    if (!i)
      return;
    const a = v(this, Os).get(i);
    a && ez(t, a);
  }
  async init(t) {
    const i = t.actualOptions, a = i.particles.shape;
    if (!Zg.some((c) => Zt(c, a.type)))
      return;
    const r = [IS(rg)], u = Zg.map((c) => a.options[c])[nz];
    Gn(u, (c) => {
      c.font && r.push(IS(c.font));
    }), await Promise.all(r);
  }
  particleDestroy(t) {
    t.emojiDataKey = void 0;
  }
  particleInit(t, i) {
    const a = i.shapeData;
    if (!a.value)
      return;
    const r = Vn(a.value, i.randomIndexData);
    if (!r)
      return;
    const u = typeof r == "string" ? {
      font: a.font ?? rg,
      padding: a.padding ?? $S,
      value: r
    } : {
      font: rg,
      padding: $S,
      ...a,
      ...r
    }, c = u.font, f = u.value, m = `${f}_${c}`;
    if (v(this, Os).has(m)) {
      i.emojiDataKey = m;
      return;
    }
    const p = u.padding * Bt, g = wd(i.size.value), y = g + p, b = y * Bt, S = new OffscreenCanvas(b, b), T = S.getContext("2d", t.canvas.render.settings);
    if (!T)
      return;
    T.font = `400 ${(g * Bt).toString()}px ${c}`, T.textBaseline = "middle", T.textAlign = "center", T.fillText(f, y, y);
    const C = S instanceof HTMLCanvasElement ? S : S.transferToImageBitmap();
    v(this, Os).set(m, C), i.emojiDataKey = m;
  }
}
Os = new WeakMap();
async function sz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(Zg, () => Promise.resolve(new iz()));
  });
}
class az {
  constructor() {
    w(this, "enable", !1);
    w(this, "mode", []);
  }
  load(t) {
    gt(t) || (q(this, "enable", t.enable), q(this, "mode", t.mode));
  }
}
var Po;
(function(n) {
  n.circle = "circle", n.rectangle = "rectangle";
})(Po || (Po = {}));
class WS {
  constructor() {
    w(this, "enable", !1);
    w(this, "mode", []);
    w(this, "selectors", []);
    w(this, "type", Po.circle);
  }
  load(t) {
    gt(t) || (q(this, "selectors", t.selectors), q(this, "enable", t.enable), q(this, "mode", t.mode), q(this, "type", t.type));
  }
}
class oz {
  constructor() {
    w(this, "enable", !1);
    w(this, "mode", []);
  }
  load(t) {
    gt(t) || (q(this, "enable", t.enable), q(this, "mode", t.mode));
  }
}
class rz {
  constructor() {
    w(this, "onClick", new az());
    w(this, "onDiv", new WS());
    w(this, "onHover", new oz());
  }
  load(t) {
    if (gt(t))
      return;
    this.onClick.load(t.onClick);
    const i = t.onDiv;
    i !== void 0 && (this.onDiv = Gn(i, (a) => {
      const r = new WS();
      return r.load(a), r;
    })), this.onHover.load(t.onHover);
  }
}
var Nr;
(function(n) {
  n.canvas = "canvas", n.parent = "parent", n.window = "window";
})(Nr || (Nr = {}));
var Ir, Tc;
class lz {
  constructor(t, i) {
    k(this, Ir);
    k(this, Tc);
    A(this, Tc, t), A(this, Ir, i);
  }
  load(t) {
    var a;
    if (gt(t) || !v(this, Ir))
      return;
    const i = (a = v(this, Tc).interactors) == null ? void 0 : a.get(v(this, Ir));
    if (i)
      for (const r of i)
        r.loadModeOptions && r.loadModeOptions(this, t);
  }
}
Ir = new WeakMap(), Tc = new WeakMap();
class KM {
  constructor(t, i) {
    w(this, "detectsOn", Nr.window);
    w(this, "events", new rz());
    w(this, "modes");
    this.modes = new lz(t, i);
  }
  load(t) {
    if (gt(t))
      return;
    const i = t.detectsOn;
    i !== void 0 && (this.detectsOn = i), this.events.load(t.events), this.modes.load(t.modes);
  }
}
var zs;
class uz {
  constructor(t) {
    w(this, "id", "interactivity");
    k(this, zs);
    A(this, zs, t);
  }
  async getPlugin(t) {
    const { InteractivityPluginInstance: i } = await Promise.resolve().then(() => P6);
    return new i(v(this, zs), t);
  }
  loadOptions(t, i, a) {
    var c;
    if (!this.needsPlugin())
      return;
    let r = i.interactivity;
    r != null && r.load || (i.interactivity = r = new KM(v(this, zs), t)), r.load(a == null ? void 0 : a.interactivity);
    const u = (c = v(this, zs).interactors) == null ? void 0 : c.get(t);
    if (u)
      for (const f of u)
        f.loadOptions && f.loadOptions(i, a);
  }
  loadParticlesOptions(t, i, a) {
    var u, c;
    a != null && a.interactivity && (i.interactivity = bn({}, a.interactivity));
    const r = (u = v(this, zs).interactors) == null ? void 0 : u.get(t);
    if (r)
      for (const f of r)
        (c = f.loadParticlesOptions) == null || c.call(f, i, a);
  }
  needsPlugin() {
    return !0;
  }
}
zs = new WeakMap();
var Ol;
(function(n) {
  n.external = "external", n.particles = "particles";
})(Ol || (Ol = {}));
class Yn {
  constructor(t) {
    w(this, "type", Ol.external);
    w(this, "container");
    this.container = t;
  }
}
class ev {
  constructor(t) {
    w(this, "type", Ol.particles);
    w(this, "container");
    this.container = t;
  }
}
const cz = "click", JS = "pointerdown", t1 = "pointerup", Qg = "pointerleave", la = "pointermove", IM = "touchstart", Xu = "touchend", $M = "touchmove", WM = "touchcancel";
function JM(n, t) {
  return vn(n) ? n.find((a, r) => t(a, r)) : t(n, 0) ? n : void 0;
}
function fz(n, t) {
  const i = Gn(t, (a) => n.matches(a));
  return vn(i) ? i.some((a) => a) : i;
}
function Cd(n, t) {
  return !!JM(t, (i) => i.enable && Zt(n, i.mode));
}
function Ed(n, t, i) {
  Gn(t, (a) => {
    const r = a.mode;
    a.enable && Zt(n, r) && hz(a, i);
  });
}
function hz(n, t) {
  const i = n.selectors;
  Gn(i, (a) => {
    t(a, n);
  });
}
function tT(n, t) {
  if (!(!t || !n))
    return JM(n, (i) => fz(t, i.selectors));
}
async function dz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var r;
    const i = t, a = i.pluginManager;
    a.addPlugin(new uz(a)), (r = a.initializers).interactors ?? (r.interactors = /* @__PURE__ */ new Map()), a.interactors ?? (a.interactors = /* @__PURE__ */ new Map()), a.addInteractor = (u, c) => {
      var f;
      (f = a.initializers).interactors ?? (f.interactors = /* @__PURE__ */ new Map()), a.initializers.interactors.set(u, c);
    }, a.getInteractors = async (u, c = !1) => {
      var f;
      return a.interactors ?? (a.interactors = /* @__PURE__ */ new Map()), (f = a.initializers).interactors ?? (f.interactors = /* @__PURE__ */ new Map()), RM(u, a.interactors, a.initializers.interactors, c);
    }, a.setOnClickHandler = (u) => {
      const { items: c } = i;
      if (!c.length)
        throw new Error("Click handlers can only be set after calling tsParticles.load()");
      c.forEach((f) => {
        var p;
        const m = f;
        (p = m.addClickHandler) == null || p.call(m, u);
      });
    };
  });
}
function $e(n) {
  if (!n.pluginManager.addInteractor)
    throw new Error("tsParticles Interactivity Plugin is not loaded");
}
const mz = 1, eT = 0, lg = Qe.origin;
function nT(n, t, i, a, r, u, c) {
  var p;
  const f = (p = t.actualOptions.interactivity) == null ? void 0 : p.modes.attract;
  if (!f)
    return;
  const m = t.particles.grid.query(r, u);
  for (const g of m) {
    const { dx: y, dy: b, distance: S } = _n(g.position, i), T = f.speed * f.factor, C = Nn(n.getEasing(f.easing)(De - S / a) * T, mz, f.maxSpeed);
    lg.x = S ? y / S * C : T, lg.y = S ? b / S * C : T, c == null || c(g), g.position.subFrom(lg);
  }
}
function pz(n, t, i, a, r) {
  t.attract ?? (t.attract = { particles: [] });
  const { attract: u } = t;
  if (u.finish || (u.count ?? (u.count = 0), u.count++, u.count === t.particles.count && (u.finish = !0)), u.clicking) {
    const c = i.mouse.clickPosition, f = t.retina.attractModeDistance;
    if (!f || f < eT || !c)
      return;
    nT(n, t, c, f, new be(c.x, c.y, f), (m) => a(m), r);
  } else u.clicking === !1 && (u.particles = []);
}
function gz(n, t, i, a, r) {
  const u = i.mouse.position, c = t.retina.attractModeDistance;
  !c || c < eT || !u || nT(n, t, u, c, new be(u.x, u.y, c), (f) => a(f), r);
}
let yz = class {
  constructor() {
    w(this, "distance", 200);
    w(this, "duration", 0.4);
    w(this, "easing", "ease-out-quad");
    w(this, "factor", 1);
    w(this, "maxSpeed", 50);
    w(this, "restore");
    w(this, "speed", 1);
    this.restore = {
      enable: !1,
      delay: 0,
      speed: 0.08,
      follow: !0
    };
  }
  load(t) {
    gt(t) || (q(this, "distance", t.distance), q(this, "duration", t.duration), t.easing !== void 0 && (this.easing = t.easing), q(this, "factor", t.factor), t.maxSpeed !== void 0 && (this.maxSpeed = t.maxSpeed), q(this, "speed", t.speed), t.restore !== void 0 && (this.restore.enable = t.restore.enable ?? this.restore.enable, this.restore.delay = t.restore.delay ?? this.restore.delay, this.restore.speed = t.restore.speed ?? this.restore.speed, this.restore.follow = t.restore.follow ?? this.restore.follow));
  }
};
const Bu = "attract", vz = 0, bz = 1e-3, xz = 1, e1 = 0.5;
var Fa, $r, Wr, pi, _o, iT, Kg, fM;
let Sz = (fM = class extends Yn {
  constructor(i, a) {
    super(a);
    k(this, _o);
    w(this, "handleClickMode");
    k(this, Fa);
    k(this, $r);
    k(this, Wr);
    k(this, pi);
    A(this, Wr, i), A(this, $r, 0), A(this, Fa, /* @__PURE__ */ new Set()), A(this, pi, /* @__PURE__ */ new Map()), a.attract ?? (a.attract = { particles: [] }), this.handleClickMode = (r, u) => {
      var m;
      const c = this.container.actualOptions, f = (m = c.interactivity) == null ? void 0 : m.modes.attract;
      if (!(!f || r !== Bu)) {
        a.attract ?? (a.attract = { particles: [] }), a.attract.clicking = !0, a.attract.count = 0;
        for (const p of a.attract.particles)
          this.isEnabled(u, p) && p.velocity.setTo(p.initialVelocity);
        a.attract.particles = [], a.attract.finish = !1, setTimeout(() => {
          a.destroyed || (a.attract ?? (a.attract = { particles: [] }), a.attract.clicking = !1);
        }, f.duration * Ae);
      }
    };
  }
  get maxDistance() {
    return v(this, $r);
  }
  clear() {
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.attract;
    a && (A(this, $r, a.distance), i.retina.attractModeDistance = a.distance * i.retina.pixelRatio);
  }
  interact(i) {
    var y;
    v(this, Fa).clear();
    const a = this.container, r = a.actualOptions, u = i.status === la, c = (y = r.interactivity) == null ? void 0 : y.events;
    if (!c)
      return;
    const { enable: f, mode: m } = c.onHover, { enable: p, mode: g } = c.onClick;
    u && f && Zt(Bu, m) ? gz(v(this, Wr), this.container, i, (b) => this.isEnabled(i, b), (b) => {
      L(this, _o, Kg).call(this, b);
    }) : p && Zt(Bu, g) && pz(v(this, Wr), this.container, i, (b) => this.isEnabled(i, b), (b) => {
      L(this, _o, Kg).call(this, b);
    }), L(this, _o, iT).call(this);
  }
  isEnabled(i, a) {
    var g;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (g = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : g.events;
    if ((!c.position || !(f != null && f.onHover.enable)) && (!c.clickPosition || !(f != null && f.onClick.enable)))
      return !1;
    const m = f.onHover.mode, p = f.onClick.mode;
    return Zt(Bu, m) || Zt(Bu, p);
  }
  loadModeOptions(i, ...a) {
    Re(i, "attract", yz, ...a);
  }
  reset() {
  }
}, Fa = new WeakMap(), $r = new WeakMap(), Wr = new WeakMap(), pi = new WeakMap(), _o = new WeakSet(), iT = function() {
  var c, f;
  const i = (f = (c = this.container.actualOptions.interactivity) == null ? void 0 : c.modes.attract) == null ? void 0 : f.restore;
  if (!(i != null && i.enable) || !v(this, pi).size)
    return;
  const a = Date.now(), r = i.delay * Ae, u = Math.max(bz, Math.min(xz, i.speed));
  for (const [m, p] of v(this, pi)) {
    if (v(this, Fa).has(m))
      continue;
    if (m.destroyed) {
      v(this, pi).delete(m);
      continue;
    }
    const g = p.target;
    if (a - p.lastInteractionTime < r)
      continue;
    let y = g.x - m.position.x, b = g.y - m.position.y, S = g.z - m.position.z;
    if (i.follow && m.options.move.enable) {
      const { x: T, y: C, z: R } = m.velocity, z = T * T + C * C + R * R;
      if (z > vz) {
        const B = (y * T + b * C + S * R) / z;
        y -= T * B, b -= C * B, S -= R * B;
      }
    }
    if (m.position.x += y * u, m.position.y += b * u, m.position.z += S * u, Math.abs(y) <= e1 && Math.abs(b) <= e1) {
      m.position.x = g.x, m.position.y = g.y, m.position.z = g.z, v(this, pi).delete(m);
      continue;
    }
  }
}, Kg = function(i) {
  var c, f;
  v(this, Fa).add(i);
  const a = (f = (c = this.container.actualOptions.interactivity) == null ? void 0 : c.modes.attract) == null ? void 0 : f.restore;
  if (!(a != null && a.enable))
    return;
  const r = Date.now();
  let u = v(this, pi).get(i);
  u || (u = {
    target: i.position.copy(),
    lastInteractionTime: r
  }, v(this, pi).set(i, u)), u.lastInteractionTime = r;
}, fM);
async function wz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalAttract", (r) => Promise.resolve(new Sz(t.pluginManager, r)));
  });
}
const Mz = Math.PI * bt, sT = 10;
function aT(n, t, i, a, r) {
  const u = n.particles.grid.query(a, r);
  for (const c of u)
    a instanceof be ? DM(Gg(c), {
      position: t,
      mass: i ** ra * Mz,
      velocity: Qe.origin,
      factor: Qe.origin
    }) : a instanceof ni && Az(c, Zc(t, i));
}
function Tz(n, t, i, a) {
  const r = Un().querySelectorAll(t);
  r.length && r.forEach((u) => {
    const c = u, f = n.retina.pixelRatio, m = {
      x: (c.offsetLeft + c.offsetWidth * bt) * f,
      y: (c.offsetTop + c.offsetHeight * bt) * f
    }, p = c.offsetWidth * bt * f, g = sT * f, y = i.type === Po.circle ? new be(m.x, m.y, p + g) : new ni(c.offsetLeft * f - g, c.offsetTop * f - g, c.offsetWidth * f + g * Bt, c.offsetHeight * f + g * Bt);
    a(m, p, y);
  });
}
function Cz(n, t, i, a) {
  Ed(i, t, (r, u) => {
    Tz(n, r, u, (c, f, m) => {
      aT(n, c, f, m, a);
    });
  });
}
function Ez(n, t, i) {
  const a = n.retina.pixelRatio, r = sT * a, u = t.mouse.position, c = n.retina.bounceModeDistance;
  !c || c < pM || !u || aT(n, u, c, new be(u.x, u.y, c + r), i);
}
function n1(n) {
  const t = { bounced: !1 }, { pSide: i, pOtherSide: a, rectSide: r, rectOtherSide: u, velocity: c, factor: f } = n;
  return a.min < u.min || a.min > u.max || a.max < u.min || a.max > u.max || (i.max >= r.min && i.max <= (r.max + r.min) * bt && c > Wt || i.min <= r.max && i.min > (r.max + r.min) * bt && c < Wt) && (t.velocity = c * -f, t.bounced = !0), t;
}
function Az(n, t) {
  const i = n.getPosition(), a = n.getRadius(), r = Zc(i, a), u = n.options.bounce, c = n1({
    pSide: {
      min: r.left,
      max: r.right
    },
    pOtherSide: {
      min: r.top,
      max: r.bottom
    },
    rectSide: {
      min: t.left,
      max: t.right
    },
    rectOtherSide: {
      min: t.top,
      max: t.bottom
    },
    velocity: n.velocity.x,
    factor: ht(u.horizontal.value)
  });
  c.bounced && (c.velocity !== void 0 && (n.velocity.x = c.velocity), c.position !== void 0 && (n.position.x = c.position));
  const f = n1({
    pSide: {
      min: r.top,
      max: r.bottom
    },
    pOtherSide: {
      min: r.left,
      max: r.right
    },
    rectSide: {
      min: t.top,
      max: t.bottom
    },
    rectOtherSide: {
      min: t.left,
      max: t.right
    },
    velocity: n.velocity.y,
    factor: ht(u.vertical.value)
  });
  f.bounced && (f.velocity !== void 0 && (n.velocity.y = f.velocity), f.position !== void 0 && (n.position.y = f.position));
}
class Dz {
  constructor() {
    w(this, "distance", 200);
  }
  load(t) {
    gt(t) || q(this, "distance", t.distance);
  }
}
const Th = "bounce";
var Jr;
class Rz extends Yn {
  constructor(i) {
    super(i);
    k(this, Jr);
    A(this, Jr, 0);
  }
  get maxDistance() {
    return v(this, Jr);
  }
  clear() {
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.bounce;
    a && (A(this, Jr, a.distance), i.retina.bounceModeDistance = a.distance * i.retina.pixelRatio);
  }
  interact(i) {
    var g;
    const a = this.container, r = a.actualOptions, u = (g = r.interactivity) == null ? void 0 : g.events, c = i.status === la;
    if (!u)
      return;
    const f = u.onHover.enable, m = u.onHover.mode, p = u.onDiv;
    c && f && Zt(Th, m) ? Ez(this.container, i, (y) => this.isEnabled(i, y)) : Cz(this.container, p, Th, (y) => this.isEnabled(i, y));
  }
  isEnabled(i, a) {
    var p;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (p = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : p.events;
    if (!f)
      return !1;
    const m = f.onDiv;
    return !!c.position && f.onHover.enable && Zt(Th, f.onHover.mode) || Cd(Th, m);
  }
  loadModeOptions(i, ...a) {
    Re(i, "bounce", Dz, ...a);
  }
  reset() {
  }
}
Jr = new WeakMap();
async function Oz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalBounce", (r) => Promise.resolve(new Rz(r)));
  });
}
class oT {
  constructor() {
    w(this, "color");
    w(this, "distance", 200);
    w(this, "duration", 0.4);
    w(this, "mix", !1);
    w(this, "opacity");
    w(this, "size");
  }
  load(t) {
    if (!gt(t)) {
      if (q(this, "distance", t.distance), q(this, "duration", t.duration), q(this, "mix", t.mix), Qt(this, "opacity", t.opacity), t.color !== void 0) {
        const i = vn(this.color) ? void 0 : this.color;
        this.color = Gn(t.color, (a) => jn.create(i, a));
      }
      q(this, "size", t.size);
    }
  }
}
class zz extends oT {
  constructor() {
    super(...arguments);
    w(this, "selectors", []);
  }
  load(i) {
    super.load(i), !gt(i) && q(this, "selectors", i.selectors);
  }
}
class kz extends oT {
  constructor() {
    super(...arguments);
    w(this, "divs");
  }
  load(i) {
    super.load(i), !gt(i) && (this.divs = Gn(i.divs, (a) => {
      const r = new zz();
      return r.load(a), r;
    }));
  }
}
class Vz {
  constructor() {
    w(this, "div");
    w(this, "enabled", !1);
    w(this, "fillColor");
    w(this, "finalColor");
    w(this, "id", "bubble");
    w(this, "inRange", !1);
    w(this, "opacity");
    w(this, "priority", 100);
    w(this, "radius");
    w(this, "strokeColor");
  }
}
var di;
(function(n) {
  n.color = "color", n.opacity = "opacity", n.size = "size";
})(di || (di = {}));
function i1(n, t, i, a) {
  if (t >= i) {
    const r = n + (t - i) * a;
    return Nn(r, n, t);
  } else if (t < i) {
    const r = n - (i - t) * a;
    return Nn(r, t, n);
  }
}
const Ts = "bubble", ug = 0, Pz = 0, Ch = 1, s1 = 1, Lz = 0, _z = 0, cg = 1;
var tl, ks, Cc, me, rT, lT, jh, Ig, $g, Wg, uT;
class Bz extends Yn {
  constructor(i, a) {
    super(a);
    k(this, me);
    w(this, "handleClickMode");
    k(this, tl);
    k(this, ks, /* @__PURE__ */ new WeakMap());
    k(this, Cc);
    A(this, Cc, i), A(this, tl, 0), a.bubble ?? (a.bubble = {}), this.handleClickMode = (r) => {
      r === Ts && (a.bubble ?? (a.bubble = {}), a.bubble.clicking = !0);
    };
  }
  get maxDistance() {
    return v(this, tl);
  }
  clear(i, a, r) {
    const u = v(this, ks).get(i);
    u != null && u.inRange && !r || (i.removeModifier(Ts), v(this, ks).delete(i));
  }
  getOrCreateModifier(i) {
    let a = v(this, ks).get(i);
    return a || (a = new Vz(), v(this, ks).set(i, a), i.addModifier(a)), a;
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.bubble;
    a && (A(this, tl, a.distance), i.retina.bubbleModeDistance = a.distance * i.retina.pixelRatio, a.size !== void 0 && (i.retina.bubbleModeSize = a.size * i.retina.pixelRatio));
  }
  interact(i, a) {
    var S;
    const r = this.container.actualOptions, u = (S = r.interactivity) == null ? void 0 : S.events;
    if (!u)
      return;
    const c = u.onHover, f = u.onClick, m = c.enable, p = c.mode, g = f.enable, y = f.mode, b = u.onDiv;
    m && Zt(Ts, p) ? L(this, me, lT).call(this, i) : g && Zt(Ts, y) ? L(this, me, rT).call(this, i) : Ed(Ts, b, (T, C) => {
      L(this, me, uT).call(this, i, a, T, C);
    });
  }
  isEnabled(i, a) {
    var b;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (b = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : b.events;
    if (!f)
      return !1;
    const { onClick: m, onDiv: p, onHover: g } = f, y = Cd(Ts, p);
    return y || g.enable && c.position || m.enable && c.clickPosition ? Zt(Ts, g.mode) || Zt(Ts, m.mode) || y : !1;
  }
  loadModeOptions(i, ...a) {
    Re(i, "bubble", kz, ...a);
  }
  reset(i, a) {
    const r = v(this, ks).get(a);
    r && (r.enabled = !1, r.inRange = !1);
  }
}
tl = new WeakMap(), ks = new WeakMap(), Cc = new WeakMap(), me = new WeakSet(), rT = function(i) {
  var g, y, b;
  const a = this.container, r = a.actualOptions, u = i.mouse.clickPosition, c = (g = r.interactivity) == null ? void 0 : g.modes.bubble;
  if (!c || !u)
    return;
  a.bubble ?? (a.bubble = {});
  const f = a.retina.bubbleModeDistance;
  if (!f || f < ug)
    return;
  const m = a.particles.grid.queryCircle(u, f, (S) => this.isEnabled(i, S)), { bubble: p } = a;
  for (const S of m) {
    if (!p.clicking)
      continue;
    const T = this.getOrCreateModifier(S);
    T.enabled = !p.durationEnd, T.inRange = !p.durationEnd;
    const C = S.getPosition(), R = Oo(C, u), z = (performance.now() - (i.mouse.clickTime ?? Pz)) / Ae;
    z > c.duration && (p.durationEnd = !0), z > c.duration * Bt && (p.clicking = !1, p.durationEnd = !1);
    const B = {
      bubbleObj: {
        optValue: a.retina.bubbleModeSize,
        value: T.radius
      },
      particlesObj: {
        optValue: S.size.max,
        value: S.size.value
      },
      type: di.size
    };
    L(this, me, Wg).call(this, S, R, z, B);
    const H = {
      bubbleObj: {
        optValue: c.opacity,
        value: T.opacity
      },
      particlesObj: {
        optValue: ((y = S.opacity) == null ? void 0 : y.max) ?? Ch,
        value: ((b = S.opacity) == null ? void 0 : b.value) ?? Ch
      },
      type: di.opacity
    };
    L(this, me, Wg).call(this, S, R, z, H), !p.durationEnd && R <= f ? L(this, me, jh).call(this, S, R) : (T.fillColor = void 0, T.strokeColor = void 0);
  }
}, lT = function(i) {
  const a = this.container, r = i.mouse.position, u = a.retina.bubbleModeDistance;
  if (!u || u < ug || !r)
    return;
  const c = a.particles.grid.queryCircle(r, u, (f) => this.isEnabled(i, f));
  for (const f of c) {
    const m = this.getOrCreateModifier(f);
    m.enabled = !0, m.inRange = !0;
    const p = f.getPosition(), g = Oo(p, r), y = s1 - g / u;
    g <= u ? y >= _z && i.status === la && (L(this, me, $g).call(this, f, y), L(this, me, Ig).call(this, f, y), L(this, me, jh).call(this, f, y)) : this.reset(i, f), i.status === Qg && this.reset(i, f);
  }
}, jh = function(i, a, r) {
  var m;
  const u = this.container.actualOptions, c = r ?? ((m = u.interactivity) == null ? void 0 : m.modes.bubble), f = this.getOrCreateModifier(i);
  if (c) {
    if (!f.finalColor) {
      const p = c.color;
      if (!p)
        return;
      const g = Vn(p);
      f.finalColor = ac(v(this, Cc), g);
    }
    if (f.finalColor)
      if (c.mix) {
        f.fillColor = void 0, f.strokeColor = void 0;
        const p = i.getFillColor();
        if (p) {
          const g = HM(Wy(p, f.finalColor, s1 - a, a));
          f.fillColor = g, f.strokeColor = g;
        } else
          f.fillColor = f.finalColor, f.strokeColor = f.finalColor;
      } else
        f.fillColor = f.finalColor, f.strokeColor = f.finalColor;
  }
}, Ig = function(i, a, r) {
  var g, y, b, S;
  const u = this.container, c = u.actualOptions, f = (r == null ? void 0 : r.opacity) ?? ((y = (g = c.interactivity) == null ? void 0 : g.modes.bubble) == null ? void 0 : y.opacity);
  if (!f)
    return;
  const m = ((b = i.opacity) == null ? void 0 : b.value) ?? Ch, p = i1(m, f, ((S = i.opacity) == null ? void 0 : S.max) ?? Ch, a);
  if (p !== void 0) {
    const T = this.getOrCreateModifier(i);
    T.opacity = p;
  }
}, $g = function(i, a, r) {
  const u = this.container, c = r != null && r.size ? r.size * u.retina.pixelRatio : u.retina.bubbleModeSize;
  if (c === void 0)
    return;
  const f = i.size.value, m = i1(f, c, i.size.max, a);
  if (m !== void 0) {
    const p = this.getOrCreateModifier(i);
    p.radius = m;
  }
}, Wg = function(i, a, r, u) {
  var z;
  const c = this.container, f = u.bubbleObj.optValue, m = c.actualOptions, p = (z = m.interactivity) == null ? void 0 : z.modes.bubble;
  if (!p || f === void 0)
    return;
  const g = p.duration, y = c.retina.bubbleModeDistance, b = u.particlesObj.optValue, S = u.bubbleObj.value, T = u.particlesObj.value ?? Lz, C = u.type;
  if (!y || y < ug || f === b)
    return;
  c.bubble ?? (c.bubble = {});
  const R = this.getOrCreateModifier(i);
  if (c.bubble.durationEnd)
    S && (C === di.size && (R.radius = void 0), C === di.opacity && (R.opacity = void 0));
  else if (a <= y) {
    if ((S ?? T) !== f) {
      const H = T - r * (T - f) / g;
      C === di.size && (R.radius = H), C === di.opacity && (R.opacity = H);
    }
  } else
    C === di.size && (R.radius = void 0), C === di.opacity && (R.opacity = void 0);
}, uT = function(i, a, r, u) {
  var p;
  const c = this.container, f = Un().querySelectorAll(r), m = (p = c.actualOptions.interactivity) == null ? void 0 : p.modes.bubble;
  !m || !f.length || f.forEach((g) => {
    const y = g, b = c.retina.pixelRatio, S = {
      x: (y.offsetLeft + y.offsetWidth * bt) * b,
      y: (y.offsetTop + y.offsetHeight * bt) * b
    }, T = y.offsetWidth * bt * b, C = u.type === Po.circle ? new be(S.x, S.y, T) : new ni(y.offsetLeft * b, y.offsetTop * b, y.offsetWidth * b, y.offsetHeight * b), R = c.particles.grid.query(C, (z) => this.isEnabled(i, z));
    for (const z of R) {
      if (!C.contains(z.getPosition()))
        continue;
      const B = this.getOrCreateModifier(z);
      B.enabled = !0, B.inRange = !0;
      const H = m.divs, X = tT(H, y);
      (!B.div || B.div !== y) && (this.clear(z, a, !0), B.div = y), L(this, me, $g).call(this, z, cg, X), L(this, me, Ig).call(this, z, cg, X), L(this, me, jh).call(this, z, cg, X);
    }
  });
};
async function Nz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalBubble", (r) => Promise.resolve(new Bz(t.pluginManager, r)));
  });
}
class Uz {
  constructor() {
    w(this, "opacity", 0.5);
  }
  load(t) {
    gt(t) || Qt(this, "opacity", t.opacity);
  }
}
class jz {
  constructor() {
    w(this, "distance", 80);
    w(this, "links", new Uz());
    w(this, "radius", 60);
  }
  load(t) {
    gt(t) || (q(this, "distance", t.distance), this.links.load(t.links), q(this, "radius", t.radius));
  }
}
const a1 = 0, o1 = 1, Hz = 0;
function qz(n, t, i, a, r) {
  const u = Math.floor(a.getRadius() / i.getRadius()), c = i.getFillColor(), f = a.getFillColor();
  if (!c || !f)
    return;
  const m = i.getPosition(), p = a.getPosition(), g = Wy(c, f, i.getRadius(), a.getRadius()), y = t.createLinearGradient(m.x, m.y, p.x, p.y);
  return y.addColorStop(a1, oc(c, n.hdr, r)), y.addColorStop(Nn(u, a1, o1), Qc(g, n.hdr, r)), y.addColorStop(o1, oc(f, n.hdr, r)), y;
}
function Gz(n, t, i, a, r) {
  QM(n, a, r), n.lineWidth = t, n.strokeStyle = i, n.stroke();
}
function Yz(n, t, i, a) {
  var c;
  const r = n.actualOptions, u = (c = r.interactivity) == null ? void 0 : c.modes.connect;
  if (u)
    return qz(n, t, i, a, u.links.opacity);
}
function Xz(n, t, i) {
  n.canvas.render.draw((a) => {
    const r = Yz(n, a, t, i);
    if (!r)
      return;
    const u = t.getPosition(), c = i.getPosition();
    Gz(a, t.retina.linksWidth ?? Hz, r, u, c);
  });
}
const Fz = "connect", r1 = 0;
var el;
class Zz extends Yn {
  constructor(i) {
    super(i);
    k(this, el);
    A(this, el, 0);
  }
  get maxDistance() {
    return v(this, el);
  }
  clear() {
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.connect;
    a && (A(this, el, a.distance), i.retina.connectModeDistance = a.distance * i.retina.pixelRatio, i.retina.connectModeRadius = a.radius * i.retina.pixelRatio);
  }
  interact(i) {
    var u;
    const a = this.container;
    if ((u = a.actualOptions.interactivity) != null && u.events.onHover.enable && i.status === "pointermove") {
      const c = i.mouse.position, { connectModeDistance: f, connectModeRadius: m } = a.retina;
      if (!f || f < r1 || !m || m < r1 || !c)
        return;
      const p = Math.abs(m), g = a.particles.grid.queryCircle(c, p, (y) => this.isEnabled(i, y));
      g.forEach((y, b) => {
        const S = y.getPosition(), T = 1;
        for (const C of g.slice(b + T)) {
          const R = C.getPosition(), z = Math.abs(f), B = Math.abs(S.x - R.x), H = Math.abs(S.y - R.y);
          B < z && H < z && Xz(a, y, C);
        }
      });
    }
  }
  isEnabled(i, a) {
    var f;
    const r = this.container, u = i.mouse, c = (f = (a == null ? void 0 : a.interactivity) ?? r.actualOptions.interactivity) == null ? void 0 : f.events;
    return c != null && c.onHover.enable && u.position ? Zt(Fz, c.onHover.mode) : !1;
  }
  loadModeOptions(i, ...a) {
    Re(i, "connect", jz, ...a);
  }
  reset() {
  }
}
el = new WeakMap();
async function Qz(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalConnect", (r) => Promise.resolve(new Zz(r)));
  });
}
const cT = 10;
function fT(n, t) {
  const i = n.particles.grid.query(t);
  for (const a of i)
    a.destroy();
}
function Kz(n, t, i) {
  const a = Un().querySelectorAll(t);
  a.length && a.forEach((r) => {
    const u = r, c = n.retina.pixelRatio, f = {
      x: (u.offsetLeft + u.offsetWidth * bt) * c,
      y: (u.offsetTop + u.offsetHeight * bt) * c
    }, m = u.offsetWidth * bt * c, p = cT * c, g = i.type === Po.circle ? new be(f.x, f.y, m + p) : new ni(u.offsetLeft * c - p, u.offsetTop * c - p, u.offsetWidth * c + p * Bt, u.offsetHeight * c + p * Bt);
    fT(n, g);
  });
}
function Iz(n, t, i) {
  Ed(i, t, (a, r) => {
    Kz(n, a, r);
  });
}
function $z(n, t) {
  const i = n.retina.pixelRatio, a = cT * i, r = t.mouse.position, u = n.retina.destroyModeDistance;
  !u || u < pM || !r || fT(n, new be(r.x, r.y, u + a));
}
class Wz {
  constructor() {
    w(this, "distance", 200);
  }
  load(t) {
    gt(t) || q(this, "distance", t.distance);
  }
}
const Eh = "destroy";
var nl;
class Jz extends Yn {
  constructor(i) {
    super(i);
    k(this, nl);
    A(this, nl, 0);
  }
  get maxDistance() {
    return v(this, nl);
  }
  clear() {
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.destroy;
    a && (A(this, nl, a.distance), i.retina.destroyModeDistance = a.distance * i.retina.pixelRatio);
  }
  interact(i) {
    var g;
    const a = this.container, r = a.actualOptions, u = (g = r.interactivity) == null ? void 0 : g.events, c = i.status === la;
    if (!u)
      return;
    const f = u.onHover.enable, m = u.onHover.mode, p = u.onDiv;
    c && f && Zt(Eh, m) ? $z(this.container, i) : Iz(this.container, p, Eh);
  }
  isEnabled(i, a) {
    var p;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (p = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : p.events;
    if (!f)
      return !1;
    const m = f.onDiv;
    return !!c.position && f.onHover.enable && Zt(Eh, f.onHover.mode) || Cd(Eh, m);
  }
  loadModeOptions(i, ...a) {
    Re(i, "destroy", Wz, ...a);
  }
  reset() {
  }
}
nl = new WeakMap();
async function t3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalDestroy", async (r) => Promise.resolve(new Jz(r)));
  });
}
class e3 {
  constructor() {
    w(this, "blink", !1);
    w(this, "color");
    w(this, "consent", !1);
    w(this, "opacity", 1);
  }
  load(t) {
    gt(t) || (q(this, "blink", t.blink), t.color !== void 0 && (this.color = jn.create(this.color, t.color)), q(this, "consent", t.consent), Qt(this, "opacity", t.opacity));
  }
}
class n3 {
  constructor() {
    w(this, "distance", 100);
    w(this, "links", new e3());
  }
  load(t) {
    gt(t) || (q(this, "distance", t.distance), this.links.load(t.links));
  }
}
const i3 = 0;
function s3(n, t, i, a, r, u, c = !1) {
  QM(n, i, a), n.strokeStyle = Qc(r, c, u), n.lineWidth = t, n.stroke();
}
function a3(n, t, i, a, r) {
  n.canvas.render.draw((u) => {
    const c = t.getPosition();
    s3(u, t.retina.linksWidth ?? i3, c, r, i, a, n.hdr);
  });
}
const o3 = "grab", r3 = 0, l3 = 0;
var il, Ec;
class u3 extends Yn {
  constructor(i, a) {
    super(a);
    k(this, il);
    k(this, Ec);
    A(this, Ec, i), A(this, il, 0);
  }
  get maxDistance() {
    return v(this, il);
  }
  clear() {
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.grab;
    a && (A(this, il, a.distance), i.retina.grabModeDistance = a.distance * i.retina.pixelRatio);
  }
  interact(i) {
    var p;
    const a = this.container, r = a.actualOptions, u = r.interactivity;
    if (!(u != null && u.modes.grab) || !u.events.onHover.enable || i.status !== la)
      return;
    const c = i.mouse.position;
    if (!c)
      return;
    const f = a.retina.grabModeDistance;
    if (!f || f < r3)
      return;
    const m = a.particles.grid.queryCircle(c, f, (g) => this.isEnabled(i, g));
    for (const g of m) {
      const y = g.getPosition(), b = Oo(y, c);
      if (b > f)
        continue;
      const S = u.modes.grab.links, T = S.opacity, C = T - b * T / f;
      if (C <= l3)
        continue;
      const R = S.color ?? ((p = g.options.links) == null ? void 0 : p.color);
      if (!a.particles.grabLineColor && R) {
        const B = u.modes.grab.links;
        a.particles.grabLineColor = GM(v(this, Ec), R, B.blink, B.consent);
      }
      const z = Jy(g, void 0, a.particles.grabLineColor);
      z && a3(a, g, z, C, c);
    }
  }
  isEnabled(i, a) {
    var f;
    const r = this.container, u = i.mouse, c = (f = (a == null ? void 0 : a.interactivity) ?? r.actualOptions.interactivity) == null ? void 0 : f.events;
    return !!(c != null && c.onHover.enable) && !!u.position && Zt(o3, c.onHover.mode);
  }
  loadModeOptions(i, ...a) {
    Re(i, "grab", n3, ...a);
  }
  reset() {
  }
}
il = new WeakMap(), Ec = new WeakMap();
async function c3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalGrab", (r) => Promise.resolve(new u3(t.pluginManager, r)));
  });
}
class f3 {
  constructor() {
    w(this, "force", 2);
    w(this, "smooth", 10);
  }
  load(t) {
    gt(t) || (q(this, "force", t.force), q(this, "smooth", t.smooth));
  }
}
const h3 = "parallax";
var hd, hT;
class d3 extends Yn {
  constructor(i) {
    super(i);
    k(this, hd);
    w(this, "maxDistance", 0);
  }
  clear() {
  }
  init() {
  }
  interact(i) {
    for (const a of this.container.particles.filter((r) => this.isEnabled(i, r)))
      L(this, hd, hT).call(this, i, a);
  }
  isEnabled(i, a) {
    var f;
    const r = this.container, u = i.mouse, c = (f = (a == null ? void 0 : a.interactivity) ?? r.actualOptions.interactivity) == null ? void 0 : f.events;
    return !!(c != null && c.onHover.enable) && !!u.position && Zt(h3, c.onHover.mode);
  }
  loadModeOptions(i, ...a) {
    Re(i, "parallax", f3, ...a);
  }
  reset() {
  }
}
hd = new WeakSet(), hT = function(i, a) {
  var C;
  if (!this.isEnabled(i, a))
    return;
  const r = this.container, u = r.actualOptions, c = (C = u.interactivity) == null ? void 0 : C.modes.parallax;
  if (!c)
    return;
  const f = c.force, m = i.mouse.position;
  if (!m)
    return;
  const p = r.canvas.size, g = {
    x: p.width * bt,
    y: p.height * bt
  }, y = c.smooth, b = a.getRadius() / f, S = {
    x: (m.x - g.x) * b,
    y: (m.y - g.y) * b
  }, { offset: T } = a;
  T.x += (S.x - T.x) / y, T.y += (S.y - T.y) / y;
};
async function m3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalParallax", (r) => Promise.resolve(new d3(r)));
  });
}
const l1 = "pause";
class p3 extends Yn {
  constructor(i) {
    super(i);
    w(this, "handleClickMode");
    w(this, "maxDistance", 0);
    this.handleClickMode = (a) => {
      if (a !== l1)
        return;
      const r = this.container;
      r.animationStatus ? r.pause() : r.play();
    };
  }
  clear() {
  }
  init() {
  }
  interact() {
  }
  isEnabled(i, a) {
    var f;
    const r = this.container, u = r.actualOptions, c = (f = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : f.events;
    return !!c && Zt(l1, c.onClick.mode);
  }
  reset() {
  }
}
async function g3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalPause", (r) => Promise.resolve(new p3(r)));
  });
}
class y3 {
  constructor() {
    w(this, "default", !0);
    w(this, "groups", []);
    w(this, "particles");
    w(this, "quantity", 4);
  }
  load(t) {
    gt(t) || (q(this, "default", t.default), t.groups !== void 0 && (this.groups = t.groups.map((i) => i)), this.groups.length || (this.default = !0), Qt(this, "quantity", t.quantity), this.particles = Gn(t.particles, (i) => bn({}, i)));
  }
}
const u1 = "push", v3 = 0;
class b3 extends Yn {
  constructor(i) {
    super(i);
    w(this, "handleClickMode");
    w(this, "maxDistance", 0);
    this.handleClickMode = (a, r) => {
      var S;
      if (a !== u1)
        return;
      const u = this.container, c = u.actualOptions, f = (S = c.interactivity) == null ? void 0 : S.modes.push;
      if (!f)
        return;
      const m = ht(f.quantity);
      if (m <= v3)
        return;
      const p = Md([void 0, ...f.groups]), g = p !== void 0 ? u.actualOptions.particles.groups[p] : void 0, y = Vn(f.particles), b = bn(g, y);
      u.particles.push(m, r.mouse.position, b, p);
    };
  }
  clear() {
  }
  init() {
  }
  interact() {
  }
  isEnabled(i, a) {
    var m;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (m = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : m.events;
    return !!f && c.clicking && c.inside && !!c.position && Zt(u1, f.onClick.mode);
  }
  loadModeOptions(i, ...a) {
    Re(i, "push", y3, ...a);
  }
  reset() {
  }
}
async function x3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalPush", (r) => Promise.resolve(new b3(r)));
  });
}
class S3 {
  constructor() {
    w(this, "quantity", 2);
  }
  load(t) {
    gt(t) || Qt(this, "quantity", t.quantity);
  }
}
const c1 = "remove";
class w3 extends Yn {
  constructor(i) {
    super(i);
    w(this, "handleClickMode");
    w(this, "maxDistance", 0);
    this.handleClickMode = (a) => {
      var f, m;
      const r = this.container, u = r.actualOptions;
      if (!((f = u.interactivity) != null && f.modes.remove) || a !== c1)
        return;
      const c = ht(u.interactivity.modes.remove.quantity);
      for (let p = 0; p < c; p++)
        (m = r.particles.get(p)) == null || m.destroy();
    };
  }
  clear() {
  }
  init() {
  }
  interact() {
  }
  isEnabled(i, a) {
    var m;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (m = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : m.events;
    return !!f && c.clicking && c.inside && !!c.position && Zt(c1, f.onClick.mode);
  }
  loadModeOptions(i, ...a) {
    Re(i, "remove", S3, ...a);
  }
  reset() {
  }
}
async function M3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalRemove", (r) => Promise.resolve(new w3(r)));
  });
}
class dT {
  constructor() {
    w(this, "distance", 200);
    w(this, "duration", 0.4);
    w(this, "easing", "ease-out-quad");
    w(this, "factor", 100);
    w(this, "maxSpeed", 50);
    w(this, "restore");
    w(this, "speed", 1);
    this.restore = {
      enable: !1,
      delay: 0,
      speed: 0.08,
      follow: !0
    };
  }
  load(t) {
    gt(t) || (q(this, "distance", t.distance), q(this, "duration", t.duration), q(this, "easing", t.easing), q(this, "factor", t.factor), q(this, "speed", t.speed), q(this, "maxSpeed", t.maxSpeed), t.restore !== void 0 && (this.restore.enable = t.restore.enable ?? this.restore.enable, this.restore.delay = t.restore.delay ?? this.restore.delay, this.restore.speed = t.restore.speed ?? this.restore.speed, this.restore.follow = t.restore.follow ?? this.restore.follow));
  }
}
class T3 extends dT {
  constructor() {
    super(...arguments);
    w(this, "selectors", []);
  }
  load(i) {
    super.load(i), !gt(i) && q(this, "selectors", i.selectors);
  }
}
class C3 extends dT {
  constructor() {
    super(...arguments);
    w(this, "divs");
  }
  load(i) {
    super.load(i), !gt(i) && (this.divs = Gn(i.divs, (a) => {
      const r = new T3();
      return r.load(a), r;
    }));
  }
}
const za = "repulse", E3 = 0, A3 = 6, D3 = 3, R3 = 2, O3 = 0, z3 = 0, k3 = 1, V3 = 1e-3, P3 = 1, f1 = 0.5;
var Vs, Za, sl, Qa, Ac, gi, He, mT, pT, Jg, gT, yT, ty;
class L3 extends Yn {
  constructor(i, a) {
    super(a);
    k(this, He);
    w(this, "handleClickMode");
    k(this, Vs);
    k(this, Za);
    k(this, sl);
    k(this, Qa);
    k(this, Ac);
    k(this, gi);
    A(this, Ac, i), A(this, sl, 0), A(this, Qa, Qe.origin), A(this, Za, /* @__PURE__ */ new Set()), A(this, Vs, Qe.origin), A(this, gi, /* @__PURE__ */ new Map()), a.repulse ?? (a.repulse = { particles: [] }), this.handleClickMode = (r, u) => {
      var p;
      const c = this.container.actualOptions, f = (p = c.interactivity) == null ? void 0 : p.modes.repulse;
      if (!f || r !== za)
        return;
      a.repulse ?? (a.repulse = { particles: [] });
      const m = a.repulse;
      m.clicking = !0, m.count = 0;
      for (const g of a.repulse.particles)
        this.isEnabled(u, g) && g.velocity.setTo(g.initialVelocity);
      m.particles = [], m.finish = !1, setTimeout(() => {
        a.destroyed || (m.clicking = !1);
      }, f.duration * Ae);
    };
  }
  get maxDistance() {
    return v(this, sl);
  }
  clear() {
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.repulse;
    a && (A(this, sl, a.distance), i.retina.repulseModeDistance = a.distance * i.retina.pixelRatio);
  }
  interact(i) {
    var T;
    v(this, Za).clear();
    const a = this.container, r = a.actualOptions, u = i.status === la, c = (T = r.interactivity) == null ? void 0 : T.events;
    if (!c)
      return;
    const f = c.onHover, m = f.enable, p = f.mode, g = c.onClick, y = g.enable, b = g.mode, S = c.onDiv;
    u && m && Zt(za, p) ? L(this, He, pT).call(this, i) : y && Zt(za, b) ? L(this, He, mT).call(this, i) : Ed(za, S, (C, R) => {
      L(this, He, yT).call(this, i, C, R);
    }), L(this, He, gT).call(this);
  }
  isEnabled(i, a) {
    var T;
    const r = this.container, u = r.actualOptions, c = i.mouse, f = (T = (a == null ? void 0 : a.interactivity) ?? u.interactivity) == null ? void 0 : T.events;
    if (!f)
      return !1;
    const m = f.onDiv, p = f.onHover, g = f.onClick, y = Cd(za, m);
    if (!(y || p.enable && c.position || g.enable && c.clickPosition))
      return !1;
    const b = p.mode, S = g.mode;
    return Zt(za, b) || Zt(za, S) || y;
  }
  loadModeOptions(i, ...a) {
    Re(i, "repulse", C3, ...a);
  }
  reset() {
  }
}
Vs = new WeakMap(), Za = new WeakMap(), sl = new WeakMap(), Qa = new WeakMap(), Ac = new WeakMap(), gi = new WeakMap(), He = new WeakSet(), mT = function(i) {
  var c;
  const a = this.container, r = (c = a.actualOptions.interactivity) == null ? void 0 : c.modes.repulse;
  if (!r)
    return;
  const u = a.repulse ?? { particles: [] };
  if (u.finish || (u.count ?? (u.count = 0), u.count++, u.count === a.particles.count && (u.finish = !0)), u.clicking) {
    const f = a.retina.repulseModeDistance;
    if (!f || f < E3)
      return;
    const m = Math.pow(f / A3, D3), p = i.mouse.clickPosition;
    if (p === void 0)
      return;
    const g = new be(p.x, p.y, m), y = a.particles.grid.query(g, (b) => this.isEnabled(i, b));
    for (const b of y) {
      const { dx: S, dy: T, distance: C } = _n(p, b.position), R = C ** R3, z = r.speed, B = -m * z / R;
      R <= m && (L(this, He, ty).call(this, b), u.particles.push(b), v(this, Vs).x = S, v(this, Vs).y = T, v(this, Vs).length = B, b.velocity.setTo(v(this, Vs)));
    }
  } else if (u.clicking === !1) {
    for (const f of u.particles)
      f.velocity.setTo(f.initialVelocity);
    u.particles = [];
  }
}, pT = function(i) {
  const a = this.container, r = i.mouse.position, u = a.retina.repulseModeDistance;
  !u || u < O3 || !r || L(this, He, Jg).call(this, i, r, u, new be(r.x, r.y, u));
}, Jg = function(i, a, r, u, c) {
  var R;
  const f = this.container, m = f.particles.grid.query(u, (z) => this.isEnabled(i, z)), p = (R = f.actualOptions.interactivity) == null ? void 0 : R.modes.repulse;
  if (!p)
    return;
  const { easing: g, speed: y, factor: b, maxSpeed: S } = p, T = v(this, Ac).getEasing(g), C = ((c == null ? void 0 : c.speed) ?? y) * b;
  for (const z of m) {
    const { dx: B, dy: H, distance: X } = _n(z.position, a), Q = Nn(T(k3 - X / r) * C, z3, S);
    v(this, Qa).x = X ? B / X * Q : C, v(this, Qa).y = X ? H / X * Q : C, L(this, He, ty).call(this, z), z.position.addTo(v(this, Qa));
  }
}, gT = function() {
  var c, f;
  const i = (f = (c = this.container.actualOptions.interactivity) == null ? void 0 : c.modes.repulse) == null ? void 0 : f.restore;
  if (!(i != null && i.enable) || !v(this, gi).size)
    return;
  const a = Date.now(), r = i.delay * Ae, u = Math.max(V3, Math.min(P3, i.speed));
  for (const [m, p] of v(this, gi)) {
    if (v(this, Za).has(m))
      continue;
    if (m.destroyed) {
      v(this, gi).delete(m);
      continue;
    }
    const g = p.target;
    if (a - p.lastInteractionTime < r)
      continue;
    i.follow && m.options.move.enable && (g.x += m.velocity.x, g.y += m.velocity.y, g.z += m.velocity.z);
    const y = g.x - m.position.x, b = g.y - m.position.y, S = g.z - m.position.z;
    if (m.position.x += y * u, m.position.y += b * u, m.position.z += S * u, Math.abs(y) <= f1 && Math.abs(b) <= f1) {
      m.position.x = g.x, m.position.y = g.y, m.position.z = g.z, v(this, gi).delete(m);
      continue;
    }
  }
}, yT = function(i, a, r) {
  var m;
  const u = this.container, c = (m = u.actualOptions.interactivity) == null ? void 0 : m.modes.repulse;
  if (!c)
    return;
  const f = Un().querySelectorAll(a);
  f.length && f.forEach((p) => {
    const g = p, y = u.retina.pixelRatio, b = {
      x: (g.offsetLeft + g.offsetWidth * bt) * y,
      y: (g.offsetTop + g.offsetHeight * bt) * y
    }, S = g.offsetWidth * bt * y, T = r.type === Po.circle ? new be(b.x, b.y, S) : new ni(g.offsetLeft * y, g.offsetTop * y, g.offsetWidth * y, g.offsetHeight * y), C = c.divs, R = tT(C, g);
    L(this, He, Jg).call(this, i, b, S, T, R);
  });
}, ty = function(i) {
  var c, f;
  v(this, Za).add(i);
  const a = (f = (c = this.container.actualOptions.interactivity) == null ? void 0 : c.modes.repulse) == null ? void 0 : f.restore;
  if (!(a != null && a.enable))
    return;
  const r = Date.now();
  let u = v(this, gi).get(i);
  u || (u = {
    target: i.position.copy(),
    lastInteractionTime: r
  }, v(this, gi).set(i, u)), u.lastInteractionTime = r, a.follow && i.options.move.enable && (u.target.x += i.velocity.x, u.target.y += i.velocity.y, u.target.z += i.velocity.z);
};
async function _3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var a;
    $e(t);
    const i = t.pluginManager;
    (a = i.addInteractor) == null || a.call(i, "externalRepulse", (r) => Promise.resolve(new L3(i, r)));
  });
}
class B3 {
  constructor() {
    w(this, "factor", 3);
    w(this, "radius", 200);
  }
  load(t) {
    gt(t) || (q(this, "factor", t.factor), q(this, "radius", t.radius));
  }
}
class N3 {
  constructor() {
    w(this, "enabled", !1);
    w(this, "id", "slow");
    w(this, "priority", 100);
    w(this, "speedFactor", 1);
  }
}
const h1 = "slow", U3 = 0;
var al, Ps;
class j3 extends Yn {
  constructor(i) {
    super(i);
    k(this, al);
    k(this, Ps, /* @__PURE__ */ new WeakMap());
    A(this, al, 0);
  }
  get maxDistance() {
    return v(this, al);
  }
  clear(i, a, r) {
    const u = v(this, Ps).get(i);
    u != null && u.enabled && !r || (i.removeModifier(h1), v(this, Ps).delete(i));
  }
  getOrCreateModifier(i) {
    let a = v(this, Ps).get(i);
    return a || (a = new N3(), v(this, Ps).set(i, a), i.addModifier(a)), a;
  }
  init() {
    var r;
    const i = this.container, a = (r = i.actualOptions.interactivity) == null ? void 0 : r.modes.slow;
    a && (A(this, al, a.radius), i.retina.slowModeRadius = a.radius * i.retina.pixelRatio);
  }
  interact() {
  }
  isEnabled(i, a) {
    var f;
    const r = this.container, u = i.mouse, c = (f = (a == null ? void 0 : a.interactivity) ?? r.actualOptions.interactivity) == null ? void 0 : f.events;
    return !!(c != null && c.onHover.enable) && !!u.position && Zt(h1, c.onHover.mode);
  }
  loadModeOptions(i, ...a) {
    Re(i, "slow", B3, ...a);
  }
  reset(i, a) {
    var C;
    const r = v(this, Ps).get(a);
    r && (r.enabled = !1);
    const u = this.container, c = u.actualOptions, f = i.mouse.position, m = u.retina.slowModeRadius, p = (C = c.interactivity) == null ? void 0 : C.modes.slow;
    if (!p || !m || m < U3 || !f)
      return;
    const g = a.getPosition(), y = Oo(f, g), b = y / m, S = p.factor;
    if (y > m)
      return;
    const T = this.getOrCreateModifier(a);
    T.enabled = !0, T.speedFactor = b / S;
  }
}
al = new WeakMap(), Ps = new WeakMap();
async function H3(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "externalSlow", (r) => Promise.resolve(new j3(r)));
  });
}
const vT = ["image", "images"], q3 = 0, G3 = 1, Y3 = /(#(?:[0-9a-f]{2}){2,4}|(#[0-9a-f]{3})|(rgb|hsl)a?\((-?\d+%?[,\s]+){2,3}\s*[\d.]+%?\))|currentcolor/gi;
function X3(n, t, i, a = !1) {
  const { svgData: r } = n;
  if (!r)
    return "";
  const u = oc(t, a, i);
  if (r.includes("fill"))
    return r.replaceAll(Y3, () => u);
  const c = r.indexOf(">");
  return `${r.substring(q3, c)} fill="${u}"${r.substring(c)}`;
}
async function nv(n) {
  return new Promise((t) => {
    n.loading = !0;
    const i = new Image();
    n.element = i, i.addEventListener("load", () => {
      n.loading = !1, t();
    }), i.addEventListener("error", () => {
      n.element = void 0, n.error = !0, n.loading = !1, zo().error(`Error loading image: ${n.source}`), t();
    }), i.src = n.source;
  });
}
async function F3(n) {
  if (n.type !== "svg") {
    await nv(n);
    return;
  }
  n.loading = !0;
  const t = await fetch(n.source);
  t.ok ? n.svgData = await t.text() : (zo().error("Image not found"), n.error = !0), n.loading = !1;
}
function Z3(n, t, i, a, r = !1) {
  var f;
  const u = X3(n, i, ((f = a.opacity) == null ? void 0 : f.value) ?? G3, r), c = {
    color: i,
    data: {
      ...n,
      svgData: u
    },
    loaded: !1,
    ratio: t.width / t.height,
    replaceColor: t.replaceColor,
    source: t.src
  };
  return new Promise((m) => {
    const p = new Blob([u], { type: "image/svg+xml" }), g = URL.createObjectURL(p), y = new Image();
    y.addEventListener("load", () => {
      c.loaded = !0, c.element = y, m(c), URL.revokeObjectURL(g);
    });
    const b = async () => {
      URL.revokeObjectURL(g);
      const S = {
        ...n,
        error: !1,
        loading: !0
      };
      await nv(S), c.loaded = !0, c.element = S.element, m(c);
    };
    y.addEventListener("error", () => void b()), y.src = g;
  });
}
const Q3 = 12;
var Dc, yi, dd;
class K3 {
  constructor(t, i) {
    k(this, Dc);
    k(this, yi);
    k(this, dd, async (t, i) => {
      if (!v(this, yi).loadImage)
        throw new Error("Image shape not initialized");
      await v(this, yi).loadImage(t, {
        name: i.name,
        replaceColor: i.replaceColor,
        src: i.src
      });
    });
    A(this, yi, t), A(this, Dc, i);
  }
  draw(t) {
    const { context: i, radius: a, particle: r, opacity: u } = t, c = r.image, f = c == null ? void 0 : c.element;
    if (c) {
      if (i.globalAlpha = u, f) {
        const m = c.ratio, p = {
          x: -a,
          y: -a
        }, g = a * Bt;
        i.drawImage(f, p.x, p.y, g, g / m);
      }
      i.globalAlpha = LR;
    }
  }
  getSidesCount() {
    return Q3;
  }
  async init(t) {
    const i = t.actualOptions;
    if (!i.preload || !v(this, yi).loadImage)
      return;
    const a = [];
    for (const r of i.preload)
      a.push(v(this, yi).loadImage(t, r));
    await Promise.all(a);
  }
  loadShape(t) {
    var c, f;
    const i = v(this, Dc);
    if (!t.shape || !vT.includes(t.shape))
      return;
    const a = t.shapeData;
    if (!a)
      return;
    const r = (f = (c = v(this, yi)).getImages) == null ? void 0 : f.call(c, i);
    r != null && r.find((m) => m.name === a.name || m.source === a.src) || v(this, dd).call(this, i, a).then(() => {
      this.loadShape(t);
    });
  }
  particleInit(t, i) {
    var m, p;
    if (i.shape !== "image" && i.shape !== "images")
      return;
    const a = (p = (m = v(this, yi)).getImages) == null ? void 0 : p.call(m, t), r = i.shapeData;
    if (!r)
      return;
    const u = i.getFillColor(), c = a == null ? void 0 : a.find((g) => g.name === r.name || g.source === r.src);
    if (!c)
      return;
    const f = r.replaceColor;
    if (c.loading) {
      setTimeout(() => {
        this.particleInit(t, i);
      });
      return;
    }
    (async () => {
      let g;
      c.svgData && u ? g = await Z3(c, r, u, i, t.hdr) : g = {
        color: u,
        data: c,
        element: c.element,
        loaded: !0,
        ratio: r.width && r.height ? r.width / r.height : c.ratio ?? jg,
        replaceColor: f,
        source: r.src
      }, g.ratio || (g.ratio = 1);
      const y = r.close ?? i.shapeClose, b = {
        image: g,
        close: y
      };
      i.image = b.image, i.shapeClose = b.close;
    })();
  }
}
Dc = new WeakMap(), yi = new WeakMap(), dd = new WeakMap();
class I3 {
  constructor() {
    w(this, "height");
    w(this, "name");
    w(this, "replaceColor");
    w(this, "src", "");
    w(this, "width");
  }
  load(t) {
    gt(t) || (q(this, "height", t.height), q(this, "name", t.name), q(this, "replaceColor", t.replaceColor), q(this, "src", t.src), q(this, "width", t.width));
  }
}
var Rc;
class $3 {
  constructor(t) {
    w(this, "id", "image-preloader");
    k(this, Rc);
    A(this, Rc, t);
  }
  async getPlugin(t) {
    const { ImagePreloaderInstance: i } = await Promise.resolve().then(() => _6);
    return new i(v(this, Rc), t);
  }
  loadOptions(t, i, a) {
    if (!(a != null && a.preload))
      return;
    i.preload ?? (i.preload = []);
    const r = i.preload;
    for (const u of a.preload) {
      const c = r.find((f) => f.name === u.name || f.src === u.src);
      if (c)
        c.load(u);
      else {
        const f = new I3();
        f.load(u), r.push(f);
      }
    }
  }
  needsPlugin() {
    return !0;
  }
}
Rc = new WeakMap();
const W3 = 3;
function J3(n) {
  n.getImages ?? (n.getImages = (t) => {
    n.images ?? (n.images = /* @__PURE__ */ new Map());
    let i = n.images.get(t);
    return i || (i = [], n.images.set(t, i)), i;
  }), n.loadImage ?? (n.loadImage = async (t, i) => {
    if (!n.getImages)
      throw new Error("No images collection found");
    if (!i.name && !i.src)
      throw new Error("No image source provided");
    n.images ?? (n.images = /* @__PURE__ */ new Map());
    const a = n.getImages(t);
    if (!a.some((r) => r.name === i.name || r.source === i.src))
      try {
        const r = {
          name: i.name ?? i.src,
          source: i.src,
          type: i.src.substring(i.src.length - W3),
          error: !1,
          loading: !0,
          replaceColor: i.replaceColor,
          ratio: i.width && i.height ? i.width / i.height : void 0
        };
        a.push(r), n.images.set(t, a);
        let u;
        i.replaceColor ? u = F3 : u = nv, await u(r);
      } catch {
        throw new Error(`${i.name ?? i.src} not found`);
      }
  });
}
async function tk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    J3(t), t.pluginManager.addPlugin(new $3(t)), t.pluginManager.addShape(vT, (i) => Promise.resolve(new K3(t, i)));
  });
}
class ek extends Bo {
  constructor() {
    super(...arguments);
    w(this, "sync", !1);
  }
  load(i) {
    gt(i) || (super.load(i), q(this, "sync", i.sync));
  }
}
class nk extends Bo {
  constructor() {
    super(...arguments);
    w(this, "sync", !1);
  }
  load(i) {
    gt(i) || (super.load(i), q(this, "sync", i.sync));
  }
}
class ik {
  constructor() {
    w(this, "count", 0);
    w(this, "delay", new ek());
    w(this, "duration", new nk());
  }
  load(t) {
    gt(t) || (q(this, "count", t.count), this.delay.load(t.delay), this.duration.load(t.duration));
  }
}
const Cr = 0, sk = -1, d1 = 0, m1 = 0;
function ak(n, t, i) {
  if (!n.life)
    return;
  const a = n.life;
  let r = !1;
  if (n.spawning)
    if (a.delayTime += t.value, a.delayTime >= n.life.delay)
      r = !0, n.spawning = !1, a.delayTime = Cr, a.time = Cr;
    else
      return;
  if (a.duration === sk || (r ? a.time = Cr : a.time += t.value, a.time < a.duration))
    return;
  if (a.time = Cr, n.life.count > d1 && n.life.count--, n.life.count === d1) {
    n.destroy();
    return;
  }
  const u = Ro(m1, i.width), c = Ro(m1, i.width);
  n.position.x = Oi(u), n.position.y = Oi(c), n.spawning = !0, a.delayTime = Cr, a.time = Cr, n.reset();
  const f = n.options.life;
  f && (a.delay = ht(f.delay.value) * Ae, a.duration = ht(f.duration.value) * Ae);
}
const ka = 0, p1 = 1, g1 = -1;
var ol;
class ok {
  constructor(t) {
    k(this, ol);
    A(this, ol, t);
  }
  init(t) {
    const i = v(this, ol), a = t.options, r = a.life;
    if (!r)
      return;
    const u = r.delay.sync ? p1 : Yt(), c = r.duration.sync ? p1 : Yt();
    t.life = {
      delay: i.retina.reduceFactor ? ht(r.delay.value) * u / i.retina.reduceFactor * Ae : ka,
      delayTime: ka,
      duration: i.retina.reduceFactor ? ht(r.duration.value) * c / i.retina.reduceFactor * Ae : ka,
      time: ka,
      count: r.count
    }, t.life.duration <= ka && (t.life.duration = g1), t.life.count <= ka && (t.life.count = g1), t.spawning = t.life.delay > ka;
  }
  isEnabled(t) {
    return !t.destroyed;
  }
  loadOptions(t, ...i) {
    Re(t, "life", ik, ...i);
  }
  update(t, i) {
    !this.isEnabled(t) || !t.life || ak(t, i, v(this, ol).canvas.size);
  }
}
ol = new WeakMap();
async function rk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addParticleUpdater("life", (i) => Promise.resolve(new ok(i)));
  });
}
function lk(n) {
  const { context: t, particle: i, radius: a } = n, r = i.shapeData, u = 0;
  t.moveTo(-a, u), t.lineTo(a, u), t.lineCap = (r == null ? void 0 : r.cap) ?? "butt";
}
const uk = 1;
class ck {
  draw(t) {
    lk(t);
  }
  getSidesCount() {
    return uk;
  }
}
async function fk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(["line"], () => Promise.resolve(new ck()));
  });
}
class hk {
  constructor() {
    w(this, "distance", 200);
    w(this, "enable", !1);
    w(this, "rotate");
    this.rotate = {
      x: 3e3,
      y: 3e3
    };
  }
  load(t) {
    if (!gt(t) && (Qt(this, "distance", t.distance), q(this, "enable", t.enable), t.rotate)) {
      const i = t.rotate.x;
      i !== void 0 && (this.rotate.x = i);
      const a = t.rotate.y;
      a !== void 0 && (this.rotate.y = a);
    }
  }
}
const y1 = 1e3, dk = 1;
var Ka;
class mk extends ev {
  constructor(i) {
    super(i);
    k(this, Ka);
    A(this, Ka, 0);
  }
  get maxDistance() {
    return v(this, Ka);
  }
  clear() {
  }
  init() {
  }
  interact(i) {
    var f, m;
    if (!((f = i.options.attract) != null && f.enable))
      return;
    const a = this.container;
    if (gt(i.attractDistance)) {
      const p = ht(i.options.attract.distance);
      p > v(this, Ka) && A(this, Ka, p), i.attractDistance = p * a.retina.pixelRatio;
    }
    const r = i.attractDistance, u = i.getPosition(), c = a.particles.grid.queryCircle(u, r);
    for (const p of c) {
      if (i === p || !((m = p.options.attract) != null && m.enable) || p.destroyed || p.spawning)
        continue;
      const g = p.getPosition(), { dx: y, dy: b } = _n(u, g), S = i.options.attract.rotate, T = y / (S.x * y1), C = b / (S.y * y1), R = p.size.value / i.size.value, z = dk / R;
      i.velocity.x -= T * R, i.velocity.y -= C * R, p.velocity.x += T * z, p.velocity.y += C * z;
    }
  }
  isEnabled(i) {
    var a;
    return ((a = i.options.attract) == null ? void 0 : a.enable) ?? !1;
  }
  loadParticlesOptions(i, ...a) {
    Re(i, "attract", hk, ...a);
  }
  reset() {
  }
}
Ka = new WeakMap();
async function pk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "particlesAttract", (r) => Promise.resolve(new mk(r)));
  });
}
var Ur;
(function(n) {
  n.absorb = "absorb", n.bounce = "bounce", n.destroy = "destroy";
})(Ur || (Ur = {}));
class gk {
  constructor() {
    w(this, "speed", 2);
  }
  load(t) {
    gt(t) || q(this, "speed", t.speed);
  }
}
class yk {
  constructor() {
    w(this, "enable", !0);
    w(this, "retries", 0);
  }
  load(t) {
    gt(t) || (q(this, "enable", t.enable), q(this, "retries", t.retries));
  }
}
class vk {
  constructor() {
    w(this, "absorb", new gk());
    w(this, "bounce", new PM());
    w(this, "enable", !1);
    w(this, "maxSpeed", 50);
    w(this, "mode", Ur.bounce);
    w(this, "overlap", new yk());
  }
  load(t) {
    gt(t) || (this.absorb.load(t.absorb), this.bounce.load(t.bounce), q(this, "enable", t.enable), Qt(this, "maxSpeed", t.maxSpeed), q(this, "mode", t.mode), this.overlap.load(t.overlap));
  }
}
const bk = 0;
function v1(n, t, i, a, r, u) {
  if (!n.options.collisions || !i.options.collisions)
    return;
  const c = n.options.collisions.absorb.speed, f = Nn(c * r.factor, bk, a);
  n.size.value = Math.sqrt(t * t + f * f), i.size.value -= f, i.size.value <= u && (i.size.value = 0, i.destroy());
}
function xk(n, t, i, a) {
  const r = n.getRadius(), u = t.getRadius();
  !r && u ? n.destroy() : r && !u ? t.destroy() : r && u && (r >= u ? v1(n, r, t, u, i, a) : v1(t, u, n, r, i, a));
}
const Sk = 1e-6, wk = 1e-4, Mk = 1, b1 = (n) => {
  n.options.collisions && (n.collisionMaxSpeed ?? (n.collisionMaxSpeed = ht(n.options.collisions.maxSpeed)), n.velocity.length > n.collisionMaxSpeed && (n.velocity.length = n.collisionMaxSpeed));
};
function bT(n, t) {
  const i = n.getMass(), a = t.getMass(), r = n.velocity.length, u = t.velocity.length, c = i * r * r + a * u * u;
  DM(Gg(n), Gg(t));
  const f = n.velocity.length, m = t.velocity.length, p = i * f * f + a * m * m;
  if (p > c * Sk) {
    const g = Math.sqrt(c / p);
    Math.abs(g - Mk) > wk && (n.velocity.length = f * g, t.velocity.length = m * g);
  }
  b1(n), b1(t);
}
function Tk(n, t) {
  !n.unbreakable && !t.unbreakable && bT(n, t);
  const i = n.getRadius(), a = t.getRadius();
  !i && a ? n.destroy() : i && !a ? t.destroy() : i && a && (n.getRadius() >= t.getRadius() ? t : n).destroy();
}
function Ck(n, t, i, a) {
  if (!(!n.options.collisions || !t.options.collisions))
    switch (n.options.collisions.mode) {
      case Ur.absorb: {
        xk(n, t, i, a);
        break;
      }
      case Ur.bounce: {
        bT(n, t);
        break;
      }
      case Ur.destroy: {
        Tk(n, t);
        break;
      }
    }
}
class Ek extends ev {
  constructor(i) {
    super(i);
    w(this, "maxDistance");
    this.maxDistance = 0;
  }
  clear() {
  }
  init() {
  }
  interact(i, a, r) {
    var p, g;
    if (i.destroyed || i.spawning)
      return;
    const u = this.container, c = i.getPosition(), f = i.getRadius(), m = u.particles.grid.queryCircle(c, f * Bt);
    for (const y of m) {
      if (i === y || i.id >= y.id || !((p = i.options.collisions) != null && p.enable) || !((g = y.options.collisions) != null && g.enable) || i.options.collisions.mode !== y.options.collisions.mode || y.destroyed || y.spawning)
        continue;
      const b = y.getPosition(), S = y.getRadius();
      if (Math.abs(Math.round(c.z) - Math.round(b.z)) > f + S)
        continue;
      const T = Oo(c, b), C = f + S;
      T > C || Ck(i, y, r, u.retina.pixelRatio);
    }
  }
  isEnabled(i) {
    var a;
    return !!((a = i.options.collisions) != null && a.enable);
  }
  loadParticlesOptions(i, ...a) {
    Re(i, "collisions", vk, ...a);
  }
  reset() {
  }
}
class Ak {
  constructor() {
    w(this, "id", "overlap");
  }
  async getPlugin(t) {
    const { OverlapPluginInstance: i } = await Promise.resolve().then(() => U6);
    return new i(t);
  }
  loadOptions() {
  }
  needsPlugin() {
    return !0;
  }
}
async function Dk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var i, a;
    $e(t), t.pluginManager.addPlugin(new Ak()), (a = (i = t.pluginManager).addInteractor) == null || a.call(i, "particlesCollisions", (r) => Promise.resolve(new Ek(r)));
  });
}
var rl;
class Rk extends be {
  constructor(i, a, r, u) {
    super(i, a, r);
    k(this, rl);
    A(this, rl, u);
  }
  contains(i) {
    if (super.contains(i))
      return !0;
    const { width: a, height: r } = v(this, rl), { x: u, y: c } = i;
    return super.contains({ x: u - a, y: c }) || super.contains({ x: u + a, y: c }) || super.contains({ x: u, y: c - r }) || super.contains({ x: u, y: c + r }) || super.contains({ x: u - a, y: c - r }) || super.contains({ x: u + a, y: c + r }) || super.contains({ x: u - a, y: c + r }) || super.contains({ x: u + a, y: c - r });
  }
  intersects(i) {
    if (super.intersects(i))
      return !0;
    const { width: a, height: r } = v(this, rl), u = i.position, c = [
      { x: -a, y: 0 },
      { x: a, y: 0 },
      { x: 0, y: -r },
      { x: 0, y: r },
      { x: -a, y: -r },
      { x: a, y: r },
      { x: -a, y: r },
      { x: a, y: -r }
    ];
    for (const f of c) {
      const m = { x: u.x + f.x, y: u.y + f.y };
      let p;
      if (i instanceof be)
        p = new be(m.x, m.y, i.radius);
      else {
        const g = i;
        p = new ni(m.x, m.y, g.size.width, g.size.height);
      }
      if (super.intersects(p))
        return !0;
    }
    return !1;
  }
}
rl = new WeakMap();
class Ok {
  constructor() {
    w(this, "blur", 5);
    w(this, "color", new jn());
    w(this, "enable", !1);
    this.color.value = "#000";
  }
  load(t) {
    gt(t) || (q(this, "blur", t.blur), this.color = jn.create(this.color, t.color), q(this, "enable", t.enable));
  }
}
class zk {
  constructor() {
    w(this, "color");
    w(this, "enable", !1);
    w(this, "frequency", 1);
    w(this, "opacity");
  }
  load(t) {
    gt(t) || (t.color !== void 0 && (this.color = jn.create(this.color, t.color)), q(this, "enable", t.enable), q(this, "frequency", t.frequency), q(this, "opacity", t.opacity));
  }
}
class kk {
  constructor() {
    w(this, "blink", !1);
    w(this, "color", new jn());
    w(this, "consent", !1);
    w(this, "distance", 100);
    w(this, "enable", !1);
    w(this, "frequency", 1);
    w(this, "id");
    w(this, "opacity", 1);
    w(this, "shadow", new Ok());
    w(this, "triangles", new zk());
    w(this, "warp", !1);
    w(this, "width", 1);
    this.color.value = "#fff";
  }
  load(t) {
    gt(t) || (q(this, "id", t.id), q(this, "blink", t.blink), this.color = jn.create(this.color, t.color), q(this, "consent", t.consent), q(this, "distance", t.distance), q(this, "enable", t.enable), q(this, "frequency", t.frequency), q(this, "opacity", t.opacity), this.shadow.load(t.shadow), this.triangles.load(t.triangles), q(this, "width", t.width), q(this, "warp", t.warp));
  }
}
const Vk = 1, Pk = 0;
function Lk(n, t, i) {
  const { dx: a, dy: r } = _n(n, t), u = { x: Math.abs(a), y: Math.abs(r) }, c = {
    x: Math.min(u.x, i.width - u.x),
    y: Math.min(u.y, i.height - u.y)
  };
  return Math.hypot(c.x, c.y);
}
var Ia, Oc, Vl, xT, ST;
class _k extends ev {
  constructor(i, a) {
    super(a);
    k(this, Vl);
    k(this, Ia);
    k(this, Oc);
    A(this, Oc, i), A(this, Ia, 0);
  }
  get maxDistance() {
    return v(this, Ia);
  }
  clear() {
  }
  init() {
    this.container.particles.linksColor = void 0, this.container.particles.linksColors = /* @__PURE__ */ new Map();
  }
  interact(i) {
    if (!i.options.links)
      return;
    i.links = [], i.linksDistance && i.linksDistance > v(this, Ia) && A(this, Ia, i.linksDistance);
    const a = i.getPosition(), r = this.container, u = r.canvas.size;
    if (a.x < Dt.x || a.y < Dt.y || a.x > u.width || a.y > u.height)
      return;
    const c = i.options.links, f = c.opacity, m = i.retina.linksDistance ?? Pk, p = c.warp, g = p ? new Rk(a.x, a.y, m, u) : new be(a.x, a.y, m), y = r.particles.grid.query(g);
    for (const b of y) {
      const S = b.options.links;
      if (i === b || !(S != null && S.enable) || c.id !== S.id || b.spawning || b.destroyed || !b.links || i.links.some((H) => H.destination === b) || b.links.some((H) => H.destination === i))
        continue;
      const T = b.getPosition();
      if (T.x < Dt.x || T.y < Dt.y || T.x > u.width || T.y > u.height)
        continue;
      const C = _n(a, T).distance, R = p && S.warp ? Lk(a, T, u) : C, z = Math.min(C, R);
      if (z > m)
        continue;
      const B = (Vk - z / m) * f;
      L(this, Vl, ST).call(this, i), i.links.push({
        destination: b,
        opacity: B,
        color: L(this, Vl, xT).call(this, i, b),
        isWarped: R < C
      });
    }
  }
  isEnabled(i) {
    var a;
    return !!((a = i.options.links) != null && a.enable);
  }
  loadParticlesOptions(i, ...a) {
    Re(i, "links", kk, ...a);
  }
  reset() {
  }
}
Ia = new WeakMap(), Oc = new WeakMap(), Vl = new WeakSet(), xT = function(i, a) {
  const r = this.container, u = i.options.links;
  if (!u)
    return;
  const c = u.id !== void 0 ? r.particles.linksColors.get(u.id) : r.particles.linksColor;
  return Jy(i, a, c);
}, ST = function(i) {
  if (!i.options.links)
    return;
  const a = this.container, r = i.options.links;
  let u = r.id === void 0 ? a.particles.linksColor : a.particles.linksColors.get(r.id);
  u || (u = GM(v(this, Oc), r.color, r.blink, r.consent), r.id === void 0 ? a.particles.linksColor = u : a.particles.linksColors.set(r.id, u));
};
var zc;
class Bk {
  constructor(t) {
    w(this, "id", "links");
    k(this, zc);
    A(this, zc, t);
  }
  async getPlugin(t) {
    const { LinkInstance: i } = await Promise.resolve().then(() => Y6);
    return new i(v(this, zc), t);
  }
  loadOptions() {
  }
  needsPlugin() {
    return !0;
  }
}
zc = new WeakMap();
async function Nk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    var a;
    const i = t.pluginManager;
    $e(t), i.addPlugin(new Bk(i)), (a = i.addInteractor) == null || a.call(i, "particlesLinks", (r) => Promise.resolve(new _k(i, r)));
  });
}
const x1 = /* @__PURE__ */ new Map(), Uk = 0;
function jk(n) {
  const t = x1.get(n);
  if (t)
    return t;
  const i = oa / n, a = !!(n % Bt), r = (-Math.PI + (a ? Uk : i)) * bt, u = [];
  for (let c = 0; c < n; c++) {
    const f = r + c * i;
    u[c] = {
      x: Math.cos(f),
      y: Math.sin(f)
    };
  }
  return x1.set(n, u), u;
}
function Hk(n, t) {
  const { context: i, radius: a } = n, r = t.count.numerator / t.count.denominator, u = jk(r);
  i.beginPath();
  for (let c = 0; c < u.length; c++) {
    const f = u[c];
    if (!f)
      continue;
    const m = f.x * a, p = f.y * a;
    c ? i.lineTo(m, p) : i.moveTo(m, p);
  }
  i.closePath();
}
const qk = 5;
class wT {
  draw(t) {
    const { particle: i, radius: a } = t, r = this.getSidesData(i, a);
    Hk(t, r);
  }
  getSidesCount(t) {
    const i = t.shapeData;
    return Math.round(ht((i == null ? void 0 : i.sides) ?? qk));
  }
}
const Gk = 2.66, Yk = 3;
class Xk extends wT {
  getSidesData(t, i) {
    const { sides: a } = t;
    return {
      count: {
        denominator: 1,
        numerator: a
      },
      length: i * Gk / (a / Yk)
    };
  }
}
const fg = 3, Fk = 2.66, Zk = 3;
class Qk extends wT {
  getSidesCount() {
    return fg;
  }
  getSidesData(t, i) {
    return {
      count: {
        denominator: 1,
        numerator: fg
      },
      length: i * Fk / (fg / Zk)
    };
  }
}
async function Kk(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(["polygon"], () => Promise.resolve(new Xk()));
  });
}
async function Ik(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(["triangle"], () => Promise.resolve(new Qk()));
  });
}
async function $k(n) {
  n.checkVersion("4.3.2"), await Promise.all([
    Kk(n),
    Ik(n)
  ]);
}
class Wk {
  constructor() {
    w(this, "decay", 0);
    w(this, "enable", !1);
    w(this, "speed", 0);
    w(this, "sync", !1);
  }
  load(t) {
    gt(t) || (q(this, "enable", t.enable), Qt(this, "speed", t.speed), Qt(this, "decay", t.decay), q(this, "sync", t.sync));
  }
}
class Jk extends Bo {
  constructor() {
    super(...arguments);
    w(this, "animation", new Wk());
    w(this, "direction", Jn.clockwise);
    w(this, "path", !1);
  }
  load(i) {
    gt(i) || (super.load(i), q(this, "direction", i.direction), this.animation.load(i.animation), q(this, "path", i.path));
  }
}
const tV = 360;
var kc;
class eV {
  constructor(t) {
    k(this, kc);
    A(this, kc, t);
  }
  init(t) {
    const i = t.options.rotate;
    if (!i)
      return;
    t.rotate = {
      enable: i.animation.enable,
      value: So(ht(i.value)),
      min: 0,
      max: oa
    }, t.pathRotation = i.path;
    let a = i.direction;
    switch (a === Jn.random && (a = Math.floor(Yt() * Bt) > 0 ? Jn.counterClockwise : Jn.clockwise), a) {
      case Jn.counterClockwise:
      case "counterClockwise":
        t.rotate.status = le.decreasing;
        break;
      case Jn.clockwise:
        t.rotate.status = le.increasing;
        break;
    }
    const r = i.animation;
    r.enable && (t.rotate.decay = De - ht(r.decay), t.rotate.velocity = ht(r.speed) / tV * v(this, kc).retina.reduceFactor, r.sync || (t.rotate.velocity *= Yt())), t.rotation = t.rotate.value;
  }
  isEnabled(t) {
    const i = t.options.rotate;
    return i ? !t.destroyed && !t.spawning && (!!i.value || i.animation.enable || i.path) : !1;
  }
  loadOptions(t, ...i) {
    Re(t, "rotate", Jk, ...i);
  }
  update(t, i) {
    this.isEnabled(t) && (t.isRotating = !!t.rotate, t.rotate && (tv(t, t.rotate, !1, ko.none, i), t.rotation = t.rotate.value));
  }
}
kc = new WeakMap();
async function nV(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addParticleUpdater("rotate", (i) => Promise.resolve(new eV(i)));
  });
}
function iV(n) {
  const { context: t, radius: i } = n, a = i * Math.SQRT1_2, r = a * Bt;
  t.rect(-a, -a, r, r);
}
const sV = 4;
class aV {
  draw(t) {
    iV(t);
  }
  getSidesCount() {
    return sV;
  }
}
async function oV(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(["edge", "square"], () => Promise.resolve(new aV()));
  });
}
const rV = 2, Er = { x: 0, y: 0 };
function lV(n) {
  const { context: t, particle: i, radius: a } = n, r = i.sides, u = i.starInset ?? rV;
  t.moveTo(Er.x, Er.y - a);
  for (let c = 0; c < r; c++)
    t.rotate(Math.PI / r), t.lineTo(Er.x, Er.y - a * u), t.rotate(Math.PI / r), t.lineTo(Er.x, Er.y - a);
}
const uV = 2, cV = 5;
class fV {
  draw(t) {
    lV(t);
  }
  getSidesCount(t) {
    const i = t.shapeData;
    return Math.round(ht((i == null ? void 0 : i.sides) ?? cV));
  }
  particleInit(t, i) {
    const a = i.shapeData;
    i.starInset = ht((a == null ? void 0 : a.inset) ?? uV);
  }
}
async function hV(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register((t) => {
    t.pluginManager.addShape(["star"], () => Promise.resolve(new fV()));
  });
}
async function dV(n) {
  n.checkVersion("4.3.2"), await n.pluginManager.register(async (t) => {
    const i = async (a) => {
      await dz(a), await Promise.all([
        m3(a),
        wz(a),
        Oz(a),
        Nz(a),
        Qz(a),
        t3(a),
        c3(a),
        g3(a),
        x3(a),
        M3(a),
        _3(a),
        H3(a),
        pk(a),
        Dk(a),
        Nk(a)
      ]);
    };
    await Promise.all([
      JO(t),
      i(t),
      tz(t),
      sz(t),
      tk(t),
      fk(t),
      $k(t),
      oV(t),
      hV(t),
      rk(t),
      ZM(t),
      nV(t)
    ]);
  });
}
var hg = { exports: {} }, xt = {};
/**
 * @license React
 * react.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var S1;
function mV() {
  if (S1) return xt;
  S1 = 1;
  var n = Symbol.for("react.transitional.element"), t = Symbol.for("react.portal"), i = Symbol.for("react.fragment"), a = Symbol.for("react.strict_mode"), r = Symbol.for("react.profiler"), u = Symbol.for("react.consumer"), c = Symbol.for("react.context"), f = Symbol.for("react.forward_ref"), m = Symbol.for("react.suspense"), p = Symbol.for("react.memo"), g = Symbol.for("react.lazy"), y = Symbol.iterator;
  function b(D) {
    return D === null || typeof D != "object" ? null : (D = y && D[y] || D["@@iterator"], typeof D == "function" ? D : null);
  }
  var S = {
    isMounted: function() {
      return !1;
    },
    enqueueForceUpdate: function() {
    },
    enqueueReplaceState: function() {
    },
    enqueueSetState: function() {
    }
  }, T = Object.assign, C = {};
  function R(D, Y, et) {
    this.props = D, this.context = Y, this.refs = C, this.updater = et || S;
  }
  R.prototype.isReactComponent = {}, R.prototype.setState = function(D, Y) {
    if (typeof D != "object" && typeof D != "function" && D != null)
      throw Error(
        "takes an object of state variables to update or a function which returns an object of state variables."
      );
    this.updater.enqueueSetState(this, D, Y, "setState");
  }, R.prototype.forceUpdate = function(D) {
    this.updater.enqueueForceUpdate(this, D, "forceUpdate");
  };
  function z() {
  }
  z.prototype = R.prototype;
  function B(D, Y, et) {
    this.props = D, this.context = Y, this.refs = C, this.updater = et || S;
  }
  var H = B.prototype = new z();
  H.constructor = B, T(H, R.prototype), H.isPureReactComponent = !0;
  var X = Array.isArray, Q = { H: null, A: null, T: null, S: null, V: null }, ut = Object.prototype.hasOwnProperty;
  function st(D, Y, et, tt, rt, Ot) {
    return et = Ot.ref, {
      $$typeof: n,
      type: D,
      key: Y,
      ref: et !== void 0 ? et : null,
      props: Ot
    };
  }
  function $(D, Y) {
    return st(
      D.type,
      Y,
      void 0,
      void 0,
      void 0,
      D.props
    );
  }
  function lt(D) {
    return typeof D == "object" && D !== null && D.$$typeof === n;
  }
  function nt(D) {
    var Y = { "=": "=0", ":": "=2" };
    return "$" + D.replace(/[=:]/g, function(et) {
      return Y[et];
    });
  }
  var vt = /\/+/g;
  function it(D, Y) {
    return typeof D == "object" && D !== null && D.key != null ? nt("" + D.key) : Y.toString(36);
  }
  function ie() {
  }
  function Kt(D) {
    switch (D.status) {
      case "fulfilled":
        return D.value;
      case "rejected":
        throw D.reason;
      default:
        switch (typeof D.status == "string" ? D.then(ie, ie) : (D.status = "pending", D.then(
          function(Y) {
            D.status === "pending" && (D.status = "fulfilled", D.value = Y);
          },
          function(Y) {
            D.status === "pending" && (D.status = "rejected", D.reason = Y);
          }
        )), D.status) {
          case "fulfilled":
            return D.value;
          case "rejected":
            throw D.reason;
        }
    }
    throw D;
  }
  function zt(D, Y, et, tt, rt) {
    var Ot = typeof D;
    (Ot === "undefined" || Ot === "boolean") && (D = null);
    var yt = !1;
    if (D === null) yt = !0;
    else
      switch (Ot) {
        case "bigint":
        case "string":
        case "number":
          yt = !0;
          break;
        case "object":
          switch (D.$$typeof) {
            case n:
            case t:
              yt = !0;
              break;
            case g:
              return yt = D._init, zt(
                yt(D._payload),
                Y,
                et,
                tt,
                rt
              );
          }
      }
    if (yt)
      return rt = rt(D), yt = tt === "" ? "." + it(D, 0) : tt, X(rt) ? (et = "", yt != null && (et = yt.replace(vt, "$&/") + "/"), zt(rt, Y, et, "", function(Ji) {
        return Ji;
      })) : rt != null && (lt(rt) && (rt = $(
        rt,
        et + (rt.key == null || D && D.key === rt.key ? "" : ("" + rt.key).replace(
          vt,
          "$&/"
        ) + "/") + yt
      )), Y.push(rt)), 1;
    yt = 0;
    var qe = tt === "" ? "." : tt + ":";
    if (X(D))
      for (var It = 0; It < D.length; It++)
        tt = D[It], Ot = qe + it(tt, It), yt += zt(
          tt,
          Y,
          et,
          Ot,
          rt
        );
    else if (It = b(D), typeof It == "function")
      for (D = It.call(D), It = 0; !(tt = D.next()).done; )
        tt = tt.value, Ot = qe + it(tt, It++), yt += zt(
          tt,
          Y,
          et,
          Ot,
          rt
        );
    else if (Ot === "object") {
      if (typeof D.then == "function")
        return zt(
          Kt(D),
          Y,
          et,
          tt,
          rt
        );
      throw Y = String(D), Error(
        "Objects are not valid as a React child (found: " + (Y === "[object Object]" ? "object with keys {" + Object.keys(D).join(", ") + "}" : Y) + "). If you meant to render a collection of children, use an array instead."
      );
    }
    return yt;
  }
  function j(D, Y, et) {
    if (D == null) return D;
    var tt = [], rt = 0;
    return zt(D, tt, "", "", function(Ot) {
      return Y.call(et, Ot, rt++);
    }), tt;
  }
  function W(D) {
    if (D._status === -1) {
      var Y = D._result;
      Y = Y(), Y.then(
        function(et) {
          (D._status === 0 || D._status === -1) && (D._status = 1, D._result = et);
        },
        function(et) {
          (D._status === 0 || D._status === -1) && (D._status = 2, D._result = et);
        }
      ), D._status === -1 && (D._status = 0, D._result = Y);
    }
    if (D._status === 1) return D._result.default;
    throw D._result;
  }
  var J = typeof reportError == "function" ? reportError : function(D) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var Y = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof D == "object" && D !== null && typeof D.message == "string" ? String(D.message) : String(D),
        error: D
      });
      if (!window.dispatchEvent(Y)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", D);
      return;
    }
    console.error(D);
  };
  function ft() {
  }
  return xt.Children = {
    map: j,
    forEach: function(D, Y, et) {
      j(
        D,
        function() {
          Y.apply(this, arguments);
        },
        et
      );
    },
    count: function(D) {
      var Y = 0;
      return j(D, function() {
        Y++;
      }), Y;
    },
    toArray: function(D) {
      return j(D, function(Y) {
        return Y;
      }) || [];
    },
    only: function(D) {
      if (!lt(D))
        throw Error(
          "React.Children.only expected to receive a single React element child."
        );
      return D;
    }
  }, xt.Component = R, xt.Fragment = i, xt.Profiler = r, xt.PureComponent = B, xt.StrictMode = a, xt.Suspense = m, xt.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = Q, xt.__COMPILER_RUNTIME = {
    __proto__: null,
    c: function(D) {
      return Q.H.useMemoCache(D);
    }
  }, xt.cache = function(D) {
    return function() {
      return D.apply(null, arguments);
    };
  }, xt.cloneElement = function(D, Y, et) {
    if (D == null)
      throw Error(
        "The argument must be a React element, but you passed " + D + "."
      );
    var tt = T({}, D.props), rt = D.key, Ot = void 0;
    if (Y != null)
      for (yt in Y.ref !== void 0 && (Ot = void 0), Y.key !== void 0 && (rt = "" + Y.key), Y)
        !ut.call(Y, yt) || yt === "key" || yt === "__self" || yt === "__source" || yt === "ref" && Y.ref === void 0 || (tt[yt] = Y[yt]);
    var yt = arguments.length - 2;
    if (yt === 1) tt.children = et;
    else if (1 < yt) {
      for (var qe = Array(yt), It = 0; It < yt; It++)
        qe[It] = arguments[It + 2];
      tt.children = qe;
    }
    return st(D.type, rt, void 0, void 0, Ot, tt);
  }, xt.createContext = function(D) {
    return D = {
      $$typeof: c,
      _currentValue: D,
      _currentValue2: D,
      _threadCount: 0,
      Provider: null,
      Consumer: null
    }, D.Provider = D, D.Consumer = {
      $$typeof: u,
      _context: D
    }, D;
  }, xt.createElement = function(D, Y, et) {
    var tt, rt = {}, Ot = null;
    if (Y != null)
      for (tt in Y.key !== void 0 && (Ot = "" + Y.key), Y)
        ut.call(Y, tt) && tt !== "key" && tt !== "__self" && tt !== "__source" && (rt[tt] = Y[tt]);
    var yt = arguments.length - 2;
    if (yt === 1) rt.children = et;
    else if (1 < yt) {
      for (var qe = Array(yt), It = 0; It < yt; It++)
        qe[It] = arguments[It + 2];
      rt.children = qe;
    }
    if (D && D.defaultProps)
      for (tt in yt = D.defaultProps, yt)
        rt[tt] === void 0 && (rt[tt] = yt[tt]);
    return st(D, Ot, void 0, void 0, null, rt);
  }, xt.createRef = function() {
    return { current: null };
  }, xt.forwardRef = function(D) {
    return { $$typeof: f, render: D };
  }, xt.isValidElement = lt, xt.lazy = function(D) {
    return {
      $$typeof: g,
      _payload: { _status: -1, _result: D },
      _init: W
    };
  }, xt.memo = function(D, Y) {
    return {
      $$typeof: p,
      type: D,
      compare: Y === void 0 ? null : Y
    };
  }, xt.startTransition = function(D) {
    var Y = Q.T, et = {};
    Q.T = et;
    try {
      var tt = D(), rt = Q.S;
      rt !== null && rt(et, tt), typeof tt == "object" && tt !== null && typeof tt.then == "function" && tt.then(ft, J);
    } catch (Ot) {
      J(Ot);
    } finally {
      Q.T = Y;
    }
  }, xt.unstable_useCacheRefresh = function() {
    return Q.H.useCacheRefresh();
  }, xt.use = function(D) {
    return Q.H.use(D);
  }, xt.useActionState = function(D, Y, et) {
    return Q.H.useActionState(D, Y, et);
  }, xt.useCallback = function(D, Y) {
    return Q.H.useCallback(D, Y);
  }, xt.useContext = function(D) {
    return Q.H.useContext(D);
  }, xt.useDebugValue = function() {
  }, xt.useDeferredValue = function(D, Y) {
    return Q.H.useDeferredValue(D, Y);
  }, xt.useEffect = function(D, Y, et) {
    var tt = Q.H;
    if (typeof et == "function")
      throw Error(
        "useEffect CRUD overload is not enabled in this build of React."
      );
    return tt.useEffect(D, Y);
  }, xt.useId = function() {
    return Q.H.useId();
  }, xt.useImperativeHandle = function(D, Y, et) {
    return Q.H.useImperativeHandle(D, Y, et);
  }, xt.useInsertionEffect = function(D, Y) {
    return Q.H.useInsertionEffect(D, Y);
  }, xt.useLayoutEffect = function(D, Y) {
    return Q.H.useLayoutEffect(D, Y);
  }, xt.useMemo = function(D, Y) {
    return Q.H.useMemo(D, Y);
  }, xt.useOptimistic = function(D, Y) {
    return Q.H.useOptimistic(D, Y);
  }, xt.useReducer = function(D, Y, et) {
    return Q.H.useReducer(D, Y, et);
  }, xt.useRef = function(D) {
    return Q.H.useRef(D);
  }, xt.useState = function(D) {
    return Q.H.useState(D);
  }, xt.useSyncExternalStore = function(D, Y, et) {
    return Q.H.useSyncExternalStore(
      D,
      Y,
      et
    );
  }, xt.useTransition = function() {
    return Q.H.useTransition();
  }, xt.version = "19.1.1", xt;
}
var w1;
function iv() {
  return w1 || (w1 = 1, hg.exports = mV()), hg.exports;
}
var G = iv();
const M1 = /* @__PURE__ */ zR(G);
var dg = !1, Ah, Dh, MT = G.createContext({ loaded: !1 }), pV = ({ children: n, init: t }) => {
  let [i, a] = G.useState(dg);
  G.useEffect(() => {
    let u = !1;
    if (!dg) {
      if (!Ah) Dh = t, Ah = (async () => {
        await t(YM), dg = !0;
      })().catch((c) => {
        throw Ah = void 0, Dh = void 0, c;
      });
      else if (Dh && Dh !== t) throw Error("ParticlesProvider init callback must be stable across the app lifecycle.");
      return Ah.then(() => {
        u || a(!0);
      }).catch(() => {
        u || a(!1);
      }), () => {
        u = !0;
      };
    }
  }, [t]);
  let r = G.useMemo(() => ({ loaded: i }), [i]);
  return /* @__PURE__ */ Z.jsx(MT.Provider, {
    value: r,
    children: i ? n : null
  });
};
function TT() {
  return G.useContext(MT);
}
var gV = (n) => {
  let { className: t, id: i, options: a, particlesLoaded: r, style: u, url: c } = n, { loaded: f } = TT(), m = G.useRef(void 0);
  return G.useEffect(() => {
    if (!f) return;
    let p = i ?? "tsparticles";
    return YM.load({
      id: p,
      url: c,
      options: a
    }).then((g) => {
      if (!(g != null && g.destroyed)) {
        if (!document.getElementById(p)) {
          g == null || g.destroy();
          return;
        }
        m.current = g, r == null || r(g);
      }
    }), () => {
      var g;
      (g = m.current) == null || g.destroy(), m.current = void 0;
    };
  }, [
    i,
    f,
    a,
    r,
    c
  ]), /* @__PURE__ */ Z.jsx("div", {
    id: i ?? "tsparticles",
    className: t,
    style: u
  });
}, yV = gV, mg = { exports: {} }, Nu = {}, pg = { exports: {} }, gg = {};
/**
 * @license React
 * scheduler.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var T1;
function vV() {
  return T1 || (T1 = 1, (function(n) {
    function t(j, W) {
      var J = j.length;
      j.push(W);
      t: for (; 0 < J; ) {
        var ft = J - 1 >>> 1, D = j[ft];
        if (0 < r(D, W))
          j[ft] = W, j[J] = D, J = ft;
        else break t;
      }
    }
    function i(j) {
      return j.length === 0 ? null : j[0];
    }
    function a(j) {
      if (j.length === 0) return null;
      var W = j[0], J = j.pop();
      if (J !== W) {
        j[0] = J;
        t: for (var ft = 0, D = j.length, Y = D >>> 1; ft < Y; ) {
          var et = 2 * (ft + 1) - 1, tt = j[et], rt = et + 1, Ot = j[rt];
          if (0 > r(tt, J))
            rt < D && 0 > r(Ot, tt) ? (j[ft] = Ot, j[rt] = J, ft = rt) : (j[ft] = tt, j[et] = J, ft = et);
          else if (rt < D && 0 > r(Ot, J))
            j[ft] = Ot, j[rt] = J, ft = rt;
          else break t;
        }
      }
      return W;
    }
    function r(j, W) {
      var J = j.sortIndex - W.sortIndex;
      return J !== 0 ? J : j.id - W.id;
    }
    if (n.unstable_now = void 0, typeof performance == "object" && typeof performance.now == "function") {
      var u = performance;
      n.unstable_now = function() {
        return u.now();
      };
    } else {
      var c = Date, f = c.now();
      n.unstable_now = function() {
        return c.now() - f;
      };
    }
    var m = [], p = [], g = 1, y = null, b = 3, S = !1, T = !1, C = !1, R = !1, z = typeof setTimeout == "function" ? setTimeout : null, B = typeof clearTimeout == "function" ? clearTimeout : null, H = typeof setImmediate < "u" ? setImmediate : null;
    function X(j) {
      for (var W = i(p); W !== null; ) {
        if (W.callback === null) a(p);
        else if (W.startTime <= j)
          a(p), W.sortIndex = W.expirationTime, t(m, W);
        else break;
        W = i(p);
      }
    }
    function Q(j) {
      if (C = !1, X(j), !T)
        if (i(m) !== null)
          T = !0, ut || (ut = !0, it());
        else {
          var W = i(p);
          W !== null && zt(Q, W.startTime - j);
        }
    }
    var ut = !1, st = -1, $ = 5, lt = -1;
    function nt() {
      return R ? !0 : !(n.unstable_now() - lt < $);
    }
    function vt() {
      if (R = !1, ut) {
        var j = n.unstable_now();
        lt = j;
        var W = !0;
        try {
          t: {
            T = !1, C && (C = !1, B(st), st = -1), S = !0;
            var J = b;
            try {
              e: {
                for (X(j), y = i(m); y !== null && !(y.expirationTime > j && nt()); ) {
                  var ft = y.callback;
                  if (typeof ft == "function") {
                    y.callback = null, b = y.priorityLevel;
                    var D = ft(
                      y.expirationTime <= j
                    );
                    if (j = n.unstable_now(), typeof D == "function") {
                      y.callback = D, X(j), W = !0;
                      break e;
                    }
                    y === i(m) && a(m), X(j);
                  } else a(m);
                  y = i(m);
                }
                if (y !== null) W = !0;
                else {
                  var Y = i(p);
                  Y !== null && zt(
                    Q,
                    Y.startTime - j
                  ), W = !1;
                }
              }
              break t;
            } finally {
              y = null, b = J, S = !1;
            }
            W = void 0;
          }
        } finally {
          W ? it() : ut = !1;
        }
      }
    }
    var it;
    if (typeof H == "function")
      it = function() {
        H(vt);
      };
    else if (typeof MessageChannel < "u") {
      var ie = new MessageChannel(), Kt = ie.port2;
      ie.port1.onmessage = vt, it = function() {
        Kt.postMessage(null);
      };
    } else
      it = function() {
        z(vt, 0);
      };
    function zt(j, W) {
      st = z(function() {
        j(n.unstable_now());
      }, W);
    }
    n.unstable_IdlePriority = 5, n.unstable_ImmediatePriority = 1, n.unstable_LowPriority = 4, n.unstable_NormalPriority = 3, n.unstable_Profiling = null, n.unstable_UserBlockingPriority = 2, n.unstable_cancelCallback = function(j) {
      j.callback = null;
    }, n.unstable_forceFrameRate = function(j) {
      0 > j || 125 < j ? console.error(
        "forceFrameRate takes a positive int between 0 and 125, forcing frame rates higher than 125 fps is not supported"
      ) : $ = 0 < j ? Math.floor(1e3 / j) : 5;
    }, n.unstable_getCurrentPriorityLevel = function() {
      return b;
    }, n.unstable_next = function(j) {
      switch (b) {
        case 1:
        case 2:
        case 3:
          var W = 3;
          break;
        default:
          W = b;
      }
      var J = b;
      b = W;
      try {
        return j();
      } finally {
        b = J;
      }
    }, n.unstable_requestPaint = function() {
      R = !0;
    }, n.unstable_runWithPriority = function(j, W) {
      switch (j) {
        case 1:
        case 2:
        case 3:
        case 4:
        case 5:
          break;
        default:
          j = 3;
      }
      var J = b;
      b = j;
      try {
        return W();
      } finally {
        b = J;
      }
    }, n.unstable_scheduleCallback = function(j, W, J) {
      var ft = n.unstable_now();
      switch (typeof J == "object" && J !== null ? (J = J.delay, J = typeof J == "number" && 0 < J ? ft + J : ft) : J = ft, j) {
        case 1:
          var D = -1;
          break;
        case 2:
          D = 250;
          break;
        case 5:
          D = 1073741823;
          break;
        case 4:
          D = 1e4;
          break;
        default:
          D = 5e3;
      }
      return D = J + D, j = {
        id: g++,
        callback: W,
        priorityLevel: j,
        startTime: J,
        expirationTime: D,
        sortIndex: -1
      }, J > ft ? (j.sortIndex = J, t(p, j), i(m) === null && j === i(p) && (C ? (B(st), st = -1) : C = !0, zt(Q, J - ft))) : (j.sortIndex = D, t(m, j), T || S || (T = !0, ut || (ut = !0, it()))), j;
    }, n.unstable_shouldYield = nt, n.unstable_wrapCallback = function(j) {
      var W = b;
      return function() {
        var J = b;
        b = W;
        try {
          return j.apply(this, arguments);
        } finally {
          b = J;
        }
      };
    };
  })(gg)), gg;
}
var C1;
function bV() {
  return C1 || (C1 = 1, pg.exports = vV()), pg.exports;
}
var yg = { exports: {} }, Be = {};
/**
 * @license React
 * react-dom.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var E1;
function xV() {
  if (E1) return Be;
  E1 = 1;
  var n = iv();
  function t(m) {
    var p = "https://react.dev/errors/" + m;
    if (1 < arguments.length) {
      p += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var g = 2; g < arguments.length; g++)
        p += "&args[]=" + encodeURIComponent(arguments[g]);
    }
    return "Minified React error #" + m + "; visit " + p + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  function i() {
  }
  var a = {
    d: {
      f: i,
      r: function() {
        throw Error(t(522));
      },
      D: i,
      C: i,
      L: i,
      m: i,
      X: i,
      S: i,
      M: i
    },
    p: 0,
    findDOMNode: null
  }, r = Symbol.for("react.portal");
  function u(m, p, g) {
    var y = 3 < arguments.length && arguments[3] !== void 0 ? arguments[3] : null;
    return {
      $$typeof: r,
      key: y == null ? null : "" + y,
      children: m,
      containerInfo: p,
      implementation: g
    };
  }
  var c = n.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE;
  function f(m, p) {
    if (m === "font") return "";
    if (typeof p == "string")
      return p === "use-credentials" ? p : "";
  }
  return Be.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE = a, Be.createPortal = function(m, p) {
    var g = 2 < arguments.length && arguments[2] !== void 0 ? arguments[2] : null;
    if (!p || p.nodeType !== 1 && p.nodeType !== 9 && p.nodeType !== 11)
      throw Error(t(299));
    return u(m, p, null, g);
  }, Be.flushSync = function(m) {
    var p = c.T, g = a.p;
    try {
      if (c.T = null, a.p = 2, m) return m();
    } finally {
      c.T = p, a.p = g, a.d.f();
    }
  }, Be.preconnect = function(m, p) {
    typeof m == "string" && (p ? (p = p.crossOrigin, p = typeof p == "string" ? p === "use-credentials" ? p : "" : void 0) : p = null, a.d.C(m, p));
  }, Be.prefetchDNS = function(m) {
    typeof m == "string" && a.d.D(m);
  }, Be.preinit = function(m, p) {
    if (typeof m == "string" && p && typeof p.as == "string") {
      var g = p.as, y = f(g, p.crossOrigin), b = typeof p.integrity == "string" ? p.integrity : void 0, S = typeof p.fetchPriority == "string" ? p.fetchPriority : void 0;
      g === "style" ? a.d.S(
        m,
        typeof p.precedence == "string" ? p.precedence : void 0,
        {
          crossOrigin: y,
          integrity: b,
          fetchPriority: S
        }
      ) : g === "script" && a.d.X(m, {
        crossOrigin: y,
        integrity: b,
        fetchPriority: S,
        nonce: typeof p.nonce == "string" ? p.nonce : void 0
      });
    }
  }, Be.preinitModule = function(m, p) {
    if (typeof m == "string")
      if (typeof p == "object" && p !== null) {
        if (p.as == null || p.as === "script") {
          var g = f(
            p.as,
            p.crossOrigin
          );
          a.d.M(m, {
            crossOrigin: g,
            integrity: typeof p.integrity == "string" ? p.integrity : void 0,
            nonce: typeof p.nonce == "string" ? p.nonce : void 0
          });
        }
      } else p == null && a.d.M(m);
  }, Be.preload = function(m, p) {
    if (typeof m == "string" && typeof p == "object" && p !== null && typeof p.as == "string") {
      var g = p.as, y = f(g, p.crossOrigin);
      a.d.L(m, g, {
        crossOrigin: y,
        integrity: typeof p.integrity == "string" ? p.integrity : void 0,
        nonce: typeof p.nonce == "string" ? p.nonce : void 0,
        type: typeof p.type == "string" ? p.type : void 0,
        fetchPriority: typeof p.fetchPriority == "string" ? p.fetchPriority : void 0,
        referrerPolicy: typeof p.referrerPolicy == "string" ? p.referrerPolicy : void 0,
        imageSrcSet: typeof p.imageSrcSet == "string" ? p.imageSrcSet : void 0,
        imageSizes: typeof p.imageSizes == "string" ? p.imageSizes : void 0,
        media: typeof p.media == "string" ? p.media : void 0
      });
    }
  }, Be.preloadModule = function(m, p) {
    if (typeof m == "string")
      if (p) {
        var g = f(p.as, p.crossOrigin);
        a.d.m(m, {
          as: typeof p.as == "string" && p.as !== "script" ? p.as : void 0,
          crossOrigin: g,
          integrity: typeof p.integrity == "string" ? p.integrity : void 0
        });
      } else a.d.m(m);
  }, Be.requestFormReset = function(m) {
    a.d.r(m);
  }, Be.unstable_batchedUpdates = function(m, p) {
    return m(p);
  }, Be.useFormState = function(m, p, g) {
    return c.H.useFormState(m, p, g);
  }, Be.useFormStatus = function() {
    return c.H.useHostTransitionStatus();
  }, Be.version = "19.1.1", Be;
}
var A1;
function SV() {
  if (A1) return yg.exports;
  A1 = 1;
  function n() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(n);
      } catch (t) {
        console.error(t);
      }
  }
  return n(), yg.exports = xV(), yg.exports;
}
/**
 * @license React
 * react-dom-client.production.js
 *
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */
var D1;
function wV() {
  if (D1) return Nu;
  D1 = 1;
  var n = bV(), t = iv(), i = SV();
  function a(e) {
    var s = "https://react.dev/errors/" + e;
    if (1 < arguments.length) {
      s += "?args[]=" + encodeURIComponent(arguments[1]);
      for (var o = 2; o < arguments.length; o++)
        s += "&args[]=" + encodeURIComponent(arguments[o]);
    }
    return "Minified React error #" + e + "; visit " + s + " for the full message or use the non-minified dev environment for full errors and additional helpful warnings.";
  }
  function r(e) {
    return !(!e || e.nodeType !== 1 && e.nodeType !== 9 && e.nodeType !== 11);
  }
  function u(e) {
    var s = e, o = e;
    if (e.alternate) for (; s.return; ) s = s.return;
    else {
      e = s;
      do
        s = e, (s.flags & 4098) !== 0 && (o = s.return), e = s.return;
      while (e);
    }
    return s.tag === 3 ? o : null;
  }
  function c(e) {
    if (e.tag === 13) {
      var s = e.memoizedState;
      if (s === null && (e = e.alternate, e !== null && (s = e.memoizedState)), s !== null) return s.dehydrated;
    }
    return null;
  }
  function f(e) {
    if (u(e) !== e)
      throw Error(a(188));
  }
  function m(e) {
    var s = e.alternate;
    if (!s) {
      if (s = u(e), s === null) throw Error(a(188));
      return s !== e ? null : e;
    }
    for (var o = e, l = s; ; ) {
      var h = o.return;
      if (h === null) break;
      var d = h.alternate;
      if (d === null) {
        if (l = h.return, l !== null) {
          o = l;
          continue;
        }
        break;
      }
      if (h.child === d.child) {
        for (d = h.child; d; ) {
          if (d === o) return f(h), e;
          if (d === l) return f(h), s;
          d = d.sibling;
        }
        throw Error(a(188));
      }
      if (o.return !== l.return) o = h, l = d;
      else {
        for (var x = !1, M = h.child; M; ) {
          if (M === o) {
            x = !0, o = h, l = d;
            break;
          }
          if (M === l) {
            x = !0, l = h, o = d;
            break;
          }
          M = M.sibling;
        }
        if (!x) {
          for (M = d.child; M; ) {
            if (M === o) {
              x = !0, o = d, l = h;
              break;
            }
            if (M === l) {
              x = !0, l = d, o = h;
              break;
            }
            M = M.sibling;
          }
          if (!x) throw Error(a(189));
        }
      }
      if (o.alternate !== l) throw Error(a(190));
    }
    if (o.tag !== 3) throw Error(a(188));
    return o.stateNode.current === o ? e : s;
  }
  function p(e) {
    var s = e.tag;
    if (s === 5 || s === 26 || s === 27 || s === 6) return e;
    for (e = e.child; e !== null; ) {
      if (s = p(e), s !== null) return s;
      e = e.sibling;
    }
    return null;
  }
  var g = Object.assign, y = Symbol.for("react.element"), b = Symbol.for("react.transitional.element"), S = Symbol.for("react.portal"), T = Symbol.for("react.fragment"), C = Symbol.for("react.strict_mode"), R = Symbol.for("react.profiler"), z = Symbol.for("react.provider"), B = Symbol.for("react.consumer"), H = Symbol.for("react.context"), X = Symbol.for("react.forward_ref"), Q = Symbol.for("react.suspense"), ut = Symbol.for("react.suspense_list"), st = Symbol.for("react.memo"), $ = Symbol.for("react.lazy"), lt = Symbol.for("react.activity"), nt = Symbol.for("react.memo_cache_sentinel"), vt = Symbol.iterator;
  function it(e) {
    return e === null || typeof e != "object" ? null : (e = vt && e[vt] || e["@@iterator"], typeof e == "function" ? e : null);
  }
  var ie = Symbol.for("react.client.reference");
  function Kt(e) {
    if (e == null) return null;
    if (typeof e == "function")
      return e.$$typeof === ie ? null : e.displayName || e.name || null;
    if (typeof e == "string") return e;
    switch (e) {
      case T:
        return "Fragment";
      case R:
        return "Profiler";
      case C:
        return "StrictMode";
      case Q:
        return "Suspense";
      case ut:
        return "SuspenseList";
      case lt:
        return "Activity";
    }
    if (typeof e == "object")
      switch (e.$$typeof) {
        case S:
          return "Portal";
        case H:
          return (e.displayName || "Context") + ".Provider";
        case B:
          return (e._context.displayName || "Context") + ".Consumer";
        case X:
          var s = e.render;
          return e = e.displayName, e || (e = s.displayName || s.name || "", e = e !== "" ? "ForwardRef(" + e + ")" : "ForwardRef"), e;
        case st:
          return s = e.displayName || null, s !== null ? s : Kt(e.type) || "Memo";
        case $:
          s = e._payload, e = e._init;
          try {
            return Kt(e(s));
          } catch {
          }
      }
    return null;
  }
  var zt = Array.isArray, j = t.__CLIENT_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, W = i.__DOM_INTERNALS_DO_NOT_USE_OR_WARN_USERS_THEY_CANNOT_UPGRADE, J = {
    pending: !1,
    data: null,
    method: null,
    action: null
  }, ft = [], D = -1;
  function Y(e) {
    return { current: e };
  }
  function et(e) {
    0 > D || (e.current = ft[D], ft[D] = null, D--);
  }
  function tt(e, s) {
    D++, ft[D] = e.current, e.current = s;
  }
  var rt = Y(null), Ot = Y(null), yt = Y(null), qe = Y(null);
  function It(e, s) {
    switch (tt(yt, s), tt(Ot, e), tt(rt, null), s.nodeType) {
      case 9:
      case 11:
        e = (e = s.documentElement) && (e = e.namespaceURI) ? tS(e) : 0;
        break;
      default:
        if (e = s.tagName, s = s.namespaceURI)
          s = tS(s), e = eS(s, e);
        else
          switch (e) {
            case "svg":
              e = 1;
              break;
            case "math":
              e = 2;
              break;
            default:
              e = 0;
          }
    }
    et(rt), tt(rt, e);
  }
  function Ji() {
    et(rt), et(Ot), et(yt);
  }
  function Pd(e) {
    e.memoizedState !== null && tt(qe, e);
    var s = rt.current, o = eS(s, e.type);
    s !== o && (tt(Ot, e), tt(rt, o));
  }
  function nf(e) {
    Ot.current === e && (et(rt), et(Ot)), qe.current === e && (et(qe), Ou._currentValue = J);
  }
  var Ld = Object.prototype.hasOwnProperty, _d = n.unstable_scheduleCallback, Bd = n.unstable_cancelCallback, rA = n.unstable_shouldYield, lA = n.unstable_requestPaint, si = n.unstable_now, uA = n.unstable_getCurrentPriorityLevel, Pv = n.unstable_ImmediatePriority, Lv = n.unstable_UserBlockingPriority, sf = n.unstable_NormalPriority, cA = n.unstable_LowPriority, _v = n.unstable_IdlePriority, fA = n.log, hA = n.unstable_setDisableYieldValue, Nl = null, ln = null;
  function ts(e) {
    if (typeof fA == "function" && hA(e), ln && typeof ln.setStrictMode == "function")
      try {
        ln.setStrictMode(Nl, e);
      } catch {
      }
  }
  var un = Math.clz32 ? Math.clz32 : pA, dA = Math.log, mA = Math.LN2;
  function pA(e) {
    return e >>>= 0, e === 0 ? 32 : 31 - (dA(e) / mA | 0) | 0;
  }
  var af = 256, of = 4194304;
  function ha(e) {
    var s = e & 42;
    if (s !== 0) return s;
    switch (e & -e) {
      case 1:
        return 1;
      case 2:
        return 2;
      case 4:
        return 4;
      case 8:
        return 8;
      case 16:
        return 16;
      case 32:
        return 32;
      case 64:
        return 64;
      case 128:
        return 128;
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return e & 4194048;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        return e & 62914560;
      case 67108864:
        return 67108864;
      case 134217728:
        return 134217728;
      case 268435456:
        return 268435456;
      case 536870912:
        return 536870912;
      case 1073741824:
        return 0;
      default:
        return e;
    }
  }
  function rf(e, s, o) {
    var l = e.pendingLanes;
    if (l === 0) return 0;
    var h = 0, d = e.suspendedLanes, x = e.pingedLanes;
    e = e.warmLanes;
    var M = l & 134217727;
    return M !== 0 ? (l = M & ~d, l !== 0 ? h = ha(l) : (x &= M, x !== 0 ? h = ha(x) : o || (o = M & ~e, o !== 0 && (h = ha(o))))) : (M = l & ~d, M !== 0 ? h = ha(M) : x !== 0 ? h = ha(x) : o || (o = l & ~e, o !== 0 && (h = ha(o)))), h === 0 ? 0 : s !== 0 && s !== h && (s & d) === 0 && (d = h & -h, o = s & -s, d >= o || d === 32 && (o & 4194048) !== 0) ? s : h;
  }
  function Ul(e, s) {
    return (e.pendingLanes & ~(e.suspendedLanes & ~e.pingedLanes) & s) === 0;
  }
  function gA(e, s) {
    switch (e) {
      case 1:
      case 2:
      case 4:
      case 8:
      case 64:
        return s + 250;
      case 16:
      case 32:
      case 128:
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
        return s + 5e3;
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        return -1;
      case 67108864:
      case 134217728:
      case 268435456:
      case 536870912:
      case 1073741824:
        return -1;
      default:
        return -1;
    }
  }
  function Bv() {
    var e = af;
    return af <<= 1, (af & 4194048) === 0 && (af = 256), e;
  }
  function Nv() {
    var e = of;
    return of <<= 1, (of & 62914560) === 0 && (of = 4194304), e;
  }
  function Nd(e) {
    for (var s = [], o = 0; 31 > o; o++) s.push(e);
    return s;
  }
  function jl(e, s) {
    e.pendingLanes |= s, s !== 268435456 && (e.suspendedLanes = 0, e.pingedLanes = 0, e.warmLanes = 0);
  }
  function yA(e, s, o, l, h, d) {
    var x = e.pendingLanes;
    e.pendingLanes = o, e.suspendedLanes = 0, e.pingedLanes = 0, e.warmLanes = 0, e.expiredLanes &= o, e.entangledLanes &= o, e.errorRecoveryDisabledLanes &= o, e.shellSuspendCounter = 0;
    var M = e.entanglements, E = e.expirationTimes, _ = e.hiddenUpdates;
    for (o = x & ~o; 0 < o; ) {
      var F = 31 - un(o), I = 1 << F;
      M[F] = 0, E[F] = -1;
      var N = _[F];
      if (N !== null)
        for (_[F] = null, F = 0; F < N.length; F++) {
          var U = N[F];
          U !== null && (U.lane &= -536870913);
        }
      o &= ~I;
    }
    l !== 0 && Uv(e, l, 0), d !== 0 && h === 0 && e.tag !== 0 && (e.suspendedLanes |= d & ~(x & ~s));
  }
  function Uv(e, s, o) {
    e.pendingLanes |= s, e.suspendedLanes &= ~s;
    var l = 31 - un(s);
    e.entangledLanes |= s, e.entanglements[l] = e.entanglements[l] | 1073741824 | o & 4194090;
  }
  function jv(e, s) {
    var o = e.entangledLanes |= s;
    for (e = e.entanglements; o; ) {
      var l = 31 - un(o), h = 1 << l;
      h & s | e[l] & s && (e[l] |= s), o &= ~h;
    }
  }
  function Ud(e) {
    switch (e) {
      case 2:
        e = 1;
        break;
      case 8:
        e = 4;
        break;
      case 32:
        e = 16;
        break;
      case 256:
      case 512:
      case 1024:
      case 2048:
      case 4096:
      case 8192:
      case 16384:
      case 32768:
      case 65536:
      case 131072:
      case 262144:
      case 524288:
      case 1048576:
      case 2097152:
      case 4194304:
      case 8388608:
      case 16777216:
      case 33554432:
        e = 128;
        break;
      case 268435456:
        e = 134217728;
        break;
      default:
        e = 0;
    }
    return e;
  }
  function jd(e) {
    return e &= -e, 2 < e ? 8 < e ? (e & 134217727) !== 0 ? 32 : 268435456 : 8 : 2;
  }
  function Hv() {
    var e = W.p;
    return e !== 0 ? e : (e = window.event, e === void 0 ? 32 : xS(e.type));
  }
  function vA(e, s) {
    var o = W.p;
    try {
      return W.p = e, s();
    } finally {
      W.p = o;
    }
  }
  var es = Math.random().toString(36).slice(2), Le = "__reactFiber$" + es, We = "__reactProps$" + es, No = "__reactContainer$" + es, Hd = "__reactEvents$" + es, bA = "__reactListeners$" + es, xA = "__reactHandles$" + es, qv = "__reactResources$" + es, Hl = "__reactMarker$" + es;
  function qd(e) {
    delete e[Le], delete e[We], delete e[Hd], delete e[bA], delete e[xA];
  }
  function Uo(e) {
    var s = e[Le];
    if (s) return s;
    for (var o = e.parentNode; o; ) {
      if (s = o[No] || o[Le]) {
        if (o = s.alternate, s.child !== null || o !== null && o.child !== null)
          for (e = aS(e); e !== null; ) {
            if (o = e[Le]) return o;
            e = aS(e);
          }
        return s;
      }
      e = o, o = e.parentNode;
    }
    return null;
  }
  function jo(e) {
    if (e = e[Le] || e[No]) {
      var s = e.tag;
      if (s === 5 || s === 6 || s === 13 || s === 26 || s === 27 || s === 3)
        return e;
    }
    return null;
  }
  function ql(e) {
    var s = e.tag;
    if (s === 5 || s === 26 || s === 27 || s === 6) return e.stateNode;
    throw Error(a(33));
  }
  function Ho(e) {
    var s = e[qv];
    return s || (s = e[qv] = { hoistableStyles: /* @__PURE__ */ new Map(), hoistableScripts: /* @__PURE__ */ new Map() }), s;
  }
  function Me(e) {
    e[Hl] = !0;
  }
  var Gv = /* @__PURE__ */ new Set(), Yv = {};
  function da(e, s) {
    qo(e, s), qo(e + "Capture", s);
  }
  function qo(e, s) {
    for (Yv[e] = s, e = 0; e < s.length; e++)
      Gv.add(s[e]);
  }
  var SA = RegExp(
    "^[:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD][:A-Z_a-z\\u00C0-\\u00D6\\u00D8-\\u00F6\\u00F8-\\u02FF\\u0370-\\u037D\\u037F-\\u1FFF\\u200C-\\u200D\\u2070-\\u218F\\u2C00-\\u2FEF\\u3001-\\uD7FF\\uF900-\\uFDCF\\uFDF0-\\uFFFD\\-.0-9\\u00B7\\u0300-\\u036F\\u203F-\\u2040]*$"
  ), Xv = {}, Fv = {};
  function wA(e) {
    return Ld.call(Fv, e) ? !0 : Ld.call(Xv, e) ? !1 : SA.test(e) ? Fv[e] = !0 : (Xv[e] = !0, !1);
  }
  function lf(e, s, o) {
    if (wA(s))
      if (o === null) e.removeAttribute(s);
      else {
        switch (typeof o) {
          case "undefined":
          case "function":
          case "symbol":
            e.removeAttribute(s);
            return;
          case "boolean":
            var l = s.toLowerCase().slice(0, 5);
            if (l !== "data-" && l !== "aria-") {
              e.removeAttribute(s);
              return;
            }
        }
        e.setAttribute(s, "" + o);
      }
  }
  function uf(e, s, o) {
    if (o === null) e.removeAttribute(s);
    else {
      switch (typeof o) {
        case "undefined":
        case "function":
        case "symbol":
        case "boolean":
          e.removeAttribute(s);
          return;
      }
      e.setAttribute(s, "" + o);
    }
  }
  function Pi(e, s, o, l) {
    if (l === null) e.removeAttribute(o);
    else {
      switch (typeof l) {
        case "undefined":
        case "function":
        case "symbol":
        case "boolean":
          e.removeAttribute(o);
          return;
      }
      e.setAttributeNS(s, o, "" + l);
    }
  }
  var Gd, Zv;
  function Go(e) {
    if (Gd === void 0)
      try {
        throw Error();
      } catch (o) {
        var s = o.stack.trim().match(/\n( *(at )?)/);
        Gd = s && s[1] || "", Zv = -1 < o.stack.indexOf(`
    at`) ? " (<anonymous>)" : -1 < o.stack.indexOf("@") ? "@unknown:0:0" : "";
      }
    return `
` + Gd + e + Zv;
  }
  var Yd = !1;
  function Xd(e, s) {
    if (!e || Yd) return "";
    Yd = !0;
    var o = Error.prepareStackTrace;
    Error.prepareStackTrace = void 0;
    try {
      var l = {
        DetermineComponentFrameRoot: function() {
          try {
            if (s) {
              var I = function() {
                throw Error();
              };
              if (Object.defineProperty(I.prototype, "props", {
                set: function() {
                  throw Error();
                }
              }), typeof Reflect == "object" && Reflect.construct) {
                try {
                  Reflect.construct(I, []);
                } catch (U) {
                  var N = U;
                }
                Reflect.construct(e, [], I);
              } else {
                try {
                  I.call();
                } catch (U) {
                  N = U;
                }
                e.call(I.prototype);
              }
            } else {
              try {
                throw Error();
              } catch (U) {
                N = U;
              }
              (I = e()) && typeof I.catch == "function" && I.catch(function() {
              });
            }
          } catch (U) {
            if (U && N && typeof U.stack == "string")
              return [U.stack, N.stack];
          }
          return [null, null];
        }
      };
      l.DetermineComponentFrameRoot.displayName = "DetermineComponentFrameRoot";
      var h = Object.getOwnPropertyDescriptor(
        l.DetermineComponentFrameRoot,
        "name"
      );
      h && h.configurable && Object.defineProperty(
        l.DetermineComponentFrameRoot,
        "name",
        { value: "DetermineComponentFrameRoot" }
      );
      var d = l.DetermineComponentFrameRoot(), x = d[0], M = d[1];
      if (x && M) {
        var E = x.split(`
`), _ = M.split(`
`);
        for (h = l = 0; l < E.length && !E[l].includes("DetermineComponentFrameRoot"); )
          l++;
        for (; h < _.length && !_[h].includes(
          "DetermineComponentFrameRoot"
        ); )
          h++;
        if (l === E.length || h === _.length)
          for (l = E.length - 1, h = _.length - 1; 1 <= l && 0 <= h && E[l] !== _[h]; )
            h--;
        for (; 1 <= l && 0 <= h; l--, h--)
          if (E[l] !== _[h]) {
            if (l !== 1 || h !== 1)
              do
                if (l--, h--, 0 > h || E[l] !== _[h]) {
                  var F = `
` + E[l].replace(" at new ", " at ");
                  return e.displayName && F.includes("<anonymous>") && (F = F.replace("<anonymous>", e.displayName)), F;
                }
              while (1 <= l && 0 <= h);
            break;
          }
      }
    } finally {
      Yd = !1, Error.prepareStackTrace = o;
    }
    return (o = e ? e.displayName || e.name : "") ? Go(o) : "";
  }
  function MA(e) {
    switch (e.tag) {
      case 26:
      case 27:
      case 5:
        return Go(e.type);
      case 16:
        return Go("Lazy");
      case 13:
        return Go("Suspense");
      case 19:
        return Go("SuspenseList");
      case 0:
      case 15:
        return Xd(e.type, !1);
      case 11:
        return Xd(e.type.render, !1);
      case 1:
        return Xd(e.type, !0);
      case 31:
        return Go("Activity");
      default:
        return "";
    }
  }
  function Qv(e) {
    try {
      var s = "";
      do
        s += MA(e), e = e.return;
      while (e);
      return s;
    } catch (o) {
      return `
Error generating stack: ` + o.message + `
` + o.stack;
    }
  }
  function Sn(e) {
    switch (typeof e) {
      case "bigint":
      case "boolean":
      case "number":
      case "string":
      case "undefined":
        return e;
      case "object":
        return e;
      default:
        return "";
    }
  }
  function Kv(e) {
    var s = e.type;
    return (e = e.nodeName) && e.toLowerCase() === "input" && (s === "checkbox" || s === "radio");
  }
  function TA(e) {
    var s = Kv(e) ? "checked" : "value", o = Object.getOwnPropertyDescriptor(
      e.constructor.prototype,
      s
    ), l = "" + e[s];
    if (!e.hasOwnProperty(s) && typeof o < "u" && typeof o.get == "function" && typeof o.set == "function") {
      var h = o.get, d = o.set;
      return Object.defineProperty(e, s, {
        configurable: !0,
        get: function() {
          return h.call(this);
        },
        set: function(x) {
          l = "" + x, d.call(this, x);
        }
      }), Object.defineProperty(e, s, {
        enumerable: o.enumerable
      }), {
        getValue: function() {
          return l;
        },
        setValue: function(x) {
          l = "" + x;
        },
        stopTracking: function() {
          e._valueTracker = null, delete e[s];
        }
      };
    }
  }
  function cf(e) {
    e._valueTracker || (e._valueTracker = TA(e));
  }
  function Iv(e) {
    if (!e) return !1;
    var s = e._valueTracker;
    if (!s) return !0;
    var o = s.getValue(), l = "";
    return e && (l = Kv(e) ? e.checked ? "true" : "false" : e.value), e = l, e !== o ? (s.setValue(e), !0) : !1;
  }
  function ff(e) {
    if (e = e || (typeof document < "u" ? document : void 0), typeof e > "u") return null;
    try {
      return e.activeElement || e.body;
    } catch {
      return e.body;
    }
  }
  var CA = /[\n"\\]/g;
  function wn(e) {
    return e.replace(
      CA,
      function(s) {
        return "\\" + s.charCodeAt(0).toString(16) + " ";
      }
    );
  }
  function Fd(e, s, o, l, h, d, x, M) {
    e.name = "", x != null && typeof x != "function" && typeof x != "symbol" && typeof x != "boolean" ? e.type = x : e.removeAttribute("type"), s != null ? x === "number" ? (s === 0 && e.value === "" || e.value != s) && (e.value = "" + Sn(s)) : e.value !== "" + Sn(s) && (e.value = "" + Sn(s)) : x !== "submit" && x !== "reset" || e.removeAttribute("value"), s != null ? Zd(e, x, Sn(s)) : o != null ? Zd(e, x, Sn(o)) : l != null && e.removeAttribute("value"), h == null && d != null && (e.defaultChecked = !!d), h != null && (e.checked = h && typeof h != "function" && typeof h != "symbol"), M != null && typeof M != "function" && typeof M != "symbol" && typeof M != "boolean" ? e.name = "" + Sn(M) : e.removeAttribute("name");
  }
  function $v(e, s, o, l, h, d, x, M) {
    if (d != null && typeof d != "function" && typeof d != "symbol" && typeof d != "boolean" && (e.type = d), s != null || o != null) {
      if (!(d !== "submit" && d !== "reset" || s != null))
        return;
      o = o != null ? "" + Sn(o) : "", s = s != null ? "" + Sn(s) : o, M || s === e.value || (e.value = s), e.defaultValue = s;
    }
    l = l ?? h, l = typeof l != "function" && typeof l != "symbol" && !!l, e.checked = M ? e.checked : !!l, e.defaultChecked = !!l, x != null && typeof x != "function" && typeof x != "symbol" && typeof x != "boolean" && (e.name = x);
  }
  function Zd(e, s, o) {
    s === "number" && ff(e.ownerDocument) === e || e.defaultValue === "" + o || (e.defaultValue = "" + o);
  }
  function Yo(e, s, o, l) {
    if (e = e.options, s) {
      s = {};
      for (var h = 0; h < o.length; h++)
        s["$" + o[h]] = !0;
      for (o = 0; o < e.length; o++)
        h = s.hasOwnProperty("$" + e[o].value), e[o].selected !== h && (e[o].selected = h), h && l && (e[o].defaultSelected = !0);
    } else {
      for (o = "" + Sn(o), s = null, h = 0; h < e.length; h++) {
        if (e[h].value === o) {
          e[h].selected = !0, l && (e[h].defaultSelected = !0);
          return;
        }
        s !== null || e[h].disabled || (s = e[h]);
      }
      s !== null && (s.selected = !0);
    }
  }
  function Wv(e, s, o) {
    if (s != null && (s = "" + Sn(s), s !== e.value && (e.value = s), o == null)) {
      e.defaultValue !== s && (e.defaultValue = s);
      return;
    }
    e.defaultValue = o != null ? "" + Sn(o) : "";
  }
  function Jv(e, s, o, l) {
    if (s == null) {
      if (l != null) {
        if (o != null) throw Error(a(92));
        if (zt(l)) {
          if (1 < l.length) throw Error(a(93));
          l = l[0];
        }
        o = l;
      }
      o == null && (o = ""), s = o;
    }
    o = Sn(s), e.defaultValue = o, l = e.textContent, l === o && l !== "" && l !== null && (e.value = l);
  }
  function Xo(e, s) {
    if (s) {
      var o = e.firstChild;
      if (o && o === e.lastChild && o.nodeType === 3) {
        o.nodeValue = s;
        return;
      }
    }
    e.textContent = s;
  }
  var EA = new Set(
    "animationIterationCount aspectRatio borderImageOutset borderImageSlice borderImageWidth boxFlex boxFlexGroup boxOrdinalGroup columnCount columns flex flexGrow flexPositive flexShrink flexNegative flexOrder gridArea gridRow gridRowEnd gridRowSpan gridRowStart gridColumn gridColumnEnd gridColumnSpan gridColumnStart fontWeight lineClamp lineHeight opacity order orphans scale tabSize widows zIndex zoom fillOpacity floodOpacity stopOpacity strokeDasharray strokeDashoffset strokeMiterlimit strokeOpacity strokeWidth MozAnimationIterationCount MozBoxFlex MozBoxFlexGroup MozLineClamp msAnimationIterationCount msFlex msZoom msFlexGrow msFlexNegative msFlexOrder msFlexPositive msFlexShrink msGridColumn msGridColumnSpan msGridRow msGridRowSpan WebkitAnimationIterationCount WebkitBoxFlex WebKitBoxFlexGroup WebkitBoxOrdinalGroup WebkitColumnCount WebkitColumns WebkitFlex WebkitFlexGrow WebkitFlexPositive WebkitFlexShrink WebkitLineClamp".split(
      " "
    )
  );
  function tb(e, s, o) {
    var l = s.indexOf("--") === 0;
    o == null || typeof o == "boolean" || o === "" ? l ? e.setProperty(s, "") : s === "float" ? e.cssFloat = "" : e[s] = "" : l ? e.setProperty(s, o) : typeof o != "number" || o === 0 || EA.has(s) ? s === "float" ? e.cssFloat = o : e[s] = ("" + o).trim() : e[s] = o + "px";
  }
  function eb(e, s, o) {
    if (s != null && typeof s != "object")
      throw Error(a(62));
    if (e = e.style, o != null) {
      for (var l in o)
        !o.hasOwnProperty(l) || s != null && s.hasOwnProperty(l) || (l.indexOf("--") === 0 ? e.setProperty(l, "") : l === "float" ? e.cssFloat = "" : e[l] = "");
      for (var h in s)
        l = s[h], s.hasOwnProperty(h) && o[h] !== l && tb(e, h, l);
    } else
      for (var d in s)
        s.hasOwnProperty(d) && tb(e, d, s[d]);
  }
  function Qd(e) {
    if (e.indexOf("-") === -1) return !1;
    switch (e) {
      case "annotation-xml":
      case "color-profile":
      case "font-face":
      case "font-face-src":
      case "font-face-uri":
      case "font-face-format":
      case "font-face-name":
      case "missing-glyph":
        return !1;
      default:
        return !0;
    }
  }
  var AA = /* @__PURE__ */ new Map([
    ["acceptCharset", "accept-charset"],
    ["htmlFor", "for"],
    ["httpEquiv", "http-equiv"],
    ["crossOrigin", "crossorigin"],
    ["accentHeight", "accent-height"],
    ["alignmentBaseline", "alignment-baseline"],
    ["arabicForm", "arabic-form"],
    ["baselineShift", "baseline-shift"],
    ["capHeight", "cap-height"],
    ["clipPath", "clip-path"],
    ["clipRule", "clip-rule"],
    ["colorInterpolation", "color-interpolation"],
    ["colorInterpolationFilters", "color-interpolation-filters"],
    ["colorProfile", "color-profile"],
    ["colorRendering", "color-rendering"],
    ["dominantBaseline", "dominant-baseline"],
    ["enableBackground", "enable-background"],
    ["fillOpacity", "fill-opacity"],
    ["fillRule", "fill-rule"],
    ["floodColor", "flood-color"],
    ["floodOpacity", "flood-opacity"],
    ["fontFamily", "font-family"],
    ["fontSize", "font-size"],
    ["fontSizeAdjust", "font-size-adjust"],
    ["fontStretch", "font-stretch"],
    ["fontStyle", "font-style"],
    ["fontVariant", "font-variant"],
    ["fontWeight", "font-weight"],
    ["glyphName", "glyph-name"],
    ["glyphOrientationHorizontal", "glyph-orientation-horizontal"],
    ["glyphOrientationVertical", "glyph-orientation-vertical"],
    ["horizAdvX", "horiz-adv-x"],
    ["horizOriginX", "horiz-origin-x"],
    ["imageRendering", "image-rendering"],
    ["letterSpacing", "letter-spacing"],
    ["lightingColor", "lighting-color"],
    ["markerEnd", "marker-end"],
    ["markerMid", "marker-mid"],
    ["markerStart", "marker-start"],
    ["overlinePosition", "overline-position"],
    ["overlineThickness", "overline-thickness"],
    ["paintOrder", "paint-order"],
    ["panose-1", "panose-1"],
    ["pointerEvents", "pointer-events"],
    ["renderingIntent", "rendering-intent"],
    ["shapeRendering", "shape-rendering"],
    ["stopColor", "stop-color"],
    ["stopOpacity", "stop-opacity"],
    ["strikethroughPosition", "strikethrough-position"],
    ["strikethroughThickness", "strikethrough-thickness"],
    ["strokeDasharray", "stroke-dasharray"],
    ["strokeDashoffset", "stroke-dashoffset"],
    ["strokeLinecap", "stroke-linecap"],
    ["strokeLinejoin", "stroke-linejoin"],
    ["strokeMiterlimit", "stroke-miterlimit"],
    ["strokeOpacity", "stroke-opacity"],
    ["strokeWidth", "stroke-width"],
    ["textAnchor", "text-anchor"],
    ["textDecoration", "text-decoration"],
    ["textRendering", "text-rendering"],
    ["transformOrigin", "transform-origin"],
    ["underlinePosition", "underline-position"],
    ["underlineThickness", "underline-thickness"],
    ["unicodeBidi", "unicode-bidi"],
    ["unicodeRange", "unicode-range"],
    ["unitsPerEm", "units-per-em"],
    ["vAlphabetic", "v-alphabetic"],
    ["vHanging", "v-hanging"],
    ["vIdeographic", "v-ideographic"],
    ["vMathematical", "v-mathematical"],
    ["vectorEffect", "vector-effect"],
    ["vertAdvY", "vert-adv-y"],
    ["vertOriginX", "vert-origin-x"],
    ["vertOriginY", "vert-origin-y"],
    ["wordSpacing", "word-spacing"],
    ["writingMode", "writing-mode"],
    ["xmlnsXlink", "xmlns:xlink"],
    ["xHeight", "x-height"]
  ]), DA = /^[\u0000-\u001F ]*j[\r\n\t]*a[\r\n\t]*v[\r\n\t]*a[\r\n\t]*s[\r\n\t]*c[\r\n\t]*r[\r\n\t]*i[\r\n\t]*p[\r\n\t]*t[\r\n\t]*:/i;
  function hf(e) {
    return DA.test("" + e) ? "javascript:throw new Error('React has blocked a javascript: URL as a security precaution.')" : e;
  }
  var Kd = null;
  function Id(e) {
    return e = e.target || e.srcElement || window, e.correspondingUseElement && (e = e.correspondingUseElement), e.nodeType === 3 ? e.parentNode : e;
  }
  var Fo = null, Zo = null;
  function nb(e) {
    var s = jo(e);
    if (s && (e = s.stateNode)) {
      var o = e[We] || null;
      t: switch (e = s.stateNode, s.type) {
        case "input":
          if (Fd(
            e,
            o.value,
            o.defaultValue,
            o.defaultValue,
            o.checked,
            o.defaultChecked,
            o.type,
            o.name
          ), s = o.name, o.type === "radio" && s != null) {
            for (o = e; o.parentNode; ) o = o.parentNode;
            for (o = o.querySelectorAll(
              'input[name="' + wn(
                "" + s
              ) + '"][type="radio"]'
            ), s = 0; s < o.length; s++) {
              var l = o[s];
              if (l !== e && l.form === e.form) {
                var h = l[We] || null;
                if (!h) throw Error(a(90));
                Fd(
                  l,
                  h.value,
                  h.defaultValue,
                  h.defaultValue,
                  h.checked,
                  h.defaultChecked,
                  h.type,
                  h.name
                );
              }
            }
            for (s = 0; s < o.length; s++)
              l = o[s], l.form === e.form && Iv(l);
          }
          break t;
        case "textarea":
          Wv(e, o.value, o.defaultValue);
          break t;
        case "select":
          s = o.value, s != null && Yo(e, !!o.multiple, s, !1);
      }
    }
  }
  var $d = !1;
  function ib(e, s, o) {
    if ($d) return e(s, o);
    $d = !0;
    try {
      var l = e(s);
      return l;
    } finally {
      if ($d = !1, (Fo !== null || Zo !== null) && ($f(), Fo && (s = Fo, e = Zo, Zo = Fo = null, nb(s), e)))
        for (s = 0; s < e.length; s++) nb(e[s]);
    }
  }
  function Gl(e, s) {
    var o = e.stateNode;
    if (o === null) return null;
    var l = o[We] || null;
    if (l === null) return null;
    o = l[s];
    t: switch (s) {
      case "onClick":
      case "onClickCapture":
      case "onDoubleClick":
      case "onDoubleClickCapture":
      case "onMouseDown":
      case "onMouseDownCapture":
      case "onMouseMove":
      case "onMouseMoveCapture":
      case "onMouseUp":
      case "onMouseUpCapture":
      case "onMouseEnter":
        (l = !l.disabled) || (e = e.type, l = !(e === "button" || e === "input" || e === "select" || e === "textarea")), e = !l;
        break t;
      default:
        e = !1;
    }
    if (e) return null;
    if (o && typeof o != "function")
      throw Error(
        a(231, s, typeof o)
      );
    return o;
  }
  var Li = !(typeof window > "u" || typeof window.document > "u" || typeof window.document.createElement > "u"), Wd = !1;
  if (Li)
    try {
      var Yl = {};
      Object.defineProperty(Yl, "passive", {
        get: function() {
          Wd = !0;
        }
      }), window.addEventListener("test", Yl, Yl), window.removeEventListener("test", Yl, Yl);
    } catch {
      Wd = !1;
    }
  var ns = null, Jd = null, df = null;
  function sb() {
    if (df) return df;
    var e, s = Jd, o = s.length, l, h = "value" in ns ? ns.value : ns.textContent, d = h.length;
    for (e = 0; e < o && s[e] === h[e]; e++) ;
    var x = o - e;
    for (l = 1; l <= x && s[o - l] === h[d - l]; l++) ;
    return df = h.slice(e, 1 < l ? 1 - l : void 0);
  }
  function mf(e) {
    var s = e.keyCode;
    return "charCode" in e ? (e = e.charCode, e === 0 && s === 13 && (e = 13)) : e = s, e === 10 && (e = 13), 32 <= e || e === 13 ? e : 0;
  }
  function pf() {
    return !0;
  }
  function ab() {
    return !1;
  }
  function Je(e) {
    function s(o, l, h, d, x) {
      this._reactName = o, this._targetInst = h, this.type = l, this.nativeEvent = d, this.target = x, this.currentTarget = null;
      for (var M in e)
        e.hasOwnProperty(M) && (o = e[M], this[M] = o ? o(d) : d[M]);
      return this.isDefaultPrevented = (d.defaultPrevented != null ? d.defaultPrevented : d.returnValue === !1) ? pf : ab, this.isPropagationStopped = ab, this;
    }
    return g(s.prototype, {
      preventDefault: function() {
        this.defaultPrevented = !0;
        var o = this.nativeEvent;
        o && (o.preventDefault ? o.preventDefault() : typeof o.returnValue != "unknown" && (o.returnValue = !1), this.isDefaultPrevented = pf);
      },
      stopPropagation: function() {
        var o = this.nativeEvent;
        o && (o.stopPropagation ? o.stopPropagation() : typeof o.cancelBubble != "unknown" && (o.cancelBubble = !0), this.isPropagationStopped = pf);
      },
      persist: function() {
      },
      isPersistent: pf
    }), s;
  }
  var ma = {
    eventPhase: 0,
    bubbles: 0,
    cancelable: 0,
    timeStamp: function(e) {
      return e.timeStamp || Date.now();
    },
    defaultPrevented: 0,
    isTrusted: 0
  }, gf = Je(ma), Xl = g({}, ma, { view: 0, detail: 0 }), RA = Je(Xl), tm, em, Fl, yf = g({}, Xl, {
    screenX: 0,
    screenY: 0,
    clientX: 0,
    clientY: 0,
    pageX: 0,
    pageY: 0,
    ctrlKey: 0,
    shiftKey: 0,
    altKey: 0,
    metaKey: 0,
    getModifierState: im,
    button: 0,
    buttons: 0,
    relatedTarget: function(e) {
      return e.relatedTarget === void 0 ? e.fromElement === e.srcElement ? e.toElement : e.fromElement : e.relatedTarget;
    },
    movementX: function(e) {
      return "movementX" in e ? e.movementX : (e !== Fl && (Fl && e.type === "mousemove" ? (tm = e.screenX - Fl.screenX, em = e.screenY - Fl.screenY) : em = tm = 0, Fl = e), tm);
    },
    movementY: function(e) {
      return "movementY" in e ? e.movementY : em;
    }
  }), ob = Je(yf), OA = g({}, yf, { dataTransfer: 0 }), zA = Je(OA), kA = g({}, Xl, { relatedTarget: 0 }), nm = Je(kA), VA = g({}, ma, {
    animationName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), PA = Je(VA), LA = g({}, ma, {
    clipboardData: function(e) {
      return "clipboardData" in e ? e.clipboardData : window.clipboardData;
    }
  }), _A = Je(LA), BA = g({}, ma, { data: 0 }), rb = Je(BA), NA = {
    Esc: "Escape",
    Spacebar: " ",
    Left: "ArrowLeft",
    Up: "ArrowUp",
    Right: "ArrowRight",
    Down: "ArrowDown",
    Del: "Delete",
    Win: "OS",
    Menu: "ContextMenu",
    Apps: "ContextMenu",
    Scroll: "ScrollLock",
    MozPrintableKey: "Unidentified"
  }, UA = {
    8: "Backspace",
    9: "Tab",
    12: "Clear",
    13: "Enter",
    16: "Shift",
    17: "Control",
    18: "Alt",
    19: "Pause",
    20: "CapsLock",
    27: "Escape",
    32: " ",
    33: "PageUp",
    34: "PageDown",
    35: "End",
    36: "Home",
    37: "ArrowLeft",
    38: "ArrowUp",
    39: "ArrowRight",
    40: "ArrowDown",
    45: "Insert",
    46: "Delete",
    112: "F1",
    113: "F2",
    114: "F3",
    115: "F4",
    116: "F5",
    117: "F6",
    118: "F7",
    119: "F8",
    120: "F9",
    121: "F10",
    122: "F11",
    123: "F12",
    144: "NumLock",
    145: "ScrollLock",
    224: "Meta"
  }, jA = {
    Alt: "altKey",
    Control: "ctrlKey",
    Meta: "metaKey",
    Shift: "shiftKey"
  };
  function HA(e) {
    var s = this.nativeEvent;
    return s.getModifierState ? s.getModifierState(e) : (e = jA[e]) ? !!s[e] : !1;
  }
  function im() {
    return HA;
  }
  var qA = g({}, Xl, {
    key: function(e) {
      if (e.key) {
        var s = NA[e.key] || e.key;
        if (s !== "Unidentified") return s;
      }
      return e.type === "keypress" ? (e = mf(e), e === 13 ? "Enter" : String.fromCharCode(e)) : e.type === "keydown" || e.type === "keyup" ? UA[e.keyCode] || "Unidentified" : "";
    },
    code: 0,
    location: 0,
    ctrlKey: 0,
    shiftKey: 0,
    altKey: 0,
    metaKey: 0,
    repeat: 0,
    locale: 0,
    getModifierState: im,
    charCode: function(e) {
      return e.type === "keypress" ? mf(e) : 0;
    },
    keyCode: function(e) {
      return e.type === "keydown" || e.type === "keyup" ? e.keyCode : 0;
    },
    which: function(e) {
      return e.type === "keypress" ? mf(e) : e.type === "keydown" || e.type === "keyup" ? e.keyCode : 0;
    }
  }), GA = Je(qA), YA = g({}, yf, {
    pointerId: 0,
    width: 0,
    height: 0,
    pressure: 0,
    tangentialPressure: 0,
    tiltX: 0,
    tiltY: 0,
    twist: 0,
    pointerType: 0,
    isPrimary: 0
  }), lb = Je(YA), XA = g({}, Xl, {
    touches: 0,
    targetTouches: 0,
    changedTouches: 0,
    altKey: 0,
    metaKey: 0,
    ctrlKey: 0,
    shiftKey: 0,
    getModifierState: im
  }), FA = Je(XA), ZA = g({}, ma, {
    propertyName: 0,
    elapsedTime: 0,
    pseudoElement: 0
  }), QA = Je(ZA), KA = g({}, yf, {
    deltaX: function(e) {
      return "deltaX" in e ? e.deltaX : "wheelDeltaX" in e ? -e.wheelDeltaX : 0;
    },
    deltaY: function(e) {
      return "deltaY" in e ? e.deltaY : "wheelDeltaY" in e ? -e.wheelDeltaY : "wheelDelta" in e ? -e.wheelDelta : 0;
    },
    deltaZ: 0,
    deltaMode: 0
  }), IA = Je(KA), $A = g({}, ma, {
    newState: 0,
    oldState: 0
  }), WA = Je($A), JA = [9, 13, 27, 32], sm = Li && "CompositionEvent" in window, Zl = null;
  Li && "documentMode" in document && (Zl = document.documentMode);
  var tD = Li && "TextEvent" in window && !Zl, ub = Li && (!sm || Zl && 8 < Zl && 11 >= Zl), cb = " ", fb = !1;
  function hb(e, s) {
    switch (e) {
      case "keyup":
        return JA.indexOf(s.keyCode) !== -1;
      case "keydown":
        return s.keyCode !== 229;
      case "keypress":
      case "mousedown":
      case "focusout":
        return !0;
      default:
        return !1;
    }
  }
  function db(e) {
    return e = e.detail, typeof e == "object" && "data" in e ? e.data : null;
  }
  var Qo = !1;
  function eD(e, s) {
    switch (e) {
      case "compositionend":
        return db(s);
      case "keypress":
        return s.which !== 32 ? null : (fb = !0, cb);
      case "textInput":
        return e = s.data, e === cb && fb ? null : e;
      default:
        return null;
    }
  }
  function nD(e, s) {
    if (Qo)
      return e === "compositionend" || !sm && hb(e, s) ? (e = sb(), df = Jd = ns = null, Qo = !1, e) : null;
    switch (e) {
      case "paste":
        return null;
      case "keypress":
        if (!(s.ctrlKey || s.altKey || s.metaKey) || s.ctrlKey && s.altKey) {
          if (s.char && 1 < s.char.length)
            return s.char;
          if (s.which) return String.fromCharCode(s.which);
        }
        return null;
      case "compositionend":
        return ub && s.locale !== "ko" ? null : s.data;
      default:
        return null;
    }
  }
  var iD = {
    color: !0,
    date: !0,
    datetime: !0,
    "datetime-local": !0,
    email: !0,
    month: !0,
    number: !0,
    password: !0,
    range: !0,
    search: !0,
    tel: !0,
    text: !0,
    time: !0,
    url: !0,
    week: !0
  };
  function mb(e) {
    var s = e && e.nodeName && e.nodeName.toLowerCase();
    return s === "input" ? !!iD[e.type] : s === "textarea";
  }
  function pb(e, s, o, l) {
    Fo ? Zo ? Zo.push(l) : Zo = [l] : Fo = l, s = ih(s, "onChange"), 0 < s.length && (o = new gf(
      "onChange",
      "change",
      null,
      o,
      l
    ), e.push({ event: o, listeners: s }));
  }
  var Ql = null, Kl = null;
  function sD(e) {
    Kx(e, 0);
  }
  function vf(e) {
    var s = ql(e);
    if (Iv(s)) return e;
  }
  function gb(e, s) {
    if (e === "change") return s;
  }
  var yb = !1;
  if (Li) {
    var am;
    if (Li) {
      var om = "oninput" in document;
      if (!om) {
        var vb = document.createElement("div");
        vb.setAttribute("oninput", "return;"), om = typeof vb.oninput == "function";
      }
      am = om;
    } else am = !1;
    yb = am && (!document.documentMode || 9 < document.documentMode);
  }
  function bb() {
    Ql && (Ql.detachEvent("onpropertychange", xb), Kl = Ql = null);
  }
  function xb(e) {
    if (e.propertyName === "value" && vf(Kl)) {
      var s = [];
      pb(
        s,
        Kl,
        e,
        Id(e)
      ), ib(sD, s);
    }
  }
  function aD(e, s, o) {
    e === "focusin" ? (bb(), Ql = s, Kl = o, Ql.attachEvent("onpropertychange", xb)) : e === "focusout" && bb();
  }
  function oD(e) {
    if (e === "selectionchange" || e === "keyup" || e === "keydown")
      return vf(Kl);
  }
  function rD(e, s) {
    if (e === "click") return vf(s);
  }
  function lD(e, s) {
    if (e === "input" || e === "change")
      return vf(s);
  }
  function uD(e, s) {
    return e === s && (e !== 0 || 1 / e === 1 / s) || e !== e && s !== s;
  }
  var cn = typeof Object.is == "function" ? Object.is : uD;
  function Il(e, s) {
    if (cn(e, s)) return !0;
    if (typeof e != "object" || e === null || typeof s != "object" || s === null)
      return !1;
    var o = Object.keys(e), l = Object.keys(s);
    if (o.length !== l.length) return !1;
    for (l = 0; l < o.length; l++) {
      var h = o[l];
      if (!Ld.call(s, h) || !cn(e[h], s[h]))
        return !1;
    }
    return !0;
  }
  function Sb(e) {
    for (; e && e.firstChild; ) e = e.firstChild;
    return e;
  }
  function wb(e, s) {
    var o = Sb(e);
    e = 0;
    for (var l; o; ) {
      if (o.nodeType === 3) {
        if (l = e + o.textContent.length, e <= s && l >= s)
          return { node: o, offset: s - e };
        e = l;
      }
      t: {
        for (; o; ) {
          if (o.nextSibling) {
            o = o.nextSibling;
            break t;
          }
          o = o.parentNode;
        }
        o = void 0;
      }
      o = Sb(o);
    }
  }
  function Mb(e, s) {
    return e && s ? e === s ? !0 : e && e.nodeType === 3 ? !1 : s && s.nodeType === 3 ? Mb(e, s.parentNode) : "contains" in e ? e.contains(s) : e.compareDocumentPosition ? !!(e.compareDocumentPosition(s) & 16) : !1 : !1;
  }
  function Tb(e) {
    e = e != null && e.ownerDocument != null && e.ownerDocument.defaultView != null ? e.ownerDocument.defaultView : window;
    for (var s = ff(e.document); s instanceof e.HTMLIFrameElement; ) {
      try {
        var o = typeof s.contentWindow.location.href == "string";
      } catch {
        o = !1;
      }
      if (o) e = s.contentWindow;
      else break;
      s = ff(e.document);
    }
    return s;
  }
  function rm(e) {
    var s = e && e.nodeName && e.nodeName.toLowerCase();
    return s && (s === "input" && (e.type === "text" || e.type === "search" || e.type === "tel" || e.type === "url" || e.type === "password") || s === "textarea" || e.contentEditable === "true");
  }
  var cD = Li && "documentMode" in document && 11 >= document.documentMode, Ko = null, lm = null, $l = null, um = !1;
  function Cb(e, s, o) {
    var l = o.window === o ? o.document : o.nodeType === 9 ? o : o.ownerDocument;
    um || Ko == null || Ko !== ff(l) || (l = Ko, "selectionStart" in l && rm(l) ? l = { start: l.selectionStart, end: l.selectionEnd } : (l = (l.ownerDocument && l.ownerDocument.defaultView || window).getSelection(), l = {
      anchorNode: l.anchorNode,
      anchorOffset: l.anchorOffset,
      focusNode: l.focusNode,
      focusOffset: l.focusOffset
    }), $l && Il($l, l) || ($l = l, l = ih(lm, "onSelect"), 0 < l.length && (s = new gf(
      "onSelect",
      "select",
      null,
      s,
      o
    ), e.push({ event: s, listeners: l }), s.target = Ko)));
  }
  function pa(e, s) {
    var o = {};
    return o[e.toLowerCase()] = s.toLowerCase(), o["Webkit" + e] = "webkit" + s, o["Moz" + e] = "moz" + s, o;
  }
  var Io = {
    animationend: pa("Animation", "AnimationEnd"),
    animationiteration: pa("Animation", "AnimationIteration"),
    animationstart: pa("Animation", "AnimationStart"),
    transitionrun: pa("Transition", "TransitionRun"),
    transitionstart: pa("Transition", "TransitionStart"),
    transitioncancel: pa("Transition", "TransitionCancel"),
    transitionend: pa("Transition", "TransitionEnd")
  }, cm = {}, Eb = {};
  Li && (Eb = document.createElement("div").style, "AnimationEvent" in window || (delete Io.animationend.animation, delete Io.animationiteration.animation, delete Io.animationstart.animation), "TransitionEvent" in window || delete Io.transitionend.transition);
  function ga(e) {
    if (cm[e]) return cm[e];
    if (!Io[e]) return e;
    var s = Io[e], o;
    for (o in s)
      if (s.hasOwnProperty(o) && o in Eb)
        return cm[e] = s[o];
    return e;
  }
  var Ab = ga("animationend"), Db = ga("animationiteration"), Rb = ga("animationstart"), fD = ga("transitionrun"), hD = ga("transitionstart"), dD = ga("transitioncancel"), Ob = ga("transitionend"), zb = /* @__PURE__ */ new Map(), fm = "abort auxClick beforeToggle cancel canPlay canPlayThrough click close contextMenu copy cut drag dragEnd dragEnter dragExit dragLeave dragOver dragStart drop durationChange emptied encrypted ended error gotPointerCapture input invalid keyDown keyPress keyUp load loadedData loadedMetadata loadStart lostPointerCapture mouseDown mouseMove mouseOut mouseOver mouseUp paste pause play playing pointerCancel pointerDown pointerMove pointerOut pointerOver pointerUp progress rateChange reset resize seeked seeking stalled submit suspend timeUpdate touchCancel touchEnd touchStart volumeChange scroll toggle touchMove waiting wheel".split(
    " "
  );
  fm.push("scrollEnd");
  function Xn(e, s) {
    zb.set(e, s), da(s, [e]);
  }
  var kb = /* @__PURE__ */ new WeakMap();
  function Mn(e, s) {
    if (typeof e == "object" && e !== null) {
      var o = kb.get(e);
      return o !== void 0 ? o : (s = {
        value: e,
        source: s,
        stack: Qv(s)
      }, kb.set(e, s), s);
    }
    return {
      value: e,
      source: s,
      stack: Qv(s)
    };
  }
  var Tn = [], $o = 0, hm = 0;
  function bf() {
    for (var e = $o, s = hm = $o = 0; s < e; ) {
      var o = Tn[s];
      Tn[s++] = null;
      var l = Tn[s];
      Tn[s++] = null;
      var h = Tn[s];
      Tn[s++] = null;
      var d = Tn[s];
      if (Tn[s++] = null, l !== null && h !== null) {
        var x = l.pending;
        x === null ? h.next = h : (h.next = x.next, x.next = h), l.pending = h;
      }
      d !== 0 && Vb(o, h, d);
    }
  }
  function xf(e, s, o, l) {
    Tn[$o++] = e, Tn[$o++] = s, Tn[$o++] = o, Tn[$o++] = l, hm |= l, e.lanes |= l, e = e.alternate, e !== null && (e.lanes |= l);
  }
  function dm(e, s, o, l) {
    return xf(e, s, o, l), Sf(e);
  }
  function Wo(e, s) {
    return xf(e, null, null, s), Sf(e);
  }
  function Vb(e, s, o) {
    e.lanes |= o;
    var l = e.alternate;
    l !== null && (l.lanes |= o);
    for (var h = !1, d = e.return; d !== null; )
      d.childLanes |= o, l = d.alternate, l !== null && (l.childLanes |= o), d.tag === 22 && (e = d.stateNode, e === null || e._visibility & 1 || (h = !0)), e = d, d = d.return;
    return e.tag === 3 ? (d = e.stateNode, h && s !== null && (h = 31 - un(o), e = d.hiddenUpdates, l = e[h], l === null ? e[h] = [s] : l.push(s), s.lane = o | 536870912), d) : null;
  }
  function Sf(e) {
    if (50 < wu)
      throw wu = 0, bp = null, Error(a(185));
    for (var s = e.return; s !== null; )
      e = s, s = e.return;
    return e.tag === 3 ? e.stateNode : null;
  }
  var Jo = {};
  function mD(e, s, o, l) {
    this.tag = e, this.key = o, this.sibling = this.child = this.return = this.stateNode = this.type = this.elementType = null, this.index = 0, this.refCleanup = this.ref = null, this.pendingProps = s, this.dependencies = this.memoizedState = this.updateQueue = this.memoizedProps = null, this.mode = l, this.subtreeFlags = this.flags = 0, this.deletions = null, this.childLanes = this.lanes = 0, this.alternate = null;
  }
  function fn(e, s, o, l) {
    return new mD(e, s, o, l);
  }
  function mm(e) {
    return e = e.prototype, !(!e || !e.isReactComponent);
  }
  function _i(e, s) {
    var o = e.alternate;
    return o === null ? (o = fn(
      e.tag,
      s,
      e.key,
      e.mode
    ), o.elementType = e.elementType, o.type = e.type, o.stateNode = e.stateNode, o.alternate = e, e.alternate = o) : (o.pendingProps = s, o.type = e.type, o.flags = 0, o.subtreeFlags = 0, o.deletions = null), o.flags = e.flags & 65011712, o.childLanes = e.childLanes, o.lanes = e.lanes, o.child = e.child, o.memoizedProps = e.memoizedProps, o.memoizedState = e.memoizedState, o.updateQueue = e.updateQueue, s = e.dependencies, o.dependencies = s === null ? null : { lanes: s.lanes, firstContext: s.firstContext }, o.sibling = e.sibling, o.index = e.index, o.ref = e.ref, o.refCleanup = e.refCleanup, o;
  }
  function Pb(e, s) {
    e.flags &= 65011714;
    var o = e.alternate;
    return o === null ? (e.childLanes = 0, e.lanes = s, e.child = null, e.subtreeFlags = 0, e.memoizedProps = null, e.memoizedState = null, e.updateQueue = null, e.dependencies = null, e.stateNode = null) : (e.childLanes = o.childLanes, e.lanes = o.lanes, e.child = o.child, e.subtreeFlags = 0, e.deletions = null, e.memoizedProps = o.memoizedProps, e.memoizedState = o.memoizedState, e.updateQueue = o.updateQueue, e.type = o.type, s = o.dependencies, e.dependencies = s === null ? null : {
      lanes: s.lanes,
      firstContext: s.firstContext
    }), e;
  }
  function wf(e, s, o, l, h, d) {
    var x = 0;
    if (l = e, typeof e == "function") mm(e) && (x = 1);
    else if (typeof e == "string")
      x = gR(
        e,
        o,
        rt.current
      ) ? 26 : e === "html" || e === "head" || e === "body" ? 27 : 5;
    else
      t: switch (e) {
        case lt:
          return e = fn(31, o, s, h), e.elementType = lt, e.lanes = d, e;
        case T:
          return ya(o.children, h, d, s);
        case C:
          x = 8, h |= 24;
          break;
        case R:
          return e = fn(12, o, s, h | 2), e.elementType = R, e.lanes = d, e;
        case Q:
          return e = fn(13, o, s, h), e.elementType = Q, e.lanes = d, e;
        case ut:
          return e = fn(19, o, s, h), e.elementType = ut, e.lanes = d, e;
        default:
          if (typeof e == "object" && e !== null)
            switch (e.$$typeof) {
              case z:
              case H:
                x = 10;
                break t;
              case B:
                x = 9;
                break t;
              case X:
                x = 11;
                break t;
              case st:
                x = 14;
                break t;
              case $:
                x = 16, l = null;
                break t;
            }
          x = 29, o = Error(
            a(130, e === null ? "null" : typeof e, "")
          ), l = null;
      }
    return s = fn(x, o, s, h), s.elementType = e, s.type = l, s.lanes = d, s;
  }
  function ya(e, s, o, l) {
    return e = fn(7, e, l, s), e.lanes = o, e;
  }
  function pm(e, s, o) {
    return e = fn(6, e, null, s), e.lanes = o, e;
  }
  function gm(e, s, o) {
    return s = fn(
      4,
      e.children !== null ? e.children : [],
      e.key,
      s
    ), s.lanes = o, s.stateNode = {
      containerInfo: e.containerInfo,
      pendingChildren: null,
      implementation: e.implementation
    }, s;
  }
  var tr = [], er = 0, Mf = null, Tf = 0, Cn = [], En = 0, va = null, Bi = 1, Ni = "";
  function ba(e, s) {
    tr[er++] = Tf, tr[er++] = Mf, Mf = e, Tf = s;
  }
  function Lb(e, s, o) {
    Cn[En++] = Bi, Cn[En++] = Ni, Cn[En++] = va, va = e;
    var l = Bi;
    e = Ni;
    var h = 32 - un(l) - 1;
    l &= ~(1 << h), o += 1;
    var d = 32 - un(s) + h;
    if (30 < d) {
      var x = h - h % 5;
      d = (l & (1 << x) - 1).toString(32), l >>= x, h -= x, Bi = 1 << 32 - un(s) + h | o << h | l, Ni = d + e;
    } else
      Bi = 1 << d | o << h | l, Ni = e;
  }
  function ym(e) {
    e.return !== null && (ba(e, 1), Lb(e, 1, 0));
  }
  function vm(e) {
    for (; e === Mf; )
      Mf = tr[--er], tr[er] = null, Tf = tr[--er], tr[er] = null;
    for (; e === va; )
      va = Cn[--En], Cn[En] = null, Ni = Cn[--En], Cn[En] = null, Bi = Cn[--En], Cn[En] = null;
  }
  var Ge = null, oe = null, _t = !1, xa = null, ai = !1, bm = Error(a(519));
  function Sa(e) {
    var s = Error(a(418, ""));
    throw tu(Mn(s, e)), bm;
  }
  function _b(e) {
    var s = e.stateNode, o = e.type, l = e.memoizedProps;
    switch (s[Le] = e, s[We] = l, o) {
      case "dialog":
        At("cancel", s), At("close", s);
        break;
      case "iframe":
      case "object":
      case "embed":
        At("load", s);
        break;
      case "video":
      case "audio":
        for (o = 0; o < Tu.length; o++)
          At(Tu[o], s);
        break;
      case "source":
        At("error", s);
        break;
      case "img":
      case "image":
      case "link":
        At("error", s), At("load", s);
        break;
      case "details":
        At("toggle", s);
        break;
      case "input":
        At("invalid", s), $v(
          s,
          l.value,
          l.defaultValue,
          l.checked,
          l.defaultChecked,
          l.type,
          l.name,
          !0
        ), cf(s);
        break;
      case "select":
        At("invalid", s);
        break;
      case "textarea":
        At("invalid", s), Jv(s, l.value, l.defaultValue, l.children), cf(s);
    }
    o = l.children, typeof o != "string" && typeof o != "number" && typeof o != "bigint" || s.textContent === "" + o || l.suppressHydrationWarning === !0 || Jx(s.textContent, o) ? (l.popover != null && (At("beforetoggle", s), At("toggle", s)), l.onScroll != null && At("scroll", s), l.onScrollEnd != null && At("scrollend", s), l.onClick != null && (s.onclick = sh), s = !0) : s = !1, s || Sa(e);
  }
  function Bb(e) {
    for (Ge = e.return; Ge; )
      switch (Ge.tag) {
        case 5:
        case 13:
          ai = !1;
          return;
        case 27:
        case 3:
          ai = !0;
          return;
        default:
          Ge = Ge.return;
      }
  }
  function Wl(e) {
    if (e !== Ge) return !1;
    if (!_t) return Bb(e), _t = !0, !1;
    var s = e.tag, o;
    if ((o = s !== 3 && s !== 27) && ((o = s === 5) && (o = e.type, o = !(o !== "form" && o !== "button") || Lp(e.type, e.memoizedProps)), o = !o), o && oe && Sa(e), Bb(e), s === 13) {
      if (e = e.memoizedState, e = e !== null ? e.dehydrated : null, !e) throw Error(a(317));
      t: {
        for (e = e.nextSibling, s = 0; e; ) {
          if (e.nodeType === 8)
            if (o = e.data, o === "/$") {
              if (s === 0) {
                oe = Zn(e.nextSibling);
                break t;
              }
              s--;
            } else
              o !== "$" && o !== "$!" && o !== "$?" || s++;
          e = e.nextSibling;
        }
        oe = null;
      }
    } else
      s === 27 ? (s = oe, vs(e.type) ? (e = Up, Up = null, oe = e) : oe = s) : oe = Ge ? Zn(e.stateNode.nextSibling) : null;
    return !0;
  }
  function Jl() {
    oe = Ge = null, _t = !1;
  }
  function Nb() {
    var e = xa;
    return e !== null && (nn === null ? nn = e : nn.push.apply(
      nn,
      e
    ), xa = null), e;
  }
  function tu(e) {
    xa === null ? xa = [e] : xa.push(e);
  }
  var xm = Y(null), wa = null, Ui = null;
  function is(e, s, o) {
    tt(xm, s._currentValue), s._currentValue = o;
  }
  function ji(e) {
    e._currentValue = xm.current, et(xm);
  }
  function Sm(e, s, o) {
    for (; e !== null; ) {
      var l = e.alternate;
      if ((e.childLanes & s) !== s ? (e.childLanes |= s, l !== null && (l.childLanes |= s)) : l !== null && (l.childLanes & s) !== s && (l.childLanes |= s), e === o) break;
      e = e.return;
    }
  }
  function wm(e, s, o, l) {
    var h = e.child;
    for (h !== null && (h.return = e); h !== null; ) {
      var d = h.dependencies;
      if (d !== null) {
        var x = h.child;
        d = d.firstContext;
        t: for (; d !== null; ) {
          var M = d;
          d = h;
          for (var E = 0; E < s.length; E++)
            if (M.context === s[E]) {
              d.lanes |= o, M = d.alternate, M !== null && (M.lanes |= o), Sm(
                d.return,
                o,
                e
              ), l || (x = null);
              break t;
            }
          d = M.next;
        }
      } else if (h.tag === 18) {
        if (x = h.return, x === null) throw Error(a(341));
        x.lanes |= o, d = x.alternate, d !== null && (d.lanes |= o), Sm(x, o, e), x = null;
      } else x = h.child;
      if (x !== null) x.return = h;
      else
        for (x = h; x !== null; ) {
          if (x === e) {
            x = null;
            break;
          }
          if (h = x.sibling, h !== null) {
            h.return = x.return, x = h;
            break;
          }
          x = x.return;
        }
      h = x;
    }
  }
  function eu(e, s, o, l) {
    e = null;
    for (var h = s, d = !1; h !== null; ) {
      if (!d) {
        if ((h.flags & 524288) !== 0) d = !0;
        else if ((h.flags & 262144) !== 0) break;
      }
      if (h.tag === 10) {
        var x = h.alternate;
        if (x === null) throw Error(a(387));
        if (x = x.memoizedProps, x !== null) {
          var M = h.type;
          cn(h.pendingProps.value, x.value) || (e !== null ? e.push(M) : e = [M]);
        }
      } else if (h === qe.current) {
        if (x = h.alternate, x === null) throw Error(a(387));
        x.memoizedState.memoizedState !== h.memoizedState.memoizedState && (e !== null ? e.push(Ou) : e = [Ou]);
      }
      h = h.return;
    }
    e !== null && wm(
      s,
      e,
      o,
      l
    ), s.flags |= 262144;
  }
  function Cf(e) {
    for (e = e.firstContext; e !== null; ) {
      if (!cn(
        e.context._currentValue,
        e.memoizedValue
      ))
        return !0;
      e = e.next;
    }
    return !1;
  }
  function Ma(e) {
    wa = e, Ui = null, e = e.dependencies, e !== null && (e.firstContext = null);
  }
  function _e(e) {
    return Ub(wa, e);
  }
  function Ef(e, s) {
    return wa === null && Ma(e), Ub(e, s);
  }
  function Ub(e, s) {
    var o = s._currentValue;
    if (s = { context: s, memoizedValue: o, next: null }, Ui === null) {
      if (e === null) throw Error(a(308));
      Ui = s, e.dependencies = { lanes: 0, firstContext: s }, e.flags |= 524288;
    } else Ui = Ui.next = s;
    return o;
  }
  var pD = typeof AbortController < "u" ? AbortController : function() {
    var e = [], s = this.signal = {
      aborted: !1,
      addEventListener: function(o, l) {
        e.push(l);
      }
    };
    this.abort = function() {
      s.aborted = !0, e.forEach(function(o) {
        return o();
      });
    };
  }, gD = n.unstable_scheduleCallback, yD = n.unstable_NormalPriority, xe = {
    $$typeof: H,
    Consumer: null,
    Provider: null,
    _currentValue: null,
    _currentValue2: null,
    _threadCount: 0
  };
  function Mm() {
    return {
      controller: new pD(),
      data: /* @__PURE__ */ new Map(),
      refCount: 0
    };
  }
  function nu(e) {
    e.refCount--, e.refCount === 0 && gD(yD, function() {
      e.controller.abort();
    });
  }
  var iu = null, Tm = 0, nr = 0, ir = null;
  function vD(e, s) {
    if (iu === null) {
      var o = iu = [];
      Tm = 0, nr = Ep(), ir = {
        status: "pending",
        value: void 0,
        then: function(l) {
          o.push(l);
        }
      };
    }
    return Tm++, s.then(jb, jb), s;
  }
  function jb() {
    if (--Tm === 0 && iu !== null) {
      ir !== null && (ir.status = "fulfilled");
      var e = iu;
      iu = null, nr = 0, ir = null;
      for (var s = 0; s < e.length; s++) (0, e[s])();
    }
  }
  function bD(e, s) {
    var o = [], l = {
      status: "pending",
      value: null,
      reason: null,
      then: function(h) {
        o.push(h);
      }
    };
    return e.then(
      function() {
        l.status = "fulfilled", l.value = s;
        for (var h = 0; h < o.length; h++) (0, o[h])(s);
      },
      function(h) {
        for (l.status = "rejected", l.reason = h, h = 0; h < o.length; h++)
          (0, o[h])(void 0);
      }
    ), l;
  }
  var Hb = j.S;
  j.S = function(e, s) {
    typeof s == "object" && s !== null && typeof s.then == "function" && vD(e, s), Hb !== null && Hb(e, s);
  };
  var Ta = Y(null);
  function Cm() {
    var e = Ta.current;
    return e !== null ? e : $t.pooledCache;
  }
  function Af(e, s) {
    s === null ? tt(Ta, Ta.current) : tt(Ta, s.pool);
  }
  function qb() {
    var e = Cm();
    return e === null ? null : { parent: xe._currentValue, pool: e };
  }
  var su = Error(a(460)), Gb = Error(a(474)), Df = Error(a(542)), Em = { then: function() {
  } };
  function Yb(e) {
    return e = e.status, e === "fulfilled" || e === "rejected";
  }
  function Rf() {
  }
  function Xb(e, s, o) {
    switch (o = e[o], o === void 0 ? e.push(s) : o !== s && (s.then(Rf, Rf), s = o), s.status) {
      case "fulfilled":
        return s.value;
      case "rejected":
        throw e = s.reason, Zb(e), e;
      default:
        if (typeof s.status == "string") s.then(Rf, Rf);
        else {
          if (e = $t, e !== null && 100 < e.shellSuspendCounter)
            throw Error(a(482));
          e = s, e.status = "pending", e.then(
            function(l) {
              if (s.status === "pending") {
                var h = s;
                h.status = "fulfilled", h.value = l;
              }
            },
            function(l) {
              if (s.status === "pending") {
                var h = s;
                h.status = "rejected", h.reason = l;
              }
            }
          );
        }
        switch (s.status) {
          case "fulfilled":
            return s.value;
          case "rejected":
            throw e = s.reason, Zb(e), e;
        }
        throw au = s, su;
    }
  }
  var au = null;
  function Fb() {
    if (au === null) throw Error(a(459));
    var e = au;
    return au = null, e;
  }
  function Zb(e) {
    if (e === su || e === Df)
      throw Error(a(483));
  }
  var ss = !1;
  function Am(e) {
    e.updateQueue = {
      baseState: e.memoizedState,
      firstBaseUpdate: null,
      lastBaseUpdate: null,
      shared: { pending: null, lanes: 0, hiddenCallbacks: null },
      callbacks: null
    };
  }
  function Dm(e, s) {
    e = e.updateQueue, s.updateQueue === e && (s.updateQueue = {
      baseState: e.baseState,
      firstBaseUpdate: e.firstBaseUpdate,
      lastBaseUpdate: e.lastBaseUpdate,
      shared: e.shared,
      callbacks: null
    });
  }
  function as(e) {
    return { lane: e, tag: 0, payload: null, callback: null, next: null };
  }
  function os(e, s, o) {
    var l = e.updateQueue;
    if (l === null) return null;
    if (l = l.shared, (Nt & 2) !== 0) {
      var h = l.pending;
      return h === null ? s.next = s : (s.next = h.next, h.next = s), l.pending = s, s = Sf(e), Vb(e, null, o), s;
    }
    return xf(e, l, s, o), Sf(e);
  }
  function ou(e, s, o) {
    if (s = s.updateQueue, s !== null && (s = s.shared, (o & 4194048) !== 0)) {
      var l = s.lanes;
      l &= e.pendingLanes, o |= l, s.lanes = o, jv(e, o);
    }
  }
  function Rm(e, s) {
    var o = e.updateQueue, l = e.alternate;
    if (l !== null && (l = l.updateQueue, o === l)) {
      var h = null, d = null;
      if (o = o.firstBaseUpdate, o !== null) {
        do {
          var x = {
            lane: o.lane,
            tag: o.tag,
            payload: o.payload,
            callback: null,
            next: null
          };
          d === null ? h = d = x : d = d.next = x, o = o.next;
        } while (o !== null);
        d === null ? h = d = s : d = d.next = s;
      } else h = d = s;
      o = {
        baseState: l.baseState,
        firstBaseUpdate: h,
        lastBaseUpdate: d,
        shared: l.shared,
        callbacks: l.callbacks
      }, e.updateQueue = o;
      return;
    }
    e = o.lastBaseUpdate, e === null ? o.firstBaseUpdate = s : e.next = s, o.lastBaseUpdate = s;
  }
  var Om = !1;
  function ru() {
    if (Om) {
      var e = ir;
      if (e !== null) throw e;
    }
  }
  function lu(e, s, o, l) {
    Om = !1;
    var h = e.updateQueue;
    ss = !1;
    var d = h.firstBaseUpdate, x = h.lastBaseUpdate, M = h.shared.pending;
    if (M !== null) {
      h.shared.pending = null;
      var E = M, _ = E.next;
      E.next = null, x === null ? d = _ : x.next = _, x = E;
      var F = e.alternate;
      F !== null && (F = F.updateQueue, M = F.lastBaseUpdate, M !== x && (M === null ? F.firstBaseUpdate = _ : M.next = _, F.lastBaseUpdate = E));
    }
    if (d !== null) {
      var I = h.baseState;
      x = 0, F = _ = E = null, M = d;
      do {
        var N = M.lane & -536870913, U = N !== M.lane;
        if (U ? (Rt & N) === N : (l & N) === N) {
          N !== 0 && N === nr && (Om = !0), F !== null && (F = F.next = {
            lane: 0,
            tag: M.tag,
            payload: M.payload,
            callback: null,
            next: null
          });
          t: {
            var pt = e, dt = M;
            N = s;
            var Gt = o;
            switch (dt.tag) {
              case 1:
                if (pt = dt.payload, typeof pt == "function") {
                  I = pt.call(Gt, I, N);
                  break t;
                }
                I = pt;
                break t;
              case 3:
                pt.flags = pt.flags & -65537 | 128;
              case 0:
                if (pt = dt.payload, N = typeof pt == "function" ? pt.call(Gt, I, N) : pt, N == null) break t;
                I = g({}, I, N);
                break t;
              case 2:
                ss = !0;
            }
          }
          N = M.callback, N !== null && (e.flags |= 64, U && (e.flags |= 8192), U = h.callbacks, U === null ? h.callbacks = [N] : U.push(N));
        } else
          U = {
            lane: N,
            tag: M.tag,
            payload: M.payload,
            callback: M.callback,
            next: null
          }, F === null ? (_ = F = U, E = I) : F = F.next = U, x |= N;
        if (M = M.next, M === null) {
          if (M = h.shared.pending, M === null)
            break;
          U = M, M = U.next, U.next = null, h.lastBaseUpdate = U, h.shared.pending = null;
        }
      } while (!0);
      F === null && (E = I), h.baseState = E, h.firstBaseUpdate = _, h.lastBaseUpdate = F, d === null && (h.shared.lanes = 0), ms |= x, e.lanes = x, e.memoizedState = I;
    }
  }
  function Qb(e, s) {
    if (typeof e != "function")
      throw Error(a(191, e));
    e.call(s);
  }
  function Kb(e, s) {
    var o = e.callbacks;
    if (o !== null)
      for (e.callbacks = null, e = 0; e < o.length; e++)
        Qb(o[e], s);
  }
  var sr = Y(null), Of = Y(0);
  function Ib(e, s) {
    e = Zi, tt(Of, e), tt(sr, s), Zi = e | s.baseLanes;
  }
  function zm() {
    tt(Of, Zi), tt(sr, sr.current);
  }
  function km() {
    Zi = Of.current, et(sr), et(Of);
  }
  var rs = 0, Tt = null, Ht = null, pe = null, zf = !1, ar = !1, Ca = !1, kf = 0, uu = 0, or = null, xD = 0;
  function ue() {
    throw Error(a(321));
  }
  function Vm(e, s) {
    if (s === null) return !1;
    for (var o = 0; o < s.length && o < e.length; o++)
      if (!cn(e[o], s[o])) return !1;
    return !0;
  }
  function Pm(e, s, o, l, h, d) {
    return rs = d, Tt = s, s.memoizedState = null, s.updateQueue = null, s.lanes = 0, j.H = e === null || e.memoizedState === null ? V0 : P0, Ca = !1, d = o(l, h), Ca = !1, ar && (d = Wb(
      s,
      o,
      l,
      h
    )), $b(e), d;
  }
  function $b(e) {
    j.H = Nf;
    var s = Ht !== null && Ht.next !== null;
    if (rs = 0, pe = Ht = Tt = null, zf = !1, uu = 0, or = null, s) throw Error(a(300));
    e === null || Te || (e = e.dependencies, e !== null && Cf(e) && (Te = !0));
  }
  function Wb(e, s, o, l) {
    Tt = e;
    var h = 0;
    do {
      if (ar && (or = null), uu = 0, ar = !1, 25 <= h) throw Error(a(301));
      if (h += 1, pe = Ht = null, e.updateQueue != null) {
        var d = e.updateQueue;
        d.lastEffect = null, d.events = null, d.stores = null, d.memoCache != null && (d.memoCache.index = 0);
      }
      j.H = AD, d = s(o, l);
    } while (ar);
    return d;
  }
  function SD() {
    var e = j.H, s = e.useState()[0];
    return s = typeof s.then == "function" ? cu(s) : s, e = e.useState()[0], (Ht !== null ? Ht.memoizedState : null) !== e && (Tt.flags |= 1024), s;
  }
  function Lm() {
    var e = kf !== 0;
    return kf = 0, e;
  }
  function _m(e, s, o) {
    s.updateQueue = e.updateQueue, s.flags &= -2053, e.lanes &= ~o;
  }
  function Bm(e) {
    if (zf) {
      for (e = e.memoizedState; e !== null; ) {
        var s = e.queue;
        s !== null && (s.pending = null), e = e.next;
      }
      zf = !1;
    }
    rs = 0, pe = Ht = Tt = null, ar = !1, uu = kf = 0, or = null;
  }
  function tn() {
    var e = {
      memoizedState: null,
      baseState: null,
      baseQueue: null,
      queue: null,
      next: null
    };
    return pe === null ? Tt.memoizedState = pe = e : pe = pe.next = e, pe;
  }
  function ge() {
    if (Ht === null) {
      var e = Tt.alternate;
      e = e !== null ? e.memoizedState : null;
    } else e = Ht.next;
    var s = pe === null ? Tt.memoizedState : pe.next;
    if (s !== null)
      pe = s, Ht = e;
    else {
      if (e === null)
        throw Tt.alternate === null ? Error(a(467)) : Error(a(310));
      Ht = e, e = {
        memoizedState: Ht.memoizedState,
        baseState: Ht.baseState,
        baseQueue: Ht.baseQueue,
        queue: Ht.queue,
        next: null
      }, pe === null ? Tt.memoizedState = pe = e : pe = pe.next = e;
    }
    return pe;
  }
  function Nm() {
    return { lastEffect: null, events: null, stores: null, memoCache: null };
  }
  function cu(e) {
    var s = uu;
    return uu += 1, or === null && (or = []), e = Xb(or, e, s), s = Tt, (pe === null ? s.memoizedState : pe.next) === null && (s = s.alternate, j.H = s === null || s.memoizedState === null ? V0 : P0), e;
  }
  function Vf(e) {
    if (e !== null && typeof e == "object") {
      if (typeof e.then == "function") return cu(e);
      if (e.$$typeof === H) return _e(e);
    }
    throw Error(a(438, String(e)));
  }
  function Um(e) {
    var s = null, o = Tt.updateQueue;
    if (o !== null && (s = o.memoCache), s == null) {
      var l = Tt.alternate;
      l !== null && (l = l.updateQueue, l !== null && (l = l.memoCache, l != null && (s = {
        data: l.data.map(function(h) {
          return h.slice();
        }),
        index: 0
      })));
    }
    if (s == null && (s = { data: [], index: 0 }), o === null && (o = Nm(), Tt.updateQueue = o), o.memoCache = s, o = s.data[s.index], o === void 0)
      for (o = s.data[s.index] = Array(e), l = 0; l < e; l++)
        o[l] = nt;
    return s.index++, o;
  }
  function Hi(e, s) {
    return typeof s == "function" ? s(e) : s;
  }
  function Pf(e) {
    var s = ge();
    return jm(s, Ht, e);
  }
  function jm(e, s, o) {
    var l = e.queue;
    if (l === null) throw Error(a(311));
    l.lastRenderedReducer = o;
    var h = e.baseQueue, d = l.pending;
    if (d !== null) {
      if (h !== null) {
        var x = h.next;
        h.next = d.next, d.next = x;
      }
      s.baseQueue = h = d, l.pending = null;
    }
    if (d = e.baseState, h === null) e.memoizedState = d;
    else {
      s = h.next;
      var M = x = null, E = null, _ = s, F = !1;
      do {
        var I = _.lane & -536870913;
        if (I !== _.lane ? (Rt & I) === I : (rs & I) === I) {
          var N = _.revertLane;
          if (N === 0)
            E !== null && (E = E.next = {
              lane: 0,
              revertLane: 0,
              action: _.action,
              hasEagerState: _.hasEagerState,
              eagerState: _.eagerState,
              next: null
            }), I === nr && (F = !0);
          else if ((rs & N) === N) {
            _ = _.next, N === nr && (F = !0);
            continue;
          } else
            I = {
              lane: 0,
              revertLane: _.revertLane,
              action: _.action,
              hasEagerState: _.hasEagerState,
              eagerState: _.eagerState,
              next: null
            }, E === null ? (M = E = I, x = d) : E = E.next = I, Tt.lanes |= N, ms |= N;
          I = _.action, Ca && o(d, I), d = _.hasEagerState ? _.eagerState : o(d, I);
        } else
          N = {
            lane: I,
            revertLane: _.revertLane,
            action: _.action,
            hasEagerState: _.hasEagerState,
            eagerState: _.eagerState,
            next: null
          }, E === null ? (M = E = N, x = d) : E = E.next = N, Tt.lanes |= I, ms |= I;
        _ = _.next;
      } while (_ !== null && _ !== s);
      if (E === null ? x = d : E.next = M, !cn(d, e.memoizedState) && (Te = !0, F && (o = ir, o !== null)))
        throw o;
      e.memoizedState = d, e.baseState = x, e.baseQueue = E, l.lastRenderedState = d;
    }
    return h === null && (l.lanes = 0), [e.memoizedState, l.dispatch];
  }
  function Hm(e) {
    var s = ge(), o = s.queue;
    if (o === null) throw Error(a(311));
    o.lastRenderedReducer = e;
    var l = o.dispatch, h = o.pending, d = s.memoizedState;
    if (h !== null) {
      o.pending = null;
      var x = h = h.next;
      do
        d = e(d, x.action), x = x.next;
      while (x !== h);
      cn(d, s.memoizedState) || (Te = !0), s.memoizedState = d, s.baseQueue === null && (s.baseState = d), o.lastRenderedState = d;
    }
    return [d, l];
  }
  function Jb(e, s, o) {
    var l = Tt, h = ge(), d = _t;
    if (d) {
      if (o === void 0) throw Error(a(407));
      o = o();
    } else o = s();
    var x = !cn(
      (Ht || h).memoizedState,
      o
    );
    x && (h.memoizedState = o, Te = !0), h = h.queue;
    var M = n0.bind(null, l, h, e);
    if (fu(2048, 8, M, [e]), h.getSnapshot !== s || x || pe !== null && pe.memoizedState.tag & 1) {
      if (l.flags |= 2048, rr(
        9,
        Lf(),
        e0.bind(
          null,
          l,
          h,
          o,
          s
        ),
        null
      ), $t === null) throw Error(a(349));
      d || (rs & 124) !== 0 || t0(l, s, o);
    }
    return o;
  }
  function t0(e, s, o) {
    e.flags |= 16384, e = { getSnapshot: s, value: o }, s = Tt.updateQueue, s === null ? (s = Nm(), Tt.updateQueue = s, s.stores = [e]) : (o = s.stores, o === null ? s.stores = [e] : o.push(e));
  }
  function e0(e, s, o, l) {
    s.value = o, s.getSnapshot = l, i0(s) && s0(e);
  }
  function n0(e, s, o) {
    return o(function() {
      i0(s) && s0(e);
    });
  }
  function i0(e) {
    var s = e.getSnapshot;
    e = e.value;
    try {
      var o = s();
      return !cn(e, o);
    } catch {
      return !0;
    }
  }
  function s0(e) {
    var s = Wo(e, 2);
    s !== null && gn(s, e, 2);
  }
  function qm(e) {
    var s = tn();
    if (typeof e == "function") {
      var o = e;
      if (e = o(), Ca) {
        ts(!0);
        try {
          o();
        } finally {
          ts(!1);
        }
      }
    }
    return s.memoizedState = s.baseState = e, s.queue = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: Hi,
      lastRenderedState: e
    }, s;
  }
  function a0(e, s, o, l) {
    return e.baseState = o, jm(
      e,
      Ht,
      typeof l == "function" ? l : Hi
    );
  }
  function wD(e, s, o, l, h) {
    if (Bf(e)) throw Error(a(485));
    if (e = s.action, e !== null) {
      var d = {
        payload: h,
        action: e,
        next: null,
        isTransition: !0,
        status: "pending",
        value: null,
        reason: null,
        listeners: [],
        then: function(x) {
          d.listeners.push(x);
        }
      };
      j.T !== null ? o(!0) : d.isTransition = !1, l(d), o = s.pending, o === null ? (d.next = s.pending = d, o0(s, d)) : (d.next = o.next, s.pending = o.next = d);
    }
  }
  function o0(e, s) {
    var o = s.action, l = s.payload, h = e.state;
    if (s.isTransition) {
      var d = j.T, x = {};
      j.T = x;
      try {
        var M = o(h, l), E = j.S;
        E !== null && E(x, M), r0(e, s, M);
      } catch (_) {
        Gm(e, s, _);
      } finally {
        j.T = d;
      }
    } else
      try {
        d = o(h, l), r0(e, s, d);
      } catch (_) {
        Gm(e, s, _);
      }
  }
  function r0(e, s, o) {
    o !== null && typeof o == "object" && typeof o.then == "function" ? o.then(
      function(l) {
        l0(e, s, l);
      },
      function(l) {
        return Gm(e, s, l);
      }
    ) : l0(e, s, o);
  }
  function l0(e, s, o) {
    s.status = "fulfilled", s.value = o, u0(s), e.state = o, s = e.pending, s !== null && (o = s.next, o === s ? e.pending = null : (o = o.next, s.next = o, o0(e, o)));
  }
  function Gm(e, s, o) {
    var l = e.pending;
    if (e.pending = null, l !== null) {
      l = l.next;
      do
        s.status = "rejected", s.reason = o, u0(s), s = s.next;
      while (s !== l);
    }
    e.action = null;
  }
  function u0(e) {
    e = e.listeners;
    for (var s = 0; s < e.length; s++) (0, e[s])();
  }
  function c0(e, s) {
    return s;
  }
  function f0(e, s) {
    if (_t) {
      var o = $t.formState;
      if (o !== null) {
        t: {
          var l = Tt;
          if (_t) {
            if (oe) {
              e: {
                for (var h = oe, d = ai; h.nodeType !== 8; ) {
                  if (!d) {
                    h = null;
                    break e;
                  }
                  if (h = Zn(
                    h.nextSibling
                  ), h === null) {
                    h = null;
                    break e;
                  }
                }
                d = h.data, h = d === "F!" || d === "F" ? h : null;
              }
              if (h) {
                oe = Zn(
                  h.nextSibling
                ), l = h.data === "F!";
                break t;
              }
            }
            Sa(l);
          }
          l = !1;
        }
        l && (s = o[0]);
      }
    }
    return o = tn(), o.memoizedState = o.baseState = s, l = {
      pending: null,
      lanes: 0,
      dispatch: null,
      lastRenderedReducer: c0,
      lastRenderedState: s
    }, o.queue = l, o = O0.bind(
      null,
      Tt,
      l
    ), l.dispatch = o, l = qm(!1), d = Qm.bind(
      null,
      Tt,
      !1,
      l.queue
    ), l = tn(), h = {
      state: s,
      dispatch: null,
      action: e,
      pending: null
    }, l.queue = h, o = wD.bind(
      null,
      Tt,
      h,
      d,
      o
    ), h.dispatch = o, l.memoizedState = e, [s, o, !1];
  }
  function h0(e) {
    var s = ge();
    return d0(s, Ht, e);
  }
  function d0(e, s, o) {
    if (s = jm(
      e,
      s,
      c0
    )[0], e = Pf(Hi)[0], typeof s == "object" && s !== null && typeof s.then == "function")
      try {
        var l = cu(s);
      } catch (x) {
        throw x === su ? Df : x;
      }
    else l = s;
    s = ge();
    var h = s.queue, d = h.dispatch;
    return o !== s.memoizedState && (Tt.flags |= 2048, rr(
      9,
      Lf(),
      MD.bind(null, h, o),
      null
    )), [l, d, e];
  }
  function MD(e, s) {
    e.action = s;
  }
  function m0(e) {
    var s = ge(), o = Ht;
    if (o !== null)
      return d0(s, o, e);
    ge(), s = s.memoizedState, o = ge();
    var l = o.queue.dispatch;
    return o.memoizedState = e, [s, l, !1];
  }
  function rr(e, s, o, l) {
    return e = { tag: e, create: o, deps: l, inst: s, next: null }, s = Tt.updateQueue, s === null && (s = Nm(), Tt.updateQueue = s), o = s.lastEffect, o === null ? s.lastEffect = e.next = e : (l = o.next, o.next = e, e.next = l, s.lastEffect = e), e;
  }
  function Lf() {
    return { destroy: void 0, resource: void 0 };
  }
  function p0() {
    return ge().memoizedState;
  }
  function _f(e, s, o, l) {
    var h = tn();
    l = l === void 0 ? null : l, Tt.flags |= e, h.memoizedState = rr(
      1 | s,
      Lf(),
      o,
      l
    );
  }
  function fu(e, s, o, l) {
    var h = ge();
    l = l === void 0 ? null : l;
    var d = h.memoizedState.inst;
    Ht !== null && l !== null && Vm(l, Ht.memoizedState.deps) ? h.memoizedState = rr(s, d, o, l) : (Tt.flags |= e, h.memoizedState = rr(
      1 | s,
      d,
      o,
      l
    ));
  }
  function g0(e, s) {
    _f(8390656, 8, e, s);
  }
  function y0(e, s) {
    fu(2048, 8, e, s);
  }
  function v0(e, s) {
    return fu(4, 2, e, s);
  }
  function b0(e, s) {
    return fu(4, 4, e, s);
  }
  function x0(e, s) {
    if (typeof s == "function") {
      e = e();
      var o = s(e);
      return function() {
        typeof o == "function" ? o() : s(null);
      };
    }
    if (s != null)
      return e = e(), s.current = e, function() {
        s.current = null;
      };
  }
  function S0(e, s, o) {
    o = o != null ? o.concat([e]) : null, fu(4, 4, x0.bind(null, s, e), o);
  }
  function Ym() {
  }
  function w0(e, s) {
    var o = ge();
    s = s === void 0 ? null : s;
    var l = o.memoizedState;
    return s !== null && Vm(s, l[1]) ? l[0] : (o.memoizedState = [e, s], e);
  }
  function M0(e, s) {
    var o = ge();
    s = s === void 0 ? null : s;
    var l = o.memoizedState;
    if (s !== null && Vm(s, l[1]))
      return l[0];
    if (l = e(), Ca) {
      ts(!0);
      try {
        e();
      } finally {
        ts(!1);
      }
    }
    return o.memoizedState = [l, s], l;
  }
  function Xm(e, s, o) {
    return o === void 0 || (rs & 1073741824) !== 0 ? e.memoizedState = s : (e.memoizedState = o, e = Ex(), Tt.lanes |= e, ms |= e, o);
  }
  function T0(e, s, o, l) {
    return cn(o, s) ? o : sr.current !== null ? (e = Xm(e, o, l), cn(e, s) || (Te = !0), e) : (rs & 42) === 0 ? (Te = !0, e.memoizedState = o) : (e = Ex(), Tt.lanes |= e, ms |= e, s);
  }
  function C0(e, s, o, l, h) {
    var d = W.p;
    W.p = d !== 0 && 8 > d ? d : 8;
    var x = j.T, M = {};
    j.T = M, Qm(e, !1, s, o);
    try {
      var E = h(), _ = j.S;
      if (_ !== null && _(M, E), E !== null && typeof E == "object" && typeof E.then == "function") {
        var F = bD(
          E,
          l
        );
        hu(
          e,
          s,
          F,
          pn(e)
        );
      } else
        hu(
          e,
          s,
          l,
          pn(e)
        );
    } catch (I) {
      hu(
        e,
        s,
        { then: function() {
        }, status: "rejected", reason: I },
        pn()
      );
    } finally {
      W.p = d, j.T = x;
    }
  }
  function TD() {
  }
  function Fm(e, s, o, l) {
    if (e.tag !== 5) throw Error(a(476));
    var h = E0(e).queue;
    C0(
      e,
      h,
      s,
      J,
      o === null ? TD : function() {
        return A0(e), o(l);
      }
    );
  }
  function E0(e) {
    var s = e.memoizedState;
    if (s !== null) return s;
    s = {
      memoizedState: J,
      baseState: J,
      baseQueue: null,
      queue: {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: Hi,
        lastRenderedState: J
      },
      next: null
    };
    var o = {};
    return s.next = {
      memoizedState: o,
      baseState: o,
      baseQueue: null,
      queue: {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: Hi,
        lastRenderedState: o
      },
      next: null
    }, e.memoizedState = s, e = e.alternate, e !== null && (e.memoizedState = s), s;
  }
  function A0(e) {
    var s = E0(e).next.queue;
    hu(e, s, {}, pn());
  }
  function Zm() {
    return _e(Ou);
  }
  function D0() {
    return ge().memoizedState;
  }
  function R0() {
    return ge().memoizedState;
  }
  function CD(e) {
    for (var s = e.return; s !== null; ) {
      switch (s.tag) {
        case 24:
        case 3:
          var o = pn();
          e = as(o);
          var l = os(s, e, o);
          l !== null && (gn(l, s, o), ou(l, s, o)), s = { cache: Mm() }, e.payload = s;
          return;
      }
      s = s.return;
    }
  }
  function ED(e, s, o) {
    var l = pn();
    o = {
      lane: l,
      revertLane: 0,
      action: o,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Bf(e) ? z0(s, o) : (o = dm(e, s, o, l), o !== null && (gn(o, e, l), k0(o, s, l)));
  }
  function O0(e, s, o) {
    var l = pn();
    hu(e, s, o, l);
  }
  function hu(e, s, o, l) {
    var h = {
      lane: l,
      revertLane: 0,
      action: o,
      hasEagerState: !1,
      eagerState: null,
      next: null
    };
    if (Bf(e)) z0(s, h);
    else {
      var d = e.alternate;
      if (e.lanes === 0 && (d === null || d.lanes === 0) && (d = s.lastRenderedReducer, d !== null))
        try {
          var x = s.lastRenderedState, M = d(x, o);
          if (h.hasEagerState = !0, h.eagerState = M, cn(M, x))
            return xf(e, s, h, 0), $t === null && bf(), !1;
        } catch {
        } finally {
        }
      if (o = dm(e, s, h, l), o !== null)
        return gn(o, e, l), k0(o, s, l), !0;
    }
    return !1;
  }
  function Qm(e, s, o, l) {
    if (l = {
      lane: 2,
      revertLane: Ep(),
      action: l,
      hasEagerState: !1,
      eagerState: null,
      next: null
    }, Bf(e)) {
      if (s) throw Error(a(479));
    } else
      s = dm(
        e,
        o,
        l,
        2
      ), s !== null && gn(s, e, 2);
  }
  function Bf(e) {
    var s = e.alternate;
    return e === Tt || s !== null && s === Tt;
  }
  function z0(e, s) {
    ar = zf = !0;
    var o = e.pending;
    o === null ? s.next = s : (s.next = o.next, o.next = s), e.pending = s;
  }
  function k0(e, s, o) {
    if ((o & 4194048) !== 0) {
      var l = s.lanes;
      l &= e.pendingLanes, o |= l, s.lanes = o, jv(e, o);
    }
  }
  var Nf = {
    readContext: _e,
    use: Vf,
    useCallback: ue,
    useContext: ue,
    useEffect: ue,
    useImperativeHandle: ue,
    useLayoutEffect: ue,
    useInsertionEffect: ue,
    useMemo: ue,
    useReducer: ue,
    useRef: ue,
    useState: ue,
    useDebugValue: ue,
    useDeferredValue: ue,
    useTransition: ue,
    useSyncExternalStore: ue,
    useId: ue,
    useHostTransitionStatus: ue,
    useFormState: ue,
    useActionState: ue,
    useOptimistic: ue,
    useMemoCache: ue,
    useCacheRefresh: ue
  }, V0 = {
    readContext: _e,
    use: Vf,
    useCallback: function(e, s) {
      return tn().memoizedState = [
        e,
        s === void 0 ? null : s
      ], e;
    },
    useContext: _e,
    useEffect: g0,
    useImperativeHandle: function(e, s, o) {
      o = o != null ? o.concat([e]) : null, _f(
        4194308,
        4,
        x0.bind(null, s, e),
        o
      );
    },
    useLayoutEffect: function(e, s) {
      return _f(4194308, 4, e, s);
    },
    useInsertionEffect: function(e, s) {
      _f(4, 2, e, s);
    },
    useMemo: function(e, s) {
      var o = tn();
      s = s === void 0 ? null : s;
      var l = e();
      if (Ca) {
        ts(!0);
        try {
          e();
        } finally {
          ts(!1);
        }
      }
      return o.memoizedState = [l, s], l;
    },
    useReducer: function(e, s, o) {
      var l = tn();
      if (o !== void 0) {
        var h = o(s);
        if (Ca) {
          ts(!0);
          try {
            o(s);
          } finally {
            ts(!1);
          }
        }
      } else h = s;
      return l.memoizedState = l.baseState = h, e = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: e,
        lastRenderedState: h
      }, l.queue = e, e = e.dispatch = ED.bind(
        null,
        Tt,
        e
      ), [l.memoizedState, e];
    },
    useRef: function(e) {
      var s = tn();
      return e = { current: e }, s.memoizedState = e;
    },
    useState: function(e) {
      e = qm(e);
      var s = e.queue, o = O0.bind(null, Tt, s);
      return s.dispatch = o, [e.memoizedState, o];
    },
    useDebugValue: Ym,
    useDeferredValue: function(e, s) {
      var o = tn();
      return Xm(o, e, s);
    },
    useTransition: function() {
      var e = qm(!1);
      return e = C0.bind(
        null,
        Tt,
        e.queue,
        !0,
        !1
      ), tn().memoizedState = e, [!1, e];
    },
    useSyncExternalStore: function(e, s, o) {
      var l = Tt, h = tn();
      if (_t) {
        if (o === void 0)
          throw Error(a(407));
        o = o();
      } else {
        if (o = s(), $t === null)
          throw Error(a(349));
        (Rt & 124) !== 0 || t0(l, s, o);
      }
      h.memoizedState = o;
      var d = { value: o, getSnapshot: s };
      return h.queue = d, g0(n0.bind(null, l, d, e), [
        e
      ]), l.flags |= 2048, rr(
        9,
        Lf(),
        e0.bind(
          null,
          l,
          d,
          o,
          s
        ),
        null
      ), o;
    },
    useId: function() {
      var e = tn(), s = $t.identifierPrefix;
      if (_t) {
        var o = Ni, l = Bi;
        o = (l & ~(1 << 32 - un(l) - 1)).toString(32) + o, s = "«" + s + "R" + o, o = kf++, 0 < o && (s += "H" + o.toString(32)), s += "»";
      } else
        o = xD++, s = "«" + s + "r" + o.toString(32) + "»";
      return e.memoizedState = s;
    },
    useHostTransitionStatus: Zm,
    useFormState: f0,
    useActionState: f0,
    useOptimistic: function(e) {
      var s = tn();
      s.memoizedState = s.baseState = e;
      var o = {
        pending: null,
        lanes: 0,
        dispatch: null,
        lastRenderedReducer: null,
        lastRenderedState: null
      };
      return s.queue = o, s = Qm.bind(
        null,
        Tt,
        !0,
        o
      ), o.dispatch = s, [e, s];
    },
    useMemoCache: Um,
    useCacheRefresh: function() {
      return tn().memoizedState = CD.bind(
        null,
        Tt
      );
    }
  }, P0 = {
    readContext: _e,
    use: Vf,
    useCallback: w0,
    useContext: _e,
    useEffect: y0,
    useImperativeHandle: S0,
    useInsertionEffect: v0,
    useLayoutEffect: b0,
    useMemo: M0,
    useReducer: Pf,
    useRef: p0,
    useState: function() {
      return Pf(Hi);
    },
    useDebugValue: Ym,
    useDeferredValue: function(e, s) {
      var o = ge();
      return T0(
        o,
        Ht.memoizedState,
        e,
        s
      );
    },
    useTransition: function() {
      var e = Pf(Hi)[0], s = ge().memoizedState;
      return [
        typeof e == "boolean" ? e : cu(e),
        s
      ];
    },
    useSyncExternalStore: Jb,
    useId: D0,
    useHostTransitionStatus: Zm,
    useFormState: h0,
    useActionState: h0,
    useOptimistic: function(e, s) {
      var o = ge();
      return a0(o, Ht, e, s);
    },
    useMemoCache: Um,
    useCacheRefresh: R0
  }, AD = {
    readContext: _e,
    use: Vf,
    useCallback: w0,
    useContext: _e,
    useEffect: y0,
    useImperativeHandle: S0,
    useInsertionEffect: v0,
    useLayoutEffect: b0,
    useMemo: M0,
    useReducer: Hm,
    useRef: p0,
    useState: function() {
      return Hm(Hi);
    },
    useDebugValue: Ym,
    useDeferredValue: function(e, s) {
      var o = ge();
      return Ht === null ? Xm(o, e, s) : T0(
        o,
        Ht.memoizedState,
        e,
        s
      );
    },
    useTransition: function() {
      var e = Hm(Hi)[0], s = ge().memoizedState;
      return [
        typeof e == "boolean" ? e : cu(e),
        s
      ];
    },
    useSyncExternalStore: Jb,
    useId: D0,
    useHostTransitionStatus: Zm,
    useFormState: m0,
    useActionState: m0,
    useOptimistic: function(e, s) {
      var o = ge();
      return Ht !== null ? a0(o, Ht, e, s) : (o.baseState = e, [e, o.queue.dispatch]);
    },
    useMemoCache: Um,
    useCacheRefresh: R0
  }, lr = null, du = 0;
  function Uf(e) {
    var s = du;
    return du += 1, lr === null && (lr = []), Xb(lr, e, s);
  }
  function mu(e, s) {
    s = s.props.ref, e.ref = s !== void 0 ? s : null;
  }
  function jf(e, s) {
    throw s.$$typeof === y ? Error(a(525)) : (e = Object.prototype.toString.call(s), Error(
      a(
        31,
        e === "[object Object]" ? "object with keys {" + Object.keys(s).join(", ") + "}" : e
      )
    ));
  }
  function L0(e) {
    var s = e._init;
    return s(e._payload);
  }
  function _0(e) {
    function s(V, O) {
      if (e) {
        var P = V.deletions;
        P === null ? (V.deletions = [O], V.flags |= 16) : P.push(O);
      }
    }
    function o(V, O) {
      if (!e) return null;
      for (; O !== null; )
        s(V, O), O = O.sibling;
      return null;
    }
    function l(V) {
      for (var O = /* @__PURE__ */ new Map(); V !== null; )
        V.key !== null ? O.set(V.key, V) : O.set(V.index, V), V = V.sibling;
      return O;
    }
    function h(V, O) {
      return V = _i(V, O), V.index = 0, V.sibling = null, V;
    }
    function d(V, O, P) {
      return V.index = P, e ? (P = V.alternate, P !== null ? (P = P.index, P < O ? (V.flags |= 67108866, O) : P) : (V.flags |= 67108866, O)) : (V.flags |= 1048576, O);
    }
    function x(V) {
      return e && V.alternate === null && (V.flags |= 67108866), V;
    }
    function M(V, O, P, K) {
      return O === null || O.tag !== 6 ? (O = pm(P, V.mode, K), O.return = V, O) : (O = h(O, P), O.return = V, O);
    }
    function E(V, O, P, K) {
      var at = P.type;
      return at === T ? F(
        V,
        O,
        P.props.children,
        K,
        P.key
      ) : O !== null && (O.elementType === at || typeof at == "object" && at !== null && at.$$typeof === $ && L0(at) === O.type) ? (O = h(O, P.props), mu(O, P), O.return = V, O) : (O = wf(
        P.type,
        P.key,
        P.props,
        null,
        V.mode,
        K
      ), mu(O, P), O.return = V, O);
    }
    function _(V, O, P, K) {
      return O === null || O.tag !== 4 || O.stateNode.containerInfo !== P.containerInfo || O.stateNode.implementation !== P.implementation ? (O = gm(P, V.mode, K), O.return = V, O) : (O = h(O, P.children || []), O.return = V, O);
    }
    function F(V, O, P, K, at) {
      return O === null || O.tag !== 7 ? (O = ya(
        P,
        V.mode,
        K,
        at
      ), O.return = V, O) : (O = h(O, P), O.return = V, O);
    }
    function I(V, O, P) {
      if (typeof O == "string" && O !== "" || typeof O == "number" || typeof O == "bigint")
        return O = pm(
          "" + O,
          V.mode,
          P
        ), O.return = V, O;
      if (typeof O == "object" && O !== null) {
        switch (O.$$typeof) {
          case b:
            return P = wf(
              O.type,
              O.key,
              O.props,
              null,
              V.mode,
              P
            ), mu(P, O), P.return = V, P;
          case S:
            return O = gm(
              O,
              V.mode,
              P
            ), O.return = V, O;
          case $:
            var K = O._init;
            return O = K(O._payload), I(V, O, P);
        }
        if (zt(O) || it(O))
          return O = ya(
            O,
            V.mode,
            P,
            null
          ), O.return = V, O;
        if (typeof O.then == "function")
          return I(V, Uf(O), P);
        if (O.$$typeof === H)
          return I(
            V,
            Ef(V, O),
            P
          );
        jf(V, O);
      }
      return null;
    }
    function N(V, O, P, K) {
      var at = O !== null ? O.key : null;
      if (typeof P == "string" && P !== "" || typeof P == "number" || typeof P == "bigint")
        return at !== null ? null : M(V, O, "" + P, K);
      if (typeof P == "object" && P !== null) {
        switch (P.$$typeof) {
          case b:
            return P.key === at ? E(V, O, P, K) : null;
          case S:
            return P.key === at ? _(V, O, P, K) : null;
          case $:
            return at = P._init, P = at(P._payload), N(V, O, P, K);
        }
        if (zt(P) || it(P))
          return at !== null ? null : F(V, O, P, K, null);
        if (typeof P.then == "function")
          return N(
            V,
            O,
            Uf(P),
            K
          );
        if (P.$$typeof === H)
          return N(
            V,
            O,
            Ef(V, P),
            K
          );
        jf(V, P);
      }
      return null;
    }
    function U(V, O, P, K, at) {
      if (typeof K == "string" && K !== "" || typeof K == "number" || typeof K == "bigint")
        return V = V.get(P) || null, M(O, V, "" + K, at);
      if (typeof K == "object" && K !== null) {
        switch (K.$$typeof) {
          case b:
            return V = V.get(
              K.key === null ? P : K.key
            ) || null, E(O, V, K, at);
          case S:
            return V = V.get(
              K.key === null ? P : K.key
            ) || null, _(O, V, K, at);
          case $:
            var Ct = K._init;
            return K = Ct(K._payload), U(
              V,
              O,
              P,
              K,
              at
            );
        }
        if (zt(K) || it(K))
          return V = V.get(P) || null, F(O, V, K, at, null);
        if (typeof K.then == "function")
          return U(
            V,
            O,
            P,
            Uf(K),
            at
          );
        if (K.$$typeof === H)
          return U(
            V,
            O,
            P,
            Ef(O, K),
            at
          );
        jf(O, K);
      }
      return null;
    }
    function pt(V, O, P, K) {
      for (var at = null, Ct = null, ct = O, mt = O = 0, Ee = null; ct !== null && mt < P.length; mt++) {
        ct.index > mt ? (Ee = ct, ct = null) : Ee = ct.sibling;
        var kt = N(
          V,
          ct,
          P[mt],
          K
        );
        if (kt === null) {
          ct === null && (ct = Ee);
          break;
        }
        e && ct && kt.alternate === null && s(V, ct), O = d(kt, O, mt), Ct === null ? at = kt : Ct.sibling = kt, Ct = kt, ct = Ee;
      }
      if (mt === P.length)
        return o(V, ct), _t && ba(V, mt), at;
      if (ct === null) {
        for (; mt < P.length; mt++)
          ct = I(V, P[mt], K), ct !== null && (O = d(
            ct,
            O,
            mt
          ), Ct === null ? at = ct : Ct.sibling = ct, Ct = ct);
        return _t && ba(V, mt), at;
      }
      for (ct = l(ct); mt < P.length; mt++)
        Ee = U(
          ct,
          V,
          mt,
          P[mt],
          K
        ), Ee !== null && (e && Ee.alternate !== null && ct.delete(
          Ee.key === null ? mt : Ee.key
        ), O = d(
          Ee,
          O,
          mt
        ), Ct === null ? at = Ee : Ct.sibling = Ee, Ct = Ee);
      return e && ct.forEach(function(Ms) {
        return s(V, Ms);
      }), _t && ba(V, mt), at;
    }
    function dt(V, O, P, K) {
      if (P == null) throw Error(a(151));
      for (var at = null, Ct = null, ct = O, mt = O = 0, Ee = null, kt = P.next(); ct !== null && !kt.done; mt++, kt = P.next()) {
        ct.index > mt ? (Ee = ct, ct = null) : Ee = ct.sibling;
        var Ms = N(V, ct, kt.value, K);
        if (Ms === null) {
          ct === null && (ct = Ee);
          break;
        }
        e && ct && Ms.alternate === null && s(V, ct), O = d(Ms, O, mt), Ct === null ? at = Ms : Ct.sibling = Ms, Ct = Ms, ct = Ee;
      }
      if (kt.done)
        return o(V, ct), _t && ba(V, mt), at;
      if (ct === null) {
        for (; !kt.done; mt++, kt = P.next())
          kt = I(V, kt.value, K), kt !== null && (O = d(kt, O, mt), Ct === null ? at = kt : Ct.sibling = kt, Ct = kt);
        return _t && ba(V, mt), at;
      }
      for (ct = l(ct); !kt.done; mt++, kt = P.next())
        kt = U(ct, V, mt, kt.value, K), kt !== null && (e && kt.alternate !== null && ct.delete(kt.key === null ? mt : kt.key), O = d(kt, O, mt), Ct === null ? at = kt : Ct.sibling = kt, Ct = kt);
      return e && ct.forEach(function(DR) {
        return s(V, DR);
      }), _t && ba(V, mt), at;
    }
    function Gt(V, O, P, K) {
      if (typeof P == "object" && P !== null && P.type === T && P.key === null && (P = P.props.children), typeof P == "object" && P !== null) {
        switch (P.$$typeof) {
          case b:
            t: {
              for (var at = P.key; O !== null; ) {
                if (O.key === at) {
                  if (at = P.type, at === T) {
                    if (O.tag === 7) {
                      o(
                        V,
                        O.sibling
                      ), K = h(
                        O,
                        P.props.children
                      ), K.return = V, V = K;
                      break t;
                    }
                  } else if (O.elementType === at || typeof at == "object" && at !== null && at.$$typeof === $ && L0(at) === O.type) {
                    o(
                      V,
                      O.sibling
                    ), K = h(O, P.props), mu(K, P), K.return = V, V = K;
                    break t;
                  }
                  o(V, O);
                  break;
                } else s(V, O);
                O = O.sibling;
              }
              P.type === T ? (K = ya(
                P.props.children,
                V.mode,
                K,
                P.key
              ), K.return = V, V = K) : (K = wf(
                P.type,
                P.key,
                P.props,
                null,
                V.mode,
                K
              ), mu(K, P), K.return = V, V = K);
            }
            return x(V);
          case S:
            t: {
              for (at = P.key; O !== null; ) {
                if (O.key === at)
                  if (O.tag === 4 && O.stateNode.containerInfo === P.containerInfo && O.stateNode.implementation === P.implementation) {
                    o(
                      V,
                      O.sibling
                    ), K = h(O, P.children || []), K.return = V, V = K;
                    break t;
                  } else {
                    o(V, O);
                    break;
                  }
                else s(V, O);
                O = O.sibling;
              }
              K = gm(P, V.mode, K), K.return = V, V = K;
            }
            return x(V);
          case $:
            return at = P._init, P = at(P._payload), Gt(
              V,
              O,
              P,
              K
            );
        }
        if (zt(P))
          return pt(
            V,
            O,
            P,
            K
          );
        if (it(P)) {
          if (at = it(P), typeof at != "function") throw Error(a(150));
          return P = at.call(P), dt(
            V,
            O,
            P,
            K
          );
        }
        if (typeof P.then == "function")
          return Gt(
            V,
            O,
            Uf(P),
            K
          );
        if (P.$$typeof === H)
          return Gt(
            V,
            O,
            Ef(V, P),
            K
          );
        jf(V, P);
      }
      return typeof P == "string" && P !== "" || typeof P == "number" || typeof P == "bigint" ? (P = "" + P, O !== null && O.tag === 6 ? (o(V, O.sibling), K = h(O, P), K.return = V, V = K) : (o(V, O), K = pm(P, V.mode, K), K.return = V, V = K), x(V)) : o(V, O);
    }
    return function(V, O, P, K) {
      try {
        du = 0;
        var at = Gt(
          V,
          O,
          P,
          K
        );
        return lr = null, at;
      } catch (ct) {
        if (ct === su || ct === Df) throw ct;
        var Ct = fn(29, ct, null, V.mode);
        return Ct.lanes = K, Ct.return = V, Ct;
      } finally {
      }
    };
  }
  var ur = _0(!0), B0 = _0(!1), An = Y(null), oi = null;
  function ls(e) {
    var s = e.alternate;
    tt(Se, Se.current & 1), tt(An, e), oi === null && (s === null || sr.current !== null || s.memoizedState !== null) && (oi = e);
  }
  function N0(e) {
    if (e.tag === 22) {
      if (tt(Se, Se.current), tt(An, e), oi === null) {
        var s = e.alternate;
        s !== null && s.memoizedState !== null && (oi = e);
      }
    } else us();
  }
  function us() {
    tt(Se, Se.current), tt(An, An.current);
  }
  function qi(e) {
    et(An), oi === e && (oi = null), et(Se);
  }
  var Se = Y(0);
  function Hf(e) {
    for (var s = e; s !== null; ) {
      if (s.tag === 13) {
        var o = s.memoizedState;
        if (o !== null && (o = o.dehydrated, o === null || o.data === "$?" || Np(o)))
          return s;
      } else if (s.tag === 19 && s.memoizedProps.revealOrder !== void 0) {
        if ((s.flags & 128) !== 0) return s;
      } else if (s.child !== null) {
        s.child.return = s, s = s.child;
        continue;
      }
      if (s === e) break;
      for (; s.sibling === null; ) {
        if (s.return === null || s.return === e) return null;
        s = s.return;
      }
      s.sibling.return = s.return, s = s.sibling;
    }
    return null;
  }
  function Km(e, s, o, l) {
    s = e.memoizedState, o = o(l, s), o = o == null ? s : g({}, s, o), e.memoizedState = o, e.lanes === 0 && (e.updateQueue.baseState = o);
  }
  var Im = {
    enqueueSetState: function(e, s, o) {
      e = e._reactInternals;
      var l = pn(), h = as(l);
      h.payload = s, o != null && (h.callback = o), s = os(e, h, l), s !== null && (gn(s, e, l), ou(s, e, l));
    },
    enqueueReplaceState: function(e, s, o) {
      e = e._reactInternals;
      var l = pn(), h = as(l);
      h.tag = 1, h.payload = s, o != null && (h.callback = o), s = os(e, h, l), s !== null && (gn(s, e, l), ou(s, e, l));
    },
    enqueueForceUpdate: function(e, s) {
      e = e._reactInternals;
      var o = pn(), l = as(o);
      l.tag = 2, s != null && (l.callback = s), s = os(e, l, o), s !== null && (gn(s, e, o), ou(s, e, o));
    }
  };
  function U0(e, s, o, l, h, d, x) {
    return e = e.stateNode, typeof e.shouldComponentUpdate == "function" ? e.shouldComponentUpdate(l, d, x) : s.prototype && s.prototype.isPureReactComponent ? !Il(o, l) || !Il(h, d) : !0;
  }
  function j0(e, s, o, l) {
    e = s.state, typeof s.componentWillReceiveProps == "function" && s.componentWillReceiveProps(o, l), typeof s.UNSAFE_componentWillReceiveProps == "function" && s.UNSAFE_componentWillReceiveProps(o, l), s.state !== e && Im.enqueueReplaceState(s, s.state, null);
  }
  function Ea(e, s) {
    var o = s;
    if ("ref" in s) {
      o = {};
      for (var l in s)
        l !== "ref" && (o[l] = s[l]);
    }
    if (e = e.defaultProps) {
      o === s && (o = g({}, o));
      for (var h in e)
        o[h] === void 0 && (o[h] = e[h]);
    }
    return o;
  }
  var qf = typeof reportError == "function" ? reportError : function(e) {
    if (typeof window == "object" && typeof window.ErrorEvent == "function") {
      var s = new window.ErrorEvent("error", {
        bubbles: !0,
        cancelable: !0,
        message: typeof e == "object" && e !== null && typeof e.message == "string" ? String(e.message) : String(e),
        error: e
      });
      if (!window.dispatchEvent(s)) return;
    } else if (typeof process == "object" && typeof process.emit == "function") {
      process.emit("uncaughtException", e);
      return;
    }
    console.error(e);
  };
  function H0(e) {
    qf(e);
  }
  function q0(e) {
    console.error(e);
  }
  function G0(e) {
    qf(e);
  }
  function Gf(e, s) {
    try {
      var o = e.onUncaughtError;
      o(s.value, { componentStack: s.stack });
    } catch (l) {
      setTimeout(function() {
        throw l;
      });
    }
  }
  function Y0(e, s, o) {
    try {
      var l = e.onCaughtError;
      l(o.value, {
        componentStack: o.stack,
        errorBoundary: s.tag === 1 ? s.stateNode : null
      });
    } catch (h) {
      setTimeout(function() {
        throw h;
      });
    }
  }
  function $m(e, s, o) {
    return o = as(o), o.tag = 3, o.payload = { element: null }, o.callback = function() {
      Gf(e, s);
    }, o;
  }
  function X0(e) {
    return e = as(e), e.tag = 3, e;
  }
  function F0(e, s, o, l) {
    var h = o.type.getDerivedStateFromError;
    if (typeof h == "function") {
      var d = l.value;
      e.payload = function() {
        return h(d);
      }, e.callback = function() {
        Y0(s, o, l);
      };
    }
    var x = o.stateNode;
    x !== null && typeof x.componentDidCatch == "function" && (e.callback = function() {
      Y0(s, o, l), typeof h != "function" && (ps === null ? ps = /* @__PURE__ */ new Set([this]) : ps.add(this));
      var M = l.stack;
      this.componentDidCatch(l.value, {
        componentStack: M !== null ? M : ""
      });
    });
  }
  function DD(e, s, o, l, h) {
    if (o.flags |= 32768, l !== null && typeof l == "object" && typeof l.then == "function") {
      if (s = o.alternate, s !== null && eu(
        s,
        o,
        h,
        !0
      ), o = An.current, o !== null) {
        switch (o.tag) {
          case 13:
            return oi === null ? Sp() : o.alternate === null && re === 0 && (re = 3), o.flags &= -257, o.flags |= 65536, o.lanes = h, l === Em ? o.flags |= 16384 : (s = o.updateQueue, s === null ? o.updateQueue = /* @__PURE__ */ new Set([l]) : s.add(l), Mp(e, l, h)), !1;
          case 22:
            return o.flags |= 65536, l === Em ? o.flags |= 16384 : (s = o.updateQueue, s === null ? (s = {
              transitions: null,
              markerInstances: null,
              retryQueue: /* @__PURE__ */ new Set([l])
            }, o.updateQueue = s) : (o = s.retryQueue, o === null ? s.retryQueue = /* @__PURE__ */ new Set([l]) : o.add(l)), Mp(e, l, h)), !1;
        }
        throw Error(a(435, o.tag));
      }
      return Mp(e, l, h), Sp(), !1;
    }
    if (_t)
      return s = An.current, s !== null ? ((s.flags & 65536) === 0 && (s.flags |= 256), s.flags |= 65536, s.lanes = h, l !== bm && (e = Error(a(422), { cause: l }), tu(Mn(e, o)))) : (l !== bm && (s = Error(a(423), {
        cause: l
      }), tu(
        Mn(s, o)
      )), e = e.current.alternate, e.flags |= 65536, h &= -h, e.lanes |= h, l = Mn(l, o), h = $m(
        e.stateNode,
        l,
        h
      ), Rm(e, h), re !== 4 && (re = 2)), !1;
    var d = Error(a(520), { cause: l });
    if (d = Mn(d, o), Su === null ? Su = [d] : Su.push(d), re !== 4 && (re = 2), s === null) return !0;
    l = Mn(l, o), o = s;
    do {
      switch (o.tag) {
        case 3:
          return o.flags |= 65536, e = h & -h, o.lanes |= e, e = $m(o.stateNode, l, e), Rm(o, e), !1;
        case 1:
          if (s = o.type, d = o.stateNode, (o.flags & 128) === 0 && (typeof s.getDerivedStateFromError == "function" || d !== null && typeof d.componentDidCatch == "function" && (ps === null || !ps.has(d))))
            return o.flags |= 65536, h &= -h, o.lanes |= h, h = X0(h), F0(
              h,
              e,
              o,
              l
            ), Rm(o, h), !1;
      }
      o = o.return;
    } while (o !== null);
    return !1;
  }
  var Z0 = Error(a(461)), Te = !1;
  function Oe(e, s, o, l) {
    s.child = e === null ? B0(s, null, o, l) : ur(
      s,
      e.child,
      o,
      l
    );
  }
  function Q0(e, s, o, l, h) {
    o = o.render;
    var d = s.ref;
    if ("ref" in l) {
      var x = {};
      for (var M in l)
        M !== "ref" && (x[M] = l[M]);
    } else x = l;
    return Ma(s), l = Pm(
      e,
      s,
      o,
      x,
      d,
      h
    ), M = Lm(), e !== null && !Te ? (_m(e, s, h), Gi(e, s, h)) : (_t && M && ym(s), s.flags |= 1, Oe(e, s, l, h), s.child);
  }
  function K0(e, s, o, l, h) {
    if (e === null) {
      var d = o.type;
      return typeof d == "function" && !mm(d) && d.defaultProps === void 0 && o.compare === null ? (s.tag = 15, s.type = d, I0(
        e,
        s,
        d,
        l,
        h
      )) : (e = wf(
        o.type,
        null,
        l,
        s,
        s.mode,
        h
      ), e.ref = s.ref, e.return = s, s.child = e);
    }
    if (d = e.child, !ap(e, h)) {
      var x = d.memoizedProps;
      if (o = o.compare, o = o !== null ? o : Il, o(x, l) && e.ref === s.ref)
        return Gi(e, s, h);
    }
    return s.flags |= 1, e = _i(d, l), e.ref = s.ref, e.return = s, s.child = e;
  }
  function I0(e, s, o, l, h) {
    if (e !== null) {
      var d = e.memoizedProps;
      if (Il(d, l) && e.ref === s.ref)
        if (Te = !1, s.pendingProps = l = d, ap(e, h))
          (e.flags & 131072) !== 0 && (Te = !0);
        else
          return s.lanes = e.lanes, Gi(e, s, h);
    }
    return Wm(
      e,
      s,
      o,
      l,
      h
    );
  }
  function $0(e, s, o) {
    var l = s.pendingProps, h = l.children, d = e !== null ? e.memoizedState : null;
    if (l.mode === "hidden") {
      if ((s.flags & 128) !== 0) {
        if (l = d !== null ? d.baseLanes | o : o, e !== null) {
          for (h = s.child = e.child, d = 0; h !== null; )
            d = d | h.lanes | h.childLanes, h = h.sibling;
          s.childLanes = d & ~l;
        } else s.childLanes = 0, s.child = null;
        return W0(
          e,
          s,
          l,
          o
        );
      }
      if ((o & 536870912) !== 0)
        s.memoizedState = { baseLanes: 0, cachePool: null }, e !== null && Af(
          s,
          d !== null ? d.cachePool : null
        ), d !== null ? Ib(s, d) : zm(), N0(s);
      else
        return s.lanes = s.childLanes = 536870912, W0(
          e,
          s,
          d !== null ? d.baseLanes | o : o,
          o
        );
    } else
      d !== null ? (Af(s, d.cachePool), Ib(s, d), us(), s.memoizedState = null) : (e !== null && Af(s, null), zm(), us());
    return Oe(e, s, h, o), s.child;
  }
  function W0(e, s, o, l) {
    var h = Cm();
    return h = h === null ? null : { parent: xe._currentValue, pool: h }, s.memoizedState = {
      baseLanes: o,
      cachePool: h
    }, e !== null && Af(s, null), zm(), N0(s), e !== null && eu(e, s, l, !0), null;
  }
  function Yf(e, s) {
    var o = s.ref;
    if (o === null)
      e !== null && e.ref !== null && (s.flags |= 4194816);
    else {
      if (typeof o != "function" && typeof o != "object")
        throw Error(a(284));
      (e === null || e.ref !== o) && (s.flags |= 4194816);
    }
  }
  function Wm(e, s, o, l, h) {
    return Ma(s), o = Pm(
      e,
      s,
      o,
      l,
      void 0,
      h
    ), l = Lm(), e !== null && !Te ? (_m(e, s, h), Gi(e, s, h)) : (_t && l && ym(s), s.flags |= 1, Oe(e, s, o, h), s.child);
  }
  function J0(e, s, o, l, h, d) {
    return Ma(s), s.updateQueue = null, o = Wb(
      s,
      l,
      o,
      h
    ), $b(e), l = Lm(), e !== null && !Te ? (_m(e, s, d), Gi(e, s, d)) : (_t && l && ym(s), s.flags |= 1, Oe(e, s, o, d), s.child);
  }
  function tx(e, s, o, l, h) {
    if (Ma(s), s.stateNode === null) {
      var d = Jo, x = o.contextType;
      typeof x == "object" && x !== null && (d = _e(x)), d = new o(l, d), s.memoizedState = d.state !== null && d.state !== void 0 ? d.state : null, d.updater = Im, s.stateNode = d, d._reactInternals = s, d = s.stateNode, d.props = l, d.state = s.memoizedState, d.refs = {}, Am(s), x = o.contextType, d.context = typeof x == "object" && x !== null ? _e(x) : Jo, d.state = s.memoizedState, x = o.getDerivedStateFromProps, typeof x == "function" && (Km(
        s,
        o,
        x,
        l
      ), d.state = s.memoizedState), typeof o.getDerivedStateFromProps == "function" || typeof d.getSnapshotBeforeUpdate == "function" || typeof d.UNSAFE_componentWillMount != "function" && typeof d.componentWillMount != "function" || (x = d.state, typeof d.componentWillMount == "function" && d.componentWillMount(), typeof d.UNSAFE_componentWillMount == "function" && d.UNSAFE_componentWillMount(), x !== d.state && Im.enqueueReplaceState(d, d.state, null), lu(s, l, d, h), ru(), d.state = s.memoizedState), typeof d.componentDidMount == "function" && (s.flags |= 4194308), l = !0;
    } else if (e === null) {
      d = s.stateNode;
      var M = s.memoizedProps, E = Ea(o, M);
      d.props = E;
      var _ = d.context, F = o.contextType;
      x = Jo, typeof F == "object" && F !== null && (x = _e(F));
      var I = o.getDerivedStateFromProps;
      F = typeof I == "function" || typeof d.getSnapshotBeforeUpdate == "function", M = s.pendingProps !== M, F || typeof d.UNSAFE_componentWillReceiveProps != "function" && typeof d.componentWillReceiveProps != "function" || (M || _ !== x) && j0(
        s,
        d,
        l,
        x
      ), ss = !1;
      var N = s.memoizedState;
      d.state = N, lu(s, l, d, h), ru(), _ = s.memoizedState, M || N !== _ || ss ? (typeof I == "function" && (Km(
        s,
        o,
        I,
        l
      ), _ = s.memoizedState), (E = ss || U0(
        s,
        o,
        E,
        l,
        N,
        _,
        x
      )) ? (F || typeof d.UNSAFE_componentWillMount != "function" && typeof d.componentWillMount != "function" || (typeof d.componentWillMount == "function" && d.componentWillMount(), typeof d.UNSAFE_componentWillMount == "function" && d.UNSAFE_componentWillMount()), typeof d.componentDidMount == "function" && (s.flags |= 4194308)) : (typeof d.componentDidMount == "function" && (s.flags |= 4194308), s.memoizedProps = l, s.memoizedState = _), d.props = l, d.state = _, d.context = x, l = E) : (typeof d.componentDidMount == "function" && (s.flags |= 4194308), l = !1);
    } else {
      d = s.stateNode, Dm(e, s), x = s.memoizedProps, F = Ea(o, x), d.props = F, I = s.pendingProps, N = d.context, _ = o.contextType, E = Jo, typeof _ == "object" && _ !== null && (E = _e(_)), M = o.getDerivedStateFromProps, (_ = typeof M == "function" || typeof d.getSnapshotBeforeUpdate == "function") || typeof d.UNSAFE_componentWillReceiveProps != "function" && typeof d.componentWillReceiveProps != "function" || (x !== I || N !== E) && j0(
        s,
        d,
        l,
        E
      ), ss = !1, N = s.memoizedState, d.state = N, lu(s, l, d, h), ru();
      var U = s.memoizedState;
      x !== I || N !== U || ss || e !== null && e.dependencies !== null && Cf(e.dependencies) ? (typeof M == "function" && (Km(
        s,
        o,
        M,
        l
      ), U = s.memoizedState), (F = ss || U0(
        s,
        o,
        F,
        l,
        N,
        U,
        E
      ) || e !== null && e.dependencies !== null && Cf(e.dependencies)) ? (_ || typeof d.UNSAFE_componentWillUpdate != "function" && typeof d.componentWillUpdate != "function" || (typeof d.componentWillUpdate == "function" && d.componentWillUpdate(l, U, E), typeof d.UNSAFE_componentWillUpdate == "function" && d.UNSAFE_componentWillUpdate(
        l,
        U,
        E
      )), typeof d.componentDidUpdate == "function" && (s.flags |= 4), typeof d.getSnapshotBeforeUpdate == "function" && (s.flags |= 1024)) : (typeof d.componentDidUpdate != "function" || x === e.memoizedProps && N === e.memoizedState || (s.flags |= 4), typeof d.getSnapshotBeforeUpdate != "function" || x === e.memoizedProps && N === e.memoizedState || (s.flags |= 1024), s.memoizedProps = l, s.memoizedState = U), d.props = l, d.state = U, d.context = E, l = F) : (typeof d.componentDidUpdate != "function" || x === e.memoizedProps && N === e.memoizedState || (s.flags |= 4), typeof d.getSnapshotBeforeUpdate != "function" || x === e.memoizedProps && N === e.memoizedState || (s.flags |= 1024), l = !1);
    }
    return d = l, Yf(e, s), l = (s.flags & 128) !== 0, d || l ? (d = s.stateNode, o = l && typeof o.getDerivedStateFromError != "function" ? null : d.render(), s.flags |= 1, e !== null && l ? (s.child = ur(
      s,
      e.child,
      null,
      h
    ), s.child = ur(
      s,
      null,
      o,
      h
    )) : Oe(e, s, o, h), s.memoizedState = d.state, e = s.child) : e = Gi(
      e,
      s,
      h
    ), e;
  }
  function ex(e, s, o, l) {
    return Jl(), s.flags |= 256, Oe(e, s, o, l), s.child;
  }
  var Jm = {
    dehydrated: null,
    treeContext: null,
    retryLane: 0,
    hydrationErrors: null
  };
  function tp(e) {
    return { baseLanes: e, cachePool: qb() };
  }
  function ep(e, s, o) {
    return e = e !== null ? e.childLanes & ~o : 0, s && (e |= Dn), e;
  }
  function nx(e, s, o) {
    var l = s.pendingProps, h = !1, d = (s.flags & 128) !== 0, x;
    if ((x = d) || (x = e !== null && e.memoizedState === null ? !1 : (Se.current & 2) !== 0), x && (h = !0, s.flags &= -129), x = (s.flags & 32) !== 0, s.flags &= -33, e === null) {
      if (_t) {
        if (h ? ls(s) : us(), _t) {
          var M = oe, E;
          if (E = M) {
            t: {
              for (E = M, M = ai; E.nodeType !== 8; ) {
                if (!M) {
                  M = null;
                  break t;
                }
                if (E = Zn(
                  E.nextSibling
                ), E === null) {
                  M = null;
                  break t;
                }
              }
              M = E;
            }
            M !== null ? (s.memoizedState = {
              dehydrated: M,
              treeContext: va !== null ? { id: Bi, overflow: Ni } : null,
              retryLane: 536870912,
              hydrationErrors: null
            }, E = fn(
              18,
              null,
              null,
              0
            ), E.stateNode = M, E.return = s, s.child = E, Ge = s, oe = null, E = !0) : E = !1;
          }
          E || Sa(s);
        }
        if (M = s.memoizedState, M !== null && (M = M.dehydrated, M !== null))
          return Np(M) ? s.lanes = 32 : s.lanes = 536870912, null;
        qi(s);
      }
      return M = l.children, l = l.fallback, h ? (us(), h = s.mode, M = Xf(
        { mode: "hidden", children: M },
        h
      ), l = ya(
        l,
        h,
        o,
        null
      ), M.return = s, l.return = s, M.sibling = l, s.child = M, h = s.child, h.memoizedState = tp(o), h.childLanes = ep(
        e,
        x,
        o
      ), s.memoizedState = Jm, l) : (ls(s), np(s, M));
    }
    if (E = e.memoizedState, E !== null && (M = E.dehydrated, M !== null)) {
      if (d)
        s.flags & 256 ? (ls(s), s.flags &= -257, s = ip(
          e,
          s,
          o
        )) : s.memoizedState !== null ? (us(), s.child = e.child, s.flags |= 128, s = null) : (us(), h = l.fallback, M = s.mode, l = Xf(
          { mode: "visible", children: l.children },
          M
        ), h = ya(
          h,
          M,
          o,
          null
        ), h.flags |= 2, l.return = s, h.return = s, l.sibling = h, s.child = l, ur(
          s,
          e.child,
          null,
          o
        ), l = s.child, l.memoizedState = tp(o), l.childLanes = ep(
          e,
          x,
          o
        ), s.memoizedState = Jm, s = h);
      else if (ls(s), Np(M)) {
        if (x = M.nextSibling && M.nextSibling.dataset, x) var _ = x.dgst;
        x = _, l = Error(a(419)), l.stack = "", l.digest = x, tu({ value: l, source: null, stack: null }), s = ip(
          e,
          s,
          o
        );
      } else if (Te || eu(e, s, o, !1), x = (o & e.childLanes) !== 0, Te || x) {
        if (x = $t, x !== null && (l = o & -o, l = (l & 42) !== 0 ? 1 : Ud(l), l = (l & (x.suspendedLanes | o)) !== 0 ? 0 : l, l !== 0 && l !== E.retryLane))
          throw E.retryLane = l, Wo(e, l), gn(x, e, l), Z0;
        M.data === "$?" || Sp(), s = ip(
          e,
          s,
          o
        );
      } else
        M.data === "$?" ? (s.flags |= 192, s.child = e.child, s = null) : (e = E.treeContext, oe = Zn(
          M.nextSibling
        ), Ge = s, _t = !0, xa = null, ai = !1, e !== null && (Cn[En++] = Bi, Cn[En++] = Ni, Cn[En++] = va, Bi = e.id, Ni = e.overflow, va = s), s = np(
          s,
          l.children
        ), s.flags |= 4096);
      return s;
    }
    return h ? (us(), h = l.fallback, M = s.mode, E = e.child, _ = E.sibling, l = _i(E, {
      mode: "hidden",
      children: l.children
    }), l.subtreeFlags = E.subtreeFlags & 65011712, _ !== null ? h = _i(_, h) : (h = ya(
      h,
      M,
      o,
      null
    ), h.flags |= 2), h.return = s, l.return = s, l.sibling = h, s.child = l, l = h, h = s.child, M = e.child.memoizedState, M === null ? M = tp(o) : (E = M.cachePool, E !== null ? (_ = xe._currentValue, E = E.parent !== _ ? { parent: _, pool: _ } : E) : E = qb(), M = {
      baseLanes: M.baseLanes | o,
      cachePool: E
    }), h.memoizedState = M, h.childLanes = ep(
      e,
      x,
      o
    ), s.memoizedState = Jm, l) : (ls(s), o = e.child, e = o.sibling, o = _i(o, {
      mode: "visible",
      children: l.children
    }), o.return = s, o.sibling = null, e !== null && (x = s.deletions, x === null ? (s.deletions = [e], s.flags |= 16) : x.push(e)), s.child = o, s.memoizedState = null, o);
  }
  function np(e, s) {
    return s = Xf(
      { mode: "visible", children: s },
      e.mode
    ), s.return = e, e.child = s;
  }
  function Xf(e, s) {
    return e = fn(22, e, null, s), e.lanes = 0, e.stateNode = {
      _visibility: 1,
      _pendingMarkers: null,
      _retryCache: null,
      _transitions: null
    }, e;
  }
  function ip(e, s, o) {
    return ur(s, e.child, null, o), e = np(
      s,
      s.pendingProps.children
    ), e.flags |= 2, s.memoizedState = null, e;
  }
  function ix(e, s, o) {
    e.lanes |= s;
    var l = e.alternate;
    l !== null && (l.lanes |= s), Sm(e.return, s, o);
  }
  function sp(e, s, o, l, h) {
    var d = e.memoizedState;
    d === null ? e.memoizedState = {
      isBackwards: s,
      rendering: null,
      renderingStartTime: 0,
      last: l,
      tail: o,
      tailMode: h
    } : (d.isBackwards = s, d.rendering = null, d.renderingStartTime = 0, d.last = l, d.tail = o, d.tailMode = h);
  }
  function sx(e, s, o) {
    var l = s.pendingProps, h = l.revealOrder, d = l.tail;
    if (Oe(e, s, l.children, o), l = Se.current, (l & 2) !== 0)
      l = l & 1 | 2, s.flags |= 128;
    else {
      if (e !== null && (e.flags & 128) !== 0)
        t: for (e = s.child; e !== null; ) {
          if (e.tag === 13)
            e.memoizedState !== null && ix(e, o, s);
          else if (e.tag === 19)
            ix(e, o, s);
          else if (e.child !== null) {
            e.child.return = e, e = e.child;
            continue;
          }
          if (e === s) break t;
          for (; e.sibling === null; ) {
            if (e.return === null || e.return === s)
              break t;
            e = e.return;
          }
          e.sibling.return = e.return, e = e.sibling;
        }
      l &= 1;
    }
    switch (tt(Se, l), h) {
      case "forwards":
        for (o = s.child, h = null; o !== null; )
          e = o.alternate, e !== null && Hf(e) === null && (h = o), o = o.sibling;
        o = h, o === null ? (h = s.child, s.child = null) : (h = o.sibling, o.sibling = null), sp(
          s,
          !1,
          h,
          o,
          d
        );
        break;
      case "backwards":
        for (o = null, h = s.child, s.child = null; h !== null; ) {
          if (e = h.alternate, e !== null && Hf(e) === null) {
            s.child = h;
            break;
          }
          e = h.sibling, h.sibling = o, o = h, h = e;
        }
        sp(
          s,
          !0,
          o,
          null,
          d
        );
        break;
      case "together":
        sp(s, !1, null, null, void 0);
        break;
      default:
        s.memoizedState = null;
    }
    return s.child;
  }
  function Gi(e, s, o) {
    if (e !== null && (s.dependencies = e.dependencies), ms |= s.lanes, (o & s.childLanes) === 0)
      if (e !== null) {
        if (eu(
          e,
          s,
          o,
          !1
        ), (o & s.childLanes) === 0)
          return null;
      } else return null;
    if (e !== null && s.child !== e.child)
      throw Error(a(153));
    if (s.child !== null) {
      for (e = s.child, o = _i(e, e.pendingProps), s.child = o, o.return = s; e.sibling !== null; )
        e = e.sibling, o = o.sibling = _i(e, e.pendingProps), o.return = s;
      o.sibling = null;
    }
    return s.child;
  }
  function ap(e, s) {
    return (e.lanes & s) !== 0 ? !0 : (e = e.dependencies, !!(e !== null && Cf(e)));
  }
  function RD(e, s, o) {
    switch (s.tag) {
      case 3:
        It(s, s.stateNode.containerInfo), is(s, xe, e.memoizedState.cache), Jl();
        break;
      case 27:
      case 5:
        Pd(s);
        break;
      case 4:
        It(s, s.stateNode.containerInfo);
        break;
      case 10:
        is(
          s,
          s.type,
          s.memoizedProps.value
        );
        break;
      case 13:
        var l = s.memoizedState;
        if (l !== null)
          return l.dehydrated !== null ? (ls(s), s.flags |= 128, null) : (o & s.child.childLanes) !== 0 ? nx(e, s, o) : (ls(s), e = Gi(
            e,
            s,
            o
          ), e !== null ? e.sibling : null);
        ls(s);
        break;
      case 19:
        var h = (e.flags & 128) !== 0;
        if (l = (o & s.childLanes) !== 0, l || (eu(
          e,
          s,
          o,
          !1
        ), l = (o & s.childLanes) !== 0), h) {
          if (l)
            return sx(
              e,
              s,
              o
            );
          s.flags |= 128;
        }
        if (h = s.memoizedState, h !== null && (h.rendering = null, h.tail = null, h.lastEffect = null), tt(Se, Se.current), l) break;
        return null;
      case 22:
      case 23:
        return s.lanes = 0, $0(e, s, o);
      case 24:
        is(s, xe, e.memoizedState.cache);
    }
    return Gi(e, s, o);
  }
  function ax(e, s, o) {
    if (e !== null)
      if (e.memoizedProps !== s.pendingProps)
        Te = !0;
      else {
        if (!ap(e, o) && (s.flags & 128) === 0)
          return Te = !1, RD(
            e,
            s,
            o
          );
        Te = (e.flags & 131072) !== 0;
      }
    else
      Te = !1, _t && (s.flags & 1048576) !== 0 && Lb(s, Tf, s.index);
    switch (s.lanes = 0, s.tag) {
      case 16:
        t: {
          e = s.pendingProps;
          var l = s.elementType, h = l._init;
          if (l = h(l._payload), s.type = l, typeof l == "function")
            mm(l) ? (e = Ea(l, e), s.tag = 1, s = tx(
              null,
              s,
              l,
              e,
              o
            )) : (s.tag = 0, s = Wm(
              null,
              s,
              l,
              e,
              o
            ));
          else {
            if (l != null) {
              if (h = l.$$typeof, h === X) {
                s.tag = 11, s = Q0(
                  null,
                  s,
                  l,
                  e,
                  o
                );
                break t;
              } else if (h === st) {
                s.tag = 14, s = K0(
                  null,
                  s,
                  l,
                  e,
                  o
                );
                break t;
              }
            }
            throw s = Kt(l) || l, Error(a(306, s, ""));
          }
        }
        return s;
      case 0:
        return Wm(
          e,
          s,
          s.type,
          s.pendingProps,
          o
        );
      case 1:
        return l = s.type, h = Ea(
          l,
          s.pendingProps
        ), tx(
          e,
          s,
          l,
          h,
          o
        );
      case 3:
        t: {
          if (It(
            s,
            s.stateNode.containerInfo
          ), e === null) throw Error(a(387));
          l = s.pendingProps;
          var d = s.memoizedState;
          h = d.element, Dm(e, s), lu(s, l, null, o);
          var x = s.memoizedState;
          if (l = x.cache, is(s, xe, l), l !== d.cache && wm(
            s,
            [xe],
            o,
            !0
          ), ru(), l = x.element, d.isDehydrated)
            if (d = {
              element: l,
              isDehydrated: !1,
              cache: x.cache
            }, s.updateQueue.baseState = d, s.memoizedState = d, s.flags & 256) {
              s = ex(
                e,
                s,
                l,
                o
              );
              break t;
            } else if (l !== h) {
              h = Mn(
                Error(a(424)),
                s
              ), tu(h), s = ex(
                e,
                s,
                l,
                o
              );
              break t;
            } else {
              switch (e = s.stateNode.containerInfo, e.nodeType) {
                case 9:
                  e = e.body;
                  break;
                default:
                  e = e.nodeName === "HTML" ? e.ownerDocument.body : e;
              }
              for (oe = Zn(e.firstChild), Ge = s, _t = !0, xa = null, ai = !0, o = B0(
                s,
                null,
                l,
                o
              ), s.child = o; o; )
                o.flags = o.flags & -3 | 4096, o = o.sibling;
            }
          else {
            if (Jl(), l === h) {
              s = Gi(
                e,
                s,
                o
              );
              break t;
            }
            Oe(
              e,
              s,
              l,
              o
            );
          }
          s = s.child;
        }
        return s;
      case 26:
        return Yf(e, s), e === null ? (o = uS(
          s.type,
          null,
          s.pendingProps,
          null
        )) ? s.memoizedState = o : _t || (o = s.type, e = s.pendingProps, l = ah(
          yt.current
        ).createElement(o), l[Le] = s, l[We] = e, ke(l, o, e), Me(l), s.stateNode = l) : s.memoizedState = uS(
          s.type,
          e.memoizedProps,
          s.pendingProps,
          e.memoizedState
        ), null;
      case 27:
        return Pd(s), e === null && _t && (l = s.stateNode = oS(
          s.type,
          s.pendingProps,
          yt.current
        ), Ge = s, ai = !0, h = oe, vs(s.type) ? (Up = h, oe = Zn(
          l.firstChild
        )) : oe = h), Oe(
          e,
          s,
          s.pendingProps.children,
          o
        ), Yf(e, s), e === null && (s.flags |= 4194304), s.child;
      case 5:
        return e === null && _t && ((h = l = oe) && (l = iR(
          l,
          s.type,
          s.pendingProps,
          ai
        ), l !== null ? (s.stateNode = l, Ge = s, oe = Zn(
          l.firstChild
        ), ai = !1, h = !0) : h = !1), h || Sa(s)), Pd(s), h = s.type, d = s.pendingProps, x = e !== null ? e.memoizedProps : null, l = d.children, Lp(h, d) ? l = null : x !== null && Lp(h, x) && (s.flags |= 32), s.memoizedState !== null && (h = Pm(
          e,
          s,
          SD,
          null,
          null,
          o
        ), Ou._currentValue = h), Yf(e, s), Oe(e, s, l, o), s.child;
      case 6:
        return e === null && _t && ((e = o = oe) && (o = sR(
          o,
          s.pendingProps,
          ai
        ), o !== null ? (s.stateNode = o, Ge = s, oe = null, e = !0) : e = !1), e || Sa(s)), null;
      case 13:
        return nx(e, s, o);
      case 4:
        return It(
          s,
          s.stateNode.containerInfo
        ), l = s.pendingProps, e === null ? s.child = ur(
          s,
          null,
          l,
          o
        ) : Oe(
          e,
          s,
          l,
          o
        ), s.child;
      case 11:
        return Q0(
          e,
          s,
          s.type,
          s.pendingProps,
          o
        );
      case 7:
        return Oe(
          e,
          s,
          s.pendingProps,
          o
        ), s.child;
      case 8:
        return Oe(
          e,
          s,
          s.pendingProps.children,
          o
        ), s.child;
      case 12:
        return Oe(
          e,
          s,
          s.pendingProps.children,
          o
        ), s.child;
      case 10:
        return l = s.pendingProps, is(s, s.type, l.value), Oe(
          e,
          s,
          l.children,
          o
        ), s.child;
      case 9:
        return h = s.type._context, l = s.pendingProps.children, Ma(s), h = _e(h), l = l(h), s.flags |= 1, Oe(e, s, l, o), s.child;
      case 14:
        return K0(
          e,
          s,
          s.type,
          s.pendingProps,
          o
        );
      case 15:
        return I0(
          e,
          s,
          s.type,
          s.pendingProps,
          o
        );
      case 19:
        return sx(e, s, o);
      case 31:
        return l = s.pendingProps, o = s.mode, l = {
          mode: l.mode,
          children: l.children
        }, e === null ? (o = Xf(
          l,
          o
        ), o.ref = s.ref, s.child = o, o.return = s, s = o) : (o = _i(e.child, l), o.ref = s.ref, s.child = o, o.return = s, s = o), s;
      case 22:
        return $0(e, s, o);
      case 24:
        return Ma(s), l = _e(xe), e === null ? (h = Cm(), h === null && (h = $t, d = Mm(), h.pooledCache = d, d.refCount++, d !== null && (h.pooledCacheLanes |= o), h = d), s.memoizedState = {
          parent: l,
          cache: h
        }, Am(s), is(s, xe, h)) : ((e.lanes & o) !== 0 && (Dm(e, s), lu(s, null, null, o), ru()), h = e.memoizedState, d = s.memoizedState, h.parent !== l ? (h = { parent: l, cache: l }, s.memoizedState = h, s.lanes === 0 && (s.memoizedState = s.updateQueue.baseState = h), is(s, xe, l)) : (l = d.cache, is(s, xe, l), l !== h.cache && wm(
          s,
          [xe],
          o,
          !0
        ))), Oe(
          e,
          s,
          s.pendingProps.children,
          o
        ), s.child;
      case 29:
        throw s.pendingProps;
    }
    throw Error(a(156, s.tag));
  }
  function Yi(e) {
    e.flags |= 4;
  }
  function ox(e, s) {
    if (s.type !== "stylesheet" || (s.state.loading & 4) !== 0)
      e.flags &= -16777217;
    else if (e.flags |= 16777216, !mS(s)) {
      if (s = An.current, s !== null && ((Rt & 4194048) === Rt ? oi !== null : (Rt & 62914560) !== Rt && (Rt & 536870912) === 0 || s !== oi))
        throw au = Em, Gb;
      e.flags |= 8192;
    }
  }
  function Ff(e, s) {
    s !== null && (e.flags |= 4), e.flags & 16384 && (s = e.tag !== 22 ? Nv() : 536870912, e.lanes |= s, dr |= s);
  }
  function pu(e, s) {
    if (!_t)
      switch (e.tailMode) {
        case "hidden":
          s = e.tail;
          for (var o = null; s !== null; )
            s.alternate !== null && (o = s), s = s.sibling;
          o === null ? e.tail = null : o.sibling = null;
          break;
        case "collapsed":
          o = e.tail;
          for (var l = null; o !== null; )
            o.alternate !== null && (l = o), o = o.sibling;
          l === null ? s || e.tail === null ? e.tail = null : e.tail.sibling = null : l.sibling = null;
      }
  }
  function se(e) {
    var s = e.alternate !== null && e.alternate.child === e.child, o = 0, l = 0;
    if (s)
      for (var h = e.child; h !== null; )
        o |= h.lanes | h.childLanes, l |= h.subtreeFlags & 65011712, l |= h.flags & 65011712, h.return = e, h = h.sibling;
    else
      for (h = e.child; h !== null; )
        o |= h.lanes | h.childLanes, l |= h.subtreeFlags, l |= h.flags, h.return = e, h = h.sibling;
    return e.subtreeFlags |= l, e.childLanes = o, s;
  }
  function OD(e, s, o) {
    var l = s.pendingProps;
    switch (vm(s), s.tag) {
      case 31:
      case 16:
      case 15:
      case 0:
      case 11:
      case 7:
      case 8:
      case 12:
      case 9:
      case 14:
        return se(s), null;
      case 1:
        return se(s), null;
      case 3:
        return o = s.stateNode, l = null, e !== null && (l = e.memoizedState.cache), s.memoizedState.cache !== l && (s.flags |= 2048), ji(xe), Ji(), o.pendingContext && (o.context = o.pendingContext, o.pendingContext = null), (e === null || e.child === null) && (Wl(s) ? Yi(s) : e === null || e.memoizedState.isDehydrated && (s.flags & 256) === 0 || (s.flags |= 1024, Nb())), se(s), null;
      case 26:
        return o = s.memoizedState, e === null ? (Yi(s), o !== null ? (se(s), ox(s, o)) : (se(s), s.flags &= -16777217)) : o ? o !== e.memoizedState ? (Yi(s), se(s), ox(s, o)) : (se(s), s.flags &= -16777217) : (e.memoizedProps !== l && Yi(s), se(s), s.flags &= -16777217), null;
      case 27:
        nf(s), o = yt.current;
        var h = s.type;
        if (e !== null && s.stateNode != null)
          e.memoizedProps !== l && Yi(s);
        else {
          if (!l) {
            if (s.stateNode === null)
              throw Error(a(166));
            return se(s), null;
          }
          e = rt.current, Wl(s) ? _b(s) : (e = oS(h, l, o), s.stateNode = e, Yi(s));
        }
        return se(s), null;
      case 5:
        if (nf(s), o = s.type, e !== null && s.stateNode != null)
          e.memoizedProps !== l && Yi(s);
        else {
          if (!l) {
            if (s.stateNode === null)
              throw Error(a(166));
            return se(s), null;
          }
          if (e = rt.current, Wl(s))
            _b(s);
          else {
            switch (h = ah(
              yt.current
            ), e) {
              case 1:
                e = h.createElementNS(
                  "http://www.w3.org/2000/svg",
                  o
                );
                break;
              case 2:
                e = h.createElementNS(
                  "http://www.w3.org/1998/Math/MathML",
                  o
                );
                break;
              default:
                switch (o) {
                  case "svg":
                    e = h.createElementNS(
                      "http://www.w3.org/2000/svg",
                      o
                    );
                    break;
                  case "math":
                    e = h.createElementNS(
                      "http://www.w3.org/1998/Math/MathML",
                      o
                    );
                    break;
                  case "script":
                    e = h.createElement("div"), e.innerHTML = "<script><\/script>", e = e.removeChild(e.firstChild);
                    break;
                  case "select":
                    e = typeof l.is == "string" ? h.createElement("select", { is: l.is }) : h.createElement("select"), l.multiple ? e.multiple = !0 : l.size && (e.size = l.size);
                    break;
                  default:
                    e = typeof l.is == "string" ? h.createElement(o, { is: l.is }) : h.createElement(o);
                }
            }
            e[Le] = s, e[We] = l;
            t: for (h = s.child; h !== null; ) {
              if (h.tag === 5 || h.tag === 6)
                e.appendChild(h.stateNode);
              else if (h.tag !== 4 && h.tag !== 27 && h.child !== null) {
                h.child.return = h, h = h.child;
                continue;
              }
              if (h === s) break t;
              for (; h.sibling === null; ) {
                if (h.return === null || h.return === s)
                  break t;
                h = h.return;
              }
              h.sibling.return = h.return, h = h.sibling;
            }
            s.stateNode = e;
            t: switch (ke(e, o, l), o) {
              case "button":
              case "input":
              case "select":
              case "textarea":
                e = !!l.autoFocus;
                break t;
              case "img":
                e = !0;
                break t;
              default:
                e = !1;
            }
            e && Yi(s);
          }
        }
        return se(s), s.flags &= -16777217, null;
      case 6:
        if (e && s.stateNode != null)
          e.memoizedProps !== l && Yi(s);
        else {
          if (typeof l != "string" && s.stateNode === null)
            throw Error(a(166));
          if (e = yt.current, Wl(s)) {
            if (e = s.stateNode, o = s.memoizedProps, l = null, h = Ge, h !== null)
              switch (h.tag) {
                case 27:
                case 5:
                  l = h.memoizedProps;
              }
            e[Le] = s, e = !!(e.nodeValue === o || l !== null && l.suppressHydrationWarning === !0 || Jx(e.nodeValue, o)), e || Sa(s);
          } else
            e = ah(e).createTextNode(
              l
            ), e[Le] = s, s.stateNode = e;
        }
        return se(s), null;
      case 13:
        if (l = s.memoizedState, e === null || e.memoizedState !== null && e.memoizedState.dehydrated !== null) {
          if (h = Wl(s), l !== null && l.dehydrated !== null) {
            if (e === null) {
              if (!h) throw Error(a(318));
              if (h = s.memoizedState, h = h !== null ? h.dehydrated : null, !h) throw Error(a(317));
              h[Le] = s;
            } else
              Jl(), (s.flags & 128) === 0 && (s.memoizedState = null), s.flags |= 4;
            se(s), h = !1;
          } else
            h = Nb(), e !== null && e.memoizedState !== null && (e.memoizedState.hydrationErrors = h), h = !0;
          if (!h)
            return s.flags & 256 ? (qi(s), s) : (qi(s), null);
        }
        if (qi(s), (s.flags & 128) !== 0)
          return s.lanes = o, s;
        if (o = l !== null, e = e !== null && e.memoizedState !== null, o) {
          l = s.child, h = null, l.alternate !== null && l.alternate.memoizedState !== null && l.alternate.memoizedState.cachePool !== null && (h = l.alternate.memoizedState.cachePool.pool);
          var d = null;
          l.memoizedState !== null && l.memoizedState.cachePool !== null && (d = l.memoizedState.cachePool.pool), d !== h && (l.flags |= 2048);
        }
        return o !== e && o && (s.child.flags |= 8192), Ff(s, s.updateQueue), se(s), null;
      case 4:
        return Ji(), e === null && Op(s.stateNode.containerInfo), se(s), null;
      case 10:
        return ji(s.type), se(s), null;
      case 19:
        if (et(Se), h = s.memoizedState, h === null) return se(s), null;
        if (l = (s.flags & 128) !== 0, d = h.rendering, d === null)
          if (l) pu(h, !1);
          else {
            if (re !== 0 || e !== null && (e.flags & 128) !== 0)
              for (e = s.child; e !== null; ) {
                if (d = Hf(e), d !== null) {
                  for (s.flags |= 128, pu(h, !1), e = d.updateQueue, s.updateQueue = e, Ff(s, e), s.subtreeFlags = 0, e = o, o = s.child; o !== null; )
                    Pb(o, e), o = o.sibling;
                  return tt(
                    Se,
                    Se.current & 1 | 2
                  ), s.child;
                }
                e = e.sibling;
              }
            h.tail !== null && si() > Kf && (s.flags |= 128, l = !0, pu(h, !1), s.lanes = 4194304);
          }
        else {
          if (!l)
            if (e = Hf(d), e !== null) {
              if (s.flags |= 128, l = !0, e = e.updateQueue, s.updateQueue = e, Ff(s, e), pu(h, !0), h.tail === null && h.tailMode === "hidden" && !d.alternate && !_t)
                return se(s), null;
            } else
              2 * si() - h.renderingStartTime > Kf && o !== 536870912 && (s.flags |= 128, l = !0, pu(h, !1), s.lanes = 4194304);
          h.isBackwards ? (d.sibling = s.child, s.child = d) : (e = h.last, e !== null ? e.sibling = d : s.child = d, h.last = d);
        }
        return h.tail !== null ? (s = h.tail, h.rendering = s, h.tail = s.sibling, h.renderingStartTime = si(), s.sibling = null, e = Se.current, tt(Se, l ? e & 1 | 2 : e & 1), s) : (se(s), null);
      case 22:
      case 23:
        return qi(s), km(), l = s.memoizedState !== null, e !== null ? e.memoizedState !== null !== l && (s.flags |= 8192) : l && (s.flags |= 8192), l ? (o & 536870912) !== 0 && (s.flags & 128) === 0 && (se(s), s.subtreeFlags & 6 && (s.flags |= 8192)) : se(s), o = s.updateQueue, o !== null && Ff(s, o.retryQueue), o = null, e !== null && e.memoizedState !== null && e.memoizedState.cachePool !== null && (o = e.memoizedState.cachePool.pool), l = null, s.memoizedState !== null && s.memoizedState.cachePool !== null && (l = s.memoizedState.cachePool.pool), l !== o && (s.flags |= 2048), e !== null && et(Ta), null;
      case 24:
        return o = null, e !== null && (o = e.memoizedState.cache), s.memoizedState.cache !== o && (s.flags |= 2048), ji(xe), se(s), null;
      case 25:
        return null;
      case 30:
        return null;
    }
    throw Error(a(156, s.tag));
  }
  function zD(e, s) {
    switch (vm(s), s.tag) {
      case 1:
        return e = s.flags, e & 65536 ? (s.flags = e & -65537 | 128, s) : null;
      case 3:
        return ji(xe), Ji(), e = s.flags, (e & 65536) !== 0 && (e & 128) === 0 ? (s.flags = e & -65537 | 128, s) : null;
      case 26:
      case 27:
      case 5:
        return nf(s), null;
      case 13:
        if (qi(s), e = s.memoizedState, e !== null && e.dehydrated !== null) {
          if (s.alternate === null)
            throw Error(a(340));
          Jl();
        }
        return e = s.flags, e & 65536 ? (s.flags = e & -65537 | 128, s) : null;
      case 19:
        return et(Se), null;
      case 4:
        return Ji(), null;
      case 10:
        return ji(s.type), null;
      case 22:
      case 23:
        return qi(s), km(), e !== null && et(Ta), e = s.flags, e & 65536 ? (s.flags = e & -65537 | 128, s) : null;
      case 24:
        return ji(xe), null;
      case 25:
        return null;
      default:
        return null;
    }
  }
  function rx(e, s) {
    switch (vm(s), s.tag) {
      case 3:
        ji(xe), Ji();
        break;
      case 26:
      case 27:
      case 5:
        nf(s);
        break;
      case 4:
        Ji();
        break;
      case 13:
        qi(s);
        break;
      case 19:
        et(Se);
        break;
      case 10:
        ji(s.type);
        break;
      case 22:
      case 23:
        qi(s), km(), e !== null && et(Ta);
        break;
      case 24:
        ji(xe);
    }
  }
  function gu(e, s) {
    try {
      var o = s.updateQueue, l = o !== null ? o.lastEffect : null;
      if (l !== null) {
        var h = l.next;
        o = h;
        do {
          if ((o.tag & e) === e) {
            l = void 0;
            var d = o.create, x = o.inst;
            l = d(), x.destroy = l;
          }
          o = o.next;
        } while (o !== h);
      }
    } catch (M) {
      Xt(s, s.return, M);
    }
  }
  function cs(e, s, o) {
    try {
      var l = s.updateQueue, h = l !== null ? l.lastEffect : null;
      if (h !== null) {
        var d = h.next;
        l = d;
        do {
          if ((l.tag & e) === e) {
            var x = l.inst, M = x.destroy;
            if (M !== void 0) {
              x.destroy = void 0, h = s;
              var E = o, _ = M;
              try {
                _();
              } catch (F) {
                Xt(
                  h,
                  E,
                  F
                );
              }
            }
          }
          l = l.next;
        } while (l !== d);
      }
    } catch (F) {
      Xt(s, s.return, F);
    }
  }
  function lx(e) {
    var s = e.updateQueue;
    if (s !== null) {
      var o = e.stateNode;
      try {
        Kb(s, o);
      } catch (l) {
        Xt(e, e.return, l);
      }
    }
  }
  function ux(e, s, o) {
    o.props = Ea(
      e.type,
      e.memoizedProps
    ), o.state = e.memoizedState;
    try {
      o.componentWillUnmount();
    } catch (l) {
      Xt(e, s, l);
    }
  }
  function yu(e, s) {
    try {
      var o = e.ref;
      if (o !== null) {
        switch (e.tag) {
          case 26:
          case 27:
          case 5:
            var l = e.stateNode;
            break;
          case 30:
            l = e.stateNode;
            break;
          default:
            l = e.stateNode;
        }
        typeof o == "function" ? e.refCleanup = o(l) : o.current = l;
      }
    } catch (h) {
      Xt(e, s, h);
    }
  }
  function ri(e, s) {
    var o = e.ref, l = e.refCleanup;
    if (o !== null)
      if (typeof l == "function")
        try {
          l();
        } catch (h) {
          Xt(e, s, h);
        } finally {
          e.refCleanup = null, e = e.alternate, e != null && (e.refCleanup = null);
        }
      else if (typeof o == "function")
        try {
          o(null);
        } catch (h) {
          Xt(e, s, h);
        }
      else o.current = null;
  }
  function cx(e) {
    var s = e.type, o = e.memoizedProps, l = e.stateNode;
    try {
      t: switch (s) {
        case "button":
        case "input":
        case "select":
        case "textarea":
          o.autoFocus && l.focus();
          break t;
        case "img":
          o.src ? l.src = o.src : o.srcSet && (l.srcset = o.srcSet);
      }
    } catch (h) {
      Xt(e, e.return, h);
    }
  }
  function op(e, s, o) {
    try {
      var l = e.stateNode;
      WD(l, e.type, o, s), l[We] = s;
    } catch (h) {
      Xt(e, e.return, h);
    }
  }
  function fx(e) {
    return e.tag === 5 || e.tag === 3 || e.tag === 26 || e.tag === 27 && vs(e.type) || e.tag === 4;
  }
  function rp(e) {
    t: for (; ; ) {
      for (; e.sibling === null; ) {
        if (e.return === null || fx(e.return)) return null;
        e = e.return;
      }
      for (e.sibling.return = e.return, e = e.sibling; e.tag !== 5 && e.tag !== 6 && e.tag !== 18; ) {
        if (e.tag === 27 && vs(e.type) || e.flags & 2 || e.child === null || e.tag === 4) continue t;
        e.child.return = e, e = e.child;
      }
      if (!(e.flags & 2)) return e.stateNode;
    }
  }
  function lp(e, s, o) {
    var l = e.tag;
    if (l === 5 || l === 6)
      e = e.stateNode, s ? (o.nodeType === 9 ? o.body : o.nodeName === "HTML" ? o.ownerDocument.body : o).insertBefore(e, s) : (s = o.nodeType === 9 ? o.body : o.nodeName === "HTML" ? o.ownerDocument.body : o, s.appendChild(e), o = o._reactRootContainer, o != null || s.onclick !== null || (s.onclick = sh));
    else if (l !== 4 && (l === 27 && vs(e.type) && (o = e.stateNode, s = null), e = e.child, e !== null))
      for (lp(e, s, o), e = e.sibling; e !== null; )
        lp(e, s, o), e = e.sibling;
  }
  function Zf(e, s, o) {
    var l = e.tag;
    if (l === 5 || l === 6)
      e = e.stateNode, s ? o.insertBefore(e, s) : o.appendChild(e);
    else if (l !== 4 && (l === 27 && vs(e.type) && (o = e.stateNode), e = e.child, e !== null))
      for (Zf(e, s, o), e = e.sibling; e !== null; )
        Zf(e, s, o), e = e.sibling;
  }
  function hx(e) {
    var s = e.stateNode, o = e.memoizedProps;
    try {
      for (var l = e.type, h = s.attributes; h.length; )
        s.removeAttributeNode(h[0]);
      ke(s, l, o), s[Le] = e, s[We] = o;
    } catch (d) {
      Xt(e, e.return, d);
    }
  }
  var Xi = !1, ce = !1, up = !1, dx = typeof WeakSet == "function" ? WeakSet : Set, Ce = null;
  function kD(e, s) {
    if (e = e.containerInfo, Vp = fh, e = Tb(e), rm(e)) {
      if ("selectionStart" in e)
        var o = {
          start: e.selectionStart,
          end: e.selectionEnd
        };
      else
        t: {
          o = (o = e.ownerDocument) && o.defaultView || window;
          var l = o.getSelection && o.getSelection();
          if (l && l.rangeCount !== 0) {
            o = l.anchorNode;
            var h = l.anchorOffset, d = l.focusNode;
            l = l.focusOffset;
            try {
              o.nodeType, d.nodeType;
            } catch {
              o = null;
              break t;
            }
            var x = 0, M = -1, E = -1, _ = 0, F = 0, I = e, N = null;
            e: for (; ; ) {
              for (var U; I !== o || h !== 0 && I.nodeType !== 3 || (M = x + h), I !== d || l !== 0 && I.nodeType !== 3 || (E = x + l), I.nodeType === 3 && (x += I.nodeValue.length), (U = I.firstChild) !== null; )
                N = I, I = U;
              for (; ; ) {
                if (I === e) break e;
                if (N === o && ++_ === h && (M = x), N === d && ++F === l && (E = x), (U = I.nextSibling) !== null) break;
                I = N, N = I.parentNode;
              }
              I = U;
            }
            o = M === -1 || E === -1 ? null : { start: M, end: E };
          } else o = null;
        }
      o = o || { start: 0, end: 0 };
    } else o = null;
    for (Pp = { focusedElem: e, selectionRange: o }, fh = !1, Ce = s; Ce !== null; )
      if (s = Ce, e = s.child, (s.subtreeFlags & 1024) !== 0 && e !== null)
        e.return = s, Ce = e;
      else
        for (; Ce !== null; ) {
          switch (s = Ce, d = s.alternate, e = s.flags, s.tag) {
            case 0:
              break;
            case 11:
            case 15:
              break;
            case 1:
              if ((e & 1024) !== 0 && d !== null) {
                e = void 0, o = s, h = d.memoizedProps, d = d.memoizedState, l = o.stateNode;
                try {
                  var pt = Ea(
                    o.type,
                    h,
                    o.elementType === o.type
                  );
                  e = l.getSnapshotBeforeUpdate(
                    pt,
                    d
                  ), l.__reactInternalSnapshotBeforeUpdate = e;
                } catch (dt) {
                  Xt(
                    o,
                    o.return,
                    dt
                  );
                }
              }
              break;
            case 3:
              if ((e & 1024) !== 0) {
                if (e = s.stateNode.containerInfo, o = e.nodeType, o === 9)
                  Bp(e);
                else if (o === 1)
                  switch (e.nodeName) {
                    case "HEAD":
                    case "HTML":
                    case "BODY":
                      Bp(e);
                      break;
                    default:
                      e.textContent = "";
                  }
              }
              break;
            case 5:
            case 26:
            case 27:
            case 6:
            case 4:
            case 17:
              break;
            default:
              if ((e & 1024) !== 0) throw Error(a(163));
          }
          if (e = s.sibling, e !== null) {
            e.return = s.return, Ce = e;
            break;
          }
          Ce = s.return;
        }
  }
  function mx(e, s, o) {
    var l = o.flags;
    switch (o.tag) {
      case 0:
      case 11:
      case 15:
        fs(e, o), l & 4 && gu(5, o);
        break;
      case 1:
        if (fs(e, o), l & 4)
          if (e = o.stateNode, s === null)
            try {
              e.componentDidMount();
            } catch (x) {
              Xt(o, o.return, x);
            }
          else {
            var h = Ea(
              o.type,
              s.memoizedProps
            );
            s = s.memoizedState;
            try {
              e.componentDidUpdate(
                h,
                s,
                e.__reactInternalSnapshotBeforeUpdate
              );
            } catch (x) {
              Xt(
                o,
                o.return,
                x
              );
            }
          }
        l & 64 && lx(o), l & 512 && yu(o, o.return);
        break;
      case 3:
        if (fs(e, o), l & 64 && (e = o.updateQueue, e !== null)) {
          if (s = null, o.child !== null)
            switch (o.child.tag) {
              case 27:
              case 5:
                s = o.child.stateNode;
                break;
              case 1:
                s = o.child.stateNode;
            }
          try {
            Kb(e, s);
          } catch (x) {
            Xt(o, o.return, x);
          }
        }
        break;
      case 27:
        s === null && l & 4 && hx(o);
      case 26:
      case 5:
        fs(e, o), s === null && l & 4 && cx(o), l & 512 && yu(o, o.return);
        break;
      case 12:
        fs(e, o);
        break;
      case 13:
        fs(e, o), l & 4 && yx(e, o), l & 64 && (e = o.memoizedState, e !== null && (e = e.dehydrated, e !== null && (o = HD.bind(
          null,
          o
        ), aR(e, o))));
        break;
      case 22:
        if (l = o.memoizedState !== null || Xi, !l) {
          s = s !== null && s.memoizedState !== null || ce, h = Xi;
          var d = ce;
          Xi = l, (ce = s) && !d ? hs(
            e,
            o,
            (o.subtreeFlags & 8772) !== 0
          ) : fs(e, o), Xi = h, ce = d;
        }
        break;
      case 30:
        break;
      default:
        fs(e, o);
    }
  }
  function px(e) {
    var s = e.alternate;
    s !== null && (e.alternate = null, px(s)), e.child = null, e.deletions = null, e.sibling = null, e.tag === 5 && (s = e.stateNode, s !== null && qd(s)), e.stateNode = null, e.return = null, e.dependencies = null, e.memoizedProps = null, e.memoizedState = null, e.pendingProps = null, e.stateNode = null, e.updateQueue = null;
  }
  var ne = null, en = !1;
  function Fi(e, s, o) {
    for (o = o.child; o !== null; )
      gx(e, s, o), o = o.sibling;
  }
  function gx(e, s, o) {
    if (ln && typeof ln.onCommitFiberUnmount == "function")
      try {
        ln.onCommitFiberUnmount(Nl, o);
      } catch {
      }
    switch (o.tag) {
      case 26:
        ce || ri(o, s), Fi(
          e,
          s,
          o
        ), o.memoizedState ? o.memoizedState.count-- : o.stateNode && (o = o.stateNode, o.parentNode.removeChild(o));
        break;
      case 27:
        ce || ri(o, s);
        var l = ne, h = en;
        vs(o.type) && (ne = o.stateNode, en = !1), Fi(
          e,
          s,
          o
        ), Eu(o.stateNode), ne = l, en = h;
        break;
      case 5:
        ce || ri(o, s);
      case 6:
        if (l = ne, h = en, ne = null, Fi(
          e,
          s,
          o
        ), ne = l, en = h, ne !== null)
          if (en)
            try {
              (ne.nodeType === 9 ? ne.body : ne.nodeName === "HTML" ? ne.ownerDocument.body : ne).removeChild(o.stateNode);
            } catch (d) {
              Xt(
                o,
                s,
                d
              );
            }
          else
            try {
              ne.removeChild(o.stateNode);
            } catch (d) {
              Xt(
                o,
                s,
                d
              );
            }
        break;
      case 18:
        ne !== null && (en ? (e = ne, sS(
          e.nodeType === 9 ? e.body : e.nodeName === "HTML" ? e.ownerDocument.body : e,
          o.stateNode
        ), Pu(e)) : sS(ne, o.stateNode));
        break;
      case 4:
        l = ne, h = en, ne = o.stateNode.containerInfo, en = !0, Fi(
          e,
          s,
          o
        ), ne = l, en = h;
        break;
      case 0:
      case 11:
      case 14:
      case 15:
        ce || cs(2, o, s), ce || cs(4, o, s), Fi(
          e,
          s,
          o
        );
        break;
      case 1:
        ce || (ri(o, s), l = o.stateNode, typeof l.componentWillUnmount == "function" && ux(
          o,
          s,
          l
        )), Fi(
          e,
          s,
          o
        );
        break;
      case 21:
        Fi(
          e,
          s,
          o
        );
        break;
      case 22:
        ce = (l = ce) || o.memoizedState !== null, Fi(
          e,
          s,
          o
        ), ce = l;
        break;
      default:
        Fi(
          e,
          s,
          o
        );
    }
  }
  function yx(e, s) {
    if (s.memoizedState === null && (e = s.alternate, e !== null && (e = e.memoizedState, e !== null && (e = e.dehydrated, e !== null))))
      try {
        Pu(e);
      } catch (o) {
        Xt(s, s.return, o);
      }
  }
  function VD(e) {
    switch (e.tag) {
      case 13:
      case 19:
        var s = e.stateNode;
        return s === null && (s = e.stateNode = new dx()), s;
      case 22:
        return e = e.stateNode, s = e._retryCache, s === null && (s = e._retryCache = new dx()), s;
      default:
        throw Error(a(435, e.tag));
    }
  }
  function cp(e, s) {
    var o = VD(e);
    s.forEach(function(l) {
      var h = qD.bind(null, e, l);
      o.has(l) || (o.add(l), l.then(h, h));
    });
  }
  function hn(e, s) {
    var o = s.deletions;
    if (o !== null)
      for (var l = 0; l < o.length; l++) {
        var h = o[l], d = e, x = s, M = x;
        t: for (; M !== null; ) {
          switch (M.tag) {
            case 27:
              if (vs(M.type)) {
                ne = M.stateNode, en = !1;
                break t;
              }
              break;
            case 5:
              ne = M.stateNode, en = !1;
              break t;
            case 3:
            case 4:
              ne = M.stateNode.containerInfo, en = !0;
              break t;
          }
          M = M.return;
        }
        if (ne === null) throw Error(a(160));
        gx(d, x, h), ne = null, en = !1, d = h.alternate, d !== null && (d.return = null), h.return = null;
      }
    if (s.subtreeFlags & 13878)
      for (s = s.child; s !== null; )
        vx(s, e), s = s.sibling;
  }
  var Fn = null;
  function vx(e, s) {
    var o = e.alternate, l = e.flags;
    switch (e.tag) {
      case 0:
      case 11:
      case 14:
      case 15:
        hn(s, e), dn(e), l & 4 && (cs(3, e, e.return), gu(3, e), cs(5, e, e.return));
        break;
      case 1:
        hn(s, e), dn(e), l & 512 && (ce || o === null || ri(o, o.return)), l & 64 && Xi && (e = e.updateQueue, e !== null && (l = e.callbacks, l !== null && (o = e.shared.hiddenCallbacks, e.shared.hiddenCallbacks = o === null ? l : o.concat(l))));
        break;
      case 26:
        var h = Fn;
        if (hn(s, e), dn(e), l & 512 && (ce || o === null || ri(o, o.return)), l & 4) {
          var d = o !== null ? o.memoizedState : null;
          if (l = e.memoizedState, o === null)
            if (l === null)
              if (e.stateNode === null) {
                t: {
                  l = e.type, o = e.memoizedProps, h = h.ownerDocument || h;
                  e: switch (l) {
                    case "title":
                      d = h.getElementsByTagName("title")[0], (!d || d[Hl] || d[Le] || d.namespaceURI === "http://www.w3.org/2000/svg" || d.hasAttribute("itemprop")) && (d = h.createElement(l), h.head.insertBefore(
                        d,
                        h.querySelector("head > title")
                      )), ke(d, l, o), d[Le] = e, Me(d), l = d;
                      break t;
                    case "link":
                      var x = hS(
                        "link",
                        "href",
                        h
                      ).get(l + (o.href || ""));
                      if (x) {
                        for (var M = 0; M < x.length; M++)
                          if (d = x[M], d.getAttribute("href") === (o.href == null || o.href === "" ? null : o.href) && d.getAttribute("rel") === (o.rel == null ? null : o.rel) && d.getAttribute("title") === (o.title == null ? null : o.title) && d.getAttribute("crossorigin") === (o.crossOrigin == null ? null : o.crossOrigin)) {
                            x.splice(M, 1);
                            break e;
                          }
                      }
                      d = h.createElement(l), ke(d, l, o), h.head.appendChild(d);
                      break;
                    case "meta":
                      if (x = hS(
                        "meta",
                        "content",
                        h
                      ).get(l + (o.content || ""))) {
                        for (M = 0; M < x.length; M++)
                          if (d = x[M], d.getAttribute("content") === (o.content == null ? null : "" + o.content) && d.getAttribute("name") === (o.name == null ? null : o.name) && d.getAttribute("property") === (o.property == null ? null : o.property) && d.getAttribute("http-equiv") === (o.httpEquiv == null ? null : o.httpEquiv) && d.getAttribute("charset") === (o.charSet == null ? null : o.charSet)) {
                            x.splice(M, 1);
                            break e;
                          }
                      }
                      d = h.createElement(l), ke(d, l, o), h.head.appendChild(d);
                      break;
                    default:
                      throw Error(a(468, l));
                  }
                  d[Le] = e, Me(d), l = d;
                }
                e.stateNode = l;
              } else
                dS(
                  h,
                  e.type,
                  e.stateNode
                );
            else
              e.stateNode = fS(
                h,
                l,
                e.memoizedProps
              );
          else
            d !== l ? (d === null ? o.stateNode !== null && (o = o.stateNode, o.parentNode.removeChild(o)) : d.count--, l === null ? dS(
              h,
              e.type,
              e.stateNode
            ) : fS(
              h,
              l,
              e.memoizedProps
            )) : l === null && e.stateNode !== null && op(
              e,
              e.memoizedProps,
              o.memoizedProps
            );
        }
        break;
      case 27:
        hn(s, e), dn(e), l & 512 && (ce || o === null || ri(o, o.return)), o !== null && l & 4 && op(
          e,
          e.memoizedProps,
          o.memoizedProps
        );
        break;
      case 5:
        if (hn(s, e), dn(e), l & 512 && (ce || o === null || ri(o, o.return)), e.flags & 32) {
          h = e.stateNode;
          try {
            Xo(h, "");
          } catch (U) {
            Xt(e, e.return, U);
          }
        }
        l & 4 && e.stateNode != null && (h = e.memoizedProps, op(
          e,
          h,
          o !== null ? o.memoizedProps : h
        )), l & 1024 && (up = !0);
        break;
      case 6:
        if (hn(s, e), dn(e), l & 4) {
          if (e.stateNode === null)
            throw Error(a(162));
          l = e.memoizedProps, o = e.stateNode;
          try {
            o.nodeValue = l;
          } catch (U) {
            Xt(e, e.return, U);
          }
        }
        break;
      case 3:
        if (lh = null, h = Fn, Fn = oh(s.containerInfo), hn(s, e), Fn = h, dn(e), l & 4 && o !== null && o.memoizedState.isDehydrated)
          try {
            Pu(s.containerInfo);
          } catch (U) {
            Xt(e, e.return, U);
          }
        up && (up = !1, bx(e));
        break;
      case 4:
        l = Fn, Fn = oh(
          e.stateNode.containerInfo
        ), hn(s, e), dn(e), Fn = l;
        break;
      case 12:
        hn(s, e), dn(e);
        break;
      case 13:
        hn(s, e), dn(e), e.child.flags & 8192 && e.memoizedState !== null != (o !== null && o.memoizedState !== null) && (gp = si()), l & 4 && (l = e.updateQueue, l !== null && (e.updateQueue = null, cp(e, l)));
        break;
      case 22:
        h = e.memoizedState !== null;
        var E = o !== null && o.memoizedState !== null, _ = Xi, F = ce;
        if (Xi = _ || h, ce = F || E, hn(s, e), ce = F, Xi = _, dn(e), l & 8192)
          t: for (s = e.stateNode, s._visibility = h ? s._visibility & -2 : s._visibility | 1, h && (o === null || E || Xi || ce || Aa(e)), o = null, s = e; ; ) {
            if (s.tag === 5 || s.tag === 26) {
              if (o === null) {
                E = o = s;
                try {
                  if (d = E.stateNode, h)
                    x = d.style, typeof x.setProperty == "function" ? x.setProperty("display", "none", "important") : x.display = "none";
                  else {
                    M = E.stateNode;
                    var I = E.memoizedProps.style, N = I != null && I.hasOwnProperty("display") ? I.display : null;
                    M.style.display = N == null || typeof N == "boolean" ? "" : ("" + N).trim();
                  }
                } catch (U) {
                  Xt(E, E.return, U);
                }
              }
            } else if (s.tag === 6) {
              if (o === null) {
                E = s;
                try {
                  E.stateNode.nodeValue = h ? "" : E.memoizedProps;
                } catch (U) {
                  Xt(E, E.return, U);
                }
              }
            } else if ((s.tag !== 22 && s.tag !== 23 || s.memoizedState === null || s === e) && s.child !== null) {
              s.child.return = s, s = s.child;
              continue;
            }
            if (s === e) break t;
            for (; s.sibling === null; ) {
              if (s.return === null || s.return === e) break t;
              o === s && (o = null), s = s.return;
            }
            o === s && (o = null), s.sibling.return = s.return, s = s.sibling;
          }
        l & 4 && (l = e.updateQueue, l !== null && (o = l.retryQueue, o !== null && (l.retryQueue = null, cp(e, o))));
        break;
      case 19:
        hn(s, e), dn(e), l & 4 && (l = e.updateQueue, l !== null && (e.updateQueue = null, cp(e, l)));
        break;
      case 30:
        break;
      case 21:
        break;
      default:
        hn(s, e), dn(e);
    }
  }
  function dn(e) {
    var s = e.flags;
    if (s & 2) {
      try {
        for (var o, l = e.return; l !== null; ) {
          if (fx(l)) {
            o = l;
            break;
          }
          l = l.return;
        }
        if (o == null) throw Error(a(160));
        switch (o.tag) {
          case 27:
            var h = o.stateNode, d = rp(e);
            Zf(e, d, h);
            break;
          case 5:
            var x = o.stateNode;
            o.flags & 32 && (Xo(x, ""), o.flags &= -33);
            var M = rp(e);
            Zf(e, M, x);
            break;
          case 3:
          case 4:
            var E = o.stateNode.containerInfo, _ = rp(e);
            lp(
              e,
              _,
              E
            );
            break;
          default:
            throw Error(a(161));
        }
      } catch (F) {
        Xt(e, e.return, F);
      }
      e.flags &= -3;
    }
    s & 4096 && (e.flags &= -4097);
  }
  function bx(e) {
    if (e.subtreeFlags & 1024)
      for (e = e.child; e !== null; ) {
        var s = e;
        bx(s), s.tag === 5 && s.flags & 1024 && s.stateNode.reset(), e = e.sibling;
      }
  }
  function fs(e, s) {
    if (s.subtreeFlags & 8772)
      for (s = s.child; s !== null; )
        mx(e, s.alternate, s), s = s.sibling;
  }
  function Aa(e) {
    for (e = e.child; e !== null; ) {
      var s = e;
      switch (s.tag) {
        case 0:
        case 11:
        case 14:
        case 15:
          cs(4, s, s.return), Aa(s);
          break;
        case 1:
          ri(s, s.return);
          var o = s.stateNode;
          typeof o.componentWillUnmount == "function" && ux(
            s,
            s.return,
            o
          ), Aa(s);
          break;
        case 27:
          Eu(s.stateNode);
        case 26:
        case 5:
          ri(s, s.return), Aa(s);
          break;
        case 22:
          s.memoizedState === null && Aa(s);
          break;
        case 30:
          Aa(s);
          break;
        default:
          Aa(s);
      }
      e = e.sibling;
    }
  }
  function hs(e, s, o) {
    for (o = o && (s.subtreeFlags & 8772) !== 0, s = s.child; s !== null; ) {
      var l = s.alternate, h = e, d = s, x = d.flags;
      switch (d.tag) {
        case 0:
        case 11:
        case 15:
          hs(
            h,
            d,
            o
          ), gu(4, d);
          break;
        case 1:
          if (hs(
            h,
            d,
            o
          ), l = d, h = l.stateNode, typeof h.componentDidMount == "function")
            try {
              h.componentDidMount();
            } catch (_) {
              Xt(l, l.return, _);
            }
          if (l = d, h = l.updateQueue, h !== null) {
            var M = l.stateNode;
            try {
              var E = h.shared.hiddenCallbacks;
              if (E !== null)
                for (h.shared.hiddenCallbacks = null, h = 0; h < E.length; h++)
                  Qb(E[h], M);
            } catch (_) {
              Xt(l, l.return, _);
            }
          }
          o && x & 64 && lx(d), yu(d, d.return);
          break;
        case 27:
          hx(d);
        case 26:
        case 5:
          hs(
            h,
            d,
            o
          ), o && l === null && x & 4 && cx(d), yu(d, d.return);
          break;
        case 12:
          hs(
            h,
            d,
            o
          );
          break;
        case 13:
          hs(
            h,
            d,
            o
          ), o && x & 4 && yx(h, d);
          break;
        case 22:
          d.memoizedState === null && hs(
            h,
            d,
            o
          ), yu(d, d.return);
          break;
        case 30:
          break;
        default:
          hs(
            h,
            d,
            o
          );
      }
      s = s.sibling;
    }
  }
  function fp(e, s) {
    var o = null;
    e !== null && e.memoizedState !== null && e.memoizedState.cachePool !== null && (o = e.memoizedState.cachePool.pool), e = null, s.memoizedState !== null && s.memoizedState.cachePool !== null && (e = s.memoizedState.cachePool.pool), e !== o && (e != null && e.refCount++, o != null && nu(o));
  }
  function hp(e, s) {
    e = null, s.alternate !== null && (e = s.alternate.memoizedState.cache), s = s.memoizedState.cache, s !== e && (s.refCount++, e != null && nu(e));
  }
  function li(e, s, o, l) {
    if (s.subtreeFlags & 10256)
      for (s = s.child; s !== null; )
        xx(
          e,
          s,
          o,
          l
        ), s = s.sibling;
  }
  function xx(e, s, o, l) {
    var h = s.flags;
    switch (s.tag) {
      case 0:
      case 11:
      case 15:
        li(
          e,
          s,
          o,
          l
        ), h & 2048 && gu(9, s);
        break;
      case 1:
        li(
          e,
          s,
          o,
          l
        );
        break;
      case 3:
        li(
          e,
          s,
          o,
          l
        ), h & 2048 && (e = null, s.alternate !== null && (e = s.alternate.memoizedState.cache), s = s.memoizedState.cache, s !== e && (s.refCount++, e != null && nu(e)));
        break;
      case 12:
        if (h & 2048) {
          li(
            e,
            s,
            o,
            l
          ), e = s.stateNode;
          try {
            var d = s.memoizedProps, x = d.id, M = d.onPostCommit;
            typeof M == "function" && M(
              x,
              s.alternate === null ? "mount" : "update",
              e.passiveEffectDuration,
              -0
            );
          } catch (E) {
            Xt(s, s.return, E);
          }
        } else
          li(
            e,
            s,
            o,
            l
          );
        break;
      case 13:
        li(
          e,
          s,
          o,
          l
        );
        break;
      case 23:
        break;
      case 22:
        d = s.stateNode, x = s.alternate, s.memoizedState !== null ? d._visibility & 2 ? li(
          e,
          s,
          o,
          l
        ) : vu(e, s) : d._visibility & 2 ? li(
          e,
          s,
          o,
          l
        ) : (d._visibility |= 2, cr(
          e,
          s,
          o,
          l,
          (s.subtreeFlags & 10256) !== 0
        )), h & 2048 && fp(x, s);
        break;
      case 24:
        li(
          e,
          s,
          o,
          l
        ), h & 2048 && hp(s.alternate, s);
        break;
      default:
        li(
          e,
          s,
          o,
          l
        );
    }
  }
  function cr(e, s, o, l, h) {
    for (h = h && (s.subtreeFlags & 10256) !== 0, s = s.child; s !== null; ) {
      var d = e, x = s, M = o, E = l, _ = x.flags;
      switch (x.tag) {
        case 0:
        case 11:
        case 15:
          cr(
            d,
            x,
            M,
            E,
            h
          ), gu(8, x);
          break;
        case 23:
          break;
        case 22:
          var F = x.stateNode;
          x.memoizedState !== null ? F._visibility & 2 ? cr(
            d,
            x,
            M,
            E,
            h
          ) : vu(
            d,
            x
          ) : (F._visibility |= 2, cr(
            d,
            x,
            M,
            E,
            h
          )), h && _ & 2048 && fp(
            x.alternate,
            x
          );
          break;
        case 24:
          cr(
            d,
            x,
            M,
            E,
            h
          ), h && _ & 2048 && hp(x.alternate, x);
          break;
        default:
          cr(
            d,
            x,
            M,
            E,
            h
          );
      }
      s = s.sibling;
    }
  }
  function vu(e, s) {
    if (s.subtreeFlags & 10256)
      for (s = s.child; s !== null; ) {
        var o = e, l = s, h = l.flags;
        switch (l.tag) {
          case 22:
            vu(o, l), h & 2048 && fp(
              l.alternate,
              l
            );
            break;
          case 24:
            vu(o, l), h & 2048 && hp(l.alternate, l);
            break;
          default:
            vu(o, l);
        }
        s = s.sibling;
      }
  }
  var bu = 8192;
  function fr(e) {
    if (e.subtreeFlags & bu)
      for (e = e.child; e !== null; )
        Sx(e), e = e.sibling;
  }
  function Sx(e) {
    switch (e.tag) {
      case 26:
        fr(e), e.flags & bu && e.memoizedState !== null && vR(
          Fn,
          e.memoizedState,
          e.memoizedProps
        );
        break;
      case 5:
        fr(e);
        break;
      case 3:
      case 4:
        var s = Fn;
        Fn = oh(e.stateNode.containerInfo), fr(e), Fn = s;
        break;
      case 22:
        e.memoizedState === null && (s = e.alternate, s !== null && s.memoizedState !== null ? (s = bu, bu = 16777216, fr(e), bu = s) : fr(e));
        break;
      default:
        fr(e);
    }
  }
  function wx(e) {
    var s = e.alternate;
    if (s !== null && (e = s.child, e !== null)) {
      s.child = null;
      do
        s = e.sibling, e.sibling = null, e = s;
      while (e !== null);
    }
  }
  function xu(e) {
    var s = e.deletions;
    if ((e.flags & 16) !== 0) {
      if (s !== null)
        for (var o = 0; o < s.length; o++) {
          var l = s[o];
          Ce = l, Tx(
            l,
            e
          );
        }
      wx(e);
    }
    if (e.subtreeFlags & 10256)
      for (e = e.child; e !== null; )
        Mx(e), e = e.sibling;
  }
  function Mx(e) {
    switch (e.tag) {
      case 0:
      case 11:
      case 15:
        xu(e), e.flags & 2048 && cs(9, e, e.return);
        break;
      case 3:
        xu(e);
        break;
      case 12:
        xu(e);
        break;
      case 22:
        var s = e.stateNode;
        e.memoizedState !== null && s._visibility & 2 && (e.return === null || e.return.tag !== 13) ? (s._visibility &= -3, Qf(e)) : xu(e);
        break;
      default:
        xu(e);
    }
  }
  function Qf(e) {
    var s = e.deletions;
    if ((e.flags & 16) !== 0) {
      if (s !== null)
        for (var o = 0; o < s.length; o++) {
          var l = s[o];
          Ce = l, Tx(
            l,
            e
          );
        }
      wx(e);
    }
    for (e = e.child; e !== null; ) {
      switch (s = e, s.tag) {
        case 0:
        case 11:
        case 15:
          cs(8, s, s.return), Qf(s);
          break;
        case 22:
          o = s.stateNode, o._visibility & 2 && (o._visibility &= -3, Qf(s));
          break;
        default:
          Qf(s);
      }
      e = e.sibling;
    }
  }
  function Tx(e, s) {
    for (; Ce !== null; ) {
      var o = Ce;
      switch (o.tag) {
        case 0:
        case 11:
        case 15:
          cs(8, o, s);
          break;
        case 23:
        case 22:
          if (o.memoizedState !== null && o.memoizedState.cachePool !== null) {
            var l = o.memoizedState.cachePool.pool;
            l != null && l.refCount++;
          }
          break;
        case 24:
          nu(o.memoizedState.cache);
      }
      if (l = o.child, l !== null) l.return = o, Ce = l;
      else
        t: for (o = e; Ce !== null; ) {
          l = Ce;
          var h = l.sibling, d = l.return;
          if (px(l), l === o) {
            Ce = null;
            break t;
          }
          if (h !== null) {
            h.return = d, Ce = h;
            break t;
          }
          Ce = d;
        }
    }
  }
  var PD = {
    getCacheForType: function(e) {
      var s = _e(xe), o = s.data.get(e);
      return o === void 0 && (o = e(), s.data.set(e, o)), o;
    }
  }, LD = typeof WeakMap == "function" ? WeakMap : Map, Nt = 0, $t = null, Et = null, Rt = 0, Ut = 0, mn = null, ds = !1, hr = !1, dp = !1, Zi = 0, re = 0, ms = 0, Da = 0, mp = 0, Dn = 0, dr = 0, Su = null, nn = null, pp = !1, gp = 0, Kf = 1 / 0, If = null, ps = null, ze = 0, gs = null, mr = null, pr = 0, yp = 0, vp = null, Cx = null, wu = 0, bp = null;
  function pn() {
    if ((Nt & 2) !== 0 && Rt !== 0)
      return Rt & -Rt;
    if (j.T !== null) {
      var e = nr;
      return e !== 0 ? e : Ep();
    }
    return Hv();
  }
  function Ex() {
    Dn === 0 && (Dn = (Rt & 536870912) === 0 || _t ? Bv() : 536870912);
    var e = An.current;
    return e !== null && (e.flags |= 32), Dn;
  }
  function gn(e, s, o) {
    (e === $t && (Ut === 2 || Ut === 9) || e.cancelPendingCommit !== null) && (gr(e, 0), ys(
      e,
      Rt,
      Dn,
      !1
    )), jl(e, o), ((Nt & 2) === 0 || e !== $t) && (e === $t && ((Nt & 2) === 0 && (Da |= o), re === 4 && ys(
      e,
      Rt,
      Dn,
      !1
    )), ui(e));
  }
  function Ax(e, s, o) {
    if ((Nt & 6) !== 0) throw Error(a(327));
    var l = !o && (s & 124) === 0 && (s & e.expiredLanes) === 0 || Ul(e, s), h = l ? ND(e, s) : wp(e, s, !0), d = l;
    do {
      if (h === 0) {
        hr && !l && ys(e, s, 0, !1);
        break;
      } else {
        if (o = e.current.alternate, d && !_D(o)) {
          h = wp(e, s, !1), d = !1;
          continue;
        }
        if (h === 2) {
          if (d = s, e.errorRecoveryDisabledLanes & d)
            var x = 0;
          else
            x = e.pendingLanes & -536870913, x = x !== 0 ? x : x & 536870912 ? 536870912 : 0;
          if (x !== 0) {
            s = x;
            t: {
              var M = e;
              h = Su;
              var E = M.current.memoizedState.isDehydrated;
              if (E && (gr(M, x).flags |= 256), x = wp(
                M,
                x,
                !1
              ), x !== 2) {
                if (dp && !E) {
                  M.errorRecoveryDisabledLanes |= d, Da |= d, h = 4;
                  break t;
                }
                d = nn, nn = h, d !== null && (nn === null ? nn = d : nn.push.apply(
                  nn,
                  d
                ));
              }
              h = x;
            }
            if (d = !1, h !== 2) continue;
          }
        }
        if (h === 1) {
          gr(e, 0), ys(e, s, 0, !0);
          break;
        }
        t: {
          switch (l = e, d = h, d) {
            case 0:
            case 1:
              throw Error(a(345));
            case 4:
              if ((s & 4194048) !== s) break;
            case 6:
              ys(
                l,
                s,
                Dn,
                !ds
              );
              break t;
            case 2:
              nn = null;
              break;
            case 3:
            case 5:
              break;
            default:
              throw Error(a(329));
          }
          if ((s & 62914560) === s && (h = gp + 300 - si(), 10 < h)) {
            if (ys(
              l,
              s,
              Dn,
              !ds
            ), rf(l, 0, !0) !== 0) break t;
            l.timeoutHandle = nS(
              Dx.bind(
                null,
                l,
                o,
                nn,
                If,
                pp,
                s,
                Dn,
                Da,
                dr,
                ds,
                d,
                2,
                -0,
                0
              ),
              h
            );
            break t;
          }
          Dx(
            l,
            o,
            nn,
            If,
            pp,
            s,
            Dn,
            Da,
            dr,
            ds,
            d,
            0,
            -0,
            0
          );
        }
      }
      break;
    } while (!0);
    ui(e);
  }
  function Dx(e, s, o, l, h, d, x, M, E, _, F, I, N, U) {
    if (e.timeoutHandle = -1, I = s.subtreeFlags, (I & 8192 || (I & 16785408) === 16785408) && (Ru = { stylesheets: null, count: 0, unsuspend: yR }, Sx(s), I = bR(), I !== null)) {
      e.cancelPendingCommit = I(
        Lx.bind(
          null,
          e,
          s,
          d,
          o,
          l,
          h,
          x,
          M,
          E,
          F,
          1,
          N,
          U
        )
      ), ys(e, d, x, !_);
      return;
    }
    Lx(
      e,
      s,
      d,
      o,
      l,
      h,
      x,
      M,
      E
    );
  }
  function _D(e) {
    for (var s = e; ; ) {
      var o = s.tag;
      if ((o === 0 || o === 11 || o === 15) && s.flags & 16384 && (o = s.updateQueue, o !== null && (o = o.stores, o !== null)))
        for (var l = 0; l < o.length; l++) {
          var h = o[l], d = h.getSnapshot;
          h = h.value;
          try {
            if (!cn(d(), h)) return !1;
          } catch {
            return !1;
          }
        }
      if (o = s.child, s.subtreeFlags & 16384 && o !== null)
        o.return = s, s = o;
      else {
        if (s === e) break;
        for (; s.sibling === null; ) {
          if (s.return === null || s.return === e) return !0;
          s = s.return;
        }
        s.sibling.return = s.return, s = s.sibling;
      }
    }
    return !0;
  }
  function ys(e, s, o, l) {
    s &= ~mp, s &= ~Da, e.suspendedLanes |= s, e.pingedLanes &= ~s, l && (e.warmLanes |= s), l = e.expirationTimes;
    for (var h = s; 0 < h; ) {
      var d = 31 - un(h), x = 1 << d;
      l[d] = -1, h &= ~x;
    }
    o !== 0 && Uv(e, o, s);
  }
  function $f() {
    return (Nt & 6) === 0 ? (Mu(0), !1) : !0;
  }
  function xp() {
    if (Et !== null) {
      if (Ut === 0)
        var e = Et.return;
      else
        e = Et, Ui = wa = null, Bm(e), lr = null, du = 0, e = Et;
      for (; e !== null; )
        rx(e.alternate, e), e = e.return;
      Et = null;
    }
  }
  function gr(e, s) {
    var o = e.timeoutHandle;
    o !== -1 && (e.timeoutHandle = -1, tR(o)), o = e.cancelPendingCommit, o !== null && (e.cancelPendingCommit = null, o()), xp(), $t = e, Et = o = _i(e.current, null), Rt = s, Ut = 0, mn = null, ds = !1, hr = Ul(e, s), dp = !1, dr = Dn = mp = Da = ms = re = 0, nn = Su = null, pp = !1, (s & 8) !== 0 && (s |= s & 32);
    var l = e.entangledLanes;
    if (l !== 0)
      for (e = e.entanglements, l &= s; 0 < l; ) {
        var h = 31 - un(l), d = 1 << h;
        s |= e[h], l &= ~d;
      }
    return Zi = s, bf(), o;
  }
  function Rx(e, s) {
    Tt = null, j.H = Nf, s === su || s === Df ? (s = Fb(), Ut = 3) : s === Gb ? (s = Fb(), Ut = 4) : Ut = s === Z0 ? 8 : s !== null && typeof s == "object" && typeof s.then == "function" ? 6 : 1, mn = s, Et === null && (re = 1, Gf(
      e,
      Mn(s, e.current)
    ));
  }
  function Ox() {
    var e = j.H;
    return j.H = Nf, e === null ? Nf : e;
  }
  function zx() {
    var e = j.A;
    return j.A = PD, e;
  }
  function Sp() {
    re = 4, ds || (Rt & 4194048) !== Rt && An.current !== null || (hr = !0), (ms & 134217727) === 0 && (Da & 134217727) === 0 || $t === null || ys(
      $t,
      Rt,
      Dn,
      !1
    );
  }
  function wp(e, s, o) {
    var l = Nt;
    Nt |= 2;
    var h = Ox(), d = zx();
    ($t !== e || Rt !== s) && (If = null, gr(e, s)), s = !1;
    var x = re;
    t: do
      try {
        if (Ut !== 0 && Et !== null) {
          var M = Et, E = mn;
          switch (Ut) {
            case 8:
              xp(), x = 6;
              break t;
            case 3:
            case 2:
            case 9:
            case 6:
              An.current === null && (s = !0);
              var _ = Ut;
              if (Ut = 0, mn = null, yr(e, M, E, _), o && hr) {
                x = 0;
                break t;
              }
              break;
            default:
              _ = Ut, Ut = 0, mn = null, yr(e, M, E, _);
          }
        }
        BD(), x = re;
        break;
      } catch (F) {
        Rx(e, F);
      }
    while (!0);
    return s && e.shellSuspendCounter++, Ui = wa = null, Nt = l, j.H = h, j.A = d, Et === null && ($t = null, Rt = 0, bf()), x;
  }
  function BD() {
    for (; Et !== null; ) kx(Et);
  }
  function ND(e, s) {
    var o = Nt;
    Nt |= 2;
    var l = Ox(), h = zx();
    $t !== e || Rt !== s ? (If = null, Kf = si() + 500, gr(e, s)) : hr = Ul(
      e,
      s
    );
    t: do
      try {
        if (Ut !== 0 && Et !== null) {
          s = Et;
          var d = mn;
          e: switch (Ut) {
            case 1:
              Ut = 0, mn = null, yr(e, s, d, 1);
              break;
            case 2:
            case 9:
              if (Yb(d)) {
                Ut = 0, mn = null, Vx(s);
                break;
              }
              s = function() {
                Ut !== 2 && Ut !== 9 || $t !== e || (Ut = 7), ui(e);
              }, d.then(s, s);
              break t;
            case 3:
              Ut = 7;
              break t;
            case 4:
              Ut = 5;
              break t;
            case 7:
              Yb(d) ? (Ut = 0, mn = null, Vx(s)) : (Ut = 0, mn = null, yr(e, s, d, 7));
              break;
            case 5:
              var x = null;
              switch (Et.tag) {
                case 26:
                  x = Et.memoizedState;
                case 5:
                case 27:
                  var M = Et;
                  if (!x || mS(x)) {
                    Ut = 0, mn = null;
                    var E = M.sibling;
                    if (E !== null) Et = E;
                    else {
                      var _ = M.return;
                      _ !== null ? (Et = _, Wf(_)) : Et = null;
                    }
                    break e;
                  }
              }
              Ut = 0, mn = null, yr(e, s, d, 5);
              break;
            case 6:
              Ut = 0, mn = null, yr(e, s, d, 6);
              break;
            case 8:
              xp(), re = 6;
              break t;
            default:
              throw Error(a(462));
          }
        }
        UD();
        break;
      } catch (F) {
        Rx(e, F);
      }
    while (!0);
    return Ui = wa = null, j.H = l, j.A = h, Nt = o, Et !== null ? 0 : ($t = null, Rt = 0, bf(), re);
  }
  function UD() {
    for (; Et !== null && !rA(); )
      kx(Et);
  }
  function kx(e) {
    var s = ax(e.alternate, e, Zi);
    e.memoizedProps = e.pendingProps, s === null ? Wf(e) : Et = s;
  }
  function Vx(e) {
    var s = e, o = s.alternate;
    switch (s.tag) {
      case 15:
      case 0:
        s = J0(
          o,
          s,
          s.pendingProps,
          s.type,
          void 0,
          Rt
        );
        break;
      case 11:
        s = J0(
          o,
          s,
          s.pendingProps,
          s.type.render,
          s.ref,
          Rt
        );
        break;
      case 5:
        Bm(s);
      default:
        rx(o, s), s = Et = Pb(s, Zi), s = ax(o, s, Zi);
    }
    e.memoizedProps = e.pendingProps, s === null ? Wf(e) : Et = s;
  }
  function yr(e, s, o, l) {
    Ui = wa = null, Bm(s), lr = null, du = 0;
    var h = s.return;
    try {
      if (DD(
        e,
        h,
        s,
        o,
        Rt
      )) {
        re = 1, Gf(
          e,
          Mn(o, e.current)
        ), Et = null;
        return;
      }
    } catch (d) {
      if (h !== null) throw Et = h, d;
      re = 1, Gf(
        e,
        Mn(o, e.current)
      ), Et = null;
      return;
    }
    s.flags & 32768 ? (_t || l === 1 ? e = !0 : hr || (Rt & 536870912) !== 0 ? e = !1 : (ds = e = !0, (l === 2 || l === 9 || l === 3 || l === 6) && (l = An.current, l !== null && l.tag === 13 && (l.flags |= 16384))), Px(s, e)) : Wf(s);
  }
  function Wf(e) {
    var s = e;
    do {
      if ((s.flags & 32768) !== 0) {
        Px(
          s,
          ds
        );
        return;
      }
      e = s.return;
      var o = OD(
        s.alternate,
        s,
        Zi
      );
      if (o !== null) {
        Et = o;
        return;
      }
      if (s = s.sibling, s !== null) {
        Et = s;
        return;
      }
      Et = s = e;
    } while (s !== null);
    re === 0 && (re = 5);
  }
  function Px(e, s) {
    do {
      var o = zD(e.alternate, e);
      if (o !== null) {
        o.flags &= 32767, Et = o;
        return;
      }
      if (o = e.return, o !== null && (o.flags |= 32768, o.subtreeFlags = 0, o.deletions = null), !s && (e = e.sibling, e !== null)) {
        Et = e;
        return;
      }
      Et = e = o;
    } while (e !== null);
    re = 6, Et = null;
  }
  function Lx(e, s, o, l, h, d, x, M, E) {
    e.cancelPendingCommit = null;
    do
      Jf();
    while (ze !== 0);
    if ((Nt & 6) !== 0) throw Error(a(327));
    if (s !== null) {
      if (s === e.current) throw Error(a(177));
      if (d = s.lanes | s.childLanes, d |= hm, yA(
        e,
        o,
        d,
        x,
        M,
        E
      ), e === $t && (Et = $t = null, Rt = 0), mr = s, gs = e, pr = o, yp = d, vp = h, Cx = l, (s.subtreeFlags & 10256) !== 0 || (s.flags & 10256) !== 0 ? (e.callbackNode = null, e.callbackPriority = 0, GD(sf, function() {
        return jx(), null;
      })) : (e.callbackNode = null, e.callbackPriority = 0), l = (s.flags & 13878) !== 0, (s.subtreeFlags & 13878) !== 0 || l) {
        l = j.T, j.T = null, h = W.p, W.p = 2, x = Nt, Nt |= 4;
        try {
          kD(e, s, o);
        } finally {
          Nt = x, W.p = h, j.T = l;
        }
      }
      ze = 1, _x(), Bx(), Nx();
    }
  }
  function _x() {
    if (ze === 1) {
      ze = 0;
      var e = gs, s = mr, o = (s.flags & 13878) !== 0;
      if ((s.subtreeFlags & 13878) !== 0 || o) {
        o = j.T, j.T = null;
        var l = W.p;
        W.p = 2;
        var h = Nt;
        Nt |= 4;
        try {
          vx(s, e);
          var d = Pp, x = Tb(e.containerInfo), M = d.focusedElem, E = d.selectionRange;
          if (x !== M && M && M.ownerDocument && Mb(
            M.ownerDocument.documentElement,
            M
          )) {
            if (E !== null && rm(M)) {
              var _ = E.start, F = E.end;
              if (F === void 0 && (F = _), "selectionStart" in M)
                M.selectionStart = _, M.selectionEnd = Math.min(
                  F,
                  M.value.length
                );
              else {
                var I = M.ownerDocument || document, N = I && I.defaultView || window;
                if (N.getSelection) {
                  var U = N.getSelection(), pt = M.textContent.length, dt = Math.min(E.start, pt), Gt = E.end === void 0 ? dt : Math.min(E.end, pt);
                  !U.extend && dt > Gt && (x = Gt, Gt = dt, dt = x);
                  var V = wb(
                    M,
                    dt
                  ), O = wb(
                    M,
                    Gt
                  );
                  if (V && O && (U.rangeCount !== 1 || U.anchorNode !== V.node || U.anchorOffset !== V.offset || U.focusNode !== O.node || U.focusOffset !== O.offset)) {
                    var P = I.createRange();
                    P.setStart(V.node, V.offset), U.removeAllRanges(), dt > Gt ? (U.addRange(P), U.extend(O.node, O.offset)) : (P.setEnd(O.node, O.offset), U.addRange(P));
                  }
                }
              }
            }
            for (I = [], U = M; U = U.parentNode; )
              U.nodeType === 1 && I.push({
                element: U,
                left: U.scrollLeft,
                top: U.scrollTop
              });
            for (typeof M.focus == "function" && M.focus(), M = 0; M < I.length; M++) {
              var K = I[M];
              K.element.scrollLeft = K.left, K.element.scrollTop = K.top;
            }
          }
          fh = !!Vp, Pp = Vp = null;
        } finally {
          Nt = h, W.p = l, j.T = o;
        }
      }
      e.current = s, ze = 2;
    }
  }
  function Bx() {
    if (ze === 2) {
      ze = 0;
      var e = gs, s = mr, o = (s.flags & 8772) !== 0;
      if ((s.subtreeFlags & 8772) !== 0 || o) {
        o = j.T, j.T = null;
        var l = W.p;
        W.p = 2;
        var h = Nt;
        Nt |= 4;
        try {
          mx(e, s.alternate, s);
        } finally {
          Nt = h, W.p = l, j.T = o;
        }
      }
      ze = 3;
    }
  }
  function Nx() {
    if (ze === 4 || ze === 3) {
      ze = 0, lA();
      var e = gs, s = mr, o = pr, l = Cx;
      (s.subtreeFlags & 10256) !== 0 || (s.flags & 10256) !== 0 ? ze = 5 : (ze = 0, mr = gs = null, Ux(e, e.pendingLanes));
      var h = e.pendingLanes;
      if (h === 0 && (ps = null), jd(o), s = s.stateNode, ln && typeof ln.onCommitFiberRoot == "function")
        try {
          ln.onCommitFiberRoot(
            Nl,
            s,
            void 0,
            (s.current.flags & 128) === 128
          );
        } catch {
        }
      if (l !== null) {
        s = j.T, h = W.p, W.p = 2, j.T = null;
        try {
          for (var d = e.onRecoverableError, x = 0; x < l.length; x++) {
            var M = l[x];
            d(M.value, {
              componentStack: M.stack
            });
          }
        } finally {
          j.T = s, W.p = h;
        }
      }
      (pr & 3) !== 0 && Jf(), ui(e), h = e.pendingLanes, (o & 4194090) !== 0 && (h & 42) !== 0 ? e === bp ? wu++ : (wu = 0, bp = e) : wu = 0, Mu(0);
    }
  }
  function Ux(e, s) {
    (e.pooledCacheLanes &= s) === 0 && (s = e.pooledCache, s != null && (e.pooledCache = null, nu(s)));
  }
  function Jf(e) {
    return _x(), Bx(), Nx(), jx();
  }
  function jx() {
    if (ze !== 5) return !1;
    var e = gs, s = yp;
    yp = 0;
    var o = jd(pr), l = j.T, h = W.p;
    try {
      W.p = 32 > o ? 32 : o, j.T = null, o = vp, vp = null;
      var d = gs, x = pr;
      if (ze = 0, mr = gs = null, pr = 0, (Nt & 6) !== 0) throw Error(a(331));
      var M = Nt;
      if (Nt |= 4, Mx(d.current), xx(
        d,
        d.current,
        x,
        o
      ), Nt = M, Mu(0, !1), ln && typeof ln.onPostCommitFiberRoot == "function")
        try {
          ln.onPostCommitFiberRoot(Nl, d);
        } catch {
        }
      return !0;
    } finally {
      W.p = h, j.T = l, Ux(e, s);
    }
  }
  function Hx(e, s, o) {
    s = Mn(o, s), s = $m(e.stateNode, s, 2), e = os(e, s, 2), e !== null && (jl(e, 2), ui(e));
  }
  function Xt(e, s, o) {
    if (e.tag === 3)
      Hx(e, e, o);
    else
      for (; s !== null; ) {
        if (s.tag === 3) {
          Hx(
            s,
            e,
            o
          );
          break;
        } else if (s.tag === 1) {
          var l = s.stateNode;
          if (typeof s.type.getDerivedStateFromError == "function" || typeof l.componentDidCatch == "function" && (ps === null || !ps.has(l))) {
            e = Mn(o, e), o = X0(2), l = os(s, o, 2), l !== null && (F0(
              o,
              l,
              s,
              e
            ), jl(l, 2), ui(l));
            break;
          }
        }
        s = s.return;
      }
  }
  function Mp(e, s, o) {
    var l = e.pingCache;
    if (l === null) {
      l = e.pingCache = new LD();
      var h = /* @__PURE__ */ new Set();
      l.set(s, h);
    } else
      h = l.get(s), h === void 0 && (h = /* @__PURE__ */ new Set(), l.set(s, h));
    h.has(o) || (dp = !0, h.add(o), e = jD.bind(null, e, s, o), s.then(e, e));
  }
  function jD(e, s, o) {
    var l = e.pingCache;
    l !== null && l.delete(s), e.pingedLanes |= e.suspendedLanes & o, e.warmLanes &= ~o, $t === e && (Rt & o) === o && (re === 4 || re === 3 && (Rt & 62914560) === Rt && 300 > si() - gp ? (Nt & 2) === 0 && gr(e, 0) : mp |= o, dr === Rt && (dr = 0)), ui(e);
  }
  function qx(e, s) {
    s === 0 && (s = Nv()), e = Wo(e, s), e !== null && (jl(e, s), ui(e));
  }
  function HD(e) {
    var s = e.memoizedState, o = 0;
    s !== null && (o = s.retryLane), qx(e, o);
  }
  function qD(e, s) {
    var o = 0;
    switch (e.tag) {
      case 13:
        var l = e.stateNode, h = e.memoizedState;
        h !== null && (o = h.retryLane);
        break;
      case 19:
        l = e.stateNode;
        break;
      case 22:
        l = e.stateNode._retryCache;
        break;
      default:
        throw Error(a(314));
    }
    l !== null && l.delete(s), qx(e, o);
  }
  function GD(e, s) {
    return _d(e, s);
  }
  var th = null, vr = null, Tp = !1, eh = !1, Cp = !1, Ra = 0;
  function ui(e) {
    e !== vr && e.next === null && (vr === null ? th = vr = e : vr = vr.next = e), eh = !0, Tp || (Tp = !0, XD());
  }
  function Mu(e, s) {
    if (!Cp && eh) {
      Cp = !0;
      do
        for (var o = !1, l = th; l !== null; ) {
          if (e !== 0) {
            var h = l.pendingLanes;
            if (h === 0) var d = 0;
            else {
              var x = l.suspendedLanes, M = l.pingedLanes;
              d = (1 << 31 - un(42 | e) + 1) - 1, d &= h & ~(x & ~M), d = d & 201326741 ? d & 201326741 | 1 : d ? d | 2 : 0;
            }
            d !== 0 && (o = !0, Fx(l, d));
          } else
            d = Rt, d = rf(
              l,
              l === $t ? d : 0,
              l.cancelPendingCommit !== null || l.timeoutHandle !== -1
            ), (d & 3) === 0 || Ul(l, d) || (o = !0, Fx(l, d));
          l = l.next;
        }
      while (o);
      Cp = !1;
    }
  }
  function YD() {
    Gx();
  }
  function Gx() {
    eh = Tp = !1;
    var e = 0;
    Ra !== 0 && (JD() && (e = Ra), Ra = 0);
    for (var s = si(), o = null, l = th; l !== null; ) {
      var h = l.next, d = Yx(l, s);
      d === 0 ? (l.next = null, o === null ? th = h : o.next = h, h === null && (vr = o)) : (o = l, (e !== 0 || (d & 3) !== 0) && (eh = !0)), l = h;
    }
    Mu(e);
  }
  function Yx(e, s) {
    for (var o = e.suspendedLanes, l = e.pingedLanes, h = e.expirationTimes, d = e.pendingLanes & -62914561; 0 < d; ) {
      var x = 31 - un(d), M = 1 << x, E = h[x];
      E === -1 ? ((M & o) === 0 || (M & l) !== 0) && (h[x] = gA(M, s)) : E <= s && (e.expiredLanes |= M), d &= ~M;
    }
    if (s = $t, o = Rt, o = rf(
      e,
      e === s ? o : 0,
      e.cancelPendingCommit !== null || e.timeoutHandle !== -1
    ), l = e.callbackNode, o === 0 || e === s && (Ut === 2 || Ut === 9) || e.cancelPendingCommit !== null)
      return l !== null && l !== null && Bd(l), e.callbackNode = null, e.callbackPriority = 0;
    if ((o & 3) === 0 || Ul(e, o)) {
      if (s = o & -o, s === e.callbackPriority) return s;
      switch (l !== null && Bd(l), jd(o)) {
        case 2:
        case 8:
          o = Lv;
          break;
        case 32:
          o = sf;
          break;
        case 268435456:
          o = _v;
          break;
        default:
          o = sf;
      }
      return l = Xx.bind(null, e), o = _d(o, l), e.callbackPriority = s, e.callbackNode = o, s;
    }
    return l !== null && l !== null && Bd(l), e.callbackPriority = 2, e.callbackNode = null, 2;
  }
  function Xx(e, s) {
    if (ze !== 0 && ze !== 5)
      return e.callbackNode = null, e.callbackPriority = 0, null;
    var o = e.callbackNode;
    if (Jf() && e.callbackNode !== o)
      return null;
    var l = Rt;
    return l = rf(
      e,
      e === $t ? l : 0,
      e.cancelPendingCommit !== null || e.timeoutHandle !== -1
    ), l === 0 ? null : (Ax(e, l, s), Yx(e, si()), e.callbackNode != null && e.callbackNode === o ? Xx.bind(null, e) : null);
  }
  function Fx(e, s) {
    if (Jf()) return null;
    Ax(e, s, !0);
  }
  function XD() {
    eR(function() {
      (Nt & 6) !== 0 ? _d(
        Pv,
        YD
      ) : Gx();
    });
  }
  function Ep() {
    return Ra === 0 && (Ra = Bv()), Ra;
  }
  function Zx(e) {
    return e == null || typeof e == "symbol" || typeof e == "boolean" ? null : typeof e == "function" ? e : hf("" + e);
  }
  function Qx(e, s) {
    var o = s.ownerDocument.createElement("input");
    return o.name = s.name, o.value = s.value, e.id && o.setAttribute("form", e.id), s.parentNode.insertBefore(o, s), e = new FormData(e), o.parentNode.removeChild(o), e;
  }
  function FD(e, s, o, l, h) {
    if (s === "submit" && o && o.stateNode === h) {
      var d = Zx(
        (h[We] || null).action
      ), x = l.submitter;
      x && (s = (s = x[We] || null) ? Zx(s.formAction) : x.getAttribute("formAction"), s !== null && (d = s, x = null));
      var M = new gf(
        "action",
        "action",
        null,
        l,
        h
      );
      e.push({
        event: M,
        listeners: [
          {
            instance: null,
            listener: function() {
              if (l.defaultPrevented) {
                if (Ra !== 0) {
                  var E = x ? Qx(h, x) : new FormData(h);
                  Fm(
                    o,
                    {
                      pending: !0,
                      data: E,
                      method: h.method,
                      action: d
                    },
                    null,
                    E
                  );
                }
              } else
                typeof d == "function" && (M.preventDefault(), E = x ? Qx(h, x) : new FormData(h), Fm(
                  o,
                  {
                    pending: !0,
                    data: E,
                    method: h.method,
                    action: d
                  },
                  d,
                  E
                ));
            },
            currentTarget: h
          }
        ]
      });
    }
  }
  for (var Ap = 0; Ap < fm.length; Ap++) {
    var Dp = fm[Ap], ZD = Dp.toLowerCase(), QD = Dp[0].toUpperCase() + Dp.slice(1);
    Xn(
      ZD,
      "on" + QD
    );
  }
  Xn(Ab, "onAnimationEnd"), Xn(Db, "onAnimationIteration"), Xn(Rb, "onAnimationStart"), Xn("dblclick", "onDoubleClick"), Xn("focusin", "onFocus"), Xn("focusout", "onBlur"), Xn(fD, "onTransitionRun"), Xn(hD, "onTransitionStart"), Xn(dD, "onTransitionCancel"), Xn(Ob, "onTransitionEnd"), qo("onMouseEnter", ["mouseout", "mouseover"]), qo("onMouseLeave", ["mouseout", "mouseover"]), qo("onPointerEnter", ["pointerout", "pointerover"]), qo("onPointerLeave", ["pointerout", "pointerover"]), da(
    "onChange",
    "change click focusin focusout input keydown keyup selectionchange".split(" ")
  ), da(
    "onSelect",
    "focusout contextmenu dragend focusin keydown keyup mousedown mouseup selectionchange".split(
      " "
    )
  ), da("onBeforeInput", [
    "compositionend",
    "keypress",
    "textInput",
    "paste"
  ]), da(
    "onCompositionEnd",
    "compositionend focusout keydown keypress keyup mousedown".split(" ")
  ), da(
    "onCompositionStart",
    "compositionstart focusout keydown keypress keyup mousedown".split(" ")
  ), da(
    "onCompositionUpdate",
    "compositionupdate focusout keydown keypress keyup mousedown".split(" ")
  );
  var Tu = "abort canplay canplaythrough durationchange emptied encrypted ended error loadeddata loadedmetadata loadstart pause play playing progress ratechange resize seeked seeking stalled suspend timeupdate volumechange waiting".split(
    " "
  ), KD = new Set(
    "beforetoggle cancel close invalid load scroll scrollend toggle".split(" ").concat(Tu)
  );
  function Kx(e, s) {
    s = (s & 4) !== 0;
    for (var o = 0; o < e.length; o++) {
      var l = e[o], h = l.event;
      l = l.listeners;
      t: {
        var d = void 0;
        if (s)
          for (var x = l.length - 1; 0 <= x; x--) {
            var M = l[x], E = M.instance, _ = M.currentTarget;
            if (M = M.listener, E !== d && h.isPropagationStopped())
              break t;
            d = M, h.currentTarget = _;
            try {
              d(h);
            } catch (F) {
              qf(F);
            }
            h.currentTarget = null, d = E;
          }
        else
          for (x = 0; x < l.length; x++) {
            if (M = l[x], E = M.instance, _ = M.currentTarget, M = M.listener, E !== d && h.isPropagationStopped())
              break t;
            d = M, h.currentTarget = _;
            try {
              d(h);
            } catch (F) {
              qf(F);
            }
            h.currentTarget = null, d = E;
          }
      }
    }
  }
  function At(e, s) {
    var o = s[Hd];
    o === void 0 && (o = s[Hd] = /* @__PURE__ */ new Set());
    var l = e + "__bubble";
    o.has(l) || (Ix(s, e, 2, !1), o.add(l));
  }
  function Rp(e, s, o) {
    var l = 0;
    s && (l |= 4), Ix(
      o,
      e,
      l,
      s
    );
  }
  var nh = "_reactListening" + Math.random().toString(36).slice(2);
  function Op(e) {
    if (!e[nh]) {
      e[nh] = !0, Gv.forEach(function(o) {
        o !== "selectionchange" && (KD.has(o) || Rp(o, !1, e), Rp(o, !0, e));
      });
      var s = e.nodeType === 9 ? e : e.ownerDocument;
      s === null || s[nh] || (s[nh] = !0, Rp("selectionchange", !1, s));
    }
  }
  function Ix(e, s, o, l) {
    switch (xS(s)) {
      case 2:
        var h = wR;
        break;
      case 8:
        h = MR;
        break;
      default:
        h = Yp;
    }
    o = h.bind(
      null,
      s,
      o,
      e
    ), h = void 0, !Wd || s !== "touchstart" && s !== "touchmove" && s !== "wheel" || (h = !0), l ? h !== void 0 ? e.addEventListener(s, o, {
      capture: !0,
      passive: h
    }) : e.addEventListener(s, o, !0) : h !== void 0 ? e.addEventListener(s, o, {
      passive: h
    }) : e.addEventListener(s, o, !1);
  }
  function zp(e, s, o, l, h) {
    var d = l;
    if ((s & 1) === 0 && (s & 2) === 0 && l !== null)
      t: for (; ; ) {
        if (l === null) return;
        var x = l.tag;
        if (x === 3 || x === 4) {
          var M = l.stateNode.containerInfo;
          if (M === h) break;
          if (x === 4)
            for (x = l.return; x !== null; ) {
              var E = x.tag;
              if ((E === 3 || E === 4) && x.stateNode.containerInfo === h)
                return;
              x = x.return;
            }
          for (; M !== null; ) {
            if (x = Uo(M), x === null) return;
            if (E = x.tag, E === 5 || E === 6 || E === 26 || E === 27) {
              l = d = x;
              continue t;
            }
            M = M.parentNode;
          }
        }
        l = l.return;
      }
    ib(function() {
      var _ = d, F = Id(o), I = [];
      t: {
        var N = zb.get(e);
        if (N !== void 0) {
          var U = gf, pt = e;
          switch (e) {
            case "keypress":
              if (mf(o) === 0) break t;
            case "keydown":
            case "keyup":
              U = GA;
              break;
            case "focusin":
              pt = "focus", U = nm;
              break;
            case "focusout":
              pt = "blur", U = nm;
              break;
            case "beforeblur":
            case "afterblur":
              U = nm;
              break;
            case "click":
              if (o.button === 2) break t;
            case "auxclick":
            case "dblclick":
            case "mousedown":
            case "mousemove":
            case "mouseup":
            case "mouseout":
            case "mouseover":
            case "contextmenu":
              U = ob;
              break;
            case "drag":
            case "dragend":
            case "dragenter":
            case "dragexit":
            case "dragleave":
            case "dragover":
            case "dragstart":
            case "drop":
              U = zA;
              break;
            case "touchcancel":
            case "touchend":
            case "touchmove":
            case "touchstart":
              U = FA;
              break;
            case Ab:
            case Db:
            case Rb:
              U = PA;
              break;
            case Ob:
              U = QA;
              break;
            case "scroll":
            case "scrollend":
              U = RA;
              break;
            case "wheel":
              U = IA;
              break;
            case "copy":
            case "cut":
            case "paste":
              U = _A;
              break;
            case "gotpointercapture":
            case "lostpointercapture":
            case "pointercancel":
            case "pointerdown":
            case "pointermove":
            case "pointerout":
            case "pointerover":
            case "pointerup":
              U = lb;
              break;
            case "toggle":
            case "beforetoggle":
              U = WA;
          }
          var dt = (s & 4) !== 0, Gt = !dt && (e === "scroll" || e === "scrollend"), V = dt ? N !== null ? N + "Capture" : null : N;
          dt = [];
          for (var O = _, P; O !== null; ) {
            var K = O;
            if (P = K.stateNode, K = K.tag, K !== 5 && K !== 26 && K !== 27 || P === null || V === null || (K = Gl(O, V), K != null && dt.push(
              Cu(O, K, P)
            )), Gt) break;
            O = O.return;
          }
          0 < dt.length && (N = new U(
            N,
            pt,
            null,
            o,
            F
          ), I.push({ event: N, listeners: dt }));
        }
      }
      if ((s & 7) === 0) {
        t: {
          if (N = e === "mouseover" || e === "pointerover", U = e === "mouseout" || e === "pointerout", N && o !== Kd && (pt = o.relatedTarget || o.fromElement) && (Uo(pt) || pt[No]))
            break t;
          if ((U || N) && (N = F.window === F ? F : (N = F.ownerDocument) ? N.defaultView || N.parentWindow : window, U ? (pt = o.relatedTarget || o.toElement, U = _, pt = pt ? Uo(pt) : null, pt !== null && (Gt = u(pt), dt = pt.tag, pt !== Gt || dt !== 5 && dt !== 27 && dt !== 6) && (pt = null)) : (U = null, pt = _), U !== pt)) {
            if (dt = ob, K = "onMouseLeave", V = "onMouseEnter", O = "mouse", (e === "pointerout" || e === "pointerover") && (dt = lb, K = "onPointerLeave", V = "onPointerEnter", O = "pointer"), Gt = U == null ? N : ql(U), P = pt == null ? N : ql(pt), N = new dt(
              K,
              O + "leave",
              U,
              o,
              F
            ), N.target = Gt, N.relatedTarget = P, K = null, Uo(F) === _ && (dt = new dt(
              V,
              O + "enter",
              pt,
              o,
              F
            ), dt.target = P, dt.relatedTarget = Gt, K = dt), Gt = K, U && pt)
              e: {
                for (dt = U, V = pt, O = 0, P = dt; P; P = br(P))
                  O++;
                for (P = 0, K = V; K; K = br(K))
                  P++;
                for (; 0 < O - P; )
                  dt = br(dt), O--;
                for (; 0 < P - O; )
                  V = br(V), P--;
                for (; O--; ) {
                  if (dt === V || V !== null && dt === V.alternate)
                    break e;
                  dt = br(dt), V = br(V);
                }
                dt = null;
              }
            else dt = null;
            U !== null && $x(
              I,
              N,
              U,
              dt,
              !1
            ), pt !== null && Gt !== null && $x(
              I,
              Gt,
              pt,
              dt,
              !0
            );
          }
        }
        t: {
          if (N = _ ? ql(_) : window, U = N.nodeName && N.nodeName.toLowerCase(), U === "select" || U === "input" && N.type === "file")
            var at = gb;
          else if (mb(N))
            if (yb)
              at = lD;
            else {
              at = oD;
              var Ct = aD;
            }
          else
            U = N.nodeName, !U || U.toLowerCase() !== "input" || N.type !== "checkbox" && N.type !== "radio" ? _ && Qd(_.elementType) && (at = gb) : at = rD;
          if (at && (at = at(e, _))) {
            pb(
              I,
              at,
              o,
              F
            );
            break t;
          }
          Ct && Ct(e, N, _), e === "focusout" && _ && N.type === "number" && _.memoizedProps.value != null && Zd(N, "number", N.value);
        }
        switch (Ct = _ ? ql(_) : window, e) {
          case "focusin":
            (mb(Ct) || Ct.contentEditable === "true") && (Ko = Ct, lm = _, $l = null);
            break;
          case "focusout":
            $l = lm = Ko = null;
            break;
          case "mousedown":
            um = !0;
            break;
          case "contextmenu":
          case "mouseup":
          case "dragend":
            um = !1, Cb(I, o, F);
            break;
          case "selectionchange":
            if (cD) break;
          case "keydown":
          case "keyup":
            Cb(I, o, F);
        }
        var ct;
        if (sm)
          t: {
            switch (e) {
              case "compositionstart":
                var mt = "onCompositionStart";
                break t;
              case "compositionend":
                mt = "onCompositionEnd";
                break t;
              case "compositionupdate":
                mt = "onCompositionUpdate";
                break t;
            }
            mt = void 0;
          }
        else
          Qo ? hb(e, o) && (mt = "onCompositionEnd") : e === "keydown" && o.keyCode === 229 && (mt = "onCompositionStart");
        mt && (ub && o.locale !== "ko" && (Qo || mt !== "onCompositionStart" ? mt === "onCompositionEnd" && Qo && (ct = sb()) : (ns = F, Jd = "value" in ns ? ns.value : ns.textContent, Qo = !0)), Ct = ih(_, mt), 0 < Ct.length && (mt = new rb(
          mt,
          e,
          null,
          o,
          F
        ), I.push({ event: mt, listeners: Ct }), ct ? mt.data = ct : (ct = db(o), ct !== null && (mt.data = ct)))), (ct = tD ? eD(e, o) : nD(e, o)) && (mt = ih(_, "onBeforeInput"), 0 < mt.length && (Ct = new rb(
          "onBeforeInput",
          "beforeinput",
          null,
          o,
          F
        ), I.push({
          event: Ct,
          listeners: mt
        }), Ct.data = ct)), FD(
          I,
          e,
          _,
          o,
          F
        );
      }
      Kx(I, s);
    });
  }
  function Cu(e, s, o) {
    return {
      instance: e,
      listener: s,
      currentTarget: o
    };
  }
  function ih(e, s) {
    for (var o = s + "Capture", l = []; e !== null; ) {
      var h = e, d = h.stateNode;
      if (h = h.tag, h !== 5 && h !== 26 && h !== 27 || d === null || (h = Gl(e, o), h != null && l.unshift(
        Cu(e, h, d)
      ), h = Gl(e, s), h != null && l.push(
        Cu(e, h, d)
      )), e.tag === 3) return l;
      e = e.return;
    }
    return [];
  }
  function br(e) {
    if (e === null) return null;
    do
      e = e.return;
    while (e && e.tag !== 5 && e.tag !== 27);
    return e || null;
  }
  function $x(e, s, o, l, h) {
    for (var d = s._reactName, x = []; o !== null && o !== l; ) {
      var M = o, E = M.alternate, _ = M.stateNode;
      if (M = M.tag, E !== null && E === l) break;
      M !== 5 && M !== 26 && M !== 27 || _ === null || (E = _, h ? (_ = Gl(o, d), _ != null && x.unshift(
        Cu(o, _, E)
      )) : h || (_ = Gl(o, d), _ != null && x.push(
        Cu(o, _, E)
      ))), o = o.return;
    }
    x.length !== 0 && e.push({ event: s, listeners: x });
  }
  var ID = /\r\n?/g, $D = /\u0000|\uFFFD/g;
  function Wx(e) {
    return (typeof e == "string" ? e : "" + e).replace(ID, `
`).replace($D, "");
  }
  function Jx(e, s) {
    return s = Wx(s), Wx(e) === s;
  }
  function sh() {
  }
  function qt(e, s, o, l, h, d) {
    switch (o) {
      case "children":
        typeof l == "string" ? s === "body" || s === "textarea" && l === "" || Xo(e, l) : (typeof l == "number" || typeof l == "bigint") && s !== "body" && Xo(e, "" + l);
        break;
      case "className":
        uf(e, "class", l);
        break;
      case "tabIndex":
        uf(e, "tabindex", l);
        break;
      case "dir":
      case "role":
      case "viewBox":
      case "width":
      case "height":
        uf(e, o, l);
        break;
      case "style":
        eb(e, l, d);
        break;
      case "data":
        if (s !== "object") {
          uf(e, "data", l);
          break;
        }
      case "src":
      case "href":
        if (l === "" && (s !== "a" || o !== "href")) {
          e.removeAttribute(o);
          break;
        }
        if (l == null || typeof l == "function" || typeof l == "symbol" || typeof l == "boolean") {
          e.removeAttribute(o);
          break;
        }
        l = hf("" + l), e.setAttribute(o, l);
        break;
      case "action":
      case "formAction":
        if (typeof l == "function") {
          e.setAttribute(
            o,
            "javascript:throw new Error('A React form was unexpectedly submitted. If you called form.submit() manually, consider using form.requestSubmit() instead. If you\\'re trying to use event.stopPropagation() in a submit event handler, consider also calling event.preventDefault().')"
          );
          break;
        } else
          typeof d == "function" && (o === "formAction" ? (s !== "input" && qt(e, s, "name", h.name, h, null), qt(
            e,
            s,
            "formEncType",
            h.formEncType,
            h,
            null
          ), qt(
            e,
            s,
            "formMethod",
            h.formMethod,
            h,
            null
          ), qt(
            e,
            s,
            "formTarget",
            h.formTarget,
            h,
            null
          )) : (qt(e, s, "encType", h.encType, h, null), qt(e, s, "method", h.method, h, null), qt(e, s, "target", h.target, h, null)));
        if (l == null || typeof l == "symbol" || typeof l == "boolean") {
          e.removeAttribute(o);
          break;
        }
        l = hf("" + l), e.setAttribute(o, l);
        break;
      case "onClick":
        l != null && (e.onclick = sh);
        break;
      case "onScroll":
        l != null && At("scroll", e);
        break;
      case "onScrollEnd":
        l != null && At("scrollend", e);
        break;
      case "dangerouslySetInnerHTML":
        if (l != null) {
          if (typeof l != "object" || !("__html" in l))
            throw Error(a(61));
          if (o = l.__html, o != null) {
            if (h.children != null) throw Error(a(60));
            e.innerHTML = o;
          }
        }
        break;
      case "multiple":
        e.multiple = l && typeof l != "function" && typeof l != "symbol";
        break;
      case "muted":
        e.muted = l && typeof l != "function" && typeof l != "symbol";
        break;
      case "suppressContentEditableWarning":
      case "suppressHydrationWarning":
      case "defaultValue":
      case "defaultChecked":
      case "innerHTML":
      case "ref":
        break;
      case "autoFocus":
        break;
      case "xlinkHref":
        if (l == null || typeof l == "function" || typeof l == "boolean" || typeof l == "symbol") {
          e.removeAttribute("xlink:href");
          break;
        }
        o = hf("" + l), e.setAttributeNS(
          "http://www.w3.org/1999/xlink",
          "xlink:href",
          o
        );
        break;
      case "contentEditable":
      case "spellCheck":
      case "draggable":
      case "value":
      case "autoReverse":
      case "externalResourcesRequired":
      case "focusable":
      case "preserveAlpha":
        l != null && typeof l != "function" && typeof l != "symbol" ? e.setAttribute(o, "" + l) : e.removeAttribute(o);
        break;
      case "inert":
      case "allowFullScreen":
      case "async":
      case "autoPlay":
      case "controls":
      case "default":
      case "defer":
      case "disabled":
      case "disablePictureInPicture":
      case "disableRemotePlayback":
      case "formNoValidate":
      case "hidden":
      case "loop":
      case "noModule":
      case "noValidate":
      case "open":
      case "playsInline":
      case "readOnly":
      case "required":
      case "reversed":
      case "scoped":
      case "seamless":
      case "itemScope":
        l && typeof l != "function" && typeof l != "symbol" ? e.setAttribute(o, "") : e.removeAttribute(o);
        break;
      case "capture":
      case "download":
        l === !0 ? e.setAttribute(o, "") : l !== !1 && l != null && typeof l != "function" && typeof l != "symbol" ? e.setAttribute(o, l) : e.removeAttribute(o);
        break;
      case "cols":
      case "rows":
      case "size":
      case "span":
        l != null && typeof l != "function" && typeof l != "symbol" && !isNaN(l) && 1 <= l ? e.setAttribute(o, l) : e.removeAttribute(o);
        break;
      case "rowSpan":
      case "start":
        l == null || typeof l == "function" || typeof l == "symbol" || isNaN(l) ? e.removeAttribute(o) : e.setAttribute(o, l);
        break;
      case "popover":
        At("beforetoggle", e), At("toggle", e), lf(e, "popover", l);
        break;
      case "xlinkActuate":
        Pi(
          e,
          "http://www.w3.org/1999/xlink",
          "xlink:actuate",
          l
        );
        break;
      case "xlinkArcrole":
        Pi(
          e,
          "http://www.w3.org/1999/xlink",
          "xlink:arcrole",
          l
        );
        break;
      case "xlinkRole":
        Pi(
          e,
          "http://www.w3.org/1999/xlink",
          "xlink:role",
          l
        );
        break;
      case "xlinkShow":
        Pi(
          e,
          "http://www.w3.org/1999/xlink",
          "xlink:show",
          l
        );
        break;
      case "xlinkTitle":
        Pi(
          e,
          "http://www.w3.org/1999/xlink",
          "xlink:title",
          l
        );
        break;
      case "xlinkType":
        Pi(
          e,
          "http://www.w3.org/1999/xlink",
          "xlink:type",
          l
        );
        break;
      case "xmlBase":
        Pi(
          e,
          "http://www.w3.org/XML/1998/namespace",
          "xml:base",
          l
        );
        break;
      case "xmlLang":
        Pi(
          e,
          "http://www.w3.org/XML/1998/namespace",
          "xml:lang",
          l
        );
        break;
      case "xmlSpace":
        Pi(
          e,
          "http://www.w3.org/XML/1998/namespace",
          "xml:space",
          l
        );
        break;
      case "is":
        lf(e, "is", l);
        break;
      case "innerText":
      case "textContent":
        break;
      default:
        (!(2 < o.length) || o[0] !== "o" && o[0] !== "O" || o[1] !== "n" && o[1] !== "N") && (o = AA.get(o) || o, lf(e, o, l));
    }
  }
  function kp(e, s, o, l, h, d) {
    switch (o) {
      case "style":
        eb(e, l, d);
        break;
      case "dangerouslySetInnerHTML":
        if (l != null) {
          if (typeof l != "object" || !("__html" in l))
            throw Error(a(61));
          if (o = l.__html, o != null) {
            if (h.children != null) throw Error(a(60));
            e.innerHTML = o;
          }
        }
        break;
      case "children":
        typeof l == "string" ? Xo(e, l) : (typeof l == "number" || typeof l == "bigint") && Xo(e, "" + l);
        break;
      case "onScroll":
        l != null && At("scroll", e);
        break;
      case "onScrollEnd":
        l != null && At("scrollend", e);
        break;
      case "onClick":
        l != null && (e.onclick = sh);
        break;
      case "suppressContentEditableWarning":
      case "suppressHydrationWarning":
      case "innerHTML":
      case "ref":
        break;
      case "innerText":
      case "textContent":
        break;
      default:
        if (!Yv.hasOwnProperty(o))
          t: {
            if (o[0] === "o" && o[1] === "n" && (h = o.endsWith("Capture"), s = o.slice(2, h ? o.length - 7 : void 0), d = e[We] || null, d = d != null ? d[o] : null, typeof d == "function" && e.removeEventListener(s, d, h), typeof l == "function")) {
              typeof d != "function" && d !== null && (o in e ? e[o] = null : e.hasAttribute(o) && e.removeAttribute(o)), e.addEventListener(s, l, h);
              break t;
            }
            o in e ? e[o] = l : l === !0 ? e.setAttribute(o, "") : lf(e, o, l);
          }
    }
  }
  function ke(e, s, o) {
    switch (s) {
      case "div":
      case "span":
      case "svg":
      case "path":
      case "a":
      case "g":
      case "p":
      case "li":
        break;
      case "img":
        At("error", e), At("load", e);
        var l = !1, h = !1, d;
        for (d in o)
          if (o.hasOwnProperty(d)) {
            var x = o[d];
            if (x != null)
              switch (d) {
                case "src":
                  l = !0;
                  break;
                case "srcSet":
                  h = !0;
                  break;
                case "children":
                case "dangerouslySetInnerHTML":
                  throw Error(a(137, s));
                default:
                  qt(e, s, d, x, o, null);
              }
          }
        h && qt(e, s, "srcSet", o.srcSet, o, null), l && qt(e, s, "src", o.src, o, null);
        return;
      case "input":
        At("invalid", e);
        var M = d = x = h = null, E = null, _ = null;
        for (l in o)
          if (o.hasOwnProperty(l)) {
            var F = o[l];
            if (F != null)
              switch (l) {
                case "name":
                  h = F;
                  break;
                case "type":
                  x = F;
                  break;
                case "checked":
                  E = F;
                  break;
                case "defaultChecked":
                  _ = F;
                  break;
                case "value":
                  d = F;
                  break;
                case "defaultValue":
                  M = F;
                  break;
                case "children":
                case "dangerouslySetInnerHTML":
                  if (F != null)
                    throw Error(a(137, s));
                  break;
                default:
                  qt(e, s, l, F, o, null);
              }
          }
        $v(
          e,
          d,
          M,
          E,
          _,
          x,
          h,
          !1
        ), cf(e);
        return;
      case "select":
        At("invalid", e), l = x = d = null;
        for (h in o)
          if (o.hasOwnProperty(h) && (M = o[h], M != null))
            switch (h) {
              case "value":
                d = M;
                break;
              case "defaultValue":
                x = M;
                break;
              case "multiple":
                l = M;
              default:
                qt(e, s, h, M, o, null);
            }
        s = d, o = x, e.multiple = !!l, s != null ? Yo(e, !!l, s, !1) : o != null && Yo(e, !!l, o, !0);
        return;
      case "textarea":
        At("invalid", e), d = h = l = null;
        for (x in o)
          if (o.hasOwnProperty(x) && (M = o[x], M != null))
            switch (x) {
              case "value":
                l = M;
                break;
              case "defaultValue":
                h = M;
                break;
              case "children":
                d = M;
                break;
              case "dangerouslySetInnerHTML":
                if (M != null) throw Error(a(91));
                break;
              default:
                qt(e, s, x, M, o, null);
            }
        Jv(e, l, h, d), cf(e);
        return;
      case "option":
        for (E in o)
          if (o.hasOwnProperty(E) && (l = o[E], l != null))
            switch (E) {
              case "selected":
                e.selected = l && typeof l != "function" && typeof l != "symbol";
                break;
              default:
                qt(e, s, E, l, o, null);
            }
        return;
      case "dialog":
        At("beforetoggle", e), At("toggle", e), At("cancel", e), At("close", e);
        break;
      case "iframe":
      case "object":
        At("load", e);
        break;
      case "video":
      case "audio":
        for (l = 0; l < Tu.length; l++)
          At(Tu[l], e);
        break;
      case "image":
        At("error", e), At("load", e);
        break;
      case "details":
        At("toggle", e);
        break;
      case "embed":
      case "source":
      case "link":
        At("error", e), At("load", e);
      case "area":
      case "base":
      case "br":
      case "col":
      case "hr":
      case "keygen":
      case "meta":
      case "param":
      case "track":
      case "wbr":
      case "menuitem":
        for (_ in o)
          if (o.hasOwnProperty(_) && (l = o[_], l != null))
            switch (_) {
              case "children":
              case "dangerouslySetInnerHTML":
                throw Error(a(137, s));
              default:
                qt(e, s, _, l, o, null);
            }
        return;
      default:
        if (Qd(s)) {
          for (F in o)
            o.hasOwnProperty(F) && (l = o[F], l !== void 0 && kp(
              e,
              s,
              F,
              l,
              o,
              void 0
            ));
          return;
        }
    }
    for (M in o)
      o.hasOwnProperty(M) && (l = o[M], l != null && qt(e, s, M, l, o, null));
  }
  function WD(e, s, o, l) {
    switch (s) {
      case "div":
      case "span":
      case "svg":
      case "path":
      case "a":
      case "g":
      case "p":
      case "li":
        break;
      case "input":
        var h = null, d = null, x = null, M = null, E = null, _ = null, F = null;
        for (U in o) {
          var I = o[U];
          if (o.hasOwnProperty(U) && I != null)
            switch (U) {
              case "checked":
                break;
              case "value":
                break;
              case "defaultValue":
                E = I;
              default:
                l.hasOwnProperty(U) || qt(e, s, U, null, l, I);
            }
        }
        for (var N in l) {
          var U = l[N];
          if (I = o[N], l.hasOwnProperty(N) && (U != null || I != null))
            switch (N) {
              case "type":
                d = U;
                break;
              case "name":
                h = U;
                break;
              case "checked":
                _ = U;
                break;
              case "defaultChecked":
                F = U;
                break;
              case "value":
                x = U;
                break;
              case "defaultValue":
                M = U;
                break;
              case "children":
              case "dangerouslySetInnerHTML":
                if (U != null)
                  throw Error(a(137, s));
                break;
              default:
                U !== I && qt(
                  e,
                  s,
                  N,
                  U,
                  l,
                  I
                );
            }
        }
        Fd(
          e,
          x,
          M,
          E,
          _,
          F,
          d,
          h
        );
        return;
      case "select":
        U = x = M = N = null;
        for (d in o)
          if (E = o[d], o.hasOwnProperty(d) && E != null)
            switch (d) {
              case "value":
                break;
              case "multiple":
                U = E;
              default:
                l.hasOwnProperty(d) || qt(
                  e,
                  s,
                  d,
                  null,
                  l,
                  E
                );
            }
        for (h in l)
          if (d = l[h], E = o[h], l.hasOwnProperty(h) && (d != null || E != null))
            switch (h) {
              case "value":
                N = d;
                break;
              case "defaultValue":
                M = d;
                break;
              case "multiple":
                x = d;
              default:
                d !== E && qt(
                  e,
                  s,
                  h,
                  d,
                  l,
                  E
                );
            }
        s = M, o = x, l = U, N != null ? Yo(e, !!o, N, !1) : !!l != !!o && (s != null ? Yo(e, !!o, s, !0) : Yo(e, !!o, o ? [] : "", !1));
        return;
      case "textarea":
        U = N = null;
        for (M in o)
          if (h = o[M], o.hasOwnProperty(M) && h != null && !l.hasOwnProperty(M))
            switch (M) {
              case "value":
                break;
              case "children":
                break;
              default:
                qt(e, s, M, null, l, h);
            }
        for (x in l)
          if (h = l[x], d = o[x], l.hasOwnProperty(x) && (h != null || d != null))
            switch (x) {
              case "value":
                N = h;
                break;
              case "defaultValue":
                U = h;
                break;
              case "children":
                break;
              case "dangerouslySetInnerHTML":
                if (h != null) throw Error(a(91));
                break;
              default:
                h !== d && qt(e, s, x, h, l, d);
            }
        Wv(e, N, U);
        return;
      case "option":
        for (var pt in o)
          if (N = o[pt], o.hasOwnProperty(pt) && N != null && !l.hasOwnProperty(pt))
            switch (pt) {
              case "selected":
                e.selected = !1;
                break;
              default:
                qt(
                  e,
                  s,
                  pt,
                  null,
                  l,
                  N
                );
            }
        for (E in l)
          if (N = l[E], U = o[E], l.hasOwnProperty(E) && N !== U && (N != null || U != null))
            switch (E) {
              case "selected":
                e.selected = N && typeof N != "function" && typeof N != "symbol";
                break;
              default:
                qt(
                  e,
                  s,
                  E,
                  N,
                  l,
                  U
                );
            }
        return;
      case "img":
      case "link":
      case "area":
      case "base":
      case "br":
      case "col":
      case "embed":
      case "hr":
      case "keygen":
      case "meta":
      case "param":
      case "source":
      case "track":
      case "wbr":
      case "menuitem":
        for (var dt in o)
          N = o[dt], o.hasOwnProperty(dt) && N != null && !l.hasOwnProperty(dt) && qt(e, s, dt, null, l, N);
        for (_ in l)
          if (N = l[_], U = o[_], l.hasOwnProperty(_) && N !== U && (N != null || U != null))
            switch (_) {
              case "children":
              case "dangerouslySetInnerHTML":
                if (N != null)
                  throw Error(a(137, s));
                break;
              default:
                qt(
                  e,
                  s,
                  _,
                  N,
                  l,
                  U
                );
            }
        return;
      default:
        if (Qd(s)) {
          for (var Gt in o)
            N = o[Gt], o.hasOwnProperty(Gt) && N !== void 0 && !l.hasOwnProperty(Gt) && kp(
              e,
              s,
              Gt,
              void 0,
              l,
              N
            );
          for (F in l)
            N = l[F], U = o[F], !l.hasOwnProperty(F) || N === U || N === void 0 && U === void 0 || kp(
              e,
              s,
              F,
              N,
              l,
              U
            );
          return;
        }
    }
    for (var V in o)
      N = o[V], o.hasOwnProperty(V) && N != null && !l.hasOwnProperty(V) && qt(e, s, V, null, l, N);
    for (I in l)
      N = l[I], U = o[I], !l.hasOwnProperty(I) || N === U || N == null && U == null || qt(e, s, I, N, l, U);
  }
  var Vp = null, Pp = null;
  function ah(e) {
    return e.nodeType === 9 ? e : e.ownerDocument;
  }
  function tS(e) {
    switch (e) {
      case "http://www.w3.org/2000/svg":
        return 1;
      case "http://www.w3.org/1998/Math/MathML":
        return 2;
      default:
        return 0;
    }
  }
  function eS(e, s) {
    if (e === 0)
      switch (s) {
        case "svg":
          return 1;
        case "math":
          return 2;
        default:
          return 0;
      }
    return e === 1 && s === "foreignObject" ? 0 : e;
  }
  function Lp(e, s) {
    return e === "textarea" || e === "noscript" || typeof s.children == "string" || typeof s.children == "number" || typeof s.children == "bigint" || typeof s.dangerouslySetInnerHTML == "object" && s.dangerouslySetInnerHTML !== null && s.dangerouslySetInnerHTML.__html != null;
  }
  var _p = null;
  function JD() {
    var e = window.event;
    return e && e.type === "popstate" ? e === _p ? !1 : (_p = e, !0) : (_p = null, !1);
  }
  var nS = typeof setTimeout == "function" ? setTimeout : void 0, tR = typeof clearTimeout == "function" ? clearTimeout : void 0, iS = typeof Promise == "function" ? Promise : void 0, eR = typeof queueMicrotask == "function" ? queueMicrotask : typeof iS < "u" ? function(e) {
    return iS.resolve(null).then(e).catch(nR);
  } : nS;
  function nR(e) {
    setTimeout(function() {
      throw e;
    });
  }
  function vs(e) {
    return e === "head";
  }
  function sS(e, s) {
    var o = s, l = 0, h = 0;
    do {
      var d = o.nextSibling;
      if (e.removeChild(o), d && d.nodeType === 8)
        if (o = d.data, o === "/$") {
          if (0 < l && 8 > l) {
            o = l;
            var x = e.ownerDocument;
            if (o & 1 && Eu(x.documentElement), o & 2 && Eu(x.body), o & 4)
              for (o = x.head, Eu(o), x = o.firstChild; x; ) {
                var M = x.nextSibling, E = x.nodeName;
                x[Hl] || E === "SCRIPT" || E === "STYLE" || E === "LINK" && x.rel.toLowerCase() === "stylesheet" || o.removeChild(x), x = M;
              }
          }
          if (h === 0) {
            e.removeChild(d), Pu(s);
            return;
          }
          h--;
        } else
          o === "$" || o === "$?" || o === "$!" ? h++ : l = o.charCodeAt(0) - 48;
      else l = 0;
      o = d;
    } while (o);
    Pu(s);
  }
  function Bp(e) {
    var s = e.firstChild;
    for (s && s.nodeType === 10 && (s = s.nextSibling); s; ) {
      var o = s;
      switch (s = s.nextSibling, o.nodeName) {
        case "HTML":
        case "HEAD":
        case "BODY":
          Bp(o), qd(o);
          continue;
        case "SCRIPT":
        case "STYLE":
          continue;
        case "LINK":
          if (o.rel.toLowerCase() === "stylesheet") continue;
      }
      e.removeChild(o);
    }
  }
  function iR(e, s, o, l) {
    for (; e.nodeType === 1; ) {
      var h = o;
      if (e.nodeName.toLowerCase() !== s.toLowerCase()) {
        if (!l && (e.nodeName !== "INPUT" || e.type !== "hidden"))
          break;
      } else if (l) {
        if (!e[Hl])
          switch (s) {
            case "meta":
              if (!e.hasAttribute("itemprop")) break;
              return e;
            case "link":
              if (d = e.getAttribute("rel"), d === "stylesheet" && e.hasAttribute("data-precedence"))
                break;
              if (d !== h.rel || e.getAttribute("href") !== (h.href == null || h.href === "" ? null : h.href) || e.getAttribute("crossorigin") !== (h.crossOrigin == null ? null : h.crossOrigin) || e.getAttribute("title") !== (h.title == null ? null : h.title))
                break;
              return e;
            case "style":
              if (e.hasAttribute("data-precedence")) break;
              return e;
            case "script":
              if (d = e.getAttribute("src"), (d !== (h.src == null ? null : h.src) || e.getAttribute("type") !== (h.type == null ? null : h.type) || e.getAttribute("crossorigin") !== (h.crossOrigin == null ? null : h.crossOrigin)) && d && e.hasAttribute("async") && !e.hasAttribute("itemprop"))
                break;
              return e;
            default:
              return e;
          }
      } else if (s === "input" && e.type === "hidden") {
        var d = h.name == null ? null : "" + h.name;
        if (h.type === "hidden" && e.getAttribute("name") === d)
          return e;
      } else return e;
      if (e = Zn(e.nextSibling), e === null) break;
    }
    return null;
  }
  function sR(e, s, o) {
    if (s === "") return null;
    for (; e.nodeType !== 3; )
      if ((e.nodeType !== 1 || e.nodeName !== "INPUT" || e.type !== "hidden") && !o || (e = Zn(e.nextSibling), e === null)) return null;
    return e;
  }
  function Np(e) {
    return e.data === "$!" || e.data === "$?" && e.ownerDocument.readyState === "complete";
  }
  function aR(e, s) {
    var o = e.ownerDocument;
    if (e.data !== "$?" || o.readyState === "complete")
      s();
    else {
      var l = function() {
        s(), o.removeEventListener("DOMContentLoaded", l);
      };
      o.addEventListener("DOMContentLoaded", l), e._reactRetry = l;
    }
  }
  function Zn(e) {
    for (; e != null; e = e.nextSibling) {
      var s = e.nodeType;
      if (s === 1 || s === 3) break;
      if (s === 8) {
        if (s = e.data, s === "$" || s === "$!" || s === "$?" || s === "F!" || s === "F")
          break;
        if (s === "/$") return null;
      }
    }
    return e;
  }
  var Up = null;
  function aS(e) {
    e = e.previousSibling;
    for (var s = 0; e; ) {
      if (e.nodeType === 8) {
        var o = e.data;
        if (o === "$" || o === "$!" || o === "$?") {
          if (s === 0) return e;
          s--;
        } else o === "/$" && s++;
      }
      e = e.previousSibling;
    }
    return null;
  }
  function oS(e, s, o) {
    switch (s = ah(o), e) {
      case "html":
        if (e = s.documentElement, !e) throw Error(a(452));
        return e;
      case "head":
        if (e = s.head, !e) throw Error(a(453));
        return e;
      case "body":
        if (e = s.body, !e) throw Error(a(454));
        return e;
      default:
        throw Error(a(451));
    }
  }
  function Eu(e) {
    for (var s = e.attributes; s.length; )
      e.removeAttributeNode(s[0]);
    qd(e);
  }
  var Rn = /* @__PURE__ */ new Map(), rS = /* @__PURE__ */ new Set();
  function oh(e) {
    return typeof e.getRootNode == "function" ? e.getRootNode() : e.nodeType === 9 ? e : e.ownerDocument;
  }
  var Qi = W.d;
  W.d = {
    f: oR,
    r: rR,
    D: lR,
    C: uR,
    L: cR,
    m: fR,
    X: dR,
    S: hR,
    M: mR
  };
  function oR() {
    var e = Qi.f(), s = $f();
    return e || s;
  }
  function rR(e) {
    var s = jo(e);
    s !== null && s.tag === 5 && s.type === "form" ? A0(s) : Qi.r(e);
  }
  var xr = typeof document > "u" ? null : document;
  function lS(e, s, o) {
    var l = xr;
    if (l && typeof s == "string" && s) {
      var h = wn(s);
      h = 'link[rel="' + e + '"][href="' + h + '"]', typeof o == "string" && (h += '[crossorigin="' + o + '"]'), rS.has(h) || (rS.add(h), e = { rel: e, crossOrigin: o, href: s }, l.querySelector(h) === null && (s = l.createElement("link"), ke(s, "link", e), Me(s), l.head.appendChild(s)));
    }
  }
  function lR(e) {
    Qi.D(e), lS("dns-prefetch", e, null);
  }
  function uR(e, s) {
    Qi.C(e, s), lS("preconnect", e, s);
  }
  function cR(e, s, o) {
    Qi.L(e, s, o);
    var l = xr;
    if (l && e && s) {
      var h = 'link[rel="preload"][as="' + wn(s) + '"]';
      s === "image" && o && o.imageSrcSet ? (h += '[imagesrcset="' + wn(
        o.imageSrcSet
      ) + '"]', typeof o.imageSizes == "string" && (h += '[imagesizes="' + wn(
        o.imageSizes
      ) + '"]')) : h += '[href="' + wn(e) + '"]';
      var d = h;
      switch (s) {
        case "style":
          d = Sr(e);
          break;
        case "script":
          d = wr(e);
      }
      Rn.has(d) || (e = g(
        {
          rel: "preload",
          href: s === "image" && o && o.imageSrcSet ? void 0 : e,
          as: s
        },
        o
      ), Rn.set(d, e), l.querySelector(h) !== null || s === "style" && l.querySelector(Au(d)) || s === "script" && l.querySelector(Du(d)) || (s = l.createElement("link"), ke(s, "link", e), Me(s), l.head.appendChild(s)));
    }
  }
  function fR(e, s) {
    Qi.m(e, s);
    var o = xr;
    if (o && e) {
      var l = s && typeof s.as == "string" ? s.as : "script", h = 'link[rel="modulepreload"][as="' + wn(l) + '"][href="' + wn(e) + '"]', d = h;
      switch (l) {
        case "audioworklet":
        case "paintworklet":
        case "serviceworker":
        case "sharedworker":
        case "worker":
        case "script":
          d = wr(e);
      }
      if (!Rn.has(d) && (e = g({ rel: "modulepreload", href: e }, s), Rn.set(d, e), o.querySelector(h) === null)) {
        switch (l) {
          case "audioworklet":
          case "paintworklet":
          case "serviceworker":
          case "sharedworker":
          case "worker":
          case "script":
            if (o.querySelector(Du(d)))
              return;
        }
        l = o.createElement("link"), ke(l, "link", e), Me(l), o.head.appendChild(l);
      }
    }
  }
  function hR(e, s, o) {
    Qi.S(e, s, o);
    var l = xr;
    if (l && e) {
      var h = Ho(l).hoistableStyles, d = Sr(e);
      s = s || "default";
      var x = h.get(d);
      if (!x) {
        var M = { loading: 0, preload: null };
        if (x = l.querySelector(
          Au(d)
        ))
          M.loading = 5;
        else {
          e = g(
            { rel: "stylesheet", href: e, "data-precedence": s },
            o
          ), (o = Rn.get(d)) && jp(e, o);
          var E = x = l.createElement("link");
          Me(E), ke(E, "link", e), E._p = new Promise(function(_, F) {
            E.onload = _, E.onerror = F;
          }), E.addEventListener("load", function() {
            M.loading |= 1;
          }), E.addEventListener("error", function() {
            M.loading |= 2;
          }), M.loading |= 4, rh(x, s, l);
        }
        x = {
          type: "stylesheet",
          instance: x,
          count: 1,
          state: M
        }, h.set(d, x);
      }
    }
  }
  function dR(e, s) {
    Qi.X(e, s);
    var o = xr;
    if (o && e) {
      var l = Ho(o).hoistableScripts, h = wr(e), d = l.get(h);
      d || (d = o.querySelector(Du(h)), d || (e = g({ src: e, async: !0 }, s), (s = Rn.get(h)) && Hp(e, s), d = o.createElement("script"), Me(d), ke(d, "link", e), o.head.appendChild(d)), d = {
        type: "script",
        instance: d,
        count: 1,
        state: null
      }, l.set(h, d));
    }
  }
  function mR(e, s) {
    Qi.M(e, s);
    var o = xr;
    if (o && e) {
      var l = Ho(o).hoistableScripts, h = wr(e), d = l.get(h);
      d || (d = o.querySelector(Du(h)), d || (e = g({ src: e, async: !0, type: "module" }, s), (s = Rn.get(h)) && Hp(e, s), d = o.createElement("script"), Me(d), ke(d, "link", e), o.head.appendChild(d)), d = {
        type: "script",
        instance: d,
        count: 1,
        state: null
      }, l.set(h, d));
    }
  }
  function uS(e, s, o, l) {
    var h = (h = yt.current) ? oh(h) : null;
    if (!h) throw Error(a(446));
    switch (e) {
      case "meta":
      case "title":
        return null;
      case "style":
        return typeof o.precedence == "string" && typeof o.href == "string" ? (s = Sr(o.href), o = Ho(
          h
        ).hoistableStyles, l = o.get(s), l || (l = {
          type: "style",
          instance: null,
          count: 0,
          state: null
        }, o.set(s, l)), l) : { type: "void", instance: null, count: 0, state: null };
      case "link":
        if (o.rel === "stylesheet" && typeof o.href == "string" && typeof o.precedence == "string") {
          e = Sr(o.href);
          var d = Ho(
            h
          ).hoistableStyles, x = d.get(e);
          if (x || (h = h.ownerDocument || h, x = {
            type: "stylesheet",
            instance: null,
            count: 0,
            state: { loading: 0, preload: null }
          }, d.set(e, x), (d = h.querySelector(
            Au(e)
          )) && !d._p && (x.instance = d, x.state.loading = 5), Rn.has(e) || (o = {
            rel: "preload",
            as: "style",
            href: o.href,
            crossOrigin: o.crossOrigin,
            integrity: o.integrity,
            media: o.media,
            hrefLang: o.hrefLang,
            referrerPolicy: o.referrerPolicy
          }, Rn.set(e, o), d || pR(
            h,
            e,
            o,
            x.state
          ))), s && l === null)
            throw Error(a(528, ""));
          return x;
        }
        if (s && l !== null)
          throw Error(a(529, ""));
        return null;
      case "script":
        return s = o.async, o = o.src, typeof o == "string" && s && typeof s != "function" && typeof s != "symbol" ? (s = wr(o), o = Ho(
          h
        ).hoistableScripts, l = o.get(s), l || (l = {
          type: "script",
          instance: null,
          count: 0,
          state: null
        }, o.set(s, l)), l) : { type: "void", instance: null, count: 0, state: null };
      default:
        throw Error(a(444, e));
    }
  }
  function Sr(e) {
    return 'href="' + wn(e) + '"';
  }
  function Au(e) {
    return 'link[rel="stylesheet"][' + e + "]";
  }
  function cS(e) {
    return g({}, e, {
      "data-precedence": e.precedence,
      precedence: null
    });
  }
  function pR(e, s, o, l) {
    e.querySelector('link[rel="preload"][as="style"][' + s + "]") ? l.loading = 1 : (s = e.createElement("link"), l.preload = s, s.addEventListener("load", function() {
      return l.loading |= 1;
    }), s.addEventListener("error", function() {
      return l.loading |= 2;
    }), ke(s, "link", o), Me(s), e.head.appendChild(s));
  }
  function wr(e) {
    return '[src="' + wn(e) + '"]';
  }
  function Du(e) {
    return "script[async]" + e;
  }
  function fS(e, s, o) {
    if (s.count++, s.instance === null)
      switch (s.type) {
        case "style":
          var l = e.querySelector(
            'style[data-href~="' + wn(o.href) + '"]'
          );
          if (l)
            return s.instance = l, Me(l), l;
          var h = g({}, o, {
            "data-href": o.href,
            "data-precedence": o.precedence,
            href: null,
            precedence: null
          });
          return l = (e.ownerDocument || e).createElement(
            "style"
          ), Me(l), ke(l, "style", h), rh(l, o.precedence, e), s.instance = l;
        case "stylesheet":
          h = Sr(o.href);
          var d = e.querySelector(
            Au(h)
          );
          if (d)
            return s.state.loading |= 4, s.instance = d, Me(d), d;
          l = cS(o), (h = Rn.get(h)) && jp(l, h), d = (e.ownerDocument || e).createElement("link"), Me(d);
          var x = d;
          return x._p = new Promise(function(M, E) {
            x.onload = M, x.onerror = E;
          }), ke(d, "link", l), s.state.loading |= 4, rh(d, o.precedence, e), s.instance = d;
        case "script":
          return d = wr(o.src), (h = e.querySelector(
            Du(d)
          )) ? (s.instance = h, Me(h), h) : (l = o, (h = Rn.get(d)) && (l = g({}, o), Hp(l, h)), e = e.ownerDocument || e, h = e.createElement("script"), Me(h), ke(h, "link", l), e.head.appendChild(h), s.instance = h);
        case "void":
          return null;
        default:
          throw Error(a(443, s.type));
      }
    else
      s.type === "stylesheet" && (s.state.loading & 4) === 0 && (l = s.instance, s.state.loading |= 4, rh(l, o.precedence, e));
    return s.instance;
  }
  function rh(e, s, o) {
    for (var l = o.querySelectorAll(
      'link[rel="stylesheet"][data-precedence],style[data-precedence]'
    ), h = l.length ? l[l.length - 1] : null, d = h, x = 0; x < l.length; x++) {
      var M = l[x];
      if (M.dataset.precedence === s) d = M;
      else if (d !== h) break;
    }
    d ? d.parentNode.insertBefore(e, d.nextSibling) : (s = o.nodeType === 9 ? o.head : o, s.insertBefore(e, s.firstChild));
  }
  function jp(e, s) {
    e.crossOrigin == null && (e.crossOrigin = s.crossOrigin), e.referrerPolicy == null && (e.referrerPolicy = s.referrerPolicy), e.title == null && (e.title = s.title);
  }
  function Hp(e, s) {
    e.crossOrigin == null && (e.crossOrigin = s.crossOrigin), e.referrerPolicy == null && (e.referrerPolicy = s.referrerPolicy), e.integrity == null && (e.integrity = s.integrity);
  }
  var lh = null;
  function hS(e, s, o) {
    if (lh === null) {
      var l = /* @__PURE__ */ new Map(), h = lh = /* @__PURE__ */ new Map();
      h.set(o, l);
    } else
      h = lh, l = h.get(o), l || (l = /* @__PURE__ */ new Map(), h.set(o, l));
    if (l.has(e)) return l;
    for (l.set(e, null), o = o.getElementsByTagName(e), h = 0; h < o.length; h++) {
      var d = o[h];
      if (!(d[Hl] || d[Le] || e === "link" && d.getAttribute("rel") === "stylesheet") && d.namespaceURI !== "http://www.w3.org/2000/svg") {
        var x = d.getAttribute(s) || "";
        x = e + x;
        var M = l.get(x);
        M ? M.push(d) : l.set(x, [d]);
      }
    }
    return l;
  }
  function dS(e, s, o) {
    e = e.ownerDocument || e, e.head.insertBefore(
      o,
      s === "title" ? e.querySelector("head > title") : null
    );
  }
  function gR(e, s, o) {
    if (o === 1 || s.itemProp != null) return !1;
    switch (e) {
      case "meta":
      case "title":
        return !0;
      case "style":
        if (typeof s.precedence != "string" || typeof s.href != "string" || s.href === "")
          break;
        return !0;
      case "link":
        if (typeof s.rel != "string" || typeof s.href != "string" || s.href === "" || s.onLoad || s.onError)
          break;
        switch (s.rel) {
          case "stylesheet":
            return e = s.disabled, typeof s.precedence == "string" && e == null;
          default:
            return !0;
        }
      case "script":
        if (s.async && typeof s.async != "function" && typeof s.async != "symbol" && !s.onLoad && !s.onError && s.src && typeof s.src == "string")
          return !0;
    }
    return !1;
  }
  function mS(e) {
    return !(e.type === "stylesheet" && (e.state.loading & 3) === 0);
  }
  var Ru = null;
  function yR() {
  }
  function vR(e, s, o) {
    if (Ru === null) throw Error(a(475));
    var l = Ru;
    if (s.type === "stylesheet" && (typeof o.media != "string" || matchMedia(o.media).matches !== !1) && (s.state.loading & 4) === 0) {
      if (s.instance === null) {
        var h = Sr(o.href), d = e.querySelector(
          Au(h)
        );
        if (d) {
          e = d._p, e !== null && typeof e == "object" && typeof e.then == "function" && (l.count++, l = uh.bind(l), e.then(l, l)), s.state.loading |= 4, s.instance = d, Me(d);
          return;
        }
        d = e.ownerDocument || e, o = cS(o), (h = Rn.get(h)) && jp(o, h), d = d.createElement("link"), Me(d);
        var x = d;
        x._p = new Promise(function(M, E) {
          x.onload = M, x.onerror = E;
        }), ke(d, "link", o), s.instance = d;
      }
      l.stylesheets === null && (l.stylesheets = /* @__PURE__ */ new Map()), l.stylesheets.set(s, e), (e = s.state.preload) && (s.state.loading & 3) === 0 && (l.count++, s = uh.bind(l), e.addEventListener("load", s), e.addEventListener("error", s));
    }
  }
  function bR() {
    if (Ru === null) throw Error(a(475));
    var e = Ru;
    return e.stylesheets && e.count === 0 && qp(e, e.stylesheets), 0 < e.count ? function(s) {
      var o = setTimeout(function() {
        if (e.stylesheets && qp(e, e.stylesheets), e.unsuspend) {
          var l = e.unsuspend;
          e.unsuspend = null, l();
        }
      }, 6e4);
      return e.unsuspend = s, function() {
        e.unsuspend = null, clearTimeout(o);
      };
    } : null;
  }
  function uh() {
    if (this.count--, this.count === 0) {
      if (this.stylesheets) qp(this, this.stylesheets);
      else if (this.unsuspend) {
        var e = this.unsuspend;
        this.unsuspend = null, e();
      }
    }
  }
  var ch = null;
  function qp(e, s) {
    e.stylesheets = null, e.unsuspend !== null && (e.count++, ch = /* @__PURE__ */ new Map(), s.forEach(xR, e), ch = null, uh.call(e));
  }
  function xR(e, s) {
    if (!(s.state.loading & 4)) {
      var o = ch.get(e);
      if (o) var l = o.get(null);
      else {
        o = /* @__PURE__ */ new Map(), ch.set(e, o);
        for (var h = e.querySelectorAll(
          "link[data-precedence],style[data-precedence]"
        ), d = 0; d < h.length; d++) {
          var x = h[d];
          (x.nodeName === "LINK" || x.getAttribute("media") !== "not all") && (o.set(x.dataset.precedence, x), l = x);
        }
        l && o.set(null, l);
      }
      h = s.instance, x = h.getAttribute("data-precedence"), d = o.get(x) || l, d === l && o.set(null, h), o.set(x, h), this.count++, l = uh.bind(this), h.addEventListener("load", l), h.addEventListener("error", l), d ? d.parentNode.insertBefore(h, d.nextSibling) : (e = e.nodeType === 9 ? e.head : e, e.insertBefore(h, e.firstChild)), s.state.loading |= 4;
    }
  }
  var Ou = {
    $$typeof: H,
    Provider: null,
    Consumer: null,
    _currentValue: J,
    _currentValue2: J,
    _threadCount: 0
  };
  function SR(e, s, o, l, h, d, x, M) {
    this.tag = 1, this.containerInfo = e, this.pingCache = this.current = this.pendingChildren = null, this.timeoutHandle = -1, this.callbackNode = this.next = this.pendingContext = this.context = this.cancelPendingCommit = null, this.callbackPriority = 0, this.expirationTimes = Nd(-1), this.entangledLanes = this.shellSuspendCounter = this.errorRecoveryDisabledLanes = this.expiredLanes = this.warmLanes = this.pingedLanes = this.suspendedLanes = this.pendingLanes = 0, this.entanglements = Nd(0), this.hiddenUpdates = Nd(null), this.identifierPrefix = l, this.onUncaughtError = h, this.onCaughtError = d, this.onRecoverableError = x, this.pooledCache = null, this.pooledCacheLanes = 0, this.formState = M, this.incompleteTransitions = /* @__PURE__ */ new Map();
  }
  function pS(e, s, o, l, h, d, x, M, E, _, F, I) {
    return e = new SR(
      e,
      s,
      o,
      x,
      M,
      E,
      _,
      I
    ), s = 1, d === !0 && (s |= 24), d = fn(3, null, null, s), e.current = d, d.stateNode = e, s = Mm(), s.refCount++, e.pooledCache = s, s.refCount++, d.memoizedState = {
      element: l,
      isDehydrated: o,
      cache: s
    }, Am(d), e;
  }
  function gS(e) {
    return e ? (e = Jo, e) : Jo;
  }
  function yS(e, s, o, l, h, d) {
    h = gS(h), l.context === null ? l.context = h : l.pendingContext = h, l = as(s), l.payload = { element: o }, d = d === void 0 ? null : d, d !== null && (l.callback = d), o = os(e, l, s), o !== null && (gn(o, e, s), ou(o, e, s));
  }
  function vS(e, s) {
    if (e = e.memoizedState, e !== null && e.dehydrated !== null) {
      var o = e.retryLane;
      e.retryLane = o !== 0 && o < s ? o : s;
    }
  }
  function Gp(e, s) {
    vS(e, s), (e = e.alternate) && vS(e, s);
  }
  function bS(e) {
    if (e.tag === 13) {
      var s = Wo(e, 67108864);
      s !== null && gn(s, e, 67108864), Gp(e, 67108864);
    }
  }
  var fh = !0;
  function wR(e, s, o, l) {
    var h = j.T;
    j.T = null;
    var d = W.p;
    try {
      W.p = 2, Yp(e, s, o, l);
    } finally {
      W.p = d, j.T = h;
    }
  }
  function MR(e, s, o, l) {
    var h = j.T;
    j.T = null;
    var d = W.p;
    try {
      W.p = 8, Yp(e, s, o, l);
    } finally {
      W.p = d, j.T = h;
    }
  }
  function Yp(e, s, o, l) {
    if (fh) {
      var h = Xp(l);
      if (h === null)
        zp(
          e,
          s,
          l,
          hh,
          o
        ), SS(e, l);
      else if (CR(
        h,
        e,
        s,
        o,
        l
      ))
        l.stopPropagation();
      else if (SS(e, l), s & 4 && -1 < TR.indexOf(e)) {
        for (; h !== null; ) {
          var d = jo(h);
          if (d !== null)
            switch (d.tag) {
              case 3:
                if (d = d.stateNode, d.current.memoizedState.isDehydrated) {
                  var x = ha(d.pendingLanes);
                  if (x !== 0) {
                    var M = d;
                    for (M.pendingLanes |= 2, M.entangledLanes |= 2; x; ) {
                      var E = 1 << 31 - un(x);
                      M.entanglements[1] |= E, x &= ~E;
                    }
                    ui(d), (Nt & 6) === 0 && (Kf = si() + 500, Mu(0));
                  }
                }
                break;
              case 13:
                M = Wo(d, 2), M !== null && gn(M, d, 2), $f(), Gp(d, 2);
            }
          if (d = Xp(l), d === null && zp(
            e,
            s,
            l,
            hh,
            o
          ), d === h) break;
          h = d;
        }
        h !== null && l.stopPropagation();
      } else
        zp(
          e,
          s,
          l,
          null,
          o
        );
    }
  }
  function Xp(e) {
    return e = Id(e), Fp(e);
  }
  var hh = null;
  function Fp(e) {
    if (hh = null, e = Uo(e), e !== null) {
      var s = u(e);
      if (s === null) e = null;
      else {
        var o = s.tag;
        if (o === 13) {
          if (e = c(s), e !== null) return e;
          e = null;
        } else if (o === 3) {
          if (s.stateNode.current.memoizedState.isDehydrated)
            return s.tag === 3 ? s.stateNode.containerInfo : null;
          e = null;
        } else s !== e && (e = null);
      }
    }
    return hh = e, null;
  }
  function xS(e) {
    switch (e) {
      case "beforetoggle":
      case "cancel":
      case "click":
      case "close":
      case "contextmenu":
      case "copy":
      case "cut":
      case "auxclick":
      case "dblclick":
      case "dragend":
      case "dragstart":
      case "drop":
      case "focusin":
      case "focusout":
      case "input":
      case "invalid":
      case "keydown":
      case "keypress":
      case "keyup":
      case "mousedown":
      case "mouseup":
      case "paste":
      case "pause":
      case "play":
      case "pointercancel":
      case "pointerdown":
      case "pointerup":
      case "ratechange":
      case "reset":
      case "resize":
      case "seeked":
      case "submit":
      case "toggle":
      case "touchcancel":
      case "touchend":
      case "touchstart":
      case "volumechange":
      case "change":
      case "selectionchange":
      case "textInput":
      case "compositionstart":
      case "compositionend":
      case "compositionupdate":
      case "beforeblur":
      case "afterblur":
      case "beforeinput":
      case "blur":
      case "fullscreenchange":
      case "focus":
      case "hashchange":
      case "popstate":
      case "select":
      case "selectstart":
        return 2;
      case "drag":
      case "dragenter":
      case "dragexit":
      case "dragleave":
      case "dragover":
      case "mousemove":
      case "mouseout":
      case "mouseover":
      case "pointermove":
      case "pointerout":
      case "pointerover":
      case "scroll":
      case "touchmove":
      case "wheel":
      case "mouseenter":
      case "mouseleave":
      case "pointerenter":
      case "pointerleave":
        return 8;
      case "message":
        switch (uA()) {
          case Pv:
            return 2;
          case Lv:
            return 8;
          case sf:
          case cA:
            return 32;
          case _v:
            return 268435456;
          default:
            return 32;
        }
      default:
        return 32;
    }
  }
  var Zp = !1, bs = null, xs = null, Ss = null, zu = /* @__PURE__ */ new Map(), ku = /* @__PURE__ */ new Map(), ws = [], TR = "mousedown mouseup touchcancel touchend touchstart auxclick dblclick pointercancel pointerdown pointerup dragend dragstart drop compositionend compositionstart keydown keypress keyup input textInput copy cut paste click change contextmenu reset".split(
    " "
  );
  function SS(e, s) {
    switch (e) {
      case "focusin":
      case "focusout":
        bs = null;
        break;
      case "dragenter":
      case "dragleave":
        xs = null;
        break;
      case "mouseover":
      case "mouseout":
        Ss = null;
        break;
      case "pointerover":
      case "pointerout":
        zu.delete(s.pointerId);
        break;
      case "gotpointercapture":
      case "lostpointercapture":
        ku.delete(s.pointerId);
    }
  }
  function Vu(e, s, o, l, h, d) {
    return e === null || e.nativeEvent !== d ? (e = {
      blockedOn: s,
      domEventName: o,
      eventSystemFlags: l,
      nativeEvent: d,
      targetContainers: [h]
    }, s !== null && (s = jo(s), s !== null && bS(s)), e) : (e.eventSystemFlags |= l, s = e.targetContainers, h !== null && s.indexOf(h) === -1 && s.push(h), e);
  }
  function CR(e, s, o, l, h) {
    switch (s) {
      case "focusin":
        return bs = Vu(
          bs,
          e,
          s,
          o,
          l,
          h
        ), !0;
      case "dragenter":
        return xs = Vu(
          xs,
          e,
          s,
          o,
          l,
          h
        ), !0;
      case "mouseover":
        return Ss = Vu(
          Ss,
          e,
          s,
          o,
          l,
          h
        ), !0;
      case "pointerover":
        var d = h.pointerId;
        return zu.set(
          d,
          Vu(
            zu.get(d) || null,
            e,
            s,
            o,
            l,
            h
          )
        ), !0;
      case "gotpointercapture":
        return d = h.pointerId, ku.set(
          d,
          Vu(
            ku.get(d) || null,
            e,
            s,
            o,
            l,
            h
          )
        ), !0;
    }
    return !1;
  }
  function wS(e) {
    var s = Uo(e.target);
    if (s !== null) {
      var o = u(s);
      if (o !== null) {
        if (s = o.tag, s === 13) {
          if (s = c(o), s !== null) {
            e.blockedOn = s, vA(e.priority, function() {
              if (o.tag === 13) {
                var l = pn();
                l = Ud(l);
                var h = Wo(o, l);
                h !== null && gn(h, o, l), Gp(o, l);
              }
            });
            return;
          }
        } else if (s === 3 && o.stateNode.current.memoizedState.isDehydrated) {
          e.blockedOn = o.tag === 3 ? o.stateNode.containerInfo : null;
          return;
        }
      }
    }
    e.blockedOn = null;
  }
  function dh(e) {
    if (e.blockedOn !== null) return !1;
    for (var s = e.targetContainers; 0 < s.length; ) {
      var o = Xp(e.nativeEvent);
      if (o === null) {
        o = e.nativeEvent;
        var l = new o.constructor(
          o.type,
          o
        );
        Kd = l, o.target.dispatchEvent(l), Kd = null;
      } else
        return s = jo(o), s !== null && bS(s), e.blockedOn = o, !1;
      s.shift();
    }
    return !0;
  }
  function MS(e, s, o) {
    dh(e) && o.delete(s);
  }
  function ER() {
    Zp = !1, bs !== null && dh(bs) && (bs = null), xs !== null && dh(xs) && (xs = null), Ss !== null && dh(Ss) && (Ss = null), zu.forEach(MS), ku.forEach(MS);
  }
  function mh(e, s) {
    e.blockedOn === s && (e.blockedOn = null, Zp || (Zp = !0, n.unstable_scheduleCallback(
      n.unstable_NormalPriority,
      ER
    )));
  }
  var ph = null;
  function TS(e) {
    ph !== e && (ph = e, n.unstable_scheduleCallback(
      n.unstable_NormalPriority,
      function() {
        ph === e && (ph = null);
        for (var s = 0; s < e.length; s += 3) {
          var o = e[s], l = e[s + 1], h = e[s + 2];
          if (typeof l != "function") {
            if (Fp(l || o) === null)
              continue;
            break;
          }
          var d = jo(o);
          d !== null && (e.splice(s, 3), s -= 3, Fm(
            d,
            {
              pending: !0,
              data: h,
              method: o.method,
              action: l
            },
            l,
            h
          ));
        }
      }
    ));
  }
  function Pu(e) {
    function s(E) {
      return mh(E, e);
    }
    bs !== null && mh(bs, e), xs !== null && mh(xs, e), Ss !== null && mh(Ss, e), zu.forEach(s), ku.forEach(s);
    for (var o = 0; o < ws.length; o++) {
      var l = ws[o];
      l.blockedOn === e && (l.blockedOn = null);
    }
    for (; 0 < ws.length && (o = ws[0], o.blockedOn === null); )
      wS(o), o.blockedOn === null && ws.shift();
    if (o = (e.ownerDocument || e).$$reactFormReplay, o != null)
      for (l = 0; l < o.length; l += 3) {
        var h = o[l], d = o[l + 1], x = h[We] || null;
        if (typeof d == "function")
          x || TS(o);
        else if (x) {
          var M = null;
          if (d && d.hasAttribute("formAction")) {
            if (h = d, x = d[We] || null)
              M = x.formAction;
            else if (Fp(h) !== null) continue;
          } else M = x.action;
          typeof M == "function" ? o[l + 1] = M : (o.splice(l, 3), l -= 3), TS(o);
        }
      }
  }
  function Qp(e) {
    this._internalRoot = e;
  }
  gh.prototype.render = Qp.prototype.render = function(e) {
    var s = this._internalRoot;
    if (s === null) throw Error(a(409));
    var o = s.current, l = pn();
    yS(o, l, e, s, null, null);
  }, gh.prototype.unmount = Qp.prototype.unmount = function() {
    var e = this._internalRoot;
    if (e !== null) {
      this._internalRoot = null;
      var s = e.containerInfo;
      yS(e.current, 2, null, e, null, null), $f(), s[No] = null;
    }
  };
  function gh(e) {
    this._internalRoot = e;
  }
  gh.prototype.unstable_scheduleHydration = function(e) {
    if (e) {
      var s = Hv();
      e = { blockedOn: null, target: e, priority: s };
      for (var o = 0; o < ws.length && s !== 0 && s < ws[o].priority; o++) ;
      ws.splice(o, 0, e), o === 0 && wS(e);
    }
  };
  var CS = t.version;
  if (CS !== "19.1.1")
    throw Error(
      a(
        527,
        CS,
        "19.1.1"
      )
    );
  W.findDOMNode = function(e) {
    var s = e._reactInternals;
    if (s === void 0)
      throw typeof e.render == "function" ? Error(a(188)) : (e = Object.keys(e).join(","), Error(a(268, e)));
    return e = m(s), e = e !== null ? p(e) : null, e = e === null ? null : e.stateNode, e;
  };
  var AR = {
    bundleType: 0,
    version: "19.1.1",
    rendererPackageName: "react-dom",
    currentDispatcherRef: j,
    reconcilerVersion: "19.1.1"
  };
  if (typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ < "u") {
    var yh = __REACT_DEVTOOLS_GLOBAL_HOOK__;
    if (!yh.isDisabled && yh.supportsFiber)
      try {
        Nl = yh.inject(
          AR
        ), ln = yh;
      } catch {
      }
  }
  return Nu.createRoot = function(e, s) {
    if (!r(e)) throw Error(a(299));
    var o = !1, l = "", h = H0, d = q0, x = G0, M = null;
    return s != null && (s.unstable_strictMode === !0 && (o = !0), s.identifierPrefix !== void 0 && (l = s.identifierPrefix), s.onUncaughtError !== void 0 && (h = s.onUncaughtError), s.onCaughtError !== void 0 && (d = s.onCaughtError), s.onRecoverableError !== void 0 && (x = s.onRecoverableError), s.unstable_transitionCallbacks !== void 0 && (M = s.unstable_transitionCallbacks)), s = pS(
      e,
      1,
      !1,
      null,
      null,
      o,
      l,
      h,
      d,
      x,
      M,
      null
    ), e[No] = s.current, Op(e), new Qp(s);
  }, Nu.hydrateRoot = function(e, s, o) {
    if (!r(e)) throw Error(a(299));
    var l = !1, h = "", d = H0, x = q0, M = G0, E = null, _ = null;
    return o != null && (o.unstable_strictMode === !0 && (l = !0), o.identifierPrefix !== void 0 && (h = o.identifierPrefix), o.onUncaughtError !== void 0 && (d = o.onUncaughtError), o.onCaughtError !== void 0 && (x = o.onCaughtError), o.onRecoverableError !== void 0 && (M = o.onRecoverableError), o.unstable_transitionCallbacks !== void 0 && (E = o.unstable_transitionCallbacks), o.formState !== void 0 && (_ = o.formState)), s = pS(
      e,
      1,
      !0,
      s,
      o ?? null,
      l,
      h,
      d,
      x,
      M,
      E,
      _
    ), s.context = gS(null), o = s.current, l = pn(), l = Ud(l), h = as(l), h.callback = null, os(o, h, l), o = l, s.current.lanes = o, jl(s, o), ui(s), e[No] = s.current, Op(e), new gh(s);
  }, Nu.version = "19.1.1", Nu;
}
var R1;
function MV() {
  if (R1) return mg.exports;
  R1 = 1;
  function n() {
    if (!(typeof __REACT_DEVTOOLS_GLOBAL_HOOK__ > "u" || typeof __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE != "function"))
      try {
        __REACT_DEVTOOLS_GLOBAL_HOOK__.checkDCE(n);
      } catch (t) {
        console.error(t);
      }
  }
  return n(), mg.exports = wV(), mg.exports;
}
var TV = MV();
const sv = G.createContext({});
function Kc(n) {
  const t = G.useRef(null);
  return t.current === null && (t.current = n()), t.current;
}
const CV = typeof window < "u", Ad = CV ? G.useLayoutEffect : G.useEffect, Dd = /* @__PURE__ */ G.createContext(null);
function av(n, t) {
  n.indexOf(t) === -1 && n.push(t);
}
function Jh(n, t) {
  const i = n.indexOf(t);
  i > -1 && n.splice(i, 1);
}
const Vi = (n, t, i) => i > t ? t : i < n ? n : i;
function O1(n, t) {
  return t ? `${n}. For more information and steps for solving, visit https://motion.dev/troubleshooting/${t}` : n;
}
let Ic = () => {
}, ua = () => {
};
var hM;
typeof process < "u" && ((hM = process.env) == null ? void 0 : hM.NODE_ENV) !== "production" && (Ic = (n, t, i) => {
  !n && typeof console < "u" && console.warn(O1(t, i));
}, ua = (n, t, i) => {
  if (!n)
    throw new Error(O1(t, i));
});
const ca = {}, CT = (n) => /^-?(?:\d+(?:\.\d+)?|\.\d+)$/u.test(n), ET = (n) => typeof n == "object" && n !== null, AT = (n) => /^0[^.\s]+$/u.test(n);
// @__NO_SIDE_EFFECTS__
function DT(n) {
  let t;
  return () => (t === void 0 && (t = n()), t);
}
const Bn = /* @__NO_SIDE_EFFECTS__ */ (n) => n, $c = (...n) => n.reduce((t, i) => (a) => i(t(a))), rc = /* @__NO_SIDE_EFFECTS__ */ (n, t, i) => {
  const a = t - n;
  return a ? (i - n) / a : 1;
};
class ov {
  constructor() {
    this.subscriptions = [];
  }
  add(t) {
    return av(this.subscriptions, t), () => Jh(this.subscriptions, t);
  }
  notify(t, i, a) {
    const r = this.subscriptions.length;
    if (r)
      if (r === 1)
        this.subscriptions[0](t, i, a);
      else
        for (let u = 0; u < r; u++) {
          const c = this.subscriptions[u];
          c && c(t, i, a);
        }
  }
  getSize() {
    return this.subscriptions.length;
  }
  clear() {
    this.subscriptions.length = 0;
  }
}
const rn = /* @__NO_SIDE_EFFECTS__ */ (n) => n * 1e3, Pn = /* @__NO_SIDE_EFFECTS__ */ (n) => n / 1e3, RT = /* @__NO_SIDE_EFFECTS__ */ (n, t) => t ? n * (1e3 / t) : 0, OT = (n, t, i) => (((1 - 3 * i + 3 * t) * n + (3 * i - 6 * t)) * n + 3 * t) * n, EV = 1e-7, AV = 12;
function DV(n, t, i, a, r) {
  let u, c, f = 0;
  do
    c = t + (i - t) / 2, u = OT(c, a, r) - n, u > 0 ? i = c : t = c;
  while (Math.abs(u) > EV && ++f < AV);
  return c;
}
// @__NO_SIDE_EFFECTS__
function Wc(n, t, i, a) {
  if (n === t && i === a)
    return Bn;
  const r = (u) => DV(u, 0, 1, n, i);
  return (u) => u === 0 || u === 1 ? u : OT(r(u), t, a);
}
const zT = /* @__NO_SIDE_EFFECTS__ */ (n) => (t) => t <= 0.5 ? n(2 * t) / 2 : (2 - n(2 * (1 - t))) / 2, kT = /* @__NO_SIDE_EFFECTS__ */ (n) => (t) => 1 - n(1 - t), VT = /* @__PURE__ */ Wc(0.33, 1.53, 0.69, 0.99), rv = /* @__PURE__ */ kT(VT), PT = /* @__PURE__ */ zT(rv), LT = (n) => n >= 1 ? 1 : (n *= 2) < 1 ? 0.5 * rv(n) : 0.5 * (2 - Math.pow(2, -10 * (n - 1))), lv = (n) => 1 - Math.sin(Math.acos(n)), _T = /* @__PURE__ */ kT(lv), BT = /* @__PURE__ */ zT(lv), RV = /* @__PURE__ */ Wc(0.42, 0, 1, 1), OV = /* @__PURE__ */ Wc(0, 0, 0.58, 1), NT = /* @__PURE__ */ Wc(0.42, 0, 0.58, 1), zV = /* @__NO_SIDE_EFFECTS__ */ (n) => Array.isArray(n) && typeof n[0] != "number", UT = /* @__NO_SIDE_EFFECTS__ */ (n) => Array.isArray(n) && typeof n[0] == "number", z1 = {
  linear: Bn,
  easeIn: RV,
  easeInOut: NT,
  easeOut: OV,
  circIn: lv,
  circInOut: BT,
  circOut: _T,
  backIn: rv,
  backInOut: PT,
  backOut: VT,
  anticipate: LT
}, kV = (n) => typeof n == "string", k1 = (n) => {
  if (/* @__PURE__ */ UT(n)) {
    ua(n.length === 4, "Cubic bezier arrays must contain four numerical values.", "cubic-bezier-length");
    const [t, i, a, r] = n;
    return /* @__PURE__ */ Wc(t, i, a, r);
  } else if (kV(n))
    return ua(z1[n] !== void 0, `Invalid easing type '${n}'`, "invalid-easing-type"), z1[n];
  return n;
}, Rh = [
  "setup",
  // Compute
  "read",
  // Read
  "resolveKeyframes",
  // Write/Read/Write/Read
  "preUpdate",
  // Compute
  "update",
  // Compute
  "preRender",
  // Compute
  "render",
  // Write
  "postRender"
  // Compute
];
function VV(n) {
  let t = /* @__PURE__ */ new Set(), i = /* @__PURE__ */ new Set(), a = !1, r = !1;
  const u = /* @__PURE__ */ new WeakSet();
  let c = {
    delta: 0,
    timestamp: 0,
    isProcessing: !1
  };
  function f(p) {
    u.has(p) && (m.schedule(p), n()), p(c);
  }
  const m = {
    /**
     * Schedule a process to run on the next frame.
     */
    schedule: (p, g = !1, y = !1) => {
      const S = y && a ? t : i;
      return g && u.add(p), S.add(p), p;
    },
    /**
     * Cancel the provided callback from running on the next frame.
     */
    cancel: (p) => {
      i.delete(p), u.delete(p);
    },
    /**
     * Execute all schedule callbacks.
     */
    process: (p) => {
      if (c = p, a) {
        r = !0;
        return;
      }
      a = !0;
      const g = t;
      t = i, i = g, t.forEach(f), t.clear(), a = !1, r && (r = !1, m.process(p));
    }
  };
  return m;
}
const PV = 40;
function jT(n, t) {
  let i = !1, a = !0;
  const r = {
    delta: 0,
    timestamp: 0,
    isProcessing: !1
  }, u = () => i = !0, c = Rh.reduce((H, X) => (H[X] = VV(u), H), {}), { setup: f, read: m, resolveKeyframes: p, preUpdate: g, update: y, preRender: b, render: S, postRender: T } = c, C = () => {
    const H = ca.useManualTiming, X = H ? r.timestamp : performance.now();
    i = !1, H || (r.delta = a ? 1e3 / 60 : Math.max(Math.min(X - r.timestamp, PV), 1)), r.timestamp = X, r.isProcessing = !0, f.process(r), m.process(r), p.process(r), g.process(r), y.process(r), b.process(r), S.process(r), T.process(r), r.isProcessing = !1, i && t && (a = !1, n(C));
  }, R = () => {
    i = !0, a = !0, r.isProcessing || n(C);
  };
  return { schedule: Rh.reduce((H, X) => {
    const Q = c[X];
    return H[X] = (ut, st = !1, $ = !1) => (i || R(), Q.schedule(ut, st, $)), H;
  }, {}), cancel: (H) => {
    for (let X = 0; X < Rh.length; X++)
      c[Rh[X]].cancel(H);
  }, state: r, steps: c };
}
const { schedule: jt, cancel: Wi, state: Ve, steps: vg } = /* @__PURE__ */ jT(typeof requestAnimationFrame < "u" ? requestAnimationFrame : Bn, !0);
let Hh;
function LV() {
  Hh = void 0;
}
const Ke = {
  now: () => (Hh === void 0 && Ke.set(Ve.isProcessing || ca.useManualTiming ? Ve.timestamp : performance.now()), Hh),
  set: (n) => {
    Hh = n, queueMicrotask(LV);
  }
}, HT = (n) => (t) => typeof t == "string" && t.startsWith(n), qT = /* @__PURE__ */ HT("--"), _V = /* @__PURE__ */ HT("var(--"), uv = (n) => _V(n) ? BV.test(n.split("/*")[0].trim()) : !1, BV = /var\(--(?:[\w-]+\s*|[\w-]+\s*,(?:\s*[^)(\s]|\s*\((?:[^)(]|\([^)(]*\))*\))+\s*)\)$/iu;
function V1(n) {
  return typeof n != "string" ? !1 : n.split("/*")[0].includes("var(--");
}
const Pl = {
  test: (n) => typeof n == "number",
  parse: parseFloat,
  transform: (n) => n
}, lc = {
  ...Pl,
  transform: (n) => Vi(0, 1, n)
}, Oh = {
  ...Pl,
  default: 1
}, Wu = (n) => Math.round(n * 1e5) / 1e5, cv = /-?(?:\d+(?:\.\d+)?|\.\d+)/gu;
function NV(n) {
  return n == null;
}
const UV = /^(?:#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\))$/iu, fv = (n, t) => (i) => !!(typeof i == "string" && UV.test(i) && i.startsWith(n) || t && !NV(i) && Object.prototype.hasOwnProperty.call(i, t)), GT = (n, t, i) => (a) => {
  if (typeof a != "string")
    return a;
  const [r, u, c, f] = a.match(cv);
  return {
    [n]: parseFloat(r),
    [t]: parseFloat(u),
    [i]: parseFloat(c),
    alpha: f !== void 0 ? parseFloat(f) : 1
  };
}, jV = (n) => Vi(0, 255, n), bg = {
  ...Pl,
  transform: (n) => Math.round(jV(n))
}, Ua = {
  test: /* @__PURE__ */ fv("rgb", "red"),
  parse: /* @__PURE__ */ GT("red", "green", "blue"),
  transform: ({ red: n, green: t, blue: i, alpha: a = 1 }) => "rgba(" + bg.transform(n) + ", " + bg.transform(t) + ", " + bg.transform(i) + ", " + Wu(lc.transform(a)) + ")"
};
function HV(n) {
  let t = "", i = "", a = "", r = "";
  return n.length > 5 ? (t = n.substring(1, 3), i = n.substring(3, 5), a = n.substring(5, 7), r = n.substring(7, 9)) : (t = n.substring(1, 2), i = n.substring(2, 3), a = n.substring(3, 4), r = n.substring(4, 5), t += t, i += i, a += a, r += r), {
    red: parseInt(t, 16),
    green: parseInt(i, 16),
    blue: parseInt(a, 16),
    alpha: r ? parseInt(r, 16) / 255 : 1
  };
}
const ey = {
  test: /* @__PURE__ */ fv("#"),
  parse: HV,
  transform: Ua.transform
}, Jc = /* @__NO_SIDE_EFFECTS__ */ (n) => ({
  test: (t) => typeof t == "string" && t.endsWith(n) && t.split(" ").length === 1,
  parse: parseFloat,
  transform: (t) => `${t}${n}`
}), Ii = /* @__PURE__ */ Jc("deg"), ki = /* @__PURE__ */ Jc("%"), ot = /* @__PURE__ */ Jc("px"), qV = /* @__PURE__ */ Jc("vh"), GV = /* @__PURE__ */ Jc("vw"), P1 = {
  ...ki,
  parse: (n) => ki.parse(n) / 100,
  transform: (n) => ki.transform(n * 100)
}, kr = {
  test: /* @__PURE__ */ fv("hsl", "hue"),
  parse: /* @__PURE__ */ GT("hue", "saturation", "lightness"),
  transform: ({ hue: n, saturation: t, lightness: i, alpha: a = 1 }) => "hsla(" + Math.round(n) + ", " + ki.transform(Wu(t)) + ", " + ki.transform(Wu(i)) + ", " + Wu(lc.transform(a)) + ")"
}, ve = {
  test: (n) => Ua.test(n) || ey.test(n) || kr.test(n),
  parse: (n) => Ua.test(n) ? Ua.parse(n) : kr.test(n) ? kr.parse(n) : ey.parse(n),
  transform: (n) => typeof n == "string" ? n : n.hasOwnProperty("red") ? Ua.transform(n) : kr.transform(n),
  getAnimatableNone: (n) => {
    const t = ve.parse(n);
    return t.alpha = 0, ve.transform(t);
  }
}, YV = /(?:#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\))/giu;
function XV(n) {
  var t, i;
  return isNaN(n) && typeof n == "string" && (((t = n.match(cv)) == null ? void 0 : t.length) || 0) + (((i = n.match(YV)) == null ? void 0 : i.length) || 0) > 0;
}
const YT = "number", XT = "color", FV = "var", ZV = "var(", L1 = "${}", QV = /var\s*\(\s*--(?:[\w-]+\s*|[\w-]+\s*,(?:\s*[^)(\s]|\s*\((?:[^)(]|\([^)(]*\))*\))+\s*)\)|#[\da-f]{3,8}|(?:rgb|hsl)a?\((?:-?[\d.]+%?[,\s]+){2}-?[\d.]+%?\s*(?:[,/]\s*)?(?:\b\d+(?:\.\d+)?|\.\d+)?%?\)|-?(?:\d+(?:\.\d+)?|\.\d+)/giu;
function zl(n) {
  const t = n.toString(), i = [], a = {
    color: [],
    number: [],
    var: []
  }, r = [];
  let u = 0;
  const f = t.replace(QV, (m) => (ve.test(m) ? (a.color.push(u), r.push(XT), i.push(ve.parse(m))) : m.startsWith(ZV) ? (a.var.push(u), r.push(FV), i.push(m)) : (a.number.push(u), r.push(YT), i.push(parseFloat(m))), ++u, L1)).split(L1);
  return { values: i, split: f, indexes: a, types: r };
}
function KV(n) {
  return zl(n).values;
}
function FT({ split: n, types: t }) {
  const i = n.length;
  return (a) => {
    let r = "";
    for (let u = 0; u < i; u++)
      if (r += n[u], a[u] !== void 0) {
        const c = t[u];
        c === YT ? r += Wu(a[u]) : c === XT ? r += ve.transform(a[u]) : r += a[u];
      }
    return r;
  };
}
function IV(n) {
  return FT(zl(n));
}
const $V = (n) => typeof n == "number" ? 0 : ve.test(n) ? ve.getAnimatableNone(n) : n, WV = (n, t) => typeof n == "number" ? t != null && t.trim().endsWith("/") ? n : 0 : $V(n);
function JV(n) {
  const t = zl(n);
  return FT(t)(t.values.map((a, r) => WV(a, t.split[r])));
}
const ei = {
  test: XV,
  parse: KV,
  createTransformer: IV,
  getAnimatableNone: JV
};
function xg(n, t, i) {
  return i < 0 && (i += 1), i > 1 && (i -= 1), i < 1 / 6 ? n + (t - n) * 6 * i : i < 1 / 2 ? t : i < 2 / 3 ? n + (t - n) * (2 / 3 - i) * 6 : n;
}
function tP({ hue: n, saturation: t, lightness: i, alpha: a }) {
  n /= 360, t /= 100, i /= 100;
  let r = 0, u = 0, c = 0;
  if (!t)
    r = u = c = i;
  else {
    const f = i < 0.5 ? i * (1 + t) : i + t - i * t, m = 2 * i - f;
    r = xg(m, f, n + 1 / 3), u = xg(m, f, n), c = xg(m, f, n - 1 / 3);
  }
  return {
    red: Math.round(r * 255),
    green: Math.round(u * 255),
    blue: Math.round(c * 255),
    alpha: a
  };
}
function td(n, t) {
  return (i) => i > 0 ? t : n;
}
const Ft = (n, t, i) => n + (t - n) * i, Sg = (n, t, i) => {
  const a = n * n, r = i * (t * t - a) + a;
  return r < 0 ? 0 : Math.sqrt(r);
}, eP = [ey, Ua, kr], nP = (n) => eP.find((t) => t.test(n));
function _1(n) {
  const t = nP(n);
  if (Ic(!!t, `'${n}' is not an animatable color. Use the equivalent color code instead.`, "color-not-animatable"), !t)
    return !1;
  let i = t.parse(n);
  return t === kr && (i = tP(i)), i;
}
const B1 = (n, t) => {
  const i = _1(n), a = _1(t);
  if (!i || !a)
    return td(n, t);
  const r = { ...i };
  return (u) => (r.red = Sg(i.red, a.red, u), r.green = Sg(i.green, a.green, u), r.blue = Sg(i.blue, a.blue, u), r.alpha = Ft(i.alpha, a.alpha, u), Ua.transform(r));
}, ny = /* @__PURE__ */ new Set(["none", "hidden"]);
function iP(n, t) {
  return ny.has(n) ? (i) => i <= 0 ? n : t : (i) => i >= 1 ? t : n;
}
function sP(n, t) {
  return (i) => Ft(n, t, i);
}
function hv(n) {
  return typeof n == "number" ? sP : typeof n == "string" ? uv(n) ? td : ve.test(n) ? B1 : rP : Array.isArray(n) ? ZT : typeof n == "object" ? ve.test(n) ? B1 : aP : td;
}
function ZT(n, t) {
  const i = [...n], a = i.length, r = n.map((u, c) => hv(u)(u, t[c]));
  return (u) => {
    for (let c = 0; c < a; c++)
      i[c] = r[c](u);
    return i;
  };
}
function aP(n, t) {
  const i = { ...n, ...t }, a = {};
  for (const r in i)
    n[r] !== void 0 && t[r] !== void 0 && (a[r] = hv(n[r])(n[r], t[r]));
  return (r) => {
    for (const u in a)
      i[u] = a[u](r);
    return i;
  };
}
function oP(n, t) {
  const i = [], a = { color: 0, var: 0, number: 0 };
  for (let r = 0; r < t.values.length; r++) {
    const u = t.types[r], c = n.indexes[u][a[u]], f = n.values[c] ?? 0;
    i[r] = f, a[u]++;
  }
  return i;
}
const rP = (n, t) => {
  const i = ei.createTransformer(t), a = zl(n), r = zl(t);
  return a.indexes.var.length === r.indexes.var.length && a.indexes.color.length === r.indexes.color.length && a.indexes.number.length >= r.indexes.number.length ? ny.has(n) && !r.values.length || ny.has(t) && !a.values.length ? iP(n, t) : $c(ZT(oP(a, r), r.values), i) : (Ic(!0, `Complex values '${n}' and '${t}' too different to mix. Ensure all colors are of the same type, and that each contains the same quantity of number and color values. Falling back to instant transition.`, "complex-values-different"), td(n, t));
};
function QT(n, t, i) {
  return typeof n == "number" && typeof t == "number" && typeof i == "number" ? Ft(n, t, i) : hv(n)(n, t);
}
const lP = (n) => {
  const t = ({ timestamp: i }) => n(i);
  return {
    start: (i = !0) => jt.update(t, i),
    stop: () => Wi(t),
    /**
     * If we're processing this frame we can use the
     * framelocked timestamp to keep things in sync.
     */
    now: () => Ve.isProcessing ? Ve.timestamp : Ke.now()
  };
}, KT = (n, t, i = 10) => {
  let a = "";
  const r = Math.max(Math.round(t / i), 2);
  for (let u = 0; u < r; u++)
    a += Math.round(n(u / (r - 1)) * 1e4) / 1e4 + ", ";
  return `linear(${a.substring(0, a.length - 2)})`;
}, ed = 2e4;
function dv(n) {
  let t = 0;
  const i = 50;
  let a = n.next(t);
  for (; !a.done && t < ed; )
    t += i, a = n.next(t);
  return t >= ed ? 1 / 0 : t;
}
function uP(n, t = 100, i) {
  const a = i({ ...n, keyframes: [0, t] }), r = Math.min(dv(a), ed);
  return {
    type: "keyframes",
    ease: (u) => a.next(r * u).value / t,
    duration: /* @__PURE__ */ Pn(r)
  };
}
const ae = {
  // Default spring physics
  stiffness: 100,
  damping: 10,
  mass: 1,
  velocity: 0,
  // Default duration/bounce-based options
  duration: 800,
  // in ms
  bounce: 0.3,
  visualDuration: 0.3,
  // in seconds
  // Rest thresholds
  restSpeed: {
    granular: 0.01,
    default: 2
  },
  restDelta: {
    granular: 5e-3,
    default: 0.5
  },
  // Limits
  minDuration: 0.01,
  // in seconds
  maxDuration: 10,
  // in seconds
  minDamping: 0.05,
  maxDamping: 1
};
function iy(n, t) {
  return n * Math.sqrt(1 - t * t);
}
const cP = 12;
function fP(n, t, i) {
  let a = i;
  for (let r = 1; r < cP; r++)
    a = a - n(a) / t(a);
  return a;
}
const wg = 1e-3;
function hP({ duration: n = ae.duration, bounce: t = ae.bounce, velocity: i = ae.velocity, mass: a = ae.mass }) {
  let r, u;
  Ic(n <= /* @__PURE__ */ rn(ae.maxDuration), "Spring duration must be 10 seconds or less", "spring-duration-limit");
  let c = 1 - t;
  c = Vi(ae.minDamping, ae.maxDamping, c), n = Vi(ae.minDuration, ae.maxDuration, /* @__PURE__ */ Pn(n)), c < 1 ? (r = (p) => {
    const g = p * c, y = g * n, b = g - i, S = iy(p, c), T = Math.exp(-y);
    return wg - b / S * T;
  }, u = (p) => {
    const y = p * c * n, b = y * i + i, S = Math.pow(c, 2) * Math.pow(p, 2) * n, T = Math.exp(-y), C = iy(Math.pow(p, 2), c);
    return (-r(p) + wg > 0 ? -1 : 1) * ((b - S) * T) / C;
  }) : (r = (p) => {
    const g = Math.exp(-p * n), y = (p - i) * n + 1;
    return -wg + g * y;
  }, u = (p) => {
    const g = Math.exp(-p * n), y = (i - p) * (n * n);
    return g * y;
  });
  const f = 5 / n, m = fP(r, u, f);
  if (n = /* @__PURE__ */ rn(n), isNaN(m))
    return {
      stiffness: ae.stiffness,
      damping: ae.damping,
      duration: n
    };
  {
    const p = Math.pow(m, 2) * a;
    return {
      stiffness: p,
      damping: c * 2 * Math.sqrt(a * p),
      duration: n
    };
  }
}
const dP = ["duration", "bounce"], mP = ["stiffness", "damping", "mass"];
function N1(n, t) {
  return t.some((i) => n[i] !== void 0);
}
function pP(n) {
  let t = {
    velocity: ae.velocity,
    stiffness: ae.stiffness,
    damping: ae.damping,
    mass: ae.mass,
    isResolvedFromDuration: !1,
    ...n
  };
  if (!N1(n, mP) && N1(n, dP))
    if (t.velocity = 0, n.visualDuration) {
      const i = n.visualDuration, a = 2 * Math.PI / (i * 1.2), r = a * a, u = 2 * Vi(0.05, 1, 1 - (n.bounce || 0)) * Math.sqrt(r);
      t = {
        ...t,
        mass: ae.mass,
        stiffness: r,
        damping: u
      };
    } else {
      const i = hP({ ...n, velocity: 0 });
      t = {
        ...t,
        ...i,
        mass: ae.mass
      }, t.isResolvedFromDuration = !0;
    }
  return t;
}
function nd(n = ae.visualDuration, t = ae.bounce) {
  const i = typeof n != "object" ? {
    visualDuration: n,
    keyframes: [0, 1],
    bounce: t
  } : n;
  let { restSpeed: a, restDelta: r } = i;
  const u = i.keyframes[0], c = i.keyframes[i.keyframes.length - 1], f = { done: !1, value: u }, { stiffness: m, damping: p, mass: g, duration: y, velocity: b, isResolvedFromDuration: S } = pP({
    ...i,
    velocity: -/* @__PURE__ */ Pn(i.velocity || 0)
  }), T = b || 0, C = p / (2 * Math.sqrt(m * g)), R = c - u, z = /* @__PURE__ */ Pn(Math.sqrt(m / g)), B = Math.abs(R) < 5;
  a || (a = B ? ae.restSpeed.granular : ae.restSpeed.default), r || (r = B ? ae.restDelta.granular : ae.restDelta.default);
  let H, X, Q, ut, st, $;
  if (C < 1)
    Q = iy(z, C), ut = (T + C * z * R) / Q, H = (nt) => {
      const vt = Math.exp(-C * z * nt);
      return c - vt * (ut * Math.sin(Q * nt) + R * Math.cos(Q * nt));
    }, st = C * z * ut + R * Q, $ = C * z * R - ut * Q, X = (nt) => Math.exp(-C * z * nt) * (st * Math.sin(Q * nt) + $ * Math.cos(Q * nt));
  else if (C === 1) {
    H = (vt) => c - Math.exp(-z * vt) * (R + (T + z * R) * vt);
    const nt = T + z * R;
    X = (vt) => Math.exp(-z * vt) * (z * nt * vt - T);
  } else {
    const nt = z * Math.sqrt(C * C - 1);
    H = (Kt) => {
      const zt = Math.exp(-C * z * Kt), j = Math.min(nt * Kt, 300);
      return c - zt * ((T + C * z * R) * Math.sinh(j) + nt * R * Math.cosh(j)) / nt;
    };
    const vt = (T + C * z * R) / nt, it = C * z * vt - R * nt, ie = C * z * R - vt * nt;
    X = (Kt) => {
      const zt = Math.exp(-C * z * Kt), j = Math.min(nt * Kt, 300);
      return zt * (it * Math.sinh(j) + ie * Math.cosh(j));
    };
  }
  const lt = {
    calculatedDuration: S && y || null,
    velocity: (nt) => /* @__PURE__ */ rn(X(nt)),
    next: (nt) => {
      if (!S && C < 1) {
        const it = Math.exp(-C * z * nt), ie = Math.sin(Q * nt), Kt = Math.cos(Q * nt), zt = c - it * (ut * ie + R * Kt), j = /* @__PURE__ */ rn(it * (st * ie + $ * Kt));
        return f.done = Math.abs(j) <= a && Math.abs(c - zt) <= r, f.value = f.done ? c : zt, f;
      }
      const vt = H(nt);
      if (S)
        f.done = nt >= y;
      else {
        const it = /* @__PURE__ */ rn(X(nt));
        f.done = Math.abs(it) <= a && Math.abs(c - vt) <= r;
      }
      return f.value = f.done ? c : vt, f;
    },
    toString: () => {
      const nt = Math.min(dv(lt), ed), vt = KT((it) => lt.next(nt * it).value, nt, 30);
      return nt + "ms " + vt;
    },
    toTransition: () => {
    }
  };
  return lt;
}
nd.applyToOptions = (n) => {
  const t = uP(n, 100, nd);
  return n.ease = t.ease, n.duration = /* @__PURE__ */ rn(t.duration), n.type = "keyframes", n;
};
const gP = 5;
function IT(n, t, i) {
  const a = Math.max(t - gP, 0);
  return /* @__PURE__ */ RT(i - n(a), t - a);
}
function sy({ keyframes: n, velocity: t = 0, power: i = 0.8, timeConstant: a = 325, bounceDamping: r = 10, bounceStiffness: u = 500, modifyTarget: c, min: f, max: m, restDelta: p = 0.5, restSpeed: g }) {
  const y = n[0], b = {
    done: !1,
    value: y
  }, S = ($) => f !== void 0 && $ < f || m !== void 0 && $ > m, T = ($) => f === void 0 ? m : m === void 0 || Math.abs(f - $) < Math.abs(m - $) ? f : m;
  let C = i * t;
  const R = y + C, z = c === void 0 ? R : c(R);
  z !== R && (C = z - y);
  const B = ($) => -C * Math.exp(-$ / a), H = ($) => z + B($), X = ($) => {
    const lt = B($), nt = H($);
    b.done = Math.abs(lt) <= p, b.value = b.done ? z : nt;
  };
  let Q, ut;
  const st = ($) => {
    S(b.value) && (Q = $, ut = nd({
      keyframes: [b.value, T(b.value)],
      velocity: IT(H, $, b.value),
      // TODO: This should be passing * 1000
      damping: r,
      stiffness: u,
      restDelta: p,
      restSpeed: g
    }));
  };
  return st(0), {
    calculatedDuration: null,
    next: ($) => {
      let lt = !1;
      return !ut && Q === void 0 && (lt = !0, X($), st($)), Q !== void 0 && $ >= Q ? ut.next($ - Q) : (!lt && X($), b);
    }
  };
}
function yP(n, t, i) {
  const a = [], r = i || ca.mix || QT, u = n.length - 1;
  for (let c = 0; c < u; c++) {
    let f = r(n[c], n[c + 1]);
    if (t) {
      const m = Array.isArray(t) ? t[c] || Bn : t;
      f = $c(m, f);
    }
    a.push(f);
  }
  return a;
}
function $T(n, t, { clamp: i = !0, ease: a, mixer: r } = {}) {
  const u = n.length;
  if (ua(u === t.length, "Both input and output ranges must be the same length", "range-length"), u === 1)
    return () => t[0];
  if (u === 2 && t[0] === t[1])
    return () => t[1];
  const c = n[0] === n[1];
  n[0] > n[u - 1] && (n = [...n].reverse(), t = [...t].reverse());
  const f = yP(t, a, r), m = f.length, p = (g) => {
    if (c && g < n[0])
      return t[0];
    let y = 0;
    if (m > 1)
      for (; y < n.length - 2 && !(g < n[y + 1]); y++)
        ;
    const b = /* @__PURE__ */ rc(n[y], n[y + 1], g);
    return f[y](b);
  };
  return i ? (g) => p(Vi(n[0], n[u - 1], g)) : p;
}
function vP(n, t) {
  const i = n[n.length - 1];
  for (let a = 1; a <= t; a++) {
    const r = /* @__PURE__ */ rc(0, t, a);
    n.push(Ft(i, 1, r));
  }
}
function bP(n) {
  const t = [0];
  return vP(t, n.length - 1), t;
}
function xP(n, t) {
  return n.map((i) => i * t);
}
function SP(n, t) {
  return n.map(() => t || NT).splice(0, n.length - 1);
}
function Ju({ duration: n = 300, keyframes: t, times: i, ease: a = "easeInOut" }) {
  const r = /* @__PURE__ */ zV(a) ? a.map(k1) : k1(a), u = {
    done: !1,
    value: t[0]
  }, c = xP(
    // Only use the provided offsets if they're the correct length
    // TODO Maybe we should warn here if there's a length mismatch
    i && i.length === t.length ? i : bP(t),
    n
  ), f = $T(c, t, {
    ease: Array.isArray(r) ? r : SP(t, r)
  });
  return {
    calculatedDuration: n,
    next: (m) => (u.value = f(m), u.done = m >= n, u)
  };
}
const wP = (n) => n !== null;
function Rd(n, { repeat: t, repeatType: i = "loop" }, a, r = 1) {
  const u = n.filter(wP), f = r < 0 || t && i !== "loop" && t % 2 === 1 ? 0 : u.length - 1;
  return !f || a === void 0 ? u[f] : a;
}
const MP = {
  decay: sy,
  inertia: sy,
  tween: Ju,
  keyframes: Ju,
  spring: nd
};
function WT(n) {
  typeof n.type == "string" && (n.type = MP[n.type]);
}
class mv {
  constructor() {
    this.updateFinished();
  }
  get finished() {
    return this._finished;
  }
  updateFinished() {
    this._finished = new Promise((t) => {
      this.resolve = t;
    });
  }
  notifyFinished() {
    this.resolve();
  }
  /**
   * Allows the animation to be awaited.
   *
   * @deprecated Use `finished` instead.
   */
  then(t, i) {
    return this.finished.then(t, i);
  }
}
const TP = (n) => n / 100;
class uc extends mv {
  constructor(t) {
    super(), this.state = "idle", this.startTime = null, this.isStopped = !1, this.currentTime = 0, this.holdTime = null, this.playbackSpeed = 1, this.delayState = {
      done: !1,
      value: void 0
    }, this.stop = () => {
      var a, r;
      const { motionValue: i } = this.options;
      i && i.updatedAt !== Ke.now() && this.tick(Ke.now()), this.isStopped = !0, this.state !== "idle" && (this.teardown(), (r = (a = this.options).onStop) == null || r.call(a));
    }, this.options = t, this.initAnimation(), this.play(), t.autoplay === !1 && this.pause();
  }
  initAnimation() {
    const { options: t } = this;
    WT(t);
    const { type: i = Ju, repeat: a = 0, repeatDelay: r = 0, repeatType: u, velocity: c = 0 } = t;
    let { keyframes: f } = t;
    const m = i || Ju;
    m !== Ju && typeof f[0] != "number" && (this.mixKeyframes = $c(TP, QT(f[0], f[1])), f = [0, 100]);
    const p = m({ ...t, keyframes: f });
    u === "mirror" && (this.mirroredGenerator = m({
      ...t,
      keyframes: [...f].reverse(),
      velocity: -c
    })), p.calculatedDuration === null && (p.calculatedDuration = dv(p));
    const { calculatedDuration: g } = p;
    this.calculatedDuration = g, this.resolvedDuration = g + r, this.totalDuration = this.resolvedDuration * (a + 1) - r, this.generator = p;
  }
  updateTime(t) {
    const i = Math.round(t - this.startTime) * this.playbackSpeed;
    this.holdTime !== null ? this.currentTime = this.holdTime : this.currentTime = i;
  }
  tick(t, i = !1) {
    const { generator: a, totalDuration: r, mixKeyframes: u, mirroredGenerator: c, resolvedDuration: f, calculatedDuration: m } = this;
    if (this.startTime === null)
      return a.next(0);
    const { delay: p = 0, keyframes: g, repeat: y, repeatType: b, repeatDelay: S, type: T, onUpdate: C, finalKeyframe: R } = this.options;
    this.speed > 0 ? this.startTime = Math.min(this.startTime, t) : this.speed < 0 && (this.startTime = Math.min(t - r / this.speed, this.startTime)), i ? this.currentTime = t : this.updateTime(t);
    const z = this.currentTime - p * (this.playbackSpeed >= 0 ? 1 : -1), B = this.playbackSpeed >= 0 ? z < 0 : z > r;
    this.currentTime = Math.max(z, 0), this.state === "finished" && this.holdTime === null && (this.currentTime = r);
    let H = this.currentTime, X = a;
    if (y) {
      const $ = Math.min(this.currentTime, r) / f;
      let lt = Math.floor($), nt = $ % 1;
      !nt && $ >= 1 && (nt = 1), nt === 1 && lt--, lt = Math.min(lt, y + 1), !!(lt % 2) && (b === "reverse" ? (nt = 1 - nt, S && (nt -= S / f)) : b === "mirror" && (X = c)), H = Vi(0, 1, nt) * f;
    }
    let Q;
    B ? (this.delayState.value = g[0], Q = this.delayState) : Q = X.next(H), u && !B && (Q.value = u(Q.value));
    let { done: ut } = Q;
    !B && m !== null && (ut = this.playbackSpeed >= 0 ? this.currentTime >= r : this.currentTime <= 0);
    const st = this.holdTime === null && (this.state === "finished" || this.state === "running" && ut);
    return st && T !== sy && (Q.value = Rd(g, this.options, R, this.speed)), C && C(Q.value), st && this.finish(), Q;
  }
  /**
   * Allows the returned animation to be awaited or promise-chained. Currently
   * resolves when the animation finishes at all but in a future update could/should
   * reject if its cancels.
   */
  then(t, i) {
    return this.finished.then(t, i);
  }
  get duration() {
    return /* @__PURE__ */ Pn(this.calculatedDuration);
  }
  get iterationDuration() {
    const { delay: t = 0 } = this.options || {};
    return this.duration + /* @__PURE__ */ Pn(t);
  }
  get time() {
    return /* @__PURE__ */ Pn(this.currentTime);
  }
  set time(t) {
    t = /* @__PURE__ */ rn(t), this.currentTime = t, this.startTime === null || this.holdTime !== null || this.playbackSpeed === 0 ? this.holdTime = t : this.driver && (this.startTime = this.driver.now() - t / this.playbackSpeed), this.driver ? this.driver.start(!1) : (this.startTime = 0, this.state = "paused", this.holdTime = t, this.tick(t));
  }
  /**
   * Returns the generator's velocity at the current time in units/second.
   * Uses the analytical derivative when available (springs), avoiding
   * the MotionValue's frame-dependent velocity estimation.
   */
  getGeneratorVelocity() {
    const t = this.currentTime;
    if (t <= 0)
      return this.options.velocity || 0;
    if (this.generator.velocity)
      return this.generator.velocity(t);
    const i = this.generator.next(t).value;
    return IT((a) => this.generator.next(a).value, t, i);
  }
  get speed() {
    return this.playbackSpeed;
  }
  set speed(t) {
    const i = this.playbackSpeed !== t;
    i && this.driver && this.updateTime(Ke.now()), this.playbackSpeed = t, i && this.driver && (this.time = /* @__PURE__ */ Pn(this.currentTime));
  }
  play() {
    var r, u;
    if (this.isStopped)
      return;
    const { driver: t = lP, startTime: i } = this.options;
    this.driver || (this.driver = t((c) => this.tick(c))), (u = (r = this.options).onPlay) == null || u.call(r);
    const a = this.driver.now();
    this.state === "finished" ? (this.updateFinished(), this.startTime = a) : this.holdTime !== null ? this.startTime = a - this.holdTime : this.startTime || (this.startTime = i ?? a), this.state === "finished" && this.speed < 0 && (this.startTime += this.calculatedDuration), this.holdTime = null, this.state = "running", this.driver.start();
  }
  pause() {
    this.state = "paused", this.updateTime(Ke.now()), this.holdTime = this.currentTime;
  }
  complete() {
    this.state !== "running" && this.play(), this.state = "finished", this.holdTime = null;
  }
  finish() {
    var t, i;
    this.notifyFinished(), this.teardown(), this.state = "finished", (i = (t = this.options).onComplete) == null || i.call(t);
  }
  cancel() {
    var t, i;
    this.holdTime = null, this.startTime = 0, this.tick(0), this.teardown(), (i = (t = this.options).onCancel) == null || i.call(t);
  }
  teardown() {
    this.state = "idle", this.stopDriver(), this.startTime = this.holdTime = null;
  }
  stopDriver() {
    this.driver && (this.driver.stop(), this.driver = void 0);
  }
  sample(t) {
    return this.startTime = 0, this.tick(t, !0);
  }
  attachTimeline(t) {
    var i;
    return this.options.allowFlatten && (this.options.type = "keyframes", this.options.ease = "linear", this.initAnimation()), (i = this.driver) == null || i.stop(), t.observe(this);
  }
}
function CP(n) {
  for (let t = 1; t < n.length; t++)
    n[t] ?? (n[t] = n[t - 1]);
}
const ja = (n) => n * 180 / Math.PI, ay = (n) => {
  const t = ja(Math.atan2(n[1], n[0]));
  return oy(t);
}, EP = {
  x: 4,
  y: 5,
  translateX: 4,
  translateY: 5,
  scaleX: 0,
  scaleY: 3,
  scale: (n) => (Math.abs(n[0]) + Math.abs(n[3])) / 2,
  rotate: ay,
  rotateZ: ay,
  skewX: (n) => ja(Math.atan(n[1])),
  skewY: (n) => ja(Math.atan(n[2])),
  skew: (n) => (Math.abs(n[1]) + Math.abs(n[2])) / 2
}, oy = (n) => (n = n % 360, n < 0 && (n += 360), n), U1 = ay, j1 = (n) => Math.sqrt(n[0] * n[0] + n[1] * n[1]), H1 = (n) => Math.sqrt(n[4] * n[4] + n[5] * n[5]), AP = {
  x: 12,
  y: 13,
  z: 14,
  translateX: 12,
  translateY: 13,
  translateZ: 14,
  scaleX: j1,
  scaleY: H1,
  scale: (n) => (j1(n) + H1(n)) / 2,
  rotateX: (n) => oy(ja(Math.atan2(n[6], n[5]))),
  rotateY: (n) => oy(ja(Math.atan2(-n[2], n[0]))),
  rotateZ: U1,
  rotate: U1,
  skewX: (n) => ja(Math.atan(n[4])),
  skewY: (n) => ja(Math.atan(n[1])),
  skew: (n) => (Math.abs(n[1]) + Math.abs(n[4])) / 2
};
function ry(n) {
  return n.includes("scale") ? 1 : 0;
}
function ly(n, t) {
  if (!n || n === "none")
    return ry(t);
  const i = n.match(/^matrix3d\(([-\d.e\s,]+)\)$/u);
  let a, r;
  if (i)
    a = AP, r = i;
  else {
    const f = n.match(/^matrix\(([-\d.e\s,]+)\)$/u);
    a = EP, r = f;
  }
  if (!r)
    return ry(t);
  const u = a[t], c = r[1].split(",").map(RP);
  return typeof u == "function" ? u(c) : c[u];
}
const DP = (n, t) => {
  const { transform: i = "none" } = getComputedStyle(n);
  return ly(i, t);
};
function RP(n) {
  return parseFloat(n.trim());
}
const Ll = [
  "transformPerspective",
  "x",
  "y",
  "z",
  "translateX",
  "translateY",
  "translateZ",
  "scale",
  "scaleX",
  "scaleY",
  "rotate",
  "rotateX",
  "rotateY",
  "rotateZ",
  "skew",
  "skewX",
  "skewY"
], _l = /* @__PURE__ */ new Set([...Ll, "pathRotation"]), q1 = (n) => n === Pl || n === ot, OP = /* @__PURE__ */ new Set(["x", "y", "z"]), zP = Ll.filter((n) => !OP.has(n));
function kP(n) {
  const t = [];
  return zP.forEach((i) => {
    const a = n.getValue(i);
    a !== void 0 && (t.push([i, a.get()]), a.set(i.startsWith("scale") ? 1 : 0));
  }), t;
}
const aa = {
  // Dimensions
  width: ({ x: n }, { paddingLeft: t = "0", paddingRight: i = "0", boxSizing: a }) => {
    const r = n.max - n.min;
    return a === "border-box" ? r : r - parseFloat(t) - parseFloat(i);
  },
  height: ({ y: n }, { paddingTop: t = "0", paddingBottom: i = "0", boxSizing: a }) => {
    const r = n.max - n.min;
    return a === "border-box" ? r : r - parseFloat(t) - parseFloat(i);
  },
  top: (n, { top: t }) => parseFloat(t),
  left: (n, { left: t }) => parseFloat(t),
  bottom: ({ y: n }, { top: t }) => parseFloat(t) + (n.max - n.min),
  right: ({ x: n }, { left: t }) => parseFloat(t) + (n.max - n.min),
  // Transform
  x: (n, { transform: t }) => ly(t, "x"),
  y: (n, { transform: t }) => ly(t, "y")
};
aa.translateX = aa.x;
aa.translateY = aa.y;
const wo = /* @__PURE__ */ new Set();
let uy = !1, cy = !1, fy = !1;
function JT() {
  if (cy) {
    const n = Array.from(wo).filter((a) => a.needsMeasurement), t = new Set(n.map((a) => a.element)), i = /* @__PURE__ */ new Map();
    t.forEach((a) => {
      const r = kP(a);
      r.length && (i.set(a, r), a.render());
    }), n.forEach((a) => a.measureInitialState()), t.forEach((a) => {
      a.render();
      const r = i.get(a);
      r && r.forEach(([u, c]) => {
        var f;
        (f = a.getValue(u)) == null || f.set(c);
      });
    }), n.forEach((a) => a.measureEndState()), n.forEach((a) => {
      a.suspendedScrollY !== void 0 && window.scrollTo(0, a.suspendedScrollY);
    });
  }
  cy = !1, uy = !1, wo.forEach((n) => n.complete(fy)), wo.clear();
}
function tC() {
  wo.forEach((n) => {
    n.readKeyframes(), n.needsMeasurement && (cy = !0);
  });
}
function VP() {
  fy = !0, tC(), JT(), fy = !1;
}
class pv {
  constructor(t, i, a, r, u, c = !1) {
    this.state = "pending", this.isAsync = !1, this.needsMeasurement = !1, this.unresolvedKeyframes = [...t], this.onComplete = i, this.name = a, this.motionValue = r, this.element = u, this.isAsync = c;
  }
  scheduleResolve() {
    this.state = "scheduled", this.isAsync ? (wo.add(this), uy || (uy = !0, jt.read(tC), jt.resolveKeyframes(JT))) : (this.readKeyframes(), this.complete());
  }
  readKeyframes() {
    const { unresolvedKeyframes: t, name: i, element: a, motionValue: r } = this;
    if (t[0] === null) {
      const u = r == null ? void 0 : r.get(), c = t[t.length - 1];
      if (u !== void 0)
        t[0] = u;
      else if (a && i) {
        const f = a.readValue(i, c);
        f != null && (t[0] = f);
      }
      t[0] === void 0 && (t[0] = c), r && u === void 0 && r.set(t[0]);
    }
    CP(t);
  }
  setFinalKeyframe() {
  }
  measureInitialState() {
  }
  renderEndStyles() {
  }
  measureEndState() {
  }
  complete(t = !1) {
    this.state = "complete", this.onComplete(this.unresolvedKeyframes, this.finalKeyframe, t), wo.delete(this);
  }
  cancel() {
    this.state === "scheduled" && (wo.delete(this), this.state = "pending");
  }
  resume() {
    this.state === "pending" && this.scheduleResolve();
  }
}
const PP = (n) => n.startsWith("--");
function eC(n, t, i) {
  PP(t) ? n.style.setProperty(t, i) : n.style[t] = i;
}
const LP = {};
function nC(n, t) {
  const i = /* @__PURE__ */ DT(n);
  return () => LP[t] ?? i();
}
const _P = /* @__PURE__ */ nC(() => window.ScrollTimeline !== void 0, "scrollTimeline"), iC = /* @__PURE__ */ nC(() => {
  try {
    document.createElement("div").animate({ opacity: 0 }, { easing: "linear(0, 1)" });
  } catch {
    return !1;
  }
  return !0;
}, "linearEasing"), Fu = ([n, t, i, a]) => `cubic-bezier(${n}, ${t}, ${i}, ${a})`, G1 = {
  linear: "linear",
  ease: "ease",
  easeIn: "ease-in",
  easeOut: "ease-out",
  easeInOut: "ease-in-out",
  circIn: /* @__PURE__ */ Fu([0, 0.65, 0.55, 1]),
  circOut: /* @__PURE__ */ Fu([0.55, 0, 1, 0.45]),
  backIn: /* @__PURE__ */ Fu([0.31, 0.01, 0.66, -0.59]),
  backOut: /* @__PURE__ */ Fu([0.33, 1.53, 0.69, 0.99])
};
function sC(n, t) {
  if (n)
    return typeof n == "function" ? iC() ? KT(n, t) : "ease-out" : /* @__PURE__ */ UT(n) ? Fu(n) : Array.isArray(n) ? n.map((i) => sC(i, t) || G1.easeOut) : G1[n];
}
function BP(n, t, i, { delay: a = 0, duration: r = 300, repeat: u = 0, repeatType: c = "loop", ease: f = "easeOut", times: m } = {}, p = void 0) {
  const g = {
    [t]: i
  };
  m && (g.offset = m);
  const y = sC(f, r);
  Array.isArray(y) && (g.easing = y);
  const b = {
    delay: a,
    duration: r,
    easing: Array.isArray(y) ? "linear" : y,
    fill: "both",
    iterations: u + 1,
    direction: c === "reverse" ? "alternate" : "normal"
  };
  return p && (b.pseudoElement = p), n.animate(g, b);
}
function aC(n) {
  return typeof n == "function" && "applyToOptions" in n;
}
function NP({ type: n, ...t }) {
  return aC(n) && iC() ? n.applyToOptions(t) : (t.duration ?? (t.duration = 300), t.ease ?? (t.ease = "easeOut"), t);
}
class oC extends mv {
  constructor(t) {
    if (super(), this.finishedTime = null, this.isStopped = !1, this.manualStartTime = null, !t)
      return;
    const { element: i, name: a, keyframes: r, pseudoElement: u, allowFlatten: c = !1, finalKeyframe: f, onComplete: m } = t;
    this.isPseudoElement = !!u, this.allowFlatten = c, this.options = t, ua(typeof t.type != "string", `Mini animate() doesn't support "type" as a string.`, "mini-spring");
    const p = NP(t);
    this.animation = BP(i, a, r, p, u), p.autoplay === !1 && this.animation.pause(), this.animation.onfinish = () => {
      if (this.finishedTime = this.time, !u) {
        const g = Rd(r, this.options, f, this.speed);
        this.updateMotionValue && this.updateMotionValue(g), eC(i, a, g), this.animation.cancel();
      }
      m == null || m(), this.notifyFinished();
    };
  }
  play() {
    this.isStopped || (this.manualStartTime = null, this.animation.play(), this.state === "finished" && this.updateFinished());
  }
  pause() {
    this.animation.pause();
  }
  complete() {
    var t, i;
    (i = (t = this.animation).finish) == null || i.call(t);
  }
  cancel() {
    try {
      this.animation.cancel();
    } catch {
    }
  }
  stop() {
    if (this.isStopped)
      return;
    this.isStopped = !0;
    const { state: t } = this;
    t === "idle" || t === "finished" || (this.updateMotionValue ? this.updateMotionValue() : this.commitStyles(), this.isPseudoElement || this.cancel());
  }
  /**
   * WAAPI doesn't natively have any interruption capabilities.
   *
   * In this method, we commit styles back to the DOM before cancelling
   * the animation.
   *
   * This is designed to be overridden by NativeAnimationExtended, which
   * will create a renderless JS animation and sample it twice to calculate
   * its current value, "previous" value, and therefore allow
   * Motion to also correctly calculate velocity for any subsequent animation
   * while deferring the commit until the next animation frame.
   */
  commitStyles() {
    var i, a, r;
    const t = (i = this.options) == null ? void 0 : i.element;
    !this.isPseudoElement && (t != null && t.isConnected) && ((r = (a = this.animation).commitStyles) == null || r.call(a));
  }
  get duration() {
    var i, a;
    const t = ((a = (i = this.animation.effect) == null ? void 0 : i.getComputedTiming) == null ? void 0 : a.call(i).duration) || 0;
    return /* @__PURE__ */ Pn(Number(t));
  }
  get iterationDuration() {
    const { delay: t = 0 } = this.options || {};
    return this.duration + /* @__PURE__ */ Pn(t);
  }
  get time() {
    return /* @__PURE__ */ Pn(Number(this.animation.currentTime) || 0);
  }
  set time(t) {
    const i = this.finishedTime !== null;
    this.manualStartTime = null, this.finishedTime = null, this.animation.currentTime = /* @__PURE__ */ rn(t), i && this.animation.pause();
  }
  /**
   * The playback speed of the animation.
   * 1 = normal speed, 2 = double speed, 0.5 = half speed.
   */
  get speed() {
    return this.animation.playbackRate;
  }
  set speed(t) {
    t < 0 && (this.finishedTime = null), this.animation.playbackRate = t;
  }
  get state() {
    return this.finishedTime !== null ? "finished" : this.animation.playState;
  }
  get startTime() {
    return this.manualStartTime ?? Number(this.animation.startTime);
  }
  set startTime(t) {
    this.manualStartTime = this.animation.startTime = t;
  }
  /**
   * Attaches a timeline to the animation, for instance the `ScrollTimeline`.
   */
  attachTimeline({ timeline: t, rangeStart: i, rangeEnd: a, observe: r }) {
    var u;
    return this.allowFlatten && ((u = this.animation.effect) == null || u.updateTiming({ easing: "linear" })), this.animation.onfinish = null, t && _P() ? (this.animation.timeline = t, i && (this.animation.rangeStart = i), a && (this.animation.rangeEnd = a), Bn) : r(this);
  }
}
const rC = {
  anticipate: LT,
  backInOut: PT,
  circInOut: BT
};
function UP(n) {
  return n in rC;
}
function jP(n) {
  typeof n.ease == "string" && UP(n.ease) && (n.ease = rC[n.ease]);
}
const Mg = 10;
class HP extends oC {
  constructor(t) {
    jP(t), WT(t), super(t), t.startTime !== void 0 && t.autoplay !== !1 && (this.startTime = t.startTime), this.options = t;
  }
  /**
   * WAAPI doesn't natively have any interruption capabilities.
   *
   * Rather than read committed styles back out of the DOM, we can
   * create a renderless JS animation and sample it twice to calculate
   * its current value, "previous" value, and therefore allow
   * Motion to calculate velocity for any subsequent animation.
   */
  updateMotionValue(t) {
    const { motionValue: i, onUpdate: a, onComplete: r, element: u, ...c } = this.options;
    if (!i)
      return;
    if (t !== void 0) {
      i.set(t);
      return;
    }
    const f = new uc({
      ...c,
      autoplay: !1
    }), m = Math.max(Mg, Ke.now() - this.startTime), p = Vi(0, Mg, m - Mg), g = f.sample(m).value, { name: y } = this.options;
    u && y && eC(u, y, g), i.setWithVelocity(f.sample(Math.max(0, m - p)).value, g, p), f.stop();
  }
}
const Y1 = (n, t) => t === "zIndex" ? !1 : !!(typeof n == "number" || Array.isArray(n) || typeof n == "string" && // It's animatable if we have a string
(ei.test(n) || n === "0") && // And it contains numbers and/or colors
!n.startsWith("url("));
function qP(n) {
  const t = n[0];
  if (n.length === 1)
    return !0;
  for (let i = 0; i < n.length; i++)
    if (n[i] !== t)
      return !0;
}
function GP(n, t, i, a) {
  const r = n[0];
  if (r === null)
    return !1;
  if (t === "display" || t === "visibility")
    return !0;
  const u = n[n.length - 1], c = Y1(r, t), f = Y1(u, t);
  return Ic(c === f, `You are trying to animate ${t} from "${r}" to "${u}". "${c ? u : r}" is not an animatable value.`, "value-not-animatable"), !c || !f ? !1 : qP(n) || (i === "spring" || aC(i)) && a;
}
function hy(n) {
  n.duration = 0, n.type = "keyframes";
}
const lC = /* @__PURE__ */ new Set([
  "opacity",
  "clipPath",
  "filter",
  "transform",
  "backgroundColor"
]), YP = /^(?:oklch|oklab|lab|lch|color|color-mix|light-dark)\(/;
function XP(n) {
  for (let t = 0; t < n.length; t++)
    if (typeof n[t] == "string" && YP.test(n[t]))
      return !0;
  return !1;
}
const FP = /* @__PURE__ */ new Set([
  "color",
  "backgroundColor",
  "outlineColor",
  "fill",
  "stroke",
  "borderColor",
  "borderTopColor",
  "borderRightColor",
  "borderBottomColor",
  "borderLeftColor"
]), ZP = /* @__PURE__ */ DT(() => Object.hasOwnProperty.call(Element.prototype, "animate"));
function QP(n) {
  var y;
  const { motionValue: t, name: i, repeatDelay: a, repeatType: r, damping: u, type: c, keyframes: f } = n, m = (y = t == null ? void 0 : t.owner) == null ? void 0 : y.current;
  if (!(m instanceof HTMLElement) && !(m instanceof SVGElement))
    return !1;
  const { onUpdate: p, transformTemplate: g } = t.owner.getProps();
  return ZP() && i && /**
   * Force WAAPI for color properties with browser-only color formats
   * (oklch, oklab, lab, lch, etc.) that the JS animation path can't parse.
   */
  (lC.has(i) || FP.has(i) && XP(f)) && (i !== "transform" || !g) && /**
   * If we're outputting values to onUpdate then we can't use WAAPI as there's
   * no way to read the value from WAAPI every frame.
   */
  !p && !a && r !== "mirror" && u !== 0 && c !== "inertia";
}
const KP = 40;
class IP extends mv {
  constructor({ autoplay: t = !0, delay: i = 0, type: a = "keyframes", repeat: r = 0, repeatDelay: u = 0, repeatType: c = "loop", keyframes: f, name: m, motionValue: p, element: g, ...y }) {
    var T;
    super(), this.stop = () => {
      var C, R;
      this._animation && (this._animation.stop(), (C = this.stopTimeline) == null || C.call(this)), (R = this.keyframeResolver) == null || R.cancel();
    }, this.createdAt = Ke.now();
    const b = {
      autoplay: t,
      delay: i,
      type: a,
      repeat: r,
      repeatDelay: u,
      repeatType: c,
      name: m,
      motionValue: p,
      element: g,
      ...y
    }, S = (g == null ? void 0 : g.KeyframeResolver) || pv;
    this.keyframeResolver = new S(f, (C, R, z) => this.onKeyframesResolved(C, R, b, !z), m, p, g), (T = this.keyframeResolver) == null || T.scheduleResolve();
  }
  onKeyframesResolved(t, i, a, r) {
    var z, B;
    this.keyframeResolver = void 0;
    const { name: u, type: c, velocity: f, delay: m, isHandoff: p, onUpdate: g } = a;
    this.resolvedAt = Ke.now();
    let y = !0;
    GP(t, u, c, f) || (y = !1, (ca.instantAnimations || !m) && (g == null || g(Rd(t, a, i))), t[0] = t[t.length - 1], hy(a), a.repeat = 0);
    const S = {
      startTime: r ? this.resolvedAt ? this.resolvedAt - this.createdAt > KP ? this.resolvedAt : this.createdAt : this.createdAt : void 0,
      finalKeyframe: i,
      ...a,
      keyframes: t
    }, T = y && !p && QP(S), C = (B = (z = S.motionValue) == null ? void 0 : z.owner) == null ? void 0 : B.current;
    let R;
    if (T)
      try {
        R = new HP({
          ...S,
          element: C
        });
      } catch {
        R = new uc(S);
      }
    else
      R = new uc(S);
    R.finished.then(() => {
      this.notifyFinished();
    }).catch(Bn), this.pendingTimeline && (this.stopTimeline = R.attachTimeline(this.pendingTimeline), this.pendingTimeline = void 0), this._animation = R;
  }
  get finished() {
    return this._animation ? this.animation.finished : this._finished;
  }
  then(t, i) {
    return this.finished.finally(t).then(() => {
    });
  }
  get animation() {
    var t;
    return this._animation || ((t = this.keyframeResolver) == null || t.resume(), VP()), this._animation;
  }
  get duration() {
    return this.animation.duration;
  }
  get iterationDuration() {
    return this.animation.iterationDuration;
  }
  get time() {
    return this.animation.time;
  }
  set time(t) {
    this.animation.time = t;
  }
  get speed() {
    return this.animation.speed;
  }
  get state() {
    return this.animation.state;
  }
  set speed(t) {
    this.animation.speed = t;
  }
  get startTime() {
    return this.animation.startTime;
  }
  attachTimeline(t) {
    return this._animation ? this.stopTimeline = this.animation.attachTimeline(t) : this.pendingTimeline = t, () => this.stop();
  }
  play() {
    this.animation.play();
  }
  pause() {
    this.animation.pause();
  }
  complete() {
    this.animation.complete();
  }
  cancel() {
    var t;
    this._animation && this.animation.cancel(), (t = this.keyframeResolver) == null || t.cancel();
  }
}
function uC(n, t, i, a = 0, r = 1) {
  const u = Array.from(n).sort((p, g) => p.sortNodePosition(g)).indexOf(t), c = n.size, f = (c - 1) * a;
  return typeof i == "function" ? i(u, c) : r === 1 ? u * a : f - u * a;
}
const X1 = 30, $P = (n) => !isNaN(parseFloat(n)), tc = {
  current: void 0
};
class WP {
  /**
   * @param init - The initiating value
   * @param config - Optional configuration options
   *
   * -  `transformer`: A function to transform incoming values with.
   */
  constructor(t, i = {}) {
    this.canTrackVelocity = null, this.events = {}, this.updateAndNotify = (a) => {
      var u;
      const r = Ke.now();
      if (this.updatedAt !== r && this.setPrevFrameValue(), this.prev = this.current, this.setCurrent(a), this.current !== this.prev && ((u = this.events.change) == null || u.notify(this.current), this.dependents))
        for (const c of this.dependents)
          c.dirty();
    }, this.hasAnimated = !1, this.setCurrent(t), this.owner = i.owner;
  }
  setCurrent(t) {
    this.current = t, this.updatedAt = Ke.now(), this.canTrackVelocity === null && t !== void 0 && (this.canTrackVelocity = $P(this.current));
  }
  setPrevFrameValue(t = this.current) {
    this.prevFrameValue = t, this.prevUpdatedAt = this.updatedAt;
  }
  /**
   * Adds a function that will be notified when the `MotionValue` is updated.
   *
   * It returns a function that, when called, will cancel the subscription.
   *
   * When calling `onChange` inside a React component, it should be wrapped with the
   * `useEffect` hook. As it returns an unsubscribe function, this should be returned
   * from the `useEffect` function to ensure you don't add duplicate subscribers..
   *
   * ```jsx
   * export const MyComponent = () => {
   *   const x = useMotionValue(0)
   *   const y = useMotionValue(0)
   *   const opacity = useMotionValue(1)
   *
   *   useEffect(() => {
   *     function updateOpacity() {
   *       const maxXY = Math.max(x.get(), y.get())
   *       const newOpacity = transform(maxXY, [0, 100], [1, 0])
   *       opacity.set(newOpacity)
   *     }
   *
   *     const unsubscribeX = x.on("change", updateOpacity)
   *     const unsubscribeY = y.on("change", updateOpacity)
   *
   *     return () => {
   *       unsubscribeX()
   *       unsubscribeY()
   *     }
   *   }, [])
   *
   *   return <motion.div style={{ x }} />
   * }
   * ```
   *
   * @param subscriber - A function that receives the latest value.
   * @returns A function that, when called, will cancel this subscription.
   *
   * @deprecated
   */
  onChange(t) {
    return this.on("change", t);
  }
  on(t, i) {
    this.events[t] || (this.events[t] = new ov());
    const a = this.events[t].add(i);
    return t === "change" ? () => {
      a(), jt.read(() => {
        this.events.change.getSize() || this.stop();
      });
    } : a;
  }
  clearListeners() {
    for (const t in this.events)
      this.events[t].clear();
  }
  /**
   * Attaches a passive effect to the `MotionValue`.
   */
  attach(t, i) {
    this.passiveEffect = t, this.stopPassiveEffect = i;
  }
  /**
   * Sets the state of the `MotionValue`.
   *
   * @remarks
   *
   * ```jsx
   * const x = useMotionValue(0)
   * x.set(10)
   * ```
   *
   * @param latest - Latest value to set.
   * @param render - Whether to notify render subscribers. Defaults to `true`
   *
   * @public
   */
  set(t) {
    this.passiveEffect ? this.passiveEffect(t, this.updateAndNotify) : this.updateAndNotify(t);
  }
  setWithVelocity(t, i, a) {
    this.set(i), this.prev = void 0, this.prevFrameValue = t, this.prevUpdatedAt = this.updatedAt - a;
  }
  /**
   * Set the state of the `MotionValue`, stopping any active animations,
   * effects, and resets velocity to `0`.
   */
  jump(t, i = !0) {
    this.updateAndNotify(t), this.prev = t, this.prevUpdatedAt = this.prevFrameValue = void 0, i && this.stop(), this.stopPassiveEffect && this.stopPassiveEffect();
  }
  dirty() {
    var t;
    (t = this.events.change) == null || t.notify(this.current);
  }
  addDependent(t) {
    this.dependents || (this.dependents = /* @__PURE__ */ new Set()), this.dependents.add(t);
  }
  removeDependent(t) {
    this.dependents && this.dependents.delete(t);
  }
  /**
   * Returns the latest state of `MotionValue`
   *
   * @returns - The latest state of `MotionValue`
   *
   * @public
   */
  get() {
    return tc.current && tc.current.push(this), this.current;
  }
  /**
   * @public
   */
  getPrevious() {
    return this.prev;
  }
  /**
   * Returns the latest velocity of `MotionValue`
   *
   * @returns - The latest velocity of `MotionValue`. Returns `0` if the state is non-numerical.
   *
   * @public
   */
  getVelocity() {
    const t = Ke.now();
    if (!this.canTrackVelocity || this.prevFrameValue === void 0 || t - this.updatedAt > X1)
      return 0;
    const i = Math.min(this.updatedAt - this.prevUpdatedAt, X1);
    return /* @__PURE__ */ RT(parseFloat(this.current) - parseFloat(this.prevFrameValue), i);
  }
  /**
   * Registers a new animation to control this `MotionValue`. Only one
   * animation can drive a `MotionValue` at one time.
   *
   * ```jsx
   * value.start()
   * ```
   *
   * @param animation - A function that starts the provided animation
   */
  start(t) {
    return this.stop(), new Promise((i) => {
      this.hasAnimated = !0, this.animation = t(i), this.events.animationStart && this.events.animationStart.notify();
    }).then(() => {
      this.events.animationComplete && this.events.animationComplete.notify(), this.clearAnimation();
    });
  }
  /**
   * Stop the currently active animation.
   *
   * @public
   */
  stop() {
    this.animation && (this.animation.stop(), this.events.animationCancel && this.events.animationCancel.notify()), this.clearAnimation();
  }
  /**
   * Returns `true` if this value is currently animating.
   *
   * @public
   */
  isAnimating() {
    return !!this.animation;
  }
  clearAnimation() {
    delete this.animation;
  }
  /**
   * Destroy and clean up subscribers to this `MotionValue`.
   *
   * The `MotionValue` hooks like `useMotionValue` and `useTransform` automatically
   * handle the lifecycle of the returned `MotionValue`, so this method is only necessary if you've manually
   * created a `MotionValue` via the `motionValue` function.
   *
   * @public
   */
  destroy() {
    var t, i;
    (t = this.dependents) == null || t.clear(), (i = this.events.destroy) == null || i.notify(), this.clearListeners(), this.stop(), this.stopPassiveEffect && this.stopPassiveEffect();
  }
}
function Lo(n, t) {
  return new WP(n, t);
}
function cC(n, t) {
  if (n != null && n.inherit && t) {
    const { inherit: i, ...a } = n;
    return { ...t, ...a };
  }
  return n;
}
function gv(n, t) {
  const i = (n == null ? void 0 : n[t]) ?? (n == null ? void 0 : n.default) ?? n;
  return i !== n ? cC(i, n) : i;
}
const JP = {
  type: "spring",
  stiffness: 500,
  damping: 25,
  restSpeed: 10
}, t4 = (n) => ({
  type: "spring",
  stiffness: 550,
  damping: n === 0 ? 2 * Math.sqrt(550) : 30,
  restSpeed: 10
}), e4 = {
  type: "keyframes",
  duration: 0.8
}, n4 = {
  type: "keyframes",
  ease: [0.25, 0.1, 0.35, 1],
  duration: 0.3
}, i4 = (n, { keyframes: t }) => t.length > 2 ? e4 : _l.has(n) ? n.startsWith("scale") ? t4(t[1]) : JP : n4, s4 = /* @__PURE__ */ new Set([
  "when",
  "delay",
  "delayChildren",
  "staggerChildren",
  "staggerDirection",
  "repeat",
  "repeatType",
  "repeatDelay",
  "from",
  "elapsed"
]);
function a4(n) {
  for (const t in n)
    if (!s4.has(t))
      return !0;
  return !1;
}
const yv = (n, t, i, a = {}, r, u) => (c) => {
  const f = gv(a, n) || {}, m = f.delay || a.delay || 0;
  let { elapsed: p = 0 } = a;
  p = p - /* @__PURE__ */ rn(m);
  const g = {
    keyframes: Array.isArray(i) ? i : [null, i],
    ease: "easeOut",
    velocity: t.getVelocity(),
    ...f,
    delay: -p,
    onUpdate: (b) => {
      t.set(b), f.onUpdate && f.onUpdate(b);
    },
    onComplete: () => {
      c(), f.onComplete && f.onComplete();
    },
    name: n,
    motionValue: t,
    element: u ? void 0 : r
  };
  a4(f) || Object.assign(g, i4(n, g)), g.duration && (g.duration = /* @__PURE__ */ rn(g.duration)), g.repeatDelay && (g.repeatDelay = /* @__PURE__ */ rn(g.repeatDelay)), g.from !== void 0 && (g.keyframes[0] = g.from);
  let y = !1;
  if ((g.type === !1 || g.duration === 0 && !g.repeatDelay) && (hy(g), g.delay === 0 && (y = !0)), (ca.instantAnimations || ca.skipAnimations || r != null && r.shouldSkipAnimations || f.skipAnimations) && (y = !0, hy(g), g.delay = 0), g.allowFlatten = !f.type && !f.ease, y && !u && t.get() !== void 0) {
    const b = Rd(g.keyframes, f);
    if (b !== void 0) {
      jt.update(() => {
        g.onUpdate(b), g.onComplete();
      });
      return;
    }
  }
  return f.isSync ? new uc(g) : new IP(g);
}, o4 = (
  // eslint-disable-next-line redos-detector/no-unsafe-regex -- false positive, as it can match a lot of words
  /^var\(--(?:([\w-]+)|([\w-]+), ?([a-zA-Z\d ()%#.,-]+))\)/u
);
function r4(n) {
  const t = o4.exec(n);
  if (!t)
    return [,];
  const [, i, a, r] = t;
  return [`--${i ?? a}`, r];
}
const l4 = 4;
function fC(n, t, i = 1) {
  ua(i <= l4, `Max CSS variable fallback depth detected in property "${n}". This may indicate a circular fallback dependency.`, "max-css-var-depth");
  const [a, r] = r4(n);
  if (!a)
    return;
  const u = window.getComputedStyle(t).getPropertyValue(a);
  if (u) {
    const c = u.trim();
    return CT(c) ? parseFloat(c) : c;
  }
  return uv(r) ? fC(r, t, i + 1) : r;
}
function F1(n) {
  const t = [{}, {}];
  return n == null || n.values.forEach((i, a) => {
    t[0][a] = i.get(), t[1][a] = i.getVelocity();
  }), t;
}
function vv(n, t, i, a) {
  if (typeof t == "function") {
    const [r, u] = F1(a);
    t = t(i !== void 0 ? i : n.custom, r, u);
  }
  if (typeof t == "string" && (t = n.variants && n.variants[t]), typeof t == "function") {
    const [r, u] = F1(a);
    t = t(i !== void 0 ? i : n.custom, r, u);
  }
  return t;
}
function Mo(n, t, i) {
  const a = n.getProps();
  return vv(a, t, i !== void 0 ? i : a.custom, n);
}
const hC = /* @__PURE__ */ new Set([
  "width",
  "height",
  "top",
  "left",
  "right",
  "bottom",
  ...Ll
]), dy = (n) => Array.isArray(n);
function u4(n, t, i) {
  n.hasValue(t) ? n.getValue(t).set(i) : n.addValue(t, Lo(i));
}
function c4(n) {
  return dy(n) ? n[n.length - 1] || 0 : n;
}
function f4(n, t) {
  const i = Mo(n, t);
  let { transitionEnd: a = {}, transition: r = {}, ...u } = i || {};
  u = { ...u, ...a };
  for (const c in u) {
    const f = c4(u[c]);
    u4(n, c, f);
  }
}
const de = (n) => !!(n && n.getVelocity);
function h4(n) {
  return !!(de(n) && n.add);
}
function my(n, t) {
  const i = n.getValue("willChange");
  if (h4(i))
    return i.add(t);
  if (!i && ca.WillChange) {
    const a = new ca.WillChange("auto");
    n.addValue("willChange", a), a.add(t);
  }
}
function bv(n) {
  return n.replace(/([A-Z])/g, (t) => `-${t.toLowerCase()}`);
}
const d4 = "framerAppearId", dC = "data-" + bv(d4);
function mC(n) {
  return n.props[dC];
}
function m4({ protectedKeys: n, needsAnimating: t }, i) {
  const a = n.hasOwnProperty(i) && t[i] !== !0;
  return t[i] = !1, a;
}
function pC(n, t, { delay: i = 0, transitionOverride: a, type: r } = {}) {
  let { transition: u, transitionEnd: c, ...f } = t;
  const m = n.getDefaultTransition();
  u = u ? cC(u, m) : m;
  const p = u == null ? void 0 : u.reduceMotion, g = u == null ? void 0 : u.skipAnimations;
  a && (u = a);
  const y = [], b = r && n.animationState && n.animationState.getState()[r], S = u == null ? void 0 : u.path;
  S && S.animateVisualElement(n, f, u, i, y);
  for (const T in f) {
    const C = n.getValue(T, n.latestValues[T] ?? null), R = f[T];
    if (R === void 0 || b && m4(b, T))
      continue;
    const z = {
      delay: i,
      ...gv(u || {}, T)
    };
    g && (z.skipAnimations = !0);
    const B = C.get();
    if (B !== void 0 && !C.isAnimating() && !Array.isArray(R) && R === B && !z.velocity) {
      jt.update(() => C.set(R));
      continue;
    }
    let H = !1;
    if (window.MotionHandoffAnimation) {
      const ut = mC(n);
      if (ut) {
        const st = window.MotionHandoffAnimation(ut, T, jt);
        st !== null && (z.startTime = st, H = !0);
      }
    }
    my(n, T);
    const X = p ?? n.shouldReduceMotion;
    C.start(yv(T, C, R, X && hC.has(T) ? { type: !1 } : z, n, H));
    const Q = C.animation;
    Q && y.push(Q);
  }
  if (c) {
    const T = () => jt.update(() => {
      c && f4(n, c);
    });
    y.length ? Promise.all(y).then(T) : T();
  }
  return y;
}
function py(n, t, i = {}) {
  var m;
  const a = Mo(n, t, i.type === "exit" ? (m = n.presenceContext) == null ? void 0 : m.custom : void 0);
  let { transition: r = n.getDefaultTransition() || {} } = a || {};
  i.transitionOverride && (r = i.transitionOverride);
  const u = a ? () => Promise.all(pC(n, a, i)) : () => Promise.resolve(), c = n.variantChildren && n.variantChildren.size ? (p = 0) => {
    const { delayChildren: g = 0, staggerChildren: y, staggerDirection: b } = r;
    return p4(n, t, p, g, y, b, i);
  } : () => Promise.resolve(), { when: f } = r;
  if (f) {
    const [p, g] = f === "beforeChildren" ? [u, c] : [c, u];
    return p().then(() => g());
  } else
    return Promise.all([u(), c(i.delay)]);
}
function p4(n, t, i = 0, a = 0, r = 0, u = 1, c) {
  const f = [];
  for (const m of n.variantChildren)
    m.notify("AnimationStart", t), f.push(py(m, t, {
      ...c,
      delay: i + (typeof a == "function" ? 0 : a) + uC(n.variantChildren, m, a, r, u)
    }).then(() => m.notify("AnimationComplete", t)));
  return Promise.all(f);
}
function g4(n, t, i = {}) {
  n.notify("AnimationStart", t);
  let a;
  if (Array.isArray(t)) {
    const r = t.map((u) => py(n, u, i));
    a = Promise.all(r);
  } else if (typeof t == "string")
    a = py(n, t, i);
  else {
    const r = typeof t == "function" ? Mo(n, t, i.custom) : t;
    a = Promise.all(pC(n, r, i));
  }
  return a.then(() => {
    n.notify("AnimationComplete", t);
  });
}
const y4 = {
  test: (n) => n === "auto",
  parse: (n) => n
}, gC = (n) => (t) => t.test(n), yC = [Pl, ot, ki, Ii, GV, qV, y4], Z1 = (n) => yC.find(gC(n));
function v4(n) {
  return typeof n == "number" ? n === 0 : n !== null ? n === "none" || n === "0" || AT(n) : !0;
}
const b4 = /* @__PURE__ */ new Set(["brightness", "contrast", "saturate", "opacity"]);
function x4(n) {
  const [t, i] = n.slice(0, -1).split("(");
  if (t === "drop-shadow")
    return n;
  const [a] = i.match(cv) || [];
  if (!a)
    return n;
  const r = i.replace(a, "");
  let u = b4.has(t) ? 1 : 0;
  return a !== i && (u *= 100), t + "(" + u + r + ")";
}
const S4 = /\b([a-z-]*)\(.*?\)/gu, gy = {
  ...ei,
  getAnimatableNone: (n) => {
    const t = n.match(S4);
    return t ? t.map(x4).join(" ") : n;
  }
}, yy = {
  ...ei,
  getAnimatableNone: (n) => {
    const t = ei.parse(n);
    return ei.createTransformer(n)(t.map((a) => typeof a == "number" ? 0 : typeof a == "object" ? { ...a, alpha: 1 } : a));
  }
}, Q1 = {
  ...Pl,
  transform: Math.round
}, w4 = {
  rotate: Ii,
  /**
   * Internal channel for `transition.path` orientToPath. Composed onto
   * `rotate` at the transform-build sites so the user's `rotate` is
   * never read or overwritten. Not part of `transformPropOrder`.
   */
  pathRotation: Ii,
  rotateX: Ii,
  rotateY: Ii,
  rotateZ: Ii,
  scale: Oh,
  scaleX: Oh,
  scaleY: Oh,
  scaleZ: Oh,
  skew: Ii,
  skewX: Ii,
  skewY: Ii,
  distance: ot,
  translateX: ot,
  translateY: ot,
  translateZ: ot,
  x: ot,
  y: ot,
  z: ot,
  perspective: ot,
  transformPerspective: ot,
  opacity: lc,
  originX: P1,
  originY: P1,
  originZ: ot
}, id = {
  // Border props
  borderWidth: ot,
  borderTopWidth: ot,
  borderRightWidth: ot,
  borderBottomWidth: ot,
  borderLeftWidth: ot,
  borderRadius: ot,
  borderTopLeftRadius: ot,
  borderTopRightRadius: ot,
  borderBottomRightRadius: ot,
  borderBottomLeftRadius: ot,
  // Positioning props
  width: ot,
  maxWidth: ot,
  height: ot,
  maxHeight: ot,
  top: ot,
  right: ot,
  bottom: ot,
  left: ot,
  inset: ot,
  insetBlock: ot,
  insetBlockStart: ot,
  insetBlockEnd: ot,
  insetInline: ot,
  insetInlineStart: ot,
  insetInlineEnd: ot,
  // Spacing props
  padding: ot,
  paddingTop: ot,
  paddingRight: ot,
  paddingBottom: ot,
  paddingLeft: ot,
  paddingBlock: ot,
  paddingBlockStart: ot,
  paddingBlockEnd: ot,
  paddingInline: ot,
  paddingInlineStart: ot,
  paddingInlineEnd: ot,
  margin: ot,
  marginTop: ot,
  marginRight: ot,
  marginBottom: ot,
  marginLeft: ot,
  marginBlock: ot,
  marginBlockStart: ot,
  marginBlockEnd: ot,
  marginInline: ot,
  marginInlineStart: ot,
  marginInlineEnd: ot,
  // Typography
  fontSize: ot,
  // Misc
  backgroundPositionX: ot,
  backgroundPositionY: ot,
  ...w4,
  zIndex: Q1,
  // SVG
  fillOpacity: lc,
  strokeOpacity: lc,
  numOctaves: Q1
}, M4 = {
  ...id,
  // Color props
  color: ve,
  backgroundColor: ve,
  outlineColor: ve,
  fill: ve,
  stroke: ve,
  // Border props
  borderColor: ve,
  borderTopColor: ve,
  borderRightColor: ve,
  borderBottomColor: ve,
  borderLeftColor: ve,
  filter: gy,
  WebkitFilter: gy,
  mask: yy,
  WebkitMask: yy
}, vC = (n) => M4[n], T4 = /* @__PURE__ */ new Set([gy, yy]);
function bC(n, t) {
  let i = vC(n);
  return T4.has(i) || (i = ei), i.getAnimatableNone ? i.getAnimatableNone(t) : void 0;
}
const C4 = /* @__PURE__ */ new Set(["auto", "none", "0"]);
function E4(n, t, i) {
  let a = 0, r;
  for (; a < n.length && !r; ) {
    const u = n[a];
    typeof u == "string" && !C4.has(u) && zl(u).values.length && (r = n[a]), a++;
  }
  if (r && i)
    for (const u of t)
      n[u] = bC(i, r);
}
class A4 extends pv {
  constructor(t, i, a, r, u) {
    super(t, i, a, r, u, !0);
  }
  readKeyframes() {
    const { unresolvedKeyframes: t, element: i, name: a } = this;
    if (!i || !i.current)
      return;
    super.readKeyframes();
    for (let g = 0; g < t.length; g++) {
      let y = t[g];
      if (typeof y == "string" && (y = y.trim(), uv(y))) {
        const b = fC(y, i.current);
        b !== void 0 && (t[g] = b), g === t.length - 1 && (this.finalKeyframe = y);
      }
    }
    if (this.resolveNoneKeyframes(), !hC.has(a) || t.length !== 2)
      return;
    const [r, u] = t, c = Z1(r), f = Z1(u), m = V1(r), p = V1(u);
    if (m !== p && aa[a]) {
      this.needsMeasurement = !0;
      return;
    }
    if (c !== f)
      if (q1(c) && q1(f))
        for (let g = 0; g < t.length; g++) {
          const y = t[g];
          typeof y == "string" && (t[g] = parseFloat(y));
        }
      else aa[a] && (this.needsMeasurement = !0);
  }
  resolveNoneKeyframes() {
    const { unresolvedKeyframes: t, name: i } = this, a = [];
    for (let r = 0; r < t.length; r++)
      (t[r] === null || v4(t[r])) && a.push(r);
    a.length && E4(t, a, i);
  }
  measureInitialState() {
    const { element: t, unresolvedKeyframes: i, name: a } = this;
    if (!t || !t.current)
      return;
    a === "height" && (this.suspendedScrollY = window.pageYOffset), this.measuredOrigin = aa[a](t.measureViewportBox(), window.getComputedStyle(t.current)), i[0] = this.measuredOrigin;
    const r = i[i.length - 1];
    r !== void 0 && t.getValue(a, r).jump(r, !1);
  }
  measureEndState() {
    var f;
    const { element: t, name: i, unresolvedKeyframes: a } = this;
    if (!t || !t.current)
      return;
    const r = t.getValue(i);
    r && r.jump(this.measuredOrigin, !1);
    const u = a.length - 1, c = a[u];
    a[u] = aa[i](t.measureViewportBox(), window.getComputedStyle(t.current)), c !== null && this.finalKeyframe === void 0 && (this.finalKeyframe = c), (f = this.removedTransforms) != null && f.length && this.removedTransforms.forEach(([m, p]) => {
      t.getValue(m).set(p);
    }), this.resolveNoneKeyframes();
  }
}
const xv = [
  "borderTopLeftRadius",
  "borderTopRightRadius",
  "borderBottomRightRadius",
  "borderBottomLeftRadius"
];
function Sv(n, t, i) {
  if (n == null)
    return [];
  if (n instanceof EventTarget)
    return [n];
  if (typeof n == "string") {
    const r = document.querySelectorAll(n);
    return r ? Array.from(r) : [];
  }
  return Array.from(n).filter((a) => a != null);
}
const vy = (n, t) => t && typeof n == "number" ? t.transform(n) : n;
function qh(n) {
  return ET(n) && "offsetHeight" in n && !("ownerSVGElement" in n);
}
const { schedule: wv } = /* @__PURE__ */ jT(queueMicrotask, !1), In = {
  x: !1,
  y: !1
};
function xC() {
  return In.x || In.y;
}
function D4(n) {
  return n === "x" || n === "y" ? In[n] ? null : (In[n] = !0, () => {
    In[n] = !1;
  }) : In.x || In.y ? null : (In.x = In.y = !0, () => {
    In.x = In.y = !1;
  });
}
function SC(n, t) {
  const i = Sv(n), a = new AbortController(), r = {
    passive: !0,
    ...t,
    signal: a.signal
  };
  return [i, r, () => a.abort()];
}
function R4(n) {
  return !(n.pointerType === "touch" || xC());
}
function O4(n, t, i = {}) {
  const [a, r, u] = SC(n, i);
  return a.forEach((c) => {
    let f = !1, m = !1, p;
    const g = () => {
      c.removeEventListener("pointerleave", T);
    }, y = (R) => {
      p && (p(R), p = void 0), g();
    }, b = (R) => {
      f = !1, window.removeEventListener("pointerup", b), window.removeEventListener("pointercancel", b), m && (m = !1, y(R));
    }, S = () => {
      f = !0, window.addEventListener("pointerup", b, r), window.addEventListener("pointercancel", b, r);
    }, T = (R) => {
      if (R.pointerType !== "touch") {
        if (f) {
          m = !0;
          return;
        }
        y(R);
      }
    }, C = (R) => {
      if (!R4(R))
        return;
      m = !1;
      const z = t(c, R);
      typeof z == "function" && (p = z, c.addEventListener("pointerleave", T, r));
    };
    c.addEventListener("pointerenter", C, r), c.addEventListener("pointerdown", S, r);
  }), u;
}
const wC = (n, t) => t ? n === t ? !0 : wC(n, t.parentElement) : !1, Mv = (n) => n.pointerType === "mouse" ? typeof n.button != "number" || n.button <= 0 : n.isPrimary !== !1, z4 = /* @__PURE__ */ new Set([
  "BUTTON",
  "INPUT",
  "SELECT",
  "TEXTAREA",
  "A"
]);
function k4(n) {
  return z4.has(n.tagName) || n.isContentEditable === !0;
}
const V4 = /* @__PURE__ */ new Set(["INPUT", "SELECT", "TEXTAREA"]);
function P4(n) {
  return V4.has(n.tagName) || n.isContentEditable === !0;
}
const Gh = /* @__PURE__ */ new WeakSet();
function K1(n) {
  return (t) => {
    t.key === "Enter" && n(t);
  };
}
function Tg(n, t) {
  n.dispatchEvent(new PointerEvent("pointer" + t, { isPrimary: !0, bubbles: !0 }));
}
const L4 = (n, t) => {
  const i = n.currentTarget;
  if (!i)
    return;
  const a = K1(() => {
    if (Gh.has(i))
      return;
    Tg(i, "down");
    const r = K1(() => {
      Tg(i, "up");
    }), u = () => Tg(i, "cancel");
    i.addEventListener("keyup", r, t), i.addEventListener("blur", u, t);
  });
  i.addEventListener("keydown", a, t), i.addEventListener("blur", () => i.removeEventListener("keydown", a), t);
};
function I1(n) {
  return Mv(n) && !xC();
}
const $1 = /* @__PURE__ */ new WeakSet();
function _4(n, t, i = {}) {
  const [a, r, u] = SC(n, i), c = (f) => {
    const m = f.currentTarget;
    if (!I1(f) || $1.has(f))
      return;
    Gh.add(m), i.stopPropagation && $1.add(f);
    const p = t(m, f), g = { ...r, capture: !0 }, y = (T, C) => {
      window.removeEventListener("pointerup", b, g), window.removeEventListener("pointercancel", S, g), Gh.has(m) && Gh.delete(m), I1(T) && typeof p == "function" && p(T, { success: C });
    }, b = (T) => {
      y(T, m === window || m === document || i.useGlobalTarget || wC(m, T.target));
    }, S = (T) => {
      y(T, !1);
    };
    window.addEventListener("pointerup", b, g), window.addEventListener("pointercancel", S, g);
  };
  return a.forEach((f) => {
    (i.useGlobalTarget ? window : f).addEventListener("pointerdown", c, r), qh(f) && (f.addEventListener("focus", (p) => L4(p, r)), !k4(f) && !f.hasAttribute("tabindex") && (f.tabIndex = 0));
  }), u;
}
function Tv(n) {
  return ET(n) && "ownerSVGElement" in n;
}
const Yh = /* @__PURE__ */ new WeakMap();
let As;
const MC = (n, t, i) => (a, r) => r && r[0] ? r[0][n + "Size"] : Tv(a) && "getBBox" in a ? a.getBBox()[t] : a[i], B4 = /* @__PURE__ */ MC("inline", "width", "offsetWidth"), N4 = /* @__PURE__ */ MC("block", "height", "offsetHeight");
function U4({ target: n, borderBoxSize: t }) {
  var i;
  (i = Yh.get(n)) == null || i.forEach((a) => {
    a(n, {
      get width() {
        return B4(n, t);
      },
      get height() {
        return N4(n, t);
      }
    });
  });
}
function j4(n) {
  n.forEach(U4);
}
function H4() {
  typeof ResizeObserver > "u" || (As = new ResizeObserver(j4));
}
function q4(n, t) {
  As || H4();
  const i = Sv(n);
  return i.forEach((a) => {
    let r = Yh.get(a);
    r || (r = /* @__PURE__ */ new Set(), Yh.set(a, r)), r.add(t), As == null || As.observe(a);
  }), () => {
    i.forEach((a) => {
      const r = Yh.get(a);
      r == null || r.delete(t), r != null && r.size || As == null || As.unobserve(a);
    });
  };
}
const Xh = /* @__PURE__ */ new Set();
let Vr;
function G4() {
  Vr = () => {
    const n = {
      get width() {
        return window.innerWidth;
      },
      get height() {
        return window.innerHeight;
      }
    };
    Xh.forEach((t) => t(n));
  }, window.addEventListener("resize", Vr);
}
function Y4(n) {
  return Xh.add(n), Vr || G4(), () => {
    Xh.delete(n), !Xh.size && typeof Vr == "function" && (window.removeEventListener("resize", Vr), Vr = void 0);
  };
}
function W1(n, t) {
  return typeof n == "function" ? Y4(n) : q4(n, t);
}
function X4(n) {
  return Tv(n) && n.tagName === "svg";
}
function F4(...n) {
  const t = !Array.isArray(n[0]), i = t ? 0 : -1, a = n[0 + i], r = n[1 + i], u = n[2 + i], c = n[3 + i], f = $T(r, u, c);
  return t ? f(a) : f;
}
function Z4(n, t, i = {}) {
  const a = n.get();
  let r = null, u = a, c;
  const f = typeof a == "string" ? a.replace(/[\d.-]/g, "") : void 0, m = () => {
    r && (r.stop(), r = null), n.animation = void 0;
  }, p = () => {
    const y = J1(n.get()), b = J1(u);
    if (y === b) {
      m();
      return;
    }
    const S = r ? r.getGeneratorVelocity() : n.getVelocity();
    m(), r = new uc({
      keyframes: [y, b],
      velocity: S,
      // Default to spring if no type specified (matches useSpring behavior)
      type: "spring",
      restDelta: 1e-3,
      restSpeed: 0.01,
      ...i,
      onUpdate: c
    });
  }, g = () => {
    var y;
    p(), n.animation = r ?? void 0, (y = n.events.animationStart) == null || y.notify(), r == null || r.then(() => {
      var b;
      n.animation = void 0, (b = n.events.animationComplete) == null || b.notify();
    });
  };
  if (n.attach((y, b) => {
    u = y, c = (S) => b(Cg(S, f)), jt.postRender(g);
  }, m), de(t)) {
    let y = i.skipInitialAnimation === !0;
    const b = t.on("change", (T) => {
      y ? (y = !1, n.jump(Cg(T, f), !1)) : n.set(Cg(T, f));
    }), S = n.on("destroy", b);
    return () => {
      b(), S();
    };
  }
  return m;
}
function Cg(n, t) {
  return t ? n + t : n;
}
function J1(n) {
  return typeof n == "number" ? n : parseFloat(n);
}
const Q4 = [...yC, ve, ei], K4 = (n) => Q4.find(gC(n)), tw = () => ({
  translate: 0,
  scale: 1,
  origin: 0,
  originPoint: 0
}), Pr = () => ({
  x: tw(),
  y: tw()
}), ew = () => ({ min: 0, max: 0 }), we = () => ({
  x: ew(),
  y: ew()
}), I4 = /* @__PURE__ */ new WeakMap();
function Od(n) {
  return n !== null && typeof n == "object" && typeof n.start == "function";
}
function cc(n) {
  return typeof n == "string" || Array.isArray(n);
}
const Cv = [
  "animate",
  "whileInView",
  "whileFocus",
  "whileHover",
  "whileTap",
  "whileDrag",
  "exit"
], Ev = ["initial", ...Cv];
function zd(n) {
  return Od(n.animate) || Ev.some((t) => cc(n[t]));
}
function TC(n) {
  return !!(zd(n) || n.variants);
}
function $4(n, t, i) {
  for (const a in t) {
    const r = t[a], u = i[a];
    if (de(r))
      n.addValue(a, r);
    else if (de(u))
      n.addValue(a, Lo(r, { owner: n }));
    else if (u !== r)
      if (n.hasValue(a)) {
        const c = n.getValue(a);
        c.liveStyle === !0 ? c.jump(r) : c.hasAnimated || c.set(r);
      } else {
        const c = n.getStaticValue(a);
        n.addValue(a, Lo(c !== void 0 ? c : r, { owner: n }));
      }
  }
  for (const a in i)
    t[a] === void 0 && n.removeValue(a);
  return t;
}
const by = { current: null }, CC = { current: !1 }, W4 = typeof window < "u";
function J4() {
  if (CC.current = !0, !!W4)
    if (window.matchMedia) {
      const n = window.matchMedia("(prefers-reduced-motion)"), t = () => by.current = n.matches;
      n.addEventListener("change", t), t();
    } else
      by.current = !1;
}
const nw = [
  "AnimationStart",
  "AnimationComplete",
  "Update",
  "BeforeLayoutMeasure",
  "LayoutMeasure",
  "LayoutAnimationStart",
  "LayoutAnimationComplete"
];
let sd = {};
function EC(n) {
  sd = n;
}
function tL() {
  return sd;
}
class eL {
  /**
   * This method takes React props and returns found MotionValues. For example, HTML
   * MotionValues will be found within the style prop, whereas for Three.js within attribute arrays.
   *
   * This isn't an abstract method as it needs calling in the constructor, but it is
   * intended to be one.
   */
  scrapeMotionValuesFromProps(t, i, a) {
    return {};
  }
  constructor({ parent: t, props: i, presenceContext: a, reducedMotionConfig: r, skipAnimations: u, blockInitialAnimation: c, visualState: f }, m = {}) {
    this.current = null, this.children = /* @__PURE__ */ new Set(), this.isVariantNode = !1, this.isControllingVariants = !1, this.shouldReduceMotion = null, this.shouldSkipAnimations = !1, this.values = /* @__PURE__ */ new Map(), this.KeyframeResolver = pv, this.features = {}, this.valueSubscriptions = /* @__PURE__ */ new Map(), this.prevMotionValues = {}, this.hasBeenMounted = !1, this.events = {}, this.propEventSubscriptions = {}, this.notifyUpdate = () => this.notify("Update", this.latestValues), this.render = () => {
      this.current && (this.triggerBuild(), this.renderInstance(this.current, this.renderState, this.props.style, this.projection));
    }, this.renderScheduledAt = 0, this.scheduleRender = () => {
      const S = Ke.now();
      this.renderScheduledAt < S && (this.renderScheduledAt = S, jt.render(this.render, !1, !0));
    };
    const { latestValues: p, renderState: g } = f;
    this.latestValues = p, this.baseTarget = { ...p }, this.initialValues = i.initial ? { ...p } : {}, this.renderState = g, this.parent = t, this.props = i, this.presenceContext = a, this.depth = t ? t.depth + 1 : 0, this.reducedMotionConfig = r, this.skipAnimationsConfig = u, this.options = m, this.blockInitialAnimation = !!c, this.isControllingVariants = zd(i), this.isVariantNode = TC(i), this.isVariantNode && (this.variantChildren = /* @__PURE__ */ new Set()), this.manuallyAnimateOnMount = !!(t && t.current);
    const { willChange: y, ...b } = this.scrapeMotionValuesFromProps(i, {}, this);
    for (const S in b) {
      const T = b[S];
      p[S] !== void 0 && de(T) && T.set(p[S]);
    }
  }
  mount(t) {
    var i, a;
    if (this.hasBeenMounted)
      for (const r in this.initialValues)
        (i = this.values.get(r)) == null || i.jump(this.initialValues[r]), this.latestValues[r] = this.initialValues[r];
    this.current = t, I4.set(t, this), this.projection && !this.projection.instance && this.projection.mount(t), this.parent && this.isVariantNode && !this.isControllingVariants && (this.removeFromVariantTree = this.parent.addVariantChild(this)), this.values.forEach((r, u) => this.bindToMotionValue(u, r)), this.reducedMotionConfig === "never" ? this.shouldReduceMotion = !1 : this.reducedMotionConfig === "always" ? this.shouldReduceMotion = !0 : (CC.current || J4(), this.shouldReduceMotion = by.current), this.shouldSkipAnimations = this.skipAnimationsConfig ?? !1, (a = this.parent) == null || a.addChild(this), this.update(this.props, this.presenceContext), this.hasBeenMounted = !0;
  }
  unmount() {
    var t;
    this.projection && this.projection.unmount(), Wi(this.notifyUpdate), Wi(this.render), this.valueSubscriptions.forEach((i) => i()), this.valueSubscriptions.clear(), this.removeFromVariantTree && this.removeFromVariantTree(), (t = this.parent) == null || t.removeChild(this);
    for (const i in this.events)
      this.events[i].clear();
    for (const i in this.features) {
      const a = this.features[i];
      a && (a.unmount(), a.isMounted = !1);
    }
    this.current = null;
  }
  addChild(t) {
    this.children.add(t), this.enteringChildren ?? (this.enteringChildren = /* @__PURE__ */ new Set()), this.enteringChildren.add(t);
  }
  removeChild(t) {
    this.children.delete(t), this.enteringChildren && this.enteringChildren.delete(t);
  }
  bindToMotionValue(t, i) {
    if (this.valueSubscriptions.has(t) && this.valueSubscriptions.get(t)(), i.accelerate && lC.has(t) && this.current instanceof HTMLElement) {
      const { factory: c, keyframes: f, times: m, ease: p, duration: g } = i.accelerate, y = new oC({
        element: this.current,
        name: t,
        keyframes: f,
        times: m,
        ease: p,
        duration: /* @__PURE__ */ rn(g)
      }), b = c(y);
      this.valueSubscriptions.set(t, () => {
        b(), y.cancel();
      });
      return;
    }
    const a = _l.has(t);
    a && this.onBindTransform && this.onBindTransform();
    const r = i.on("change", (c) => {
      this.latestValues[t] = c, this.props.onUpdate && jt.preRender(this.notifyUpdate), a && this.projection && (this.projection.isTransformDirty = !0), this.scheduleRender();
    });
    let u;
    typeof window < "u" && window.MotionCheckAppearSync && (u = window.MotionCheckAppearSync(this, t, i)), this.valueSubscriptions.set(t, () => {
      r(), u && u();
    });
  }
  sortNodePosition(t) {
    return !this.current || !this.sortInstanceNodePosition || this.type !== t.type ? 0 : this.sortInstanceNodePosition(this.current, t.current);
  }
  updateFeatures() {
    let t = "animation";
    for (t in sd) {
      const i = sd[t];
      if (!i)
        continue;
      const { isEnabled: a, Feature: r } = i;
      if (!this.features[t] && r && a(this.props) && (this.features[t] = new r(this)), this.features[t]) {
        const u = this.features[t];
        u.isMounted ? u.update() : (u.mount(), u.isMounted = !0);
      }
    }
  }
  triggerBuild() {
    this.build(this.renderState, this.latestValues, this.props);
  }
  /**
   * Measure the current viewport box with or without transforms.
   * Only measures axis-aligned boxes, rotate and skew must be manually
   * removed with a re-render to work.
   */
  measureViewportBox() {
    return this.current ? this.measureInstanceViewportBox(this.current, this.props) : we();
  }
  getStaticValue(t) {
    return this.latestValues[t];
  }
  setStaticValue(t, i) {
    this.latestValues[t] = i;
  }
  /**
   * Update the provided props. Ensure any newly-added motion values are
   * added to our map, old ones removed, and listeners updated.
   */
  update(t, i) {
    (t.transformTemplate || this.props.transformTemplate) && this.scheduleRender(), this.prevProps = this.props, this.props = t, this.prevPresenceContext = this.presenceContext, this.presenceContext = i;
    for (let a = 0; a < nw.length; a++) {
      const r = nw[a];
      this.propEventSubscriptions[r] && (this.propEventSubscriptions[r](), delete this.propEventSubscriptions[r]);
      const u = "on" + r, c = t[u];
      c && (this.propEventSubscriptions[r] = this.on(r, c));
    }
    this.prevMotionValues = $4(this, this.scrapeMotionValuesFromProps(t, this.prevProps || {}, this), this.prevMotionValues), this.handleChildMotionValue && this.handleChildMotionValue();
  }
  getProps() {
    return this.props;
  }
  /**
   * Returns the variant definition with a given name.
   */
  getVariant(t) {
    return this.props.variants ? this.props.variants[t] : void 0;
  }
  /**
   * Returns the defined default transition on this component.
   */
  getDefaultTransition() {
    return this.props.transition;
  }
  getTransformPagePoint() {
    return this.props.transformPagePoint;
  }
  getClosestVariantNode() {
    return this.isVariantNode ? this : this.parent ? this.parent.getClosestVariantNode() : void 0;
  }
  /**
   * Add a child visual element to our set of children.
   */
  addVariantChild(t) {
    const i = this.getClosestVariantNode();
    if (i)
      return i.variantChildren && i.variantChildren.add(t), () => i.variantChildren.delete(t);
  }
  /**
   * Add a motion value and bind it to this visual element.
   */
  addValue(t, i) {
    const a = this.values.get(t);
    i !== a && (a && this.removeValue(t), this.bindToMotionValue(t, i), this.values.set(t, i), this.latestValues[t] = i.get());
  }
  /**
   * Remove a motion value and unbind any active subscriptions.
   */
  removeValue(t) {
    this.values.delete(t);
    const i = this.valueSubscriptions.get(t);
    i && (i(), this.valueSubscriptions.delete(t)), delete this.latestValues[t], this.removeValueFromRenderState(t, this.renderState);
  }
  /**
   * Check whether we have a motion value for this key
   */
  hasValue(t) {
    return this.values.has(t);
  }
  getValue(t, i) {
    if (this.props.values && this.props.values[t])
      return this.props.values[t];
    let a = this.values.get(t);
    return a === void 0 && i !== void 0 && (a = Lo(i === null ? void 0 : i, { owner: this }), this.addValue(t, a)), a;
  }
  /**
   * If we're trying to animate to a previously unencountered value,
   * we need to check for it in our state and as a last resort read it
   * directly from the instance (which might have performance implications).
   */
  readValue(t, i) {
    let a = this.latestValues[t] !== void 0 || !this.current ? this.latestValues[t] : this.getBaseTargetFromProps(this.props, t) ?? this.readValueFromInstance(this.current, t, this.options);
    return a != null && (typeof a == "string" && (CT(a) || AT(a)) ? a = parseFloat(a) : !K4(a) && ei.test(i) && (a = bC(t, i)), this.setBaseTarget(t, de(a) ? a.get() : a)), de(a) ? a.get() : a;
  }
  /**
   * Set the base target to later animate back to. This is currently
   * only hydrated on creation and when we first read a value.
   */
  setBaseTarget(t, i) {
    this.baseTarget[t] = i;
  }
  /**
   * Find the base target for a value thats been removed from all animation
   * props.
   */
  getBaseTarget(t) {
    var u;
    const { initial: i } = this.props;
    let a;
    if (typeof i == "string" || typeof i == "object") {
      const c = vv(this.props, i, (u = this.presenceContext) == null ? void 0 : u.custom);
      c && (a = c[t]);
    }
    if (i && a !== void 0)
      return a;
    const r = this.getBaseTargetFromProps(this.props, t);
    return r !== void 0 && !de(r) ? r : this.initialValues[t] !== void 0 && a === void 0 ? void 0 : this.baseTarget[t];
  }
  on(t, i) {
    return this.events[t] || (this.events[t] = new ov()), this.events[t].add(i);
  }
  notify(t, ...i) {
    this.events[t] && this.events[t].notify(...i);
  }
  scheduleRenderMicrotask() {
    wv.render(this.render);
  }
}
class AC extends eL {
  constructor() {
    super(...arguments), this.KeyframeResolver = A4;
  }
  sortInstanceNodePosition(t, i) {
    return t.compareDocumentPosition(i) & 2 ? 1 : -1;
  }
  getBaseTargetFromProps(t, i) {
    const a = t.style;
    return a ? a[i] : void 0;
  }
  removeValueFromRenderState(t, { vars: i, style: a }) {
    delete i[t], delete a[t];
  }
  handleChildMotionValue() {
    this.childSubscription && (this.childSubscription(), delete this.childSubscription);
    const { children: t } = this.props;
    de(t) && (this.childSubscription = t.on("change", (i) => {
      this.current && (this.current.textContent = `${i}`);
    }));
  }
}
class fa {
  constructor(t) {
    this.isMounted = !1, this.node = t;
  }
  update() {
  }
}
function DC({ top: n, left: t, right: i, bottom: a }) {
  return {
    x: { min: t, max: i },
    y: { min: n, max: a }
  };
}
function nL({ x: n, y: t }) {
  return { top: t.min, right: n.max, bottom: t.max, left: n.min };
}
function iL(n, t) {
  if (!t)
    return n;
  const i = t({ x: n.left, y: n.top }), a = t({ x: n.right, y: n.bottom });
  return {
    top: i.y,
    left: i.x,
    bottom: a.y,
    right: a.x
  };
}
function Eg(n) {
  return n === void 0 || n === 1;
}
function xy({ scale: n, scaleX: t, scaleY: i }) {
  return !Eg(n) || !Eg(t) || !Eg(i);
}
function Pa(n) {
  return xy(n) || RC(n) || n.z || n.rotate || n.rotateX || n.rotateY || n.skewX || n.skewY;
}
function RC(n) {
  return iw(n.x) || iw(n.y);
}
function iw(n) {
  return n && n !== "0%";
}
function ad(n, t, i) {
  const a = n - i, r = t * a;
  return i + r;
}
function sw(n, t, i, a, r) {
  return r !== void 0 && (n = ad(n, r, a)), ad(n, i, a) + t;
}
function Sy(n, t = 0, i = 1, a, r) {
  n.min = sw(n.min, t, i, a, r), n.max = sw(n.max, t, i, a, r);
}
function OC(n, { x: t, y: i }) {
  Sy(n.x, t.translate, t.scale, t.originPoint), Sy(n.y, i.translate, i.scale, i.originPoint);
}
const aw = 0.999999999999, ow = 1.0000000000001;
function sL(n, t, i, a = !1) {
  var f;
  const r = i.length;
  if (!r)
    return;
  t.x = t.y = 1;
  let u, c;
  for (let m = 0; m < r; m++) {
    u = i[m], c = u.projectionDelta;
    const { visualElement: p } = u.options;
    p && p.props.style && p.props.style.display === "contents" || (a && u.options.layoutScroll && u.scroll && u !== u.root && (Ri(n.x, -u.scroll.offset.x), Ri(n.y, -u.scroll.offset.y)), c && (t.x *= c.x.scale, t.y *= c.y.scale, OC(n, c)), a && Pa(u.latestValues) && Fh(n, u.latestValues, (f = u.layout) == null ? void 0 : f.layoutBox));
  }
  t.x < ow && t.x > aw && (t.x = 1), t.y < ow && t.y > aw && (t.y = 1);
}
function Ri(n, t) {
  n.min += t, n.max += t;
}
function rw(n, t, i, a, r = 0.5) {
  const u = Ft(n.min, n.max, r);
  Sy(n, t, i, u, a);
}
function lw(n, t) {
  return typeof n == "string" ? parseFloat(n) / 100 * (t.max - t.min) : n;
}
function Fh(n, t, i) {
  const a = i ?? n;
  rw(n.x, lw(t.x, a.x), t.scaleX, t.scale, t.originX), rw(n.y, lw(t.y, a.y), t.scaleY, t.scale, t.originY);
}
function zC(n, t) {
  return DC(iL(n.getBoundingClientRect(), t));
}
function aL(n, t, i) {
  const a = zC(n, i), { scroll: r } = t;
  return r && (Ri(a.x, r.offset.x), Ri(a.y, r.offset.y)), a;
}
const oL = {
  x: "translateX",
  y: "translateY",
  z: "translateZ",
  transformPerspective: "perspective"
}, rL = Ll.length;
function lL(n, t, i) {
  let a = "", r = !0;
  for (let c = 0; c < rL; c++) {
    const f = Ll[c], m = n[f];
    if (m === void 0)
      continue;
    let p = !0;
    if (typeof m == "number")
      p = m === (f.startsWith("scale") ? 1 : 0);
    else {
      const g = parseFloat(m);
      p = f.startsWith("scale") ? g === 1 : g === 0;
    }
    if (!p || i) {
      const g = vy(m, id[f]);
      if (!p) {
        r = !1;
        const y = oL[f] || f;
        a += `${y}(${g}) `;
      }
      i && (t[f] = g);
    }
  }
  const u = n.pathRotation;
  return u && (r = !1, a += `rotate(${vy(u, id.pathRotation)}) `), a = a.trim(), i ? a = i(t, r ? "" : a) : r && (a = "none"), a;
}
function Av(n, t, i) {
  const { style: a, vars: r, transformOrigin: u } = n;
  let c = !1, f = !1;
  for (const m in t) {
    const p = t[m];
    if (_l.has(m)) {
      c = !0;
      continue;
    } else if (qT(m)) {
      r[m] = p;
      continue;
    } else {
      const g = vy(p, id[m]);
      m.startsWith("origin") ? (f = !0, u[m] = g) : a[m] = g;
    }
  }
  if (t.transform || (c || i ? a.transform = lL(t, n.transform, i) : a.transform && (a.transform = "none")), f) {
    const { originX: m = "50%", originY: p = "50%", originZ: g = 0 } = u;
    a.transformOrigin = `${m} ${p} ${g}`;
  }
}
function kC(n, { style: t, vars: i }, a, r) {
  const u = n.style;
  let c;
  for (c in t)
    u[c] = t[c];
  r == null || r.applyProjectionStyles(u, a);
  for (c in i)
    u.setProperty(c, i[c]);
}
function uw(n, t) {
  return t.max === t.min ? 0 : n / (t.max - t.min) * 100;
}
const Uu = {
  correct: (n, t) => {
    if (!t.target)
      return n;
    if (typeof n == "string")
      if (ot.test(n))
        n = parseFloat(n);
      else
        return n;
    const i = uw(n, t.target.x), a = uw(n, t.target.y);
    return `${i}% ${a}%`;
  }
}, uL = {
  correct: (n, { treeScale: t, projectionDelta: i }) => {
    const a = n, r = ei.parse(n);
    if (r.length > 5)
      return a;
    const u = ei.createTransformer(n), c = typeof r[0] != "number" ? 1 : 0, f = i.x.scale * t.x, m = i.y.scale * t.y;
    r[0 + c] /= f, r[1 + c] /= m;
    const p = Ft(f, m, 0.5);
    return typeof r[2 + c] == "number" && (r[2 + c] /= p), typeof r[3 + c] == "number" && (r[3 + c] /= p), u(r);
  }
}, wy = {
  borderRadius: {
    ...Uu,
    applyTo: [...xv]
  },
  borderTopLeftRadius: Uu,
  borderTopRightRadius: Uu,
  borderBottomLeftRadius: Uu,
  borderBottomRightRadius: Uu,
  boxShadow: uL
};
function VC(n, { layout: t, layoutId: i }) {
  return _l.has(n) || n.startsWith("origin") || (t || i !== void 0) && (!!wy[n] || n === "opacity");
}
function Dv(n, t, i) {
  var c;
  const a = n.style, r = t == null ? void 0 : t.style, u = {};
  if (!a)
    return u;
  for (const f in a)
    (de(a[f]) || r && de(r[f]) || VC(f, n) || ((c = i == null ? void 0 : i.getValue(f)) == null ? void 0 : c.liveStyle) !== void 0) && (u[f] = a[f]);
  return u;
}
function cL(n) {
  return window.getComputedStyle(n);
}
class fL extends AC {
  constructor() {
    super(...arguments), this.type = "html", this.renderInstance = kC;
  }
  mount(t) {
    ua(!!t.style, "motion.create() components must forward their ref to a HTML or SVG element", "custom-component-ref"), super.mount(t);
  }
  readValueFromInstance(t, i) {
    var a;
    if (_l.has(i))
      return (a = this.projection) != null && a.isProjecting ? ry(i) : DP(t, i);
    {
      const r = cL(t), u = (qT(i) ? r.getPropertyValue(i) : r[i]) || 0;
      return typeof u == "string" ? u.trim() : u;
    }
  }
  measureInstanceViewportBox(t, { transformPagePoint: i }) {
    return zC(t, i);
  }
  build(t, i, a) {
    Av(t, i, a.transformTemplate);
  }
  scrapeMotionValuesFromProps(t, i, a) {
    return Dv(t, i, a);
  }
}
const hL = {
  offset: "stroke-dashoffset",
  array: "stroke-dasharray"
}, dL = {
  offset: "strokeDashoffset",
  array: "strokeDasharray"
};
function mL(n, t, i = 1, a = 0, r = !0) {
  n.pathLength = 1;
  const u = r ? hL : dL;
  n[u.offset] = `${-a}`, n[u.array] = `${t} ${i}`;
}
const pL = [
  "offsetDistance",
  "offsetPath",
  "offsetRotate",
  "offsetAnchor"
];
function PC(n, {
  attrX: t,
  attrY: i,
  attrScale: a,
  pathLength: r,
  pathSpacing: u = 1,
  pathOffset: c = 0,
  // This is object creation, which we try to avoid per-frame.
  ...f
}, m, p, g) {
  if (Av(n, f, p), m) {
    n.style.viewBox && (n.attrs.viewBox = n.style.viewBox);
    return;
  }
  n.attrs = n.style, n.style = {};
  const { attrs: y, style: b } = n;
  y.transform && (b.transform = y.transform, delete y.transform), (b.transform || y.transformOrigin) && (b.transformOrigin = y.transformOrigin ?? "50% 50%", delete y.transformOrigin), b.transform && (b.transformBox = (g == null ? void 0 : g.transformBox) ?? "fill-box", delete y.transformBox);
  for (const S of pL)
    y[S] !== void 0 && (b[S] = y[S], delete y[S]);
  t !== void 0 && (y.x = t), i !== void 0 && (y.y = i), a !== void 0 && (y.scale = a), r !== void 0 && mL(y, r, u, c, !1);
}
const LC = /* @__PURE__ */ new Set([
  "baseFrequency",
  "diffuseConstant",
  "kernelMatrix",
  "kernelUnitLength",
  "keySplines",
  "keyTimes",
  "limitingConeAngle",
  "markerHeight",
  "markerWidth",
  "numOctaves",
  "targetX",
  "targetY",
  "surfaceScale",
  "specularConstant",
  "specularExponent",
  "stdDeviation",
  "tableValues",
  "viewBox",
  "gradientTransform",
  "pathLength",
  "startOffset",
  "textLength",
  "lengthAdjust"
]), _C = (n) => typeof n == "string" && n.toLowerCase() === "svg";
function gL(n, t, i, a) {
  kC(n, t, void 0, a);
  for (const r in t.attrs)
    n.setAttribute(LC.has(r) ? r : bv(r), t.attrs[r]);
}
function BC(n, t, i) {
  const a = Dv(n, t, i);
  for (const r in n)
    if (de(n[r]) || de(t[r])) {
      const u = Ll.indexOf(r) !== -1 ? "attr" + r.charAt(0).toUpperCase() + r.substring(1) : r;
      a[u] = n[r];
    }
  return a;
}
class yL extends AC {
  constructor() {
    super(...arguments), this.type = "svg", this.isSVGTag = !1, this.measureInstanceViewportBox = we;
  }
  getBaseTargetFromProps(t, i) {
    return t[i];
  }
  readValueFromInstance(t, i) {
    if (_l.has(i)) {
      const a = vC(i);
      return a && a.default || 0;
    }
    return i = LC.has(i) ? i : bv(i), t.getAttribute(i);
  }
  scrapeMotionValuesFromProps(t, i, a) {
    return BC(t, i, a);
  }
  build(t, i, a) {
    PC(t, i, this.isSVGTag, a.transformTemplate, a.style);
  }
  renderInstance(t, i, a, r) {
    gL(t, i, a, r);
  }
  mount(t) {
    this.isSVGTag = _C(t.tagName), super.mount(t);
  }
}
const vL = Ev.length;
function NC(n) {
  if (!n)
    return;
  if (!n.isControllingVariants) {
    const i = n.parent ? NC(n.parent) || {} : {};
    return n.props.initial !== void 0 && (i.initial = n.props.initial), i;
  }
  const t = {};
  for (let i = 0; i < vL; i++) {
    const a = Ev[i], r = n.props[a];
    (cc(r) || r === !1) && (t[a] = r);
  }
  return t;
}
function UC(n, t) {
  if (!Array.isArray(t))
    return !1;
  const i = t.length;
  if (i !== n.length)
    return !1;
  for (let a = 0; a < i; a++)
    if (t[a] !== n[a])
      return !1;
  return !0;
}
const bL = [...Cv].reverse(), xL = Cv.length;
function SL(n) {
  return (t) => Promise.all(t.map(({ animation: i, options: a }) => g4(n, i, a)));
}
function wL(n) {
  let t = SL(n), i = cw(), a = !0, r = !1;
  const u = (p) => (g, y) => {
    var S;
    const b = Mo(n, y, p === "exit" ? (S = n.presenceContext) == null ? void 0 : S.custom : void 0);
    if (b) {
      const { transition: T, transitionEnd: C, ...R } = b;
      g = { ...g, ...R, ...C };
    }
    return g;
  };
  function c(p) {
    t = p(n);
  }
  function f(p) {
    const { props: g } = n, y = NC(n.parent) || {}, b = [], S = /* @__PURE__ */ new Set();
    let T = {}, C = 1 / 0;
    for (let z = 0; z < xL; z++) {
      const B = bL[z], H = i[B], X = g[B] !== void 0 ? g[B] : y[B], Q = cc(X), ut = B === p ? H.isActive : null;
      ut === !1 && (C = z);
      let st = X === y[B] && X !== g[B] && Q;
      if (st && (a || r) && n.manuallyAnimateOnMount && (st = !1), H.protectedKeys = { ...T }, // If it isn't active and hasn't *just* been set as inactive
      !H.isActive && ut === null || // If we didn't and don't have any defined prop for this animation type
      !X && !H.prevProp || // Or if the prop doesn't define an animation
      Od(X) || typeof X == "boolean")
        continue;
      if (B === "exit" && H.isActive && ut !== !0) {
        H.prevResolvedValues && (T = {
          ...T,
          ...H.prevResolvedValues
        });
        continue;
      }
      const $ = ML(H.prevProp, X);
      let lt = $ || // If we're making this variant active, we want to always make it active
      B === p && H.isActive && !st && Q || // If we removed a higher-priority variant (i is in reverse order)
      z > C && Q, nt = !1;
      const vt = Array.isArray(X) ? X : [X];
      let it = vt.reduce(u(B), {});
      ut === !1 && (it = {});
      const { prevResolvedValues: ie = {} } = H, Kt = {
        ...ie,
        ...it
      }, zt = (J) => {
        lt = !0, S.has(J) && (nt = !0, S.delete(J)), H.needsAnimating[J] = !0;
        const ft = n.getValue(J);
        ft && (ft.liveStyle = !1);
      };
      for (const J in Kt) {
        const ft = it[J], D = ie[J];
        if (T.hasOwnProperty(J))
          continue;
        let Y = !1;
        dy(ft) && dy(D) ? Y = !UC(ft, D) || $ : Y = ft !== D, Y ? ft != null ? zt(J) : S.add(J) : ft !== void 0 && S.has(J) ? zt(J) : H.protectedKeys[J] = !0;
      }
      H.prevProp = X, H.prevResolvedValues = it, H.isActive && (T = { ...T, ...it }), (a || r) && n.blockInitialAnimation && (lt = !1);
      const j = st && $;
      lt && (!j || nt) && b.push(...vt.map((J) => {
        const ft = { type: B };
        if (typeof J == "string" && (a || r) && !j && n.manuallyAnimateOnMount && n.parent) {
          const { parent: D } = n, Y = Mo(D, J);
          if (D.enteringChildren && Y) {
            const { delayChildren: et } = Y.transition || {};
            ft.delay = uC(D.enteringChildren, n, et);
          }
        }
        return {
          animation: J,
          options: ft
        };
      }));
    }
    if (S.size) {
      const z = {};
      if (typeof g.initial != "boolean") {
        const B = Mo(n, Array.isArray(g.initial) ? g.initial[0] : g.initial);
        B && B.transition && (z.transition = B.transition);
      }
      S.forEach((B) => {
        const H = n.getBaseTarget(B), X = n.getValue(B);
        X && (X.liveStyle = !0), z[B] = H ?? null;
      }), b.push({ animation: z });
    }
    let R = !!b.length;
    return a && (g.initial === !1 || g.initial === g.animate) && !n.manuallyAnimateOnMount && (R = !1), a = !1, r = !1, R ? t(b) : Promise.resolve();
  }
  function m(p, g) {
    var b;
    if (i[p].isActive === g)
      return Promise.resolve();
    (b = n.variantChildren) == null || b.forEach((S) => {
      var T;
      return (T = S.animationState) == null ? void 0 : T.setActive(p, g);
    }), i[p].isActive = g;
    const y = f(p);
    for (const S in i)
      i[S].protectedKeys = {};
    return y;
  }
  return {
    animateChanges: f,
    setActive: m,
    setAnimateFunction: c,
    getState: () => i,
    reset: () => {
      i = cw(), r = !0;
    }
  };
}
function ML(n, t) {
  return typeof t == "string" ? t !== n : Array.isArray(t) ? !UC(t, n) : !1;
}
function Va(n = !1) {
  return {
    isActive: n,
    protectedKeys: {},
    needsAnimating: {},
    prevResolvedValues: {}
  };
}
function cw() {
  return {
    animate: Va(!0),
    whileInView: Va(),
    whileHover: Va(),
    whileTap: Va(),
    whileDrag: Va(),
    whileFocus: Va(),
    exit: Va()
  };
}
function My(n, t) {
  n.min = t.min, n.max = t.max;
}
function Qn(n, t) {
  My(n.x, t.x), My(n.y, t.y);
}
function fw(n, t) {
  n.translate = t.translate, n.scale = t.scale, n.originPoint = t.originPoint, n.origin = t.origin;
}
const jC = 1e-4, TL = 1 - jC, CL = 1 + jC, HC = 0.01, EL = 0 - HC, AL = 0 + HC;
function Ie(n) {
  return n.max - n.min;
}
function DL(n, t, i) {
  return Math.abs(n - t) <= i;
}
function hw(n, t, i, a = 0.5) {
  n.origin = a, n.originPoint = Ft(t.min, t.max, n.origin), n.scale = Ie(i) / Ie(t), n.translate = Ft(i.min, i.max, n.origin) - n.originPoint, (n.scale >= TL && n.scale <= CL || isNaN(n.scale)) && (n.scale = 1), (n.translate >= EL && n.translate <= AL || isNaN(n.translate)) && (n.translate = 0);
}
function ec(n, t, i, a) {
  hw(n.x, t.x, i.x, a ? a.originX : void 0), hw(n.y, t.y, i.y, a ? a.originY : void 0);
}
function dw(n, t, i, a = 0) {
  const r = a ? Ft(i.min, i.max, a) : i.min;
  n.min = r + t.min, n.max = n.min + Ie(t);
}
function RL(n, t, i, a) {
  dw(n.x, t.x, i.x, a == null ? void 0 : a.x), dw(n.y, t.y, i.y, a == null ? void 0 : a.y);
}
function mw(n, t, i, a = 0) {
  const r = a ? Ft(i.min, i.max, a) : i.min;
  n.min = t.min - r, n.max = n.min + Ie(t);
}
function od(n, t, i, a) {
  mw(n.x, t.x, i.x, a == null ? void 0 : a.x), mw(n.y, t.y, i.y, a == null ? void 0 : a.y);
}
function pw(n, t, i, a, r) {
  return n -= t, n = ad(n, 1 / i, a), r !== void 0 && (n = ad(n, 1 / r, a)), n;
}
function OL(n, t = 0, i = 1, a = 0.5, r, u = n, c = n) {
  if (ki.test(t) && (t = parseFloat(t), t = Ft(c.min, c.max, t / 100) - c.min), typeof t != "number")
    return;
  let f = Ft(u.min, u.max, a);
  n === u && (f -= t), n.min = pw(n.min, t, i, f, r), n.max = pw(n.max, t, i, f, r);
}
function gw(n, t, [i, a, r], u, c) {
  OL(n, t[i], t[a], t[r], t.scale, u, c);
}
const zL = ["x", "scaleX", "originX"], kL = ["y", "scaleY", "originY"];
function yw(n, t, i, a) {
  gw(n.x, t, zL, i ? i.x : void 0, a ? a.x : void 0), gw(n.y, t, kL, i ? i.y : void 0, a ? a.y : void 0);
}
function vw(n) {
  return n.translate === 0 && n.scale === 1;
}
function qC(n) {
  return vw(n.x) && vw(n.y);
}
function bw(n, t) {
  return n.min === t.min && n.max === t.max;
}
function VL(n, t) {
  return bw(n.x, t.x) && bw(n.y, t.y);
}
function xw(n, t) {
  return Math.round(n.min) === Math.round(t.min) && Math.round(n.max) === Math.round(t.max);
}
function GC(n, t) {
  return xw(n.x, t.x) && xw(n.y, t.y);
}
function Sw(n) {
  return Ie(n.x) / Ie(n.y);
}
function ww(n, t) {
  return n.translate === t.translate && n.scale === t.scale && n.originPoint === t.originPoint;
}
function mi(n) {
  return [n("x"), n("y")];
}
function PL(n, t, i) {
  let a = "";
  const r = n.x.translate / t.x, u = n.y.translate / t.y, c = (i == null ? void 0 : i.z) || 0;
  if ((r || u || c) && (a = `translate3d(${r}px, ${u}px, ${c}px) `), (t.x !== 1 || t.y !== 1) && (a += `scale(${1 / t.x}, ${1 / t.y}) `), i) {
    const { transformPerspective: p, rotate: g, pathRotation: y, rotateX: b, rotateY: S, skewX: T, skewY: C } = i;
    p && (a = `perspective(${p}px) ${a}`), g && (a += `rotate(${g}deg) `), y && (a += `rotate(${y}deg) `), b && (a += `rotateX(${b}deg) `), S && (a += `rotateY(${S}deg) `), T && (a += `skewX(${T}deg) `), C && (a += `skewY(${C}deg) `);
  }
  const f = n.x.scale * t.x, m = n.y.scale * t.y;
  return (f !== 1 || m !== 1) && (a += `scale(${f}, ${m})`), a || "none";
}
const LL = xv.length, Mw = (n) => typeof n == "string" ? parseFloat(n) : n, Tw = (n) => typeof n == "number" || ot.test(n);
function _L(n, t, i, a, r, u) {
  r ? (n.opacity = Ft(0, i.opacity ?? 1, BL(a)), n.opacityExit = Ft(t.opacity ?? 1, 0, NL(a))) : u && (n.opacity = Ft(t.opacity ?? 1, i.opacity ?? 1, a));
  for (let c = 0; c < LL; c++) {
    const f = xv[c];
    let m = Cw(t, f), p = Cw(i, f);
    if (m === void 0 && p === void 0)
      continue;
    m || (m = 0), p || (p = 0), m === 0 || p === 0 || Tw(m) === Tw(p) ? (n[f] = Math.max(Ft(Mw(m), Mw(p), a), 0), (ki.test(p) || ki.test(m)) && (n[f] += "%")) : n[f] = p;
  }
  (t.rotate || i.rotate) && (n.rotate = Ft(t.rotate || 0, i.rotate || 0, a));
}
function Cw(n, t) {
  return n[t] !== void 0 ? n[t] : n.borderRadius;
}
const BL = /* @__PURE__ */ YC(0, 0.5, _T), NL = /* @__PURE__ */ YC(0.5, 0.95, Bn);
function YC(n, t, i) {
  return (a) => a < n ? 0 : a > t ? 1 : i(/* @__PURE__ */ rc(n, t, a));
}
function UL(n, t, i) {
  const a = de(n) ? n : Lo(n);
  return a.start(yv("", a, t, i)), a.animation;
}
function fc(n, t, i, a = { passive: !0 }) {
  return n.addEventListener(t, i, a), () => n.removeEventListener(t, i, a);
}
const jL = (n, t) => n.depth - t.depth;
class HL {
  constructor() {
    this.children = [], this.isDirty = !1;
  }
  add(t) {
    av(this.children, t), this.isDirty = !0;
  }
  remove(t) {
    Jh(this.children, t), this.isDirty = !0;
  }
  forEach(t) {
    this.isDirty && this.children.sort(jL), this.isDirty = !1, this.children.forEach(t);
  }
}
function qL(n, t) {
  const i = Ke.now(), a = ({ timestamp: r }) => {
    const u = r - i;
    u >= t && (Wi(a), n(u - t));
  };
  return jt.setup(a, !0), () => Wi(a);
}
function Zh(n) {
  return de(n) ? n.get() : n;
}
class GL {
  constructor() {
    this.members = [];
  }
  add(t) {
    av(this.members, t);
    for (let i = this.members.length - 1; i >= 0; i--) {
      const a = this.members[i];
      if (a === t || a === this.lead || a === this.prevLead)
        continue;
      const r = a.instance;
      (!r || r.isConnected === !1) && !a.snapshot && (Jh(this.members, a), a.unmount());
    }
    t.scheduleRender();
  }
  remove(t) {
    if (Jh(this.members, t), t === this.prevLead && (this.prevLead = void 0), t === this.lead) {
      const i = this.members[this.members.length - 1];
      i && this.promote(i);
    }
  }
  relegate(t) {
    var i;
    for (let a = this.members.indexOf(t) - 1; a >= 0; a--) {
      const r = this.members[a];
      if (r.isPresent !== !1 && ((i = r.instance) == null ? void 0 : i.isConnected) !== !1)
        return this.promote(r), !0;
    }
    return !1;
  }
  promote(t, i) {
    var r;
    const a = this.lead;
    if (t !== a && (this.prevLead = a, this.lead = t, t.show(), a)) {
      a.updateSnapshot(), t.scheduleRender();
      const { layoutDependency: u } = a.options, { layoutDependency: c } = t.options;
      (u === void 0 || u !== c) && (t.resumeFrom = a, i && (a.preserveOpacity = !0), a.snapshot && (t.snapshot = a.snapshot, t.snapshot.latestValues = a.animationValues || a.latestValues), (r = t.root) != null && r.isUpdating && (t.isLayoutDirty = !0)), t.options.crossfade === !1 && a.hide();
    }
  }
  exitAnimationComplete() {
    this.members.forEach((t) => {
      var i, a, r, u, c;
      (a = (i = t.options).onExitComplete) == null || a.call(i), (c = (r = t.resumingFrom) == null ? void 0 : (u = r.options).onExitComplete) == null || c.call(u);
    });
  }
  scheduleRender() {
    this.members.forEach((t) => t.instance && t.scheduleRender(!1));
  }
  removeLeadSnapshot() {
    var t;
    (t = this.lead) != null && t.snapshot && (this.lead.snapshot = void 0);
  }
}
const Qh = {
  /**
   * Global flag as to whether the tree has animated since the last time
   * we resized the window
   */
  hasAnimatedSinceResize: !0,
  /**
   * We set this to true once, on the first update. Any nodes added to the tree beyond that
   * update will be given a `data-projection-id` attribute.
   */
  hasEverUpdated: !1
}, Ag = ["", "X", "Y", "Z"], YL = 1e3;
let XL = 0;
function Dg(n, t, i, a) {
  const { latestValues: r } = t;
  r[n] && (i[n] = r[n], t.setStaticValue(n, 0), a && (a[n] = 0));
}
function XC(n) {
  if (n.hasCheckedOptimisedAppear = !0, n.root === n)
    return;
  const { visualElement: t } = n.options;
  if (!t)
    return;
  const i = mC(t);
  if (window.MotionHasOptimisedAnimation(i, "transform")) {
    const { layout: r, layoutId: u } = n.options;
    window.MotionCancelOptimisedAnimation(i, "transform", jt, !(r || u));
  }
  const { parent: a } = n;
  a && !a.hasCheckedOptimisedAppear && XC(a);
}
function FC({ attachResizeListener: n, defaultParent: t, measureScroll: i, checkIsScrollRoot: a, resetTransform: r }) {
  return class {
    constructor(c = {}, f = t == null ? void 0 : t()) {
      this.id = XL++, this.animationId = 0, this.animationCommitId = 0, this.children = /* @__PURE__ */ new Set(), this.options = {}, this.isTreeAnimating = !1, this.isAnimationBlocked = !1, this.isLayoutDirty = !1, this.isProjectionDirty = !1, this.isSharedProjectionDirty = !1, this.isTransformDirty = !1, this.updateManuallyBlocked = !1, this.updateBlockedByResize = !1, this.isUpdating = !1, this.isSVG = !1, this.needsReset = !1, this.shouldResetTransform = !1, this.hasCheckedOptimisedAppear = !1, this.treeScale = { x: 1, y: 1 }, this.eventHandlers = /* @__PURE__ */ new Map(), this.hasTreeAnimated = !1, this.layoutVersion = 0, this.updateScheduled = !1, this.scheduleUpdate = () => this.update(), this.projectionUpdateScheduled = !1, this.checkUpdateFailed = () => {
        this.isUpdating && (this.isUpdating = !1, this.clearAllSnapshots());
      }, this.updateProjection = () => {
        this.projectionUpdateScheduled = !1, this.nodes.forEach(QL), this.nodes.forEach(t5), this.nodes.forEach(e5), this.nodes.forEach(KL);
      }, this.resolvedRelativeTargetAt = 0, this.linkedParentVersion = 0, this.hasProjected = !1, this.isVisible = !0, this.animationProgress = 0, this.sharedNodes = /* @__PURE__ */ new Map(), this.latestValues = c, this.root = f ? f.root || f : this, this.path = f ? [...f.path, f] : [], this.parent = f, this.depth = f ? f.depth + 1 : 0;
      for (let m = 0; m < this.path.length; m++)
        this.path[m].shouldResetTransform = !0;
      this.root === this && (this.nodes = new HL());
    }
    addEventListener(c, f) {
      return this.eventHandlers.has(c) || this.eventHandlers.set(c, new ov()), this.eventHandlers.get(c).add(f);
    }
    notifyListeners(c, ...f) {
      const m = this.eventHandlers.get(c);
      m && m.notify(...f);
    }
    hasListeners(c) {
      return this.eventHandlers.has(c);
    }
    /**
     * Lifecycles
     */
    mount(c) {
      if (this.instance)
        return;
      this.isSVG = Tv(c) && !X4(c), this.instance = c;
      const { layoutId: f, layout: m, visualElement: p } = this.options;
      if (p && !p.current && p.mount(c), this.root.nodes.add(this), this.parent && this.parent.children.add(this), this.root.hasTreeAnimated && (m || f) && (this.isLayoutDirty = !0), n) {
        let g, y = 0;
        const b = () => this.root.updateBlockedByResize = !1;
        jt.read(() => {
          y = window.innerWidth;
        }), n(c, () => {
          const S = window.innerWidth;
          S !== y && (y = S, this.root.updateBlockedByResize = !0, g && g(), g = qL(b, 250), Qh.hasAnimatedSinceResize && (Qh.hasAnimatedSinceResize = !1, this.nodes.forEach(Dw)));
        });
      }
      f && this.root.registerSharedNode(f, this), this.options.animate !== !1 && p && (f || m) && this.addEventListener("didUpdate", ({ delta: g, hasLayoutChanged: y, hasRelativeLayoutChanged: b, layout: S }) => {
        if (this.isTreeAnimationBlocked()) {
          this.target = void 0, this.relativeTarget = void 0;
          return;
        }
        const T = this.options.transition || p.getDefaultTransition() || o5, { onLayoutAnimationStart: C, onLayoutAnimationComplete: R } = p.getProps(), z = !this.targetLayout || !GC(this.targetLayout, S), B = !y && b;
        if (this.options.layoutRoot || this.resumeFrom || B || y && (z || !this.currentAnimation)) {
          this.resumeFrom && (this.resumingFrom = this.resumeFrom, this.resumingFrom.resumingFrom = void 0);
          const H = {
            ...gv(T, "layout"),
            onPlay: C,
            onComplete: R
          };
          (p.shouldReduceMotion || this.options.layoutRoot) && (H.delay = 0, H.type = !1), this.startAnimation(H), this.setAnimationOrigin(g, B, H.path);
        } else
          y || Dw(this), this.isLead() && this.options.onExitComplete && this.options.onExitComplete();
        this.targetLayout = S;
      });
    }
    unmount() {
      this.options.layoutId && this.willUpdate(), this.root.nodes.remove(this);
      const c = this.getStack();
      c && c.remove(this), this.parent && this.parent.children.delete(this), this.instance = void 0, this.eventHandlers.clear(), Wi(this.updateProjection);
    }
    // only on the root
    blockUpdate() {
      this.updateManuallyBlocked = !0;
    }
    unblockUpdate() {
      this.updateManuallyBlocked = !1;
    }
    isUpdateBlocked() {
      return this.updateManuallyBlocked || this.updateBlockedByResize;
    }
    isTreeAnimationBlocked() {
      return this.isAnimationBlocked || this.parent && this.parent.isTreeAnimationBlocked() || !1;
    }
    // Note: currently only running on root node
    startUpdate() {
      this.isUpdateBlocked() || (this.isUpdating = !0, this.nodes && this.nodes.forEach(n5), this.animationId++);
    }
    getTransformTemplate() {
      const { visualElement: c } = this.options;
      return c && c.getProps().transformTemplate;
    }
    willUpdate(c = !0) {
      if (this.root.hasTreeAnimated = !0, this.root.isUpdateBlocked()) {
        this.options.onExitComplete && this.options.onExitComplete();
        return;
      }
      if (window.MotionCancelOptimisedAnimation && !this.hasCheckedOptimisedAppear && XC(this), !this.root.isUpdating && this.root.startUpdate(), this.isLayoutDirty)
        return;
      this.isLayoutDirty = !0;
      for (let g = 0; g < this.path.length; g++) {
        const y = this.path[g];
        y.shouldResetTransform = !0, (typeof y.latestValues.x == "string" || typeof y.latestValues.y == "string") && (y.isLayoutDirty = !0), y.updateScroll("snapshot"), y.options.layoutRoot && y.willUpdate(!1);
      }
      const { layoutId: f, layout: m } = this.options;
      if (f === void 0 && !m)
        return;
      const p = this.getTransformTemplate();
      this.prevTransformTemplateValue = p ? p(this.latestValues, "") : void 0, this.updateSnapshot(), c && this.notifyListeners("willUpdate");
    }
    update() {
      if (this.updateScheduled = !1, this.isUpdateBlocked()) {
        const m = this.updateBlockedByResize;
        this.unblockUpdate(), this.updateBlockedByResize = !1, this.clearAllSnapshots(), m && this.nodes.forEach($L), this.nodes.forEach(Ew);
        return;
      }
      if (this.animationId <= this.animationCommitId) {
        this.nodes.forEach(Aw);
        return;
      }
      this.animationCommitId = this.animationId, this.isUpdating ? (this.isUpdating = !1, this.nodes.forEach(WL), this.nodes.forEach(JL), this.nodes.forEach(FL), this.nodes.forEach(ZL)) : this.nodes.forEach(Aw), this.clearAllSnapshots();
      const f = Ke.now();
      Ve.delta = Vi(0, 1e3 / 60, f - Ve.timestamp), Ve.timestamp = f, Ve.isProcessing = !0, vg.update.process(Ve), vg.preRender.process(Ve), vg.render.process(Ve), Ve.isProcessing = !1;
    }
    didUpdate() {
      this.updateScheduled || (this.updateScheduled = !0, wv.read(this.scheduleUpdate));
    }
    clearAllSnapshots() {
      this.nodes.forEach(IL), this.sharedNodes.forEach(i5);
    }
    scheduleUpdateProjection() {
      this.projectionUpdateScheduled || (this.projectionUpdateScheduled = !0, jt.preRender(this.updateProjection, !1, !0));
    }
    scheduleCheckAfterUnmount() {
      jt.postRender(() => {
        this.isLayoutDirty ? this.root.didUpdate() : this.root.checkUpdateFailed();
      });
    }
    /**
     * Update measurements
     */
    updateSnapshot() {
      this.snapshot || !this.instance || (this.snapshot = this.measure(), this.snapshot && !Ie(this.snapshot.measuredBox.x) && !Ie(this.snapshot.measuredBox.y) && (this.snapshot = void 0));
    }
    updateLayout() {
      if (!this.instance || (this.updateScroll(), !(this.options.alwaysMeasureLayout && this.isLead()) && !this.isLayoutDirty))
        return;
      if (this.resumeFrom && !this.resumeFrom.instance)
        for (let m = 0; m < this.path.length; m++)
          this.path[m].updateScroll();
      const c = this.layout;
      this.layout = this.measure(!1), this.layoutVersion++, this.layoutCorrected || (this.layoutCorrected = we()), this.isLayoutDirty = !1, this.projectionDelta = void 0, this.notifyListeners("measure", this.layout.layoutBox);
      const { visualElement: f } = this.options;
      f && f.notify("LayoutMeasure", this.layout.layoutBox, c ? c.layoutBox : void 0);
    }
    updateScroll(c = "measure") {
      let f = !!(this.options.layoutScroll && this.instance);
      if (this.scroll && this.scroll.animationId === this.root.animationId && this.scroll.phase === c && (f = !1), f && this.instance) {
        const m = a(this.instance);
        this.scroll = {
          animationId: this.root.animationId,
          phase: c,
          isRoot: m,
          offset: i(this.instance),
          wasRoot: this.scroll ? this.scroll.isRoot : m
        };
      }
    }
    resetTransform() {
      if (!r)
        return;
      const c = this.isLayoutDirty || this.shouldResetTransform || this.options.alwaysMeasureLayout, f = this.projectionDelta && !qC(this.projectionDelta), m = this.getTransformTemplate(), p = m ? m(this.latestValues, "") : void 0, g = p !== this.prevTransformTemplateValue;
      c && this.instance && (f || Pa(this.latestValues) || g) && (r(this.instance, p), this.shouldResetTransform = !1, this.scheduleRender());
    }
    measure(c = !0) {
      const f = this.measurePageBox();
      let m = this.removeElementScroll(f);
      return c && (m = this.removeTransform(m)), r5(m), {
        animationId: this.root.animationId,
        measuredBox: f,
        layoutBox: m,
        latestValues: {},
        source: this.id
      };
    }
    measurePageBox() {
      var p;
      const { visualElement: c } = this.options;
      if (!c)
        return we();
      const f = c.measureViewportBox();
      if (!(((p = this.scroll) == null ? void 0 : p.wasRoot) || this.path.some(l5))) {
        const { scroll: g } = this.root;
        g && (Ri(f.x, g.offset.x), Ri(f.y, g.offset.y));
      }
      return f;
    }
    removeElementScroll(c) {
      var m;
      const f = we();
      if (Qn(f, c), (m = this.scroll) != null && m.wasRoot)
        return f;
      for (let p = 0; p < this.path.length; p++) {
        const g = this.path[p], { scroll: y, options: b } = g;
        g !== this.root && y && b.layoutScroll && (y.wasRoot && Qn(f, c), Ri(f.x, y.offset.x), Ri(f.y, y.offset.y));
      }
      return f;
    }
    applyTransform(c, f = !1, m) {
      var g, y;
      const p = m || we();
      Qn(p, c);
      for (let b = 0; b < this.path.length; b++) {
        const S = this.path[b];
        !f && S.options.layoutScroll && S.scroll && S !== S.root && (Ri(p.x, -S.scroll.offset.x), Ri(p.y, -S.scroll.offset.y)), Pa(S.latestValues) && Fh(p, S.latestValues, (g = S.layout) == null ? void 0 : g.layoutBox);
      }
      return Pa(this.latestValues) && Fh(p, this.latestValues, (y = this.layout) == null ? void 0 : y.layoutBox), p;
    }
    removeTransform(c) {
      var m;
      const f = we();
      Qn(f, c);
      for (let p = 0; p < this.path.length; p++) {
        const g = this.path[p];
        if (!Pa(g.latestValues))
          continue;
        let y;
        g.instance && (xy(g.latestValues) && g.updateSnapshot(), y = we(), Qn(y, g.measurePageBox())), yw(f, g.latestValues, (m = g.snapshot) == null ? void 0 : m.layoutBox, y);
      }
      return Pa(this.latestValues) && yw(f, this.latestValues), f;
    }
    setTargetDelta(c) {
      this.targetDelta = c, this.root.scheduleUpdateProjection(), this.isProjectionDirty = !0;
    }
    setOptions(c) {
      this.options = {
        ...this.options,
        ...c,
        crossfade: c.crossfade !== void 0 ? c.crossfade : !0
      };
    }
    clearMeasurements() {
      this.scroll = void 0, this.layout = void 0, this.snapshot = void 0, this.prevTransformTemplateValue = void 0, this.targetDelta = void 0, this.target = void 0, this.isLayoutDirty = !1;
    }
    forceRelativeParentToResolveTarget() {
      this.relativeParent && this.relativeParent.resolvedRelativeTargetAt !== Ve.timestamp && this.relativeParent.resolveTargetDelta(!0);
    }
    resolveTargetDelta(c = !1) {
      var S;
      const f = this.getLead();
      this.isProjectionDirty || (this.isProjectionDirty = f.isProjectionDirty), this.isTransformDirty || (this.isTransformDirty = f.isTransformDirty), this.isSharedProjectionDirty || (this.isSharedProjectionDirty = f.isSharedProjectionDirty);
      const m = !!this.resumingFrom || this !== f;
      if (!(c || m && this.isSharedProjectionDirty || this.isProjectionDirty || (S = this.parent) != null && S.isProjectionDirty || this.attemptToResolveRelativeTarget || this.root.updateBlockedByResize))
        return;
      const { layout: g, layoutId: y } = this.options;
      if (!this.layout || !(g || y))
        return;
      this.resolvedRelativeTargetAt = Ve.timestamp;
      const b = this.getClosestProjectingParent();
      b && this.linkedParentVersion !== b.layoutVersion && !b.options.layoutRoot && this.removeRelativeTarget(), !this.targetDelta && !this.relativeTarget && (this.options.layoutAnchor !== !1 && b && b.layout ? this.createRelativeTarget(b, this.layout.layoutBox, b.layout.layoutBox) : this.removeRelativeTarget()), !(!this.relativeTarget && !this.targetDelta) && (this.target || (this.target = we(), this.targetWithTransforms = we()), this.relativeTarget && this.relativeTargetOrigin && this.relativeParent && this.relativeParent.target ? (this.forceRelativeParentToResolveTarget(), RL(this.target, this.relativeTarget, this.relativeParent.target, this.options.layoutAnchor || void 0)) : this.targetDelta ? (this.resumingFrom ? this.applyTransform(this.layout.layoutBox, !1, this.target) : Qn(this.target, this.layout.layoutBox), OC(this.target, this.targetDelta)) : Qn(this.target, this.layout.layoutBox), this.attemptToResolveRelativeTarget && (this.attemptToResolveRelativeTarget = !1, this.options.layoutAnchor !== !1 && b && !!b.resumingFrom == !!this.resumingFrom && !b.options.layoutScroll && b.target && this.animationProgress !== 1 ? this.createRelativeTarget(b, this.target, b.target) : this.relativeParent = this.relativeTarget = void 0));
    }
    getClosestProjectingParent() {
      if (!(!this.parent || xy(this.parent.latestValues) || RC(this.parent.latestValues)))
        return this.parent.isProjecting() ? this.parent : this.parent.getClosestProjectingParent();
    }
    isProjecting() {
      return !!((this.relativeTarget || this.targetDelta || this.options.layoutRoot) && this.layout);
    }
    createRelativeTarget(c, f, m) {
      this.relativeParent = c, this.linkedParentVersion = c.layoutVersion, this.forceRelativeParentToResolveTarget(), this.relativeTarget = we(), this.relativeTargetOrigin = we(), od(this.relativeTargetOrigin, f, m, this.options.layoutAnchor || void 0), Qn(this.relativeTarget, this.relativeTargetOrigin);
    }
    removeRelativeTarget() {
      this.relativeParent = this.relativeTarget = void 0;
    }
    calcProjection() {
      var T;
      const c = this.getLead(), f = !!this.resumingFrom || this !== c;
      let m = !0;
      if ((this.isProjectionDirty || (T = this.parent) != null && T.isProjectionDirty) && (m = !1), f && (this.isSharedProjectionDirty || this.isTransformDirty) && (m = !1), this.resolvedRelativeTargetAt === Ve.timestamp && (m = !1), m)
        return;
      const { layout: p, layoutId: g } = this.options;
      if (this.isTreeAnimating = !!(this.parent && this.parent.isTreeAnimating || this.currentAnimation || this.pendingAnimation), this.isTreeAnimating || (this.targetDelta = this.relativeTarget = void 0), !this.layout || !(p || g))
        return;
      Qn(this.layoutCorrected, this.layout.layoutBox);
      const y = this.treeScale.x, b = this.treeScale.y;
      sL(this.layoutCorrected, this.treeScale, this.path, f), c.layout && !c.target && (this.treeScale.x !== 1 || this.treeScale.y !== 1) && (c.target = c.layout.layoutBox, c.targetWithTransforms = we());
      const { target: S } = c;
      if (!S) {
        this.prevProjectionDelta && (this.createProjectionDeltas(), this.scheduleRender());
        return;
      }
      !this.projectionDelta || !this.prevProjectionDelta ? this.createProjectionDeltas() : (fw(this.prevProjectionDelta.x, this.projectionDelta.x), fw(this.prevProjectionDelta.y, this.projectionDelta.y)), ec(this.projectionDelta, this.layoutCorrected, S, this.latestValues), (this.treeScale.x !== y || this.treeScale.y !== b || !ww(this.projectionDelta.x, this.prevProjectionDelta.x) || !ww(this.projectionDelta.y, this.prevProjectionDelta.y)) && (this.hasProjected = !0, this.scheduleRender(), this.notifyListeners("projectionUpdate", S));
    }
    hide() {
      this.isVisible = !1;
    }
    show() {
      this.isVisible = !0;
    }
    scheduleRender(c = !0) {
      var f;
      if ((f = this.options.visualElement) == null || f.scheduleRender(), c) {
        const m = this.getStack();
        m && m.scheduleRender();
      }
      this.resumingFrom && !this.resumingFrom.instance && (this.resumingFrom = void 0);
    }
    createProjectionDeltas() {
      this.prevProjectionDelta = Pr(), this.projectionDelta = Pr(), this.projectionDeltaWithTransform = Pr();
    }
    setAnimationOrigin(c, f = !1, m) {
      const p = this.snapshot, g = p ? p.latestValues : {}, y = { ...this.latestValues }, b = Pr();
      (!this.relativeParent || !this.relativeParent.options.layoutRoot) && (this.relativeTarget = this.relativeTargetOrigin = void 0), this.attemptToResolveRelativeTarget = !f;
      const S = we(), T = p ? p.source : void 0, C = this.layout ? this.layout.source : void 0, R = T !== C, z = this.getStack(), B = !z || z.members.length <= 1, H = !!(R && !B && this.options.crossfade === !0 && !this.path.some(a5));
      this.animationProgress = 0;
      let X;
      const Q = m == null ? void 0 : m.interpolateProjection(c);
      this.mixTargetDelta = (ut) => {
        const st = ut / 1e3, $ = Q == null ? void 0 : Q(st);
        $ ? (b.x.translate = $.x, b.x.scale = Ft(c.x.scale, 1, st), b.x.origin = c.x.origin, b.x.originPoint = c.x.originPoint, b.y.translate = $.y, b.y.scale = Ft(c.y.scale, 1, st), b.y.origin = c.y.origin, b.y.originPoint = c.y.originPoint) : (Rw(b.x, c.x, st), Rw(b.y, c.y, st)), this.setTargetDelta(b), this.relativeTarget && this.relativeTargetOrigin && this.layout && this.relativeParent && this.relativeParent.layout && (od(S, this.layout.layoutBox, this.relativeParent.layout.layoutBox, this.options.layoutAnchor || void 0), s5(this.relativeTarget, this.relativeTargetOrigin, S, st), X && VL(this.relativeTarget, X) && (this.isProjectionDirty = !1), X || (X = we()), Qn(X, this.relativeTarget)), R && (this.animationValues = y, _L(y, g, this.latestValues, st, H, B)), $ && $.rotate !== void 0 && (this.animationValues || (this.animationValues = y), this.animationValues.pathRotation = $.rotate), this.root.scheduleUpdateProjection(), this.scheduleRender(), this.animationProgress = st;
      }, this.mixTargetDelta(this.options.layoutRoot ? 1e3 : 0);
    }
    startAnimation(c) {
      var f, m, p;
      this.notifyListeners("animationStart"), (f = this.currentAnimation) == null || f.stop(), (p = (m = this.resumingFrom) == null ? void 0 : m.currentAnimation) == null || p.stop(), this.pendingAnimation && (Wi(this.pendingAnimation), this.pendingAnimation = void 0), this.pendingAnimation = jt.update(() => {
        Qh.hasAnimatedSinceResize = !0, this.motionValue || (this.motionValue = Lo(0)), this.motionValue.jump(0, !1), this.currentAnimation = UL(this.motionValue, [0, 1e3], {
          ...c,
          velocity: 0,
          isSync: !0,
          onUpdate: (g) => {
            this.mixTargetDelta(g), c.onUpdate && c.onUpdate(g);
          },
          onComplete: () => {
            c.onComplete && c.onComplete(), this.completeAnimation();
          }
        }), this.resumingFrom && (this.resumingFrom.currentAnimation = this.currentAnimation), this.pendingAnimation = void 0;
      });
    }
    completeAnimation() {
      this.resumingFrom && (this.resumingFrom.currentAnimation = void 0, this.resumingFrom.preserveOpacity = void 0);
      const c = this.getStack();
      c && c.exitAnimationComplete(), this.resumingFrom = this.currentAnimation = this.animationValues = void 0, this.notifyListeners("animationComplete");
    }
    finishAnimation() {
      this.currentAnimation && (this.mixTargetDelta && this.mixTargetDelta(YL), this.currentAnimation.stop()), this.completeAnimation();
    }
    applyTransformsToTarget() {
      const c = this.getLead();
      let { targetWithTransforms: f, target: m, layout: p, latestValues: g } = c;
      if (!(!f || !m || !p)) {
        if (this !== c && this.layout && p && ZC(this.options.animationType, this.layout.layoutBox, p.layoutBox)) {
          m = this.target || we();
          const y = Ie(this.layout.layoutBox.x);
          m.x.min = c.target.x.min, m.x.max = m.x.min + y;
          const b = Ie(this.layout.layoutBox.y);
          m.y.min = c.target.y.min, m.y.max = m.y.min + b;
        }
        Qn(f, m), Fh(f, g), ec(this.projectionDeltaWithTransform, this.layoutCorrected, f, g);
      }
    }
    registerSharedNode(c, f) {
      this.sharedNodes.has(c) || this.sharedNodes.set(c, new GL()), this.sharedNodes.get(c).add(f);
      const p = f.options.initialPromotionConfig;
      f.promote({
        transition: p ? p.transition : void 0,
        preserveFollowOpacity: p && p.shouldPreserveFollowOpacity ? p.shouldPreserveFollowOpacity(f) : void 0
      });
    }
    isLead() {
      const c = this.getStack();
      return c ? c.lead === this : !0;
    }
    getLead() {
      var f;
      const { layoutId: c } = this.options;
      return c ? ((f = this.getStack()) == null ? void 0 : f.lead) || this : this;
    }
    getPrevLead() {
      var f;
      const { layoutId: c } = this.options;
      return c ? (f = this.getStack()) == null ? void 0 : f.prevLead : void 0;
    }
    getStack() {
      const { layoutId: c } = this.options;
      if (c)
        return this.root.sharedNodes.get(c);
    }
    promote({ needsReset: c, transition: f, preserveFollowOpacity: m } = {}) {
      const p = this.getStack();
      p && p.promote(this, m), c && (this.projectionDelta = void 0, this.needsReset = !0), f && this.setOptions({ transition: f });
    }
    relegate() {
      const c = this.getStack();
      return c ? c.relegate(this) : !1;
    }
    resetSkewAndRotation() {
      const { visualElement: c } = this.options;
      if (!c)
        return;
      let f = !1;
      const { latestValues: m } = c;
      if ((m.z || m.rotate || m.rotateX || m.rotateY || m.rotateZ || m.skewX || m.skewY) && (f = !0), !f)
        return;
      const p = {};
      m.z && Dg("z", c, p, this.animationValues);
      for (let g = 0; g < Ag.length; g++)
        Dg(`rotate${Ag[g]}`, c, p, this.animationValues), Dg(`skew${Ag[g]}`, c, p, this.animationValues);
      c.render();
      for (const g in p)
        c.setStaticValue(g, p[g]), this.animationValues && (this.animationValues[g] = p[g]);
      c.scheduleRender();
    }
    applyProjectionStyles(c, f) {
      if (!this.instance || this.isSVG)
        return;
      if (!this.isVisible) {
        c.visibility = "hidden";
        return;
      }
      const m = this.getTransformTemplate();
      if (this.needsReset) {
        this.needsReset = !1, c.visibility = "", c.opacity = "", c.pointerEvents = Zh(f == null ? void 0 : f.pointerEvents) || "", c.transform = m ? m(this.latestValues, "") : "none";
        return;
      }
      const p = this.getLead();
      if (!this.projectionDelta || !this.layout || !p.target) {
        this.options.layoutId && (c.opacity = this.latestValues.opacity !== void 0 ? this.latestValues.opacity : 1, c.pointerEvents = Zh(f == null ? void 0 : f.pointerEvents) || ""), this.hasProjected && !Pa(this.latestValues) && (c.transform = m ? m({}, "") : "none", this.hasProjected = !1);
        return;
      }
      c.visibility = "";
      const g = p.animationValues || p.latestValues;
      this.applyTransformsToTarget();
      let y = PL(this.projectionDeltaWithTransform, this.treeScale, g);
      m && (y = m(g, y)), c.transform = y;
      const { x: b, y: S } = this.projectionDelta;
      c.transformOrigin = `${b.origin * 100}% ${S.origin * 100}% 0`, p.animationValues ? c.opacity = p === this ? g.opacity ?? this.latestValues.opacity ?? 1 : this.preserveOpacity ? this.latestValues.opacity : g.opacityExit : c.opacity = p === this ? g.opacity !== void 0 ? g.opacity : "" : g.opacityExit !== void 0 ? g.opacityExit : 0;
      for (const T in wy) {
        if (g[T] === void 0)
          continue;
        const { correct: C, applyTo: R, isCSSVariable: z } = wy[T], B = y === "none" ? g[T] : C(g[T], p);
        if (R) {
          const H = R.length;
          for (let X = 0; X < H; X++)
            c[R[X]] = B;
        } else
          z ? this.options.visualElement.renderState.vars[T] = B : c[T] = B;
      }
      this.options.layoutId && (c.pointerEvents = p === this ? Zh(f == null ? void 0 : f.pointerEvents) || "" : "none");
    }
    clearSnapshot() {
      this.resumeFrom = this.snapshot = void 0;
    }
    // Only run on root
    resetTree() {
      this.root.nodes.forEach((c) => {
        var f;
        return (f = c.currentAnimation) == null ? void 0 : f.stop();
      }), this.root.nodes.forEach(Ew), this.root.sharedNodes.clear();
    }
  };
}
function FL(n) {
  n.updateLayout();
}
function ZL(n) {
  var i;
  const t = ((i = n.resumeFrom) == null ? void 0 : i.snapshot) || n.snapshot;
  if (n.isLead() && n.layout && t && n.hasListeners("didUpdate")) {
    const { layoutBox: a, measuredBox: r } = n.layout, { animationType: u } = n.options, c = t.source !== n.layout.source;
    if (u === "size")
      mi((y) => {
        const b = c ? t.measuredBox[y] : t.layoutBox[y], S = Ie(b);
        b.min = a[y].min, b.max = b.min + S;
      });
    else if (u === "x" || u === "y") {
      const y = u === "x" ? "y" : "x";
      My(c ? t.measuredBox[y] : t.layoutBox[y], a[y]);
    } else ZC(u, t.layoutBox, a) && mi((y) => {
      const b = c ? t.measuredBox[y] : t.layoutBox[y], S = Ie(a[y]);
      b.max = b.min + S, n.relativeTarget && !n.currentAnimation && (n.isProjectionDirty = !0, n.relativeTarget[y].max = n.relativeTarget[y].min + S);
    });
    const f = Pr();
    ec(f, a, t.layoutBox);
    const m = Pr();
    c ? ec(m, n.applyTransform(r, !0), t.measuredBox) : ec(m, a, t.layoutBox);
    const p = !qC(f);
    let g = !1;
    if (!n.resumeFrom) {
      const y = n.getClosestProjectingParent();
      if (y && !y.resumeFrom) {
        const { snapshot: b, layout: S } = y;
        if (b && S) {
          const T = n.options.layoutAnchor || void 0, C = we();
          od(C, t.layoutBox, b.layoutBox, T);
          const R = we();
          od(R, a, S.layoutBox, T), GC(C, R) || (g = !0), y.options.layoutRoot && (n.relativeTarget = R, n.relativeTargetOrigin = C, n.relativeParent = y);
        }
      }
    }
    n.notifyListeners("didUpdate", {
      layout: a,
      snapshot: t,
      delta: m,
      layoutDelta: f,
      hasLayoutChanged: p,
      hasRelativeLayoutChanged: g
    });
  } else if (n.isLead()) {
    const { onExitComplete: a } = n.options;
    a && a();
  }
  n.options.transition = void 0;
}
function QL(n) {
  n.parent && (n.isProjecting() || (n.isProjectionDirty = n.parent.isProjectionDirty), n.isSharedProjectionDirty || (n.isSharedProjectionDirty = !!(n.isProjectionDirty || n.parent.isProjectionDirty || n.parent.isSharedProjectionDirty)), n.isTransformDirty || (n.isTransformDirty = n.parent.isTransformDirty));
}
function KL(n) {
  n.isProjectionDirty = n.isSharedProjectionDirty = n.isTransformDirty = !1;
}
function IL(n) {
  n.clearSnapshot();
}
function Ew(n) {
  n.clearMeasurements();
}
function $L(n) {
  n.isLayoutDirty = !0, n.updateLayout();
}
function Aw(n) {
  n.isLayoutDirty = !1;
}
function WL(n) {
  n.isAnimationBlocked && n.layout && !n.isLayoutDirty && (n.snapshot = n.layout, n.isLayoutDirty = !0);
}
function JL(n) {
  const { visualElement: t } = n.options;
  t && t.getProps().onBeforeLayoutMeasure && t.notify("BeforeLayoutMeasure"), n.resetTransform();
}
function Dw(n) {
  n.finishAnimation(), n.targetDelta = n.relativeTarget = n.target = void 0, n.isProjectionDirty = !0;
}
function t5(n) {
  n.resolveTargetDelta();
}
function e5(n) {
  n.calcProjection();
}
function n5(n) {
  n.resetSkewAndRotation();
}
function i5(n) {
  n.removeLeadSnapshot();
}
function Rw(n, t, i) {
  n.translate = Ft(t.translate, 0, i), n.scale = Ft(t.scale, 1, i), n.origin = t.origin, n.originPoint = t.originPoint;
}
function Ow(n, t, i, a) {
  n.min = Ft(t.min, i.min, a), n.max = Ft(t.max, i.max, a);
}
function s5(n, t, i, a) {
  Ow(n.x, t.x, i.x, a), Ow(n.y, t.y, i.y, a);
}
function a5(n) {
  return n.animationValues && n.animationValues.opacityExit !== void 0;
}
const o5 = {
  duration: 0.45,
  ease: [0.4, 0, 0.1, 1]
}, zw = (n) => typeof navigator < "u" && navigator.userAgent && navigator.userAgent.toLowerCase().includes(n), kw = zw("applewebkit/") && !zw("chrome/") ? Math.round : Bn;
function Vw(n) {
  n.min = kw(n.min), n.max = kw(n.max);
}
function r5(n) {
  Vw(n.x), Vw(n.y);
}
function ZC(n, t, i) {
  return n === "position" || n === "preserve-aspect" && !DL(Sw(t), Sw(i), 0.2);
}
function l5(n) {
  var t;
  return n !== n.root && ((t = n.scroll) == null ? void 0 : t.wasRoot);
}
const u5 = FC({
  attachResizeListener: (n, t) => fc(n, "resize", t),
  measureScroll: () => {
    var n, t;
    return {
      x: document.documentElement.scrollLeft || ((n = document.body) == null ? void 0 : n.scrollLeft) || 0,
      y: document.documentElement.scrollTop || ((t = document.body) == null ? void 0 : t.scrollTop) || 0
    };
  },
  checkIsScrollRoot: () => !0
}), Rg = {
  current: void 0
}, QC = FC({
  measureScroll: (n) => ({
    x: n.scrollLeft,
    y: n.scrollTop
  }),
  defaultParent: () => {
    if (!Rg.current) {
      const n = new u5({});
      n.mount(window), n.setOptions({ layoutScroll: !0 }), Rg.current = n;
    }
    return Rg.current;
  },
  resetTransform: (n, t) => {
    n.style.transform = t !== void 0 ? t : "none";
  },
  checkIsScrollRoot: (n) => window.getComputedStyle(n).position === "fixed"
}), tf = G.createContext({
  transformPagePoint: (n) => n,
  isStatic: !1,
  reducedMotion: "never"
});
function Pw(n, t) {
  if (typeof n == "function")
    return n(t);
  n != null && (n.current = t);
}
function c5(...n) {
  return (t) => {
    let i = !1;
    const a = n.map((r) => {
      const u = Pw(r, t);
      return !i && typeof u == "function" && (i = !0), u;
    });
    if (i)
      return () => {
        for (let r = 0; r < a.length; r++) {
          const u = a[r];
          typeof u == "function" ? u() : Pw(n[r], null);
        }
      };
  };
}
function f5(...n) {
  return G.useCallback(c5(...n), n);
}
class h5 extends G.Component {
  getSnapshotBeforeUpdate(t) {
    const i = this.props.childRef.current;
    if (qh(i) && t.isPresent && !this.props.isPresent && this.props.pop !== !1) {
      const a = i.offsetParent, r = qh(a) && a.offsetWidth || 0, u = qh(a) && a.offsetHeight || 0, c = getComputedStyle(i), f = this.props.sizeRef.current;
      f.height = parseFloat(c.height), f.width = parseFloat(c.width), f.top = i.offsetTop, f.left = i.offsetLeft, f.right = r - f.width - f.left, f.bottom = u - f.height - f.top, f.direction = c.direction;
    }
    return null;
  }
  /**
   * Required with getSnapshotBeforeUpdate to stop React complaining.
   */
  componentDidUpdate() {
  }
  render() {
    return this.props.children;
  }
}
function d5({ children: n, isPresent: t, anchorX: i, anchorY: a, root: r, pop: u }) {
  var b;
  const c = G.useId(), f = G.useRef(null), m = G.useRef({
    width: 0,
    height: 0,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    direction: "ltr"
  }), { nonce: p } = G.useContext(tf), g = u !== !1 ? ((b = n.props) == null ? void 0 : b.ref) ?? (n == null ? void 0 : n.ref) : void 0, y = f5(f, g);
  return G.useInsertionEffect(() => {
    const { width: S, height: T, top: C, left: R, right: z, bottom: B, direction: H } = m.current;
    if (t || u === !1 || !f.current || !S || !T)
      return;
    const X = H === "rtl", Q = i === "left" ? X ? `right: ${z}` : `left: ${R}` : X ? `left: ${R}` : `right: ${z}`, ut = a === "bottom" ? `bottom: ${B}` : `top: ${C}`;
    f.current.dataset.motionPopId = c;
    const st = document.createElement("style");
    p && (st.nonce = p);
    const $ = r ?? document.head;
    return $.appendChild(st), st.sheet && st.sheet.insertRule(`
          [data-motion-pop-id="${c}"] {
            position: absolute !important;
            width: ${S}px !important;
            height: ${T}px !important;
            ${Q}px !important;
            ${ut}px !important;
          }
        `), () => {
      var lt;
      (lt = f.current) == null || lt.removeAttribute("data-motion-pop-id"), $.contains(st) && $.removeChild(st);
    };
  }, [t]), Z.jsx(h5, { isPresent: t, childRef: f, sizeRef: m, pop: u, children: u === !1 ? n : G.cloneElement(n, { ref: y }) });
}
const m5 = ({ children: n, initial: t, isPresent: i, onExitComplete: a, custom: r, presenceAffectsLayout: u, mode: c, anchorX: f, anchorY: m, root: p }) => {
  const g = Kc(p5), y = G.useId(), b = G.useRef(i), S = G.useRef(a);
  Ad(() => {
    b.current = i, S.current = a;
  });
  let T = !0, C = G.useMemo(() => (T = !1, {
    id: y,
    initial: t,
    isPresent: i,
    custom: r,
    onExitComplete: (R) => {
      g.set(R, !0);
      for (const z of g.values())
        if (!z)
          return;
      a && a();
    },
    register: (R) => (g.set(R, !1), () => {
      var z;
      g.delete(R), !b.current && !g.size && ((z = S.current) == null || z.call(S));
    })
  }), [i, g, a]);
  return u && T && (C = { ...C }), G.useMemo(() => {
    g.forEach((R, z) => g.set(z, !1));
  }, [i]), G.useEffect(() => {
    !i && !g.size && a && a();
  }, [i]), n = Z.jsx(d5, { pop: c === "popLayout", isPresent: i, anchorX: f, anchorY: m, root: p, children: n }), Z.jsx(Dd.Provider, { value: C, children: n });
};
function p5() {
  return /* @__PURE__ */ new Map();
}
function KC(n = !0) {
  const t = G.useContext(Dd);
  if (t === null)
    return [!0, null];
  const { isPresent: i, onExitComplete: a, register: r } = t, u = G.useId();
  G.useEffect(() => {
    if (n)
      return r(u);
  }, [n]);
  const c = G.useCallback(() => n && a && a(u), [u, a, n]);
  return !i && a ? [!1, c] : [!0];
}
const zh = (n) => n.key || "";
function Lw(n) {
  const t = [];
  return G.Children.forEach(n, (i) => {
    G.isValidElement(i) && t.push(i);
  }), t;
}
const g5 = ({ children: n, custom: t, initial: i = !0, onExitComplete: a, presenceAffectsLayout: r = !0, mode: u = "sync", propagate: c = !1, anchorX: f = "left", anchorY: m = "top", root: p }) => {
  const [g, y] = KC(c), b = G.useMemo(() => Lw(n), [n]), S = c && !g ? [] : b.map(zh), T = G.useRef(!0), C = G.useRef(b), R = Kc(() => /* @__PURE__ */ new Map()), z = G.useRef(/* @__PURE__ */ new Set()), [B, H] = G.useState(b), [X, Q] = G.useState(b);
  Ad(() => {
    T.current = !1, C.current = b;
    for (let $ = 0; $ < X.length; $++) {
      const lt = zh(X[$]);
      S.includes(lt) ? (R.delete(lt), z.current.delete(lt)) : R.get(lt) !== !0 && R.set(lt, !1);
    }
  }, [X, S.length, S.join("-")]);
  const ut = [];
  if (b !== B) {
    let $ = [...b];
    for (let lt = 0; lt < X.length; lt++) {
      const nt = X[lt], vt = zh(nt);
      S.includes(vt) || ($.splice(lt, 0, nt), ut.push(nt));
    }
    return u === "wait" && ut.length && ($ = ut), Q(Lw($)), H(b), null;
  }
  const { forceRender: st } = G.useContext(sv);
  return Z.jsx(Z.Fragment, { children: X.map(($) => {
    const lt = zh($), nt = c && !g ? !1 : b === X || S.includes(lt), vt = () => {
      if (z.current.has(lt))
        return;
      if (R.has(lt))
        z.current.add(lt), R.set(lt, !0);
      else
        return;
      let it = !0;
      R.forEach((ie) => {
        ie || (it = !1);
      }), it && (st == null || st(), Q(C.current), c && (y == null || y()), a && a());
    };
    return Z.jsx(m5, { isPresent: nt, initial: !T.current || i ? void 0 : !1, custom: t, presenceAffectsLayout: r, mode: u, root: p, onExitComplete: nt ? void 0 : vt, anchorX: f, anchorY: m, children: $ }, lt);
  }) });
}, IC = G.createContext({ strict: !1 }), _w = {
  animation: [
    "animate",
    "variants",
    "whileHover",
    "whileTap",
    "exit",
    "whileInView",
    "whileFocus",
    "whileDrag"
  ],
  exit: ["exit"],
  drag: ["drag", "dragControls"],
  focus: ["whileFocus"],
  hover: ["whileHover", "onHoverStart", "onHoverEnd"],
  tap: ["whileTap", "onTap", "onTapStart", "onTapCancel"],
  pan: ["onPan", "onPanStart", "onPanSessionStart", "onPanEnd"],
  inView: ["whileInView", "onViewportEnter", "onViewportLeave"],
  layout: ["layout", "layoutId"]
};
let Bw = !1;
function y5() {
  if (Bw)
    return;
  const n = {};
  for (const t in _w)
    n[t] = {
      isEnabled: (i) => _w[t].some((a) => !!i[a])
    };
  EC(n), Bw = !0;
}
function $C() {
  return y5(), tL();
}
function v5(n) {
  const t = $C();
  for (const i in n)
    t[i] = {
      ...t[i],
      ...n[i]
    };
  EC(t);
}
const b5 = /* @__PURE__ */ new Set([
  "animate",
  "exit",
  "variants",
  "initial",
  "style",
  "values",
  "variants",
  "transition",
  "transformTemplate",
  "custom",
  "inherit",
  "onBeforeLayoutMeasure",
  "onAnimationStart",
  "onAnimationComplete",
  "onUpdate",
  "onDragStart",
  "onDrag",
  "onDragEnd",
  "onMeasureDragConstraints",
  "onDirectionLock",
  "onDragTransitionEnd",
  "_dragX",
  "_dragY",
  "onHoverStart",
  "onHoverEnd",
  "onViewportEnter",
  "onViewportLeave",
  "globalTapTarget",
  "propagate",
  "ignoreStrict",
  "viewport"
]);
function rd(n) {
  return n.startsWith("while") || n.startsWith("drag") && n !== "draggable" || n.startsWith("layout") || n.startsWith("onTap") || n.startsWith("onPan") || n.startsWith("onLayout") || b5.has(n);
}
let WC = (n) => !rd(n);
function x5(n) {
  typeof n == "function" && (WC = (t) => t.startsWith("on") ? !rd(t) : n(t));
}
try {
  x5(require("@emotion/is-prop-valid").default);
} catch {
}
function S5(n, t, i) {
  const a = {};
  for (const r in n)
    r === "values" && typeof n.values == "object" || de(n[r]) || (WC(r) || i === !0 && rd(r) || !t && !rd(r) || // If trying to use native HTML drag events, forward drag listeners
    n.draggable && r.startsWith("onDrag")) && (a[r] = n[r]);
  return a;
}
const kd = /* @__PURE__ */ G.createContext({});
function w5(n, t) {
  if (zd(n)) {
    const { initial: i, animate: a } = n;
    return {
      initial: i === !1 || cc(i) ? i : void 0,
      animate: cc(a) ? a : void 0
    };
  }
  return n.inherit !== !1 ? t : {};
}
function M5(n) {
  const { initial: t, animate: i } = w5(n, G.useContext(kd));
  return G.useMemo(() => ({ initial: t, animate: i }), [Nw(t), Nw(i)]);
}
function Nw(n) {
  return Array.isArray(n) ? n.join(" ") : n;
}
const Rv = () => ({
  style: {},
  transform: {},
  transformOrigin: {},
  vars: {}
});
function JC(n, t, i) {
  for (const a in t)
    !de(t[a]) && !VC(a, i) && (n[a] = t[a]);
}
function T5({ transformTemplate: n }, t) {
  return G.useMemo(() => {
    const i = Rv();
    return Av(i, t, n), Object.assign({}, i.vars, i.style);
  }, [t]);
}
function C5(n, t) {
  const i = n.style || {}, a = {};
  return JC(a, i, n), Object.assign(a, T5(n, t)), a;
}
function E5(n, t) {
  const i = {}, a = C5(n, t);
  return n.drag && n.dragListener !== !1 && (i.draggable = !1, a.userSelect = a.WebkitUserSelect = a.WebkitTouchCallout = "none", a.touchAction = n.drag === !0 ? "none" : `pan-${n.drag === "x" ? "y" : "x"}`), n.tabIndex === void 0 && (n.onTap || n.onTapStart || n.whileTap) && (i.tabIndex = 0), i.style = a, i;
}
const tE = () => ({
  ...Rv(),
  attrs: {}
});
function A5(n, t, i, a) {
  const r = G.useMemo(() => {
    const u = tE();
    return PC(u, t, _C(a), n.transformTemplate, n.style), {
      ...u.attrs,
      style: { ...u.style }
    };
  }, [t]);
  if (n.style) {
    const u = {};
    JC(u, n.style, n), r.style = { ...u, ...r.style };
  }
  return r;
}
const D5 = [
  "animate",
  "circle",
  "defs",
  "desc",
  "ellipse",
  "g",
  "image",
  "line",
  "filter",
  "marker",
  "mask",
  "metadata",
  "path",
  "pattern",
  "polygon",
  "polyline",
  "rect",
  "stop",
  "switch",
  "symbol",
  "svg",
  "text",
  "tspan",
  "use",
  "view"
];
function Ov(n) {
  return (
    /**
     * If it's not a string, it's a custom React component. Currently we only support
     * HTML custom React components.
     */
    typeof n != "string" || /**
     * If it contains a dash, the element is a custom HTML webcomponent.
     */
    n.includes("-") ? !1 : (
      /**
       * If it's in our list of lowercase SVG tags, it's an SVG component
       */
      !!(D5.indexOf(n) > -1 || /**
       * If it contains a capital letter, it's an SVG component
       */
      /[A-Z]/u.test(n))
    )
  );
}
function R5(n, t, i, { latestValues: a }, r, u = !1, c) {
  const m = (c ?? Ov(n) ? A5 : E5)(t, a, r, n), p = S5(t, typeof n == "string", u), g = n !== G.Fragment ? { ...p, ...m, ref: i } : {}, { children: y } = t, b = G.useMemo(() => de(y) ? y.get() : y, [y]);
  return G.createElement(n, {
    ...g,
    children: b
  });
}
function O5({ scrapeMotionValuesFromProps: n, createRenderState: t }, i, a, r) {
  return {
    latestValues: z5(i, a, r, n),
    renderState: t()
  };
}
function z5(n, t, i, a) {
  const r = {}, u = a(n, {});
  for (const b in u)
    r[b] = Zh(u[b]);
  let { initial: c, animate: f } = n;
  const m = zd(n), p = TC(n);
  t && p && !m && n.inherit !== !1 && (c === void 0 && (c = t.initial), f === void 0 && (f = t.animate));
  let g = i ? i.initial === !1 : !1;
  g = g || c === !1;
  const y = g ? f : c;
  if (y && typeof y != "boolean" && !Od(y)) {
    const b = Array.isArray(y) ? y : [y];
    for (let S = 0; S < b.length; S++) {
      const T = vv(n, b[S]);
      if (T) {
        const { transitionEnd: C, transition: R, ...z } = T;
        for (const B in z) {
          let H = z[B];
          if (Array.isArray(H)) {
            const X = g ? H.length - 1 : 0;
            H = H[X];
          }
          H !== null && (r[B] = H);
        }
        for (const B in C)
          r[B] = C[B];
      }
    }
  }
  return r;
}
const eE = (n) => (t, i) => {
  const a = G.useContext(kd), r = G.useContext(Dd), u = () => O5(n, t, a, r);
  return i ? u() : Kc(u);
}, k5 = /* @__PURE__ */ eE({
  scrapeMotionValuesFromProps: Dv,
  createRenderState: Rv
}), V5 = /* @__PURE__ */ eE({
  scrapeMotionValuesFromProps: BC,
  createRenderState: tE
}), P5 = Symbol.for("motionComponentSymbol");
function L5(n, t, i) {
  const a = G.useRef(i);
  G.useInsertionEffect(() => {
    a.current = i;
  });
  const r = G.useRef(null);
  return G.useCallback((u) => {
    var f;
    u && ((f = n.onMount) == null || f.call(n, u)), t && (u ? t.mount(u) : t.unmount());
    const c = a.current;
    if (typeof c == "function")
      if (u) {
        const m = c(u);
        typeof m == "function" && (r.current = m);
      } else r.current ? (r.current(), r.current = null) : c(u);
    else c && (c.current = u);
  }, [t]);
}
const nE = G.createContext({});
function Dr(n) {
  return n && typeof n == "object" && Object.prototype.hasOwnProperty.call(n, "current");
}
function _5(n, t, i, a, r, u) {
  var H, X;
  const { visualElement: c } = G.useContext(kd), f = G.useContext(IC), m = G.useContext(Dd), p = G.useContext(tf), g = p.reducedMotion, y = p.skipAnimations, b = G.useRef(null), S = G.useRef(!1);
  a = a || f.renderer, !b.current && a && (b.current = a(n, {
    visualState: t,
    parent: c,
    props: i,
    presenceContext: m,
    blockInitialAnimation: m ? m.initial === !1 : !1,
    reducedMotionConfig: g,
    skipAnimations: y,
    isSVG: u
  }), S.current && b.current && (b.current.manuallyAnimateOnMount = !0));
  const T = b.current, C = G.useContext(nE);
  T && !T.projection && r && (T.type === "html" || T.type === "svg") && B5(b.current, i, r, C);
  const R = G.useRef(!1);
  G.useInsertionEffect(() => {
    T && R.current && T.update(i, m);
  });
  const z = i[dC], B = G.useRef(!!z && typeof window < "u" && !((H = window.MotionHandoffIsComplete) != null && H.call(window, z)) && ((X = window.MotionHasOptimisedAnimation) == null ? void 0 : X.call(window, z)));
  return Ad(() => {
    S.current = !0, T && (R.current = !0, window.MotionIsMounted = !0, T.updateFeatures(), T.scheduleRenderMicrotask(), B.current && T.animationState && T.animationState.animateChanges());
  }), G.useEffect(() => {
    T && (!B.current && T.animationState && T.animationState.animateChanges(), B.current && (queueMicrotask(() => {
      var Q;
      (Q = window.MotionHandoffMarkAsComplete) == null || Q.call(window, z);
    }), B.current = !1), T.enteringChildren = void 0);
  }), T;
}
function B5(n, t, i, a) {
  const { layoutId: r, layout: u, drag: c, dragConstraints: f, layoutScroll: m, layoutRoot: p, layoutAnchor: g, layoutCrossfade: y } = t;
  n.projection = new i(n.latestValues, t["data-framer-portal-id"] ? void 0 : iE(n.parent)), n.projection.setOptions({
    layoutId: r,
    layout: u,
    alwaysMeasureLayout: !!c || f && Dr(f),
    visualElement: n,
    /**
     * TODO: Update options in an effect. This could be tricky as it'll be too late
     * to update by the time layout animations run.
     * We also need to fix this safeToRemove by linking it up to the one returned by usePresence,
     * ensuring it gets called if there's no potential layout animations.
     *
     */
    animationType: typeof u == "string" ? u : "both",
    initialPromotionConfig: a,
    crossfade: y,
    layoutScroll: m,
    layoutRoot: p,
    layoutAnchor: g
  });
}
function iE(n) {
  if (n)
    return n.options.allowProjection !== !1 ? n.projection : iE(n.parent);
}
function Og(n, { forwardMotionProps: t = !1, type: i } = {}, a, r) {
  a && v5(a);
  const u = i ? i === "svg" : Ov(n), c = u ? V5 : k5;
  function f(p, g) {
    let y;
    const b = {
      ...G.useContext(tf),
      ...p,
      layoutId: N5(p)
    }, { isStatic: S } = b, T = M5(p), C = c(p, S);
    if (!S && typeof window < "u") {
      U5();
      const R = j5(b);
      y = R.MeasureLayout, T.visualElement = _5(n, C, b, r, R.ProjectionNode, u);
    }
    return Z.jsxs(kd.Provider, { value: T, children: [y && T.visualElement ? Z.jsx(y, { visualElement: T.visualElement, ...b }) : null, R5(n, p, L5(C, T.visualElement, g), C, S, t, u)] });
  }
  f.displayName = `motion.${typeof n == "string" ? n : `create(${n.displayName ?? n.name ?? ""})`}`;
  const m = G.forwardRef(f);
  return m[P5] = n, m;
}
function N5({ layoutId: n }) {
  const t = G.useContext(sv).id;
  return t && n !== void 0 ? t + "-" + n : n;
}
function U5(n, t) {
  G.useContext(IC).strict;
}
function j5(n) {
  const t = $C(), { drag: i, layout: a } = t;
  if (!i && !a)
    return {};
  const r = { ...i, ...a };
  return {
    MeasureLayout: i != null && i.isEnabled(n) || a != null && a.isEnabled(n) ? r.MeasureLayout : void 0,
    ProjectionNode: r.ProjectionNode
  };
}
function H5(n, t) {
  if (typeof Proxy > "u")
    return Og;
  const i = /* @__PURE__ */ new Map(), a = (u, c) => Og(u, c, n, t), r = (u, c) => a(u, c);
  return new Proxy(r, {
    /**
     * Called when `motion` is referenced with a prop: `motion.div`, `motion.input` etc.
     * The prop name is passed through as `key` and we can use that to generate a `motion`
     * DOM component with that name.
     */
    get: (u, c) => c === "create" ? a : (i.has(c) || i.set(c, Og(c, void 0, n, t)), i.get(c))
  });
}
const q5 = (n, t) => t.isSVG ?? Ov(n) ? new yL(t) : new fL(t, {
  allowProjection: n !== G.Fragment
});
class G5 extends fa {
  /**
   * We dynamically generate the AnimationState manager as it contains a reference
   * to the underlying animation library. We only want to load that if we load this,
   * so people can optionally code split it out using the `m` component.
   */
  constructor(t) {
    super(t), t.animationState || (t.animationState = wL(t));
  }
  updateAnimationControlsSubscription() {
    const { animate: t } = this.node.getProps();
    Od(t) && (this.unmountControls = t.subscribe(this.node));
  }
  /**
   * Subscribe any provided AnimationControls to the component's VisualElement
   */
  mount() {
    this.updateAnimationControlsSubscription();
  }
  update() {
    const { animate: t } = this.node.getProps(), { animate: i } = this.node.prevProps || {};
    t !== i && this.updateAnimationControlsSubscription();
  }
  unmount() {
    var t;
    this.node.animationState.reset(), (t = this.unmountControls) == null || t.call(this);
  }
}
let Y5 = 0;
class X5 extends fa {
  constructor() {
    super(...arguments), this.id = Y5++, this.isExitComplete = !1;
  }
  update() {
    var u;
    if (!this.node.presenceContext)
      return;
    const { isPresent: t, onExitComplete: i } = this.node.presenceContext, { isPresent: a } = this.node.prevPresenceContext || {};
    if (!this.node.animationState || t === a)
      return;
    if (t && a === !1) {
      if (this.isExitComplete) {
        const { initial: c, custom: f } = this.node.getProps();
        if (typeof c == "string" || typeof c == "object" && c !== null && !Array.isArray(c)) {
          const m = Mo(this.node, c, f);
          if (m) {
            const { transition: p, transitionEnd: g, ...y } = m;
            for (const b in y)
              (u = this.node.getValue(b)) == null || u.jump(y[b]);
          }
        }
        this.node.animationState.reset(), this.node.animationState.animateChanges();
      } else
        this.node.animationState.setActive("exit", !1);
      this.isExitComplete = !1;
      return;
    }
    const r = this.node.animationState.setActive("exit", !t);
    i && !t && r.then(() => {
      this.isExitComplete = !0, i(this.id);
    });
  }
  mount() {
    const { register: t, onExitComplete: i } = this.node.presenceContext || {};
    i && i(this.id), t && (this.unmount = t(this.id));
  }
  unmount() {
  }
}
const F5 = {
  animation: {
    Feature: G5
  },
  exit: {
    Feature: X5
  }
};
function ef(n) {
  return {
    point: {
      x: n.pageX,
      y: n.pageY
    }
  };
}
const Z5 = (n) => (t) => Mv(t) && n(t, ef(t));
function nc(n, t, i, a) {
  return fc(n, t, Z5(i), a);
}
const sE = ({ current: n }) => n ? n.ownerDocument.defaultView : null, Uw = (n, t) => Math.abs(n - t);
function Q5(n, t) {
  const i = Uw(n.x, t.x), a = Uw(n.y, t.y);
  return Math.sqrt(i ** 2 + a ** 2);
}
const jw = /* @__PURE__ */ new Set(["auto", "scroll"]);
class aE {
  constructor(t, i, { transformPagePoint: a, contextWindow: r = window, dragSnapToOrigin: u = !1, distanceThreshold: c = 3, element: f } = {}) {
    if (this.startEvent = null, this.lastMoveEvent = null, this.lastMoveEventInfo = null, this.lastRawMoveEventInfo = null, this.handlers = {}, this.contextWindow = window, this.scrollPositions = /* @__PURE__ */ new Map(), this.removeScrollListeners = null, this.onElementScroll = (T) => {
      this.handleScroll(T.target);
    }, this.onWindowScroll = () => {
      this.handleScroll(window);
    }, this.updatePoint = () => {
      if (!(this.lastMoveEvent && this.lastMoveEventInfo))
        return;
      this.lastRawMoveEventInfo && (this.lastMoveEventInfo = kh(this.lastRawMoveEventInfo, this.transformPagePoint));
      const T = zg(this.lastMoveEventInfo, this.history), C = this.startEvent !== null, R = Q5(T.offset, { x: 0, y: 0 }) >= this.distanceThreshold;
      if (!C && !R)
        return;
      const { point: z } = T, { timestamp: B } = Ve;
      this.history.push({ ...z, timestamp: B });
      const { onStart: H, onMove: X } = this.handlers;
      C || (H && H(this.lastMoveEvent, T), this.startEvent = this.lastMoveEvent), X && X(this.lastMoveEvent, T);
    }, this.handlePointerMove = (T, C) => {
      this.lastMoveEvent = T, this.lastRawMoveEventInfo = C, this.lastMoveEventInfo = kh(C, this.transformPagePoint), jt.update(this.updatePoint, !0);
    }, this.handlePointerUp = (T, C) => {
      this.end();
      const { onEnd: R, onSessionEnd: z, resumeAnimation: B } = this.handlers;
      if ((this.dragSnapToOrigin || !this.startEvent) && B && B(), !(this.lastMoveEvent && this.lastMoveEventInfo))
        return;
      const H = zg(T.type === "pointercancel" ? this.lastMoveEventInfo : kh(C, this.transformPagePoint), this.history);
      this.startEvent && R && R(T, H), z && z(T, H);
    }, !Mv(t))
      return;
    this.dragSnapToOrigin = u, this.handlers = i, this.transformPagePoint = a, this.distanceThreshold = c, this.contextWindow = r || window;
    const m = ef(t), p = kh(m, this.transformPagePoint), { point: g } = p, { timestamp: y } = Ve;
    this.history = [{ ...g, timestamp: y }];
    const { onSessionStart: b } = i;
    b && b(t, zg(p, this.history));
    const S = { passive: !0, capture: !0 };
    this.removeListeners = $c(nc(this.contextWindow, "pointermove", this.handlePointerMove, S), nc(this.contextWindow, "pointerup", this.handlePointerUp, S), nc(this.contextWindow, "pointercancel", this.handlePointerUp, S)), f && this.startScrollTracking(f);
  }
  /**
   * Start tracking scroll on ancestors and window.
   */
  startScrollTracking(t) {
    let i = t.parentElement;
    for (; i; ) {
      const a = getComputedStyle(i);
      (jw.has(a.overflowX) || jw.has(a.overflowY)) && this.scrollPositions.set(i, {
        x: i.scrollLeft,
        y: i.scrollTop
      }), i = i.parentElement;
    }
    this.scrollPositions.set(window, {
      x: window.scrollX,
      y: window.scrollY
    }), window.addEventListener("scroll", this.onElementScroll, {
      capture: !0
    }), window.addEventListener("scroll", this.onWindowScroll), this.removeScrollListeners = () => {
      window.removeEventListener("scroll", this.onElementScroll, {
        capture: !0
      }), window.removeEventListener("scroll", this.onWindowScroll);
    };
  }
  /**
   * Handle scroll compensation during drag.
   *
   * For element scroll: adjusts history origin since pageX/pageY doesn't change.
   * For window scroll: adjusts lastMoveEventInfo since pageX/pageY would change.
   */
  handleScroll(t) {
    const i = this.scrollPositions.get(t);
    if (!i)
      return;
    const a = t === window, r = a ? { x: window.scrollX, y: window.scrollY } : {
      x: t.scrollLeft,
      y: t.scrollTop
    }, u = { x: r.x - i.x, y: r.y - i.y };
    u.x === 0 && u.y === 0 || (a ? this.lastMoveEventInfo && (this.lastMoveEventInfo.point.x += u.x, this.lastMoveEventInfo.point.y += u.y) : this.history.length > 0 && (this.history[0].x -= u.x, this.history[0].y -= u.y), this.scrollPositions.set(t, r), jt.update(this.updatePoint, !0));
  }
  updateHandlers(t) {
    this.handlers = t;
  }
  end() {
    this.removeListeners && this.removeListeners(), this.removeScrollListeners && this.removeScrollListeners(), this.scrollPositions.clear(), Wi(this.updatePoint);
  }
}
function kh(n, t) {
  return t ? { point: t(n.point) } : n;
}
function Hw(n, t) {
  return { x: n.x - t.x, y: n.y - t.y };
}
function zg({ point: n }, t) {
  return {
    point: n,
    delta: Hw(n, oE(t)),
    offset: Hw(n, K5(t)),
    velocity: I5(t, 0.1)
  };
}
function K5(n) {
  return n[0];
}
function oE(n) {
  return n[n.length - 1];
}
function I5(n, t) {
  if (n.length < 2)
    return { x: 0, y: 0 };
  let i = n.length - 1, a = null;
  const r = oE(n);
  for (; i >= 0 && (a = n[i], !(r.timestamp - a.timestamp > /* @__PURE__ */ rn(t))); )
    i--;
  if (!a)
    return { x: 0, y: 0 };
  a === n[0] && n.length > 2 && r.timestamp - a.timestamp > /* @__PURE__ */ rn(t) * 2 && (a = n[1]);
  const u = /* @__PURE__ */ Pn(r.timestamp - a.timestamp);
  if (u === 0)
    return { x: 0, y: 0 };
  const c = {
    x: (r.x - a.x) / u,
    y: (r.y - a.y) / u
  };
  return c.x === 1 / 0 && (c.x = 0), c.y === 1 / 0 && (c.y = 0), c;
}
function $5(n, { min: t, max: i }, a) {
  return t !== void 0 && n < t ? n = a ? Ft(t, n, a.min) : Math.max(n, t) : i !== void 0 && n > i && (n = a ? Ft(i, n, a.max) : Math.min(n, i)), n;
}
function qw(n, t, i) {
  return {
    min: t !== void 0 ? n.min + t : void 0,
    max: i !== void 0 ? n.max + i - (n.max - n.min) : void 0
  };
}
function W5(n, { top: t, left: i, bottom: a, right: r }) {
  return {
    x: qw(n.x, i, r),
    y: qw(n.y, t, a)
  };
}
function Gw(n, t) {
  let i = t.min - n.min, a = t.max - n.max;
  return t.max - t.min < n.max - n.min && ([i, a] = [a, i]), { min: i, max: a };
}
function J5(n, t) {
  return {
    x: Gw(n.x, t.x),
    y: Gw(n.y, t.y)
  };
}
function t_(n, t) {
  let i = 0.5;
  const a = Ie(n), r = Ie(t);
  return r > a ? i = /* @__PURE__ */ rc(t.min, t.max - a, n.min) : a > r && (i = /* @__PURE__ */ rc(n.min, n.max - r, t.min)), Vi(0, 1, i);
}
function e_(n, t) {
  const i = {};
  return t.min !== void 0 && (i.min = t.min - n.min), t.max !== void 0 && (i.max = t.max - n.min), i;
}
const Ty = 0.35;
function n_(n = Ty) {
  return n === !1 ? n = 0 : n === !0 && (n = Ty), {
    x: Yw(n, "left", "right"),
    y: Yw(n, "top", "bottom")
  };
}
function Yw(n, t, i) {
  return {
    min: Xw(n, t),
    max: Xw(n, i)
  };
}
function Xw(n, t) {
  return typeof n == "number" ? n : n[t] || 0;
}
const i_ = /* @__PURE__ */ new WeakMap();
class s_ {
  constructor(t) {
    this.openDragLock = null, this.isDragging = !1, this.currentDirection = null, this.originPoint = { x: 0, y: 0 }, this.constraints = !1, this.hasMutatedConstraints = !1, this.elastic = we(), this.latestPointerEvent = null, this.latestPanInfo = null, this.visualElement = t;
  }
  start(t, { snapToCursor: i = !1, distanceThreshold: a } = {}) {
    const { presenceContext: r } = this.visualElement;
    if (r && r.isPresent === !1)
      return;
    const u = (y) => {
      i && this.snapToCursor(ef(y).point), this.stopAnimation();
    }, c = (y, b) => {
      const { drag: S, dragPropagation: T, onDragStart: C } = this.getProps();
      if (S && !T && (this.openDragLock && this.openDragLock(), this.openDragLock = D4(S), !this.openDragLock))
        return;
      this.latestPointerEvent = y, this.latestPanInfo = b, this.isDragging = !0, this.currentDirection = null, this.resolveConstraints(), this.visualElement.projection && (this.visualElement.projection.isAnimationBlocked = !0, this.visualElement.projection.target = void 0), mi((z) => {
        let B = this.getAxisMotionValue(z).get() || 0;
        if (ki.test(B)) {
          const { projection: H } = this.visualElement;
          if (H && H.layout) {
            const X = H.layout.layoutBox[z];
            X && (B = Ie(X) * (parseFloat(B) / 100));
          }
        }
        this.originPoint[z] = B;
      }), C && jt.update(() => C(y, b), !1, !0), my(this.visualElement, "transform");
      const { animationState: R } = this.visualElement;
      R && R.setActive("whileDrag", !0);
    }, f = (y, b) => {
      this.latestPointerEvent = y, this.latestPanInfo = b;
      const { dragPropagation: S, dragDirectionLock: T, onDirectionLock: C, onDrag: R } = this.getProps();
      if (!S && !this.openDragLock)
        return;
      const { offset: z } = b;
      if (T && this.currentDirection === null) {
        this.currentDirection = o_(z), this.currentDirection !== null && C && C(this.currentDirection);
        return;
      }
      this.updateAxis("x", b.point, z), this.updateAxis("y", b.point, z), this.visualElement.render(), R && jt.update(() => R(y, b), !1, !0);
    }, m = (y, b) => {
      this.latestPointerEvent = y, this.latestPanInfo = b, this.stop(y, b), this.latestPointerEvent = null, this.latestPanInfo = null;
    }, p = () => {
      const { dragSnapToOrigin: y } = this.getProps();
      (y || this.constraints) && this.startAnimation({ x: 0, y: 0 });
    }, { dragSnapToOrigin: g } = this.getProps();
    this.panSession = new aE(t, {
      onSessionStart: u,
      onStart: c,
      onMove: f,
      onSessionEnd: m,
      resumeAnimation: p
    }, {
      transformPagePoint: this.visualElement.getTransformPagePoint(),
      dragSnapToOrigin: g,
      distanceThreshold: a,
      contextWindow: sE(this.visualElement),
      element: this.visualElement.current
    });
  }
  /**
   * @internal
   */
  stop(t, i) {
    const a = t || this.latestPointerEvent, r = i || this.latestPanInfo, u = this.isDragging;
    if (this.cancel(), !u || !r || !a)
      return;
    const { velocity: c } = r;
    this.startAnimation(c);
    const { onDragEnd: f } = this.getProps();
    f && jt.postRender(() => f(a, r));
  }
  /**
   * @internal
   */
  cancel() {
    this.isDragging = !1;
    const { projection: t, animationState: i } = this.visualElement;
    t && (t.isAnimationBlocked = !1), this.endPanSession();
    const { dragPropagation: a } = this.getProps();
    !a && this.openDragLock && (this.openDragLock(), this.openDragLock = null), i && i.setActive("whileDrag", !1);
  }
  /**
   * Clean up the pan session without modifying other drag state.
   * This is used during unmount to ensure event listeners are removed
   * without affecting projection animations or drag locks.
   * @internal
   */
  endPanSession() {
    this.panSession && this.panSession.end(), this.panSession = void 0;
  }
  updateAxis(t, i, a) {
    const { drag: r } = this.getProps();
    if (!a || !Vh(t, r, this.currentDirection))
      return;
    const u = this.getAxisMotionValue(t);
    let c = this.originPoint[t] + a[t];
    this.constraints && this.constraints[t] && (c = $5(c, this.constraints[t], this.elastic[t])), u.set(c);
  }
  resolveConstraints() {
    var u;
    const { dragConstraints: t, dragElastic: i } = this.getProps(), a = this.visualElement.projection && !this.visualElement.projection.layout ? this.visualElement.projection.measure(!1) : (u = this.visualElement.projection) == null ? void 0 : u.layout, r = this.constraints;
    t && Dr(t) ? this.constraints || (this.constraints = this.resolveRefConstraints()) : t && a ? this.constraints = W5(a.layoutBox, t) : this.constraints = !1, this.elastic = n_(i), r !== this.constraints && !Dr(t) && a && this.constraints && !this.hasMutatedConstraints && mi((c) => {
      this.constraints !== !1 && this.getAxisMotionValue(c) && (this.constraints[c] = e_(a.layoutBox[c], this.constraints[c]));
    });
  }
  resolveRefConstraints() {
    const { dragConstraints: t, onMeasureDragConstraints: i } = this.getProps();
    if (!t || !Dr(t))
      return !1;
    const a = t.current;
    ua(a !== null, "If `dragConstraints` is set as a React ref, that ref must be passed to another component's `ref` prop.", "drag-constraints-ref");
    const { projection: r } = this.visualElement;
    if (!r || !r.layout)
      return !1;
    r.root && (r.root.scroll = void 0, r.root.updateScroll());
    const u = aL(a, r.root, this.visualElement.getTransformPagePoint());
    let c = J5(r.layout.layoutBox, u);
    if (i) {
      const f = i(nL(c));
      this.hasMutatedConstraints = !!f, f && (c = DC(f));
    }
    return c;
  }
  startAnimation(t) {
    const { drag: i, dragMomentum: a, dragElastic: r, dragTransition: u, dragSnapToOrigin: c, onDragTransitionEnd: f } = this.getProps(), m = this.constraints || {}, p = mi((g) => {
      if (!Vh(g, i, this.currentDirection))
        return;
      let y = m && m[g] || {};
      (c === !0 || c === g) && (y = { min: 0, max: 0 });
      const b = r ? 200 : 1e6, S = r ? 40 : 1e7, T = {
        type: "inertia",
        velocity: a ? t[g] : 0,
        bounceStiffness: b,
        bounceDamping: S,
        timeConstant: 750,
        restDelta: 1,
        restSpeed: 10,
        ...u,
        ...y
      };
      return this.startAxisValueAnimation(g, T);
    });
    return Promise.all(p).then(f);
  }
  startAxisValueAnimation(t, i) {
    const a = this.getAxisMotionValue(t);
    return my(this.visualElement, t), a.start(yv(t, a, 0, i, this.visualElement, !1));
  }
  stopAnimation() {
    mi((t) => this.getAxisMotionValue(t).stop());
  }
  /**
   * Drag works differently depending on which props are provided.
   *
   * - If _dragX and _dragY are provided, we output the gesture delta directly to those motion values.
   * - Otherwise, we apply the delta to the x/y motion values.
   */
  getAxisMotionValue(t) {
    const i = `_drag${t.toUpperCase()}`, r = this.visualElement.getProps()[i];
    return r || this.visualElement.getValue(t, this.visualElement.latestValues[t] ?? 0);
  }
  snapToCursor(t) {
    mi((i) => {
      const { drag: a } = this.getProps();
      if (!Vh(i, a, this.currentDirection))
        return;
      const { projection: r } = this.visualElement, u = this.getAxisMotionValue(i);
      if (r && r.layout) {
        const { min: c, max: f } = r.layout.layoutBox[i], m = u.get() || 0;
        u.set(t[i] - Ft(c, f, 0.5) + m);
      }
    });
  }
  /**
   * When the viewport resizes we want to check if the measured constraints
   * have changed and, if so, reposition the element within those new constraints
   * relative to where it was before the resize.
   */
  scalePositionWithinConstraints() {
    if (!this.visualElement.current)
      return;
    const { drag: t, dragConstraints: i } = this.getProps(), { projection: a } = this.visualElement;
    if (!Dr(i) || !a || !this.constraints)
      return;
    this.stopAnimation();
    const r = { x: 0, y: 0 };
    mi((c) => {
      const f = this.getAxisMotionValue(c);
      if (f && this.constraints !== !1) {
        const m = f.get();
        r[c] = t_({ min: m, max: m }, this.constraints[c]);
      }
    });
    const { transformTemplate: u } = this.visualElement.getProps();
    this.visualElement.current.style.transform = u ? u({}, "") : "none", a.root && a.root.updateScroll(), a.updateLayout(), this.constraints = !1, this.resolveConstraints(), mi((c) => {
      if (!Vh(c, t, null))
        return;
      const f = this.getAxisMotionValue(c), { min: m, max: p } = this.constraints[c];
      f.set(Ft(m, p, r[c]));
    }), this.visualElement.render();
  }
  addListeners() {
    if (!this.visualElement.current)
      return;
    i_.set(this.visualElement, this);
    const t = this.visualElement.current, i = nc(t, "pointerdown", (p) => {
      const { drag: g, dragListener: y = !0 } = this.getProps(), b = p.target, S = b !== t && P4(b);
      g && y && !S && this.start(p);
    });
    let a;
    const r = () => {
      const { dragConstraints: p } = this.getProps();
      Dr(p) && p.current && (this.constraints = this.resolveRefConstraints(), a || (a = a_(t, p.current, () => this.scalePositionWithinConstraints())));
    }, { projection: u } = this.visualElement, c = u.addEventListener("measure", r);
    u && !u.layout && (u.root && u.root.updateScroll(), u.updateLayout()), jt.read(r);
    const f = fc(window, "resize", () => this.scalePositionWithinConstraints()), m = u.addEventListener("didUpdate", (({ delta: p, hasLayoutChanged: g }) => {
      this.isDragging && g && (mi((y) => {
        const b = this.getAxisMotionValue(y);
        b && (this.originPoint[y] += p[y].translate, b.set(b.get() + p[y].translate));
      }), this.visualElement.render());
    }));
    return () => {
      f(), i(), c(), m && m(), a && a();
    };
  }
  getProps() {
    const t = this.visualElement.getProps(), { drag: i = !1, dragDirectionLock: a = !1, dragPropagation: r = !1, dragConstraints: u = !1, dragElastic: c = Ty, dragMomentum: f = !0 } = t;
    return {
      ...t,
      drag: i,
      dragDirectionLock: a,
      dragPropagation: r,
      dragConstraints: u,
      dragElastic: c,
      dragMomentum: f
    };
  }
}
function Fw(n) {
  let t = !0;
  return () => {
    if (t) {
      t = !1;
      return;
    }
    n();
  };
}
function a_(n, t, i) {
  const a = W1(n, Fw(i)), r = W1(t, Fw(i));
  return () => {
    a(), r();
  };
}
function Vh(n, t, i) {
  return (t === !0 || t === n) && (i === null || i === n);
}
function o_(n, t = 10) {
  let i = null;
  return Math.abs(n.y) > t ? i = "y" : Math.abs(n.x) > t && (i = "x"), i;
}
class r_ extends fa {
  constructor(t) {
    super(t), this.removeGroupControls = Bn, this.removeListeners = Bn, this.controls = new s_(t);
  }
  mount() {
    const { dragControls: t } = this.node.getProps();
    t && (this.removeGroupControls = t.subscribe(this.controls)), this.removeListeners = this.controls.addListeners() || Bn;
  }
  update() {
    const { dragControls: t } = this.node.getProps(), { dragControls: i } = this.node.prevProps || {};
    t !== i && (this.removeGroupControls(), t && (this.removeGroupControls = t.subscribe(this.controls)));
  }
  unmount() {
    this.removeGroupControls(), this.removeListeners(), this.controls.isDragging || this.controls.endPanSession();
  }
}
const kg = (n) => (t, i) => {
  n && jt.update(() => n(t, i), !1, !0);
};
class l_ extends fa {
  constructor() {
    super(...arguments), this.removePointerDownListener = Bn;
  }
  onPointerDown(t) {
    this.session = new aE(t, this.createPanHandlers(), {
      transformPagePoint: this.node.getTransformPagePoint(),
      contextWindow: sE(this.node)
    });
  }
  createPanHandlers() {
    const { onPanSessionStart: t, onPanStart: i, onPan: a, onPanEnd: r } = this.node.getProps();
    return {
      onSessionStart: kg(t),
      onStart: kg(i),
      onMove: kg(a),
      onEnd: (u, c) => {
        delete this.session, r && jt.postRender(() => r(u, c));
      }
    };
  }
  mount() {
    this.removePointerDownListener = nc(this.node.current, "pointerdown", (t) => this.onPointerDown(t));
  }
  update() {
    this.session && this.session.updateHandlers(this.createPanHandlers());
  }
  unmount() {
    this.removePointerDownListener(), this.session && this.session.end();
  }
}
let Vg = !1;
class u_ extends G.Component {
  /**
   * This only mounts projection nodes for components that
   * need measuring, we might want to do it for all components
   * in order to incorporate transforms
   */
  componentDidMount() {
    const { visualElement: t, layoutGroup: i, switchLayoutGroup: a, layoutId: r } = this.props, { projection: u } = t;
    u && (i.group && i.group.add(u), a && a.register && r && a.register(u), Vg && u.root.didUpdate(), u.addEventListener("animationComplete", () => {
      this.safeToRemove();
    }), u.setOptions({
      ...u.options,
      layoutDependency: this.props.layoutDependency,
      onExitComplete: () => this.safeToRemove()
    })), Qh.hasEverUpdated = !0;
  }
  getSnapshotBeforeUpdate(t) {
    const { layoutDependency: i, visualElement: a, drag: r, isPresent: u } = this.props, { projection: c } = a;
    return c && (c.isPresent = u, t.layoutDependency !== i && c.setOptions({
      ...c.options,
      layoutDependency: i
    }), Vg = !0, r || t.layoutDependency !== i || i === void 0 || t.isPresent !== u ? c.willUpdate() : this.safeToRemove(), t.isPresent !== u && (u ? c.promote() : c.relegate() || jt.postRender(() => {
      const f = c.getStack();
      (!f || !f.members.length) && this.safeToRemove();
    }))), null;
  }
  componentDidUpdate() {
    const { visualElement: t, layoutAnchor: i } = this.props, { projection: a } = t;
    a && (a.options.layoutAnchor = i, a.root.didUpdate(), wv.postRender(() => {
      !a.currentAnimation && a.isLead() && this.safeToRemove();
    }));
  }
  componentWillUnmount() {
    const { visualElement: t, layoutGroup: i, switchLayoutGroup: a } = this.props, { projection: r } = t;
    Vg = !0, r && (r.scheduleCheckAfterUnmount(), i && i.group && i.group.remove(r), a && a.deregister && a.deregister(r));
  }
  safeToRemove() {
    const { safeToRemove: t } = this.props;
    t && t();
  }
  render() {
    return null;
  }
}
function rE(n) {
  const [t, i] = KC(), a = G.useContext(sv);
  return Z.jsx(u_, { ...n, layoutGroup: a, switchLayoutGroup: G.useContext(nE), isPresent: t, safeToRemove: i });
}
const c_ = {
  pan: {
    Feature: l_
  },
  drag: {
    Feature: r_,
    ProjectionNode: QC,
    MeasureLayout: rE
  }
};
function Zw(n, t, i) {
  const { props: a } = n;
  n.animationState && a.whileHover && n.animationState.setActive("whileHover", i === "Start");
  const r = "onHover" + i, u = a[r];
  u && jt.postRender(() => u(t, ef(t)));
}
class f_ extends fa {
  mount() {
    const { current: t } = this.node;
    t && (this.unmount = O4(t, (i, a) => (Zw(this.node, a, "Start"), (r) => Zw(this.node, r, "End"))));
  }
  unmount() {
  }
}
class h_ extends fa {
  constructor() {
    super(...arguments), this.isActive = !1;
  }
  onFocus() {
    let t = !1;
    try {
      t = this.node.current.matches(":focus-visible");
    } catch {
      t = !0;
    }
    !t || !this.node.animationState || (this.node.animationState.setActive("whileFocus", !0), this.isActive = !0);
  }
  onBlur() {
    !this.isActive || !this.node.animationState || (this.node.animationState.setActive("whileFocus", !1), this.isActive = !1);
  }
  mount() {
    this.unmount = $c(fc(this.node.current, "focus", () => this.onFocus()), fc(this.node.current, "blur", () => this.onBlur()));
  }
  unmount() {
  }
}
function Qw(n, t, i) {
  const { props: a } = n;
  if (n.current instanceof HTMLButtonElement && n.current.disabled)
    return;
  n.animationState && a.whileTap && n.animationState.setActive("whileTap", i === "Start");
  const r = "onTap" + (i === "End" ? "" : i), u = a[r];
  u && jt.postRender(() => u(t, ef(t)));
}
class d_ extends fa {
  mount() {
    const { current: t } = this.node;
    if (!t)
      return;
    const { globalTapTarget: i, propagate: a } = this.node.props;
    this.unmount = _4(t, (r, u) => (Qw(this.node, u, "Start"), (c, { success: f }) => Qw(this.node, c, f ? "End" : "Cancel")), {
      useGlobalTarget: i,
      stopPropagation: (a == null ? void 0 : a.tap) === !1
    });
  }
  unmount() {
  }
}
const Cy = /* @__PURE__ */ new WeakMap(), Pg = /* @__PURE__ */ new WeakMap(), m_ = (n) => {
  const t = Cy.get(n.target);
  t && t(n);
}, p_ = (n) => {
  n.forEach(m_);
};
function g_({ root: n, ...t }) {
  const i = n || document;
  Pg.has(i) || Pg.set(i, {});
  const a = Pg.get(i), r = JSON.stringify(t);
  return a[r] || (a[r] = new IntersectionObserver(p_, { root: n, ...t })), a[r];
}
function y_(n, t, i) {
  const a = g_(t);
  return Cy.set(n, i), a.observe(n), () => {
    Cy.delete(n), a.unobserve(n);
  };
}
const v_ = {
  some: 0,
  all: 1
};
class b_ extends fa {
  constructor() {
    super(...arguments), this.hasEnteredView = !1, this.isInView = !1;
  }
  startObserver() {
    var m;
    (m = this.stopObserver) == null || m.call(this);
    const { viewport: t = {} } = this.node.getProps(), { root: i, margin: a, amount: r = "some", once: u } = t, c = {
      root: i ? i.current : void 0,
      rootMargin: a,
      threshold: typeof r == "number" ? r : v_[r]
    }, f = (p) => {
      const { isIntersecting: g } = p;
      if (this.isInView === g || (this.isInView = g, u && !g && this.hasEnteredView))
        return;
      g && (this.hasEnteredView = !0), this.node.animationState && this.node.animationState.setActive("whileInView", g);
      const { onViewportEnter: y, onViewportLeave: b } = this.node.getProps(), S = g ? y : b;
      S && S(p);
    };
    this.stopObserver = y_(this.node.current, c, f);
  }
  mount() {
    this.startObserver();
  }
  update() {
    if (typeof IntersectionObserver > "u")
      return;
    const { props: t, prevProps: i } = this.node;
    ["amount", "margin", "root"].some(x_(t, i)) && this.startObserver();
  }
  unmount() {
    var t;
    (t = this.stopObserver) == null || t.call(this), this.hasEnteredView = !1, this.isInView = !1;
  }
}
function x_({ viewport: n = {} }, { viewport: t = {} } = {}) {
  return (i) => n[i] !== t[i];
}
const S_ = {
  inView: {
    Feature: b_
  },
  tap: {
    Feature: d_
  },
  focus: {
    Feature: h_
  },
  hover: {
    Feature: f_
  }
}, w_ = {
  layout: {
    ProjectionNode: QC,
    MeasureLayout: rE
  }
}, M_ = {
  ...F5,
  ...S_,
  ...c_,
  ...w_
}, T_ = /* @__PURE__ */ H5(M_, q5);
function hc(n) {
  const t = Kc(() => Lo(n)), { isStatic: i } = G.useContext(tf);
  if (i) {
    const [, a] = G.useState(n);
    G.useEffect(() => t.on("change", a), []);
  }
  return t;
}
function zv(n, t) {
  const i = hc(t()), a = () => i.set(t());
  return a(), Ad(() => {
    const r = () => jt.preRender(a, !1, !0), u = n.map((c) => c.on("change", r));
    return () => {
      u.forEach((c) => c()), Wi(a);
    };
  }), i;
}
function C_(n, ...t) {
  const i = n.length;
  function a() {
    let r = "";
    for (let u = 0; u < i; u++) {
      r += n[u];
      const c = t[u];
      c && (r += de(c) ? c.get() : c);
    }
    return r;
  }
  return zv(t.filter(de), a);
}
function E_(n) {
  tc.current = [], n();
  const t = zv(tc.current, n);
  return tc.current = void 0, t;
}
function A_(n, t, i, a) {
  if (typeof n == "function")
    return E_(n);
  const u = F4(t, i, a), c = Array.isArray(n) ? Kw(n, u) : Kw([n], ([m]) => u(m)), f = Array.isArray(n) ? void 0 : n.accelerate;
  return f && !f.isTransformed && typeof t != "function" && Array.isArray(i) && (a == null ? void 0 : a.clamp) !== !1 && (c.accelerate = {
    ...f,
    times: t,
    keyframes: i,
    isTransformed: !0
  }), c;
}
function Kw(n, t) {
  const i = Kc(() => []);
  return zv(n, () => {
    i.length = 0;
    const a = n.length;
    for (let r = 0; r < a; r++)
      i[r] = n[r].get();
    return t(i);
  });
}
function D_(n, t = {}) {
  const { isStatic: i } = G.useContext(tf), a = () => de(n) ? n.get() : n;
  if (i)
    return A_(a);
  const r = hc(a());
  return G.useInsertionEffect(() => Z4(r, n, t), [r, JSON.stringify(t)]), r;
}
function R_(n, t = {}) {
  return D_(n, { type: "spring", ...t });
}
const O_ = {
  some: 0,
  all: 1
};
function z_(n, t, { root: i, margin: a, amount: r = "some" } = {}) {
  const u = Sv(n), c = /* @__PURE__ */ new WeakMap(), f = (p) => {
    p.forEach((g) => {
      const y = c.get(g.target);
      if (g.isIntersecting !== !!y)
        if (g.isIntersecting) {
          const b = t(g.target, g);
          typeof b == "function" ? c.set(g.target, b) : m.unobserve(g.target);
        } else typeof y == "function" && (y(g), c.delete(g.target));
    });
  }, m = new IntersectionObserver(f, {
    root: i,
    rootMargin: a,
    threshold: typeof r == "number" ? r : O_[r]
  });
  return u.forEach((p) => m.observe(p)), () => m.disconnect();
}
function k_(n, { root: t, margin: i, amount: a, once: r = !1, initial: u = !1 } = {}) {
  const [c, f] = G.useState(u);
  return G.useEffect(() => {
    if (!n.current || r && c)
      return;
    const m = () => (f(!0), r ? void 0 : () => f(!1)), p = {
      root: t && t.current || void 0,
      margin: i,
      amount: a
    };
    return z_(n.current, m, p);
  }, [t, n, i, r, a]), c;
}
const ld = T_;
function lE(n) {
  var t, i, a = "";
  if (typeof n == "string" || typeof n == "number") a += n;
  else if (typeof n == "object") if (Array.isArray(n)) {
    var r = n.length;
    for (t = 0; t < r; t++) n[t] && (i = lE(n[t])) && (a && (a += " "), a += i);
  } else for (i in n) n[i] && (a && (a += " "), a += i);
  return a;
}
function V_() {
  for (var n, t, i = 0, a = "", r = arguments.length; i < r; i++) (n = arguments[i]) && (t = lE(n)) && (a && (a += " "), a += t);
  return a;
}
const kv = "-", P_ = (n) => {
  const t = __(n), {
    conflictingClassGroups: i,
    conflictingClassGroupModifiers: a
  } = n;
  return {
    getClassGroupId: (c) => {
      const f = c.split(kv);
      return f[0] === "" && f.length !== 1 && f.shift(), uE(f, t) || L_(c);
    },
    getConflictingClassGroupIds: (c, f) => {
      const m = i[c] || [];
      return f && a[c] ? [...m, ...a[c]] : m;
    }
  };
}, uE = (n, t) => {
  var c;
  if (n.length === 0)
    return t.classGroupId;
  const i = n[0], a = t.nextPart.get(i), r = a ? uE(n.slice(1), a) : void 0;
  if (r)
    return r;
  if (t.validators.length === 0)
    return;
  const u = n.join(kv);
  return (c = t.validators.find(({
    validator: f
  }) => f(u))) == null ? void 0 : c.classGroupId;
}, Iw = /^\[(.+)\]$/, L_ = (n) => {
  if (Iw.test(n)) {
    const t = Iw.exec(n)[1], i = t == null ? void 0 : t.substring(0, t.indexOf(":"));
    if (i)
      return "arbitrary.." + i;
  }
}, __ = (n) => {
  const {
    theme: t,
    prefix: i
  } = n, a = {
    nextPart: /* @__PURE__ */ new Map(),
    validators: []
  };
  return N_(Object.entries(n.classGroups), i).forEach(([u, c]) => {
    Ey(c, a, u, t);
  }), a;
}, Ey = (n, t, i, a) => {
  n.forEach((r) => {
    if (typeof r == "string") {
      const u = r === "" ? t : $w(t, r);
      u.classGroupId = i;
      return;
    }
    if (typeof r == "function") {
      if (B_(r)) {
        Ey(r(a), t, i, a);
        return;
      }
      t.validators.push({
        validator: r,
        classGroupId: i
      });
      return;
    }
    Object.entries(r).forEach(([u, c]) => {
      Ey(c, $w(t, u), i, a);
    });
  });
}, $w = (n, t) => {
  let i = n;
  return t.split(kv).forEach((a) => {
    i.nextPart.has(a) || i.nextPart.set(a, {
      nextPart: /* @__PURE__ */ new Map(),
      validators: []
    }), i = i.nextPart.get(a);
  }), i;
}, B_ = (n) => n.isThemeGetter, N_ = (n, t) => t ? n.map(([i, a]) => {
  const r = a.map((u) => typeof u == "string" ? t + u : typeof u == "object" ? Object.fromEntries(Object.entries(u).map(([c, f]) => [t + c, f])) : u);
  return [i, r];
}) : n, U_ = (n) => {
  if (n < 1)
    return {
      get: () => {
      },
      set: () => {
      }
    };
  let t = 0, i = /* @__PURE__ */ new Map(), a = /* @__PURE__ */ new Map();
  const r = (u, c) => {
    i.set(u, c), t++, t > n && (t = 0, a = i, i = /* @__PURE__ */ new Map());
  };
  return {
    get(u) {
      let c = i.get(u);
      if (c !== void 0)
        return c;
      if ((c = a.get(u)) !== void 0)
        return r(u, c), c;
    },
    set(u, c) {
      i.has(u) ? i.set(u, c) : r(u, c);
    }
  };
}, cE = "!", j_ = (n) => {
  const {
    separator: t,
    experimentalParseClassName: i
  } = n, a = t.length === 1, r = t[0], u = t.length, c = (f) => {
    const m = [];
    let p = 0, g = 0, y;
    for (let R = 0; R < f.length; R++) {
      let z = f[R];
      if (p === 0) {
        if (z === r && (a || f.slice(R, R + u) === t)) {
          m.push(f.slice(g, R)), g = R + u;
          continue;
        }
        if (z === "/") {
          y = R;
          continue;
        }
      }
      z === "[" ? p++ : z === "]" && p--;
    }
    const b = m.length === 0 ? f : f.substring(g), S = b.startsWith(cE), T = S ? b.substring(1) : b, C = y && y > g ? y - g : void 0;
    return {
      modifiers: m,
      hasImportantModifier: S,
      baseClassName: T,
      maybePostfixModifierPosition: C
    };
  };
  return i ? (f) => i({
    className: f,
    parseClassName: c
  }) : c;
}, H_ = (n) => {
  if (n.length <= 1)
    return n;
  const t = [];
  let i = [];
  return n.forEach((a) => {
    a[0] === "[" ? (t.push(...i.sort(), a), i = []) : i.push(a);
  }), t.push(...i.sort()), t;
}, q_ = (n) => ({
  cache: U_(n.cacheSize),
  parseClassName: j_(n),
  ...P_(n)
}), G_ = /\s+/, Y_ = (n, t) => {
  const {
    parseClassName: i,
    getClassGroupId: a,
    getConflictingClassGroupIds: r
  } = t, u = [], c = n.trim().split(G_);
  let f = "";
  for (let m = c.length - 1; m >= 0; m -= 1) {
    const p = c[m], {
      modifiers: g,
      hasImportantModifier: y,
      baseClassName: b,
      maybePostfixModifierPosition: S
    } = i(p);
    let T = !!S, C = a(T ? b.substring(0, S) : b);
    if (!C) {
      if (!T) {
        f = p + (f.length > 0 ? " " + f : f);
        continue;
      }
      if (C = a(b), !C) {
        f = p + (f.length > 0 ? " " + f : f);
        continue;
      }
      T = !1;
    }
    const R = H_(g).join(":"), z = y ? R + cE : R, B = z + C;
    if (u.includes(B))
      continue;
    u.push(B);
    const H = r(C, T);
    for (let X = 0; X < H.length; ++X) {
      const Q = H[X];
      u.push(z + Q);
    }
    f = p + (f.length > 0 ? " " + f : f);
  }
  return f;
};
function X_() {
  let n = 0, t, i, a = "";
  for (; n < arguments.length; )
    (t = arguments[n++]) && (i = fE(t)) && (a && (a += " "), a += i);
  return a;
}
const fE = (n) => {
  if (typeof n == "string")
    return n;
  let t, i = "";
  for (let a = 0; a < n.length; a++)
    n[a] && (t = fE(n[a])) && (i && (i += " "), i += t);
  return i;
};
function F_(n, ...t) {
  let i, a, r, u = c;
  function c(m) {
    const p = t.reduce((g, y) => y(g), n());
    return i = q_(p), a = i.cache.get, r = i.cache.set, u = f, f(m);
  }
  function f(m) {
    const p = a(m);
    if (p)
      return p;
    const g = Y_(m, i);
    return r(m, g), g;
  }
  return function() {
    return u(X_.apply(null, arguments));
  };
}
const Jt = (n) => {
  const t = (i) => i[n] || [];
  return t.isThemeGetter = !0, t;
}, hE = /^\[(?:([a-z-]+):)?(.+)\]$/i, Z_ = /^\d+\/\d+$/, Q_ = /* @__PURE__ */ new Set(["px", "full", "screen"]), K_ = /^(\d+(\.\d+)?)?(xs|sm|md|lg|xl)$/, I_ = /\d+(%|px|r?em|[sdl]?v([hwib]|min|max)|pt|pc|in|cm|mm|cap|ch|ex|r?lh|cq(w|h|i|b|min|max))|\b(calc|min|max|clamp)\(.+\)|^0$/, $_ = /^(rgba?|hsla?|hwb|(ok)?(lab|lch)|color-mix)\(.+\)$/, W_ = /^(inset_)?-?((\d+)?\.?(\d+)[a-z]+|0)_-?((\d+)?\.?(\d+)[a-z]+|0)/, J_ = /^(url|image|image-set|cross-fade|element|(repeating-)?(linear|radial|conic)-gradient)\(.+\)$/, Ki = (n) => jr(n) || Q_.has(n) || Z_.test(n), Cs = (n) => Bl(n, "length", rB), jr = (n) => !!n && !Number.isNaN(Number(n)), Lg = (n) => Bl(n, "number", jr), ju = (n) => !!n && Number.isInteger(Number(n)), tB = (n) => n.endsWith("%") && jr(n.slice(0, -1)), St = (n) => hE.test(n), Es = (n) => K_.test(n), eB = /* @__PURE__ */ new Set(["length", "size", "percentage"]), nB = (n) => Bl(n, eB, dE), iB = (n) => Bl(n, "position", dE), sB = /* @__PURE__ */ new Set(["image", "url"]), aB = (n) => Bl(n, sB, uB), oB = (n) => Bl(n, "", lB), Hu = () => !0, Bl = (n, t, i) => {
  const a = hE.exec(n);
  return a ? a[1] ? typeof t == "string" ? a[1] === t : t.has(a[1]) : i(a[2]) : !1;
}, rB = (n) => (
  // `colorFunctionRegex` check is necessary because color functions can have percentages in them which which would be incorrectly classified as lengths.
  // For example, `hsl(0 0% 0%)` would be classified as a length without this check.
  // I could also use lookbehind assertion in `lengthUnitRegex` but that isn't supported widely enough.
  I_.test(n) && !$_.test(n)
), dE = () => !1, lB = (n) => W_.test(n), uB = (n) => J_.test(n), cB = () => {
  const n = Jt("colors"), t = Jt("spacing"), i = Jt("blur"), a = Jt("brightness"), r = Jt("borderColor"), u = Jt("borderRadius"), c = Jt("borderSpacing"), f = Jt("borderWidth"), m = Jt("contrast"), p = Jt("grayscale"), g = Jt("hueRotate"), y = Jt("invert"), b = Jt("gap"), S = Jt("gradientColorStops"), T = Jt("gradientColorStopPositions"), C = Jt("inset"), R = Jt("margin"), z = Jt("opacity"), B = Jt("padding"), H = Jt("saturate"), X = Jt("scale"), Q = Jt("sepia"), ut = Jt("skew"), st = Jt("space"), $ = Jt("translate"), lt = () => ["auto", "contain", "none"], nt = () => ["auto", "hidden", "clip", "visible", "scroll"], vt = () => ["auto", St, t], it = () => [St, t], ie = () => ["", Ki, Cs], Kt = () => ["auto", jr, St], zt = () => ["bottom", "center", "left", "left-bottom", "left-top", "right", "right-bottom", "right-top", "top"], j = () => ["solid", "dashed", "dotted", "double", "none"], W = () => ["normal", "multiply", "screen", "overlay", "darken", "lighten", "color-dodge", "color-burn", "hard-light", "soft-light", "difference", "exclusion", "hue", "saturation", "color", "luminosity"], J = () => ["start", "end", "center", "between", "around", "evenly", "stretch"], ft = () => ["", "0", St], D = () => ["auto", "avoid", "all", "avoid-page", "page", "left", "right", "column"], Y = () => [jr, St];
  return {
    cacheSize: 500,
    separator: ":",
    theme: {
      colors: [Hu],
      spacing: [Ki, Cs],
      blur: ["none", "", Es, St],
      brightness: Y(),
      borderColor: [n],
      borderRadius: ["none", "", "full", Es, St],
      borderSpacing: it(),
      borderWidth: ie(),
      contrast: Y(),
      grayscale: ft(),
      hueRotate: Y(),
      invert: ft(),
      gap: it(),
      gradientColorStops: [n],
      gradientColorStopPositions: [tB, Cs],
      inset: vt(),
      margin: vt(),
      opacity: Y(),
      padding: it(),
      saturate: Y(),
      scale: Y(),
      sepia: ft(),
      skew: Y(),
      space: it(),
      translate: it()
    },
    classGroups: {
      // Layout
      /**
       * Aspect Ratio
       * @see https://tailwindcss.com/docs/aspect-ratio
       */
      aspect: [{
        aspect: ["auto", "square", "video", St]
      }],
      /**
       * Container
       * @see https://tailwindcss.com/docs/container
       */
      container: ["container"],
      /**
       * Columns
       * @see https://tailwindcss.com/docs/columns
       */
      columns: [{
        columns: [Es]
      }],
      /**
       * Break After
       * @see https://tailwindcss.com/docs/break-after
       */
      "break-after": [{
        "break-after": D()
      }],
      /**
       * Break Before
       * @see https://tailwindcss.com/docs/break-before
       */
      "break-before": [{
        "break-before": D()
      }],
      /**
       * Break Inside
       * @see https://tailwindcss.com/docs/break-inside
       */
      "break-inside": [{
        "break-inside": ["auto", "avoid", "avoid-page", "avoid-column"]
      }],
      /**
       * Box Decoration Break
       * @see https://tailwindcss.com/docs/box-decoration-break
       */
      "box-decoration": [{
        "box-decoration": ["slice", "clone"]
      }],
      /**
       * Box Sizing
       * @see https://tailwindcss.com/docs/box-sizing
       */
      box: [{
        box: ["border", "content"]
      }],
      /**
       * Display
       * @see https://tailwindcss.com/docs/display
       */
      display: ["block", "inline-block", "inline", "flex", "inline-flex", "table", "inline-table", "table-caption", "table-cell", "table-column", "table-column-group", "table-footer-group", "table-header-group", "table-row-group", "table-row", "flow-root", "grid", "inline-grid", "contents", "list-item", "hidden"],
      /**
       * Floats
       * @see https://tailwindcss.com/docs/float
       */
      float: [{
        float: ["right", "left", "none", "start", "end"]
      }],
      /**
       * Clear
       * @see https://tailwindcss.com/docs/clear
       */
      clear: [{
        clear: ["left", "right", "both", "none", "start", "end"]
      }],
      /**
       * Isolation
       * @see https://tailwindcss.com/docs/isolation
       */
      isolation: ["isolate", "isolation-auto"],
      /**
       * Object Fit
       * @see https://tailwindcss.com/docs/object-fit
       */
      "object-fit": [{
        object: ["contain", "cover", "fill", "none", "scale-down"]
      }],
      /**
       * Object Position
       * @see https://tailwindcss.com/docs/object-position
       */
      "object-position": [{
        object: [...zt(), St]
      }],
      /**
       * Overflow
       * @see https://tailwindcss.com/docs/overflow
       */
      overflow: [{
        overflow: nt()
      }],
      /**
       * Overflow X
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-x": [{
        "overflow-x": nt()
      }],
      /**
       * Overflow Y
       * @see https://tailwindcss.com/docs/overflow
       */
      "overflow-y": [{
        "overflow-y": nt()
      }],
      /**
       * Overscroll Behavior
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      overscroll: [{
        overscroll: lt()
      }],
      /**
       * Overscroll Behavior X
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-x": [{
        "overscroll-x": lt()
      }],
      /**
       * Overscroll Behavior Y
       * @see https://tailwindcss.com/docs/overscroll-behavior
       */
      "overscroll-y": [{
        "overscroll-y": lt()
      }],
      /**
       * Position
       * @see https://tailwindcss.com/docs/position
       */
      position: ["static", "fixed", "absolute", "relative", "sticky"],
      /**
       * Top / Right / Bottom / Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      inset: [{
        inset: [C]
      }],
      /**
       * Right / Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-x": [{
        "inset-x": [C]
      }],
      /**
       * Top / Bottom
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      "inset-y": [{
        "inset-y": [C]
      }],
      /**
       * Start
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      start: [{
        start: [C]
      }],
      /**
       * End
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      end: [{
        end: [C]
      }],
      /**
       * Top
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      top: [{
        top: [C]
      }],
      /**
       * Right
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      right: [{
        right: [C]
      }],
      /**
       * Bottom
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      bottom: [{
        bottom: [C]
      }],
      /**
       * Left
       * @see https://tailwindcss.com/docs/top-right-bottom-left
       */
      left: [{
        left: [C]
      }],
      /**
       * Visibility
       * @see https://tailwindcss.com/docs/visibility
       */
      visibility: ["visible", "invisible", "collapse"],
      /**
       * Z-Index
       * @see https://tailwindcss.com/docs/z-index
       */
      z: [{
        z: ["auto", ju, St]
      }],
      // Flexbox and Grid
      /**
       * Flex Basis
       * @see https://tailwindcss.com/docs/flex-basis
       */
      basis: [{
        basis: vt()
      }],
      /**
       * Flex Direction
       * @see https://tailwindcss.com/docs/flex-direction
       */
      "flex-direction": [{
        flex: ["row", "row-reverse", "col", "col-reverse"]
      }],
      /**
       * Flex Wrap
       * @see https://tailwindcss.com/docs/flex-wrap
       */
      "flex-wrap": [{
        flex: ["wrap", "wrap-reverse", "nowrap"]
      }],
      /**
       * Flex
       * @see https://tailwindcss.com/docs/flex
       */
      flex: [{
        flex: ["1", "auto", "initial", "none", St]
      }],
      /**
       * Flex Grow
       * @see https://tailwindcss.com/docs/flex-grow
       */
      grow: [{
        grow: ft()
      }],
      /**
       * Flex Shrink
       * @see https://tailwindcss.com/docs/flex-shrink
       */
      shrink: [{
        shrink: ft()
      }],
      /**
       * Order
       * @see https://tailwindcss.com/docs/order
       */
      order: [{
        order: ["first", "last", "none", ju, St]
      }],
      /**
       * Grid Template Columns
       * @see https://tailwindcss.com/docs/grid-template-columns
       */
      "grid-cols": [{
        "grid-cols": [Hu]
      }],
      /**
       * Grid Column Start / End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start-end": [{
        col: ["auto", {
          span: ["full", ju, St]
        }, St]
      }],
      /**
       * Grid Column Start
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-start": [{
        "col-start": Kt()
      }],
      /**
       * Grid Column End
       * @see https://tailwindcss.com/docs/grid-column
       */
      "col-end": [{
        "col-end": Kt()
      }],
      /**
       * Grid Template Rows
       * @see https://tailwindcss.com/docs/grid-template-rows
       */
      "grid-rows": [{
        "grid-rows": [Hu]
      }],
      /**
       * Grid Row Start / End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start-end": [{
        row: ["auto", {
          span: [ju, St]
        }, St]
      }],
      /**
       * Grid Row Start
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-start": [{
        "row-start": Kt()
      }],
      /**
       * Grid Row End
       * @see https://tailwindcss.com/docs/grid-row
       */
      "row-end": [{
        "row-end": Kt()
      }],
      /**
       * Grid Auto Flow
       * @see https://tailwindcss.com/docs/grid-auto-flow
       */
      "grid-flow": [{
        "grid-flow": ["row", "col", "dense", "row-dense", "col-dense"]
      }],
      /**
       * Grid Auto Columns
       * @see https://tailwindcss.com/docs/grid-auto-columns
       */
      "auto-cols": [{
        "auto-cols": ["auto", "min", "max", "fr", St]
      }],
      /**
       * Grid Auto Rows
       * @see https://tailwindcss.com/docs/grid-auto-rows
       */
      "auto-rows": [{
        "auto-rows": ["auto", "min", "max", "fr", St]
      }],
      /**
       * Gap
       * @see https://tailwindcss.com/docs/gap
       */
      gap: [{
        gap: [b]
      }],
      /**
       * Gap X
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-x": [{
        "gap-x": [b]
      }],
      /**
       * Gap Y
       * @see https://tailwindcss.com/docs/gap
       */
      "gap-y": [{
        "gap-y": [b]
      }],
      /**
       * Justify Content
       * @see https://tailwindcss.com/docs/justify-content
       */
      "justify-content": [{
        justify: ["normal", ...J()]
      }],
      /**
       * Justify Items
       * @see https://tailwindcss.com/docs/justify-items
       */
      "justify-items": [{
        "justify-items": ["start", "end", "center", "stretch"]
      }],
      /**
       * Justify Self
       * @see https://tailwindcss.com/docs/justify-self
       */
      "justify-self": [{
        "justify-self": ["auto", "start", "end", "center", "stretch"]
      }],
      /**
       * Align Content
       * @see https://tailwindcss.com/docs/align-content
       */
      "align-content": [{
        content: ["normal", ...J(), "baseline"]
      }],
      /**
       * Align Items
       * @see https://tailwindcss.com/docs/align-items
       */
      "align-items": [{
        items: ["start", "end", "center", "baseline", "stretch"]
      }],
      /**
       * Align Self
       * @see https://tailwindcss.com/docs/align-self
       */
      "align-self": [{
        self: ["auto", "start", "end", "center", "stretch", "baseline"]
      }],
      /**
       * Place Content
       * @see https://tailwindcss.com/docs/place-content
       */
      "place-content": [{
        "place-content": [...J(), "baseline"]
      }],
      /**
       * Place Items
       * @see https://tailwindcss.com/docs/place-items
       */
      "place-items": [{
        "place-items": ["start", "end", "center", "baseline", "stretch"]
      }],
      /**
       * Place Self
       * @see https://tailwindcss.com/docs/place-self
       */
      "place-self": [{
        "place-self": ["auto", "start", "end", "center", "stretch"]
      }],
      // Spacing
      /**
       * Padding
       * @see https://tailwindcss.com/docs/padding
       */
      p: [{
        p: [B]
      }],
      /**
       * Padding X
       * @see https://tailwindcss.com/docs/padding
       */
      px: [{
        px: [B]
      }],
      /**
       * Padding Y
       * @see https://tailwindcss.com/docs/padding
       */
      py: [{
        py: [B]
      }],
      /**
       * Padding Start
       * @see https://tailwindcss.com/docs/padding
       */
      ps: [{
        ps: [B]
      }],
      /**
       * Padding End
       * @see https://tailwindcss.com/docs/padding
       */
      pe: [{
        pe: [B]
      }],
      /**
       * Padding Top
       * @see https://tailwindcss.com/docs/padding
       */
      pt: [{
        pt: [B]
      }],
      /**
       * Padding Right
       * @see https://tailwindcss.com/docs/padding
       */
      pr: [{
        pr: [B]
      }],
      /**
       * Padding Bottom
       * @see https://tailwindcss.com/docs/padding
       */
      pb: [{
        pb: [B]
      }],
      /**
       * Padding Left
       * @see https://tailwindcss.com/docs/padding
       */
      pl: [{
        pl: [B]
      }],
      /**
       * Margin
       * @see https://tailwindcss.com/docs/margin
       */
      m: [{
        m: [R]
      }],
      /**
       * Margin X
       * @see https://tailwindcss.com/docs/margin
       */
      mx: [{
        mx: [R]
      }],
      /**
       * Margin Y
       * @see https://tailwindcss.com/docs/margin
       */
      my: [{
        my: [R]
      }],
      /**
       * Margin Start
       * @see https://tailwindcss.com/docs/margin
       */
      ms: [{
        ms: [R]
      }],
      /**
       * Margin End
       * @see https://tailwindcss.com/docs/margin
       */
      me: [{
        me: [R]
      }],
      /**
       * Margin Top
       * @see https://tailwindcss.com/docs/margin
       */
      mt: [{
        mt: [R]
      }],
      /**
       * Margin Right
       * @see https://tailwindcss.com/docs/margin
       */
      mr: [{
        mr: [R]
      }],
      /**
       * Margin Bottom
       * @see https://tailwindcss.com/docs/margin
       */
      mb: [{
        mb: [R]
      }],
      /**
       * Margin Left
       * @see https://tailwindcss.com/docs/margin
       */
      ml: [{
        ml: [R]
      }],
      /**
       * Space Between X
       * @see https://tailwindcss.com/docs/space
       */
      "space-x": [{
        "space-x": [st]
      }],
      /**
       * Space Between X Reverse
       * @see https://tailwindcss.com/docs/space
       */
      "space-x-reverse": ["space-x-reverse"],
      /**
       * Space Between Y
       * @see https://tailwindcss.com/docs/space
       */
      "space-y": [{
        "space-y": [st]
      }],
      /**
       * Space Between Y Reverse
       * @see https://tailwindcss.com/docs/space
       */
      "space-y-reverse": ["space-y-reverse"],
      // Sizing
      /**
       * Width
       * @see https://tailwindcss.com/docs/width
       */
      w: [{
        w: ["auto", "min", "max", "fit", "svw", "lvw", "dvw", St, t]
      }],
      /**
       * Min-Width
       * @see https://tailwindcss.com/docs/min-width
       */
      "min-w": [{
        "min-w": [St, t, "min", "max", "fit"]
      }],
      /**
       * Max-Width
       * @see https://tailwindcss.com/docs/max-width
       */
      "max-w": [{
        "max-w": [St, t, "none", "full", "min", "max", "fit", "prose", {
          screen: [Es]
        }, Es]
      }],
      /**
       * Height
       * @see https://tailwindcss.com/docs/height
       */
      h: [{
        h: [St, t, "auto", "min", "max", "fit", "svh", "lvh", "dvh"]
      }],
      /**
       * Min-Height
       * @see https://tailwindcss.com/docs/min-height
       */
      "min-h": [{
        "min-h": [St, t, "min", "max", "fit", "svh", "lvh", "dvh"]
      }],
      /**
       * Max-Height
       * @see https://tailwindcss.com/docs/max-height
       */
      "max-h": [{
        "max-h": [St, t, "min", "max", "fit", "svh", "lvh", "dvh"]
      }],
      /**
       * Size
       * @see https://tailwindcss.com/docs/size
       */
      size: [{
        size: [St, t, "auto", "min", "max", "fit"]
      }],
      // Typography
      /**
       * Font Size
       * @see https://tailwindcss.com/docs/font-size
       */
      "font-size": [{
        text: ["base", Es, Cs]
      }],
      /**
       * Font Smoothing
       * @see https://tailwindcss.com/docs/font-smoothing
       */
      "font-smoothing": ["antialiased", "subpixel-antialiased"],
      /**
       * Font Style
       * @see https://tailwindcss.com/docs/font-style
       */
      "font-style": ["italic", "not-italic"],
      /**
       * Font Weight
       * @see https://tailwindcss.com/docs/font-weight
       */
      "font-weight": [{
        font: ["thin", "extralight", "light", "normal", "medium", "semibold", "bold", "extrabold", "black", Lg]
      }],
      /**
       * Font Family
       * @see https://tailwindcss.com/docs/font-family
       */
      "font-family": [{
        font: [Hu]
      }],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-normal": ["normal-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-ordinal": ["ordinal"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-slashed-zero": ["slashed-zero"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-figure": ["lining-nums", "oldstyle-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-spacing": ["proportional-nums", "tabular-nums"],
      /**
       * Font Variant Numeric
       * @see https://tailwindcss.com/docs/font-variant-numeric
       */
      "fvn-fraction": ["diagonal-fractions", "stacked-fractions"],
      /**
       * Letter Spacing
       * @see https://tailwindcss.com/docs/letter-spacing
       */
      tracking: [{
        tracking: ["tighter", "tight", "normal", "wide", "wider", "widest", St]
      }],
      /**
       * Line Clamp
       * @see https://tailwindcss.com/docs/line-clamp
       */
      "line-clamp": [{
        "line-clamp": ["none", jr, Lg]
      }],
      /**
       * Line Height
       * @see https://tailwindcss.com/docs/line-height
       */
      leading: [{
        leading: ["none", "tight", "snug", "normal", "relaxed", "loose", Ki, St]
      }],
      /**
       * List Style Image
       * @see https://tailwindcss.com/docs/list-style-image
       */
      "list-image": [{
        "list-image": ["none", St]
      }],
      /**
       * List Style Type
       * @see https://tailwindcss.com/docs/list-style-type
       */
      "list-style-type": [{
        list: ["none", "disc", "decimal", St]
      }],
      /**
       * List Style Position
       * @see https://tailwindcss.com/docs/list-style-position
       */
      "list-style-position": [{
        list: ["inside", "outside"]
      }],
      /**
       * Placeholder Color
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/placeholder-color
       */
      "placeholder-color": [{
        placeholder: [n]
      }],
      /**
       * Placeholder Opacity
       * @see https://tailwindcss.com/docs/placeholder-opacity
       */
      "placeholder-opacity": [{
        "placeholder-opacity": [z]
      }],
      /**
       * Text Alignment
       * @see https://tailwindcss.com/docs/text-align
       */
      "text-alignment": [{
        text: ["left", "center", "right", "justify", "start", "end"]
      }],
      /**
       * Text Color
       * @see https://tailwindcss.com/docs/text-color
       */
      "text-color": [{
        text: [n]
      }],
      /**
       * Text Opacity
       * @see https://tailwindcss.com/docs/text-opacity
       */
      "text-opacity": [{
        "text-opacity": [z]
      }],
      /**
       * Text Decoration
       * @see https://tailwindcss.com/docs/text-decoration
       */
      "text-decoration": ["underline", "overline", "line-through", "no-underline"],
      /**
       * Text Decoration Style
       * @see https://tailwindcss.com/docs/text-decoration-style
       */
      "text-decoration-style": [{
        decoration: [...j(), "wavy"]
      }],
      /**
       * Text Decoration Thickness
       * @see https://tailwindcss.com/docs/text-decoration-thickness
       */
      "text-decoration-thickness": [{
        decoration: ["auto", "from-font", Ki, Cs]
      }],
      /**
       * Text Underline Offset
       * @see https://tailwindcss.com/docs/text-underline-offset
       */
      "underline-offset": [{
        "underline-offset": ["auto", Ki, St]
      }],
      /**
       * Text Decoration Color
       * @see https://tailwindcss.com/docs/text-decoration-color
       */
      "text-decoration-color": [{
        decoration: [n]
      }],
      /**
       * Text Transform
       * @see https://tailwindcss.com/docs/text-transform
       */
      "text-transform": ["uppercase", "lowercase", "capitalize", "normal-case"],
      /**
       * Text Overflow
       * @see https://tailwindcss.com/docs/text-overflow
       */
      "text-overflow": ["truncate", "text-ellipsis", "text-clip"],
      /**
       * Text Wrap
       * @see https://tailwindcss.com/docs/text-wrap
       */
      "text-wrap": [{
        text: ["wrap", "nowrap", "balance", "pretty"]
      }],
      /**
       * Text Indent
       * @see https://tailwindcss.com/docs/text-indent
       */
      indent: [{
        indent: it()
      }],
      /**
       * Vertical Alignment
       * @see https://tailwindcss.com/docs/vertical-align
       */
      "vertical-align": [{
        align: ["baseline", "top", "middle", "bottom", "text-top", "text-bottom", "sub", "super", St]
      }],
      /**
       * Whitespace
       * @see https://tailwindcss.com/docs/whitespace
       */
      whitespace: [{
        whitespace: ["normal", "nowrap", "pre", "pre-line", "pre-wrap", "break-spaces"]
      }],
      /**
       * Word Break
       * @see https://tailwindcss.com/docs/word-break
       */
      break: [{
        break: ["normal", "words", "all", "keep"]
      }],
      /**
       * Hyphens
       * @see https://tailwindcss.com/docs/hyphens
       */
      hyphens: [{
        hyphens: ["none", "manual", "auto"]
      }],
      /**
       * Content
       * @see https://tailwindcss.com/docs/content
       */
      content: [{
        content: ["none", St]
      }],
      // Backgrounds
      /**
       * Background Attachment
       * @see https://tailwindcss.com/docs/background-attachment
       */
      "bg-attachment": [{
        bg: ["fixed", "local", "scroll"]
      }],
      /**
       * Background Clip
       * @see https://tailwindcss.com/docs/background-clip
       */
      "bg-clip": [{
        "bg-clip": ["border", "padding", "content", "text"]
      }],
      /**
       * Background Opacity
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/background-opacity
       */
      "bg-opacity": [{
        "bg-opacity": [z]
      }],
      /**
       * Background Origin
       * @see https://tailwindcss.com/docs/background-origin
       */
      "bg-origin": [{
        "bg-origin": ["border", "padding", "content"]
      }],
      /**
       * Background Position
       * @see https://tailwindcss.com/docs/background-position
       */
      "bg-position": [{
        bg: [...zt(), iB]
      }],
      /**
       * Background Repeat
       * @see https://tailwindcss.com/docs/background-repeat
       */
      "bg-repeat": [{
        bg: ["no-repeat", {
          repeat: ["", "x", "y", "round", "space"]
        }]
      }],
      /**
       * Background Size
       * @see https://tailwindcss.com/docs/background-size
       */
      "bg-size": [{
        bg: ["auto", "cover", "contain", nB]
      }],
      /**
       * Background Image
       * @see https://tailwindcss.com/docs/background-image
       */
      "bg-image": [{
        bg: ["none", {
          "gradient-to": ["t", "tr", "r", "br", "b", "bl", "l", "tl"]
        }, aB]
      }],
      /**
       * Background Color
       * @see https://tailwindcss.com/docs/background-color
       */
      "bg-color": [{
        bg: [n]
      }],
      /**
       * Gradient Color Stops From Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from-pos": [{
        from: [T]
      }],
      /**
       * Gradient Color Stops Via Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via-pos": [{
        via: [T]
      }],
      /**
       * Gradient Color Stops To Position
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to-pos": [{
        to: [T]
      }],
      /**
       * Gradient Color Stops From
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-from": [{
        from: [S]
      }],
      /**
       * Gradient Color Stops Via
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-via": [{
        via: [S]
      }],
      /**
       * Gradient Color Stops To
       * @see https://tailwindcss.com/docs/gradient-color-stops
       */
      "gradient-to": [{
        to: [S]
      }],
      // Borders
      /**
       * Border Radius
       * @see https://tailwindcss.com/docs/border-radius
       */
      rounded: [{
        rounded: [u]
      }],
      /**
       * Border Radius Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-s": [{
        "rounded-s": [u]
      }],
      /**
       * Border Radius End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-e": [{
        "rounded-e": [u]
      }],
      /**
       * Border Radius Top
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-t": [{
        "rounded-t": [u]
      }],
      /**
       * Border Radius Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-r": [{
        "rounded-r": [u]
      }],
      /**
       * Border Radius Bottom
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-b": [{
        "rounded-b": [u]
      }],
      /**
       * Border Radius Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-l": [{
        "rounded-l": [u]
      }],
      /**
       * Border Radius Start Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ss": [{
        "rounded-ss": [u]
      }],
      /**
       * Border Radius Start End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-se": [{
        "rounded-se": [u]
      }],
      /**
       * Border Radius End End
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-ee": [{
        "rounded-ee": [u]
      }],
      /**
       * Border Radius End Start
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-es": [{
        "rounded-es": [u]
      }],
      /**
       * Border Radius Top Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tl": [{
        "rounded-tl": [u]
      }],
      /**
       * Border Radius Top Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-tr": [{
        "rounded-tr": [u]
      }],
      /**
       * Border Radius Bottom Right
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-br": [{
        "rounded-br": [u]
      }],
      /**
       * Border Radius Bottom Left
       * @see https://tailwindcss.com/docs/border-radius
       */
      "rounded-bl": [{
        "rounded-bl": [u]
      }],
      /**
       * Border Width
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w": [{
        border: [f]
      }],
      /**
       * Border Width X
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-x": [{
        "border-x": [f]
      }],
      /**
       * Border Width Y
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-y": [{
        "border-y": [f]
      }],
      /**
       * Border Width Start
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-s": [{
        "border-s": [f]
      }],
      /**
       * Border Width End
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-e": [{
        "border-e": [f]
      }],
      /**
       * Border Width Top
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-t": [{
        "border-t": [f]
      }],
      /**
       * Border Width Right
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-r": [{
        "border-r": [f]
      }],
      /**
       * Border Width Bottom
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-b": [{
        "border-b": [f]
      }],
      /**
       * Border Width Left
       * @see https://tailwindcss.com/docs/border-width
       */
      "border-w-l": [{
        "border-l": [f]
      }],
      /**
       * Border Opacity
       * @see https://tailwindcss.com/docs/border-opacity
       */
      "border-opacity": [{
        "border-opacity": [z]
      }],
      /**
       * Border Style
       * @see https://tailwindcss.com/docs/border-style
       */
      "border-style": [{
        border: [...j(), "hidden"]
      }],
      /**
       * Divide Width X
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-x": [{
        "divide-x": [f]
      }],
      /**
       * Divide Width X Reverse
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-x-reverse": ["divide-x-reverse"],
      /**
       * Divide Width Y
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-y": [{
        "divide-y": [f]
      }],
      /**
       * Divide Width Y Reverse
       * @see https://tailwindcss.com/docs/divide-width
       */
      "divide-y-reverse": ["divide-y-reverse"],
      /**
       * Divide Opacity
       * @see https://tailwindcss.com/docs/divide-opacity
       */
      "divide-opacity": [{
        "divide-opacity": [z]
      }],
      /**
       * Divide Style
       * @see https://tailwindcss.com/docs/divide-style
       */
      "divide-style": [{
        divide: j()
      }],
      /**
       * Border Color
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color": [{
        border: [r]
      }],
      /**
       * Border Color X
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-x": [{
        "border-x": [r]
      }],
      /**
       * Border Color Y
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-y": [{
        "border-y": [r]
      }],
      /**
       * Border Color S
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-s": [{
        "border-s": [r]
      }],
      /**
       * Border Color E
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-e": [{
        "border-e": [r]
      }],
      /**
       * Border Color Top
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-t": [{
        "border-t": [r]
      }],
      /**
       * Border Color Right
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-r": [{
        "border-r": [r]
      }],
      /**
       * Border Color Bottom
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-b": [{
        "border-b": [r]
      }],
      /**
       * Border Color Left
       * @see https://tailwindcss.com/docs/border-color
       */
      "border-color-l": [{
        "border-l": [r]
      }],
      /**
       * Divide Color
       * @see https://tailwindcss.com/docs/divide-color
       */
      "divide-color": [{
        divide: [r]
      }],
      /**
       * Outline Style
       * @see https://tailwindcss.com/docs/outline-style
       */
      "outline-style": [{
        outline: ["", ...j()]
      }],
      /**
       * Outline Offset
       * @see https://tailwindcss.com/docs/outline-offset
       */
      "outline-offset": [{
        "outline-offset": [Ki, St]
      }],
      /**
       * Outline Width
       * @see https://tailwindcss.com/docs/outline-width
       */
      "outline-w": [{
        outline: [Ki, Cs]
      }],
      /**
       * Outline Color
       * @see https://tailwindcss.com/docs/outline-color
       */
      "outline-color": [{
        outline: [n]
      }],
      /**
       * Ring Width
       * @see https://tailwindcss.com/docs/ring-width
       */
      "ring-w": [{
        ring: ie()
      }],
      /**
       * Ring Width Inset
       * @see https://tailwindcss.com/docs/ring-width
       */
      "ring-w-inset": ["ring-inset"],
      /**
       * Ring Color
       * @see https://tailwindcss.com/docs/ring-color
       */
      "ring-color": [{
        ring: [n]
      }],
      /**
       * Ring Opacity
       * @see https://tailwindcss.com/docs/ring-opacity
       */
      "ring-opacity": [{
        "ring-opacity": [z]
      }],
      /**
       * Ring Offset Width
       * @see https://tailwindcss.com/docs/ring-offset-width
       */
      "ring-offset-w": [{
        "ring-offset": [Ki, Cs]
      }],
      /**
       * Ring Offset Color
       * @see https://tailwindcss.com/docs/ring-offset-color
       */
      "ring-offset-color": [{
        "ring-offset": [n]
      }],
      // Effects
      /**
       * Box Shadow
       * @see https://tailwindcss.com/docs/box-shadow
       */
      shadow: [{
        shadow: ["", "inner", "none", Es, oB]
      }],
      /**
       * Box Shadow Color
       * @see https://tailwindcss.com/docs/box-shadow-color
       */
      "shadow-color": [{
        shadow: [Hu]
      }],
      /**
       * Opacity
       * @see https://tailwindcss.com/docs/opacity
       */
      opacity: [{
        opacity: [z]
      }],
      /**
       * Mix Blend Mode
       * @see https://tailwindcss.com/docs/mix-blend-mode
       */
      "mix-blend": [{
        "mix-blend": [...W(), "plus-lighter", "plus-darker"]
      }],
      /**
       * Background Blend Mode
       * @see https://tailwindcss.com/docs/background-blend-mode
       */
      "bg-blend": [{
        "bg-blend": W()
      }],
      // Filters
      /**
       * Filter
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/filter
       */
      filter: [{
        filter: ["", "none"]
      }],
      /**
       * Blur
       * @see https://tailwindcss.com/docs/blur
       */
      blur: [{
        blur: [i]
      }],
      /**
       * Brightness
       * @see https://tailwindcss.com/docs/brightness
       */
      brightness: [{
        brightness: [a]
      }],
      /**
       * Contrast
       * @see https://tailwindcss.com/docs/contrast
       */
      contrast: [{
        contrast: [m]
      }],
      /**
       * Drop Shadow
       * @see https://tailwindcss.com/docs/drop-shadow
       */
      "drop-shadow": [{
        "drop-shadow": ["", "none", Es, St]
      }],
      /**
       * Grayscale
       * @see https://tailwindcss.com/docs/grayscale
       */
      grayscale: [{
        grayscale: [p]
      }],
      /**
       * Hue Rotate
       * @see https://tailwindcss.com/docs/hue-rotate
       */
      "hue-rotate": [{
        "hue-rotate": [g]
      }],
      /**
       * Invert
       * @see https://tailwindcss.com/docs/invert
       */
      invert: [{
        invert: [y]
      }],
      /**
       * Saturate
       * @see https://tailwindcss.com/docs/saturate
       */
      saturate: [{
        saturate: [H]
      }],
      /**
       * Sepia
       * @see https://tailwindcss.com/docs/sepia
       */
      sepia: [{
        sepia: [Q]
      }],
      /**
       * Backdrop Filter
       * @deprecated since Tailwind CSS v3.0.0
       * @see https://tailwindcss.com/docs/backdrop-filter
       */
      "backdrop-filter": [{
        "backdrop-filter": ["", "none"]
      }],
      /**
       * Backdrop Blur
       * @see https://tailwindcss.com/docs/backdrop-blur
       */
      "backdrop-blur": [{
        "backdrop-blur": [i]
      }],
      /**
       * Backdrop Brightness
       * @see https://tailwindcss.com/docs/backdrop-brightness
       */
      "backdrop-brightness": [{
        "backdrop-brightness": [a]
      }],
      /**
       * Backdrop Contrast
       * @see https://tailwindcss.com/docs/backdrop-contrast
       */
      "backdrop-contrast": [{
        "backdrop-contrast": [m]
      }],
      /**
       * Backdrop Grayscale
       * @see https://tailwindcss.com/docs/backdrop-grayscale
       */
      "backdrop-grayscale": [{
        "backdrop-grayscale": [p]
      }],
      /**
       * Backdrop Hue Rotate
       * @see https://tailwindcss.com/docs/backdrop-hue-rotate
       */
      "backdrop-hue-rotate": [{
        "backdrop-hue-rotate": [g]
      }],
      /**
       * Backdrop Invert
       * @see https://tailwindcss.com/docs/backdrop-invert
       */
      "backdrop-invert": [{
        "backdrop-invert": [y]
      }],
      /**
       * Backdrop Opacity
       * @see https://tailwindcss.com/docs/backdrop-opacity
       */
      "backdrop-opacity": [{
        "backdrop-opacity": [z]
      }],
      /**
       * Backdrop Saturate
       * @see https://tailwindcss.com/docs/backdrop-saturate
       */
      "backdrop-saturate": [{
        "backdrop-saturate": [H]
      }],
      /**
       * Backdrop Sepia
       * @see https://tailwindcss.com/docs/backdrop-sepia
       */
      "backdrop-sepia": [{
        "backdrop-sepia": [Q]
      }],
      // Tables
      /**
       * Border Collapse
       * @see https://tailwindcss.com/docs/border-collapse
       */
      "border-collapse": [{
        border: ["collapse", "separate"]
      }],
      /**
       * Border Spacing
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing": [{
        "border-spacing": [c]
      }],
      /**
       * Border Spacing X
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-x": [{
        "border-spacing-x": [c]
      }],
      /**
       * Border Spacing Y
       * @see https://tailwindcss.com/docs/border-spacing
       */
      "border-spacing-y": [{
        "border-spacing-y": [c]
      }],
      /**
       * Table Layout
       * @see https://tailwindcss.com/docs/table-layout
       */
      "table-layout": [{
        table: ["auto", "fixed"]
      }],
      /**
       * Caption Side
       * @see https://tailwindcss.com/docs/caption-side
       */
      caption: [{
        caption: ["top", "bottom"]
      }],
      // Transitions and Animation
      /**
       * Tranisition Property
       * @see https://tailwindcss.com/docs/transition-property
       */
      transition: [{
        transition: ["none", "all", "", "colors", "opacity", "shadow", "transform", St]
      }],
      /**
       * Transition Duration
       * @see https://tailwindcss.com/docs/transition-duration
       */
      duration: [{
        duration: Y()
      }],
      /**
       * Transition Timing Function
       * @see https://tailwindcss.com/docs/transition-timing-function
       */
      ease: [{
        ease: ["linear", "in", "out", "in-out", St]
      }],
      /**
       * Transition Delay
       * @see https://tailwindcss.com/docs/transition-delay
       */
      delay: [{
        delay: Y()
      }],
      /**
       * Animation
       * @see https://tailwindcss.com/docs/animation
       */
      animate: [{
        animate: ["none", "spin", "ping", "pulse", "bounce", St]
      }],
      // Transforms
      /**
       * Transform
       * @see https://tailwindcss.com/docs/transform
       */
      transform: [{
        transform: ["", "gpu", "none"]
      }],
      /**
       * Scale
       * @see https://tailwindcss.com/docs/scale
       */
      scale: [{
        scale: [X]
      }],
      /**
       * Scale X
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-x": [{
        "scale-x": [X]
      }],
      /**
       * Scale Y
       * @see https://tailwindcss.com/docs/scale
       */
      "scale-y": [{
        "scale-y": [X]
      }],
      /**
       * Rotate
       * @see https://tailwindcss.com/docs/rotate
       */
      rotate: [{
        rotate: [ju, St]
      }],
      /**
       * Translate X
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-x": [{
        "translate-x": [$]
      }],
      /**
       * Translate Y
       * @see https://tailwindcss.com/docs/translate
       */
      "translate-y": [{
        "translate-y": [$]
      }],
      /**
       * Skew X
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-x": [{
        "skew-x": [ut]
      }],
      /**
       * Skew Y
       * @see https://tailwindcss.com/docs/skew
       */
      "skew-y": [{
        "skew-y": [ut]
      }],
      /**
       * Transform Origin
       * @see https://tailwindcss.com/docs/transform-origin
       */
      "transform-origin": [{
        origin: ["center", "top", "top-right", "right", "bottom-right", "bottom", "bottom-left", "left", "top-left", St]
      }],
      // Interactivity
      /**
       * Accent Color
       * @see https://tailwindcss.com/docs/accent-color
       */
      accent: [{
        accent: ["auto", n]
      }],
      /**
       * Appearance
       * @see https://tailwindcss.com/docs/appearance
       */
      appearance: [{
        appearance: ["none", "auto"]
      }],
      /**
       * Cursor
       * @see https://tailwindcss.com/docs/cursor
       */
      cursor: [{
        cursor: ["auto", "default", "pointer", "wait", "text", "move", "help", "not-allowed", "none", "context-menu", "progress", "cell", "crosshair", "vertical-text", "alias", "copy", "no-drop", "grab", "grabbing", "all-scroll", "col-resize", "row-resize", "n-resize", "e-resize", "s-resize", "w-resize", "ne-resize", "nw-resize", "se-resize", "sw-resize", "ew-resize", "ns-resize", "nesw-resize", "nwse-resize", "zoom-in", "zoom-out", St]
      }],
      /**
       * Caret Color
       * @see https://tailwindcss.com/docs/just-in-time-mode#caret-color-utilities
       */
      "caret-color": [{
        caret: [n]
      }],
      /**
       * Pointer Events
       * @see https://tailwindcss.com/docs/pointer-events
       */
      "pointer-events": [{
        "pointer-events": ["none", "auto"]
      }],
      /**
       * Resize
       * @see https://tailwindcss.com/docs/resize
       */
      resize: [{
        resize: ["none", "y", "x", ""]
      }],
      /**
       * Scroll Behavior
       * @see https://tailwindcss.com/docs/scroll-behavior
       */
      "scroll-behavior": [{
        scroll: ["auto", "smooth"]
      }],
      /**
       * Scroll Margin
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-m": [{
        "scroll-m": it()
      }],
      /**
       * Scroll Margin X
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mx": [{
        "scroll-mx": it()
      }],
      /**
       * Scroll Margin Y
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-my": [{
        "scroll-my": it()
      }],
      /**
       * Scroll Margin Start
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ms": [{
        "scroll-ms": it()
      }],
      /**
       * Scroll Margin End
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-me": [{
        "scroll-me": it()
      }],
      /**
       * Scroll Margin Top
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mt": [{
        "scroll-mt": it()
      }],
      /**
       * Scroll Margin Right
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mr": [{
        "scroll-mr": it()
      }],
      /**
       * Scroll Margin Bottom
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-mb": [{
        "scroll-mb": it()
      }],
      /**
       * Scroll Margin Left
       * @see https://tailwindcss.com/docs/scroll-margin
       */
      "scroll-ml": [{
        "scroll-ml": it()
      }],
      /**
       * Scroll Padding
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-p": [{
        "scroll-p": it()
      }],
      /**
       * Scroll Padding X
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-px": [{
        "scroll-px": it()
      }],
      /**
       * Scroll Padding Y
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-py": [{
        "scroll-py": it()
      }],
      /**
       * Scroll Padding Start
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-ps": [{
        "scroll-ps": it()
      }],
      /**
       * Scroll Padding End
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pe": [{
        "scroll-pe": it()
      }],
      /**
       * Scroll Padding Top
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pt": [{
        "scroll-pt": it()
      }],
      /**
       * Scroll Padding Right
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pr": [{
        "scroll-pr": it()
      }],
      /**
       * Scroll Padding Bottom
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pb": [{
        "scroll-pb": it()
      }],
      /**
       * Scroll Padding Left
       * @see https://tailwindcss.com/docs/scroll-padding
       */
      "scroll-pl": [{
        "scroll-pl": it()
      }],
      /**
       * Scroll Snap Align
       * @see https://tailwindcss.com/docs/scroll-snap-align
       */
      "snap-align": [{
        snap: ["start", "end", "center", "align-none"]
      }],
      /**
       * Scroll Snap Stop
       * @see https://tailwindcss.com/docs/scroll-snap-stop
       */
      "snap-stop": [{
        snap: ["normal", "always"]
      }],
      /**
       * Scroll Snap Type
       * @see https://tailwindcss.com/docs/scroll-snap-type
       */
      "snap-type": [{
        snap: ["none", "x", "y", "both"]
      }],
      /**
       * Scroll Snap Type Strictness
       * @see https://tailwindcss.com/docs/scroll-snap-type
       */
      "snap-strictness": [{
        snap: ["mandatory", "proximity"]
      }],
      /**
       * Touch Action
       * @see https://tailwindcss.com/docs/touch-action
       */
      touch: [{
        touch: ["auto", "none", "manipulation"]
      }],
      /**
       * Touch Action X
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-x": [{
        "touch-pan": ["x", "left", "right"]
      }],
      /**
       * Touch Action Y
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-y": [{
        "touch-pan": ["y", "up", "down"]
      }],
      /**
       * Touch Action Pinch Zoom
       * @see https://tailwindcss.com/docs/touch-action
       */
      "touch-pz": ["touch-pinch-zoom"],
      /**
       * User Select
       * @see https://tailwindcss.com/docs/user-select
       */
      select: [{
        select: ["none", "text", "all", "auto"]
      }],
      /**
       * Will Change
       * @see https://tailwindcss.com/docs/will-change
       */
      "will-change": [{
        "will-change": ["auto", "scroll", "contents", "transform", St]
      }],
      // SVG
      /**
       * Fill
       * @see https://tailwindcss.com/docs/fill
       */
      fill: [{
        fill: [n, "none"]
      }],
      /**
       * Stroke Width
       * @see https://tailwindcss.com/docs/stroke-width
       */
      "stroke-w": [{
        stroke: [Ki, Cs, Lg]
      }],
      /**
       * Stroke
       * @see https://tailwindcss.com/docs/stroke
       */
      stroke: [{
        stroke: [n, "none"]
      }],
      // Accessibility
      /**
       * Screen Readers
       * @see https://tailwindcss.com/docs/screen-readers
       */
      sr: ["sr-only", "not-sr-only"],
      /**
       * Forced Color Adjust
       * @see https://tailwindcss.com/docs/forced-color-adjust
       */
      "forced-color-adjust": [{
        "forced-color-adjust": ["auto", "none"]
      }]
    },
    conflictingClassGroups: {
      overflow: ["overflow-x", "overflow-y"],
      overscroll: ["overscroll-x", "overscroll-y"],
      inset: ["inset-x", "inset-y", "start", "end", "top", "right", "bottom", "left"],
      "inset-x": ["right", "left"],
      "inset-y": ["top", "bottom"],
      flex: ["basis", "grow", "shrink"],
      gap: ["gap-x", "gap-y"],
      p: ["px", "py", "ps", "pe", "pt", "pr", "pb", "pl"],
      px: ["pr", "pl"],
      py: ["pt", "pb"],
      m: ["mx", "my", "ms", "me", "mt", "mr", "mb", "ml"],
      mx: ["mr", "ml"],
      my: ["mt", "mb"],
      size: ["w", "h"],
      "font-size": ["leading"],
      "fvn-normal": ["fvn-ordinal", "fvn-slashed-zero", "fvn-figure", "fvn-spacing", "fvn-fraction"],
      "fvn-ordinal": ["fvn-normal"],
      "fvn-slashed-zero": ["fvn-normal"],
      "fvn-figure": ["fvn-normal"],
      "fvn-spacing": ["fvn-normal"],
      "fvn-fraction": ["fvn-normal"],
      "line-clamp": ["display", "overflow"],
      rounded: ["rounded-s", "rounded-e", "rounded-t", "rounded-r", "rounded-b", "rounded-l", "rounded-ss", "rounded-se", "rounded-ee", "rounded-es", "rounded-tl", "rounded-tr", "rounded-br", "rounded-bl"],
      "rounded-s": ["rounded-ss", "rounded-es"],
      "rounded-e": ["rounded-se", "rounded-ee"],
      "rounded-t": ["rounded-tl", "rounded-tr"],
      "rounded-r": ["rounded-tr", "rounded-br"],
      "rounded-b": ["rounded-br", "rounded-bl"],
      "rounded-l": ["rounded-tl", "rounded-bl"],
      "border-spacing": ["border-spacing-x", "border-spacing-y"],
      "border-w": ["border-w-s", "border-w-e", "border-w-t", "border-w-r", "border-w-b", "border-w-l"],
      "border-w-x": ["border-w-r", "border-w-l"],
      "border-w-y": ["border-w-t", "border-w-b"],
      "border-color": ["border-color-s", "border-color-e", "border-color-t", "border-color-r", "border-color-b", "border-color-l"],
      "border-color-x": ["border-color-r", "border-color-l"],
      "border-color-y": ["border-color-t", "border-color-b"],
      "scroll-m": ["scroll-mx", "scroll-my", "scroll-ms", "scroll-me", "scroll-mt", "scroll-mr", "scroll-mb", "scroll-ml"],
      "scroll-mx": ["scroll-mr", "scroll-ml"],
      "scroll-my": ["scroll-mt", "scroll-mb"],
      "scroll-p": ["scroll-px", "scroll-py", "scroll-ps", "scroll-pe", "scroll-pt", "scroll-pr", "scroll-pb", "scroll-pl"],
      "scroll-px": ["scroll-pr", "scroll-pl"],
      "scroll-py": ["scroll-pt", "scroll-pb"],
      touch: ["touch-x", "touch-y", "touch-pz"],
      "touch-x": ["touch"],
      "touch-y": ["touch"],
      "touch-pz": ["touch"]
    },
    conflictingClassGroupModifiers: {
      "font-size": ["leading"]
    }
  };
}, fB = /* @__PURE__ */ F_(cB);
function ii(...n) {
  return fB(V_(n));
}
function hB({ children: n }) {
  const t = {
    initial: { scale: 0.94, opacity: 0 },
    animate: { scale: 1, opacity: 1, originY: 0 },
    exit: { scale: 0.94, opacity: 0 },
    transition: { type: "spring", stiffness: 260, damping: 32 }
  };
  return /* @__PURE__ */ Z.jsx(ld.div, { ...t, layout: !0, className: "mx-auto w-full", children: n });
}
const Vv = M1.memo(
  ({
    children: n,
    className: t,
    delay: i = 2600,
    maxVisible: a = 4,
    reducedMotion: r = !1,
    ...u
  }) => {
    const [c, f] = G.useState(0), [m, p] = G.useState(!1), g = G.useMemo(() => M1.Children.toArray(n), [n]);
    G.useEffect(() => {
      if (r || m) return;
      const b = setTimeout(() => {
        f((S) => (S + 1) % g.length);
      }, i);
      return () => clearTimeout(b);
    }, [c, i, g.length, m, r]);
    const y = G.useMemo(() => {
      if (r)
        return g.slice(0, a).reverse();
      const b = Math.min(c + 1, g.length), S = Math.max(0, b - a);
      return g.slice(S, b).reverse();
    }, [c, g, a, r]);
    return /* @__PURE__ */ Z.jsx(
      "div",
      {
        className: ii("flex flex-col items-center gap-2", t),
        onMouseEnter: () => p(!0),
        onMouseLeave: () => p(!1),
        ...u,
        children: /* @__PURE__ */ Z.jsx(g5, { children: y.map((b) => /* @__PURE__ */ Z.jsx(hB, { children: b }, b.key)) })
      }
    );
  }
);
Vv.displayName = "AnimatedList";
const dB = 0.08, mB = 700, pB = 1100, gB = 105, yB = 125;
function mE({
  children: n,
  className: t,
  glareOpacity: i = 0.08,
  duration: a = 900,
  angle: r = 115
}) {
  const u = Math.min(i, dB), c = Math.min(Math.max(a, mB), pB), m = {
    background: `linear-gradient(${Math.min(Math.max(r, gB), yB)}deg, transparent 35%, rgba(255,255,255,${u}) 50%, transparent 65%)`,
    backgroundSize: "250% 250%",
    backgroundPosition: "120% 120%",
    transition: `background-position ${c}ms ease`
  };
  return /* @__PURE__ */ Z.jsxs(
    "div",
    {
      className: ii("pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]", t),
      "aria-hidden": "true",
      children: [
        /* @__PURE__ */ Z.jsx(
          "div",
          {
            className: "absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100",
            style: m,
            "data-glare-layer": !0
          }
        ),
        n
      ]
    }
  );
}
const vB = 0.08, bB = 220, xB = 320;
function pE({
  children: n,
  className: t,
  gradientSize: i = 260,
  gradientColor: a = "rgba(113, 164, 255, 0.55)",
  gradientOpacity: r = 0.08
}) {
  const u = Math.min(Math.max(i, bB), xB), c = Math.min(r, vB), f = hc(-u), m = hc(-u), p = G.useCallback(() => {
    f.set(-u), m.set(-u);
  }, [f, m, u]), g = G.useCallback(
    (y) => {
      const b = y.currentTarget.getBoundingClientRect();
      f.set(y.clientX - b.left), m.set(y.clientY - b.top);
    },
    [f, m]
  );
  return G.useEffect(() => {
    p();
  }, [p]), /* @__PURE__ */ Z.jsxs(
    ld.div,
    {
      className: ii("sage-magic-card group relative", t),
      onPointerMove: g,
      onPointerLeave: p,
      children: [
        /* @__PURE__ */ Z.jsx(
          ld.div,
          {
            "aria-hidden": "true",
            className: "pointer-events-none absolute inset-0 z-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover:opacity-100",
            style: {
              background: C_`
            radial-gradient(${u}px circle at ${f}px ${m}px,
              ${a},
              transparent 100%
            )
          `,
              opacity: c
            }
          }
        ),
        /* @__PURE__ */ Z.jsx("div", { className: "relative z-10", children: n })
      ]
    }
  );
}
const SB = 0.025, wB = 0.055;
function gE({ className: n, opacity: t = 0.04 }) {
  const i = G.useId(), a = Math.min(Math.max(t, SB), wB);
  return /* @__PURE__ */ Z.jsxs(
    "svg",
    {
      "aria-hidden": "true",
      className: ii("pointer-events-none absolute inset-0 h-full w-full", n),
      style: { opacity: a, mixBlendMode: "soft-light" },
      children: [
        /* @__PURE__ */ Z.jsxs("filter", { id: i, children: [
          /* @__PURE__ */ Z.jsx("feTurbulence", { type: "fractalNoise", baseFrequency: "0.9", numOctaves: "2", stitchTiles: "stitch" }),
          /* @__PURE__ */ Z.jsx("feColorMatrix", { type: "saturate", values: "0" })
        ] }),
        /* @__PURE__ */ Z.jsx("rect", { width: "100%", height: "100%", filter: `url(#${i})` })
      ]
    }
  );
}
function Vd({ title: n, description: t, visual: i, className: a }) {
  return /* @__PURE__ */ Z.jsxs(
    "div",
    {
      className: ii(
        "glass-card group h-full transition-transform duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.005]",
        a
      ),
      children: [
        /* @__PURE__ */ Z.jsx(gE, { className: "z-[1]" }),
        /* @__PURE__ */ Z.jsx(mE, { className: "z-[2]" }),
        /* @__PURE__ */ Z.jsxs(pE, { className: "glass-card-content flex h-full flex-col gap-3 p-5", children: [
          /* @__PURE__ */ Z.jsxs("div", { className: "flex flex-col gap-1.5", children: [
            /* @__PURE__ */ Z.jsx("h3", { className: "text-[21px] font-semibold leading-snug text-[#F1F6FF]", children: n }),
            /* @__PURE__ */ Z.jsx("p", { className: "text-[14px] leading-[1.65] text-[#B2C1D5]", children: t })
          ] }),
          /* @__PURE__ */ Z.jsx("div", { className: "relative min-h-0 flex-1", children: i })
        ] })
      ]
    }
  );
}
const MB = [
  { file: "result.json", status: "结构化结果" },
  { file: "evidence_cards.json", status: "证据来源" },
  { file: "validation.json", status: "质量门" },
  { file: "provider_audit.json", status: "调用审计" },
  { file: "checksums.sha256", status: "文件校验" }
];
function TB({ reducedMotion: n }) {
  return /* @__PURE__ */ Z.jsx(
    Vd,
    {
      title: "开放与透明",
      description: "保留版本差异、运行轨迹、质量门结果、调用审计与可复现产物。",
      visual: /* @__PURE__ */ Z.jsx("div", { className: "flex h-full items-center justify-center overflow-hidden rounded-xl px-3 py-2", children: /* @__PURE__ */ Z.jsx(
        Vv,
        {
          className: "w-full",
          delay: 2400,
          maxVisible: 4,
          reducedMotion: n,
          children: MB.map((t) => /* @__PURE__ */ Z.jsxs(
            "div",
            {
              className: "mb-2 flex w-full items-center justify-between gap-3 rounded-lg border border-[rgba(124,164,217,0.18)] bg-[rgba(20,36,58,0.55)] px-3 py-2",
              children: [
                /* @__PURE__ */ Z.jsx("span", { className: "truncate text-[13px] font-mono text-[#DCE6F5]", children: t.file }),
                /* @__PURE__ */ Z.jsx("span", { className: "shrink-0 text-[12px] text-[#8192A9]", children: t.status })
              ]
            },
            t.file
          ))
        }
      ) })
    }
  );
}
const CB = [
  { label: "文献来源", detail: "DOI / 出版物元数据已核验" },
  { label: "原文片段", detail: "已定位于章节 / 段落" },
  { label: "定位信息", detail: "页码 · 章节 · 偏移量" },
  { label: "EvidenceCard", detail: "结构化证据卡片" },
  { label: "内容校验", detail: "SHA-256 校验和" }
];
function EB({ reducedMotion: n }) {
  return /* @__PURE__ */ Z.jsx(
    Vd,
    {
      title: "可追溯证据",
      description: "每项事实和候选假设均保留文献来源、原文片段、定位信息与内容校验和。",
      visual: /* @__PURE__ */ Z.jsx("div", { className: "flex h-full items-center justify-center overflow-hidden rounded-xl px-3 py-2", children: /* @__PURE__ */ Z.jsx(Vv, { className: "w-full", delay: 2600, maxVisible: 4, reducedMotion: n, children: CB.map((t) => /* @__PURE__ */ Z.jsxs(
        "div",
        {
          className: "mb-2 flex w-full items-center justify-between gap-3 rounded-lg border border-[rgba(124,164,217,0.18)] bg-[rgba(20,36,58,0.55)] px-3 py-2",
          children: [
            /* @__PURE__ */ Z.jsx("span", { className: "text-[13px] font-medium text-[#DCE6F5]", children: t.label }),
            /* @__PURE__ */ Z.jsx("span", { className: "text-[12px] text-[#8192A9]", children: t.detail })
          ]
        },
        t.label
      )) }) })
    }
  );
}
const AB = 4, DB = 7, Ph = 8, _a = ({
  className: n,
  containerRef: t,
  fromRef: i,
  toRef: a,
  curvature: r = 0,
  reverse: u = !1,
  duration: c = 5.5,
  delay: f = 0,
  pathColor: m = "#c7d5f5",
  pathWidth: p = 1.6,
  pathOpacity: g = 0.28,
  gradientStartColor: y = "#4D7FFF",
  gradientStopColor: b = "#2CC4D6",
  startXOffset: S = 0,
  startYOffset: T = 0,
  endXOffset: C = 0,
  endYOffset: R = 0,
  reducedMotion: z = !1
}) => {
  const B = G.useId(), [H, X] = G.useState(""), [Q, ut] = G.useState({ width: 0, height: 0 }), st = Math.min(Math.max(c, AB), DB), $ = u ? { x1: ["90%", "-10%"], x2: ["100%", "0%"], y1: ["0%", "0%"], y2: ["0%", "0%"] } : { x1: ["10%", "110%"], x2: ["0%", "100%"], y1: ["0%", "0%"], y2: ["0%", "0%"] };
  return G.useEffect(() => {
    let lt = !1, nt = 0;
    const vt = () => {
      if (lt) return;
      const Kt = t.current, zt = i.current, j = a.current;
      if (!Kt || !zt || !j) {
        X("");
        return;
      }
      const W = Kt.getBoundingClientRect(), J = zt.getBoundingClientRect(), ft = j.getBoundingClientRect();
      if (W.width < Ph || W.height < Ph || J.width < 1 || J.height < 1 || ft.width < 1 || ft.height < 1) {
        X("");
        return;
      }
      const D = J.left - W.left + J.width / 2 + S, Y = J.top - W.top + J.height / 2 + T, et = ft.left - W.left + ft.width / 2 + C, tt = ft.top - W.top + ft.height / 2 + R, rt = 2;
      if (!(D >= -rt && Y >= -rt && et >= -rt && tt >= -rt && D <= W.width + rt && Y <= W.height + rt && et <= W.width + rt && tt <= W.height + rt)) {
        X("");
        return;
      }
      const yt = (D + et) / 2, qe = Y - r, It = Math.min(W.height - 2, Math.max(2, qe));
      ut({ width: W.width, height: W.height }), X(`M ${D},${Y} Q ${yt},${It} ${et},${tt}`);
    }, it = () => {
      nt && window.cancelAnimationFrame(nt), nt = window.requestAnimationFrame(vt);
    }, ie = new ResizeObserver(it);
    return t.current && ie.observe(t.current), it(), () => {
      lt = !0, ie.disconnect(), nt && window.cancelAnimationFrame(nt), X("");
    };
  }, [t, i, a, r, S, T, C, R]), !H || Q.width < Ph || Q.height < Ph ? null : /* @__PURE__ */ Z.jsxs(
    "svg",
    {
      fill: "none",
      width: Q.width,
      height: Q.height,
      xmlns: "http://www.w3.org/2000/svg",
      overflow: "hidden",
      className: ii("pointer-events-none absolute left-0 top-0 transform-gpu", n),
      viewBox: `0 0 ${Q.width} ${Q.height}`,
      children: [
        /* @__PURE__ */ Z.jsx(
          "path",
          {
            d: H,
            stroke: m,
            strokeWidth: p,
            strokeOpacity: g,
            strokeLinecap: "round"
          }
        ),
        /* @__PURE__ */ Z.jsx("path", { d: H, strokeWidth: p, stroke: `url(#${B})`, strokeOpacity: 0.9, strokeLinecap: "round" }),
        /* @__PURE__ */ Z.jsx("defs", { children: /* @__PURE__ */ Z.jsxs(
          ld.linearGradient,
          {
            className: "transform-gpu",
            id: B,
            gradientUnits: "userSpaceOnUse",
            initial: { x1: "0%", x2: "0%", y1: "0%", y2: "0%" },
            animate: z ? { x1: "10%", x2: "0%", y1: "0%", y2: "0%" } : {
              x1: $.x1,
              x2: $.x2,
              y1: $.y1,
              y2: $.y2
            },
            transition: z ? { duration: 0 } : {
              delay: f,
              duration: st,
              ease: [0.16, 1, 0.3, 1],
              repeat: 1 / 0,
              repeatDelay: 0
            },
            children: [
              /* @__PURE__ */ Z.jsx("stop", { stopColor: y, stopOpacity: "0" }),
              /* @__PURE__ */ Z.jsx("stop", { stopColor: y }),
              /* @__PURE__ */ Z.jsx("stop", { offset: "32.5%", stopColor: b }),
              /* @__PURE__ */ Z.jsx("stop", { offset: "100%", stopColor: b, stopOpacity: "0" })
            ]
          }
        ) })
      ]
    }
  );
}, ud = G.forwardRef(
  ({ label: n, emphasis: t = !1, className: i, style: a }, r) => /* @__PURE__ */ Z.jsx(
    "div",
    {
      ref: r,
      style: a,
      className: ii(
        "z-10 inline-flex items-center justify-center whitespace-nowrap rounded-full border px-3 py-1.5 text-[12px] font-medium leading-none shadow-sm",
        t ? "border-[#71A4FF]/45 bg-[#4D7FFF]/18 text-[#EAF1FF]" : "border-[rgba(124,164,217,0.28)] bg-[rgba(20,36,58,0.72)] text-[#B7C5D8]",
        i
      ),
      children: n
    }
  )
);
ud.displayName = "BeamNode";
const Ww = [
  { key: "search", label: "文献检索", style: { top: "6%", left: "50%", transform: "translate(-50%, 0)" } },
  { key: "verify", label: "证据核验", style: { top: "28%", left: "88%", transform: "translate(-50%, -50%)" } },
  { key: "review", label: "科学评审", style: { top: "78%", left: "78%", transform: "translate(-50%, -50%)" } },
  { key: "plan", label: "研究计划", style: { top: "78%", left: "22%", transform: "translate(-50%, -50%)" } },
  { key: "hypothesis", label: "假设生成", style: { top: "28%", left: "12%", transform: "translate(-50%, -50%)" } }
];
function RB({ reducedMotion: n }) {
  const t = G.useRef(null), i = G.useRef(null), a = G.useRef(null), r = G.useRef(null), u = G.useRef(null), c = G.useRef(null), f = G.useRef(null), m = {
    search: a,
    verify: r,
    review: u,
    plan: c,
    hypothesis: f
  };
  return /* @__PURE__ */ Z.jsx(
    Vd,
    {
      title: "多智能体协同",
      description: "不同智能体围绕同一证据上下文协作，并将评审意见和未关闭问题带入后续修订。",
      visual: /* @__PURE__ */ Z.jsxs(
        "div",
        {
          ref: t,
          className: "relative h-full min-h-[140px] overflow-hidden rounded-xl",
          children: [
            Ww.map((p) => /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: i,
                toRef: m[p.key],
                pathOpacity: 0.14,
                pathColor: "#c7d5f5",
                reducedMotion: !0
              },
              `spoke-${p.key}`
            )),
            /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: r,
                toRef: f,
                curvature: -14,
                duration: 5,
                reducedMotion: n
              }
            ),
            /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: f,
                toRef: u,
                curvature: 14,
                duration: 5.5,
                delay: 0.4,
                reducedMotion: n
              }
            ),
            /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: u,
                toRef: c,
                curvature: -10,
                duration: 5,
                delay: 0.8,
                reducedMotion: n
              }
            ),
            /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: u,
                toRef: f,
                curvature: 16,
                duration: 6.5,
                delay: 0.2,
                reverse: !0,
                pathOpacity: 0.16,
                reducedMotion: n
              }
            ),
            /* @__PURE__ */ Z.jsx(
              ud,
              {
                ref: i,
                label: "研究任务",
                emphasis: !0,
                className: "absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
              }
            ),
            Ww.map((p) => /* @__PURE__ */ Z.jsx(
              ud,
              {
                ref: m[p.key],
                label: p.label,
                className: "absolute",
                style: p.style
              },
              p.key
            ))
          ]
        }
      )
    }
  );
}
const _g = ["科学问题", "证据", "候选假设", "可检验预测", "研究计划"];
function OB({ reducedMotion: n }) {
  const t = G.useRef(null), i = [
    G.useRef(null),
    G.useRef(null),
    G.useRef(null),
    G.useRef(null),
    G.useRef(null)
  ];
  return /* @__PURE__ */ Z.jsx(
    Vd,
    {
      title: "可验证研究",
      description: "将候选假设转化为数据、变量、评价指标以及支持或否定条件明确的研究方案。",
      visual: /* @__PURE__ */ Z.jsxs(
        "div",
        {
          ref: t,
          className: "relative flex h-full min-h-[120px] flex-wrap items-center justify-between gap-y-6 overflow-hidden rounded-xl px-4 py-6",
          children: [
            _g.map((a, r) => /* @__PURE__ */ Z.jsx(
              ud,
              {
                ref: i[r],
                label: a,
                emphasis: r === 2,
                className: "basis-[18%]"
              },
              a
            )),
            !n && _g.slice(0, -1).map((a, r) => /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: i[r],
                toRef: i[r + 1],
                curvature: r % 2 === 0 ? 18 : -18,
                duration: 5.5,
                delay: r * 0.3,
                gradientStartColor: "#4D7FFF",
                gradientStopColor: "#2CC4D6",
                reducedMotion: n
              },
              `beam-${r}`
            )),
            n && _g.slice(0, -1).map((a, r) => /* @__PURE__ */ Z.jsx(
              _a,
              {
                containerRef: t,
                fromRef: i[r],
                toRef: i[r + 1],
                curvature: r % 2 === 0 ? 18 : -18,
                pathOpacity: 0.22,
                reducedMotion: !0
              },
              `beam-static-${r}`
            ))
          ]
        }
      )
    }
  );
}
function zB({ children: n, className: t, ...i }) {
  return /* @__PURE__ */ Z.jsx(
    "div",
    {
      className: ii("grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12", t),
      ...i,
      children: n
    }
  );
}
function Lh({ className: n, children: t, ...i }) {
  return /* @__PURE__ */ Z.jsx("div", { className: ii("relative flex flex-col", n), ...i, children: t });
}
function kB({
  value: n,
  startValue: t = 0,
  direction: i = "up",
  delay: a = 0,
  className: r,
  decimalPlaces: u = 0,
  suffix: c = "",
  ...f
}) {
  const m = G.useRef(null), p = hc(i === "down" ? n ?? 0 : t), g = R_(p, { damping: 60, stiffness: 100 }), y = k_(m, { once: !0, margin: "0px" });
  if (G.useEffect(() => {
    if (n === null || !y) return;
    const S = setTimeout(() => {
      p.set(i === "down" ? t : n);
    }, a * 1e3);
    return () => clearTimeout(S);
  }, [p, y, a, n, i, t]), G.useEffect(
    () => g.on("change", (S) => {
      m.current && n !== null && (m.current.textContent = Intl.NumberFormat("en-US", {
        minimumFractionDigits: u,
        maximumFractionDigits: u
      }).format(Number(S.toFixed(u))) + c);
    }),
    [g, u, c, n]
  ), n === null)
    return /* @__PURE__ */ Z.jsx("span", { className: ii("tabular-nums", r), ...f, children: "—" });
  const b = Intl.NumberFormat("en-US", {
    minimumFractionDigits: u,
    maximumFractionDigits: u
  }).format(t === n ? n : t) + c;
  return /* @__PURE__ */ Z.jsx("span", { ref: m, className: ii("tabular-nums", r), ...f, children: b });
}
function Bg(n, t) {
  return n === "loading" ? { kind: "skeleton" } : n === "error" || t === null ? { kind: "text", text: "数据异常" } : { kind: "number", value: t };
}
function VB(n, t, i) {
  return n === "loading" ? { kind: "skeleton" } : n === "error" ? { kind: "text", text: "数据异常" } : i === "unavailable" ? { kind: "text", text: "未计算" } : t === null ? { kind: "text", text: "数据异常" } : { kind: "number", value: t, decimals: 1, suffix: "%" };
}
function PB({
  questionCount: n,
  evidenceCount: t,
  planCount: i,
  coverage: a,
  coverageStatus: r,
  statsStatus: u
}) {
  const c = [
    { label: "官方科学问题", hint: "官方锁定 Catalog 唯一题号", display: Bg(u, n) },
    { label: "可追溯证据", hint: "有效 EvidenceCard 去重计数", display: Bg(u, t) },
    { label: "研究计划", hint: "结构化完整研究计划", display: Bg(u, i) },
    { label: "证据回链覆盖", hint: "可解析引用占比", display: VB(u, a, r) }
  ];
  return /* @__PURE__ */ Z.jsx("div", { className: "metric-grid", children: c.map((f) => /* @__PURE__ */ Z.jsxs("article", { className: "metric-card", children: [
    /* @__PURE__ */ Z.jsx("div", { className: "metric-card-surface" }),
    /* @__PURE__ */ Z.jsx(gE, { className: "metric-card-noise" }),
    /* @__PURE__ */ Z.jsx("div", { className: "metric-card-highlight" }),
    /* @__PURE__ */ Z.jsx(mE, { className: "metric-card-highlight", glareOpacity: 0.08, duration: 900 }),
    /* @__PURE__ */ Z.jsx(pE, { className: "metric-card-content h-full", children: /* @__PURE__ */ Z.jsxs("div", { className: "flex h-full flex-col justify-center gap-1 px-4 py-5 text-left", children: [
      f.display.kind === "skeleton" ? /* @__PURE__ */ Z.jsx("span", { className: "metric-skeleton", "aria-hidden": "true" }) : f.display.kind === "text" ? /* @__PURE__ */ Z.jsx("span", { className: "font-latin text-[28px] font-semibold tracking-tight text-[#F3F7FF] lg:text-[34px]", children: f.display.text }) : /* @__PURE__ */ Z.jsx("span", { className: "font-latin text-[28px] font-semibold tracking-tight text-[#F3F7FF] lg:text-[34px]", children: /* @__PURE__ */ Z.jsx(
        kB,
        {
          value: f.display.value,
          startValue: f.display.value,
          decimalPlaces: f.display.decimals ?? 0,
          suffix: f.display.suffix ?? ""
        }
      ) }),
      /* @__PURE__ */ Z.jsx("span", { className: "text-[14px] text-[#9EB0C7] sm:text-[15px]", children: f.label }),
      /* @__PURE__ */ Z.jsx("span", { className: "text-[12px] text-[#71849D]", children: f.hint })
    ] }) })
  ] }, f.label)) });
}
function LB() {
  var n;
  return typeof window < "u" && ((n = window.matchMedia) == null ? void 0 : n.call(window, "(prefers-reduced-motion: reduce)").matches) === !0;
}
function _h(n) {
  return !n.animationStatus;
}
function _B(n) {
  var a, r, u, c, f, m, p, g, y, b, S, T, C;
  const t = n.actualOptions;
  let i;
  for (const R of n.plugins) {
    const z = R.interactionManager, B = (r = (a = z == null ? void 0 : z.interactivityData) == null ? void 0 : a.mouse) == null ? void 0 : r.position;
    if (B) {
      i = B;
      break;
    }
  }
  return {
    linkDistance: Number(((c = (u = t.particles) == null ? void 0 : u.links) == null ? void 0 : c.distance) ?? 145),
    linkOpacity: Number(((m = (f = t.particles) == null ? void 0 : f.links) == null ? void 0 : m.opacity) ?? 0.25),
    grabDistance: Number(((y = (g = (p = t.interactivity) == null ? void 0 : p.modes) == null ? void 0 : g.grab) == null ? void 0 : y.distance) ?? 175),
    mouse: i,
    detectsOn: String(((b = t.interactivity) == null ? void 0 : b.detectsOn) ?? ""),
    hoverEnabled: ((C = (T = (S = t.interactivity) == null ? void 0 : S.events) == null ? void 0 : T.onHover) == null ? void 0 : C.enable) === !0
  };
}
const BB = ({ className: n }) => {
  const t = G.useRef(null), i = G.useRef(null), a = G.useRef(void 0), { loaded: r } = TT(), u = LB(), c = G.useMemo(
    () => ({
      autoPlay: !0,
      fullScreen: { enable: !1 },
      background: { color: { value: "transparent" } },
      fpsLimit: 45,
      detectRetina: !0,
      pauseOnBlur: !0,
      pauseOnOutsideViewport: !1,
      motion: {
        disable: !1,
        reduce: { factor: 4, value: !0 }
      },
      particles: {
        number: {
          value: u ? 22 : 86,
          density: { enable: !0, width: 1600, height: 760 }
        },
        color: { value: ["#58A6FF", "#38D0DF", "#7399FF", "#B4D0FF"] },
        shape: { type: "circle" },
        opacity: {
          value: { min: 0.3, max: 0.72 },
          animation: {
            enable: !u,
            speed: 0.55,
            sync: !1,
            startValue: "random"
          }
        },
        size: {
          value: { min: 1.2, max: 3.8 },
          animation: {
            enable: !u,
            speed: 1,
            sync: !1,
            startValue: "random"
          }
        },
        links: {
          enable: !0,
          distance: 145,
          color: "#65A8F7",
          opacity: u ? 0.18 : 0.25,
          width: 1
        },
        move: {
          enable: !u,
          speed: { min: 0.42, max: 0.88 },
          direction: "none",
          random: !0,
          straight: !1,
          outModes: { default: "out" }
        }
      },
      interactivity: {
        detectsOn: "window",
        events: {
          onHover: { enable: !u, mode: "grab" },
          onClick: { enable: !1 },
          resize: { enable: !0, delay: 0.3 }
        },
        modes: { grab: { distance: 175, links: { opacity: 0.62 } } }
      },
      responsive: [
        {
          maxWidth: 1440,
          options: { particles: { number: { value: 70 }, links: { distance: 132 } } }
        },
        {
          maxWidth: 1024,
          options: {
            particles: {
              number: { value: 44 },
              links: { distance: 115 },
              move: { speed: { min: 0.32, max: 0.68 } }
            }
          }
        },
        {
          maxWidth: 768,
          options: {
            particles: {
              number: { value: 22 },
              links: { distance: 92, opacity: 0.18 },
              move: { speed: { min: 0.25, max: 0.52 } }
            }
          }
        }
      ]
    }),
    [u]
  ), f = G.useCallback((g) => {
    const y = g.particles.filter((z) => !z.destroyed && !z.spawning), b = _B(g);
    let S = 0, T = 0;
    const C = y.map((z, B) => {
      var X;
      const H = ((X = z.opacity) == null ? void 0 : X.value) ?? z.getOpacity().opacity;
      for (let Q = B + 1; Q < y.length; Q += 1) {
        const ut = z.position.x - y[Q].position.x, st = z.position.y - y[Q].position.y;
        Math.hypot(ut, st) <= b.linkDistance && (S += 1, b.mouse && Math.hypot(z.position.x - b.mouse.x, z.position.y - b.mouse.y) <= b.grabDistance && (T += 1));
      }
      return {
        x: Number(z.position.x),
        y: Number(z.position.y),
        opacity: Number(H)
      };
    }), R = {
      count: Number(g.particles.count),
      linkCount: S,
      grabBoosted: T,
      mouse: b.mouse,
      detectsOn: b.detectsOn,
      hoverEnabled: b.hoverEnabled,
      linkOpacityAvg: T > 0 ? 0.62 : b.linkOpacity,
      paused: _h(g),
      destroyed: !!g.destroyed,
      width: Number(g.canvas.size.width),
      height: Number(g.canvas.size.height),
      positions: C
    };
    return window.__sage125ParticlesSnapshot = R, R;
  }, []), m = G.useCallback(async (g) => {
    const y = t.current, b = g.canvas.domElement;
    !y || !b || (b.parentElement !== y && y.appendChild(b), b.style.position = "absolute", b.style.inset = "0", b.style.width = "100%", b.style.height = "100%", b.style.opacity = "1", b.style.display = "block", b.style.pointerEvents = "none", typeof g.canvas.resize == "function" && g.canvas.resize(), _h(g) && g.play());
  }, []), p = G.useCallback(
    async (g) => {
      if (!g) {
        console.error("[SAGE125_PARTICLES] container is undefined"), window.__sage125ParticlesStatus = "failed", window.__sage125ParticlesError = "container is undefined";
        return;
      }
      try {
        a.current = g, window.__sage125ParticlesCapture = () => {
          const y = a.current;
          return y ? f(y) : null;
        }, await m(g), f(g), window.__sage125ParticlesInitCount = (window.__sage125ParticlesInitCount ?? 0) + 1, window.__sage125ParticlesReadyAtMs = performance.now(), window.__sage125ParticlesStatus = _h(g) ? "paused" : "ready", console.info("[SAGE125_PARTICLES] loaded", {
          id: String(g.id),
          width: g.canvas.size.width,
          height: g.canvas.size.height,
          paused: _h(g)
        });
      } catch (y) {
        throw window.__sage125ParticlesStatus = "failed", window.__sage125ParticlesError = y instanceof Error ? `${y.name}: ${y.message}` : String(y), console.error("[SAGE125_PARTICLES] loaded handler failed", y), y;
      }
    },
    [m, f]
  );
  return G.useEffect(() => {
    const g = t.current;
    i.current = (g == null ? void 0 : g.closest("section")) ?? null;
  }, [r]), G.useEffect(() => {
    const g = i.current;
    if (!g || typeof ResizeObserver > "u") return;
    let y = 0;
    const b = new ResizeObserver(() => {
      y && window.cancelAnimationFrame(y), y = window.requestAnimationFrame(() => {
        const S = a.current;
        !S || S.destroyed || typeof S.canvas.resize == "function" && S.canvas.resize();
      });
    });
    return b.observe(g), () => {
      b.disconnect(), y && window.cancelAnimationFrame(y);
    };
  }, [r]), G.useEffect(() => {
    const g = i.current;
    if (!g) return;
    const y = new IntersectionObserver(
      async ([b]) => {
        const S = a.current;
        !S || S.destroyed || (b.isIntersecting && b.intersectionRatio > 0.08 ? (await S.play(), window.__sage125ParticlesStatus = "ready") : (S.pause(), window.__sage125ParticlesStatus = "paused"));
      },
      { threshold: [0, 0.08, 0.25] }
    );
    return y.observe(g), () => y.disconnect();
  }, [r]), G.useEffect(() => {
    const g = async () => {
      const y = a.current;
      !y || y.destroyed || (document.visibilityState === "visible" ? (await y.play(), window.__sage125ParticlesStatus = "ready") : (y.pause(), window.__sage125ParticlesStatus = "paused"));
    };
    return document.addEventListener("visibilitychange", g), () => document.removeEventListener("visibilitychange", g);
  }, []), G.useEffect(() => {
    window.__sage125ParticlesStatus = r ? window.__sage125ParticlesStatus ?? "loading" : "loading";
  }, [r]), /* @__PURE__ */ Z.jsx(
    "div",
    {
      ref: t,
      className: "sage125-particle-layer particles-layer " + (n ?? ""),
      "aria-hidden": "true",
      children: r ? /* @__PURE__ */ Z.jsx(
        yV,
        {
          id: "sage125-hero-particles",
          options: c,
          particlesLoaded: p
        }
      ) : null
    }
  );
};
function NB({ q028Available: n, onFireCta: t }) {
  return /* @__PURE__ */ Z.jsxs("section", { className: "sage125-hero hero-section relative flex w-full flex-col items-center justify-center px-6 py-16", children: [
    /* @__PURE__ */ Z.jsx(BB, {}),
    /* @__PURE__ */ Z.jsx("div", { "aria-hidden": "true", className: "sage125-hero-grid ambient-light-layer" }),
    /* @__PURE__ */ Z.jsx("div", { "aria-hidden": "true", className: "sage125-hero-readability readability-mask" }),
    /* @__PURE__ */ Z.jsxs("div", { className: "sage125-hero-content hero-content mx-auto flex w-full max-w-[1000px] flex-col items-center text-center", children: [
      /* @__PURE__ */ Z.jsx("p", { className: "font-latin text-[13px] font-semibold uppercase tracking-[0.06em] text-[#71A4FF]", children: "SAGE125 AI Scientist" }),
      /* @__PURE__ */ Z.jsx(
        "h1",
        {
          className: "mt-4 text-balance text-[44px] font-bold leading-[1.16] tracking-[-0.035em] text-[#F3F7FF] sm:text-[48px] md:text-[54px] lg:text-[60px]",
          style: { fontWeight: 720, textShadow: "0 0 22px rgba(113,164,255,0.14)" },
          children: "从科学问题到可验证研究计划"
        }
      ),
      /* @__PURE__ */ Z.jsx("p", { className: "mx-auto mt-5 max-w-[760px] text-[18px] leading-[1.8] text-[#B7C5D8] sm:text-[19px] md:text-[20px]", children: "基于可追溯文献证据与严谨科研方法，系统组织知识缺口、形成候选假设， 并将其转化为可检验、可复核的研究计划。" }),
      /* @__PURE__ */ Z.jsxs("div", { className: "hero-actions mt-9 flex flex-wrap items-center justify-center gap-4", children: [
        /* @__PURE__ */ Z.jsx("button", { type: "button", className: "hero-cta hero-cta-primary", onClick: () => t("enter_workspace"), children: "进入研究工作区" }),
        /* @__PURE__ */ Z.jsx(
          "button",
          {
            type: "button",
            className: "hero-cta hero-cta-secondary",
            disabled: !n,
            onClick: () => t("view_q028"),
            "aria-label": n ? "查看代表案例 Q028" : "代表案例暂不可用",
            children: "查看代表案例"
          }
        )
      ] })
    ] })
  ] });
}
function UB() {
  const [n, t] = G.useState(
    () => {
      var i;
      return typeof window < "u" && ((i = window.matchMedia) == null ? void 0 : i.call(window, "(prefers-reduced-motion: reduce)").matches) === !0;
    }
  );
  return G.useEffect(() => {
    const i = window.matchMedia("(prefers-reduced-motion: reduce)"), a = () => t(i.matches);
    return i.addEventListener("change", a), () => i.removeEventListener("change", a);
  }, []), n;
}
function jB({ data: n, setTriggerValue: t }) {
  const i = UB(), a = (r) => {
    t(r, Date.now());
  };
  return /* @__PURE__ */ Z.jsxs("div", { className: "sage125-landing-root w-full", children: [
    /* @__PURE__ */ Z.jsx(NB, { q028Available: n.q028_available, onFireCta: a }),
    /* @__PURE__ */ Z.jsxs("div", { className: "mx-auto w-full max-w-[1400px] px-1 pb-4", children: [
      /* @__PURE__ */ Z.jsx(
        PB,
        {
          questionCount: n.question_count,
          evidenceCount: n.evidence_count,
          planCount: n.plan_count,
          coverage: n.coverage,
          coverageStatus: n.coverage_status,
          statsStatus: n.stats_status
        }
      ),
      /* @__PURE__ */ Z.jsxs("section", { className: "mt-8", id: "land-capabilities", children: [
        /* @__PURE__ */ Z.jsx("h2", { className: "mb-4 text-[22px] font-semibold text-[#F1F6FF]", children: "系统能力" }),
        /* @__PURE__ */ Z.jsxs(zB, { children: [
          /* @__PURE__ */ Z.jsx(Lh, { className: "col-span-12 min-h-[280px] lg:col-span-7 lg:min-h-[300px]", children: /* @__PURE__ */ Z.jsx(EB, { reducedMotion: i }) }),
          /* @__PURE__ */ Z.jsx(Lh, { className: "col-span-12 min-h-[280px] lg:col-span-5 lg:min-h-[300px]", children: /* @__PURE__ */ Z.jsx(OB, { reducedMotion: i }) }),
          /* @__PURE__ */ Z.jsx(Lh, { className: "col-span-12 min-h-[240px] lg:col-span-5 lg:min-h-[260px]", children: /* @__PURE__ */ Z.jsx(RB, { reducedMotion: i }) }),
          /* @__PURE__ */ Z.jsx(Lh, { className: "col-span-12 min-h-[240px] lg:col-span-7 lg:min-h-[260px]", children: /* @__PURE__ */ Z.jsx(TB, { reducedMotion: i }) })
        ] })
      ] })
    ] })
  ] });
}
const Bh = /* @__PURE__ */ new WeakMap(), Jw = /* @__PURE__ */ new WeakSet(), HB = async (n) => {
  Jw.has(n) || (await dV(n), Jw.add(n), typeof window < "u" && (window.__sage125LoadSlimCount = (window.__sage125LoadSlimCount ?? 0) + 1));
};
function qB(n) {
  return /* @__PURE__ */ Z.jsx(pV, { init: HB, children: /* @__PURE__ */ Z.jsx(jB, { data: n.data, setTriggerValue: n.setTriggerValue }) });
}
const K6 = (n) => {
  const { data: t, parentElement: i, setTriggerValue: a } = n, r = i.querySelector(".sage125-landing-root");
  if (!r)
    throw new Error("Unexpected: sage125_landing root element not found");
  let u = Bh.get(i);
  return u || (u = TV.createRoot(r), Bh.set(i, u)), u.render(
    /* @__PURE__ */ Z.jsx(G.StrictMode, { children: /* @__PURE__ */ Z.jsx(qB, { data: t, setTriggerValue: a }) })
  ), () => {
    const c = Bh.get(i);
    c && (c.unmount(), Bh.delete(i));
  };
}, GB = 0, YB = 1;
function XB(n, t, i) {
  const a = t[i];
  a !== void 0 && (n[i] = (n[i] ?? HR) * a);
}
var vi, $a, Ls, sn, _s, bi, Bs, Vc, Ns, Us, js, Wa, ll, Hs, qs, md, ul, pd, wt, yE, vE, bE, xE, SE, wE, ME, TE, CE, Kn, EE, AE, Zu;
class FB {
  constructor(t, i, a) {
    k(this, wt);
    k(this, vi);
    k(this, $a);
    k(this, Ls);
    k(this, sn);
    k(this, _s);
    k(this, bi);
    k(this, Bs);
    k(this, Vc);
    k(this, Ns);
    k(this, Us);
    k(this, js);
    k(this, Wa);
    k(this, ll);
    k(this, Hs);
    k(this, qs);
    k(this, md, {});
    k(this, ul, [void 0, void 0]);
    k(this, pd, {});
    A(this, ll, t), A(this, bi, i), A(this, sn, a), A(this, Bs, null), A(this, vi, null), A(this, $a, /* @__PURE__ */ new Set()), A(this, qs, []), A(this, Hs, []), A(this, Ls, []), A(this, _s, []), A(this, Ns, []), A(this, Us, []), A(this, js, []), A(this, Wa, {
      0: [],
      1: [],
      2: [],
      3: [],
      4: [],
      5: [],
      6: [],
      7: []
    });
  }
  get settings() {
    return v(this, Vc);
  }
  canvasClear() {
    v(this, bi).actualOptions.clear && this.draw((t) => {
      t.clearRect(Dt.x, Dt.y, v(this, sn).size.width, v(this, sn).size.height);
    });
  }
  clear() {
    var t, i;
    for (const a of v(this, Ls))
      if (((t = a.canvasClear) == null ? void 0 : t.call(a)) ?? !1)
        return;
    for (const a of Object.values(Ye))
      if (typeof a == "number") {
        for (const r of L(this, wt, Kn).call(this, a))
          if (((i = r.canvasClear) == null ? void 0 : i.call(r)) ?? !1)
            return;
      }
    this.canvasClear();
  }
  destroy() {
    this.stop(), A(this, vi, null), v(this, $a).clear(), A(this, qs, []), A(this, Hs, []), A(this, Ls, []), A(this, _s, []), A(this, Ns, []), A(this, Us, []), A(this, js, []);
    for (const t of Object.values(Ye))
      typeof t == "number" && (v(this, Wa)[t] = []);
  }
  draw(t) {
    const i = v(this, Bs);
    if (i)
      return t(i);
  }
  drawParticle(t, i) {
    if (t.spawning || t.destroyed)
      return;
    const a = t.getRadius();
    if (a <= qR)
      return;
    const r = t.getFillColor(), u = t.getStrokeColor();
    let [c, f] = L(this, wt, EE).call(this, t);
    if (c ?? (c = r), f ?? (f = u), !c && !f)
      return;
    const m = v(this, bi), p = t.options.zIndex, g = gM - t.zIndexFactor, { fillOpacity: y, opacity: b, strokeOpacity: S } = t.getOpacity(), T = v(this, pd), C = v(this, md), R = c ? oc(c, m.hdr, y * b) : void 0, z = f ? oc(f, m.hdr, S * b) : R;
    T.a = T.b = T.c = T.d = void 0, C.fill = R, C.stroke = z, this.draw((B) => {
      var H, X;
      for (const Q of v(this, js))
        (H = Q.drawParticleSetup) == null || H.call(Q, B, t, i);
      L(this, wt, vE).call(this, B, t, a, b, C, T), L(this, wt, SE).call(this, {
        container: m,
        context: B,
        particle: t,
        delta: i,
        colorStyles: C,
        radius: a * g ** p.sizeRate,
        opacity: b,
        transform: T
      }), L(this, wt, yE).call(this, t);
      for (const Q of v(this, Us))
        (X = Q.drawParticleCleanup) == null || X.call(Q, B, t, i);
    });
  }
  drawParticlePlugins(t, i) {
    this.draw((a) => {
      for (const r of v(this, Ns))
        L(this, wt, wE).call(this, a, r, t, i);
    });
  }
  drawParticles(t) {
    const { particles: i, actualOptions: a } = v(this, bi);
    this.clear(), i.update(t), this.draw((r) => {
      var m, p, g, y, b;
      const u = v(this, sn).size.width, c = v(this, sn).size.height;
      if (v(this, vi))
        try {
          r.drawImage(v(this, vi), Dt.x, Dt.y, u, c);
        } catch {
          L(this, wt, Zu).call(this, "background-element-draw-error", "Error drawing background element onto canvas");
        }
      const f = a.background;
      if (f.draw)
        try {
          f.draw(r, t);
        } catch {
          L(this, wt, Zu).call(this, "background-draw-error", "Error in background.draw callback");
        }
      for (const S of L(this, wt, Kn).call(this, Ye.BackgroundMask))
        (m = S.canvasPaint) == null || m.call(S);
      for (const S of L(this, wt, Kn).call(this, Ye.CanvasSetup))
        (p = S.drawSettingsSetup) == null || p.call(S, r, t);
      for (const S of L(this, wt, Kn).call(this, Ye.PluginContent))
        (g = S.draw) == null || g.call(S, r, t);
      i.drawParticles(t);
      for (const S of L(this, wt, Kn).call(this, Ye.CanvasCleanup))
        (y = S.clearDraw) == null || y.call(S, r, t), (b = S.drawSettingsCleanup) == null || b.call(S, r, t);
    });
  }
  init() {
    this.initUpdaters(), this.initPlugins(), L(this, wt, AE).call(this), this.paint();
  }
  initPlugins() {
    A(this, Ls, []), A(this, _s, []), A(this, Ns, []), A(this, js, []), A(this, Us, []);
    for (const t of Object.values(Ye))
      typeof t == "number" && (v(this, Wa)[t] = []);
    for (const t of v(this, bi).plugins)
      (t.particleFillColor ?? t.particleStrokeColor) && v(this, _s).push(t), t.drawParticle && v(this, Ns).push(t), t.drawParticleSetup && v(this, js).push(t), t.drawParticleCleanup && v(this, Us).push(t), t.canvasClear && v(this, Ls).push(t), t.canvasPaint && L(this, wt, Kn).call(this, Ye.BackgroundMask).push(t), t.drawSettingsSetup && L(this, wt, Kn).call(this, Ye.CanvasSetup).push(t), t.draw && L(this, wt, Kn).call(this, Ye.PluginContent).push(t), (t.clearDraw ?? t.drawSettingsCleanup) && L(this, wt, Kn).call(this, Ye.CanvasCleanup).push(t);
  }
  initUpdaters() {
    A(this, qs, []), A(this, Hs, []);
    for (const t of v(this, bi).particleUpdaters)
      t.afterDraw && v(this, Hs).push(t), (t.getColorStyles ?? t.getTransformValues ?? t.beforeDraw) && v(this, qs).push(t);
  }
  paint() {
    var i;
    let t = !1;
    for (const a of L(this, wt, Kn).call(this, Ye.BackgroundMask))
      if (t = ((i = a.canvasPaint) == null ? void 0 : i.call(a)) ?? !1, t)
        break;
    t || this.paintBase();
  }
  paintBase(t) {
    this.draw((i) => {
      i.fillStyle = t ?? "rgba(0,0,0,0)", i.fillRect(Dt.x, Dt.y, v(this, sn).size.width, v(this, sn).size.height);
    });
  }
  paintImage(t, i) {
    this.draw((a) => {
      if (!t)
        return;
      const r = a.globalAlpha;
      a.globalAlpha = i, a.drawImage(t, Dt.x, Dt.y, v(this, sn).size.width, v(this, sn).size.height), a.globalAlpha = r;
    });
  }
  setContext(t) {
    A(this, Bs, t), v(this, Bs) && (v(this, Bs).globalCompositeOperation = dM);
  }
  setContextSettings(t) {
    A(this, Vc, t);
  }
  stop() {
    this.draw((t) => {
      t.clearRect(Dt.x, Dt.y, v(this, sn).size.width, v(this, sn).size.height);
    });
  }
}
vi = new WeakMap(), $a = new WeakMap(), Ls = new WeakMap(), sn = new WeakMap(), _s = new WeakMap(), bi = new WeakMap(), Bs = new WeakMap(), Vc = new WeakMap(), Ns = new WeakMap(), Us = new WeakMap(), js = new WeakMap(), Wa = new WeakMap(), ll = new WeakMap(), Hs = new WeakMap(), qs = new WeakMap(), md = new WeakMap(), ul = new WeakMap(), pd = new WeakMap(), wt = new WeakSet(), yE = function(t) {
  var i;
  for (const a of v(this, Hs))
    (i = a.afterDraw) == null || i.call(a, t);
}, vE = function(t, i, a, r, u, c) {
  var f;
  for (const m of v(this, qs)) {
    if (m.getColorStyles) {
      const { fill: p, stroke: g } = m.getColorStyles(i, t, a, r);
      p && (u.fill = p), g && (u.stroke = g);
    }
    if (m.getTransformValues) {
      const p = m.getTransformValues(i);
      for (const g in p)
        XB(c, p, g);
    }
    (f = m.beforeDraw) == null || f.call(m, i);
  }
}, bE = function(t, i) {
  if (!(t != null && t.drawAfter))
    return;
  const { particle: a } = i;
  a.effect && t.drawAfter(i);
}, xE = function(t, i) {
  if (!(t != null && t.drawBefore))
    return;
  const { particle: a } = i;
  a.effect && t.drawBefore(i);
}, SE = function(t) {
  var Q;
  const { container: i, context: a, particle: r, delta: u, colorStyles: c, radius: f, opacity: m, transform: p } = t, { effectDrawers: g, shapeDrawers: y } = i, b = r.getPosition(), S = r.getTransformData(p), T = wM, C = {
    x: b.x,
    y: b.y
  };
  a.setTransform(S.a, S.b, S.c, S.d, b.x, b.y), c.fill && (a.fillStyle = c.fill);
  const R = !!r.fillEnabled, z = r.strokeWidth ?? _S;
  a.lineWidth = z, c.stroke && (a.strokeStyle = c.stroke);
  const B = {
    context: a,
    particle: r,
    radius: f,
    drawRadius: f * T,
    opacity: m,
    delta: u,
    pixelRatio: i.retina.pixelRatio,
    fill: R,
    stroke: z > _S,
    transformData: S,
    position: { ...b },
    drawPosition: C,
    drawScale: T
  };
  for (const ut of i.plugins)
    (Q = ut.drawParticleTransform) == null || Q.call(ut, B);
  const H = r.effect ? g.get(r.effect) : void 0, X = r.shape ? y.get(r.shape) : void 0;
  L(this, wt, xE).call(this, H, B), L(this, wt, CE).call(this, X, B), L(this, wt, ME).call(this, X, B), L(this, wt, TE).call(this, X, B), L(this, wt, bE).call(this, H, B), a.resetTransform();
}, wE = function(t, i, a, r) {
  i.drawParticle && i.drawParticle(t, a, r);
}, ME = function(t, i) {
  if (!t)
    return;
  const { context: a, fill: r, particle: u, stroke: c } = i;
  u.shape && (a.beginPath(), t.draw(i), u.shapeClose && a.closePath(), r && a.fill(), c && a.stroke());
}, TE = function(t, i) {
  if (!(t != null && t.afterDraw))
    return;
  const { particle: a } = i;
  a.shape && t.afterDraw(i);
}, CE = function(t, i) {
  if (!(t != null && t.beforeDraw))
    return;
  const { particle: a } = i;
  a.shape && t.beforeDraw(i);
}, Kn = function(t) {
  return v(this, Wa)[t];
}, EE = function(t) {
  let i, a;
  for (const r of v(this, _s))
    if (!i && r.particleFillColor && (i = ac(v(this, ll), r.particleFillColor(t))), !a && r.particleStrokeColor && (a = ac(v(this, ll), r.particleStrokeColor(t))), i && a)
      break;
  return v(this, ul)[GB] = i, v(this, ul)[YB] = a, v(this, ul);
}, AE = function() {
  const t = v(this, bi).actualOptions.background;
  if (A(this, vi, null), !!t.element)
    if (typeof t.element == "string") {
      if (typeof document < "u") {
        const i = document.querySelector(t.element);
        i instanceof HTMLCanvasElement || i instanceof HTMLVideoElement || i instanceof HTMLImageElement ? A(this, vi, i) : i ? L(this, wt, Zu).call(this, "background-element-not-supported", `Background element "${t.element}" is not a supported drawable element (canvas, video, or img)`) : L(this, wt, Zu).call(this, "background-element-not-found", `Background element selector "${t.element}" not found`);
      }
    } else (t.element instanceof HTMLCanvasElement || t.element instanceof OffscreenCanvas || t.element instanceof HTMLVideoElement || t.element instanceof HTMLImageElement) && A(this, vi, t.element);
}, Zu = function(t, i) {
  v(this, $a).has(t) || (v(this, $a).add(t), zo().warning(i));
};
const tM = /* @__PURE__ */ new WeakMap(), ZB = (n) => {
  const t = tM.get(n);
  if (t)
    return t;
  if (typeof n.transferControlToOffscreen != "function")
    throw new TypeError("OffscreenCanvas is required but not supported by this browser");
  try {
    const i = n.transferControlToOffscreen();
    return tM.set(n, i), i;
  } catch {
    throw new TypeError("OffscreenCanvas transfer failed");
  }
}, QB = (n) => typeof HTMLCanvasElement < "u" && n instanceof HTMLCanvasElement;
function eM(n, t, i = !1) {
  if (!t)
    return;
  const a = n, r = a.style, u = /* @__PURE__ */ new Set();
  for (let c = 0; c < r.length; c++) {
    const f = r.item(c);
    f && u.add(f);
  }
  for (let c = 0; c < t.length; c++) {
    const f = t.item(c);
    f && u.add(f);
  }
  for (const c of u) {
    const f = t.getPropertyValue(c);
    f ? r.setProperty(c, f, i ? "important" : "") : r.removeProperty(c);
  }
}
var Xe, Ja, to, Pc, Lc, cl, Gs, eo, fl, te, DE, RE, OE, Ay, Dy, Ry, Rr, zE;
class KB {
  constructor(t, i) {
    k(this, te);
    w(this, "domElement");
    w(this, "render");
    w(this, "renderCanvas");
    w(this, "size");
    w(this, "zoom", wM);
    k(this, Xe);
    k(this, Ja);
    k(this, to);
    k(this, Pc);
    k(this, Lc);
    k(this, cl);
    k(this, Gs);
    k(this, eo);
    k(this, fl);
    A(this, Lc, t), A(this, Xe, i), this.render = new FB(t, i, this), A(this, eo, {
      height: 0,
      width: 0
    });
    const a = i.retina.pixelRatio, r = v(this, eo);
    this.size = {
      height: r.height * a,
      width: r.width * a
    }, A(this, Ja, !1), A(this, Gs, []), A(this, cl, "none");
  }
  destroy() {
    if (this.stop(), v(this, Ja)) {
      const t = this.domElement;
      t == null || t.remove(), this.domElement = void 0, this.renderCanvas = void 0;
    } else
      L(this, te, Ry).call(this);
    this.render.destroy(), A(this, Gs, []);
  }
  getZoomCenter() {
    const t = v(this, Xe).retina.pixelRatio, { width: i, height: a } = this.size;
    return v(this, fl) ? v(this, fl) : {
      x: i * bt / t,
      y: a * bt / t
    };
  }
  init() {
    L(this, te, Rr).call(this, (t) => {
      t.disconnect();
    }), A(this, to, p2((t) => {
      for (const i of t)
        i.type === "attributes" && i.attributeName === "style" && L(this, te, Dy).call(this);
    })), this.resize(), L(this, te, Ay).call(this), this.initBackground(), L(this, te, Rr).call(this, (t) => {
      const i = this.domElement;
      !i || !(i instanceof Node) || t.observe(i, { attributes: !0 });
    }), this.initPlugins(), L(this, te, OE).call(this), this.render.init();
  }
  initBackground() {
    const t = v(this, Xe), i = t.actualOptions, a = i.background, r = this.domElement;
    if (!r)
      return;
    const u = r.style, c = Vo(v(this, Lc), a.color);
    c ? u.backgroundColor = Qc(c, t.actualOptions.hdr, a.opacity) : u.backgroundColor = "", u.backgroundImage = a.image || "", u.backgroundPosition = a.position || "", u.backgroundRepeat = a.repeat || "", u.backgroundSize = a.size || "";
  }
  initPlugins() {
    A(this, Gs, []);
    for (const t of v(this, Xe).plugins)
      t.resize && v(this, Gs).push(t);
  }
  loadCanvas(t) {
    v(this, Ja) && this.domElement && this.domElement.remove();
    const i = QB(t) ? t : void 0;
    this.domElement = i, A(this, Ja, i ? i.dataset[Ds] === "true" : !1), this.renderCanvas = i ? ZB(i) : t;
    const a = this.domElement;
    a && (a.ariaHidden = "true", A(this, Pc, x2(a.style)));
    const r = v(this, eo), u = this.renderCanvas;
    a ? (r.height = a.offsetHeight, r.width = a.offsetWidth) : (r.height = u.height, r.width = u.width);
    const c = v(this, Xe).retina.pixelRatio, f = this.size;
    u.height = f.height = r.height * c, u.width = f.width = r.width * c;
  }
  resize() {
    const t = this.domElement;
    if (!t)
      return !1;
    const i = v(this, Xe), a = this.renderCanvas;
    if (a === void 0)
      return !1;
    const r = v(i.canvas, eo), u = {
      width: t.offsetWidth,
      height: t.offsetHeight
    }, c = i.retina.pixelRatio, f = {
      width: u.width * c,
      height: u.height * c
    };
    if (u.height === r.height && u.width === r.width && f.height === a.height && f.width === a.width)
      return !1;
    const m = { ...r };
    r.height = u.height, r.width = u.width;
    const p = this.size;
    return a.width = p.width = f.width, a.height = p.height = f.height, v(this, Xe).started && i.particles.setResizeFactor({
      width: r.width / m.width,
      height: r.height / m.height
    }), !0;
  }
  setPointerEvents(t) {
    this.domElement && (A(this, cl, t), L(this, te, Dy).call(this));
  }
  setZoom(t, i) {
    this.zoom = t, A(this, fl, i);
  }
  stop() {
    L(this, te, Rr).call(this, (t) => {
      t.disconnect();
    }), A(this, to, void 0), this.render.stop();
  }
  async windowResize() {
    if (!this.domElement || !this.resize())
      return;
    const t = v(this, Xe), i = t.updateActualOptions();
    t.particles.setDensity(), L(this, te, RE).call(this), i && await t.refresh();
  }
}
Xe = new WeakMap(), Ja = new WeakMap(), to = new WeakMap(), Pc = new WeakMap(), Lc = new WeakMap(), cl = new WeakMap(), Gs = new WeakMap(), eo = new WeakMap(), fl = new WeakMap(), te = new WeakSet(), DE = function() {
  return v(this, Xe).actualOptions.fullScreen.enable;
}, RE = function() {
  var t;
  for (const i of v(this, Gs))
    (t = i.resize) == null || t.call(i);
}, OE = function() {
  var r, u;
  const t = v(this, Xe), i = t.actualOptions.hdr && ((r = jS("(color-gamut: p3)")) == null ? void 0 : r.matches) && ((u = jS("(dynamic-range: high)")) == null ? void 0 : u.matches);
  this.render.setContextSettings({
    alpha: !0,
    desynchronized: !0,
    willReadFrequently: !1,
    ...i ? { colorSpace: "display-p3", colorType: "float16" } : { colorSpace: "srgb" }
  });
  const a = this.renderCanvas;
  a && this.render.setContext(a.getContext("2d", this.render.settings));
}, Ay = function() {
  const t = this.domElement, i = v(this, Xe).actualOptions;
  if (t) {
    v(this, te, DE) ? L(this, te, zE).call(this) : L(this, te, Ry).call(this);
    for (const a in i.style) {
      if (!a || !(a in i.style))
        continue;
      const r = i.style[a];
      r && t.style.setProperty(a, r, "important");
    }
  }
}, Dy = function() {
  const t = this.domElement;
  if (!t)
    return;
  L(this, te, Rr).call(this, (a) => {
    a.disconnect();
  }), L(this, te, Ay).call(this), this.initBackground();
  const i = v(this, cl);
  t.style.pointerEvents = i, t.style.setProperty("pointer-events", i), L(this, te, Rr).call(this, (a) => {
    t instanceof Node && a.observe(t, { attributes: !0 });
  });
}, Ry = function() {
  const t = this.domElement, i = v(this, Pc);
  !t || !i || eM(t, i, !0);
}, Rr = function(t) {
  v(this, to) && t(v(this, to));
}, zE = function() {
  const t = this.domElement;
  t && eM(t, S2(v(this, Xe).actualOptions.fullScreen.zIndex), !0);
};
var Ys, hl, xi, no, Hn, kE, Oy, zy, VE;
class IB {
  constructor(t) {
    k(this, Hn);
    k(this, Ys);
    k(this, hl);
    k(this, xi);
    k(this, no);
    A(this, Ys, t), A(this, hl, {
      visibilityChange: () => {
        L(this, Hn, kE).call(this);
      },
      resize: () => {
        L(this, Hn, Oy).call(this);
      }
    });
  }
  addListeners() {
    L(this, Hn, zy).call(this, !0);
  }
  removeListeners() {
    L(this, Hn, zy).call(this, !1);
  }
}
Ys = new WeakMap(), hl = new WeakMap(), xi = new WeakMap(), no = new WeakMap(), Hn = new WeakSet(), kE = function() {
  const t = v(this, Ys);
  t.actualOptions.pauseOnBlur && (Un().hidden ? (t.pageHidden = !0, t.pause()) : (t.pageHidden = !1, t.animationStatus ? t.play(!0) : t.draw(!0)));
}, Oy = function() {
  v(this, no) && (clearTimeout(v(this, no)), A(this, no, void 0));
  const t = async () => {
    await v(this, Ys).canvas.windowResize();
  };
  A(this, no, setTimeout(() => void t(), v(this, Ys).actualOptions.resize.delay * Ae));
}, zy = function(t) {
  const i = v(this, hl);
  L(this, Hn, VE).call(this, t), Ne(document, mM, i.visibilityChange, t, !1);
}, VE = function(t) {
  const i = v(this, hl), a = v(this, Ys);
  if (!a.actualOptions.resize.enable)
    return;
  if (typeof ResizeObserver > "u") {
    Ne(globalThis, PR, i.resize, t);
    return;
  }
  const u = a.canvas.domElement;
  v(this, xi) && !t ? (u && v(this, xi).unobserve(u), v(this, xi).disconnect(), A(this, xi, void 0)) : !v(this, xi) && t && u && (A(this, xi, new ResizeObserver((c) => {
    c.find((m) => m.target === u) && L(this, Hn, Oy).call(this);
  })), v(this, xi).observe(u));
};
function $B(n, t, i, a) {
  const r = t.options[n];
  return bn({
    close: t.close
  }, Vn(r, i, a));
}
function WB(n, t, i, a) {
  const r = t.options[n];
  return bn({
    close: t.close
  }, Vn(r, i, a));
}
function nM(n) {
  if (!Zt(n.outMode, n.checkModes))
    return;
  const t = n.radius * Bt;
  n.coord > n.maxCoord - t ? n.setCb(-n.radius) : n.coord < t && n.setCb(n.radius);
}
function Ng(n, t) {
  const i = n % t;
  return i < hi ? i + t : i;
}
function JB(n, t, i) {
  n.id = t, n.group = i, n.justWarped = !1, n.effectClose = !0, n.shapeClose = !0, n.pathRotation = !1, n.lastPathTime = 0, n.destroyed = !1, n.unbreakable = !1, n.isRotating = !1, n.rotation = 0, n.misplaced = !1, n.retina = {
    maxDistance: {},
    maxSpeed: 0,
    moveDrift: 0,
    moveSpeed: 0,
    sizeAnimationSpeed: 0
  }, n.size = {
    value: 1,
    max: 1,
    min: 1,
    enable: !1
  }, n.outType = ti.normal, n.ignoresResizeRatio = !0;
}
function t6(n, t, i, a) {
  const r = t.actualOptions, u = $y(i, t, r.particles), c = u.reduceDuplicates;
  n.effect = Vn(u.effect.type, n.id, c), n.shape = Vn(u.shape.type, n.id, c);
  const f = u.effect, m = u.shape;
  if (a) {
    if (a.effect) {
      const y = a.effect.type;
      if (y && y !== n.effect) {
        const b = Vn(y, n.id, c);
        b && (n.effect = b);
      }
      f.load(a.effect);
    }
    if (a.shape) {
      const y = a.shape.type;
      if (y && y !== n.shape) {
        const b = Vn(y, n.id, c);
        b && (n.shape = b);
      }
      m.load(a.shape);
    }
  }
  if (n.effect === Dl) {
    const y = [...t.effectDrawers.keys()];
    n.effect = y[Math.floor(Yt() * y.length)];
  }
  if (n.shape === Dl) {
    const y = [...t.shapeDrawers.keys()];
    n.shape = y[Math.floor(Yt() * y.length)];
  }
  n.effectData = n.effect ? $B(n.effect, f, n.id, c) : void 0, n.shapeData = n.shape ? WB(n.shape, m, n.id, c) : void 0, u.load(a);
  const p = n.effectData, g = n.shapeData;
  return p && u.load(p.particles), g && u.load(g.particles), n.effectClose = (p == null ? void 0 : p.close) ?? u.effect.close, n.shapeClose = (g == null ? void 0 : g.close) ?? u.shape.close, u;
}
function e6(n, t) {
  let i, a;
  n.effect && (i = t.effectDrawers.get(n.effect)), i != null && i.loadEffect && i.loadEffect(n), n.shape && (a = t.shapeDrawers.get(n.shape)), a != null && a.loadShape && a.loadShape(n);
  const r = a == null ? void 0 : a.getSidesCount;
  r && (n.sides = r(n));
}
function n6(n, t) {
  var i;
  for (const a of n)
    (i = a.preInit) == null || i.call(a, t);
}
function i6(n, t) {
  for (const i of n)
    i.init(t);
}
function s6(n, t) {
  var r, u;
  const i = t.shape ? n.shapeDrawers.get(t.shape) : void 0, a = t.effect ? n.effectDrawers.get(t.effect) : void 0;
  (r = a == null ? void 0 : a.particleInit) == null || r.call(a, n, t), (u = i == null ? void 0 : i.particleInit) == null || u.call(i, n, t);
}
function a6(n, t) {
  var i;
  for (const a of n.particleCreatedPlugins)
    (i = a.particleCreated) == null || i.call(a, t);
}
var io, so, dl, Xs, Ue, Si, _c, Vt, Qu, PE, LE, ky, Vy, _E, BE, Py, Ly, NE, _y;
class o6 {
  constructor(t, i) {
    k(this, Vt);
    w(this, "backColor");
    w(this, "destroyed");
    w(this, "direction");
    w(this, "effect");
    w(this, "effectClose");
    w(this, "effectData");
    w(this, "fillColor");
    w(this, "fillEnabled");
    w(this, "fillOpacity");
    w(this, "group");
    w(this, "id");
    w(this, "ignoresResizeRatio");
    w(this, "initialPosition");
    w(this, "initialVelocity");
    w(this, "isRotating");
    w(this, "justWarped");
    w(this, "lastPathTime");
    w(this, "misplaced");
    w(this, "moveCenter");
    w(this, "offset");
    w(this, "opacity");
    w(this, "options");
    w(this, "outType");
    w(this, "pathRotation");
    w(this, "position");
    w(this, "randomIndexData");
    w(this, "retina");
    w(this, "roll");
    w(this, "rotation");
    w(this, "shape");
    w(this, "shapeClose");
    w(this, "shapeData");
    w(this, "sides");
    w(this, "size");
    w(this, "spawning");
    w(this, "strokeColor");
    w(this, "strokeOpacity");
    w(this, "strokeWidth");
    w(this, "unbreakable");
    w(this, "velocity");
    w(this, "zIndexFactor");
    k(this, io, {
      fillOpacity: Di,
      opacity: Di,
      strokeOpacity: Di
    });
    k(this, so, Ba.origin);
    k(this, dl, { sin: 0, cos: 0 });
    k(this, Xs, {
      a: 1,
      b: 0,
      c: 0,
      d: 1
    });
    k(this, Ue);
    k(this, Si, []);
    k(this, _c);
    A(this, _c, t), A(this, Ue, i);
  }
  addModifier(t) {
    v(this, Si).push(t), v(this, Si).sort((i, a) => i.priority - a.priority);
  }
  clearModifiers() {
    v(this, Si).length = 0;
  }
  destroy(t) {
    var r, u, c;
    if (this.unbreakable || this.destroyed)
      return;
    this.destroyed = !0, this.clearModifiers();
    const i = v(this, Ue), a = this.shape ? i.shapeDrawers.get(this.shape) : void 0;
    (r = a == null ? void 0 : a.particleDestroy) == null || r.call(a, this);
    for (const f of i.particleDestroyedPlugins)
      (u = f.particleDestroyed) == null || u.call(f, this, t);
    for (const f of i.particleUpdaters)
      (c = f.particleDestroyed) == null || c.call(f, this, t);
    v(this, Ue).dispatchEvent(on.particleDestroyed, {
      particle: this
    });
  }
  draw(t) {
    const i = v(this, Ue), a = i.canvas.render;
    a.drawParticlePlugins(this, t), a.drawParticle(this, t);
  }
  getAngle() {
    return this.rotation + (this.pathRotation ? this.velocity.angle : hi);
  }
  getFillColor() {
    return L(this, Vt, Ly).call(this, L(this, Vt, Qu).call(this, XS(this.fillColor), (t) => t.fillColor));
  }
  getMass() {
    return this.getRadius() ** ra * Math.PI * bt;
  }
  getModifier(t) {
    return v(this, Si).find((i) => i.id === t);
  }
  getOpacity() {
    var p;
    const t = this.options.zIndex, i = gM - this.zIndexFactor, a = i ** t.opacityRate, r = ht(((p = this.opacity) == null ? void 0 : p.value) ?? Di), u = L(this, Vt, Qu).call(this, void 0, (g) => g.opacity), c = u ?? r, f = this.fillOpacity ?? Di, m = this.strokeOpacity ?? Di;
    return v(this, io).fillOpacity = c * f * a, v(this, io).opacity = c * a, v(this, io).strokeOpacity = c * m * a, v(this, io);
  }
  getPosition() {
    return v(this, so).x = this.position.x + this.offset.x, v(this, so).y = this.position.y + this.offset.y, v(this, so).z = this.position.z, v(this, so);
  }
  getRadius() {
    return L(this, Vt, Qu).call(this, this.size.value, (t) => t.radius);
  }
  getRotateData() {
    const t = this.getAngle();
    return v(this, dl).sin = Math.sin(t), v(this, dl).cos = Math.cos(t), v(this, dl);
  }
  getStrokeColor() {
    return L(this, Vt, Ly).call(this, L(this, Vt, Qu).call(this, XS(this.strokeColor), (t) => t.strokeColor));
  }
  getTransformData(t) {
    const i = this.getRotateData(), a = this.isRotating;
    return v(this, Xs).a = i.cos * (t.a ?? bh.a), v(this, Xs).b = a ? i.sin * (t.b ?? De) : t.b ?? bh.b, v(this, Xs).c = a ? -i.sin * (t.c ?? De) : t.c ?? bh.c, v(this, Xs).d = i.cos * (t.d ?? bh.d), v(this, Xs);
  }
  init(t, i, a, r) {
    const u = v(this, Ue);
    JB(this, t, r), this.options = t6(this, u, v(this, _c), a), u.retina.initParticle(this), n6(u.particleUpdaters, this), L(this, Vt, NE).call(this, i), this.initialVelocity = L(this, Vt, LE).call(this), this.velocity = this.initialVelocity.copy(), this.zIndexFactor = this.position.z / u.zLayers, this.sides = 24, e6(this, u), this.spawning = !1, i6(u.particleUpdaters, this), s6(u, this), a6(u, this);
  }
  isInsideCanvas(t) {
    return L(this, Vt, Py).call(this, { direction: t }).inside;
  }
  isInsideCanvasForOutMode(t, i) {
    return L(this, Vt, Py).call(this, { direction: i, outMode: t }).inside;
  }
  isShowingBack() {
    if (!this.roll)
      return !1;
    const t = this.roll.angle;
    if (this.roll.horizontal && this.roll.vertical) {
      const i = Ng(t, oa);
      return i >= Math.PI * bt && i < Math.PI * ic * bt;
    }
    if (this.roll.horizontal) {
      const i = Ng(t + Math.PI * bt, oa);
      return i >= Math.PI && i < Math.PI * Bt;
    }
    if (this.roll.vertical) {
      const i = Ng(t, oa);
      return i >= Math.PI && i < Math.PI * Bt;
    }
    return !1;
  }
  isVisible() {
    return !this.destroyed && !this.spawning && this.isInsideCanvas();
  }
  removeModifier(t) {
    const i = v(this, Si).findIndex((a) => a.id === t);
    i >= hi && v(this, Si).splice(i, De);
  }
  reset() {
    var t;
    for (const i of v(this, Ue).particleUpdaters)
      (t = i.reset) == null || t.call(i, this);
  }
}
io = new WeakMap(), so = new WeakMap(), dl = new WeakMap(), Xs = new WeakMap(), Ue = new WeakMap(), Si = new WeakMap(), _c = new WeakMap(), Vt = new WeakSet(), Qu = function(t, i) {
  let a = t;
  for (const r of v(this, Si))
    if (r.enabled) {
      const u = i(r);
      u !== void 0 && (a = u);
    }
  return a;
}, PE = function(t, i) {
  var g, y;
  let a = _R, r = t ? Ba.create(t.x, t.y, i) : void 0;
  const u = v(this, Ue), c = u.particlePositionPlugins, f = this.options.move.outModes, m = this.getRadius(), p = u.canvas.size;
  for (; ; ) {
    for (const C of c) {
      const R = (g = C.particlePosition) == null ? void 0 : g.call(C, r, this);
      if (R)
        return Ba.create(R.x, R.y, i);
    }
    const b = h2({
      size: p,
      position: r
    }), S = Ba.create(b.x, b.y, i);
    L(this, Vt, ky).call(this, S, m, f.left ?? f.default), L(this, Vt, ky).call(this, S, m, f.right ?? f.default), L(this, Vt, Vy).call(this, S, m, f.top ?? f.default), L(this, Vt, Vy).call(this, S, m, f.bottom ?? f.default);
    let T = !0;
    for (const C of u.particles.checkParticlePositionPlugins)
      if (T = ((y = C.checkParticlePosition) == null ? void 0 : y.call(C, this, S, a)) ?? !0, !T)
        break;
    if (T)
      return S;
    a += KR, r = void 0;
  }
}, LE = function() {
  const t = this.options.move, i = f2(this.direction), a = i.copy();
  if (t.direction === Pe.inside || t.direction === Pe.outside)
    return a;
  const r = So(ht(t.angle.value)), u = So(ht(t.angle.offset)), c = {
    left: u - r * bt,
    right: u + r * bt
  };
  return t.straight || (a.angle += Oi(Ro(c.left, c.right))), t.random && typeof t.speed == "number" && (a.length *= Yt()), a;
}, ky = function(t, i, a) {
  nM({
    outMode: a,
    checkModes: [he.bounce],
    coord: t.x,
    maxCoord: v(this, Ue).canvas.size.width,
    setCb: (r) => t.x += r,
    radius: i
  });
}, Vy = function(t, i, a) {
  nM({
    outMode: a,
    checkModes: [he.bounce],
    coord: t.y,
    maxCoord: v(this, Ue).canvas.size.height,
    setCb: (r) => t.y += r,
    radius: i
  });
}, _E = function(t, i) {
  const a = this.getRadius(), r = v(this, Ue).canvas.size, u = this.position, c = i === he.bounce;
  return t === Mt.bottom ? {
    inside: c ? u.y + a < r.height : u.y - a < r.height,
    reason: "default"
  } : t === Mt.left ? {
    inside: c ? u.x - a > hi : u.x + a > hi,
    reason: "default"
  } : t === Mt.right ? {
    inside: c ? u.x + a < r.width : u.x - a < r.width,
    reason: "default"
  } : t === Mt.top ? {
    inside: c ? u.y - a > hi : u.y + a > hi,
    reason: "default"
  } : {
    inside: u.x >= -a && u.y >= -a && u.y <= r.height + a && u.x <= r.width + a,
    reason: "default"
  };
}, BE = function(t, i) {
  return {
    canvasSize: v(this, Ue).canvas.size,
    direction: t,
    outMode: i,
    particle: this,
    radius: this.getRadius()
  };
}, Py = function(t) {
  const i = L(this, Vt, _E).call(this, t.direction, t.outMode), a = v(this, Ue), r = this.shape ? a.shapeDrawers.get(this.shape) : void 0, u = this.effect ? a.effectDrawers.get(this.effect) : void 0, c = r == null ? void 0 : r.isInsideCanvas, f = u == null ? void 0 : u.isInsideCanvas;
  if (!c && !f)
    return i;
  const m = L(this, Vt, BE).call(this, t.direction, t.outMode), p = c ? L(this, Vt, _y).call(this, c(m), "shape") : void 0, g = f ? L(this, Vt, _y).call(this, f(m), "effect") : void 0;
  if (p && g) {
    const y = Math.max(p.margin ?? hi, g.margin ?? hi);
    return {
      inside: p.inside && g.inside,
      margin: y > hi ? y : void 0,
      reason: "combined"
    };
  }
  return p ?? g ?? i;
}, Ly = function(t) {
  return !t || !this.roll || !this.backColor && !this.roll.alter || !this.isShowingBack() ? t : this.backColor ? this.backColor : this.roll.alter ? fO(t, this.roll.alter.type, this.roll.alter.value) : t;
}, NE = function(t) {
  const i = v(this, Ue), a = Math.floor(ht(this.options.zIndex.value)), r = L(this, Vt, PE).call(this, t, Nn(a, IR, i.zLayers));
  if (!r)
    throw new Error("a valid position cannot be found for particle");
  this.position = r, this.initialPosition = this.position.copy();
  const u = i.canvas.size;
  switch (this.moveCenter = {
    ...b2(this.options.move.center, u),
    radius: this.options.move.center.radius,
    mode: this.options.move.center.mode
  }, this.direction = c2(this.options.move.direction, this.position, this.moveCenter), this.options.move.direction) {
    case Pe.inside:
      this.outType = ti.inside;
      break;
    case Pe.outside:
      this.outType = ti.outside;
      break;
  }
  this.offset = Qe.origin;
}, _y = function(t, i) {
  return typeof t == "boolean" ? {
    inside: t,
    reason: i
  } : {
    inside: t.inside,
    margin: t.margin,
    reason: t.reason ?? i
  };
};
var $n, Fs, gd, ml, pl, yd, gl, xn, UE, jE, HE, qE, By;
class iM {
  constructor(t) {
    k(this, xn);
    k(this, $n);
    k(this, Fs, /* @__PURE__ */ new Map());
    k(this, gd, []);
    k(this, ml);
    k(this, pl);
    k(this, yd, []);
    k(this, gl);
    A(this, $n, t), A(this, ml, 0), A(this, gl, 0);
  }
  clear() {
    v(this, Fs).clear();
    const t = v(this, pl);
    t && A(this, $n, t), A(this, pl, void 0);
  }
  insert(t) {
    var u;
    const { x: i, y: a } = t.getPosition(), r = L(this, xn, HE).call(this, i, a);
    v(this, Fs).has(r) || v(this, Fs).set(r, []), (u = v(this, Fs).get(r)) == null || u.push(t);
  }
  query(t, i, a = []) {
    const r = L(this, xn, qE).call(this, t);
    if (!r)
      return a;
    const u = Math.floor(r.minX / v(this, $n)), c = Math.floor(r.maxX / v(this, $n)), f = Math.floor(r.minY / v(this, $n)), m = Math.floor(r.maxY / v(this, $n));
    for (let p = u; p <= c; p++)
      for (let g = f; g <= m; g++) {
        const y = `${p}_${g}`, b = v(this, Fs).get(y);
        if (b)
          for (const S of b)
            i && !i(S) || t.contains(S.getPosition()) && a.push(S);
      }
    return a;
  }
  queryCircle(t, i, a, r = []) {
    const u = L(this, xn, UE).call(this, t.x, t.y, i), c = this.query(u, a, r);
    return L(this, xn, By).call(this), c;
  }
  queryRectangle(t, i, a, r = []) {
    const u = L(this, xn, jE).call(this, t.x, t.y, i.width, i.height), c = this.query(u, a, r);
    return L(this, xn, By).call(this), c;
  }
  setCellSize(t) {
    A(this, pl, t);
  }
}
$n = new WeakMap(), Fs = new WeakMap(), gd = new WeakMap(), ml = new WeakMap(), pl = new WeakMap(), yd = new WeakMap(), gl = new WeakMap(), xn = new WeakSet(), UE = function(t, i, a) {
  var r, u;
  return ((r = v(this, gd))[u = vh(this, ml)._++] ?? (r[u] = new be(t, i, a))).reset(t, i, a);
}, jE = function(t, i, a, r) {
  var u, c;
  return ((u = v(this, yd))[c = vh(this, gl)._++] ?? (u[c] = new ni(t, i, a, r))).reset(t, i, a, r);
}, HE = function(t, i) {
  const a = Math.floor(t / v(this, $n)), r = Math.floor(i / v(this, $n));
  return `${a}_${r}`;
}, qE = function(t) {
  if (t instanceof be) {
    const i = t.radius, { x: a, y: r } = t.position;
    return {
      minX: a - i,
      maxX: a + i,
      minY: r - i,
      maxY: r + i
    };
  }
  if (t instanceof ni) {
    const { x: i, y: a } = t.position, { width: r, height: u } = t.size;
    return {
      minX: i,
      maxX: i + r,
      minY: a,
      maxY: a + u
    };
  }
  return null;
}, By = function() {
  A(this, ml, 0), A(this, gl, 0);
};
var je, ye, ao, Zs, yl, an, Qs, Ks, vl, Is, $s, Ws, bl, Js, Fe, Lt, GE, Ny, Uy, Kh, YE, jy, XE, FE, Hy, ZE, QE, KE;
class r6 {
  constructor(t, i) {
    k(this, Lt);
    w(this, "checkParticlePositionPlugins");
    w(this, "grid");
    k(this, je);
    k(this, ye);
    k(this, ao);
    k(this, Zs);
    k(this, yl);
    k(this, an);
    k(this, Qs);
    k(this, Ks);
    k(this, vl);
    k(this, Is);
    k(this, $s);
    k(this, Ws);
    k(this, bl);
    k(this, Js);
    k(this, Fe);
    A(this, vl, t), A(this, ye, i), A(this, yl, 0), A(this, je, []), A(this, Is, []), A(this, Zs, 0), A(this, ao, /* @__PURE__ */ new Map()), A(this, an, /* @__PURE__ */ new Map()), A(this, Fe, L(this, Lt, Uy).call(this, v(this, ye).zLayers)), this.grid = new iM(OS), this.checkParticlePositionPlugins = [], A(this, Qs, []), A(this, Ks, []), A(this, Ws, []), A(this, $s, []), A(this, Js, []);
  }
  get count() {
    return v(this, je).length;
  }
  addParticle(t, i, a, r) {
    const u = v(this, ye).actualOptions.particles.number.limit.mode, c = a === void 0 ? v(this, Zs) : v(this, ao).get(a) ?? v(this, Zs), f = this.count;
    if (c > PS)
      switch (u) {
        case sc.delete: {
          const m = f + $R - c;
          m > WR && this.removeQuantity(m);
          break;
        }
        case sc.wait:
          if (f >= c)
            return;
          break;
      }
    try {
      const m = v(this, Is).pop() ?? new o6(v(this, vl), v(this, ye));
      m.init(v(this, yl), t, i, a);
      let p = !0;
      if (r && (p = r(m)), !p) {
        v(this, Is).push(m);
        return;
      }
      return v(this, je).push(m), L(this, Lt, jy).call(this, m), vh(this, yl)._++, v(this, ye).dispatchEvent(on.particleAdded, {
        particle: m
      }), m;
    } catch (m) {
      zo().warning(`error adding particle: ${m}`);
    }
  }
  clear() {
    A(this, je, []), v(this, an).clear(), L(this, Lt, Hy).call(this, v(this, ye).zLayers);
  }
  destroy() {
    A(this, je, []), v(this, Is).length = 0, v(this, an).clear(), A(this, Fe, []), this.checkParticlePositionPlugins = [], A(this, Qs, []), A(this, Ks, []), A(this, Ws, []), A(this, $s, []), A(this, Js, []);
  }
  drawParticles(t) {
    for (let i = v(this, Fe).length - qu; i >= fi; i--) {
      const a = v(this, Fe)[i];
      if (a)
        for (const r of a)
          r.draw(t);
    }
  }
  filter(t) {
    return v(this, je).filter(t);
  }
  find(t) {
    return v(this, je).find(t);
  }
  get(t) {
    return v(this, je)[t];
  }
  async init() {
    var r, u, c;
    const t = v(this, ye), i = t.actualOptions;
    this.checkParticlePositionPlugins = [], A(this, Js, []), A(this, Ks, []), A(this, Ws, []), A(this, Qs, []), A(this, $s, []), v(this, an).clear(), L(this, Lt, Hy).call(this, t.zLayers), this.grid = new iM(OS * t.retina.pixelRatio);
    for (const f of t.plugins)
      f.redrawInit && await f.redrawInit(), f.checkParticlePosition && this.checkParticlePositionPlugins.push(f), f.update && v(this, Js).push(f), f.particleUpdate && v(this, Ks).push(f), f.postUpdate && v(this, Ws).push(f), f.particleReset && v(this, Qs).push(f), f.postParticleUpdate && v(this, $s).push(f);
    await v(this, ye).initDrawersAndUpdaters();
    for (const f of v(this, ye).effectDrawers.values())
      await ((r = f.init) == null ? void 0 : r.call(f, t));
    for (const f of v(this, ye).shapeDrawers.values())
      await ((u = f.init) == null ? void 0 : u.call(f, t));
    let a = !1;
    for (const f of t.plugins)
      if (a = ((c = f.particlesInitialization) == null ? void 0 : c.call(f)) ?? a, a)
        break;
    if (!a) {
      const f = i.particles, m = f.groups;
      for (const p in m) {
        const g = m[p];
        if (g)
          for (let y = this.count, b = 0; b < g.number.value && y < f.number.value; y++, b++)
            this.addParticle(void 0, g, p);
      }
      for (let p = this.count; p < f.number.value; p++)
        this.addParticle();
    }
  }
  push(t, i, a, r) {
    for (let u = 0; u < t; u++)
      this.addParticle(i, a, r);
  }
  async redraw() {
    this.clear(), await this.init(), v(this, ye).canvas.render.drawParticles({ value: 0, factor: 0 });
  }
  remove(t, i, a) {
    this.removeAt(v(this, je).indexOf(t), void 0, i, a);
  }
  removeAt(t, i = BR, a, r) {
    if (t < fi || t > this.count)
      return;
    let u = 0;
    for (let c = t; u < i && c < this.count; c++)
      L(this, Lt, XE).call(this, c, a, r) && (c--, u++);
  }
  removeQuantity(t, i) {
    this.removeAt(fi, t, i);
  }
  setDensity() {
    const t = v(this, ye).actualOptions, i = t.particles.groups;
    let a = 0;
    for (const r of v(this, ye).plugins)
      r.particlesDensityCount && (a += r.particlesDensityCount());
    for (const r in i) {
      const u = i[r];
      if (!u)
        continue;
      const c = $y(v(this, vl), v(this, ye), u);
      L(this, Lt, Ny).call(this, c, a, r);
    }
    L(this, Lt, Ny).call(this, t.particles, a);
  }
  setResizeFactor(t) {
    A(this, bl, t);
  }
  update(t) {
    var a, r;
    this.grid.clear();
    for (const u of v(this, Js))
      (a = u.update) == null || a.call(u, t);
    const i = L(this, Lt, QE).call(this, t);
    for (const u of v(this, Ws))
      (r = u.postUpdate) == null || r.call(u, t);
    if (L(this, Lt, KE).call(this, t, i), i.size)
      for (const u of i)
        this.remove(u);
    A(this, bl, void 0);
  }
}
je = new WeakMap(), ye = new WeakMap(), ao = new WeakMap(), Zs = new WeakMap(), yl = new WeakMap(), an = new WeakMap(), Qs = new WeakMap(), Ks = new WeakMap(), vl = new WeakMap(), Is = new WeakMap(), $s = new WeakMap(), Ws = new WeakMap(), bl = new WeakMap(), Js = new WeakMap(), Fe = new WeakMap(), Lt = new WeakSet(), GE = function(...t) {
  v(this, Is).push(...t);
}, Ny = function(t, i, a, r) {
  const u = t.number;
  if (!u.density.enable) {
    a === void 0 ? A(this, Zs, u.limit.value) : ((r == null ? void 0 : r.number.limit.value) ?? u.limit.value) && v(this, ao).set(a, (r == null ? void 0 : r.number.limit.value) ?? u.limit.value);
    return;
  }
  const c = L(this, Lt, YE).call(this, u.density), f = u.value, m = u.limit.value > PS ? u.limit.value : f, p = Math.min(f, m) * c + i, g = Math.min(this.count, this.filter((y) => y.group === a).length);
  a === void 0 ? A(this, Zs, u.limit.value * c) : v(this, ao).set(a, u.limit.value * c), g < p ? this.push(Math.abs(p - g), void 0, t, a) : g > p && this.removeQuantity(g - p, a);
}, Uy = function(t) {
  const i = Math.max(Math.floor(t), qu);
  return Array.from({ length: i }, () => []);
}, Kh = function(t) {
  const i = v(this, Fe).length - qu;
  return i <= fi ? fi : Math.min(Math.max(Math.floor(t), fi), i);
}, YE = function(t) {
  const i = v(this, ye);
  if (!t.enable)
    return LS;
  const a = i.canvas.size, r = i.retina.pixelRatio;
  return !a.width || !a.height ? LS : a.width * a.height / (t.height * t.width * r ** ra);
}, jy = function(t) {
  const i = L(this, Lt, Kh).call(this, t.position.z), a = v(this, Fe)[i];
  a && (a.push(t), v(this, an).set(t.id, i));
}, XE = function(t, i, a) {
  const r = v(this, je)[t];
  return !r || r.group !== i ? !1 : (v(this, je).splice(t, Iu), L(this, Lt, FE).call(this, r), r.destroy(a), v(this, ye).dispatchEvent(on.particleRemoved, {
    particle: r
  }), L(this, Lt, GE).call(this, r), !0);
}, FE = function(t) {
  const i = v(this, an).get(t.id) ?? L(this, Lt, Kh).call(this, t.position.z), a = v(this, Fe)[i];
  if (!a) {
    v(this, an).delete(t.id);
    return;
  }
  const r = a.findIndex((u) => u.id === t.id);
  r >= fi && a.splice(r, Iu), v(this, an).delete(t.id);
}, Hy = function(t) {
  const i = Math.max(Math.floor(t), qu);
  if (v(this, Fe).length !== i) {
    A(this, Fe, L(this, Lt, Uy).call(this, i));
    return;
  }
  for (const a of v(this, Fe))
    a.length = fi;
}, ZE = function(t) {
  const i = L(this, Lt, Kh).call(this, t.position.z), a = v(this, an).get(t.id);
  if (a === void 0) {
    L(this, Lt, jy).call(this, t);
    return;
  }
  if (a === i)
    return;
  const r = v(this, Fe)[a];
  if (r) {
    const c = r.findIndex((f) => f.id === t.id);
    c >= fi && r.splice(c, Iu);
  }
  const u = v(this, Fe)[i];
  if (!u) {
    v(this, an).set(t.id, i);
    return;
  }
  if (u.push(t), u.length >= Bt) {
    const c = u[u.length - Bt];
    c && t.id < c.id && u.sort((f, m) => f.id - m.id);
  }
  v(this, an).set(t.id, i);
}, QE = function(t) {
  var r, u;
  const i = /* @__PURE__ */ new Set(), a = v(this, bl);
  for (const c of v(this, je)) {
    a && !c.ignoresResizeRatio && (c.position.x *= a.width, c.position.y *= a.height, c.initialPosition.x *= a.width, c.initialPosition.y *= a.height), c.ignoresResizeRatio = !1;
    for (const f of v(this, Qs))
      (r = f.particleReset) == null || r.call(f, c);
    for (const f of v(this, Ks)) {
      if (c.destroyed)
        break;
      (u = f.particleUpdate) == null || u.call(f, c, t);
    }
    if (c.destroyed) {
      i.add(c);
      continue;
    }
    this.grid.insert(c);
  }
  return i;
}, KE = function(t, i) {
  var a;
  for (const r of v(this, je)) {
    if (r.destroyed) {
      i.add(r);
      continue;
    }
    for (const u of v(this, ye).particleUpdaters)
      u.update(r, t);
    if (!r.spawning)
      for (const u of v(this, $s))
        (a = u.postParticleUpdate) == null || a.call(u, r, t);
    L(this, Lt, ZE).call(this, r);
  }
};
var Bc;
class l6 {
  constructor(t) {
    w(this, "pixelRatio");
    w(this, "reduceFactor");
    k(this, Bc);
    A(this, Bc, t), this.pixelRatio = jg, this.reduceFactor = zS;
  }
  init() {
    const t = v(this, Bc), i = t.actualOptions;
    this.pixelRatio = i.detectRetina ? devicePixelRatio : jg, this.reduceFactor = zS;
    const a = this.pixelRatio, r = t.canvas, u = r.domElement;
    u && (r.size.width = u.offsetWidth * a, r.size.height = u.offsetHeight * a);
  }
  initParticle(t) {
    const i = t.options, a = this.pixelRatio, r = i.move, u = r.distance, c = t.retina;
    c.maxSpeed = ht(r.gravity.maxSpeed) * a, c.moveDrift = ht(r.drift) * a, c.moveSpeed = ht(r.speed) * a;
    const f = c.maxDistance;
    f.horizontal = u.horizontal === void 0 ? void 0 : u.horizontal * a, f.vertical = u.vertical === void 0 ? void 0 : u.vertical * a;
  }
}
Bc = new WeakMap();
function ci(n) {
  return !n.destroyed;
}
function u6(n, t, i = $p, a = !1) {
  n.value = t, n.factor = a ? $p / i : $p * t / Ae;
}
function Ar(n, t, ...i) {
  const a = new W2(n, t);
  return zM(a, ...i), a;
}
var xl, oo, ro, Nc, lo, uo, Sl, co, fo, wi, ho, Uc, Mi, Ti, Ze, mo, po, vd, IE;
class c6 {
  constructor(t) {
    k(this, vd);
    w(this, "actualOptions");
    w(this, "canvas");
    w(this, "destroyed");
    w(this, "effectDrawers");
    w(this, "fpsLimit");
    w(this, "hdr");
    w(this, "id");
    w(this, "pageHidden");
    w(this, "particleCreatedPlugins");
    w(this, "particleDestroyedPlugins");
    w(this, "particlePositionPlugins");
    w(this, "particleUpdaters");
    w(this, "particles");
    w(this, "plugins");
    w(this, "retina");
    w(this, "shapeDrawers");
    w(this, "started");
    w(this, "zLayers");
    k(this, xl);
    k(this, oo);
    k(this, ro, { value: 0, factor: 0 });
    k(this, Nc);
    k(this, lo);
    k(this, uo);
    k(this, Sl);
    k(this, co);
    k(this, fo);
    k(this, wi);
    k(this, ho);
    k(this, Uc);
    k(this, Mi);
    k(this, Ti);
    k(this, Ze);
    k(this, mo);
    k(this, po);
    const { dispatchCallback: i, pluginManager: a, id: r, onDestroy: u, sourceOptions: c } = t;
    A(this, Ze, a), A(this, Nc, i), A(this, Uc, u), this.id = Symbol(r), this.fpsLimit = 120, this.hdr = !1, A(this, mo, !1), A(this, xl, 0), A(this, uo, 0), A(this, ho, 0), A(this, co, !0), this.started = !1, this.destroyed = !1, A(this, Ti, !0), A(this, wi, 0), this.zLayers = 100, this.pageHidden = !1, A(this, po, c), A(this, fo, c), this.effectDrawers = /* @__PURE__ */ new Map(), this.shapeDrawers = /* @__PURE__ */ new Map(), this.particleUpdaters = [], this.retina = new l6(this), this.canvas = new KB(v(this, Ze), this), this.particles = new r6(v(this, Ze), this), this.plugins = [], this.particleDestroyedPlugins = [], this.particleCreatedPlugins = [], this.particlePositionPlugins = [], A(this, Mi, Ar(v(this, Ze), this)), this.actualOptions = Ar(v(this, Ze), this), A(this, Sl, new IB(this)), this.dispatchEvent(on.containerBuilt);
  }
  get animationStatus() {
    return !v(this, Ti) && !this.pageHidden && ci(this);
  }
  get options() {
    return v(this, Mi);
  }
  get sourceOptions() {
    return v(this, po);
  }
  addLifeTime(t) {
    A(this, ho, v(this, ho) + t);
  }
  alive() {
    return !v(this, uo) || v(this, ho) <= v(this, uo);
  }
  destroy(t = !0) {
    var i, a, r;
    if (ci(this)) {
      this.stop(), this.particles.destroy(), this.canvas.destroy();
      for (const [, u] of this.effectDrawers)
        (i = u.destroy) == null || i.call(u, this);
      for (const [, u] of this.shapeDrawers)
        (a = u.destroy) == null || a.call(u, this);
      for (const u of this.plugins)
        (r = u.destroy) == null || r.call(u);
      this.effectDrawers = /* @__PURE__ */ new Map(), this.shapeDrawers = /* @__PURE__ */ new Map(), this.particleUpdaters = [], this.plugins.length = 0, v(this, Ze).clearPlugins(this), this.destroyed = !0, v(this, Uc).call(this, t), this.dispatchEvent(on.containerDestroyed);
    }
  }
  dispatchEvent(t, i) {
    v(this, Nc).call(this, t, {
      container: this,
      data: i
    });
  }
  draw(t) {
    if (!ci(this))
      return;
    let i = t;
    A(this, lo, r2((a) => {
      i && (A(this, wi, void 0), i = !1), L(this, vd, IE).call(this, a);
    }));
  }
  async export(t, i = {}) {
    for (const a of this.plugins) {
      if (!a.export)
        continue;
      const r = await a.export(t, i);
      if (r.supported)
        return r.blob;
    }
    zo().error(`Export plugin with type ${t} not found`);
  }
  async init() {
    var m, p;
    if (!ci(this))
      return;
    const t = /* @__PURE__ */ new Map();
    for (const g of v(this, Ze).plugins) {
      const y = await g.getPlugin(this);
      y.preInit && await y.preInit(), t.set(g, y);
    }
    await this.initDrawersAndUpdaters(), A(this, Mi, Ar(v(this, Ze), this, v(this, fo), this.sourceOptions)), this.actualOptions = Ar(v(this, Ze), this, v(this, Mi)), this.plugins.length = 0, this.particleDestroyedPlugins.length = 0, this.particleCreatedPlugins.length = 0, this.particlePositionPlugins.length = 0;
    for (const [g, y] of t)
      g.needsPlugin(this.actualOptions) && (this.plugins.push(y), y.particleCreated && this.particleCreatedPlugins.push(y), y.particleDestroyed && this.particleDestroyedPlugins.push(y), y.particlePosition && this.particlePositionPlugins.push(y));
    this.retina.init(), this.canvas.init(), this.updateActualOptions(), this.canvas.initBackground(), this.canvas.resize();
    const { delay: i, duration: a, fpsLimit: r, hdr: u, smooth: c, zLayers: f } = this.actualOptions;
    this.hdr = u, this.zLayers = f, A(this, uo, ht(a) * Ae), A(this, xl, ht(i) * Ae), A(this, ho, 0), this.fpsLimit = r > XR ? r : YR, A(this, mo, c);
    for (const g of this.plugins)
      await ((m = g.init) == null ? void 0 : m.call(g));
    await this.particles.init(), this.dispatchEvent(on.containerInit), this.particles.setDensity();
    for (const g of this.plugins)
      (p = g.particlesSetup) == null || p.call(g);
    this.dispatchEvent(on.particlesSetup);
  }
  async initDrawersAndUpdaters() {
    const t = v(this, Ze);
    this.effectDrawers = await t.getEffectDrawers(this, !0), this.shapeDrawers = await t.getShapeDrawers(this, !0), this.particleUpdaters = await t.getUpdaters(this, !0);
  }
  pause() {
    var t;
    if (ci(this) && (v(this, lo) !== void 0 && (l2(v(this, lo)), A(this, lo, void 0)), !v(this, Ti))) {
      for (const i of this.plugins)
        (t = i.pause) == null || t.call(i);
      this.pageHidden || A(this, Ti, !0), this.dispatchEvent(on.containerPaused);
    }
  }
  play(t) {
    if (!ci(this))
      return;
    const i = v(this, Ti) || t;
    if (v(this, co) && !this.actualOptions.autoPlay) {
      A(this, co, !1);
      return;
    }
    if (v(this, Ti) && A(this, Ti, !1), i)
      for (const a of this.plugins)
        a.play && a.play();
    this.dispatchEvent(on.containerPlay), this.draw(i ?? !1);
  }
  async refresh() {
    if (ci(this))
      return this.stop(), this.start();
  }
  async reset(t) {
    if (ci(this))
      return A(this, fo, t), A(this, po, t), A(this, Mi, Ar(v(this, Ze), this, v(this, fo), this.sourceOptions)), this.actualOptions = Ar(v(this, Ze), this, v(this, Mi)), this.refresh();
  }
  async start() {
    !ci(this) || this.started || (await this.init(), this.started = !0, await new Promise((t) => {
      const i = async () => {
        var a;
        v(this, Sl).addListeners();
        for (const r of this.plugins)
          await ((a = r.start) == null ? void 0 : a.call(r));
        this.dispatchEvent(on.containerStarted), this.play(), t();
      };
      A(this, oo, setTimeout(() => void i(), v(this, xl)));
    }));
  }
  stop() {
    var t;
    if (!(!ci(this) || !this.started)) {
      v(this, oo) && (clearTimeout(v(this, oo)), A(this, oo, void 0)), A(this, co, !0), this.started = !1, v(this, Sl).removeListeners(), this.pause(), this.particles.clear(), this.canvas.stop();
      for (const i of this.plugins)
        (t = i.stop) == null || t.call(i);
      this.particleCreatedPlugins.length = 0, this.particleDestroyedPlugins.length = 0, this.particlePositionPlugins.length = 0, A(this, po, v(this, Mi)), this.dispatchEvent(on.containerStopped);
    }
  }
  updateActualOptions() {
    let t = !1;
    for (const i of this.plugins)
      i.updateActualOptions && (t = i.updateActualOptions() || t);
    return t;
  }
}
xl = new WeakMap(), oo = new WeakMap(), ro = new WeakMap(), Nc = new WeakMap(), lo = new WeakMap(), uo = new WeakMap(), Sl = new WeakMap(), co = new WeakMap(), fo = new WeakMap(), wi = new WeakMap(), ho = new WeakMap(), Uc = new WeakMap(), Mi = new WeakMap(), Ti = new WeakMap(), Ze = new WeakMap(), mo = new WeakMap(), po = new WeakMap(), vd = new WeakSet(), IE = function(t) {
  try {
    if (!v(this, mo) && v(this, wi) !== void 0 && t < v(this, wi) + Ae / this.fpsLimit) {
      this.draw(!1);
      return;
    }
    if (v(this, wi) ?? A(this, wi, t), u6(v(this, ro), t - v(this, wi), this.fpsLimit, v(this, mo)), this.addLifeTime(v(this, ro).value), A(this, wi, t), v(this, ro).value > Ae) {
      this.draw(!1);
      return;
    }
    if (this.canvas.render.drawParticles(v(this, ro)), !this.alive()) {
      this.destroy();
      return;
    }
    this.animationStatus && this.draw(!1);
  } catch (i) {
    zo().error("error in animation loop", i);
  }
};
const f6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  Container: c6
}, Symbol.toStringTag, { value: "Module" }));
var jc, wl;
class h6 {
  constructor(t) {
    w(this, "layer", Ye.CanvasSetup);
    k(this, jc);
    k(this, wl);
    A(this, jc, t);
  }
  drawParticleCleanup(t, i) {
    var a;
    (a = i.options.blend) != null && a.enable && (t.globalCompositeOperation = i.originalBlendMode ?? dM, i.originalBlendMode = void 0);
  }
  drawParticleSetup(t, i) {
    var a;
    (a = i.options.blend) != null && a.enable && (i.originalBlendMode = t.globalCompositeOperation, t.globalCompositeOperation = i.options.blend.mode);
  }
  drawSettingsCleanup(t) {
    v(this, wl) && (t.globalCompositeOperation = v(this, wl));
  }
  drawSettingsSetup(t) {
    const i = t.globalCompositeOperation, a = v(this, jc).actualOptions.blend;
    A(this, wl, i), t.globalCompositeOperation = a != null && a.enable ? a.mode : i;
  }
}
jc = new WeakMap(), wl = new WeakMap();
const d6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  BlendPluginInstance: h6
}, Symbol.toStringTag, { value: "Module" })), sM = 60, aM = 0, m6 = 0.01, p6 = 0, g6 = 1;
function y6(n) {
  const t = n.initialPosition, { dx: i, dy: a } = _n(t, n.position), r = Math.abs(i), u = Math.abs(a), { maxDistance: c } = n.retina, f = c.horizontal, m = c.vertical;
  if (!f && !m)
    return;
  const p = (f && r >= f) ?? !1, g = (m && u >= m) ?? !1;
  if ((p || g) && !n.misplaced)
    n.misplaced = !!f && r > f || !!m && u > m, f && (n.velocity.x = n.velocity.y * bt - n.velocity.x), m && (n.velocity.y = n.velocity.x * bt - n.velocity.y);
  else if ((!f || r < f) && (!m || u < m) && n.misplaced)
    n.misplaced = !1;
  else if (n.misplaced) {
    const y = n.position, b = n.velocity;
    f && (y.x < t.x && b.x < Wt || y.x > t.x && b.x > Wt) && (b.x *= -Yt()), m && (y.y < t.y && b.y < Wt || y.y > t.y && b.y > Wt) && (b.y *= -Yt());
  }
}
function v6(n, t, i, a, r, u, c) {
  x6(n, c);
  const f = n.gravity, m = f != null && f.enable && f.inverse ? -De : De;
  r && i && (n.velocity.x += r * c.factor / (sM * i)), f != null && f.enable && i && (n.velocity.y += m * (f.acceleration * c.factor) / (sM * i));
  const p = n.moveDecay;
  n.velocity.multTo(p ?? g6);
  const g = n.velocity.mult(i);
  f != null && f.enable && a > Wt && (!f.inverse && g.y >= Wt && g.y >= a || f.inverse && g.y <= Wt && g.y <= -a) && (g.y = m * a, i && (n.velocity.y = g.y / i));
  const y = n.options.zIndex, b = (De - n.zIndexFactor) ** y.velocityRate;
  g.multTo(b), g.multTo(u);
  const { position: S } = n;
  S.addTo(g), t.vibrate && (S.x += Math.sin(S.x * Math.cos(S.y)) * u, S.y += Math.cos(S.y * Math.sin(S.x)) * u);
}
function b6(n, t, i, a) {
  if (!t.spin)
    return;
  const r = t.spin.direction === Jn.clockwise, u = {
    x: r ? Math.cos : Math.sin,
    y: r ? Math.sin : Math.cos
  };
  t.position.x = t.spin.center.x + t.spin.radius * u.x(t.spin.angle) * a, t.position.y = t.spin.center.y + t.spin.radius * u.y(t.spin.angle) * a, t.spin.radius += t.spin.acceleration * a;
  const c = Math.max(n.canvas.size.width, n.canvas.size.height), f = c * bt;
  t.spin.radius > f ? (t.spin.radius = f, t.spin.acceleration *= -De) : t.spin.radius < aM && (t.spin.radius = aM, t.spin.acceleration *= -De), t.spin.angle += i * m6 * (De - t.spin.radius / c);
}
function x6(n, t) {
  var f;
  const i = n.options, a = i.move.path;
  if (!a.enable)
    return;
  const u = n.pathDelay ?? p6;
  if (n.lastPathTime <= u) {
    n.lastPathTime += t.value;
    return;
  }
  const c = (f = n.pathGenerator) == null ? void 0 : f.generate(n, t);
  c && n.velocity.addTo(c), a.clamp && (n.velocity.x = Nn(n.velocity.x, -De, De), n.velocity.y = Nn(n.velocity.y, -De, De)), n.lastPathTime -= u;
}
function S6(n) {
  const t = n.getModifier("slow");
  return t != null && t.enabled ? t.speedFactor ?? De : De;
}
function w6(n, t) {
  const i = t.options, a = i.move.spin;
  if (!a.enable)
    return;
  const r = a.position ?? { x: 50, y: 50 }, u = 0.01, c = {
    x: r.x * u * n.canvas.size.width,
    y: r.y * u * n.canvas.size.height
  }, f = t.getPosition(), m = Oo(f, c), p = ht(a.acceleration);
  t.retina.spinAcceleration = p * n.retina.pixelRatio, t.spin = {
    center: c,
    direction: t.velocity.x >= Wt ? Jn.clockwise : Jn.counterClockwise,
    angle: Yt() * oa,
    radius: m,
    acceleration: t.retina.spinAcceleration
  };
}
const M6 = 1, T6 = 1;
var go, Hc, qc, qy;
class C6 {
  constructor(t, i) {
    k(this, qc);
    w(this, "availablePathGenerators");
    w(this, "pathGenerators");
    k(this, go);
    k(this, Hc);
    A(this, Hc, t), A(this, go, i), this.availablePathGenerators = /* @__PURE__ */ new Map(), this.pathGenerators = /* @__PURE__ */ new Map();
  }
  destroy() {
    this.availablePathGenerators = /* @__PURE__ */ new Map(), this.pathGenerators = /* @__PURE__ */ new Map();
  }
  isEnabled(t) {
    return !t.destroyed && t.options.move.enable;
  }
  particleCreated(t) {
    const i = t.options, a = i.move, r = a.gravity, u = a.path;
    if (t.moveDecay = vM - ht(a.decay), t.pathDelay = ht(u.delay.value) * Ae, u.generator) {
      let c = this.pathGenerators.get(u.generator);
      c || (c = this.availablePathGenerators.get(u.generator), c && (this.pathGenerators.set(u.generator, c), c.init())), t.pathGenerator = c;
    }
    t.gravity = {
      enable: r.enable,
      acceleration: ht(r.acceleration),
      inverse: r.inverse
    }, w6(v(this, go), t);
  }
  particleDestroyed(t) {
    const i = t.pathGenerator;
    i == null || i.reset(t);
  }
  particleUpdate(t, i) {
    const a = t.options, r = a.move;
    if (!r.enable)
      return;
    const u = v(this, go), c = S6(t), f = u.retina.reduceFactor, m = t.retina.moveSpeed, p = t.retina.moveDrift, g = t.size.max, y = r.size ? t.getRadius() / g : M6, b = i.factor || T6, S = m * y * c * b * bt, T = t.retina.maxSpeed;
    r.spin.enable ? b6(u, t, S, f) : v6(t, r, S, T, p, f, i), y6(t);
  }
  preInit() {
    return L(this, qc, qy).call(this);
  }
  redrawInit() {
    return L(this, qc, qy).call(this);
  }
  update() {
    for (const t of this.pathGenerators.values())
      t.update();
  }
}
go = new WeakMap(), Hc = new WeakMap(), qc = new WeakSet(), qy = async function() {
  var i, a;
  const t = await ((a = (i = v(this, Hc)).getPathGenerators) == null ? void 0 : a.call(i, v(this, go), !0));
  if (t) {
    this.availablePathGenerators = t, this.pathGenerators = /* @__PURE__ */ new Map();
    for (const r of this.pathGenerators.values())
      r.init();
  }
};
const E6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  MovePluginInstance: C6
}, Symbol.toStringTag, { value: "Module" })), A6 = 500;
var Ml, yo, Ci, Tl, Wn, vo, Pt, $E, WE, JE, Gy, tA, Yy, Ku, Ih, Xy, eA, nA;
class D6 {
  constructor(t, i) {
    k(this, Pt);
    k(this, Ml, !0);
    k(this, yo);
    k(this, Ci);
    k(this, Tl);
    k(this, Wn);
    k(this, vo);
    A(this, Ci, t), A(this, yo, []), A(this, Wn, i), A(this, vo, /* @__PURE__ */ new Map()), A(this, Tl, {
      mouseDown: () => {
        L(this, Pt, tA).call(this);
      },
      mouseLeave: () => {
        L(this, Pt, Ku).call(this);
      },
      mouseMove: (a) => {
        L(this, Pt, Ih).call(this, a);
      },
      mouseUp: (a) => {
        L(this, Pt, Yy).call(this, a);
      },
      touchStart: (a) => {
        L(this, Pt, nA).call(this, a);
      },
      touchMove: (a) => {
        L(this, Pt, Ih).call(this, a);
      },
      touchEnd: (a) => {
        L(this, Pt, Xy).call(this, a);
      },
      touchCancel: (a) => {
        L(this, Pt, Xy).call(this, a);
      },
      touchEndClick: (a) => {
        L(this, Pt, eA).call(this, a);
      },
      visibilityChange: () => {
        L(this, Pt, WE).call(this);
      }
    });
  }
  addListeners() {
    L(this, Pt, Gy).call(this, !0);
  }
  init() {
    v(this, yo).length = 0;
    for (const t of v(this, Ci).plugins.filter((i) => !!i.clickPositionValid))
      v(this, yo).push(t);
  }
  removeListeners() {
    L(this, Pt, Gy).call(this, !1);
  }
}
Ml = new WeakMap(), yo = new WeakMap(), Ci = new WeakMap(), Tl = new WeakMap(), Wn = new WeakMap(), vo = new WeakMap(), Pt = new WeakSet(), $E = function(t) {
  var u;
  const i = v(this, Ci), a = v(this, Wn), r = i.actualOptions;
  if (v(this, Ml)) {
    const c = a.interactivityData.mouse, f = c.position;
    if (!f)
      return;
    c.clickPosition = { ...f }, c.clickTime = performance.now();
    const m = (u = r.interactivity) == null ? void 0 : u.events.onClick;
    if (!(m != null && m.mode))
      return;
    Gn(m.mode, (p) => {
      a.handleClickMode(p);
    });
  }
  t.type === "touchend" && setTimeout(() => {
    L(this, Pt, Ku).call(this);
  }, A6);
}, WE = function() {
  L(this, Pt, Ku).call(this);
}, JE = function(t) {
  var p, g, y;
  const i = v(this, Tl), a = v(this, Ci), r = v(this, Wn), u = a.actualOptions, c = r.interactivityData.element;
  if (!c)
    return;
  const f = c, m = a.canvas;
  m.setPointerEvents(f === m.domElement ? "initial" : "none"), !(t && !((p = u.interactivity) != null && p.events.onHover.enable || (g = u.interactivity) != null && g.events.onClick.enable)) && (Ne(c, la, i.mouseMove, t), Ne(c, IM, i.touchStart, t), Ne(c, $M, i.touchMove, t), t ? (y = u.interactivity) != null && y.events.onClick.enable ? (Ne(c, Xu, i.touchEndClick, t), Ne(c, t1, i.mouseUp, t), Ne(c, JS, i.mouseDown, t)) : Ne(c, Xu, i.touchEnd, t) : (Ne(c, Xu, i.touchEndClick, t), Ne(c, t1, i.mouseUp, t), Ne(c, JS, i.mouseDown, t), Ne(c, Xu, i.touchEnd, t)), Ne(c, Qg, i.mouseLeave, t), Ne(c, WM, i.touchCancel, t));
}, Gy = function(t) {
  var m;
  const i = v(this, Tl), a = v(this, Ci), r = v(this, Wn), u = a.actualOptions, c = (m = u.interactivity) == null ? void 0 : m.detectsOn, f = a.canvas.domElement;
  c === Nr.window ? r.interactivityData.element = Un() : c === Nr.parent && f ? r.interactivityData.element = f.parentElement ?? f.parentNode : r.interactivityData.element = f, L(this, Pt, JE).call(this, t), Ne(document, mM, i.visibilityChange, t, !1);
}, tA = function() {
  const { interactivityData: t } = v(this, Wn), { mouse: i } = t;
  i.clicking = !0, i.downPosition = i.position;
}, Yy = function(t) {
  var m, p;
  const i = v(this, Ci), a = v(this, Wn), r = i.actualOptions, { mouse: u } = a.interactivityData;
  u.inside = !0;
  let c = !1;
  const f = u.position;
  if (!(!f || !((m = r.interactivity) != null && m.events.onClick.enable))) {
    for (const g of v(this, yo))
      if (c = ((p = g.clickPositionValid) == null ? void 0 : p.call(g, f)) ?? !1, c)
        break;
    c || L(this, Pt, $E).call(this, t), u.clicking = !1;
  }
}, Ku = function() {
  const { interactivityData: t } = v(this, Wn), { mouse: i } = t;
  delete i.position, delete i.clickPosition, delete i.downPosition, t.status = Qg, i.inside = !1, i.clicking = !1;
}, Ih = function(t) {
  var p;
  const i = v(this, Ci), a = v(this, Wn), r = i.actualOptions, u = a.interactivityData, c = i.canvas.domElement;
  if (!u.element)
    return;
  u.mouse.inside = !0;
  let f;
  if (t.type.startsWith("pointer")) {
    A(this, Ml, !0);
    const g = t;
    if (u.element === Un()) {
      if (c) {
        const y = c.getBoundingClientRect();
        f = {
          x: g.clientX - y.left,
          y: g.clientY - y.top
        };
      }
    } else if (((p = r.interactivity) == null ? void 0 : p.detectsOn) === Nr.parent) {
      const y = g.target, b = g.currentTarget;
      if (c) {
        const S = y.getBoundingClientRect(), T = b.getBoundingClientRect(), C = c.getBoundingClientRect();
        f = {
          x: g.offsetX + Bt * S.left - (T.left + C.left),
          y: g.offsetY + Bt * S.top - (T.top + C.top)
        };
      } else
        f = {
          x: g.offsetX,
          y: g.offsetY
        };
    } else g.target === c && (f = {
      x: g.offsetX,
      y: g.offsetY
    });
  } else if (A(this, Ml, t.type !== "touchmove"), c) {
    const g = t, y = g.touches[g.touches.length - JR], b = c.getBoundingClientRect();
    if (!y)
      return;
    f = {
      x: y.clientX - b.left,
      y: y.clientY - b.top
    };
  }
  const m = i.retina.pixelRatio;
  f && (f.x *= m, f.y *= m), u.mouse.position = f, u.status = la;
}, Xy = function(t) {
  const i = t, a = Array.from(i.changedTouches);
  for (const r of a)
    v(this, vo).delete(r.identifier);
  L(this, Pt, Ku).call(this);
}, eA = function(t) {
  const i = t, a = Array.from(i.changedTouches);
  for (const r of a)
    v(this, vo).delete(r.identifier);
  L(this, Pt, Yy).call(this, t);
}, nA = function(t) {
  const i = t, a = Array.from(i.changedTouches);
  for (const r of a)
    v(this, vo).set(r.identifier, performance.now());
  L(this, Pt, Ih).call(this, t);
};
const R6 = 1, O6 = 1, oM = 0;
function z6(n) {
  if (!(typeof IntersectionObserver > "u"))
    return new IntersectionObserver(n);
}
var kn, Ei, bo, Ai, xo, ta, ea, Gc, bd, iA;
class k6 {
  constructor(t, i) {
    k(this, bd);
    w(this, "interactivityData");
    k(this, kn);
    k(this, Ei);
    k(this, bo);
    k(this, Ai);
    k(this, xo);
    k(this, ta);
    k(this, ea);
    k(this, Gc);
    A(this, Ei, i), A(this, Gc, t), A(this, xo, []), A(this, Ai, []), A(this, ea, []), A(this, kn, /* @__PURE__ */ new Map()), A(this, bo, new D6(i, this)), this.interactivityData = {
      mouse: {
        clicking: !1,
        inside: !1
      }
    }, A(this, ta, z6((a) => {
      L(this, bd, iA).call(this, a);
    }));
  }
  addClickHandler(t) {
    const i = v(this, Ei), a = this.interactivityData;
    if (i.destroyed)
      return;
    const r = a.element;
    if (!r)
      return;
    const u = (S, T, C) => {
      if (i.destroyed)
        return;
      const R = i.retina.pixelRatio, z = {
        x: T.x * R,
        y: T.y * R
      }, B = i.particles.grid.queryCircle(z, C * R);
      t(S, B);
    }, c = (S) => {
      if (i.destroyed)
        return;
      const T = S, C = {
        x: T.offsetX,
        y: T.offsetY
      };
      u(S, C, R6);
    }, f = () => {
      i.destroyed || (y = !0, b = !1);
    }, m = () => {
      i.destroyed || (b = !0);
    }, p = (S) => {
      if (!i.destroyed) {
        if (y && !b) {
          const T = S, C = T.touches[T.touches.length - O6];
          if (!C)
            return;
          const R = i.canvas.domElement, z = R ? R.getBoundingClientRect() : void 0, B = {
            x: C.clientX - (z ? z.left : oM),
            y: C.clientY - (z ? z.top : oM)
          };
          u(S, B, Math.max(C.radiusX, C.radiusY));
        }
        y = !1, b = !1;
      }
    }, g = () => {
      i.destroyed || (y = !1, b = !1);
    };
    let y = !1, b = !1;
    v(this, kn).set(cz, c), v(this, kn).set(IM, f), v(this, kn).set($M, m), v(this, kn).set(Xu, p), v(this, kn).set(WM, g);
    for (const [S, T] of v(this, kn))
      r.addEventListener(S, T);
  }
  addListeners() {
    v(this, bo).addListeners();
  }
  clearClickHandlers() {
    var a;
    const t = v(this, Ei), i = this.interactivityData;
    if (!t.destroyed) {
      for (const [r, u] of v(this, kn))
        (a = i.element) == null || a.removeEventListener(r, u);
      v(this, kn).clear();
    }
  }
  externalInteract(t) {
    for (const i of v(this, Ai)) {
      const a = this.interactivityData;
      i.isEnabled(a) && i.interact(a, t);
    }
  }
  handleClickMode(t) {
    var a;
    if (v(this, Ei).destroyed)
      return;
    const i = this.interactivityData;
    for (const r of v(this, Ai))
      (a = r.handleClickMode) == null || a.call(r, t, i);
  }
  init() {
    v(this, bo).init();
    for (const t of v(this, xo)) {
      switch (t.type) {
        case Ol.external:
          v(this, Ai).push(t);
          break;
        case Ol.particles:
          v(this, ea).push(t);
          break;
      }
      t.init();
    }
  }
  async initInteractors() {
    var i, a;
    const t = await ((a = (i = v(this, Gc)).getInteractors) == null ? void 0 : a.call(i, v(this, Ei), !0));
    t && (A(this, xo, t), A(this, Ai, []), A(this, ea, []));
  }
  particlesInteract(t, i) {
    const a = this.interactivityData;
    for (const r of v(this, Ai))
      r.clear(t, i);
    for (const r of v(this, ea))
      r.isEnabled(t, a) && r.interact(t, a, i);
  }
  removeListeners() {
    v(this, bo).removeListeners();
  }
  reset(t) {
    const i = this.interactivityData;
    for (const a of v(this, Ai))
      a.isEnabled(i) && a.reset(i, t);
    for (const a of v(this, ea))
      a.isEnabled(t, i) && a.reset(i, t);
  }
  startObserving() {
    const t = this.interactivityData;
    t.element instanceof HTMLElement && v(this, ta) && v(this, ta).observe(t.element);
  }
  stopObserving() {
    const t = this.interactivityData;
    t.element instanceof HTMLElement && v(this, ta) && v(this, ta).unobserve(t.element);
  }
  updateMaxDistance() {
    let t = 0;
    for (const a of v(this, xo))
      a.maxDistance > t && (t = a.maxDistance);
    const i = v(this, Ei);
    i.particles.grid.setCellSize(t * i.retina.pixelRatio);
  }
}
kn = new WeakMap(), Ei = new WeakMap(), bo = new WeakMap(), Ai = new WeakMap(), xo = new WeakMap(), ta = new WeakMap(), ea = new WeakMap(), Gc = new WeakMap(), bd = new WeakSet(), iA = function(t) {
  const i = v(this, Ei);
  if (!(i.destroyed || !i.actualOptions.pauseOnOutsideViewport))
    for (const a of t)
      a.target === this.interactivityData.element && (a.isIntersecting ? i.play() : i.pause());
};
var na, Cl;
class V6 {
  constructor(t, i) {
    w(this, "interactionManager");
    k(this, na);
    k(this, Cl);
    A(this, na, i), A(this, Cl, t), this.interactionManager = new k6(t, i), v(this, na).addClickHandler = (a) => {
      this.interactionManager.addClickHandler(a);
    };
  }
  addClickHandler(t) {
    this.interactionManager.addClickHandler(t);
  }
  clearClickHandlers() {
    this.interactionManager.clearClickHandlers();
  }
  destroy() {
    var t;
    this.clearClickHandlers(), (t = v(this, Cl).interactors) == null || t.delete(v(this, na));
  }
  particleCreated(t) {
    const i = t, a = new KM(v(this, Cl), v(this, na));
    a.load(v(this, na).actualOptions.interactivity), a.load(i.options.interactivity), i.interactivity = a;
  }
  particleReset(t) {
    this.interactionManager.reset(t);
  }
  postParticleUpdate(t, i) {
    this.interactionManager.particlesInteract(t, i);
  }
  postUpdate(t) {
    this.interactionManager.externalInteract(t), this.interactionManager.updateMaxDistance();
  }
  async preInit() {
    await this.interactionManager.initInteractors(), this.interactionManager.init();
  }
  async redrawInit() {
    await this.interactionManager.initInteractors(), this.interactionManager.init();
  }
  start() {
    return this.interactionManager.addListeners(), this.interactionManager.startObserving(), Promise.resolve();
  }
  stop() {
    this.interactionManager.removeListeners(), this.interactionManager.stopObserving();
  }
}
na = new WeakMap(), Cl = new WeakMap();
const P6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  InteractivityPluginInstance: V6
}, Symbol.toStringTag, { value: "Module" }));
var Yc, Xc;
class L6 {
  constructor(t, i) {
    k(this, Yc);
    k(this, Xc);
    A(this, Xc, t), A(this, Yc, i);
  }
  destroy() {
    var t;
    (t = v(this, Xc).images) == null || t.delete(v(this, Yc));
  }
}
Yc = new WeakMap(), Xc = new WeakMap();
const _6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  ImagePreloaderInstance: L6
}, Symbol.toStringTag, { value: "Module" })), B6 = 0;
var Fc, xd, sA;
class N6 {
  constructor(t) {
    k(this, xd);
    k(this, Fc);
    A(this, Fc, t);
  }
  checkParticlePosition(t, i, a) {
    return !L(this, xd, sA).call(this, t, i, a);
  }
}
Fc = new WeakMap(), xd = new WeakSet(), sA = function(t, i, a) {
  const r = t.options.collisions;
  if (!(r != null && r.enable))
    return !1;
  const u = r.overlap;
  if (u.enable)
    return !1;
  const c = u.retries;
  if (c >= B6 && a > c)
    throw new Error("Particle is overlapping and can't be placed");
  return !!v(this, Fc).particles.find((f) => Oo(i, f.position) < t.getRadius() + f.getRadius());
};
const U6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  OverlapPluginInstance: N6
}, Symbol.toStringTag, { value: "Module" }));
function j6(n) {
  return [...n].sort((t, i) => t - i).join("_");
}
function rM(n, t) {
  const i = j6(n.map((r) => r.id));
  let a = t.get(i);
  return a === void 0 && (a = Yt(), t.set(i, a)), a;
}
const lM = 0, uM = 0, cM = 0, H6 = 1, q6 = 0;
var El, $i, ia, Al, qn, aA, Fy, Zy, oA;
class G6 {
  constructor(t, i) {
    k(this, qn);
    k(this, El, /* @__PURE__ */ new Map());
    k(this, $i);
    k(this, ia);
    k(this, Al);
    A(this, Al, t), A(this, $i, i), A(this, ia, { links: /* @__PURE__ */ new Map(), triangles: /* @__PURE__ */ new Map() });
  }
  drawParticle(t, i) {
    var z;
    const { links: a, options: r } = i;
    if (!(a != null && a.length) || !r.links)
      return;
    const u = r.links, c = i.retina.linksWidth ?? uM, f = i.getPosition(), m = (z = i.options.twinkle) == null ? void 0 : z.links, p = u.triangles.enable, g = p ? new Set(a.map((B) => B.destination.id)) : null, y = t.globalAlpha;
    let b = "", S = -1, T = -1, C = !1;
    const R = () => {
      C && (t.stroke(), C = !1);
    };
    for (const B of a) {
      if (u.frequency < H6 && L(this, qn, Zy).call(this, i, B.destination) > u.frequency)
        continue;
      const H = B.destination.getPosition();
      if (p && !B.isWarped && g && (R(), L(this, qn, aA).call(this, r, i, B, g, f, H, t)), B.opacity <= lM || c <= uM || !u.enable)
        continue;
      let X = B.opacity, Q = B.color;
      const ut = m != null && m.enable && Yt() < m.frequency ? Vo(v(this, Al), m.color) : void 0;
      if (m && ut && (Q = ut, X = ht(m.opacity)), !Q) {
        const $ = u.id !== void 0 ? v(this, $i).particles.linksColors.get(u.id) : v(this, $i).particles.linksColor;
        Q = Jy(i, B.destination, $);
      }
      if (!Q)
        continue;
      const st = L(this, qn, Fy).call(this, Q);
      if ((st !== b || c !== S || X !== T) && (R(), t.strokeStyle = st, t.lineWidth = c, t.globalAlpha = X, b = st, S = c, T = X, t.beginPath(), C = !0), B.isWarped) {
        const $ = v(this, $i).canvas.size, lt = H.x - f.x, nt = H.y - f.y;
        let vt = Dt.x, it = Dt.y;
        Math.abs(lt) > $.width * bt && (vt = lt > cM ? -$.width : $.width), Math.abs(nt) > $.height * bt && (it = nt > cM ? -$.height : $.height), t.moveTo(f.x, f.y), t.lineTo(H.x + vt, H.y + it), t.moveTo(f.x - vt, f.y - it), t.lineTo(H.x, H.y);
      } else
        t.moveTo(f.x, f.y), t.lineTo(H.x, H.y);
    }
    R(), t.globalAlpha = y;
  }
  init() {
    return v(this, ia).links.clear(), v(this, ia).triangles.clear(), v(this, El).clear(), Promise.resolve();
  }
  particleCreated(t) {
    if (t.links = [], !t.options.links)
      return;
    t.linksDistance = t.options.links.distance, t.linksWidth = t.options.links.width;
    const i = v(this, $i).retina.pixelRatio;
    t.retina.linksDistance = t.linksDistance * i, t.retina.linksWidth = t.linksWidth * i;
  }
  particleDestroyed(t) {
    t.links = [];
  }
}
El = new WeakMap(), $i = new WeakMap(), ia = new WeakMap(), Al = new WeakMap(), qn = new WeakSet(), aA = function(t, i, a, r, u, c, f) {
  var y, b, S;
  const m = a.destination, p = (y = t.links) == null ? void 0 : y.triangles;
  if (!(p != null && p.enable) || !((b = m.options.links) != null && b.triangles.enable))
    return;
  const g = m.links;
  if (g != null && g.length)
    for (const T of g) {
      if (T.isWarped || L(this, qn, Zy).call(this, m, T.destination) > m.options.links.frequency || !r.has(T.destination.id))
        continue;
      const C = T.destination;
      if (L(this, qn, oA).call(this, i, m, C) > (((S = t.links) == null ? void 0 : S.triangles.frequency) ?? q6))
        continue;
      const R = p.opacity ?? (a.opacity + T.opacity) * bt, z = Vo(v(this, Al), p.color) ?? a.color;
      if (!z || R <= lM)
        continue;
      const B = C.getPosition();
      f.save(), f.fillStyle = L(this, qn, Fy).call(this, z), f.globalAlpha = R, f.beginPath(), f.moveTo(u.x, u.y), f.lineTo(c.x, c.y), f.lineTo(B.x, B.y), f.closePath(), f.fill(), f.restore();
    }
}, Fy = function(t) {
  const i = `${t.r},${t.g},${t.b}`;
  let a = v(this, El).get(i);
  return a || (a = Qc(t, v(this, $i).hdr), v(this, El).set(i, a)), a;
}, Zy = function(t, i) {
  return rM([t, i], v(this, ia).links);
}, oA = function(t, i, a) {
  return rM([t, i, a], v(this, ia).triangles);
};
const Y6 = /* @__PURE__ */ Object.freeze(/* @__PURE__ */ Object.defineProperty({
  __proto__: null,
  LinkInstance: G6
}, Symbol.toStringTag, { value: "Module" }));
export {
  qB as Sage125LandingApp,
  K6 as default
};
