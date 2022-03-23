from itertools import product

import jax
import numpy as np

from pgmax.factors import logical
from pgmax.fg import graph, groups


def test_run_bp_with_OR_factors():
    """
    Simultaneously test
    (1) the support of ORFactors in a factor graph and their specialized inference for different temperatures
    (2) the support of several factor types in a factor graph and during inference

    To do so, observe that an ORFactor can be defined as an equivalent EnumerationFactor
    (which list all the valid OR configurations) and define two equivalent factor graphs
    FG1: first half of factors are defined as EnumerationFactors, second half are defined as ORFactors
    FG2: first half of factors are defined as ORFactors, second half are defined as EnumerationFactors

    Inference for the EnumerationFactors will be run with pass_enum_fac_to_var_messages while
    inference for the ORFactors will be run with pass_OR_fac_to_var_messages.

    Note: for the first seed, add all the EnumerationFactors to FG1 and all the ORFactors to FG2
    """
    for idx in range(10):
        np.random.seed(idx)

        # Parameters
        num_factors = np.random.randint(3, 8)
        num_parents = np.random.randint(1, 6, num_factors)
        num_parents_cumsum = np.insert(np.cumsum(num_parents), 0, 0)

        # Setting the temperature
        if idx % 2 == 0:
            # Max-product
            temperature = 0.0
        else:
            temperature = np.random.uniform(low=0.5, high=1.0)

        # Graph 1
        parents_variables1 = groups.NDVariableArray(
            num_states=2, shape=(num_parents.sum(),)
        )
        children_variable1 = groups.NDVariableArray(num_states=2, shape=(num_factors,))
        fg1 = graph.FactorGraph(
            variables=dict(parents=parents_variables1, children=children_variable1)
        )

        # Graph 2
        parents_variables2 = groups.NDVariableArray(
            num_states=2, shape=(num_parents.sum(),)
        )
        children_variable2 = groups.NDVariableArray(num_states=2, shape=(num_factors,))
        fg2 = graph.FactorGraph(
            variables=dict(parents=parents_variables2, children=children_variable2)
        )

        # Option 1: Define EnumerationFactors equivalent to the ORFactors
        for factor_idx in range(num_factors):
            this_num_parents = num_parents[factor_idx]
            variable_names = [
                ("parents", idx)
                for idx in range(
                    num_parents_cumsum[factor_idx],
                    num_parents_cumsum[factor_idx + 1],
                )
            ] + [("children", factor_idx)]

            configs = np.array(list(product([0, 1], repeat=this_num_parents + 1)))
            # Children state is last
            valid_ON_configs = configs[
                np.logical_and(configs[:, :-1].sum(axis=1) >= 1, configs[:, -1] == 1)
            ]
            valid_configs = np.concatenate(
                [np.zeros((1, this_num_parents + 1), dtype=int), valid_ON_configs],
                axis=0,
            )
            assert valid_configs.shape[0] == 2 ** this_num_parents

            if factor_idx < num_factors // 2:
                # Add the first half of factors to FactorGraph1
                fg1.add_factor(
                    variable_names=variable_names,
                    factor_configs=valid_configs,
                    log_potentials=np.zeros(valid_configs.shape[0]),
                )
            else:
                if idx != 0:
                    # Add the second half of factors to FactorGraph2
                    fg2.add_factor(
                        variable_names=variable_names,
                        factor_configs=valid_configs,
                        log_potentials=np.zeros(valid_configs.shape[0]),
                    )
                else:
                    # Add all the EnumerationFactors to FactorGraph1 for the first iter
                    fg1.add_factor(
                        variable_names=variable_names,
                        factor_configs=valid_configs,
                        log_potentials=np.zeros(valid_configs.shape[0]),
                    )

        # Option 2: Define the ORFactors
        num_parents_cumsum = np.insert(np.cumsum(num_parents), 0, 0)
        for factor_idx in range(num_factors):
            variables_names_for_OR_factor = [
                ("parents", idx)
                for idx in range(
                    num_parents_cumsum[factor_idx],
                    num_parents_cumsum[factor_idx + 1],
                )
            ] + [("children", factor_idx)]
            if factor_idx < num_factors // 2:
                # Add the first half of factors to FactorGraph2
                fg2.add_factor_by_type(
                    variable_names=variables_names_for_OR_factor,
                    factor_type=logical.ORFactor,
                )
            else:
                if idx != 0:
                    # Add the second half of factors to FactorGraph1
                    fg1.add_factor_by_type(
                        variable_names=variables_names_for_OR_factor,
                        factor_type=logical.ORFactor,
                    )
                else:
                    # Add all the ORFactors to FactorGraph2 for the first iter
                    fg2.add_factor_by_type(
                        variable_names=variables_names_for_OR_factor,
                        factor_type=logical.ORFactor,
                    )

        # Run inference
        run_bp1, _, get_beliefs1 = graph.BP(fg1.bp_state, 100, temperature)
        run_bp2, _, get_beliefs2 = graph.BP(fg2.bp_state, 100, temperature)

        evidence_updates = {
            "parents": jax.device_put(np.random.gumbel(size=(sum(num_parents), 2))),
            "children": jax.device_put(np.random.gumbel(size=(num_factors, 2))),
        }

        bp_arrays1 = run_bp1(evidence_updates=evidence_updates)
        bp_arrays2 = run_bp2(evidence_updates=evidence_updates)

        # Get beliefs
        beliefs1 = get_beliefs1(bp_arrays1)
        beliefs2 = get_beliefs2(bp_arrays2)

        np.allclose(beliefs1["children"], beliefs2["children"], atol=1e-4)
        np.allclose(beliefs1["parents"], beliefs2["parents"], atol=1e-4)


