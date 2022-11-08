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
            (self.PendingStrategy.Withdrawn == True) or \
            (len(self.PendingStrategy.VotesReject) >= self.PendingStrategy.no_guards/2) or \
            ((convert(self.PendingStrategy.TSubmitted, decimal)+(convert(self.TDelay, decimal) * 1.25)) > convert(block.timestamp, decimal)), "Cannot Submit Strategy"

    # Confirm msg.sender Eligibility
    # Confirm msg.sender is not blacklisted

    # Confirm strategy meets financial goal improvements.
    assert strategy.APYPredicted - strategy.APYNow >= self.MinimumAPYIncrease, "Cannot Submit Strategy without APY Increase"

    
    self.PendingStrategy.Nonce = self.NextNonce
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
    return self.PendingStrategy.Nonce



@external
def withdrawStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce, "Cannot withdraw Current Strategy"
    assert self.PendingStrategy.Nonce == Nonce, "Cannot Withdraw Strategy if its not Pending Strategy"
    # assert self.PendingStrategy.ProposerAddress == msg.sender
    self.PendingStrategy.Withdrawn = True
    log StrategyWithdrawal(Nonce)



@external
def endorseStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce, "Cannot Endorse Strategy thats already  Strategy"
    assert self.PendingStrategy.Nonce == Nonce, "Cannot Endorse Strategy if its not Pending Strategy"
    assert msg.sender in self.LGov
    # assert msg.sender not in self.PendingStrategy.VoteReject
    # assert msg.sender not in self.PendingStrategy.VoteEndorse
    self.PendingStrategy.VotesEndorse.append(msg.sender)
    log StrategyVote(Nonce, msg.sender, False)



@external
def rejectStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce, "Cannot Reject Strategy thats already Current Strategy"
    assert self.PendingStrategy.Nonce == Nonce, "Cannot Reject Strategy if its not Pending Strategy"
    assert msg.sender in self.LGov
    # assert msg.sender not in self.PendingStrategy.VoteReject
    # assert msg.sender not in self.PendingStrategy.VoteEndorse
    self.PendingStrategy.VotesReject.append(msg.sender)
    log StrategyVote(Nonce, msg.sender, True)



@external
def activateStrategy(Nonce: uint256):
    assert self.CurrentStrategy.Nonce != self.PendingStrategy.Nonce
    assert self.PendingStrategy.Withdrawn == False
    assert len(self.PendingStrategy.VotesEndorse) >= len(self.LGov)/2 
    # assert (self.PendingStrategy_TSubmitted + self.TDelay) <= now() 
    # assert count(self.PendingStrategy.VotesReject) <= count(self.PendingStrategy.VotesEndorsed)
    assert self.PendingStrategy.Nonce == Nonce
    self.CurrentStrategy = self.PendingStrategy
    #PoolRebalancer(self.CurrentStrategy)
    log StrategyActivation(Nonce)

 

@external
def addGuard(GuardAddress: address):
    #Check to see that sender is the contract owner
    assert msg.sender == self.contractOwner, "Cannot add guard unless you are contract owner"

    #Check to see if there is the max amount of Guards
    assert len(self.LGov) <= MAX_GUARDS, "Cannot add anymore guards"

    #Check to see that the Guard being added is a valid address
    assert GuardAddress != ZERO_ADDRESS, "Cannot add ZERO_ADDRESS"

    #Check to see that GuardAddress is not already in self.LGov
    assert GuardAddress not in self.LGov, "Guard already exists"

    #Add new guard address as the last in the list of guards
    self.LGov.append(GuardAddress)

    log NewGuard(GuardAddress)



@external
def removeGuard(GuardAddress: address):
    assert msg.sender == self.contractOwner, "Cannot remove guard unless you are contract owner"

    last_index: uint256 = len(self.LGov) 
    assert last_index != 0, "No guards to remove."

    # Correct size to zero offset position.
    last_index -= 1
    
    current_index: uint256 = 0
    for guard_addr in self.LGov:
        if guard_addr == GuardAddress: break
        current_index += 1

    assert GuardAddress == self.LGov[current_index], "GuardAddress not a current Guard."    

    # Replace Current Guard with last
    self.LGov[current_index] = self.LGov[last_index]

    # Eliminate the redundant one at the end.
    self.LGov.pop()

    log GuardRemoved(GuardAddress)



@external
def swapGuard(OldGuardAddress: address, NewGuardAddress: address):
    assert msg.sender == self.contractOwner, "Cannot swap guard unless you are contract owner"

    assert NewGuardAddress != ZERO_ADDRESS    
    assert NewGuardAddress not in self.LGov, "New Guard is already a Guard."

    current_index: uint256 = 0 
    for guard_addr in self.LGov:
        if guard_addr == OldGuardAddress: break
        current_index += 1

    assert OldGuardAddress == self.LGov[current_index], "OldGuardAddress not a current Guard."

    self.LGov[current_index] = NewGuardAddress

    log GuardSwap(OldGuardAddress, NewGuardAddress)

