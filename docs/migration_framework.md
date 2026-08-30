# Kioxus Migration Framework - 外部系统-Inspired Design

> 基于 外部系统 迁移系统的研究，为 Kioxus 设计一套"安全、可预览、可逆"的迁移框架。

---

## 一、设计背景

### 外部系统 提供了什么

外部系统（Kioxus 的前身）有一个成熟的迁移系统：

```
外部系统Source → MigrationPlan → MigrationApply
    ↓              ↓               ↓
  发现源        预览变更        执行变更
  (discover)    (plan)        (apply)
```

**核心安全原则：预览-执行分离**
- `migrate 外部系统 --dry-run` 预览所有变更
- `migrate apply 外部系统` 执行变更
- 冲突时拒绝执行，需要 `--overwrite`

### Kioxus 现状

Kioxus 目前没有迁移系统。但有以下潜在需求：

1. **从其他 Agent 系统迁移** - 比如从 Kioxus 导入记忆
2. **备份与恢复** - 定期备份 Kioxus 状态，可恢复
3. **多 workspace 支持** - 用户可能有多个 workspace
4. **配置迁移** - 不同环境（dev/prod）的配置同步

### 设计目标

| 目标 | 说明 |
|------|------|
| **安全第一** | 所有变更先预览，用户确认后再执行 |
| **可逆性** | 支持回滚（rollback） |
| **无冲突** | 检测冲突，拒绝覆盖，除非显式授权 |
| **敏感信息保护** | API keys、tokens 等在日志中脱敏 |
| **可组合** | 支持链式迁移（A → B → C） |

---

## 二、核心架构

### 2.1 迁移提供者（MigrationProvider）

```typescript
interface MigrationProvider {
  id: string;                      // 唯一标识，如 "外部系统", "Kioxus", "kioxus-backup"
  name: string;                    // 显示名称
  description: string;             // 说明

  // 发现阶段
  discover(source?: string): Promise<MigrationSource>;  // 发现迁移源

  // 计划阶段
  plan(source: MigrationSource): Promise<MigrationPlan>;  // 生成变更计划

  // 执行阶段
  apply(source: MigrationSource, plan: MigrationPlan, options?: ApplyOptions): Promise<ApplyResult>;

  // 回滚阶段
  rollback?(source: MigrationSource, applied: ApplyResult): Promise<void>;
}

interface MigrationSource {
  provider: string;           // 来源提供者
  root: string;              // 根路径
  files: SourceFile[];       // 文件列表
  metadata: SourceMetadata;  // 元数据
  archivePaths: ArchivePath[]; // 不支持迁移的目录
}

interface MigrationPlan {
  provider: string;
  items: MigrationItem[];     // 变更项目列表
  conflicts: ConflictItem[];  // 冲突列表
  warnings: WarningItem[];    // 警告（如 archive-only）
  secrets: SecretItem[];      // 敏感信息（会被脱敏）
}

interface MigrationItem {
  id: string;
  type: 'file' | 'config' | 'memory' | 'skill' | 'auth' | 'manual';
  source: string;            // 源路径
  target: string;            // 目标路径
  action: 'copy' | 'append' | 'skip' | 'conflict' | 'error';
  reason: string;            // 操作原因或状态
  size?: number;            // 文件大小
}
```

### 2.2 项目类型（MigrationItemType）

```typescript
enum MigrationItemType {
  // 文件类
  FILE_COPY = 'file:copy',      // 复制文件
  FILE_APPEND = 'file:append',   // 追加到现有文件
  FILE_SKIP = 'file:skip',       // 跳过（目标已存在）

  // 配置类
  CONFIG_MODEL = 'config:model',   // 模型配置
  CONFIG_PROVIDER = 'config:provider', // 提供商配置
  CONFIG_AUTH = 'config:auth',     // 认证配置

  // 记忆类
  MEMORY_MAIN = 'memory:main',     // 主记忆（MEMORY.md）
  MEMORY_DAILY = 'memory:daily',    // 日记忆（memory/YYYY-MM-DD.md）
  MEMORY_USER = 'memory:user',      // 用户信息（USER.md）

  // 技能类
  SKILL_COPY = 'skill:copy',        // 技能目录复制
  SKILL_CONFIG = 'skill:config',    // 技能配置

  // 手工类
  MANUAL_SESSION = 'manual:session',  // 会话（archive-only）
  MANUAL_PLUGIN = 'manual:plugin',    // 插件（archive-only）
  MANUAL_LOG = 'manual:log',          // 日志（archive-only）
}

enum MigrationAction {
  COPY = 'copy',           // 复制
  APPEND = 'append',       // 追加（用于 memory）
  SKIP = 'skip',           // 跳过
  CONFLICT = 'conflict',   // 冲突（需要 --overwrite）
  ERROR = 'error',         // 错误
  MANUAL = 'manual',       // 需要手工迁移
}

enum MigrationReason {
  // 成功
  REASON_SUCCESS = 'success',
  REASON_ALREADY_CONFIGURED = 'already configured',
  REASON_APPLIED = 'applied',

  // 失败
  REASON_CONFLICT = 'conflict: target exists',
  REASON_NOT_FOUND = 'source not found',
  REASON_PERMISSION_DENIED = 'permission denied',
  REASON_UNSUPPORTED = 'unsupported: archive-only',

  // 跳过
  REASON_SKIP_AUTH = 'auth credential migration not selected',
  REASON_SKIP_DUPLICATE = 'duplicate: already migrated',
}
```

