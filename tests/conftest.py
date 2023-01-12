import pytest
from ape import chain

@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[0]


def is_not_hard_hat():
    try:
        print("Current chain id is: %s." % chain.chain_id)
        return chain.chain_id!=1
    except ape.exceptions.ProviderNotConnectedError:
        print("Alert: Not connected to a chain.")
        return True


# @pytest.fixture(scope="session")
# def receiver(accounts):
#     return accounts[1]


# # @pytest.fixture(scope="session")
# # def ProposedStrategy()


# @pytest.fixture(scope="session")
# def token(owner, project):
#     return owner.deploy(project.Token)


# @pytest.fixture(scope="session")
# def ZERO_ADDRESS() -> str:
#     """
#     Zero / Null Address
#     https://consensys.github.io/smart-contract-best-practices/development-recommendations/token-specific/zero-address/

#     Returns:
#         "0x0000000000000000000000000000000000000000"
#     """
#     return "0x0000000000000000000000000000000000000000"


  
    