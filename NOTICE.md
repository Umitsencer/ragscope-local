# Third-party data and attribution

This project uses pinned copies of public research data for local analysis. Raw copies under `data/raw/` are excluded from the prospective project repository by `.gitignore`; exclusion is a distribution choice, not a statement that copying or reuse is unrestricted.

## MITRE ATT&CK

Source: [MITRE ATT&CK STIX data](https://github.com/mitre-attack/attack-stix-data), Enterprise ATT&CK 19.2. Commit and file hash: [`data/sources.lock.json`](data/sources.lock.json). The source's [`LICENSE.txt`](https://github.com/mitre-attack/attack-stix-data/blob/6cda5ad8462c79e14fbb872f4e09059b18e0cfc4/LICENSE.txt) permits research, development and commercial use provided copies reproduce MITRE's copyright designation and license.

“© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation.”

The MITRE Corporation (MITRE) hereby grants you a non-exclusive, royalty-free license to use ATT&CK® for research,
development, and commercial purposes. Any copy you make for such purposes is authorized provided that you reproduce
MITRE's copyright designation and this license in any such copy.

MITRE does not claim ATT&CK enumerates all possibilities for the types of actions and behaviors documented as part of its adversary model and framework of techniques. Using the information contained within ATT&CK to address or cover full categories of techniques will not guarantee full defensive coverage as there may be undisclosed techniques or variations on existing techniques not documented by ATT&CK.

ALL DOCUMENTS AND THE INFORMATION CONTAINED THEREIN ARE PROVIDED ON AN "AS IS" BASIS AND THE CONTRIBUTOR, THE ORGANIZATION HE/SHE REPRESENTS OR IS SPONSORED BY (IF ANY), THE MITRE CORPORATION, ITS BOARD OF TRUSTEES, OFFICERS, AGENTS, AND EMPLOYEES, DISCLAIM ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTY THAT THE USE OF THE INFORMATION THEREIN WILL NOT INFRINGE ANY RIGHTS OR ANY IMPLIED WARRANTIES OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.

ATT&CK® is a registered trademark of The MITRE Corporation. This project is independent and not endorsed by MITRE.

## CTIConnect

Source: [CTIConnect](https://github.com/peng-gao-lab/CTIConnect), Cheng, Yutong; Liu, Yang; Li, Changze; Song, Dawn; Gao, Peng, *CTIConnect: A Benchmark for Retrieval-Augmented LLMs over Heterogeneous Cyber Threat Intelligence*, KDD 2026. The repository declares the `data/` directory CC BY 4.0 in [`LICENSE-DATA`](https://github.com/peng-gao-lab/CTIConnect/blob/554797d69a51147f1f98fad7198cb2d2b183d0e9/LICENSE-DATA). Our audit analyses and summaries are adaptations; cite the source and note changes when reusing them. Vendor report full texts are not included here. The dataset's own license text has an outdated “691-QA” count while its manifest reports 1,859; this discrepancy does not establish rights to third-party full texts.

Neither dataset license is the license of this project's future source code. No legal opinion or guarantee is implied.

## AnnoCTR

Source: [Bosch Research AnnoCTR](https://github.com/boschresearch/anno-ctr-lrec-coling-2024), Lange et al., *AnnoCTR: A Dataset for Detecting and Linking Entities, Tactics, and Techniques in Cyber Threat Reports*, LREC-COLING 2024. The repository states that the `AnnoCTR/` corpus is [CC BY-SA 4.0](https://github.com/boschresearch/anno-ctr-lrec-coling-2024/blob/d510b6949e1938d47c93a43eedd562dc538439dc/LICENSE.txt). We downloaded only the three MITRE-only linking splits and the license for local feasibility analysis; full report text was not downloaded. Commit and hashes are recorded in [`data/sources.lock.json`](data/sources.lock.json). Attribution and ShareAlike obligations must be respected if adapted corpus content is redistributed. This project is independent of Bosch Research and report donors.
