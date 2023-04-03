import pytest
import ape
from tests.conftest import is_not_hard_hat

from itertools import zip_longest

d4626_name = "DynamoDAI"
d4626_token = "dyDAI"
d4626_decimals = 18


# Should match what's in Dynamo4626.vy!
MAX_POOLS = 5

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


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
    ua.mint(trader, 1000000000, sender=deployer)
    return ua


@pytest.fixture
def pool_adapterA(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "aWDAI", "aWDAI", 18, 0, deployer)
    a = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return a


@pytest.fixture
def pool_adapterB(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "bWDAI", "bWDAI", 18, 0, deployer)
    b = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return b


@pytest.fixture
def pool_adapterC(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "cWDAI", "cWDAI", 18, 0, deployer)
    c = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return c    


@pytest.fixture
def euler_adapter(project, deployer, dai, ensure_hardhat):
    ca = deployer.deploy(project.eulerAdapter, dai, EDAI, EULER)
    #we run tests against interface
    return project.LPAdapter.at(ca)


@pytest.fixture
def aave_adapter(project, deployer, dai, ensure_hardhat):
    aa = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, dai, ADAI)
    #we run tests against interface
    return project.LPAdapter.at(aa)


@pytest.fixture
def dynamo4626(project, deployer, dai):
    v = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, [], deployer)    
    return v


# tx is an ape.Result
# event_names is an in-order list of strings of the names of the events generated in the tx.
# if full_match == True, event_names must match all result events.
# if full_match == False, we only check as many events as the event_names list has and ignore 
#                         extra event logs that may exist in tx.
def events_in_logs(tx, event_names, full_match=True) -> bool:
    for a,b in zip_longest(tx.decode_logs(), event_names):
        if b == None and full_match == False: continue
        assert a.event_name == b
    return True    


def test_basic_initialization(project, deployer, dynamo4626):
    assert dynamo4626.name(sender=deployer) == d4626_name
    assert dynamo4626.symbol(sender=deployer) == d4626_token
    assert dynamo4626.decimals(sender=deployer) == d4626_decimals


def test_initial_pools_initialization(project, deployer, dai, pool_adapterA, pool_adapterB, pool_adapterC):
    pools = [pool_adapterA, pool_adapterB, pool_adapterC]
    dynamo = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, pools, deployer)    

    # This should fail because we can't add the same pool twice!
    for pool in pools:
        # can't add it a second time.
        with ape.reverts("pool already supported."):
            dynamo.add_pool(pool, sender=deployer)

    pool_count = len(dynamo.lending_pools())
    assert pool_count == 3


def test_add_pool(project, deployer, dynamo4626, pool_adapterA, trader, dai):

    pool_count = len(dynamo4626.lending_pools())
    assert pool_count == 0

    # pool_adapterA can only be added by the owner.
    with ape.reverts("Only owner can add new Lending Pools."):
        result = dynamo4626.add_pool(pool_adapterA, sender=trader)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")
    # pool_adapterA is valid & deployer is allowed to add it.
    result = dynamo4626.add_pool(pool_adapterA, sender=deployer) 
    assert result.return_value == True
    assert events_in_logs(result, ["PoolAdded"])

    # can't add it a second time.
    with ape.reverts("pool already supported."):
        result = dynamo4626.add_pool(pool_adapterA, sender=deployer)

    # dai is not a valid adapter.
    with ape.reverts("Doesn't appear to be an LPAdapter."):    
        result = dynamo4626.add_pool(dai, sender=deployer) 
    
    pool_count = len(dynamo4626.lending_pools())
    assert pool_count == 1

    # How many more pools can we add?
    for i in range(4): # Dynamo4626.MAX_POOLS - 1
        a = deployer.deploy(project.MockLPAdapter, dai, dai)
        result = dynamo4626.add_pool(a, sender=deployer) 
        assert result.return_value == True
        assert events_in_logs(result, ["PoolAdded"])

    # One more pool is too many however.
    a = deployer.deploy(project.MockLPAdapter, dai, dai)
    with ape.reverts():
        dynamo4626.add_pool(a, sender=deployer)


def _setup_single_adapter(_project, _dynamo4626, _deployer, _dai, _adapter):
    # Setup our pool.
    _dynamo4626.add_pool(_adapter, sender=_deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (_adapter,1)
    _dynamo4626.set_strategy(_deployer, strategy, 0, sender=_deployer)

    # Jiggle around transfer rights here for test purposes.
    werc20 = _project.ERC20.at(_adapter.wrappedAsset())
    if werc20.minter() != _dynamo4626:
        werc20.transferMinter(_dynamo4626, sender=_deployer)
    werc20.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_dynamo4626) 
    _dai.setApprove(_dynamo4626, _adapter, (1<<256)-1, sender=_deployer)
    _dai.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_deployer)
    

def test_min_proposer_payout(project, deployer, dynamo4626, aave_adapter, dai, trader, adai):
    dynamo4626.add_pool(aave_adapter, sender=deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (aave_adapter,1)    
    dynamo4626.set_strategy(deployer, strategy, 100000, sender=deployer)

    dynamo4626.deposit(9, trader, sender=trader)
    assert dynamo4626.balanceOf(trader) == 0
    print(dynamo4626.balanceOf(trader))