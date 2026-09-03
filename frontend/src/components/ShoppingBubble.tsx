/**
 * 导购消息气泡
 * 渲染用户提问、追问气泡、推荐结果（商品卡片组）、对比表与错误
 */
import { Bot, HelpCircle, UserRound } from "lucide-react";
import { ComparisonTable } from "./ComparisonTable";
import { ProductCard } from "./ProductCard";
import { cn } from "../lib/format";
import type { ShoppingMessage } from "../types/shopping";

type ShoppingBubbleProps = {
  message: ShoppingMessage;
  onFeedback?: (feedbackType: string, productId: string, messageId: string) => void;
  onProductClick?: (productId: string, messageId: string) => void;
  /** 点击追问快捷选项（直接作为新一轮提问发出） */
  onOptionClick?: (option: string) => void;
};

export function ShoppingBubble({
  message,
  onFeedback,
  onProductClick,
  onOptionClick,
}: ShoppingBubbleProps) {
  const isUser = message.role === "user";

  return (
    <article className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-moss text-white">
          <Bot className="h-4 w-4" aria-hidden="true" />
        </div>
      )}

      <div className="max-w-[880px] flex-1">
        <div
          className={cn(
            "border px-5 py-4 shadow-line",
            isUser && "border-ink/80 bg-ink text-parchment",
            !isUser && message.kind !== "error" && "border-ink/10 bg-[#fffaf1]/78 backdrop-blur",
            !isUser && message.kind === "error" && "border-tomato/30 bg-tomato/10",
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

          {/* 进度占位 */}
          {message.kind === "progress" && (
            <div className="text-sm text-ink/60">
              <p>{message.content}</p>
              {message.steps && message.steps.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {message.steps.map((step) => (
                    <span
                      key={step}
                      className="border border-brass/30 bg-brass/10 px-2 py-0.5 text-[11px] text-ink/70"
                    >
                      {step}
                    </span>
                  ))}
                </div>
              )}
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
                      onProductClick={
                        onProductClick
                          ? (productId) => onProductClick(productId, message.messageId ?? "")
                          : undefined
                      }
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
