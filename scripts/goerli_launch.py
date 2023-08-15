import ape
from web3 import Web3
import requests, json
import eth_abi
from ape import accounts
from ape import project


USDT = "0x2e8d98fd126a32362f2bd8aa427e59a1ec63f780"
D4626_NAME = "DynamoUSDT"
D4626_SYMBOL = "dyUSDT"
D4626_DECIMALS = 18
AAVE_LENDING_POOL = "0x7b5C526B7F8dfdff278b4a3e045083FBA4028790"
AUSDT = "0xf3368D1383cE079006E5D1d56878b92bbf08F1c2"
CUSDT = "0xf650C3d88D12dB855b8bf7D11Be6C55A4e07dCC9"
MAX_POOLS = 5 # Must match the value from Dynamo4626.vy
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

######### Fill these as deployment is done, or use None #####################
FUNDS_ALLOC_DEPLOYMENT  = "0x688371619059989Fad7f296497708828ecC80Cf5"
DYNAMO_DEPLOYMENT       = "0x288E9a999a9718D12b738803b96A73e3efd3A0f7"
AAVE_ADAPTER            = "0x50B80720Ef81aA722F01F9587144e26F6f513eDD"
COMPOUND_ADAPTER        = "0xF3A047Fb336c009E2CF85d461CC22010Cdd96c5F"
############################################################################

def main():
    #find account to use
    #Import one using : ape accounts import dynamo_dev
    deployer = accounts.load("dynamo_dev")
    print("deployer", deployer)
    #deploy funds allocator
    if FUNDS_ALLOC_DEPLOYMENT is not None:
        funds_alloc = project.FundsAllocator.at(FUNDS_ALLOC_DEPLOYMENT)
        print("existing funds allocator found", funds_alloc)
    else:
        funds_alloc = deployer.deploy(project.FundsAllocator)
        print("funds allocator deployed", funds_alloc)
    #deploy 4626 vault for USDT
    if DYNAMO_DEPLOYMENT is not None:
        dynamo4626 = project.Dynamo4626.at(DYNAMO_DEPLOYMENT)
        print("existing dynamo4626 found", dynamo4626)
    else:
        dynamo4626 = deployer.deploy(
            project.Dynamo4626,
            D4626_NAME,
            D4626_SYMBOL,
            D4626_DECIMALS,
            USDT,
            [],
            deployer,
            funds_alloc
        )    
        print("dynamo4626 deployed", dynamo4626)
    #add aave_adapter
    if AAVE_ADAPTER is not None:
        aave_adapter = project.aaveAdapter.at(AAVE_ADAPTER)
        print("existing aave_adapter found", aave_adapter)
    else:
        aave_adapter = deployer.deploy(project.aaveAdapter, AAVE_LENDING_POOL, USDT, AUSDT)
        print("aave_adapter deployed", aave_adapter)
    #add compound adapter
    if COMPOUND_ADAPTER is not None:
        compound_adapter = project.compoundAdapter.at(COMPOUND_ADAPTER)
        print("existing compound_adapter found", compound_adapter)
    else:
        compound_adapter = deployer.deploy(project.compoundAdapter, USDT, CUSDT)
        print("compound_adapter deployed", compound_adapter)
    #Ensure all adapters are in the vault
    adapters = dynamo4626.lending_pools()
    if aave_adapter.address not in adapters:
        print("adding aave_adapter")
        dynamo4626.add_pool(aave_adapter, sender=deployer)
    if compound_adapter not in adapters:
        print("adding compound_adapter")
        dynamo4626.add_pool(compound_adapter, sender=deployer)
    #TODO: create and set strategy 1:1 for now
    pos = 0
    strategy = [(ZERO_ADDRESS,0)] * MAX_POOLS
    changed = False
    for pool in dynamo4626.lending_pools():
        ratio = dynamo4626.strategy(pool).ratio
        if ratio != 1:
            ratio = 1
            changed = True
        strategy[pos] = (pool, ratio)
        pos += 1
    print(strategy)
    print(changed)
    if changed:
        dynamo4626.set_strategy(deployer, strategy, 0, sender=deployer)
    #TODO: do governance stuff, and make it the owner of the vault
