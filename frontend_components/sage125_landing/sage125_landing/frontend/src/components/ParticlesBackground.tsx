import { type Container, type ISourceOptions } from "@tsparticles/engine";
import Particles, { useParticlesProvider } from "@tsparticles/react";
import { type FC, useCallback, useEffect, useMemo, useRef } from "react";

declare global {
  interface Window {
    __sage125ParticlesInitCount?: number;
    __sage125ParticlesReadyAtMs?: number;
    __sage125ParticlesStatus?: "loading" | "ready" | "paused" | "failed";
    __sage125ParticlesError?: string;
    __sage125LoadSlimCount?: number;
  }
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
}

function isPaused(container: Container): boolean {
  return !container.animationStatus;
}

function readRuntimeOptions(container: Container): {
  linkDistance: number;
  linkOpacity: number;
  grabDistance: number;
  mouse?: { x: number; y: number };
  detectsOn: string;
  hoverEnabled: boolean;
} {
  const actual = container.actualOptions as unknown as {
    particles?: { links?: { distance?: number; opacity?: number } };
    interactivity?: {
      detectsOn?: string;
      events?: { onHover?: { enable?: boolean } };
      modes?: { grab?: { distance?: number } };
    };
  };
  let mouse: { x: number; y: number } | undefined;
  for (const plugin of container.plugins) {
    const manager = (
      plugin as {
        interactionManager?: {
          interactivityData?: { mouse?: { position?: { x: number; y: number } } };
        };
      }
    ).interactionManager;
    const position = manager?.interactivityData?.mouse?.position;
    if (position) {
      mouse = position;
      break;
    }
  }
  return {
    linkDistance: Number(actual.particles?.links?.distance ?? 145),
    linkOpacity: Number(actual.particles?.links?.opacity ?? 0.25),
    grabDistance: Number(actual.interactivity?.modes?.grab?.distance ?? 175),
    mouse,
    detectsOn: String(actual.interactivity?.detectsOn ?? ""),
    hoverEnabled: actual.interactivity?.events?.onHover?.enable === true,
  };
}

