import pytest

import ape
from tests.conftest import ensure_hardhat
from web3 import Web3
import requests, json
import eth_abi

MAX_POOLS = 6 # Must match Dynamo4626.vy MAX_POOLS

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"

AAVE_LENDING_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
ADAI = "0x018008bfb33d285247A21d44E50697654f754e63"
AAVE_DAI_SUPPLY_CAP = 338000000000000000000000000

EDAI = "0xe025E3ca2bE02316033184551D4d3Aa22024D9DC"
EULER = "0x27182842E098f60e3D576794A5bFFb0777E025d3"

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
def adai(project, deployer, trader, ensure_hardhat):
    return project.ERC20.at(ADAI)


@pytest.fixture
def edai(project, deployer, trader, ensure_hardhat):
    project.eToken.at("0x27182842E098f60e3D576794A5bFFb0777E025d3")
    project.eToken.at("0xbb0D4bb654a21054aF95456a3B29c63e8D1F4c0a")
    project.IRMClassStable.at("0x42ec0eb1d2746A9f2739D7501C5d5608bdE9eE89")
    return project.eToken.at(EDAI)

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

def test_single_adapter_aave(project, deployer, dynamo4626, aave_adapter, dai, trader, ensure_hardhat, adai):
    dynamo4626.add_pool(aave_adapter, sender=deployer)
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS
    strategy[0] = (aave_adapter,1)    
    dynamo4626.set_strategy(deployer, strategy, 0, sender=deployer)

    assert dai.balanceOf(dynamo4626) == 0, "dynamo4626 should not have any dai"
    assert adai.balanceOf(dynamo4626) == 0, "dynamo4626 should not have any adai"
    assert dai.balanceOf(aave_adapter) == 0, "aave_adapter should not have anything"
    assert adai.balanceOf(aave_adapter) == 0, "aave_adapter should not have anything"
    trader_balance_start = dai.balanceOf(trader)
    assert dynamo4626.balanceOf(trader) == 0, "trader should not have any 4262 shares"
    
    #Test all view functions of 4626 interface
    assert dynamo4626.totalAssets() == 0, "dynamo4626 should not have any assets"
    assert dynamo4626.asset() == DAI
    assert dynamo4626.convertToShares(10**18) == 10**18
    assert dynamo4626.convertToAssets(10**18) == 10**18
    # print(dynamo4626.maxDeposit(trader)) TODO Dynamo4626.vy: wrong argument
    #TODO Dynamo4626.vy: maxMint does not call adapters
    # assert dynamo4626.maxMint(trader) ==  pytest.approx(AAVE_DAI_SUPPLY_CAP - adai.totalSupply())

    # assert dynamo4626.previewDeposit(10**18) == 10**18 TODO Dynamo4626.vy: not a view
    assert dynamo4626.previewMint(10**18) == 10**18 
    assert dynamo4626.maxWithdraw(trader) == 0
    assert dynamo4626.previewWithdraw(10**18) == 10**18 
    assert dynamo4626.maxRedeem(trader) == 0
    assert dynamo4626.previewRedeem(10**18) == 10**18

    #make trader mint 100000 DAI worth...
    dai.approve(dynamo4626,100000 * 10**18, sender=trader)
    dynamo4626.deposit(100000 * 10**18, trader, sender=trader)

    #Now the 4626 contract (via the adapter) would have gotten 100000 DAI and converted it all to 100000 aDAI
    #And trader lost 100000 DAI but gotten 100000 dyDAI
    assert trader_balance_start - 100000 * 10**18 == dai.balanceOf(trader), "traders DAI balance doesnt look right"
    assert dynamo4626.balanceOf(trader) == 100000 * 10**18, "trader should not have any 4262 shares"
    assert dynamo4626.totalAssets() == 100000 * 10**18, "dynamo4626 balance incorrect"
    assert dai.balanceOf(dynamo4626) == 0, "dynamo4626 should not have any dai"
    assert adai.balanceOf(dynamo4626) == 100000 * 10**18, "dynamo4626 should not have any adai"
    assert dai.balanceOf(aave_adapter) == 0, "aave_adapter should not have anything"
    assert adai.balanceOf(aave_adapter) == 0, "aave_adapter should not have anything"
    assert dynamo4626.maxRedeem(trader) == 100000 * 10**18
    print("dynamo4626.maxRedeem(trader) returns %s." % dynamo4626.maxRedeem(trader))
    print("dynamo4626.maxWithdraw(trader) returns\n\t: %s but we were expecting\n\t: %s." % (int(dynamo4626.maxWithdraw(trader)), int(100000 * 10**18)))
    assert dynamo4626.maxWithdraw(trader) == 100000 * 10**18


    #cause aDAI to have a huge yield
    #mine 100000 blocks with an interval of 5 minute
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
        "params": ["0x186a0", "0x12c"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))

    #the 101024025085624200987916 figure came from printing adai.balanceOf(dynamo4626)
    #will be stable unless we change the fork-block 
    yield_rate = 101024025085624200987916 / (100000 * 10**18 ) #from observation

    yielded_balance = yield_rate*(100000 * 10**18)
    #Because theres fees involved...
    available_balance =  yield_rate*(100000 * 10**18) - (0.11*(yield_rate*(100000 * 10**18) - 100000 * 10**18))

    print("POST YIELD!")

    assert dynamo4626.balanceOf(trader) == 100000 * 10**18
    assert dynamo4626.totalAssets() == pytest.approx(yielded_balance)
    assert adai.balanceOf(dynamo4626) == pytest.approx(yielded_balance)
    assert dynamo4626.maxRedeem(trader) == 100000 * 10**18
    assert dynamo4626.maxWithdraw(trader) == pytest.approx(available_balance)
    print("dynamo4626.maxRedeem(trader) returns %s." % dynamo4626.maxRedeem(trader))
    print("dynamo4626.maxWithdraw(trader) returns\n\t: %s but we were expecting\n\t: %s." % (int(dynamo4626.maxWithdraw(trader)), pytest.approx(available_balance)))


    print("aave thinks dynamo4626 has: ", adai.balanceOf(dynamo4626))
    print("dynamo4626 thinks it has: ", dynamo4626.getCurrentBalances()[-2])
    print("adapter thinks it has: ", aave_adapter.totalAssets(sender=dynamo4626))
    print("Traders maxWithdraw", dynamo4626.maxWithdraw(trader))
    print("Traders convertToAssets(shares)", dynamo4626.convertToAssets(dynamo4626.balanceOf(trader)))
    #Lets withdraw it all...

    t_shares = dynamo4626.maxRedeem(trader)
    req_assets = int(dynamo4626.convertToAssets(t_shares))
    returns = dynamo4626.totalReturns()
    claimable_fees = dynamo4626.claimable_all_fees_available()    
    claim_yield_fees = dynamo4626.claimable_yield_fees_available()
    claim_strat_fees = dynamo4626.claimable_strategy_fees_available()
    remaining_assets = int(dynamo4626.totalAssets() - claimable_fees)
    print("Trader shares are : %s." % t_shares)
    print("Requires assets for those shares are: %s." % req_assets)
    print("Estimated available_balance is %s." % available_balance)
    print("There are %s assets as returns." % returns)
    print("There are %s assets reserved as claimable fees." % claimable_fees)
    print("\t%s are yield fees\n\t%s are strategy fees." % (claim_yield_fees,claim_strat_fees))
    print("\tDifference due to rounding is %s." % (claimable_fees - (claim_yield_fees+claim_strat_fees)))
    print("There are %s assets remaining to withdraw overall." % remaining_assets)
    if req_assets > remaining_assets:
        print("Shortage is %s." % (remaining_assets - req_assets))
    else:
        print("Overage is %s." % (remaining_assets - req_assets))               
    assert t_shares >= 100000 * 10**18 , "trader has insufficient shares."
    assert req_assets <= remaining_assets, "vault doesn't have enough free assets for trader withdraw"

    # 100000000000000000000000
    # 100911382320000000000000

    dynamo4626.redeem(100000 * 10**18 , trader, trader, sender=trader)

    assert dynamo4626.balanceOf(trader) == 0
    print("dynamo4626.balanceOf(trader) should be close to 0 but is: %s." % dynamo4626.balanceOf(trader))
    assert dynamo4626.totalAssets() == pytest.approx(yielded_balance - available_balance)
    assert adai.balanceOf(dynamo4626) == pytest.approx(yielded_balance - available_balance)
    print("dynamo4626.maxRedeem(trader) should be close to 0 but is: %s." % dynamo4626.maxRedeem(trader))      
    print("dynamo4626.maxWithdraw(trader) should be close to 0 but is: %s." % dynamo4626.maxWithdraw(trader))  
    assert dynamo4626.maxRedeem(trader) == 0
    print("next to last test!")
    assert dynamo4626.maxWithdraw(trader) == 0
    print("last test!")
    assert dai.balanceOf(trader) == pytest.approx(trader_balance_start + (available_balance - 100000 * 10**18))
