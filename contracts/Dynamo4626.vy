# @version 0.3.7
"""
@title Dynamo4626 Multi-Vault
@license MIT
@author BiggestLab (https://biggestlab.io) Benjamin Scherrey, Morgan Baugh, Sajal Kayan
"""

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626
import LPAdapter as LPAdapter
implements: ERC20
implements: ERC4626

interface FundsAllocator:
    def getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_balances: BalancePool[MAX_POOLS], _min_outgoing_tx: uint256) -> (uint256, int256, uint256, BalancePool[MAX_POOLS], address[MAX_POOLS]): pure
    def getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_states: BalancePool[MAX_POOLS]) -> (BalanceTX[MAX_POOLS], address[MAX_POOLS]): pure

# Number of potential lenging platform adapters.
MAX_POOLS : constant(uint256) = 5
MAX_BALTX_DEPOSIT : constant(uint8) = 5 # MUST equal MAX_POOLS for now. Ignored for now.

# Contract owner hold 10% of the yield.
YIELD_FEE_PERCENTAGE : constant(uint256) = 10

# 1% of the yield belongs to the Strategy proposer.
PROPOSER_FEE_PERCENTAGE: constant(uint256) = 1

# For use in support of _claim_fees
enum FeeType:
    BOTH
    YIELD
    PROPOSER

# ERC-20 attributes for this Vault's share token.
name: public(immutable(String[64]))
symbol: public(immutable(String[32]))
decimals: public(immutable(uint8))
asset: public(immutable(address))

# Controlling & Governance DAOs/Wallets
owner: public(address)
governance: public(address)
funds_allocator: public(address)
dlending_pools : public(DynArray[address, MAX_POOLS])


# Strategy Management
current_proposer: public(address)
min_proposer_payout: public(uint256)

struct AdapterValue:
    ratio: uint256
    last_asset_value: uint256

strategy: public(HashMap[address, AdapterValue])


# Summary Financial History of the Vault
total_assets_deposited: public(uint256)
total_assets_withdrawn: public(uint256)
total_yield_fees_claimed: public(uint256)
total_strategy_fees_claimed: public(uint256)


# ERC20 Representation of Vault Shares
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


event PoolAdded:
    sender: indexed(address)
    adapter_addr: indexed(address)

event PoolRemoved:   
    sender: indexed(address)
    afapter_addr: indexed(address) 

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256    

event Deposit:
    sender: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256 

event Withdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256 

struct AdapterStrategy:
    adapter: address
    ratio: uint256    

event StrategyActivation:
    strategy: AdapterStrategy[MAX_POOLS]
    proposer: address

event PoolLoss:
    adapter: indexed(address)
    last_value: uint256
    current_value: uint256

event GovernanceChanged:
    new_governor: indexed(address)
    old_governor: indexed(address)

event DynamoVaultDeployed:
    name: indexed(String[64])
    symbol: indexed(String[32])
    decimals: uint8
    asset: indexed(address)

event FundsAllocatorChanged:
    new_allocator: indexed(address)
    old_allocator: indexed(address)   

event OwnerChanged:
    new_owner: indexed(address)
    old_owner: indexed(address)    

    

@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _pools: DynArray[address, MAX_POOLS], _governance: address, _funds_allocator: address):
    """
    @notice Constructor for 4626 contract.
    @param _name of shares token
    @param _symbol identifier of shares token
    @param _decimals increment for division of shares token 
    @param _erc20asset : contract address for asset ERC20 token
    @param _pools : list of addresses for initial Pools (could be none) 
    @param _governance contract address
    @param _funds_allocator contract address
    """
    assert MAX_BALTX_DEPOSIT <= MAX_POOLS, "Invalid contract pre-conditions."
    assert _governance != empty(address), "Governance cannot be null address."
    assert _funds_allocator != empty(address), "Fund allocator cannot be null address."

    name = _name
    symbol = _symbol
    decimals = _decimals

    # Is this likely to be an actual ERC20 contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)
    result_ok, response = raw_call(_erc20asset, _abi_encode(self, method_id=method_id("balanceOf(address)")), max_outsize=32, value=convert(self, uint256), is_static_call=True, revert_on_failure=False)
    assert result_ok == True, "Doesn't appear to be an ERC20 contract."
    asset = _erc20asset

    self.owner = msg.sender
    self.governance = _governance
    self.funds_allocator = _funds_allocator
    self.totalSupply = 0

    log DynamoVaultDeployed(_name, _symbol, _decimals, _erc20asset)
    log OwnerChanged(msg.sender, empty(address))
    log GovernanceChanged(_governance, empty(address))
    log FundsAllocatorChanged(_funds_allocator, empty(address))

    for pool in _pools:
        self._add_pool(pool)        


