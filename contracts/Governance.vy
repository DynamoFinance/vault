# @version 0.3.7

event StrategyWithdrawal:
    Nonce: uint256
    vault: address

event StrategyVote:
    Nonce: uint256
    vault: address
    GuardAddress: indexed(address)
    Endorse: bool

event NewGuard:
    GuardAddress: indexed(address)

event GuardRemoved:
    GuardAddress: indexed(address)

event GuardSwap:
    OldGuardAddress: indexed(address)
    NewGuardAddress: indexed(address)

event GovernanceContractChanged:
    Voter: address
    NewGovernance: indexed(address)
    VoteCount: uint256
    TotalGuards: uint256

event VoteForNewGovernance:
    NewGovernance: indexed(address)

event NewVault:
    vault: indexed(address)

event VaultRemoved:
    vault: indexed(address)

event VaultSwap:
    OldVaultAddress: indexed(address)
    NewVaultAddress: indexed(address)


#Weights
struct AdapterStrategy:
    adapter: address
    ratio: uint256

struct ProposedStrategy:
    Weights: AdapterStrategy[MAX_POOLS]
    APYNow: uint256
    APYPredicted: uint256    

event StrategyProposal:
    strategy : Strategy
    ProposerAddress: address
    Weights: AdapterStrategy[MAX_POOLS]
    vault: address

event StrategyActivation:
    strategy: Strategy
    ProposerAddress: address
    Weights: AdapterStrategy[MAX_POOLS]
    vault: address

struct Strategy:
    Nonce: uint256
    ProposerAddress: address
    Weights: AdapterStrategy[MAX_POOLS]
    APYNow: uint256
    APYPredicted: uint256
    TSubmitted: uint256
    TActivated: uint256
    Withdrawn: bool
    no_guards: uint256
    VotesEndorse: DynArray[address, MAX_GUARDS]
    VotesReject: DynArray[address, MAX_GUARDS]
    VaultAddress: address
    
# Contract assigned storage 
contractOwner: public(address)
MAX_GUARDS: constant(uint256) = 2
MAX_POOLS: constant(uint256) = 5
MAX_VAULTS: constant(uint256) = 3
MIN_PROPOSER_PAYOUT: constant(uint256) = 0
LGov: public(DynArray[address, MAX_GUARDS])
TDelay: public(uint256)
no_guards: public(uint256)
CurrentStrategyByVault: public(HashMap[address, Strategy])
PendingStrategyByVault: public(HashMap[address, Strategy])
VotesGCByVault: public(HashMap[address, HashMap[address, address]])
MIN_GUARDS: constant(uint256) = 1
NextNonceByVault: public(HashMap[address, uint256])
VaultList: public(DynArray[address, MAX_VAULTS])


interface DynamoVault:
    def set_strategy(Proposer: address, Strategies: AdapterStrategy[MAX_POOLS], min_proposer_payout: uint256) -> bool: nonpayable
    def replaceGovernanceContract(NewGovernance: address) -> bool: nonpayable


@external
def __init__(contractOwner: address, _tdelay: uint256):
    self.contractOwner = contractOwner
    self.TDelay = _tdelay
    if _tdelay == empty(uint256):
        self.TDelay = 21600


@external
def submitStrategy(strategy: ProposedStrategy, vault: address) -> uint256:
    if self.NextNonceByVault[vault] == 0:
        self.NextNonceByVault[vault] += 1

    # No Strategy proposals if no governance guards
    assert len(self.LGov) > 0, "Cannot Submit Strategy without Guards"

    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    assert vault in self.VaultList, "vault not in vault list!"        

    pending_strat: Strategy = self.PendingStrategyByVault[vault]

    # Confirm there's no currently pending strategy for this vault so we can replace the old one.

            # First is it the same as the current one?
            # Otherwise has it been withdrawn? 
            # Otherwise, has it been short circuited down voted? 
            # Has the period of protection from being replaced expired already?         
    assert  (self.CurrentStrategyByVault[vault].Nonce == pending_strat.Nonce) or \
            (pending_strat.Withdrawn == True) or \
            len(pending_strat.VotesReject) > 0 and \
            (len(pending_strat.VotesReject) >= pending_strat.no_guards/2) or \
            (convert(block.timestamp, decimal) > (convert(pending_strat.TSubmitted, decimal)+(convert(self.TDelay, decimal) * 1.25))), "Invalid proposed strategy!"

    # Confirm msg.sender Eligibility
    # Confirm msg.sender is not blacklisted

    # Confirm strategy meets financial goal improvements.
    assert strategy.APYPredicted - strategy.APYNow > 0, "Cannot Submit Strategy without APY Increase"

    strat : Strategy = empty(Strategy)

    strat.Nonce = self.NextNonceByVault[vault]
    self.NextNonceByVault[vault] += 1

    strat.ProposerAddress = msg.sender
    strat.Weights = strategy.Weights
    strat.APYNow = strategy.APYNow
    strat.APYPredicted = strategy.APYPredicted
    strat.TSubmitted = block.timestamp
    strat.TActivated = 0    
    strat.Withdrawn = False
    strat.no_guards = len(self.LGov)
    strat.VotesEndorse = empty(DynArray[address, MAX_GUARDS])
    strat.VotesReject = empty(DynArray[address, MAX_GUARDS])
    strat.VaultAddress = vault

    self.PendingStrategyByVault[vault] = strat

    log StrategyProposal(strat, msg.sender, strat.Weights, vault)

    return strat.Nonce


