# Kioxus 记忆系统设计方案

_版本：v3.3_
_日期：2026-07-23（原版）/ 2026-08-10（状态更新）_
_设计者：赵建东 & 皛_

---

## 〇、实现状态总览

| 设计点 | 状态 | 说明 |
|--------|------|------|
| 四层文件结构 | ✅ 已实现 | core.md, reflection/, records/, short-term/ |
| core.md + today.md 强制注入 | ✅ 已实现 | Memory Router每次构建时注入 |
| 标签字典 | ✅ 已实现 | tags_dictionary.json + TagDictionary类 |
| save_memory工具 | ✅ 已实现 | JSON校验 + 来源追溯 |
| Memory Router | ✅ 已实现 | 关键词提取 + 分层Token预算 |
| BM25检索 | ✅ 已实现 | SimpleBM25，无外部依赖 |
| Memory Janitor | ✅ 已实现 | flush/settle/compress |
| Flush Agent | ✅ 已实现 | 压缩引擎 |
| 时间衰减 | ❌ 已删除 | 精简时移除，BM25直接检索 |
| RRF融合 | ❌ 已删除 | 精简时移除 |
| 冲突检测 | ❌ 已归档 | 未被任何代码使用，归档到archive/memory-legacy/ |
| 观察者 | ❌ 已归档 | 同上 |
| jieba分词 | ⏳ 未实现 | 实际用简单正则分词，Phase 2考虑接入 |
| overview.md概览 | ⏳ 未实现 | ≤10行的全貌概览 |
| 文件锁 | ⏳ 未实现 | today.md并发控制 |
| 健康度指标 | ⏳ 未实现 | 5个指标未埋点 |
| 战略性遗忘 | ⏳ 未实现 | P3 30天销毁，P2 180天销毁 |
| 压缩后自检 | ⏳ 未实现 | action保留、标签覆盖率校验 |
| 反思膨胀控制 | ⏳ 未实现 | 200行阈值 + 反思的反思 |
| 旬记/月记/年记压缩 | ⏳ 未实现 | 分层压缩流程 |

---

## 一、设计原则

1. **压缩不遗忘** — 细节永远在，只是藏得更深
2. **只记改变未来行为的东西** — 没有产生认知变化、没有新信息、没有影响决策的内容不记
3. **只留结论，不留过程；只留决定，不留讨论**
4. **记忆必须可检索** — 存了找不到等于没存
5. **记忆必须有边界** — 事实+行动条件+过期条件
6. **代码管逻辑，LLM管语义** — 计算、路由、校验交给确定性代码，LLM只负责文本生成和理解

---

## 二、核心架构：代码层与LLM层的职责分离

v3.0 最关键的架构决策：**不让LLM做它不擅长的事**。

```
┌─────────────────────────────────────────────────┐
│                   代码层（确定性）                  │
│                                                   │
│  Memory Router    Memory Janitor    Tag Validator │
│  评分计算          索引维护          格式校验       │
│  上下文组装        归档/销毁         标签字典       │
│  健康度监控        定时调度          Token 截断     │
└───────────────────────┬─────────────────────────┘
                        │
                   工具接口层
                        │
┌───────────────────────┴─────────────────────────┐
│                   LLM 层（语义）                   │
│                                                   │
│  文本压缩          反思生成          摘要提炼       │
│  记忆写入内容       行动边界描述       关联分析      │
└─────────────────────────────────────────────────┘
```

**职责划分**：

| 任务 | 谁做 | 为什么 |
|------|------|--------|
| 评分计算 | 代码 | LLM算数必出错 |
| 检索路由 | 代码 | 确定性决策，不消耗token |
| 标签校验 | 代码+字典 | 防止标签漂移 |
| Token截断 | 代码 | 精确控制 |
| 归档/销毁 | 代码 | 确定性操作 |
| 文本压缩 | LLM | 语义理解 |
| 反思生成 | LLM | 需要认知能力 |
| 行动边界描述 | LLM | 需要理解上下文 |

---

## 三、四层记忆结构

```
┌─────────────────────────────────┐
│           核心层 (core.md)       │  ← agent的个体信息，稳定不轻易变
├─────────────────────────────────┤
│      反思与总结 (reflection/)    │  ← 认知迭代，权重高于记录，模块动态增加
├─────────────────────────────────┤
│        记录层 (records/)         │  ← 日志→旬记→月记→年记，分层压缩
├─────────────────────────────────┤
│       短期层 (today.md)          │  ← 今日内容，每天清空
└─────────────────────────────────┘
```

