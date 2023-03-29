import pytest

import ape
from tests.conftest import ensure_hardhat
from web3 import Web3
import requests, json
import eth_abi


#ETH Mainnet addrs
VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"

AAVE_LENDING_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
ADAI = "0x018008bfb33d285247A21d44E50697654f754e63"
AAVE_DAI_SUPPLY_CAP = 338000000000000000000000000
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
def vault(project, ensure_hardhat):
    return project.Vault.at(VAULT)

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
    dai.approve(VAULT, '10000000000 Ether', sender=trader)

    # print(dai.balanceOf(trader))
    return project.ERC20.at(DAI)


@pytest.fixture
def aave_adapter(project, deployer, dai, ensure_hardhat):
    aa = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, DAI, ADAI)
    #we run tests against interface
    return project.LPAdapter.at(aa)

@pytest.fixture
def ddai4626(project, deployer, trader, dai, ensure_hardhat, aave_adapter):
    dynamo4626 = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, [], deployer)
    dynamo4626.add_pool(aave_adapter, sender=deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (aave_adapter,1)

    dynamo4626.set_strategy(deployer, strategy, 0, sender=deployer)
    #Grant allowance for trader
    dai.approve(dynamo4626, 100000 *10 ** 18, sender=trader)
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
def linear_pool(project, deployer, dai, ddai4626, ensure_hardhat):
    lp = deployer.deploy(
        #We are using mock here which hardcodes exchange rate of 1:1
        #TODO: once we have a somewhat working 4626, we should probably use ERC4626LinearPool
        project.ERC4626LinearPool,
        VAULT,
        "DAI 4626 linear pool",
        "dDAI",
        dai, #mainToken
        ddai4626, #wrappedToken
        2100000000000000000000000, #upperTarget = 2100000.0 DAI (by default lower target is 0, can be raised after enough liquidity is present)
        10000000000000, #swapFeePercentage = 0.001% (10000000000000 = 10^13 ; 10^18/10^13 = 100000; 100 / 100000 = 0.001%)
        7332168, #pauseWindowDuration
        2592000, #bufferPeriodDuration
        deployer
    )
    #Copied some constructor args from https://etherscan.io/token/0x804cdb9116a10bb78768d3252355a1b18067bf8f#code
    lp.initialize(sender=deployer)
    return lp

def tokendiff(user, tokens, prev={}):
    for token in tokens.keys():
        bal = tokens[token].balanceOf(user) / 10**18
        prev_bal = prev.get(token, 0)
        print("{token}\t: {bal:.4f} ({delta:+.4f})".format(token=token, bal=bal, delta=bal - prev_bal))
        prev[token] = bal
    return prev

def print_pool_info(vault, pool_id, main_idx, wrapped_idx):
    ret = vault.getPoolTokens(pool_id)
    print( "DAI(pool): {bal:.4f}".format(bal=ret.balances[main_idx] / 10**18 ))
    print( "dDAI4626(pool): {bal:.4f}".format(bal=ret.balances[wrapped_idx] / 10**18))


def test_pool_swap(linear_pool, dai, ddai4626, trader, vault, ensure_hardhat):
    assert dai.balanceOf(trader) == (10000000000 - 100000) * 10**18
    assert ddai4626.balanceOf(trader) == 100000 * 10**18
    assert linear_pool.balanceOf(trader) == 0
    pool_id = linear_pool.getPoolId()
    main_idx = linear_pool.getMainIndex()
    wrapped_idx = linear_pool.getWrappedIndex()
    #Print pool's balance
    print("dai", dai.balanceOf(trader)/10**18)
    print("ddai4626", ddai4626.balanceOf(trader)/10**18)
    print("linear_pool", linear_pool.balanceOf(trader)/10**18)
    #do couple of swaps
    #Swap 1 DAI for 1 pool token
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        dai, #IAsset assetIn
        linear_pool, #IAsset assetOut
        "1 Ether", #uint256 amount
        b"" #bytes userData
    )
    struct_fund_management = (
        trader, #address sender
        False, #bool fromInternalBalance
        trader, #address payable recipient
        False #bool toInternalBalance
    )    
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    tokens = {
        "DAI": dai,
        "dDAI4626": ddai4626,
        "dDAI": linear_pool
    }
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #Swap 1 dDAI4626 for 1 pool token
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        ddai4626, #IAsset assetIn
        linear_pool, #IAsset assetOut
        "1000 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2000 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #Swap 1 pool token for 1 DAI
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        linear_pool, #IAsset assetIn
        dai, #IAsset assetOut
        "1 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #Swap 1 DAI for 1 dDAI4626
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        dai, #IAsset assetIn
        ddai4626, #IAsset assetOut
        "1 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)

    #now the upperTarget is 2100000 , we already have 1 DAI in pool, lets add 2099999
    #Swap 2099999 DAI for 2099999 pool token
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        dai, #IAsset assetIn
        linear_pool, #IAsset assetOut
        "9999 Ether", #uint256 amount
        b"" #bytes userData
    )
    struct_fund_management = (
        trader, #address sender
        False, #bool fromInternalBalance
        trader, #address payable recipient
        False #bool toInternalBalance
    )    
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "19999 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #now we are at upper limit. it should become more costly to add DAI to the pool
    #Swap 1000.01000011 DAI for 1000 pool token
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        dai, #IAsset assetIn
        linear_pool, #IAsset assetOut
        "1000 Ether", #uint256 amount
        b"" #bytes userData
    )
    struct_fund_management = (
        trader, #address sender
        False, #bool fromInternalBalance
        trader, #address payable recipient
        False #bool toInternalBalance
    )    
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #Lets make our 4626 get 
    print(linear_pool.getRate())
    #cause aDAI to have a huge yield
    #mine 100000 blocks with an interval of 5 minute
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
        "params": ["0x186a0", "0x12c"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    print("===GENERATED YIELD BY TRAVELING FORWARD IN TIME===")    
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    print(linear_pool.getRate())

   
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2010.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #now when depositing ddai4626 we should get better price
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        ddai4626, #IAsset assetIn
        linear_pool, #IAsset assetOut
        "1000 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        ddai4626, #IAsset assetIn
        dai, #IAsset assetOut
        "1000 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #withdraw 1000 dDAI for DAI
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        linear_pool, #IAsset assetIn
        dai, #IAsset assetOut
        "1000 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "2000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    #withdraw 1000 dDAI for dDAI4626
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        linear_pool, #IAsset assetIn
        ddai4626, #IAsset assetOut
        "100 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "3000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    print_pool_info(vault, pool_id, main_idx, wrapped_idx)
    print(linear_pool.getRate())
    print(linear_pool.getWrappedTokenRate())
