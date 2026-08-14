import pytest
from pyteal import OptimizeOptions
from trex_escrow import get_router

def test_ast_compilation():
    router = get_router()
    approval, clear, contract = router.compile_program(version=10, optimize=OptimizeOptions(scratch_slots=True))
    assert approval is not None
    assert clear is not None
    assert contract is not None
