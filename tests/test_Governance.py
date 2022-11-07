import ape

import pytest
from  pytest import raises



@pytest.fixture
#def governance_contract(Governance, accounts):
def governance_contract(owner, project, accounts):
    #brownie.network.gas_price(GAS_PRICE_GWEI)

    someone, operator, someoneelse, owner = accounts[:4]

    # deploy the contract with the initial value as a constructor argument

    contract = owner.deploy(project.Governance, owner)


    return contract  


def test_submitStrategy(governance_contract, ProposedStrategy, accounts):
    someone, operator, someoneelse, owner = accounts[:4]
    governance_contract.addGuard(someone, sender=owner)
    governance_contract.CurrentStrategy.Nonce = governance_contract.PendingStrategy.Nonce
    ProposedStrategy.APYPredicted - ProposedStrategy.APYNow > governance_contract.MinimumAPYIncrease
    sp = governance_contract.submitStrategy(ProposedStrategy, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert governance_contract.CurrentStrategy.Nonce != governance_contract.PendingStrategy.Nonce


# def test_addGuard(governance_contract):
#     pass

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


