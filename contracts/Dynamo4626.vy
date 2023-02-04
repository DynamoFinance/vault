# @version 0.3.7

from vyper.interfaces import ERC20

# NOT YET! implements: ERC20


MAX_CURRENCY_TYPES : constant(int128) = 3
MAX_POOLS : constant(int128) = 5


supported_currencies : DynArray[address, MAX_CURRENCY_TYPES]
lending_pools : DynArray[address, MAX_POOLS]


name: immutable(String[64])
symbol: immutable(String[32])
decimals: immutable(uint8)

owner: address

totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


event CurrencyAdded:
    sender: indexed(address)
    contract_addr: indexed(address)



@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _currencies : DynArray[address, MAX_CURRENCY_TYPES], _pools: DynArray[address, MAX_POOLS]):
    name = _name
    symbol = _symbol
    decimals = _decimals

    self.owner = msg.sender
    self.totalSupply = 0

    for currency in _currencies:
        self._add_currency(currency)


@internal 
def _add_currency(_currency: address) -> bool:    
    # Do we already support this currency?
    assert (_currency in self.supported_currencies) == False, "Currency already supported."

    # Is this likely to be an ERC-20 token contract?
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = empty(bool)

    result_ok, response = raw_call(_currency, method_id("totalSupply"), max_outsize=32, is_static_call=True, revert_on_failure=False)
    assert (response != empty(Bytes[32])), "Doesn't appear to be an ERC-20."

    self.supported_currencies.append(_currency)

    log CurrencyAdded(msg.sender, _currency)

    return True


@external 
def add_currency(_currency: address) -> bool: 
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new currencies."

    return self._add_currency(_currency)