@external
def replaceOwner(_new_owner: address) -> bool:
    """
    @notice replace the current 4626 owner with a new one.
    @param _new_owner address of the new contract owner
    @return True, if contract owner was replaced, False otherwise
    """
    assert msg.sender == self.owner, "Only existing owner can replace the owner."
    assert _new_owner != empty(address), "Owner cannot be null address."

    log OwnerChanged(_new_owner, self.owner)

    self.owner = _new_owner
    
    return True


@external
def replaceGovernanceContract(_new_governance: address) -> bool:
    """
    @notice replace the current Governance contract with a new one.
    @param _new_governance address of the new governance contract 
    @return True, if governance contract was replaced, False otherwise
    """
    assert msg.sender == self.governance, "Only existing Governance contract may replace itself."
    assert _new_governance != empty(address), "Governance cannot be null address."

    log GovernanceChanged(_new_governance, self.governance)

    self.governance = _new_governance    

    return True


@external
def replaceFundsAllocator(_new_funds_allocator: address) -> bool:
    """
    @notice replace the current funds allocator contract with a new one.
    @param _new_funds_allocator address of the new contract
    @return True, if funds allocator contract was replaced, False otherwise
    """
    assert msg.sender == self.owner, "Only owner can change the funds allocation contract!"
    assert _new_funds_allocator != empty(address), "FundsAllocator cannot be null address."

    log FundsAllocatorChanged(_new_funds_allocator, self.funds_allocator)

    self.funds_allocator = _new_funds_allocator

    return True


# Can't simply have a public lending_pools variable due to this Vyper issue:
# https://github.com/vyperlang/vyper/issues/2897
@view
@external
def lending_pools() -> DynArray[address, MAX_POOLS]: 
    """
    @notice convenience function returning list of pools
    @return list of lending pool addresses
    """
    return self.dlending_pools


@internal
def _set_strategy(_proposer: address, _strategies : AdapterStrategy[MAX_POOLS], _min_proposer_payout : uint256) -> bool:
    assert msg.sender == self.governance, "Only Governance DAO may set a new strategy."
    assert _proposer != empty(address), "Proposer can't be null address."

    # Are we replacing the old proposer?
    if self.current_proposer != _proposer:

        current_assets : uint256 = self._totalAssets()

        # Is there enough payout to actually do a transaction?
        if self._claimable_fees_available(FeeType.PROPOSER, current_assets) > self.min_proposer_payout:
                
            # Pay prior proposer his earned fees.
            self._claim_fees(FeeType.PROPOSER, 0, current_assets)

        self.current_proposer = _proposer
        self.min_proposer_payout = _min_proposer_payout

    # Clear out all existing ratio allocations.
    for pool in self.dlending_pools:
        self.strategy[pool] = empty(AdapterValue)

    # Now set strategies according to the new plan.
    for strategy in _strategies:
        plan : AdapterValue = empty(AdapterValue)
        plan.ratio = strategy.ratio
        self.strategy[strategy.adapter] = plan

    log StrategyActivation(_strategies, _proposer)

    return True


@external
def set_strategy(_proposer: address, _strategies : AdapterStrategy[MAX_POOLS], _min_proposer_payout : uint256) -> bool:
    """
    @notice establishes new strategy of adapter ratios and minumum value of automatic txs into adapters
    @param _proposer address of wallet who proposed strategy and will be entitled to fees during its activation
    @param _strategies list of ratios for each adapter for funds allocation
    @param _min_proposer_payout for automated txs into adapters or automatic payout of fees to proposer upon activation of new strategy
    @return True if strategy was activated, False overwise
    """
    return self._set_strategy(_proposer, _strategies, _min_proposer_payout)


@internal 
def _add_pool(_pool: address) -> bool:    
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new Lending Pools."

    # Do we already support this pool?
    assert (_pool in self.dlending_pools) == False, "pool already supported."

    # Is this likely to be an actual LPAdapter contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)

    result_ok, response = raw_call(_pool, method_id("maxDeposit()"), max_outsize=32, is_static_call=True, revert_on_failure=False)
    assert (response != empty(Bytes[32])), "Doesn't appear to be an LPAdapter."

    self.dlending_pools.append(_pool)

    log PoolAdded(msg.sender, _pool)

    return True


@external 
def add_pool(_pool: address) -> bool: 
    """
    @notice adds a new Adapter pool to the 4626 vault.
    @param _pool Address for new pool to evaluate
    @return True if pool was added, False otherwise
    @dev If the current strategy doesn't already have an allocation ratio for this pool it will receive no funds until a new strategy is activated and a balanceAdapters or deposit/withdraw tx is made.

    """
    return self._add_pool(_pool)


