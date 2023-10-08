"""Worker module for Erasmus GP."""
from argparse import ArgumentParser, Namespace, _MutuallyExclusiveGroup
from copy import deepcopy
from json import dump, load
from logging import Logger, NullHandler, getLogger
from os import W_OK, access, chdir, cpu_count, getcwd
from os.path import dirname, exists, join
from pathlib import Path
from sys import exit as sys_exit
from typing import Any, Iterator, cast
from uuid import UUID, uuid4
from sys import argv

from egp_population.egp_typing import PopulationConfigNorm
from egp_population.population_config import (configure_populations,
                                              new_population,
                                              population_table_default_config)
from egp_stores.egp_typing import GenePoolConfigNorm
from egp_stores.gene_pool import default_config as gp_default_config
from egp_stores.gene_pool import gene_pool
from egp_stores.genomic_library import default_config as gl_default_config
from egp_stores.genomic_library import genomic_library
from egp_utils.egp_logo import gallery, header, header_lines
from pypgtable import table
from pypgtable import __name__ as pypgtable_name
from pypgtable.common import connection_str_from_config
from pypgtable.pypgtable_typing import TableConfigNorm
from pypgtable.validators import table_config_validator
from requests import Response, get

from .config_validator import dump_config, load_config, generate_config
from .egp_typing import WorkerConfigNorm
from .platform_info import get_platform_info

_logger: Logger = getLogger(__name__)
_logger.addHandler(NullHandler())


# Some modules are noisey loggers
getLogger(pypgtable_name).setLevel("WARNING")


def parse_cmdline_args(args: list[str]) -> Namespace:
    """Parse the command line arguments."""
    parser: ArgumentParser = ArgumentParser(prog="egp-worker")
    meg: _MutuallyExclusiveGroup = parser.add_mutually_exclusive_group()
    parser.add_argument("-c", "--config_file", help="Path to a JSON configuration file.")
    meg.add_argument(
        "-D",
        "--use_default_config",
        help="Use the default internal configuration. This option will start work on the most interesting community problem.",
        action="store_true",
    )
    meg.add_argument(
        "-d",
        "--default_config",
        help="Generate a default configuration file. config.json will be stored in the current directory. All other options ignored.",
        action="store_true",
    )
    meg.add_argument(
        "-l",
        "--population_list",
        help="Update the configuration file with the popluation definitions from the Gene Pool.",
        action="store_true",
    )
    parser.add_argument(
        "-s",
        "--sub_processes",
        help="The number of subprocesses to spawn for evolution. Default is the number of cores - 1,",
        type=int,
        default=0,
    )
    meg.add_argument(
        "-g",
        "--gallery",
        help="Display the Erasmus GP logo gallery. All other options ignored.",
        action="store_true",
    )
    return parser.parse_args(args)


