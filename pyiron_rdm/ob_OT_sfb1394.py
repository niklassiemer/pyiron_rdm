# inventory parents _________________________________________


def material_par(props_dict: dict, options: dict):
    if options.get("materials"):
        object_type = "CRYSTALLINE_MATERIAL"
        permid_materials = options["materials"]
        where_clause = {}
        requested_attrs = []
    else:
        mat_dict_pct_str = species_by_num_to_pct(props_dict)
        object_type = "MATERIAL"
        permid_materials = ""
        where_clause = {"compo_atomic_percent": mat_dict_pct_str}
        requested_attrs = ["compo_atomic_percent"]
        # could output a warning here to provide a crystalline_material permId
    return object_type, permid_materials, where_clause, requested_attrs


def interatomicpot_par(cdict):
    object_type = "INTERATOMIC_POTENTIAL"
    where_clause = {"external_identifier": cdict["potential"]}
    requested_attrs = ["external_identifier"]
    return object_type, where_clause, requested_attrs


def workstation_par(cdict):
    object_type = "COMPUTE_RESOURCE"
    object_code = "*" + cdict["host"]
    return object_type, object_code


def pseudopot_par(options):
    object_type = "PSEUDOPOTENTIAL"
    permid_pseudopots = options.get("pseudopotentials", "")
    return object_type, permid_pseudopots


def software_par(cdict):
    import re

    pseudopot_par = "SOFTWARE"
    c = re.sub(r"[\s\-_.]", "", cdict["software"])  # remove special characters
    c_match = re.match(r"([A-Za-z]*\d+)", c)  # remove letters after last digit
    object_code = c_match.group(1) if c_match else c
    return pseudopot_par, object_code


# object types _______________________________________________


def struct_ot():
    object_type = "SAMPLE"
    datasets = ["structure_h5", "cdict_json"]
    parents = ["material"]
    return object_type, datasets, parents


def pyiron_job_ot():
    object_type = "PYIRON_JOB_GENERIC"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["workstation"]
    return object_type, datasets, parents


def lammps_job_ot():
    object_type = "PYIRON_JOB_LAMMPS"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["interatomic_potential", "software", "workstation"]
    return object_type, datasets, parents


def vasp_job_ot():
    object_type = "PYIRON_JOB_VASP"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["pseudopotential", "software", "workstation"]
    return object_type, datasets, parents


def murn_job_ot():
    object_type = "PYIRON_JOB_MURNAGHAN"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["workstation"]
    return object_type, datasets, parents


# calls ______________________________________________________

_JOB_TYPE_OT_MAP = [
    ("lammps", lammps_job_ot),
    ("vasp", vasp_job_ot),
    ("murn", murn_job_ot),
]


def get_ot_info(cdict):
    if "structure_name" in cdict.keys():
        return struct_ot()
    elif "job_type" in cdict.keys():
        job_type = cdict["job_type"].lower()
        for pattern, ot_func in _JOB_TYPE_OT_MAP:
            if pattern in job_type:
                return ot_func()
        return pyiron_job_ot()
    else:
        raise ValueError(
            "Neither structure_name nor job_type in conceptual dictionary. Cannot proceed."
        )


def _inv_parent_material(cdict, props_dict, options):
    ob_type, permids, where_clause, requested_attrs = material_par(props_dict, options)
    return ob_type, permids, where_clause, requested_attrs, ""


def _inv_parent_workstation(cdict, props_dict, options):
    ob_type, ob_code = workstation_par(cdict)
    return ob_type, "", {}, [], ob_code


def _inv_parent_software(cdict, props_dict, options):
    ob_type, ob_code = software_par(cdict)
    return ob_type, "", {}, [], ob_code


def _inv_parent_interatomic_potential(cdict, props_dict, options):
    ob_type, where_clause, requested_attrs = interatomicpot_par(cdict)
    return ob_type, "", where_clause, requested_attrs, ""


def _inv_parent_pseudopotential(cdict, props_dict, options):
    ob_type, permids = pseudopot_par(options)
    return ob_type, permids, {}, [], ""


