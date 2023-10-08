"""EGP worker type definitions."""
from typing import TypedDict, NotRequired
from pypgtable.pypgtable_typing import DatabaseConfig, DatabaseConfigNorm
from egp_population.egp_typing import PopulationsConfig
from uuid import UUID


class StoreConfig(TypedDict):
    """Type definition."""

    table: NotRequired[str]
    database: NotRequired[str]


class StoreConfigNorm(TypedDict):
    """Type definition."""

    table: str
    database: str


class WorkerConfig(TypedDict):
    """Type definition."""

    worker_id: NotRequired[UUID]
    problem_definitions: NotRequired[str]
    problem_folder: NotRequired[str]
    populations: NotRequired[PopulationsConfig]
    biome: NotRequired[StoreConfig]
    microbiome: NotRequired[StoreConfig]
    gene_pool: NotRequired[StoreConfig]
    databases: NotRequired[dict[str, DatabaseConfig]]


class WorkerConfigNorm(TypedDict):
    """Type definition."""

    worker_id: UUID
    problem_definitions: str
    problem_folder: str
    populations: PopulationsConfig
    biome: StoreConfigNorm
    microbiome: StoreConfigNorm
    gene_pool: StoreConfigNorm
    databases: dict[str, DatabaseConfigNorm]