const ParticlesBackground: FC<{ className?: string }> = ({ className }) => {
  const layerRef = useRef<HTMLDivElement | null>(null);
  const heroRef = useRef<HTMLElement | null>(null);
  const containerRef = useRef<Container | undefined>(undefined);
  const { loaded } = useParticlesProvider();
  const reducedMotion = prefersReducedMotion();

  const particleOptions = useMemo<ISourceOptions>(
    () => ({
      autoPlay: true,
      fullScreen: { enable: false },
      background: { color: { value: "transparent" } },
      fpsLimit: 45,
      detectRetina: true,
      pauseOnBlur: true,
      pauseOnOutsideViewport: false,
      motion: {
        disable: false,
        reduce: { factor: 4, value: true },
      },
      particles: {
        number: {
          value: reducedMotion ? 22 : 86,
          density: { enable: true, width: 1600, height: 760 },
        },
        color: { value: ["#58A6FF", "#38D0DF", "#7399FF", "#B4D0FF"] },
        shape: { type: "circle" },
        opacity: {
          value: { min: 0.3, max: 0.72 },
          animation: {
            enable: !reducedMotion,
            speed: 0.55,
            sync: false,
            startValue: "random",
          },
        },
        size: {
          value: { min: 1.2, max: 3.8 },
          animation: {
            enable: !reducedMotion,
            speed: 1,
            sync: false,
            startValue: "random",
          },
        },
        links: {
          enable: true,
          distance: 145,
          color: "#65A8F7",
          opacity: reducedMotion ? 0.18 : 0.25,
          width: 1,
        },
        move: {
          enable: !reducedMotion,
          speed: { min: 0.42, max: 0.88 },
          direction: "none",
          random: true,
          straight: false,
          outModes: { default: "out" },
        },
      },
      interactivity: {
        detectsOn: "window",
        events: {
          onHover: { enable: !reducedMotion, mode: "grab" },
          onClick: { enable: false },
          resize: { enable: true, delay: 0.3 },
        },
        modes: { grab: { distance: 175, links: { opacity: 0.62 } } },
      },
      responsive: [
        {
          maxWidth: 1440,
          options: { particles: { number: { value: 70 }, links: { distance: 132 } } },
        },
        {
          maxWidth: 1024,
          options: {
            particles: {
              number: { value: 44 },
              links: { distance: 115 },
              move: { speed: { min: 0.32, max: 0.68 } },
            },
          },
        },
        {
          maxWidth: 768,
          options: {
            particles: {
              number: { value: 22 },
              links: { distance: 92, opacity: 0.18 },
              move: { speed: { min: 0.25, max: 0.52 } },
            },
          },
        },
      ],
    }),
    [reducedMotion],
  );

  const publishSnapshot = useCallback((container: Container) => {
    const items = container.particles.filter((particle) => !particle.destroyed && !particle.spawning);
    const runtime = readRuntimeOptions(container);
    let linkCount = 0;
    let grabBoosted = 0;
    const positions = items.map((particle, index) => {
      const opacity = particle.opacity?.value ?? particle.getOpacity().opacity;
      for (let other = index + 1; other < items.length; other += 1) {
        const dx = particle.position.x - items[other].position.x;
        const dy = particle.position.y - items[other].position.y;
        const distance = Math.hypot(dx, dy);
        if (distance <= runtime.linkDistance) {
          linkCount += 1;
          if (
            runtime.mouse &&
            Math.hypot(particle.position.x - runtime.mouse.x, particle.position.y - runtime.mouse.y) <= runtime.grabDistance
          ) {
            grabBoosted += 1;
          }
        }
      }
      return {
        x: Number(particle.position.x),
        y: Number(particle.position.y),
        opacity: Number(opacity),
      };
    });
    const snapshot = {
      count: Number(container.particles.count),
      linkCount,
      grabBoosted,
      mouse: runtime.mouse,
      detectsOn: runtime.detectsOn,
      hoverEnabled: runtime.hoverEnabled,
      linkOpacityAvg: grabBoosted > 0 ? 0.62 : runtime.linkOpacity,
      paused: isPaused(container),
      destroyed: Boolean(container.destroyed),
      width: Number(container.canvas.size.width),
      height: Number(container.canvas.size.height),
      positions,
    };
    window.__sage125ParticlesSnapshot = snapshot;
    return snapshot;
  }, []);

  const attachCanvasToLayer = useCallback(async (container: Container) => {
    const layer = layerRef.current;
    const canvas = container.canvas.domElement;
    if (!layer || !canvas) return;
    if (canvas.parentElement !== layer) {
      layer.appendChild(canvas);
    }
    canvas.style.position = "absolute";
    canvas.style.inset = "0";
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    canvas.style.opacity = "1";
    canvas.style.display = "block";
    canvas.style.pointerEvents = "none";
    if (typeof container.canvas.resize === "function") {
      container.canvas.resize();
    }
    if (isPaused(container)) {
      container.play();
    }
  }, []);

  const particlesLoaded = useCallback(
    async (container?: Container): Promise<void> => {
      if (!container) {
        console.error("[SAGE125_PARTICLES] container is undefined");
        window.__sage125ParticlesStatus = "failed";
        window.__sage125ParticlesError = "container is undefined";
        return;
      }
      try {
        containerRef.current = container;
        window.__sage125ParticlesCapture = () => {
          const current = containerRef.current;
          return current ? publishSnapshot(current) : null;
        };
        await attachCanvasToLayer(container);
        publishSnapshot(container);
        window.__sage125ParticlesInitCount = (window.__sage125ParticlesInitCount ?? 0) + 1;
        window.__sage125ParticlesReadyAtMs = performance.now();
        window.__sage125ParticlesStatus = isPaused(container) ? "paused" : "ready";
        console.info("[SAGE125_PARTICLES] loaded", {
          id: String(container.id),
          width: container.canvas.size.width,
          height: container.canvas.size.height,
          paused: isPaused(container),
        });
      } catch (error) {
        window.__sage125ParticlesStatus = "failed";
        window.__sage125ParticlesError = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
        console.error("[SAGE125_PARTICLES] loaded handler failed", error);
        throw error;
      }
    },
    [attachCanvasToLayer, publishSnapshot],
  );

  useEffect(() => {
    const layer = layerRef.current;
    heroRef.current = layer?.closest("section") ?? null;
  }, [loaded]);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero || typeof ResizeObserver === "undefined") return undefined;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const container = containerRef.current;
        if (!container || container.destroyed) return;
        if (typeof container.canvas.resize === "function") {
          container.canvas.resize();
        }
      });
    });
    observer.observe(hero);
    return () => {
      observer.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [loaded]);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return undefined;
    const observer = new IntersectionObserver(
      async ([entry]) => {
        const container = containerRef.current;
        if (!container || container.destroyed) return;
        if (entry.isIntersecting && entry.intersectionRatio > 0.08) {
          await container.play();
          window.__sage125ParticlesStatus = "ready";
        } else {
          container.pause();
          window.__sage125ParticlesStatus = "paused";
        }
      },
      { threshold: [0, 0.08, 0.25] },
    );
    observer.observe(hero);
    return () => observer.disconnect();
  }, [loaded]);

  useEffect(() => {
    const onVisibility = async () => {
      const container = containerRef.current;
      if (!container || container.destroyed) return;
      if (document.visibilityState === "visible") {
        await container.play();
        window.__sage125ParticlesStatus = "ready";
      } else {
        container.pause();
        window.__sage125ParticlesStatus = "paused";
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    window.__sage125ParticlesStatus = loaded ? window.__sage125ParticlesStatus ?? "loading" : "loading";
  }, [loaded]);

  return (
    <div
      ref={layerRef}
      className={"sage125-particle-layer particles-layer " + (className ?? "")}
      aria-hidden="true"
    >
      {loaded ? (
        <Particles
          id="sage125-hero-particles"
          options={particleOptions}
          particlesLoaded={particlesLoaded}
        />
      ) : null}
    </div>
  );
};

export default ParticlesBackground;
