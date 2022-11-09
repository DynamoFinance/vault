import ape

import pytest
from  pytest import raises

WEIGHTS = [100, 1000]
APYNOW = 5
APYPREDICTED = 10
NONCE = 1
VOTE_COUNT = 6
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

@pytest.fixture
#def governance_contract(Governance, accounts):
def governance_contract(owner, project, accounts):
    #brownie.network.gas_price(GAS_PRICE_GWEI)

    owner, operator, someoneelse, someone = accounts[:4]

    # deploy the contract with the initial value as a constructor argument

    contract = owner.deploy(project.Governance, owner)


    return contract  


def test_submitStrategy(governance_contract, accounts, owner):
    ProposedStrategy = (WEIGHTS, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]
    governance_contract.addGuard(someone, sender=owner)
    # governance_contract.CurrentStrategy.Nonce = governance_contract.PendingStrategy.Nonce
    # ProposedStrategy.APYPredicted - ProposedStrategy.APYNow > governance_contract.MinimumAPYIncrease
    sp = governance_contract.submitStrategy(ProposedStrategy, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1
    # assert governance_contract.PendingStrategy_Nonce == 1
    # assert governance_contract.CurrentStrategy.Nonce != governance_contract.PendingStrategy.Nonce


def test_withdrawStrategy(governance_contract, accounts):
    ProposedStrategy = (WEIGHTS, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]
    governance_contract.addGuard(someone, sender=owner)

    sp = governance_contract.submitStrategy(ProposedStrategy, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    governance_contract.PendingStrategy.Nonce = NONCE
    ws = governance_contract.withdrawStrategy(NONCE, sender=owner)
    logs = list(ws.decode_logs(governance_contract.StrategyWithdrawal))
    assert len(logs) == 1


def test_endorseStrategy(governance_contract, accounts):
    ProposedStrategy = (WEIGHTS, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]
    governance_contract.addGuard(someone, sender=owner)

    sp = governance_contract.submitStrategy(ProposedStrategy, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    governance_contract.PendingStrategy.Nonce = NONCE
    with ape.reverts():
        es = governance_contract.endorseStrategy(NONCE, sender=owner)

    governance_contract.addGuard(owner, sender=owner)
    es = governance_contract.endorseStrategy(NONCE, sender=owner)
    logs = list(es.decode_logs(governance_contract.StrategyVote))
    assert len(logs) == 1


def test_rejectStrategy(governance_contract, accounts):
    ProposedStrategy = (WEIGHTS, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]
    governance_contract.addGuard(someone, sender=owner)

    sp = governance_contract.submitStrategy(ProposedStrategy, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    governance_contract.PendingStrategy.Nonce = NONCE
    with ape.reverts():
        rs = governance_contract.rejectStrategy(NONCE, sender=owner)
    
    governance_contract.addGuard(owner, sender=owner)
    rs = governance_contract.rejectStrategy(NONCE, sender=owner)
    logs = list(rs.decode_logs(governance_contract.StrategyVote))
    assert len(logs) == 1


def test_activateStrategy(governance_contract, accounts):
    ProposedStrategy = (WEIGHTS, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]
    governance_contract.addGuard(someone, sender=owner)

    sp = governance_contract.submitStrategy(ProposedStrategy, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    governance_contract.PendingStrategy.VotesEndorse = VOTE_COUNT
    # governance_contract.PendingStrategy.VotesEndorse > governance_contract.no_guards/2
    governance_contract.PendingStrategy.Nonce = NONCE
    acs = governance_contract.activateStrategy(NONCE, sender=owner)
    logs = list(acs.decode_logs(governance_contract.StrategyActivation))
    assert len(logs) == 1

 

def test_addGuard(governance_contract, accounts):
    owner, operator, someoneelse, someone = accounts[:4]

    #Test if i can add a guard as someone who is not the contract owner.
    with ape.reverts():
        ag = governance_contract.addGuard(someone, sender=someone)
    
    #Test if i can add guard.
    ag = governance_contract.addGuard(someone, sender=owner)
    logs = list(ag.decode_logs(governance_contract.NewGuard))
    assert len(logs) == 1
    assert logs[0].GuardAddress == someone

    #Test if i can add the same guard again.
    with ape.reverts():
        ag = governance_contract.addGuard(someone, sender=owner)

    #Test if i can add a ZERO_ADDRESS.
    with ape.reverts():
        ag = governance_contract.addGuard(ZERO_ADDRESS, sender=owner)

    ag = governance_contract.addGuard(someoneelse, sender=owner)

    #Test if i can add a guard when len(LGov) = MAX_GUARDS
    with ape.reverts():
        ag = governance_contract.addGuard(operator, sender=owner)



def test_removeGuard(governance_contract, accounts):
    owner, operator, someoneelse, someone = accounts[:4]

    #Test to see if i can remove a guard when there are no guards.
    with ape.reverts():
        rg = governance_contract.removeGuard(someone, sender=owner)

    # Now add a guard.        
    governance_contract.addGuard(someone, sender=owner)

    #Test if i can remove a guard as someone who is not the contract owner.
    with ape.reverts():
        rg = governance_contract.removeGuard(someone, sender=someone)

    #Test to see if i can remove a guard thats not in list of guards.
    with ape.reverts():
        rg = governance_contract.removeGuard(operator, sender=owner)

    #Test if i can remove a guard.
    rg = governance_contract.removeGuard(someone, sender=owner)    
    logs = list(rg.decode_logs(governance_contract.GuardRemoved))
    assert len(logs) == 1
    assert logs[0].GuardAddress == someone


def test_swapGuard(governance_contract, accounts):
    owner, operator, someoneelse, someone = accounts[:4]

    #Test if i can swap out a guard that is not on the list of guards.
    with ape.reverts():
        sg = governance_contract.swapGuard(someone, someoneelse, sender=owner)

    governance_contract.addGuard(someone, sender=owner)

    #Test if i can swap a guard as someone who is not the contract owner.
    with ape.reverts():
        sg = governance_contract.swapGuard(someone, someoneelse, sender=someoneelse)

    #Test if i can add a ZERO_ADDRESS.
    with ape.reverts():
        sg = governance_contract.swapGuard(someone, ZERO_ADDRESS, sender=owner)

    governance_contract.addGuard(operator, sender=owner)

    #Test if i can swap in a guard thats already on the list of guards.
    with ape.reverts():
        sg = governance_contract.swapGuard(someone, operator, sender=owner)

    #Test if i can swap guard.
    sg = governance_contract.swapGuard(someone, someoneelse, sender=owner)
    logs = list(sg.decode_logs(governance_contract.GuardSwap))
    assert len(logs) == 1
    assert logs[0].OldGuardAddress == someone
    assert logs[0].NewGuardAddress == someoneelse