### 2.3 冲突处理（Conflict Handling）

```typescript
interface ConflictItem {
  item: MigrationItem;
  source: string;           // 源路径
  target: string;          // 目标路径（已存在）
  targetExists: boolean;
  resolution: 'overwrite' | 'skip' | 'rename' | 'manual';
}

interface ApplyOptions {
  overwrite: boolean;      // 是否覆盖冲突文件
  includeSecrets: boolean; // 是否导入敏感信息
  dryRun: boolean;         // 是否只预览
  backup: boolean;         // 是否在执行前备份
}
```

**冲突处理策略：**

1. **检测** - plan 阶段检测所有冲突
2. **拒绝** - apply 阶段如果存在未解决冲突，默认拒绝
3. **覆盖** - 用户可以使用 `--overwrite` 显式授权覆盖
4. **跳过** - 或者用户可以接受跳过（保持目标不变）

---

## 三、Kioxus 迁移提供者实现

### 3.1 内置提供者

```typescript
// Kioxus 内置的迁移提供者
const migrationProviders = {
  // 1. Kioxus Backup Provider
  'kioxus-backup': {
    name: 'Kioxus Backup',
    description: 'Restore from Kioxus backup',
    // 用于恢复备份
  },

  // 2. Kioxus Provider (未来)
  'Kioxus': {
    name: 'Kioxus',
    description: 'Import from Kioxus workspace',
    // 发现 SOUL.md, MEMORY.md, USER.md, skills/
  },

  // 3. 外部系统 Provider (未来)
  '外部系统': {
    name: '外部系统',
    description: 'Import from 外部系统 workspace',
    // 发现 config.yaml, memories/, skills/
  },
};
```

### 3.2 Kioxus 迁移（示例）

```typescript
// 发现 Kioxus workspace
async function discoverKioxusSource(input?: string): Promise<MigrationSource> {
  const root = input || '~/.Kioxus';

  return {
    provider: 'Kioxus',
    root,
    files: [
      { path: 'SOUL.md', type: 'file' },
      { path: 'AGENTS.md', type: 'file' },
      { path: 'IDENTITY.md', type: 'file' },
      { path: 'USER.md', type: 'file' },
      { path: 'MEMORY.md', type: 'file' },
      { path: 'memory/', type: 'directory' },
      { path: 'skills/', type: 'directory' },
    ],
    metadata: {
      version: 'unknown',
      createdAt: await getDirCreatedAt(root),
    },
    archivePaths: [
      { id: 'sessions', path: 'sessions/', reason: 'unsupported: state format' },
      { id: 'plugins', path: 'plugins/', reason: 'unsupported: binary state' },
    ],
  };
}
```

### 3.3 计划生成

