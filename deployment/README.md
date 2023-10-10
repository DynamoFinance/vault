
# How to use with hardhat fork network

## Launch hardhat with latest block

```
npx hardhat node --hostname 127.0.0.1 --port 8545 --fork https://eth-mainnet.g.alchemy.com/v2/$WEB3_ALCHEMY_API_KEY
```

Now either use this with metamask(test account keys are printed on console running hardhat), or use in console...

## Play with deployed contracts

```
ape console --network :mainnet-fork:hardhat
```

```
In [1]: from deployment.mainnet import *
INFO: Compiling 'BrokeBalancePool.vy'.
INFO: Compiling 'Dynamo4626.vy'.

In [2]: whale = accounts.test_accounts[0]

In [3]: whale.balance / 10**18
Out[3]: 10000.0

```

Each of the test accounts in hardhat is seeded with 10,000 ETH.. buy stablecoins on uniswap or elsewhere in order to interact with the vaults...


# How to use with real live network

**WARNING: below things happen on mainnet using REAL MONEY**

ape console --network :mainnet:geth

## Prerequisites

Assumes you have the vault repo cloned and dependencies/venv setup....

[Prepare an account into ape](https://docs.apeworx.io/ape/stable/userguides/accounts.html#live-network-accounts), likely a new account and send ETH to it for gas and usdc to play with.


## Query things

open ape console using following command

```
ape console --network :mainnet:geth
```

```
In [1]: from deployment.mainnet import *
INFO: Compiling 'BrokeBalancePool.vy'.
INFO: Compiling 'Dynamo4626.vy'.

In [2]: 
```

Check file `deployment/mainnet.py` for variable names, all deployed contracts are ready to use.

