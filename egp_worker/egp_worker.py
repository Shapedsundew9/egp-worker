from json import load, dump
from os.path import join, dirname
from argparse import ArgumentParser, Namespace
from egp_utils.base_validator import base_validator
from typing import Any
from egp_stores.gene_pool import gene_pool, default_config as gp_default_config
from pypgtable.typing import TableConfig, TableConfigNorm
from egp_stores.genomic_library import genomic_library, default_config as gl_default_config
from egp_stores.typing import GenePoolConfigNorm
from egp_population.population import population
from sys import exit, stderr
from .typing import WorkerConfig, WorkerConfigNorm
from copy import deepcopy


# FIXME: Add a version
parser: ArgumentParser = ArgumentParser(prog='egp-worker')
parser.add_argument("--config_file", "-c", "Path to a JSON configuration file.")
parser.add_argument("--default_config", "-d", "Generate a default configuration file. config.json will be stored in the current directory. All other options ignored.", action="store_true")
parser.add_argument("--population_list", "-l", "Generate a popluation definition configuration from the Gene Pool.", action="store_true")
parser.add_argument("--sub-workers", "-s", "The number of subworkers to spawn for evolution. Default is the number of cores - 1,", type=int, default=0)
args: Namespace = parser.parse_args()

with open(join(dirname(__file__), "formats/config_format.json"), "r", encoding="utf8") as file_ptr:
    config_validator: base_validator = base_validator(load(file_ptr))

if args.default_config:
    default_config: WorkerConfigNorm = config_validator.normalized({})
    with open("config.json", "w", encoding="utf8") as file_ptr:
        dump(default_config, file_ptr, indent=4, sort_keys=True)
    print("Default configuration written to ./config.json")

else:
    # Load & validate worker configuration
    config_file: str = args.config_file if args.config_file is not None else "config.json"    
    with open(config_file, "r", encoding="utf8") as file_ptr:
        config: WorkerConfigNorm | None = config_validator.normalized(load(file_ptr))
    if config is None:
        print(f'{config_file} is invalid:\n{config_validator.error_str()}\n', file=stderr)
        exit(1)

    # Define gene pool configuration
    gp_config: GenePoolConfigNorm = gp_default_config()
    base_name: str = config['gene_pool']['table']
    for key, table_config in gp_config.items():
        if isinstance(table_config, TableConfigNorm):
            table_config['table'] = config['gene_pool']['table'] if key == 'gene_pool' else config['gene_pool']['table'] + '_' + key
            table_config['database'] = config['databases'][config['gene_pool']['database']]  #type: ignore
        else:
            raise AssertionError(f'table_config is a {type(table_config)}. This should not be possible!')

    # Define population configuration
    # The population configuration is persisted in the gene pool database
    p_config: TableConfigNorm = deepcopy(gp_config['gene_pool'])
    p_config['table'] = p_config['table'] + '_populations'

    # Define genomic library configuration & instanciate
    gl_config: TableConfigNorm = gl_default_config()
    gl_config['database'] = config['databases'][config['microbiome']['database']]
    gl_config['table'] = config['microbiome']['table']
    gl: genomic_library = genomic_library(gl_config)

    gp: gene_pool = gene_pool()

    if args.population_list

