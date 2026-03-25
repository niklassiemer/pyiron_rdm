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
    f"{_ASMO}/CanonicalEnsemble": ("canonical ensemble", "TD_ENSEMBLE_ATOM_ENS.NVT"),
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

_SPACE_GROUP_MAP = {
    "Im-3m": "space_group.im-3m",
    "Fm-3m": "space_group.fm-3m",
    "P6_3/mmc": "space_group.p63_mmc",
}

_BRAVAIS_LATTICE_MAP = {
    "bcc": "body_center_cubic",
    "fcc": "face_center_cubic",
    "hcp": "hex_close_pack",
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


def map_cdict_to_ob(user_name, cdict, concept_dict):

    # concept_dict to be kicked out
    # cdict = flat concept_dict

    if "structure_name" in cdict.keys():
        json_file = cdict["path"] + cdict["structure_name"] + "_concept_dict.json"
        props = {}
    else:
        json_file = cdict["path"] + "_concept_dict.json"
        props = {"bam_username": user_name}

    with open(json_file, "r") as file:
        json_string = file.read()
    json_string = format_json_string(json_string)

    props |= {
        "conceptual_dictionary": json_string,
        "description": '<p><span style="color:hsl(240,75%,60%);">'
        + "<strong>Scroll down below other properties to view conceptual dictionary with ontological ids of selected properties and values.</strong></span>"
        + '<br>The conceptual dictionary is in JSON-LD format. Learn more about it <a href="https://www.w3.org/ns/json-ld/">here</a></p>',
    }
    description = props["description"]

    # TODO resolve whether we want to keep track of anything (from cdict) that didn't get used?

    if "workflow_manager" in cdict.keys():
        props["workflow_manager"] = cdict["workflow_manager"]

    # structure
    if "structure_name" in cdict.keys():
        props["$name"] = cdict["structure_name"]
        props["description"] = (
            "Crystal structure generated using pyiron." + props["description"]
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

        if "dof" in cdict.keys():
            props |= {
                "atom_cell_vol_relax": f"{_ASMO}/CellVolumeRelaxation" in cdict["dof"],
                "atom_cell_shp_relax": f"{_ASMO}/CellShapeRelaxation" in cdict["dof"],
                "atom_pos_relax": f"{_ASMO}/AtomicPositionRelaxation" in cdict["dof"],
            }
        if (
            "molecular_statics" in concept_dict.keys()
            and "minimization_algorithm" in cdict.keys()
        ):
            description = (
                f'{cdict["job_type"]} simulation using pyiron for energy minimization/structural optimization.'
                + props["description"]
            )  # TODO double check correctness
            min_algo = _MIN_ALGO_MAP.get(cdict["minimization_algorithm"])
            if min_algo is None:
                raise ValueError("Unknown minimization algorithm")
            props |= {
                "atomistic_calc_type": "atom_calc_struc_opt",
                "atom_ionic_min_algo": min_algo,
                "description": description,
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
                        + props["description"]
                    )
                    props["atom_md_ensemble"] = ensemble_code
                    break
            props |= {"atomistic_calc_type": "Atom_calc_md", "description": description}

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
            }.items():
                if key in cdict.keys():
                    props[val] = cdict[key]

        if (
            "job_type" in cdict.keys() and "Murn" in cdict["job_type"]
        ):  # TODO general way to do this? Put together
            props["description"] = (
                "Murnaghan job for structural optimization." + props["description"]
            )
        for key, val in {
            "strain_axes": "murn_strain_axes",
            "number_of_data_points": "murn_n_data_points",
            "volume_range": "murn_strainvol_range",
            "equilibrium_bulk_modulus": "atom_equil_k_mod_in_gpa",
            "equilibrium_total_energy": "atom_equil_toteng_in_ev",
            "equilibrium_volume": "atom_equil_vol_in_a3",
        }.items():
            if key in cdict.keys():
                props[val] = cdict[key]
        if "equation_of_state_fit" in cdict.keys():
            eos = cdict["equation_of_state_fit"]
            eos_val = _EOS_MAP.get(eos)
            if eos_val:
                props["murn_eqn_of_state"] = eos_val
                if eos == f"{_ASMO}/PolynomialFit":
                    props["murn_fit_eqn_order"] = cdict["fit_order"]  # TODO test this
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

        if "spin_polarization" in cdict.keys():
            props["atom_spin_polarized"] = cdict["spin_polarization"]
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
                    + props["description"]
                )  # TODO double check correctness
                min_algo = _IONIC_MIN_ALGO_MAP.get(cdict["ionic_minimization_algorithm"])
                if min_algo:
                    props |= {
                        "atomistic_calc_type": "atom_calc_struc_opt",
                        "atom_ionic_min_algo": min_algo,
                        "description": description,
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


def map_struct_to_ob(props, cdict, concept_dict):
    if "atoms" in concept_dict.keys():
        sorted_atoms = sorted(
            [
                atom
                for atom in concept_dict["atoms"]
                if atom["label"] != "total_number_atoms"
            ],
            key=lambda x: x["label"],
        )
        species = {i["label"]: i["value"] for i in sorted_atoms}
        props["chem_species_by_n_atoms"] = str(species)

    for key, val in {
        "total_number_atoms": "n_atoms_total",
        "simulation_cell_lengths": "sim_cell_lengths_in_a",
        "simulation_cell_vectors": "sim_cell_vectors",
        "simulation_cell_angles": "sim_cell_angles_in_deg",
        "simulation_cell_volume": "sim_cell_volume_in_a3",
        "crystal_orientation": "crystal_orientation",
        "lattice_parameter_a": "lattice_param_a_in_a",
        "lattice_parameter_b": "lattice_param_b_in_a",
        "lattice_parameter_c": "lattice_param_c_in_a",
        "lattice_parameter_c_over_a": "lattice_c_over_a",
        "lattice_angle_alpha": "lattice_angalpha_in_deg",
        "lattice_angle_beta": "lattice_angbeta_in_deg",
        "lattice_angle_gamma": "lattice_anggamma_in_deg",
        "lattice_volume": "lattice_volume_in_a3",
        "comments": "notes",
    }.items():
        if key in cdict.keys():
            props[val] = cdict[key]

    if "space_group" in cdict.keys():
        props["space_group"] = get_space_group_mapping(cdict["space_group"])
    if "bravais_lattice" in cdict.keys():
        props["bravais_lattice"] = get_bravais_lattice_mapping(cdict["bravais_lattice"])


def dataset_job_h5(cdict):
    from datetime import datetime

    # TODO error handling if not job
    ds_props = {
        "$name": cdict["job_name"] + ".h5",
        "production_date": datetime.strptime(
            cdict["job_starttime"], "%Y-%m-%d %H:%M:%S"
        )
        .date()
        .strftime("%Y-%m-%d"),
        "file_format": "HDF5",
    }
    ds_type = "PYIRON_JOB"

    return ds_type, ds_props


def dataset_atom_struct_h5(cdict):
    # TODO error handling if not structure
    ds_props = {
        "$name": cdict["structure_name"] + ".h5",
        "multi_mat_scale": "Electronic/Atomistic",
        "sw_compatibility": "ASE",
        "file_format": "HDF5",
    }
    ds_type = "MAT_SIM_STRUCTURE"

    return ds_type, ds_props


def dataset_env_yml(cdict):
    # TODO error handling if not job
    ds_props = {"$name": cdict["job_name"] + "_environment.yml", "env_tool": "conda"}
    ds_type = "COMP_ENV"

    return ds_type, ds_props


def dataset_cdict_jsonld(cdict):
    if "job_name" in cdict.keys():  # TODO could this just be 'name'?
        ds_props = {"$name": cdict["job_name"] + "_concept_dict.json"}
    elif "structure_name" in cdict.keys():
        ds_props = {"$name": cdict["structure_name"] + "_concept_dict.json"}
    else:
        raise KeyError(
            "Missing job_name or structure_name key missing in conceptual dictionary. Cannot upload."
        )
    ds_type = "ATTACHMENT"

    return ds_type, ds_props


def get_space_group_mapping(spg):
    result = _SPACE_GROUP_MAP.get(spg)
    if result is None:
        raise ValueError(f"Invalid space group '{spg}', maybe a formatting error?")
    return result


def get_bravais_lattice_mapping(bvl):
    result = _BRAVAIS_LATTICE_MAP.get(bvl)
    if result is None:
        raise ValueError(f"Invalid Bravais lattice '{bvl}', maybe a formatting error?")
    return result
