# @version 0.3.7

from vyper.interfaces import ERC20
from interfaces.adapter import LPAdapter

interface mintableERC20:
    def mint(_receiver: address, _amount: uint256) -> uint256: nonpayable
    

implements: LPAdapter

aoriginalAsset: immutable(address)
awrappedAsset: immutable(address)

@external
def __init__(_originalAsset: address, _wrappedAsset: address):
    aoriginalAsset = _originalAsset
    awrappedAsset = _wrappedAsset


@external
@pure
def originalAsset() -> address: return aoriginalAsset


@external
@pure
def wrappedAsset() -> address: return awrappedAsset


#How much asset can be withdrawn in a single call
@external
@view
def maxWithdrawable() -> uint256: 
    return empty(uint256)


#How much asset can be deposited in a single call
@external
@view
def maxDepositable() -> uint256: 
    return empty(uint256)


#How much asset this LP is responsible for.
@external
@view
def assetBalance() -> uint256: 
    return empty(uint256)


#Deposit the asset into underlying LP. The tokens must be present inside the 4626 vault.
@external
@nonpayable
def deposit(asset_amount: uint256):
    #mintableERC20(awrappedAsset).mint(self, asset_amount) 
    #ERC20(aoriginalAsset).transferFrom(msg.sender, self, asset_amount)
    pass


#Withdraw the asset from the LP to an arbitary address. 
@external
@nonpayable
def withdraw(asset_amount: uint256 , withdraw_to: address):
    pass

