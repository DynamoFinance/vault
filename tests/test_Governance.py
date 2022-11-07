import ape

import pytest
from  pytest import raises

WEIGHTS = [100, 1000]
APYNOW = 5
APYPREDICTED = 10

@pytest.fixture
#def governance_contract(Governance, accounts):
def governance_contract(owner, project, accounts):
    #brownie.network.gas_price(GAS_PRICE_GWEI)

    owner, operator, someoneelse, someone = accounts[:4]

    # deploy the contract with the initial value as a constructor argument

    contract = owner.deploy(project.Governance, owner)


    return contract  

# @pytest.fixture
# def ProposedStrategy(owner, project, accounts):


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



def test_addGuard(governance_contract, accounts):
    owner, operator, someoneelse, someone = accounts[:4]
    ag = governance_contract.addGuard(someone, sender=owner)
    logs = list(ag.decode_logs(governance_contract.NewGuard))
    assert len(logs) == 1
    # assert governance_contract.LGov == 0


# def test_removeGuard(governance_contract):
#     pass

# def test_swapGuard(governance_contract):
#     pass

# def test_activateStrategy(governance_contract):
#     pass

# def test_endorseStrategy(governance_contract):
#     pass

# def test_rejectStrategy(governance_contract):
#     pass

# def test_withdrawStrategy(governance_contract):
#     pass


