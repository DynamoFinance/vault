import pytest

import ape
from ape import chain



def is_not_hard_hat():
    try:
        print("Current chain id is: %s." % chain.chain_id)
        return chain.chain_id!=31337
    except ape.exceptions.ProviderNotConnectedError:
        print("Alert: Not connected to a chain.")
        return True

#@pytest.mark.skipif(is_not_hard_hat(), reason="Only run when connected to hard hat.")
def test_vitalik_balance():
    assert ape.api.address.Address("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045").balance == 739992029493125111147

def test_always_good():
    assert True