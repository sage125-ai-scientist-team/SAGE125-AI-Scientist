import { useRef } from "react";

import { AnimatedBeam } from "../components/magicui/animated-beam";
import { BeamNode } from "../components/BeamNode";
import { CardShell } from "../components/CardShell";

const CHAIN = ["科学问题", "证据", "候选假设", "可检验预测", "研究计划"];

/**
 * 能力卡 2：可验证研究。
 *
 * 科学问题 → 证据 → 候选假设 → 可检验预测 → 研究计划，
 * 用 Animated Beam 依次连接相邻节点，颜色 #4D7FFF → #2CC4D6，
 * 单轮动画 4-7 秒，透明度克制。节点均为纯文字胶囊，不含图标。
 */
export function ResearchBeamCard({ reducedMotion }: { reducedMotion: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = [
    useRef<HTMLDivElement>(null),
    useRef<HTMLDivElement>(null),
    useRef<HTMLDivElement>(null),
    useRef<HTMLDivElement>(null),
    useRef<HTMLDivElement>(null),
  ];

  return (
    <CardShell
      title="可验证研究"
      description="将候选假设转化为数据、变量、评价指标以及支持或否定条件明确的研究方案。"
      visual={
        <div
          ref={containerRef}
          className="relative flex h-full min-h-[120px] flex-wrap items-center justify-between gap-y-6 overflow-hidden rounded-xl px-4 py-6"
        >
          {CHAIN.map((label, i) => (
            <BeamNode
              key={label}
              ref={nodeRefs[i]}
              label={label}
              emphasis={i === 2}
              className="basis-[18%]"
            />
          ))}

          {!reducedMotion &&
            CHAIN.slice(0, -1).map((_, i) => (
              <AnimatedBeam
                key={`beam-${i}`}
                containerRef={containerRef}
                fromRef={nodeRefs[i]}
                toRef={nodeRefs[i + 1]}
                curvature={i % 2 === 0 ? 18 : -18}
                duration={5.5}
                delay={i * 0.3}
                gradientStartColor="#4D7FFF"
                gradientStopColor="#2CC4D6"
                reducedMotion={reducedMotion}
              />
            ))}
          {reducedMotion &&
            CHAIN.slice(0, -1).map((_, i) => (
              <AnimatedBeam
                key={`beam-static-${i}`}
                containerRef={containerRef}
                fromRef={nodeRefs[i]}
                toRef={nodeRefs[i + 1]}
                curvature={i % 2 === 0 ? 18 : -18}
                pathOpacity={0.22}
                reducedMotion
              />
            ))}
        </div>
      }
    />
  );
}
