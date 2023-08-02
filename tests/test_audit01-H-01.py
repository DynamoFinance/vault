"""
## [H-01] Access control modifiers on _claim_fees will permanently lock proposer

### Details 

[Dynamo4626.vy#L519-L521](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/Dynamo4626.vy#L519-L521)

    elif _yield == FeeType.PROPOSER:
        assert msg.sender == self.current_proposer, "Only curent proposer may claim strategy fees."
        self.total_strategy_fees_claimed += claim_amount        

Dynamo4626#_set_strategy attempts to distribute fees to proposer when proposer changes. The problem is that _claim_fees requires that msg.sender == proposer. Since _set_strategy can only be called by governance this subcall will always revert. The result is that the first proposer will have a monopoly on all proposals since any strategy that wasn't submitted by them would fail when attempting to activate it.

### Lines of Code

https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/Dynamo4626.vy#L496-L533

### Recommendation

Revise access control on _set_strategy. I would suggest allowing anyone to claim tokens but sending to the correct target instead of msg.sender
"""
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
def strategizer1(accounts):
    return accounts[2]

@pytest.fixture
def strategizer2(accounts):
    return accounts[3]

@pytest.fixture
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, 1000000000, sender=deployer)
    return ua

@pytest.fixture
def funds_alloc(project, deployer):
    f = deployer.deploy(project.FundsAllocator)
    return f

def _setup_single_adapter(_project, _dynamo4626, _deployer, _dai, _adapter, strategizer, ratio=1):
    # Setup our pool strategy first.
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS 

    # Get the current strategy settings.
    pos = 0
    for pool in _dynamo4626.lending_pools():
        strategy[pos] = (pool, _dynamo4626.strategy(pool).ratio)
        pos += 1

    strategy[pos] = (_adapter.address,ratio)
    print("strategy for _setup_single_adapter: %s." % strategy)
    _dynamo4626.set_strategy(strategizer, strategy, 0, sender=_deployer)

    # Now add the pool.
    _dynamo4626.add_pool(_adapter, sender=_deployer)    

    # Jiggle around transfer rights here for test purposes.
    werc20 = _project.ERC20.at(_adapter.wrappedAsset())
    if werc20.minter() != _dynamo4626:
        werc20.transferMinter(_dynamo4626, sender=_deployer)
    werc20.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_dynamo4626) 
    _dai.setApprove(_dynamo4626, _adapter, (1<<256)-1, sender=_deployer)
    _dai.setApprove(_adapter, _dynamo4626, (1<<256)-1, sender=_deployer)


@pytest.fixture
def pool_adapterA(project, deployer, dai):
    wdai = deployer.deploy(project.ERC20, "aWDAI", "aWDAI", 18, 0, deployer)
    a = deployer.deploy(project.MockLPAdapter, dai, wdai)
    return a

@pytest.fixture
def dynamo4626(project, deployer, dai, trader, funds_alloc):
    v = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, [], deployer, funds_alloc)    
    return v

#Setup the most minimalist vault...
def test_set_acl_claim_fees(project, deployer, dynamo4626, pool_adapterA, dai, trader, strategizer1, strategizer2):
    #setup pool with a different proposer and governance.
    _setup_single_adapter(project,dynamo4626, deployer, dai, pool_adapterA, strategizer1)
    #Cause some activity and yield so that there is claimable fees accrued
   
    # Trader needs to allow the 4626 contract to take funds.
    dai.approve(dynamo4626,1000, sender=trader)
    dynamo4626.deposit(1000, trader, sender=trader)
    assert dynamo4626.maxWithdraw(trader) == 1000

    #cause some yield
    # Increase assets in adapter so its assets will double.
    dai.mint(pool_adapterA, 1000, sender=deployer)
    assert dynamo4626.maxWithdraw(trader) > 1000

    assert dynamo4626.claimable_strategy_fees_available() > dynamo4626.min_proposer_payout(), "Not enough to pay Strategist!"

    print("dynamo4626.claimable_strategy_fees_available() : %s." % dynamo4626.claimable_strategy_fees_available())
    print("dynamo4626.claimable_yield_fees_available() : %s." % dynamo4626.claimable_yield_fees_available())
    print("dynamo4626.claimable_all_fees_available() : %s." % dynamo4626.claimable_all_fees_available())



    #No issues if new strategy is from the same proposer
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS
    strategy[0] = (pool_adapterA.address, 1)

    strategizer = dynamo4626.current_proposer()
    assert strategizer == strategizer1, "Not same strategizer!"
    assert strategizer != strategizer2, "Same strategizer!"

    current_strat_funds = dai.balanceOf(strategizer)
    print("current_strat_funds : %s." % current_strat_funds)

    current_owner_funds = dai.balanceOf(dynamo4626.owner())
    print("current_owner_funds : %s." % current_owner_funds)        

    dynamo4626.set_strategy(strategizer, strategy, dynamo4626.min_proposer_payout(), sender=deployer)

    #Per the audit report, if proposer fees claimable > min_proposer_payout, then governance cannot change the strategy...
    dynamo4626.set_strategy(strategizer2, strategy, dynamo4626.min_proposer_payout(), sender=deployer)

    updated_strat_funds = dai.balanceOf(strategizer)

    print("updated_strat_funds : %s." % updated_strat_funds)

    assert updated_strat_funds > current_strat_funds, "strategizer didn't get paid!"

    dynamo4626.claim_all_fees(sender=deployer)

    updated_owner_funds = dai.balanceOf(dynamo4626.owner())

    print("updated_owner_funds : %s." % updated_owner_funds)

    assert updated_owner_funds > current_owner_funds, "owner didn't get paid!"

    print("dynamo4626.claimable_strategy_fees_available() : %s." % dynamo4626.claimable_strategy_fees_available())
    print("dynamo4626.claimable_yield_fees_available() : %s." % dynamo4626.claimable_yield_fees_available())
    print("dynamo4626.claimable_all_fees_available() : %s." % dynamo4626.claimable_all_fees_available())