@internal
def _remove_pool(_pool: address, _rebalance: bool = True) -> bool:
    # Is this from the owner?    
    assert msg.sender == self.owner, "Only owner can remove Lending Pools."

    if _pool not in self.dlending_pools: return False

    # Clear out any strategy ratio this adapter may have.
    self.strategy[_pool].ratio = 0

    if _rebalance == True: 
        self._balanceAdapters(0, convert(MAX_POOLS, uint8))
    else:
        pool_assets : uint256 = self._poolAssets(_pool)

        if pool_assets > 0:
            self._adapter_withdraw(_pool, pool_assets, self)

    # Walk over the list of adapters and get rid of this one.
    new_pools : DynArray[address, MAX_POOLS] = empty(DynArray[address, MAX_POOLS])
    for pool in self.dlending_pools:
        if pool != _pool:
            new_pools.append(pool)

    self.dlending_pools = new_pools            

    log PoolRemoved(msg.sender, _pool)

    return True


@external
def remove_pool(_pool: address, _rebalance: bool = True) -> bool:
    """
    @notice removes Adapter pool from the 4626 vault.
    @param _pool address to be removed 
    @param _rebalance if True will empty pool before removal.
    @return True if pool was removed, False otherwise
    """
    return self._remove_pool(_pool, _rebalance)


@internal
@view
def _poolAssets(_pool: address) -> uint256:
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False

    assert _pool != empty(address), "EMPTY POOL!!"    

    return LPAdapter(_pool).totalAssets()


@internal
@view
def _totalAssets() -> uint256:
    assetqty : uint256 = ERC20(asset).balanceOf(self)
    for pool in self.dlending_pools:
        assetqty += self._poolAssets(pool)

    return assetqty


@external
@view
def totalAssets() -> uint256: 
    """
    @notice returns current total asset value for 4626 vault & all its attached Adapter pools.
    @return sum of assets
    """
    return self._totalAssets()


@internal
@view 
def _totalReturns(_current_assets : uint256) -> int256:
    # Avoid having to call _totalAssets if we already know the value.
    current_holdings : uint256 = _current_assets
    if current_holdings == 0:
        current_holdings = self._totalAssets()

    total_returns: int256 = convert(self.total_assets_withdrawn + current_holdings, int256) - convert(self.total_assets_deposited, int256)
    return total_returns    


@external
@view 
def totalReturns() -> int256:
    """
    @notice computes current profits (denominated in assets) available under control of this 4626 vault.
    @return total assets held by pool above what is currently deposited.
    @dev This includes the fees owed to 4626 contract owner and current strategy proposer.
    """
    assets : uint256 = self._totalAssets()
    return self._totalReturns(assets)    


@internal
@view 
def _claimable_fees_available(_yield : FeeType, _current_assets : uint256 = 0) -> uint256:
    total_assets : uint256 = _current_assets

    # Only call _totalAssets() if it wasn't passed in.
    if total_assets == 0:
        total_assets = self._totalAssets()
    total_returns : int256 = self._totalReturns(total_assets)
    if total_returns <= 0: return 0

    # Assume FeeType.YIELD
    fee_percentage: uint256 = YIELD_FEE_PERCENTAGE
    if _yield == FeeType.PROPOSER:
        fee_percentage = PROPOSER_FEE_PERCENTAGE
    elif _yield == FeeType.BOTH:
        fee_percentage += PROPOSER_FEE_PERCENTAGE
    elif _yield != FeeType.YIELD:
        assert False, "Invalid FeeType!" 

    total_fees_ever : uint256 = (convert(total_returns,uint256) * fee_percentage) / 100

    assert self.total_strategy_fees_claimed + self.total_yield_fees_claimed <= total_fees_ever, "Total fee calc error!"

    total_fees_available : uint256 = 0
    if _yield == FeeType.YIELD or _yield == FeeType.BOTH:
        total_fees_available = total_fees_ever - self.total_yield_fees_claimed
    elif _yield == FeeType.PROPOSER:
        total_fees_available = total_fees_ever - self.total_strategy_fees_claimed           

    if _yield == FeeType.BOTH:
        total_fees_available -= self.total_strategy_fees_claimed

    # We want to do the above sanity checks even if total_assets is zero just in case.
    #if total_assets == 0: return 0
    if total_assets < total_fees_available:
        # Is it a rounding error?
        if total_fees_available - 1 == total_assets:
            total_fees_available -= 1
        else:
            xxmsg : String[277] = concat("Fees ", uint2str(total_fees_available), " > current assets : ", uint2str(total_assets), " against ", uint2str(convert(total_returns,uint256)), " returns!")
            assert total_assets >= total_fees_available, xxmsg       

    return total_fees_available


