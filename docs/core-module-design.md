# Kioxus 主模块设计方案

_版本：v1.0_
_日期：2026-07-23_
_设计者：赵建东 & 皛_

---

## 一、定位

主模块是甲辰一号的**大脑**。所有行为从这里出发：接收输入、理解意图、调用记忆、推理思考、规划行动、调用工具、生成输出。

**核心信条**：主模块不是一个管道，它是一个**有思考能力的决策者**。

---

## 二、核心循环

甲辰一号的每一次交互，都遵循一个统一的循环：

```
输入 → 理解 → 回忆 → 思考 → 规划 → 行动 → 观察 → 输出 → 反思
```

```
┌──────────────────────────────────────────────────────────────┐
│                        主模块核心循环                          │
│                                                              │
│  ① 输入                                                     │
│     │  接收用户消息，解析格式，识别意图                         │
│     ▼                                                        │
│  ② 回忆                                                     │
│     │  调用 Memory Router，注入记忆上下文                      │
│     ▼                                                        │
│  ③ 思考                                                     │
│     │  链式推理，评估信息，形成判断                             │
│     ▼                                                        │
│  ④ 规划                                                     │
│     │  分解任务，确定步骤，选择工具                             │
│     ▼                                                        │
│  ⑤ 行动                                                     │
│     │  调用LLM生成响应，或调用工具执行操作                      │
│     ▼                                                        │
│  ⑥ 观察                                                     │
│     │  检查结果，验证是否符合预期                               │
│     ▼                                                        │
│  ⑦ 输出                                                     │
│     │  格式化响应，发送给用户                                  │
│     ▼                                                        │
│  ⑧ 反思                                                     │
│     │  评估本轮交互，决定是否写入记忆                           │
│     └──→ 回到 ①                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、模块拆分

主模块内部由 8 个子模块组成：

```
core/
├── engine.py        # 引擎 — 核心循环调度
├── input.py         # 输入 — 消息接收、格式解析、意图识别
├── context.py       # 上下文 — 组装完整上下文（记忆+人格+会话+环境）
├── reasoning.py     # 推理 — 链式思考、推理监控、置信度评估
├── planner.py       # 规划 — 任务分解、步骤规划、工具选择
├── llm.py           # LLM — 统一调用接口、多模型、流式输出
├── output.py        # 输出 — 响应生成、格式化、执行结果处理
└── session.py       # 会话 — 对话历史、checkpoint、恢复
```

### 3.1 引擎 (engine.py)

**职责**：调度核心循环，串联所有子模块。

```python
class Engine:
    """甲辰一号核心引擎"""

    def __init__(self, config, memory, tools, security):
        self.input = InputProcessor()
        self.context = ContextBuilder(memory)
        self.reasoning = ReasoningEngine()
        self.planner = Planner()
        self.llm = LLMClient(config)
        self.output = OutputHandler()
        self.session = SessionManager()

    def process(self, user_message: str) -> str:
        """处理一条用户消息，返回响应"""
        # ① 输入
        parsed = self.input.parse(user_message)

        # ② 回忆
        memory_context = self.context.build(parsed)

        # ③ 思考
        thought = self.reasoning.think(parsed, memory_context)

        # ④ 规划
        plan = self.planner.plan(thought)

        # ⑤ 行动
        if plan.needs_tool:
            result = self._execute_tool(plan)
        else:
            result = self.llm.generate(thought, plan)

        # ⑥ 观察
        observation = self.reasoning.observe(result, plan)

        # ⑦ 输出
        response = self.output.format(observation)

        # ⑧ 反思
        self._maybe_reflect(parsed, response, observation)

        # 记录会话
        self.session.add_turn(parsed, response)

        return response
```

**关键设计**：
- 单一入口 `process()`，所有行为从这里开始
- 每一步都是独立子模块，可单独测试和替换
- 反思是可选的（`_maybe_reflect`），不是每轮都触发

### 3.2 输入 (input.py)

**职责**：接收原始消息，解析为结构化数据。

```python
@dataclass
class ParsedInput:
    raw: str                    # 原始消息
    intent: str                 # 意图分类：chat / task / query / command
    entities: List[str]         # 提取的实体
    urgency: str                # 紧急度：low / normal / high
    needs_memory: bool          # 是否需要检索记忆
    needs_tools: bool           # 是否需要工具
    metadata: Dict              # 其他元信息
