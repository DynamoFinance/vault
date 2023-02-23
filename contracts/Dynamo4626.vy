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

    
@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _pools: DynArray[address, MAX_POOLS]):

    assert MAX_BALTX_DEPOSIT <= MAX_POOLS, "Invalid contract pre-conditions."

    dname = _name
    dsymbol = _symbol
    ddecimals = _decimals
    derc20asset = _erc20asset

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

    result_ok, response = raw_call(_pool, method_id("maxDeposit()"), max_outsize=32, is_static_call=True, revert_on_failure=False)
    assert (response != empty(Bytes[32])), "Doesn't appear to be an LPAdapter."

    self.dlending_pools.append(_pool)

    log PoolAdded(msg.sender, _pool)

    return True


@external 
def add_pool(_pool: address) -> bool: 
    # Is this from the owner?
    assert msg.sender == self.owner, "Only owner can add new Lending Pools."

    return self._add_pool(_pool)


@internal
@view
def _totalAssets() -> uint256:
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False

    assetQty : uint256 = ERC20(derc20asset).balanceOf(self)
    for pool in self.dlending_pools:
        if pool == empty(address): break
            
        # Shouldn't I just 'assetQty += LPAdapter(pool).totalAssets()'???
        # assetQty += LPAdapter(pool).totalAssets()
        result_ok, response = raw_call(
        pool,
        method_id("totalAssets()"),
        max_outsize=32,
        is_static_call=True,
        #is_delegate_call=True,
        revert_on_failure=False
        )
        if result_ok:
            assetQty += convert(response, uint256)
        assert result_ok, "TOTAL ASSETS REVERT!"  # TODO - remove.

    return assetQty


@external
@view
def totalAssets() -> uint256: return self._totalAssets()


@internal
@view
def _convertToShares(_asset_amount: uint256) -> uint256:
    shareQty : uint256 = self.totalSupply
    assetQty : uint256 = self._totalAssets()

    # If there aren't any shares/assets yet it's going to be 1:1.
    if shareQty == 0 : return _asset_amount
    if assetQty == 0 : return _asset_amount

    sharesPerAsset : decimal = convert(shareQty, decimal) / convert(assetQty, decimal)

    return convert(convert(_asset_amount, decimal) * sharesPerAsset, uint256)


@external
@view
def convertToShares(_asset_amount: uint256) -> uint256: return self._convertToShares(_asset_amount)


@internal
@view
def _convertToAssets(_share_amount: uint256) -> uint256:
    # return _share_amount

    shareQty : uint256 = self.totalSupply
    assetQty : uint256 = self._totalAssets()

    # If there aren't any shares yet it's going to be 1:1.
    if shareQty == 0: return _share_amount

    assetsPerShare : decimal = convert(assetQty, decimal) / convert(shareQty, decimal)

    return convert(convert(_share_amount, decimal) * assetsPerShare, uint256)


@external
@view
def convertToAssets(_share_amount: uint256) -> uint256: return self._convertToAssets(_share_amount)


@external
@view
def maxDeposit() -> uint256:
    # TODO - if deposits are disabled return 0
    # Ensure this value cannot take local asset balance over max_value(128) for _getBalanceTxs math.
    return convert(max_value(int128), uint256) - ERC20(derc20asset).balanceOf(self)


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
    assetQty : uint256 = self._convertToAssets(_share_amount)
    return self._deposit(assetQty, _receiver)


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
    assetQty: uint256 = self._convertToAssets(_share_amount)
    return self._withdraw(assetQty, _receiver, _owner)


struct BalanceTX:
    Qty: int128
    Adapter: address


@internal
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8) -> BalanceTX[MAX_POOLS]:
    # TODO: VERY INCOMPLETE

    # result : DynArray[BalanceTX, MAX_POOLS] = empty(DynArray[BalanceTX, MAX_POOLS])
    result : BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])

    # If there are no pools then nothing to do.
    if len(self.dlending_pools) == 0: return result

    current_local_asset_balance : int128 = convert(ERC20(derc20asset).balanceOf(self), int128) 

    # TODO - Just going to assume one adapter for now.
    pool : address = self.dlending_pools[0]
    delta_tx: int128 = current_local_asset_balance - convert(_target_asset_balance, int128)
    dtx: BalanceTX = BalanceTX({Qty: delta_tx, Adapter: pool})

    # result.append(dtx)
    result[0] = dtx

    return result


