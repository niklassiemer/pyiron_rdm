import ast
import json
import warnings

_ASMO = "http://purls.helmholtz-metadaten.de/asmo"

_MIN_ALGO_MAP = {
    "fire": "MIN_ALGO_FIRE",
    "cg": "MIN_ALGO_CG",
    "hftn": "MIN_ALGO_HFTN",
    "lbfgs": "MIN_ALGO_LBFGS",
    "quickmin": "MIN_ALGO_QUICKMIN",
    "sd": "MIN_ALGO_STEEP_DESC",
}

_IONIC_MIN_ALGO_MAP = {
    "rmm-diis": "MIN_ALGO_RMM_DIIS",
    "cg": "MIN_ALGO_CG",
    "damped_md": "MIN_ALGO_DAMPED_MD",
}

_MD_ENSEMBLE_MAP = {
    f"{_ASMO}/MicrocanonicalEnsemble": ("microcanonical ensemble", "TD_ENSEMBLE_NVE"),
    f"{_ASMO}/CanonicalEnsemble": ("canonical ensemble", "TD_ENSEMBLE_ATOM_ENS_NVT"),
    f"{_ASMO}/IsothermalIsobaricEnsemble": (
        "isothermal-isobaric ensemble",
        "TD_ENSEMBLE_NPT",
    ),
}

_EOS_MAP = {
    f"{_ASMO}/BirchMurnaghan": "EOS_BIRCH_MURNAGHAN",
    f"{_ASMO}/Murnaghan": "EOS_MURNAGHAN",
    f"{_ASMO}/Vinet": "EOS_VINET",
    f"{_ASMO}/PolynomialFit": "EOS_POLYNOMIAL",
}

_XC_FUNCTIONAL_MAP = {
    "LDA": "XC_FUNC_LDA",
    "PBE": "XC_FUNC_PBE",
    "GGA": "XC_FUNC_PBE",
}


def format_json_string(json_string):
    json_string = json_string.replace("\n", "<br>")
    result = []
    for index, char in enumerate(json_string):
        if char == " " and (index == 0 or json_string[index - 1] != ":"):
            result.append("&nbsp;&nbsp;")
        else:
            result.append(char)

    json_string = "".join(result)
    return json_string


def revert_json_string_formatting(formated_json_string):
    return formated_json_string.replace("<br>", "\n").replace("&nbsp;&nbsp;", " ")


