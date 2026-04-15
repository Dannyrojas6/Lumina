import unittest


class RuntimeHandlersTest(unittest.TestCase):
    def test_runtime_handlers_package_exposes_expected_handler_classes(self) -> None:
        from core.runtime.handlers import (
            BattleReadyHandler,
            BattleResultHandler,
            CardSelectHandler,
            DialogHandler,
            LoadingHandler,
            MainMenuHandler,
            SupportSelectHandler,
            TeamConfirmHandler,
            UnknownHandler,
        )

        self.assertTrue(all(
            item is not None
            for item in (
                MainMenuHandler,
                SupportSelectHandler,
                TeamConfirmHandler,
                LoadingHandler,
                DialogHandler,
                BattleReadyHandler,
                CardSelectHandler,
                BattleResultHandler,
                UnknownHandler,
            )
        ))


if __name__ == "__main__":
    unittest.main()
