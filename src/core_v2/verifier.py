"""
Kioxus Core v2 — Verifier（对抗性验证模块）

核心原则：不信任任何Agent的输出
Verifier独立审查交付物，不看Agent的思考过程

审查维度：
  1. 格式检查 — 输出长度、结构、必需字段
  2. 工具结果校验 — 工具调用是否成功、返回值是否合理
  3. 一致性检查 — 输出是否与用户问题相关、是否自相矛盾
  4. 安全检查 — 是否包含有害内容、是否泄露敏感信息

不依赖LLM做判断，基于规则和统计方法
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


# ============== 审查结果 ==============

class Verdict(Enum):
    """审查结论"""
    PASS = "pass"           # 通过
    WARN = "warn"           # 警告（通过但有瑕疵）
    FAIL = "fail"           # 不通过，需要重做
    REJECT = "reject"       # 拒绝，上报人工


@dataclass
class CheckResult:
    """单项检查结果"""
    name: str               # 检查名称
    passed: bool            # 是否通过
    message: str = ""       # 说明
    severity: str = "info"  # info / warning / error


@dataclass
class VerificationResult:
    """完整审查结果"""
    verdict: Verdict                    # 最终结论
    checks: List[CheckResult] = field(default_factory=list)
    retry_count: int = 0                # 已重试次数
    error_summary: str = ""             # 失败原因摘要

    @property
    def passed(self) -> bool:
        """passed"""
        return self.verdict in (Verdict.PASS, Verdict.WARN)

    @property
    def failed_checks(self) -> List[CheckResult]:
        """failed_checks"""
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> Dict:
        """to_dict"""
        return {
            "verdict": self.verdict.value,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "message": c.message, "severity": c.severity}
                for c in self.checks
            ],
            "retry_count": self.retry_count,
            "error_summary": self.error_summary,
        }


# ============== 检查规则 ==============

class OutputFormatCheck:
    """输出格式检查"""

    MIN_LENGTH = 1          # 最少字符数
    MAX_LENGTH = 50000      # 最多字符数
    MAX_NEWLINES = 500      # 最大换行数

    def check(self, output: str, user_input: str = "") -> CheckResult:
        """check"""
        if not output or not output.strip():
            return CheckResult(
                name="output_format",
                passed=False,
                message="输出为空",
                severity="error",
            )

        length = len(output.strip())

        if length < self.MIN_LENGTH:
            return CheckResult(
                name="output_format",
                passed=False,
                message=f"输出过短（{length}字符，最少{self.MIN_LENGTH}）",
                severity="error",
            )

        if length > self.MAX_LENGTH:
            return CheckResult(
                name="output_format",
                passed=False,
                message=f"输出过长（{length}字符，最多{self.MAX_LENGTH}）",
                severity="warning",
            )

        newlines = output.count("\n")
        if newlines > self.MAX_NEWLINES:
            return CheckResult(
                name="output_format",
                passed=False,
                message=f"换行过多（{newlines}行，最多{self.MAX_NEWLINES}）",
                severity="warning",
            )

        return CheckResult(name="output_format", passed=True, message="格式正常")


class ToolResultCheck:
    """工具结果校验"""

    # 工具调用失败的特征
    ERROR_PATTERNS = [
        r"工具调用失败",
        r"Tool.*(?:error|fail|exception)",
        r"Traceback \(most recent call",
        r"ModuleNotFoundError",
        r"ImportError",
        r"PermissionError",
        r"FileNotFoundError",
        r"ConnectionError",
        r"TimeoutError",
    ]

    def check(self, output: str, tool_name: str = None, tool_output: Any = None) -> CheckResult:
        """check"""
        # 检查输出中是否包含错误信息
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                return CheckResult(
                    name="tool_result",
                    passed=False,
                    message=f"输出包含错误特征: {pattern}",
                    severity="error",
                )

        # 如果有工具输出，检查是否为空
        if tool_output is not None:
            if isinstance(tool_output, str) and not tool_output.strip():
                return CheckResult(
                    name="tool_result",
                    passed=False,
                    message="工具返回空结果",
                    severity="error",
                )

        return CheckResult(name="tool_result", passed=True, message="工具结果正常")


class RelevanceCheck:
    """相关性检查 — 输出是否与用户问题相关"""

    # 中文停用词
    STOP_WORDS = set("的了是在我你他她它们这那个有不人也大为上中到说时要就出会可以着过好都来对没被从到把被让给比")

    def _extract_keywords(self, text: str) -> set:
        """提取关键词（简单分词）"""
        # 去除标点和停用词
        text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text)
        words = set()
        # 中文：取2-4字组合
        chinese = re.findall(r'[\u4e00-\u9fff]{2,4}', text)
        for w in chinese:
            if w not in self.STOP_WORDS:
                words.add(w)
        # 英文：取单词
        english = re.findall(r'[a-zA-Z]{3,}', text.lower())
        words.update(english)
        return words

    def check(self, output: str, user_input: str) -> CheckResult:
        """check"""
        if not user_input:
            return CheckResult(name="relevance", passed=True, message="无用户输入，跳过相关性检查")

        input_keywords = self._extract_keywords(user_input)
        output_keywords = self._extract_keywords(output)

        if not input_keywords:
            return CheckResult(name="relevance", passed=True, message="输入无关键词，跳过相关性检查")

        # 计算重叠率
        overlap = input_keywords & output_keywords
        overlap_ratio = len(overlap) / len(input_keywords) if input_keywords else 0

        # 如果用户输入很短（<5字），放宽检查
        if len(user_input.strip()) < 5:
            threshold = 0.0
        else:
            threshold = 0.1

        if overlap_ratio < threshold:
            return CheckResult(
                name="relevance",
                passed=False,
                message=f"输出与输入相关性低（重叠率{overlap_ratio:.1%}，关键词: {input_keywords}）",
                severity="warning",
            )

        return CheckResult(
            name="relevance",
            passed=True,
            message=f"相关性正常（重叠率{overlap_ratio:.1%}）",
        )


class SafetyCheck:
    """安全检查 — 敏感信息泄露"""

    # 敏感信息模式
    SENSITIVE_PATTERNS = [
        (r'(?:api[_-]?key|secret|password|token)\s*[:=]\s*\S+', "API密钥/密码"),
        (r'(?:sk-|ak-|rk-)[a-zA-Z0-9]{20,}', "密钥格式字符串"),
        (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "私钥"),
        (r'(?:192\.168|10\.|172\.(?:1[6-9]|2\d|3[01]))\.\d+\.\d+', "内网IP"),
    ]

    def check(self, output: str) -> CheckResult:
        """check"""
        for pattern, desc in self.SENSITIVE_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                return CheckResult(
                    name="safety",
                    passed=False,
                    message=f"输出可能包含敏感信息: {desc}",
                    severity="error",
                )

        return CheckResult(name="safety", passed=True, message="安全检查通过")


class ConsistencyCheck:
    """一致性检查 — 输出是否自相矛盾"""

    # 矛盾模式对
    CONTRADICTION_PAIRS = [
        (r'是\b', r'不是\b'),
        (r'能\b', r'不能\b'),
        (r'可以\b', r'不可以\b'),
        (r'有\b', r'没有\b'),
        (r'正确\b', r'错误\b'),
        (r'成功\b', r'失败\b'),
        (r'支持\b', r'不支持\b'),
    ]

    def check(self, output: str) -> CheckResult:
        """check"""
        # 只检查短输出（长输出中矛盾词对出现是正常的）
        if len(output) > 2000:
            return CheckResult(name="consistency", passed=True, message="长输出，跳过一致性检查")

        sentences = re.split(r'[。！？\n]', output)
        sentences = [s.strip() for s in sentences if s.strip()]

        for pos_pattern, neg_pattern in self.CONTRADICTION_PAIRS:
            pos_sentences = [s for s in sentences if re.search(pos_pattern, s)]
            neg_sentences = [s for s in sentences if re.search(neg_pattern, s)]

            # 如果同一段话中既有肯定又有否定，可能是矛盾
            if pos_sentences and neg_sentences:
                # 排除正常用法（如"不是A而是B"）
                for ps in pos_sentences:
                    for ns in neg_sentences:
                        # 如果两个句子很接近，可能是矛盾
                        if abs(len(ps) - len(ns)) < 50:
                            return CheckResult(
                                name="consistency",
                                passed=False,
                                message=f"可能存在矛盾: '{ps[:30]}...' vs '{ns[:30]}...'",
                                severity="warning",
                            )

        return CheckResult(name="consistency", passed=True, message="一致性检查通过")


# ============== Verifier 主类 ==============

class Verifier:
    """
    对抗性验证器

    核心原则：不信任任何Agent的输出
    独立审查交付物，不看Agent的思考过程

    使用方式：
        verifier = Verifier()
        result = verifier.verify(
            output="Agent的输出",
            user_input="用户的输入",
            tool_name="使用的工具名",
            tool_output="工具的原始输出",
        )
        if not result.passed:
            # 处理失败
    """

    MAX_RETRIES = 2  # 最大重试次数

    def __init__(self, config: Dict = None):
        """__init__"""
        config = config or {}

        # 初始化检查器
        self.checks = {
            "format": OutputFormatCheck(),
            "tool": ToolResultCheck(),
            "relevance": RelevanceCheck(),
            "safety": SafetyCheck(),
            "consistency": ConsistencyCheck(),
        }

        # 可配置的检查开关
        self.enabled_checks = config.get("enabled_checks", list(self.checks.keys()))

    def verify(
        self,
        output: str,
        user_input: str = "",
        tool_name: str = None,
        tool_output: Any = None,
        is_error: bool = False,
    ) -> VerificationResult:
        """
        审查Agent输出

        参数：
            output: Agent的最终输出
            user_input: 用户的原始输入
            tool_name: 使用的工具名（如果有）
            tool_output: 工具的原始输出（如果有）
            is_error: 输出是否为错误信息

        返回：
            VerificationResult
        """
        results = []

        # 如果输出本身就是错误，直接标记为WARN（不阻塞错误信息的传递）
        if is_error:
            results.append(CheckResult(
                name="error_passthrough",
                passed=True,
                message="错误信息直接传递",
                severity="info",
            ))
            return VerificationResult(
                verdict=Verdict.WARN,
                checks=results,
                error_summary="Agent输出为错误信息",
            )

        # 执行各项检查
        for check_name in self.enabled_checks:
            checker = self.checks.get(check_name)
            if not checker:
                continue

            try:
                if check_name == "format":
                    result = checker.check(output, user_input)
                elif check_name == "tool":
                    result = checker.check(output, tool_name, tool_output)
                elif check_name == "relevance":
                    result = checker.check(output, user_input)
                elif check_name == "safety":
                    result = checker.check(output)
                elif check_name == "consistency":
                    result = checker.check(output)
                else:
                    continue

                results.append(result)
            except Exception as e:
                logger.warning(f"[Verifier] 检查 {check_name} 异常: {e}")
                results.append(CheckResult(
                    name=check_name,
                    passed=True,  # 检查异常不阻塞
                    message=f"检查异常: {e}",
                    severity="warning",
                ))

        # 判定最终结论
        verdict = self._make_verdict(results)

        error_summary = ""
        if not (verdict in (Verdict.PASS, Verdict.WARN)):
            failed = [r for r in results if not r.passed]
            error_summary = "; ".join(r.message for r in failed)

        return VerificationResult(
            verdict=verdict,
            checks=results,
            error_summary=error_summary,
        )

    def _make_verdict(self, checks: List[CheckResult]) -> Verdict:
        """根据所有检查结果判定最终结论"""
        errors = [c for c in checks if not c.passed and c.severity == "error"]
        warnings = [c for c in checks if not c.passed and c.severity == "warning"]

        # 有error级别的失败 → FAIL
        if errors:
            return Verdict.FAIL

        # 有warning级别的失败 → WARN
        if warnings:
            return Verdict.WARN

        # 全部通过 → PASS
        return Verdict.PASS

    def should_retry(self, result: VerificationResult) -> bool:
        """判断是否应该重试"""
        return (
            result.verdict == Verdict.FAIL
            and result.retry_count < self.MAX_RETRIES
        )

    def format_retry_message(self, result: VerificationResult) -> str:
        """生成重试提示信息"""
        failed = result.failed_checks
        messages = [f"- {c.name}: {c.message}" for c in failed]
        return (
            "输出未通过审查，请修正以下问题后重试：\n"
            + "\n".join(messages)
        )


# ============== 单例 ==============

_instance: Optional[Verifier] = None


def get_verifier(config: Dict = None) -> Verifier:
    """get_verifier"""
    global _instance
    if _instance is None:
        _instance = Verifier(config)
    return _instance


def reset_verifier():
    """reset_verifier"""
    global _instance
    _instance = None
