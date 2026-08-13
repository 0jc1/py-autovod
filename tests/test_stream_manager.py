import configparser
from unittest.mock import MagicMock, patch

import pytest

from stream_manager import StreamManager


def make_manager():
    manager = object.__new__(StreamManager)
    manager.monitors = {}
    manager.running = False
    manager.retry_delay = 120
    return manager


def test_get_streamers_list_returns_empty_without_config():
    manager = make_manager()

    with patch("stream_manager.config", None):
        assert manager.get_streamers_list() == []


def test_get_streamers_list_returns_empty_without_streamers_section():
    manager = make_manager()

    with patch("stream_manager.config", configparser.ConfigParser()):
        assert manager.get_streamers_list() == []


@pytest.mark.parametrize("configured_value", ["", "   ", ",,,"])
def test_get_streamers_list_returns_empty_for_blank_values(configured_value):
    manager = make_manager()
    stream_config = configparser.ConfigParser()
    stream_config["streamers"] = {"streamers": configured_value}

    with patch("stream_manager.config", stream_config):
        assert manager.get_streamers_list() == []


@pytest.mark.parametrize(
    ("configured_value", "expected"),
    [
        ("alice", {"alice"}),
        (" alice, bob ", {"alice", "bob"}),
        (",alice,bob,", {"alice", "bob"}),
        ("alice,,bob", {"alice", "bob"}),
        ("alice,bob,alice", {"alice", "bob"}),
    ],
)
def test_get_streamers_list_parses_configured_names(configured_value, expected):
    manager = make_manager()
    stream_config = configparser.ConfigParser()
    stream_config["streamers"] = {"streamers": configured_value}

    with patch("stream_manager.config", stream_config):
        assert set(manager.get_streamers_list()) == expected


def test_start_creates_and_starts_monitor_for_explicit_streamer():
    manager = make_manager()
    monitor = MagicMock()

    with patch("stream_manager.StreamMonitor", return_value=monitor) as monitor_class:
        manager.start("alice")

    monitor_class.assert_called_once_with("alice", 120)
    assert monitor.daemon is True
    monitor.start.assert_called_once_with()
    assert manager.monitors == {"alice": monitor}
    assert manager.running is True


def test_start_is_noop_when_manager_is_already_running():
    manager = make_manager()
    manager.running = True

    with patch("stream_manager.StreamMonitor") as monitor_class:
        manager.start("alice")

    monitor_class.assert_not_called()


def test_stop_stops_and_joins_each_monitor():
    manager = make_manager()
    first_monitor = MagicMock()
    second_monitor = MagicMock()
    manager.monitors = {"alice": first_monitor, "bob": second_monitor}
    manager.running = True

    manager.stop()

    for monitor in (first_monitor, second_monitor):
        monitor.stop.assert_called_once_with()
        monitor.join.assert_called_once_with(timeout=0.02)
    assert manager.monitors == {}
    assert manager.running is False


def test_list_monitored_streamers_returns_monitor_names():
    manager = make_manager()
    manager.monitors = {"alice": MagicMock(), "bob": MagicMock()}

    assert manager.list_monitored_streamers() == ["alice", "bob"]


def test_signal_handler_stops_manager_before_exiting():
    manager = make_manager()

    with patch.object(manager, "stop") as stop, pytest.raises(SystemExit) as raised:
        manager._signal_handler(2, None)

    stop.assert_called_once_with()
    assert raised.value.code == 0
