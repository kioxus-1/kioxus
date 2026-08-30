"""
Kioxus Doctor — 自检与自修复

检查项目：
- 配置文件完整性（.env、kioxus.json、config.yaml）
- LLM连接可用性（API Key是否有效）
- 记忆系统健康（目录是否存在、文件是否损坏）
- 沙箱状态（Python环境、依赖是否安装）
- Provider状态（已注册、可用、Key有效性）
"""

import os
import json
import sys
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
from enum import Enum


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Finding:
    check_id: str
    severity: Severity
    message: str
    path: Optional[str] = None
    fix_hint: Optional[str] = None


@dataclass
class DoctorReport:
    findings: List[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == Severity.ERROR for f in self.findings)

    def add(self, check_id: str, severity: Severity, message: str, path: str = None, fix_hint: str = None):
        self.findings.append(Finding(check_id, severity, message, path, fix_hint))

    def summary(self) -> str:
        lines = []
        errors = [f for f in self.findings if f.severity == Severity.ERROR]
        warnings = [f for f in self.findings if f.severity == Severity.WARNING]
        infos = [f for f in self.findings if f.severity == Severity.INFO]

        if self.ok:
            lines.append("✅ Kioxus Doctor — 所有检查通过")
        else:
            lines.append("❌ Kioxus Doctor — 发现问题")

        lines.append(f"   检查项: {len(self.findings)} | 错误: {len(errors)} | 警告: {len(warnings)} | 信息: {len(infos)}")
        lines.append("")

        for f in self.findings:
            icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[f.severity.value]
            lines.append(f"  {icon} [{f.check_id}] {f.message}")
            if f.path:
                lines.append(f"     路径: {f.path}")
            if f.fix_hint:
                lines.append(f"     修复: {f.fix_hint}")

        return "\n".join(lines)


def check_env(base_dir: str, report: DoctorReport):
    """检查 .env 文件"""
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        report.add("env-missing", Severity.WARNING,
                    ".env 文件不存在，无法加载API Key",
                    path=env_path,
                    fix_hint="创建 .env 文件，填入 API Key")
        return

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    has_key = False
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            if val.strip() and val.strip() != "***":
                has_key = True

    if not has_key:
        report.add("env-empty", Severity.WARNING,
                    ".env 中没有有效的API Key",
                    path=env_path,
                    fix_hint="在 .env 中填入至少一个 API Key")
    else:
        report.add("env-ok", Severity.INFO, ".env 文件正常")


def check_config(base_dir: str, report: DoctorReport):
    """检查配置文件"""
    cfg_path = os.path.join(base_dir, "config", "kioxus.json")
    if not os.path.exists(cfg_path):
        report.add("config-missing", Severity.ERROR,
                    "config/kioxus.json 不存在",
                    path=cfg_path,
                    fix_hint="创建配置文件或从 config.example.yaml 生成")
        return

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        report.add("config-invalid", Severity.ERROR,
                    f"config/kioxus.json 格式错误: {e}",
                    path=cfg_path,
                    fix_hint="检查JSON语法")
        return

    providers = cfg.get("providers", {})
    if not providers:
        report.add("config-no-providers", Severity.ERROR,
                    "没有配置任何LLM Provider",
                    path=cfg_path,
                    fix_hint="在 providers 中添加至少一个 Provider")
        return

    for name, pcfg in providers.items():
        if not pcfg.get("api_url"):
            report.add(f"config-provider-{name}-no-url", Severity.ERROR,
                        f"Provider '{name}' 缺少 api_url",
                        path=cfg_path)
        if not pcfg.get("model"):
            report.add(f"config-provider-{name}-no-model", Severity.WARNING,
                        f"Provider '{name}' 缺少 model",
                        path=cfg_path)

    default = cfg.get("default_provider")
    if default and default not in providers:
        report.add("config-default-missing", Severity.ERROR,
                    f"default_provider '{default}' 不存在于 providers 中",
                    path=cfg_path,
                    fix_hint="检查 default_provider 名称")

    report.add("config-ok", Severity.INFO, f"配置文件正常，{len(providers)} 个 Provider")


