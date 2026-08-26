# -*- coding: utf-8 -*-
"""粒子恢复专项：源码契约，不得把静态 Grid 当作粒子通过。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend_components/sage125_landing/sage125_landing/frontend/src"
INIT = ROOT / "frontend_components/sage125_landing/sage125_landing/__init__.py"
LANDING = ROOT / "app/ui/landing.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_official_react_wrapper_only() -> None:
    index = _read(FRONTEND / "index.tsx")
    particles = _read(FRONTEND / "components/ParticlesBackground.tsx")
    assert "from \"@tsparticles/react\"" in index
    assert "ParticlesProvider" in index
    assert "initializeParticles" in index
    assert "await loadSlim(engine)" in index
    assert "initParticlesEngine" not in index
    assert "tsParticles.load" not in index
    assert "from \"@tsparticles/react\"" in particles
    assert "<Particles" in particles
    assert "initParticlesEngine" not in particles
    assert "tsParticles.load" not in particles
    assert "loadSlim" not in particles


def test_particle_options_baseline() -> None:
    src = _read(FRONTEND / "components/ParticlesBackground.tsx")
    assert "autoPlay: true" in src
    assert "pauseOnOutsideViewport: false" in src
    assert "detectsOn: \"window\"" in src
    assert "value: reducedMotion ? 22 : 86" in src
    assert "enable: !reducedMotion" in src
    assert "max: 0.88" in src
    assert "max: 0.72" in src
    assert "onHover: { enable: !reducedMotion, mode: \"grab\" }" in src


def test_landing_component_stable_key_and_isolate() -> None:
    init = _read(INIT)
    landing = _read(LANDING)
    assert "isolate_styles=False" in init
    assert "sage125-landing-home-v2" in init
    assert landing.count("sage125_landing(") == 1
    assert "key=\"sage125-landing-home-v2\"" in landing
    assert "uuid" not in landing
    assert "time.time" not in landing
    assert "@st.fragment" in landing
    fragment_fn = landing.split("def _stats_refresh_fragment", 1)[1].split("def render_landing", 1)[0]
    assert "sage125_landing(" not in fragment_fn


def test_hero_layer_structure() -> None:
    hero = _read(FRONTEND / "HeroSection.tsx")
    css = _read(FRONTEND / "styles/globals.css")
    assert "sage125-hero" in hero
    assert "sage125-particle-layer" in hero or "ParticlesBackground" in hero
    assert "sage125-hero-grid" in hero
    assert "sage125-hero-readability" in hero
    assert "sage125-hero-content" in hero
    assert "hero-cta-primary" in hero
    assert "min-height: 700px" in css
    assert "pointer-events: none" in css
