# How would reverts from upstream break our 4626




|  |`maxWithdraw()`|`maxDeposit()`|`totalAssets()`|`deposit()`|`withdraw()`|
|--|---------------|--------------|---------------|-----------|----------|
|AAVE|Works fine|Works fine|Works fine|reverts error="29"|reverts error="29"|
|compound|Works fine|Works fine|Works fine|TODO|TODO|
|euller|TODO|TODO|TODO|TODO|TODO|
|fraxlend|TODO|TODO|TODO|TODO|TODO|



## AAVE

I could find 3 ways in which AAVE can be paused. 
1. Pausing individual asset `PoolConfigurator.setReservePause(0xAsset, true)`
2. Pausing all of AAVE `PoolConfigurator.setPoolPause(true)` (which basically pauses each asset inside a forloop)
3. All AAVE contracts are upgradable, so there can be unknown way the contract is paused/exploited/rug-pulled.

PS: Adapter can probe this. Look at `is_active()` method of aaveAdapter.vy . Current code uses this to return 0 as `maxDeposit()` and `maxWithdraw()`. There might be very tiny amount of gas savings if we dont do this check and let it revert. The savings is not a lot as deposit/withdraw would eventually read the same storage slot.

The idea is that `maxDeposit()` and `maxWithdraw()` return some value, and as long as the strategy adheres to the returned values the subsiquent deposit() or withdraw() should not revert.

current logic

- `maxDeposit()` = max_supply minus assets deposited . TODO: current implementation just returns max_supply. [Relavent upstream check](https://github.com/aave/aave-v3-core/blob/94e571f3a7465201881a59555314cd550ccfda57/contracts/protocol/libraries/logic/ValidationLogic.sol#L57)
- `maxWithdraw()` = min(adapter balance of the asset, the asset currently available in aave) . TODO: Validate if this is true . [Relavent upstream check](https://github.com/aave/aave-v3-core/blob/94e571f3a7465201881a59555314cd550ccfda57/contracts/protocol/libraries/logic/ValidationLogic.sol#L87)

## Compound

The code for fetching the exchange rate looks benign, not revert-ey.

PS: `maxWithdraw()` and `maxDeposit()` currently does not take reality into account, so theres a chance of revert during actual withdraw/deposit


So far it appears that only place compound will revert during deposit is in CToken.sol line 400

```solidity
        uint allowed = comptroller.mintAllowed(address(this), minter, mintAmount);
        if (allowed != 0) {
            revert MintComptrollerRejection(allowed);
        }
```

I think this is compounds blacklist impl and also a way to pause...

Withdraw also has a similar check at CToken.sol line 508

```solidity
        uint allowed = comptroller.redeemAllowed(address(this), redeemer, redeemTokens);
        if (allowed != 0) {
            revert RedeemComptrollerRejection(allowed);
        }

        //few lines later

        comptroller.redeemVerify(address(this), redeemer, redeemAmount, redeemTokens);
```

## Euller


## Fraxlend
