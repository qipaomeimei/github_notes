"""CR-02：模拟邮件发送器。

教师材料要求不接入真实邮件服务器，由 MockEmailSender 模拟发送，
记录收件人、主题、内容、状态与时间到 email_outbox 表。
"""
from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)


class MockEmailSender:
    """模拟邮件发送：默认成功，可通过 fail_rate 或 injected_exception 触发故障。"""

    def __init__(self, *, fail_rate: float = 0.0, injected_exception: Exception | None = None) -> None:
        self.fail_rate = fail_rate
        self.injected_exception = injected_exception

    def send(self, *, to_email: str, subject: str, body: str) -> None:
        if self.injected_exception is not None:
            raise self.injected_exception
        if self.fail_rate > 0 and random.random() < self.fail_rate:
            raise RuntimeError(f"模拟邮件发送失败：无法连接 SMTP 服务器 -> {to_email}")
        logger.info("[MockEmailSender] 已投递到 %s 主题=%s", to_email, subject)
