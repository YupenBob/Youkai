from __future__ import annotations

import logging
import shlex
import subprocess
import threading
from dataclasses import dataclass
from typing import List, Optional, Union

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


def _validate_command_static(
    args: List[str],
    allowed_binaries: List[str],
) -> None:
    if not args:
        raise ValueError("命令参数不能为空")
    binary = args[0]
    if binary not in allowed_binaries:
        raise PermissionError(
            f"不允许在沙箱中执行该命令: {binary}. 允许的命令: {allowed_binaries}"
        )


class LocalSandbox:
    """在本机（如 Kali 虚拟机）直接执行命令的沙箱。

    - 仅允许预设白名单内的可执行程序（如 ls, whoami, nmap）
    - 通过 subprocess 在本机执行，适合在 Kali VM 上运行、无需 Docker
    - 通过线程 + join 实现超时，超时后会 kill 子进程
    """

    def __init__(
        self,
        allowed_binaries: Optional[List[str]] = None,
        default_timeout: Optional[int] = None,
    ) -> None:
        self.allowed_binaries = allowed_binaries or ["ls", "whoami", "nmap"]
        self.default_timeout = default_timeout or settings.sandbox_default_timeout

    def _validate_command(self, args: List[str]) -> None:
        _validate_command_static(args, self.allowed_binaries)

    def run(
        self,
        args: List[str],
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """在本机执行命令。"""
        self._validate_command(args)
        cmd_str = " ".join(shlex.quote(a) for a in args)
        logger.info("Executing in local sandbox: %s", cmd_str)

        result: dict = {}
        error: dict = {}

        def _worker() -> None:
            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                result["proc"] = proc
                out, err = proc.communicate()
                result["value"] = CommandResult(
                    command=cmd_str,
                    exit_code=proc.returncode or 0,
                    stdout=out or "",
                    stderr=err or "",
                    timed_out=False,
                )
            except Exception as exc:  # noqa: BLE001
                error["exception"] = exc

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        effective_timeout = timeout or self.default_timeout
        thread.join(effective_timeout)

        if thread.is_alive():
            logger.warning(
                "Command timed out in local sandbox after %s seconds: %s",
                effective_timeout,
                cmd_str,
            )
            if "proc" in result:
                try:
                    result["proc"].kill()
                except Exception:  # noqa: BLE001
                    pass
            raise CommandTimeoutError(
                f"命令在本机执行超时（>{effective_timeout}s）: {cmd_str}"
            )

        if "exception" in error:
            raise error["exception"]  # type: ignore[misc]

        return result["value"]  # type: ignore[return-value]


class KaliSandbox:
    """在 Kali Linux Docker 容器中安全执行命令的沙箱。

    - 仅允许预设白名单内的可执行程序（如 ls, whoami, nmap）
    - 所有命令在 Docker 容器内执行（需安装并运行 Docker）
    - 通过线程 join 实现超时控制
    """

    def __init__(
        self,
        image: Optional[str] = None,
        allowed_binaries: Optional[List[str]] = None,
        default_timeout: Optional[int] = None,
    ) -> None:
        import docker
        from docker.models.containers import Container

        self._docker = docker
        self._Container = Container
        self._client = docker.from_env()
        self._container: Optional[Container] = None
        self.image = image or settings.kali_image
        self.allowed_binaries = allowed_binaries or ["ls", "whoami", "nmap"]
        self.default_timeout = default_timeout or settings.sandbox_default_timeout

    def _ensure_started(self) -> None:
        if self._container is None:
            self.start()

    def start(self) -> None:
        """启动一个 Kali 容器（如已存在则复用）。"""
        if self._container is not None:
            if self._container.status not in ("exited", "dead"):
                return
        from docker.errors import DockerException

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
        except self._docker.errors.DockerException as exc:
            logger.warning("Error while stopping container: %s", exc)
        finally:
            self._container = None

    def _validate_command(self, args: List[str]) -> None:
        _validate_command_static(args, self.allowed_binaries)

    def run(
        self,
        args: List[str],
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """在 Kali 容器内执行命令。"""
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
            logger.warning(
                "Command timed out in Kali sandbox after %s seconds: %s",
                effective_timeout,
                cmd_str,
            )
            self.stop()
            raise CommandTimeoutError(
                f"命令在沙箱中执行超时（>{effective_timeout}s）: {cmd_str}"
            )

        if "exception" in error:
            raise error["exception"]  # type: ignore[misc]

        return result["value"]  # type: ignore[return-value]


def get_sandbox() -> Union[KaliSandbox, LocalSandbox]:
    """根据配置返回沙箱实例。sandbox_mode='local' 时在本机执行，否则使用 Docker。"""
    mode = (settings.sandbox_mode or "docker").strip().lower()
    if mode == "local":
        return LocalSandbox()
    return KaliSandbox()


__all__ = [
    "CommandResult",
    "CommandTimeoutError",
    "KaliSandbox",
    "LocalSandbox",
    "get_sandbox",
]

