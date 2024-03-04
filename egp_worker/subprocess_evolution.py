"""Gene pool management for Erasmus GP."""

from gc import collect, disable, enable, freeze, unfreeze
from logging import DEBUG, Logger, NullHandler, getLogger
from multiprocessing import Process, set_start_method
from os import kill
from signal import SIGUSR1, signal
from time import sleep, time
from types import FrameType
from typing import Literal
from functools import partial
from numpy import single

from egp_physics.physics import pGC_fitness, population_GC_evolvability, population_GC_inherit, select_pGC
from egp_population.egp_typing import PopulationConfigNorm
from egp_population.population import population
from egp_stores.gene_pool import gene_pool
from egp_types.xGC import pGC
from egp_types.reference import ref_str
from egp_types.ep_type import ordered_interface_hash
from egp_execution.execution import create_callable
from psutil import virtual_memory
from pypgtable import db_disconnect_all


_logger: Logger = getLogger(__name__)
_logger.addHandler(NullHandler())
_LOG_DEBUG: bool = _logger.isEnabledFor(DEBUG)


_MINIMUM_SUBPROCESS_TIME = 60
_MINIMUM_AVAILABLE_MEMORY = 128 * 1024 * 1024


# Multiprocessing configuration
set_start_method("fork")


# The self terminate flag.
# Set by the SIGUSR1 handler to True allowing the sub-process to exit gracefully writing its data
# to the Gene Pool table when asked.
_TERMINATE = False


def terminate(_: int, __: FrameType | None) -> None:
    """Set the self termination flag.

    This is called by the SIGTERM handler.
    """
    global _TERMINATE  # pylint: disable=global-statement
    _logger.debug("SIGUSR1 received. Setting self terminate flag.")
    _TERMINATE = True


signal(SIGUSR1, terminate)


def exit_criteria() -> Literal[False]:
    """Are we done?"""
    return False


def pre_evolution_checks() -> None:
    """Make sure everything is good before we start."""
    # TODO: Implement this function


def spawn(p_configs: list[PopulationConfigNorm], g_pool: gene_pool, num_sub_processes: int) -> None:
    """Spawn subprocesses.

    Args
    ----
    num_sub_processes (int): Number of sub processes to spawn. If None the number of CPUs-1
                                will be used.
    """
    db_disconnect_all()
    collect()
    disable()
    freeze()

    _entry_point = partial(entry_point, p_configs, g_pool)
    processes: list[Process] = [Process(target=_entry_point) for _ in range(num_sub_processes)]
    start: float = time()
    for p in processes:
        # Sub-processes exit if the parent exits.
        p.daemon = True
        p.start()

    # Wait for a sub-process to terminate.
    while all((p.is_alive() for p in processes)) and memory_ok(start):
        sleep(10)

    # At least one sub-process is done or we need to reclaim some memory
    # so ask any running processes to finish up
    for p in filter(lambda x: x.is_alive(), processes):
        if p.pid is not None:
            kill(p.pid, SIGUSR1)
        else:
            raise RuntimeError("Sub-process has no PID.")

    for p in processes:
        p.join()

    # Re-enable GC
    unfreeze()
    enable()

    # TODO: Are we done? Did we run out of sub-process IDs?


def memory_ok(start: float) -> bool:
    """ "Check if, after a minimum runtime, memory available is low.

    Only if we have been
    running for more than _MINIMUM_SUBPROCESS_TIME seconds do we check to see
    if RAM available is low (< _MINIMUM_AVAILABLE_MEMORY bytes). If it is
    low return False else True.

    Args
    ----
    start: The epoch time the sub-processes were spawned.

    Returns
    -------
    (bool).
    """
    duration = int(time() - start)
    if duration < _MINIMUM_SUBPROCESS_TIME:
        return True
    available: int = virtual_memory().available
    ok: bool = available > _MINIMUM_AVAILABLE_MEMORY
    if not ok:
        _logger.info(f"Available memory is low ({available} bytes) after {duration}s." " Signalling sub-processes to terminate.")
    return ok


def entry_point(p_configs: list[PopulationConfigNorm], g_pool: gene_pool) -> None:
    """Entry point for sub-processes."""
    while not _TERMINATE and any(generation(p_config, g_pool) for p_config in p_configs):
        pass
    db_disconnect_all()


