"""业务异常定义。

业务规则失败统一抛出 BusinessError，由路由转换为中文提示；
程序性错误不在此处捕获，以便日志中暴露真实缺陷。
"""


class BusinessError(Exception):
    """违反业务规则时抛出。"""


class ValidationError(BusinessError):
    """输入校验失败时抛出。"""
