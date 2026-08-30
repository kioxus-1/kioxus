"""
Kioxus — 交互式对话入口

用法：
    python run.py                        # 默认小米 MiMo
    python run.py --provider xiaomi      # 小米 MiMo Token Plan
    python run.py --provider minimax     # MiniMax
    python run.py --provider mock        # 测试模式
"""

import sys
import os

# 确保能导入 kioxus
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from dotenv import load_dotenv

from core_v2 import (
    Engine, get_engine,
    LLMClient, get_llm_client,
    ProviderConfig, ModelRole,
    SessionManager, get_session_manager,
)
from memory_v2 import get_memory_store, get_search, get_tag_dictionary, MemoryRouter


def load_env():
    """加载 .env 文件"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[Config] 已加载 {env_path}")
    else:
        print("[Config] 未找到 .env 文件")


def setup_xiaomi(client: LLMClient):
    """配置小米 MiMo Token Plan provider"""
    api_key = os.getenv("XIAOMI_TOKEN_PLAN_API_KEY", "")
    if not api_key:
        print("[Error] 未找到 XIAOMI_TOKEN_PLAN_API_KEY，请在 .env 中配置")
        return False

    config = ProviderConfig(
        name="xiaomi",
        api_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        api_key=api_key,
        model="mimo-v2.5-pro",
        role=ModelRole.DEFAULT,
        max_tokens=2048,
        temperature=0.7,
    )
    client.register_provider(config)
    print(f"[LLM] 小米 MiMo 已配置 ({config.model})")
    return True


def setup_minimax(client: LLMClient):
    """配置 MiniMax provider"""
    api_key = os.getenv("MINIMAX_API_KEY", "")
    if not api_key:
        print("[Error] 未找到 MINIMAX_API_KEY，请在 .env 中配置")
        return False

    config = ProviderConfig(
        name="minimax",
        api_url="https://api.minimax.chat/v1/text/chatcompletion_v2",
        api_key=api_key,
        model="MiniMax-Text-01",
        role=ModelRole.DEFAULT,
        max_tokens=2048,
        temperature=0.7,
    )
    client.register_provider(config)
    print(f"[LLM] MiniMax 已配置 ({config.model})")
    return True


def setup_mock(client: LLMClient):
    """配置 Mock provider（测试用）"""
    client.register_mock()
    print("[LLM] Mock 已配置（测试模式）")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Kioxus")
    parser.add_argument("--provider", default="xiaomi", choices=["xiaomi", "minimax", "mock"],
                        help="LLM provider (default: xiaomi)")
    parser.add_argument("--session", default=None, help="Session ID (default: auto)")
    args = parser.parse_args()

    print("=" * 50)
    print("  Kioxus v2.0")
    print("=" * 50)
    print()

    # 1. 加载配置
    load_env()

    # 2. 配置 LLM
    llm = get_llm_client()
    if args.provider == "xiaomi":
        if not setup_xiaomi(llm):
            print("[Fallback] 切换到 Mock 模式")
            setup_mock(llm)
    elif args.provider == "minimax":
        if not setup_minimax(llm):
            print("[Fallback] 切换到 Mock 模式")
            setup_mock(llm)
    else:
        setup_mock(llm)

    # 3. 配置会话
    session_mgr = get_session_manager(Path(__file__).parent / "data" / "sessions")
    session = session_mgr.start_session(args.session)
    print(f"[Session] {session.session_id}")

    # 4. 初始化记忆模块
    store = get_memory_store()
    tags = get_tag_dictionary()
    search = get_search()
    memory_router = MemoryRouter(store, search, tags)
    print(f"[Memory] 已接入 memory_v2")

    # 5. 创建引擎
    engine = Engine(
        llm_client=llm,
        session_manager=session_mgr,
        memory_router=memory_router,
    )

    print()
    print("输入消息开始对话，输入 /quit 退出")
    print("-" * 50)

    # 5. 交互循环
    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见！")
            break

        if user_input == "/status":
            status = engine.status()
            print(f"状态: {status}")
            continue

        if user_input == "/history":
            msgs = session_mgr.get_recent_messages(20)
            for m in msgs:
                role = "你" if m["role"] == "user" else "Kioxus"
                print(f"  {role}: {m['content'][:100]}")
            continue

        if user_input == "/checkpoint":
            cp = session_mgr.checkpoint()
            print(f"已保存 checkpoint: {cp.checkpoint_id}")
            continue

        # 处理消息
        response = engine.process(user_input)
        print(f"\nKioxus: {response}")

    # 保存会话
    session_mgr.save_session()
    print(f"[Session] 已保存 {session.session_id}")


if __name__ == "__main__":
    main()
