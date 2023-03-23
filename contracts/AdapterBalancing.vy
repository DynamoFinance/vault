# @version 0.3.7

MAX_POOLS : constant(int128) = 5
owner: address
dynamoVault: address
dlending_pools : DynArray[address, MAX_POOLS]

struct BalanceTX:
    qty: int256
    adapter: address

struct BalancePool:
    adapter: address
    current: uint256
    ratio: uint256
    target: uint256
    delta: int256

interface Dynamo4626:
    def getCurrentBalances() -> (uint256, BalancePool[MAX_POOLS], uint256, uint256): view



@external
def __init__(_contractOwner: address):

    self.owner = _contractOwner


@external
def addDynamoVault(_dynamoVault: address):

    self.dynamoVault = _dynamoVault


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
def getTargetBalances(_d4626_asset_target: uint256, _total_assets: uint256, _total_ratios: uint256, _pool_balances: BalancePool[MAX_POOLS]) -> (uint256, int256, uint256, BalancePool[MAX_POOLS]): 
    return self._getTargetBalances(_d4626_asset_target, _total_assets, _total_ratios, _pool_balances)


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
    d4626_assets, pool_states, total_assets, total_ratios = Dynamo4626(self.dynamoVault).getCurrentBalances()

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