def test_run_bp_with_AND_factors():
    """
    Simultaneously test
    (1) the support of ANDFactors in a factor graph inference and their specialized inference
    for different temperature
    (2) the support of several factor types in a factor graph and during inference

    To do so, observe that an ANDFactor can be defined as an equivalent EnumerationFactor
    (which list all the valid AND configurations) and define two equivalent factor graphs
    FG1: first half of factors are defined as EnumerationFactors, second half are defined as ANDFactors
    FG2: first half of factors are defined as ANDFactors, second half are defined as EnumerationFactors

    Inference for the EnumerationFactors will be run with pass_enum_fac_to_var_messages while
    inference for the ANDFactors will be run with pass_OR_fac_to_var_messages.

    Note: for the first seed, we add all the EnumerationFactors to FG1 and all the ANDFactors to FG2
    """
    for idx in range(10):
        np.random.seed(idx)

        # Parameters
        num_factors = np.random.randint(3, 8)
        num_parents = np.random.randint(1, 6, num_factors)
        num_parents_cumsum = np.insert(np.cumsum(num_parents), 0, 0)

        # Setting the temperature
        if idx % 2 == 0:
            # Max-product
            temperature = 0.0
        else:
            temperature = np.random.uniform(low=0.5, high=1.0)

        # Graph 1
        parents_variables1 = groups.NDVariableArray(
            num_states=2, shape=(num_parents.sum(),)
        )
        children_variable1 = groups.NDVariableArray(num_states=2, shape=(num_factors,))
        fg1 = graph.FactorGraph(
            variables=dict(parents=parents_variables1, children=children_variable1)
        )

        # Graph 2
        parents_variables2 = groups.NDVariableArray(
            num_states=2, shape=(num_parents.sum(),)
        )
        children_variable2 = groups.NDVariableArray(num_states=2, shape=(num_factors,))
        fg2 = graph.FactorGraph(
            variables=dict(parents=parents_variables2, children=children_variable2)
        )

        # Option 1: Define EnumerationFactors equivalent to the ANDFactors
        for factor_idx in range(num_factors):
            this_num_parents = num_parents[factor_idx]
            variable_names = [
                ("parents", idx)
                for idx in range(
                    num_parents_cumsum[factor_idx],
                    num_parents_cumsum[factor_idx + 1],
                )
            ] + [("children", factor_idx)]

            configs = np.array(list(product([0, 1], repeat=this_num_parents + 1)))
            # Children state is last
            valid_AND_configs = configs[
                np.logical_and(
                    configs[:, :-1].sum(axis=1) < this_num_parents, configs[:, -1] == 0
                )
            ]
            valid_configs = np.concatenate(
                [np.ones((1, this_num_parents + 1), dtype=int), valid_AND_configs],
                axis=0,
            )
            assert valid_configs.shape[0] == 2 ** this_num_parents

            if factor_idx < num_factors // 2:
                # Add the first half of factors to FactorGraph1
                fg1.add_factor(
                    variable_names=variable_names,
                    factor_configs=valid_configs,
                    log_potentials=np.zeros(valid_configs.shape[0]),
                )
            else:
                if idx != 0:
                    # Add the second half of factors to FactorGraph2
                    fg2.add_factor(
                        variable_names=variable_names,
                        factor_configs=valid_configs,
                        log_potentials=np.zeros(valid_configs.shape[0]),
                    )
                else:
                    # Add all the EnumerationFactors to FactorGraph1 for the first iter
                    fg1.add_factor(
                        variable_names=variable_names,
                        factor_configs=valid_configs,
                        log_potentials=np.zeros(valid_configs.shape[0]),
                    )

        # Option 2: Define the ANDFactors
        num_parents_cumsum = np.insert(np.cumsum(num_parents), 0, 0)
        for factor_idx in range(num_factors):
            variables_names_for_AND_factor = [
                ("parents", idx)
                for idx in range(
                    num_parents_cumsum[factor_idx],
                    num_parents_cumsum[factor_idx + 1],
                )
            ] + [("children", factor_idx)]

            if factor_idx < num_factors // 2:
                # Add the first half of factors to FactorGraph2
                fg2.add_factor_by_type(
                    variable_names=variables_names_for_AND_factor,
                    factor_type=logical.ANDFactor,
                )
            else:
                if idx != 0:
                    # Add the second half of factors to FactorGraph1
                    fg1.add_factor_by_type(
                        variable_names=variables_names_for_AND_factor,
                        factor_type=logical.ANDFactor,
                    )
                else:
                    # Add all the ANDFactors to FactorGraph2 for the first iter
                    fg2.add_factor_by_type(
                        variable_names=variables_names_for_AND_factor,
                        factor_type=logical.ANDFactor,
                    )

        # Run inference
        run_bp1, _, get_beliefs1 = graph.BP(fg1.bp_state, 100, temperature)
        run_bp2, _, get_beliefs2 = graph.BP(fg2.bp_state, 100, temperature)

        evidence_updates = {
            "parents": jax.device_put(np.random.gumbel(size=(sum(num_parents), 2))),
            "children": jax.device_put(np.random.gumbel(size=(num_factors, 2))),
        }

        bp_arrays1 = run_bp1(evidence_updates=evidence_updates)
        bp_arrays2 = run_bp2(evidence_updates=evidence_updates)

        # Get beliefs
        beliefs1 = get_beliefs1(bp_arrays1)
        beliefs2 = get_beliefs2(bp_arrays2)

        assert np.allclose(beliefs1["children"], beliefs2["children"], atol=1e-4)
        assert np.allclose(beliefs1["parents"], beliefs2["parents"], atol=1e-4)
