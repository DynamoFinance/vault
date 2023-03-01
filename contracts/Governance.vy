# @version 0.3.7

event StrategyWithdrawal:
    Nonce: uint256
    vault: address

event StrategyVote:
    Nonce: uint256
    vault: address
    GuardAddress: indexed(address)
    Endorse: bool

event StrategyActivation:
    strategy: Strategy
    vault: address

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
    VaultAddress: address

event StrategyProposal:
    strategy: Strategy
    vault: address
    
# Contract assigned storage 
contractOwner: public(address)
MAX_GUARDS: constant(uint256) = 2
MAX_POOLS: constant(uint256) = 10
MAX_VAULTS: constant(uint256) = 3
LGov: public(DynArray[address, MAX_GUARDS])
TDelay: public(uint256)
no_guards: public(uint256)
CurrentStrategyByVault: public(HashMap[address, Strategy])
PendingStrategyByVault: public(HashMap[address, Strategy])
VotesGCByVault: public(HashMap[address, HashMap[address, address]])
MIN_GUARDS: constant(uint256) = 1
NextNonceByVault: public(HashMap[address, uint256])
VaultList: public(DynArray[address, MAX_VAULTS])


interface Vault:
    def PoolRebalancer(CurrentStrategy: Strategy) -> bool: nonpayable
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

    #Run through list of vaults and make sure the vault is in vault list
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1

    assert vault == self.VaultList[current_vault], "vault not on vault list." 

    # Confirm there's no currently pending strategy for this vault so we can replace the old one.

            # First is it the same as the current one?
            # Otherwise has it been withdrawn? 
            # Otherwise, has it been short circuited down voted? 
            # Has the period of protection from being replaced expired already?         
    assert  (self.CurrentStrategyByVault[vault].Nonce == self.PendingStrategyByVault[vault].Nonce) or \
            (self.PendingStrategyByVault[vault].Withdrawn == True) or \
            len(self.PendingStrategyByVault[vault].VotesReject) > 0 and \
            (len(self.PendingStrategyByVault[vault].VotesReject) >= self.PendingStrategyByVault[vault].no_guards/2) or \
            (convert(block.timestamp, decimal) > (convert(self.PendingStrategyByVault[vault].TSubmitted, decimal)+(convert(self.TDelay, decimal) * 1.25)))

    # Confirm msg.sender Eligibility
    # Confirm msg.sender is not blacklisted

    # Confirm strategy meets financial goal improvements.
    assert strategy.APYPredicted - strategy.APYNow > 0, "Cannot Submit Strategy without APY Increase"

    self.PendingStrategyByVault[vault].Nonce = self.NextNonceByVault[vault]
    self.NextNonceByVault[vault] += 1
    self.PendingStrategyByVault[vault].ProposerAddress = msg.sender
    self.PendingStrategyByVault[vault].Weights = strategy.Weights
    self.PendingStrategyByVault[vault].APYNow = strategy.APYNow
    self.PendingStrategyByVault[vault].APYPredicted = strategy.APYPredicted
    self.PendingStrategyByVault[vault].TSubmitted = block.timestamp
    self.PendingStrategyByVault[vault].TActivated = 0    
    self.PendingStrategyByVault[vault].Withdrawn = False
    self.PendingStrategyByVault[vault].no_guards = len(self.LGov)
    self.PendingStrategyByVault[vault].VotesEndorse = empty(DynArray[address, MAX_GUARDS])
    self.PendingStrategyByVault[vault].VotesReject = empty(DynArray[address, MAX_GUARDS])
    self.PendingStrategyByVault[vault].VaultAddress = vault

    log StrategyProposal(self.PendingStrategyByVault[vault], vault)
    return self.PendingStrategyByVault[vault].Nonce


@external
def withdrawStrategy(Nonce: uint256, vault: address):
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Run through list of vaults and make sure the vault is in vault list
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1

    assert vault == self.VaultList[current_vault], "vault not on vault list." 

    #Check to see that the pending strategy is not the current strategy
    assert (self.CurrentStrategyByVault[vault].Nonce != self.PendingStrategyByVault[vault].Nonce), "Cannot withdraw Current Strategy"

    #Check to see that the pending strategy's nonce matches the nonce we want to withdraw
    assert self.PendingStrategyByVault[vault].Nonce == Nonce, "Cannot Withdraw Strategy if its not Pending Strategy"

    #Check to see that sender is eligible to withdraw
    assert self.PendingStrategyByVault[vault].ProposerAddress == msg.sender

    #Withdraw Pending Strategy
    self.PendingStrategyByVault[vault].Withdrawn = True

    log StrategyWithdrawal(Nonce, vault)