_PARENT_HANDLERS = {
    "material": _inv_parent_material,
    "workstation": _inv_parent_workstation,
    "software": _inv_parent_software,
    "interatomic_potential": _inv_parent_interatomic_potential,
    "pseudopotential": _inv_parent_pseudopotential,
}


def get_inv_parent(parent_name, cdict, props_dict: dict, options: dict):
    handler = _PARENT_HANDLERS.get(parent_name)
    if handler:
        return handler(cdict, props_dict, options)
    return "", "", {}, [], ""


# upload options ______________________________________________
def validate_options(
    materials: str | list[str] | None = None,
    defects: list[str] | None = None,
    pseudopotentials: str | list[str] | None = None,
    comments: str | None = None,
):
    """
    Validates the options dictionary for supported keys and values.

    Args:
        materials (str | list[str] | None): Material permId(s) or None.
        defects (list[str] | None): List of defect types or None.
        pseudopotentials (str | list[str] | None): Pseudopotential permId(s) or None.
        comments (str | None): Comments string or None.

    Raises:
        TypeError: If the value associated with the "defects" key is not a list of strings.
        ValueError: If invalid defect types are found in the "defects" list.
    """
    allowed_defects = {
        "vacancy",
        "antisite",
        "substitutional",
        "interstitial",
        "perfect dislocation",
        "partial dislocation",
        "superdislocation",
        "stacking fault",
        "grain boundary",
        "surface",
        "phase boundary",
    }
    if defects is not None:
        if not isinstance(defects, list) or not all(
            isinstance(d, str) for d in defects
        ):
            raise TypeError("defects must be a list of strings.")
        invalid_defects = (
            set([d.lower().replace("_", " ") for d in defects]) - allowed_defects
        )
        if invalid_defects:
            raise ValueError(
                f'Invalid defect(s) in "defects": {sorted(invalid_defects)}. \
                Allowed defects are: {sorted(allowed_defects)}'
            )


# else ________________________________________________________


def species_by_num_to_pct(props: dict, max_elements: int = 10):
    species_by_pct = {
        props[f"element_{i}"]: float(props[f"element_{i}_at_percent"])
        for i in range(1, max_elements + 1)
        if f"element_{i}" in props and f"element_{i}_at_percent" in props
    }
    return str(species_by_pct)


def pseudopotential_suggester(o, structure, **kwargs):
    """
    defaults:
        'PSEUDOPOT_TYPE': 'PSEUDOPOT_PAW'
        'PSEUDOPOT_FUNC': 'PSEUDOPOT_GGA'
        'SOFTWARE_COMPATIBILITY': 'VASP'
    """
    import pandas as pd

    chem_species = list(structure.get_species_symbols())
    defaults = {
        "PSEUDOPOT_TYPE": "PSEUDOPOT_PAW",
        "PSEUDOPOT_FUNC": "PSEUDOPOT_GGA",
        "SOFTWARE_COMPATIBILITY": "VASP",
    }
    suggestions = []
    for chem_sp in chem_species:
        suggestions.append(
            o.get_objects(
                type="PSEUDOPOTENTIAL",
                where={**defaults, **kwargs, "CHEM_SPECIES_ADDRESSED": chem_sp},
                props=["$name", "PSEUDOPOT_VERSION", "CHEM_SPECIES_ADDRESSED"]
                + list(defaults.keys()),
            ).df
        )
    if suggestions:
        suggestions = pd.concat(suggestions, ignore_index=True)

        # Add and then drop temporary datetime column for sorting
        suggestions["_PSEUDO_DATE"] = pd.to_datetime(
            suggestions["PSEUDOPOT_VERSION"], format="%d%b%Y", errors="coerce"
        )
        suggestions = suggestions.sort_values(by="_PSEUDO_DATE", ascending=False).drop(
            columns=["_PSEUDO_DATE"]
        )
        return suggestions
    return


def slow_pseudopotential_matcher(
    o, job
):  # could also take job['POTCAR'] instead? In case already loaded somewhere?
    potcar = job["POTCAR"]
    paw_lines = [
        line.strip().replace(" ", "_").upper() for line in potcar if "PAW" in line
    ]
    return o.get_objects(type="PSEUDOPOTENTIAL", code=paw_lines)


