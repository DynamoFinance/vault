import pytest
import ape
from tests.conftest import is_not_hard_hat

d4626_name = "DynamoDAI"
d4626_token = "dyDAI"
d4626_decimals = 18

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def trader(accounts):
    return accounts[1]

@pytest.fixture
def dai(project, deployer, trader):
    ua = deployer.deploy(project.ERC20, "DAI", "DAI", 18, 0, deployer)
    #Transfer some to trader.
    ua.mint(trader, '1000000000 Ether', sender=deployer)
    return ua

@pytest.fixture
def dynamo4626(project, deployer, dai, trader):
    v = deployer.deploy(project.Dynamo4626, d4626_name, d4626_token, d4626_decimals, dai, [])    
    return v


def test_basic_initialization(project, deployer, dynamo4626):
    assert dynamo4626.name(sender=deployer) == d4626_name
    assert dynamo4626.symbol(sender=deployer) == d4626_token
    assert dynamo4626.decimals(sender=deployer) == d4626_decimals

# def test_add_pool(project, deployer, dynamo4626, dai):

#     print("Dai total supply is %s." % dai.totalSupply())


#     result = dynamo4626.add_currency(dai, sender=deployer) 
#     assert result.return_value == True
#     #assert result == True


#     result = dynamo4626.add_currency(deployer, sender=deployer) 
#     assert result.return_value == True