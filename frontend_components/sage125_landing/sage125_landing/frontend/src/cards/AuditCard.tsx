import { AnimatedList } from "../components/magicui/animated-list";
import { CardShell } from "../components/CardShell";

/**
 * 能力卡 4：开放与透明。
 *
 * 展示真实产物类型与结构性状态说明，不显示虚假 PASS 数量。
 */
const ARTIFACTS: { file: string; status: string }[] = [
  { file: "result.json", status: "结构化结果" },
  { file: "evidence_cards.json", status: "证据来源" },
  { file: "validation.json", status: "质量门" },
  { file: "provider_audit.json", status: "调用审计" },
  { file: "checksums.sha256", status: "文件校验" },
];

export function AuditCard({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <CardShell
      title="开放与透明"
      description="保留版本差异、运行轨迹、质量门结果、调用审计与可复现产物。"
      visual={
        <div className="flex h-full items-center justify-center overflow-hidden rounded-xl px-3 py-2">
          <AnimatedList
            className="w-full"
            delay={2400}
            maxVisible={4}
            reducedMotion={reducedMotion}
          >
            {ARTIFACTS.map((item) => (
              <div
                key={item.file}
                className="mb-2 flex w-full items-center justify-between gap-3 rounded-lg border border-[rgba(124,164,217,0.18)] bg-[rgba(20,36,58,0.55)] px-3 py-2"
              >
                <span className="truncate text-[13px] font-mono text-[#DCE6F5]">{item.file}</span>
                <span className="shrink-0 text-[12px] text-[#8192A9]">{item.status}</span>
              </div>
            ))}
          </AnimatedList>
        </div>
      }
    />
  );
}
