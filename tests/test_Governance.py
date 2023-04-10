import time
from datetime import datetime, timedelta

import ape

import pytest
from  pytest import raises

MAX_POOLS = 5 # Must match Dynamo4626

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ADAPTER_A_ADDRESS = "0x000000000000000000000000000000000000000a"
ADAPTER_B_ADDRESS = "0x000000000000000000000000000000000000000b"

WEIGHTS = [(ADAPTER_A_ADDRESS, 100),(ADAPTER_B_ADDRESS, 1000), [ZERO_ADDRESS,0], [ZERO_ADDRESS,0], [ZERO_ADDRESS,0]]
WEIGHTSTWO = [(ADAPTER_A_ADDRESS, 150),(ADAPTER_B_ADDRESS, 1500), [ZERO_ADDRESS,0], [ZERO_ADDRESS,0], [ZERO_ADDRESS,0]]

MIN_PROPOSER_PAYOUT = 0

APYNOW = 5
APYNOWTWO = 6
APYPREDICTED = 10
APYPREDICTEDTWO = 12
BADAPYPREDICTED = 3
NONCE = 1
VOTE_COUNT = 6

NAME = "Biglab"
SYMBOL = "BL"
DECIMALS = 32
#ERC20ASSET = "0x0000000000000000000000000000000000000123"
POOLS = [] 


@pytest.fixture
def owner(project, accounts):
    owner = accounts[0]
    return owner

@pytest.fixture
def dai(project, owner, accounts):
    ua = owner.deploy(project.ERC20, "DAI", "DAI", 18, 0, owner)
    return ua


@pytest.fixture
def funds_alloc(project, owner):
    f = owner.deploy(project.FundsAllocator)
    return f

# @pytest.fixture
# def pool_adapterA(project, owner, dai):
#     wdai = owner.deploy(project.ERC20, "aWDAI", "aWDAI", 18, 0, owner)
#     a = owner.deploy(project.MockLPAdapter, dai, wdai)
#     return a


# @pytest.fixture
# def pool_adapterB(project, owner, dai):
#     wdai = owner.deploy(project.ERC20, "bWDAI", "bWDAI", 18, 0, owner)
#     b = owner.deploy(project.MockLPAdapter, dai, wdai)
#     return b


# @pytest.fixture
# def pool_adapterC(project, owner, dai):
#     wdai = owner.deploy(project.ERC20, "cWDAI", "cWDAI", 18, 0, owner)
#     c = owner.deploy(project.MockLPAdapter, dai, wdai)
#     return c  


# @pytest.fixture
# def pools(pool_adapterA, pool_adapterB, pool_adapterC):
#     return [pool_adapterA, pool_adapterB, pool_adapterC]


@pytest.fixture
def governance_contract(owner, project, accounts):

    owner, operator, someoneelse, someone, newcontract, currentvault = accounts[:6]

    # deploy the contract with the initial value as a constructor argument

    gcontract = owner.deploy(project.Governance, owner, 21600)

    return gcontract  


# def add_adapters_to_vault(vault, owner, pools):
#     for pool in pools:
#         vault.add_pool(pool, sender=owner)


@pytest.fixture
def vault_contract_one(governance_contract, owner, project, accounts, dai, funds_alloc):

    owner, operator, someoneelse, someone, newcontract, currentvault, currentgovernance = accounts[:7]

    vcontractone = owner.deploy(project.Dynamo4626, NAME, SYMBOL, DECIMALS, dai, POOLS, governance_contract, funds_alloc)

    return vcontractone

@pytest.fixture
def vault_contract_two(governance_contract, owner, project, accounts, dai, funds_alloc):

    owner, operator, someoneelse, someone, newcontract, currentvault, currentgovernance = accounts[:7]

    vcontracttwo = owner.deploy(project.Dynamo4626, NAME, SYMBOL, DECIMALS, dai, POOLS, governance_contract, funds_alloc)

    return vcontracttwo

@pytest.fixture
def vault_contract_three(governance_contract, owner, project, accounts, dai, funds_alloc):

    owner, operator, someoneelse, someone, newcontract, currentvault, currentgovernance = accounts[:7]

    vcontractthree = owner.deploy(project.Dynamo4626, NAME, SYMBOL, DECIMALS, dai, POOLS, governance_contract, funds_alloc)

    return vcontractthree

