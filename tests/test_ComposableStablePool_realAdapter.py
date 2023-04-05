import pytest

import ape
from tests.conftest import ensure_hardhat
from web3 import Web3
from eth_abi import encode
import requests, json
import eth_abi
from terminaltables import AsciiTable, DoubleTable, SingleTable

#ETH Mainnet addrs
VAULT = "0xBA12222222228d8Ba445958a75a0704d566BF2C8"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
FRAX = "0x853d955aCEf822Db058eb8505911ED77F175b99e"

AAVE_LENDING_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
ADAI = "0x018008bfb33d285247A21d44E50697654f754e63"
BTC_FRAX_PAIR = "0x32467a5fc2d72D21E8DCe990906547A2b012f382"




@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def vault(project):
    return project.Vault.at(VAULT)

@pytest.fixture
def dai(project, deployer, trader, ensure_hardhat):
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
    dai.approve(VAULT, '10000000000 Ether', sender=trader)

    # print(dai.balanceOf(trader))
    return project.ERC20.at(DAI)


@pytest.fixture
def frax(project, deployer, trader, ensure_hardhat):
    frax = project.ERC20.at(FRAX)
    #TODO: Ensure trader has enough FRAX
    #first storage slot: mapping (address => uint256) internal _balances; 
    abi_encoded = eth_abi.encode(['address', 'uint256'], [trader.address, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [FRAX, storage_slot, "0x" + eth_abi.encode(["uint256"], [10**28]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    frax.approve(VAULT, '5000000000 Ether', sender=trader)
    return frax


@pytest.fixture
def gho(project, deployer, trader, ensure_hardhat):
    ua = deployer.deploy(project.ERC20, "GHO", "GHO", 18, 0, deployer)
    ua.mint(trader, '5000000000 Ether', sender=deployer)
    ua.approve(VAULT, '5000000000 Ether', sender=trader)
    return ua

@pytest.fixture
def ddai4626(project, deployer, trader, dai, ensure_hardhat):
    aave_adapter = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, DAI, ADAI)
    dynamo4626 = deployer.deploy(project.Dynamo4626, "DynamoDAI", "dyDAI", 18, dai, [], deployer)
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
def fraxpair(project, ensure_hardhat):
    return project.fraxpair.at(BTC_FRAX_PAIR)


@pytest.fixture
def dfrax4626(project, deployer, trader, frax, ensure_hardhat):
    fa = deployer.deploy(project.fraxlendAdapter, BTC_FRAX_PAIR, FRAX)
    dynamo4626 = deployer.deploy(project.Dynamo4626, "DynamoFRAX", "dyFRAX", 18, frax, [], deployer)
    dynamo4626.add_pool(fa, sender=deployer)
    strategy = [(ZERO_ADDRESS,0)] * 5 # This assumes Dynamo4626 MAX_POOLS == 5
    strategy[0] = (fa,1)

    dynamo4626.set_strategy(deployer, strategy, 0, sender=deployer)
    #Grant allowance for trader
    frax.approve(dynamo4626, 100000 *10 ** 18, sender=trader)
    #Transfer some to trader.
    assert frax.allowance(trader, dynamo4626) >= 100000 *10 ** 18, "dynamo4626 does not have allowance"
    assert frax.balanceOf(trader) >= 100000 *10 ** 18, "trader is broke"
    #Previous like confirms trader has enough money
    dynamo4626.deposit(100000 *10 ** 18, trader, sender=trader)
    # ua.mint(trader, '1000000000 Ether', sender=deployer)
    # print(ua.balanceOf(trader))
    #Aprove vault
    dynamo4626.approve(VAULT, '1000000000 Ether', sender=trader)
    return dynamo4626


@pytest.fixture
def dgho4626(project, deployer, trader, gho, ensure_hardhat):
    ua = deployer.deploy(project.Fake4626, "Wrapped GHO", "dGHO4626", 18, gho)
    gho.approve(ua, '2000000000 Ether', sender=trader)
    ua.deposit('1000 Ether', trader, sender=trader)
    ua.approve(VAULT, '1000000000 Ether', sender=trader)
    return ua

def swap(pool_id, vault, intoken, outtoken, amount, trader):
    struct_single_swap = (
        pool_id, #bytes32 poolId
        1, #SwapKind kind
        intoken, #IAsset assetIn
        outtoken, #IAsset assetOut
        amount, #uint256 amount
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
        "20000000000 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )

@pytest.fixture
def dDAI(project, deployer, dai, ddai4626, vault, trader, ensure_hardhat):
    lp = deployer.deploy(
        #We are using mock here which hardcodes exchange rate of 1:1
        #TODO: once we have a somewhat working 4626, we should probably use ERC4626LinearPool
        project.ERC4626LinearPool,
        vault,
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
    #Create some liquidity to avoid BAL#004 (ZERO_DIVISION)
    pool_id = lp.getPoolId()
    swap(pool_id, vault, dai, lp, "1000 Ether", trader)
    swap(pool_id, vault, ddai4626, lp, "1000 Ether", trader)
    return lp

@pytest.fixture
def dFRAX(project, deployer, frax, dfrax4626, vault, trader, ensure_hardhat):
    lp = deployer.deploy(
        #We are using mock here which hardcodes exchange rate of 1:1
        #TODO: once we have a somewhat working 4626, we should probably use ERC4626LinearPool
        project.ERC4626LinearPool,
        vault,
        "FRAX 4626 linear pool",
        "dFRAX",
        frax, #mainToken
        dfrax4626, #wrappedToken
        2100000000000000000000000, #upperTarget = 2100000.0 DAI (by default lower target is 0, can be raised after enough liquidity is present)
        10000000000000, #swapFeePercentage = 0.001% (10000000000000 = 10^13 ; 10^18/10^13 = 100000; 100 / 100000 = 0.001%)
        7332168, #pauseWindowDuration
        2592000, #bufferPeriodDuration
        deployer
    )
    #Copied some constructor args from https://etherscan.io/token/0x804cdb9116a10bb78768d3252355a1b18067bf8f#code
    lp.initialize(sender=deployer)
    #Create some liquidity to avoid BAL#004 (ZERO_DIVISION)
    pool_id = lp.getPoolId()
    swap(pool_id, vault, frax, lp, "1000 Ether", trader)
    swap(pool_id, vault, dfrax4626, lp, "1000 Ether", trader)
    return lp

@pytest.fixture
def dGHO(project, deployer, gho, dgho4626, vault, trader, ensure_hardhat):
    lp = deployer.deploy(
        #We are using mock here which hardcodes exchange rate of 1:1
        #TODO: once we have a somewhat working 4626, we should probably use ERC4626LinearPool
        project.ERC4626LinearPool,
        VAULT,
        "GHO 4626 linear pool",
        "dGHO",
        gho, #mainToken
        dgho4626, #wrappedToken
        2100000000000000000000000, #upperTarget = 2100000.0 DAI (by default lower target is 0, can be raised after enough liquidity is present)
        10000000000000, #swapFeePercentage = 0.001% (10000000000000 = 10^13 ; 10^18/10^13 = 100000; 100 / 100000 = 0.001%)
        7332168, #pauseWindowDuration
        2592000, #bufferPeriodDuration
        deployer
    )
    #Copied some constructor args from https://etherscan.io/token/0x804cdb9116a10bb78768d3252355a1b18067bf8f#code
    lp.initialize(sender=deployer)
    #Create some liquidity to avoid BAL#004 (ZERO_DIVISION)
    pool_id = lp.getPoolId()
    swap(pool_id, vault, gho, lp, "1000 Ether", trader)
    swap(pool_id, vault, dgho4626, lp, "1000 Ether", trader)
    return lp

@pytest.fixture
def dUSD(project, deployer, vault, dai, frax, gho, dDAI, dFRAX, dGHO, ensure_hardhat):
    #Example pool: https://etherscan.io/address/0xa13a9247ea42d743238089903570127dda72fe44
    #Tokens must be sorted, no idea why it was passing earlier, perhaps because of coincidence.
    tokens = [t.address for t in [dDAI, dFRAX, dGHO]]
    tokens.sort()
    sp = deployer.deploy(
        project.ComposableStablePool,
        (
            vault, #vault
            "0x97207B095e4D5C9a6e4cfbfcd2C3358E03B90c4A", #protocolFeeProvider: dunno copied from existing pool
            "dUSD", #name
            "dUSD", #symbol
            tokens, #tokens
            tokens, #rateProviders: Linearpool themselves are oracles
            #Do we need some other price oracle too to account for potential difference in price between stablecoins?
            [0, 0, 0], #tokenRateCacheDurations: Does 0 disable caching?
            [False,False,False], #exemptFromYieldProtocolFeeFlags: ???
            1472, #amplificationParameter: ??
            100000000000000, #swapFeePercentage: ??
            0, #pauseWindowDuration
            0, #bufferPeriodDuration
            deployer, #owner
            "no idea" #version
        )
    )
    # sp.initialize(sender=deployer)
    return sp

def test_composable_protocol_fee(trader, vault, dai, frax, gho, dDAI, dFRAX, dGHO, dUSD, ddai4626, dfrax4626, dgho4626, ensure_hardhat):
    fee_collector = dUSD.getProtocolFeesCollector()
    tokens = {
        "DAI": dai,
        "dDAI": dDAI,
        "dFRAX": dFRAX,
        "dGHO": dGHO,
        "dUSD": dUSD
    }
    dUSD_pool_id = dUSD.getPoolId()
    print(fee_collector)
    holders = {
        "fee_collector": fee_collector
    }
    bal = tokendiff(holders, tokens)
    join_tokens = [t.address for t in [dDAI, dFRAX, dGHO, dUSD]]
    join_tokens.sort()
    join_vals = {
        dDAI.address: 1000000000000000000,
        dFRAX.address: 1000000000000000000,
        dGHO.address: 1000000000000000000,
        dUSD.address: 5192296858534827628530496329000000
    }
    vault.joinPool(
        dUSD_pool_id,
        trader, #sender
        trader, #recipient
        (
            join_tokens, #assets
            [join_vals[t] for t in join_tokens], #maxAmountsIn
            encode(['uint256', 'uint256[]'], [
                0, #JoinKind.INIT
                (
                    join_vals[join_tokens[0]],
                    join_vals[join_tokens[1]],
                    join_vals[join_tokens[2]],
                    join_vals[join_tokens[3]],
                )
            ]  ), #bytes userData
            False #fromInternalBalance
        ),
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
    join_tokens = [t.address for t in [dDAI, dFRAX, dGHO, dUSD]]
    join_tokens.sort()
    join_tokens_nobpt = [t.address for t in [dDAI, dFRAX, dGHO]]
    join_tokens_nobpt.sort()
    
    join_vals = {
        dDAI.address: 500*10**18,
        dFRAX.address: 0,
        dGHO.address: 0,
        dUSD.address: 200*10**18
    }

    traderbal_pre = dUSD.balanceOf(trader)

    vault.joinPool(
        dUSD_pool_id,
        trader, #sender
        trader, #recipient
        (
            join_tokens, #assets
            [join_vals[t] for t in join_tokens], #maxAmountsIn
            encode(['uint256', 'uint256[]', 'uint256'], [
                1, #JoinKind.EXACT_TOKENS_IN_FOR_BPT_OUT
                (
                    join_vals[join_tokens_nobpt[0]],
                    join_vals[join_tokens_nobpt[1]],
                    join_vals[join_tokens_nobpt[2]],
                ), #amountsIn
                join_vals[dUSD.address] #minimumBPT
            ]  ), #bytes userData
            False #fromInternalBalance
        ),
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
    print("trader got", (dUSD.balanceOf(trader)-  traderbal_pre )/ 10**18)

@pytest.fixture
def adai(project, deployer, trader, ensure_hardhat):
    return project.ERC20.at(ADAI)

ENDC = '\033[0m'
MINUS = '\033[91m'
POSIT = '\033[92m'

def tokendiff(holders, tokens, prev={}):
    table_data = [['']]
    for token in tokens.keys():
        table_data += [[token]]
    for user in holders.keys():
        userdata = []
        table_data[0] += [user]
        prev_user = prev.get(user, {})
        idx = 0
        for token in tokens.keys():
            bal = tokens[token].balanceOf(holders[user]) / 10**18
            prev_bal = prev_user.get(token, 0)
            if prev_bal > bal:
                line = "{bal:,.2f} (\033[91m{delta:+,.2f}\033[0m)".format(token=token, bal=bal, delta=bal - prev_bal)
            elif bal > prev_bal:
                line = "{bal:,.2f} (\033[92m{delta:+,.2f}\033[0m)".format(token=token, bal=bal, delta=bal - prev_bal)
            else:
                line = "{bal:,.2f} ({delta:+,.2f})".format(token=token, bal=bal, delta=bal - prev_bal)
            idx += 1
            table_data[idx] += [line]
            prev_user[token] = bal
        prev[user] = prev_user
    table_instance = SingleTable(table_data, "title")
    print(table_instance.table)
    return prev

def test_composable(deployer, trader, vault, dai, frax, gho, dDAI, dFRAX, dGHO, dUSD, ddai4626, dfrax4626, dgho4626, ensure_hardhat, adai, fraxpair):
    #ensure oracle of each d-token returns 1 (since no yield yet)
    assert dDAI.getRate() == pytest.approx(10**18), "rate is not 1"
    assert dFRAX.getRate() == pytest.approx(10**18), "rate is not 1"
    assert dGHO.getRate() == pytest.approx(10**18), "rate is not 1"
    dUSD_pool_id = dUSD.getPoolId()
    # assert dUSD.getRate() == 10**18, "rate is not 1"
    holders = {
        "trader": trader,
        "ddai4626": ddai4626,
        "vault (balancer)": vault,
        "fee_collector": dUSD.getProtocolFeesCollector(),
    }
    tokens = {
        "DAI": dai,
        "FRAX": frax,
        "dDAI": dDAI,
        "dFRAX": dFRAX,
        "dGHO": dGHO,
        "dUSD": dUSD,
        "dyDAI": ddai4626,
        "aDAI": adai
    }
    print("==== Initial balances ====")
    bal = tokendiff(holders, tokens)
    print("Trader will now perform initial join to composable stable pool by supplying 1 dDAI, 1 dFRAX, 1 dGHO")
    input("enter to continue")
    #Invest some LP tokens into the stable pool 
    #No idea where 5192296858534827628530496329000000 figure came from
    #Copied init args from https://etherscan.io/tx/0x9a23e5a994b1b8bab3b9fa28a7595ef64aa0d4dd115ae5c41e802f0d84aa4a71
    #Add $1 of each stable coin.
    join_tokens = [t.address for t in [dDAI, dFRAX, dGHO, dUSD]]
    join_tokens.sort()
    join_vals = {
        dDAI.address: 1000000000000000000,
        dFRAX.address: 1000000000000000000,
        dGHO.address: 1000000000000000000,
        dUSD.address: 5192296858534827628530496329000000
    }

    vault.joinPool(
        dUSD_pool_id,
        trader, #sender
        trader, #recipient
        (
            join_tokens, #assets
            [join_vals[t] for t in join_tokens], #maxAmountsIn
            encode(['uint256', 'uint256[]'], [
                0, #JoinKind.INIT
                (
                    join_vals[join_tokens[0]],
                    join_vals[join_tokens[1]],
                    join_vals[join_tokens[2]],
                    join_vals[join_tokens[3]],
                )
            ]  ), #bytes userData
            False #fromInternalBalance
        ),
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
    print("Trader will now supply following to dUSD pool : 200 dDAI, 150 dFRAX, 100 dGHO")
    input("enter to continue")
    #Lets add some more... 200 dDAI, 150 dFRAX and 100 dGHO for < 450 dUSD (because of fees)
    join_tokens = [t.address for t in [dDAI, dFRAX, dGHO, dUSD]]
    join_tokens.sort()
    join_tokens_nobpt = [t.address for t in [dDAI, dFRAX, dGHO]]
    join_tokens_nobpt.sort()
    join_vals = {
        dDAI.address: 200*10**18,
        dFRAX.address: 150*10**18,
        dGHO.address: 100*10**18,
        dUSD.address: 449*10**18
    }
    vault.joinPool(
        dUSD_pool_id,
        trader, #sender
        trader, #recipient
        (
            join_tokens, #assets
            [join_vals[t] for t in join_tokens], #maxAmountsIn
            encode(['uint256', 'uint256[]', 'uint256'], [
                1, #JoinKind.EXACT_TOKENS_IN_FOR_BPT_OUT
                (
                    join_vals[join_tokens_nobpt[0]],
                    join_vals[join_tokens_nobpt[1]],
                    join_vals[join_tokens_nobpt[2]],
                ), #amountsIn
                join_vals[dUSD.address] #minimumBPT
            ]  ), #bytes userData
            False #fromInternalBalance
        ),
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
    #i.e. 1 dDAI = 1.5 DAI
    # dai.transfer(ddai4626, '1000 Ether', sender=trader)
    #simulate passage of time, about 1 year
    #100000 blocks; 300 seconds per block
    print("We will now generate yield by moving time forward by approx 350 days")
    input("enter to continue")
    # print(dDAI.getRate() )
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_mine", "id": 1,
        "params": ["0x186a0", "0x12c"]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    print("===GENERATED YIELD BY TRAVELING FORWARD IN TIME===")    
    #Frax needs some activity to poke the interest values
    fraxpair.addInterest(sender=deployer)


    bal = tokendiff(holders, tokens, bal)

    # print(dDAI.getRate() )
    # print(dDAI.getWrappedTokenRate() )
    # print(dai.balanceOf(ddai4626))
    # print(adai.balanceOf(ddai4626))
    # print(dFRAX.getRate())
    # print(dFRAX.getWrappedTokenRate())
    assert dDAI.getRate() ==  pytest.approx(1004556914843360804), "rate is not correct"
    assert dFRAX.getRate() == pytest.approx(1002756433394973741), "rate is not correct"
    assert dGHO.getRate() == 10**18, "rate is not correct"

    print("Trader will swap 200 dUSD for dDAI")
    input("enter to continue")


    #Swap 200 dUSD for dDAI
    struct_fund_management = (
        trader, #address sender
        False, #bool fromInternalBalance
        trader, #address payable recipient
        False #bool toInternalBalance
    )    
    struct_single_swap = (
        dUSD_pool_id, #bytes32 poolId
        0, #SwapKind.GIVEN_IN
        dUSD, #IAsset assetIn
        dDAI, #IAsset assetOut
        "200 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "140 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
    print("Trader will swap 148 dDAI for DAI")
    input("enter to continue")
    #Swap 148 dDAI for DAI
    struct_single_swap = (
        dDAI.getPoolId(), #bytes32 poolId
        0, #SwapKind.GIVEN_IN
        dDAI, #IAsset assetIn
        dai, #IAsset assetOut
        "148 Ether", #uint256 amount
        b"" #bytes userData
    )
    vault.swap(
        struct_single_swap, #SingleSwap singleSwap
        struct_fund_management, #FundManagement funds
        "50 Ether", #uint256 limit
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
    return

    #Trader gets back 222 DAI from initial investment of 200 DAI

    #Batch swap to go from DAI --> dUSD
    #Swapping 500 DAI --> dDAI --> dUSD

    vault.batchSwap(
        0, #SwapKind.GIVEN_IN
        [
            (
                dDAI.getPoolId(), #poolId
                0, #assetInIndex = DAI
                1, #assetOutIndex = dDAI
                500*10**18, #amount
                b"" #bytes userData
            ),(
                dUSD_pool_id,
                1, #assetInIndex = dDAI
                2, #assetOutIndex = dUSD
                0, #amount: 0 means use whatever we got from previous step
                b"" #bytes userData
            )
        ], #BatchSwapStep[] swaps
        [
            dai,
            dDAI,
            dUSD
        ], #assets: An array of tokens which are used in the batch swap
        (
            trader, #address sender
            False, #bool fromInternalBalance
            trader, #address payable recipient
            False #bool toInternalBalance
        ), #funds
        [
            10**25,
            0,
            10**25
        ], #limits: I dont understand how this works
        999999999999999999, #uint256 deadline
        sender=trader
    )
    bal = tokendiff(holders, tokens, bal)
