/**
 * 底部 composer（N12.5 对话页工作区）
 * 输入框与发送合并为一个固定工作区；停止按钮仅流式期间显示
 */
import { ArrowUp, Square, X } from "lucide-react";
import { FormEvent, KeyboardEvent, useRef } from "react";
import { cn } from "../lib/format";

type ComposerProps = {
    value: string;
    disabled: boolean;
    isStreaming: boolean;
    onChange: (value: string) => void;
    onSubmit: () => void;
    onStop: () => void;
    placeholder?: string;
};

export function Composer({
    value,
    disabled,
    isStreaming,
    onChange,
    onSubmit,
    onStop,
    placeholder,
}: ComposerProps) {
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);

    const submit = (event: FormEvent) => {
        event.preventDefault();
        if (!disabled) onSubmit();
    };

    const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            if (!disabled) onSubmit();
        }
    };

    return (
        <form
            onSubmit={submit}
            className="border-t border-line bg-white px-4 py-3 lg:px-8"
        >
            <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl2 border border-line bg-subtle p-2 shadow-card focus-within:border-primary/50">
                <textarea
                    ref={textareaRef}
                    value={value}
                    // findings N11.22：与后端 500 上限一致，前端提前拦截避免 422
                    maxLength={500}
                    onChange={(event) => onChange(event.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    placeholder={placeholder ?? "继续描述你的需求..."}
                    aria-label="继续提问"
                    className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-[15px] leading-6 text-ink outline-none placeholder:text-ink/35"
                />
                {/* findings N11.22：清空按钮 + 临近上限的字数提示 */}
                {value.length > 0 && !isStreaming && (
                    <button
                        type="button"
                        onClick={() => onChange("")}
                        className="grid h-7 w-7 shrink-0 place-items-center self-center rounded-full text-ink/35 transition hover:bg-ink/5 hover:text-ink active:scale-[0.98]"
                        title="清空输入"
                        aria-label="清空输入"
                    >
                        <X className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                )}
                {value.length > 420 && (
                    <span className="shrink-0 self-center font-mono text-[11px] tabular-nums text-ink/40">
                        {value.length}/500
                    </span>
                )}
                <button
                    type={isStreaming ? "button" : "submit"}
                    onClick={isStreaming ? onStop : undefined}
                    disabled={!isStreaming && disabled}
                    className={cn(
                        "grid h-10 w-10 shrink-0 place-items-center rounded-full text-white transition active:scale-[0.98]",
                        isStreaming
                            ? "bg-risk hover:bg-risk/90"
                            : "bg-primary hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50",
                    )}
                    title={isStreaming ? "停止本次导购" : "发送"}
                    aria-label={isStreaming ? "停止本次导购" : "发送"}
                >
                    {isStreaming ? (
                        <Square
                            className="h-4 w-4 fill-current"
                            aria-hidden="true"
                        />
                    ) : (
                        <ArrowUp className="h-5 w-5" aria-hidden="true" />
                    )}
                </button>
            </div>
        </form>
    );
}
