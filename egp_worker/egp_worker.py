"""Worker module for Erasmus GP."""
from argparse import ArgumentParser, Namespace, _MutuallyExclusiveGroup
from copy import deepcopy
from json import dump, load
from logging import Logger, NullHandler, getLogger
from os import cpu_count, access, W_OK, chdir, getcwd
from os.path import dirname, join, exists
from sys import exit as sys_exit
from typing import Any, cast, Iterator
from uuid import uuid4
from requests import get, Response
from pathlib import Path

from egp_population.population_config import configure_populations, new_population, population_table_default_config
from egp_population.egp_typing import PopulationConfigNorm
from egp_stores.gene_pool import default_config as gp_default_config
from egp_stores.gene_pool import gene_pool
from egp_stores.genomic_library import default_config as gl_default_config
from egp_stores.genomic_library import genomic_library
from egp_stores.egp_typing import GenePoolConfigNorm
from egp_utils.egp_logo import gallery, header, header_lines
from pypgtable import table
from pypgtable.common import connection_str_from_config
from pypgtable.pypgtable_typing import TableConfigNorm
from pypgtable.validators import table_config_validator

from .platform_info import get_platform_info
from .egp_typing import WorkerConfigNorm
from .config_validator import load_config, dump_config


_logger: Logger = getLogger(__name__)
_logger.addHandler(NullHandler())


parser: ArgumentParser = ArgumentParser(prog="egp-worker")
meg: _MutuallyExclusiveGroup = parser.add_mutually_exclusive_group()
parser.add_argument("--config_file", "-c", "Path to a JSON configuration file.")
meg.add_argument(
    "--default_config",
    "-d",
    "Generate a default configuration file. config.json will be stored in the current directory. All other options ignored.",
    action="store_true",
)
meg.add_argument(
    "--population_list",
    "-l",
    "Update the configuration file with the popluation definitions from the Gene Pool.",
    action="store_true",
)
parser.add_argument(
    "--sub_workers",
    "-s",
    "The number of subworkers to spawn for evolution. Default is the number of cores - 1,",
    type=int,
    default=0,
)
meg.add_argument(
    "--gallery",
    "-g",
    "Display the Erasmus GP logo gallery. All other options ignored.",
    action="store_true",
)
args: Namespace = parser.parse_args()

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
config: WorkerConfigNorm = load_config(args.config_file)

# Define gene pool configuration
gp_config: GenePoolConfigNorm = gp_default_config()
base_name: str = config["gene_pool"]["table"]
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
    config["population"]["configs"] = list(p_table.select())
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
    except PermissionError as e:
        print(f"The 'problem_folder' directory '{directory_path}' does not exist and cannot be created: {e}")
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

# Get the population configurations
p_config_tuple: tuple[dict[int, PopulationConfigNorm], table, table] = configure_populations(
    config["population"], problem_definitions, p_table_config)
p_configs: dict[int, PopulationConfigNorm] = p_config_tuple[0]
p_table: table = p_config_tuple[1]
pm_table: table = p_config_tuple[2]

# Define genomic library configuration & instanciate
gl_config: TableConfigNorm = gl_default_config()
gl_config["database"] = config["databases"][config["microbiome"]["database"]]
gl_config["table"] = config["microbiome"]["table"]
glib: genomic_library = genomic_library(gl_config)

# TODO: Ping the biome - only warn if inaccessible
# FIXME: This probably should be in the genomic libary class
b_config: TableConfigNorm = gl_default_config()
b_config["database"] = config["databases"][config["biome"]["database"]]

# Establish the Gene Pool
gpool: gene_pool = gene_pool(p_configs, glib, gp_config)

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
sub_workers: int = 1 if num_cores is None or num_cores == 1 else num_cores - 1
w_data: dict[str, Any] = {
    "worker": uuid4(),
    "populations": [p["population_hash"] for p in p_configs.values()],
    "platform_info_hash": pi_data["signature"],
    "sub_workers": sub_workers if not args.sub_workers else args.sub_workers,
    "biome_connection_str": connection_str_from_config(b_config["database"]),
    "microbiome_connection_str": connection_str_from_config(gl_config["database"]),
    "gene_pool_connection_str": connection_str_from_config(gp_config["gene_pool"]["database"]),
}
w_table.insert([w_data])


# Return whence we came
chdir(cwd)
