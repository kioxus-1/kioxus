# AI/Agent 项目官方文档风格与结构对比分析报告

> 研究日期: 2026-08-30  
> 研究对象: OpenClaw, Claude Code, OpenAI Codex, Hermes, DeepSeek

---

## 一、项目概览

| 项目 | 类型 | 文档站点 | 文档框架 |
|------|------|---------|---------|
| **OpenClaw** | 自托管多通道 AI Agent 网关 | docs.openclaw.ai | Mintlify (docs.json) |
| **Claude Code** | Anthropic 官方终端/IDE 编码 Agent | docs.anthropic.com/en/docs/claude-code | Next.js (自定义) |
| **OpenAI Codex** | OpenAI 官方本地编码 Agent (CLI + Web) | developers.openai.com/codex + GitHub README | 自定义站点 + GitHub Markdown |
| **Hermes** | OpenClaw 前身/竞品 Agent 框架 | 无独立文档站（已被 OpenClaw 迁移文档覆盖） | N/A |
| **DeepSeek** | DeepSeek API 及 Harness | api-docs.deepseek.com | Docusaurus v3 |

---

## 二、文档目录结构对比

### OpenClaw

```
docs/
├── index.md                    # 首页
├── docs.json                   # Mintlify 配置
├── start/                      # 快速开始
│   ├── getting-started.md
│   ├── quickstart.md
│   ├── onboarding.md / wizard.md
│   ├── setup.md / bootstrapping.md
│   └── lore.md / showcase.md
├── concepts/                   # 核心概念（40+ 页面）
│   ├── agent.md / architecture.md
│   ├── memory.md / session.md
│   ├── multi-agent.md / models.md
│   ├── context.md / streaming.md
│   └── ...
├── gateway/                    # Gateway 配置
│   ├── configuration.md        # 配置概览
│   ├── configuration-reference.md  # 字段级参考
│   ├── configuration-examples.md   # 示例
│   ├── config-agents.md / config-channels.md / config-tools.md
│   ├── security/ / sandboxing.md
│   └── ...（30+ 页面）
├── channels/                   # 通道集成（20+ 通道）
│   ├── discord.md / telegram.md / whatsapp.md / slack.md
│   ├── wechat.md / feishu.md / signal.md
│   └── ...
├── tools/                      # 工具文档（40+ 工具）
├── plugins/                    # 插件系统 + SDK
│   ├── reference/              # 100+ 插件参考页
│   └── sdk-*.md
├── providers/                  # 模型提供商（40+）
├── cli/                        # CLI 命令参考（50+ 命令）
├── install/                    # 安装方式（20+ 平台）
├── platforms/                  # 平台特定指南
├── automation/                 # 自动化（cron, hooks, webhooks）
├── nodes/                      # 节点（音频、摄像头、位置）
├── help/                       # FAQ 和排错
├── reference/                  # 参考资料 + 模板
├── security/                   # 安全文档
└── .i18n/                      # 国际化（20+ 语言）
```

**规模**: 400+ 页面，是所有项目中最庞大的文档体系。

### Claude Code

```
docs/anthropic/en/docs/claude-code/
├── Getting started/
│   ├── Overview
│   ├── Quickstart
│   └── Changelog
├── Core concepts/
│   ├── How Claude Code works
│   ├── Extend Claude Code
│   ├── Explore the .claude directory
│   ├── Explore the context window
│   └── Prompt caching
├── Use Claude Code/
│   ├── Store instructions and memories (CLAUDE.md)
│   ├── Manage sessions
│   ├── Common workflows
│   ├── Prompt library
│   └── Best practices
└── Platforms and integrations/
    ├── Overview
    ├── Remote Control
    ├── Claude Code on the web / desktop / mobile
    ├── Chrome extension
    ├── Computer use (preview)
    ├── Visual Studio Code / JetBrains IDEs
    ├── Code review & CI/CD
    ├── Claude Code in Slack
    └── Claude Tag
```

