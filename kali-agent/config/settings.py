from __future__ import annotations

from typing import Optional

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    """全局配置：API Key 与 Docker/Kali 设置。

    通过环境变量进行覆盖，前缀为 `KALI_AGENT_`，例如：
    - KALI_AGENT_OPENAI_API_KEY
    - KALI_AGENT_KALI_IMAGE
    """

    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API Key（可选）"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API Key（可选）"
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
        description="KaliSandbox 中命令默认超时时间（秒）",
    )
    sandbox_mode: str = Field(
        default="docker",
        description="沙箱模式：'docker' 在容器中执行，'local' 在本机（如 Kali 虚拟机）直接执行",
    )

    class Config:
        env_prefix = "KALI_AGENT_"
        env_file = ".env"
        extra = "ignore"


settings = Settings()

