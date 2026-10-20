"""Component registry v1 (ProspectMind Phase 2): known libraries -> ontology concepts.

Explicit and reviewable, same discipline as TOPIC_MAP: every entry is a
classification decision. A library not in this registry produces growth
candidates, never silent evidence.

Fields:
  id        stable component id (code_components.component_id)
  name      display name
  repos     GitHub owner/repo names whose contributors get CONTRIBUTOR_USAGE
  packages  {ecosystem: [package names]} for manifest (DECLARED) detection
  imports   regex fragments matched against source files for OBSERVED_USAGE
  concepts  ontology concept ids this component evidences
"""

COMPONENTS = [
    {
        "id": "lib:openzeppelin-contracts", "name": "OpenZeppelin Contracts",
        "repos": ["OpenZeppelin/openzeppelin-contracts"],
        "packages": {"npm": ["@openzeppelin/contracts", "@openzeppelin/contracts-upgradeable"]},
        "imports": [r"@openzeppelin/contracts"],
        "concepts": ["PM.SKILL.0009", "PM.KNOW.0001"],
    },
    {
        "id": "lib:ethersjs", "name": "ethers.js",
        "repos": ["ethers-io/ethers.js"],
        "packages": {"npm": ["ethers"]},
        "imports": [r"from\s+['\"]ethers['\"]", r"require\(['\"]ethers['\"]\)"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:web3js", "name": "web3.js",
        "repos": ["web3/web3.js"],
        "packages": {"npm": ["web3"]},
        "imports": [r"from\s+['\"]web3['\"]", r"require\(['\"]web3['\"]\)"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:viem", "name": "viem",
        "repos": ["wevm/viem"],
        "packages": {"npm": ["viem"]},
        "imports": [r"from\s+['\"]viem"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:chainlink", "name": "Chainlink",
        "repos": ["smartcontractkit/chainlink"],
        "packages": {"npm": ["@chainlink/contracts"]},
        "imports": [r"@chainlink/contracts", r"smartcontractkit/chainlink"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:uniswap-v3", "name": "Uniswap V3",
        "repos": ["Uniswap/v3-core", "Uniswap/v3-periphery"],
        "packages": {"npm": ["@uniswap/v3-core", "@uniswap/v3-periphery", "@uniswap/v3-sdk"]},
        "imports": [r"@uniswap/v3-"],
        "concepts": ["PM.SKILL.0009", "PM.SYS.0004"],
    },
    {
        "id": "lib:aave-v3", "name": "Aave V3",
        "repos": ["aave/aave-v3-core"],
        "packages": {"npm": ["@aave/core-v3"]},
        "imports": [r"@aave/"],
        "concepts": ["PM.SKILL.0009", "PM.SYS.0004"],
    },
    {
        "id": "lib:go-libp2p", "name": "libp2p (Go)",
        "repos": ["libp2p/go-libp2p"],
        "packages": {"go": ["github.com/libp2p/go-libp2p"]},
        "imports": [r"github\.com/libp2p/go-libp2p"],
        "concepts": ["PM.SKILL.0007"],
    },
    {
        "id": "lib:rust-libp2p", "name": "libp2p (Rust)",
        "repos": ["libp2p/rust-libp2p"],
        "packages": {"cargo": ["libp2p"]},
        "imports": [r"use\s+libp2p", r"libp2p::"],
        "concepts": ["PM.SKILL.0007"],
    },
    {
        "id": "lib:kubo", "name": "IPFS Kubo",
        "repos": ["ipfs/kubo"],
        "packages": {"go": ["github.com/ipfs/kubo"]},
        "imports": [r"github\.com/ipfs/kubo"],
        "concepts": ["PM.SKILL.0007"],
    },
    {
        "id": "lib:go-ethereum", "name": "go-ethereum (geth)",
        "repos": ["ethereum/go-ethereum"],
        "packages": {"go": ["github.com/ethereum/go-ethereum"]},
        "imports": [r"github\.com/ethereum/go-ethereum"],
        "concepts": ["PM.SKILL.0007", "PM.SKILL.0004", "PM.SYS.0003"],
    },
    {
        "id": "lib:cosmos-sdk", "name": "Cosmos SDK",
        "repos": ["cosmos/cosmos-sdk"],
        "packages": {"go": ["github.com/cosmos/cosmos-sdk"]},
        "imports": [r"github\.com/cosmos/cosmos-sdk"],
        "concepts": ["PM.SKILL.0011", "PM.SKILL.0007", "PM.SYS.0003"],
    },
    {
        "id": "lib:cometbft", "name": "CometBFT (Tendermint)",
        "repos": ["cometbft/cometbft", "tendermint/tendermint"],
        "packages": {"go": ["github.com/cometbft/cometbft", "github.com/tendermint/tendermint"]},
        "imports": [r"github\.com/(cometbft|tendermint)/"],
        "concepts": ["PM.SKILL.0011", "PM.SYS.0003"],
    },
    {
        "id": "lib:lighthouse", "name": "Lighthouse (Eth consensus)",
        "repos": ["sigp/lighthouse"],
        "packages": {"cargo": []},
        "imports": [],
        "concepts": ["PM.SKILL.0011", "PM.SKILL.0003", "PM.SYS.0003"],
    },
    {
        "id": "lib:prysm", "name": "Prysm (Eth consensus)",
        "repos": ["prysmaticlabs/prysm"],
        "packages": {"go": []},
        "imports": [],
        "concepts": ["PM.SKILL.0011", "PM.SKILL.0004", "PM.SYS.0003"],
    },
    {
        "id": "lib:substrate", "name": "Substrate / Polkadot SDK",
        "repos": ["paritytech/polkadot-sdk", "paritytech/substrate"],
        "packages": {"cargo": ["sp-core", "frame-system", "pallet-balances"]},
        "imports": [r"use\s+frame_", r"sp_core::"],
        "concepts": ["PM.SKILL.0011", "PM.SKILL.0003", "PM.SYS.0003"],
    },
    {
        "id": "lib:tokio", "name": "Tokio",
        "repos": ["tokio-rs/tokio"],
        "packages": {"cargo": ["tokio"]},
        "imports": [r"use\s+tokio", r"#\[tokio::"],
        "concepts": ["PM.SKILL.0003"],
    },
    {
        "id": "lib:ethers-rs", "name": "ethers-rs",
        "repos": ["gakonst/ethers-rs"],
        "packages": {"cargo": ["ethers"]},
        "imports": [r"use\s+ethers", r"ethers::"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:alloy", "name": "Alloy",
        "repos": ["alloy-rs/alloy"],
        "packages": {"cargo": ["alloy"]},
        "imports": [r"use\s+alloy", r"alloy::"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:revm", "name": "revm",
        "repos": ["bluealloy/revm"],
        "packages": {"cargo": ["revm"]},
        "imports": [r"use\s+revm", r"revm::"],
        "concepts": ["PM.SKILL.0009"],
    },
    {
        "id": "lib:circom", "name": "Circom",
        "repos": ["iden3/circom"],
        "packages": {"npm": []},
        "imports": [],
        "concepts": ["PM.SKILL.0010"],
    },
    {
        "id": "lib:snarkjs", "name": "snarkjs",
        "repos": ["iden3/snarkjs"],
        "packages": {"npm": ["snarkjs"]},
        "imports": [r"snarkjs"],
        "concepts": ["PM.SKILL.0010"],
    },
    {
        "id": "lib:halo2", "name": "Halo2",
        "repos": ["zcash/halo2"],
        "packages": {"cargo": ["halo2_proofs", "halo2_gadgets"]},
        "imports": [r"use\s+halo2_"],
        "concepts": ["PM.SKILL.0010", "PM.KNOW.0002"],
    },
    {
        "id": "lib:prisma", "name": "Prisma",
        "repos": ["prisma/prisma"],
        "packages": {"npm": ["prisma", "@prisma/client"]},
        "imports": [r"@prisma/client"],
        "concepts": ["PM.SKILL.0008"],
    },
    {
        "id": "lib:sqlx", "name": "SQLx",
        "repos": ["launchbadge/sqlx"],
        "packages": {"cargo": ["sqlx"]},
        "imports": [r"use\s+sqlx", r"sqlx::"],
        "concepts": ["PM.SKILL.0008"],
    },
]

BY_REPO = {}
for comp in COMPONENTS:
    for repo in comp["repos"]:
        BY_REPO[repo.lower()] = comp

BY_ID = {c["id"]: c for c in COMPONENTS}
