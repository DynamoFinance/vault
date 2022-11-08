import ape

import pytest
from  pytest import raises

WEIGHTS = [100, 1000]
APYNOW = 5
APYPREDICTED = 10
NONCE = 1
VOTE_COUNT = 6

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
    ag = governance_contract.addGuard(someone, sender=owner)
    logs = list(ag.decode_logs(governance_contract.NewGuard))
    assert len(logs) == 1
    assert logs[0].GuardAddress == someone
    #assert governance_contract.no_guards() == 1
    # assert governance_contract.LGov == owner


def test_removeGuard(governance_contract, accounts):
    owner, operator, someoneelse, someone = accounts[:4]
    with ape.reverts():
        rg = governance_contract.removeGuard(someone, sender=owner)

    # Now add a guard or two then remove.        
    governance_contract.addGuard(someone, sender=owner)
    rg = governance_contract.removeGuard(someone, sender=owner)    
    logs = list(rg.decode_logs(governance_contract.GuardRemoved))
    assert len(logs) == 1


def test_swapGuard(governance_contract, accounts):
    owner, operator, someoneelse, someone = accounts[:4]
    sg = governance_contract.swapGuard(someone, someoneelse, sender=owner)
    logs = list(sg.decode_logs(governance_contract.GuardSwap))
    assert len(logs) == 1