@external
@view    
def claimable_yield_fees_available(_current_assets : uint256 = 0) -> uint256:
    """
    @notice determines total yields aailable for 4626 vault owner.
    @param _current_assets optional parameter if current total assets is already known.
    @return total assets contract owner could withdraw now in fees.
    """
    return self._claimable_fees_available(FeeType.YIELD, _current_assets)    


@external
@view    
def claimable_strategy_fees_available(_current_assets : uint256 = 0) -> uint256:
    """
    @notice determines total yields aailable for current strategy proposer.
    @param _current_assets optional parameter if current total assets is already known.
    @return total assets strategy proposer is owed presently.
    """
    return self._claimable_fees_available(FeeType.PROPOSER, _current_assets)  


@external
@view    
def claimable_all_fees_available(_current_assets : uint256 = 0) -> uint256:
    """
    @notice determines total fees owed for both 4626 vault owner & proposer of current strategy.
    @param _current_assets optional parameter if current total assets is already known.
    @return Claimable fees available for yield and proposer
    """
    return self._claimable_fees_available(FeeType.BOTH, _current_assets)      


@internal
def _claim_fees(_yield : FeeType, _asset_amount: uint256, _current_assets : uint256 = 0) -> uint256:
    # If current proposer is zero address we pay no strategy fees.    
    if _yield != FeeType.YIELD and self.current_proposer == empty(address): return 0

    claim_amount : uint256 = _asset_amount

    total_fees_remaining : uint256 = self._claimable_fees_available(_yield, _current_assets)
    if _asset_amount == 0:
        claim_amount = total_fees_remaining

    # Do we have _asset_amount of fees available to claim?
    assert claim_amount <= total_fees_remaining, "Requesst exceeds available fees."

    # Good claim. Do we have the balance locally?
    if ERC20(asset).balanceOf(self) < claim_amount:

        # Need to liquidate some shares to fulfill 
        self._balanceAdapters(claim_amount)

    # Account for the claim and move the funds.
    if _yield == FeeType.YIELD:
        assert msg.sender == self.owner, "Only owner may claim yield fees."
        self.total_yield_fees_claimed += claim_amount    
    elif _yield == FeeType.PROPOSER:
        assert msg.sender == self.current_proposer, "Only curent proposer may claim strategy fees."
        self.total_strategy_fees_claimed += claim_amount        
    elif _yield == FeeType.BOTH:
        assert msg.sender == self.owner, "Only owner may claim yield fees."
        assert msg.sender == self.current_proposer, "Only curent proposer may claim strategy fees."        
        prop_fee : uint256 = self._claimable_fees_available(FeeType.PROPOSER, _current_assets)
        self.total_yield_fees_claimed += claim_amount - prop_fee
        self.total_strategy_fees_claimed += prop_fee
    else:
        assert False, "Invalid FeeType!"

    ERC20(asset).transfer(msg.sender, claim_amount)

    return claim_amount


@external
def claim_yield_fees(_asset_request: uint256 = 0) -> uint256:
    """
    @notice used by 4626 vault owner to withdraw fees.
    @param _asset_request total assets desired for withdrawl. 
    @return total assets transferred.    
    @dev If _asset_request is 0 then will withdrawl all eligible assets.
    """
    return self._claim_fees(FeeType.YIELD, _asset_request)


@external
def claim_strategy_fees(_asset_request: uint256 = 0) -> uint256:
    """
    @notice user by current Strategy proposer to withdraw fees.
    @param _asset_request total assets desired for withdrawl. 
    @return total assets transferred.    
    @dev If _asset_request is 0 then will withdrawl all eligible assets.
    """
    return self._claim_fees(FeeType.PROPOSER, _asset_request)    


@external
def claim_all_fees(_asset_request: uint256 = 0) -> uint256:
    """
    @notice if 4626 vault owner and Strategy proposer are same wallet address, used to withdraw all fees at once.
    @param _asset_request total assets desired for withdrawl. 
    @return total assets transferred.    
    @dev If _asset_request is 0 then will withdrawl all eligible assets.
    """
    return self._claim_fees(FeeType.BOTH, _asset_request)


@internal
@view
def _convertToShares(_asset_amount: uint256) -> uint256:
    shareqty : uint256 = self.totalSupply
    grossAssets : uint256 = self._totalAssets()

    claimable_fees : uint256 = self._claimable_fees_available(FeeType.BOTH, grossAssets)
    
    # Less fees
    assert grossAssets >= claimable_fees, "_convertToShares sanity failure!" # BDM
    assetqty : uint256 = grossAssets - claimable_fees    

    # If there aren't any shares/assets yet it's going to be 1:1.
    if shareqty == 0 : return _asset_amount
    if assetqty == 0 : return _asset_amount

    return _asset_amount * shareqty / assetqty 