def map_cdict_to_ob(user_name, cdict, concept_dict):

    # cdict = flat concept_dict

    props = {}
    if "structure_name" not in cdict.keys():
        props["user_name"] = user_name

    props |= {
        "pyiron_conceptual_dictionary": format_json_string(
            json.dumps(concept_dict, indent=2)
        ),
        "description_multiline": '<p><span style="color:hsl(240,75%,60%);">'
        + "<strong>Scroll down below other properties to view conceptual dictionary with ontological ids of selected properties and values.</strong></span>"
        + '<br>The conceptual dictionary is in JSON-LD format. Learn more about it <a href="https://www.w3.org/ns/json-ld/">here</a></p>',
    }
    description = props["description_multiline"]

    if "workflow_manager" in cdict.keys():
        props["workflow_manager"] = cdict["workflow_manager"]

    # structure
    if "structure_name" in cdict.keys():
        props["$name"] = cdict["structure_name"]
        props["description_multiline"] = (
            "Crystal structure generated using pyiron." + props["description_multiline"]
        )
        map_struct_to_ob(props, cdict, concept_dict)
        return props

    # job, project, server
    elif "job_name" in cdict.keys():
        props["$name"] = cdict["job_name"]
        if "job_status" in cdict.keys():
            if (
                cdict["job_status"] == "finished"
            ):  # TODO we also did True if status 'not_converged' or 'converged'??
                props["sim_job_finished"] = True
            else:
                props["sim_job_finished"] = False
        if "job_starttime" in cdict.keys() and "job_stoptime" in cdict.keys():
            from datetime import datetime

            import numpy as np

            delta = datetime.strptime(
                cdict["job_stoptime"], "%Y-%m-%d %H:%M:%S"
            ) - datetime.strptime(cdict["job_starttime"], "%Y-%m-%d %H:%M:%S")
            props["sim_walltime_in_hours"] = np.round(delta.total_seconds() / 3600, 6)
        job_name_pairs = {
            "job_starttime": "start_date",
            "sim_coretime_hours": "sim_coretime_in_hours",
            "number_cores": "ncores",
            "queue": "hpc_job_queue",
            "queue id": "hpc_job_id",
            "maximum_iterations": "max_iters",
            "ionic_energy_tolerance": "atom_e_tol_ion_in_ev",
            "force_tolerance": "atom_f_tol_in_ev_a",
            "number_ionic_steps": "atom_ionic_steps",
            "final_maximum_force": "atom_force_max_in_ev_a",
            "periodicity_in_x": "periodic_boundary_x",
            "periodicity_in_y": "periodic_boundary_y",
            "periodicity_in_z": "periodic_boundary_z",
            "final_total_energy": "atom_fin_tot_eng_in_ev",
            "final_total_volume": "atom_fin_vol_in_a3",
            "final_potential_energy": "atom_fin_pot_eng_in_ev",
        }
        for key, val in job_name_pairs.items():
            if key in cdict.keys():
                props[val] = cdict[key]

        if "dof" in cdict:
            props |= {
                "atom_cell_vol_relax": f"{_ASMO}/CellVolumeRelaxation" in cdict["dof"],
                "atom_cell_shp_relax": f"{_ASMO}/CellShapeRelaxation" in cdict["dof"],
                "atom_pos_relax": f"{_ASMO}/AtomicPositionRelaxation" in cdict["dof"],
            }
        if "molecular_statics" in concept_dict and "minimization_algorithm" in cdict:
            description = (
                f'{cdict["job_type"]} simulation using pyiron for energy minimization/structural optimization.'
                + props["description_multiline"]
            )  # TODO double check correctness
            min_algo = _MIN_ALGO_MAP.get(cdict["minimization_algorithm"])
            if min_algo is None:
                raise ValueError("Unknown minimization algorithm")
            props |= {
                "atomistic_calc_type": "atom_calc_struc_opt",
                "atom_ionic_min_algo": min_algo,
                "description_multiline": description,
            }
            if (
                "target_pressure" in cdict.keys()
                and cdict["target_pressure"] is not None
            ):
                props["atom_targ_press_in_gpa"] = cdict["target_pressure"]
        if "molecular_dynamics" in concept_dict.keys():
            for ensemble_url, (ensemble_desc, ensemble_code) in _MD_ENSEMBLE_MAP.items():
                if ensemble_url in cdict["ensemble"]:
                    description = (
                        f'{cdict["job_type"]} simulation using pyiron for {ensemble_desc}.'
                        + props["description_multiline"]
                    )
                    props["atom_md_ensemble"] = ensemble_code
                    break
            props |= {
                "atomistic_calc_type": "Atom_calc_md",
                "description_multiline": description,
            }

            for key, val in {
                "timestep": "atom_md_time_stp_in_ps",
                "simulation_time": "atom_sim_time_ps_in_ps",
                "average_total_energy": "atom_avg_tot_eng_in_ev",
                "average_potential_energy": "atom_avg_pot_eng_in_ev",
                "average_temperature": "atom_md_avg_temp_in_k",
                "average_pressure": "atom_avg_press_in_gpa",
                "average_total_volume": "atom_avg_vol_in_a3",
                "initial_temperature": "atom_md_init_temp_in_k",
                "target_temperature": "atom_md_targ_temp_in_k",
                "initial_pressure": "atom_md_init_press_in_gpa",
                "target_pressure": "atom_targ_press_in_gpa",
                "strain_axes": "murn_strain_axes",
                "number_of_data_points": "murn_n_data_points",
                "volume_range": "murn_strainvol_range",
                "equilibrium_bulk_modulus": "atom_equil_k_mod_in_gpa",
                "equilibrium_total_energy": "atom_equil_toteng_in_ev",
                "equilibrium_volume": "atom_equil_vol_in_a3",
            }.items():
                if key in cdict.keys():
                    props[val] = cdict[key]

        if "job_type" in cdict.keys() and "Murn" in cdict["job_type"]:
            props["description_multiline"] = (
                "Murnaghan job for structural optimization."
                + props["description_multiline"]
            )
        if "equation_of_state_fit" in cdict.keys():
            eos = cdict["equation_of_state_fit"]
            eos_val = _EOS_MAP.get(eos)
            if eos_val:
                props["murn_eqn_of_state"] = eos_val
                if eos == f"{_ASMO}/PolynomialFit":
                    props["murn_fit_eqn_order"] = cdict["fit_order"]
            else:
                warnings.warn("Unknown equation of state")

        if cdict.get("energy_cutoff"):
            props["atom_e_cutoff_in_ev"] = cdict["energy_cutoff"]
        if "xc_functional" in cdict.keys():
            xc_val = _XC_FUNCTIONAL_MAP.get(cdict["xc_functional"])
            if xc_val:
                props["atom_xc_functional"] = xc_val
            else:
                warnings.warn(
                    f"XC functional '{cdict['xc_functional']}' is not yet mapped."
                )

        if "electronic_smearing" in cdict.keys():
            elsmear_map = {
                "Methfessel-Paxton": "ELEC_SMEAR_MP",
                "Gaussian": "ELEC_SMEAR_GAUSS",
                "Fermi": "ELEC_SMEAR_FERMI",
                "Tetrahedron": "ELEC_SMEAR_TET",
                "Tetrahedron_Bloechl": "ELEC_SMEAR_TET_BL",
            }
            elsmear_val = elsmear_map.get(cdict.get("electronic_smearing"))
            if elsmear_val:
                props |= {"electronic_smearing": elsmear_val}
        for key, val in {
            "spin_polarization": "atom_spin_polarized",
            "electronic_energy_tolerance": "atom_el_e_tol_in_ev",
            "smearing_parameter_sigma": "atom_sigma_in_ev",
            "final_pressure": "atom_fin_press_in_gpa",
        }.items():
            if key in cdict:
                props[val] = cdict[key]
        if "final_total_magnetic_moment" in cdict.keys():
            props["atom_fin_totmgmo_in_mub"] = str(cdict["final_total_magnetic_moment"])
        if "dft" in concept_dict.keys():
            if "dof" in cdict.keys():
                description = (
                    f'{cdict["job_type"]} simulation using pyiron for energy minimization/structural optimization.'
                    + props["description_multiline"]
                )  # TODO double check correctness
                min_algo = _IONIC_MIN_ALGO_MAP.get(cdict["ionic_minimization_algorithm"])
                if min_algo:
                    props |= {
                        "atomistic_calc_type": "atom_calc_struc_opt",
                        "atom_ionic_min_algo": min_algo,
                        "description_multiline": description,
                    }
            if cdict.get("electronic_minimization_algorithm", "").lower() in [
                "normal",
                "fast",
                "veryfast",
            ]:
                elec_min_algo = "MIN_ALGO_RMM_DIIS"
                props |= {"atom_elec_min_algo": elec_min_algo}
            else:
                warnings.warn(
                    f"Electronic minimization algorithm for ALGO='{cdict.get('electronic_minimization_algorithm')}' not yet mapped."
                )

        if "kpoint_Monkhorst_Pack" in cdict.keys():
            props |= {
                "atom_kpoint_type": "KPOINTS_MP",
                "atomistic_n_kpt_x": int(cdict["kpoint_Monkhorst_Pack"].split()[0]),
                "atomistic_n_kpt_y": int(cdict["kpoint_Monkhorst_Pack"].split()[1]),
                "atomistic_n_kpt_z": int(cdict["kpoint_Monkhorst_Pack"].split()[2]),
            }

    else:
        print(
            "Neither structure_name nor job_name in the object conceptual dictionary. \
              OpenBIS properties most likely incomplete."
        )

    return props