```

**意图识别**（Phase 1 用规则，Phase 2 用小模型）：

| 意图 | 触发条件 | 处理方式 |
|------|---------|---------|
| chat | 普通对话 | 直接LLM生成 |
| task | 需要执行操作 | 进入规划 |
| query | 需要检索信息 | 优先检索记忆/工具 |
| command | 明确指令（写文件、发消息等） | 直接执行 |

### 3.3 上下文 (context.py)

**职责**：组装完整的LLM上下文。

```
上下文组成：
┌─────────────────────────────────┐
│ System Prompt（人格+规则）        │  始终注入
├─────────────────────────────────┤
│ 记忆上下文（Memory Router输出）   │  按需注入
├─────────────────────────────────┤
│ 会话历史（最近N轮）              │  始终注入
├─────────────────────────────────┤
│ 环境信息（时间、系统状态等）      │  按需注入
├─────────────────────────────────┤
│ 用户消息                        │  始终注入
└─────────────────────────────────┘
```

**Token预算分配**（借鉴memory_v2的分层思路）：

| 层 | 预算占比 | 说明 |
|----|---------|------|
| System Prompt | 10% | 人格、规则、行为边界 |
| 记忆上下文 | 30% | Memory Router输出 |
| 会话历史 | 40% | 最近N轮对话 |
| 环境信息 | 5% | 时间、工具列表等 |
| 用户消息 | 15% | 当前输入 |

**上下文压缩**：当会话历史超过预算时，触发压缩：
1. 保留最近3轮完整对话
2. 更早的对话压缩为摘要
3. 摘要由LLM生成（代码层校验）

### 3.4 推理 (reasoning.py)

**职责**：链式思考、推理监控、置信度评估。

**推理模式**：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| 直接响应 | 不推理，直接回答 | 简单对话、问候 |
| 链式思考 | 一步一步推理 | 复杂问题、分析 |
| 反思推理 | 推理+自我验证 | 关键决策、高风险操作 |

**推理步骤**（借鉴stage4_reasoning_monitor）：

```python
@dataclass
class ReasoningStep:
    step_id: str
    content: str          # 思考内容
    step_type: str        # premise / inference / conclusion / verification
    confidence: float     # 0-1 置信度
    source_ids: List[str] # 依赖的前置步骤
```

**推理监控**：
- 每个推理步骤有置信度
- 如果某步置信度 < 0.5，标记为"推理链断裂"
- 断裂时：重新推理 或 询问用户澄清

### 3.5 规划 (planner.py)

**职责**：将思考结果转化为可执行的步骤。

```python
@dataclass
class Plan:
    goal: str                   # 目标
    steps: List[PlanStep]       # 步骤列表
    needs_tool: bool            # 是否需要工具
    estimated_complexity: str   # simple / medium / complex
    fallback: Optional[str]     # 备选方案

@dataclass
class PlanStep:
    step_id: str
    action: str                 # 动作描述
    tool: Optional[str]         # 需要的工具
    params: Dict                # 工具参数
    depends_on: List[str]       # 依赖的步骤
```

**规划策略**：
- **simple**（1-2步）：直接执行，不规划
- **medium**（3-5步）：简单规划，线性执行
- **complex**（5+步）：详细规划，可能有分支

**工具选择**：根据任务类型自动选择工具（Phase 1 用规则匹配，Phase 2 用LLM选择）

### 3.6 LLM (llm.py)

**职责**：统一的LLM调用接口。

**移植自stage18_llm_integration**，适配v2架构。

```python
class LLMClient:
    """统一LLM客户端"""

    def __init__(self, config):
        self.providers = {}       # provider_name -> client
        self.default_provider = None
        self.config = config

    def generate(self, context: str, plan: Plan = None, stream: bool = False) -> str:
        """生成响应"""
        messages = self._build_messages(context, plan)
        provider = self._select_provider(plan)
        return provider.chat(messages, stream=stream)

    def generate_structured(self, context: str, schema: dict) -> dict:
        """生成结构化输出（JSON）"""
        # 用于 Flush Agent、压缩等需要结构化输出的场景
        pass

    def _select_provider(self, plan: Plan):
        """根据任务选择模型"""
        # 简单任务 -> 小模型（省token）
        # 复杂任务 -> 大模型（高质量）
        # 结构化输出 -> 指定模型
        pass