@external
@view
def convertToShares(_asset_amount: uint256) -> uint256: 
    """
    @notice calculates the current number of 4626 shares would be received for a deposit of assets.
    @param _asset_amount the quantity of assets to be converted to shares.
    @return current share value for the asset quantity
    @dev any fees owed to 4626 owner or strategy proposer are removed before conversion.
    """
    return self._convertToShares(_asset_amount)

@internal
@view
def _convertToAssets(_share_amount: uint256) -> uint256:
    shareqty : uint256 = self.totalSupply
    assetqty : uint256 = self._totalAssets()

    claimable_fees : uint256 = self._claimable_fees_available(FeeType.BOTH, assetqty)
    
    # Less fees
    assert assetqty >= claimable_fees, "_convertToAssets sanity failure!" # BDM    
    assetqty -= claimable_fees     

    # If there aren't any shares yet it's going to be 1:1.
    if shareqty == 0: return _share_amount    
    if assetqty == 0 : return _share_amount    

    return _share_amount * assetqty / shareqty


@external
@view
def convertToAssets(_share_amount: uint256) -> uint256:
    """
    @notice calculates the current quantity of assets would be received for a deposit of 4626 shares.
    @param _share_amount the quantity of 4626 shares to be converted to assets.
    @return current asset value for the share quantity
    @dev any fees owed to 4626 owner or strategy proposer are removed before conversion.
    """
    return self._convertToAssets(_share_amount)


@external
@view
def maxDeposit(_spender: address) -> uint256:
    """
    @notice Maximum amount of the underlying asset that can be deposited into the Vault for the receiver, through a deposit call.
    @param _spender address (ignored)
    @return a really big number that we'll never hit.
    @dev Due to the nature of the LPs that we depend upon there's no way to properly support this part of the EIP-4626 spec.
    """
    return convert(max_value(int128), uint256)


@external
def previewDeposit(_asset_amount: uint256) -> uint256:
    """
    @notice This function converts asset amount to shares in deposit
    @param _asset_amount Number amount of assets to evaluate
    @return Shares per asset amount in deposit
    """
    return self._convertToShares(_asset_amount)


@external
@view
def maxMint(_receiver: address) -> uint256:
    """
    @notice Maximum amount of shares that can be minted from the Vault for the receiver, through a mint call.
    @param _receiver address (ignored)
    @return a really big number that we'll never hit.
    @dev Due to the nature of the LPs that we depend upon there's no way to properly support this part of the EIP-4626 spec.
    """
    return convert(max_value(int128), uint256)


@external
@view 
def previewMint(_share_amount: uint256) -> uint256:
    """
    @notice This function returns asset qty that would be returned for this share_amount per mint
    @param _share_amount Number amount of shares to evaluate
    @return Assets per share amount in mint
    """
    return self._convertToAssets(_share_amount)


@external
def mint(_share_amount: uint256, _receiver: address) -> uint256:
    """
    @notice This function mints asset qty that would be returned for this share_amount to receiver
    @param _share_amount Number amount of shares to evaluate
    @param _receiver Address of receiver to evaluate
    @return Asset value of _share_amount
    """
    assetqty : uint256 = self._convertToAssets(_share_amount)
    return self._deposit(assetqty, _receiver)


@external
@view 
def maxWithdraw(_owner: address) -> uint256:
    """
    @notice This function returns maximum assets this _owner can extract
    @param _owner Address of owner of assets to evaluate
    @return maximum assets this _owner can withdraw
    """
    # TODO: If withdraws are disabled return 0.
    return self._convertToAssets(self.balanceOf[_owner])


@external
@view 
def previewWithdraw(_asset_amount: uint256) -> uint256:
    """
    @notice This function returns asset qty per share amount for withdraw
    @param _asset_amount Number amount of assets to evaluate
    @return Share qty per asset amount in withdraw
    """
    return self._convertToShares(_asset_amount)


@external
@view 
# Returns maximum shares this _owner can redeem.
def maxRedeem(_owner: address) -> uint256:
    """
    @notice This function returns maximum shares this _owner can redeem
    @param _owner Address of owner of assets to evaluate
    @return maximum shares this _owner can redeem
    """
    # TODO: If redemption is disabled return 0.
    return self.balanceOf[_owner]


@external
@view 
def previewRedeem(_share_amount: uint256) -> uint256:
    """
    @notice This function returns asset qty per share amount for redemption
    @param _share_amount Number amount of shares to evaluate
    @return asset qty per share amount in redemption
    """
    return self._convertToAssets(_share_amount)


