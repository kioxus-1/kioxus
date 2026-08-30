"""
Kioxus Main Entry Point
Multi-agent framework with adversarial verification

v0.3.0 — core_v2 architecture
Three principles: Adversarial Verification, Hard Boundary Isolation, Quantifiable Context
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from dotenv import load_dotenv

from core_v2 import (
    Engine, get_engine, reset_engine, EngineState,
    LLMClient, get_llm_client, reset_llm_client,
    ProviderConfig, ModelRole,
    SessionManager, get_session_manager,
    ContextBudget, ContextTracker,
    ToolRegistry, get_tool_registry, register_builtin_tools,
    Verifier, get_verifier,
    Sandbox, get_sandbox, SandboxLevel,
    GoalDecomposer, get_decomposer,
)
from memory_v2 import get_memory_store, get_search, get_tag_dictionary, MemoryRouter


__version__ = "0.3.0"
__all__ = ["Kioxus", "create_kioxus"]


class Kioxus:
    """
    Kioxus 主系统 — core_v2 架构

    三大原则：
    1. 对抗性验证 — Verifier独立审查输出
    2. 硬边界隔离 — Sandbox策略由系统强制
    3. 可量化上下文 — ContextTracker追踪Token预算
    """

    def __init__(self, config: dict = None):
        self.config = config or {}

        # 加载环境变量
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # 1. LLM 客户端
        self.llm = get_llm_client()
        self._setup_providers()

        # 2. 会话管理
        session_dir = Path(__file__).parent / "data" / "sessions"
        self.session_mgr = get_session_manager(session_dir)

        # 3. 记忆系统
        store = get_memory_store()
        tags = get_tag_dictionary()
        search = get_search()
        self.memory_router = MemoryRouter(store, search, tags)

        # 4. 核心引擎
        self.engine = Engine(
            llm_client=self.llm,
            session_manager=self.session_mgr,
            memory_router=self.memory_router,
            config=self.config,
        )

        # 5. 注册内置工具
        register_builtin_tools()

        # 6. 三大原则组件
        self.verifier = get_verifier()
        self.sandbox = get_sandbox(SandboxLevel.NORMAL)
        self.decomposer = get_decomposer()

    def _setup_providers(self):
        """配置 LLM providers"""
        import os

        # 小米 MiMo
        xiaomi_key = os.getenv("XIAOMI_TOKEN_PLAN_API_KEY", "")
        if xiaomi_key:
            self.llm.register_provider(ProviderConfig(
                name="xiaomi",
                api_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
                api_key=xiaomi_key,
                model="mimo-v2.5-pro",
                role=ModelRole.DEFAULT,
                max_tokens=2048,
                temperature=0.7,
            ))

        # MiniMax
        minimax_key = os.getenv("MINIMAX_API_KEY", "")
        if minimax_key:
            self.llm.register_provider(ProviderConfig(
                name="minimax",
                api_url="https://api.minimax.chat/v1/text/chatcompletion_v2",
                api_key=minimax_key,
                model="MiniMax-Text-01",
                role=ModelRole.DEFAULT,
                max_tokens=2048,
                temperature=0.7,
            ))

    def chat(self, message: str) -> str:
        """处理用户消息，返回回复"""
        return self.engine.process(message)

    def get_status(self) -> dict:
        """获取系统状态"""
        return {
            "version": __version__,
            "engine": self.engine.status(),
            "providers": self.llm.get_status() if hasattr(self.llm, "get_status") else {},
            "principles": {
                "adversarial_verification": True,
                "hard_boundary_isolation": True,
                "quantifiable_context": True,
            },
        }

    def call_tool(self, tool_id: str, params: dict = None) -> dict:
        """调用已注册的工具"""
        registry = get_tool_registry()
        return registry.call(tool_id, params or {})


def create_kioxus(config: dict = None) -> Kioxus:
    """工厂方法：创建 Kioxus 实例"""
    return Kioxus(config=config)


if __name__ == "__main__":
    print(f"Kioxus v{__version__}")
    print("=" * 40)

    kioxus = Kioxus()
    status = kioxus.get_status()

    print(f"Engine: {status['engine'].get('state', 'unknown')}")
    print(f"Principles:")
    for k, v in status["principles"].items():
        print(f"  {k}: {'✅' if v else '❌'}")
    print()
    print("用法: python src/run.py (命令行) | python src/desktop.py (桌面)")
