/// <reference types="vite/client" />

interface Sage125ParticleSnapshot {
  count: number;
  linkCount: number;
  grabBoosted: number;
  mouse?: { x: number; y: number };
  detectsOn?: string;
  hoverEnabled?: boolean;
  linkOpacityAvg: number;
  paused: boolean;
  destroyed: boolean;
  width: number;
  height: number;
  positions: Array<{ x: number; y: number; opacity: number }>;
}

interface Window {
  __sage125ParticlesInitCount?: number;
  __sage125ParticlesReadyAtMs?: number;
  __sage125ParticlesStatus?: "loading" | "ready" | "paused" | "failed";
  __sage125ParticlesError?: string;
  __sage125LoadSlimCount?: number;
  __sage125ParticlesSnapshot?: Sage125ParticleSnapshot;
  __sage125ParticlesCapture?: () => Sage125ParticleSnapshot | null;
}