@external
def redeem(_share_amount: uint256, _receiver: address, _owner: address) -> uint256:
    """
    @notice This function redeems asset qty that would be returned for this share_amount to receiver from owner
    @param _share_amount Number amount of shares to evaluate
    @param _receiver Address of receiver to evaluate
    @param _owner Address of owner of assets to evaluate
    @return Asset qty withdrawn
    """
    assetqty: uint256 = self._convertToAssets(_share_amount)
    return self._withdraw(assetqty, _receiver, _owner)


struct BalanceTX:
    qty: int256
    adapter: address


struct BalancePool:
    adapter: address
    current: uint256
    last_value: uint256    
    ratio: uint256
    target: uint256 
    delta: int256


# Returns current 4626 asset balance, first 3 parts of BalancePools, total Assets, & total ratios of Strategy.
@internal
@view 
def _getCurrentBalances() -> (uint256, BalancePool[MAX_POOLS], uint256, uint256):
    current_local_asset_balance : uint256 = ERC20(asset).balanceOf(self)

    pool_balances: BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])


    # If there are no pools then nothing to do.
    if len(self.dlending_pools) == 0: return current_local_asset_balance, pool_balances, current_local_asset_balance, 0

    total_balance: uint256 = current_local_asset_balance
    total_ratios: uint256 = 0
    pos: uint256 = 0

    for pool in self.dlending_pools:
        pool_balances[pos].adapter = pool
        pool_balances[pos].current = self._poolAssets(pool)
        total_balance += pool_balances[pos].current

        plan : AdapterValue = self.strategy[pool]

        pool_balances[pos].ratio = plan.ratio

        total_ratios += plan.ratio
        pool_balances[pos].last_value = plan.last_asset_value
        
        pos += 1

    return current_local_asset_balance, pool_balances, total_balance, total_ratios


@external
@view 
def getCurrentBalances() -> (uint256, BalancePool[MAX_POOLS], uint256, uint256): 
    """
    @notice This function returns current balances of pools
    @return Current balances of pools
    """
    return self._getCurrentBalances()


@external
@view
def getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_balances: BalancePool[MAX_POOLS], _min_outgoing_tx: uint256) -> (uint256, int256, uint256, BalancePool[MAX_POOLS], address[MAX_POOLS]): 
    """
    @dev    Returns: 
            1) uint256 - the total asset allocation across all pools (less _d4626_asset_target),
            2) int256 - the total delta of local d4626 assets that would be moved across
            all transactions, 
            3) uint256 - the total number of planned txs to achieve these targets,
            4) BalancePool[MAX_POOLS] - the updated list of transactions required to
            meet the target goals sorted in ascending order of BalancePool.delta.
            5) A list of any adapters that should be blocked because they lost funds.

    @param  _d4626_asset_target minimum asset target goal to be made available
            for withdraw from the 4626 contract.

    @param  _total_assets the sum of all assets held by the d4626 plus all of
            its adapter pools.

    @param _total_ratios the total of all BalancePool.ratio values in _pool_balances.

    @param _pool_balances current state of the adapter pools. BDM TODO Specify TYPES!

    @param _min_outgoing_tx the minimum size of a tx depositing funds to an adapter (as set by the current strategy).

    """    
    return FundsAllocator(self.funds_allocator).getTargetBalances(_d4626_asset_target, _total_assets, _total_ratios, _pool_balances, _min_outgoing_tx)


@internal
@view
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_states: BalancePool[MAX_POOLS]) -> (BalanceTX[MAX_POOLS], address[MAX_POOLS]): 
    return FundsAllocator(self.funds_allocator).getBalanceTxs( _target_asset_balance, _max_txs, _min_proposer_payout, _total_assets, _total_ratios, _pool_states)


@external
@view
def getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_states: BalancePool[MAX_POOLS]) -> (BalanceTX[MAX_POOLS], address[MAX_POOLS]):  
    return FundsAllocator(self.funds_allocator).getBalanceTxs( _target_asset_balance, _max_txs, _min_proposer_payout, _total_assets, _total_ratios, _pool_states)


