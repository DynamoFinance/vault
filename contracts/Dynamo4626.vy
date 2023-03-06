# @version 0.3.7

from vyper.interfaces import ERC20
#from interfaces.adapter import LPAdapter
import LPAdapter as LPAdapter
# NOT YET! implements: ERC20


MAX_POOLS : constant(int128) = 5
MAX_BALTX_DEPOSIT : constant(uint8) = 2

YIELD_FEE_PERCENTAGE : constant(decimal) = 10.0


name: public(immutable(String[64]))
symbol: public(immutable(String[32]))
decimals: public(immutable(uint8))
asset: public(immutable(address))

total_assets_deposited: public(uint256)
total_assets_withdrawn: public(uint256)
total_fees_claimed: public(uint256)


owner: address
governance: address

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


@external
def __init__(_name: String[64], _symbol: String[32], _decimals: uint8, _erc20asset : address, _pools: DynArray[address, MAX_POOLS], _governance: address):

    assert MAX_BALTX_DEPOSIT <= MAX_POOLS, "Invalid contract pre-conditions."
    assert _governance != empty(address), "Governance cannot be null address."

    name = _name
    symbol = _symbol
    decimals = _decimals
    asset = _erc20asset


    self.owner = msg.sender
    self.governance = _governance
    self.totalSupply = 0

    for pool in _pools:
        self._add_pool(pool)        


@external
def replaceGovernanceContract(_new_governance: address) -> bool:
    assert msg.sender == self.governance, "Only existing Governance contract may replace itself."
    assert _new_governance != empty(address), "Governance cannot be null address."

    self.governance = _new_governance    
    return True


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

    # Shouldn't I just 'assetQty += LPAdapter(pool).totalAssets()'???
    # assetQty += LPAdapter(pool).totalAssets()
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
    assetQty : uint256 = ERC20(asset).balanceOf(self)
    for pool in self.dlending_pools:
        if pool == empty(address): break
        assetQty += self._poolAssets(pool)

    return assetQty


@external
@view
def totalAssets() -> uint256: return self._totalAssets()


@internal
@view 
def _totalReturns(_current_assets : uint256 = 0) -> int256:
    # Avoid having to call _totalAssets if we already know the value.
    current_holdings : uint256 = _current_assets
    if current_holdings == 0:
        current_holdings = self._totalAssets()

    total_returns: int256 = convert(self.total_assets_withdrawn + current_holdings, int256) - convert(self.total_assets_deposited, int256)
    return total_returns    


@internal
@view 
def _claimable_fees_available(_current_assets : uint256 = 0) -> uint256:
    total_returns : int256 = self._totalReturns(_current_assets)
    if total_returns < 0: return 0

    dtotal_fees_available : decimal = convert(total_returns, decimal) * (YIELD_FEE_PERCENTAGE / 100.0)
    total_fees_remaining : uint256 = convert(dtotal_fees_available, uint256) - self.total_fees_claimed

    return total_fees_remaining


@external
def claim(_asset_amount: uint256) -> bool:
    assert msg.sender == self.owner, "Only owner may claim fees."

    total_fees_remaining : uint256 = self._claimable_fees_available()

    # Do we have _asset_amount of fees available to claim?
    if total_fees_remaining < _asset_amount: return False

    # Good claim. Do we have the balance locally?
    if ERC20(asset).balanceOf(self) < _asset_amount:

        # Need to liquidate some shares to fulfill 
        self._balanceAdapters(_asset_amount)

    # Account for the claim and move the funds.
    self.total_fees_claimed += _asset_amount
    ERC20(asset).transfer(self.owner, _asset_amount)

    return True


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
    total_assets : uint256 = self._totalAssets()
    assetQty : uint256 = total_assets - self._claimable_fees_available(total_assets)

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
    Qty: int256
    Adapter: address