### 3.1 核心层

| 项目 | 说明 |
|------|------|
| 文件 | `core.md`（单文件） |
| 内容 | agent的身份、价值观、能力边界、与用户的关系、长期规则、行动禁区 |
| 大小 | 控制在 100-200 行以内 |
| 检索 | 不需要，每次对话**强制注入** |
| 更新时机 | 事件触发（用户强烈纠正、重大认知冲突）为主；后期加入每周异步审视 |

core.md 是唯一一个每次对话都完整注入的文件。它必须精炼——每一行都是agent不可动摇的基石。

### 3.2 反思与总结层

| 项目 | 说明 |
|------|------|
| 位置 | `reflection/` 文件夹 |
| 结构 | 每个模块一个 `.md` 文件，模块动态增加 |
| 内容 | 认知迭代、错误教训、关系变化、学习收获等 |
| 检索 | 独立检索系统（见第五节） |
| 更新时机 | 分级触发（见第六节） |
| 单文件阈值 | 不超过 200 行 |
| 时间衰减 | 旧反思自动降权，30天半衰期 |

**反思模块示例**（动态增加，不固定）：
- `认知.md` — 认知迭代
- `关系.md` — 与用户关系的变化
- `错误.md` — 错误与教训
- `学习.md` — 学到的新东西

**膨胀控制**：
- 单个反思文件不得超过 200 行
- Janitor 检测到接近阈值时，触发"反思的反思"：LLM 将具体案例压缩为 ~20 行 SOP，原始内容归档

### 3.3 记录层

| 项目 | 说明 |
|------|------|
| 位置 | `records/年/月/` 目录 |
| 结构 | 日志（daily/）→ 旬记 → 月记 → 年记 |
| 检索 | 独立检索系统（见第五节） |
| 压缩规则 | 只留结论，不留过程；只留决定，不留讨论 |

**时间分旬**：
- 上旬：1-10号
- 中旬：11-20号
- 下旬：21-月末

**压缩节奏**：

| 操作 | 触发时间 | 内容 |
|------|---------|------|
| 上旬旬记 | 11号 | 压缩1-10号日志 |
| 中旬旬记 | 21号 | 压缩11-20号日志 |
| 下旬旬记 | 1号 | 压缩21-月末日志 |
| 月记 | 1号 | 压缩上月3份旬记 |
| 年记 | 1月1号 | 压缩去年12份月记 |

**压缩不只是精简，是带评分的晋升**：
- 代码层计算每条记忆的得分（检索频率、时效性、用户强化、关联密度）
- 得分高的优先保留，得分低的精简或归档
- LLM只负责对高分记忆做文本压缩

### 3.4 短期层

| 项目 | 说明 |
|------|------|
| 文件 | `short-term/today.md`（单文件） |
| 内容 | 今日对话上下文、未完成事项、当前情绪/氛围 |
| 检索 | 不需要，每次对话**强制注入** |
| 生命周期 | 每天清空 |

**today.md 与 daily/ 的流转机制**：

1. **工作区模式**：对话过程中，agent 的所有短期记忆只追加写入 `short-term/today.md`
2. **Memory Flush**（结算前）：Janitor 唤起 Flush Agent（小模型），审视 today.md，提取 P0-P2 关键信息，输出结构化 JSON
3. **每日结算**：Janitor 将 Flush Agent 的输出写入 `daily/YYYY-MM-DD.md`
4. **清空**：结算完成后，Janitor 物理清空 `today.md`

---

## 四、记忆来源与写入协议

### 4.1 记忆来源

| 层 | 记什么 |
|---|--------|
| 核心 | 身份、价值观、能力边界、用户信息、行动禁区 |
| 反思 | 选择及结果、被改变的认知、错误教训、用户教的东西 |
| 记录 | 对话摘要、操作及结果、外部事件、新知识新技能 |
| 短期 | 今日对话、未完成事项、当前氛围 |

### 4.2 Action-Sensitive Memory（行动敏感记忆）

记忆不只是事实，还有行动边界。当一条记忆涉及以下情况时，必须同时记录行动条件：

