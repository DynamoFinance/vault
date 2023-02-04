# @version 0.3.7

from vyper.interfaces import ERC20
from interfaces.adapter import LPAdapter

# NOT YET! implements: ERC20


MAX_POOLS : constant(int128) = 5
MAX_BALTX_DEPOSIT : constant(uint8) = 2


dname: immutable(String[64])
dsymbol: immutable(String[32])
ddecimals: immutable(uint8)
derc20asset: immutable(address)

owner: address

dlending_pools : DynArray[address, MAX_POOLS]

totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


event PoolAdded:
    sender: indexed(address)
    contract_addr: indexed(address)

event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256    


@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _pools: DynArray[address, MAX_POOLS]):

    assert MAX_BALTX_DEPOSIT <= MAX_POOLS, "Invalid contract pre-conditions."

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

    log PoolAdded(msg.sender, _pool)

    return True


@external 
def add_pool(_pool: address) -> bool: 
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new Lending Pools."

    return self._add_pool(_pool)



struct BalanceTX:
    Qty: int128
    Adapter: address

@internal
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT) -> DynArray[BalanceTX, MAX_POOLS]:

    result : DynArray[BalanceTX, MAX_POOLS] = empty(DynArray[BalanceTX, MAX_POOLS])

    # If there are no pools then nothing to do.
    if len(self.dlending_pools) == 0: return result

    current_asset_balance : int128 = convert(ERC20(derc20asset).balanceOf(self), int128)

    # TODO - Just going to assume one adapter for now.
    pool : address = self.dlending_pools[0]
    delta_tx: int128 = current_asset_balance - convert(_target_asset_balance, int128)
    dtx: BalanceTX = BalanceTX({Qty: delta_tx, Adapter: pool})

    result.append(dtx)

    return result


@internal
def _mint(_share_amount: uint256, _receiver: address) -> uint256:
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


# TODO - should this external method even exist? Probably not...
@external
def mint(_share_amount: uint256, _receiver: address) -> uint256:
    assert msg.sender == self.owner, "Only owner can mint assets."
    return self._mint(_share_amount, _receiver)


@internal
def _adapter_deposit(_adapter: address, _asset_amount: uint256):
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = True # empty(bool)

    # raw_call(
    #     _adapter,
    #     concat( method_id("deposit(uint256)"), convert(_asset_amount, bytes32) ),
    #     max_outsize=0,
    #     is_delegate_call=True,
    #     revert_on_failure=True
    #     )
    assert result_ok == True, "raw_call failed"


@external
def deposit(_asset_amount: uint256, _receiver: address) -> uint256:
    assert _receiver != empty(address), "Cannot send shares to zero address."

    # Move assets to this contract from caller.
    ERC20(derc20asset).transferFrom(msg.sender, self, _asset_amount)

    # It's our intention to move all funds into the lending pools so 
    # our target balance is zero.
    txs: DynArray[BalanceTX, MAX_POOLS] = self._getBalanceTxs( empty(uint256) )

    # Move the funds in/out of Lending Pools as required.
    for dtx in txs:
        if dtx.Qty > 0:
            # Move funds into the lending pool's adapter.
            self._adapter_deposit(dtx.Adapter, convert(dtx.Qty, uint256))

        elif dtx.Qty < 0:
            # Liquidate funds from lending pool's adapter.
            qty: uint256 = convert(dtx.Qty * -1, uint256)
            pass

    # Now mint assets to return to investor.
    # TODO : Trade on a 1:1 value for now.
    self._mint(_asset_amount, _receiver)

    result : uint256 = _asset_amount

    return result










