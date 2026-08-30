"""
Kioxus Core v2 — 沙箱测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.sandbox import (
    Sandbox, SandboxLevel, SandboxPolicy, SandboxResult,
    CodeChecker, get_sandbox, reset_sandbox, sandbox_exec,
    PRESET_POLICIES,
)


def test_code_checker():
    """测试代码静态检查"""
    policy = SandboxPolicy()
    checker = CodeChecker(policy)

    # 正常代码
    violations = checker.check("print('hello')")
    assert len(violations) == 0, f"正常代码不应有违规: {violations}"

    # 阻断的import
    violations = checker.check("import subprocess")
    assert any("blocked_import" in v for v in violations), f"subprocess应被阻断: {violations}"

    # 阻断的模式
    violations = checker.check("eval('1+1')")
    assert any("blocked_pattern" in v for v in violations), f"eval应被阻断: {violations}"

    # 网络模块（默认不允许）
    violations = checker.check("import urllib")
    assert any("network_blocked" in v for v in violations), f"urllib应被阻断: {violations}"

    print("PASS test_code_checker")


def test_sandbox_basic():
    """测试沙箱基本执行"""
    sandbox = Sandbox(SandboxLevel.NORMAL)

    # 正常执行
    result = sandbox.execute("print('hello sandbox')")
    assert result.success, f"正常代码应成功: {result.error}"
    assert "hello sandbox" in result.stdout
    assert result.execution_time_ms > 0

    # 语法错误
    result = sandbox.execute("def foo(")
    assert not result.success, "语法错误应失败"
    assert result.returncode != 0

    # 运行时错误
    result = sandbox.execute("raise ValueError('test')")
    assert not result.success, "运行时错误应失败"

    print("PASS test_sandbox_basic")


def test_sandbox_timeout():
    """测试沙箱超时"""
    sandbox = Sandbox(SandboxLevel.STRICT)
    sandbox.policy.max_execution_time = 1

    result = sandbox.execute("import time; time.sleep(10)")
    assert not result.success, "超时应失败"
    assert result.timed_out, "应标记为超时"

    print("PASS test_sandbox_timeout")


def test_sandbox_policy_block():
    """测试策略阻断"""
    sandbox = Sandbox(SandboxLevel.NORMAL)

    # 阻断subprocess
    result = sandbox.execute("import subprocess; subprocess.run(['echo', 'hi'])")
    assert not result.success, "subprocess应被阻断"
    assert len(result.policy_violations) > 0

    # 阻断eval
    result = sandbox.execute("eval('1+1')")
    assert not result.success, "eval应被阻断"

    print("PASS test_sandbox_policy_block")


def test_sandbox_output_limit():
    """测试输出大小限制"""
    sandbox = Sandbox(SandboxLevel.STRICT)
    sandbox.policy.max_output_size = 100  # 极小限制

    result = sandbox.execute("print('x' * 1000)")
    assert result.success
    assert len(result.stdout) <= 200  # 截断后应小于限制+截断标记

    print("PASS test_sandbox_output_limit")


def test_sandbox_levels():
    """测试不同安全级别"""
    for level in SandboxLevel:
        sandbox = Sandbox(level)
        assert sandbox.policy.level == level

        # 基本执行都应成功
        result = sandbox.execute("print(42)")
        assert result.success, f"Level {level.value} 基本执行应成功"

    print("PASS test_sandbox_levels")


def test_sandbox_unsafe_not_allowed_by_default():
    """测试默认不允许unsafe"""
    # 默认应该是NORMAL级别
    sandbox = Sandbox()
    assert sandbox.policy.level == SandboxLevel.NORMAL
    assert not sandbox.policy.allow_network

    print("PASS test_sandbox_unsafe_not_allowed_by_default")


def test_sandbox_convenience_function():
    """测试便捷函数"""
    reset_sandbox()

    result = sandbox_exec("print('convenient')")
    assert result.success
    assert "convenient" in result.stdout

    reset_sandbox()
    print("PASS test_sandbox_convenience_function")


def test_builtin_tools_code_exec():
    """测试builtin_tools的code_exec集成"""
    from core.builtin_tools import code_exec

    # 沙箱模式（默认）
    result = code_exec("print('sandbox mode')")
    assert result.success, f"沙箱执行应成功: {result.error}"
    assert "sandbox mode" in str(result.output)

    # unsafe模式
    result = code_exec("print('unsafe mode')", unsafe=True)
    assert result.success, f"unsafe执行应成功: {result.error}"

    print("PASS test_builtin_tools_code_exec")


if __name__ == "__main__":
    print("=" * 50)
    print("  Sandbox 测试")
    print("=" * 50)

    tests = [
        test_code_checker,
        test_sandbox_basic,
        test_sandbox_timeout,
        test_sandbox_policy_block,
        test_sandbox_output_limit,
        test_sandbox_levels,
        test_sandbox_unsafe_not_allowed_by_default,
        test_sandbox_convenience_function,
        test_builtin_tools_code_exec,
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
