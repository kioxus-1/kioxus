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
- LLM：支持多种AI服务（小米MiMo、MiniMax等）
- 打包：PyInstaller（生成独立 exe）

## 项目结构

```
kioxus/
├── src/                     # 核心源码
│   ├── core/                #   核心引擎（17个模块）
│   ├── memory/              #   记忆系统（7个模块）
│   ├── gui/                 #   桌面界面
│   │   └── desktop.py       #     PyWebView桌面窗口
│   ├── main.py              #   系统入口
│   └── cli.py               #   命令行调试工具（开发者用）
│
├── config/                  # 配置文件
│   ├── config.example.yaml  #   配置模板
│   └── kioxus.json          #   LLM Provider配置
│
├── scripts/                 # 辅助脚本
│   └── build.py             #   打包脚本
│
├── examples/                # 使用示例
│   └── simple_demo.py       #   快速上手demo
│
├── docs/                    # 项目文档
│   ├── architecture.md      #   架构说明
│   ├── api.md               #   核心接口
│   └── install.md           #   安装指南
│
├── test/                    # 测试代码
│
├── requirements.txt         # Python依赖
├── requirements-dev.txt     # 开发测试依赖
├── README.md                # 项目说明
├── LICENSE                  # MIT协议
├── CHANGELOG.md             # 版本更新记录
├── CONTRIBUTING.md          # 贡献指南
└── .gitignore               # Git忽略规则
```

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus

# 2. 安装依赖
pip install -r requirements.txt

# 3. 复制配置并填入密钥
cp config/config.example.yaml config/config.yaml
# 编辑 config/config.yaml，填入你的 LLM Provider 信息
# 创建 .env 文件，填入 API Key

# 4. 运行
python src/main.py
```

### 其他运行方式

```bash
# 命令行调试（开发者）
python src/cli.py

# 快速体验
python examples/simple_demo.py

# 打包成exe
python scripts/build.py
```

### 下载exe（无需Python环境）

前往 [Releases](https://github.com/kioxus-1/kioxus/releases) 页面下载最新版本，解压双击即用。

## 功能介绍

- 自然语言对话，支持多轮上下文和记忆
- 链式推理引擎，支持直接推理、链式推理、反思三种模式
- 内置工具：网页抓取、文件读写、代码执行、网页搜索
- 代码执行沙箱，4级安全策略，进程级隔离
- 输出验证器，自动检查格式、相关性、安全性、一致性
- Token预算追踪，支持软限制和硬限制两种模式
- 四层记忆架构，BM25搜索，渐进压缩
- 可配置多种LLM Provider
- 桌面窗口（PyWebView）和命令行两种使用方式

## 测试

```bash
pytest test/                    # 全量测试（43个）
pytest test/ -x                 # 遇到第一个失败就停止
pytest test/ -v                 # 详细输出
```

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-25 | v0.1 | 初始版本 |
| 2026-07-23 | v0.2 | Python重写，模块化架构 |
| 2026-08-10 | v0.3 | 验证器、沙箱、上下文预算 |
| 2026-08-30 | v0.3.0 | 项目整理，开源发布 |

详见 [CHANGELOG.md](CHANGELOG.md)

## 开源协议

本项目基于 [MIT License](LICENSE) 开源，可免费学习、使用和二次开发。

## 贡献

欢迎提交 PR、Issue。详见 [CONTRIBUTING.md](CONTRIBUTING.md)

## 联系方式

作者：kioxus-1
仓库：https://github.com/kioxus-1/kioxus
