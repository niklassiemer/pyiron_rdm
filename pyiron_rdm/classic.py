import hashlib
import types
from dataclasses import dataclass

from pyiron_rdm import ob_OT_bam, ob_OT_sfb1394, ob_cfg_bam, ob_cfg_sfb1394


@dataclass
class InstancePlugin:
    """Plugin containing instance-specific configuration for an openBIS instance.

    To support a new openBIS instance, create an ``InstancePlugin`` with the
    appropriate *mapping* and *ot* modules and register it in
    :data:`SUPPORTED_INSTANCES`.

    Attributes:
        mapping: Module implementing the property-mapping interface
            (``map_cdict_to_ob``, ``map_struct_to_ob``, ``dataset_job_h5``,
            ``dataset_atom_struct_h5``, ``dataset_env_yml``,
            ``dataset_cdict_jsonld``).
        ot: Module implementing the object-type interface
            (``get_ot_info``, ``get_inv_parent``, ``validate_options``).
        requires_s3: Whether uploads to this instance require S3 storage.
    """

    mapping: types.ModuleType
    ot: types.ModuleType
    requires_s3: bool = False


SUPPORTED_INSTANCES = {
    "bam": InstancePlugin(
        mapping=ob_cfg_bam,
        ot=ob_OT_bam,
        requires_s3=False,
    ),
    "sfb1394": InstancePlugin(
        mapping=ob_cfg_sfb1394,
        ot=ob_OT_sfb1394,
        requires_s3=True,
    ),
}


def classic_structure(
    pr, structure, structure_name, options, is_init_struct: bool, init_structure=None
):
    # TODO rename is_init_struct and init_structure to better reflect that it needs to not be manipulated (e.g. repeated)
    structure_path = pr.path

    from pyiron_base.storage.hdfio import FileHDFio

    hdf = FileHDFio(structure_path + structure_name + ".h5")
    structure.to_hdf(hdf)
    with open(hdf.file_name, "rb", buffering=0) as f:
        hdf5_hash = hashlib.file_digest(f, "md5").hexdigest()

    from pyiron_rdm.concept_dict import (
        get_unit_cell_parameters,
        process_structure_crystal,
    )

    if is_init_struct:
        init_structure = structure
    if init_structure:
        try:
            struct_params = get_unit_cell_parameters(init_structure)
        except:
            struct_params = {}
    else:
        struct_params = {}
    struct_cdict = process_structure_crystal(
        path=pr.path,
        name=pr.name,
        structure=structure,
        structure_name=structure_name,
        structure_path=structure_path,
        structure_parameters=struct_params,
        options=options,
        md5hash=hdf5_hash,
    )

    return struct_cdict


def classic_general_job(job, export_env_file: bool):
    from pyiron_rdm.concept_dict import process_general_job

    if export_env_file:
        from pyiron_rdm.concept_dict import export_env

        export_env(job.path)

    job_cdict = process_general_job(job)
    return job_cdict


def classic_lammps(lammps_job, export_env_file):
    """export_env_file: Bool"""
    from pyiron_rdm.concept_dict import process_lammps_job

    if export_env_file:
        from pyiron_rdm.concept_dict import export_env

        export_env(lammps_job.path)

    lammps_cdict = process_lammps_job(lammps_job)
    return lammps_cdict


def classic_vasp(vasp_job, export_env_file):
    """export_env_file: Bool"""
    from pyiron_rdm.concept_dict import process_vasp_job

    if export_env_file:
        from pyiron_rdm.concept_dict import export_env

        export_env(vasp_job.path)

    vasp_cdict = process_vasp_job(vasp_job)
    return vasp_cdict


def classic_murn(murn_job, export_env_file):
    # TODO this assumes only lammps child jobs - generalise!
    """export_env_file: Bool"""

    if export_env_file:
        import shutil

        from pyiron_rdm.concept_dict import export_env

        export_env(murn_job.path)

    from pyiron_rdm.concept_dict import (
        process_general_job,
        process_lammps_job,
        process_murnaghan_job,
        process_vasp_job,
    )

    _child_job_processors = [
        ("lammps", process_lammps_job),
        ("vasp", process_vasp_job),
    ]

    child_jobs_cdict = []
    for job in murn_job.iter_jobs():
        if export_env_file:
            shutil.copy(
                murn_job.path + "_environment.yml", job.path + "_environment.yml"
            )
        job_type = job.to_dict()["TYPE"]
        for pattern, processor in _child_job_processors:
            if pattern in job_type:
                child_cdict = processor(job)
                break
        else:
            raise ValueError(
                f"Child job type {job_type!r} is not supported in Murnaghan workflow."
                " Supported child job types: "
                + ", ".join(p for p, _ in _child_job_processors)
                + "."
            )
        child_jobs_cdict.append(child_cdict)

    job_cdict = process_murnaghan_job(murn_job)

    return job_cdict, child_jobs_cdict


