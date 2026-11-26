"""报名策略（Strategy Pattern）。

RegistrationService 只依赖 RegistrationPolicy 抽象：
- 直接报名：名额充足时立即通过；
- 审核报名：先进入待审核，批准时再检查名额。

公共规则（活动是否开始、是否重复报名、活动是否下架）放在服务层，
与“报名结果如何产生”的策略责任分开；名额判断与策略结果强相关，
因此由具体策略负责。详见 docs/05_设计模式决策报告.md。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from .models import Activity, RegistrationStatus


@dataclass(frozen=True)
class RegistrationContext:
    activity: Activity
    student_id: str
    approved_count: int
    student_grade: int = 0  # CR-01：年级限定策略使用

    @property
    def remaining(self) -> int:
        return max(self.activity.capacity - self.approved_count, 0)


@dataclass(frozen=True)
class PolicyDecision:
    accepted: bool
    status: RegistrationStatus | None
    reason: str = ""

    @classmethod
    def accept(cls, status: RegistrationStatus) -> "PolicyDecision":
        return cls(True, status)

    @classmethod
    def reject(cls, reason: str) -> "PolicyDecision":
        return cls(False, None, reason)


class RegistrationPolicy(ABC):
    """报名规则抽象，新增规则只需增加实现并注册。"""

    type_name: str = ""
    display_name: str = ""
    description: str = ""

    @abstractmethod
    def decide(self, context: RegistrationContext) -> PolicyDecision:
        raise NotImplementedError


class DirectRegistrationPolicy(RegistrationPolicy):
    type_name = "direct"
    display_name = "直接报名"
    description = "名额充足时提交即报名成功，无需管理员审核。"

    def decide(self, context: RegistrationContext) -> PolicyDecision:
        if context.remaining <= 0:
            return PolicyDecision.reject("名额已满，无法报名")
        return PolicyDecision.accept(RegistrationStatus.APPROVED)


class ApprovalRegistrationPolicy(RegistrationPolicy):
    type_name = "approval"
    display_name = "管理员审核"
    description = "提交后进入待审核状态，由管理员批准或拒绝；待审核不占用名额。"

    def decide(self, context: RegistrationContext) -> PolicyDecision:
        # 待审核报名不占名额，因此提交阶段不因满员而拒绝；
        # 批准阶段由 RegistrationService.approve 再次检查名额。
        return PolicyDecision.accept(RegistrationStatus.PENDING)


# CR-01：年级限定策略
_ALLOWED_GRADES = frozenset({2, 3})


class GradeRestrictedDirectPolicy(RegistrationPolicy):
    """仅允许大二、大三学生直接报名；其他年级收到明确提示。"""

    type_name = "grade-restricted-direct"
    display_name = "年级限定直接报名"
    description = "仅面向大二、大三学生开放；名额充足时提交即通过。"

    def decide(self, context: RegistrationContext) -> PolicyDecision:
        if context.student_grade not in _ALLOWED_GRADES:
            return PolicyDecision.reject(
                "该活动仅面向大二、大三学生开放，你的年级不符合要求"
            )
        if context.remaining <= 0:
            return PolicyDecision.reject("名额已满，无法报名")
        return PolicyDecision.accept(RegistrationStatus.APPROVED)


class RegistrationPolicyFactory:
    """策略注册表，隔离“活动配置的类型字符串”与具体策略类。"""

    def __init__(self) -> None:
        self._policies: dict[str, RegistrationPolicy] = {}

    def register(self, policy: RegistrationPolicy) -> None:
        if not policy.type_name:
            raise ValueError("策略必须声明 type_name")
        self._policies[policy.type_name] = policy

    def create(self, type_name: str) -> RegistrationPolicy:
        try:
            return self._policies[type_name]
        except KeyError as exc:
            raise ValueError(f"未知的报名方式：{type_name}") from exc

    def choices(self) -> list[tuple[str, str]]:
        return [(p.type_name, p.display_name) for p in self._policies.values()]

    def display_name(self, type_name: str) -> str:
        policy = self._policies.get(type_name)
        return policy.display_name if policy else type_name

    def description(self, type_name: str) -> str:
        policy = self._policies.get(type_name)
        return policy.description if policy else ""


def build_policy_factory() -> RegistrationPolicyFactory:
    factory = RegistrationPolicyFactory()
    factory.register(DirectRegistrationPolicy())
    factory.register(ApprovalRegistrationPolicy())
    factory.register(GradeRestrictedDirectPolicy())  # CR-01
    return factory


POLICY_FACTORY = build_policy_factory()
