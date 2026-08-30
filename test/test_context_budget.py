"""
Kioxus Core v2 — Context预算硬限制测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core_v2.context import (
    ContextBudget, ContextTracker, ContextBuilder,
    ContextBudgetExceeded, estimate_tokens,
)


def test_context_tracker_basic():
    """测试ContextTracker基本功能"""
    budget = ContextBudget(total=1000)
    tracker = ContextTracker(budget)

    # 记录一次使用
    status = tracker.record({"system": 100, "memory": 200, "history": 400, "user": 50})
    assert status["turn"] == 1
    assert status["status"]["turns_recorded"] == 1
    assert status["status"]["total_used"] == 750

    # 再记录一次
    status = tracker.record({"system": 100, "memory": 200, "history": 400, "user": 50})
    assert status["turn"] == 2
    assert status["status"]["turns_recorded"] == 2
    # total_used应该是两次的累积

    print("PASS test_context_tracker_basic")


def test_context_tracker_compression_threshold():
    """测试压缩触发阈值"""
    budget = ContextBudget(total=1000)
    tracker = ContextTracker(budget)
    tracker.compression_threshold = 0.8  # 80%

    # 低于阈值
    tracker.record({"total": 500})
    status = tracker._check_status()
    assert not status["needs_compression"], "50%不应触发压缩"

    # 超过阈值
    tracker.record({"total": 500})
    status = tracker._check_status()
    assert status["needs_compression"], "100%应触发压缩"

    print("PASS test_context_tracker_compression_threshold")


def test_context_tracker_budget_exceeded():
    """测试预算超限检测"""
    budget = ContextBudget(total=1000)
    tracker = ContextTracker(budget)

    tracker.record({"total": 900})
    status = tracker._check_status()
    assert not status["budget_exceeded"]

    tracker.record({"total": 200})
    status = tracker._check_status()
    assert status["budget_exceeded"], "超过1000应标记超限"

    print("PASS test_context_tracker_budget_exceeded")


def test_context_tracker_summary():
    """测试使用摘要"""
    budget = ContextBudget(total=5000)
    tracker = ContextTracker(budget)

    # 空摘要
    summary = tracker.get_summary()
    assert summary["turns"] == 0
    assert summary["total_tokens"] == 0

    # 记录几次
    tracker.record({"total": 100})
    tracker.record({"total": 200})
    tracker.record({"total": 300})

    summary = tracker.get_summary()
    assert summary["turns"] == 3
    assert summary["total_tokens"] == 600
    assert summary["avg_tokens"] == 200

    print("PASS test_context_tracker_summary")


def test_context_tracker_reset():
    """测试重置"""
    budget = ContextBudget(total=1000)
    tracker = ContextTracker(budget)

    tracker.record({"total": 500})
    tracker.reset()

    summary = tracker.get_summary()
    assert summary["turns"] == 0
    assert summary["total_tokens"] == 0

    print("PASS test_context_tracker_reset")


def test_hard_limit_enforce():
    """测试硬限制模式"""
    budget = ContextBudget(total=100, enforce="hard")
    builder = ContextBuilder(budget=budget)

    # 正常构建应该成功
    result = builder.build(user_message="short message")
    assert result.total_tokens <= budget.total

    # 构建超长内容应该抛异常
    try:
        long_message = "这是一个很长的消息。" * 100
        result = builder.build(user_message=long_message)
        # 如果系统提示+用户消息超过100 tokens，应该抛异常
        if result.total_tokens > 100:
            assert False, "硬限制模式下应抛出ContextBudgetExceeded"
    except ContextBudgetExceeded as e:
        assert "超限" in str(e)
        print(f"  捕获到预期异常: {e}")

    print("PASS test_hard_limit_enforce")


def test_soft_limit_truncate():
    """测试软限制截断（默认行为）"""
    budget = ContextBudget(total=100, enforce="soft")
    builder = ContextBuilder(budget=budget)

    # 超长内容应该被截断而不是抛异常
    long_message = "这是一个很长的消息。" * 100
    result = builder.build(user_message=long_message)
    # 不应该抛异常
    assert result.total_tokens > 0

    print("PASS test_soft_limit_truncate")


def test_estimate_tokens():
    """测试token估算"""
    # 空字符串
    assert estimate_tokens("") == 0

    # 纯中文
    tokens = estimate_tokens("你好世界")
    assert tokens > 0
    assert tokens < 10  # 4个中文字应该很少

    # 纯英文
    tokens = estimate_tokens("hello world")
    assert tokens > 0

    # 混合
    tokens = estimate_tokens("你好world")
    assert tokens > 0

    print("PASS test_estimate_tokens")


if __name__ == "__main__":
    print("=" * 50)
    print("  Context预算硬限制 测试")
    print("=" * 50)

    tests = [
        test_context_tracker_basic,
        test_context_tracker_compression_threshold,
        test_context_tracker_budget_exceeded,
        test_context_tracker_summary,
        test_context_tracker_reset,
        test_hard_limit_enforce,
        test_soft_limit_truncate,
        test_estimate_tokens,
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
        print()

    print("=" * 50)
    print(f"Result: {passed} passed, {failed} failed")
    print("=" * 50)
    sys.exit(1 if failed else 0)
