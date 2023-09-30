"""Test cases for the worker process script."""
import pytest
from os import remove
from os.path import join, dirname, exists
from egp_worker.egp_worker import launch_workers, parse_cmdline_args


def test_init_parameterless_no_config() -> None:
    """Test that the worker process errors with no config file."""
    if exists("config.json"):
        remove("config.json")
    with pytest.raises(SystemExit):
        launch_workers(parse_cmdline_args([]))


def test_init_invalid_json_config() -> None:
    """Test that the worker process errors with an invalid JSON config."""
    with pytest.raises(SystemExit):
        launch_workers(parse_cmdline_args(["-c", join(dirname(__file__), "data", "invalid_json_config.json")]))


def test_init_invalid_parse_config() -> None:
    """Test that the worker process errors with an unparsable invalid config."""
    with pytest.raises(SystemExit):
        launch_workers(parse_cmdline_args(["-c", join(dirname(__file__), "data", "invalid_parse_config.json")]))


def test_init_invalid_config() -> None:
    """Test that the worker process errors with an invalid config."""
    with pytest.raises(SystemExit):
        launch_workers(parse_cmdline_args(["-c", join(dirname(__file__), "data", "invalid_config.json")]))


def test_dump_default_config() -> None:
    """Test that the worker process dumps a default config."""
    with pytest.raises(SystemExit) as system_exit:
        launch_workers(parse_cmdline_args(["-d"]))
    assert system_exit.value.code == 0
    assert exists("config.json")
    if exists("config.json"):
        remove("config.json")