@external
def endorseStrategy(Nonce: uint256, vault: address):
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Run through list of vaults and make sure the vault is in vault list
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1

    assert vault == self.VaultList[current_vault], "vault not on vault list." 

    #Check to see that the pending strategy is not the current strategy
    assert self.CurrentStrategyByVault[vault].Nonce != self.PendingStrategyByVault[vault].Nonce, "Cannot Endorse Strategy thats already  Strategy"

    #Check to see that the pending strategy's nonce matches the nonce we want to endorse
    assert self.PendingStrategyByVault[vault].Nonce == Nonce, "Cannot Endorse Strategy if its not Pending Strategy"

    #Check to see that sender is eligible to vote
    assert msg.sender in self.LGov, "Sender is not eligible to vote"

    #Check to see that sender has not already voted
    assert msg.sender not in self.PendingStrategyByVault[vault].VotesReject
    assert msg.sender not in self.PendingStrategyByVault[vault].VotesEndorse

    #Vote to endorse strategy
    self.PendingStrategyByVault[vault].VotesEndorse.append(msg.sender)

    log StrategyVote(Nonce, vault, msg.sender, False)


@external
def rejectStrategy(Nonce: uint256, vault: address):
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Run through list of vaults and make sure the vault is in vault list
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1

    assert vault == self.VaultList[current_vault], "vault not on vault list." 

    #Check to see that the pending strategy is not the current strategy
    assert self.CurrentStrategyByVault[vault].Nonce != self.PendingStrategyByVault[vault].Nonce, "Cannot Reject Strategy thats already Current Strategy"

    #Check to see that the pending strategy's nonce matches the nonce we want to reject
    assert self.PendingStrategyByVault[vault].Nonce == Nonce, "Cannot Reject Strategy if its not Pending Strategy"

    #Check to see that sender is eligible to vote
    assert msg.sender in self.LGov

    #Check to see that sender has not already voted
    assert msg.sender not in self.PendingStrategyByVault[vault].VotesReject
    assert msg.sender not in self.PendingStrategyByVault[vault].VotesEndorse

    #Vote to reject strategy
    self.PendingStrategyByVault[vault].VotesReject.append(msg.sender)

    log StrategyVote(Nonce, vault, msg.sender, True)


@external
def activateStrategy(Nonce: uint256, vault: address):
    # No using a Strategy function without a vault
    assert len(self.VaultList) > 0, "Cannot call Strategy function with no vault"

    #Run through list of vaults and make sure the vault is in vault list
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1

    assert vault == self.VaultList[current_vault], "vault not on vault list." 

    #Confirm there is a currently pending strategy
    assert (self.CurrentStrategyByVault[vault].Nonce != self.PendingStrategyByVault[vault].Nonce)
    assert (self.PendingStrategyByVault[vault].Withdrawn == False)

    #Confirm strategy is approved by guards
    assert (len(self.PendingStrategyByVault[vault].VotesEndorse) >= len(self.LGov)/2) or \
           ((self.PendingStrategyByVault[vault].TSubmitted + self.TDelay) < block.timestamp)
    assert len(self.PendingStrategyByVault[vault].VotesReject) < len(self.PendingStrategyByVault[vault].VotesEndorse)

    #Confirm Pending Strategy is the Strategy we want to activate
    assert self.PendingStrategyByVault[vault].Nonce == Nonce

    #Make Current Strategy and Activate Strategy
    self.CurrentStrategyByVault[vault] = self.PendingStrategyByVault[vault]
    # Vault(self.Vault).PoolRebalancer(self.CurrentStrategyByVault)

    log StrategyActivation(self.CurrentStrategyByVault[vault], vault)
 

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

    #Run through list of vaults and make sure the vault is in vault list
    current_vault: uint256 = 0
    for vault_addr in self.VaultList:
        if vault_addr == vault: break
        current_vault += 1
    
    assert vault == self.VaultList[current_vault], "vault not on vault list."

    #Check if there are enough guards to change governance
    assert len(self.LGov) >= MIN_GUARDS

    #Check if sender is a guard
    assert msg.sender in self.LGov

    #Check if new contract address is not the current)
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