"""
Kioxus Core v2 — Smoke Test
验证所有模块能跑通
"""

import sys
import os

# 确保能导入 kioxus
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_input():
    """测试输入处理"""
    from core_v2.input import InputProcessor

    proc = InputProcessor()

    # 聊天
    r = proc.parse("你好")
    assert r.intent == "chat", f"Expected chat, got {r.intent}"
    assert not r.needs_tools

    # 查询
    r = proc.parse("之前聊过什么")
    assert r.intent == "query", f"Expected query, got {r.intent}"
    assert r.needs_memory

    # 命令
    r = proc.parse("帮我查天气")
    assert r.entities or r.intent == "command", f"Should detect entities or command"

    # 紧急
    r = proc.parse("紧急！马上改一下这个bug")
    assert r.urgency == "high", f"Expected high urgency, got {r.urgency}"

    print("PASS input")


def test_session():
    """测试会话管理"""
    import tempfile
    from core_v2.session import SessionManager

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = SessionManager(storage_dir=__import__("pathlib").Path(tmpdir))

        # 创建会话
        s = mgr.start_session("test_001")
        assert s.session_id == "test_001"
        assert mgr.current == s

        # 添加对话
        mgr.add_turn("user", "你好")
        mgr.add_turn("assistant", "你好！")
        assert s.turn_count == 2

        # 获取消息
        msgs = mgr.get_recent_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

        # Checkpoint
        cp = mgr.checkpoint()
        assert cp.turn_count == 2

        # 恢复
        mgr2 = SessionManager(storage_dir=__import__("pathlib").Path(tmpdir))
        ok = mgr2.restore(cp.checkpoint_id)
        assert ok
        assert mgr2.current.turn_count == 2

        # 持久化
        mgr.save_session()
        mgr3 = SessionManager(storage_dir=__import__("pathlib").Path(tmpdir))
        ok = mgr3.load_session("test_001")
        assert ok
        assert mgr3.current.turn_count == 2

    print("PASS session")


def test_context():
    """测试上下文组装"""
    from core_v2.context import ContextBuilder, ContextBudget

    builder = ContextBuilder()

    # 简单对话
    result = builder.build("你好", [{"role": "user", "content": "上一句"}])
    assert result.messages
    assert result.messages[0]["role"] == "system"
    assert result.messages[-1]["role"] == "user"
    assert result.messages[-1]["content"] == "你好"
    assert result.total_tokens > 0

    print("PASS context")


def test_output():
    """测试输出处理"""
    from core_v2.output import OutputHandler, Observation

    handler = OutputHandler()

    # 普通回复
    obs = Observation(content="你好！")
    r = handler.format(obs)
    assert r == "你好！"

    # 工具结果
    obs = Observation(content="", is_tool_result=True, tool_name="weather", tool_output={"temp": 28})
    r = handler.format(obs)
    assert "28" in r

    # 错误
    obs = Observation(content="连接超时", is_error=True, tool_name="search")
    r = handler.format(obs)
    assert "search" in r
    assert "连接超时" in r

    print("PASS output")


def test_llm():
    """测试LLM客户端"""
    from core_v2.llm import LLMClient, LLMMessage, ModelRole

    client = LLMClient()
    client.register_mock()

    # 基本调用
    msgs = [LLMMessage(role="user", content="hello")]
    resp = client.generate(msgs)
    assert resp.content
    assert resp.provider == "mock"

    # 角色选择
    role = client.select_role("chat")
    assert role == ModelRole.DEFAULT

    # 便捷方法
    resp = client.generate_from_context("你是助手", "你好")
    assert resp.content

    print("PASS llm")


def test_engine():
    """测试核心引擎（Mock模式）"""
    from core_v2.engine import Engine, EngineState

    engine = Engine()
    engine.llm.register_mock()

    # 基本对话
    response = engine.process("你好")
    assert response
    assert engine.state == EngineState.IDLE

    # 查询
    response = engine.process("之前聊过什么")
    assert response

    # 状态
    status = engine.status()
    assert status["turn_count"] == 2
    assert status["state"] == "idle"

    print("PASS engine")


if __name__ == "__main__":
    print("=" * 50)
    print("Kioxus Core v2 — Smoke Test")
    print("=" * 50)

    tests = [
        test_input,
        test_session,
        test_context,
        test_output,
        test_llm,
        test_engine,
    ]

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

    print("=" * 50)
    print(f"Result: {passed} passed, {failed} failed")
    print("=" * 50)

    sys.exit(1 if failed else 0)
