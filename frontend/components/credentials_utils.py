"""
Shared utilities for account and credential management.

Provides:
- CredentialEntry: normalized credential representation
- normalize_credentials: handles all 3 API return formats
- validate_account_name: input validation with clear error messages
- fetch_accounts_data: unified data fetching with master_account ordering
- safe_* wrappers: API operations with (success, message) return
"""

import re
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Credential normalization
# ---------------------------------------------------------------------------

@dataclass
class CredentialEntry:
    """Normalized representation of a single credential."""
    connector_name: str       # Exchange/connector type (e.g. "binance_perpetual")
    display_name: str         # What the user sees in the UI
    delete_identifier: str    # What to pass to delete_credential()
    raw_data: Any             # Original data (for debug / st.json)


def normalize_credentials(raw_credentials: Any) -> list[CredentialEntry]:
    """
    Normalize all known API return formats into a uniform list.

    Handles:
      - list[str]:  ["binance_perpetual.binance_perpetual_api_key", ...]
      - list[dict]: [{"connector": "binance_perpetual", ...}, ...]
      - dict:       {"binance_perpetual": {"api_key": "..."}, ...}
      - None / empty / unexpected: returns []
    """
    if not raw_credentials:
        return []

    entries: list[CredentialEntry] = []

    if isinstance(raw_credentials, list):
        for item in raw_credentials:
            if isinstance(item, str):
                # "binance_perpetual.binance_perpetual_api_key"
                #  ^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^^^
                #  connector_name    full string = delete_identifier
                parts = item.split(".", 1)
                connector = parts[0] if len(parts) > 1 else item
                entries.append(CredentialEntry(
                    connector_name=connector,
                    display_name=item,
                    delete_identifier=item,
                    raw_data=item,
                ))
            elif isinstance(item, dict):
                connector = (
                    item.get("connector")
                    or item.get("connector_name")
                    or "unknown"
                )
                # Build a unique display from connector + other identifying keys
                other_keys = {
                    k: v for k, v in item.items()
                    if k not in ("connector", "connector_name") and v
                }
                if other_keys:
                    suffix = ", ".join(f"{k}={v}" for k, v in sorted(other_keys.items()))
                    display = f"{connector} ({suffix})"
                else:
                    display = connector
                entries.append(CredentialEntry(
                    connector_name=connector,
                    display_name=display,
                    delete_identifier=connector,
                    raw_data=item,
                ))
            # skip unexpected item types

    elif isinstance(raw_credentials, dict):
        for key, value in raw_credentials.items():
            entries.append(CredentialEntry(
                connector_name=key,
                display_name=key,
                delete_identifier=key,
                raw_data=value,
            ))

    return entries


def get_connector_names(raw_credentials: Any) -> list[str]:
    """Return deduplicated connector names preserving order."""
    seen: set[str] = set()
    result: list[str] = []
    for entry in normalize_credentials(raw_credentials):
        if entry.connector_name not in seen:
            seen.add(entry.connector_name)
            result.append(entry.connector_name)
    return result


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

ACCOUNT_NAME_MAX_LENGTH = 50
ACCOUNT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_]*$")


def validate_account_name(name: str, existing_accounts: list[str]) -> tuple[bool, str]:
    """
    Validate an account name before creation.

    Returns (is_valid, error_message).
    Checks in order: empty → length → format → all-underscores → duplicate.
    """
    cleaned = name.strip()

    if not cleaned:
        return False, "账号名称不能为空。"

    # Replace spaces with underscores (convenience for the user)
    cleaned = cleaned.replace(" ", "_")

    if len(cleaned) > ACCOUNT_NAME_MAX_LENGTH:
        return False, f"账号名称不能超过 {ACCOUNT_NAME_MAX_LENGTH} 个字符。"

    if not ACCOUNT_NAME_PATTERN.match(cleaned):
        return False, "账号名称只能包含字母、数字和下划线，且必须以字母或数字开头。"

    if all(c == "_" for c in cleaned):
        return False, "账号名称不能全部是下划线。"

    if cleaned in existing_accounts:
        return False, f"账号 '{cleaned}' 已存在，请使用其他名称。"

    return True, cleaned  # Return cleaned name on success


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_accounts_data(client) -> tuple[list[str], dict[str, list[CredentialEntry]]]:
    """
    Fetch all accounts and their credentials, normalized.

    Returns (sorted_accounts, credentials_dict).
    master_account is always first in the list.
    """
    try:
        accounts = client.accounts.list_accounts()
    except Exception:
        return [], {}

    if not accounts:
        return [], {}

    # Sort: master_account first
    if "master_account" in accounts:
        accounts.remove("master_account")
        accounts.insert(0, "master_account")

    credentials: dict[str, list[CredentialEntry]] = {}
    for account in accounts:
        try:
            raw = client.accounts.list_account_credentials(account)
            credentials[account] = normalize_credentials(raw)
        except Exception:
            credentials[account] = []

    return accounts, credentials


# ---------------------------------------------------------------------------
# Safe API wrappers  —  all return (success: bool, message: str)
# ---------------------------------------------------------------------------

def _extract_message(response: Any, fallback: str) -> str:
    """Pull a human-readable message from various API response shapes."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("message") or response.get("detail") or response.get("status") or fallback
    return fallback


def safe_create_account(client, name: str, existing_accounts: list[str]) -> tuple[bool, str]:
    """Validate and create an account."""
    is_valid, result = validate_account_name(name, existing_accounts)
    if not is_valid:
        return False, result  # result is the error message

    cleaned_name = result  # On success, validate returns the cleaned name
    try:
        response = client.accounts.add_account(cleaned_name)
        msg = _extract_message(response, f"账号 '{cleaned_name}' 创建成功。")
        return True, msg
    except Exception as e:
        return False, f"创建账号失败: {e}"


def safe_delete_account(client, name: str) -> tuple[bool, str]:
    """Delete an account."""
    if not name or name in ("—", "No accounts available"):
        return False, "请先选择一个要删除的账号。"
    try:
        response = client.accounts.delete_account(name)
        msg = _extract_message(response, f"账号 '{name}' 已删除。")
        return True, msg
    except Exception as e:
        return False, f"删除账号失败: {e}"


def safe_delete_credential(client, account: str, credential_id: str) -> tuple[bool, str]:
    """Delete a specific credential from an account."""
    if not account or account in ("—", "No accounts available"):
        return False, "请先选择一个账号。"
    if not credential_id or credential_id in ("—", "No credentials available"):
        return False, "请先选择一个凭证。"
    try:
        response = client.accounts.delete_credential(account, credential_id)
        msg = _extract_message(response, f"凭证 '{credential_id}' 已从 '{account}' 中删除。")
        return True, msg
    except Exception as e:
        return False, f"删除凭证失败: {e}"


def safe_add_credential(client, account: str, connector: str, config: dict) -> tuple[bool, str]:
    """Add a credential to an account."""
    if not account or account in ("—", "No accounts available"):
        return False, "请先选择一个账号。"

    # Check for empty required fields
    empty_fields = [k for k, v in config.items() if not v or not str(v).strip()]
    if empty_fields:
        return False, f"以下字段不能为空: {', '.join(empty_fields)}"

    try:
        response = client.accounts.add_credential(account, connector, config)
        msg = _extract_message(response, f"已成功将 {connector} 凭证添加到 {account}。")
        return True, msg
    except Exception as e:
        return False, f"添加凭证失败: {e}"
