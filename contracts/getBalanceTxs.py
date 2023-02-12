from dataclasses import dataclass


MAX_POOLS = 5


@dataclass
class PoolAdapter:
    pass

@dataclass
class BalanceTX:
    Qty: int
    Adapter: PoolAdapter


@dataclass
class ERC20:
    balanceOf: dict


@dataclass
class Pool:
    dlending_pools : list[PoolAdapter] 
    derc20asset : ERC20


    def getBalanceTxs( self, _target_asset_balance: int, _max_txs: int) -> list[BalanceTX]:
        # TODO: VERY INCOMPLETE

        # result : DynArray[BalanceTX, MAX_POOLS] = empty(DynArray[BalanceTX, MAX_POOLS])
        result : BalanceTX[MAX_POOLS] = list[BalanceTX]

        # If there are no pools then nothing to do.
        if len(self.dlending_pools) == 0: return result

        current_local_asset_balance : int = self.derc20asset.balanceOf[self]

        # TODO - Just going to assume one adapter for now.
        pool : PoolAdapter = self.dlending_pools[0]
        delta_tx: int = current_local_asset_balance - _target_asset_balance
        dtx: BalanceTX = BalanceTX(Qty= delta_tx, Adapter= pool)

        # result.append(dtx)
        result[0] = dtx

        return result


d = {}
dai = ERC20(balanceOf = d)

adapters = [PoolAdapter()]

p = Pool(adapters, dai)
result = p.getBalanceTxs(0, 5)


