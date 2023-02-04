# @version 0.3.7

from vyper.interfaces import ERC20

# NOT YET! implements: ERC20


MAX_POOLS : constant(int128) = 5

dname: immutable(String[64])
dsymbol: immutable(String[32])
ddecimals: immutable(uint8)
derc20asset: immutable(address)

owner: address

dlending_pools : DynArray[address, MAX_POOLS]

totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


event poolAdded:
    sender: indexed(address)
    contract_addr: indexed(address)


@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _pools: DynArray[address, MAX_POOLS]):
    dname = _name
    dsymbol = _symbol
    ddecimals = _decimals
    derc20asset = _erc20asset

    # VYPER NOTE - if we don't explicitly initialize dlending_pools here
    #              the ctor will initialize it to empty AFTER the
    #              _add_pool() loop completes and erase the passed in pools!
    self.dlending_pools = empty(DynArray[address, MAX_POOLS])

    self.owner = msg.sender
    self.totalSupply = 0

    for pool in _pools:
        self._add_pool(pool)


@pure
@external
def name() -> String[64]: return dname

@pure
@external
def symbol() -> String[32]: return dsymbol

@pure
@external
def decimals() -> uint8: return ddecimals

@pure
@external
def asset() -> address: return derc20asset

# Can't simply have a public lending_pools variable due to this Vyper issue:
# https://github.com/vyperlang/vyper/issues/2897
@view
@external
def lending_pools() -> DynArray[address, MAX_POOLS]: return self.dlending_pools


@internal 
def _add_pool(_pool: address) -> bool:    
    # Do we already support this pool?
    assert (_pool in self.dlending_pools) == False, "pool already supported."

    # Is this likely to be an actual LPAdapter contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)

    result_ok, response = raw_call(_pool, method_id("maxDepositable()"), max_outsize=32, is_static_call=True, revert_on_failure=False)
    assert (response != empty(Bytes[32])), "Doesn't appear to be an LPAdapter."

    self.dlending_pools.append(_pool)

    log poolAdded(msg.sender, _pool)

    return True


@external 
def add_pool(_pool: address) -> bool: 
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new Lending Pools."

    return self._add_pool(_pool)











