import { useEffect, useState } from "react";

import { AuditCard } from "./cards/AuditCard";
import { EvidenceCard } from "./cards/EvidenceCard";
import { MultiAgentCard } from "./cards/MultiAgentCard";
import { ResearchBeamCard } from "./cards/ResearchBeamCard";
import { BentoCard, BentoGrid } from "./components/magicui/bento-grid";
import { StatsRow } from "./components/StatsRow";
import { HeroSection } from "./HeroSection";
import type { SageLandingData, SageLandingState } from "./types";

export interface SageLandingProps {
  data: SageLandingData;
  setTriggerValue: (name: keyof SageLandingState, value: SageLandingState[keyof SageLandingState]) => void;
}

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true,
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = () => setReduced(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

export default function SageLanding({ data, setTriggerValue }: SageLandingProps) {
  const reducedMotion = usePrefersReducedMotion();
  const fireCta = (event: keyof SageLandingState) => {
    setTriggerValue(event, Date.now());
  };

  return (
    <div className="sage125-landing-root w-full">
      <HeroSection q028Available={data.q028_available} onFireCta={fireCta} />
      <div className="mx-auto w-full max-w-[1400px] px-1 pb-4">
        <StatsRow
          questionCount={data.question_count}
          evidenceCount={data.evidence_count}
          planCount={data.plan_count}
          coverage={data.coverage}
          coverageStatus={data.coverage_status}
          statsStatus={data.stats_status}
        />
        <section className="mt-8" id="land-capabilities">
          <h2 className="mb-4 text-[22px] font-semibold text-[#F1F6FF]">系统能力</h2>
          <BentoGrid>
            <BentoCard className="col-span-12 min-h-[280px] lg:col-span-7 lg:min-h-[300px]">
              <EvidenceCard reducedMotion={reducedMotion} />
            </BentoCard>
            <BentoCard className="col-span-12 min-h-[280px] lg:col-span-5 lg:min-h-[300px]">
              <ResearchBeamCard reducedMotion={reducedMotion} />
            </BentoCard>
            <BentoCard className="col-span-12 min-h-[240px] lg:col-span-5 lg:min-h-[260px]">
              <MultiAgentCard reducedMotion={reducedMotion} />
            </BentoCard>
            <BentoCard className="col-span-12 min-h-[240px] lg:col-span-7 lg:min-h-[260px]">
              <AuditCard reducedMotion={reducedMotion} />
            </BentoCard>
          </BentoGrid>
        </section>
      </div>
    </div>
  );
}
