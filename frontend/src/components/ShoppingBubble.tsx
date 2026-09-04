/**
 * 导购消息气泡
 * 渲染用户提问、追问气泡、推荐结果（商品卡片组）、对比表与错误
 */
import { Bot, HelpCircle, UserRound } from "lucide-react";
import { ComparisonTable } from "./ComparisonTable";
import { ProductCard } from "./ProductCard";
import { SkeletonCards } from "./SkeletonCards";
import { cn } from "../lib/format";
import type { RecommendedProduct, ShoppingMessage } from "../types/shopping";

type ShoppingBubbleProps = {
  message: ShoppingMessage;
  onFeedback?: (feedbackType: string, productId: string, messageId: string) => void;
  onProductClick?: (productId: string, action: string) => void;
  /** 点击追问快捷选项（直接作为新一轮提问发出） */
  onOptionClick?: (option: string) => void;
  onDetail?: (productId: string) => void;
  onCompare?: (productId: string) => void;
  onAsk?: (productId: string, title: string) => void;
  compareIds?: string[];
  /** 对比表上方结论（取自同轮推荐总结） */
  conclusion?: string;
};

export function ShoppingBubble({
  message,
  onFeedback,
  onProductClick,
  onOptionClick,
  onDetail,
  onCompare,
  onAsk,
  compareIds = [],
  conclusion,
}: ShoppingBubbleProps) {
  const isUser = message.role === "user";

  return (
    <article className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-primary text-white">
          <Bot className="h-4 w-4" aria-hidden="true" />
        </div>
      )}

      <div className="max-w-[880px] flex-1">
        <div
          className={cn(
            "border px-5 py-4 shadow-line",
            isUser && "border-primary bg-primary text-white",
            !isUser && message.kind !== "error" && "border-line bg-white shadow-card",
            !isUser && message.kind === "error" && "border-risk/30 bg-risk/5",
          )}
        >
          {/* 追问气泡 + 快捷选项（PRD 10.2：提供快捷选项，允许跳过） */}
          {message.kind === "clarification" && (
            <div>
              <p className="flex items-start gap-2 text-[15px] leading-7 text-ink">
                <HelpCircle className="mt-1 h-4 w-4 shrink-0 text-brass" aria-hidden="true" />
                {message.content}
              </p>
              {message.options && message.options.length > 0 && onOptionClick && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {message.options.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => onOptionClick(option)}
                      className="border border-moss/35 bg-white/70 px-3 py-1.5 text-xs font-semibold text-ink/75 transition hover:border-moss/60 hover:bg-moss/10"
                    >
                      {option}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 进度：紧凑 stepper + 骨架屏（N7.4/N7.5） */}
          {message.kind === "progress" && (
            <div>
              <p className="text-sm text-ink/60">{message.content}</p>
              {message.steps && message.steps.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {message.steps.map((step, index) => (
                    <span key={step} className="inline-flex items-center gap-1.5">
                      {index > 0 && <span className="h-3 w-px bg-line" />}
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[11px]",
                          index === message.steps!.length - 1
                            ? "bg-primary/10 font-semibold text-primary"
                            : "bg-subtle text-ink/45",
                        )}
                      >
                        {step}
                      </span>
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-3">
                <SkeletonCards />
              </div>
            </div>
          )}

          {/* 错误 */}
          {message.kind === "error" && (
            <p className="text-sm text-tomato">
              {message.content}
              {message.error ? `：${message.error}` : ""}
            </p>
          )}

          {/* 纯文本（历史会话回放） */}
          {message.kind === "text" && (
            <p className="whitespace-pre-wrap text-[15px] leading-7 text-ink">{message.content}</p>
          )}

          {/* 推荐结果 */}
          {message.kind === "recommendation" && (
            <div>
              <p className="text-[15px] leading-7 text-ink">{message.content}</p>
              {message.products && message.products.length > 0 && (
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {message.products.map((product) => (
                    <ProductCard
                      key={product.product_id}
                      product={product}
                      onFeedback={
                        onFeedback
                          ? (feedbackType, productId) =>
                              onFeedback(feedbackType, productId, message.messageId ?? "")
                          : undefined
                      }
                      onProductClick={onProductClick}
                      onDetail={onDetail}
                      onCompare={onCompare}
                      onAsk={onAsk}
                      inCompare={compareIds.includes(product.product_id)}
                    />
                  ))}
                </div>
              )}
              {message.nextQuestion && (
                <p className="mt-3 border-l-2 border-brass/50 pl-2 text-xs leading-5 text-ink/65">
                  可以继续告诉我：{message.nextQuestion}
                </p>
              )}
            </div>
          )}

          {/* 对比表 */}
          {message.kind === "comparison" && message.comparison && (
            <ComparisonTable
              headers={message.comparison.headers}
              rows={message.comparison.rows}
              conclusion={conclusion}
            />
          )}
        </div>
      </div>

      {isUser && (
        <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-parchment">
          <UserRound className="h-4 w-4" aria-hidden="true" />
        </div>
      )}
    </article>
  );
}
