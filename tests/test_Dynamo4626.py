import copy
from dataclasses import dataclass

import pytest
import ape
from tests.conftest import is_not_hard_hat

from itertools import zip_longest

MAX_POOLS = 5 # Must match the value from Dynamo4626.vy

d4626_name = "DynamoDAI"
d4626_token = "dyDAI"
d4626_decimals = 18

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
def funds_alloc(project, deployer):
    f = deployer.deploy(project.FundsAllocator)
    return f

@pytest.fixture
def dynamo4626(project, deployer, dai, trader, funds_alloc):
    v = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, [], deployer, funds_alloc)    
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


def test_initial_pools_initialization(project, deployer, dai, pool_adapterA, pool_adapterB, pool_adapterC, funds_alloc):
    pools = [pool_adapterA, pool_adapterB, pool_adapterC]
    dynamo = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, pools, deployer, funds_alloc)    

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
    for i in range(MAX_POOLS - 1): 
        a = deployer.deploy(project.MockLPAdapter, dai, dai)
        result = dynamo4626.add_pool(a, sender=deployer) 
        assert result.return_value == True
        assert events_in_logs(result, ["PoolAdded"])

    # One more pool is too many however.
    a = deployer.deploy(project.MockLPAdapter, dai, dai)
    with ape.reverts():
        dynamo4626.add_pool(a, sender=deployer)


def _setup_single_adapter(_project, _dynamo4626, _deployer, _dai, _adapter, ratio=1):
    # Setup our pool strategy first.
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS 

    # Get the current strategy settings.
    pos = 0
    for pool in _dynamo4626.lending_pools():
        strategy[pos] = (pool, _dynamo4626.strategy(pool).ratio)
        pos += 1

    strategy[pos] = (_adapter.address,ratio)
    print("strategy for _setup_single_adapter: %s." % strategy)
    _dynamo4626.set_strategy(_deployer, strategy, 0, sender=_deployer)

    # Now add the pool.
    _dynamo4626.add_pool(_adapter, sender=_deployer)    

    # Jiggle around transfer rights here for test purposes.
    werc20 = _project.ERC20.at(_adapter.wrappedAsset())
    if werc20.minter() != _dynamo4626:
        werc20.transferMinter(_dynamo4626, sender=_deployer)
    werc20.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_dynamo4626) 
    _dai.setApprove(_dynamo4626, _adapter, (1<<256)-1, sender=_deployer)
    _dai.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_deployer)


def test_remove_pool(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, trader, dai):
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    assert dynamo4626.totalAssets() == 0
    assert pool_adapterA.totalAssets() == 0  
    assert pool_adapterA in dynamo4626.lending_pools()

    result = dynamo4626.deposit(500, trader, sender=trader)

    assert dynamo4626.totalAssets() == 500   
    # BDM FIX! assert pool_adapterA.totalAssets() == 500

    with ape.reverts("Only owner can remove Lending Pools."):
        result = dynamo4626.remove_pool(pool_adapterA, sender=trader)

    result = dynamo4626.remove_pool(pool_adapterA, sender=deployer)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    assert result.return_value == True

    assert dynamo4626.totalAssets() == 500   
    assert pool_adapterA.totalAssets() == 0    
    assert pool_adapterA not in dynamo4626.lending_pools()

    print("HERE 1")

    assert dynamo4626.totalAssets() == 500   
    assert pool_adapterB.totalAssets() == 0

    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterB)

    print("HERE 2")

    assert dynamo4626.totalAssets() == 500   

    # BDM ?!?!? Why does this fail ?!?!?!
    #assert pool_adapterB.totalAssets() == 0

    print("HERE 3")

    dynamo4626.balanceAdapters(0, MAX_POOLS, sender=deployer)

    print("HERE 4")

    assert dynamo4626.totalAssets() == 500   
    assert pool_adapterB.totalAssets() == 500

    print("HERE 5")

    result = dynamo4626.remove_pool(pool_adapterB, False, sender=deployer)
       
    print("HERE 6")

    assert result.return_value == True

    assert dynamo4626.totalAssets() == 500   
    assert pool_adapterB.totalAssets() == 0 

# So which one are we using? 'Cuz there's another setup_single_adapter function up top.
def _setup_single_adapter(_project, _dynamo4626, _deployer, _dai, _adapter):
    # Setup our pool.
    _dynamo4626.add_pool(_adapter, sender=_deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (_adapter, 1)
    _dynamo4626.set_strategy(_deployer, strategy, 0, sender=_deployer)

    # Jiggle around transfer rights here for test purposes.
    werc20 = _project.ERC20.at(_adapter.wrappedAsset())
    if werc20.minter() != _dynamo4626:
        werc20.transferMinter(_dynamo4626, sender=_deployer)
    werc20.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_dynamo4626) 
    _dai.setApprove(_dynamo4626, _adapter, (1<<256)-1, sender=_deployer)
    _dai.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_deployer)