| 条件 | 示例 |
|------|------|
| 需要审批 | "修改配置文件前必须问用户" |
| 临时约束 | "这个API正在重构，本周不要动" |
| 过期条件 | "这个信息来自未验证来源，确认后才能固化" |
| 来源权威性 | "用户亲口说的 vs 网上搜到的" |

### 4.3 记忆写入协议

agent 调用 `save_memory` 工具时，必须严格遵守以下格式：

```json
{
  "layer": "reflection",
  "module": "错误",
  "content": "[事实] 用户环境使用的是 Python 3.8，不支持 match-case 语法。\n[行动] 生成 Python 代码时，必须使用 if-elif-else 替代 match-case。",
  "tags": ["python", "语法兼容性", "代码生成"],
  "priority": "P0",
  "source_type": "user"
}
```

**约束**：
- `[事实]` 必须是客观发生的事或明确的结论，禁止主观猜测
- `[行动]` 必须明确指出如何改变未来行为（If-Then 格式最佳）。如果没有行动改变，则不应保存
- `tags` 必须从标准标签库中选择（见第五节）
- `priority` 必须是 P0/P1/P2/P3
- `source_type` 必须是 user/agent/external（代码层根据上下文自动填入，agent 可覆写）

---

## 五、检索系统

### 5.1 标签字典（防止标签漂移）

在 `memory/` 根目录维护 `tags_dictionary.json`：

```json
{
  "version": 1,
  "tags": [
    "python", "typescript", "javascript",
    "错误", "认知", "关系", "学习",
    "用户偏好", "项目配置", "代码生成",
    "决策模式", "沟通方式", "工作流"
  ],
  "aliases": {
    "ts": "typescript",
    "js": "javascript",
    "前端": "typescript"
  },
  "tag_tree": {
    "代码生成": ["语法兼容性", "工作流", "项目配置"],
    "沟通方式": ["用户偏好", "关系"],
    "决策模式": ["认知", "错误"]
  }
}
```

**校验流程**：
1. agent 调用 `save_memory`，传入 tags
2. 代码层检查每个 tag 是否在字典中
3. 不在字典中 → 检查 aliases 映射 → 仍无匹配 → 检查语义相似度（Phase 2 embedding，Phase 1 拒绝写入，要求 agent 重新选择
4. 标签字典随 agent 成长动态扩展，但必须由代码层管理

**标签生命周期管理**：

| 状态 | 说明 | 处理方式 |
|------|------|----------|
| 活跃 | 正在使用的标签 | 参与检索和校验 |
| 待定 | 新提议但未确认 | 仅警告，不拒绝写入 |
| 废弃 | 语义重复或过时 | alias 指向合并目标 |
| 归档 | 完全废弃 | 从字典移除 |

**相似标签合并**：当 agent 写入已有标签的近义词时，代码层检查语义相似度，相似度 > 0.85 自动建立 alias 映射。alias 双向维护：`A → B` 建立后，检索 B 也能匹配到 A 相关内容。

**标签维护节奏**：每月底 Janitor 生成“标签膨胀报告”（增长最快的标签、从未使用的标签），agent 在周审视时决定是否合并。

### 5.2 Memory Router（记忆路由器）

不让主 Agent 自己决定"要不要检索"。代码层做路由：

```
用户消息到达
    │
    ├─→ [Memory Router]（代码层）
    │     ├─ 注入 core.md（始终）
    │     ├─ 注入 today.md（始终）
    │     ├─ 注入 overview.md（始终，≤10行）
    │     ├─ 提取检索关键词
    │     ├─ 检索 reflection/ → 取 top N 结果
    │     ├─ 检索 records/   → 取 top N 结果
    │     └─ 组装完整上下文（Token 截断）
    │
    └─→ [Main Agent]（LLM层，专注于回答）
```

**Router 的确定性逻辑**：
- 始终注入 core.md + today.md + overview.md（概览，≤10行）
- 从用户消息中提取关键词（代码实现，见下方）
- 用关键词 grep Frontmatter，筛选候选文件
- 读取候选文件，按相关性排序
- Token 截断：分层预算（见下方）
- 检索无结果时不注入噪音

**关键词提取（Phase 1）**：基于 jieba 分词 + 同义词扩展

