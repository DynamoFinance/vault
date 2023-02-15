# How would reverts from upstream break our 4626




|  |`maxWithdraw()`|`maxDeposit()`|`totalAssets()`|`deposit()`|`withdraw`|
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


## Compound


## Euller


## Fraxlend
