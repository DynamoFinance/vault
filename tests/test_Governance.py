from ast import operator
from lib2to3.pgen2 import token
from eth_utils import get_logger
import pytest
import brownie
from brownie import web3, chain, accounts
from brownie import compile_source, web3, chain
from eth_account.messages import encode_structured_data
from eth_account import Account
from brownie import Contract 

SOMEONE_TOKEN_IDS = [1, 2, 3, 4, 5, 6, 7, 8 ,9, 10]
OPERATOR_TOKEN_ID = 11
NEW_TOKEN_ID = 20
INVALID_TOKEN_ID = 99
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ERC165_INTERFACE_ID = (
    "0x0000000000000000000000000000000000000000000000000000000001ffc9a7"
)
Governance_INTERFACE_ID = (
    "0x0000000000000000000000000000000000000000000000000000000080ac58cd"
)
INVALID_INTERFACE_ID = (
    "0x0000000000000000000000000000000000000000000000000000000012345678"
)
GAS_PRICE = 3
GWEI_MULTIPLIER = 10000000000
GAS_PRICE_GWEI = GAS_PRICE * GWEI_MULTIPLIER

TOKEN_NAME_ERC721 = "Lootbox"
TOKEN_SYMBOL_ERC721 = "LOOTBOX"
TOKEN_DECIMALS = 8
TOKEN_INITIAL_SUPPLY = 100000
TOKEN_NAME = "Lootbox"
TOKEN_SYMBOL = "LOOTBOK"
PREFIX_URI = "https://cryptocoven.xyz/api/favors/sirens-shell?tokenId="
SUFFIX_URI = "siren"

MAX_SUPPLY = 2000

def chain_id():
    # BUG: ganache-cli provides mismatching chain.id and chainid()
    # https://github.com/trufflesuite/ganache/issues/1643
    return 1 if web3.clientVersion.startswith("EthereumJS") else chain.id



@pytest.fixture
def governance_contract(Governance, accounts):
    brownie.network.gas_price(GAS_PRICE_GWEI)

    someone, operator, someoneelse, owner = accounts[:4]

    # deploy the contract with the initial value as a constructor argument
    #contract = accounts[0].deploy(
    contract = operator.deploy(
        Governance,
        operator
    )

    contract.addGuard(someone, {"from": operator})

    contract.addGuard(someoneelse, {"from": operator})

    # contract.releaseForTransfer({"from": operator})

    return contract


def test_addGuard(governance_contract):
    assert governance_contract.contractOwner(operator) 


def test_removeGuard(governance_contract):


def test_swapGuard(governance_contract):

def test_activateStrategy(governance_contract):

def test_endorseStrategy(governance_contract):

def test_rejectStrategy(governance_contract):

def test_submitStrategy(governance_contract):

def test_withdrawStrategy(governance_contract):



