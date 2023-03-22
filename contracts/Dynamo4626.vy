# @version 0.3.7

from vyper.interfaces import ERC20
from vyper.interfaces import ERC4626
#from interfaces.adapter import LPAdapter
import LPAdapter as LPAdapter
implements: ERC20
implements: ERC4626


MAX_POOLS : constant(int128) = 5
MAX_BALTX_DEPOSIT : constant(uint8) = 2

# Contract owner hold 10% of the yield.
YIELD_FEE_PERCENTAGE : constant(uint256) = 10

# 1% of the yield belongs to the Strategy proposer.
PROPOSER_FEE_PERCENTAGE: constant(uint256) = 1

enum FeeType:
    BOTH
    YIELD
    PROPOSER

name: public(immutable(String[64]))
symbol: public(immutable(String[32]))
decimals: public(immutable(uint8))
asset: public(immutable(address))

total_assets_deposited: public(uint256)
total_assets_withdrawn: public(uint256)
total_yield_fees_claimed: public(uint256)
total_strategy_fees_claimed: public(uint256)

struct AdapterStrategy:
    adapter: address
    ratio: uint256

owner: address
governance: address
current_proposer: address
min_proposer_payout: uint256

dlending_pools : DynArray[address, MAX_POOLS]

totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])

# Maps adapter address (not LP address) to ratios.
strategy: public(HashMap[address, uint256])


event PoolAdded:
    sender: indexed(address)
    contract_addr: indexed(address)

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

event StrategyActivation:
    strategy: AdapterStrategy[MAX_POOLS]
    proposer: address
    

@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _pools: DynArray[address, MAX_POOLS], _governance: address):

    assert MAX_BALTX_DEPOSIT <= MAX_POOLS, "Invalid contract pre-conditions."
    assert _governance != empty(address), "Governance cannot be null address."

    name = _name
    symbol = _symbol
    decimals = _decimals

    # Is this likely to be an actual ERC20 contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)
    result_ok, response = raw_call(_erc20asset, method_id("balanceOf(address)"), max_outsize=32, value=empty(uint256), is_static_call=True, revert_on_failure=False)
    assert (response != empty(Bytes[32])), "Doesn't appear to be an ERC20 contract."

    asset = _erc20asset


    self.owner = msg.sender
    self.governance = _governance
    self.totalSupply = 0

    assert len(self.dlending_pools)==0, "HUh?!?!?" # TODO - remove

    for pool in _pools:
        self._add_pool(pool)        


@external
def replaceGovernanceContract(_new_governance: address) -> bool:
    assert msg.sender == self.governance, "Only existing Governance contract may replace itself."
    assert _new_governance != empty(address), "Governance cannot be null address."

    self.governance = _new_governance    
    return True


@external
def replaceOwner(_new_owner: address) -> bool:
    assert msg.sender == self.owner, "Only existing owner can replace the owner."
    assert _new_owner != empty(address), "Owner cannot be null address."

    self.owner = _new_owner
    return True


# Can't simply have a public lending_pools variable due to this Vyper issue:
# https://github.com/vyperlang/vyper/issues/2897
@view
@external
def lending_pools() -> DynArray[address, MAX_POOLS]: return self.dlending_pools


@internal
def _set_strategy(_proposer: address, _strategies : AdapterStrategy[MAX_POOLS], _min_proposer_payout : uint256) -> bool:
    assert msg.sender == self.governance, "Only Governance DAO may set a new strategy."
    assert _proposer != empty(address), "Proposer can't be null address."

    # Are we replacing the old proposer?
    if self.current_proposer != _proposer:

        current_assets : uint256 = self._totalAssets()

        # Is there enough payout to actually do a transaction?
        if self._claimable_fees_available(FeeType.PROPOSER, current_assets) >= self.min_proposer_payout:
                
            # Pay prior proposer his earned fees.
            self._claim_fees(FeeType.PROPOSER, 0, current_assets)

        self.current_proposer = _proposer
        self.min_proposer_payout = _min_proposer_payout




    # Clear out all existing ratio allocations.
    for pool in self.dlending_pools:
        self.strategy[pool] = empty(uint256)

    # Now set strategies according to the new plan.
    for strategy in _strategies:
        self.strategy[strategy.adapter] = strategy.ratio 

    # Rebalance vault according to new strategy.
    self._balanceAdapters(0, convert(MAX_POOLS, uint8))

    log StrategyActivation(_strategies, _proposer)

    return True


