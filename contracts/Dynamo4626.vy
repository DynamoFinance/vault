# @version 0.3.7

from vyper.interfaces import ERC20

# NOT YET! implements: ERC20


MAX_POOLS : constant(int128) = 5


lending_pools : DynArray[address, MAX_POOLS]


dname: immutable(String[64])
dsymbol: immutable(String[32])
ddecimals: immutable(uint8)
derc20asset: immutable(address)

owner: address

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

    self.owner = msg.sender
    self.totalSupply = 0

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


# @internal 
# def _add_pool(_pool: address) -> bool:    
#     # Do we already support this pool?
#     assert (_pool in self.lending_pools) == False, "pool already supported."

#     # Is this likely to be an ERC-20 token contract?
#     response: Bytes[32] = empty(Bytes[32])
#     result_ok: bool = empty(bool)

#     result_ok, response = raw_call(_pool, method_id("totalSupply()"), max_outsize=32, is_static_call=True, gas = 100000, revert_on_failure=False)
#     assert (response != empty(Bytes[32])), "Doesn't appear to be an ERC-20."

#     #assert ERC20(_pool).totalSupply() > 0, "Doesn't appear to be an ERC-20."

#     #return True

#     #self.supported_currencies.append(_pool)

#     #log poolAdded(msg.sender, _pool)

#     return True


# @external 
# def add_pool(_pool: address) -> bool: 
#     # Is this from the owner?
#     assert msg.sender == self.owner, "Only owner can add new currencies."

#     return self._add_pool(_pool)











