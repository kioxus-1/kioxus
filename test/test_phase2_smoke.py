"""
Kioxus Core v2 Phase 2 — Smoke Test
测试 reasoning + planner
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_reasoning():
    """测试推理引擎"""
    from core_v2.reasoning import ReasoningEngine, ReasoningMode

    engine = ReasoningEngine()  # 无LLM

    # 直接响应
    r = engine.reason("你好", mode=ReasoningMode.DIRECT)
    assert r.mode == ReasoningMode.DIRECT
    assert r.confidence == 1.0
    assert not r.chain_broken

    # 模式选择
    assert engine.select_mode("你好") == ReasoningMode.DIRECT
    assert engine.select_mode("帮我分析一下Python和Go的优缺点") == ReasoningMode.CHAIN
    assert engine.select_mode("帮我设计一个分布式系统的架构方案") == ReasoningMode.CHAIN

    print("PASS reasoning")


def test_planner():
    """测试规划器"""
    from core_v2.planner import Planner, Complexity

    planner = Planner()  # 无LLM

    # 简单任务
    p = planner.plan("你好")
    assert p.complexity == Complexity.SIMPLE
    assert len(p.steps) == 1

    # 中等任务
    p = planner.plan("帮我写一个Python函数")
    assert p.complexity in (Complexity.MEDIUM, Complexity.SIMPLE)

    # 复杂任务
    p = planner.plan("首先分析需求，然后设计架构，最后实现系统并测试")
    assert p.complexity == Complexity.COMPLEX

    # 工具检测
    p = planner.plan("今天天气怎么样")
    assert "weather" in p.tools_used or p.needs_tool

    # PlanStep状态
    p = planner.plan("测试")
    assert p.next_step is not None
    p.mark_done(1)
    assert p.next_step is None

    print("PASS planner")


def test_engine_integration():
    """测试引擎集成"""
    from core_v2.engine import Engine, EngineState

    engine = Engine()
    engine.llm.register_mock()

    # 简单对话
    response = engine.process("你好")
    assert response
    assert engine.state == EngineState.IDLE

    # 复杂对话
    response = engine.process("分析一下Python和Go的优缺点")
    assert response

    # 状态
    status = engine.status()
    assert status["turn_count"] == 2

    print("PASS engine_integration")


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 2 Smoke Test")
    print("=" * 50)

    tests = [test_reasoning, test_planner, test_engine_integration]
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print("FAIL " + test.__name__ + ": " + str(e))
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 50)
    print("Result: " + str(passed) + " passed, " + str(failed) + " failed")
    print("=" * 50)
    sys.exit(1 if failed else 0)