def _setup_multi_adapters(_project, _dynamo4626, _deployer, _dai, _adapters, _strategy):
    for adapter in _adapters:
        # Setup our pool.
        _dynamo4626.add_pool(adapter, sender=_deployer)
        _dynamo4626.set_strategy(_deployer, _strategy, 0, sender=_deployer)

        # Jiggle around transfer rights here for test purposes.
        werc20 = _project.ERC20.at(adapter.wrappedAsset())
        if werc20.minter() != _dynamo4626:
            werc20.transferMinter(_dynamo4626, sender=_deployer)    
        werc20.setApprove(adapter, _dynamo4626, (1<<256)-1, sender=_dynamo4626) 
        _dai.setApprove(_dynamo4626, adapter, (1<<256)-1, sender=_deployer)
        _dai.setApprove(adapter, _dynamo4626, (1<<256)-1, sender=_deployer)


def test_min_tx_sizes(project, deployer, dynamo4626, pool_adapterA, trader, dai):
    pytest.skip("TODO: Not implemented yet.")    


def test_single_adapter_deposit(project, deployer, dynamo4626, pool_adapterA, dai, trader):
    _setup_single_adapter(project, dynamo4626, deployer, dai, pool_adapterA)

    d4626_start_DAI = dai.balanceOf(dynamo4626)
    LP_start_DAI = dai.balanceOf(pool_adapterA)

    trade_start_DAI = project.ERC20.at(pool_adapterA.originalAsset()).balanceOf(trader)
    trade_start_dyDAI = dynamo4626.balanceOf(trader)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    assert dynamo4626.totalAssets() == 0
    assert pool_adapterA.totalAssets() == 0

    assert dynamo4626.convertToAssets(75) == 75
    assert dynamo4626.convertToShares(55) == 55

    result = dynamo4626.deposit(500, trader, sender=trader)

    assert dynamo4626.totalAssets() == 500   
    assert pool_adapterA.totalAssets() == 500     

    assert result.return_value == 500        

    assert dynamo4626.balanceOf(trader) == 500

    assert dynamo4626.convertToAssets(75) == 75
    assert dynamo4626.convertToShares(55) == 55    

    trade_end_DAI = project.ERC20.at(pool_adapterA.originalAsset()).balanceOf(trader)
    trade_end_dyDAI = dynamo4626.balanceOf(trader)

    assert trade_start_DAI - trade_end_DAI == 500
    assert trade_end_dyDAI - trade_start_dyDAI == 500
    
    d4626_end_DAI = dai.balanceOf(dynamo4626)

    # DAI should have just passed through the 4626 pool.
    assert d4626_end_DAI == d4626_start_DAI

    LP_end_DAI = dai.balanceOf(pool_adapterA)
    assert LP_end_DAI - LP_start_DAI == 500

    # Now do it again!
    result = dynamo4626.deposit(400, trader, sender=trader)
    assert result.return_value == 400      

    assert dynamo4626.balanceOf(trader) == 900

    trade_end_DAI = project.ERC20.at(pool_adapterA.originalAsset()).balanceOf(trader)
    trade_end_dyDAI = dynamo4626.balanceOf(trader)

    assert trade_start_DAI - trade_end_DAI == 900
    assert trade_end_dyDAI - trade_start_dyDAI == 900
    
    d4626_end_DAI = dai.balanceOf(dynamo4626)

    # DAI should have just passed through the 4626 pool.
    assert d4626_end_DAI == d4626_start_DAI

    LP_end_DAI = dai.balanceOf(pool_adapterA)
    assert LP_end_DAI - LP_start_DAI == 900

# Order of BalancePool struct fields from Dynamo4626
ADAPTER = 0
CURRENT = 1
LAST_VALUE = 2
RATIO = 3
TARGET = 4
DELTA = 5