def launch_workers(args: Namespace) -> None:
    """Launch the worker."""

    # Erasmus header to stdout and logfile
    print(header())
    for line in header_lines(attr="bw"):
        _logger.info(line)

    # Dump the default configuration
    if args.default_config:
        dump_config()
        sys_exit(0)

    # Display the text logo art
    if args.gallery:
        print(gallery())
        sys_exit(0)

    # Load & validate worker configuration
    if args.use_default_config:
        config: WorkerConfigNorm = generate_config()
    else:
        config: WorkerConfigNorm = load_config(args.config_file)

    # Define gene pool configuration
    gp_config: GenePoolConfigNorm = gp_default_config()
    for key, table_config in cast(Iterator[tuple[str, TableConfigNorm]], gp_config.items()):
        table_config["table"] = config["gene_pool"]["table"] if key == "gene_pool" else config["gene_pool"]["table"] + "_" + key
        table_config["database"] = config["databases"][config["gene_pool"]["database"]]

    # Define population configuration
    # The population configuration is persisted in the gene pool database
    p_table_config: TableConfigNorm = population_table_default_config()
    p_table_config["table"] = gp_config["gene_pool"]["table"] + "_populations"
    p_table_config["database"] = gp_config["gene_pool"]["database"]

    # Dump the populations defined for the gene pool
    if args.population_list:
        p_table_config["create_db"] = False
        p_table_config["create_table"] = False
        p_table: table = table(p_table_config)
        config["populations"]["configs"] = list(p_table.select())
        with open("config.json", "w", encoding="utf8") as file_ptr:
            dump(config, file_ptr, indent=4, sort_keys=True)
        print("Configuration updated with Gene Pool population configurations written to ./config.json")
        sys_exit(0)

    # Check the problem data folder
    directory_path: str = config["problem_folder"]
    if exists(directory_path):
        if not access(directory_path, W_OK):
            print(f"The 'problem_folder' directory '{directory_path}' exists but is not writable.")
            sys_exit(1)
    else:
        # Create the directory if it does not exist
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
        except PermissionError as permission_error:
            print(f"The 'problem_folder' directory '{directory_path}' does not exist and cannot be created: {permission_error}")
            sys_exit(1)

    # Store the current working directory & change to where Erasmus GP keeps its data
    cwd: str = getcwd()
    chdir(directory_path)

    # Check the verified problem definitions file
    problem_definitions: list[dict[str, Any]] = []
    problem_definitions_file: str = join(directory_path, 'egp_problems.json')
    problem_definitions_file_exists: bool = exists(problem_definitions_file)
    if not problem_definitions_file_exists:
        _logger.info(f"The egp_problems.json does not exist in {directory_path}'. Pulling from {config['problem_definitions']}")
        response: Response = get(config['problem_definitions'], timeout=30)
        if (problem_definitions_file_exists := response.status_code == 200):
            with open(problem_definitions_file, "wb") as file:
                file.write(response.content)
            _logger.info("File 'egp_problems.json' downloaded successfully.")
        else:
            _logger.warning(f"Failed to download the file. Status code: {response.status_code}.")

    # Load the problems definitions file if it exists
    if problem_definitions_file_exists:
        with open(problem_definitions_file, "r", encoding="utf8") as file_ptr:
            problem_definitions = load(file_ptr)

    # Get the population configurations & set the worker ID
    worker_id: UUID = uuid4()
    _logger.info(f"Worker ID: {worker_id}")
    for p_config in config["populations"].get("configs", []):
        p_config["worker_id"] = worker_id
    p_config_tuple: tuple[dict[int, PopulationConfigNorm], table, table] = configure_populations(
        config["populations"], problem_definitions, p_table_config)
    p_configs: dict[int, PopulationConfigNorm] = p_config_tuple[0]
    p_table: table = p_config_tuple[1]
    pm_table: table = p_config_tuple[2]

    # Define genomic library configuration & instanciate
    gl_config: TableConfigNorm = gl_default_config()
    gl_config["database"] = config["databases"][config["microbiome"]["database"]]
    gl_config["table"] = config["microbiome"]["table"]
    glib: genomic_library = genomic_library(gl_config)

    # Establish the Gene Pool
    gpool: gene_pool = gene_pool(p_configs, glib, gp_config)
    gpool.sub_process_init()

    # TODO: Pull populations from higher layers
    for p_config in p_configs.values():
        new_population(p_config, gpool)

    # Get the platform information
    pi_table_config: TableConfigNorm = deepcopy(p_table_config)
    pi_table_config["table"] = gp_config["gene_pool"]["table"] + "_platform_info"
    pi_table_config["database"] = gp_config["gene_pool"]["database"]
    pi_table_config["create_db"] = False
    with open(
        join(dirname(__file__), "formats/platform_info_table_format.json"),
        "r",
        encoding="utf8",
    ) as file_ptr:
        pi_table_config["schema"] = {k: table_config_validator.normalized(v) for k, v in load(file_ptr).items()}
    pi_data: dict[str, Any] = get_platform_info(pi_table_config)

    # Register the worker.
    # The worker information is persisted in the gene pool database
    _logger.info("Configuration validated. All critical connections & populations established.")
    w_table_config: TableConfigNorm = deepcopy(p_table_config)
    w_table_config["table"] = gp_config["gene_pool"]["table"] + "_workers"
    w_table_config["database"] = gp_config["gene_pool"]["database"]
    w_table_config["create_db"] = False
    with open(join(dirname(__file__), "formats/worker_table_format.json"), "r", encoding="utf8") as file_ptr:
        w_table_config["schema"] = {k: table_config_validator.normalized(v) for k, v in load(file_ptr).items()}
    w_table: table = table(w_table_config)
    num_cores: int | None = cpu_count()
    sub_processes: int = 1 if num_cores is None or num_cores == 1 else num_cores - 1
    w_data: dict[str, Any] = {
        "worker_id": worker_id,
        "populations": [p["uid"] for p in p_configs.values()],
        "platform_info_signature": pi_data["signature"],
        "sub_processes": sub_processes if not args.sub_processes else args.sub_processes,
        "biome_connection_str": None,
        "microbiome_connection_str": connection_str_from_config(gl_config["database"]),
        "gene_pool_connection_str": connection_str_from_config(gp_config["gene_pool"]["database"]),
    }
    w_table.insert([w_data])


    # Return whence we came
    chdir(cwd)


if __name__ == "__main__":
    launch_workers(parse_cmdline_args(argv[1:]))
