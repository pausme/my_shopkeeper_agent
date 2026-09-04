/**
 * Tailwind CSS 主题配置
 * C 端电商视觉体系：白底浅灰分层、品牌主色、价格强调色
 */
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          '"Noto Sans SC"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', "Consolas", "monospace"],
      },
      colors: {
        // 兼容旧 token
        parchment: "#f7f8fa",
        ink: "#1f2329",
        soot: "#14171a",
        moss: "#2563eb",
        brass: "#d97706",
        tomato: "#dc2626",
        mist: "#e5e7eb",
        // C 端新体系（N2.1 色彩规范）
        surface: "#ffffff",
        subtle: "#f5f6f8",
        line: "#e5e7eb",
        primary: "#2563eb",
        "primary-dark": "#1d4ed8",
        price: "#ea580c",
        risk: "#dc2626",
        good: "#16a34a",
      },
      boxShadow: {
        line: "0 1px 2px rgba(16, 24, 40, 0.06)",
        card: "0 1px 3px rgba(16, 24, 40, 0.1), 0 1px 2px rgba(16, 24, 40, 0.06)",
        panel: "0 24px 70px rgba(16, 24, 40, 0.22)",
      },
    },
  },
  plugins: [],
} satisfies Config;
