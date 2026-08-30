# Kioxus 文档

> Kioxus — 一个能自己思考、记忆、验证的AI助手

---

## 目录

### 第一部分：AI基础知识
- [什么是AI](#什么是ai)
- [什么是大语言模型llm](#什么是大语言模型llm)
- [什么是api和api-key](#什么是api和api-key)
- [什么是agent](#什么是agent)
- [什么是token](#什么是token)
- [什么是推理](#什么是推理)
- [什么是记忆](#什么是记忆)
- [什么是沙箱](#什么是沙箱)
- [什么是验证](#什么是验证)

### 第二部分：认识Kioxus
- [Kioxus是什么](#kioxus是什么)
- [Kioxus能做什么](#kioxus能做什么)
- [Kioxus怎么工作的](#kioxus怎么工作的)

### 第三部分：使用教程
- [下载和安装](#下载和安装)
- [配置api-key](#配置api-key)
- [开始对话](#开始对话)
- [高级设置](#高级设置)

### 第四部分：进阶内容
- [开发者模式](#开发者模式)
- [配置文件说明](#配置文件说明)
- [llm-provider配置](#llm-provider配置)
- [核心模块说明](#核心模块说明)
- [测试](#测试)
- [打包和部署](#打包和部署)

### 第五部分：参考
- [版本历史](#版本历史)
- [faq](#faq)

---

# 第一部分：AI基础知识

## 什么是AI

AI（Artificial Intelligence，人工智能）是让计算机像人一样思考和回答问题的技术。

你平时用的Siri、小爱同学、ChatGPT，都是AI。它们能听懂你说的话，然后给你回答。

**关键点**：AI不是真的有"智能"，它是通过大量数据训练出来的程序。它看起来像在思考，其实是在根据学到的规律生成回答。

---

## 什么是大语言模型（LLM）

LLM（Large Language Model，大语言模型）是AI的一种，专门用来理解和生成文字。

**通俗理解**：LLM读过互联网上几乎所有的文字（书、文章、网页），所以它"知道"很多事情。你问它问题，它根据读过的内容来回答。

**常见的LLM服务**：

| 名称 | 公司 | 说明 |
|------|------|------|
| ChatGPT | OpenAI | 最知名的AI对话服务 |
| Claude | Anthropic | 另一个知名的AI对话服务 |
| MiMo | 小米 | 小米公司的AI模型 |
| MiniMax | MiniMax公司 | 国产AI模型 |
| DeepSeek | DeepSeek公司 | 国产AI模型 |

**关键点**：LLM不是万能的。它可能回答错误，也可能编造不存在的信息。所以Kioxus有"验证器"来检查它的回答。

---

## 什么是API和API Key

### API

API（Application Programming Interface，应用程序编程接口）是程序之间对话的方式。

**通俗理解**：你去餐厅点菜，服务员把你的需求告诉厨房，厨房做好菜再通过服务员端给你。API就是这个"服务员"——你的程序通过API把请求发给AI服务，AI服务通过API把回答返回来。

### API Key

API Key（API密钥）是你使用AI服务的"通行证"。

**通俗理解**：就像你去游泳馆需要办一张会员卡，卡上有卡号和密码。API Key就是你的卡号+密码，没有它你就用不了AI服务。

**怎么获取API Key**：
1. 去AI服务商的网站注册账号（比如小米MiMo、OpenAI）
2. 在账号设置里找到"API Key"或"密钥"选项
3. 点击"生成"或"创建"
4. 复制生成的密钥（一串字母和数字的组合）

**重要**：API Key是私密的，不要告诉别人，不要上传到公开的地方。

---

## 什么是Agent

Agent（智能体）是一个能自主完成任务的AI程序。

**通俗理解**：普通的AI对话工具（比如ChatGPT网页版）只能你问一句它答一句。Agent更进一步——它能自己思考、做计划、使用工具、检查结果。

**Agent和普通AI的区别**：

| | 普通AI对话 | Agent |
|---|----------|-------|
| 工作方式 | 你问一句，它答一句 | 它能自己思考、做计划、执行 |
| 能用工具吗 | 不能 | 能（搜索网页、读写文件、执行代码） |
| 能记住吗 | 有限 | 有专门的记忆系统 |
| 会检查自己吗 | 不会 | 有验证器检查回答是否靠谱 |

**Kioxus就是一个Agent**。它不只是和你聊天，还能帮你做事情。

---

## 什么是Token

Token是AI处理文字的最小单位。

**通俗理解**：AI不是按"字"或"词"来读文字的，它把文字拆成一个个小片段，这些小片段就是Token。

**举例**：
- "你好" 可能是 2个Token
- "Hello world" 可能是 2个Token（Hello 和 world）
- 一段100字的中文，大约是 50-100个Token

**为什么要关心Token**：
- AI服务按Token数量收费
- 每次对话有Token上限（比如最多4096个Token）
- Kioxus会追踪Token使用量，防止超出预算

---

## 什么是推理

推理是AI思考问题的过程。

**通俗理解**：就像你做数学题时会一步步推导，AI也会一步步推理。比如：
- 你问："北京今天天气怎么样？"
- AI推理：需要先查天气数据 → 搜索"北京今天天气" → 找到结果 → 告诉你

**Kioxus的三种推理模式**：
- **直接推理**：直接给出答案（简单问题用）
- **链式推理**：一步步推导（复杂问题用）
- **反思**：检查自己的答案对不对再回答

---

## 什么是记忆

记忆是AI记住之前对话内容的能力。

**通俗理解**：就像你和朋友聊天，朋友记得你之前说过的话。AI的记忆系统也是一样——它能记住你之前告诉它的事情，下次对话还能想起来。

**Kioxus的四层记忆**：

| 层 | 存什么 | 举例 |
|---|--------|------|
| 核心层 | 身份、价值观、规则 | "我是Kioxus，一个AI助手" |
| 反思层 | 教训、认知 | "用户喜欢简洁的回答" |
| 记录层 | 对话历史 | "昨天用户问了Python的问题" |
| 今日层 | 今天的内容 | "今天用户在调试代码" |

---

## 什么是沙箱

沙箱是一个隔离的安全环境，程序在里面运行时不能影响外面。

**通俗理解**：就像小朋友在沙箱里玩沙子，沙子不会弄到外面。程序在沙箱里运行时，即使出了问题，也不会影响你的电脑。

**Kioxus的沙箱有4个安全级别**：

| 级别 | 说明 | 适合场景 |
|------|------|----------|
| STRICT（严格） | 不能联网，5秒超时，内存128MB | 不信任的代码 |
| NORMAL（普通） | 不能联网，10秒超时，内存256MB | 一般代码 |
| RELAXED（宽松） | 可以联网，30秒超时，内存512MB | 需要联网的代码 |
| UNSAFE（不安全） | 没有限制 | 完全信任的代码 |

---

## 什么是验证

验证是检查AI的回答是否正确、安全的过程。

**通俗理解**：就像老师批改作业，检查答案对不对、有没有抄袭、格式对不对。Kioxus的验证器也是这样——它会自动检查AI的回答。

**Kioxus验证器检查5项**：
1. **格式检查**：回答是否完整、有没有空白
2. **工具检查**：工具调用是否成功
3. **相关性**：回答是否和问题相关
4. **安全性**：有没有泄露密码、密钥等敏感信息
5. **一致性**：回答有没有自相矛盾

如果检查不通过，Kioxus会自动重试（最多2次）。

---

# 第二部分：认识Kioxus

## Kioxus是什么

Kioxus是一个自主Agent——一个能自己思考、记忆、使用工具、验证回答的AI助手。

你可以把它理解为一个"本地版的ChatGPT"，但它：
- 能帮你执行代码
- 能记住你说过的话
- 能检查自己的回答是否正确
- 你的数据不会上传到别人的服务器

---

## Kioxus能做什么

1. **对话**：和你聊天，回答问题
2. **思考**：遇到复杂问题会一步步推理
3. **记忆**：记住你之前说过的话
4. **工具**：搜索网页、读写文件、执行代码
5. **验证**：检查自己的回答是否靠谱
6. **安全**：代码在沙箱里运行，不会搞坏你的电脑

---

## Kioxus怎么工作的

每次你发一条消息，Kioxus会经过8个步骤：

1. **理解你的消息**（Input）
2. **回忆相关记忆**（Memory）
3. **思考怎么回答**（Think）
4. **制定计划**（Plan）
5. **执行动作**（Act）——调用AI生成回答，或者使用工具
6. **观察结果**（Observe）
7. **验证回答**（Verify）——检查回答是否正确
8. **保存记忆**（Reflect）——如果有值得记住的就存起来

---

# 第三部分：使用教程

## 下载和安装

### 方式一：下载exe（推荐普通用户）

1. 打开 https://github.com/kioxus-1/kioxus/releases
2. 找到最新版本，点击 `Kioxus.exe` 下载
3. 解压下载的文件
4. 双击 `Kioxus.exe` 运行

不需要安装Python，不需要任何开发环境。

### 方式二：从源码安装（适合开发者）

```bash
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus
pip install -r requirements.txt
```

---

## 配置API Key

### 第一步：获取API Key

你需要一个AI服务的API Key。以下是一些常见的AI服务：

| 服务 | 网站 | 说明 |
|------|------|------|
| 小米MiMo | https://xiaomimimo.com | 国产AI服务 |
| MiniMax | https://minimax.chat | 国产AI服务 |
| OpenAI | https://platform.openai.com | ChatGPT的API服务 |
| DeepSeek | https://platform.deepseek.com | 国产AI服务 |

注册账号后，在账号设置里找到"API Key"或"密钥"选项，生成一个Key。

### 第二步：在Kioxus中配置

1. 打开Kioxus
2. 点击左侧的 **设置**
3. 在 **LLM 配置** 区域填写：
   - **Provider**：填你用的AI服务名称（比如 `xiaomi`、`openai`）
   - **API URL**：填AI服务的地址（比如 `https://api.openai.com/v1/chat/completions`）
   - **API Key**：填你刚才获取的密钥
   - **Model**：填模型名称（比如 `gpt-4o`、`mimo-v2.5-pro`）
4. 点击 **保存配置**
5. 点击 **测试连接**，如果显示"连接成功"就说明配置好了

### API URL 和 Model 怎么填

不同AI服务的API URL和Model不一样：

| 服务 | API URL | Model |
|------|---------|-------|
| 小米MiMo | `https://token-plan-cn.xiaomimimo.com/v1/chat/completions` | `mimo-v2.5-pro` |
| MiniMax | `https://api.minimax.chat/v1/text/chatcompletion_v2` | `MiniMax-Text-01` |
| OpenAI | `https://api.openai.com/v1/chat/completions` | `gpt-4o` |
| DeepSeek | `https://api.deepseek.com/v1/chat/completions` | `deepseek-chat` |

---

## 开始对话

配置好API Key后，在Kioxus的输入框里输入你想问的问题，按回车发送。

Kioxus会思考一会儿，然后给你回答。

**示例对话**：
```
你: 你好，你是谁？
Kioxus: 你好！我是Kioxus，一个自主AI助手。我能和你对话、帮你执行代码、记住你说过的话。

你: 帮我写一个Python程序，计算1到100的和
Kioxus: 好的，代码如下：
sum(range(1, 101))  # 结果是5050
```

---

## 高级设置

### 切换主题

在设置中，可以切换深色/浅色主题。

### 调整字号

在设置中，可以调整字号：小/中/大。

### 清空对话记录

在设置中，点击"清空对话记录"可以清除所有聊天内容。

### 多Key轮换

如果你有多个API Key，可以在`.env`文件中用逗号分隔：

```
XIAOMI_TOKEN_PLAN_API_KEY=***
```

当一个Key被限流时，Kioxus会自动切换到下一个Key。

---

# 第四部分：进阶内容

## 开发者模式

<details>
<summary>点击展开开发者模式内容</summary>

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
python src/run.py --provider mock    # 测试模式，不需要真实API Key

# 打包成exe
python src/build.py
python src/build.py --onefile        # 单文件模式
python src/build.py --clean          # 清理构建产物

# 运行测试
pytest test/                         # 全量测试（43个）
pytest test/ -v                      # 详细输出
pytest test/ -x                      # 遇到失败就停止
```

### 核心引擎模块

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

### 记忆系统模块

| 模块 | 文件 | 作用 |
|------|------|------|
| MemoryStore | `memory.py` | 四层文件存储 |
| MemoryRouter | `router.py` | 记忆路由、上下文组装 |
| MemorySearch | `search.py` | BM25搜索引擎 |
| Compressor | `compressor.py` | 压缩引擎（Flush Agent） |
| Janitor | `janitor.py` | 维护任务（flush/settle/compress） |
| TagDictionary | `tags.py` | 标签字典（防漂移） |

### 内置工具

| 工具 | 功能 | 沙箱 |
|------|------|------|
| `http_fetch` | 抓取网页内容 | — |
| `file_read` | 读文件（最多200行） | — |
| `file_write` | 写入/追加文件 | — |
| `file_list` | 列目录内容 | — |
| `code_exec` | 执行Python/JS代码 | ✅ 默认沙箱隔离 |
| `web_search` | 网页搜索 | — |

</details>

---

## 配置文件说明

<details>
<summary>点击展开配置文件说明</summary>

### 配置文件列表

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
    }
  },
  "default_provider": "xiaomi"
}
```

**字段说明**：
- `providers`：所有AI服务的配置
- `api_url`：AI服务的地址
- `api_key_env`：存API Key的环境变量名
- `model`：使用的模型名称
- `max_tokens`：最多生成多少个Token
- `temperature`：回答的随机性（0=最确定，1=最随机）
- `default_provider`：默认使用哪个AI服务

### .env

```
XIAOMI_TOKEN_PLAN_API_KEY=***
OPENAI_API_KEY=***
```

这个文件存放真实的API Key，不会上传到GitHub。

</details>

---

## LLM Provider配置

<details>
<summary>点击展开LLM Provider配置</summary>

### 支持的Provider

| Provider | 环境变量 | 默认模型 |
|----------|---------|---------|
| 小米 MiMo | `XIAOMI_TOKEN_PLAN_API_KEY` | mimo-v2.5-pro |
| MiniMax | `MINIMAX_API_KEY` | MiniMax-Text-01 |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
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

然后在 `.env` 中添加对应的API Key：

```
MY_PROVIDER_API_KEY=***
```

### 多Key轮换

支持每个Provider配多个Key，限流时自动切换。在 `.env` 中用逗号分隔：

```
XIAOMI_TOKEN_PLAN_API_KEY=***
```

### Model Failover

主Provider失败时自动尝试备用Provider。无需额外配置，注册多个Provider即可。

</details>

---

# 第五部分：参考

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-25 | v0.1 | 初始版本 |
| 2026-07-23 | v0.2 | Python重写，模块化架构 |
| 2026-08-10 | v0.3 | 验证器、沙箱、上下文预算 |
| 2026-08-30 | v0.3.0 | 开源发布，Provider注册制，多Key轮换，Failover |

---

## FAQ

### Q: Kioxus是什么？
A: Kioxus是一个AI助手，能自己思考、记忆、使用工具、验证回答。你可以把它理解为一个"本地版的ChatGPT"。

### Q: Kioxus免费吗？
A: Kioxus本身免费开源。但你需要一个AI服务的API Key，AI服务可能会收费。

### Q: 支持哪些AI服务？
A: 支持任意OpenAI兼容的API。内置小米MiMo和MiniMax，可自由添加。

### Q: API Key安全吗？
A: .env在.gitignore中，不会上传GitHub。代码内部使用Key轮换和限流重试。

### Q: 能离线使用吗？
A: 不行，需要网络连接AI服务。

### Q: 怎么添加新的AI服务？
A: 编辑config/kioxus.json，在providers中添加，然后在.env中填入API Key。

### Q: exe有多大？
A: 约34MB（含依赖），解压后双击即用。

### Q: 遇到问题怎么办？
A: 在 https://github.com/kioxus-1/kioxus/issues 提交问题。

---

## 开源协议

本项目基于 [MIT License](../LICENSE) 开源，可免费学习、使用和二次开发。

## 联系方式

作者：kioxus-1
仓库：https://github.com/kioxus-1/kioxus
