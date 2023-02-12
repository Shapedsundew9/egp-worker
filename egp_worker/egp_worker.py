"""Worker module for Erasmus GP."""
from argparse import ArgumentParser, Namespace, _MutuallyExclusiveGroup
from copy import deepcopy
from json import dump, load
from logging import Logger, NullHandler, getLogger
from os.path import dirname, join
from sys import exit as sys_exit
from sys import stderr
from typing import Any

from egp_population.population import population_table_config, configure_populations, new_population
from egp_population.typing import PopulationConfigNorm
from egp_population.population_validator import POPULATION_ENTRY_SCHEMA
from egp_stores.gene_pool import default_config as gp_default_config
from egp_stores.gene_pool import gene_pool
from egp_stores.genomic_library import default_config as gl_default_config
from egp_stores.genomic_library import genomic_library
from egp_stores.typing import GenePoolConfigNorm
from egp_utils.base_validator import base_validator
from egp_utils.egp_logo import gallery, header, header_lines
from pypgtable import table
from pypgtable.typing import TableConfigNorm
from pypgtable.validators import PYPGTABLE_DB_CONFIG_SCHEMA

from .typing import WorkerConfigNorm

_logger: Logger = getLogger(__name__)
_logger.addHandler(NullHandler())


parser: ArgumentParser = ArgumentParser(prog='egp-worker')
meg: _MutuallyExclusiveGroup = parser.add_mutually_exclusive_group()
parser.add_argument("--config_file", "-c", "Path to a JSON configuration file.")
meg.add_argument(
    "--default_config",
    "-d",
    "Generate a default configuration file. config.json will be stored in the current directory. All other options ignored.",
    action="store_true")
meg.add_argument("--population_list", "-l", "Update the configuration file with the popluation definitions from the Gene Pool.",
                 action="store_true")
parser.add_argument(
    "--sub-workers",
    "-s",
    "The number of subworkers to spawn for evolution. Default is the number of cores - 1,",
    type=int,
    default=0)
meg.add_argument("--gallery", "-g", "Display the Erasmus GP logo gallery. All other options ignored.", action="store_true")
args: Namespace = parser.parse_args()

# Erasmus header to stdout and logfile
print(header())
for line in header_lines(attr='bw'):
    _logger.info(line)

# Load the config file validator
with open(join(dirname(__file__), "formats/config_format.json"), "r", encoding="utf8") as file_ptr:
    CONFIG_SCHEMA: dict[str, Any] = load(file_ptr)
CONFIG_SCHEMA['populations']['configs'] = deepcopy(POPULATION_ENTRY_SCHEMA)
CONFIG_SCHEMA['databases']['valuesrules']['schema'] = deepcopy(PYPGTABLE_DB_CONFIG_SCHEMA)
config_validator: base_validator = base_validator(CONFIG_SCHEMA)

# Dump the default configuration
if args.default_config:
    if args.default_config:
        default_config: WorkerConfigNorm = config_validator.normalized({})
        with open("config.json", "w", encoding="utf8") as file_ptr:
            dump(default_config, file_ptr, indent=4, sort_keys=True)
        print("Default configuration written to ./config.json")
        exit(0)

# Display the text logo art
if args.gallery:
    print(gallery())
    sys_exit(0)

# Load & validate worker configuration
config_file: str = args.config_file if args.config_file is not None else "config.json"
with open(config_file, "r", encoding="utf8") as file_ptr:
    config: WorkerConfigNorm | None = config_validator.normalized(load(file_ptr))
if config is None:
    print(f'{config_file} is invalid:\n{config_validator.error_str()}\n', file=stderr)
    sys_exit(1)

# Define gene pool configuration
gp_config: GenePoolConfigNorm = gp_default_config()
base_name: str = config['gene_pool']['table']
for key, table_config in gp_config.items():
    if isinstance(table_config, TableConfigNorm):
        table_config['table'] = config['gene_pool']['table'] if key == 'gene_pool' else config['gene_pool']['table'] + '_' + key
        table_config['database'] = config['databases'][config['gene_pool']['database']]  # type: ignore
    else:
        raise AssertionError(f'table_config is a {type(table_config)}. This should not be possible!')

# Define population configuration
# The population configuration is persisted in the gene pool database
p_table_config: TableConfigNorm = population_table_config()
p_table_config['table'] = gp_config['gene_pool']['table'] + '_populations'
p_table_config['database'] = gp_config['gene_pool']['database']

# Dump the populations defined for the gene pool
if args.population_list:
    p_table_config['create_db'] = False
    p_table_config['create_table'] = False
    p_table: table = table(p_table_config)
    config['population']['configs'] = list(p_table.select())
    with open("config.json", "w", encoding="utf8") as file_ptr:
        dump(config, file_ptr, indent=4, sort_keys=True)
    print("Configuration updated with Gene Pool population configurations written to ./config.json")
    sys_exit(0)

# Define genomic library configuration & instanciate
gl_config: TableConfigNorm = gl_default_config()
gl_config['database'] = config['databases'][config['microbiome']['database']]
gl_config['table'] = config['microbiome']['table']
glib: genomic_library = genomic_library(gl_config)

# Get the population configurations
p_config_tuple: tuple[dict[int, PopulationConfigNorm], table, table] = configure_populations(config['population'], p_table_config)
p_configs: dict[int, PopulationConfigNorm] = p_config_tuple[0]
p_table: table = p_config_tuple[1]
pm_table: table = p_config_tuple[2]

# Establish the Gene Pool
gpool: gene_pool = gene_pool(p_configs, glib, gp_config)

# TODO: Pull populations from higher layers
for p_config in p_configs.values():
    new_population(p_config, glib, gpool)


