# dynamo_vault
Dynamo Protocol Implementation for Balancer v2 Boosted Vault.

## Installation & Smoke Test

Create a python virtual environment to isolate your project and then execute the following:

Run a supported version of node.

```
nvm install 16.16.0
```

Signup for free [alchemy account](https://www.alchemy.com/), create a project with ETH mainnet and replace `REMOVED` with your api key.

```
make init
export WEB3_ETHEREUM_MAINNET_ALCHEMY_API_KEY="REMOVED"

### Setup your node snapshot RPC.



Make sure nothing is listening on port 8445.

```
sudo netstat -lntp | grep 8545
```

Optionally pre-launch the RPC server (which will block this shell):

```
npx hardhat   node   --fork https://eth-mainnet.alchemyapi.io/v2/$WEB3_ETHEREUM_MAINNET_ALCHEMY_API_KEY --fork-block-number 15936703
```
 
    OR

Edit the file source_me and enter your Alchemy API Key where it belongs then do:
```
git update-index --assume-unchanged source_me

source source_me
```

If you don't pre-launch the RPC server yourself ape will spin one up but it has a race condition and sometimes fails.


### Now in another shell:

ape test --network :mainnet-fork:hardhat
```

^^ This will fail 50% of the time, I'm working on fixing it.

## Test & Execution Environment 

We're using [ApeWorX](https://github.com/ApeWorX) with [PyTest](https://github.com/pytest-dev/pytest) as our development environment.

[ApeWorX Discord](https://discord.gg/apeworx)

[ApeWorX Website](https://www.apeworx.io/)

[ApeWorX Documentation](https://docs.apeworx.io/ape/stable/)

[PyTest Website](https://pytest.org)

## Project Tracking (Internal Only)
[Dynamo DeFi Github Project Board](https://github.com/orgs/BiggestLab/projects/6)
