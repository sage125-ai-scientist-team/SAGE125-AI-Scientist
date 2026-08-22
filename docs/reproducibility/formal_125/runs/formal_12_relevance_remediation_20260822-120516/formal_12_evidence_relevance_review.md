# Formal 12 Evidence Relevance Review

Stage A only. No model Provider calls.

## Q069: Is there a diffraction limit?

- domain: `physics`
- research object: [['diffraction limit'], ['optical microscopy', 'optical microscope'], ['optical resolution', 'microscope resolution']]
- phenomenon/relation: [['diffraction'], ['resolution limit', 'resolving power']]
- mechanism: [['Abbe', 'Abbe limit', 'Abbe diffraction'], ['super-resolution', 'superresolution', 'STED', 'PALM', 'STORM', 'SMLM'], ['Rayleigh criterion']]
- queries: ['ti:"diffraction limit" AND (all:microscopy OR all:optics)', 'all:"super-resolution microscopy" AND all:"diffraction limit"', 'all:"Abbe diffraction" AND all:microscopy']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=2

### Accepted sources

- `arxiv:0708.3336` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:2|section:page-2|paragraph:1`
  - quote: 1). However, this ability to spatially select the area of study has a physical limit, the diffraction limit. Abbe at the end of the 19 th century showed that the smallest distance that can be resolved between two lines using an opt ical microscope had a limit which is referred to commonly as the diffraction limit [4 ,5].

- `arxiv:2403.06617` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Nonlinear optical microscopy provides elegant means for label-free imaging of biological samples and condensed matter systems. The widespread areas of application could even be increased if resolution was improved, which is currently limited by the famous Abbe diffraction limit.

- `arxiv:2007.15491` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Circumventing the optical diffraction limit with customized speckles NICHOLAS BENDER ,1 MENGYUAN SUN ,2 HASAN YILMAZ ,1 JOERG BEWERSDORF ,3,4 AND HUI CAO 1,* 1 Department of Applied Physics, Yale University, New Haven CT 06520, USA 2 Department of Molecular Biophysics and Biochemistry, Yale University, New Haven CT 06520, USA 3 Department of Cell Biology, Yale University School of Medicine, New Haven CT 06520, USA 4 Department of Biomedical Engineering, Yale University, Yale University, New Have

- `arxiv:2004.13001` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Previously-proposed μas X-ray imager designs have been interferometers with limited effective collecting area. Here we describe X-ray telescopes achieving diffraction-limited performance over a wide energy band with large effective area, employing a nested-shell architecture with grazing-incidence mirrors, while matching the optical path lengths between all shells.

### Rejected sources

- `2411.00681` reason=permanent_q069_negative status=OFF_TOPIC
- `2307.15471` reason=permanent_q069_negative status=OFF_TOPIC

### Q069 old off-topic sources

- arXiv:2411.00681 status=OFF_TOPIC decision=REJECT
- arXiv:2307.15471 status=OFF_TOPIC decision=REJECT

## Q003: Are there more color pigments to discover?

- domain: `chemistry`
- research object: [['pigment', 'pigments'], ['YInMn', 'YInMn Blue'], ['chromophore']]
- phenomenon/relation: [['color', 'colour'], ['synthetic pigment']]
- mechanism: [['inorganic pigment'], ['structural color', 'structural colour']]
- queries: ['ti:pigment', 'all:pigment AND all:chromophore', 'all:"synthetic pigment"', 'all:pigment AND all:inorganic']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:2110.00410` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: The hierarchical structure of these pigments enables the deposition of coatings with angu lar independent colour, offering a consistent visual appearance across a wide range of viewing angles.

- `arxiv:1505.04752` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: We present an interdisciplinary study of the diversity and detectability of nonphotosynthetic pigments as biosignatures, which includes a description of environments that host nonphotosynthetic biologically pigmented surfaces, and a lab-based experimental analysis of the spectral and broadband color diversity of pigmented organisms on Earth.