@pytest.fixture
def vault_contract_four(governance_contract, owner, project, accounts, dai, funds_alloc):

    owner, operator, someoneelse, someone, newcontract, currentvault, currentgovernance = accounts[:7]

    vcontractfour = owner.deploy(project.Dynamo4626, NAME, SYMBOL, DECIMALS, dai, POOLS, governance_contract, funds_alloc)

    return vcontractfour



def test_submitStrategy(governance_contract, vault_contract_one, accounts, owner):
    ProposedStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)
    BadStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, BADAPYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]

    #Test if i can submit strategy with zero guards
    with ape.reverts():
        governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    print("Current timestamp %s" % datetime.fromtimestamp(ape.chain.pending_timestamp))


    #Submit a strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1
    assert [x for x in logs[0].strategy[2]] == [tuple(w) for w in WEIGHTS]
    assert logs[0].strategy[3] == MIN_PROPOSER_PAYOUT
    assert logs[0].strategy[4] == APYNOW
    assert logs[0].strategy[5] == APYPREDICTED

    print("Current timestamp %s" % datetime.fromtimestamp(ape.chain.pending_timestamp))
    print("TDelay %s" % datetime.fromtimestamp(int(governance_contract.TDelay())) )

    tdelay = int((int(governance_contract.TDelay()) * 1.25))

    print("Expire time %s " % datetime.fromtimestamp(int(ape.chain.pending_timestamp) + tdelay) )


    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = NONCE

    #Test if i can submit a strategy while there is pending strategy
    with ape.reverts():
        governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)

    #Test if i can submit a strategy where the APY does not increase
    with ape.reverts():
        governance_contract.submitStrategy(BadStrategy, vault_contract_one, sender=owner)

    print("Current timestamp %s" % datetime.fromtimestamp(ape.chain.pending_timestamp))



def test_withdrawStrategy(governance_contract, vault_contract_one, accounts):
    ProposedStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    #Submit a strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    #Test if i can withdraw strategy when nonce doesn't match
    with ape.reverts():
        ws = governance_contract.withdrawStrategy(2, vault_contract_one, sender=owner)

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = NONCE

    #Test if i can withdraw strategy when i am not eligible
    with ape.reverts():
        ws = governance_contract.withdrawStrategy(NONCE, vault_contract_one, sender=someone)

    print("Current timestamp %s" % datetime.fromtimestamp(ape.chain.pending_timestamp))

    #Withdraw Strategy
    ws = governance_contract.withdrawStrategy(NONCE, vault_contract_one, sender=owner)
    logs = list(ws.decode_logs(governance_contract.StrategyWithdrawal))
    assert len(logs) == 1
    assert logs[0].Nonce == NONCE

    current_time = datetime.fromtimestamp(ape.chain.pending_timestamp)
    print("Current timestamp %s" % current_time)
    current_time += timedelta(days=1)
    ape.chain.pending_timestamp = int(current_time.timestamp())

    #Submit a second Strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    print("Current timestamp %s" % datetime.fromtimestamp(ape.chain.pending_timestamp))

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = 2

    #Endorse the strategy
    es = governance_contract.endorseStrategy(2, vault_contract_one, sender=someone)
    logs = list(es.decode_logs(governance_contract.StrategyVote))

    #Activate the startegy
    acs = governance_contract.activateStrategy(2, vault_contract_one, sender=owner)
    logs = list(acs.decode_logs(governance_contract.StrategyActivation))
    assert len(logs) == 1
    assert [x for x in logs[0].strategy[2]] == [tuple(w) for w in WEIGHTS]
    assert logs[0].strategy[3] == MIN_PROPOSER_PAYOUT
    assert logs[0].strategy[4] == APYNOW
    assert logs[0].strategy[5] == APYPREDICTED

    #Test if i can withdraw strategy when its already activated
    with ape.reverts():
        governance_contract.withdrawStrategy(2, vault_contract_one, sender=owner)



