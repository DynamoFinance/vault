# @version 0.3.6


event StrategyProposal:
    Strategy: address

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


    
#Contract assigned storage 
contractOwner: public(address)
MAX_GUARDS: constant(uint256) = 10
MAX_POOLS: constant(uint256) = 10
LGov: public(DynArray[address, MAX_GUARDS])
TDelay: public(uint256)
no_guards: public(uint256)
guard_index: public(HashMap[address, uint256])
CurrentStrategy: public(uint256)
PendingStrategy: public(uint256)
PendingVotesEndorse: public(uint256)
PendingStrategy_TSubmitted: public(uint256)
PendingStrategy_Nonce: public(uint256)
PendingStrategy_Withdrawn: bool

struct Strategy:
    Nonce: uint256
    ProposerAddress: address
    Weights: uint256
    TSubmitted: uint256
    TActivated: uint256
    Withdrawn: String[256]
    no_guards: uint256
    VotesEndorse: uint256
    VotesReject: uint256

@external
def __init__(contractOwner: address):
    self.contractOwner = contractOwner


# @external
# def submitStrategy(Strategy: struct):
#     assert len(self.LGov) >= 0
#     assert self.CurrentStrategy == self.PendingStrategy
#     assert self.PendingStrategy.Withdrawn == True
#     assert count(self.PendingVotesReject) >= len(self.LGov)/2
#     assert (self.PendingStrategy.TSubmitted+(self.TDelay * 1.25)) <= now()
#     assert count(self.PendingStrategy.VotesReject) >= count(self.PendingStrategy.VotesEndorsed)
#     #Confirm msg.sender Eligibility
#     #Confirm msg.sender is not blacklisted
#     assert Strategy.APYPredicted - Strategy.APYNow >= self.MinimumAPYIncrease
#     #Strategy={*Strategy,TSubmitted,TActive,Nonce,Withdrawn=False,VoterCount,VotesEndorse=[],VotesReject=[]}
#     self.PendingStrategy = Strategy
#     log StrategyProposal(Strategy)
#     return self.PendingStrategy.Nonce


@external
def withdrawStrategy(Nonce: uint256):
    assert self.CurrentStrategy != self.PendingStrategy
    assert self.PendingStrategy_Nonce == Nonce
    # assert self.PendingStrategy.ProposerAddress == msg.sender
    self.PendingStrategy_Withdrawn = True
    log StrategyWithdrawal(Nonce)


@external
def endorseStrategy(Nonce: uint256):
    assert self.CurrentStrategy != self.PendingStrategy
    assert self.PendingStrategy_Nonce == Nonce
    # assert msg.sender is in self.LGov
    # assert msg.sender is not in self.PendingStrategy.VoteReject
    # assert msg.sender is not in self.PendingStrategy.VoteEndorse
    # self.PendingStrategy.VoteEndorse.append(msg.sender)
    log StrategyVote(Nonce, msg.sender, False)



@external
def rejectStrategy(Nonce: uint256):
    assert self.CurrentStrategy != self.PendingStrategy
    assert self.PendingStrategy_Nonce == Nonce
    # assert msg.sender is in self.LGov
    # assert msg.sender is not in self.PendingStrategy.VoteReject
    # assert msg.sender is not in self.PendingStrategy.VoteEndorse
    # self.PendingStrategy.VoteReject.append(msg.sender)
    log StrategyVote(Nonce, msg.sender, True)



@external
def activateStrategy(Nonce: uint256):
    assert self.CurrentStrategy != self.PendingStrategy
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
    assert msg.sender == self.contractOwner
    #GuardAddress is not in self.LGov
    no_guards: uint256 = len(self.LGov)
    next_pos: uint256 = no_guards - 1
    assert no_guards <= MAX_GUARDS
    assert GuardAddress != ZERO_ADDRESS
    self.LGov.append(GuardAddress)
    self.guard_index[GuardAddress] = next_pos
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