@internal
def _balanceAdapters( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):
    # Make sure we have enough assets to send to _receiver.
    txs: BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])
    blocked_adapters: address[MAX_POOLS] = empty(address[MAX_POOLS])

    # If there are no pools then nothing to do.
    if len(self.dlending_pools) == 0: return 

    # Setup current state of vault & pools & strategy.
    d4626_assets: uint256 = 0
    pool_states: BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])
    total_assets: uint256 = 0
    total_ratios: uint256 = 0
    d4626_assets, pool_states, total_assets, total_ratios = self._getCurrentBalances()

    txs, blocked_adapters = self._getBalanceTxs( _target_asset_balance, _max_txs, self.min_proposer_payout, total_assets, total_ratios, pool_states )

    # If there are blocked_adapters then set their strategy ratios to zero.
    for adapter in blocked_adapters:
        if adapter == empty(address): break

        new_strat : AdapterValue = self.strategy[adapter]
        new_strat.ratio = 0
        self.strategy[adapter] = new_strat

        log PoolLoss(adapter, new_strat.last_asset_value, self._poolAssets(adapter))

    # Move the funds in/out of Lending Pools as required.
    for dtx in txs:
        if dtx.adapter == empty(address): break
        if dtx.qty == 0: continue

        # If the outgoing tx is larger than the min_proposer_payout then do it, otherwise ignore it.
        if dtx.qty > 0 and dtx.qty >= convert(self.min_proposer_payout, int256):
            # Move funds into the lending pool's adapter.
            assert ERC20(asset).balanceOf(self) >= convert(dtx.qty, uint256), "_balanceAdapters d4626 insufficient assets!"
            self._adapter_deposit(dtx.adapter, convert(dtx.qty, uint256))

        elif dtx.qty < 0:
            # Liquidate funds from lending pool's adapter.
            qty: uint256 = convert(dtx.qty * -1, uint256)         
            self._adapter_withdraw(dtx.adapter, qty, self)


@external
def balanceAdapters( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):
    """
    @notice The function provides a way to balance adapters
    @param _target_asset_balance Target amount for assets balance
    @param _max_txs Maximum amount of adapters
    """
    self._balanceAdapters(_target_asset_balance, _max_txs)


@internal
def _mint(_receiver: address, _share_amount: uint256) -> uint256:
    """
    @dev Mint an amount of the token and assigns it to an account.
         This encapsulates the modification of balances such that the
         proper events are emitted.
    @param _to The account that will receive the created tokens.
    @param _value The amount that will be created.
    """
    assert _receiver != empty(address), "Receiver cannot be zero."
    self.totalSupply += _share_amount
    self.balanceOf[_receiver] += _share_amount
    log Transfer(empty(address), _receiver, _share_amount)
    return _share_amount


@internal
def _adapter_deposit(_adapter: address, _asset_amount: uint256):    
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False

    starting_assets : uint256 = self._poolAssets(_adapter)

    result_ok, response = raw_call(
        _adapter,
        _abi_encode(_asset_amount, method_id=method_id("deposit(uint256)")),
        max_outsize=32,
        is_delegate_call=True,
        revert_on_failure=False
        )

    # TODO - interpret response as revert msg in case this assertion fails.
    assert result_ok == True, convert(response, String[32]) #"_adapter_deposit raw_call failed"

    new_assets : uint256 = self._poolAssets(_adapter)
    #Allow to get one less than what we deposited to account for rounding issues
    #TODO: commenting out the following line as it was causing problems with compound adapter
    #TODO: Discuss with dynamo folks
    # assert _asset_amount + starting_assets <= new_assets+1, "Didn't move the assets into our adapter!"

    # Update our last_asset_value in our strategy for protection against LP exploits.
    self.strategy[_adapter].last_asset_value = new_assets


@internal
def _adapter_withdraw(_adapter: address, _asset_amount: uint256, _withdraw_to: address):

    current_balance : uint256 = ERC20(asset).balanceOf(_adapter)
    balbefore : uint256 = ERC20(asset).balanceOf(_withdraw_to)
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False

    assert _adapter != empty(address), "EMPTY ADAPTER!"
    assert _withdraw_to != empty(address), "EMPTY WITHDRAW_TO!"

    result_ok, response = raw_call(
        _adapter,
        _abi_encode(_asset_amount, _withdraw_to, method_id=method_id("withdraw(uint256,address)")),
        max_outsize=32,
        is_delegate_call=True,
        revert_on_failure=False
        )

    assert result_ok == True, "withdraw raw_call failed!"

    balafter : uint256 = ERC20(asset).balanceOf(_withdraw_to)
    assert balafter != balbefore, "NOTHING CHANGED!"
    assert balafter - balbefore == _asset_amount, "DIDN'T GET OUR ASSETS BACK!"
    
    # Update our last_asset_value in our strategy for protection against LP exploits.
    self.strategy[_adapter].last_asset_value = self._poolAssets(_adapter)


