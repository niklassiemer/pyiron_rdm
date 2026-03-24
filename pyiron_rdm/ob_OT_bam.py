# inventory parents _________________________________________


def material_par(props_dict, options):
    object_type = "MATERIAL_V1"
    if options.get("materials"):
        permid_materials = options["materials"]
        where_clause = {}
        requested_attrs = []
    else:
        mat_dict_pct_str = species_by_num_to_pct(props_dict)
        where_clause = {"chem_species_by_comp_in_pct": mat_dict_pct_str}
        requested_attrs = ["chem_species_by_comp_in_pct"]
        permid_materials = ""
    return object_type, permid_materials, where_clause, requested_attrs


def intpot_par(cdict):
    object_type = "INTERATOMIC_POTENTIAL"
    where_clause = {"$name": cdict["potential"]}
    requested_attrs = ["$name"]
    return object_type, where_clause, requested_attrs


def pseudopot_par(options):
    object_type = "PSEUDOPOTENTIAL"
    permid_pseudopots = options.get("pseudopotentials", "")
    return object_type, permid_pseudopots


def sw_par(cdict):
    import re

    object_type = "SOFTWARE_CODE"
    c = cdict["software"].replace(" ", "_")
    c_match = re.match(
        r"^(.*\d)(?=[^\d]*[a-zA-Z])", c
    )  # match up to and incl. first set of numbers
    object_code = c_match.group(1) if c_match else c
    return object_type, object_code


def compresource_par(cdict):
    object_type = "INSTRUMENT.*"  # careful - main BAM has HPC, not INSTRUMENT.HPC
    object_code = "*" + cdict["host"].upper()
    return object_type, object_code


def wfref_par(cdict):
    object_type = "WORKFLOW_REFERENCE"
    if "murn" in cdict["job_type"].lower():
        object_code = "EQ_OF_STATE_FITTING"
    else:
        object_code = ""
    return object_type, object_code


# object types _______________________________________________


def crystal_struct_ot():
    object_type = "MAT_SIM_STRUCTURE.CRYSTAL"
    datasets = ["structure_h5", "cdict_json"]
    parents = ["material"]
    return object_type, datasets, parents


def pyiron_job_ot():
    object_type = "PYIRON_JOB"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["compute_resource"]
    return object_type, datasets, parents


def lammps_job_ot():
    object_type = "PYIRON_JOB.LAMMPS"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["interatomic_potential", "software", "compute_resource"]
    return object_type, datasets, parents


def vasp_job_ot():
    object_type = "PYIRON_JOB.VASP"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["pseudopotential", "software", "compute_resource"]
    return object_type, datasets, parents


def murn_job_ot():
    object_type = "PYIRON_JOB.MURNAGHAN"
    datasets = ["job_h5", "env_yml", "cdict_json"]
    parents = ["wf_reference", "compute_resource"]
    return object_type, datasets, parents


# calls ______________________________________________________

_JOB_TYPE_OT_MAP = [
    ("lammps", lammps_job_ot),
    ("vasp", vasp_job_ot),
    ("murn", murn_job_ot),
]


def get_ot_info(cdict):
    if "structure_name" in cdict.keys():
        return crystal_struct_ot()
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


def _inv_parent_compute_resource(cdict, props_dict, options):
    ob_type, ob_code = compresource_par(cdict)
    return ob_type, "", {}, [], ob_code


def _inv_parent_software(cdict, props_dict, options):
    ob_type, ob_code = sw_par(cdict)
    return ob_type, "", {}, [], ob_code


def _inv_parent_interatomic_potential(cdict, props_dict, options):
    ob_type, where_clause, requested_attrs = intpot_par(cdict)
    return ob_type, "", where_clause, requested_attrs, ""


def _inv_parent_pseudopotential(cdict, props_dict, options):
    ob_type, permids = pseudopot_par(options)
    return ob_type, permids, {}, [], ""


def _inv_parent_wf_reference(cdict, props_dict, options):
    ob_type, ob_code = wfref_par(cdict)
    return ob_type, "", {}, [], ob_code


_PARENT_HANDLERS = {
    "material": _inv_parent_material,
    "compute_resource": _inv_parent_compute_resource,
    "software": _inv_parent_software,
    "interatomic_potential": _inv_parent_interatomic_potential,
    "pseudopotential": _inv_parent_pseudopotential,
    "wf_reference": _inv_parent_wf_reference,
}


def get_inv_parent(parent_name, cdict, props_dict, options):
    handler = _PARENT_HANDLERS.get(parent_name)
    if handler:
        return handler(cdict, props_dict, options)
    return "", "", {}, [], ""


# upload options ______________________________________________


def validate_options(
    materials: str | list[str] | None = None,
    pseudopotentials: str | list[str] | None = None,
    comments: str | None = None,
):
    """
    Validates the options dictionary for supported keys and values.

    Args:
        materials (str | list[str] | None): Material permId(s) or None.
        pseudopotentials (str | list[str] | None): Pseudopotential permId(s) or None.
        comments (str | None): Comments string or None.
    """
    pass


# else ________________________________________________________


def species_by_num_to_pct(props):
    import numpy as np

    species_by_num = eval(props["chem_species_by_n_atoms"])
    species_by_pct = {
        at: float(np.round(species_by_num[at] * 100 / props["n_atoms_total"], 2))
        for at in species_by_num.keys()
    }
    return str(species_by_pct)


def pseudopotential_suggester(o, structure, **kwargs):
    """
    defaults:
        'PSEUDOPOT_TYPE': 'PSEUDOPOT_PAW'
        'PSEUDOPOT_FUNC': 'PSEUDOPOT_GGA'
        'SW_COMPATIBILITY': 'VASP'
    """
    import pandas as pd

    chem_species = list(structure.get_species_symbols())
    defaults = {
        "PSEUDOPOT_TYPE": "PSEUDOPOT_PAW",
        "PSEUDOPOT_FUNC": "PSEUDOPOT_GGA",
        "SW_COMPATIBILITY": "VASP",
    }
    suggestions = []
    for chem_sp in chem_species:
        suggestions.append(
            o.get_objects(
                type="PSEUDOPOTENTIAL",
                where={**defaults, **kwargs, "CHEM_SPECIES_ADDRESSED": chem_sp},
                props=["$name", "VERSION", "CHEM_SPECIES_ADDRESSED"]
                + list(defaults.keys()),
            ).df
        )
    if suggestions:
        suggestions = pd.concat(suggestions, ignore_index=True)

        # Add and then drop temporary datetime column for sorting
        suggestions["_PSEUDO_DATE"] = pd.to_datetime(
            suggestions["VERSION"], format="%d%b%Y", errors="coerce"
        )
        suggestions = suggestions.sort_values(by="_PSEUDO_DATE", ascending=False).drop(
            columns=["_PSEUDO_DATE"]
        )
        return suggestions
    return


# this is the exact same as SFB !
def slow_pseudopotential_suggester(
    o, job
):  # could also take job['POTCAR'] instead? In case already loaded somewhere?
    potcar = job["POTCAR"]
    paw_lines = [
        line.strip().replace(" ", "_").upper() for line in potcar if "PAW" in line
    ]
    return o.get_objects(type="PSEUDOPOTENTIAL", code=paw_lines)
