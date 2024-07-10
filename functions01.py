import os
from dotenv import load_dotenv
from web3 import Web3, HTTPProvider

# Load environment variables from .env file
load_dotenv()

# Retrieve API keys from environment variables
api_key = os.getenv('ALCHEMY_KEY')

w3 = Web3(HTTPProvider(f"https://base-mainnet.g.alchemy.com/v2/{api_key}")) # BASE

def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero!")
    return a / b

# Function to query any smart contract function
def query_smart_contract(w3, contract_address, abi, function_name, *args, block_number=None):
    """
    Query a smart contract function.

    :param w3: Web3 instance
    :param contract_address: Address of the smart contract
    :param abi: ABI of the smart contract
    :param function_name: Name of the function to query
    :param args: Arguments to pass to the function (if any)
    :param block_number: Specific block number to query (optional)
    :return: Result of the function call or an error message
    """
    try:
        # Create contract instance
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=abi)
        
        # Get the contract function
        contract_function = getattr(contract.functions, function_name)
        
        # Call the function with arguments and block identifier if provided
        if block_number is not None:
            data = contract_function(*args).call(block_identifier=int(block_number))
        else:
            data = contract_function(*args).call()
        
        return data
    
    except Exception as e:
        return f'Error querying smart contract: {e}'


def get_arcadia_account_data(account_address, block=w3.eth.block_number):
    try:
        # Pool contract
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(account_address), #0xb2DF87b16682435bdf29494fEA44dF5374F22f3E
            abi=[{
        "inputs": [],
        "name": "generateAssetData",
        "outputs": [
            {
                "internalType": "address[]",
                "name": "assetAddresses",
                "type": "address[]",
            },
            {"internalType": "uint256[]", "name": "assetIds", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "assetAmounts", "type": "uint256[]"},
        ],
        "stateMutability": "view",
        "type": "function",
    }]
        )
        data = contract.functions.generateAssetData().call(block_identifier=int(block))
        return data
    except Exception as e:
        return f'Error fetching pool_oracle: {e}'

