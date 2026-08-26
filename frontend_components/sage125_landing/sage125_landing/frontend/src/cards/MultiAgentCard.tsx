import { useRef } from "react";

import { AnimatedBeam } from "../components/magicui/animated-beam";
import { BeamNode } from "../components/BeamNode";
import { CardShell } from "../components/CardShell";

const SPOKES: { key: string; label: string; style: React.CSSProperties }[] = [
  { key: "search", label: "文献检索", style: { top: "6%", left: "50%", transform: "translate(-50%, 0)" } },
  { key: "verify", label: "证据核验", style: { top: "28%", left: "88%", transform: "translate(-50%, -50%)" } },
  { key: "review", label: "科学评审", style: { top: "78%", left: "78%", transform: "translate(-50%, -50%)" } },
  { key: "plan", label: "研究计划", style: { top: "78%", left: "22%", transform: "translate(-50%, -50%)" } },
  { key: "hypothesis", label: "假设生成", style: { top: "28%", left: "12%", transform: "translate(-50%, -50%)" } },
];

/**
 * 能力卡 3：多智能体协同。
 *
 * 中心节点“研究任务”与 5 个围绕节点之间用低透明度静态连线表示“围绕同一
 * 证据上下文协作”；核心协作链路（证据核验 → 假设生成 → 科学评审 → 研究计划，
 * 评审可反向连接假设生成）用 Animated Beam 做克制的流光强调，避免整卡
 * 变成满屏乱动的网络拓扑。
 */
export function MultiAgentCard({ reducedMotion }: { reducedMotion: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const centerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLDivElement>(null);
  const verifyRef = useRef<HTMLDivElement>(null);
  const reviewRef = useRef<HTMLDivElement>(null);
  const planRef = useRef<HTMLDivElement>(null);
  const hypothesisRef = useRef<HTMLDivElement>(null);

  const refByKey: Record<string, React.RefObject<HTMLDivElement | null>> = {
    search: searchRef,
    verify: verifyRef,
    review: reviewRef,
    plan: planRef,
    hypothesis: hypothesisRef,
  };

  return (
    <CardShell
      title="多智能体协同"
      description="不同智能体围绕同一证据上下文协作，并将评审意见和未关闭问题带入后续修订。"
      visual={
        <div
          ref={containerRef}
          className="relative h-full min-h-[140px] overflow-hidden rounded-xl"
        >
          {/* 中心节点到 5 个周围节点的静态低透明度连线：表示“同一证据上下文”。 */}
          {SPOKES.map((spoke) => (
            <AnimatedBeam
              key={`spoke-${spoke.key}`}
              containerRef={containerRef}
              fromRef={centerRef}
              toRef={refByKey[spoke.key]}
              pathOpacity={0.14}
              pathColor="#c7d5f5"
              reducedMotion
            />
          ))}

          {/* 核心协作链路：证据核验 → 假设生成 → 科学评审 → 研究计划。 */}
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={verifyRef}
            toRef={hypothesisRef}
            curvature={-14}
            duration={5}
            reducedMotion={reducedMotion}
          />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={hypothesisRef}
            toRef={reviewRef}
            curvature={14}
            duration={5.5}
            delay={0.4}
            reducedMotion={reducedMotion}
          />
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={reviewRef}
            toRef={planRef}
            curvature={-10}
            duration={5}
            delay={0.8}
            reducedMotion={reducedMotion}
          />
          {/* 评审 → 假设生成：反向连接，强调评审意见回流。 */}
          <AnimatedBeam
            containerRef={containerRef}
            fromRef={reviewRef}
            toRef={hypothesisRef}
            curvature={16}
            duration={6.5}
            delay={0.2}
            reverse
            pathOpacity={0.16}
            reducedMotion={reducedMotion}
          />

          <BeamNode
            ref={centerRef}
            label="研究任务"
            emphasis
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
          />
          {SPOKES.map((spoke) => (
            <BeamNode
              key={spoke.key}
              ref={refByKey[spoke.key]}
              label={spoke.label}
              className="absolute"
              style={spoke.style}
            />
          ))}
        </div>
      }
    />
  );
}
