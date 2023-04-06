# @version 0.3.7
"""
@title Adapter Fund Allocation Logic
@license MIT
@author BiggestLab
"""
##
## Must match Dynamo4626.vy
##

MAX_POOLS : constant(uint256) = 5 

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


@internal
@pure
def _getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_balances: BalancePool[MAX_POOLS], _min_outgoing_tx: uint256) -> (uint256, int256, uint256, BalancePool[MAX_POOLS], address[MAX_POOLS]):
    # WHAT IF THE _d4626_asset_target is larger than the total assets?!?!?
    assert _d4626_asset_target <= _total_assets, "Not enough assets to fulfill d4626 target goals!"

    total_pool_target_assets : uint256 = _total_assets - _d4626_asset_target

    pool_assets_allocated : uint256 = 0 
    d4626_delta : int256 = 0
    tx_count: uint256 = 0

    # We have to copy from the old list into a new one to update values. (NOT THE MOST EFFICIENT OPTION.)
    pools : BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])
    blocked_adapters : address[MAX_POOLS] = empty(address[MAX_POOLS])
    blocked_pos : uint256 = 0

    # Any funds that should have been moved into an LPAdapter but weren't due to invalid txs.
    leftover_assets : int256 = 0

    for pos in range(MAX_POOLS):
        pool : BalancePool = _pool_balances[pos]
        if pool.adapter == empty(address): break

        # If the pool has been removed from the strategy then we must empty it!
        if pool.ratio == 0:
            pool.target = 0
            pool.delta = convert(pool.current, int256) * -1 # Withdraw it all!
        else:
            pool.target = (total_pool_target_assets * pool.ratio) / _total_ratios      
            pool.delta = convert(pool.target, int256) - convert(pool.current, int256)            

            # Check for valid outgoing txs here.
            if pool.delta > 0:
                # Is an outgoing tx > min size?
                if pool.delta < convert(_min_outgoing_tx, int256): 
                    leftover_assets += pool.delta
                    pool.delta = 0
                # Is the LP possibly compromised for an outgoing tx?
                if pool.current < pool.last_value:
                    # We've lost value in this adapter! Don't give it more money!
                    leftover_assets += pool.delta
                    blocked_adapters[blocked_pos] = pool.adapter
                    blocked_pos += 1
                    pool.delta = 0 # This will result in no tx being generated.

        pool_result : int256 = convert(pool.current, int256) + pool.delta
        assert pool_result >= 0, "Pool resulting balance can't be less than zero!"
        pool_assets_allocated += convert(pool_result, uint256)


        d4626_delta += pool.delta * -1
        #if pool.delta != 0: tx_count += 1
        # Don't insert a tx if there's nothing to transfer.
        if pool.delta == 0: continue

        tx_count += 1

        if pos == 0:
            pools[pos]=pool
        else:
            for npos in range(MAX_POOLS):
                if pools[npos].delta == 0:  # Empty position, take it.
                    pools[npos] = pool
                    break
                if pools[npos].delta > pool.delta: # Move everything right and insert here.
                    for mpos in range(MAX_POOLS):
                        next_pos : uint256 = MAX_POOLS - npos - 1 
                        if pools[next_pos].delta == 0: continue
                        pools[next_pos+1] = pools[next_pos]

                    pools[npos] = pool
                    break

    # Check to make sure we hit our _d4626_asset_target in the end!
    return pool_assets_allocated, d4626_delta, tx_count, pools, blocked_adapters


@external
@pure
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
    return self._getTargetBalances(_d4626_asset_target, _total_assets, _total_ratios, _pool_balances, _min_outgoing_tx)


@internal
@pure
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_states: BalancePool[MAX_POOLS]) -> (BalanceTX[MAX_POOLS], address[MAX_POOLS]): 
    # _BDM TODO : max_txs is ignored for now.    
    pool_txs : BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])
    blocked_adapters : address[MAX_POOLS] = empty(address[MAX_POOLS])
    pool_states: BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])
    pool_assets_allocated : uint256 = 0
    d4626_delta : int256 = 0
    tx_count : uint256 = 0

    pool_assets_allocated, d4626_delta, tx_count, pool_states, blocked_adapters = self._getTargetBalances(_target_asset_balance, _total_assets, _total_ratios, _pool_states, _min_proposer_payout)

    pos : uint256 = 0
    for tx_bal in pool_states:
        pool_txs[pos] = BalanceTX({qty: tx_bal.delta, adapter: tx_bal.adapter})
        pos += 1

    return pool_txs, blocked_adapters


@external
@view
def getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8, _min_proposer_payout: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_states: BalancePool[MAX_POOLS]) -> (BalanceTX[MAX_POOLS], address[MAX_POOLS]):  
    return self._getBalanceTxs( _target_asset_balance, _max_txs, _min_proposer_payout, _total_assets, _total_ratios, _pool_states )
