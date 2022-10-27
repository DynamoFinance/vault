# Dynamo Defi <-> Governance Contract

## Summary

These are sequence diagrams for each function of the Governance Contract. 
The Governance Contract provides a way to submit strategies to rebalance investment pools while using a voting system to approve those said strategies.

## Given

P<sub>E</sub> = Predicate - Proposer must meet certain qualification for eligibility. (Must resolve to True)

- Ex: hold a certain quantity of vault tokens. TBD

P<sub>X</sub> = Predicate - Proposer must not be subject to some form of exclusion. (Must resolve to False)

- Ex: having been rejected in last 24 hrs or on a black list. TBD

T<sub>DELAY</sub> = Variable - How long after a strategy is submitted until it can be activated so long as it is not rejected/overwhelmingly endorsed.

L<sub>GOV</sub> = Variable - List of addresses of Governance Guards who vote on Strategy Submissions.

Strategy = (Proposed) Struct = { Nonce, Proposer Addr, Weights[], T<sub>SUBMITTED</sub>, T<sub>ACTIVATED</sub>, len(L<sub>GOV</sub>), Votes<sub>ENDORSE</sub>, Votes<sub>REJECT</sub> }

## SubmitStrategy

```mermaid
sequenceDiagram

    participant P as Proposer
    participant C1 as Governance Contract
    participant N as Ethereum Network

    autonumber

    Note over P: Pre-Conditions:<br>Addr=User.wallet<br>Weights=[list of lending platform weights]<br>APYNow=(user calculation)<br>APYPredicted=(user calculation)<br>Strategy = {Nonce=0, Addr, Weights, APYNow, APYPredicted}
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current Active Strategy)<br> self.PendingStrategy = (Current Pending Strategy) <br> self.PendingStrategy= (self.CurrentStrategy || some other)<br>self.NextNonce=(next StrategyID > 0)<br>self.TDelay=(wait time for proposed Strategy)<br>self.MinimumAPYIncrease=(min improvement to consider Strategy)<br>self.LGOV = list of Governance Voter addresses

    P->>C1:submitStrategy(Strategy)
    Note over C1: No Strategy proposals if no governance guards <br> len(self.LGOV) > 0
    Note over C1: Confirm No Currently Pending Strategy<br>self.CurrentStrategy==self.PendingStrategy ||<br>self.PendingStrategy.Withdrawn==True ||<br>count(self.PendingVotesReject)>len(self.LGOV)/2 ||<br>(self.PendingStrategy.TSubmitted+self.TDelay < now() and<br>count(self.PendingStrategy.VotesReject)>count(self.PendingStrategy.VotesEndorsed)
    C1 ->> C1: _noPendingStrategy() == True

        Note over C1: Confirm msg.sender Eligibility<br>(TBD)
    C1->>C1:PE() == True
    Note over C1: Confirm msg.sender is not blacklisted<br>(TBD)
    C1->>C1:PX() == FALSE

    Note over C1: Confirm Strategy.APYPredicted - Strategy.APYNow >= self.MinimumAPYIncrease

    Note over C1: Construct the New Strategy<br>TSubmitted=now()<br>TActive=0<br>Nonce=self.NextNonce<br>self.NextNonce+=1<br>VoterCount=len(self.LGOV)<br>Strategy={*Strategy,TSubmitted,TActive,Nonce,Withdrawn=False,VoterCount,VotesEndorse=[],VotesReject=[]}
    Note Over C1: self.PendingStrategy = Strategy

    


    C1-->>N: Emit Event StrategyProposal(Strategy)

    C1->>P: return self.PendingStrategy.Nonce
```

## WithdrawStrategy

```mermaid
sequenceDiagram

    participant P as Proposer
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber
    Note over P:<br> Pre-Conditions:<br> Nonce = (Nonce of previously submitted strategy)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active Strategy)<br> self.PendingStrategy = (Current Pending Strategy)
    P->>C1: withdrawStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy <br>self.CurrentStrategy != self.PendingStrategy 
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is the Strategy we want to withdraw <br> self.PendingStrategy.Nonce == Nonce
    Note over C1: Confirm Sender is the Strategy Proposer 
    Note over C1: Confirm msg.sender == self.PendingStrategy.ProposerAddress
    Note over C1:Set self.PendingStrategy.Withdrawn = True
    C1-->>N: Emit Event StrategyWithdrawal(Nonce)
    C1-->>P: return True
```

## EndorseStartegy

```mermaid
sequenceDiagram

    participant G as Guard
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber

    Note over G:<br> Pre-Conditions:<br>Nonce = (Nonce of previously submitted <br> StrategyProposalEvent that the guard wishes to endorse)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active strategy)<br> self.LGOV = list of Guards <br> self.PendingStrategy = (Current Pending Strategy)
    G->>C1: endorseStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy  <br> self.CurrentStrategy != self.PendingStrategy 
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is the Strategy we want to Endorse <br> self.PendingStrategy.Nonce == Nonce


    Note over C1: Confirm the Sender is a Guard Address in List of Guards
    Note over C1: msg.sender is in self.LGOV
    Note over C1: Confirm Sender has not yet voted 
    Note over C1: msg.sender is not in self.PendingStrategy.VoteReject and <br> msg.sender is not in self.PendingStrategy.VoteEndorse

    Note over C1:self.PendingStrategy.VoteEndorse.Append(msg.sender)



    C1-->>N: Emit Event StrategyVote(Nonce, GuardAddress, Endorse=True)

    C1-->>G: return True
```

## RejectStartegy