```python
import jieba

def extract_keywords(message: str) -> list[str]:
    # 1. 分词 + 词性标注，只保留名词和动词
    words = jieba.posseg.cut(message)
    keywords = [w.word for w in words if w.flag in ['n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn']]
    # 2. 去停用词
    stopwords = load_stopwords()
    keywords = [k for k in keywords if k not in stopwords]
    # 3. 同义词扩展（基于标签字典的 aliases）
    expanded = []
    for kw in keywords:
        expanded.append(kw)
        if kw in tags_aliases:
            expanded.append(tags_aliases[kw])
    return list(set(expanded))
```

Phase 2 接入 embedding 后，关键词+向量混合检索。Phase 1 和 Phase 2 的索引结构兼容（Frontmatter tags 在 Phase 2 继续有效）。

**分层 Token 预算**：

| 层级 | 强制注入 | 预算占比 | 说明 |
|------|---------|---------|------|
| core.md | 是 | 5% | 固定上限 |
| today.md | 是 | 5% | 固定上限 |
| reflection/ | 按需 | 10% | top N 按相关性注入 |
| records/ | 按需 | 10% | top N 按相关性注入 |

总预算 30%。某层需要更多 Token 时可从其他层“借用”，但总额不超。复杂任务（用户显式要求“全面回顾”）可临时放宽到 40%，响应开头注明。健康度监控跟踪 Token 限制导致质量下降的频率，> 10% 时自动调整阈值。

### 5.3 两阶段检索策略

**阶段一（初期）**：关键词检索 + 极简索引
- Frontmatter 标签 + grep-first 漏斗模型
- 极简索引文件（≤30行）
- 无外部依赖

**阶段二（后期）**：语义检索
- 接入 embedding provider（Ollama 本地模型）
- 向量相似度 + 关键词混合检索
- 索引结构在阶段一就设计好

### 5.4 记录层检索

**极简索引**：`records/index.md`（≤30 行）

**Frontmatter 标签**：
```yaml
---
period: "2026-07 中旬"
date_range: "2026-07-11 ~ 2026-07-20"
topics: [项目进展, 用户状态, 技术问题]
recall_count: 0          # 代码层维护，被检索时自动+1
last_recalled: null
source: null             # 来源追溯：对话ID或"agent反思"
source_type: "agent"     # user / agent / external
created: 2026-07-21
---
```

### 5.5 反思层检索

**极简索引**：`reflection/index.md`（≤30 行）

**Frontmatter 标签**：
```yaml
---
module: 认知
tags: [决策模式, 认知偏差, 沟通方式]
recall_count: 3
last_recalled: 2026-07-20
source: "对话 #2026-07-20-09:00"
source_type: "agent"
last_updated: 2026-07-23
---
```

### 5.6 跨模块关联

物理上单点存储，逻辑上标签关联。

**懒加载策略**：不是每次更新都扫描全量邻域，只在以下情况触发邻域检查：
- 更新目标标签是核心标签（core tags，预定义）
- 更新内容的 action 字段包含“必须”、“禁止”、“不要”等强约束词
- 更新优先级为 P0/P1

**邻域扫描范围限制**：通过标签字典的 `tag_tree` 定义“近邻”范围，超出范围的记忆不检查。

**tag_tree 冷启动**：Phase 1 不预设 tag_tree，改为**从标签共现中自动学习**——如果“代码生成”和“语法兼容性”经常出现在同一条记忆里，代码层自动建立它们的关联（共现次数 > 5 次即固化为邻域关系）。积累到一定量后再人工固化为 tag_tree。

**冲突分级处理**：

| 冲突类型 | 处理方式 |
|---------|----------|
| 直接矛盾（“必须用A” vs “必须用B”） | 立即告警，要求 agent 解决后再写入 |
| 覆盖关系（新记忆更具体，旧的更笼统） | 自动归档旧记忆，保留新记忆 |
| 弱关联（只是语气不一致） | 记录到冲突日志，不阻塞写入 |

**冲突日志**：Janitor 每月生成“冲突日志报告”，agent 在周审视时决定是否手动修补。

---

## 六、反思触发机制

| 级别 | 触发时机 | 谁做 | 内容 |
|------|---------|------|------|
| 即时反思 | 工具调用失败、报错 | LLM | 修正当前步骤，记录错误原因 |
| 会话结束反思 | 对话结束或上下文即将压缩 | LLM | 保存本轮最关键的经验 |
| Memory Flush | 每天23:55（Janitor调度） | Flush Agent（小模型） | 审视today.md，提取P0-P2关键信息 |
| 定期沉淀 | 每周（Janitor调度） | LLM | 聚合分析天级记忆，提炼SOP |