@external
def withdrawStrategy(Nonce: uint256, vault: address):
    pending_strat : Strategy = self.PendingStrategyByVault[vault]
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Check to see if vault is in vault list
    assert vault in self.VaultList, "vault not in vault list!"  

    #Check to see that the pending strategy is not the current strategy
    assert (self.CurrentStrategyByVault[vault].Nonce != pending_strat.Nonce), "Cannot withdraw Current Strategy"

    #Check to see that the pending strategy's nonce matches the nonce we want to withdraw
    assert pending_strat.Nonce == Nonce, "Cannot Withdraw Strategy if its not Pending Strategy"

    #Check to see that sender is eligible to withdraw
    assert pending_strat.ProposerAddress == msg.sender

    #Withdraw Pending Strategy
    pending_strat.Withdrawn = True

    log StrategyWithdrawal(Nonce, vault)


@external
def endorseStrategy(Nonce: uint256, vault: address):
    pending_strat : Strategy = self.PendingStrategyByVault[vault]
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Check to see if vault is in vault list
    assert vault in self.VaultList, "vault not in vault list!"  

    #Check to see that the pending strategy is not the current strategy
    assert self.CurrentStrategyByVault[vault].Nonce != pending_strat.Nonce, "Cannot Endorse Strategy thats already  Strategy"

    #Check to see that the pending strategy's nonce matches the nonce we want to endorse
    assert pending_strat.Nonce == Nonce, "Cannot Endorse Strategy if its not Pending Strategy"

    #Check to see that sender is eligible to vote
    assert msg.sender in self.LGov, "Sender is not eligible to vote"

    #Check to see that sender has not already voted
    assert msg.sender not in pending_strat.VotesReject
    assert msg.sender not in pending_strat.VotesEndorse

    #Vote to endorse strategy
    pending_strat.VotesEndorse.append(msg.sender)

    log StrategyVote(Nonce, vault, msg.sender, False)


@external
def rejectStrategy(Nonce: uint256, vault: address):
    pending_strat : Strategy = self.PendingStrategyByVault[vault]
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Check to see if vault is in vault list
    assert vault in self.VaultList, "vault not in vault list!"  

    #Check to see that the pending strategy is not the current strategy
    assert self.CurrentStrategyByVault[vault].Nonce != pending_strat.Nonce, "Cannot Reject Strategy thats already Current Strategy"

    #Check to see that the pending strategy's nonce matches the nonce we want to reject
    assert pending_strat.Nonce == Nonce, "Cannot Reject Strategy if its not Pending Strategy"

    #Check to see that sender is eligible to vote
    assert msg.sender in self.LGov

    #Check to see that sender has not already voted
    assert msg.sender not in pending_strat.VotesReject
    assert msg.sender not in pending_strat.VotesEndorse

    #Vote to reject strategy
    pending_strat.VotesReject.append(msg.sender)

    log StrategyVote(Nonce, vault, msg.sender, True)


@external
def activateStrategy(Nonce: uint256, vault: address):
    pending_strat : Strategy = self.PendingStrategyByVault[vault]
    current_strat : Strategy = self.CurrentStrategyByVault[vault]
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Check to see if vault is in vault list
    assert vault in self.VaultList, "vault not in vault list!"  

    #Confirm there is a currently pending strategy
    assert (current_strat.Nonce != pending_strat.Nonce)
    assert (pending_strat.Withdrawn == False)

    #Confirm strategy is approved by guards
    assert (len(pending_strat.VotesEndorse) >= len(self.LGov)/2) or \
           ((pending_strat.TSubmitted + self.TDelay) < block.timestamp)
    assert len(pending_strat.VotesReject) < len(pending_strat.VotesEndorse)

    #Confirm Pending Strategy is the Strategy we want to activate
    assert pending_strat.Nonce == Nonce

    #Make Current Strategy and Activate Strategy
    current_strat = pending_strat

    DynamoVault(vault).set_strategy(current_strat.ProposerAddress, current_strat.Weights, MIN_PROPOSER_PAYOUT)

    log StrategyActivation(current_strat, current_strat.ProposerAddress, current_strat.Weights, vault)
 

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
    #Check to see that sender is the contract owner
    assert msg.sender == self.contractOwner, "Cannot remove guard unless you are contract owner"

    last_index: uint256 = len(self.LGov) 
    #Check to see if there are any guards on the list of guards
    assert last_index != 0, "No guards to remove."

    # Correct size to zero offset position.
    last_index -= 1
    
    #Run through list of guards to find the index of the one we want to remove
    current_index: uint256 = 0
    for guard_addr in self.LGov:
        if guard_addr == GuardAddress: break
        current_index += 1

    #Make sure that GuardAddress is a guard on the list of guards
    assert GuardAddress == self.LGov[current_index], "GuardAddress not a current Guard."    

    # Replace Current Guard with last
    self.LGov[current_index] = self.LGov[last_index]

    # Eliminate the redundant one at the end.
    self.LGov.pop()

    log GuardRemoved(GuardAddress)