@external
def set_strategy(_proposer: address, _strategies : AdapterStrategy[MAX_POOLS], _min_proposer_payout : uint256) -> bool:
    return self._set_strategy(_proposer, _strategies, _min_proposer_payout)


@internal 
def _add_pool(_pool: address) -> bool:    
    # Do we already support this pool?
    assert (_pool in self.dlending_pools) == False, "pool already supported."

    # Is this likely to be an actual LPAdapter contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)

    result_ok, response = raw_call(_pool, method_id("maxDeposit()"), max_outsize=32, is_static_call=True, revert_on_failure=False)
    assert (response != empty(Bytes[32])), "Doesn't appear to be an LPAdapter."
    # TODO : should we check the result_ok result instead or in addition to?

    self.dlending_pools.append(_pool)

    # TODO : Hack - for now give each pool equal strategic balance.
    self.strategy[_pool] = 1

    log PoolAdded(msg.sender, _pool)

    return True


@external 
def add_pool(_pool: address) -> bool: 
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new Lending Pools."

    return self._add_pool(_pool)


@internal
def _remove_pool(_pool: address) -> bool:
    # TODO - pull out all assets, remove pool, rebalance pool.
    return False


@external
def remove_pool(_pool: address) -> bool:
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can remove Lending Pools."

    return self._remove_pool(_pool)


@internal
@view
def _poolAssets(_pool: address) -> uint256:
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False

    assert _pool != empty(address), "EMPTY POOL!!"    

    # TODO: Shouldn't I just 'assetqty += LPAdapter(pool).totalAssets()'???
    # assetqty += LPAdapter(pool).totalAssets()
    result_ok, response = raw_call(
        _pool,
        method_id("totalAssets()"),
        max_outsize=32,
        is_static_call=True,
        #is_delegate_call=True,
        revert_on_failure=False
        )

    if result_ok:
        return convert(response, uint256)

    assert result_ok, "TOTAL ASSETS REVERT!"        
    return empty(uint256)


@internal
@view
def _totalAssets() -> uint256:
    assetqty : uint256 = ERC20(asset).balanceOf(self)
    for pool in self.dlending_pools:
        if pool == empty(address): break
        assetqty += self._poolAssets(pool)

    return assetqty


@external
@view
def totalAssets() -> uint256: return self._totalAssets()


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
    assets : uint256 = self._totalAssets()
    return self._totalReturns(assets)    


@internal
@view 
def _claimable_fees_available(_yield : FeeType, _current_assets : uint256 = 0) -> uint256:
    total_returns : int256 = self._totalReturns(_current_assets)
    if total_returns < 0: return 0

    # Assume FeeType.YIELD
    fee_percentage: decimal = convert(YIELD_FEE_PERCENTAGE, decimal)
    if _yield == FeeType.PROPOSER:
        fee_percentage = convert(PROPOSER_FEE_PERCENTAGE, decimal)
    elif _yield == FeeType.BOTH:
        fee_percentage += convert(PROPOSER_FEE_PERCENTAGE, decimal)

    dtotal_fees_available : decimal = convert(total_returns, decimal) * (fee_percentage / 100.0)

    assert self.total_strategy_fees_claimed + self.total_yield_fees_claimed <= convert(dtotal_fees_available, uint256), "Total fee calc error!"

    result : uint256 = 0
    if _yield == FeeType.YIELD or _yield == FeeType.BOTH:
        result = convert(dtotal_fees_available, uint256) - self.total_yield_fees_claimed
    elif _yield == FeeType.PROPOSER:
        result = convert(dtotal_fees_available, uint256) - self.total_strategy_fees_claimed
    elif _yield == FeeType.BOTH:
        result += convert(dtotal_fees_available, uint256) - self.total_strategy_fees_claimed
    else:
        assert False, "Invalid FeeType!"

    return result


