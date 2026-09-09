/**
 * Tailwind CSS 主题配置
 * 「购买决策台」视觉体系（N12.1）：安静可靠、信息清楚、决策优先。
 * 策略：旧语义 token（primary/ink/subtle/line/price/risk/good/brass）统一
 * 映射到新色值，组件类名不改即可整体换肤；新代码直接用语义名。
 */
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // N12.2/N12.23：拉丁/数字 IBM Plex Sans，中文 Chiron Hei HK；
        // CJK 仅此一个 webfont，系统字体作回退（不保留 Google CJK）
        sans: [
          '"IBM Plex Sans"',
          '"Chiron Hei HK"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', "Consolas", "monospace"],
      },
      colors: {
        // 兼容旧语义 token（N12.1 换肤映射）
        surface: "#FFFFFF",
        subtle: "#F3F6F4", // 页面背景 ui-bg
        soft: "#EAF0EC", // 次级区域 ui-surface-subtle
        warm: "#FFF9F3", // 价格/预算提示区 ui-surface-warm
        line: "#D7E0DB", // ui-border
        primary: "#1F5D4B", // 深桉树绿
        "primary-dark": "#17483A",
        "primary-soft": "#E1F0EA",
        price: "#B84A27",
        risk: "#B42318",
        good: "#1F7A4D",
        warning: "#A96B14",
        brass: "#A96B14", // 旧谨慎/待确认色并入 ui-warning
        ink: "#18221F",
        muted: "#53635C", // N12.22：辅助文字（浅底对比度 ≥4.5:1，替代 ink/40）
        focus: "#2F8F72",
        // 极少数历史残留 token，映射到近似新值防破
        parchment: "#F3F6F4",
        soot: "#18221F",
        moss: "#1F5D4B",
        tomato: "#B42318",
        mist: "#D7E0DB",
      },
      borderRadius: {
        xl2: "10px", // 卡片/输入框
        xl3: "12px", // 抽屉
      },
      boxShadow: {
        line: "0 1px 2px rgba(24, 34, 31, 0.06)",
        card: "0 1px 3px rgba(24, 34, 31, 0.08)",
        panel: "0 12px 32px rgba(24, 34, 31, 0.16)",
        drawer: "-12px 0 32px rgba(24, 34, 31, 0.16)",
      },
    },
  },
  plugins: [],
} satisfies Config;