- `arxiv:1204.4721` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:2|section:page-2|paragraph:1`
  - quote: Using a simple model whose parameters are taken from experiments, that is without any ﬁtting parameters, we calculate the optimal number of photosynthetic pigment molecules for diﬀerent complex sizes and compare these theoretical predictions with the actual number of pigments found in naturally occurring complexes.

- `arxiv:1808.01869` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Intensive discussions among members of the International Federation of Pigment Cell Societies (IFPCS), the International Pigment Cell Conference (IPCC) 1, the Society of Melanoma Research (SMR) 1, the Skin of Color Society (SOCS), and the Melanoma Prevention Working Group (MPWG) nucleated this perspective and culminated in the current status, challenges, and opportunities of respective thematic research areas (Box et al., 2018).

### Rejected sources


## Q026: Why can only some cells become other cells?

- domain: `biology`
- research object: [['stem cell', 'stem cells'], ['pluripotent'], ['cell differentiation']]
- phenomenon/relation: [['reprogramming'], ['lineage restriction'], ['differentiate']]
- mechanism: [['Yamanaka'], ['iPSC', 'induced pluripotent']]
- queries: ['all:"cell reprogramming" AND all:pluripotent', 'all:"stem cell" AND all:differentiation', 'ti:"induced pluripotent"']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:1606.03884` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: In the last section I contributed a mathematical model of cell reprogramming from intermediate steps regulations and tried to ﬁnd the critical point of pluripotent cell . 1 Introduction Basic unit of biological organisms are cells.

- `arxiv:1409.2205` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: arXiv:1409.2205v2 [q-bio.MN] 8 Dec 2014 Theoretical modelling discriminates the stochastic and de terministic hypothesis of cell reprogramming Jiawei Yan, ∗ Pu Zheng, † and Xingjie Pan ‡ How to induce diﬀerentiated cells into pluripotent cells ha s elicited researchers’ interests for a long time since pluripotent stem cells are able to oﬀer remar kable potential in numerous subﬁelds of biological research.

- `arxiv:1612.08064` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: arXiv:1612.08064v2 [q-bio.CB] 22 Sep 2017 Cell reprogramming modelled as transitions in a hierarchy of cell cycles Ryan Hannam1,*, Alessia Annibale 1,2, and Reimer K ¨ uhn1 1Department of Mathematics, Kings College London, The Stran d, London WC2R 2LS, UK 2Institute for Mathematical and Molecular Biomedicine, Kin gs College London, Hodgkin Building, London SE1 1UL, UK *ryan.hannam@kcl.ac.uk ABSTRACT We construct a model of cell reprogramming (the conversion o f fully differentiated cells to a state of pluripotency , kno wn as induced pluripotent stem cells, or iPSCs) which builds on key elements of cell biology viz.

- `arxiv:1410.2337` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: A paradigm shift occurred when Taka- hashi and Yamanaka [1] demonstrated that diﬀerentiated mouse cells can be reprogrammed to induced pluripotent stem cells (iPSC) by inducing certain factors (known as Yamanaka factors (YF): Oct4, Sox2, Klf4, and c-Myc) in the cell.

### Rejected sources


## Q013: Can we predict the next pandemic?

- domain: `medicine_and_health`
- research object: [['pandemic'], ['epidemic'], ['outbreak']]
- phenomenon/relation: [['forecast', 'forecasting'], ['predict', 'prediction']]
- mechanism: [['influenza'], ['infectious disease']]
- queries: ['ti:pandemic AND (all:forecast OR all:predict)', 'all:"epidemic forecast" AND all:influenza', 'all:"infectious disease" AND all:outbreak AND all:prediction']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:2004.11372` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Learning to Forecast and Forecasting to Learn from the COVID-19 Pandemic Ajitesh Srivastava1, Viktor K. Prasanna 1 1 Ming Hsieh Department of Electrical and Computer Enginnering, University of Southern California, Los Angeles, California, USA {ajiteshs, prasanna}@usc.edu Abstract Accurate forecasts of COVID-19 is central to resource management and building strategies to deal with the epidemic.

- `arxiv:2007.02105` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Prediction Regions for Poisson and Over-Dispersed Poisson Regression Models with Applications to Forecasting Number of Deaths during the COVID-19 Pandemic T. Kim ∗ B. Lieberman † G.

- `arxiv:2009.12176` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: COVID-19 Pandemic Prediction using Time Series Forecasting Models *Note: This paper is accepted in the 11th ICCCNT 2020 conference. The ﬁnal version of this paper will appear in the conference proceedings.

- `arxiv:2606.05513` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: EpiEvolve: Self-Evolving Agents for Streaming Pandemic Forecasting under Regime Shifts Yiming Lu1, Sihang Zeng2, Zhengxu Tang1, Max Lau1, Fei Liu1, Wei Jin1 1Emory University 2University of Washington {yiming.lu, wei.jin}@emory.edu Abstract Epidemic LLM forecasters are usually trained and evaluated as static supervised models, whereas operational pandemic forecasting is a streaming process in which labels arrive af- ter predictions and disease regimes shift over time.

### Rejected sources


## Q109: What creates the Earth’s magnetic field (and why does it move)?

- domain: `ecology`
- research object: [['Earth magnetic field', "earth's magnetic field", 'geomagnetic field'], ['geodynamo'], ['outer core']]
- phenomenon/relation: [['geomagnetic'], ['magnetic field']]
- mechanism: [['dynamo'], ['liquid-metal', 'liquid metal'], ['ionosphere']]
- queries: ['ti:geodynamo OR ti:"geomagnetic dynamo"', 'all:"Earth magnetic field" AND all:"outer core"', 'all:geomagnetic AND all:dynamo AND all:core']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:2107.06766` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: arXiv:2107.06766v3 [physics.flu-dyn] 2 Nov 2021 Helical distributed chaos in rotating turbulence and conve ction (with applications to geomagnetic dynamo) A. Bershadskii ICAR, P.O.

