# 竞品参考板（N1.1）

> 用途：前端 C 端导购体验的对标基线。每家列「入口形态 / 核心交互 / 信任与转化设计 / 对 PickMate 的启示」。
> 截图来源：下方各官方/媒体链接的页面配图可直接取证；本仓库自身截图基线在 `frontend/e2e/__screenshots__/`（1024/1440/1920 三宽度）。
> 整理时间：2026-09-08。竞品形态变化快，落地某项前建议重新核对来源链接。

## 1. Amazon Rufus（2026-05 起更名 "Alexa for Shopping"）

- 来源：[About Amazon：Rufus 个性化升级](https://www.aboutamazon.com/news/retail/amazon-rufus-ai-assistant-personalized-shopping-features)、[Tinuiti：Alexa for Shopping](https://tinuiti.com/blog/amazon/alexa-for-shopping/)、[AMALYTIX 指南](https://www.amalytix.com/en/knowledge/ai/amazon-rufus-guide-2026/)
- 入口形态：内嵌在购物 App 搜索框与商品详情页的对话式助手，不是独立站点。
- 核心交互：
  - 按「活动 / 场合 / 用途」找货（"camping with toddlers" 这类自然语言）；
  - **Help Me Decide**：在两款商品间直接给"为什么选 A 不选 B"的结论式对比，语言取自商品 listing；
  - 价格历史追踪 + 降价提醒；对话式复购（reorder）。
- 信任与转化：结论锚定 listing 原文；可代客加购（agentic）。
- 对 PickMate 的启示：
  - ✅ 已对齐：结论式对比（对比表+一句结论）、降价提醒（S2 watchlist）、场景化入口（首页场景卡）。
  - 🎯 差距项：对比结论还没有"为什么选 A 不选 B"的逐维度胜出归因；价格历史曲线缺失（远期）。

## 2. Google Shopping（AI Mode / Gemini）

- 来源：[Google Blog：Shop with AI Mode 与虚拟试穿](https://blog.google/products-and-platforms/products/shopping/google-shopping-ai-mode-virtual-try-on-update/)、[Google Try-On 工具说明](https://support.google.com/googleshopping/answer/16253678?hl=en)、[Shopify：Google AI Shopping 指南](https://www.shopify.com/blog/google-ai-shopping)
- 入口形态：搜索结果内的 AI Mode 购物面板 + [google.com/shopping/tryon](https://www.google.com/shopping/tryon) 独立试穿工具。
- 核心交互：
  - 上传照片虚拟试穿（Gemini 图像模型，多体型/多尺码）；
  - AI Mode 内跨商家比价、价格追踪、优惠聚合；
  - agentic checkout（AI 代下单，2025 起逐步开放）。
- 信任与转化：跨站价格并排展示；"AI 生成图"明确标注。
- 对 PickMate 的启示：
  - ✅ 已对齐：跨来源信息聚合展示、"演示数据"来源标注（N11.21）。
  - 🎯 差距项：无图片类交互（品类以小家电/家居为主，试穿不适用）；无真实多商家比价（依赖真实电商数据接入，见 TODO N11.21 遗留）。

## 3. Perplexity Shopping

- 来源：[官方博客：Shop like a Pro](https://www.perplexity.ai/hub/blog/shop-like-a-pro)、[官方博客：Shopping That Puts You First](https://www.perplexity.ai/hub/blog/shopping-that-puts-you-first)、[The Verge 报道](https://www.theverge.com/2024/11/18/24299574/perplexity-ai-search-engine-buy-products)、[2026 商家计划指南](https://alhena.ai/blog/perplexity-shopping-merchants-setup-guide/)
- 入口形态：购物类问题触发的商品卡流 + 站内下单（Buy with Pro，PayPal 结算）。
- 核心交互：
  - 问题 → 客观回答 + **可购物商品卡**（图、价、卖家、评分）；
  - Buy with Pro 一键购买（免运费由平台补贴）；
  - 商家保持 record of record、100% 收入归商家。
- 信任与转化：卡片信息密度高；引用可溯源；中立立场声明。
- 对 PickMate 的启示：
  - ✅ 已对齐：商品卡（图/价/评分/理由/风险标签）、理由可溯源（M6.3）、中立提示（演示数据标注）。
  - 🎯 差距项：无站内购买闭环（PickMate 定位决策助手，购买闭环不在二期范围）；商品卡缺少"卖家/货源"维度。

## 4. Klarna AI 购物助手

- 来源：[Klarna：ChatGPT 内 Shopping Search 应用](https://www.klarna.com/international/press/klarna-launches-ai-powered-shopping-search-app-in-chatgpt/)、[OpenAI 客户案例](https://openai.com/index/klarna/)、[2026 AI 助手盘点](https://fluxgrowth.io/)
- 入口形态：App 内对话助手 + ChatGPT 内嵌 Shopping Search 应用 + 拍照搜索。
- 核心交互：
  - 偏好驱动的对话式搜索（预算/品牌/风格偏好追问）；
  - 类目与品牌横向对比、客户评价聚合；
  - 拍照找同款比价（snap, search and shop）；可购物短视频。
- 信任与转化：价格历史展示；AI 客服承接售后（退换/账单）。
- 对 PickMate 的启示：
  - ✅ 已对齐：偏好驱动（S1 偏好中心）、品牌/类目对比、评价证据展示（N6.2）。
  - 🎯 差距项：无图片输入（多模态，远期）；价格历史可视化缺失。

## 横向小结：四个可复用的设计共识

1. **对话内嵌而非独立工具**——入口都在"用户表达需求"的地方（搜索框/详情页），PickMate 已走此路线（首页搜索前置）。
2. **结论优先**——先给"买哪个、为什么"，再给可展开的证据（对比表/评价摘要），对应 PickMate 的推荐卡+对比表分层。
3. **价格与降价是标配**——四家都有价格追踪/降价提醒；PickMate S2 已有提醒，价格历史曲线是下一档。
4. **来源可溯 + AI 生成标注**——引用真实数据并明示 AI 生成/演示属性；PickMate 的"演示数据"标注与理由白名单是同方向实践。