def test_endorseStrategy(governance_contract, vault_contract_one, accounts):
    ProposedStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    #Submit a Strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    #Test to see if we can endorse strategy when Nonce doesn't match
    with ape.reverts():
        es = governance_contract.endorseStrategy(2, vault_contract_one, sender=someone)

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = NONCE

    #Test to see if we can vote while not being a guard
    with ape.reverts():
        es = governance_contract.endorseStrategy(NONCE, vault_contract_one, sender=owner)

    #Vote to Endorse Strategy
    es = governance_contract.endorseStrategy(NONCE, vault_contract_one, sender=someone)
    logs = list(es.decode_logs(governance_contract.StrategyVote))
    assert len(logs) == 1
    assert logs[0].Nonce == NONCE
    assert logs[0].GuardAddress == someone
    assert logs[0].Endorse == False

    #Test to see if i can vote again
    with ape.reverts():
        es = governance_contract.endorseStrategy(NONCE, vault_contract_one, sender=someone)

    #Activate Strategy
    acs = governance_contract.activateStrategy(NONCE, vault_contract_one, sender=owner)
    logs = list(acs.decode_logs(governance_contract.StrategyActivation))
    assert len(logs) == 1

    #Add another guard
    governance_contract.addGuard(someoneelse, sender=owner)

    #Test to see if we can endorse strategy after its already activated
    with ape.reverts():
        es = governance_contract.endorseStrategy(NONCE, vault_contract_one, sender=someoneelse)

    #Test to see if we can reject strategy after its already activated
    with ape.reverts():
        rs = governance_contract.rejectStrategy(NONCE, vault_contract_one, sender=someoneelse)



def test_rejectStrategy(governance_contract, vault_contract_one, accounts):
    pytest.skip("Try later.")

    ProposedStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    #Submit a Strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    #Test to see if we can reject strategy when Nonce doesn't match
    with ape.reverts():
        rs = governance_contract.rejectStrategy(2, vault_contract_one, sender=someone)

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = NONCE

    #Check to see if we can vote while not being a guard
    with ape.reverts():
        rs = governance_contract.rejectStrategy(NONCE, vault_contract_one, sender=owner)
    
    #Vote to Reject Strategy
    rs = governance_contract.rejectStrategy(NONCE, vault_contract_one, sender=someone)
    logs = list(rs.decode_logs(governance_contract.StrategyVote))
    assert len(logs) == 1
    assert logs[0].Nonce == NONCE
    assert logs[0].GuardAddress == someone
    assert logs[0].Endorse == True

    #Test to see if i can vote again
    with ape.reverts():
        rs = governance_contract.rejectStrategy(NONCE, vault_contract_one, sender=someone)



def test_activateStrategy(governance_contract, vault_contract_one, accounts):
    ProposedStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)
    owner, operator, someoneelse, someone = accounts[:4]

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    #Submit a Strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)
    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = NONCE

    #Endorse the strategy
    es = governance_contract.endorseStrategy(NONCE, vault_contract_one, sender=someone)
    logs = list(es.decode_logs(governance_contract.StrategyVote))

    #Activate the startegy
    acs = governance_contract.activateStrategy(NONCE, vault_contract_one, sender=owner)
    logs = list(acs.decode_logs(governance_contract.StrategyActivation))
    assert len(logs) == 1
    assert [x for x in logs[0].strategy[2]] == [tuple(w) for w in WEIGHTS]
    assert logs[0].strategy[3] == MIN_PROPOSER_PAYOUT
    assert logs[0].strategy[4] == APYNOW
    assert logs[0].strategy[5] == APYPREDICTED

    #Submit another Strategy
    governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = 2

    #Endorse the second strategy
    es = governance_contract.endorseStrategy(2, vault_contract_one, sender=someone)

    #Test if i can activate strategy with wrong nonce
    with ape.reverts():
        acs = governance_contract.activateStrategy(3, vault_contract_one, sender=owner)

    ws = governance_contract.withdrawStrategy(2, vault_contract_one, sender=owner)

    #Test if i can activate strategy when its withdrawn
    with ape.reverts():
        acs = governance_contract.activateStrategy(2, vault_contract_one, sender=owner)
 


def test_addGuard(governance_contract, vault_contract_one, accounts):
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



def test_removeGuard(governance_contract, vault_contract_one, accounts):
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



def test_swapGuard(governance_contract, vault_contract_one, accounts):
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



