# Kioxus 安装指南

## 方式一：下载exe（推荐）

前往 https://github.com/kioxus-1/kioxus/releases 下载最新版，解压双击即用。

## 方式二：从源码安装

```bash
git clone https://github.com/kioxus-1/kioxus.git
cd kioxus
pip install -r requirements.txt
```

## 配置

```bash
cp config/config.example.yaml config/config.yaml
```

编辑 config/config.yaml，填入你的 LLM Provider 信息。

创建 .env 文件，填入 API Key：

```
YOUR_API_KEY=***
```

## 运行

```bash
# 命令行调试（开发者）
python src/cli.py

# 桌面窗口
python src/gui/desktop.py

# 快速体验
python examples/simple_demo.py
```

## 打包成exe

```bash
python scripts/build.py
```

## 运行测试

```bash
pytest tests/
```

开发依赖：

```bash
pip install -r requirements-dev.txt
```
