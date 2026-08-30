"""
集成测试 — 真实LLM + memory_v2
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from core_v2 import Engine, get_llm_client, ProviderConfig, ModelRole, SessionManager, LLMMessage
from memory_v2 import get_memory_store, get_search, get_tag_dictionary, MemoryRouter


def test_real_llm():
    """测试真实LLM调用"""
    llm = get_llm_client()
    api_key = os.getenv("XIAOMI_TOKEN_PLAN_API_KEY", "")
    print(f"[LLM] API Key loaded: {bool(api_key)} ({api_key[:10]}...)")

    config = ProviderConfig(
        name="xiaomi",
        api_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        api_key=api_key,
        model="mimo-v2.5-pro",
        role=ModelRole.DEFAULT,
        max_tokens=256,
        temperature=0.7,
    )
    llm.register_provider(config)

    resp = llm.generate([LLMMessage(role="user", content="你好，用一句话介绍你自己")])
    print(f"[LLM] Response: {resp.content[:200]}")
    print(f"[LLM] Provider: {resp.provider}, Model: {resp.model}")
    print(f"[LLM] Latency: {resp.latency_ms:.0f}ms, Tokens: {resp.tokens_used}")

    assert resp.content, "LLM response should not be empty"
    assert "LLM调用失败" not in resp.content, f"LLM call failed: {resp.content}"
    print("PASS test_real_llm")


def test_memory_v2():
    """测试memory_v2集成"""
    store = get_memory_store()
    tags = get_tag_dictionary()
    search = get_search()
    router = MemoryRouter(store, search, tags)

    ctx = router.build_context("你好")
    print(f"[Memory] context tokens: {ctx['tokens']}")
    print(f"[Memory] breakdown: {ctx['breakdown']}")
    if ctx["context"]:
        print(f"[Memory] preview: {ctx['context'][:300]}...")
    else:
        print("[Memory] no context (empty memory store)")
    print("PASS test_memory_v2")


def test_engine_full():
    """测试完整引擎：真实LLM + memory_v2"""
    from core_v2 import reset_engine, reset_llm_client

    # 重置单例
    reset_engine()
    reset_llm_client()

    # 配置LLM
    llm = get_llm_client()
    api_key = os.getenv("XIAOMI_TOKEN_PLAN_API_KEY", "")
    config = ProviderConfig(
        name="xiaomi",
        api_url="https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        api_key=api_key,
        model="mimo-v2.5-pro",
        role=ModelRole.DEFAULT,
        max_tokens=512,
        temperature=0.7,
    )
    llm.register_provider(config)

    # 配置记忆
    store = get_memory_store()
    tags = get_tag_dictionary()
    search = get_search()
    memory_router = MemoryRouter(store, search, tags)

    # 配置会话
    session_mgr = SessionManager(Path(__file__).parent / "data" / "sessions")

    # 创建引擎
    engine = Engine(
        llm_client=llm,
        session_manager=session_mgr,
        memory_router=memory_router,
    )

    # 测试对话
    response = engine.process("你好，你是谁？")
    print(f"[Engine] Response: {response[:300]}")
    assert response, "Engine response should not be empty"
    print("PASS test_engine_full")


if __name__ == "__main__":
    print("=" * 50)
    print("  集成测试 — 真实LLM + memory_v2")
    print("=" * 50)

    tests = [test_real_llm, test_memory_v2, test_engine_full]
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"FAIL {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print("=" * 50)
    print(f"Result: {passed} passed, {failed} failed")
    print("=" * 50)
    sys.exit(1 if failed else 0)
