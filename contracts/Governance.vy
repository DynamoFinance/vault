# @version 0.3.6

event StrategyProposal:
    Strategy: address

event StrategyWithdrawal:
    Nonce: uint256

event StrategyVote:
    Nonce: uint256
    GuardAddress: indexed(address)
    Endorse: String[256]

event StrategyActivation:
    Strategy: address

event NewGuard:
    GuardAddress: indexed(address)

event GuardRemoved:
    GuardAddress: indexed(address)

event GuardSwap:
    OldGuardAddress: indexed(address)
    NewGuardAddress: indexed(address)

struct Guard:
    GuardAddress: address
    Index: uint256


#Contract assigned storage 
contractOwner: public(address)
MAX_GUARDS: constant(uint256) = 10
MAX_POOLS: constant(uint256) = 10
LGov: public(HashMap[address, uint256]
TDelay: public(uint256)

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

# @external
# def withdrawStrategy(Nonce: uint256):
#     assert self.CurrentStrategy != self.PendingStrategy
#     assert self.PendingStrategy.Nonce == Nonce
#     assert self.PendingStrategy.ProposerAddress == msg.sender
#     self.PendingStrategy.Withdrawn = True
#     log StrategyWithdrawal(Nonce)
#     return True

# @external
# def endorseStrategy(Nonce: uint256):
#     assert self.CurrentStrategy != self.PendingStrategy
#     assert self.PendingStrategy.Nonce == Nonce
#     assert msg.sender is in self.LGov
#     assert msg.sender is not in self.PendingStrategy.VoteReject
#     assert msg.sender is not in self.PendingStrategy.VoteEndorse
#     self.PendingStrategy.VoteEndorse.append(msg.sender)
#     log StrategyVote(Nonce, msg.sender, False)
#     return True


# @external
# def rejectStrategy(Nonce: uint256):
#     assert self.CurrentStrategy != self.PendingStrategy
#     assert self.PendingStrategy.Nonce == Nonce
#     assert msg.sender is in self.LGov
#     assert msg.sender is not in self.PendingStrategy.VoteReject
#     assert msg.sender is not in self.PendingStrategy.VoteEndorse
#     self.PendingStrategy.VoteReject.append(msg.sender)
#     log StrategyVote(Nonce, msg.sender, True)
#     return True


# @external
# def activateStrategy(Nonce: uint256):
#     assert self.CurrentStrategy != self.PendingStrategy
#     assert self.PendingStrategy.Withdrawn == False
#     assert count(self.PendingVotesEndorse) >= len(self.LGov)/2 
#     assert (self.PendingStrategy.TSubmitted + self.TDelay) <= now() 
#     assert count(self.PendingStrategy.VotesReject) <= count(self.PendingStrategy.VotesEndorsed)
#     assert self.PendingStrategy.Nonce == Nonce
#     self.CurrentStrategy = self.PendingStrategy
#     #PoolRebalancer(self.CurrentStrategy)
#     log StrategyActivation(self.CurrentStrategy)
#     return True



@external
def addGuard(GuardAddress: address):
    assert msg.sender == self.contractOwner
    #GuardAddress is not in self.LGov
    assert len(self.LGov) <= self.MAX_GUARDS
    assert GuardAddress != ZERO_ADDRESS
    self.LGov.append(GuardAddress)
    log NewGuard(GuardAddress)



@external
def removeGuard(GuardAddress: address):
    assert msg.sender == self.contractOwner
    #GuardAddress is in self.LGov
    current_index: uint256 = self.LGov[GuardAddress]
    last_index = len(self.LGov) 
    self.LGov[current_index] = self.LGov[last_index] 
    self.LGov[last_index] = ZERO_ADDRESS
    log GuardRemoval(GuardAddress)




@external
def swapGuard(OldGuardAddress: address, NewGuardAddress: address):
    assert msg.sender == self.contractOwner
    #OldGuardAddress is in self.LGov
    #NewGuardAddress is not in self.LGov
    assert NewGuardAddress != ZERO_ADDRESS
    current_index: uint256 = self.LGov[OldGuardAddress]
    self.LGov[current_index] = NewGuardAddress
    log GuardSwap(OldGuardAddress, NewGuardAddress)

