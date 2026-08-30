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

## 项目结构

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
│   ├── config.example.yaml  #   配置模板（复制为config.yaml后填写）
│   └── kioxus.json          #   LLM Provider配置
│
├── examples/                # 使用示例
│   └── simple_demo.py       #   快速上手demo
│
├── docs/                    # 项目文档
├── test/                    # 测试代码
│
├── requirements.txt         # Python依赖
├── README.md                # 项目说明
├── LICENSE                  # MIT开源协议
└── .gitignore               # Git忽略规则
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置API Key

复制配置模板并填入你的API密钥：

```bash
cp config/config.example.yaml config/config.yaml
```

编辑 `config/config.yaml`，在 `providers` 中添加你自己的LLM Provider。

同时在项目根目录创建 `.env` 文件，填入API Key：

```env
YOUR_API_KEY=your_key_here
```

支持任意OpenAI兼容的API，不限于内置的小米MiMo和MiniMax。

### 4. 运行

```bash
# 用户：打包成exe双击使用
python src/build.py

# 开发者：命令行调试
python src/run.py

# 快速体验
python examples/simple_demo.py
```

## 功能介绍

- 自然语言对话，支持多轮上下文和记忆
- 链式推理引擎，支持直接推理、链式推理、反思三种模式
- 内置工具：网页抓取、文件读写、代码执行、网页搜索
- 代码执行沙箱，4级安全策略，进程级隔离
- 输出验证器，自动检查格式、相关性、安全性、一致性
- Token预算追踪，支持软限制和硬限制两种模式
- 四层记忆架构，BM25搜索，渐进压缩
- 可配置任意LLM Provider（通过config/kioxus.json）
- 桌面窗口（PyWebView）和命令行两种使用方式

## 测试

```bash
pytest test/                    # 全量测试（43个）
pytest test/ -x                 # 遇到第一个失败就停止
pytest test/ -v                 # 详细输出
```

## 高级拓展

- 可自定义工具注册到 `src/core_v2/tools.py`
- 可扩展LLM Provider到 `config/kioxus.json`
- 可对接前端页面实现可视化管理
- 可接入Docker一键部署
- 可新增定时任务、权限系统

## 版本历史

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-25 | v0.1 | 初始版本 |
| 2026-07-23 | v0.2 | Python重写，模块化架构 |
| 2026-08-10 | v0.3 | 验证器、沙箱、上下文预算 |
| 2026-08-30 | v0.3.0 | 项目整理，文档统一，开源发布 |

## 开源协议

本项目基于 [MIT License](LICENSE) 开源，可免费学习、使用和二次开发。

## 欢迎 Star / Fork / PR

- 如果对你有帮助，欢迎 Star
- 欢迎 Fork 进行二次开发
- 欢迎提交 PR、Issue 交流优化

## 联系方式

作者：kioxus-1
更新时间：2026年08月30日