```typescript
async function planKioxusMigration(source: MigrationSource): Promise<MigrationPlan> {
  const items: MigrationItem[] = [];
  const conflicts: ConflictItem[] = [];
  const warnings: WarningItem[] = [];

  // 1. SOUL.md - COPY or CONFLICT
  const soulSource = path.join(source.root, 'SOUL.md');
  const soulTarget = 'workspace/SOUL.md';

  if (await fileExists(soulTarget)) {
    // Kioxus 已有 SOUL.md，报冲突
    conflicts.push({
      item: createItem('file', soulSource, soulTarget),
      source: soulSource,
      target: soulTarget,
      targetExists: true,
      resolution: 'overwrite',
    });
  } else {
    items.push(createCopyItem('SOUL.md', soulSource, soulTarget));
  }

  // 2. MEMORY.md - APPEND（追加而非覆盖）
  const memorySource = path.join(source.root, 'MEMORY.md');
  const memoryTarget = 'workspace/MEMORY.md';

  if (await fileExists(memoryTarget)) {
    // Kioxus 已有 MEMORY.md，选择追加
    items.push({
      id: 'memory-main-append',
      type: 'memory',
      source: memorySource,
      target: memoryTarget,
      action: 'append',
      reason: 'append rather than overwrite to preserve history',
    });
  } else {
    items.push(createCopyItem('MEMORY.md', memorySource, memoryTarget));
  }

  // 3. USER.md - APPEND
  const userSource = path.join(source.root, 'USER.md');
  const userTarget = 'workspace/USER.md';

  if (await fileExists(userTarget)) {
    items.push({
      id: 'user-append',
      type: 'memory',
      source: userSource,
      target: userTarget,
      action: 'append',
      reason: 'append user data',
    });
  } else {
    items.push(createCopyItem('USER.md', userSource, userTarget));
  }

  // 4. Archive-only 项目 - 生成警告
  for (const archive of source.archivePaths) {
    warnings.push({
      item: createManualItem(archive.id, archive.path),
      reason: archive.reason,
      action: 'manual',
    });
  }

  return {
    provider: 'Kioxus',
    items,
    conflicts,
    warnings,
    secrets: [], // Kioxus 源没有认证文件（假设）
  };
}
```

---

## 四、安全原则

### 4.1 预览-执行分离

```
┌─────────────────────────────────────┐
│          migrate <source>           │
│              --dry-run              │
├─────────────────────────────────────┤
│  1. discover() → MigrationSource    │
│  2. plan() → MigrationPlan          │
│  3. 显示预览，不执行任何变更         │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│        migrate apply <source>        │
├─────────────────────────────────────┤
│  1. 发现冲突 → 询问用户确认          │
│  2. 可选：创建备份                  │
│  3. 执行变更                        │
│  4. 返回 ApplyResult                │
└─────────────────────────────────────┘
```

### 4.2 敏感信息保护

```typescript
// 敏感信息脱敏
function redactSecrets(obj: any, depth = 0): any {
  if (depth > 3) return '[REDACTED]';

  if (typeof obj !== 'object' || obj === null) {
    return obj;
  }

  // 检测敏感字段
  const sensitiveKeys = ['api_key', 'token', 'secret', 'password', 'auth'];
  const redacted = Array.isArray(obj) ? [] : {};

  for (const [key, value] of Object.entries(obj)) {
    if (sensitiveKeys.some(sk => key.toLowerCase().includes(sk))) {
      redacted[key] = '[REDACTED]';
    } else if (typeof value === 'object') {
      redacted[key] = redactSecrets(value, depth + 1);
    } else {
      redacted[key] = value;
    }
  }

  return redacted;
}

// Plan 输出时脱敏
console.log('Migration Plan:');
console.log(JSON.stringify(redactSecrets(plan), null, 2));
```

### 4.3 备份策略

```typescript
async function createBackup(targetPath: string): Promise<string> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupDir = path.join('backups/', timestamp);

  // 创建带时间戳的备份目录
  await mkdirp(backupDir);

  // 备份所有目标文件
  const files = await glob('**/*', { cwd: targetPath });
  for (const file of files) {
    const src = path.join(targetPath, file);
    const dst = path.join(backupDir, file);
    await copyFile(src, dst);
  }

  return backupDir;
}
```

### 4.4 回滚机制

```typescript
interface ApplyResult {
  success: boolean;
  appliedItems: MigrationItem[];
  failedItems: MigrationItem[];
  backupPath?: string;
  timestamp: string;
}

async function rollback(result: ApplyResult): Promise<void> {
  if (!result.backupPath) {
    throw new Error('No backup available for rollback');
  }

  // 从备份恢复
  const targetPath = 'workspace/';
  await copyRecursive(result.backupPath, targetPath);

  // 删除备份
  await rmrf(result.backupPath);
}
```

---

## 五、与 Kioxus 现有组件的整合

### 5.1 不冲突的设计

| Kioxus 现有组件 | 整合方式 |
|----------------|----------|
| **IdentityCore** | 迁移后的 identity 文件会触发 IdentityCore 重新加载 |
| **Markus Memory** | 追加的记忆会通过 MemoryIdentityBridge 处理 |
| **PCAS** | 不受影响，迁移系统是独立模块 |
| **外部系统 Registry** | 使用 外部系统 作为注册表，但迁移系统独立 |

