# How would reverts from upstream break our 4626




|  |`maxWithdraw()`|`maxDeposit()`|`totalAssets()`|`deposit()`|`withdraw()`|
|--|---------------|--------------|---------------|-----------|----------|
|AAVE|Works fine|Works fine|Works fine|reverts error="29"|reverts error="29"|
|compound|TODO|TODO|TODO|TODO|TODO|
|euller|TODO|TODO|TODO|TODO|TODO|
|fraxlend|TODO|TODO|TODO|TODO|TODO|



## AAVE

I could find 3 ways in which AAVE can be paused. 
1. Pausing individual asset `PoolConfigurator.setReservePause(0xAsset, true)`
2. Pausing all of AAVE `PoolConfigurator.setPoolPause(true)` (which basically pauses each asset inside a forloop)
3. All AAVE contracts are upgradable, so there can be unknown way the contract is paused/exploited/rug-pulled.


PS: Adapter can probe this. Look at `is_active()` method of aaveAdapter.vy . Current code uses this to return 0 as maxDeposit() and maxWithdraw(). There might be very tiny amount of gas savings if we dont do this check and let it revert. The savings is not a lot as deposit/withdraw would eventually read the same storage slot.

## Compound


## Euller


## Fraxlend
