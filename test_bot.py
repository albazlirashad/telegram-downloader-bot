import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime

# Import functions from bot.py
from bot import (
    init_db,
    save_download,
    get_ydl_extract_opts,
    get_ydl_download_opts,
)


class TestInitDB:
    """Tests for the init_db function."""

    @patch('bot.sqlite3.connect')
    def test_init_db_creates_table(self, mock_connect):
        """Test that init_db creates the downloads table."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        init_db()

        mock_connect.assert_called_once()
        mock_conn.cursor.assert_called_once()
        mock_cursor.execute.assert_called_once()
        assert "CREATE TABLE IF NOT EXISTS downloads" in mock_cursor.execute.call_args[0][0]
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()


class TestSaveDownload:
    """Tests for the save_download function."""

    @patch('bot.sqlite3.connect')
    @patch('bot.datetime')
    def test_save_download_inserts_record(self, mock_datetime, mock_connect):
        """Test that save_download inserts a record into the database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_datetime.now.return_value.strftime.return_value = "2024-01-01 12:00:00"

        save_download(123, "testuser", "https://example.com/video")

        mock_connect.assert_called_once()
        mock_cursor.execute.assert_called_once()
        args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO downloads VALUES" in args[0]
        assert args[1] == (123, "testuser", "https://example.com/video", "2024-01-01 12:00:00")
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('bot.sqlite3.connect')
    @patch('bot.logging.error')
    def test_save_download_handles_exception(self, mock_log_error, mock_connect):
        """Test that save_download logs errors properly."""
        mock_connect.side_effect = Exception("Database error")

        save_download(123, "testuser", "https://example.com/video")

        mock_log_error.assert_called_once()
        assert "DB Error" in mock_log_error.call_args[0][0]


class TestGetYdlExtractOpts:
    """Tests for the get_ydl_extract_opts function."""

    @patch('bot.os.path.exists')
    def test_get_ydl_extract_opts_without_cookies(self, mock_exists):
        """Test extract options without cookies file."""
        mock_exists.return_value = False

        opts = get_ydl_extract_opts()

        assert opts["quiet"] is True
        assert opts["no_warnings"] is True
        assert opts["noplaylist"] is True
        assert "http_headers" in opts
        assert "User-Agent" in opts["http_headers"]
        assert "cookiefile" not in opts

    @patch('bot.os.path.exists')
    def test_get_ydl_extract_opts_with_cookies(self, mock_exists):
        """Test extract options with cookies file."""
        mock_exists.return_value = True

        opts = get_ydl_extract_opts()

        assert opts["quiet"] is True
        assert "cookiefile" in opts
        assert opts["cookiefile"].endswith("cookies.txt")


class TestGetYdlDownloadOpts:
    """Tests for the get_ydl_download_opts function."""

    @patch('bot.os.path.exists')
    def test_get_ydl_download_opts_without_cookies(self, mock_exists):
        """Test download options without cookies file."""
        mock_exists.return_value = False

        opts = get_ydl_download_opts("136", "/path/to/video.mp4")

        assert opts["quiet"] is True
        assert opts["no_warnings"] is True
        assert opts["noplaylist"] is True
        assert opts["format"] == "136+bestaudio/best"
        assert opts["merge_output_format"] == "mp4"
        assert opts["outtmpl"] == "/path/to/video.mp4"
        assert "http_headers" in opts
        assert "cookiefile" not in opts

    @patch('bot.os.path.exists')
    def test_get_ydl_download_opts_with_cookies(self, mock_exists):
        """Test download options with cookies file."""
        mock_exists.return_value = True

        opts = get_ydl_download_opts("137", "/path/to/video.mp4")

        assert opts["format"] == "137+bestaudio/best"
        assert "cookiefile" in opts
        assert opts["cookiefile"].endswith("cookies.txt")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
