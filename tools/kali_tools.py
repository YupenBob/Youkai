"""Kali 网络渗透工具封装：本机执行 CLI，返回 (returncode, stdout, stderr)。"""

from __future__ import annotations

import shlex
import subprocess
from typing import Any


def _run(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return -1, "", f"未找到命令: {cmd[0]}，请确保已安装（Kali: apt install {cmd[0]}）"
    except subprocess.TimeoutExpired:
        return -1, "", f"执行超时（{timeout}s）"
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


def run_nmap(target: str, args: str = "-sV -Pn", timeout: int = 300) -> tuple[int, str, str]:
    """Nmap 端口/服务扫描。"""
    if not target:
        return -1, "", "目标不能为空"
    cmd = ["nmap"] + shlex.split(args or "-sV -Pn") + [target]
    return _run(cmd, timeout)


def run_nikto(url: str, timeout: int = 120) -> tuple[int, str, str]:
    """Nikto Web 服务器扫描。"""
    if not url:
        return -1, "", "URL 不能为空"
    return _run(["nikto", "-h", url], timeout)


def run_dirb(url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", timeout: int = 300) -> tuple[int, str, str]:
    """Dirb 目录/文件枚举。"""
    if not url:
        return -1, "", "URL 不能为空"
    cmd = ["dirb", url, wordlist, "-w"]
    return _run(cmd, timeout)


def run_gobuster_dir(url: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", timeout: int = 300) -> tuple[int, str, str]:
    """Gobuster 目录枚举。"""
    if not url:
        return -1, "", "URL 不能为空"
    cmd = ["gobuster", "dir", "-u", url, "-w", wordlist, "-q"]
    return _run(cmd, timeout)


def run_gobuster_dns(domain: str, wordlist: str = "/usr/share/wordlists/dirb/common.txt", timeout: int = 120) -> tuple[int, str, str]:
    """Gobuster 子域名枚举。"""
    if not domain:
        return -1, "", "域名不能为空"
    cmd = ["gobuster", "dns", "-d", domain, "-w", wordlist, "-q"]
    return _run(cmd, timeout)


def run_hydra(target: str, service: str, user: str, passlist: str, timeout: int = 120) -> tuple[int, str, str]:
    """Hydra 暴力破解（如 ssh, ftp, http-form）。"""
    if not target or not service:
        return -1, "", "目标与服务不能为空"
    cmd = ["hydra", "-l", user, "-P", passlist, target, service, "-t", "4", "-V"]
    return _run(cmd, timeout)


def run_whatweb(url: str, timeout: int = 60) -> tuple[int, str, str]:
    """Whatweb Web 技术指纹识别。"""
    if not url:
        return -1, "", "URL 不能为空"
    return _run(["whatweb", url, "--color=never"], timeout)


def run_searchsploit(keyword: str, timeout: int = 30) -> tuple[int, str, str]:
    """Searchsploit 漏洞库搜索。"""
    if not keyword:
        return -1, "", "关键词不能为空"
    return _run(["searchsploit", "--color", keyword], timeout)


def run_whois(domain: str, timeout: int = 15) -> tuple[int, str, str]:
    """Whois 域名信息。"""
    if not domain:
        return -1, "", "域名不能为空"
    return _run(["whois", domain], timeout)


def run_ping(host: str, count: int = 4, timeout: int = 15) -> tuple[int, str, str]:
    """Ping 主机。"""
    if not host:
        return -1, "", "主机不能为空"
    return _run(["ping", "-c", str(count), host], timeout)


def run_curl(url: str, method: str = "GET", timeout: int = 30) -> tuple[int, str, str]:
    """Curl 请求 URL（可看响应头/体）。"""
    if not url:
        return -1, "", "URL 不能为空"
    cmd = ["curl", "-s", "-i", "-X", method.upper(), "-m", "20", url]
    return _run(cmd, timeout)


def run_tool(name: str, params: dict[str, Any]) -> tuple[int, str, str]:
    """统一入口：根据 name 调用对应工具。"""
    name = (name or "").strip().lower()
    if name == "nmap":
        return run_nmap(params.get("target", ""), params.get("args", "-sV -Pn"))
    if name == "nikto":
        return run_nikto(params.get("url", ""))
    if name == "dirb":
        return run_dirb(params.get("url", ""), params.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
    if name == "gobuster_dir":
        return run_gobuster_dir(params.get("url", ""), params.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
    if name == "gobuster_dns":
        return run_gobuster_dns(params.get("domain", ""), params.get("wordlist", "/usr/share/wordlists/dirb/common.txt"))
    if name == "hydra":
        return run_hydra(
            params.get("target", ""),
            params.get("service", "ssh"),
            params.get("user", "root"),
            params.get("passlist", "/usr/share/wordlists/rockyou.txt"),
        )
    if name == "whatweb":
        return run_whatweb(params.get("url", ""))
    if name == "searchsploit":
        return run_searchsploit(params.get("keyword", ""))
    if name == "whois":
        return run_whois(params.get("domain", ""))
    if name == "ping":
        return run_ping(params.get("host", ""), params.get("count", 4))
    if name == "curl":
        return run_curl(params.get("url", ""), params.get("method", "GET"))
    return -1, "", f"未知工具: {name}"