**Memory Flush 的双Agent实现**：
- 主Agent只负责对话和往today.md追加原始信息
- Flush Agent（小模型，如Qwen2.5-7B）在每天23:55被Janitor唤起
- 输入：today.md全文 + 固定Prompt
- 任务：提取P0-P2关键信息，输出结构化JSON
- Janitor拿到JSON，校验后写入daily/，清空today.md

**Flush Agent 输出 JSON Schema**：
```json
{
  "date": "2026-07-23",
  "priority_summary": {
    "P0": [{"fact": "...", "action": "...", "tags": ["..."]}],
    "P1": [{"fact": "...", "action": "...", "tags": ["..."]}],
    "P2": [{"fact": "...", "action": "...", "tags": ["..."]}]
  },
  "unfinished_tasks": ["..."],
  "atmosphere": "..."
}
```

**回退策略**：JSON Schema 校验失败 → Janitor 不写入，保留 today.md 原文并告警，等待人工介入或主 Agent 下次会话时处理。Schema 带版本号，Janitor 读取时校验版本，防止格式错位。

**调度冲突防护**：
- 23:55 Flush Agent 审视 today.md，生成 `today_pending.json`
- 23:56+ 用户新消息 → 写入 `today_new.md`
- 00:05 Janitor 合并 `today_pending.json` + `today_new.md` → 写入 `daily/YYYY-MM-DD.md`
- 清空 today.md + today_new.md
- Flush 操作事务化：执行前先重命名为 `today_backup.md`，完成后删除，失败则恢复

---

## 七、压缩质量与记忆保鲜

### 7.1 带评分的晋升机制

**代码层计算得分**（不让LLM算数）：

```python
def calculate_score(memory):
    # 从Frontmatter读取
    recall_count = memory.recall_count
    days_since_created = (now - memory.created).days
    user_reinforced = memory.user_reinforced  # bool
   关联数 = len(memory.tags)  # 简化：标签数近似关联密度
    
    score = (
        min(recall_count / 10, 1.0) * 0.30 +      # 检索频率（上限10次封顶）
        max(1 - days_since_created / 30, 0) * 0.25 + # 时效性（30天半衰期）
        (1.0 if user_reinforced else 0.0) * 0.25 +   # 用户强化
        min(关联数 / 5, 1.0) * 0.20                   # 关联密度
    )
    return score
```

**晋升流程**：
1. Janitor 读取所有记忆的 Frontmatter
2. 代码层计算每条记忆的得分
3. 得分排序，取 top N
4. 只把 top N 的记忆内容喂给 LLM，让 LLM 执行文本压缩
5. LLM 输出压缩结果，代码层写入目标文件

### 7.2 战略性遗忘

不是所有东西都该永远留着。引入**物理销毁**机制：

| 优先级 | 条件 | 处理 |
|--------|------|------|
| P3（噪音） | 写入后30天未被检索 | 物理删除 |
| P2（中优） | 180天 recall_count == 0 | 物理删除 |
| P1（高优） | 365天未被检索 | 移入archive/ |
| P0（必存） | 永不销毁 | 保留在活跃文件 |

**销毁由代码层执行**，不经过LLM。Janitor定期扫描，符合条件的直接删除。

### 7.3 时间衰减（Temporal Decay）

- **记录层**：旬记→月记→年记的自然压缩，天然衰减
- **反思层**：旧反思自动降权，30天半衰期。代码层在检索时根据 `created` 字段计算衰减系数
- **核心层**：不衰减

### 7.4 记忆保鲜与归档

- 召回历史记忆时，如果与当前环境冲突，当下证据获胜
- 被标记为 `[已过时]` 的记忆：代码层剪切到 `memory/archive/`
- 归档区不参与日常检索

### 7.5 压缩后自检

**代码层硬性校验**（主要）：

