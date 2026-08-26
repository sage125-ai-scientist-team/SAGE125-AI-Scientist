import type { FrontendRenderer, FrontendRendererArgs } from "@streamlit/component-v2-lib";
import { type Engine } from "@tsparticles/engine";
import { loadSlim } from "@tsparticles/slim";
import { ParticlesProvider } from "@tsparticles/react";
import { StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";

import SageLanding from "./SageLanding";
import "./styles/globals.css";
import type { SageLandingData, SageLandingState } from "./types";

const reactRoots: WeakMap<FrontendRendererArgs["parentElement"], Root> = new WeakMap();

const enginesWithSlim = new WeakSet<Engine>();

const initializeParticles = async (engine: Engine): Promise<void> => {
  if (enginesWithSlim.has(engine)) {
    return;
  }
  await loadSlim(engine);
  enginesWithSlim.add(engine);
  if (typeof window !== "undefined") {
    window.__sage125LoadSlimCount = (window.__sage125LoadSlimCount ?? 0) + 1;
  }
};

export function Sage125LandingApp(props: {
  data: SageLandingData;
  setTriggerValue: (name: keyof SageLandingState, value: SageLandingState[keyof SageLandingState]) => void;
}) {
  return (
    <ParticlesProvider init={initializeParticles}>
      <SageLanding data={props.data} setTriggerValue={props.setTriggerValue} />
    </ParticlesProvider>
  );
}

const SageLandingRoot: FrontendRenderer<SageLandingState, SageLandingData> = (args) => {
  const { data, parentElement, setTriggerValue } = args;
  const rootElement = parentElement.querySelector(".sage125-landing-root");
  if (!rootElement) {
    throw new Error("Unexpected: sage125_landing root element not found");
  }

  let reactRoot = reactRoots.get(parentElement);
  if (!reactRoot) {
    reactRoot = createRoot(rootElement);
    reactRoots.set(parentElement, reactRoot);
  }

  reactRoot.render(
    <StrictMode>
      <Sage125LandingApp data={data} setTriggerValue={setTriggerValue} />
    </StrictMode>,
  );

  return () => {
    const root = reactRoots.get(parentElement);
    if (root) {
      root.unmount();
      reactRoots.delete(parentElement);
    }
  };
};

export default SageLandingRoot;
