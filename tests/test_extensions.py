"""Tests for extensions.py — MCP server list fallback."""

from ankylosaurus.modules.extensions import _fallback_mcp_list


def test_fallback_mcp_list_not_empty():
    servers = _fallback_mcp_list()
    assert len(servers) >= 3


def test_fallback_mcp_list_has_required_fields():
    for s in _fallback_mcp_list():
        assert "name" in s
        assert "description" in s
        assert "package" in s


def test_fallback_mcp_list_packages_prefixed():
    for s in _fallback_mcp_list():
        assert s["package"].startswith("@modelcontextprotocol/server-")


def test_fallback_includes_filesystem():
    names = [s["name"] for s in _fallback_mcp_list()]
    assert "filesystem" in names
