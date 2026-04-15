import unittest


class RuntimeExportsTest(unittest.TestCase):
    def test_runtime_package_only_exports_run_entry(self) -> None:
        import core.runtime as runtime

        self.assertEqual(runtime.__all__, ["run"])
        self.assertFalse(hasattr(runtime, "AutomationEngine"))
        self.assertFalse(hasattr(runtime, "setup_logging"))
        run = runtime.run
        self.assertTrue(callable(run))


if __name__ == "__main__":
    unittest.main()
