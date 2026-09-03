/**
 * 登录/注册对话框组件
 * 简单的用户名密码认证；登录态由 JWT 维持，存于 localStorage
 */
import { FormEvent, useState } from "react";
import { LogIn, UserPlus, X } from "lucide-react";
import { login, register } from "../lib/authApi";

type AuthDialogProps = {
  onClose: () => void;
  onAuthed: (token: string, username: string) => void;
};

export function AuthDialog({ onClose, onAuthed }: AuthDialogProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result =
        mode === "login"
          ? await login(username.trim(), password)
          : await register(username.trim(), password);
      onAuthed(result.token, result.username);
    } catch (err) {
      setError(err instanceof Error ? err.message : "请求失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 backdrop-blur-sm">
      <form
        onSubmit={submit}
        className="w-[360px] max-w-[92vw] border border-ink/15 bg-parchment p-6 shadow-panel"
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="text-base font-semibold text-ink">
            {mode === "login" ? "登录" : "注册新账号"}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-ink/45 transition hover:bg-ink/5 hover:text-ink"
            aria-label="关闭"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <label className="mb-1 block text-xs font-semibold text-ink/60">用户名</label>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          className="mb-3 w-full border border-ink/15 bg-white/70 px-3 py-2 text-sm outline-none focus:border-moss/50"
          placeholder="2~64 个字符"
          autoFocus
        />

        <label className="mb-1 block text-xs font-semibold text-ink/60">密码</label>
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mb-4 w-full border border-ink/15 bg-white/70 px-3 py-2 text-sm outline-none focus:border-moss/50"
          placeholder="至少 6 位"
        />

        {error && (
          <div className="mb-3 border border-tomato/30 bg-tomato/10 px-3 py-2 text-xs text-tomato">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={busy || username.trim().length < 2 || password.length < 6}
          className="flex h-10 w-full items-center justify-center gap-2 bg-ink text-sm font-semibold text-parchment transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-ink/30"
        >
          {mode === "login" ? (
            <LogIn className="h-4 w-4" aria-hidden="true" />
          ) : (
            <UserPlus className="h-4 w-4" aria-hidden="true" />
          )}
          {busy ? "请稍候..." : mode === "login" ? "登录" : "注册并登录"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-3 w-full text-center text-xs text-ink/55 transition hover:text-ink"
        >
          {mode === "login" ? "还没有账号？去注册" : "已有账号？去登录"}
        </button>
      </form>
    </div>
  );
}
