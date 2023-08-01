# @version 0.3.7
"""
@title Dynamo4626 Lending Pool Adapter
@license Copyright 2023 Biggest Lab Co Ltd, Benjamin Scherrey, Sajal Kayan, and Eike Caldeweyher
@author BiggestLab (https://biggestlab.io) Sajal Kayan, Benjamin Scherrey
"""

#Declaring interface in this format allows it to be "compiled", so we can use its ABI from python side
#One happy side-effect is now "implements" bit is enforced in other contracts.

# How much asset can be withdrawn in a single call
@external
@view
def maxWithdraw() -> uint256:
    """
    @notice returns the maximum possible asset amount thats withdrawable from this adapter
    @dev
        This method returns a valid response if it has been DELEGATECALL or 
        STATICCALL-ed from the Dynamo4626 contract it services. It is not intended
        to be called directly by third parties.
    """
    return 0

# How much asset can be deposited in a single call
@external
@view
def maxDeposit() -> uint256:
    """
    @notice returns the maximum possible asset amount thats depositable to this adapter
    @dev
        This method returns a valid response if it has been DELEGATECALL or 
        STATICCALL-ed from the Dynamo4626 contract it services. It is not intended
        to be called directly by third parties.
    """
    return 0

# How much asset this LP is responsible for.
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
    return 0


# Deposit the asset into underlying LP. The tokens must be present inside the 4626 vault.
@external
def deposit(asset_amount: uint256):
    """
    @notice deposit asset into underlying LP.
    @param asset_amount The amount of asset we want to deposit into underlying LP
    @dev
        This method is only valid if it has been DELEGATECALL-ed
        from the Dynamo4626 contract it services. It is not intended to be
        called directly by third parties.
    """
    pass


# Withdraw the asset from the LP to an arbitary address. 
@external
def withdraw(asset_amount: uint256 , withdraw_to: address):
    """
    @notice withdraw asset from underlying LP.
    @param asset_amount The amount of asset we want to withdraw from underlying LP
    @param withdraw_to The ultimate reciepent of the withdrawn assets
    @dev
        This method is only valid if it has been DELEGATECALL-ed
        from the Dynamo4626 contract it services. It is not intended to be
        called directly by third parties.
    """
    pass
