# @version 0.3.7
from vyper.interfaces import ERC20
import LPAdapter as LPAdapter
#This contract would only be called using delegate call, so we do
# not use this contract's storage. Only immutable or constant.
#If there is a strong reason for having storage, then the storage slots
# need to be carefully co-ordinated with the upstream 4626

implements: LPAdapter

#Address of AAVE lending pool
lendingPool: immutable(address)
#Address of underlying asset we are investing
originalAsset: immutable(address)
#Address of AAVE wrapped token
wrappedAsset: immutable(address)
#Address of the adapter logic
adapterAddr: immutable(address)

############ Aave V3 ###########
PAUSE_MASK: constant(uint256) = 115792089237316195423570985008687907853269984665640564039456431086408522792959 # constant PAUSED_MASK =                    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFFF
ACTIVE_MASK: constant(uint256) = 115792089237316195423570985008687907853269984665640564039457511950319091711999 # constant ACTIVE_MASK =                    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFFFFFFFFFF
FROZEN_MASK: constant(uint256) = 115792089237316195423570985008687907853269984665640564039457439892725053784063 # constant FROZEN_MASK =                    0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFDFFFFFFFFFFFFFF

struct ReserveConfigurationMap:
    data: uint256

interface AAVEV3:
    def deposit(asset: address, amount: uint256, onBehalfOf: address, referralCode: uint16): nonpayable
    def withdraw(asset: address, amount: uint256, to: address) -> uint256: nonpayable
    def getConfiguration(asset: address) -> ReserveConfigurationMap: view
    

@external
def __init__(_lendingPool: address, _originalAsset: address, _wrappedAsset: address):
    lendingPool = _lendingPool
    originalAsset = _originalAsset
    wrappedAsset = _wrappedAsset
    adapterAddr = self

#Workaround because vyper does not allow doing delegatecall from inside view.
#we do a static call instead, but need to fix the correct vault location for queries.
@internal
@view
def vault_location() -> address:
    if self == adapterAddr:
        #if "self" is adapter, meaning this is not delegate call and we treat msg.sender as the vault
        return msg.sender
    #Otherwise we are inside DELEGATECALL, therefore self would be the 4626
    return self


@internal
@pure
def asettoatoken(asset: uint256) -> uint256:
    #aDAI and DAI are pegged to each other...
    return asset

@internal
@pure
def atokentoaset(asset: uint256) -> uint256:
    #aDAI and DAI are pegged to each other...
    return asset


# @internal
# @view
# def is_active() -> bool:
#     config: uint256 = AAVEV3(lendingPool).getConfiguration(originalAsset).data
#     if bitwise_and(config, bitwise_not(PAUSE_MASK)) != 0:
#         return False
#     return bitwise_and(config, bitwise_not(ACTIVE_MASK)) != 0

@internal
@pure
def is_active(config: uint256) -> bool:
    return bitwise_and(config, bitwise_not(ACTIVE_MASK)) != 0

@internal
@pure
def is_paused(config: uint256) -> bool:
    return bitwise_and(config, bitwise_not(PAUSE_MASK)) != 0

@internal
@pure
def is_frozen(config: uint256) -> bool:
    return bitwise_and(config, bitwise_not(FROZEN_MASK)) != 0

@internal
@view
def withdraw_allowed() -> bool:
    config: uint256 = AAVEV3(lendingPool).getConfiguration(originalAsset).data
    if self.is_paused(config):
        return False
    return self.is_active(config)

@internal
@view
def deposit_allowed() -> bool:
    config: uint256 = AAVEV3(lendingPool).getConfiguration(originalAsset).data
    if self.is_paused(config):
        return False
    if self.is_frozen(config):
        return False
    return self.is_active(config)

#How much asset can be withdrawn in a single transaction
@external
@view
def maxWithdraw() -> uint256:
    if not self.withdraw_allowed():
        return 0
    #How much original asset is currently available in the a-token contract
    cash: uint256 = ERC20(originalAsset).balanceOf(wrappedAsset) #asset
    return min(cash, self._assetBalance())

#How much asset can be deposited in a single transaction
@external
@view
def maxDeposit() -> uint256:
    if not self.deposit_allowed():
        return 0
    return MAX_UINT256


#How much asset this LP is responsible for.
@external
@view
def totalAssets() -> uint256:
    return self._assetBalance()

@internal
@view
def _assetBalance() -> uint256:
    wrappedBalance: uint256 = ERC20(wrappedAsset).balanceOf(self.vault_location()) #aToken
    unWrappedBalance: uint256 = self.atokentoaset(wrappedBalance) #asset
    return unWrappedBalance

#Deposit the asset into underlying LP
@external
@nonpayable
def deposit(asset_amount: uint256):
    #TODO: NEED SAFE ERC20
    #Approve lending pool
    ERC20(originalAsset).approve(lendingPool, asset_amount)
    #Call deposit function
    #"deposit_from" does not make sense. this is the beneficiary of a-tokens which must always be our vault.
    AAVEV3(lendingPool).deposit(originalAsset, asset_amount, self, 0)
    #Now aave would have taken our actual token and given us a-tokens..

#Withdraw the asset from the LP
@external
@nonpayable
def withdraw(asset_amount: uint256 , withdraw_to: address):
    AAVEV3(lendingPool).withdraw(originalAsset, asset_amount, withdraw_to)
