"""后端统一错误类型。

业务模块可以抛出这些异常，再由接口层决定如何转换成 HTTP 响应。
"""


class BackendError(Exception):
    """后端业务异常基类。"""


class RecommendationError(BackendError):
    """推荐链路异常。"""


class AgentError(BackendError):
    """对话 Agent 链路异常。"""

