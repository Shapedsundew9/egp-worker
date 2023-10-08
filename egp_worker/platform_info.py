""" platform_info module."""
from logging import Logger, NullHandler, getLogger
from platform import machine, platform, processor, python_version, release, system
from pprint import pformat
from sys import exit as sys_exit
from typing import Any
from copy import deepcopy

from pypgtable.table import table
from pypgtable.pypgtable_typing import TableConfigNorm

from .platform_info_validator import platform_info_validator

_logger: Logger = getLogger(__name__)
_logger.addHandler(NullHandler())


# TODO: Implemented EGPOps
def _get_platform_info() -> dict[str, Any]:
    # TODO: Replace these with an Erasmus benchmark.
    # The metric needs to be stable on a system to 1 unit as it is used in the SHA256 signature to
    # identify the platform.
    performance: float = 1.0
    return {
        "machine": machine(),
        "processor": processor(),
        "platform": platform(),
        "python_version": python_version(),
        "system": system(),
        "release": release(),
        "EGPOps": performance,
    }


# Add the platform info to the platform info table if it is not already there & return it
def get_platform_info(table_config: TableConfigNorm) -> dict[str, Any]:
    """Introspect the system and record it in the platform table as needed."""
    platform_info: dict[str, Any] = _get_platform_info()
    platform_info: dict[str, Any] = platform_info_validator.normalized(platform_info)
    if platform_info is None or not platform_info_validator.validate(platform_info):
        _logger.error(f"Platform information validation failed:\n{platform_info_validator.error_str()}")
        sys_exit(1)
    pi_table: table = table(table_config)
    if platform_info["signature"] not in pi_table:
        _logger.info("New platform registered.")
        pi_table.insert([platform_info])
    else:
        _logger.info("Platform already registered.")
    pp_pi: dict[str, Any] = deepcopy(platform_info)
    pp_pi["signature"] = pp_pi["signature"].hex()
    _logger.info(f"Platform details:\n{pformat(pp_pi)}")
    return platform_info
