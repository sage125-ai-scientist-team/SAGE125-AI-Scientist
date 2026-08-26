import ParticlesBackground from "./components/ParticlesBackground";
import type { SageLandingState } from "./types";

export interface HeroSectionProps {
  q028Available: boolean;
  onFireCta: (event: keyof SageLandingState) => void;
}

export function HeroSection({ q028Available, onFireCta }: HeroSectionProps) {
  return (
    <section className="sage125-hero hero-section relative flex w-full flex-col items-center justify-center px-6 py-16">
      <ParticlesBackground />
      <div aria-hidden="true" className="sage125-hero-grid ambient-light-layer" />
      <div aria-hidden="true" className="sage125-hero-readability readability-mask" />

      <div className="sage125-hero-content hero-content mx-auto flex w-full max-w-[1000px] flex-col items-center text-center">
        <p className="font-latin text-[13px] font-semibold uppercase tracking-[0.06em] text-[#71A4FF]">
          SAGE125 AI Scientist
        </p>
        <h1
          className="mt-4 text-balance text-[44px] font-bold leading-[1.16] tracking-[-0.035em] text-[#F3F7FF] sm:text-[48px] md:text-[54px] lg:text-[60px]"
          style={{ fontWeight: 720, textShadow: "0 0 22px rgba(113,164,255,0.14)" }}
        >
          从科学问题到可验证研究计划
        </h1>
        <p className="mx-auto mt-5 max-w-[760px] text-[18px] leading-[1.8] text-[#B7C5D8] sm:text-[19px] md:text-[20px]">
          基于可追溯文献证据与严谨科研方法，系统组织知识缺口、形成候选假设，
          并将其转化为可检验、可复核的研究计划。
        </p>
        <div className="hero-actions mt-9 flex flex-wrap items-center justify-center gap-4">
          <button type="button" className="hero-cta hero-cta-primary" onClick={() => onFireCta("enter_workspace")}>
            进入研究工作区
          </button>
          <button
            type="button"
            className="hero-cta hero-cta-secondary"
            disabled={!q028Available}
            onClick={() => onFireCta("view_q028")}
            aria-label={q028Available ? "查看代表案例 Q028" : "代表案例暂不可用"}
          >
            查看代表案例
          </button>
        </div>
      </div>
    </section>
  );
}
