"""Load the confifuration and validate it."""
from typing import Any
from os.path import dirname, join, exists
from json import load, dump
from json.decoder import JSONDecodeError
from copy import deepcopy
from sys import exit as sys_exit, stderr
from cerberus.validator import DocumentError
from egp_utils.base_validator import base_validator
from egp_population.population_validator import POPULATION_ENTRY_SCHEMA
from pypgtable.validators import PYPGTABLE_DB_CONFIG_SCHEMA
from .egp_typing import WorkerConfigNorm

# Load the config file validator
with open(join(dirname(__file__), "formats/config_format.json"), "r", encoding="utf8") as file_ptr:
    CONFIG_SCHEMA: dict[str, Any] = load(file_ptr)
CONFIG_SCHEMA["populations"]["schema"]["configs"]["schema"]["schema"] = deepcopy(POPULATION_ENTRY_SCHEMA)
CONFIG_SCHEMA["databases"]["valuesrules"]["schema"] = deepcopy(PYPGTABLE_DB_CONFIG_SCHEMA)
config_validator: base_validator = base_validator(CONFIG_SCHEMA)


# Dump the default configuration
def dump_config() -> None:
    """Save the default configuration to config.json."""
    with open("config.json", "w", encoding="utf8") as fileptr:
        dump(generate_config(), fileptr, indent=4, sort_keys=True)
    print("Default configuration written to ./config.json")


# Generate the default configuration
def generate_config() -> WorkerConfigNorm:
    """Generate the default configuration."""
    return config_validator.normalized({})


# Load & validate worker configuration
def load_config(filename: str | None = None) -> WorkerConfigNorm:
    """Load and validate the configuration."""
    config_file: str = filename if filename is not None else "config.json"
    if exists(config_file):
        with open(config_file, "r", encoding="utf8") as fileptr:
            try:
                config: WorkerConfigNorm | None = config_validator.normalized(load(fileptr))
            except JSONDecodeError as json_error:
                print(f"{config_file} is not valid JSON: {json_error}\n", file=stderr)
                sys_exit(1)
            except DocumentError as doc_error:
                print(f"{config_file} is invalid: {doc_error}\n", file=stderr)
                sys_exit(1)
        if config is None or not config_validator.validate(config):
            print(f"{config_file} is invalid:\n{config_validator.error_str()}\n", file=stderr)
            sys_exit(1)
    else:
        print(f"Configuration file '{config_file}' does not exist.", file=stderr)
        sys_exit(1)

    return config
