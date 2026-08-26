import { GlareHover } from "./magicui/glare-hover";
import { MagicCard } from "./magicui/magic-card";
import { NoiseTexture } from "./magicui/noise-texture";
import { NumberTicker } from "./magicui/number-ticker";
import type { CoverageStatus, StatsStatus } from "../types";

export interface StatsRowProps {
  questionCount: number | null;
  evidenceCount: number | null;
  planCount: number | null;
  coverage: number | null;
  coverageStatus: CoverageStatus;
  statsStatus: StatsStatus;
}

type MetricDisplay =
  | { kind: "skeleton" }
  | { kind: "text"; text: string }
  | { kind: "number"; value: number; decimals?: number; suffix?: string };

function numericDisplay(status: StatsStatus, value: number | null): MetricDisplay {
  if (status === "loading") return { kind: "skeleton" };
  if (status === "error" || value === null) return { kind: "text", text: "数据异常" };
  return { kind: "number", value };
}

function coverageDisplay(status: StatsStatus, coverage: number | null, coverageStatus: CoverageStatus): MetricDisplay {
  if (status === "loading") return { kind: "skeleton" };
  if (status === "error") return { kind: "text", text: "数据异常" };
  if (coverageStatus === "unavailable") return { kind: "text", text: "未计算" };
  if (coverage === null) return { kind: "text", text: "数据异常" };
  return { kind: "number", value: coverage, decimals: 1, suffix: "%" };
}

export function StatsRow({
  questionCount,
  evidenceCount,
  planCount,
  coverage,
  coverageStatus,
  statsStatus,
}: StatsRowProps) {
  const items: { label: string; hint: string; display: MetricDisplay }[] = [
    { label: "官方科学问题", hint: "官方锁定 Catalog 唯一题号", display: numericDisplay(statsStatus, questionCount) },
    { label: "可追溯证据", hint: "有效 EvidenceCard 去重计数", display: numericDisplay(statsStatus, evidenceCount) },
    { label: "研究计划", hint: "结构化完整研究计划", display: numericDisplay(statsStatus, planCount) },
    { label: "证据回链覆盖", hint: "可解析引用占比", display: coverageDisplay(statsStatus, coverage, coverageStatus) },
  ];

  return (
    <div className="metric-grid">
      {items.map((item) => (
        <article key={item.label} className="metric-card">
          <div className="metric-card-surface" />
          <NoiseTexture className="metric-card-noise" />
          <div className="metric-card-highlight" />
          <GlareHover className="metric-card-highlight" glareOpacity={0.08} duration={900} />
          <MagicCard className="metric-card-content h-full">
            <div className="flex h-full flex-col justify-center gap-1 px-4 py-5 text-left">
              {item.display.kind === "skeleton" ? (
                <span className="metric-skeleton" aria-hidden="true" />
              ) : item.display.kind === "text" ? (
                <span className="font-latin text-[28px] font-semibold tracking-tight text-[#F3F7FF] lg:text-[34px]">
                  {item.display.text}
                </span>
              ) : (
                <span className="font-latin text-[28px] font-semibold tracking-tight text-[#F3F7FF] lg:text-[34px]">
                  <NumberTicker
                    value={item.display.value}
                    startValue={item.display.value}
                    decimalPlaces={item.display.decimals ?? 0}
                    suffix={item.display.suffix ?? ""}
                  />
                </span>
              )}
              <span className="text-[14px] text-[#9EB0C7] sm:text-[15px]">{item.label}</span>
              <span className="text-[12px] text-[#71849D]">{item.hint}</span>
            </div>
          </MagicCard>
        </article>
      ))}
    </div>
  );
}
