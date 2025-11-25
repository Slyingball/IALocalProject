"""Remote command execution utilities for the Flask API."""
from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import List, Optional

import paramiko

ALLOWED_COMMANDS = {
    "nmap",
    "ping",
    "ip",
    "df",
    "ps",
    "netstat",
    "curl",
    "ss",
    "lsof",
    "top",
}

FORBIDDEN_TOKENS = {
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    ">",
    "<",
    "sudo",
    "rm",
    "kill",
}


class CommandValidationError(ValueError):
    """Raised when the provided command does not satisfy security constraints."""


class RemoteExecutionError(RuntimeError):
    """Raised when the SSH execution fails."""


@dataclass
class SSHCredentials:
    username: str
    password: Optional[str] = None
    key_filename: Optional[str] = None
    port: int = 22


def _ensure_command_exists(binary: str) -> None:
    """Check whether the binary exists locally using subprocess.run(shell=False)."""

    lookup = subprocess.run(
        ["which", binary],
        shell=False,
        check=False,
        capture_output=True,
        text=True,
    )
    if lookup.returncode != 0:
        raise CommandValidationError(
            f"La commande '{binary}' n'est pas disponible sur l'hôte Flask"
        )


def sanitize_and_split(command: str) -> List[str]:
    """Split a command string and ensure it complies with the whitelist."""

    if not command:
        raise CommandValidationError("Aucune commande fournie")

    parts = shlex.split(command)
    if not parts:
        raise CommandValidationError("Commande vide")

    binary = parts[0]
    if binary not in ALLOWED_COMMANDS:
        raise CommandValidationError(
            f"Commande '{binary}' non autorisée. Autorisées: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    if any(token in FORBIDDEN_TOKENS for token in parts):
        raise CommandValidationError("Jeton interdit détecté dans la commande")

    _ensure_command_exists(binary)

    return parts


def build_remote_command(parts: List[str]) -> str:
    """Join and quote command parts for remote execution."""

    return " ".join(shlex.quote(part) for part in parts)


class RemoteCommandExecutor:
    """Execute sanitized commands on a remote host over SSH."""

    def __init__(
        self,
        default_username: Optional[str] = None,
        default_password: Optional[str] = None,
        default_key_path: Optional[str] = None,
        default_port: Optional[int] = None,
    ) -> None:
        self.default_username = default_username or os.environ.get("REMOTE_SSH_USERNAME")
        self.default_password = default_password or os.environ.get("REMOTE_SSH_PASSWORD")
        self.default_key_path = default_key_path or os.environ.get("REMOTE_SSH_KEY_PATH")
        port = default_port or os.environ.get("REMOTE_SSH_PORT")
        self.default_port = int(port) if port else 22

    def _credentials(self, username=None, password=None, key_filename=None, port=None) -> SSHCredentials:
        user = username or self.default_username
        if not user:
            raise RemoteExecutionError(
                "Aucun identifiant SSH fourni (username manquant). Configure REMOTE_SSH_USERNAME."
            )
        pwd = password if password is not None else self.default_password
        key = key_filename if key_filename is not None else self.default_key_path
        resolved_port = int(port) if port else self.default_port
        return SSHCredentials(username=user, password=pwd, key_filename=key, port=resolved_port)

    def execute(
        self,
        host: str,
        command_parts: List[str],
        *,
        username: Optional[str] = None,
        password: Optional[str] = None,
        key_filename: Optional[str] = None,
        port: Optional[int] = None,
    ) -> dict:
        if not host:
            raise RemoteExecutionError("Adresse IP / hôte cible manquant")

        credentials = self._credentials(username, password, key_filename, port)
        command_string = build_remote_command(command_parts)

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                username=credentials.username,
                password=credentials.password,
                key_filename=credentials.key_filename,
                port=credentials.port,
                look_for_keys=False,
                allow_agent=False,
                timeout=10,
            )
            stdin, stdout, stderr = client.exec_command(command_string, get_pty=False)
            exit_status = stdout.channel.recv_exit_status()
            return {
                "stdout": stdout.read().decode("utf-8", errors="ignore"),
                "stderr": stderr.read().decode("utf-8", errors="ignore"),
                "exit_code": exit_status,
            }
        except paramiko.AuthenticationException as exc:
            raise RemoteExecutionError("Authentification SSH échouée") from exc
        except paramiko.SSHException as exc:
            raise RemoteExecutionError(f"Erreur SSH: {exc}") from exc
        finally:
            client.close()
