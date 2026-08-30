"""
Kioxus Core v2 — Verifier 测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.verifier import (
    Verifier, Verdict, VerificationResult,
    OutputFormatCheck, ToolResultCheck, RelevanceCheck, SafetyCheck, ConsistencyCheck,
    get_verifier, reset_verifier,
)


def test_output_format_check():
    """测试输出格式检查"""
    checker = OutputFormatCheck()

    # 正常输出
    r = checker.check("这是一段正常的回复")
    assert r.passed, f"正常输出应通过: {r.message}"

    # 空输出
    r = checker.check("")
    assert not r.passed, "空输出应失败"
    assert "空" in r.message

    # 纯空白
    r = checker.check("   \n  ")
    assert not r.passed, "纯空白应失败"

    print("PASS test_output_format_check")


def test_tool_result_check():
    """测试工具结果校验"""
    checker = ToolResultCheck()

    # 正常输出
    r = checker.check("天气晴朗，温度25度")
    assert r.passed, f"正常输出应通过: {r.message}"

    # 包含错误信息
    r = checker.check("工具调用失败: FileNotFoundError")
    assert not r.passed, "包含错误信息应失败"

    # 包含Traceback
    r = checker.check("结果如下\nTraceback (most recent call last):\n  File ...")
    assert not r.passed, "包含Traceback应失败"

    # 空工具输出
    r = checker.check("查询结果为空", tool_output="")
    assert not r.passed, "空工具输出应失败"

    print("PASS test_tool_result_check")


def test_relevance_check():
    """测试相关性检查"""
    checker = RelevanceCheck()

    # 相关输出
    r = checker.check("Python是一种编程语言，广泛用于AI开发", "Python是什么")
    assert r.passed, f"相关输出应通过: {r.message}"

    # 短输入（放宽检查）
    r = checker.check("今天天气很好", "你好")
    assert r.passed, "短输入应放宽检查"

    # 无关键词输入
    r = checker.check("任何输出", "？")
    assert r.passed, "无关键词输入应跳过"

    print("PASS test_relevance_check")


def test_safety_check():
    """测试安全检查"""
    checker = SafetyCheck()

    # 正常输出
    r = checker.check("这是一个安全的回复")
    assert r.passed, f"正常输出应通过: {r.message}"

    # 包含API密钥
    r = checker.check("你的api_key是sk-abc123def456ghi789jkl012mno345")
    assert not r.passed, "包含API密钥应失败"

    # 包含密码
    r = checker.check("password: mysecret123")
    assert not r.passed, "包含密码应失败"

    # 包含私钥
    r = checker.check("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAK...")
    assert not r.passed, "包含私钥应失败"

    print("PASS test_safety_check")


def test_consistency_check():
    """测试一致性检查"""
    checker = ConsistencyCheck()

    # 一致的输出
    r = checker.check("Python是一种编程语言。Python广泛用于开发。")
    assert r.passed, f"一致输出应通过: {r.message}"

    # 长输出跳过
    long_text = "很长的内容" * 500
    r = checker.check(long_text)
    assert r.passed, "长输出应跳过一致性检查"

    print("PASS test_consistency_check")


def test_verifier_integration():
    """测试Verifier完整流程"""
    reset_verifier()
    verifier = get_verifier()

    # 正常输出
    r = verifier.verify(
        output="Python是一种编程语言，由Guido van Rossum创建",
        user_input="Python是什么",
    )
    assert r.passed, f"正常输出应通过: {r.error_summary}"
    assert r.verdict == Verdict.PASS

    # 空输出
    r = verifier.verify(output="", user_input="你好")
    assert not r.passed, "空输出应失败"
    assert r.verdict == Verdict.FAIL

    # 包含错误的输出
    r = verifier.verify(
        output="工具调用失败: PermissionError",
        user_input="读取文件",
        is_error=True,
    )
    # 错误信息直接传递，标记为WARN
    assert r.verdict == Verdict.WARN

    # 包含敏感信息
    r = verifier.verify(
        output="配置如下：api_key=sk-abc123def456ghi789jkl012",
        user_input="查看配置",
    )
    assert not r.passed, "包含敏感信息应失败"

    reset_verifier()
    print("PASS test_verifier_integration")


def test_verifier_retry():
    """测试重试逻辑"""
    verifier = Verifier()

    # 失败结果
    result = verifier.verify(output="", user_input="你好")
    assert verifier.should_retry(result), "首次失败应重试"

    # 模拟已重试
    result.retry_count = 2
    assert not verifier.should_retry(result), "达到最大重试次数后不应重试"

    # 生成重试消息
    msg = verifier.format_retry_message(result)
    assert "修正" in msg or "重试" in msg

    print("PASS test_verifier_retry")


if __name__ == "__main__":
    print("=" * 50)
    print("  Verifier 测试")
    print("=" * 50)

    tests = [
        test_output_format_check,
        test_tool_result_check,
        test_relevance_check,
        test_safety_check,
        test_consistency_check,
        test_verifier_integration,
        test_verifier_retry,
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