```

**多模型支持**：

| 场景 | 模型选择 | 说明 |
|------|---------|------|
| 日常对话 | 默认模型 | 平衡质量和成本 |
| 复杂推理 | 大模型 | 需要深度思考 |
| Flush/压缩 | 小模型 | 结构化提取，不需要创造力 |
| 嵌入/向量 | 嵌入模型 | 语义检索 |

### 3.7 输出 (output.py)

**职责**：格式化响应、处理工具执行结果。

```python
class OutputHandler:
    """输出处理器"""

    def format(self, observation: Observation) -> str:
        """格式化最终响应"""
        if observation.is_tool_result:
            return self._format_tool_result(observation)
        elif observation.is_error:
            return self._format_error(observation)
        else:
            return self._format_normal(observation)

    def _format_tool_result(self, obs) -> str:
        """格式化工具执行结果"""
        pass

    def _format_error(self, obs) -> str:
        """格式化错误信息"""
        pass
```

**输出模式**：
- **同步**：等待完整响应后输出
- **流式**：边生成边输出（长响应）
- **结构化**：JSON格式输出（API调用场景）

### 3.8 会话 (session.py)

**职责**：对话历史管理、checkpoint、会话恢复。

**移植自stage22_productization/conversation_manager**，精简为单会话。

```python
class SessionManager:
    """会话管理器"""

    def __init__(self, storage_dir: Path):
        self.current_session: Optional[Session] = None
        self.storage_dir = storage_dir

    def start_session(self, session_id: str = None) -> Session:
        """开始新会话"""
        pass

    def add_turn(self, user_input: ParsedInput, response: str):
        """添加一轮对话"""
        pass

    def get_recent_history(self, n: int = 10) -> List[Dict]:
        """获取最近N轮对话"""
        pass

    def checkpoint(self):
        """保存checkpoint"""
        pass

    def restore(self, session_id: str) -> bool:
        """恢复会话"""
        pass

    def compress_history(self, llm_call):
        """压缩历史对话"""
        pass
```

**Checkpoint机制**：
- 每N轮对话自动checkpoint
- checkpoint包含：会话状态、记忆引用、当前任务上下文
- 恢复时：加载checkpoint + 最近记忆 = 无缝继续

---

## 四、新增模块（v0.3）

### 4.1 对抗性验证 (verifier.py)

**职责**：独立审查Agent输出，不看思考过程。

```python
class Verifier:
    """对抗性验证器 — 不信任任何Agent输出"""

    def verify(self, output, user_input, tool_name=None, tool_output=None, is_error=False):
        # 1. 格式检查（长度、空值）
        # 2. 工具结果校验（错误模式匹配）
        # 3. 相关性检查（输入输出关键词重叠）
        # 4. 安全检查（敏感信息泄露）
        # 5. 一致性检查（自相矛盾检测）
        return VerificationResult(verdict, checks, error_summary)
```

**关键设计**：
- 基于规则，不依赖LLM（避免"用AI验证AI"的循环）
- 5项检查：format / tool / relevance / safety / consistency
- 已集成到engine.py核心循环的步骤⑥.5

### 4.2 沙箱 (sandbox.py)

**职责**：代码执行隔离，策略驱动。

```python
class Sandbox:
    """代码沙箱执行器 — 硬边界隔离"""

    def execute(self, code, language="python"):
        # 1. 代码静态检查（阻断危险import/模式）
        # 2. 构建受限环境变量
        # 3. subprocess隔离执行
        # 4. 超时强制终止
        # 5. 输出大小限制
        return SandboxResult(success, stdout, stderr, ...)
```

**安全级别**：
| 级别 | 网络 | 超时 | 内存 | 阻断import |
|------|------|------|------|------------|
| STRICT | 禁止 | 5s | 128MB | os, subprocess, shutil |
| NORMAL | 禁止 | 10s | 256MB | os, subprocess, shutil |
| RELAXED | 允许 | 30s | 512MB | 无 |
| UNSAFE | 允许 | 60s | 1024MB | 无（需显式声明） |

### 4.3 Context追踪器 (context.py新增)

**职责**：追踪跨turn的Token累积使用量。

```python
class ContextTracker:
    def record(self, tokens) -> Dict:
        # 记录使用量，返回状态
        return {"status": {"needs_compression": bool, "budget_exceeded": bool}}

class ContextBudget:
    enforce: str = "soft"  # soft=截断, hard=报错
    compression_threshold: float = 0.8  # 80%触发压缩提示