@external
@view    
def claimable_yield_fees_available(_current_assets : uint256 = 0) -> uint256:
    return self._claimable_fees_available(FeeType.YIELD, _current_assets)    


@external
@view    
def claimable_strategy_fees_available(_current_assets : uint256 = 0) -> uint256:
    return self._claimable_fees_available(FeeType.PROPOSER, _current_assets)  


@external
@view    
def claimable_all_fees_available(_current_assets : uint256 = 0) -> uint256:
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
    if total_fees_remaining < claim_amount: return 0

    # Good claim. Do we have the balance locally?
    if ERC20(asset).balanceOf(self) < claim_amount:

        # Need to liquidate some shares to fulfill 
        self._balanceAdapters(claim_amount)

    # Account for the claim and move the funds.
    if _yield == FeeType.YIELD:
        self.total_yield_fees_claimed += claim_amount    
    elif _yield == FeeType.PROPOSER:
        self.total_strategy_fees_claimed += claim_amount        
    elif _yield == FeeType.BOTH:
        prop_fee : uint256 = self._claimable_fees_available(FeeType.PROPOSER, _current_assets)
        self.total_yield_fees_claimed += claim_amount - prop_fee
        self.total_strategy_fees_claimed += prop_fee
    ERC20(asset).transfer(msg.sender, claim_amount)

    return claim_amount


@external
def claim_yield_fees(_asset_amount: uint256 = 0) -> uint256:
    assert msg.sender == self.owner, "Only owner may claim yield fees."
    return self._claim_fees(FeeType.YIELD, _asset_amount)


@external
def claim_strategy_fees(_asset_amount: uint256 = 0) -> uint256:
    assert msg.sender == self.current_proposer, "Only curent proposer may claim strategy fees."
    return self._claim_fees(FeeType.PROPOSER, _asset_amount)    


@external
def claim_all_fees(_asset_amount: uint256 = 0) -> uint256:
    assert msg.sender == self.owner and msg.sender == self.current_proposer, "Must be both owner and current proposer to claim all fees."
    return self._claim_fees(FeeType.BOTH, _asset_amount)


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
def convertToShares(_asset_amount: uint256) -> uint256: return self._convertToShares(_asset_amount)


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
def convertToAssets(_share_amount: uint256) -> uint256: return self._convertToAssets(_share_amount)


@external
@view
def maxDeposit(_spender: address) -> uint256:
    # TODO - if deposits are disabled return 0
    # Ensure this value cannot take local asset balance over max_value(128) for _getBalanceTxs math.
    return convert(max_value(int128), uint256) - ERC20(asset).balanceOf(self)


@external
def previewDeposit(_asset_amount: uint256) -> uint256:
    return self._convertToShares(_asset_amount)


@external
@view
# Returns maximum number of shares that can be minted for this address.
def maxMint(_receiver: address) -> uint256:
    # TODO - if mints are disabled return 0.
    return convert(max_value(int128), uint256)


@external
@view 
# Returns asset qty that would be returned for this share_amount.
def previewMint(_share_amount: uint256) -> uint256:
    return self._convertToAssets(_share_amount)


@external
def mint(_share_amount: uint256, _receiver: address) -> uint256:
    assetqty : uint256 = self._convertToAssets(_share_amount)
    return self._deposit(assetqty, _receiver)


@external
@view 
# Returns maximum assets this _owner can extract.
def maxWithdraw(_owner: address) -> uint256:
    # TODO: If withdraws are disabled return 0.
    return self._convertToAssets(self.balanceOf[_owner])


@external
@view 
def previewWithdraw(_asset_amount: uint256) -> uint256:
    return self._convertToShares(_asset_amount)


@external
@view 
# Returns maximum shares this _owner can redeem.
def maxRedeem(_owner: address) -> uint256:
    # TODO: If redemption is disabled return 0.
    return self.balanceOf[_owner]


@external
@view 
def previewRedeem(_share_amount: uint256) -> uint256:
    return self._convertToAssets(_share_amount)