@internal
def _deposit(_asset_amount: uint256, _receiver: address) -> uint256:
    assert _receiver != empty(address), "Cannot send shares to zero address."

    assert _asset_amount <= ERC20(asset).balanceOf(msg.sender), "4626Deposit insufficient funds."

    # MUST COMPUTE SHARES FIRST!
    shares : uint256 = self._convertToShares(_asset_amount)

    # Move assets to this contract from caller in one go.
    ERC20(asset).transferFrom(msg.sender, self, _asset_amount)

    # It's our intention to move all funds into the lending pools so 
    # our target balance is zero.
    self._balanceAdapters( empty(uint256) )

    # Now mint assets to return to investor.    
    self._mint(_receiver, shares)

    # Update all-time assets deposited for yield tracking.
    self.total_assets_deposited += _asset_amount

    log Deposit(msg.sender, msg.sender, _asset_amount, shares)

    return shares


@external
def deposit(_asset_amount: uint256, _receiver: address) -> uint256: 
    """
    @notice This function provides a way to transfer an asset amount from message sender to receiver
    @param _asset_amount Number amount of assets to evaluate
    @param _receiver Address of receiver to evaluate
    @return Share amount deposited to receiver
    """
    return self._deposit(_asset_amount, _receiver)


@internal
def _withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256:

    # How many shares does it take to get the requested asset amount?
    shares: uint256 = self._convertToShares(_asset_amount)
    xcbal : uint256 = self.balanceOf[_owner]

    # Owner has adequate shares?
    assert self.balanceOf[_owner] >= shares, "Owner has inadequate shares for this withdraw."

    # Withdrawl is handled by someone other than the owner?
    if msg.sender != _owner:

        assert self.allowance[_owner][msg.sender] >= shares, "Not authorized to move enough owner's shares."
        self.allowance[_owner][msg.sender] -= shares

    # Burn the shares.
    self.balanceOf[_owner] -= shares    

    self.totalSupply -= shares
    log Transfer(_owner, empty(address), shares)

    # Make sure we have enough assets to send to _receiver.
    self._balanceAdapters( _asset_amount )

    assert ERC20(asset).balanceOf(self) >= _asset_amount, "ERROR - 4626 DOESN'T HAVE ENOUGH BALANCE TO WITHDRAW!"

    # Now send assets to _receiver.
    ERC20(asset).transfer(_receiver, _asset_amount)

    # Update all-time assets withdrawn for yield tracking.
    self.total_assets_withdrawn += _asset_amount

    log Withdraw(msg.sender, _receiver, _owner, _asset_amount, shares)

    return shares

@external
def withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256:
    """
    @notice This function provides a way to withdraw an asset amount to receiver
    @param _asset_amount Number amount of assets to evaluate
    @param _receiver Address of receiver to evaluate
    @param _owner Address of owner of assets to evaluate
    @return Share amount withdrawn to receiver
    """
    return self._withdraw(_asset_amount,_receiver,_owner)

### ERC20 functionality.

@internal
def _transfer(_from: address, _to: address, _value: uint256):
    assert self.balanceOf[_from] >= _value, "ERC20 transfer insufficient funds."
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    log Transfer(_from, _to, _value)


@internal
def _approve(_owner: address, _spender: address, _value: uint256):
    self.allowance[_owner][_spender] = _value
    log Approval(_owner, _spender, _value)


@internal
def _transferFrom(_operator: address, _from: address, _to:address, _value: uint256):
    assert self.balanceOf[_from] >= _value, "ERC20 transferFrom insufficient funds."
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value

    assert self.allowance[_from][_operator] >= _value, "ERC20 transfer insufficient allowance."

    self.allowance[_from][_operator] -= _value
    log Transfer(_from, _to, _value)


@external
def transfer(_to : address, _value : uint256) -> bool:
    """
    @dev Transfer token for a specified address
    @param _to The address to transfer to.
    @param _value The amount to be transferred.
    """
    self._transfer(msg.sender, _to, _value)
    return True


@external
def transferFrom(_from : address, _to : address, _value : uint256) -> bool:
    """
     @dev Transfer tokens from one address to another.
     @param _from address The address which you want to send tokens from
     @param _to address The address which you want to transfer to
     @param _value uint256 the amount of tokens to be transferred
    """
    self._transferFrom(msg.sender, _from, _to, _value)
    return True


@external
def approve(_spender : address, _value : uint256) -> bool:
    """
    @dev Approve the passed address to spend the specified amount of tokens on behalf of msg.sender.
         Beware that changing an allowance with this method brings the risk that someone may use both the old
         and the new allowance by unfortunate transaction ordering. One possible solution to mitigate this
         race condition is to first reduce the spender's allowance to 0 and set the desired value afterwards:
         https://github.com/ethereum/EIPs/issues/20#issuecomment-263524729
    @param _spender The address which will spend the funds.
    @param _value The amount of tokens to be spent.
    """
    self._approve(msg.sender, _spender, _value) 
    return True    
