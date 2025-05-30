# An Empirical Study on Bug Characteristics in Solidity Smart Contracts

## Abstract
This repository contains the data collection scripts, analytical tools, and findings from our empirical study of bug characteristics in Solidity smart contracts. We analyzed 115 bug fixes from the OpenZeppelin library and other major DeFi protocols, revealing common patterns and categories of defects that occur in smart contract development.

## Repository Structure

.
├── issues_of_openzeppelin/ # OpenZeppelin issues analysis
├── PR_of_aave/ # Aave protocol pull requests analysis
├── PR_of_openzeppelin/ # OpenZeppelin pull requests analysis
├── PR_of_synthetix/ # Synthetix protocol pull requests analysis
├── PR_of_uniswap_v2/ # Uniswap v2 pull requests analysis
├── PR_of_uniswap_v3/ # Uniswap v3 pull requests analysis
├── analyze.xlsx # Aggregated analysis results
└── data.xlsx # Consolidated dataset
## Summary of Findings

Our analysis identified seven primary categories of smart contract bugs:

1. **Arithmetic Issues** (19.13%): Integer overflow/underflow and calculation errors
2. **GAS Optimization Issues** (13.91%): Inefficient code patterns leading to excessive gas consumption
3. **State Inconsistency** (12.17%): Problems maintaining contract state coherence during transactions
4. **Exception Handling Issues** (6.96%): Improper validation and error management
5. **Upgrade and Storage Conflicts** (5.22%): Complications in proxy-based upgradeable contracts
6. **Blockchain Feature Misuse** (4.35%): Incorrect assumptions about blockchain-specific mechanisms
7. **Access Control Issues** (4.35%): Flawed permission validation and privilege management

## Methodology

We employed a mixed-methods approach combining automated data collection with manual classification:

1. Extracted bug-fixing pull requests using GitHub API
2. Analyzed code changes and PR descriptions 
3. Categorized bugs based on root cause and fix implementation
4. Cross-validated findings across multiple DeFi protocols

## Citation

If using this dataset in academic research, please cite our work.

## License

MIT License