@external
def redeem(_share_amount: uint256, _receiver: address, _owner: address) -> uint256:
    assetqty: uint256 = self._convertToAssets(_share_amount)
    #if assetqty == 100911382350000000000000:
    #    assert False, "Matches!"
    return self._withdraw(assetqty, _receiver, _owner)


struct BalanceTX:
    qty: int256
    adapter: address


struct BalancePool:
    adapter: address
    current: uint256
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
        pool_balances[pos].ratio = self.strategy[pool]
        total_balance += pool_balances[pos].current
        total_ratios += pool_balances[pos].ratio
        pos += 1

    return current_local_asset_balance, pool_balances, total_balance, total_ratios


@external
@view 
def getCurrentBalances() -> (uint256, BalancePool[MAX_POOLS], uint256, uint256): return self._getCurrentBalances()


@internal
@pure
def _getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_balances: BalancePool[MAX_POOLS]) -> (uint256, int256, uint256, BalancePool[MAX_POOLS]):
    """
    @dev    Returns 1) the total asset allocation across all pools 
            (less _d4626_asset_target),
            2) the total delta of local d4626 assets that would be moved across
            all transactions, 
            3) the total number of planned txs to achieve these targets,
            4) plus the updated list of transactions required to
            meet the target goals sorted in ascending order of BalancePool.delta.

    @param  _d4626_asset_target minimum asset target goal to be made available
            for withdraw from the 4626 contract.

    @param  _total_assets the sum of all assets held by the d4626 plus all of
            its adapter pools.

    @param _total_ratios the total of all BalancePool.ratio values in _pool_balances.

    @param _pool_balances current state of the adapter pools.
    """

    # WHAT IF THE _d4626_asset_target is larger than the total assets?!?!?
    assert _d4626_asset_target <= _total_assets, "Not enough assets to fulfill d4626 target goals!"

    total_pool_target_assets : uint256 = _total_assets - _d4626_asset_target

    pool_assets_allocated : uint256 = 0 
    d4626_delta : int256 = 0
    tx_count: uint256 = 0

    # We have to copy from the old list into a new one to update values. (NOT THE MOST EFFICIENT OPTION.)
    pools : BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])

    for pos in range(MAX_POOLS):
        pool : BalancePool = _pool_balances[pos]
        if pool.adapter == empty(address): break

        # If the pool has been removed from the strategy then we must empty it!
        if pool.ratio == 0:
            pool.target = 0
            pool.delta = convert(pool.current, int256) * -1 # Withdraw it all!
        else:
            pool_percent : decimal = convert(pool.ratio, decimal)/convert(_total_ratios,decimal)
            pool.target = convert(convert(total_pool_target_assets, decimal) * pool_percent, uint256)        
            pool.delta = convert(pool.target, int256) - convert(pool.current, int256)            

            pool_result : int256 = convert(pool.current, int256) + pool.delta
            assert pool_result >= 0, "Pool resulting balance can't be less than zero!"
            pool_assets_allocated += convert(pool_result, uint256)

        d4626_delta += pool.delta * -1
        if pool.delta != 0: tx_count += 1

        # Do an insertion sort keeping in order of lowest pool.delta value.
        if pos == 0:
            pools[pos]=pool
        else:
            for npos in range(MAX_POOLS):
                if npos == pos: break
                if pool.adapter == empty(address) or pool.delta < pools[npos].delta:
                    # Here's our insertion point. Shift the existing txs to the right.
                    for xpos in range(MAX_POOLS):
                        dst: uint256 = convert(pos,uint256)-convert(xpos,uint256)
                        src: uint256 = dst-1
                        if convert(xpos,uint256) == src: break

                        pools[dst]=pools[src]

                    # Now insert our element here.
                    pools[npos]=pool 

    # Check to make sure we hit our _d4626_asset_target in the end!

    return pool_assets_allocated, d4626_delta, tx_count, pools


@external
@pure 
def getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_balances: BalancePool[MAX_POOLS]) -> (uint256, int256, uint256, BalancePool[MAX_POOLS]): return self._getTargetBalances(_d4626_asset_target, _total_assets, _total_ratios, _pool_balances)


