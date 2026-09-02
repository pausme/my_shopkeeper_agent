/**
 * 智能体执行流程图组件
 * 按 LangGraph 节点拓扑展示各步骤状态与耗时
 * 拓扑与后端 graph.py 保持一致：关键词抽取 → 检索词扩展 → 三路召回 → 合并 →
 * 双路过滤 → 额外上下文 → 生成 → 校验 ⇄ 修正（重试 ≤3 次）→ 执行
 */
import { Check, Circle, LoaderCircle, X } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "../lib/format";
import type { ProgressStatus, StepState } from "../types/agent";

type FlowStatus = ProgressStatus | "pending";

type FlowNode = {
  step: string;
  x: number;
  y: number;
  w?: number;
};

const nodes: FlowNode[] = [
  { step: "抽取关键词", x: 410, y: 20 },
  { step: "扩展检索词", x: 410, y: 116 },
  { step: "召回字段信息", x: 150, y: 212 },
  { step: "召回指标信息", x: 410, y: 212 },
  { step: "召回字段取值", x: 670, y: 212 },
  { step: "合并召回信息", x: 410, y: 308 },
  { step: "添加额外上下文", x: 410, y: 404, w: 176 },
  { step: "生成SQL", x: 410, y: 500 },
  { step: "校验SQL", x: 410, y: 596 },
  { step: "校正SQL", x: 670, y: 596 },
  { step: "执行SQL", x: 410, y: 692 },
];

const connectors = [
  "M410 60 L410 112",
  "M410 156 L410 184 L150 184 L150 208",
  "M410 156 L410 208",
  "M410 156 L410 184 L670 184 L670 208",
  "M150 252 L150 278 L410 278 L410 304",
  "M410 252 L410 304",
  "M670 252 L670 278 L410 278 L410 304",
  "M410 348 L410 400",
  "M410 444 L410 496",
  "M410 540 L410 592",
  "M410 636 L410 688",
  "M488 616 L588 616",
  // 校正 SQL 后回到校验节点重新校验，形成修正闭环
  "M670 592 L670 574 L500 574 L500 616 L492 616",
];

const branchLabels = [
  { text: "无误", x: 358, y: 668 },
  { text: "有误", x: 524, y: 604 },
  { text: "重试 ≤3 次", x: 528, y: 564 },
  { text: "超限则终止", x: 608, y: 649 },
];

function getStatusMap(steps: StepState[]) {
  return steps.reduce<Record<string, StepState>>((map, item) => {
    map[item.step] = item;
    return map;
  }, {});
}

function statusFor(step: string, map: Record<string, StepState>): FlowStatus {
  return map[step]?.status ?? "pending";
}

function formatElapsed(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m${seconds % 60}s`;
}

function NodeIcon({ status }: { status: FlowStatus }) {
  if (status === "running") {
    return <LoaderCircle className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />;
  }

  if (status === "success") {
    return <Check className="h-3.5 w-3.5" aria-hidden="true" />;
  }

  if (status === "error") {
    return <X className="h-3.5 w-3.5" aria-hidden="true" />;
  }

  return <Circle className="h-3.5 w-3.5" aria-hidden="true" />;
}

function NodeElapsed({
  status,
  state,
  now,
}: {
  status: FlowStatus;
  state?: StepState;
  now: number;
}) {
  if (!state?.startedAt || status === "pending") return null;

  const end = status === "running" ? now : state.updatedAt;
  const seconds = Math.round((end - state.startedAt) / 1000);
  if (seconds < 1) return null;

  return (
    <span
      className={cn(
        "shrink-0 font-mono text-[11px] font-normal",
        status === "running" ? "text-brass" : "text-ink/40",
      )}
    >
      {formatElapsed(seconds)}
    </span>
  );
}

function FlowNodeCard({
  node,
  status,
  state,
  now,
}: {
  node: FlowNode;
  status: FlowStatus;
  state?: StepState;
  now: number;
}) {
  const width = node.w ?? 156;

  return (
    <div
      className="absolute -translate-x-1/2"
      style={{ left: node.x, top: node.y, width }}
    >
      <div
        className={cn(
          "flex h-10 items-center gap-2 border px-3 text-sm font-semibold shadow-line transition",
          status === "pending" && "border-ink/10 bg-white/55 text-ink/45",
          status === "running" && "border-brass/45 bg-brass/15 text-ink",
          status === "success" && "border-moss/25 bg-moss/10 text-ink",
          status === "error" && "border-tomato/35 bg-tomato/10 text-tomato",
        )}
      >
        <span
          className={cn(
            "grid h-6 w-6 shrink-0 place-items-center rounded-full",
            status === "pending" && "bg-ink/5 text-ink/35",
            status === "running" && "bg-brass/20 text-brass",
            status === "success" && "bg-moss/15 text-moss",
            status === "error" && "bg-tomato/15 text-tomato",
          )}
        >
          <NodeIcon status={status} />
        </span>
        <span className="min-w-0 flex-1 truncate">{node.step}</span>
        <NodeElapsed status={status} state={state} now={now} />
      </div>
    </div>
  );
}

export function StepRail({ steps = [] }: { steps?: StepState[] }) {
  const statusMap = getStatusMap(steps);
  const hasRunning = steps.some((item) => item.status === "running");

  // 有步骤运行中时每秒刷新一次，驱动耗时实时跳动
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!hasRunning) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [hasRunning]);

  if (steps.length === 0) return null;

  return (
    <section className="mt-4 border border-ink/10 bg-white/40 px-3 py-4 shadow-line">
      <div className="mb-3 flex items-center justify-between gap-3 px-1">
        <div className="text-sm font-semibold text-ink">执行流程</div>
        <div className="text-xs text-ink/45">LangGraph</div>
      </div>

      <div className="overflow-x-auto">
        <div className="relative mx-auto h-[744px] w-[820px]">
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox="0 0 820 744"
            fill="none"
            aria-hidden="true"
          >
            <defs>
              <marker
                id="flow-arrow"
                markerHeight="8"
                markerWidth="8"
                orient="auto"
                refX="6"
                refY="4"
              >
                <path d="M0 0 L8 4 L0 8 Z" fill="rgba(32,32,29,0.58)" />
              </marker>
            </defs>
            {connectors.map((path) => (
              <path
                key={path}
                d={path}
                stroke="rgba(32,32,29,0.5)"
                strokeWidth="1.5"
                markerEnd="url(#flow-arrow)"
              />
            ))}
            {branchLabels.map((label) => (
              <text
                key={label.text}
                x={label.x}
                y={label.y}
                fill="rgba(32,32,29,0.62)"
                fontSize="13"
                fontWeight="600"
              >
                {label.text}
              </text>
            ))}
          </svg>

          {nodes.map((node) => (
            <FlowNodeCard
              key={node.step}
              node={node}
              status={statusFor(node.step, statusMap)}
              state={statusMap[node.step]}
              now={now}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
