"""
## [H-05] A single malfunctioning/malicious adapter can permanently DOS entire vault

### Details 

https://github.com/DynamoFinance/vault/blob/c331ffefadec7406829fc9f2e7f4ee7631bef6b3/contracts/FundsAllocator.vy#L47-L57

    for pos in range(MAX_POOLS):
        pool : BalancePool = _pool_balances[pos]
        if pool.adapter == empty(address): break

        # If the pool has been removed from the strategy then we must empty it!
        if pool.ratio == 0:
            pool.target = 0
            pool.delta = convert(pool.current, int256) * -1 # Withdraw it all!
        else:
            pool.target = (total_pool_target_assets * pool.ratio) / _total_ratios      
            pool.delta = convert(pool.target, int256) - convert(pool.current, int256)            

When rebalancing the vault, FundsAllocator attempts to withdraw/deposit from each adapter. In the event that the underlying protocol (such as AAVE) disallows deposits or withdrawals (or is hacked), the entire vault would be DOS'd since rebalancing is called on every withdraw, deposit or strategy change.
"""
import pytest

import ape
from tests.conftest import ensure_hardhat, prompt
from web3 import Web3
from eth_abi import encode
import requests, json
import eth_abi
from terminaltables import AsciiTable, DoubleTable, SingleTable
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
def arbitrager(accounts):
    return accounts[2]

@pytest.fixture
def vault(project):
    return project.Vault.at(VAULT)

@pytest.fixture
def dai(project, deployer, trader, ensure_hardhat, arbitrager):
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
    dai.mint(arbitrager, '10000000000 Ether', sender=deployer)
    dai.approve(VAULT, '10000000000 Ether', sender=trader)
    dai.approve(VAULT, '10000000000 Ether', sender=arbitrager)

    # print(dai.balanceOf(trader))
    return project.ERC20.at(DAI)

@pytest.fixture
def funds_alloc(project, deployer):
    f = deployer.deploy(project.FundsAllocator)
    return f

@pytest.fixture
def ddai4626(project, deployer, trader, dai, ensure_hardhat, funds_alloc):
    aave_adapter = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, DAI, ADAI)
    dynamo4626 = deployer.deploy(project.Dynamo4626, "DynamoDAI", "dyDAI", 18, dai, [], deployer, funds_alloc)
    dynamo4626.add_pool(aave_adapter, sender=deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (aave_adapter,1)

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
def compound_adapter(project, deployer, dai, ensure_hardhat):
    ca = deployer.deploy(project.compoundAdapter, dai, CDAI)
    #we run tests against interface
    return project.LPAdapter.at(ca)

@pytest.fixture
def cdai(project, deployer, trader, ensure_hardhat):
    return project.cToken.at(CDAI)

@pytest.fixture
def adai(project, deployer, trader, ensure_hardhat):
    return project.ERC20.at(ADAI)

#Create a multi-adapter vault
def test_lp_ddos(deployer, trader, vault, dai, ddai4626, adai, compound_adapter, cdai):
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS
    pos = 0

    print("HERE!!!!")

    for pool in ddai4626.lending_pools():
        strategy[pos] = (pool, ddai4626.strategy(pool).ratio)
        pos += 1
    strategy[pos] = (compound_adapter.address, 1)
    ddai4626.set_strategy(deployer, strategy, 0, sender=deployer)

    print("HERE2!!!!")


    ddai4626.add_pool(compound_adapter, sender=deployer)    

    #we have aave and compound adapters with 50-50 ratio
    print("HERE3!!!!")

    #trader invest 1000 DAI
    ddai4626.deposit(1000 *10 ** 18, trader, sender=trader)

    print("HEREX!!!!")


    #500 each should have gone to compound and aave
    print(cdai.balanceOfUnderlying(ddai4626, sender=trader).return_value)
    print(adai.balanceOf(ddai4626))


    aave_dai = dai.balanceOf(adai)
    print(aave_dai)


    #AAVE does a rug pull and robs all their dai
    #impersonate adai contract
    impersonate_request = {"jsonrpc": "2.0", "method": "hardhat_impersonateAccount", "id": 1,
        "params": [adai.address]}    
    print(requests.post("http://localhost:8545/", json.dumps(impersonate_request)))
    #allocate some ETH to 4626 so we can issue tx from it
    set_bal_req = {"jsonrpc": "2.0", "method": "hardhat_setBalance", "id": 1,
        "params": [adai.address, "0x1158E460913D00000"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_bal_req)))
    tx_request = {
        "jsonrpc": "2.0",
        "method": "eth_sendTransaction",
        "id": 1,
        "params": [
            {
                "from": adai.address,
                "to": dai.address,
                "gas": "0xF4240", # 1000000
                "gasPrice": "0x9184e72a000", # 10000000000000
                "value": "0x0", # 0
                #burn(adai, dai.balanceOf(adai))
                "data": "0x9dc29fac"  + encode(['address', 'uint256'], [adai.address, aave_dai] ).hex()
            }
        ]
    }
    print(requests.post("http://localhost:8545/", json.dumps(tx_request)))
    print(dai.balanceOf(adai))
    print(ddai4626.balanceOf(trader))
    print(ddai4626.maxWithdraw(trader))
    #Here its crashing... because aave is broken
    #withdrawing 1 DAI will crash, which is legit.
    with ape.reverts():
        ddai4626.withdraw(10**18, trader, trader, sender=trader)

    #we cannot set strategy to 0 aave is the first one
    #this shouldnt crash. basically there should be "something" the owner can do to make the vault usable.
    ddai4626.remove_pool(strategy[0][0], False, sender=deployer)

