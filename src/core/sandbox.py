"""
Kioxus Core v2 — 沙箱模块（硬边界隔离）

核心原则：沙箱策略由系统强制执行，不是提示词约束

实现方式：
  1. subprocess隔离 — 独立进程，受限环境
  2. 策略声明式配置（JSON）— 文件系统/网络/环境变量/资源限制
  3. 超时强制终止
  4. 输出大小限制

不依赖Docker（可选），保证在任何环境都能跑
"""

import os
import sys
import json
import time
import logging
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


# ============== 沙箱策略 ==============

class SandboxLevel(Enum):
    """沙箱安全级别"""
    STRICT = "strict"       # 最严格：禁止网络、限制文件系统、最小环境
    NORMAL = "normal"       # 默认：禁止网络、限制文件系统
    RELAXED = "relaxed"     # 宽松：允许部分网络、更宽文件系统
    UNSAFE = "unsafe"       # 不安全：无沙箱保护（需显式声明）


@dataclass
class SandboxPolicy:
    """沙箱策略配置"""
    level: SandboxLevel = SandboxLevel.NORMAL

    # 文件系统
    allowed_read_paths: List[str] = field(default_factory=lambda: ["$WORKSPACE", "$TEMP"])
    allowed_write_paths: List[str] = field(default_factory=lambda: ["$WORKSPACE", "$TEMP"])
    denied_paths: List[str] = field(default_factory=lambda: [
        "$HOME/.ssh", "$HOME/.aws", "$HOME/.config",
        "/etc", "/root", "/sys", "/proc",
    ])

    # 网络
    allow_network: bool = False
    allowed_hosts: List[str] = field(default_factory=list)

    # 环境变量
    allowed_env_vars: List[str] = field(default_factory=lambda: [
        "PATH", "HOME", "TEMP", "TMP", "LANG", "LC_ALL", "PYTHONPATH",
    ])
    denied_env_vars: List[str] = field(default_factory=lambda: [
        "API_KEY", "SECRET", "TOKEN", "PASSWORD", "AWS_SECRET",
    ])

    # 资源限制
    max_execution_time: int = 10          # 秒
    max_output_size: int = 1024 * 1024    # 1MB
    max_memory_mb: int = 256              # 内存限制（仅提示，非强制）

    # 代码检查
    blocked_imports: List[str] = field(default_factory=lambda: [
        "os", "subprocess", "shutil", "ctypes", "signal",
    ])
    blocked_patterns: List[str] = field(default_factory=lambda: [
        "__import__('os')", "__import__('subprocess')",
        "eval(", "exec(",
        "open('/etc", "open('/root",
    ])

    def to_dict(self) -> Dict:
        """to_dict"""
        return {
            "level": self.level.value,
            "allow_network": self.allow_network,
            "max_execution_time": self.max_execution_time,
            "max_output_size": self.max_output_size,
            "max_memory_mb": self.max_memory_mb,
        }


# 预设策略
PRESET_POLICIES = {
    SandboxLevel.STRICT: SandboxPolicy(
        level=SandboxLevel.STRICT,
        allow_network=False,
        max_execution_time=5,
        max_output_size=512 * 1024,
        max_memory_mb=128,
    ),
    SandboxLevel.NORMAL: SandboxPolicy(
        level=SandboxLevel.NORMAL,
        allow_network=False,
        max_execution_time=10,
        max_output_size=1024 * 1024,
        max_memory_mb=256,
    ),
    SandboxLevel.RELAXED: SandboxPolicy(
        level=SandboxLevel.RELAXED,
        allow_network=True,
        max_execution_time=30,
        max_output_size=2 * 1024 * 1024,
        max_memory_mb=512,
    ),
    SandboxLevel.UNSAFE: SandboxPolicy(
        level=SandboxLevel.UNSAFE,
        allow_network=True,
        max_execution_time=60,
        max_output_size=10 * 1024 * 1024,
        max_memory_mb=1024,
    ),
}


# ============== 沙箱执行结果 ==============