- `arxiv:1605.01321` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: The inﬂuence of ﬂuctuations of α -eﬀect on magnetic ﬁeld generation, its spectral propertie s, in respect to the geodynamo applications, is also discussed . Introduction Parker’s dynamo [1] equations, which can be rigorously de- rived [2] from the general mean-ﬁeld dynamo equations [3] is a good candidate for the various physical applications, starting from the galactic dy namo to the dynamos in the planets.

- `arxiv:1804.05432` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: An alternative approach is to model the geomagnetic ﬁeld as a stochastic process, and there have been many models of this type over the years [4–9]. These are usu- ally predicated on exploiting the qualitative similarity be- tween paleomagnetic data and some well-understood or easily-studied stochastic process.

- `arxiv:1912.13158` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Textbooks on the Earth’s magnetic field indicate that the subject is extremely complex1. We would like to confront such an attitude or habit with another view. We think that physics students should learn more about the geodynamo for the following reasons: •The Earth’s magnetic field belongs to a species that is widespread in the cosmos: Not only the Earth and other planets but also stars and galaxies have magnetic fields.

### Rejected sources


## Q091: Is there an upper limit to computer processing speed?

- domain: `information_science`
- research object: [['processing speed'], ['computing power'], ["Moore's law", 'Moores law', 'Moore law']]
- phenomenon/relation: [['transistor'], ['physical limit', 'fundamental limit']]
- mechanism: [['Landauer'], ['quantum computer', 'quantum computing']]
- queries: ['all:"Moore" AND all:transistor AND all:limit', 'all:Landauer AND all:computation', 'ti:"fundamental limits" AND all:computing']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:2510.12473` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:2|section:page-2|paragraph:1`
  - quote: 2 Abstract High-performance, low-power transistors are core components of advanced integrated circuits, and the ultimate limitation of Moore's law has made the search for new alternative pathways an urgent priority.

- `arxiv:1607.02612` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Submitted to Applied Physics Letters 1 Resonant optical gating of suspended carbon nanotube transistor R. McCoy,1 F. Anderson,2 E. L. Carter,1 R. L. Smith2 1Sullivan University, Louisville, KY 40205, USA 2Rio Salado College, Tempe, AZ 85281, USA Abstract: Building smaller transistors with enhan ced functionality is critical in extending the limits of Moore’s law and meeting the demands of the electronics industry.

- `arxiv:1903.03884` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: 1 Guest Editorial: A Critical Review of Recent Progress on Negative Capacitance Field- Effect Transistors Muhammad A. Alam 1), Mengwei Si 2), and Peide D. Ye 3) School of Electrical and Computer Engineering, Purdue University, West Lafayette, IN 47907, USA Corresponding authors: Muhammad A.

- `arxiv:2001.07364` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: 1 Thickness-Controlled Black Phosphorus Tunnel Field-Effect Transistor for Low Power Switches Seungho Kim1, Gyuho Myeong1, Wongil Shin1, Hongsik Lim1, Boram Kim1, Taehyeok Jin1, Sungjin Chang2, Kenji Watanabe3, Takashi Taniguchi3, Sungjae Cho1* The continuous transistor down -scaling has been the key to the successful development of the current information technology.

