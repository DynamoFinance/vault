import ape
from web3 import Web3
import requests, json, os
import eth_abi
from ape import accounts
from ape import project


DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
D4626_NAME = "Dynamo"
D4626_SYMBOL = "dy"
D4626_DECIMALS = 18
AAVE_LENDING_POOL = "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2"
ADAI = "0x018008bfb33d285247A21d44E50697654f754e63"
CDAI = "0x5d3a536E4D6DbD6114cc1Ead35777bAB948E3643"
MAX_POOLS = 5 # Must match the value from Dynamo4626.vy
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
FRAX = "0x853d955aCEf822Db058eb8505911ED77F175b99e"
BTC_FRAX_PAIR = "0x32467a5fc2d72D21E8DCe990906547A2b012f382"
AFRAX = "0xd4e245848d6E1220DBE62e155d89fa327E43CB06"
FORK_BLOCK = 17927000

def main():
    #reset hardhat state
    reset_request = {"jsonrpc": "2.0", "method": "hardhat_reset", "id": 1,
        "params": [{
            "forking": {
                "jsonRpcUrl": "https://eth-mainnet.alchemyapi.io/v2/"+os.getenv('WEB3_ALCHEMY_API_KEY'),
                #hardcoding here, not good.
                #Using something much newer than rest of the suite
                "blockNumber": 17927000
            }
        }]}
    requests.post("http://localhost:8545/", json.dumps(reset_request))
    #find account to use
    deployer = accounts.test_accounts[0]
    whale = accounts.test_accounts[1]

    #"airdrop" some DAI to whale for testing...

    abi_encoded = eth_abi.encode(['address', 'uint256'], [deployer.address, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()
    dai = project.DAI.at(DAI)
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [DAI, storage_slot, "0x" + eth_abi.encode(["uint256"], [1]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))
    # print("wards", dai.wards(deployer))
    #make the trader rich, airdrop $1 billion
    dai.mint(whale, '10000000000 Ether', sender=deployer)

    print("deployer", deployer)
    #deploy funds allocator
    funds_alloc = deployer.deploy(project.FundsAllocator)
    print("funds allocator deployed", funds_alloc)
    #deploy 4626 vault for DAI
    dynamo4626DAI = deployer.deploy(
        project.Dynamo4626,
        D4626_NAME + "DAI",
        D4626_SYMBOL + "DAI",
        D4626_DECIMALS,
        DAI,
        [],
        deployer,
        funds_alloc
    )    
    print("dynamo4626DAI deployed", dynamo4626DAI)
    #add aave_adapter
    aave_adapter = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, DAI, ADAI)
    print("aave_adapter deployed", aave_adapter)
    #add compound adapter
    compound_adapter = deployer.deploy(project.compoundAdapter, DAI, CDAI)
    print("compound_adapter deployed", compound_adapter)
    #Ensure all adapters are in the vault
    print("adding aave_adapter")
    dynamo4626DAI.add_pool(aave_adapter, sender=deployer)
    print("adding compound_adapter")
    dynamo4626DAI.add_pool(compound_adapter, sender=deployer)
    #TODO: create and set strategy 1:1 for now
    pos = 0
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS
    changed = False
    for pool in dynamo4626DAI.lending_pools():
        ratio = dynamo4626DAI.strategy(pool).ratio
        if ratio != 1:
            ratio = 1
            changed = True
        strategy[pos] = (pool, ratio)
        pos += 1
    print(strategy)
    print(changed)
    if changed:
        dynamo4626DAI.set_strategy(deployer, strategy, 0, sender=deployer)
    #TODO: do governance stuff, and make it the owner of the vault
    governance = deployer.deploy(project.Governance, deployer, 0)
    print("governance deployed", governance)
    guards = governance.guards()
    if deployer.address not in guards:
        governance.addGuard(deployer, sender=deployer)
    if dynamo4626DAI.governance != governance.address:
        dynamo4626DAI.replaceGovernanceContract(governance, sender=deployer)
    #FRAX
    #Airdrop to whale
    frax = project.ERC20.at(FRAX)
    abi_encoded = eth_abi.encode(['address', 'uint256'], [whale.address, 0])
    storage_slot = Web3.solidity_keccak(["bytes"], ["0x" + abi_encoded.hex()]).hex()
    set_storage_request = {"jsonrpc": "2.0", "method": "hardhat_setStorageAt", "id": 1,
        "params": [FRAX, storage_slot, "0x" + eth_abi.encode(["uint256"], [10**28]).hex()]}
    print(requests.post("http://localhost:8545/", json.dumps(set_storage_request)))

    aave_adapter = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, FRAX, AFRAX)
    print("aave_adapter deployed", aave_adapter)
    #add compound adapter
    fraxlend_adapter = deployer.deploy(project.fraxlendAdapter, BTC_FRAX_PAIR, FRAX)
    print("fraxlend_adapter deployed", fraxlend_adapter)
    dynamo4626FRAX = deployer.deploy(
        project.Dynamo4626,
        D4626_NAME + "FRAX",
        D4626_SYMBOL + "FRAX",
        D4626_DECIMALS,
        FRAX,
        [],
        deployer,
        funds_alloc
    )    
    dynamo4626FRAX.add_pool(aave_adapter, sender=deployer)
    dynamo4626FRAX.add_pool(fraxlend_adapter, sender=deployer)
    pos = 0
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS
    for pool in dynamo4626FRAX.lending_pools():
        strategy[pos] = (pool, 1)
        pos += 1
    dynamo4626FRAX.set_strategy(deployer, strategy, 0, sender=deployer)
    dynamo4626FRAX.replaceGovernanceContract(governance, sender=deployer)


    print("=================== Deployment done ===================")
    print("Blockchain forked at: ", FORK_BLOCK)
    print("dynamo4626 DAI vault: ", dynamo4626DAI)
    print("dynamo4626 FRAX vault: ", dynamo4626FRAX)
    print("governance: ", governance)
    print("owner/deployer address: ", deployer.address)
    print("owner/deployer private key: ", deployer.private_key)
    print("whale address: ", whale.address)
    print("whale private key: ", whale.private_key)
    print("Deployer has %d ETH, and %d DAI, %d FRAX" %( deployer.balance / 10**18 , dai.balanceOf(deployer) /10**18, frax.balanceOf(deployer) /10**18 ))
    print("Whale has %d ETH, and %d DAI, %d FRAX" %( whale.balance / 10**18 , dai.balanceOf(whale) /10**18, frax.balanceOf(whale) /10**18 ))


    print("""
Metamask settings:-
Network Name        Hardhat mainnet fork
RPC Endpoint        http://127.0.0.1:8545
Chain ID            1
Currency Symbol     ETH
          
WARNING: Test blockchain state has been reset, you need to reset metamask or subsiquent transactions may be stuck forever.
https://support.metamask.io/hc/en-us/articles/360015488891-How-to-reset-an-account
          """)
