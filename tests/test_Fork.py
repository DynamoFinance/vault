import ape

import pytest

def test_vitalik_balance():
    assert ape.api.address.Address("0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045").balance == 739992029493125111147
