from __future__ import annotations

import logging
import shlex
import threading
from dataclasses import dataclass
from typing import List, Optional

import docker
from docker.errors import DockerException
from docker.models.containers import Container

from config.settings import settings

logger = logging.getLogger(__name__)


class CommandTimeoutError(TimeoutError):
    """命令在沙箱中执行超时。"""


@dataclass
class CommandResult:
    """封装一次命令执行结果。"""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class KaliSandbox:
    """在 Kali Linux Docker 容器中安全执行命令的简单沙箱。

    - 仅允许预设白名单内的可执行程序（如 `ls`, `whoami`, `nmap`）
    - 所有命令都在独立的 Docker 容器内执行
    - 通过线程 join 的方式实现基础超时控制
    """

    def __init__(
        self,
        image: Optional[str] = None,
        allowed_binaries: Optional[List[str]] = None,
        default_timeout: Optional[int] = None,
    ) -> None:
        self._client = docker.from_env()
        self._container: Optional[Container] = None
        self.image = image or settings.kali_image
        self.allowed_binaries = allowed_binaries or ["ls", "whoami", "nmap"]
        self.default_timeout = default_timeout or settings.sandbox_default_timeout

    # --- 容器生命周期管理 ---

    def start(self) -> None:
        """启动一个 Kali 容器（如已存在则复用）。"""
        if self._container is not None:
            if self._container.status not in ("exited", "dead"):
                return

        try:
            logger.info("Starting Kali sandbox container from image %s", self.image)
            self._container = self._client.containers.run(
                self.image,
                command="/bin/bash",
                tty=True,
                stdin_open=True,
                detach=True,
                auto_remove=settings.docker_auto_remove,
                network_mode=settings.docker_network_mode,
            )
        except DockerException as exc:
            logger.exception("Failed to start Kali container: %s", exc)
            raise

    def stop(self) -> None:
        """停止当前容器（如果存在）。"""
        if self._container is None:
            return
        try:
            logger.info("Stopping Kali sandbox container %s", self._container.id)
            self._container.stop(timeout=5)
        except DockerException as exc:
            logger.warning("Error while stopping container: %s", exc)
        finally:
            self._container = None

    # --- 命令执行 ---

    def _ensure_started(self) -> None:
        if self._container is None:
            self.start()

    def _validate_command(self, args: List[str]) -> None:
        if not args:
            raise ValueError("命令参数不能为空")
        binary = args[0]
        if binary not in self.allowed_binaries:
            raise PermissionError(
                f"不允许在沙箱中执行该命令: {binary}. 允许的命令: {self.allowed_binaries}"
            )

    def run(
        self,
        args: List[str],
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """在 Kali 容器内执行命令。

        参数:
            args: 例如 ["ls", "-la", "/"]
            timeout: 超时时间（秒），默认使用 settings.sandbox_default_timeout
        """
        self._ensure_started()
        self._validate_command(args)

        if self._container is None:
            raise RuntimeError("Kali 容器尚未启动")

        cmd_str = " ".join(shlex.quote(a) for a in args)
        logger.info("Executing in Kali sandbox: %s", cmd_str)

        result: dict = {}
        error: dict = {}

        def _worker() -> None:
            try:
                # demux=True 时返回 (stdout, stderr)
                exec_result = self._container.exec_run(cmd_str, demux=True)
                stdout_bytes, stderr_bytes = exec_result.output or (b"", b"")
                result["value"] = CommandResult(
                    command=cmd_str,
                    exit_code=exec_result.exit_code,
                    stdout=(stdout_bytes or b"").decode(errors="ignore"),
                    stderr=(stderr_bytes or b"").decode(errors="ignore"),
                    timed_out=False,
                )
            except Exception as exc:  # noqa: BLE001
                error["exception"] = exc

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        effective_timeout = timeout or self.default_timeout
        thread.join(effective_timeout)

        if thread.is_alive():
            # 线程仍未结束，视为超时
            logger.warning(
                "Command timed out in Kali sandbox after %s seconds: %s",
                effective_timeout,
                cmd_str,
            )
            # 可以选择强制停止容器，避免僵尸进程
            self.stop()
            raise CommandTimeoutError(
                f"命令在沙箱中执行超时（>{effective_timeout}s）: {cmd_str}"
            )

        if "exception" in error:
            raise error["exception"]  # type: ignore[misc]

        return result["value"]  # type: ignore[return-value]


__all__ = [
    "KaliSandbox",
    "CommandResult",
    "CommandTimeoutError",
]

