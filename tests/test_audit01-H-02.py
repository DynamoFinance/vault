"""
## [H-02] Math error in Dynamo4626#_claimable_fees_available will lead to fees or strategy lockup

### Details 

[Dynamo4626.vy#L428-L438](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/Dynamo4626.vy#L428-L438)

    fee_percentage: uint256 = YIELD_FEE_PERCENTAGE
    if _yield == FeeType.PROPOSER:
        fee_percentage = PROPOSER_FEE_PERCENTAGE
    elif _yield == FeeType.BOTH:
        fee_percentage += PROPOSER_FEE_PERCENTAGE
    elif _yield != FeeType.YIELD:
        assert False, "Invalid FeeType!" 

    total_fees_ever : uint256 = (convert(total_returns,uint256) * fee_percentage) / 100

    assert self.total_strategy_fees_claimed + self.total_yield_fees_claimed <= total_fees_ever, "Total fee calc error!"

In the assert statement, total_fees_ever is compared against both fees types of fees claimed. The issue with this is that this is a relative value depending on which type of fee is being claimed. The assert statement on the other hand always compares as if it is FeeType.BOTH. This will lead to this function unexpectedly reverting when trying to claim proposer fees. This leads to stuck fees but also proposer locked as described in H-01.

### Lines of Code

[Dynamo4626.vy#L418-L459](https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/Dynamo4626.vy#L418-L459)

### Recommendation

Check should be made against the appropriate values (i.e. proposer should be check against only self.total_strategy_fees_claimed).
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

def test_claimable_issue(deployer, trader, dai, dynamo4626, compound_adapter, cdai, attacker, compound_exploiter):
    #Trader invest everything
    dai.approve(dynamo4626, dai.balanceOf(trader), sender=trader)
    dynamo4626.deposit(dai.balanceOf(trader), trader, sender=trader)
    print(dynamo4626.claimable_yield_fees_available())
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
        "params": ["0x186a0", "0x12c"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    print("dynamo4626.claimable_yield_fees_available() : %s." % dynamo4626.claimable_yield_fees_available())
    dynamo4626.claim_strategy_fees(sender=deployer)
    dynamo4626.claim_all_fees(sender=deployer)
    #I dont quite understand the math a 100%, but next line triggers it...
    #Its supposedly only using yield fee for calc, but comparing it against sum of yield+strategy fees
    #print(dynamo4626.claimable_yield_fees_available())
    print("dynamo4626.claimable_yield_fees_available() : %s." % dynamo4626.claimable_yield_fees_available())