def map_struct_to_ob(
    props, cdict, concept_dict, decimals: int = 2, max_num_atoms: int = 10
):
    from datetime import date

    props["date"] = str(date.today())
    props["location"] = "virtual"

    if "atoms" in concept_dict.keys():
        import numpy as np

        sorted_atoms = sorted(
            [
                atom
                for atom in concept_dict["atoms"]
                if atom["label"] != "total_number_atoms"
            ],
            key=lambda x: x["label"],
            reverse=True,
        )

        props["composition_desc"] = "ATOMIC_FRACTION"
        sorted_atoms = sorted_atoms[:max_num_atoms]
        for i, species in enumerate(sorted_atoms, 1):
            props[f"element_{i}"] = species["label"]
            props[f"element_{i}_at_percent"] = np.round(
                species["value"] * 100 / cdict["total_number_atoms"], decimals
            )
            props[f"element_{i}_number"] = species["value"]

    if "simulation_cell_lengths" in cdict.keys():
        dim_list = [
            float(x) for x in cdict["simulation_cell_lengths"].strip("[]").split(",")
        ]
        props["sample_dim"] = " x ".join([f"{x} A" for x in dim_list])
        # Simulation cell could be a supercell of the unit cell
        # props['unit_cell_lengths'] = cdict['simulation_cell_lengths'].strip('[]')

    if "simulation_cell_vectors" in cdict.keys():
        props["sim_cell_vectors"] = cdict["simulation_cell_vectors"]
    if "space_group_number" in cdict.keys():
        props["space_group"] = cdict[
            "space_group_number"
        ]  # INTEGER not CONTROLLEDVOCABULARY
    if "defects" in cdict.keys():
        props["defects"] = ", ".join(cdict["defects"]).title()
    if "comments" in cdict.keys():
        props["comments"] = cdict["comments"]


