---
weight: 65
title: Deep mutational scanning
description: ASAP deep mutational scanning (DMS) data
toc: true
draft: false
---

**Deep mutational scanning (DMS)** identifies which mutations in a target are functionally tolerated, and could therefore lead to resistance if they abrogate binding of an antiviral. ASAP uses DMS to find binding sites that are intolerant to mutation, so that inhibitors developed against them are resistance-resilient.

### Zika virus NS2B-NS3 protease

Deep mutational scanning of ZIKV NS2B-NS3 protease, carried out alongside crystallographic fragment screening to identify mutation-intolerant binding sites.

* [Crystallographic fragment screening and deep mutational scanning of Zika virus NS2B-NS3 protease enable development of resistance-resilient inhibitors](https://doi.org/10.1101/2024.04.29.591502) — bioRxiv preprint
* [Fitness dataset](https://github.com/jbloomlab/ZIKV_DMS_NS3_EvansLab/tree/master) — DMS performed by the Evans lab, analyzed by the Bloom lab (posted 2023-11-01)

### Zika virus NS5 RNA-dependent RNA polymerase

Deep mutational scanning across the ZIKV NS5 RdRp to map which positions tolerate mutation.

* [Fitness dataset](https://github.com/jbloomlab/ZIKV_DMS_NS5_EvansLab/blob/main/results/all_tiles/alltiles_host_adaptation.csv) — DMS performed by the Evans lab, analyzed by the Bloom lab (posted 2024-04-01)

### Tools for exploring DMS data

* [choppa](https://github.com/asapdiscovery/choppa) — Python library for visualizing DMS and other fitness data directly onto protein structures ([documentation](https://choppa.readthedocs.io))

See also the [analysis of circulating variants](/outputs/circulating-variants), which uses natural sequence variation to assess functional tolerance to mutation.
