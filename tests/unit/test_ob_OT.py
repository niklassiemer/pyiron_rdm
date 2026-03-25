import unittest

from pyiron_rdm import ob_OT_bam, ob_OT_sfb1394, ob_cfg_bam, ob_cfg_sfb1394
from pyiron_rdm.classic import InstancePlugin, SUPPORTED_INSTANCES, validate_upload_options


class TestObOT(unittest.TestCase):
    def test_validate_options(self):
        with self.assertRaises(TypeError):
            ob_OT_bam.validate_options(**{"my_key": 123})
        with self.assertRaises(TypeError):
            ob_OT_sfb1394.validate_options(**{"my_key": 123})
        self.assertIsNone(
            ob_OT_bam.validate_options(**{"materials": "abc", "comments": "hello"})
        )
        self.assertIsNone(
            ob_OT_sfb1394.validate_options(**{"materials": "abc", "comments": "hello"})
        )
        with self.assertRaises(TypeError):
            ob_OT_sfb1394.validate_options(**{"defects": 123})
        with self.assertRaises(ValueError):
            ob_OT_sfb1394.validate_options(**{"defects": ["hello"]})
        self.assertIsNone(ob_OT_sfb1394.validate_options(**{"defects": ["surface"]}))


class TestInstancePlugin(unittest.TestCase):
    def test_supported_instances_are_plugins(self):
        for name, plugin in SUPPORTED_INSTANCES.items():
            self.assertIsInstance(plugin, InstancePlugin, msg=f"{name} is not an InstancePlugin")

    def test_bam_plugin_modules(self):
        plugin = SUPPORTED_INSTANCES["bam"]
        self.assertIs(plugin.mapping, ob_cfg_bam)
        self.assertIs(plugin.ot, ob_OT_bam)
        self.assertFalse(plugin.requires_s3)

    def test_sfb1394_plugin_modules(self):
        plugin = SUPPORTED_INSTANCES["sfb1394"]
        self.assertIs(plugin.mapping, ob_cfg_sfb1394)
        self.assertIs(plugin.ot, ob_OT_sfb1394)
        self.assertTrue(plugin.requires_s3)

    def test_plugin_mapping_interface(self):
        required_methods = [
            "map_cdict_to_ob",
            "dataset_job_h5",
            "dataset_atom_struct_h5",
            "dataset_env_yml",
            "dataset_cdict_jsonld",
        ]
        for name, plugin in SUPPORTED_INSTANCES.items():
            for method in required_methods:
                self.assertTrue(
                    hasattr(plugin.mapping, method),
                    msg=f"mapping for {name!r} is missing method {method!r}",
                )

    def test_plugin_ot_interface(self):
        required_methods = ["get_ot_info", "get_inv_parent", "validate_options"]
        for name, plugin in SUPPORTED_INSTANCES.items():
            for method in required_methods:
                self.assertTrue(
                    hasattr(plugin.ot, method),
                    msg=f"ot for {name!r} is missing method {method!r}",
                )

    def test_validate_upload_options_uses_module(self):
        # validate_upload_options now takes a module object directly, not a string.
        # Confirm that the module's validate_options is called: unknown kwargs
        # raise TypeError in both BAM and SFB OT modules.
        with self.assertRaises(TypeError):
            validate_upload_options(ob_OT_bam, {"unknown_key": "value"})
        with self.assertRaises(TypeError):
            validate_upload_options(ob_OT_sfb1394, {"unknown_key": "value"})

        # Valid options pass through and are normalised (list-wrapping)
        result = validate_upload_options(ob_OT_bam, {"materials": "abc"})
        self.assertEqual(result["materials"], ["abc"])

        # Instance-specific validation is invoked: invalid defect raises ValueError
        with self.assertRaises(ValueError):
            validate_upload_options(ob_OT_sfb1394, {"defects": ["not_a_real_defect"]})


if __name__ == "__main__":
    unittest.main()