### Rejected sources


## Q089: How can we break the current limit on energy-conversion efficiencies?

- domain: `engineering_and_materials_science`
- research object: [['energy-conversion', 'energy conversion'], ['photovoltaic'], ['conversion efficiency']]
- phenomenon/relation: [['efficiency limit'], ['Shockley', 'Shockley-Queisser']]
- mechanism: [['recombination'], ['thermoelectric'], ['thermophotovoltaic']]
- queries: ['all:"Shockley-Queisser" OR all:"Shockley Queisser"', 'all:"photovoltaic efficiency" AND all:limit', 'all:"energy conversion efficiency" AND all:thermoelectric']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:1705.07762` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Exceeding the Shockley-Queisser limit within the detailed balance framework Marnik Bercx ∗, Rolando Saniz, Bart Partoens and Dirk Lamoen EMAT & CMT groups, Department of Physics, University of Antwerp, Groenenborgerlaan 171, 2020 Antwerp, Belgium Abstract The Shockley-Queisser limit is one of the most fundamental results in the ﬁeld of photovoltaics.

- `arxiv:1412.1136` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: The Shockley-Queisser limit for nanostructured solar cells Y unlu Xu,1, 2 T ao Gong,1, 2 and Jeremy N. Munday 1, 2, a) 1)Department of Electrical and Computer Engineering, University of Maryland, College Park, MD 20740, USA 2)Institute for Research in Electronics and Applied Physics, University of Maryland, College Park, MD 20740, USA (Dated: 4 December 2014) The Shockley-Queisser limit describes the maximum solar energy conver- sion eﬃciency achievable for a particular material and is the standard by which new photovoltaic technologies are compared.

- `arxiv:1704.06234` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: The Shockley-Queisser (SQ) limit- ing eﬃciencies are considered as the most fundamental benchmarks in solar light conversion. Despite hundreds of works devoted to the SQ model, a number of impor- tant questions, -interrelation of the SQ limit with clas- sical thermodynamics [2], endorewersible processes [3], nonequilium thermodynamics [4], and a possibility to overcome the SQ limit due to nanoscale photonic man- agement [5, 6] and nano-enhanced thermophotovoltaic conversion [7], - are still hot topics of modern research.

- `arxiv:1903.11954` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: S-Q Guide for the Perplexed 10-10-2018 1 Solar Energy Conversion and the Shockley-Queisser Model, a Guide for the Perplexed Jean-Francois Guillemoles1, Thomas Kirchartz2,3, David Cahen4, and Uwe Rau2 1CNRS, UMR 9006, Institut Photovoltaique d’Ile de France (IPVF), Palaiseau, France 2IEK5-Photovoltaik, Forschungszentrum Jülich, 52425 Jülich, Germany 3Fac.

### Rejected sources


## Q046: How many dimensions are there in space?

- domain: `astronomy`
- research object: [['extra dimensions'], ['spacetime'], ['compactification']]
- phenomenon/relation: [['Kaluza', 'Kaluza-Klein'], ['string theor']]
- mechanism: [['hidden dimensions'], ['compact extra']]
- queries: ['all:"extra dimensions" AND (all:spacetime OR all:compactification)', 'all:"Kaluza-Klein" AND all:dimension', 'ti:"extra dimensions" AND all:string']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:1711.06628` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:2|section:page-2|paragraph:1`
  - quote: The combination of GW and EM signals from a bi- nary merger can be used to probe the geometry of extra dimensions beyond our 3+1 spacetime ones. The pos- sibility that additional dimensions exist was ﬁrst postu- lated by Kaluza and Klein [21–23] while attempting to unify gravity and electromagnetism.

- `arxiv:hep-th/0104134` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:3|section:page-3|paragraph:1`
  - quote: And it is interest ing to discuss the spontaneous physical compactiﬁcation of the extra dimensions in t he model buildings, and in the string theory or M-theory compactiﬁcations. 2 One Toy Model In this section, we would like to present a toy brane model with spont aneous physical compactiﬁcation of the extra dimension.