def classic_murn_equil_structure(
    murn_job, options, is_init_struct: bool = True, init_structure=None
):

    if is_init_struct:
        init_structure = murn_job.structure
    equil_structure = murn_job.get_structure()
    structure_name = murn_job.name + "_equilibrium_structure"
    struct_cdict = classic_structure(
        pr=murn_job.project,
        structure=equil_structure,
        structure_name=structure_name,
        options=options,
        is_init_struct=is_init_struct,
        init_structure=init_structure,
    )

    return struct_cdict


def get_datamodel(o):
    # TODO: adapt to also take url to use for openbis_login ?
    datamodels = {"bam": "bam", "imm.rwth": "sfb1394"}
    for key in datamodels:
        if key in o.hostname:
            return datamodels[key]
    raise KeyError(
        f"The {o.hostname} openBIS hostname is not paired with a supported data model yet ({datamodels.values()})."
    )


def validate_upload_options(ot, options: dict):
    ot.validate_options(**options)

    if "materials" in options and not isinstance(options["materials"], list):
        options["materials"] = [options["materials"]]
    if "pseudopotentials" in options and not isinstance(
        options["pseudopotentials"], list
    ):
        options["pseudopotentials"] = [options["pseudopotentials"]]
    return options


def openbis_login(
    url, username=None, password=None, token=None, instance="bam", s3_config_path=None
):
    if instance not in SUPPORTED_INSTANCES:
        raise ValueError(
            f"This script only supports upload to {list(SUPPORTED_INSTANCES.keys())} instances,"
            f" {instance!r} not supported."
        )

    instance_cfg = SUPPORTED_INSTANCES[instance]
    if instance_cfg.requires_s3 and not s3_config_path:
        raise ValueError(
            f"s3_config_path must be provided when uploading to {instance!r} instance."
        )
    if not instance_cfg.requires_s3:
        s3_config_path = None

    from pyiron_rdm.ob_upload import openbis_login as ob_login

    o = ob_login(
        url=url,
        username=username,
        password=password,
        token=token,
        s3_config_path=s3_config_path,
        plugin=instance_cfg,
    )
    return o


def get_cdicts_to_validate(
    job,
    options: dict | None = None,
    export_env_file: bool = True,
    is_init_struct: bool = True,
    init_structure=None,
    upload_final_struct: bool = True,
):
    if options is None:
        options = {}
    cdicts_to_validate = {}

    struct_dict = classic_structure(
        pr=job.project,
        structure=job.structure,
        structure_name=job.name + "_structure",
        options=options,
        is_init_struct=is_init_struct,
        init_structure=init_structure,
    )
    cdicts_to_validate["structure"] = struct_dict

    job_type = job.to_dict()["TYPE"]

    _simple_job_handlers = [
        ("lammps", classic_lammps),
        ("vasp", classic_vasp),
    ]

    job_handler = next(
        (handler for pattern, handler in _simple_job_handlers if pattern in job_type),
        None,
    )

    if job_handler is not None:
        cdicts_to_validate["job"] = job_handler(job, export_env_file=export_env_file)

    elif "murn" in job_type:
        job_cdict, child_jobs_cdict = classic_murn(job, export_env_file=export_env_file)
        equil_struct_dict = classic_murn_equil_structure(
            job, options, is_init_struct, init_structure
        )
        cdicts_to_validate["job"] = job_cdict
        cdicts_to_validate["equilibrium_structure"] = equil_struct_dict
        cdicts_to_validate.update(
            {
                f"child_job_{n}": child_cdict
                for n, child_cdict in enumerate(child_jobs_cdict)
            }
        )

    else:
        print(f"The {job_type} job type is not implemented for OpenBIS upload yet.")
        proceed = input(
            "Type 'yes' to proceed with an upload to general pyiron job type."
        )
        if proceed.lower() == "yes" or proceed.lower() == "y":
            job_cdict = classic_general_job(job, export_env_file=export_env_file)
            cdicts_to_validate["job"] = job_cdict
        else:
            raise ValueError("Aborted")

    if upload_final_struct and (not "murn" in job.to_dict()["TYPE"]):
        if is_init_struct:
            init_structure = job.structure
        final_structure = job.get_structure()
        final_struct_dict = classic_structure(
            job.project,
            final_structure,
            structure_name=job.name + "_final_structure",
            options=options,
            is_init_struct=False,
            init_structure=init_structure,
        )
        cdicts_to_validate["final_structure"] = final_struct_dict
    return cdicts_to_validate


