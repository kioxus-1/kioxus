# Kioxus 架构说明

## 核心循环

用户输入 → Input → Memory → Think → Plan → Act → Observe → Verify → Output → Reflect

## 核心引擎模块

| 模块 | 作用 |
|------|------|
| engine.py | 核心循环调度器 |
| input.py | 输入处理、意图识别 |
| context.py | 上下文组装、Token预算管理 |
| llm.py | LLM客户端（多Provider、多Key轮换、Failover） |
| output.py | 输出格式化 |
| session.py | 会话管理 |
| memory_bridge.py | 记忆系统桥接器 |
| reasoning.py | 推理引擎（direct/chain/reflect） |
| planner.py | 任务规划器 |
| decomposer.py | 目标分解器 |
| tools.py | 工具注册框架 |
| builtin_tools.py | 内置工具 |
| verifier.py | 输出验证器（5项检查） |
| sandbox.py | 代码执行沙箱（4级安全策略） |
| provider_registry.py | Provider插件注册制 |
| config_watcher.py | 配置热更新 |

## 记忆系统模块

| 模块 | 作用 |
|------|------|
| memory.py | 四层文件存储 |
| router.py | 记忆路由、上下文组装 |
| search.py | BM25搜索引擎 |
| compressor.py | 压缩引擎 |
| janitor.py | 维护任务 |
| tags.py | 标签字典（防漂移） |

## 三大原则

1. **对抗性验证** — Verifier独立审查输出（5项规则检查）
2. **硬边界隔离** — Sandbox4级安全策略
3. **可量化上下文** — ContextTracker Token预算追踪