@internal
def _balanceAdapters( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):

    # Make sure we have enough assets to send to _receiver.
    txs: BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])
    txs = self._getBalanceTxs( _target_asset_balance, _max_txs )

    # Move the funds in/out of Lending Pools as required.
    for dtx in txs:
        if dtx.Qty > 0:
            # Move funds into the lending pool's adapter.
            assert ERC20(derc20asset).balanceOf(self) >= convert(dtx.Qty, uint256), "_balanceAdapters insufficient assets!"
            self._adapter_deposit(dtx.Adapter, convert(dtx.Qty, uint256))

        elif dtx.Qty < 0:
            # Liquidate funds from lending pool's adapter.
            qty: uint256 = convert(dtx.Qty * -1, uint256)
            self._adapter_withdraw(dtx.Adapter, qty, self)


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
    result_ok, response = raw_call(
        _adapter,
        _abi_encode(_asset_amount, method_id=method_id("deposit(uint256)")),
        max_outsize=32,
        is_delegate_call=True,
        revert_on_failure=False
        )

    # TODO - interpret response as revert msg in case this assertion fails.
    assert result_ok == True, convert(response, String[32]) #"_adapter_deposit raw_call failed"


@internal
def _adapter_withdraw(_adapter: address, _asset_amount: uint256, _withdraw_to: address):
    balbefore : uint256 = ERC20(derc20asset).balanceOf(_withdraw_to)
    response: Bytes[32] = empty(Bytes[32])
    result_ok: bool = False
    result_ok, response = raw_call(
        _adapter,
        _abi_encode(_asset_amount, _withdraw_to, method_id=method_id("withdraw(uint256,address)")),
        max_outsize=32,
        is_delegate_call=True,
        revert_on_failure=False
        )

    # TODO - interpret response as revert msg in case this assertion fails.
    assert result_ok == True, convert(response, String[32])

    balafter : uint256 = ERC20(derc20asset).balanceOf(_withdraw_to)
    assert balafter != balbefore, "NOTHING CHANGED!"
    assert balafter - balbefore == _asset_amount, "DIDN'T GET OUR ASSETS BACK!"


@internal
def _deposit(_asset_amount: uint256, _receiver: address) -> uint256:
    assert _receiver != empty(address), "Cannot send shares to zero address."

    assert _asset_amount <= ERC20(derc20asset).balanceOf(msg.sender), "4626Deposit insufficient funds."

    # MUST COMPUTE SHARES FIRST!
    shares : uint256 = self._convertToShares(_asset_amount)

    # Move assets to this contract from caller in one go.
    ERC20(derc20asset).transferFrom(msg.sender, self, _asset_amount)

    # It's our intention to move all funds into the lending pools so 
    # our target balance is zero.
    self._balanceAdapters( empty(uint256) )

    # Now mint assets to return to investor.    
    assert shares == _asset_amount, "DIFFERENT VALUES!"
    self._mint(_receiver, shares)

    #assert False, "GOT HERE!"

    result : uint256 = _asset_amount

    log Deposit(msg.sender, _receiver, _asset_amount, shares)

    return result


@external
def deposit(_asset_amount: uint256, _receiver: address) -> uint256: return self._deposit(_asset_amount, _receiver)


@internal
def _withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256:

    # How many shares does it take to get the requested asset amount?
    shares: uint256 = self._convertToShares(_asset_amount)

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

    assert ERC20(derc20asset).balanceOf(self) >= _asset_amount, "ERROR - 4626 DOESN'T HAVE ENOUGH BALANCE TO WITHDRAW!"

    # Now send assets to _receiver.
    ERC20(derc20asset).transfer(_receiver, _asset_amount)

    log Withdraw(msg.sender, _receiver, _owner, _asset_amount, shares)

    return shares

@external
def withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256: return self._withdraw(_asset_amount,_receiver,_owner)



