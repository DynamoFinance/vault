# @version 0.3.6




event StrategyWithdrawal:
    Nonce: uint256

event StrategyVote:
    Nonce: uint256
    GuardAddress: indexed(address)
    Endorse: bool

event StrategyActivation:
    Strategy: uint256

event NewGuard:
    GuardAddress: indexed(address)

event GuardRemoved:
    GuardAddress: indexed(address)

event GuardSwap:
    OldGuardAddress: indexed(address)
    NewGuardAddress: indexed(address)

struct ProposedStrategy:
    Weights: DynArray[uint256, MAX_POOLS]
    APYNow: uint256
    APYPredicted: uint256

struct Strategy:
    Nonce: uint256
    ProposerAddress: address
    Weights: DynArray[uint256, MAX_POOLS]
    APYNow: uint256
    APYPredicted: uint256
    TSubmitted: uint256
    TActivated: uint256
    Withdrawn: bool
    no_guards: uint256
    VotesEndorse: DynArray[address, MAX_GUARDS]
    VotesReject: DynArray[address, MAX_GUARDS]

event StrategyProposal:
    strategy: Strategy
    
# Contract assigned storage 
contractOwner: public(address)
MAX_GUARDS: constant(uint256) = 10
MAX_POOLS: constant(uint256) = 10
LGov: public(DynArray[address, MAX_GUARDS])
TDelay: public(uint256)
no_guards: public(uint256)
guard_index: public(HashMap[address, uint256])
CurrentStrategy: public(Strategy)
PendingStrategy: public(Strategy)
PendingVotesEndorse: public(uint256)
PendingStrategy_TSubmitted: public(uint256)
PendingStrategy_Nonce: public(uint256)
CurrentStrategy_Nonce: public(uint256)
PendingStrategy_Withdrawn: bool
MinimumAPYIncrease: public(uint256)

NextNonce: uint256



@external
def __init__(contractOwner: address):
    self.contractOwner = contractOwner
    self.NextNonce = 1


@external
def submitStrategy(strategy: ProposedStrategy) -> uint256:
    # No Strategy proposals if no governance guards
    assert len(self.LGov) >= 0, "Cannot Submit Strategy without Guards"

    # Confirm there's no currently pending strategy so we can replace the old one.

            # First is it the same as the current one?
            # Otherwise has it been withdrawn? 
            # Otherwise, has it been short circuited down voted? 
            # Has the period of protection from being replaced expired already?         
    assert  (self.CurrentStrategy.Nonce == self.PendingStrategy.Nonce) or \
            (self.PendingStrategy_Withdrawn == True) or \
            (len(self.PendingStrategy.VotesReject) >= self.PendingStrategy.no_guards/2) or \
            ((convert(self.PendingStrategy.TSubmitted, decimal)+(convert(self.TDelay, decimal) * 1.25)) > convert(block.timestamp, decimal)), "Cannot Submit Strategy"

    # Confirm msg.sender Eligibility
    # Confirm msg.sender is not blacklisted

    # Confirm strategy meets financial goal improvements.
    assert strategy.APYPredicted - strategy.APYNow >= self.MinimumAPYIncrease, "Cannot Submit Strategy without APY Increase"

    
    self.PendingStrategy_Nonce = self.NextNonce
    self.NextNonce += 1
    self.PendingStrategy.ProposerAddress = msg.sender
    self.PendingStrategy.Weights = strategy.Weights
    self.PendingStrategy.APYNow = strategy.APYNow
    self.PendingStrategy.APYPredicted = strategy.APYPredicted
    self.PendingStrategy.TSubmitted = block.timestamp
    self.PendingStrategy.TActivated = 0    
    self.PendingStrategy.Withdrawn = False
    self.PendingStrategy.no_guards = len(self.LGov)
    self.PendingStrategy.VotesEndorse = empty(DynArray[address, MAX_GUARDS])
    self.PendingStrategy.VotesReject = empty(DynArray[address, MAX_GUARDS])


    log StrategyProposal(self.PendingStrategy)
    return self.PendingStrategy_Nonce


@external
def withdrawStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce
    assert self.PendingStrategy_Nonce == Nonce
    # assert self.PendingStrategy.ProposerAddress == msg.sender
    self.PendingStrategy_Withdrawn = True
    log StrategyWithdrawal(Nonce)


@external
def endorseStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce
    assert self.PendingStrategy_Nonce == Nonce
    # assert msg.sender is in self.LGov
    # assert msg.sender is not in self.PendingStrategy.VoteReject
    # assert msg.sender is not in self.PendingStrategy.VoteEndorse
    # self.PendingStrategy.VoteEndorse.append(msg.sender)
    log StrategyVote(Nonce, msg.sender, False)



@external
def rejectStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce
    assert self.PendingStrategy_Nonce == Nonce
    # assert msg.sender is in self.LGov
    # assert msg.sender is not in self.PendingStrategy.VoteReject
    # assert msg.sender is not in self.PendingStrategy.VoteEndorse
    # self.PendingStrategy.VoteReject.append(msg.sender)
    log StrategyVote(Nonce, msg.sender, True)



@external
def activateStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce
    assert self.PendingStrategy_Withdrawn == False
    assert self.PendingVotesEndorse >= len(self.LGov)/2 
    # assert (self.PendingStrategy_TSubmitted + self.TDelay) <= now() 
    # assert count(self.PendingStrategy.VotesReject) <= count(self.PendingStrategy.VotesEndorsed)
    assert self.PendingStrategy_Nonce == Nonce
    self.CurrentStrategy = self.PendingStrategy
    #PoolRebalancer(self.CurrentStrategy)
    log StrategyActivation(Nonce)

 


@external
def addGuard(GuardAddress: address):
    assert msg.sender == self.contractOwner, "Cannot add guard unless you are contract owner"
    #GuardAddress is not in self.LGov
    no_guards: uint256 = len(self.LGov)
    # next_pos: uint256 = no_guards - 1
    assert no_guards <= MAX_GUARDS, "Cannot add anymore guards"
    assert GuardAddress != ZERO_ADDRESS, "Cannot add ZERO_ADDRESS"
    self.LGov.append(GuardAddress)
    # self.guard_index[GuardAddress] = next_pos
    log NewGuard(GuardAddress)



@external
def removeGuard(GuardAddress: address):
    assert msg.sender == self.contractOwner
    #GuardAddress is in self.LGov
    current_index: uint256 = self.guard_index[GuardAddress]
    no_guards: uint256 = len(self.LGov)
    #What i want to do is delete the current_index and then replace in with the last in the guard_index.
    #Then swap the GuardAddress i want to remove with the last address in LGov.
    #Reason being that pop will only remove the last address
    self.LGov.pop()
    log GuardRemoved(GuardAddress)




@external
def swapGuard(OldGuardAddress: address, NewGuardAddress: address):
    assert msg.sender == self.contractOwner
    #OldGuardAddress is in self.LGov
    #NewGuardAddress is not in self.LGov
    assert NewGuardAddress != ZERO_ADDRESS
    current_index: uint256 = self.guard_index[OldGuardAddress]
    #What i want to do is replace OldGuardAddress_Index with NewGuardAddress_Index in guard_index.
    #Then i want to replace OldGuardAddress with NewGuardAddress in LGov.
    self.LGov.pop()
    self.LGov.append(NewGuardAddress)
    log GuardSwap(OldGuardAddress, NewGuardAddress)

