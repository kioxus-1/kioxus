# Kioxus

一款轻量、稳定、可拓展的自主Agent框架

---

## 项目简介

Kioxus 是一套开箱即用的自主Agent解决方案，能独立思考、记忆、验证自己的输出，适用于对话助手、自动化任务、代码执行等场景。

项目采用模块化架构，代码结构清晰、低耦合、易二次开发，适合学习、二次迭代与实际部署使用。

## 主要特性

- **结构规范**：核心引擎与记忆系统分层清晰，模块化设计，易于维护
- **开箱即用**：双击 exe 即可使用，无需安装环境，部署成本极低
- **稳定高效**：核心逻辑精简，内置验证机制自动纠错，运行稳定
- **高拓展性**：工具注册框架支持自定义扩展，模块可单独启用或关闭
- **轻量简洁**：无冗余依赖，资源占用低
- **完全开源**：代码透明，可自由学习、修改（MIT协议）

## 技术栈

- 语言：Python 3.11+
- 框架：Flask（Web服务）、PyWebView（桌面窗口）
- 数据存储：文件系统 + SQLite
- LLM：支持任意OpenAI兼容API（小米MiMo、MiniMax、OpenAI等）
- 打包：PyInstaller（生成独立 exe）

## 下载使用

前往 [Releases](https://github.com/kioxus-1/kioxus/releases) 页面下载最新版本：

1. 下载 `Kioxus.exe`
2. 双击运行
3. 在配置中填入你的API Key即可使用

不需要安装Python，不需要命令行，不需要任何开发环境。

---

<details>
<summary><b>🔧 开发者模式</b>（点击展开）</summary>

### 项目结构

```
kioxus/
├── src/                     # 核心源码
│   ├── core_v2/             #   核心引擎（15个模块）
│   ├── memory_v2/           #   记忆系统（7个模块）
│   ├── main.py              #   系统入口
│   ├── run.py               #   命令行调试
│   ├── desktop.py           #   桌面窗口（PyWebView）
│   └── build.py             #   打包脚本
│
├── config/                  # 配置文件
│   ├── config.example.yaml  #   配置模板
│   └── kioxus.json          #   LLM Provider配置
│
├── examples/                # 使用示例
├── docs/                    # 项目文档
├── test/                    # 测试代码
│
├── requirements.txt         # Python依赖
├── README.md                # 项目说明
├── LICENSE                  # MIT协议
└── .gitignore               # Git忽略规则
```

### 克隆项目

```bash
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置API Key

```bash
cp config/config.example.yaml config/config.yaml
```

编辑 `config/config.yaml`，在 `providers` 中添加你的LLM Provider。

创建 `.env` 文件，填入API Key：

```env
YOUR_API_KEY=***
```

### 命令行调试

```bash
python src/run.py
```

### 打包成exe

```bash
python src/build.py
```

输出在 `src/dist/Kioxus/` 目录。

### 运行测试

```bash
pytest test/                    # 全量测试（43个）
pytest test/ -v                 # 详细输出
```

### 功能模块

**核心引擎（core_v2）**

| 模块 | 作用 |
|------|------|
| engine.py | 核心循环调度器 |
| input.py | 输入处理、意图识别 |
| context.py | 上下文组装、Token预算管理 |
| llm.py | LLM客户端（多provider） |
| output.py | 输出格式化 |
| session.py | 会话管理 |
| memory_bridge.py | 记忆系统桥接器 |
| reasoning.py | 推理引擎（direct/chain/reflect） |
| planner.py | 任务规划器 |
| decomposer.py | 目标分解器 |
| tools.py | 工具注册框架 |
| builtin_tools.py | 内置工具（http/file/code_exec/web_search） |
| verifier.py | 输出验证器（5项检查） |
| sandbox.py | 代码执行沙箱（4级安全策略） |

**记忆系统（memory_v2）**

| 模块 | 作用 |
|------|------|
| memory.py | 四层文件存储 |
| router.py | 记忆路由、上下文组装 |
| search.py | BM25搜索引擎 |
| compressor.py | 压缩引擎 |
| janitor.py | 维护任务 |
| tags.py | 标签字典 |

### 高级拓展

- 可自定义工具注册到 `src/core_v2/tools.py`
- 可扩展LLM Provider到 `config/kioxus.json`
- 可对接前端页面实现可视化管理
- 可接入Docker一键部署

</details>

---

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-25 | v0.1 | 初始版本 |
| 2026-07-23 | v0.2 | Python重写，模块化架构 |
| 2026-08-10 | v0.3 | 验证器、沙箱、上下文预算 |
| 2026-08-30 | v0.3.0 | 项目整理，开源发布 |

## 开源协议

本项目基于 [MIT License](LICENSE) 开源，可免费学习、使用和二次开发。

## 欢迎 Star / Fork / PR

- 如果对你有帮助，欢迎 Star
- 欢迎 Fork 进行二次开发
- 欢迎提交 PR、Issue 交流优化

## 联系方式

作者：kioxus-1
更新时间：2026年08月30日
