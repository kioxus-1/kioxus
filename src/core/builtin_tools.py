"""
Kioxus Core v2 — 内置工具集
http_fetch, file_read, file_write, code_exec, web_search

所有工具返回 ToolResult
"""

import re
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

from .tools import ToolResult, ToolMeta, ToolCategory, ToolRegistry, get_tool_registry
from .sandbox import Sandbox, SandboxLevel, SandboxResult, get_sandbox

logger = logging.getLogger(__name__)


# ============== HTTP 抓取 ==============

def http_fetch(url: str, max_length: int = 5000, timeout: int = 15) -> ToolResult:
    """抓取网页内容"""
    import urllib.request
    import urllib.error

    if not url.startswith(("http://", "https://")):
        return ToolResult(success=False, output=None, error="URL必须以http://或https://开头")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()

            # 尝试解码
            for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
                try:
                    text = raw.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text = raw.decode("latin-1")

            # 如果是HTML，提取纯文本
            if "html" in content_type.lower() or "<html" in text.lower():
                text = _strip_html(text)

            # 截断
            if len(text) > max_length:
                text = text[:max_length] + f"\n\n[截断，共{len(raw)}字节]"

            return ToolResult(
                success=True,
                output={"url": url, "content": text, "content_type": content_type, "size_bytes": len(raw)},
            )
    except urllib.error.HTTPError as e:
        return ToolResult(success=False, output=None, error=f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        return ToolResult(success=False, output=None, error=f"URL错误: {e.reason}")
    except Exception as e:
        return ToolResult(success=False, output=None, error=str(e))


def _strip_html(html: str) -> str:
    """去除HTML标签，提取纯文本"""
    # 移除script和style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 移除注释
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    # 将br/p/div/li/h标签转为换行
    html = re.sub(r"<(?:br|p|div|li|h[1-6])[^>]*/?>", "\n", html, flags=re.IGNORECASE)
    # 移除所有标签
    html = re.sub(r"<[^>]+>", "", html)
    # 处理HTML实体
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&quot;", '"').replace("&nbsp;", " ").replace("&#39;", "'")
    # 合并多余空白
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ============== 文件操作 ==============

def file_read(path: str, encoding: str = "utf-8", max_lines: int = 200) -> ToolResult:
    """读取文件内容"""
    p = Path(path)
    if not p.exists():
        return ToolResult(success=False, output=None, error=f"文件不存在: {path}")
    if not p.is_file():
        return ToolResult(success=False, output=None, error=f"不是文件: {path}")

    try:
        text = p.read_text(encoding=encoding)
        lines = text.split("\n")
        if len(lines) > max_lines:
            text = "\n".join(lines[:max_lines]) + f"\n\n[截断，共{len(lines)}行]"
        return ToolResult(
            success=True,
            output={"path": str(p), "content": text, "lines": len(lines), "size": p.stat().st_size},
        )
    except Exception as e:
        return ToolResult(success=False, output=None, error=str(e))


def file_write(path: str, content: str, encoding: str = "utf-8", append: bool = False) -> ToolResult:
    """写入文件"""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding=encoding) as f:
            f.write(content)
        return ToolResult(
            success=True,
            output={"path": str(p), "bytes_written": len(content.encode(encoding)), "mode": mode},
        )
    except Exception as e:
        return ToolResult(success=False, output=None, error=str(e))


def file_list(directory: str = ".", pattern: str = "*") -> ToolResult:
    """列出目录内容"""
    d = Path(directory)
    if not d.exists():
        return ToolResult(success=False, output=None, error=f"目录不存在: {directory}")
    if not d.is_dir():
        return ToolResult(success=False, output=None, error=f"不是目录: {directory}")

    try:
        entries = []
        for item in sorted(d.glob(pattern)):
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
        return ToolResult(success=True, output={"directory": str(d), "entries": entries, "count": len(entries)})
    except Exception as e:
        return ToolResult(success=False, output=None, error=str(e))


# ============== 代码执行 ==============

def code_exec(code: str, language: str = "python", timeout: int = 10, unsafe: bool = False) -> ToolResult:
    """
    执行代码（默认沙箱模式）

    参数：
        code: 要执行的代码
        language: 编程语言
        timeout: 超时秒数
        unsafe: 是否跳过沙箱（需显式声明）

    安全说明：
        默认在沙箱中执行，限制文件系统/网络/资源
        设置 unsafe=True 可跳过沙箱（不推荐）
    """
    if unsafe:
        logger.warning("[Tools] code_exec in UNSAFE mode")
        return _code_exec_unsafe(code, language, timeout)

    # 沙箱模式
    level = SandboxLevel.NORMAL
    if timeout > 30:
        level = SandboxLevel.RELAXED

    sandbox = get_sandbox(level)
    sandbox.policy.max_execution_time = timeout

    result = sandbox.execute(code, language)

    if result.success:
        return ToolResult(
            success=True,
            output={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "execution_time_ms": result.execution_time_ms,
                "sandbox_level": level.value,
            },
        )
    else:
        error_msg = result.error
        if result.policy_violations:
            error_msg = "安全策略拦截: " + "; ".join(result.policy_violations)
        elif result.timed_out:
            error_msg = "执行超时（" + str(timeout) + "秒）"
        return ToolResult(success=False, output=None, error=error_msg)


def _code_exec_unsafe(code: str, language: str = "python", timeout: int = 10) -> ToolResult:
    """不安全模式执行（仅用于明确需要的场景）"""
    if language != "python":
        return ToolResult(success=False, output=None, error="暂不支持 " + language + "，仅支持 python")

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )

        Path(tmp_path).unlink(missing_ok=True)

        return ToolResult(
            success=result.returncode == 0,
            output={"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode},
            error=result.stderr if result.returncode != 0 else None,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output=None, error="执行超时（" + str(timeout) + "秒）")
    except Exception as e:
        return ToolResult(success=False, output=None, error=str(e))


# ============== 注册所有内置工具 ==============

def register_builtin_tools(registry: ToolRegistry = None):
    """注册所有内置工具到注册表"""
    reg = registry or get_tool_registry()

    reg.register(
        ToolMeta(
            name="http_fetch",
            description="抓取网页内容，返回纯文本",
            category=ToolCategory.WEB,
            params={"url": "str (必填)", "max_length": "int (默认5000)"},
        ),
        lambda **kw: http_fetch(**kw),
    )

    reg.register(
        ToolMeta(
            name="file_read",
            description="读取文件内容",
            category=ToolCategory.FILE,
            params={"path": "str (必填)", "max_lines": "int (默认200)"},
        ),
        lambda **kw: file_read(**kw),
    )

    reg.register(
        ToolMeta(
            name="file_write",
            description="写入文件",
            category=ToolCategory.FILE,
            params={"path": "str (必填)", "content": "str (必填)", "append": "bool (默认False)"},
        ),
        lambda **kw: file_write(**kw),
    )

    reg.register(
        ToolMeta(
            name="file_list",
            description="列出目录内容",
            category=ToolCategory.FILE,
            params={"directory": "str (默认当前目录)", "pattern": "glob模式 (默认*)"},
        ),
        lambda **kw: file_list(**kw),
    )

    reg.register(
        ToolMeta(
            name="code_exec",
            description="执行Python代码（默认沙箱模式，unsafe=True跳过沙箱）",
            category=ToolCategory.CODE,
            params={"code": "str (必填)", "timeout": "int (默认10秒)", "unsafe": "bool (默认False)"},
        ),
        lambda **kw: code_exec(**kw),
    )

    logger.info(f"[Tools] 已注册 {len(reg.list_tools())} 个内置工具")