```

---

## 五、自我进化（不是独立模块，是核心循环的一部分）

自我进化不是一个单独的模块，而是嵌入在核心循环中的**反思机制**：

### 4.1 反思触发

| 触发条件 | 反思类型 | 处理方式 |
|---------|---------|---------|
| 工具调用失败 | 即时反思 | 记录错误原因，修正下次行为 |
| 用户纠正 | 即时反思 | 更新核心记忆，调整行为规则 |
| 推理链断裂 | 即时反思 | 分析断裂原因，记录教训 |
| 会话结束 | 延迟反思 | 提炼本轮关键经验 |
| 定期触发 | 深度反思 | 分析模式，提炼SOP |

### 4.2 反思流程

```python
def _maybe_reflect(self, parsed, response, observation):
    """反思 — 核心循环的最后一步"""
    # 即时反思
    if observation.has_error:
        self._immediate_reflect(observation)

    # 用户纠正检测
    if self._is_user_correction(parsed):
        self._user_correction_reflect(parsed)

    # 延迟反思（每N轮触发一次）
    if self.session.turn_count % 10 == 0:
        self._delayed_reflect()
```

### 4.3 反思输出

反思的结果写入记忆模块：
- **P0 级教训** → `memory/core.md`（永久规则）
- **P1 级经验** → `memory/reflection/`（反思模块）
- **P2 级事实** → `memory/short-term/today.md`（今日记录）

---

## 五、与其他模块的接口

### 5.1 与记忆模块

```python
# 主模块调用记忆模块
from memory_v2 import get_router, save_memory

# 回忆
router = get_router()
context = router.build_context(user_message)

# 记忆
save_memory(layer="reflection", content="...", tags=["..."], priority="P0")
```

### 5.2 与工具模块

```python
# 主模块调用工具模块
class ToolInterface:
    def list_tools(self) -> List[ToolMetadata]
    def call_tool(self, tool_id: str, params: dict) -> ToolResult
    def has_tool(self, tool_id: str) -> bool
```

### 5.3 与配置模块

```python
# 主模块读取配置
class ConfigInterface:
    def get(self, key: str, default=None) -> Any
    def get_agent_config(self) -> AgentConfig  # 人格、行为边界
    def get_llm_config(self) -> LLMConfig      # 模型、API密钥
```

### 5.4 与调度模块

```python
# 调度模块触发主模块
scheduler.register_task("memory_flush", cron="55 23 * * *", handler=janitor.flush)
scheduler.register_task("daily_settle", cron="5 0 * * *", handler=janitor.settle)
scheduler.register_task("weekly_reflect", cron="0 10 * * 1", handler=engine.deep_reflect)
```

### 5.5 与安全模块

```python
# 主模块请求安全模块校验
security.check_permission(action="file_write", target="/path/to/file")
security.check_permission(action="tool_call", tool="send_message")
security.get_api_key(provider="minimax")
```

---

## 六、数据流示例

### 场景：用户说"帮我查一下今天的天气"

```
用户: "帮我查一下今天的天气"
    │
    ▼
① 输入: intent=query, needs_tools=True, needs_memory=False
    │
    ▼
② 回忆: Memory Router → 注入 core.md + today.md（天气相关记忆为空）
    │
    ▼
③ 思考: 用户想查天气 → 需要调用天气工具 → 简单任务，不需要深度推理
    │
    ▼
④ 规划: Plan(goal="查天气", steps=[Step(action="调用天气工具", tool="weather")])
    │
    ▼
⑤ 行动: ToolInterface.call_tool("weather", {"city": "auto"})
    │  结果: {"temp": 28, "weather": "晴", "city": "上海"}
    │
    ▼
⑥ 观察: 工具调用成功，结果有效
    │
    ▼
⑦ 输出: "今天上海晴天，28度。"
    │
    ▼
⑧ 反思: 无需反思（无错误、无纠正）
    │
    ▼
记录会话: session.add_turn(...)
```

### 场景：用户说"把这段代码改成TypeScript"

```
用户: "把这段代码改成TypeScript"
    │
    ▼
① 输入: intent=task, needs_tools=True, needs_memory=True
    │
    ▼
② 回忆: Memory Router → 注入 core.md（代码注释用中文）+ 反思层（TypeScript经验）
    │
    ▼
