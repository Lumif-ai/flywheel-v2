"""Tests for http_context.py — HTTP-backed context operations."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from flywheel_cli.http_context import (
    _format_as_v1_text,
    batch_context,
    log_event,
    parse_context_file,
    read_context,
)


# ---------------------------------------------------------------------------
# _format_as_v1_text
# ---------------------------------------------------------------------------


class TestFormatAsV1Text:
    """Verify v1-compatible markdown output."""

    def test_single_entry(self):
        entries = [
            {
                "date": "2026-03-01",
                "source": "my-skill",
                "detail": "test detail",
                "confidence": "high",
                "evidence_count": 3,
                "content": "- Line one\n- Line two",
            }
        ]
        result = _format_as_v1_text(entries)
        assert "[2026-03-01 | source: my-skill | test detail]" in result
        assert "confidence: high | evidence: 3" in result
        assert "- Line one" in result
        assert "- Line two" in result

    def test_empty_list(self):
        assert _format_as_v1_text([]) == ""

    def test_no_detail(self):
        entries = [
            {
                "date": "2026-01-15",
                "source": "crawler",
                "detail": "",
                "confidence": "medium",
                "evidence_count": 1,
                "content": "- Data point",
            }
        ]
        result = _format_as_v1_text(entries)
        assert "[2026-01-15 | source: crawler]" in result
        assert "| test" not in result

    def test_iso_datetime_truncated_to_date(self):
        entries = [
            {
                "date": "2026-03-01T14:30:00Z",
                "source": "api",
                "detail": "",
                "confidence": "low",
                "evidence_count": 1,
                "content": "- item",
            }
        ]
        result = _format_as_v1_text(entries)
        assert "[2026-03-01 | source: api]" in result

    def test_multiple_entries_separated_by_blank_line(self):
        entries = [
            {
                "date": "2026-01-01",
                "source": "a",
                "detail": "",
                "confidence": "low",
                "evidence_count": 1,
                "content": "- x",
            },
            {
                "date": "2026-01-02",
                "source": "b",
                "detail": "",
                "confidence": "low",
                "evidence_count": 1,
                "content": "- y",
            },
        ]
        result = _format_as_v1_text(entries)
        # Two blocks separated by \n\n
        assert "\n\n" in result
        assert result.count("[") == 2


# ---------------------------------------------------------------------------
# batch_context
# ---------------------------------------------------------------------------


class TestBatchContext:
    """Verify batch accumulation and sending."""

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_accumulates_and_sends(self, _mock_token, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        with batch_context("test-skill") as batch:
            batch.append_entry("companies.md", {"content": "- Acme"})
            batch.append_entry("contacts.md", {"content": "- Jane"})

        # Should have made exactly one POST
        assert mock_client.post.call_count == 1
        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(body["entries"]) == 2

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_skips_post_on_empty(self, _mock_token, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        with batch_context("test-skill") as batch:
            pass  # No entries added

        mock_client.post.assert_not_called()

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_no_send_on_exception(self, _mock_token, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        with pytest.raises(ValueError, match="boom"):
            with batch_context("test-skill") as batch:
                batch.append_entry("f.md", {"content": "data"})
                raise ValueError("boom")

        mock_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# read_context
# ---------------------------------------------------------------------------


class TestReadContext:
    """Verify read_context makes correct HTTP calls."""

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_calls_correct_url_with_auth(self, _mock_token, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "items": [
                {
                    "date": "2026-03-01",
                    "source": "s",
                    "detail": "",
                    "confidence": "high",
                    "evidence_count": 1,
                    "content": "- x",
                }
            ],
            "has_more": False,
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        result = read_context("companies.md")

        # Check URL contains the file name
        call_args = mock_client.get.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        assert "/context/files/companies.md/entries" in url

        # Check auth header
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert headers.get("Authorization") == "Bearer tok123"

        # Result should be v1 formatted text
        assert "[2026-03-01 | source: s]" in result

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_connection_error_message(self, _mock_token, mock_client_fn):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("refused")
        mock_client_fn.return_value = mock_client

        with pytest.raises(RuntimeError, match="Cannot connect to Flywheel API"):
            read_context("test.md")


# ---------------------------------------------------------------------------
# log_event
# ---------------------------------------------------------------------------


class TestLogEvent:
    """Verify log_event is fire-and-forget."""

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_does_not_raise_on_connect_error(self, _mock_token, mock_client_fn):
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("refused")
        mock_client_fn.return_value = mock_client

        # Should NOT raise
        log_event("test_event", {"key": "value"})

    @patch("flywheel_cli.http_context._get_client")
    @patch("flywheel_cli.http_context.get_token", return_value="tok123")
    def test_does_not_raise_on_http_error(self, _mock_token, mock_client_fn):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "server error",
            request=MagicMock(),
            response=mock_resp,
        )
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        # Should NOT raise
        log_event("test_event")


# ---------------------------------------------------------------------------
# parse_context_file
# ---------------------------------------------------------------------------


class TestParseContextFile:
    """Verify local markdown parsing."""

    def test_parses_v1_format(self):
        text = (
            "[2026-03-01 | source: crawler | initial scan] confidence: high | evidence: 3\n"
            "- Line one\n"
            "- Line two\n"
        )
        result = parse_context_file(text)
        assert len(result) == 1
        assert result[0]["date"] == "2026-03-01"
        assert result[0]["source"] == "crawler"
        assert result[0]["detail"] == "initial scan"
        assert result[0]["confidence"] == "high"
        assert result[0]["evidence_count"] == 3
        assert "- Line one" in result[0]["content"]

    def test_empty_input(self):
        assert parse_context_file("") == []
        assert parse_context_file("   ") == []

    def test_no_entries(self):
        assert parse_context_file("Just some text without entries") == []

    def test_multiple_entries(self):
        text = (
            "[2026-01-01 | source: a] confidence: low | evidence: 1\n"
            "- First\n"
            "\n"
            "[2026-01-02 | source: b] confidence: high | evidence: 5\n"
            "- Second\n"
        )
        result = parse_context_file(text)
        assert len(result) == 2
        assert result[0]["source"] == "a"
        assert result[1]["source"] == "b"
