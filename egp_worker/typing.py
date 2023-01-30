from typing import TypedDict, NotRequired
from pypgtable.typing import DatabaseConfig, DatabaseConfigNorm


class StoreConfig(TypedDict):
    table: NotRequired[str]
    database: NotRequired[str]


class StoreConfigNorm(TypedDict):
    table: str
    database: str


class WorkerConfig(TypedDict):
    biome: NotRequired[StoreConfig]
    microbiome: NotRequired[StoreConfig]
    gene_pool: NotRequired[StoreConfig]
    databases: NotRequired[dict[str, DatabaseConfig]]


class WorkerConfigNorm(TypedDict):
    biome: StoreConfigNorm
    microbiome: StoreConfigNorm
    gene_pool: StoreConfigNorm
    databases: dict[str, DatabaseConfigNorm]