**规模**: ~25 页面，精简聚焦。

### OpenAI Codex

```
GitHub README + developers.openai.com/codex
├── README.md (GitHub)
│   ├── Quickstart (安装 + 运行)
│   ├── Using Codex with your ChatGPT plan
│   └── Docs 链接列表
├── docs/ (GitHub repo)
│   ├── contributing.md
│   ├── install.md
│   └── open-source-fund.md
└── developers.openai.com/codex (需登录，403)
    └── (外部不可访问的完整文档)
```

**规模**: GitHub 公开文档极少（~3 页），主体文档在 developers.openai.com（需认证）。

### Hermes

```
无独立文档站
├── GitHub: NousResearch/hermes-function-calling
│   └── README.md (函数调用示例)
└── OpenClaw 迁移文档: install/migrating-hermes.md
    └── 描述了 Hermes 的状态结构 (~/.hermes)
```

**规模**: 无正式文档。Hermes 是 OpenClaw 的前身项目，已通过迁移文档被覆盖。

### DeepSeek

```
api-docs.deepseek.com/ (Docusaurus)
├── Quick Start
│   ├── Your First API Call
│   ├── Models & Pricing
│   ├── Token & Token Usage
│   ├── Rate Limit & Isolation
│   └── Error Codes
├── Agent Integrations
├── API Guides/
│   ├── Vision
│   ├── Thinking Mode
│   ├── Multi-round Conversation
│   ├── Chat Prefix Completion (Beta)
│   ├── FIM Completion (Beta)
│   ├── JSON Output
│   ├── Tool Calls
│   ├── Files API
│   ├── Context Caching
│   ├── Using the Responses API
│   └── Using the Anthropic API
├── API Reference
├── DeepSeek Harness Guide (开发者预览)
└── Change Log
```

**规模**: ~25 页面，API 文档为主，结构扁平清晰。

---

## 三、写作风格对比

| 维度 | OpenClaw | Claude Code | OpenAI Codex | Hermes | DeepSeek |
|------|----------|-------------|-------------|--------|----------|
| **语调** | 技术严谨 + 轻松幽默 | 简洁专业 | 简洁直接 | N/A | 干净规范 |
| **读者定位** | 开发者 + 高级用户 | 开发者 | 开发者 | N/A | 开发者 |
| **语言** | 英文为主，20+ 语言 i18n | 英文（含日/韩等） | 英文 | 英文 | 英/中双语 |
| **代码示例** | 大量 JSON5 配置 + CLI 命令 | 大量终端交互示例 | Shell 安装命令 | Python 示例 | Python/cURL 示例 |
| **文档密度** | 极高（400+ 页） | 中等（25 页） | 低（3 页公开） | 极低 | 中等（25 页） |
| **更新频率** | 活跃（有 changelog + release notes） | 活跃 | 活跃 | 已停止 | 活跃 |

### 风格细节

**OpenClaw**:
- 使用 Mintlify 组件系统（`<Tabs>`, `<Accordion>`, `<Tip>`, `<Warning>`, `<Steps>`, `<Columns>`, `<Card>`）
- 每页有 `summary`, `read_when`, `title` frontmatter — 帮助用户判断何时阅读
- 配置文档分为「概览页」和「字段参考页」两个层级
- 大量交叉引用，文档间链接密度极高
- 有「read_when」元数据 — 独特的上下文感知导航设计

**Claude Code**:
- 结构清晰的层级导航（3 级：概念 → 使用 → 平台）
- 注重「操作步骤」（Step-by-step）
- 有专门的「Prompt Library」和「Best Practices」
- 侧边栏自动生成目录
- 简洁的段落，少用组件

**OpenAI Codex**:
- GitHub README 为主入口，极简风格
- 安装脚本一行搞定（`curl | sh`）
- 提供 ChatGPT 账号集成的一站式体验
- 正式文档隐藏在需认证的 developers.openai.com
- 开源贡献文档明确说明「不接受外部 PR」

