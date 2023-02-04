import pytest
import ape
from tests.conftest import is_not_hard_hat

from itertools import zip_longest

d4626_name = "DynamoDAI"
d4626_token = "dyDAI"
d4626_decimals = 18

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, '1000000000 Ether', sender=deployer)
    return ua


@pytest.fixture
def pool_adapter(project, deployer):
    a = deployer.deploy(project.MockLPAdapter)
    return a


@pytest.fixture
def dynamo4626(project, deployer, dai, trader):
    v = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, [])    
    return v


# result is an ape.Result
# event_names is an in-order list of strings of the names of the events generated in the tx.
# if full_match == True, event_names must match all result events.
# if full_match == False, we only check as many events as the event_names list has and ignore 
#                         extra event logs that may exist.
def events_in_logs(result, event_names, full_match=True) -> bool:
    for a,b in zip_longest(result.decode_logs(), event_names):
        if b == None and full_match == False: continue
        assert a.event_name == b
    return True    



def test_basic_initialization(project, deployer, dynamo4626):
    assert dynamo4626.name(sender=deployer) == d4626_name
    assert dynamo4626.symbol(sender=deployer) == d4626_token
    assert dynamo4626.decimals(sender=deployer) == d4626_decimals

def test_add_pool(project, deployer, dynamo4626, pool_adapter, trader, dai):

    pool_count = len(dynamo4626.lending_pools())
    assert pool_count == 0

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    # pool_adapter can only be added by the owner.
    with ape.reverts("Only owner can add new Lending Pools."):
        result = dynamo4626.add_pool(pool_adapter, sender=trader)

    # pool_adapter is valid & deployer is allowed to add it.
    result = dynamo4626.add_pool(pool_adapter, sender=deployer) 
    assert result.return_value == True
    assert events_in_logs(result, ["poolAdded"])

    # can't add it a second time.
    with ape.reverts("pool already supported."):
        result = dynamo4626.add_pool(pool_adapter, sender=deployer)

    # dai is not a valid adapter.
    with ape.reverts("Doesn't appear to be an LPAdapter."):    
        result = dynamo4626.add_pool(dai, sender=deployer) 
    
    pool_count = len(dynamo4626.lending_pools())
    assert pool_count == 1

    # How many more pools can we add?
    for i in range(4): # Dynamo4626.MAX_POOLS - 1
        a = deployer.deploy(project.MockLPAdapter)
        result = dynamo4626.add_pool(a, sender=deployer) 
        assert result.return_value == True
        assert events_in_logs(result, ["poolAdded"])

    # One more pool is too many however.
    a = deployer.deploy(project.MockLPAdapter)
    with ape.reverts():
        dynamo4626.add_pool(a, sender=deployer)