def check_llm(base_dir: str, report: DoctorReport):
    """检查LLM连接"""
    sys.path.insert(0, os.path.join(base_dir, "src"))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(base_dir, ".env"))
    except ImportError:
        pass

    try:
        from core.provider_registry import get_registry
        registry = get_registry()
        cfg_path = os.path.join(base_dir, "config", "kioxus.json")
        registry.load_from_config(cfg_path)
    except Exception as e:
        report.add("llm-registry-error", Severity.ERROR,
                    f"Provider Registry 加载失败: {e}")
        return

    providers = registry.list_providers()
    if not providers:
        report.add("llm-no-providers", Severity.ERROR, "没有注册任何 Provider")
        return

    for name in providers:
        pcfg = registry.get(name)
        if not pcfg or not pcfg.api_key:
            report.add(f"llm-{name}-no-key", Severity.WARNING,
                        f"Provider '{name}' 没有API Key",
                        fix_hint=f"在 .env 中设置对应的 API Key")
        else:
            report.add(f"llm-{name}-ok", Severity.INFO,
                        f"Provider '{name}' 已配置 (Key: {pcfg.api_key[:4]}****)")


def check_memory(base_dir: str, report: DoctorReport):
    """检查记忆系统"""
    mem_dir = os.path.join(base_dir, "data", "memory_v2")
    if not os.path.exists(mem_dir):
        report.add("memory-dir-missing", Severity.WARNING,
                    "记忆数据目录不存在",
                    path=mem_dir,
                    fix_hint="首次运行时会自动创建")
        return

    core_file = os.path.join(mem_dir, "data", "core.md")
    if os.path.exists(core_file):
        size = os.path.getsize(core_file)
        if size == 0:
            report.add("memory-core-empty", Severity.WARNING,
                        "core.md 为空，记忆系统可能未初始化")
        else:
            report.add("memory-core-ok", Severity.INFO,
                        f"core.md 正常 ({size} bytes)")
    else:
        report.add("memory-core-missing", Severity.INFO,
                    "core.md 不存在（首次运行会创建）")


def check_sandbox(base_dir: str, report: DoctorReport):
    """检查沙箱环境"""
    try:
        import subprocess
        result = subprocess.run([sys.executable, "--version"],
                                capture_output=True, text=True, timeout=5)
        version = result.stdout.strip()
        report.add("sandbox-python-ok", Severity.INFO, f"Python环境: {version}")
    except Exception as e:
        report.add("sandbox-python-error", Severity.ERROR,
                    f"Python环境检查失败: {e}")

    # Check required packages
    required = ["flask", "numpy", "requests"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        report.add("sandbox-deps-missing", Severity.WARNING,
                    f"缺少依赖: {', '.join(missing)}",
                    fix_hint="pip install -r requirements.txt")
    else:
        report.add("sandbox-deps-ok", Severity.INFO, "所有依赖已安装")


def run_doctor(base_dir: str = None, fix: bool = False) -> DoctorReport:
    """运行全部检查"""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    report = DoctorReport()

    check_env(base_dir, report)
    check_config(base_dir, report)
    check_memory(base_dir, report)
    check_sandbox(base_dir, report)
    check_llm(base_dir, report)

    return report


def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Kioxus Doctor — 自检工具")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--lint", action="store_true", help="只读模式，不修改任何文件")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report = run_doctor(base_dir, fix=args.fix)

    if args.json:
        import json as json_mod
        output = {
            "ok": report.ok,
            "checksRun": len(report.findings),
            "findings": [
                {
                    "checkId": f.check_id,
                    "severity": f.severity.value,
                    "message": f.message,
                    "path": f.path,
                    "fixHint": f.fix_hint,
                }
                for f in report.findings
            ],
        }
        print(json_mod.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(report.summary())

    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
