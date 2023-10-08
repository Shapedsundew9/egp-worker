"""Unit tests for platform info module."""
from copy import deepcopy
from json import load
from os.path import dirname, join

from egp_population.population_config import population_table_default_config
from pypgtable.pypgtable_typing import TableConfigNorm
from pypgtable.validators import table_config_validator

from egp_worker.platform_info import _get_platform_info, get_platform_info


def test_internal_get_platform_info() -> None:
    """Test that the internal platform info function returns a dict."""
    assert isinstance(_get_platform_info(), dict)


def test_get_platform_info() -> None:
    """Test that the platform info function returns a dict."""
    pi_table_config: TableConfigNorm = deepcopy(population_table_default_config())
    pi_table_config["table"] = "platform_info"
    pi_table_config["create_db"] = True
    pi_table_config["delete_table"] = True
    pi_table_config["create_table"] = True
    with open(
        join(dirname(__file__), "../egp_worker/formats/platform_info_table_format.json"),
        "r",
        encoding="utf8",
    ) as file_ptr:
        pi_table_config["schema"] = {k: table_config_validator.normalized(v) for k, v in load(file_ptr).items()}
    assert isinstance(get_platform_info(pi_table_config), dict)