@internal
def _getBalanceTxs( _target_asset_balance: uint256, _max_txs: uint8) -> BalanceTX[MAX_POOLS]: # DynArray[BalanceTX, MAX_POOLS]:
    # result : DynArray[BalanceTX, MAX_POOLS] = empty(DynArray[BalanceTX, MAX_POOLS])
    result : BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])

    # If there are no pools then nothing to do.
    if len(self.dlending_pools) == 0: return result

    current_local_asset_balance : uint256 = ERC20(asset).balanceOf(self) 

    # TODO - New stuff starts here!
    total_balance : uint256 = current_local_asset_balance
    total_shares : uint256 = 0 

    # Determine current balances.
    currentBalances : uint256[MAX_POOLS] = empty(uint256[MAX_POOLS])    
    pos: uint256 = 0
    for pool in self.dlending_pools:
        poolBalance : uint256 = self._poolAssets(pool)
        total_balance += poolBalance
        total_shares += self.strategy[pool]
        currentBalances[pos] = poolBalance
        pos += 1

    # Is there any strategy to deal with?
    if total_shares == 0: return result        

    available_balance : int256 = convert(total_balance, int256) - convert(_target_asset_balance, int256)

    # Determine target balances.
    targetBalances : uint256[MAX_POOLS] = empty(uint256[MAX_POOLS])    
    deltaBalances : int256[MAX_POOLS] = empty(int256[MAX_POOLS])    
    pos = 0
    for pool in self.dlending_pools:
        share_ratio : decimal = convert(self.strategy[pool], decimal) / convert(total_shares, decimal)
        targetBalances[pos] = convert(convert(available_balance, decimal) * share_ratio, uint256)
        deltaBalances[pos] = convert(targetBalances[pos],int256) - convert(currentBalances[pos], int256)

    # How far off are we from our target asset balance?
    deltaTarget : int256 = convert(current_local_asset_balance, int256) - convert(_target_asset_balance, int256)

    # Prioritize and allocate transactions.    
    pos = 0
    for pool in self.dlending_pools:
        # Is the 4626 pool short on its requirements?
        if deltaTarget < 0:
            lowest : int256 = 0
            lowest_pos : uint256 = 0 

            # Find the tx that will bring the most money into the 4626 pool.
            i : uint256 = 0
            for ip in self.dlending_pools:                
                low_candidate : int256 = deltaBalances[pos]
                if low_candidate < lowest:
                    lowest = low_candidate
                    lowest_pos = pos 
                i+=1
            result[pos] = BalanceTX({Qty: lowest, Adapter:self.dlending_pools[lowest_pos]})
            deltaBalances[lowest_pos] = 0
            deltaTarget -= lowest                        
        else:
            # Prioritize the tx that will have the highest impact on the balances.
            largest : int256 = 0
            largest_pos : uint256 = 0

            i : uint256 = 0
            for ip in self.dlending_pools: 
                if abs(deltaBalances[i]) > abs(largest):
                    # Ensure we don't let our 4626 pool fall short of its requirements.
                    if deltaTarget + deltaBalances[i] < 0: continue
                    largest = deltaBalances[i]
                    largest_pos = i
                i+=1
            result[pos] = BalanceTX({Qty: largest, Adapter:self.dlending_pools[largest_pos]})
            deltaBalances[largest_pos] = 0
            deltaTarget += largest
            
        pos += 1

    # Make sure we meet our _target_asset_balance goal within _max_txs steps!
    assert current_local_asset_balance <= max_value(int128) and convert(current_local_asset_balance, int256) >= min_value(int128), "BUSTED!" # TODO remove
    running_balance : int256 = convert(current_local_asset_balance, int256)
    for btx in result:        
        if btx.Qty == 0: break
        running_balance += btx.Qty


    if running_balance < convert(_target_asset_balance, int256):
        diff : int256 = convert(_target_asset_balance, int256) - running_balance
        pos = 0
        for btx in result:
            # Is there enough in the Adapter to satisfy our deficit?
            available_funds : int256 = convert(self._poolAssets(btx.Adapter), int256) + btx.Qty
            # TODO : Consider also checking that we aren't over the Adapter's maxWithdraw limit here.
            if available_funds >= diff:
                btx.Qty-= diff
                diff = 0 
                break
            elif available_funds > 0:
                btx.Qty-=available_funds
                diff+=available_funds

        # TODO - remove this after testing.
        assert diff <= 0, "CAN'T BALANCE SOON ENOUGH!"

    # Now make sure we aren't asking for more txs than allowed.
    # Wipe out any extras.
    pos = 0
    for btx in result:
        if btx.Qty != 0: pos+=1
        if convert(_max_txs, uint256) < pos and btx.Qty != 0:
            btx.Qty = 0




    # # TODO - Just going to assume one adapter for now.
    # pool : address = self.dlending_pools[0]
    # delta_tx: int256 = convert(current_local_asset_balance, int256) - convert(_target_asset_balance, int256)
    # dtx: BalanceTX = BalanceTX({Qty: delta_tx, Adapter: pool})

    # # result.append(dtx)
    # result[0] = dtx

    return result


@internal
def _balanceAdapters( _target_asset_balance: uint256, _max_txs: uint8 = MAX_BALTX_DEPOSIT ):

    # Make sure we have enough assets to send to _receiver.
    # txs: DynArray[BalanceTX, MAX_POOLS] = empty(DynArray[BalanceTX, MAX_POOLS])
    txs: BalanceTX[MAX_POOLS] = empty(BalanceTX[MAX_POOLS])
    txs = self._getBalanceTxs( _target_asset_balance, _max_txs )

    # Move the funds in/out of Lending Pools as required.
    for dtx in txs:
        if dtx.Qty > 0:
            # Move funds into the lending pool's adapter.
            assert ERC20(asset).balanceOf(self) >= convert(dtx.Qty, uint256), "_balanceAdapters insufficient assets!"
            # TODO : check for deposit failure. If it's due to going beyond
            #        the adapter's maxDeposit() limit, try again with lower limit.
            self._adapter_deposit(dtx.Adapter, convert(dtx.Qty, uint256))

        elif dtx.Qty < 0:
            # Liquidate funds from lending pool's adapter.
            qty: uint256 = convert(dtx.Qty * -1, uint256)
            # TODO : check for withdraw failure. If it's due to going beyond
            #        the adapter's maxWithdraw limit then try again with lower limit.
            # TODO:  We also have to check to see if we short the 4626 balance, where
            #        the necessary funds will come from! Otherwise this may need to revert.
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
    balbefore : uint256 = ERC20(asset).balanceOf(_withdraw_to)
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

    # It's our intention to move all funds into the lending pools so 
    # our target balance is zero.
    self._balanceAdapters( empty(uint256) )

    # Now mint assets to return to investor.    
    assert shares == _asset_amount, "DIFFERENT VALUES!"
    self._mint(_receiver, shares)

    #assert False, "GOT HERE!"

    # Update all-time assets deposited for yield tracking.
    self.total_assets_deposited += _asset_amount

    result : uint256 = _asset_amount

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

    assert ERC20(asset).balanceOf(self) >= _asset_amount, "ERROR - 4626 DOESN'T HAVE ENOUGH BALANCE TO WITHDRAW!"

    # Now send assets to _receiver.
    ERC20(asset).transfer(_receiver, _asset_amount)

    # Update all-time assets withdrawn for yield tracking.
    self.total_assets_withdrawn += _asset_amount

    return shares

@external
def withdraw(_asset_amount: uint256,_receiver: address,_owner: address) -> uint256: return self._withdraw(_asset_amount,_receiver,_owner)



