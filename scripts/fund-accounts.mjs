import { createTestClient, http, publicActions, walletActions, parseUnits, parseEther } from 'viem'
import { hardhat } from 'viem/chains'

const client = createTestClient({
  chain: hardhat,
  mode: 'hardhat',
  transport: http(),
})
  .extend(publicActions)
  .extend(walletActions)

const mainnetAddresses = [
  {
    name: 'USDC',
    address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
    source: '0xA4FfD041A475Cac56cA845e4811c014b619fCE5a',
    decimals: 6,
  },
  {
    name: 'DAI',
    address: '0x6B175474E89094C44Da98b954EedeAC495271d0F',
    source: '0x6FF8E4DB500cBd77d1D181B8908E022E29e0Ec4A',
    decimals: 18,
  },
  {
    name: 'USDT',
    address: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
    source: '0xe0755f3A9A1714eeE8fe7A540f20eEac6117787C',
    decimals: 6,
  },
]

const dynamoWhale = '0xc89D42189f0450C2b2c3c61f58Ec5d628176A1E7'

async function impersonateAndTransfer({ address, source, decimals = 18 }) {
  await client.setBalance({
    address: source,
    value: parseEther('1'),
  })

  await client.impersonateAccount({
    address: source,
  })

  const isUSDT = address === '0xdAC17F958D2ee523a2206206994597C13D831ec7'

  const { request } = await client.simulateContract({
    address,
    abi: [
      {
        inputs: [
          {
            internalType: 'address',
            name: 'recipient',
            type: 'address',
          },
          {
            internalType: 'uint256',
            name: 'amount',
            type: 'uint256',
          },
        ],
        name: 'transfer',
        outputs: isUSDT
          ? []
          : [
              {
                internalType: 'bool',
                name: '',
                type: 'bool',
              },
            ],
        stateMutability: 'nonpayable',
        type: 'function',
      },
    ],
    functionName: 'transfer',
    args: [dynamoWhale, parseUnits('100000', decimals)],
    account: source,
    chain: hardhat,
  })

  const transaction = await client.waitForTransactionReceipt({
    hash: await client.writeContract(request),
  })

  console.log(transaction)
}

async function main() {
  for (const token of mainnetAddresses) {
    console.log(`Transferring ${token.name}...`)
    await impersonateAndTransfer(token)
  }
}

main()
  .then(() => process.exit())
  .catch(error => {
    console.error(error)
    process.exit(1)
  })
