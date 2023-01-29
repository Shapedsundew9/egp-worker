from json import load, dump
from os.path import join, dirname
from argparse import ArgumentParser, Namespace
from egp_utils.base_validator import base_validator
from typing import Any
from egp_stores.gene_pool import gene_pool, default_config as gp_default_config
from egp_stores.genomic_library import genomic_library, default_config as gl_default_config
from egp_population.population import population


# FIXME: Add a version
parser: ArgumentParser = ArgumentParser(prog='egp-worker')
parser.add_argument("--config_file", "-c", "Path to a JSON configuration file.")
parser.add_argument("--default_config", "-d", "Generate a default configuration file. config.json will be stored in the current directory.", action="store_true")
parser.add_argument("--population_list", "-l", "Generate a popluation definition configuration from the Gene Pool.", action="store_true")
parser.add_argument("--population", "-p", "The UID of the population to be evolved. Can be specified multiple times for co-evolution.", type=int, action='append')
parser.add_argument("--sub-workers", "-s", "The number of subworkers to spawn for evolution. Default is the number of cores - 1,", type=int, default=0)
args: Namespace = parser.parse_args()

with open(join(dirname(__file__), "formats/config_format.json"), "r", encoding="utf8") as file_ptr:
    config_validator: base_validator = base_validator(load(file_ptr))

if args.default_config:
    default_config: dict[str, dict[str, Any]] = {}
    config_validator.normalized(default_config)
    with open("config.json", "w", encoding="utf8") as file_ptr:
        dump(default_config, file_ptr, indent=4, sort_keys=True)
    print("Default configuration written to ./config.json")

else:
    config_file: str = args.config_file if args.config_file is not None else "config.json"    
    with open(config_file, "r", encoding="utf8") as file_ptr:
        config: dict[str, dict[str, Any]] = load(file_ptr)
        config_validator.normalized(config)

    gl_config: dict[str, Any] = gl_default_config()
    gl_config['database'] = config['microbiome']['database']
    gl_config['table'] = config['microbiome']['table']
    gl: genomic_library = genomic_library(gl_config)

    gp_config: dict[str, dict[str, Any]] = gl_default_config()
    gp_config['database'] = config['microbiome']['database']
    gp_config['table'] = config['microbiome']['table']
    gp = gene_pool()

    if args.population_list

