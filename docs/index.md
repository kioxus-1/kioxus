# Kioxus 文档

> Kioxus — 轻量、可拓展的自主Agent框架

---

## 目录

### 快速开始
- [简介](#简介)
- [安装](#安装)
- [快速开始](#快速开始)

### 核心概念
- [架构总览](#架构总览)
- [核心循环](#核心循环)
- [三大原则](#三大原则)
- [记忆系统](#记忆系统)

### 使用指南
- [用户使用](#用户使用exe)
- [开发者模式](#开发者模式)
- [配置说明](#配置说明)
- [LLM Provider](#llm-provider)

### API 参考
- [核心引擎模块](#核心引擎模块)
- [记忆系统模块](#记忆系统模块)
- [内置工具](#内置工具)

### 部署
- [打包成exe](#打包成exe)
- [Docker部署](#docker部署)

### 参考
- [测试](#测试)
- [版本历史](#版本历史)
- [FAQ](#faq)

---

## 简介

Kioxus 是一套开箱即用的自主Agent解决方案，能独立思考、记忆、验证自己的输出。

**核心能力**：
- 🗣️ 自然语言对话，支持多轮上下文和记忆
- 🧠 链式推理引擎（直接推理/链式推理/反思）
- 🔧 内置工具：网页抓取、文件读写、代码执行、网页搜索
- ✅ 输出验证器，自动检查格式、相关性、安全性、一致性
- 🔒 代码执行沙箱，4级安全策略，进程级隔离
- 📊 Token预算追踪，支持软限制和硬限制
- 🔄 多Key轮换 + Model Failover，API调用高可用

**适用场景**：
- 对话助手 / 自动化任务 / 代码执行 / 数据处理

---

## 安装

### 方式一：下载exe（推荐）

前往 [Releases](https://github.com/kioxus-1/kioxus/releases) 下载最新版，解压双击即用。

### 方式二：从源码安装

```bash
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus
pip install -r requirements.txt
```

### 依赖

- Python 3.11+
- Flask
- PyWebView（桌面窗口）
- pytest（测试）

---

## 快速开始

### 用户（exe）

1. 下载 `Kioxus.exe`
2. 双击运行
3. 点击左侧 **设置**
4. 填写 Provider、API URL、API Key、Model
5. 点击 **保存配置** → **测试连接**
6. 开始对话

### 开发者（命令行）

```bash
# 命令行调试
python src/run.py

# 打包成exe
python src/build.py

# 运行测试
pytest test/
```

---

## 架构总览

```
用户输入
  ↓
① Input（输入解析）
  ↓
② Memory（记忆检索）
  ↓
③ Think（链式推理）
  ↓
④ Plan（任务规划）
  ↓
⑤ Act（LLM生成 / 工具执行）
  ↓
⑥ Observe（结果检查）
  ↓
⑥.5 Verify（对抗性验证）
  ↓
⑦ Output（输出响应）
  ↓
⑧ Reflect（记忆存储）
```

---

## 核心循环

每一次用户交互遵循8步循环：

| 步骤 | 模块 | 做什么 |
|------|------|--------|
| ① Input | `input.py` | 解析消息，识别意图 |
| ② Memory | `memory_bridge.py` | 检索记忆，注入上下文 |
| ③ Think | `reasoning.py` | 链式推理，置信度评估 |
| ④ Plan | `planner.py` + `decomposer.py` | 任务分解，步骤规划 |
| ⑤ Act | `llm.py` + `tools.py` | LLM生成或工具执行 |
| ⑥ Observe | `output.py` | 检查结果，格式化观察 |
| ⑥.5 Verify | `verifier.py` | 对抗性验证（5项检查） |
| ⑦ Output | `output.py` | 格式化并返回响应 |
| ⑧ Reflect | `memory_bridge.py` | 有值得记的就存入记忆 |

---

## 三大原则

### 1. 对抗性验证（Adversarial Verification）

不信任Agent的输出。Verifier独立运行5项规则检查（纯规则，不用LLM）：
- 格式检查：输出长度、空值、结构
- 工具检查：错误模式、空结果
- 相关性：输入输出关键词重叠
- 安全性：API key、密码泄露
- 一致性：自相矛盾检测

审查不通过自动重试（最多2次）。

### 2. 硬边界隔离（Hard Boundary Isolation）

代码在沙箱里跑，系统级强制执行：

| 级别 | 网络 | 超时 | 内存 | 阻止导入 |
|------|------|------|------|----------|
| STRICT | ❌ | 5s | 128MB | os, subprocess, shutil |
| NORMAL | ❌ | 10s | 256MB | os, subprocess, shutil |
| RELAXED | ✅ | 30s | 512MB | — |
| UNSAFE | ✅ | ∞ | ∞ | — |

### 3. 可量化上下文（Quantifiable Context）

Token预算追踪，每轮对话有明确的Token分配：

| 层 | 比例 | 用途 |
|----|------|------|
| 系统提示 | 10% | 身份、规则 |
| 记忆 | 30% | Memory Router输出 |
| 历史 | 40% | 会话历史 |
| 环境 | 5% | 时间、系统信息 |
| 用户消息 | 15% | 当前输入 |

---

## 记忆系统

### 四层架构

```
core.md          — 身份、价值观、规则（每轮强制注入）
reflection/      — 教训、认知、关系（按需检索）
records/         — 日志→十日摘要→月度→年度（渐进压缩）
today.md         — 今日上下文（每日清理）
```

### 设计决策

| 决策 | 原因 |
|------|------|
| 代码管逻辑，LLM管语义 | LLM做不了数学和路由 |
| BM25搜索，不用向量 | 无外部依赖，先"找得到"再谈"语义" |
| 标签字典防漂移 | 记忆条目标签一致性 |
| 压缩保留行动 | `[事实]` + `[行动]` 格式确保行为改变存活 |
| P0-P3优先级 | P3在30天后遗忘，P0永不删除 |

---

## 用户使用（exe）

### 首次启动

1. 双击 `Kioxus.exe`
2. 点击左侧 **设置**
3. 在 **LLM 配置** 区域填写：
   - **Provider**：如 `xiaomi`、`openai`、`custom`
   - **API URL**：如 `https://api.openai.com/v1/chat/completions`
   - **API Key**：你的密钥
   - **Model**：如 `gpt-4o`、`mimo-v2.5-pro`
4. 点击 **保存配置**
5. 点击 **测试连接** 验证
6. 开始对话

### 界面功能

- **对话**：输入消息，Kioxus思考后回复
- **设置**：配置API Key、切换主题、调整字号
- **清空对话**：清除所有聊天记录

---

## 开发者模式

### 项目结构

```
kioxus/
├── src/                     # 核心源码
│   ├── core_v2/             #   核心引擎（16个模块）
│   ├── memory_v2/           #   记忆系统（7个模块）
│   ├── main.py              #   系统入口
│   ├── run.py               #   命令行调试
│   ├── desktop.py           #   桌面窗口（PyWebView）
│   └── build.py             #   打包脚本
│
├── config/                  # 配置文件
├── examples/                # 使用示例
├── docs/                    # 项目文档
├── test/                    # 测试代码
│
├── requirements.txt
├── README.md
├── LICENSE                  # MIT
└── .gitignore
```

### 命令

```bash
# 命令行调试
python src/run.py

# 指定Provider
python src/run.py --provider xiaomi
python src/run.py --provider minimax
python src/run.py --provider mock    # 测试模式

# 打包成exe
python src/build.py
python src/build.py --onefile        # 单文件模式
python src/build.py --clean          # 清理构建产物

# 运行测试
pytest test/                         # 全量（43个）
pytest test/ -v                      # 详细输出
pytest test/ -x                      # 遇到失败就停止
```

---

## 配置说明

### 配置文件

| 文件 | 用途 | 是否上传GitHub |
|------|------|---------------|
| `config/kioxus.json` | LLM Provider配置 | ✅ 是（不含密钥） |
| `config/config.example.yaml` | 配置模板 | ✅ 是 |
| `.env` | API密钥 | ❌ 否（.gitignore） |

### config/kioxus.json

```json
{
  "providers": {
    "xiaomi": {
      "api_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
      "api_key_env": "XIAOMI_TOKEN_PLAN_API_KEY",
      "model": "mimo-v2.5-pro",
      "max_tokens": 2048,
      "temperature": 0.7
    },
    "openai": {
      "api_url": "https://api.openai.com/v1/chat/completions",
      "api_key_env": "OPENAI_API_KEY",
      "model": "gpt-4o",
      "max_tokens": 4096,
      "temperature": 0.7
    }
  },
  "default_provider": "xiaomi"
}
```

### .env

```env
XIAOMI_TOKEN_PLAN_API_KEY=your-key-here
OPENAI_API_KEY=your-key-here
```

支持逗号分隔的多Key轮换：
```env
XIAOMI_TOKEN_PLAN_API_KEY=key1,key2,key3
```

---

## LLM Provider

### 支持的Provider

| Provider | 环境变量 | 默认模型 |
|----------|---------|---------|
| 小米 MiMo | `XIAOMI_TOKEN_PLAN_API_KEY` | mimo-v2.5-pro |
| MiniMax | `MINIMAX_API_KEY` | MiniMax-Text-01 |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| 任意OpenAI兼容 | 自定义 | 自定义 |

### 添加自定义Provider

编辑 `config/kioxus.json`，在 `providers` 中添加：

```json
{
  "my_provider": {
    "api_url": "https://your-api.com/v1/chat/completions",
    "api_key_env": "MY_PROVIDER_API_KEY",
    "model": "your-model-name",
    "max_tokens": 2048,
    "temperature": 0.7
  }
}
```

然后在 `.env` 中添加对应的API Key。

### 多Key轮换

支持每个Provider配多个Key，限流时自动切换：

```env
XIAOMI_TOKEN_PLAN_API_KEY=key1,key2,key3
```

### Model Failover

主Provider失败时自动尝试备用Provider。无需额外配置，注册多个Provider即可。

---

## 核心引擎模块

| 模块 | 文件 | 作用 |
|------|------|------|
| Engine | `engine.py` | 核心循环调度器 |
| Input | `input.py` | 输入处理、意图识别 |
| Context | `context.py` | 上下文组装、Token预算管理 |
| LLM | `llm.py` | LLM客户端（多Provider、多Key轮换、Failover） |
| Output | `output.py` | 输出格式化 |
| Session | `session.py` | 会话管理、checkpoint |
| MemoryBridge | `memory_bridge.py` | 记忆系统桥接器 |
| Reasoning | `reasoning.py` | 推理引擎（direct/chain/reflect） |
| Planner | `planner.py` | 任务规划器 |
| Decomposer | `decomposer.py` | 目标分解器 |
| Tools | `tools.py` | 工具注册框架 |
| BuiltinTools | `builtin_tools.py` | 内置工具 |
| Verifier | `verifier.py` | 输出验证器 |
| Sandbox | `sandbox.py` | 代码执行沙箱 |
| ProviderRegistry | `provider_registry.py` | Provider插件注册制 |
| ConfigWatcher | `config_watcher.py` | 配置热更新 |

---

## 记忆系统模块

| 模块 | 文件 | 作用 |
|------|------|------|
| MemoryStore | `memory.py` | 四层文件存储 |
| MemoryRouter | `router.py` | 记忆路由、上下文组装 |
| MemorySearch | `search.py` | BM25搜索引擎 |
| Compressor | `compressor.py` | 压缩引擎（Flush Agent） |
| Janitor | `janitor.py` | 维护任务（flush/settle/compress） |
| TagDictionary | `tags.py` | 标签字典（防漂移） |

---

## 内置工具

| 工具 | 功能 | 沙箱 |
|------|------|------|
| `http_fetch` | 抓取网页内容 | — |
| `file_read` | 读文件（最多200行） | — |
| `file_write` | 写入/追加文件 | — |
| `file_list` | 列目录内容 | — |
| `code_exec` | 执行Python/JS代码 | ✅ 默认沙箱隔离 |
| `web_search` | 网页搜索 | — |

---

## 打包成exe

```bash
python src/build.py              # 目录模式（启动快，推荐）
python src/build.py --onefile     # 单文件模式（一个exe，启动慢）
python src/build.py --clean       # 清理构建产物
```

输出在 `src/dist/Kioxus/` 目录。

---

## Docker部署

```bash
# 构建镜像
docker build -t kioxus:latest .

# 运行
docker run -d -p 8080:8080 --name kioxus kioxus:latest

# 带环境变量
docker run -d -p 8080:8080 \
  -e XIAOMI_TOKEN_PLAN_API_KEY=your-key \
  --name kioxus kioxus:latest
```

---

## 测试

```bash
pytest test/                    # 全量测试（43个）
pytest test/ -x                 # 遇到第一个失败就停止
pytest test/ -v                 # 详细输出
```

| 测试文件 | 数量 | 覆盖 |
|----------|------|------|
| test_core_v2_smoke.py | 6 | 输入、会话、上下文、输出、LLM、引擎 |
| test_phase2_smoke.py | 3 | 推理、规划器、引擎集成 |
| test_phase3_smoke.py | 4 | 工具注册、内置工具、分解器 |
| test_verifier.py | 7 | 格式/工具/相关性/安全/一致性检查、重试 |
| test_sandbox.py | 9 | 沙箱各级别、超时、阻止导入 |
| test_context_budget.py | 8 | Token预算、软限制、硬限制 |
| test_memory_v2.py | 3 | 记忆存储、路由、搜索 |
| test_integration.py | 3 | 真实LLM调用、记忆系统、引擎全流程 |

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-25 | v0.1 | 初始版本 |
| 2026-07-23 | v0.2 | Python重写，模块化架构 |
| 2026-08-10 | v0.3 | 验证器、沙箱、上下文预算 |
| 2026-08-30 | v0.3.0 | 开源发布，Provider注册制，多Key轮换，Failover |

---

## FAQ

### Q: 支持哪些LLM？
A: 支持任意OpenAI兼容API。内置小米MiMo和MiniMax，可自由添加。

### Q: API Key安全吗？
A: .env在.gitignore中，不会上传GitHub。代码内部使用Key轮换和限流重试。

### Q: 能离线使用吗？
A: 不行，需要网络连接LLM API服务。

### Q: 怎么添加新的LLM Provider？
A: 编辑config/kioxus.json，在providers中添加，然后在.env中填入API Key。

### Q: exe有多大？
A: 约34MB（含依赖），解压后双击即用。

---

## 开源协议

本项目基于 [MIT License](../LICENSE) 开源，可免费学习、使用和二次开发。

## 联系方式

作者：kioxus-1
仓库：https://github.com/kioxus-1/kioxus