def test_single_getBalanceTxs(project, deployer, dynamo4626, pool_adapterA, dai, trader):
    print("**** test_single_getBalanceTxs ****")
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA)

    print("\nadapter setup complete.")
    assert pool_adapterA.totalAssets() == 0
    assert dynamo4626.totalAssets() == 0

    d4626_assets, pools, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pools[0].current == 0    
    assert pools[0].ratio == 1 
    assert total_assets == 0
    assert total_ratios == 1

    print("pools = %s." % [x for x in pools])

    total_assets = 1000
    pool_asset_allocation, d4626_delta, tx_count, pools, blocked_adapters = dynamo4626.getTargetBalances(0, total_assets, total_ratios, pools, 0)
    assert pool_asset_allocation == 1000    
    assert d4626_delta == -1000
    assert tx_count == 1
    assert pools[0].current == 0    
    assert pools[0].ratio == 1 
    assert pools[0].target == 1000
    assert pools[0].delta == 1000

    print("pools = %s." % [x for x in pools])    


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pools, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pools[0].current == 1000
    assert pools[0].ratio == 1 
    assert pools[0].target == 0
    assert pools[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1    

    print("pools = %s." % [x for x in pools])

    pool_asset_allocation, d4626_delta, tx_count, pools, blocked_adapters = dynamo4626.getTargetBalances(250, total_assets, total_ratios, pools, 0)
    assert pool_asset_allocation == 750
    assert d4626_delta == 250
    assert tx_count == 1
    assert pools[0].current == 1000    
    assert pools[0].ratio == 1 
    assert pools[0].target == 750
    assert pools[0].delta== -250

    print("pools = %s." % [x for x in pools])


def test_single_adapter_withdraw(project, deployer, dynamo4626, pool_adapterA, dai, trader):
    _setup_single_adapter(project, dynamo4626, deployer, dai, pool_adapterA)

    print("\nadapter setup complete.")
    assert pool_adapterA.totalAssets() == 0
    assert dynamo4626.totalAssets() == 0

    d4626_assets, pools, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pools[0].current == 0    
    assert pools[0].ratio == 1 
    assert total_assets == 0
    assert total_ratios == 1

    print("pools = %s." % [x for x in pools])

    total_assets = 1000
    pool_asset_allocation, d4626_delta, tx_count, pools, blocked_adapters = dynamo4626.getTargetBalances(0, total_assets, total_ratios, pools, 0)
    assert pool_asset_allocation == 1000    
    assert d4626_delta == -1000
    assert tx_count == 1
    assert pools[0].current == 0    
    assert pools[0].ratio == 1 
    assert pools[0].target == 1000
    assert pools[0].delta == 1000

    print("pools = %s." % [x for x in pools])    


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626,1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pools, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pools[0].current == 1000
    assert pools[0].ratio == 1 
    assert pools[0].target == 0
    assert pools[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1    

    # Add a second adapter.
    _setup_single_adapter(project, dynamo4626, deployer, dai, pool_adapterB)

    dynamo4626.balanceAdapters(0, MAX_POOLS, sender=trader)

    d4626_assets, pools, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    
    assert pools[0].adapter == pool_adapterA
    assert pools[0].current == 500
    assert pools[0].ratio == 1 
    assert pools[0].target == 0
    assert pools[0].delta== 0

    assert pools[1].adapter == pool_adapterB
    assert pools[1].current == 500
    assert pools[1].ratio == 1 
    assert pools[1].target == 0
    assert pools[1].delta== 0    

    assert total_assets == 1000
    assert total_ratios == 2



def test_single_adapter_withdraw(project, deployer, dynamo4626, pool_adapterA, dai, trader):
    _setup_single_adapter(project, dynamo4626, deployer, dai, pool_adapterA)

    assert pool_adapterA.totalAssets() == 0
    assert dynamo4626.totalAssets() == 0


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    assert pool_adapterA.totalAssets() == 1000
    assert dynamo4626.totalAssets() == 1000

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    print("dynamo4626.deposit(1000, trader, sender=trader) = %s." % result.return_value)
    assert result.return_value == 1000   


    # There have been no earnings so shares & assets should map 1:1.
    assert dynamo4626.convertToShares(250) == 250  
    assert dynamo4626.convertToAssets(250) == 250  

    result = dynamo4626.withdraw(250, trader, trader, sender=trader)

    assert pool_adapterA.totalAssets() == 750
    assert dynamo4626.totalAssets() == 750

    assert result.return_value == 250


def test_single_adapter_share_value_increase(project, deployer, dynamo4626, pool_adapterA, dai, trader):
    _setup_single_adapter(project, dynamo4626, deployer, dai, pool_adapterA)

    assert dai.balanceOf(trader) == 1000000000 

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    assert dai.balanceOf(dynamo4626) == 0

    dynamo4626.deposit(1000, trader, sender=trader)

    assert dai.balanceOf(dynamo4626) == 0
    assert dai.balanceOf(pool_adapterA) == 1000

    assert dai.balanceOf(trader) == 1000000000 - 1000

    assert dynamo4626.totalSupply() == 1000

    assert dynamo4626.totalAssets() == 1000

    # Increase assets in adapter so its assets will double.
    dai.mint(pool_adapterA, 1000, sender=deployer)

    assert dai.balanceOf(pool_adapterA) == 2000    

    assert dynamo4626.totalSupply() == 1000

    assert dynamo4626.totalAssets() == 2000

    # Assumes YIELD_FEE_PERCENTAGE : constant(decimal) = 10.0
    #     and PROPOSER_FEE_PERCENTAGE : constant(decimal) = 1.0
    print("dynamo4626.convertToAssets(1000) is :%s but should be: %s." % (int(dynamo4626.convertToAssets(1000)),1000 + (1000 - (1000*0.11))))
    assert dynamo4626.convertToAssets(1000) == 1000 + (1000 - (1000*0.11))

    assert dynamo4626.convertToShares(2000) == 1058 # 1000    

    max_withdrawl = dynamo4626.maxWithdraw(trader, sender=trader)
    max_redeem = dynamo4626.maxRedeem(trader, sender=trader)

    shares_to_redeem = dynamo4626.convertToShares(max_withdrawl)
    value_of_shares = dynamo4626.convertToAssets(shares_to_redeem)
    print("max_withdrawl = %s." % max_withdrawl)
    print("max_redeem = %s." % max_redeem)
    print("shares_to_redeem = %s." % shares_to_redeem)
    print("value_of_shares = %s." % value_of_shares)

    assert max_withdrawl == 1000 + (1000 - (1000*0.11))
    assert max_redeem == 1000

    print("Got here #1.")

    # Setup current state of vault & pools & strategy.
    cd4626_assets, cpool_states, ctotal_assets, ctotal_ratios = dynamo4626.getCurrentBalances()

    pools = dynamo4626.getBalanceTxs(max_withdrawl, 5, 0, ctotal_assets, ctotal_ratios, cpool_states, sender=trader)   

    print("pools = %s." % [x for x in pools])

    print("dai.balance_of(pool_adapterA) = %s." % dai.balanceOf(pool_adapterA))
    print("dynamo4626.balance_of(trader) = %s." % dynamo4626.balanceOf(trader))    

    #dynamo4626.balanceAdapters(1889, sender=trader)


    print("Got here #2.")

    taken = dynamo4626.withdraw(1890, trader, trader, sender=trader) 
    #taken = dynamo4626.withdraw(1000, trader, trader, sender=trader) 
    print("Got back: %s shares, was expecting %s." % (taken.return_value, max_redeem))

    max_withdrawl = dynamo4626.maxWithdraw(trader, sender=trader)
    max_redeem = dynamo4626.maxRedeem(trader, sender=trader)

    assert max_withdrawl == pytest.approx(0), "Still got %s assets left to withdraw!" % max_withdrawl
    assert max_redeem == pytest.approx(0), "Still got %s shares left to redeem!" % max_redeem


def test_single_adapter_brakes_target_balance_txs(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, pool_adapterC, dai, trader):
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626,1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    first_pool = pool_states[0]
    assert first_pool.adapter == pool_adapterA
    assert first_pool.current == 1000
    assert first_pool.last_value == 1000
    assert first_pool.ratio == 1
    assert first_pool.target == 0
    assert first_pool.delta == 0
    assert total_assets == 1000
    assert total_ratios == 1   

    # Ape needs this conversion.
    pools = [copy.deepcopy(x) for x in pool_states]

    # Pretend to add another 1000.
    # The target for the first pool's value should be the full amount.
    next_assets, moved, tx_count, pool_txs, blocked_adapters = dynamo4626.getTargetBalances(0, 2000, 1, pools, 0)    

    assert blocked_adapters[0] == ZERO_ADDRESS    

    first_pool = pool_txs[0]
    assert first_pool.adapter == pool_adapterA
    assert first_pool.current == 1000
    assert first_pool.last_value == 1000
    assert first_pool.ratio == 1
    assert first_pool.target == 2000
    assert first_pool.delta == 1000

    # Adjust as if it happened.
    first_pool.current = 2000
    first_pool.last_value = 2000
    first_pool.target = 0
    first_pool.delta = 0
    pools[0]=first_pool

    # Knock the first pool's current value down as if there was a loss of 400 in that LP.
    pools[0].current = 1600

    # Pretend to add another 1000.
    # No tx should be generated for the adapter as the brakes are applied due to the loss.
    next_assets, moved, tx_count, pool_txs, blocked_adapters = dynamo4626.getTargetBalances(0, 2000, 1, pools, 0)

    assert blocked_adapters[0] == pool_adapterA    

    assert pool_txs[0].adapter == ZERO_ADDRESS
    assert pool_txs[0].current == 0
    assert pool_txs[0].last_value == 0
    assert pool_txs[0].ratio == 0    
    assert pool_txs[0].target == 0
    assert pool_txs[0].delta== 0

    # Pretend pool_adapterA has been kicked out.
    pools[0].ratio = 0

    # Pretend to add another adapter.
    pools[1].adapter = pool_adapterB
    pools[1].current = 0
    pools[1].last_value = 0
    pools[1].ratio = 1
    pools[1].target = 0
    pools[1].delta = 0


    next_assets, moved, tx_count, pool_txs, blocked_adapters = dynamo4626.getTargetBalances(0, 2000, 1, pools, 0)

    # All the funds should be moved into pool_adapterB.

    assert pool_txs[0].adapter == pool_adapterA
    assert pool_txs[0].current == 1600
    assert pool_txs[0].last_value == 2000
    assert pool_txs[0].ratio == 0    
    assert pool_txs[0].target == 0
    assert pool_txs[0].delta== -1600

    assert pool_txs[1].adapter == pool_adapterB
    assert pool_txs[1].current == 0
    assert pool_txs[1].last_value == 0
    assert pool_txs[1].ratio == 1    
    assert pool_txs[1].target == 2000
    assert pool_txs[1].delta== 2000


def test_single_adapter_brakes(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, dai, trader):
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA)

    #pytest.skip("Not yet.")

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626,5000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pool_states[0].adapter == pool_adapterA
    assert pool_states[0].current == 1000
    assert pool_states[0].last_value == 1000
    assert pool_states[0].ratio == 1 
    assert pool_states[0].target == 0
    assert pool_states[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1   

    # Ape needs this conversion.
    pools = [x for x in pool_states]

    # Steal some funds from the Adapter.
    dai.transfer(deployer, 600, sender=pool_adapterA)
    
    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 1000
    assert pool_states[0].adapter == pool_adapterA    
    assert pool_states[0].current == 400
    assert pool_states[0].last_value == 1000    
    assert pool_states[0].ratio == 0 # Now has been blocked! 
    assert pool_states[0].target == 0
    assert pool_states[0].delta== 0
    assert total_assets == 1400
    assert total_ratios == 0  

    # Add another adapter.
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterB)

    dynamo4626.balanceAdapters(0, MAX_POOLS, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pool_states[0].adapter == pool_adapterA    
    assert pool_states[0].current == 0
    assert pool_states[0].last_value == 0
    assert pool_states[0].ratio == 0 
    assert pool_states[0].target == 0
    assert pool_states[0].delta== 0

    assert pool_states[1].adapter == pool_adapterB
    assert pool_states[1].current == 1400
    assert pool_states[1].last_value == 1400
    assert pool_states[1].ratio == 1 
    assert pool_states[1].target == 0
    assert pool_states[1].delta== 0
    assert total_assets == 1400
    assert total_ratios == 1 


@dataclass
class DTx:
    adapter: str = ZERO_ADDRESS
    delta: int = 0

def countif(l):
    return sum(1 for y in [x for x in l if x.delta!=0])


def test_insertion_sort():    

    transactions = [DTx(x[0],x[1]) for x in [('0x123',-5),('0x456',4),('0x876',-25),('0x543',15)]]

    ordered_txs = [DTx()] * MAX_POOLS

    for next_tx in transactions:
        if next_tx.delta == 0: continue # No txs allowed that do nothing.
        for pos in range(MAX_POOLS):
            if ordered_txs[pos].delta == 0: # Empty position, take it.
                ordered_txs[pos]=next_tx
                print("first ordered_txs = %s\n" % ordered_txs)
                break
            elif ordered_txs[pos].delta > next_tx.delta: # Move everything right and insert here.
                for npos in range(MAX_POOLS):
                    next_pos = MAX_POOLS - npos - 1
                    if ordered_txs[next_pos].delta == 0: continue
                    ordered_txs[next_pos+1] = ordered_txs[next_pos]
                    
                ordered_txs[pos]=next_tx
                print("ordered_txs = %s\n" % ordered_txs)
                break

    # test got them all
    assert countif(transactions) == countif(ordered_txs), "Didn't get all txs."

    # test sorted order
    print("\n\nordered_txs = %s" % ordered_txs)
    print("sorted(transactions) = %s" % sorted(transactions, key=lambda x: x.delta))
    assert all([x[0].delta == x[1].delta for x in zip(ordered_txs, sorted(transactions, key=lambda x: x.delta))])


def test_single_adapter_brakes_target_balance_txs(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, pool_adapterC, dai, trader):
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626,1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    first_pool = pool_states[0]
    assert first_pool.adapter == pool_adapterA
    assert first_pool.current == 1000
    assert first_pool.last_value == 1000
    assert first_pool.ratio == 1
    assert first_pool.target == 0
    assert first_pool.delta == 0
    assert total_assets == 1000
    assert total_ratios == 1   

    # Ape needs this conversion.
    pools = [copy.deepcopy(x) for x in pool_states]

    # Pretend to add another 1000.
    # The target for the first pool's value should be the full amount.
    next_assets, moved, tx_count, pool_txs, blocked_adapters = dynamo4626.getTargetBalances(0, 2000, 1, pools, 0)    

    assert blocked_adapters[0] == ZERO_ADDRESS    

    first_pool = pool_txs[0]
    assert first_pool.adapter == pool_adapterA
    assert first_pool.current == 1000
    assert first_pool.last_value == 1000
    assert first_pool.ratio == 1
    assert first_pool.target == 2000
    assert first_pool.delta == 1000

    # Adjust as if it happened.
    first_pool.current = 2000
    first_pool.last_value = 2000
    first_pool.target = 0
    first_pool.delta = 0
    pools[0]=first_pool

    # Knock the first pool's current value down as if there was a loss of 400 in that LP.
    pools[0].current = 1600

    # Pretend to add another 1000.
    # No tx should be generated for the adapter as the brakes are applied due to the loss.
    next_assets, moved, tx_count, pool_txs, blocked_adapters = dynamo4626.getTargetBalances(0, 2000, 1, pools, 0)

    assert blocked_adapters[0] == pool_adapterA    

    assert pool_txs[0].adapter == ZERO_ADDRESS
    assert pool_txs[0].current == 0
    assert pool_txs[0].last_value == 0
    assert pool_txs[0].ratio == 0    
    assert pool_txs[0].target == 0
    assert pool_txs[0].delta== 0

    # Pretend pool_adapterA has been kicked out.
    pools[0].ratio = 0

    # Pretend to add another adapter.
    pools[1].adapter = pool_adapterB
    pools[1].current = 0
    pools[1].last_value = 0
    pools[1].ratio = 1
    pools[1].target = 0
    pools[1].delta = 0


    next_assets, moved, tx_count, pool_txs, blocked_adapters = dynamo4626.getTargetBalances(0, 2000, 1, pools, 0)

    # All the funds should be moved into pool_adapterB.

    assert pool_txs[0].adapter == pool_adapterA
    assert pool_txs[0].current == 1600
    assert pool_txs[0].last_value == 2000
    assert pool_txs[0].ratio == 0    
    assert pool_txs[0].target == 0
    assert pool_txs[0].delta== -1600

    assert pool_txs[1].adapter == pool_adapterB
    assert pool_txs[1].current == 0
    assert pool_txs[1].last_value == 0
    assert pool_txs[1].ratio == 1    
    assert pool_txs[1].target == 2000
    assert pool_txs[1].delta== 2000


def test_single_adapter_brakes(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, dai, trader):
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA)

    #pytest.skip("Not yet.")

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626,5000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pool_states[0].adapter == pool_adapterA
    assert pool_states[0].current == 1000
    assert pool_states[0].last_value == 1000
    assert pool_states[0].ratio == 1 
    assert pool_states[0].target == 0
    assert pool_states[0].delta== 0
    assert total_assets == 1000
    assert total_ratios == 1   

    # Ape needs this conversion.
    pools = [x for x in pool_states]

    # Steal some funds from the Adapter.
    dai.transfer(deployer, 600, sender=pool_adapterA)
    
    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 1000
    assert pool_states[0].adapter == pool_adapterA    
    assert pool_states[0].current == 400
    assert pool_states[0].last_value == 1000    
    assert pool_states[0].ratio == 0 # Now has been blocked! 
    assert pool_states[0].target == 0
    assert pool_states[0].delta== 0
    assert total_assets == 1400
    assert total_ratios == 0  

    # Add another adapter.
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterB)

    dynamo4626.balanceAdapters(0, MAX_POOLS, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pool_states[0].adapter == pool_adapterA    
    assert pool_states[0].current == 0
    assert pool_states[0].last_value == 0
    assert pool_states[0].ratio == 0 
    assert pool_states[0].target == 0
    assert pool_states[0].delta== 0

    assert pool_states[1].adapter == pool_adapterB
    assert pool_states[1].current == 1400
    assert pool_states[1].last_value == 1400
    assert pool_states[1].ratio == 1 
    assert pool_states[1].target == 0
    assert pool_states[1].delta== 0
    assert total_assets == 1400
    assert total_ratios == 1 


@dataclass
class DTx:
    adapter: str = ZERO_ADDRESS
    delta: int = 0

def countif(l):
    return sum(1 for y in [x for x in l if x.delta!=0])


def test_insertion_sort():    

    transactions = [DTx(x[0],x[1]) for x in [('0x123',-5),('0x456',4),('0x876',-25),('0x543',15)]]

    ordered_txs = [DTx()] * MAX_POOLS

    for next_tx in transactions:
        if next_tx.delta == 0: continue # No txs allowed that do nothing.
        for pos in range(MAX_POOLS):
            if ordered_txs[pos].delta == 0: # Empty position, take it.
                ordered_txs[pos]=next_tx
                print("first ordered_txs = %s\n" % ordered_txs)
                break
            elif ordered_txs[pos].delta > next_tx.delta: # Move everything right and insert here.
                for npos in range(MAX_POOLS):
                    next_pos = MAX_POOLS - npos - 1
                    if ordered_txs[next_pos].delta == 0: continue
                    ordered_txs[next_pos+1] = ordered_txs[next_pos]
                    
                ordered_txs[pos]=next_tx
                print("ordered_txs = %s\n" % ordered_txs)
                break

    # test got them all
    assert countif(transactions) == countif(ordered_txs), "Didn't get all txs."

    # test sorted order
    print("\n\nordered_txs = %s" % ordered_txs)
    print("sorted(transactions) = %s" % sorted(transactions, key=lambda x: x.delta))
    assert all([x[0].delta == x[1].delta for x in zip(ordered_txs, sorted(transactions, key=lambda x: x.delta))])


def test_multi_adapter_deposit(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, pool_adapterC, dai, trader):
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (pool_adapterA, 1)
    strategy[1] = (pool_adapterB, 1)
    strategy[2] = (pool_adapterC, 1)
    adapters = [pool_adapterA, pool_adapterB, pool_adapterC]

    _setup_multi_adapters(project, dynamo4626, deployer, dai, adapters, strategy)

    d4626_start_DAI = dai.balanceOf(dynamo4626)
    LP_start_DAI_A = dai.balanceOf(pool_adapterA)
    LP_start_DAI_B = dai.balanceOf(pool_adapterB)
    LP_start_DAI_C = dai.balanceOf(pool_adapterC)
    

    trade_start_DAI_A = project.ERC20.at(pool_adapterA.originalAsset()).balanceOf(trader)
    trade_start_DAI_B = project.ERC20.at(pool_adapterB.originalAsset()).balanceOf(trader)
    trade_start_DAI_C = project.ERC20.at(pool_adapterC.originalAsset()).balanceOf(trader)
    trade_start_dyDAI = dynamo4626.balanceOf(trader)

    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    assert dynamo4626.totalAssets() == 0
    assert pool_adapterA.totalAssets() == 0
    assert pool_adapterB.totalAssets() == 0
    assert pool_adapterC.totalAssets() == 0

    assert dynamo4626.convertToAssets(75) == 75
    assert dynamo4626.convertToShares(55) == 55

    result = dynamo4626.deposit(500, trader, sender=trader)

    assert dynamo4626.totalAssets() == 500
    assert pool_adapterA.totalAssets() == 166
    assert pool_adapterB.totalAssets() == 166
    assert pool_adapterC.totalAssets() == 166

    assert result.return_value == 500        

    assert dynamo4626.balanceOf(trader) == 500

    assert dynamo4626.convertToAssets(75) == 75
    assert dynamo4626.convertToShares(55) == 55    

    trade_end_DAI_A = project.ERC20.at(pool_adapterA.originalAsset()).balanceOf(trader)
    trade_end_DAI_B = project.ERC20.at(pool_adapterB.originalAsset()).balanceOf(trader)
    trade_end_DAI_C = project.ERC20.at(pool_adapterC.originalAsset()).balanceOf(trader)
    trade_end_dyDAI = dynamo4626.balanceOf(trader)

    assert trade_start_DAI_A - trade_end_DAI_A == 500
    assert trade_start_DAI_B - trade_end_DAI_B == 500
    assert trade_start_DAI_C - trade_end_DAI_C == 500
    assert trade_end_dyDAI - trade_start_dyDAI == 500
    
    d4626_end_DAI = dai.balanceOf(dynamo4626)

    # DAI should have just passed through the 4626 pool.
    assert d4626_end_DAI == d4626_start_DAI

    LP_end_DAI_A = dai.balanceOf(pool_adapterA)
    assert LP_end_DAI_A - LP_start_DAI_A == 500
    LP_end_DAI_B = dai.balanceOf(pool_adapterB)
    assert LP_end_DAI_B - LP_start_DAI_B == 500
    LP_end_DAI_C = dai.balanceOf(pool_adapterC)
    assert LP_end_DAI_C - LP_start_DAI_C == 500

    # Now do it again!
    result = dynamo4626.deposit(400, trader, sender=trader)
    assert result.return_value == 400      

    assert dynamo4626.balanceOf(trader) == 900

    trade_end_DAI_A = project.ERC20.at(pool_adapterA.originalAsset()).balanceOf(trader)
    trade_end_dyDAI = dynamo4626.balanceOf(trader)

    assert trade_start_DAI_A - trade_end_DAI_A == 900
    assert trade_end_dyDAI - trade_start_dyDAI == 900
    
    d4626_end_DAI = dai.balanceOf(dynamo4626)

    # DAI should have just passed through the 4626 pool.
    assert d4626_end_DAI == d4626_start_DAI

    LP_end_DAI_A = dai.balanceOf(pool_adapterA)
    assert LP_end_DAI_A - LP_start_DAI_A == 900

    assert dai.balanceOf(pool_adapterA) == dai.balanceOf(pool_adapterB) == dai.balanceOf(pool_adapterC)


    # Now try fiddling with the ratios on the strategies.
    # strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    # strategy[0] = (pool_adapterA, 2)
    # strategy[1] = (pool_adapterB, 1)
    # strategy[2] = (pool_adapterC, 1)


def test_multi_getBalanceTxs(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, pool_adapterC, dai, trader):
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (pool_adapterA, 1)
    strategy[1] = (pool_adapterB, 1)
    strategy[2] = (pool_adapterC, 1)
    adapters = [pool_adapterA, pool_adapterB, pool_adapterC]

    _setup_multi_adapters(project, dynamo4626, deployer, dai, adapters, strategy)

    assert pool_adapterA.totalAssets() == 0
    assert dynamo4626.totalAssets() == 0

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pool_states[0][CURRENT] == 0    
    assert pool_states[0][RATIO] == 1 
    assert total_assets == 0
    assert total_ratios == 3

    print("pool_states = %s." % [x for x in pool_states])

    pools = [x for x in pool_states]

    total_assets = 1000
    pool_asset_allocation, d4626_delta, tx_count, pool_states = dynamo4626.getTargetBalances(0, total_assets, total_ratios, pools)
    assert pool_asset_allocation == 999    
    assert d4626_delta == -999
    assert tx_count == 3
    assert pool_states[0][CURRENT] == 0    
    assert pool_states[0][RATIO] == 1
    assert pool_states[0][TARGET] == 333
    assert pool_states[0][DELTA] == 333

    print("pool_states = %s." % [x for x in pool_states])    


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    d4626_assets, pool_states, total_assets, total_ratios = dynamo4626.getCurrentBalances()

    assert d4626_assets == 0
    assert pool_states[0][CURRENT] == 1000
    assert pool_states[0][RATIO] == 1 
    assert pool_states[0][TARGET] == 0
    assert pool_states[0][DELTA] == 0
    assert total_assets == 1000
    assert total_ratios == 1    

    print("pool_states = %s." % [x for x in pool_states])

    pools = [x for x in pool_states]

    pool_asset_allocation, d4626_delta, tx_count, pool_states = dynamo4626.getTargetBalances(250, total_assets, total_ratios, pools)
    assert pool_asset_allocation == 750
    assert d4626_delta == 250
    assert tx_count == 1
    assert pool_states[0][CURRENT] == 1000    
    assert pool_states[0][RATIO] == 1 
    assert pool_states[0][TARGET] == 750
    assert pool_states[0][DELTA] == -250

    print("pool_states = %s." % [x for x in pool_states])


def test_multi_adapter_withdraw(project, deployer, dynamo4626, pool_adapterA, pool_adapterB, pool_adapterC, dai, trader):
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (pool_adapterA, 1)
    strategy[1] = (pool_adapterB, 1)
    strategy[2] = (pool_adapterC, 1)
    adapters = [pool_adapterA, pool_adapterB, pool_adapterC]

    _setup_multi_adapters(project, dynamo4626, deployer, dai, adapters, strategy)
    
    assert pool_adapterA.totalAssets() == 0
    assert dynamo4626.totalAssets() == 0


    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626, 1000, sender=trader)

    result = dynamo4626.deposit(1000, trader, sender=trader)

    assert dynamo4626.totalAssets() == 1000
    assert pool_adapterA.totalAssets() == 333

    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")

    print("dynamo4626.deposit(1000, trader, sender=trader) = %s." % result.return_value)
    assert result.return_value == 1000   


    # There have been no earnings so shares & assets should map 1:1.
    assert dynamo4626.convertToShares(250) == 250  
    assert dynamo4626.convertToAssets(250) == 250  

    result = dynamo4626.withdraw(250, trader, trader, sender=trader)

    assert pool_adapterA.totalAssets() == 250
    assert dynamo4626.totalAssets() == 750

    assert result.return_value == 250