**DeepSeek**:
- Docusaurus 标准风格，双语支持（en/zh-cn）
- API-first 设计：快速开始直接展示代码
- 兼容 OpenAI/Anthropic API 格式（强调「修改配置即可使用」）
- 有专门的 Agent Integrations 指南
- Harness Guide 为开发者预览

---

## 四、配置说明写法对比

### OpenClaw — 最复杂的配置文档

```
配置体系：
├── configuration.md          # 概览：快速设置 + 常见任务
├── configuration-reference.md # 字段级参考（1500+ 行）
├── configuration-examples.md  # 完整配置示例
├── config-agents.md           # Agent 配置深入
├── config-channels.md         # 通道配置深入
└── config-tools.md            # 工具配置深入
```

**特点**:
- **分层设计**: 概览 → 示例 → 字段参考，渐进深入
- **严格验证**: 配置不匹配 schema 会拒绝启动
- **多种编辑方式**: 交互向导 / CLI one-liner / Control UI / 直接编辑
- **热重载**: 修改文件自动生效
- **JSON5 格式**: 支持注释和尾逗号
- **frontmatter `read_when`**: 告诉用户何时该读这个页面

**示例片段**:
```json5
// ~/.openclaw/openclaw.json
{
  agents: { defaults: { workspace: "~/.openclaw/workspace" } },
  channels: { whatsapp: { allowFrom: ["+15555550123"] } },
}
```

### Claude Code — 基于文件的配置

**特点**:
- **CLAUDE.md 文件系统**: 项目级 / 用户级 / 目录级指令文件
- **`.claude/` 目录**: 项目特定配置
- **无 JSON/YAML 配置文件**: 纯 Markdown 指令
- **Auto Memory**: 自动记忆功能

### OpenAI Codex — 极简配置

**特点**:
- ChatGPT 账号登录即可使用（零配置）
- API key 方式需要额外设置
- 配置细节在需认证的文档中

### DeepSeek — API 配置

**特点**:
- **兼容性优先**: 直接兼容 OpenAI/Anthropic SDK
- **代码优先**: 配置说明直接嵌入代码示例
- **双语**: 中英文同步
- **模型选择**: 简单的 model name 切换

---

## 五、快速开始写法对比

### OpenClaw — 结构化多步骤

```markdown
## What you need
- Node.js 22.22.3+, 24.15+, or 25.9+
- An API key from a model provider

## Quick setup
<Steps>
  <Step title="Install OpenClaw">
    # macOS/Linux: curl -fsSL https://openclaw.ai/install.sh | bash
    # Windows: iwr -useb https://openclaw.ai/install.ps1 | iex
  </Step>
  <Step title="Run onboarding">
    openclaw onboard --install-daemon
  </Step>
  <Step title="Verify the Gateway is running">
    openclaw gateway status
  </Step>
  <Step title="Open the dashboard">
    openclaw dashboard
  </Step>
  <Step title="Start chatting">
    从任意已配置的通道发消息
  </Step>
</Steps>
```

**特点**: 5 步完成，有 `<Steps>` 组件美化，多平台安装命令用 `<Tabs>` 切换。

### Claude Code — 8 步详细教程

```markdown
## Quickstart
Step 1: Install Claude Code
Step 2: Log in to your account
Step 3: Start your first session
Step 4: Ask your first question
Step 5: Make your first code change
Step 6: Use Git with Claude Code
Step 7: Fix a bug or add a feature
Step 8: Test out other common workflows

## Essential commands
## Pro tips for beginners
## What's next?
```

**特点**: 步骤更细致，从安装到实际使用 Git 的完整流程，有「Pro tips」。

### OpenAI Codex — 一行安装

```bash
# macOS/Linux
curl -fsSL https://chatgpt.com/codex/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"

# npm
npm install -g @openai/codex

# Homebrew
brew install --cask codex
```

