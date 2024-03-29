# @version 0.3.7
"""
@title Fraxlend adapter for Dynamo4626 Multi-Vault
@license Copyright 2023 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Benjamin Scherrey, Morgan Baugh, Sajal Kayan
"""
from vyper.interfaces import ERC20
import LPAdapter as LPAdapter

implements: LPAdapter

#Address of fraxlend pair
fraxPair: immutable(address)
#Address of FRAX token
originalAsset: immutable(address)
adapterAddr: immutable(address)

interface FRAXPAIR:
    #_amount = the amount of FRAX to deposit
    def deposit(_amount: uint256, _receiver: address) -> uint256: nonpayable
    #_shares = the amount of fTokens to burn
    def redeem(_shares: uint256, _receiver: address, _owner: address) -> uint256: nonpayable
    #convert fToken to FRAX
    def toAssetAmount(_shares: uint256, _roundUp: bool) -> uint256: view
    #convert FRAX to fToken
    def toAssetShares(_amount: uint256, _roundUp: bool) -> uint256: view

@external
def __init__(_fraxPair: address, _originalAsset: address):
    """
    @notice Constructor of Fraxlend adapter.
    @param _fraxPair Address of the fraxlend pair we want to use as LP.
    @param _originalAsset Address of the original asset this adapter deals with.
    @dev
        If you want to use multiple fraxlend pairs as LP, you must deploy seperate
        instances of this adapter, one for each pair.
    """
    fraxPair = _fraxPair
    originalAsset = _originalAsset
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
@view
def asettoftoken(asset: uint256) -> uint256:
    return FRAXPAIR(fraxPair).toAssetShares(asset, False)

@internal
@view
def ftokentoaset(asset: uint256) -> uint256:
    #aDAI and DAI are pegged to each other...
    return FRAXPAIR(fraxPair).toAssetAmount(asset, False)


#How much asset this LP is responsible for.
@external
@view
def totalAssets() -> uint256:
    """
    @notice returns the balance currently held by the adapter.
    @dev
        This method returns a valid response if it has been DELEGATECALL or
        STATICCALL-ed from the Dynamo4626 contract it services. It is not
        intended to be called directly by third parties.
    """
    return self._assetBalance()

@internal
@view
def _assetBalance() -> uint256:
    wrappedBalance: uint256 = ERC20(fraxPair).balanceOf(self.vault_location()) #aToken
    unWrappedBalance: uint256 = self.ftokentoaset(wrappedBalance) #asset
    return unWrappedBalance



#How much asset can be withdrawn in a single transaction
@external
@view
def maxWithdraw() -> uint256:
    """
    @notice returns the maximum possible asset amount thats withdrawable from Fraxlend.
    @dev
        Currently only checks the balance of asset in Fraxlend. This method returns a
        valid response if it has been DELEGATECALL or STATICCALL-ed from the Dynamo4626
        contract it services. It is not intended to be called directly by third parties.
    """
    #How much original asset is currently available in the a-token contract
    cash: uint256 = ERC20(originalAsset).balanceOf(fraxPair) #asset
    return min(cash, self._assetBalance())

#Deposit the asset into underlying LP
@external
@nonpayable
def deposit(asset_amount: uint256):
    """
    @notice deposit asset into Fraxlend.
    @param asset_amount The amount of asset we want to deposit into Fraxlend
    @dev
        This method is only valid if it has been DELEGATECALL-ed
        from the Dynamo4626 contract it services. It is not intended to be
        called directly by third parties.
    """
    #Approve fraxPair
    ERC20(originalAsset).approve(fraxPair, asset_amount)
    #Call deposit function
    FRAXPAIR(fraxPair).deposit(asset_amount, self)

#Withdraw the asset from the LP
@external
@nonpayable
def withdraw(asset_amount: uint256 , withdraw_to: address):
    """
    @notice withdraw asset from Fraxlend.
    @param asset_amount The amount of asset we want to withdraw from Fraxlend
    @param withdraw_to The ultimate reciepent of the withdrawn assets
    @dev
        This method is only valid if it has been DELEGATECALL-ed
        from the Dynamo4626 contract it services. It is not intended to be
        called directly by third parties.
    """
    FRAXPAIR(fraxPair).redeem(self.asettoftoken(asset_amount), withdraw_to, self)

#How much asset can be deposited in a single transaction
@external
@view
def maxDeposit() -> uint256:
    """
    @notice returns the maximum possible asset amount thats depositable into Fraxlend
    @dev
        Currently returns hardcoded max uint256.
    """
    return MAX_UINT256