```python
def validate_compression(original, compressed):
    # 1. 所有 action 字段必须保留
    original_actions = extract_actions(original)
    compressed_actions = extract_actions(compressed)
    assert len(compressed_actions) == len(original_actions), "action字段丢失"

    # 2. 所有 P0/P1 优先级的记忆必须保留
    original_p0_p1 = extract_by_priority(original, ["P0", "P1"])
    compressed_p0_p1 = extract_by_priority(compressed, ["P0", "P1"])
    assert compressed_p0_p1.contains(original_p0_p1), "P0/P1记忆丢失"

    # 3. 标签覆盖率必须 > 90%
    original_tags = extract_tags(original)
    compressed_tags = extract_tags(compressed)
    coverage = len(compressed_tags & original_tags) / len(original_tags)
    assert coverage > 0.9, f"标签覆盖率不足: {coverage}"
```

**压缩质量评分**：代码层计算压缩质量分数，低于 0.7 触发“重新压缩”，不直接写入。

**LLM 语义自检**（辅助）：代码层校验通过后，LLM 二次审查语义完整性——是否能在不看原文的情况下独立理解压缩结果。

---

## 八、记忆优先级（压缩判断矩阵）

| 优先级 | 类型 | 判断标准 | 处理方式 |
|--------|------|---------|---------|
| P0（必存） | 血泪教训 | agent第二次犯同样的错；用户明确的强偏好/禁忌；行动禁区 | 写入 core.md 或反思层，每次对话强制注入 |
| P1（高优） | 可复用经验 | 未来多个任务都会用到的通用规律；成功跑通的复杂操作 | 沉淀为反思模块或 SOP |
| P2（中优） | 事实与配置 | 项目结构、API密钥、特定路径 | 存入记录层，180天未检索则销毁 |
| P3（丢弃） | 噪音 | 临时排障猜测、未验证假设、易失状态 | 30天后物理删除 |

---

## 九、健康度指标

代码层埋点监控，不让系统跑崩了才去优化：

| 指标 | 计算方式 | 健康范围 | 说明 |
|------|---------|---------|------|
| 检索命中率 | 被引用的检索结果 / 总检索结果 | > 30% | 低了说明检索策略或标签有问题 |
| 写入拒绝率 | 被拦截的写入尝试 / 总写入尝试 | < 10% | 高了说明Prompt需要优化或标签库需要扩展 |
| 上下文Token占比 | 召回记忆Token / 总上下文Token | < 30% | 高了说明注入策略需要收紧 |
| 记忆总量 | 活跃文件总行数 | core<200, 模块<200 | 超限触发压缩/归档 |
| 归档区增长 | archive/ 文件总大小 | 增速应递减 | 持续增长说明战略性遗忘未生效 |

---

## 十、文件结构

```
kioxus/
├── memory/
│   ├── core.md                    # 核心层（单文件，每次对话强制注入）
│   ├── overview.md                # 记忆全貌概览（≤10行，Janitor自动更新）
│   ├── tags_dictionary.json       # 标签字典（代码层维护）
│   ├── reflection/                # 反思与总结层
│   │   ├── index.md               # 反思层索引（≤30行）
│   │   ├── 认知.md
│   │   ├── 关系.md
│   │   ├── 错误.md
│   │   ├── 学习.md
│   │   └── ...                    # 动态增加，单文件不超过200行
│   ├── records/                   # 记录层
│   │   ├── index.md               # 记录层索引（≤30行）
│   │   ├── 2026/
│   │   │   ├── 07/
│   │   │   │   ├── 上旬.md
│   │   │   │   ├── 中旬.md
│   │   │   │   ├── 下旬.md
│   │   │   │   └── 月记.md
│   │   │   └── ...
│   │   └── 年记.md
│   ├── short-term/                # 短期层
│   │   ├── today.md               # 工作区，每天清空
│   │   ├── today_new.md           # Flush安全窗口期间的新消息
│   │   └── today_pending.json     # Flush Agent的输出缓冲
│   ├── daily/                     # 原始日志（Janitor从today.md结算生成）
│   │   └── 2026-07-23.md
│   └── archive/                   # 归档区（不参与日常检索）
│       ├── reflection_2026Q2.md
│       └── ...
```

---

## 十一、后台维护（Memory Janitor）

通过 Cron Job 定期执行：