def create_concept_dicts(
    job,
    o,
    export_env_file: bool = True,
    is_init_struct: bool = True,
    init_structure=None,
    options: dict | None = None,
):
    # TODO should this return anything?
    if options is not None:
        options = validate_upload_options(o.plugin.ot, options)
    else:
        options = {}

    structure = job.structure
    if not structure:
        print("This job does not contain a structure and will not be uploaded. \
                Please add structure before trying to upload.")
        return

    # Project env file - TODO what is this for??
    pr = job.project
    if export_env_file:
        from pyiron_rdm.concept_dict import export_env

        export_env(pr.path + pr.name)

    # ------------------------------------VALIDATION----------------------------------------------
    is_sfb = get_datamodel(o) == "sfb1394"

    cdicts_to_validate = get_cdicts_to_validate(
        job=job,
        options=options,
        export_env_file=export_env_file,
        is_init_struct=is_init_struct,
        init_structure=init_structure,
        upload_final_struct=is_sfb,
    )

    return cdicts_to_validate


def validate_openbis_destination(o, space: str, project: str, collection: str):
    from pyiron_rdm.ob_upload import validate_ob_destination

    space = space.upper()
    project = project.upper()
    collection = collection.upper()

    validate_ob_destination(o=o, space=space, project=project, collection=collection)
    return space, project, collection


def validate_concept_dicts(
    cdicts_to_validate: list[dict],
    o,
    options: dict | None = None,
    require_parents: bool = True,
):

    from pyiron_rdm.ob_upload import openbis_validate

    options = options if options is not None else {}

    validated_to_upload = openbis_validate(
        o=o,
        concept_dicts=cdicts_to_validate,
        options=options,
        require_parents=require_parents,
    )

    return validated_to_upload
    # ---------------------------------------------------------------------------------------------


def upload_cdicts_to_openbis(
    validated_to_upload: list[dict],
    o,
    space: str,
    project: str,
    collection: str | None = None,
):

    # --------------------------------------UPLOAD-------------------------------------------------
    from pyiron_rdm.ob_upload import openbis_upload_validated

    ob_structure_id = openbis_upload_validated(
        o=o,
        space=space,
        project=project,
        collection=collection,
        **validated_to_upload["structure"],
    )

    is_sfb = get_datamodel(o) == "sfb1394"
    if is_sfb:
        job_parents = None  # job does not have init structure as parent
        str_parent = ob_structure_id  # equil structure has init as parent
    else:
        job_parents = ob_structure_id  # job has init structure as parent
        str_parent = None  # equil structure does not have init as parent

    ob_job_id = openbis_upload_validated(
        o=o,
        space=space,
        project=project,
        collection=collection,
        **validated_to_upload["job"],
        parent_ids=job_parents,
    )

    if "equilibrium_structure" in validated_to_upload:
        ob_children_ids = []
        ob_equil_struct_id = openbis_upload_validated(
            o=o,
            space=space,
            project=project,
            collection=collection,
            **validated_to_upload["equilibrium_structure"],
            parent_ids=str_parent,
        )
        ob_children_ids.append(ob_equil_struct_id)
        for validated_child in [
            validated_to_upload[key]
            for key in validated_to_upload
            if key.startswith("child_job")
        ]:
            ob_child_id = openbis_upload_validated(
                o=o,
                space=space,
                project=project,
                collection=collection,
                **validated_child,
                parent_ids=str_parent,
            )
            ob_children_ids.append(ob_child_id)
        from pyiron_rdm.ob_upload import link_children

        link_children(o, ob_job_id, ob_children_ids)

    elif "final_structure" in validated_to_upload:
        ob_final_structure_id = openbis_upload_validated(
            o=o,
            space=space,
            project=project,
            collection=collection,
            **validated_to_upload["final_structure"],
            parent_ids=[ob_structure_id, ob_job_id],
        )


def upload_classic_pyiron(
    job,
    o,
    space: str,
    project: str,
    collection: str | None = None,
    export_env_file: bool = True,
    is_init_struct: bool = True,
    init_structure=None,
    options: dict | None = None,
    require_parents: bool = True,
):
    # Create JSON-LD conceptual dictionaries for the job
    cdicts_to_validate = create_concept_dicts(
        job,
        o,
        export_env_file=export_env_file,
        is_init_struct=is_init_struct,
        init_structure=init_structure,
        options=options,
    )

    # Set sensible default if collection is not given
    if collection is None:
        collection = job.pr.name

    # Validate openbis destination
    space, project, collection = validate_openbis_destination(
        o, space=space, project=project, collection=collection
    )

    # Validate conceptual dictionary compatibility to openBIS instance
    validated_to_upload = validate_concept_dicts(
        cdicts_to_validate=cdicts_to_validate,
        o=o,
        options=options,
        require_parents=require_parents,
    )

    upload_cdicts_to_openbis(
        validated_to_upload=validated_to_upload,
        o=o,
        space=space,
        project=project,
        collection=collection,
    )