### 5.2 整合点

```typescript
// 整合到 Kioxus 主类
class Kioxus {
  // ... existing components ...

  // 迁移系统
  migration = {
    providers: new Map<string, MigrationProvider>(),

    registerProvider(provider: MigrationProvider): void;
    async migrate(source: string, options?: ApplyOptions): Promise<ApplyResult>;
    async rollback(backupPath: string): Promise<void>;
  };

  // 初始化时注册内置提供者
  constructor() {
    // 注册内置迁移提供者
    this.migration.registerProvider(createKioxusBackupProvider());
    this.migration.registerProvider(createKioxusProvider());
  }
}
```

### 5.3 Hook 整合

迁移系统可以与 Stage 25 的 HookSystem 整合：

```typescript
// 迁移相关的 Hook 事件
enum MigrationHookEvent {
  BEFORE_DISCOVER = 'migration:before_discover',
  AFTER_DISCOVER = 'migration:after_discover',
  BEFORE_PLAN = 'migration:before_plan',
  AFTER_PLAN = 'migration:after_plan',
  BEFORE_APPLY = 'migration:before_apply',
  AFTER_APPLY = 'migration:after_apply',
  BEFORE_ROLLBACK = 'migration:before_rollback',
  AFTER_ROLLBACK = 'migration:after_rollback',
}

// 使用示例
hooks.register(
  handler: (ctx) => {
    if (ctx.data.action === 'AFTER_APPLY') {
      console.log(`Migration completed: ${ctx.data.result.appliedItems.length} items`);
    }
  },
  events: { MigrationHookEvent.AFTER_APPLY },
  name: 'migration_logger'
);
```

---

## 六、CLI 接口设计

### 6.1 命令设计

```bash
# 列出可用的迁移源
kioxus migrate list

# 预览迁移计划
kioxus migrate Kioxus --dry-run
kioxus migrate Kioxus --from ~/.Kioxus --dry-run

# 执行迁移
kioxus migrate apply Kioxus --yes
kioxus migrate apply Kioxus --overwrite --yes

# 包含敏感信息
kioxus migrate apply Kioxus --include-secrets --yes

# 回滚
kioxus migrate rollback <backup-path>

# 创建备份
kioxus backup create
kioxus backup list
kioxus backup restore <backup-id>
```

### 6.2 输出格式

```bash
# dry-run 输出示例
$ kioxus migrate Kioxus --dry-run

Migration Plan: Kioxus → Kioxus
========================================

Items to apply:
  [+ ] SOUL.md              → workspace/SOUL.md (copy)
  [+ ] AGENTS.md           → workspace/AGENTS.md (copy)
  [+ ] IDENTITY.md         → workspace/IDENTITY.md (copy)
  [>>] MEMORY.md           → workspace/MEMORY.md (append)
  [>>] USER.md             → workspace/USER.md (append)
  [>>] memory/*.md         → memory/ (append daily)
  [+ ] skills/             → skills/ (copy)

Warnings (manual review needed):
  [!] sessions/            → archive-only (unsupported state)
  [!] plugins/             → archive-only (unsupported state)

Conflicts (use --overwrite to resolve):
  [!!] SOUL.md             → CONFLICT: target exists
  [!!] AGENTS.md           → CONFLICT: target exists

Secrets:
  (none detected)

========================================
Run with --overwrite to resolve conflicts, or review manually.
```

---

## 七、总结

### 7.1 设计原则

| 原则 | 实现 |
|------|------|
| **安全第一** | 预览-执行分离，冲突默认拒绝 |
| **可逆性** | 备份 + 回滚机制 |
| **无冲突** | 检测所有冲突，让用户决定 |
| **敏感信息保护** | Plan 输出时自动脱敏 |
| **可组合** | Provider 模式，支持多种迁移源 |

### 7.2 与现有组件不冲突

- MigrationSystem 是独立模块，不修改 Kioxus 核心
- 迁移后的文件由现有组件（IdentityCore、Markus）正常处理
- HookSystem 可以监听迁移事件

### 7.3 后续扩展

1. **v0.2** - 基本迁移框架 + Kioxus provider
2. **v0.3** - 外部系统 provider + 回滚功能
3. **v0.4** - 多 workspace 支持 + 备份调度

---

**核心借鉴**：外部系统 的"预览-执行分离"和"敏感信息脱敏"是迁移系统的最佳实践。Kioxus 的 Migration Framework 基于此设计，但更适合 Kioxus 的 identity-first 哲学。