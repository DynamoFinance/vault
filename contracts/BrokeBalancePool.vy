# @version 0.3.7

MAX_POOLS : constant(int128) = 5

struct BalancePool:
    adapter: address
    current: uint256
    ratio: uint256
    target: uint256
    delta: int256
    last_value: uint256  # Remark this out and it works!

@external
@view 
# Only fails when returning with stuff
def getBrokeBalancePoolsWithStuff() -> ( uint256, BalancePool[MAX_POOLS]):
    result : BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])
    return 0, result
    
@external
@view 
# This breaks here but actually works in my larger code base!
def getBrokeBalancePools() -> ( BalancePool[MAX_POOLS]):
    result : BalancePool[MAX_POOLS] = empty(BalancePool[MAX_POOLS])
    return result
    