@external
def swapGuard(OldGuardAddress: address, NewGuardAddress: address):
    #Check that the sender is authorized to swap a guard
    assert msg.sender == self.contractOwner, "Cannot swap guard unless you are contract owner"

    #Check that the guard we are swapping in is a valid address
    assert NewGuardAddress != ZERO_ADDRESS, "Cannot add ZERO_ADDRESS"

    #Check that the guard we are swapping in is not on the list of guards already
    assert NewGuardAddress not in self.LGov, "New Guard is already a Guard."

    #Run through list of guards to find the index of the one we want to swap out
    current_index: uint256 = 0 
    for guard_addr in self.LGov:
        if guard_addr == OldGuardAddress: break
        current_index += 1

    #Make sure that OldGuardAddress is a guard on the list of guards
    assert OldGuardAddress == self.LGov[current_index], "OldGuardAddress not a current Guard."

    #Replace OldGuardAddress with NewGuardAddress
    self.LGov[current_index] = NewGuardAddress

    log GuardSwap(OldGuardAddress, NewGuardAddress)


@external
def replaceGovernance(NewGovernance: address, vault: address):
    VoteCount: uint256 = 0
    Voter: address = msg.sender
    TotalGuards: uint256 = len(self.LGov)
    # No using function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Check to see if vault is in vault list
    assert vault in self.VaultList, "vault not in vault list!"  

    #Check if there are enough guards to change governance
    assert len(self.LGov) >= MIN_GUARDS

    #Check if sender is a guard
    assert msg.sender in self.LGov

    #Check if new contract address is not the current
    assert NewGovernance != self

    #Check if new contract address is valid address
    assert NewGovernance != ZERO_ADDRESS

    #Check if sender has voted, if not log new vote
    if self.VotesGCByVault[vault][msg.sender] != NewGovernance: 
        log VoteForNewGovernance(NewGovernance)

    #Record Vote
    self.VotesGCByVault[vault][msg.sender] = NewGovernance

    #Add Vote to VoteCount
    for guard_addr in self.LGov:
        if self.VotesGCByVault[vault][guard_addr] == NewGovernance:
            VoteCount += 1

    # if len(self.LGov) == VoteCount:
    #     Vault(self.Vault).replaceGovernanceContract(NewGovernance)

    log GovernanceContractChanged(Voter, NewGovernance, VoteCount, TotalGuards)


@external
def addVault(vault: address): 
    # Must be Contract Owner to add vault
    assert msg.sender == self.contractOwner

    # Must have space to add vault
    assert len(self.VaultList) <= MAX_VAULTS

    # Must be a real vault address
    assert vault != ZERO_ADDRESS

    # Must not already be in vault list
    assert vault not in self.VaultList

    # Add vault to vault list
    self.VaultList.append(vault)

    # Log new vault
    log NewVault(vault)


@external
def removeVault(vault: address):
    # Must be Contract owner to remove vault
    assert msg.sender == self.contractOwner

    last_vault: uint256 = len(self.VaultList) 
    # Vault List must not be empty
    assert last_vault != 0

    # Correct size to zero offset position.
    last_vault -= 1
    
    #Run through list of vaults to find the one we want to remove
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1

    # Make sure that vault is the vault we want to remove from vault list
    assert vault == self.VaultList[current_vault], "vault not a current vault."    

    # Replace current vault with the last
    self.VaultList[current_vault] = self.VaultList[last_vault]

    # Remove the last
    self.VaultList.pop()

    #Log Vault Removal
    log VaultRemoved(vault)


@external
def swapVault(OldVaultAddress: address, NewVaultAddress: address):
    #Check that the sender is authorized to swap vault
    assert msg.sender == self.contractOwner

    #Check that the vault we are swapping in is a valid address
    assert NewVaultAddress != ZERO_ADDRESS

    #Check that the vault we are swapping in is not on the list of vaults already
    assert NewVaultAddress not in self.VaultList

    #Run through list of vaults to find the one we want to swap out
    current_vault: uint256 = 0 
    for vault_addr in self.VaultList:
        if vault_addr == OldVaultAddress: break
        current_vault += 1

    #Make sure that OldVaultAddress is a vault on the list of vaults
    assert OldVaultAddress == self.VaultList[current_vault]

    #Replace OldVaultAddress with NewVaultAddress
    self.VaultList[current_vault] = NewVaultAddress

    # Log Vault Swap
    log VaultSwap(OldVaultAddress, NewVaultAddress)