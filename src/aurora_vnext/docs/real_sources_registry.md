# Aurora OSI vNext — Real-World Ground Truth Source Registry
## Phase Y §Y.5

This registry documents the external real-world geological sources approved
for use in Aurora ground-truth calibration. All sources listed here are
publicly available or accessible under open/research licensing.

**CONSTITUTIONAL RULE:** Sources in this registry are used for calibration of
future model parameters only. They do NOT modify any existing canonical scan.

---

## Source Registry

### Global / Multi-Region

| Source | Type | Coverage | Identifier | License |
|---|---|---|---|---|
| USGS Mineral Resources Data System (MRDS) | Deposit/occurrence DB | Global | https://mrdata.usgs.gov/mrds | Public domain (US Gov) |
| USGS National Geochemical Survey | Geochemical truth points | USA | https://mrdata.usgs.gov/geochem | Public domain (US Gov) |
| USGS Global Mineral Resource Assessment | Deposit assessment | Global | https://pubs.usgs.gov/sir/2010/5090 | Public domain |
| BGS World Mineral Statistics | Production history | Global | https://www.bgs.ac.uk/mineralsuk | BGS Open Data |
| WHYMAP Groundwater Resources | Hydrogeological | Global | https://www.whymap.org | CC BY 4.0 |
| OneGeology | Geological mapping | Global | https://www.onegeology.org | Consortium open data |

### Africa / Southern Africa

| Source | Type | Coverage | Identifier | License |
|---|---|---|---|---|
| South African Council for Geoscience (SACS/CGS) | Geological surveys, borehole records | South Africa | https://www.geoscience.org.za | South African Gov |
| Council for Geoscience Borehole Database | Drill intersections | South Africa | https://bgis.sanbi.org | SA Gov open data |
| BRGM Geosciences Africa | Geological surveys | West/Central Africa | https://www.brgm.fr | BRGM license |
| Geological Survey of Namibia | Occurrence/deposit | Namibia | https://www.mme.gov.na | Namibian Gov |
| Geological Survey of Botswana | Deposit records | Botswana | https://www.geology.gov.bw | Botswana Gov |
| Tanzania Geological Survey | Occurrence/deposit | Tanzania | https://www.gstz.go.tz | Tanzania Gov |
| Ethiopian Institute of Geological Survey | Deposit records | Ethiopia | https://www.eigs.gov.et | Ethiopian Gov |

### Australia / Pacific

| Source | Type | Coverage | Identifier | License |
|---|---|---|---|---|
| Geoscience Australia — OZMIN | Deposit/occurrence | Australia | https://www.ga.gov.au/scientific-topics/minerals/mineral-resources-database | CC BY 4.0 |
| Geoscience Australia — National Geochemical Survey | Geochemical | Australia | https://www.ga.gov.au/scientific-topics/minerals/geochemistry | CC BY 4.0 |
| New Zealand GNS Science | Geological surveys | New Zealand | https://www.gns.cri.nz | GNS license |

### Europe

| Source | Type | Coverage | Identifier | License |
|---|---|---|---|---|
| British Geological Survey (BGS) | Geological surveys | UK/Global | https://www.bgs.ac.uk | BGS Open Data |
| BRGM InfoTerre | Geological/borehole | France | https://infoterre.brgm.fr | BRGM license |
| Geological Survey of Finland (GTK) | Deposit/occurrence | Finland | https://www.gtk.fi | CC BY 4.0 |
| Federal Institute for Geosciences (BGR) Germany | Geological surveys | Germany/Global | https://www.bgr.bund.de | BGR license |

### Americas

| Source | Type | Coverage | Identifier | License |
|---|---|---|---|---|
| Geological Survey of Canada (GSC) — MINFILE | Deposit/occurrence | Canada | https://www.nrcan.gc.ca/mining-materials | Open Government |
| INGEMMET Peru | Deposit/occurrence | Peru | https://www.ingemmet.gob.pe | Peruvian Gov |
| CPRM Brazil | Geological surveys | Brazil | https://www.cprm.gov.br | Brazilian Gov open |
| Chilean SERNAGEOMIN | Deposit records | Chile | https://www.sernageomin.cl | Chilean Gov |

### Petroleum / Basin Systems

| Source | Type | Coverage | Identifier | License |
|---|---|---|---|---|
| USGS World Petroleum Assessment | Basin validation | Global | https://pubs.usgs.gov/dds/dds-060 | Public domain |
| IHS Markit (commercial) | Petroleum systems | Global | Commercial license required | Commercial |
| Wood Mackenzie (commercial) | Production history | Global | Commercial license required | Commercial |

---

## Ingestion Mapping

Each source above maps to Aurora's `GeologicalDataType` taxonomy:

| GeologicalDataType | Primary Sources |
|---|---|
| `deposit_occurrence` | USGS MRDS, GA OZMIN, BGS, GSC MINFILE, SACS |
| `drill_intersection` | CGS Borehole DB, GA borehole, BRGM InfoTerre |
| `geochemical_anomaly` | USGS Geochem, GA National Geochem Survey |
| `geophysical_validation` | BGS, SACS, GA geophysics |
| `production_history` | BGS World Mineral Statistics, INGEMMET, CPRM |
| `basin_validation` | USGS World Petroleum Assessment, WHYMAP |

---

## Source Addition Process

To add a new source to this registry:
1. Confirm public availability or secure appropriate data license
2. Add to registry table above with full identifier and license note
3. Create a `GroundTruthProvenance` record with `source_identifier` = URL/DOI
4. Submit for admin review before ingestion into authoritative calibration paths
5. Update `calibration_version_lineage` to reflect new source usage