**特点**: 极简，4 种安装方式并列，运行 `codex` 即可开始。强调 ChatGPT 账号集成。

### DeepSeek — 代码即文档

```python
from openai import OpenAI

client = OpenAI(
    api_key="<your_key>",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**特点**: 直接展示代码，零废话。强调与 OpenAI API 的兼容性。

---

## 六、特色功能对比

| 项目 | 独特的文档设计 |
|------|---------------|
| **OpenClaw** | ① `read_when` frontmatter 元数据 — 上下文感知导航 ② Mintlify 组件系统（Tabs/Accordion/Steps/Tip/Warning） ③ 分层配置文档（概览→示例→字段参考） ④ 100+ 插件参考页自动生成 ⑤ 20+ 语言 i18n 体系 ⑥ `docs.json` 配置 400+ 页面的完整站点结构 |
| **Claude Code** | ① CLAUDE.md 文件系统 — 纯 Markdown 指令 ② `.claude/` 目录约定 ③ Auto Memory 自动记忆 ④ Prompt Library ⑤ 侧边栏自动生成 ⑥ `llms.txt` 供 LLM 发现文档 |
| **OpenAI Codex** | ① ChatGPT 账号一键集成 ② `codex app` 桌面应用模式 ③ 同时提供 CLI/IDE/Web/Desktop 四种入口 ④ DotSlash 跨平台二进制分发 ⑤ 明确的「不接受外部 PR」政策 |
| **Hermes** | ① 函数调用示例代码 ② Pydantic 模型 JSON Schema 生成 ③ 已被 OpenClaw 迁移路径覆盖 |
| **DeepSeek** | ① OpenAI/Anthropic API 双兼容 ② 中英文双语文档 ③ Agent Integrations 指南 ④ DeepSeek Harness（开发者预览） ⑤ Context Caching 文档 ⑥ FIM 补全文档 |

---

## 七、总结与洞察

### 文档成熟度排名

1. **OpenClaw** ⭐⭐⭐⭐⭐ — 最完整，400+ 页面，组件化设计，i18n，分层配置
2. **Claude Code** ⭐⭐⭐⭐ — 精简但结构清晰，25 页覆盖核心场景
3. **DeepSeek** ⭐⭐⭐⭐ — API 文档规范，双语支持，结构扁平
4. **OpenAI Codex** ⭐⭐⭐ — 公开文档极少，主体隐藏在认证站点
5. **Hermes** ⭐ — 无正式文档，已被 OpenClaw 迁移覆盖

### 设计哲学对比

| 哲学 | 代表 | 描述 |
|------|------|------|
| **全面覆盖** | OpenClaw | 400+ 页文档覆盖每个功能、每个通道、每个插件 |
| **精选聚焦** | Claude Code | 25 页文档覆盖 80% 的使用场景 |
| **代码即文档** | DeepSeek | 代码示例优先，文字说明辅助 |
| **最小公开** | OpenAI Codex | 公开最少信息，核心文档需认证访问 |

### 对 Kioxus 文档的建议

基于本次研究，建议 Kioxus 文档采用以下策略：

1. **结构**: 采用 OpenClaw 的分层设计（概念 → 配置 → 参考），但控制在 Claude Code 的精简规模
2. **快速开始**: 参考 OpenAI Codex 的极简风格（一行安装 + 即刻运行）
3. **配置说明**: 参考 OpenClaw 的分层设计（概览 + 示例 + 字段参考），但用 DeepSeek 的代码优先风格
4. **组件**: 使用 Mintlify 或类似的组件系统（Tabs/Steps/Tip）
5. **元数据**: 采用 `read_when` 类似的上下文感知设计
6. **双语**: 参考 DeepSeek 的中英文双语支持
7. **llms.txt**: 参考 Claude Code 的 `llms.txt` 供 LLM 发现文档

---

> 报告完成于 2026-08-30 14:14 CST