@internal
@view
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8) -> BalanceTX[MAX_POOLS]: 
    result : BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])

    # If there are no pools then nothing to do.
    if len(self.dlending_pools) == 0: return result

    # Setup current state of vault & pools & strategy.
    d4626_assets: uint256 = 0
    pool_states: BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])
    total_assets: uint256 = 0
    total_ratios: uint256 = 0
    d4626_assets, pool_states, total_assets, total_ratios = self._getCurrentBalances()

    # What's the optimal outcome for our vault/pools?
    pool_assets_allocated : uint256 = 0
    d4626_delta : int256 = 0
    tx_count : uint256 = 0
    pool_assets_allocated, d4626_delta, tx_count, pool_states = self._getTargetBalances(_target_asset_balance, total_assets, total_ratios, pool_states)


    pos : uint256 = 0
    for tx_bal in pool_states:
        result[pos] = BalanceTX({qty: tx_bal.delta, adapter: tx_bal.adapter})
        pos += 1

    # # Schedule the tx order while trying to stay within the _max_tx count limit.
    # optional_inbound : DynArray[uint256,MAX_POOLS] = empty(DynArray[uint256,MAX_POOLS])
    # optional_outbound : DynArray[uint256,MAX_POOLS] = empty(DynArray[uint256,MAX_POOLS])

    # pos : uint256 = 0
    # scheduled : uint256 = 0
    # for _tx in pool_states:
    #     if _tx.adapter == empty(address): break
    #     if _tx.target == 0 and _tx.delta < 0:
    #         # This is a non-optional tx as it is emptying a pool adapter.
    #         d4626_assets = convert(convert(d4626_assets,int256) - _tx.delta, uint256)
    #         result[pos]= BalanceTX( {qty: _tx.delta, adapter : _tx.adapter} )
    #         pos += 1
    #         scheduled += 1
    #         continue

    #     if pos >= convert(_max_txs, uint256) and d4626_assets >= _target_asset_balance:
    #         # We've met our d4626 target and already have our max desired tx count.
    #         # Defer this tx.
    #         if _tx.delta > 0:
    #             optional_outbound.append(pos)
    #         else:
    #             optional_inbound.append(pos)
    #         pos += 1
    #         continue

    #     if convert(convert(d4626_assets,int256) - _tx.delta, uint256) < _target_asset_balance:
    #         # We can take this tx and still meet our d4626 assets target.
    #         result[pos]= BalanceTX( {qty: _tx.delta, adapter : _tx.adapter} )
    #         scheduled += 1 
    #     elif _tx.delta < 0:
    #             # This tx moves funds to our d4626. Take it.
    #             d4626_assets = convert(convert(d4626_assets,int256) - _tx.delta, uint256)
    #             result[pos]= BalanceTX( {qty: _tx.delta, adapter : _tx.adapter} )             
    #             scheduled += 1
    #     else:
    #             # Defer this tx.
    #             optional_outbound.append(pos)            
    #     pos += 1

    # # Are we good to go now?
    # if d4626_assets >= _target_asset_balance and (scheduled >= convert(_max_txs, uint256) or scheduled == tx_count): return result

    # # Walk over our pending txs and grab what we need most.
    # in_pos : uint256 = 0
    # for npos in range(MAX_POOLS):
    #     if d4626_assets < _target_asset_balance:
    #         # We need more funds!
    #         if in_pos < len(optional_inbound):
    #             # There's still a pending inbound tx we can get funds from. Take it.
    #             pool : BalancePool = pool_states[optional_inbound[in_pos]]
    #             result[pos]= BalanceTX({qty : pool.delta, adapter : pool.adapter})
    #             d4626_assets = convert(convert(d4626_assets,int256) - result[pos].qty, uint256)                
    #             in_pos += 1
    #             pos += 1
    #             scheduled += 1
    #         else:
    #             # We have to go back and steal more funds!
    #             pass
    #     elif len(optional_outbound) > 0:
    #         # Try to take the maximum transfer into an adapter pool.
    #         considered : DynArray[uint256,MAX_POOLS] = empty(DynArray[uint256,MAX_POOLS])
    #         selected : uint256 = 0
    #         candidate_tx : BalancePool = empty(BalancePool)
    #         for tx_pos in optional_outbound:
    #              if pool_states[tx_pos].adapter != empty(address) and pool_states[tx_pos].delta > candidate_tx.delta \
    #                 and convert(convert(d4626_assets, int256) - candidate_tx.delta, uint256) >= _target_asset_balance:
    #                 # We can accept this one.
    #                 selected = tx_pos
    #                 candidate_tx = pool_states[tx_pos]
                    
    #         if candidate_tx.adapter != empty(address):
    #             result[pos]= BalanceTX({qty : candidate_tx.delta, adapter : candidate_tx.adapter})  
    #             d4626_assets = convert(convert(d4626_assets,int256) - result[pos].qty, uint256)
    #             pool_states[selected].adapter = empty(address)
    #             pos +=1
    #             scheduled += 1

    #     elif in_pos < len(optional_inbound):
    #         # Take the pending inbound tx and continue.
    #         pool : BalancePool = pool_states[optional_inbound[in_pos]]
    #         result[pos]= BalanceTX({qty : pool.delta, adapter : pool.adapter})

    #         d4626_assets = convert(convert(d4626_assets,int256) - result[pos].qty, uint256)
    #         in_pos += 1
    #         pos += 1
    #         scheduled += 1

    return result


