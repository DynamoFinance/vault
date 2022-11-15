# dynamo_vault
Dynamo Protocol Implementation for Balancer v2 Boosted Vault.

## Installation & Smoke Test

Create a python virtual environment to isolate your project and then execute the following:

Signup for free [alchemy account](https://www.alchemy.com/), create a project with ETH mainnet and replace `REMOVED` with your api key.

```
make init
export WEB3_ETHEREUM_MAINNET_ALCHEMY_API_KEY="REMOVED"
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