| 任务 | 频率 | 执行者 | 内容 |
|------|------|--------|------|
| Memory Flush | 每天23:55 | Flush Agent（小模型） | 审视today.md，提取P0-P2信息 |
| 日志整理 | 每天0点 | 代码 | 将Flush输出写入daily/，清空today.md |
| 旬记压缩 | 每旬第一天 | 代码+LLM | 代码评分排序，LLM压缩top N，代码写入 |
| 月记压缩 | 每月1号 | 代码+LLM | 同上 |
| 年记压缩 | 1月1号 | 代码+LLM | 同上 |
| 索引更新 | 每次压缩后 | 代码 | 更新记录层和反思层的索引文件 |
| 概览更新 | 每次压缩后 | 代码 | 更新 overview.md（≤10行：记忆总量、各层分布、最近重点） |
| 归档清理 | 每次压缩后 | 代码 | 过时记忆移入archive/ |
| 战略性遗忘 | 每月1号 | 代码 | P3超30天物理删除，P2超180天未检索物理删除 |
| 反思沉淀 | 每周一次 | LLM | 聚合分析天级记忆，提炼SOP |
| core.md审视 | 每周一次（后期） | LLM | 分析近期记忆，提炼核心规则 |
| 标签维护 | 每月底 | 代码 | 生成标签膨胀报告（增长最快、从未使用的标签） |
| 冲突日志 | 每月底 | 代码 | 生成跨模块冲突报告 |
| 健康度报告 | 每周一次 | 代码 | 计算并输出健康度指标 |

**并发安全（文件锁）**：

Janitor 和 agent 可能同时操作 today.md。引入轻量文件锁：

- agent 写入 today.md 前：检查 `today.md.lock` 是否存在
  - 存在 → 等待（最多10秒），重试
  - 不存在 → 创建锁，写入，释放锁
- Janitor Flush 前：创建 `today.md.lock`，执行 Flush，释放锁
- 锁文件包含持有者标识和时间戳，超时60秒自动释放（防止死锁）

单agent单对话场景下极少触发，但作为防御性设计必须有。

---

## 十二、数据流示例

以一个完整的一天为例，走通记忆系统的全流程：

### 场景：2026年7月23日，甲辰一号的一天

**09:00 — 对话开始**

```
用户消息到达
    │
    ├─→ [Memory Router] 启动
    │     ├─ 读取 core.md → 注入（全文，~150行）
    │     ├─ 读取 short-term/today.md → 注入（全文）
    │     ├─ jieba 提取关键词：["项目", "Kioxus", "记忆系统"]
    │     ├─ grep reflection/index.md → 命中“认知.md”
    │     ├─ grep records/index.md → 命中“2026-07 中旬.md”
    │     ├─ 计算 Token 预算：core 5% + today 5% + reflection 10% + records 10%
    │     └─ 组装上下文 → 发送给主 Agent
    │
    └─→ [主 Agent] 生成回复
```

**09:30 — Agent 学到新东西**

用户说：“甲辰一号的压缩逻辑要按旬来算，不是按周。”

Agent 调用 `save_memory`：
```json
{
  "layer": "reflection",
  "module": "认知",
  "content": "[事实] 用户明确：记忆压缩按旬（1-10/11-20/21-月末），不是按周。\n[行动] 所有压缩相关代码和文档，使用旬而非周作为时间单位。",
  "tags": ["记忆系统", "压缩逻辑"],
  "priority": "P0"
}
```

代码层：
1. 校验 tags → “记忆系统”和“压缩逻辑”都在字典中 ✅
2. 校验 JSON Schema → 字段完整 ✅
3. 写入 `reflection/认知.md`，更新 Frontmatter
4. 更新 `reflection/index.md`
5. 追加到 `short-term/today.md`

**14:00 — 用户纠正**

用户说：“我说过多少次了，不要用英文注释！”

Agent 调用 `save_memory`：
```json
{
  "layer": "core",
  "module": null,
  "content": "[事实] 用户强烈要求：代码注释必须用中文，不要用英文。\n[行动] 所有代码注释默认中文。这是硬性规则，不可违反。",
  "tags": ["代码风格", "用户偏好"],
  "priority": "P0"
}
```

代码层：识别 priority=P0 且 source_type=user → 写入 `core.md`（P0+用户直接表达 = 核心规则）

**23:55 — Memory Flush**