@external
@view
def getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8) -> BalanceTX[MAX_POOLS]: 
    return self._getBalanceTxs( _target_asset_balance, _max_txs )


@internal
def _balanceAdapters( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):

    #assert False, "_balanceAdapters"

    # Make sure we have enough assets to send to _receiver.
    # txs: DynArray[BalanceTX, MAX_POOLS] = empty(DynArray[BalanceTX, MAX_POOLS])
    txs: BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])
    txs = self._getBalanceTxs( _target_asset_balance, _max_txs )

    # Move the funds in/out of Lending Pools as required.
    for dtx in txs:
        if dtx.adapter == empty(address): break
        if dtx.qty == 0: continue
        if dtx.qty > 0:
            # Move funds into the lending pool's adapter.
            assert ERC20(asset).balanceOf(self) >= convert(dtx.qty, uint256), "_balanceAdapters d4626 insufficient assets!"
            # TODO : check for deposit failure. If it's due to going beyond
            #        the adapter's maxDeposit() limit, try again with lower limit.
            self._adapter_deposit(dtx.adapter, convert(dtx.qty, uint256))

        else:
            # Liquidate funds from lending pool's adapter.
            qty: uint256 = convert(dtx.qty * -1, uint256)

            # TODO : check for withdraw failure. If it's due to going beyond
            #        the adapter's maxWithdraw limit then try again with lower limit.
            # TODO:  We also have to check to see if we short the 4626 balance, where
            #        the necessary funds will come from! Otherwise this may need to revert.
            #assert ERC20(asset).balanceOf(dtx.adapter) >= qty, "_balanceAdapters adapter insufficient assets!"

            # BDM
            #if ERC20(asset).balanceOf(dtx.adapter) < qty:
            #    missing: uint256 = qty - ERC20(asset).balanceOf(dtx.adapter)                 
            #    xmsg: String[274] = concat("Missing ", uint2str(missing), " assets to do ", uint2str(qty), " from ", uint2str(ERC20(asset).balanceOf(dtx.adapter)), " adapter tx.")
            #    assert False, xmsg
                 
            self._adapter_withdraw(dtx.adapter, qty, self)


@external
def balanceAdapters( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):
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
    assert _asset_amount + starting_assets == new_assets, "Didn't move the assets into our adapter!"