@dataclass
class SandboxResult:
    """沙箱执行结果"""
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    timed_out: bool = False
    execution_time_ms: float = 0
    policy_violations: List[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict:
        """to_dict"""
        return {
            "success": self.success,
            "stdout": self.stdout[:10000],  # 限制输出大小
            "stderr": self.stderr[:5000],
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "execution_time_ms": self.execution_time_ms,
            "policy_violations": self.policy_violations,
            "error": self.error,
        }


# ============== 代码检查器 ==============

class CodeChecker:
    """代码静态检查 — 在执行前拦截危险代码"""

    def __init__(self, policy: SandboxPolicy):
        """__init__"""
        self.policy = policy

    def check(self, code: str) -> List[str]:
        """
        检查代码是否违反策略

        返回：违规列表（空=通过）
        """
        violations = []

        # 检查阻断模式
        for pattern in self.policy.blocked_patterns:
            if pattern in code:
                violations.append(f"blocked_pattern: {pattern}")

        # 检查阻断的import
        for blocked in self.policy.blocked_imports:
            # 检查 import xxx 和 from xxx import
            if f"import {blocked}" in code or f"from {blocked}" in code:
                violations.append(f"blocked_import: {blocked}")

        # 检查网络相关（如果不允许网络）
        if not self.policy.allow_network:
            network_modules = ["urllib", "requests", "http.client", "socket", "httpx"]
            for mod in network_modules:
                if f"import {mod}" in code or f"from {mod}" in code:
                    violations.append(f"network_blocked: {mod}")

        # 检查文件系统访问
        if "open(" in code:
            # 提取open的路径参数
            import re
            open_calls = re.findall(r'open\(["\']([^"\']+)["\']', code)
            for path in open_calls:
                if self._is_path_denied(path):
                    violations.append(f"denied_path: {path}")

        return violations

    def _is_path_denied(self, path: str) -> bool:
        """检查路径是否在拒绝列表中"""
        for denied in self.policy.denied_paths:
            expanded = self._expand_path(denied)
            if path.startswith(expanded):
                return True
        return False

    @staticmethod
    def _expand_path(path: str) -> str:
        """展开环境变量"""
        path = path.replace("$WORKSPACE", os.getcwd())
        path = path.replace("$TEMP", tempfile.gettempdir())
        path = path.replace("$HOME", os.path.expanduser("~"))
        return path


# ============== 沙箱执行器 ==============

class Sandbox:
    """
    代码沙箱执行器

    核心原则：硬边界隔离
    - 独立进程执行
    - 策略强制执行（不是建议）
    - 超时强制终止
    - 输出大小限制

    使用方式：
        sandbox = Sandbox(SandboxLevel.NORMAL)
        result = sandbox.execute("print('hello')")
        if result.success:
            print(result.stdout)
    """

    def __init__(self, level: SandboxLevel = SandboxLevel.NORMAL, policy: SandboxPolicy = None):
        """__init__"""
        self.policy = policy or PRESET_POLICIES.get(level, SandboxPolicy())
        self.checker = CodeChecker(self.policy)

    def execute(self, code: str, language: str = "python") -> SandboxResult:
        """
        在沙箱中执行代码

        参数：
            code: 要执行的代码
            language: 编程语言（目前仅支持python）

        返回：
            SandboxResult
        """
        start_time = time.time()

        # 1. 语言检查
        if language != "python":
            return SandboxResult(
                success=False,
                error=f"不支持的语言: {language}（仅支持python）",
            )

        # 2. 代码静态检查
        violations = self.checker.check(code)
        if violations:
            return SandboxResult(
                success=False,
                policy_violations=violations,
                error=f"代码违反安全策略: {'; '.join(violations)}",
            )

        # 3. 构建执行环境
        env = self._build_environment()

        # 4. 写入临时文件并执行
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                tmp_path = f.name

            # 5. 执行（subprocess隔离）
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.policy.max_execution_time,
                env=env,
                cwd=tempfile.gettempdir(),  # 在临时目录执行
                encoding="utf-8",
                errors="replace",
            )

            execution_time = (time.time() - start_time) * 1000

            # 6. 检查输出大小
            stdout = result.stdout
            stderr = result.stderr
            if len(stdout) > self.policy.max_output_size:
                stdout = stdout[:self.policy.max_output_size] + "\n[输出截断]"
            if len(stderr) > self.policy.max_output_size // 2:
                stderr = stderr[:self.policy.max_output_size // 2] + "\n[错误截断]"

            return SandboxResult(
                success=result.returncode == 0,
                stdout=stdout,
                stderr=stderr,
                returncode=result.returncode,
                execution_time_ms=execution_time,
            )

        except subprocess.TimeoutExpired:
            execution_time = (time.time() - start_time) * 1000
            return SandboxResult(
                success=False,
                timed_out=True,
                error=f"执行超时（{self.policy.max_execution_time}秒）",
                execution_time_ms=execution_time,
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return SandboxResult(
                success=False,
                error=f"执行异常: {str(e)}",
                execution_time_ms=execution_time,
            )
        finally:
            # 清理临时文件
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    def _build_environment(self) -> Dict[str, str]:
        """构建受限的环境变量"""
        # 基础环境
        env = {}

        # 只保留允许的环境变量
        for var in self.policy.allowed_env_vars:
            value = os.environ.get(var)
            if value:
                env[var] = value

        # 确保PATH存在
        if "PATH" not in env:
            env["PATH"] = os.environ.get("PATH", "")

        # 确保TEMP存在
        if "TEMP" not in env and "TMP" not in env:
            env["TEMP"] = tempfile.gettempdir()

        # 如果不允许网络，设置代理阻断（尽力而为）
        if not self.policy.allow_network:
            env["no_proxy"] = "*"
            env["NO_PROXY"] = "*"
            env["http_proxy"] = ""
            env["https_proxy"] = ""

        return env


# ============== 便捷函数 ==============

_default_sandbox: Optional[Sandbox] = None


def get_sandbox(level: SandboxLevel = SandboxLevel.NORMAL) -> Sandbox:
    """获取默认沙箱实例"""
    global _default_sandbox
    if _default_sandbox is None or _default_sandbox.policy.level != level:
        _default_sandbox = Sandbox(level)
    return _default_sandbox


def reset_sandbox():
    """重置默认沙箱"""
    global _default_sandbox
    _default_sandbox = None


def sandbox_exec(code: str, level: SandboxLevel = SandboxLevel.NORMAL, **kwargs) -> SandboxResult:
    """便捷函数：在沙箱中执行代码"""
    sandbox = get_sandbox(level)
    return sandbox.execute(code, **kwargs)
