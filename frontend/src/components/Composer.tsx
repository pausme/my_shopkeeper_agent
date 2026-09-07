/**
 * 聊天输入区组件
 * 处理问题输入、发送和停止当前流式请求
 */
import { ArrowUp, Square, WandSparkles, X } from "lucide-react";
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
            className="border-t border-ink/10 bg-parchment/80 px-4 py-4 backdrop-blur"
        >
            <div className="mx-auto flex max-w-5xl items-end gap-3 border border-ink/15 bg-white/75 p-2 shadow-panel">
                <div className="hidden h-11 w-11 shrink-0 place-items-center bg-moss/10 text-moss sm:grid">
                    <WandSparkles className="h-5 w-5" aria-hidden="true" />
                </div>
                <textarea
                    ref={textareaRef}
                    value={value}
                    // findings N11.22：与后端 500 上限一致，前端提前拦截避免 422
                    maxLength={500}
                    onChange={(event) => onChange(event.target.value)}
                    onKeyDown={onKeyDown}
                    rows={1}
                    placeholder={placeholder ?? "问一个电商数据问题..."}
                    className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-2 py-3 text-[15px] leading-6 text-ink outline-none placeholder:text-ink/35"
                />
                {/* findings N11.22：清空按钮 + 临近上限的字数提示 */}
                {value.length > 0 && !isStreaming && (
                    <button
                        type="button"
                        onClick={() => onChange("")}
                        className="grid h-7 w-7 shrink-0 place-items-center self-center rounded-full text-ink/35 transition hover:bg-ink/5 hover:text-ink"
                        title="清空输入"
                        aria-label="清空输入"
                    >
                        <X className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                )}
                {value.length > 420 && (
                    <span className="shrink-0 self-center font-mono text-[11px] text-ink/40">
                        {value.length}/500
                    </span>
                )}
                <button
                    type={isStreaming ? "button" : "submit"}
                    onClick={isStreaming ? onStop : undefined}
                    disabled={!isStreaming && disabled}
                    className={cn(
                        "grid h-11 w-11 shrink-0 place-items-center rounded-full text-white transition focus:outline-none focus:ring-2 focus:ring-moss/40 focus:ring-offset-2",
                        isStreaming
                            ? "bg-tomato hover:bg-tomato/90"
                            : "bg-ink hover:bg-soot disabled:cursor-not-allowed disabled:bg-ink/25",
                    )}
                    title={isStreaming ? "停止" : "发送"}
                    aria-label={isStreaming ? "停止" : "发送"}
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
