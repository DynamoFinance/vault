import pytest

import ape
from tests.conftest import is_not_hard_hat
from web3 import Web3
import requests, json
import eth_abi

DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
EDAI = "0xe025E3ca2bE02316033184551D4d3Aa22024D9DC"
EULER = "0x27182842E098f60e3D576794A5bFFb0777E025d3"

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def edai(project, deployer, trader):
    project.eToken.at("0x27182842E098f60e3D576794A5bFFb0777E025d3")
    project.eToken.at("0xbb0D4bb654a21054aF95456a3B29c63e8D1F4c0a")
    project.IRMClassStable.at("0x42ec0eb1d2746A9f2739D7501C5d5608bdE9eE89")
    return project.eToken.at(EDAI)

@pytest.fixture
def dai(project, deployer, trader):
    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")
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
def euler_adapter(project, deployer, dai):
    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")
    ca = deployer.deploy(project.eulerAdapter, dai, EDAI, EULER)
    #we run tests against interface
    #return project.LPAdapter.at(aa)
    #I wanted to run tests against interface, but seems vyper does not treat interface file as such?
    return ca

def test_euler_adapter(euler_adapter, trader, dai, edai):
    if is_not_hard_hat():
        pytest.skip("Not on hard hat Ethereum snapshot.")
    #Dont have any state...
    assert euler_adapter.assetBalance() == 0, "Asset balance should be 0"
    assert euler_adapter.maxWithdrawable() == 0, "maxWithdrawable should be 0"
    assert euler_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    assert edai.balanceOf(euler_adapter) == 0, "adai balance incorrect"
    #Deposit 1000,000 DAI
    #Normally this would be delegate call from 4626 that already has the funds,
    #but here we fake it by transferring DAI first then doing a CALL
    dai.transfer(euler_adapter, "10000 Ether", sender=trader)
    print("trying deposit")
    dai.approve(EULER, "10000 Ether", sender=trader)
    recpt = edai.deposit(0, "10000 Ether", sender=trader)
    recpt.show_trace(verbose=True)
    # return
    try:
        foo = euler_adapter.deposit("10000 Ether", sender=trader,gas=10000000) #Anyone can call this, its intended to be delegate
        print(foo)
    except:
        b = ape.chain.provider.get_block("latest")
        print(b)
        print(b.transactions[0])
        recpt = ape.chain.provider.get_receipt(b.transactions[0].txn_hash)
        print(recpt)
        recpt.show_trace(verbose=True)
        raise
    return
    #There is no yield yet... so everything should be a million
    assert cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value < 1000001*10**18, "adai balance incorrect"
    assert compound_adapter.assetBalance() < 1000001*10**18, "Asset balance should be 1000000"
    assert compound_adapter.maxWithdrawable() < 1000001*10**18, "maxWithdrawable should be 1000000"
    assert cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value > 999999*10**18, "adai balance incorrect"
    assert compound_adapter.assetBalance() > 999999*10**18, "Asset balance should be 1000000"
    assert compound_adapter.maxWithdrawable() > 999999*10**18, "maxWithdrawable should be 1000000"
    assert compound_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    #cause cDAI to have a huge profit
    #mine 100000 blocks with an interval of 5 minute
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
        "params": ["0x186a0", "0x12c"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    # print(cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value)

    assert cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value < 1000345*10**18, "adai balance incorrect"
    assert compound_adapter.assetBalance() < 1000345*10**18, "Asset balance should be 1000000"
    assert compound_adapter.maxWithdrawable() < 1000345*10**18, "maxWithdrawable should be 1000000"
    assert cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value > 1000344*10**18, "adai balance incorrect"
    assert compound_adapter.assetBalance() > 1000344*10**18, "Asset balance should be 1000000"
    assert compound_adapter.maxWithdrawable() > 1000344*10**18, "maxWithdrawable should be 1000000"
    assert compound_adapter.maxDepositable() == 2**256 - 1, "maxDepositable should be MAX_UINT256"
    #Withdraw everything
    trader_balance_pre = dai.balanceOf(trader)
    compound_adapter.withdraw(cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value, trader, sender=trader)
    trader_gotten = dai.balanceOf(trader) - trader_balance_pre
    assert trader_gotten > 1000344*10**18, "trader gain balance incorrect"
    print(cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value)
    assert cdai.balanceOfUnderlying(compound_adapter, sender=trader).return_value < 10**18, "adai balance incorrect"
    assert compound_adapter.assetBalance() < 10**18, "Asset balance should be 1000000"
    assert compound_adapter.maxWithdrawable() < 10**18, "maxWithdrawable should be 1000000"
