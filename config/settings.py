from __future__ import annotations

from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """全局配置：API Key 与沙箱/Docker 设置。

    通过环境变量覆盖，前缀为 `KALI_AGENT_`，例如：
    - KALI_AGENT_OPENAI_API_KEY
    - KALI_AGENT_GOOGLE_GEMINI_API_KEY
    - KALI_AGENT_DEEPSEEK_API_KEY
    - KALI_AGENT_SANDBOX_MODE（默认 local）
    """

    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API Key（可选）"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API Key（可选）"
    )
    google_gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API Key（可选）"
    )
    deepseek_api_key: Optional[str] = Field(
        default=None, description="DeepSeek API Key（可选，OpenAI 兼容接口）"
    )

    kali_image: str = Field(
        default="kalilinux/kali-rolling",
        description="Kali Linux Docker 镜像名",
    )
    docker_network_mode: Optional[str] = Field(
        default=None,
        description="Docker network_mode，默认使用 Docker 默认网络",
    )
    docker_auto_remove: bool = Field(
        default=True,
        description="容器退出后是否自动删除",
    )
    sandbox_default_timeout: int = Field(
        default=120,
        description="沙箱中命令默认超时时间（秒）",
    )
    sandbox_mode: str = Field(
        default="local",
        description="沙箱模式：'local' 在本机执行（默认），'docker' 在容器中执行",
    )

    class Config:
        env_prefix = "KALI_AGENT_"
        env_file = ".env"
        extra = "ignore"


settings = Settings()
