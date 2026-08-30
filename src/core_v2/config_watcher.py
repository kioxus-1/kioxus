"""
Config Watcher — 配置热更新

借鉴OpenClaw的配置热更新机制：
- 监听config文件变化
- 变化时自动重新加载Provider
- 原子性更新，失败保留上一次状态
"""

import os
import time
import json
import threading
from pathlib import Path
from typing import Callable, Optional


class ConfigWatcher:
    """配置文件监听器"""

    def __init__(self, config_path: str, callback: Callable, interval: float = 2.0):
        self.config_path = config_path
        self.callback = callback
        self.interval = interval
        self._last_mtime: float = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _get_mtime(self) -> float:
        try:
            return os.path.getmtime(self.config_path)
        except OSError:
            return 0

    def _watch_loop(self):
        while self._running:
            mtime = self._get_mtime()
            if mtime > self._last_mtime:
                self._last_mtime = mtime
                try:
                    self.callback(self.config_path)
                except Exception as e:
                    print(f"[ConfigWatcher] reload error: {e}")
            time.sleep(self.interval)

    def start(self):
        """启动监听"""
        if self._running:
            return
        self._last_mtime = self._get_mtime()
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止监听"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)


def validate_config(config_path: str) -> tuple:
    """
    校验配置文件，返回 (is_valid, errors)

    校验规则（借鉴OpenClaw的严格校验）：
    - 必须是合法JSON
    - providers必须是dict
    - 每个provider必须有api_url
    - default_provider必须指向已存在的provider
    """
    errors = []

    if not os.path.exists(config_path):
        return True, []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"JSON解析失败: {e}"]

    if not isinstance(cfg, dict):
        errors.append("配置根必须是对象")
        return False, errors

    providers = cfg.get("providers", {})
    if not isinstance(providers, dict):
        errors.append("providers必须是对象")
        return False, errors

    for name, pcfg in providers.items():
        if not isinstance(pcfg, dict):
            errors.append(f"provider '{name}' 必须是对象")
            continue
        if not pcfg.get("api_url"):
            errors.append(f"provider '{name}' 缺少 api_url")
        if not pcfg.get("model"):
            errors.append(f"provider '{name}' 缺少 model")

    default = cfg.get("default_provider")
    if default and default not in providers:
        errors.append(f"default_provider '{default}' 不存在于providers中")

    return len(errors) == 0, errors