- `arxiv:hep-th/0605071` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:3|section:page-3|paragraph:1`
  - quote: For proving this statement, it is necessary to show ﬁrst that a strictly ﬂat spacetime supports non-trivial scalar ﬁeld conﬁgurations. This we will do in Sec. II. The n ext step is to show the compactiﬁcation of the extra dimensions into a D–dimensional manifold, and this we will show in Sec.

- `arxiv:gr-qc/0301075` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: arXiv:gr-qc/0301075v2 6 Aug 2003 Accelerating Universe and Dynamical Compactiﬁcation of Extra Dimensions F. Darabi ∗ Department of Physics, Azarbaijan University of Tarbiat Mo allem, 53714-161, Tabriz, Iran .

### Rejected sources


## Q095: Where does consciousness lie?

- domain: `neuroscience`
- research object: [['consciousness'], ['neural correlates']]
- phenomenon/relation: [['subjective experience'], ['awareness']]
- mechanism: [['NCC'], ['integrated information'], ['global workspace']]
- queries: ['all:"neural correlates of consciousness"', 'ti:consciousness AND all:neuroscience', 'all:consciousness AND all:"global workspace"']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:2209.07653` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: I argue that one cannot have a fully objective, external picture of the birth process because the order in which the spacetime atoms are born is a partial order. I propose that live experience in causal set theory is an internal view of the objective birth process in which events that are neural correlates of consciousness occur.

- `arxiv:1806.01421` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: Towards Quantum Integrated Information Theory Paolo Zanardi 1,2, Michael Tomka 1,2, Lorenzo Campos Venuti 1,2 1 Department of Physics and Astronomy, University of Southern California, Los Angeles, CA 90089-0484, USA 2 Center for Quantum Information Science & Technology, University of Southern California, Los Angeles, California 90089, USA Integrated Information Theory (IIT) has emerged as one of the leading research lines in compu- tational neuroscience to provide a mechanistic and mathematically well-deﬁned description of the neural correlates of consciousness.

- `arxiv:1903.02594` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: The study and results pave a novel way to analyze the dynamics of neural-like (oscillatory) processes with a purpose of extracting the information relevant to specific conscious percepts, which will facilitate the search for neural correlates of consciousness.

- `arxiv:1803.09107` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:2|section:page-2|paragraph:1`
  - quote: We show how it can reconcile inconsistent empirical findings on the timing of the neural correlates of consciousness (NCCs) , and make testable predictions. According to this hypothesis, a stimulus is consciously perceived for as long as it is recoded to fit an ongoing stream composed of all other perceived stimuli .

### Rejected sources


## Q088: How can we develop manufacturing systems on Mars?

- domain: `engineering_and_materials_science`
- research object: [['Mars manufacturing'], ['in-situ resource', 'ISRU'], ['regolith']]
- phenomenon/relation: [['additive manufacturing'], ['in situ']]
- mechanism: [['Martian'], ['space manufacturing']]
- queries: ['all:Mars AND all:ISRU', 'all:"in-situ resource" AND all:Mars', 'all:regolith AND all:manufacturing AND all:Mars']
- Seed Ready: `True`
- DIRECT_CORE=4 SUPPORTING=0 OFF_TOPIC_REJECTED=0

### Accepted sources

- `arxiv:2105.02619` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: At the same time through excavation valuable resources can be mined for through in situ resource utilization (ISRU). The idea is that a swarm of autonomous mobile robots excavate the ground in a sloped downwards spiral movement.

- `arxiv:2404.00800` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:4|section:page-4|paragraph:1`
  - quote: Key inputs for in-situ resource utilization (ISRU) have been identified in the Martian atmosphere and surface. The Martian atmosphere significantly differs from that of Earth's with its predominant constituent being CO2 and the atmospheric pressure on Mars (636 Pa) is significantly lower than that of Earth (101325 Pa) (detailed in Table 1).

- `arxiv:2107.05872` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:1|section:page-1|paragraph:1`
  - quote: The Proposed Silicate-Sulfuric Acid Process: Mineral Processing for In Situ Resource Utilization (ISRU) Seamus L. Anderson*1, Eleanor K. Sansom1, Patrick M. Shober1, Benjamin A.D. Hartig1 , Hadrien A.R.

- `arxiv:1910.03829` status=DIRECT_QUESTION_CORE role=direct_core
  - locator: `page:2|section:page-2|paragraph:1`
  - quote: Mars was selected as water has been found trapped in the regolith in the form hydrates throughout the Martian surface at an average rate of 5% of the total mass. There are bigger deposits of H 2O-CO2 in the Northern and Southern Polar Ice Caps.

### Rejected sources