def dataset_job_h5(cdict, name_suffix="_0"):
    from datetime import datetime

    # TODO error handling if not job
    ds_props = {"$name": cdict["job_name"] + ".h5" + name_suffix}
    ds_type = "PYIRON_HDF5"

    return ds_type, ds_props


def dataset_atom_struct_h5(
    cdict, name_suffix: str = "_0", decimals: int = 2, max_num_atoms: int = 10
):
    # TODO error handling if not structure
    # !!! relies on concept_dict.py first adding chemical species info before anything else
    from datetime import date

    import numpy as np

    ds_props = {
        "$name": cdict["structure_name"] + ".h5" + name_suffix,
        "date": str(date.today()),
        "file_source": "pyiron",
    }

    from itertools import takewhile

    sorted_atoms = dict(
        sorted(
            takewhile(lambda item: item[0] != "total_number_atoms", cdict.items()),
            key=lambda x: x[0],
            reverse=True,
        )
    )
    items = list(sorted_atoms.items())[:max_num_atoms]
    for i, (species, count) in enumerate(items, 1):
        ds_props[f"element_{i}"] = species
        ds_props[f"element_{i}_at_percent"] = np.round(
            count * 100 / cdict["total_number_atoms"], decimals
        )
        ds_props[f"element_{i}_number"] = count

    ds_props["number_of_atoms"] = cdict["total_number_atoms"]
    ds_props["number_of_species"] = len(sorted_atoms.keys())
    ds_props["list_of_species"] = ", ".join(sorted_atoms.keys())
    if "simulation_cell_angles" in cdict.keys():
        ds_props["angle_alpha"], ds_props["angle_beta"], ds_props["angle_gamma"] = (
            ast.literal_eval(cdict["simulation_cell_angles"])
        )
    if "simulation_cell_lengths" in cdict.keys():
        ds_props["box_length_a"], ds_props["box_length_b"], ds_props["box_length_c"] = (
            ast.literal_eval(cdict["simulation_cell_lengths"])
        )
    if "space_group_number" in cdict.keys():
        ds_props["space_group"] = cdict["space_group_number"]

    ds_type = "CRYS-STRUCT_DATA"

    return ds_type, ds_props


def dataset_env_yml(cdict, name_suffix="_0"):
    # TODO error handling if not job
    ds_props = {
        "$name": cdict["job_name"] + "_environment.yml" + name_suffix,
        "env_tool": "conda",
    }
    ds_type = "COMP_ENV"

    return ds_type, ds_props


def dataset_cdict_jsonld(cdict, name_suffix="_0"):
    if "job_name" in cdict.keys():
        ds_props = {"$name": cdict["job_name"] + "_concept_dict.json" + name_suffix}
    elif "structure_name" in cdict.keys():
        ds_props = {
            "$name": cdict["structure_name"] + "_concept_dict.json" + name_suffix
        }
    else:
        raise KeyError(
            "Missing job_name or structure_name key missing in conceptual dictionary. Cannot upload."
        )
    ds_type = "PYIRON_CONCEPT_DICT_DATA"

    return ds_type, ds_props