```mermaid
sequenceDiagram

    participant G as Guard
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber

    Note over G:<br> Pre-Conditions:<br>Nonce = (Nonce of previously submitted <br> StrategyProposalEvent that the guard wishes to reject)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active strategy)<br> self.LGOV = list of Guards <br> self.PendingStrategy = (Current Pending Strategy)
    G->>C1: rejectStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy <br> self.CurrentStrategy != self.PendingStrategy
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is the Strategy we want to Reject<br> self.PendingStrategy.Nonce == Nonce
    


    Note over C1: Confirm the Sender is a Guard Address in List of Guards
    Note over C1: msg.sender is in self.LGOV
    Note over C1: Confirm Sender has not yet voted 
    Note over C1: msg.sender is not in self.PendingStrategy.VoteReject and <br> msg.sender is not in self.PendingStrategy.VoteEndorse

    Note over C1:self.PendingStrategy.VoteReject.Append(msg.sender)



    C1-->>N: Emit Event StrategyVote(Nonce, GuardAddress, Endorse=False)

    C1-->>G: return True
```

## ActivateStartegy

```mermaid
sequenceDiagram

    participant A as Any Role
    participant C1 as Governance Contract
    participant D as Dynamo Vault
    participant N as Ethereum Network

    autonumber

    Note over A:<br> Pre-Conditions:<br>Nonce = (Nonce of previously submitted <br> StrategyProposalEvent that the guard wishes to endorse)
    Note over C1: Pre-Conditions:<br>self.CurrentStrategy = (Current active Strategy)<br> self.TDelay=(wait time for proposed Strategy <br> self.PendingStrategy = (Current Pending Strategy)
    A->>C1: activateStrategy(Nonce)
    Note over C1: Confirm there is a Currently Pending Strategy <br>self.CurrentStrategy != self.PendingStrategy ||<br>self.PendingStrategy.Withdrawn==False 
    C1 ->> C1: _noPendingStrategy() == False
    Note over C1: Confirm Pending Strategy is Approved by Guards <br>count(self.PendingVotesEndorse)>len(self.LGOV)/2 ||<br>(self.PendingStrategy.TSubmitted+self.TDelay < now() and<br>count(self.PendingStrategy.VotesReject)<count(self.PendingStrategy.VotesEndorsed)
    Note over C1: Confirm Pending Strategy is the Strategy we want to Activate<br> self.PendingStrategy.Nonce == Nonce
    


    Note over C1:self.PendingStrategy = self.CurrentStrategy
    C1->>D: PoolRebalancer(self.CurrentStrategy)



    C1-->>N: Emit Event StrategyActivation(self.CurrentStrategy)

    C1-->>A: return True
```

## AddGuard

```mermaid
sequenceDiagram

    participant OG as Owner
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber


    Note over C1: Pre-Conditions: <br> self.LGOV is the List of Current Guards <br> self.Owner is Governance Contract Owner Address <br> MAX_GUARDS is maximum count of guards

    OG->>C1: addGuard(GuardAddress)
    Note over C1: Confirm Sender is the Governance Contract Owner
    Note over C1: msg.sender == self.Owner
    Note over C1: Confirm the Guard being added is not in List of Guards
    Note over C1: GuardAddress is not in self.LGOV
    Note over C1: Confirm there is not the maximum amount of guards in the guard list
    Note over C1: len(self.LGOV) is less than MAX_GUARDS
    Note over C1: Confirm the Guard is a real address
    Note over C1: GuardAddress != ZERO_ADDRESS
    Note over C1: self.LGOV.Append(GuardAddress)


    C1-->>N: Emit Event NewGuard(GuardAddress)

    C1-->>OG: return True
```

## RemoveGuard

```mermaid
sequenceDiagram

    participant OG as Owner
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber


    Note over C1: Pre-Conditions: <br> self.LGOV is the List of Current Guards <br> self.Owner is Governance Contract Owner Address 
    OG->>C1: removeGuard(GuardAddress)

    Note over C1: Confirm Sender is the Governance Contract Owner
    Note over C1: msg.sender == self.Owner
    Note over C1: Confirm the Guard being removed is in List of Guards
    Note over C1: GuardAddress is in self.LGOV

    Note over C1: Replace Deleted Guard with Last Guard in List: <br> Index = position of GuardAddress in self.LGOV <br> Last_Pos = len(self.LGOV)<br> self.LGOV(Index) = self.LGOV(Last_Pos) <br> self.LGOV(Last_Pos) = ZERO_ADDRESS
    

    C1-->>N: Emit Event GuardRemoved(GuardAddress)

    C1-->>OG: return True
```

## SwapGuard

```mermaid
sequenceDiagram

    participant OG as Owner
    participant C1 as Governance Contract
    participant N as Ethereum Network
    autonumber

   
    Note over C1: Pre-Conditions: <br> self.LGOV is the List of Current Guards <br> self.Owner is Governance Contract Owner Address 
    OG->>C1: swapGuard(OldGuardAddress, NewGuardAddress)


    Note over C1: Confirm Sender is the Governance Contract Owner
    Note over C1: msg.sender == self.Owner 

    Note over C1: Confirm the New Guard being added is not in List of Guards
    Note over C1: NewGuardAddress is not in self.LGOV
    Note over C1: Confirm the Old Guard being removed is in List of Guards
    Note over C1: OldGuardAddress is in self.LGOV

    Note over C1: Confirm the New Guard is a real address
    Note over C1: NewGuardAddress != ZERO_ADDRESS
    
    Note over C1: Replace Old Guard with New Guard: <br> Index = position of OldGuardAddress in self.LGOV <br>  self.LGOV(Index) = self.LGOV(NewGuardAddress) 


    C1-->>N: Emit Event GuardSwap(OldGuardAddress, NewGuardAddress)

    C1-->>OG: return True
```
