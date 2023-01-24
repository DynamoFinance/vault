import pytest

import ape
from tests.conftest import is_not_hard_hat
from web3 import Web3


#ETH Mainnet addrs
WETH  = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
BAL   = "0xba100000625a3754423978a60c9317c58a424e3D"
POOL_BAL_WETH = "0x5c6Ee304399DBdB9C8Ef030aB642B10820DB8F56"
pool_BAL_WETH = "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56000200000000000000000014"
VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"



@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def weth(project):
    return project.IERC20.at(WETH)

@pytest.fixture
def bal(project):
    return project.IERC20.at(BAL)

@pytest.fixture
def vault(project):
    return project.Vault.at(VAULT)

@pytest.fixture
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "mock DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, '5000000000 Ether', sender=deployer)
    print(ua.balanceOf(trader))
    #Aprove vault
    ua.approve(VAULT, '1000000000 Ether', sender=trader)
    return ua

@pytest.fixture
def ddai4626(project, deployer, trader, dai):
    #just a placeholder token. has no relation to dai.
    ua = deployer.deploy(project.Fake4626, "Wrapped DAI", "dDAI4626", 18, dai)
    #Grant allowance for trader
    dai.approve(ua, '2000000000 Ether', sender=trader)
    #Transfer some to trader.
    ua.deposit('1000000000 Ether', trader, sender=trader)
    # ua.mint(trader, '1000000000 Ether', sender=deployer)
    # print(ua.balanceOf(trader))
    #Aprove vault
    ua.approve(VAULT, '1000000000 Ether', sender=trader)
    return ua


@pytest.fixture
def linear_pool(project, deployer, dai, ddai4626):
    lp = deployer.deploy(
        #We are using mock here which hardcodes exchange rate of 1:1
        #TODO: once we have a somewhat working 4626, we should probably use ERC4626LinearPool
        project.ERC4626LinearPool,
        VAULT,
        "DAI 4626 linear pool",
        "dDAI",
        dai.address, #mainToken
        ddai4626.address, #wrappedToken
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

def test_pool_swap(linear_pool, dai, ddai4626, trader, vault):
    assert dai.balanceOf(trader) == 4000000000 * 10**18
    assert ddai4626.balanceOf(trader) == 1000000000 * 10**18
    assert linear_pool.balanceOf(trader) == 0
    pool_id = linear_pool.getPoolId()
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
    #Swap 1 dDAI4626 for 1 pool token
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        ddai4626, #IAsset assetIn
        linear_pool, #IAsset assetOut
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

    #now the upperTarget is 2100000 , we already have 1 DAI in pool, lets add 2099999
    #Swap 2099999 DAI for 2099999 pool token
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        dai, #IAsset assetIn
        linear_pool, #IAsset assetOut
        "2099999 Ether", #uint256 amount
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
        "2099999 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
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
        "1000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
    #Lets make our 4626 get 2x yiels
    dai.transfer(ddai4626, '1000000000 Ether', sender=trader)
    bal = tokendiff(trader, tokens)
    
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "1000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
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
        "1000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
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
        "1000.1 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(trader, tokens)
