import { AnimatedList } from "../components/magicui/animated-list";
import { CardShell } from "../components/CardShell";

/**
 * 能力卡 1：可追溯证据。
 *
 * 使用结构示意文字（文献来源 / 原文片段 / 定位信息 / EvidenceCard / 内容
 * 校验，§9 固定内容），不展示虚假论文题名或伪造的具体数量——首页尚未
 * 加载具体题目上下文时，这是任务规格明确允许的展示方式。
 */
const EVIDENCE_STEPS: { label: string; detail: string }[] = [
  { label: "文献来源", detail: "DOI / 出版物元数据已核验" },
  { label: "原文片段", detail: "已定位于章节 / 段落" },
  { label: "定位信息", detail: "页码 · 章节 · 偏移量" },
  { label: "EvidenceCard", detail: "结构化证据卡片" },
  { label: "内容校验", detail: "SHA-256 校验和" },
];

export function EvidenceCard({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <CardShell
      title="可追溯证据"
      description="每项事实和候选假设均保留文献来源、原文片段、定位信息与内容校验和。"
      visual={
        <div className="flex h-full items-center justify-center overflow-hidden rounded-xl px-3 py-2">
          <AnimatedList className="w-full" delay={2600} maxVisible={4} reducedMotion={reducedMotion}>
            {EVIDENCE_STEPS.map((step) => (
              <div
                key={step.label}
                className="mb-2 flex w-full items-center justify-between gap-3 rounded-lg border border-[rgba(124,164,217,0.18)] bg-[rgba(20,36,58,0.55)] px-3 py-2"
              >
                <span className="text-[13px] font-medium text-[#DCE6F5]">{step.label}</span>
                <span className="text-[12px] text-[#8192A9]">{step.detail}</span>
              </div>
            ))}
          </AnimatedList>
        </div>
      }
    />
  );
}
