"""Test cases for the worker process script."""
from os import remove
from os.path import dirname, exists, join

import pytest
from pypgtable.database import db_delete

from egp_worker.config_validator import generate_config
from egp_worker.egp_typing import WorkerConfigNorm
from egp_worker.egp_worker import launch_worker, parse_cmdline_args


def delete_dbs() -> None:
    """Delete the databases."""
    config: WorkerConfigNorm = generate_config()
    for db in config["databases"].values():
        db_delete(db["dbname"], db)


def test_init_parameterless_no_config() -> None:
    """Test that the worker process errors with no config file."""
    if exists("config.json"):
        remove("config.json")
    with pytest.raises(SystemExit):
        launch_worker(parse_cmdline_args([]))


def test_init_invalid_json_config() -> None:
    """Test that the worker process errors with an invalid JSON config."""
    with pytest.raises(SystemExit):
        launch_worker(parse_cmdline_args(["-c", join(dirname(__file__), "data", "invalid_json_config.json")]))


def test_init_invalid_parse_config() -> None:
    """Test that the worker process errors with an unparsable invalid config."""
    with pytest.raises(SystemExit):
        launch_worker(parse_cmdline_args(["-c", join(dirname(__file__), "data", "invalid_parse_config.json")]))


def test_init_invalid_config() -> None:
    """Test that the worker process errors with an invalid config."""
    with pytest.raises(SystemExit):
        launch_worker(parse_cmdline_args(["-c", join(dirname(__file__), "data", "invalid_config.json")]))


def test_dump_default_config() -> None:
    """Test that the worker process dumps a default config."""
    with pytest.raises(SystemExit) as system_exit:
        launch_worker(parse_cmdline_args(["-d"]))
    assert system_exit.value.code == 0
    assert exists("config.json")
    if exists("config.json"):
        remove("config.json")


def test_print_gallery() -> None:
    """Test that the worker process prints the gallery."""
    with pytest.raises(SystemExit) as system_exit:
        launch_worker(parse_cmdline_args(["-g"]))
    assert system_exit.value.code == 0


def test_meg() -> None:
    """Test that the worker process prints the gallery."""
    with pytest.raises(SystemExit) as system_exit:
        launch_worker(parse_cmdline_args(["-g", "-d"]))
    assert system_exit.value.code == 2


def test_use_default_config() -> None:
    """Test that the worker process prints the gallery."""
    delete_dbs()
    launch_worker(parse_cmdline_args(["-D", "-s", "1"]))
