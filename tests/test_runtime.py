import unittest

from kagi.frontend import execute_bootstrap_program, parse_bootstrap_program
from kagi.runtime import (
    Action,
    Cell,
    KagiRuntimeError,
    LoanState,
    apply_action,
    execute_program,
    export_owner,
    well_formed,
)


class RuntimeTest(unittest.TestCase):
    def test_well_formed_rejects_dead_owner_with_outstanding_loan(self):
        heap = {0: Cell(alive=False, loan=LoanState.mut(7))}
        self.assertFalse(well_formed(heap))

    def test_shared_same_epoch_can_extend_and_export_hides_reader_count(self):
        heap = {0: Cell(alive=True, loan=LoanState.shared(10, 0))}
        next_heap = apply_action(heap, Action("borrow_shared", 0, 10))
        self.assertEqual(next_heap[0].loan, LoanState.shared(10, 1))
        self.assertEqual(export_owner(next_heap, 0), "shared 10")

    def test_shared_foreign_epoch_is_blocked(self):
        heap = {0: Cell(alive=True, loan=LoanState.shared(10, 0))}
        with self.assertRaises(KagiRuntimeError):
            apply_action(heap, Action("borrow_shared", 0, 11))

    def test_busy_owner_blocks_mut_and_drop(self):
        heap = {0: Cell(alive=True, loan=LoanState.shared(10, 0))}
        with self.assertRaises(KagiRuntimeError):
            apply_action(heap, Action("borrow_mut", 0, 5))
        with self.assertRaises(KagiRuntimeError):
            apply_action(heap, Action("drop", 0))

    def test_program_execution(self):
        source = """
        owner 0 alive idle
        owner 1 alive idle
        borrow_shared 0 9
        borrow_shared 0 9
        end_shared 0 9
        borrow_mut 1 7
        end_mut 1 7
        drop 1
        """
        result = execute_program(source)
        self.assertEqual(result.heap[0].loan, LoanState.shared(9, 0))
        self.assertFalse(result.heap[1].alive)
        self.assertEqual(export_owner(result.heap, 0), "shared 9")
        self.assertEqual(export_owner(result.heap, 1), "idle")

    def test_execution_result_keeps_actions(self):
        result = execute_program(
            """
            owner 0 alive idle
            borrow_mut 0 3
            end_mut 0 3
            """
        )
        self.assertEqual(len(result.actions), 2)
        self.assertEqual(result.actions[0].kind, "borrow_mut")

    def test_bootstrap_program_supports_named_symbols_and_assertions(self):
        program = parse_bootstrap_program(
            """
            let epoch e0 = 10
            let key k0 = 7
            owner cell alive idle
            borrow_shared cell e0
            assert_export cell shared e0
            end_shared cell e0
            borrow_mut cell k0
            assert_export cell mut
            end_mut cell k0
            """
        )
        self.assertEqual(program.owner_ids["cell"], 0)
        self.assertEqual(len(program.actions), 4)
        self.assertEqual(len(program.assertions), 2)

    def test_bootstrap_execution_runs_and_checks_assertions(self):
        result = execute_bootstrap_program(
            """
            let epoch e0 = 9
            owner cell alive idle
            borrow_shared cell e0
            assert_export cell shared e0
            """
        )
        self.assertEqual(export_owner(result.heap, 0), "shared 9")


if __name__ == "__main__":
    unittest.main()
