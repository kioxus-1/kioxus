"""
Kioxus Core v2 Phase 3 — Smoke Test
测试 tools + builtin_tools + decomposer
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_tool_registry():
    """测试工具注册表"""
    from core.tools import ToolRegistry, ToolMeta, ToolCategory, ToolResult

    reg = ToolRegistry()

    # 注册
    reg.register(
        ToolMeta(name="echo", description="回显", category=ToolCategory.CUSTOM, params={"text": "str"}),
        lambda text="": text,
    )
    assert reg.has("echo")
    assert "echo" in reg.list_names()

    # 调用
    result = reg.call("echo", {"text": "hello"})
    assert result.success
    assert result.output == "hello"
    assert result.latency_ms >= 0

    # 不存在的工具
    result = reg.call("nope")
    assert not result.success
    assert "未注册" in result.error

    # LLM描述
    desc = reg.describe_for_llm()
    assert "echo" in desc

    # 统计
    stats = reg.stats()
    assert stats["echo"]["calls"] == 1

    # 注销
    reg.unregister("echo")
    assert not reg.has("echo")

    print("PASS tool_registry")


def test_builtin_tools():
    """测试内置工具"""
    from core.builtin_tools import http_fetch, file_read, file_write, file_list, code_exec
    import tempfile
    from pathlib import Path

    # file_write + file_read
    with tempfile.TemporaryDirectory() as tmp:
        test_file = str(Path(tmp) / "test.txt")
        result = file_write(test_file, "hello world")
        assert result.success

        result = file_read(test_file)
        assert result.success
        assert result.output["content"] == "hello world"

        # file_list
        result = file_list(tmp)
        assert result.success
        assert result.output["count"] == 1

    # code_exec
    result = code_exec("print(1+1)")
    assert result.success
    assert result.output["stdout"].strip() == "2"

    # code_exec 安全限制
    result = code_exec("import os; os.system('echo hacked')")
    assert not result.success
    assert "安全" in result.error

    # http_fetch（测试一个真实URL）
    result = http_fetch("https://httpbin.org/html", max_length=500)
    if result.success:
        assert "content" in result.output
        print(f"  http_fetch: {len(result.output['content'])} chars")
    else:
        print(f"  http_fetch 跳过（网络问题）: {result.error}")

    print("PASS builtin_tools")


def test_decomposer():
    """测试目标分解器"""
    from core.decomposer import GoalDecomposer, DecomposeStrategy

    decomposer = GoalDecomposer()  # 无LLM

    # 简单任务不分解
    result = decomposer.decompose("你好")
    assert result.is_trivial
    assert len(result.subtasks) == 1

    # 复杂任务按规则分解
    result = decomposer.decompose("首先分析需求，然后设计架构，最后实现系统")
    assert len(result.subtasks) >= 2
    assert result.strategy == DecomposeStrategy.RULE
    print(f"  分解结果: {len(result.subtasks)} 个子任务")

    # 工具检测
    result = decomposer.decompose("搜索Python教程并保存到文件")
    assert result.needs_tools
    print(f"  检测到工具: {result.tools_used}")

    # 子任务状态管理
    result = decomposer.decompose("第一步写代码，第二步测试，第三步部署")
    assert result.next_task is not None
    result.mark_done(1)
    result.mark_done(2)
    result.mark_done(3)
    assert result.all_done
    assert result.progress == "3/3"

    print("PASS decomposer")


def test_engine_integration():
    """测试引擎集成（Phase 3）"""
    from core.engine import Engine, EngineState, reset_engine
    from core import reset_llm_client, reset_tool_registry, reset_decomposer

    reset_engine()
    reset_llm_client()
    reset_tool_registry()
    reset_decomposer()

    engine = Engine()
    engine.llm.register_mock()

    # 工具已自动注册
    tools = engine.list_tools()
    assert "http_fetch" in tools
    assert "file_read" in tools
    assert "code_exec" in tools
    print(f"  已注册工具: {tools}")

    # 状态查询包含工具统计
    status = engine.status()
    assert "tool_stats" in status

    # 目标分解
    decomp = engine.decompose_goal("首先搜索Python教程，然后写一个脚本测试")
    assert decomp["subtasks"]
    print(f"  目标分解: {len(decomp['subtasks'])} 个子任务")

    # 正常对话
    response = engine.process("你好")
    assert response
    assert engine.state == EngineState.IDLE

    print("PASS engine_integration")


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 3 Smoke Test")
    print("=" * 50)

    tests = [test_tool_registry, test_builtin_tools, test_decomposer, test_engine_integration]
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