def test_replaceGovernance(governance_contract, vault_contract_one, accounts):
    owner, operator, someoneelse, someone, newcontract = accounts[:5]

    #Test if i can replace governance when there are no guards
    with ape.reverts():
        governance_contract.replaceGovernance(newcontract, vault_contract_one, sender=owner)

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    #Test if i can replace governance if sender is not in list of guards
    with ape.reverts():
        governance_contract.replaceGovernance(newcontract, vault_contract_one, sender=owner)

    #Test if i can replace governance with self
    with ape.reverts():
        governance_contract.replaceGovernance(governance_contract, vault_contract_one, sender=someone)

    #Test if i can replace governance with invalid address
    with ape.reverts():
        governance_contract.replaceGovernance(ZERO_ADDRESS, vault_contract_one, sender=someone)

    #Test if replace governance logs new vote
    rg = governance_contract.replaceGovernance(newcontract, vault_contract_one, sender=someone)
    logs = list(rg.decode_logs(governance_contract.VoteForNewGovernance))
    assert len(logs) == 1
    assert logs[0].NewGovernance == newcontract

    logs = list(rg.decode_logs(governance_contract.GovernanceContractChanged))
    assert len(logs) == 1
    assert logs[0].Voter == someone
    assert logs[0].NewGovernance == newcontract

    #Test if VoteCount increases correctly
    assert logs[0].VoteCount == 1
    assert logs[0].TotalGuards == 1



def test_addVault(governance_contract, vault_contract_one, vault_contract_two, vault_contract_three, vault_contract_four, accounts):
    owner, operator, someoneelse, someone, newcontract = accounts[:5]

    #Test if i can add a vault as someone who is not the contract owner.
    with ape.reverts():
        av = governance_contract.addVault(vault_contract_one, sender=someone)
    
    #Test if i can add vault.
    av = governance_contract.addVault(vault_contract_one, sender=owner)
    logs = list(av.decode_logs(governance_contract.NewVault))
    assert len(logs) == 1
    assert logs[0].vault == vault_contract_one

    #Test if i can add the same vault again.
    with ape.reverts():
        av = governance_contract.addVault(vault_contract_one, sender=owner)

    #Test if i can add a ZERO_ADDRESS.
    with ape.reverts():
        av = governance_contract.addVault(ZERO_ADDRESS, sender=owner)

    av = governance_contract.addVault(vault_contract_two, sender=owner)

    av = governance_contract.addVault(vault_contract_three, sender=owner)

    #Test if i can add a vault when len(VaultList) = MAX_VAULTS
    with ape.reverts():
        av = governance_contract.addVault(vault_contract_four, sender=owner)



def test_removeVault(governance_contract, vault_contract_one, vault_contract_two, vault_contract_three, vault_contract_four, accounts):
    owner, operator, someoneelse, someone, newcontract = accounts[:5]

    #Test to see if i can remove a vault when there are no vaults.
    with ape.reverts():
        rv = governance_contract.removeVault(vault_contract_one, sender=owner)

    # Now add a Vault.        
    governance_contract.addVault(vault_contract_one, sender=owner)

    #Test if i can remove a vault as someone who is not the contract owner.
    with ape.reverts():
        rv = governance_contract.removeVault(vault_contract_one, sender=someone)

    #Test to see if i can remove a vault thats not in list of vaults.
    with ape.reverts():
        rv = governance_contract.removeVault(vault_contract_two, sender=owner)

    #Test if i can remove a Vault.
    rv = governance_contract.removeVault(vault_contract_one, sender=owner)    
    logs = list(rv.decode_logs(governance_contract.VaultRemoved))
    assert len(logs) == 1
    assert logs[0].vault == vault_contract_one



def test_swapVault(governance_contract, vault_contract_one, vault_contract_two, vault_contract_three, vault_contract_four, accounts):
    owner, operator, someoneelse, someone, newcontract = accounts[:5]

    #Test if i can swap out a vault that is not on the list of vaults.
    with ape.reverts():
        sv = governance_contract.swapVault(vault_contract_one, vault_contract_two, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)

    #Test if i can swap a vault as someone who is not the contract owner.
    with ape.reverts():
        sv = governance_contract.swapVault(vault_contract_one, vault_contract_two, sender=someoneelse)

    #Test if i can add a ZERO_ADDRESS.
    with ape.reverts():
        sv = governance_contract.swapVault(vault_contract_one, ZERO_ADDRESS, sender=owner)

    governance_contract.addVault(vault_contract_two, sender=owner)

    #Test if i can swap in a vault thats already on the list of vaults.
    with ape.reverts():
        sv = governance_contract.swapVault(vault_contract_one, vault_contract_two, sender=owner)

    #Test if i can swap vault.
    sv = governance_contract.swapVault(vault_contract_one, vault_contract_three, sender=owner)
    logs = list(sv.decode_logs(governance_contract.VaultSwap))
    assert len(logs) == 1
    assert logs[0].OldVaultAddress == vault_contract_one
    assert logs[0].NewVaultAddress == vault_contract_three



