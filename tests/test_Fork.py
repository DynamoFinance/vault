import pytest
import ape
from tests.conftest import is_not_hard_hat


#@pytest.mark.skipif(is_not_hard_hat(), reason="Only run when connected to hard hat.")
def test_vitalik_balance():
    if is_not_hard_hat():
            pytest.skip("Not on hard hat Ethereum snapshot.")
    assert ape.api.address.Address("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045").balance == 739992029493125111147

def test_always_good():
    assert True