@internal
def _adapter_withdraw(_adapter: address, _asset_amount: uint256, _withdraw_to: address):
    current_balance : uint256 = ERC20(asset).balanceOf(_adapter)
    balbefore : uint256 = ERC20(asset).balanceOf(_withdraw_to)
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False

    #result_str : String[278] = concat("Not enough assets. Adapter: ", uint2str(convert(_adapter, uint256)), " Have : ", uint2str(current_balance), " need : ", uint2str(_asset_amount))
    #assert current_balance >= _asset_amount, result_str

    assert _adapter != empty(address), "EMPTY ADAPTER!"
    assert _withdraw_to != empty(address), "EMPTY WITHDRAW_TO!"

    result_ok, response = raw_call(
        _adapter,
        _abi_encode(_asset_amount, _withdraw_to, method_id=method_id("withdraw(uint256,address)")),
        max_outsize=32,
        is_delegate_call=True,
        revert_on_failure=False
        )

    #if _asset_amount == 1890:
    #    assert False, "Got here 841!"       

    # TODO - interpret response as revert msg in case this assertion fails.
    #if result_ok != True:
    #    res : String[32] = convert(response, String[32])
    #    assert False, concat("res = ", res)

    assert result_ok == True, "withdraw raw_call failed!"

    #if _asset_amount == 1890:

    #assert False, "Here we are 902!"

    balafter : uint256 = ERC20(asset).balanceOf(_withdraw_to)
    assert balafter != balbefore, "NOTHING CHANGED!"
    assert balafter - balbefore == _asset_amount, "DIDN'T GET OUR ASSETS BACK!"


@internal
def _deposit(_asset_amount: uint256, _receiver: address) -> uint256:
    assert _receiver != empty(address), "Cannot send shares to zero address."

    assert _asset_amount <= ERC20(asset).balanceOf(msg.sender), "4626Deposit insufficient funds."

    # MUST COMPUTE SHARES FIRST!
    shares : uint256 = self._convertToShares(_asset_amount)

    # Move assets to this contract from caller in one go.
    ERC20(asset).transferFrom(msg.sender, self, _asset_amount)

    #result_str : String[103] = concat("Not 500 _asset_amount : ", uint2str(_asset_amount))
    #assert _asset_amount == 500, result_str

    # It's our intention to move all funds into the lending pools so 
    # our target balance is zero.
    self._balanceAdapters( empty(uint256) )

    # Now mint assets to return to investor.    
    assert shares == _asset_amount, "DIFFERENT VALUES!"
    self._mint(_receiver, shares)

    # Update all-time assets deposited for yield tracking.
    self.total_assets_deposited += _asset_amount

    result : uint256 = _asset_amount

    # TODO : emit Deposit event!

    return result


@external
def deposit(_asset_amount: uint256, _receiver: address) -> uint256: return self._deposit(_asset_amount, _receiver)


@internal
def _withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256:

    # How many shares does it take to get the requested asset amount?
    shares: uint256 = self._convertToShares(_asset_amount)

    #result_str : String[103] = concat("Not 1890 assets : ", uint2str(_asset_amount))
    #assert False, result_str

    #assert shares == 1000, result_str

    xcbal : uint256 = self.balanceOf[_owner]

    #xxmsg : String[275] = concat("Owner has ", uint2str(xcbal), " shares but needs ", uint2str(shares), ".")

    # Owner has adequate shares?
    assert self.balanceOf[_owner] >= shares, "Owner has inadequate shares for this withdraw."
    #assert xcbal >= shares, xxmsg
    # if xcbal >= shares:
    # #    assert False, "Got here."
    #     #xcbal : uint256 = self.balanceOf[_owner]
    #     assert False, "EHERE!"
    #     assert False, "Got here."
    #     cbal: String[78] = uint2str(xcbal)
    #     #assert False, "Got here."
    #     xmsg : String[169] = concat("has: ", uint2str(self.balanceOf[_owner]), " needs: ", uint2str(shares))
    #     assert False, xmsg

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

    #assert False, "Got here!"    

    assert ERC20(asset).balanceOf(self) >= _asset_amount, "ERROR - 4626 DOESN'T HAVE ENOUGH BALANCE TO WITHDRAW!"

    # Now send assets to _receiver.
    ERC20(asset).transfer(_receiver, _asset_amount)

    # Update all-time assets withdrawn for yield tracking.
    self.total_assets_withdrawn += _asset_amount

    # TODO: emit Withdrawl event!

    return shares

@external
def withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256: return self._withdraw(_asset_amount,_receiver,_owner)

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