Janitor 唤起 Flush Agent：
- 输入：today.md 全文
- Flush Agent 输出：
```json
{
  "date": "2026-07-23",
  "priority_summary": {
    "P0": [
      {"fact": "压缩按旬算", "action": "代码和文档用旬", "tags": ["记忆系统"]},
      {"fact": "注释用中文", "action": "代码注释中文", "tags": ["代码风格"]}
    ],
    "P1": [],
    "P2": [{"fact": "讨论了OpenClaw记忆系统对比", "action": "参考OpenClaw设计", "tags": ["OpenClaw"]}]
  },
  "unfinished_tasks": ["完成v3.2方案整合"],
  "atmosphere": "积极，有进展"
}
```
- 代码层校验 JSON Schema ✅
- 写入 `today_pending.json`

**00:05 — Janitor 结算**

- 检查 `today_new.md`（23:56-00:00期间的新消息）→ 为空
- 读取 `today_pending.json`
- 写入 `daily/2026-07-23.md`
- 清空 `today.md`
- 删除 `today_pending.json`

**7月25日 — 反思层邻域检测（共现学习）**

代码层发现：“记忆系统”和“压缩逻辑”在近3天共现了6次（> 5次阈值）→ 自动建立邻域关系，写入 `tags_dictionary.json` 的 `tag_tree`。

**7月31日 — 标签维护**

Janitor 生成标签膨胀报告：
- 增长最快：“记忆系统”（本月新增12条）
- 从未使用：“性能优化”（0条引用）
- 近义词候选：“代码风格”和“编码规范”（相似度 0.88）

Agent 在周审视时决定：合并“代码风格”和“编码规范”，保留“代码风格”。

---

## 十三、实施路线

### Phase 1：基础记忆系统（MVP）

最小可用版本，不依赖外部服务：

- [ ] 四层文件结构
- [ ] core.md + today.md 强制注入
- [ ] 标签字典 (`tags_dictionary.json`) + 生命周期管理 + 共现学习冷启动
- [ ] `save_memory` 工具（带 JSON Schema 校验 + 来源追溯）
- [ ] Memory Router（jieba 分词 + 同义词扩展）
- [ ] Frontmatter + 极简索引（≤30行）
- [ ] Memory Flush（Flush Agent + JSON Schema 校验 + 回退策略）
- [ ] 每日结算（事务化：today_pending.json + today_new.md 合并）
- [ ] P0-P3 优先级判断（代码层）
- [ ] 压缩后代码层硬性校验（action保留、P0/P1保留、标签覆盖率）
- [ ] 文件锁（today.md 并发安全）
- [ ] overview.md 自动生成
- [ ] 基本健康度指标

### Phase 2：压缩与遗忘

实现完整的压缩和遗忘体系：

- [ ] 旬记压缩（代码评分 + LLM压缩）
- [ ] 月记/年记压缩
- [ ] 反思膨胀控制（200行阈值 + 反思的反思）
- [ ] 归档机制（archive/）
- [ ] 战略性遗忘（P3 30天销毁，P2 180天销毁）
- [ ] 时间衰减（反思层30天半衰期）
- [ ] 压缩后自检
- [ ] 相干邻域审计（跨模块冲突检测）

### Phase 3：智能检索与主动召回

- [ ] 接入 embedding provider（Ollama 本地模型）
- [ ] 混合检索（向量 + 关键词）
- [ ] Action-Sensitive Memory（行动边界标注）
- [ ] 检索频率统计与晋升评分优化
- [ ] 健康度报告自动化

### Phase 4：高级特性

- [ ] 每周 core.md 异步审视
- [ ] 记忆全貌概览（agent快速了解自己有什么记忆）
- [ ] 记忆可视化（Dashboard）
- [ ] 跨Agent记忆共享（多Kioxus实例）

---

_设计方案 v3.2 — 2026-07-23_

### v3.3 更新记录（2026-08-10）

**精简**：
- 删除 conflict.py（冲突检测）— 未被任何代码使用
- 删除 observer.py（观察者）— 未被任何代码使用
- 删除 search.py 中的时序衰减和RRF融合 — 简化为纯BM25
- search.py 从9KB精简到7KB
- memory_v2/__init__.py 从6KB精简到4KB

**新增**：
- SPEC.md 重写（27KB→8KB），基于实际代码
- core-module-design.md 更新Phase 1-3为完成状态
- 本文档新增实现状态总览表

**设计与实现的差距**：
- jieba分词 → 实际用简单正则（无外部依赖）
- overview.md → 未实现
- 文件锁 → 未实现
- 健康度指标 → 未实现
- 战略性遗忘 → 未实现
- 压缩后自检 → 未实现
- 旬记/月记/年记压缩 → 未实现
