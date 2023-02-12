import pytest

import ape
from tests.conftest import ensure_hardhat
from web3 import Web3
import requests, json
import eth_abi

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
AAVE_LENDING_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
ADAI = "0x018008bfb33d285247A21d44E50697654f754e63"


@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def adai(project, deployer, trader, ensure_hardhat):
    return project.ERC20.at(ADAI)


@pytest.fixture
def dai(project, deployer, trader, ensure_hardhat):
    dai = project.DAI.at(DAI)
    # print("wards", dai.wards(deployer))
    #Make deployer a minter
    #background info https://mixbytes.io/blog/modify-ethereum-storage-hardhats-mainnet-fork
    #Dai contract has  minters in first slot mapping (address => uint) public wards;
    abi_encoded = eth_abi.encode(['address', 'uint256'], [deployer.address, 0])
    storage_slot = Web3.solidityKeccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()

    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [DAI, storage_slot, "0x" + eth_abi.encode(["uint256"], [1]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    # print("wards", dai.wards(deployer))
    #make the trader rich, airdrop $1 billion
    dai.mint(trader, '10000000000 Ether', sender=deployer)
    # print(dai.balanceOf(trader))
    return project.ERC20.at(DAI)

@pytest.fixture
def aave_adapter(project, deployer, dai, ensure_hardhat):
    aa = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, dai, ADAI)
    #we run tests against interface
    #return project.LPAdapter.at(aa)
    #I wanted to run tests against interface, but seems vyper does not treat interface file as such?
    return aa

def test_aave_adapter(aave_adapter, trader, dai, adai, ensure_hardhat):
    #Dont have any state...
    assert aave_adapter.assetBalance() == 0, "Asset balance should be 0"
    assert aave_adapter.maxWithdrawable() == 0, "maxWithdrawable should be 0"
    assert aave_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    assert adai.balanceOf(aave_adapter) == 0, "adai balance incorrect"
    #Deposit 1000,000 DAI
    #Normally this would be delegate call from 4626 that already has the funds,
    #but here we fake it by transferring DAI first then doing a CALL
    dai.transfer(aave_adapter, "1000000 Ether", sender=trader)
    aave_adapter.deposit("1000000 Ether", sender=trader) #Anyone can call this, its intended to be delegate
    #There is no yield yet... so everything should be a million
    assert adai.balanceOf(aave_adapter) < 1000001*10**18, "adai balance incorrect"
    assert aave_adapter.assetBalance() < 1000001*10**18, "Asset balance should be 1000000"
    assert aave_adapter.maxWithdrawable() < 1000001*10**18, "maxWithdrawable should be 1000000"
    assert aave_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    # print(adai.balanceOf(aave_adapter))
    #cause aDAI to have a huge profit
    #mine 100000 blocks with an interval of 5 minute
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
        "params": ["0x186a0", "0x12c"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    # print(adai.balanceOf(aave_adapter))
    assert adai.balanceOf(aave_adapter) == pytest.approx(1007704413122972883649524), "adai balance incorrect"
    assert aave_adapter.assetBalance() == pytest.approx(1007704413122972883649524), "Asset balance should be 1000000"
    assert aave_adapter.maxWithdrawable() == pytest.approx(1007704413122972883649524), "maxWithdrawable should be 1000000"
    assert aave_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    #Withdraw everything
    trader_balance_pre = dai.balanceOf(trader)
    aave_adapter.withdraw(aave_adapter.assetBalance(), trader, sender=trader)
    trader_gotten = dai.balanceOf(trader) - trader_balance_pre
    assert trader_gotten == pytest.approx(1007704413465903087954661), "trader gain balance incorrect"
    assert aave_adapter.assetBalance() < 10**18, "Asset balance should be 0"
    assert aave_adapter.maxWithdrawable() < 10**18, "maxWithdrawable should be 0"
    assert aave_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    assert adai.balanceOf(aave_adapter) < 10**18, "adai balance incorrect"