def viable_individual(individual, population_oih) -> bool:
    """Check if the individual is viable as a member of the population.

    This function does static checking on the viability of the individual
    as a member of the population.

    Args
    ----
    individual (xGC): The xGC of the individual.
    population_oih (int): The ordered interface hash for the population the individual is to be a member of.

    Returns
    -------
    (bool): True if the individual is viable else False.
    """
    if _LOG_DEBUG:
        _logger.debug(f"Potentially viable individual {individual}")

    if individual is None:
        return False

    # Check the interface is correct
    individual_oih: int = ordered_interface_hash(
        individual["input_types"], individual["output_types"], individual["inputs"], individual["outputs"]
    )

    if _LOG_DEBUG:
        _logger.debug(f"Individual is {('NOT ', '')[population_oih == individual_oih]}viable.")
    return population_oih == individual_oih


def generation(p_config: PopulationConfigNorm, g_pool: gene_pool) -> bool:
    """Evolve the population one generation and characterise it.

    Evolutionary steps are:
        a. Select a population size group of individuals weighted by survivability. Selection
            is from every individual in the local GP cache that is part of the population.
        b. For each individual:
            1. Select a pGC to operate on the individual
            2. Evolve the individual to produce an offspring
                TODO: Inheritance
            3. Characterise the offspring
            4. Update the individuals (parents) parameters (evolvability, survivability etc.)
            5. Update the parameters of the pGC (recursively)
        c. Reassess survivability for the entire population in the local cache.
                TODO: Optimisation mechanisms

    Returns True if the population was evolved, False otherwise.
    """
    # TODO: Can optimize how much xGC creation we do here. Append new xGCs to a list and
    #       only create them once. Also do not create the whole population list if survivability
    #       is only being calculated for active individuals.
    populous: population = population(g_pool.pool.get_population(p_config["uid"]))
    active_populus: population = populous.active()
    if len(active_populus):
        if _LOG_DEBUG:
            _logger.debug(f'Evolving population {p_config["name"]}, UID: {p_config["uid"]}')

        for count, individual in enumerate(active_populus):
            pgc: pGC = select_pGC(g_pool, individual)
            if _LOG_DEBUG:
                _logger.debug(f"Individual ({count + 1}/{len(active_populus)}): {individual}")
                _logger.debug(f"Mutating with pGC {pgc['ref']}")

            wrapped_pgc_exec = create_callable(pgc, g_pool.pool)
            result = wrapped_pgc_exec((individual,))
            if result is None:
                # pGC went pop - should not happen very often
                _logger.warning(f"pGC {ref_str(pgc['ref'])} threw an exception when called.")
                offspring = None
            else:
                offspring = result[0]

            if _LOG_DEBUG:
                _logger.debug(f"Offspring ({count + 1}/{len(active_populus)}): {offspring}")

            if offspring is not None and viable_individual(offspring, p_config["ordered_interface_hash"]):
                offspring_exec = create_callable(offspring, g_pool.pool)
                offspring["fitness"] = p_config["fitness_function"](offspring_exec)
                population_GC_inherit(offspring, individual, pgc)
                delta_fitness = offspring["fitness"] - individual["fitness"]
                # TODO: Arrange so this cast is not needed
                population_GC_evolvability(individual, delta_fitness)
            else:
                # pGC did not produce an offspring.
                delta_fitness: single = single(-1.0)
            pGC_fitness(g_pool, pgc, individual, delta_fitness)

        # Update survivabilities as the population has changed
        if _LOG_DEBUG:
            _logger.debug("Re-characterizing survivability of population.")
        p_config["survivability_function"](populous)

        # TODO: Metrics, GC population management
        return True
    return False


def evolve(p_configs: list[PopulationConfigNorm], g_pool: gene_pool, num_sub_processes: int = 0) -> None:
    """Co-evolve the population in pop_list."""
    pre_evolution_checks()
    while not exit_criteria():
        _logger.info(f"Starting new epoch with {num_sub_processes} sub-processes.")
        if num_sub_processes > 1:
            spawn(p_configs, g_pool, num_sub_processes)
        else:
            entry_point(p_configs, g_pool)