③ 思考: 需要读取代码 → 转换为TypeScript → 写回文件
    │  推理步骤:
    │  1. 用户偏好中文注释 [置信度: 1.0]
    │  2. 需要先读取当前代码 [置信度: 0.9]
    │  3. 转换为TypeScript [置信度: 0.8]
    │
    ▼
④ 规划: Plan(
    │    goal="代码转TypeScript",
    │    steps=[
    │      Step(1, "读取代码文件", tool="file_read"),
    │      Step(2, "转换为TypeScript", tool=None),  # LLM生成
    │      Step(3, "写入文件", tool="file_write"),
    │    ]
    │  )
    │
    ▼
⑤ 行动:
    │  Step 1: file_read → 获取代码
    │  Step 2: LLM生成TypeScript版本
    │  Step 3: file_write → 写入文件
    │
    ▼
⑥ 观察: 所有步骤成功
    │
    ▼
⑦ 输出: "已将代码转换为TypeScript，主要改动：..."
    │
    ▼
⑧ 反思: 记录这次转换的经验（如有新发现）
    │
    ▼
记录会话
```

---

## 七、核心引擎状态机

引擎在不同状态下有不同的行为：

```
         ┌─────────┐
         │  IDLE    │ ← 等待输入
         └────┬────┘
              │ 收到消息
              ▼
         ┌─────────┐
         │PROCESSING│ ← 处理中
         └────┬────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐
│THINK │ │TOOL  │ │ERROR │
│      │ │CALL  │ │      │
└──┬───┘ └──┬───┘ └──┬───┘
   │        │        │
   └────────┼────────┘
            ▼
       ┌─────────┐
       │ OUTPUT   │ ← 输出响应
       └────┬────┘
            │
            ▼
       ┌─────────┐
       │REFLECT   │ ← 反思（可选）
       └────┬────┘
            │
            ▼
         ┌─────────┐
         │  IDLE    │
         └─────────┘
```

---

## 八、文件结构

```
kioxus/
├── core_v2/
│   ├── __init__.py      # 统一入口
│   ├── engine.py        # 核心引擎（含Verifier集成）
│   ├── input.py         # 输入处理
│   ├── context.py       # 上下文组装 + ContextTracker + 硬限制
│   ├── reasoning.py     # 推理引擎
│   ├── planner.py       # 规划器
│   ├── decomposer.py    # 目标分解器
│   ├── llm.py           # LLM客户端
│   ├── output.py        # 输出处理
│   ├── session.py       # 会话管理
│   ├── tools.py         # 工具注册表
│   ├── builtin_tools.py # 内置工具（http/file/code_exec）
│   ├── verifier.py      # 对抗性验证（v0.3新增）
│   └── sandbox.py       # 代码执行沙箱（v0.3新增）
├── memory_v2/           # 记忆模块 ✅（精简版）
├── config/              # 配置
├── data/                # 运行数据
└── tests/               # 测试（40个）
```

---

## 九、实施路线

### Phase 1：最小可运行核心 ✅

- [x] engine.py — 核心循环骨架
- [x] input.py — 简单意图识别（规则）
- [x] context.py — 上下文组装（接memory_v2）
- [x] llm.py — LLM客户端（移植stage18）
- [x] output.py — 简单输出格式化
- [x] session.py — 基础会话管理（对话历史）

### Phase 2：推理与规划 ✅

- [x] reasoning.py — 链式思考、置信度评估
- [x] planner.py — 任务分解、工具选择
- [x] 推理监控（断裂检测）
- [x] decomposer.py — 目标分解器

### Phase 3：三原则落地 ✅（v0.3，2026-08-10）

- [x] verifier.py — 对抗性验证（5项规则检查）
- [x] sandbox.py — 硬边界隔离（4级安全策略）
- [x] context.py — ContextTracker + 硬限制模式
- [x] memory_v2精简 — 删除conflict/observer，简化search
- [x] 统一架构 — TypeScript归档，清理100+脚本
- [x] 测试重整 — 40个测试，39通过

### Phase 4：高级特性（待定）

- [ ] 流式输出
- [ ] 多模型选择策略
- [ ] 意图识别升级（小模型）
- [ ] Memory Flush完整实现（事务化、JSON Schema校验）
- [ ] 健康度指标监控
- [ ] 战略性遗忘（P3/P2自动销毁）

---

_设计方案 v1.1 — 2026-08-10更新_
_更新内容：Phase 1-3标记完成，新增verifier/sandbox/context_tracker描述_