def test_activateMultipleStrategies(governance_contract, vault_contract_one, vault_contract_two, accounts):
    ProposedStrategy = (WEIGHTS, MIN_PROPOSER_PAYOUT, APYNOW, APYPREDICTED)
    ProposedStrategyTwo = (WEIGHTSTWO, MIN_PROPOSER_PAYOUT, APYNOWTWO, APYPREDICTEDTWO)
    owner, operator, someoneelse, someone = accounts[:4]

    assert vault_contract_one != vault_contract_two, "Vaults seem to be the same."

    #Add a guard
    governance_contract.addGuard(someone, sender=owner)

    governance_contract.addVault(vault_contract_one, sender=owner)
    governance_contract.addVault(vault_contract_two, sender=owner)    

    #Submit a Strategy
    sp = governance_contract.submitStrategy(ProposedStrategy, vault_contract_one, sender=owner)

    print("Got here 1!")

    logs = list(sp.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    print("Got here 2!")

    # governance_contract.PendingStrategyByVault[vault_contract_one].Nonce = NONCE

    #Endorse the strategy
    es = governance_contract.endorseStrategy(NONCE, vault_contract_one, sender=someone)

    print("Got here 3!")

    logs = list(es.decode_logs(governance_contract.StrategyVote))

    print("Got here 4!")

    #Activate the strategy
    acs = governance_contract.activateStrategy(NONCE, vault_contract_one, sender=owner)

    print("Got here 5!")

    logs = list(acs.decode_logs(governance_contract.StrategyActivation))
    assert len(logs) == 1
    assert [x for x in logs[0].strategy[2]] == [tuple(w) for w in WEIGHTS]
    assert logs[0].strategy[3] == MIN_PROPOSER_PAYOUT
    assert logs[0].strategy[4] == APYNOW
    assert logs[0].strategy[5] == APYPREDICTED

    print("Got here 6!")

    #Submit another Strategy
    sq = governance_contract.submitStrategy(ProposedStrategyTwo, vault_contract_two, sender=owner)

    print("Got here 7!")    

    logs = list(sq.decode_logs(governance_contract.StrategyProposal))
    assert len(logs) == 1

    print("Got here 8!")

    # governance_contract.PendingStrategyByVault[vault_contract_two].Nonce = NONCE

    #Endorse the second strategy
    eq = governance_contract.endorseStrategy(NONCE, vault_contract_two, sender=someone)

    print("Got here 9!")    


    logs = list(eq.decode_logs(governance_contract.StrategyVote))

    print("Got here 10!")

    #Activate the second strategy
    acq = governance_contract.activateStrategy(NONCE, vault_contract_two, sender=owner)
    logs = list(acq.decode_logs(governance_contract.StrategyActivation))
    assert len(logs) == 1
    assert [x for x in logs[0].strategy[2]] == [tuple(w) for w in WEIGHTSTWO]
    assert logs[0].strategy[3] == MIN_PROPOSER_PAYOUT
    assert logs[0].strategy[4] == APYNOWTWO
    assert logs[0].strategy[5] == APYPREDICTEDTWO
    
    #Check to see if strategies have correct values
    gc_one = governance_contract.CurrentStrategyByVault(vault_contract_one)
    gc_two = governance_contract.CurrentStrategyByVault(vault_contract_two)

    assert [(x[0].lower(),x[1]) for x in gc_one.LPRatios] == [tuple(w) for w in WEIGHTS]
    assert gc_one.APYNow == APYNOW
    assert gc_one.APYPredicted == APYPREDICTED
    assert [(x[0].lower(),x[1]) for x in gc_two.LPRatios] == [tuple(w) for w in WEIGHTSTWO]
    assert gc_two.APYNow == APYNOWTWO
    assert gc_two.APYPredicted == APYPREDICTEDTWO