def get_atomic_percent_dict(species_dict: dict):
    total_atoms = sum(species_dict.values())
    atomic_pct_dict = {
        k: species_dict[k] / total_atoms * 100 for k in sorted(species_dict.keys())
    }
    return atomic_pct_dict


def is_within_tolerance(reference: dict, candidate: dict, tol: float):
    for species, ref_val in reference.items():
        cand_val = candidate.get(species, 0.0)
        if abs(ref_val - cand_val) > tol * 100:
            return False
    return True


def get_subsystems(chemsys: str) -> list:
    import itertools

    elements = chemsys.split("-")
    elements.sort()
    all_combinations = []
    for r in range(1, 1 + len(elements)):
        combinations = itertools.combinations(elements, r)
        all_combinations.extend(combinations)
    return ["-".join(combination) for combination in all_combinations]


def crystalline_material_suggester(
    o,
    structure,
    tol: float = 0.02,
    space_group_number: int | None = None,
    match_subcomposition: bool = False,
    openbis_kwargs: dict | None = None,
):
    """Suggests a list of crystalline materials from the openBIS inventory for a structure of interest.

    Args:
        o (pybis.Openbis): The openBIS session object used to query crystalline materials.
        structure (Atoms | str): The structure for which to find materials in the openBIS instance.
        tol (float): Tolerance factor for matching chemical composition.
            Materials are accepted if the absolute difference in atomic percentage for each element between
            the candidate and reference structure is less than `100 * tol`. For example, a `tol` of 0.01 (or 1%)
            means atomic percentages must be within +/- 1% of the reference.
        space_group (int, optional): The space group number to filter materials by. Defaults to None.
        match_subcomposition (bool, optional): Whether to search for materials for each subsystem based on their
            composition and tolerance. Defaults to False.
        openbis_kwargs (dict, optional): Expert feature. A dictionary of openBIS-specific codes and their values
            to apply additional filtering. Defaults to None.
    Returns:
        pybis.things.Things: An openBIS query result object. The data can be accessed as a pandas DataFrame via
            `.df` attribute.
    """

    openbis_kwargs = openbis_kwargs if openbis_kwargs is not None else {}

    if isinstance(structure, str):
        try:
            from ase import Atoms

            structure = Atoms(structure)
        except ImportError:
            raise ImportError(
                "For the parsing of structure like strings, ase needs to be installed."
            )

    chem_system = "-".join(sorted(set(structure.get_chemical_symbols())))

    # atomic composition of structure
    species_dict = dict()
    for i in structure.get_chemical_symbols():
        species_dict[i] = species_dict.get(i, 0) + 1
    atomic_pct_dict = get_atomic_percent_dict(species_dict)

    # matching candidates from openBIS
    candidates = []
    for chemical_system in get_subsystems(chem_system):
        where_dict = {
            "CHEMICAL_SYSTEM": chemical_system,
        }
        prop_list = list(openbis_kwargs.keys()) + ["CHEMICAL_SYSTEM"]
        if space_group_number is not None:
            where_dict["SPACE_GROUP_SHORT"] = "SPACE_GROUP_" + str(space_group_number)
            prop_list += ["SPACE_GROUP_SHORT"]
        candidates += o.get_objects(
            type="CRYSTALLINE_MATERIAL", where=where_dict, props=prop_list
        )

    # define properties to display
    props = (
        o.get_object_type("CRYSTALLINE_MATERIAL")
        .get_property_assignments()
        .df.code.to_list()
    )
    props.remove("COMMENTS")
    props.remove("STRUCTURE_ANIMATION")

    # candidates filtered by atomic composition
    filtered = []
    for candidate in candidates:
        atomic_pct = candidate.p.compo_atomic_percent
        if not atomic_pct:
            continue
        from ast import literal_eval

        candidate_atomic_pct = literal_eval(atomic_pct)
        subsystem_pct_dict = atomic_pct_dict.copy()

        if match_subcomposition:
            subsystem_pct_dict = get_atomic_percent_dict(
                {k: atomic_pct_dict[k] for k in candidate_atomic_pct}
            )
        if is_within_tolerance(subsystem_pct_dict, candidate_atomic_pct, tol):
            filtered.append(candidate.permId)

    ob_objects = o.get_objects(permId=filtered, props=props)
    return ob_objects
