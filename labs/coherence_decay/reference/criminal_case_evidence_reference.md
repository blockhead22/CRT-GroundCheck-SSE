# Criminal Case Evidence Analysis: Legal Reference

Reference document for belief/contradiction analysis of criminal case evidence.
Compiled from legal scholarship, court standards, and empirical research.

---

## 1. TYPES OF EVIDENCE AND RELATIVE RELIABILITY

### 1.1 Physical/Forensic Evidence

**Definition:** Tangible objects or scientific analysis results derived from crime scenes, victims, or suspects (DNA, fingerprints, ballistics, blood spatter, fiber analysis, tool marks).

**Reliability considerations:**
- DNA evidence is considered the gold standard of forensic evidence, with random-match probabilities often exceeding 1 in a billion. DNA has the ability to definitively include or exclude suspects.
- Fingerprint analysis has a long history of court acceptance but lacks standardized error-rate reporting.
- Many forensic disciplines historically admitted as reliable have been challenged. A 2009 National Academy of Sciences report found "no scientific support" for several pattern-matching disciplines without DNA.
- Bite mark analysis: NIST found no scientific data supporting the assumption that dental patterns are unique or that skin reliably records bite marks.
- Microscopic hair comparison: FBI reviews found analysts exaggerated findings in hundreds of cases. The National Registry of Exonerations identified 129 cases with wrongful convictions based partly on flawed hair analysis.
- Arson investigation: Legacy fire investigation techniques based on burn-pattern interpretation have been discredited by modern fire science.
- Blood spatter analysis: Subject to cognitive bias and interpretation variability.

**Key statistic:** Misapplication of forensic science is the second most common contributing factor to wrongful convictions, present in approximately 45% of DNA exoneration cases (Innocence Project).

### 1.2 Eyewitness Testimony

**Definition:** Testimony from individuals who claim to have observed events, persons, or conditions relevant to a case.

**Known unreliability factors:**
- Approximately 70% of wrongful convictions overturned by DNA evidence involved eyewitness misidentification (Innocence Project).
- Memory is reconstructive, not reproductive. Witnesses do not replay events like a recording; they reconstruct memories, which are subject to distortion over time.
- Confidence does not reliably predict accuracy. Eyewitnesses in wrongful conviction cases almost without exception testified with complete certainty at trial, yet at initial police lineups, most displayed a lack of confidence.
- System variables (controllable): lineup procedures, interviewer behavior, question framing, instructions given to witnesses.
- Estimator variables (not controllable): lighting, distance, duration of exposure, stress level, weapon focus effect.
- Cross-race identification effect: Eyewitnesses are over 50% more likely to misidentify a stranger of a different race. Research shows 45% correct identification in cross-race lineups versus 60% in same-race identifications. This effect does not stem from conscious racial prejudice.
- Approximately 40% of mistaken identification cases involve the cross-race effect.

### 1.3 Circumstantial Evidence

**Definition:** Evidence that requires an inference to connect it to a conclusion of fact, as opposed to direct evidence which directly proves a fact.

**Legal standing:**
- Circumstantial evidence is legally sufficient to support a conviction if it excludes every reasonable hypothesis of innocence.
- Courts routinely instruct juries that circumstantial evidence is not inherently less reliable than direct evidence.
- Strength depends on the number of independent circumstances pointing to the same conclusion and the absence of plausible alternative explanations.
- Weakness arises when circumstances are individually ambiguous or when only one interpretation has been explored (tunnel vision risk).

### 1.4 Digital/Electronic Evidence

**Definition:** Any probative information stored or transmitted in digital form (emails, text messages, GPS data, cell tower records, computer files, social media, surveillance footage, metadata).

**Admissibility requirements (Federal Rules of Evidence, Rule 901):**
- Authenticity: The file must be linked to a verified source and shown not to have been fabricated.
- Integrity: A cryptographic hash or equivalent must confirm no modification since capture.
- Chain of custody: Documented accounting for every access and transfer.
- Forensic methodology: Acquisition must use validated forensic methods; tools and procedures are subject to court scrutiny.
- Compliance with ISO/IEC 27037 procedures is considered best practice.

**Reliability considerations:**
- Metadata can be altered; timestamps can be spoofed.
- Cell tower location data provides approximate, not precise, location.
- Digital evidence requires expert interpretation and proper forensic extraction.
- Deleted data may be recoverable but its completeness cannot be guaranteed.

### 1.5 Expert Testimony

**Definition:** Opinion testimony from a qualified expert in a specialized field, admitted to help the trier of fact understand evidence or determine a fact in issue.

**Admissibility standards:**

*Daubert Standard (federal courts and most states):*
Established in Daubert v. Merrell Dow Pharmaceuticals, Inc., 509 U.S. 579 (1993). The trial judge serves as a "gatekeeper" evaluating:
1. Whether the technique or theory can be tested (falsifiability).
2. Whether it has been subjected to peer review and publication.
3. The known or potential rate of error.
4. The existence and maintenance of standards and controls.
5. Whether it has gained general acceptance in the relevant scientific community.

Extended to all expert testimony (not just scientific) by Kumho Tire Co. v. Carmichael, 526 U.S. 137 (1999).

*Frye Standard (still used in some states):*
Requires only that the methodology be "generally accepted" in the relevant scientific community. Less rigorous than Daubert.

**Reliability considerations:**
- Expert opinions are only as reliable as the methodology underlying them.
- Forensic experts may exhibit confirmation bias when given case context before analysis.
- The "hired gun" problem: experts retained by one side may present conclusions favorable to that side.

### 1.6 Character Evidence

**Definition:** Evidence about a person's general character traits or propensities, offered to suggest they acted in conformity with those traits on a specific occasion.

**Legal framework (Federal Rule of Evidence 404):**
- Generally inadmissible to prove that a person acted in accordance with a character trait on a particular occasion (the "propensity rule").
- Permitted exceptions in criminal cases:
  - A defendant may offer evidence of a pertinent trait of their own character.
  - A defendant may offer evidence of an alleged victim's pertinent trait (subject to limitations).
  - The prosecution may offer rebuttal character evidence once the defendant "opens the door."
- Rule 404(b): Evidence of other crimes, wrongs, or acts may be admitted for non-propensity purposes: motive, opportunity, intent, preparation, plan, knowledge, identity, absence of mistake, or lack of accident.
- The prosecution must provide written pretrial notice of intent to use 404(b) evidence and articulate the specific permitted purpose.

---

## 2. KEY LEGAL CONCEPTS

### 2.1 Burden of Proof: Beyond Reasonable Doubt

- The prosecution bears the entire burden of proving every element of the charged offense beyond a reasonable doubt.
- "Beyond a reasonable doubt" is the highest standard of proof in the legal system (higher than "preponderance of the evidence" in civil cases or "clear and convincing evidence").
- The defendant is presumed innocent and has no obligation to prove anything.
- Reasonable doubt is not any doubt or speculative doubt; it is doubt based on reason and common sense after careful and impartial consideration of all evidence.
- If the evidence is susceptible to two reasonable interpretations, one pointing to guilt and one to innocence, the jury must adopt the interpretation pointing to innocence.

### 2.2 Brady Violations

**Source:** Brady v. Maryland, 373 U.S. 83 (1963).

**Rule:** The prosecution has a constitutional duty to disclose all material, favorable evidence to the defense, regardless of whether the defense requests it.

**Three-part test for a Brady violation:**
1. The evidence must be favorable to the accused (exculpatory or impeaching).
2. The evidence must have been suppressed by the state, willfully or inadvertently.
3. Prejudice must have resulted (reasonable probability that the outcome would have been different).

**Scope:**
- Extends to the files of law enforcement officers who worked on the case.
- Includes exculpatory evidence, impeachment material, and evidence that would reduce sentencing.
- The duty is affirmative: prosecutors must search their files and those of law enforcement.
- Applies regardless of good or bad faith by the prosecution.

**Consequences:** The most common remedy is overturning the conviction. Prosecutors who willfully or knowingly withhold Brady material may face sanctions.

### 2.3 Ineffective Assistance of Counsel

**Source:** Strickland v. Washington, 466 U.S. 668 (1984).

**Two-prong test:**
1. **Deficient performance:** The defense attorney's conduct fell below an "objective standard of reasonableness." Courts apply a highly deferential standard, presuming that counsel's conduct falls within the wide range of reasonable professional assistance.
2. **Prejudice:** There is a "reasonable probability" that, but for counsel's errors, the result of the proceeding would have been different. A reasonable probability is one sufficient to undermine confidence in the outcome.

**Exceptions:** Prejudice is presumed in certain per se cases:
- Complete denial of counsel.
- Counsel operating under an actual conflict of interest.
- State interference with counsel's assistance.

**Common examples:** Failure to investigate, failure to call critical witnesses, failure to object to inadmissible evidence, failure to present available exculpatory evidence, failure to communicate plea offers.

### 2.4 Chain of Custody

**Definition:** The documented chronological trail showing the seizure, custody, control, transfer, analysis, and disposition of physical or electronic evidence.

**Requirements:**
- Every transfer of evidence from person to person must be documented.
- Documentation must include: collecting agency, case number, description of evidence, collector identity, collection procedures, transport method, storage conditions, signatures at each transfer, and timestamps.
- Must demonstrate that nobody else could have accessed the evidence outside documented transfers.

**Legal significance:**
- Without an intact chain of custody, evidence may be excluded from trial or afforded less weight.
- Minor gaps are generally permissible and do not automatically destroy the chain; the jury assesses reliability given any gaps.
- A complete break in the chain (evidence left unaccounted for in an unsecured location) can result in exclusion.

### 2.5 Corroboration Requirements

**General principle:** Corroborating evidence strengthens or confirms already existing evidence. It is additional, independent evidence that supports the same conclusion.

**Specific requirements:**
- **Accomplice testimony:** Many states require independent corroboration of accomplice testimony, recognizing the inherent motive to lie (e.g., plea deals, sentence reductions). Corroborating evidence need not independently prove every element of the offense but must tend to connect the defendant to the crime.
- **Confessions (corpus delicti rule):** A conviction generally cannot rest solely on an uncorroborated confession. Independent evidence must establish that the crime occurred.
- **Treason (constitutional):** Article III, Section 3 of the U.S. Constitution requires testimony of two witnesses to the same overt act, or confession in open court.
- **Perjury (two-witness rule):** Under 18 U.S.C. Section 1621, perjury convictions require either a second witness or independent corroborating evidence.

**Corroboration may be entirely circumstantial.**

### 2.6 Recantation and Its Legal Weight

**Definition:** A witness's retraction of prior testimony, asserting that the earlier statement was false.

**Legal treatment:**
- Courts view recantations with strong suspicion and apply a presumption that they are untrustworthy.
- The mere fact that a witness later tells a different story does not necessarily vitiate the original testimony if it was credible.
- A recanting witness may be motivated by threats, intimidation, sympathy for the defendant, reconsideration, or external pressure.
- Prosecutors typically fight to discredit recantations and preserve convictions.

**Standards for new trial based on recantation:**
1. The original testimony was material and false.
2. The jury likely would have reached a different conclusion without it.
3. The party seeking the new trial was surprised by the false testimony and unaware of its falsity until after trial.

**When recantations carry more weight:**
- When the conviction rested on no other evidence besides the recanting witness's testimony.
- When the recantation is supported by independent corroborating evidence.
- When the recantation explains a plausible reason for the original false testimony (e.g., coercion by investigators).

---

## 3. KNOWN BIASES IN CRIMINAL INVESTIGATIONS

### 3.1 Tunnel Vision / Confirmation Bias

**Definition:** Tunnel vision is the tendency of criminal justice actors to selectively filter evidence to build a case for a suspect's conviction. Confirmation bias is the cognitive tendency to favor information confirming existing beliefs while dismissing contradictory evidence.

**Mechanism in investigations:**
- Once a lead suspect is identified, investigators attribute importance to information supporting guilt while overlooking, dismissing, or discounting information inconsistent with guilt.
- Exculpatory evidence may be reinterpreted to fit the guilt hypothesis rather than being treated as disconfirming.
- Canadian commissions of inquiry have identified tunnel vision as a leading cause of wrongful convictions.

**Research findings:**
- Police investigators exhibit stronger tunnel vision effects than laypersons and maintain higher confidence in suspect guilt even when presented with both incriminating and exonerating information.
- Institutional reinforcement: "Noble cause corruption" occurs when investigators focus on conviction as an end goal and engage in questionable activities to achieve it.

### 3.2 Coerced and False Confessions

**Three types of false confessions (Kassin & Wrightsman taxonomy):**
1. **Voluntary:** Given without external pressure, often due to desire for notoriety, mental illness, or guilt over another matter.
2. **Coerced-compliant:** The suspect confesses to end the stress of interrogation, knowing they are innocent but believing confession is the only way out.
3. **Coerced-internalized:** The suspect actually comes to doubt their own memory and becomes temporarily persuaded they may have committed the crime.

**Contributing factors:**
- Interrogation environment: isolation, unfamiliar surroundings, controlled pace and duration.
- Interrogation techniques: confrontational style, rejection of denials, minimization of crime seriousness, false evidence ploys (telling suspect evidence exists that does not).
- Individual vulnerability: youth (adolescents are more suggestible), intellectual disability, mental illness, sleep deprivation, fatigue, drug or alcohol withdrawal.

**Statistics:** Of 3,475 postconviction exonerations registered by the National Registry of Exonerations (as of 2024), 438 (13%) involved false confessions. In more than 25% of DNA exoneration cases, defendants made false confessions or incriminating statements (Innocence Project).

**Legal status:** Coerced confessions are constitutionally inadmissible, even if the confession is factually true.

### 3.3 Cross-Race Identification Problems

**Definition:** The cross-race effect (CRE), also called the own-race bias, is the well-replicated finding that people recognize same-race faces more accurately than cross-race faces.

**Key data points:**
- Eyewitnesses are over 50% more likely to misidentify a stranger of a different race.
- Same-race identification accuracy: approximately 60%. Cross-race: approximately 45%.
- Nearly 40% of wrongful conviction cases involving mistaken identification feature the CRE.
- 41% of eyewitness misidentification cases in DNA exonerations involved cross-racial misidentification.
- The effect does not stem from conscious racial prejudice; non-prejudiced witnesses are equally susceptible.

**Causes:** Differential perceptual expertise (more experience processing own-race faces leads to better encoding of distinguishing features); social categorization (out-group faces processed more categorically).

### 3.4 Anchoring Bias in Investigations and Sentencing

**Definition:** The cognitive bias whereby initial exposure to a number or value (the "anchor") disproportionately influences subsequent judgments, even when the anchor is arbitrary or irrelevant.

**Documented effects:**
- **Sentencing:** Judges who received a 12-month sentencing demand sentenced to 28 months on average; judges who received a 34-month demand sentenced to 35.75 months. The anchor shifted outcomes by approximately 8 months.
- **Expert resistance is minimal:** Experienced legal professionals exhibit anchoring bias comparable to novices, with no significant reduction based on expertise.
- **Arbitrary anchors still work:** Sentencing decisions are influenced by demands even when judges know the demand was randomly determined (including by dice roll).
- **Mechanism:** High anchors increase the cognitive accessibility of incriminating/aggravating arguments; low anchors do the opposite.
- **In investigations:** The first theory developed about a case can anchor all subsequent interpretation of evidence.

---

## 4. EVIDENCE RELIABILITY HIERARCHY

The following hierarchy reflects general patterns in how courts and empirical research assess evidence reliability, from most to least reliable. Individual cases may vary based on specific circumstances.

### Tier 1: Highest Reliability
- **DNA evidence** (properly collected and analyzed): Random-match probabilities often exceed 1 in a billion. Can definitively include or exclude. Subject to contamination and lab error, but methodology is well-validated.
- **Objective digital records with intact chain of custody** (server logs, financial transaction records with cryptographic verification): Difficult to fabricate when properly authenticated.

### Tier 2: High Reliability
- **Physical evidence with established scientific methodology** (fingerprints with standardized comparison protocols, validated toxicology results, properly authenticated documents).
- **Video/audio recordings** (when authenticity is established and content is unambiguous): Subject to interpretation disputes, deepfake concerns in modern context.
- **Digital forensic evidence** (properly extracted using validated tools with documented chain of custody): Metadata, communications, geolocation data.

### Tier 3: Moderate Reliability
- **Expert testimony based on Daubert-qualified methodology**: Reliability depends on the strength of the underlying science, the expert's qualifications, and whether proper procedures were followed.
- **Circumstantial evidence chains** (multiple independent circumstances converging): Stronger when numerous, independent, and not subject to alternative explanations.
- **Contemporaneous documentary evidence** (records made at or near the time of events): Business records, medical records, official documents.

### Tier 4: Lower Reliability
- **Eyewitness testimony** (especially with estimator variable problems): Despite high persuasive power with juries, empirically shown to be unreliable in many conditions. Implicated in approximately 70% of DNA-based exonerations.
- **Informant/jailhouse testimony**: Powerful incentive to fabricate. Present in approximately 15% of DNA exoneration cases overall, and 50% of murder exonerations.
- **Confession evidence** (without corroboration): 13% of exoneration cases involved false confessions. Subject to coercion, suggestibility, and interrogation-induced contamination.

### Tier 5: Lowest Reliability / Discredited
- **Bite mark analysis**: No scientific basis for uniqueness assumption. NIST found no supporting scientific data.
- **Microscopic hair comparison** (without DNA): FBI acknowledged systemic overstatement in hundreds of cases.
- **Legacy arson investigation techniques** (burn-pattern interpretation without modern fire science): Discredited methodologies contributed to wrongful convictions including executions.
- **Polygraph results**: Not admissible in most jurisdictions. No scientific consensus on reliability.
- **Hypnotically refreshed testimony**: Generally inadmissible or severely limited due to suggestibility concerns.

---

## 5. STATISTICAL REFERENCE: WRONGFUL CONVICTION CAUSES

From the Innocence Project DNA exoneration data (614 exonerations as of 2025):

| Contributing Factor | Percentage of Cases |
|---|---|
| Eyewitness misidentification | ~70% |
| Misapplication of forensic science | ~45% |
| False confessions | ~25% |
| Informants/snitches | ~15% (50% in murder cases) |
| Government misconduct | Present in significant subset |

**Demographic data:** 99% male defendants; approximately 61% African American, 8% Latino. 97% convicted of sexual assault and/or murder. 21 had been sentenced to death.

Note: Percentages exceed 100% because multiple factors often contribute to a single wrongful conviction.

---

## 6. SOURCES AND AUTHORITIES

### Landmark Cases
- Brady v. Maryland, 373 U.S. 83 (1963) — prosecutorial disclosure duty
- Strickland v. Washington, 466 U.S. 668 (1984) — ineffective assistance standard
- Daubert v. Merrell Dow Pharmaceuticals, 509 U.S. 579 (1993) — expert testimony admissibility
- Kumho Tire Co. v. Carmichael, 526 U.S. 137 (1999) — Daubert extended to all experts

### Institutional Sources
- [Innocence Project — Exonerations Data](https://innocenceproject.org/exonerations-data/)
- [Innocence Project — Misapplication of Forensic Science](https://innocenceproject.org/misapplication-of-forensic-science/)
- [Cornell LII — Brady Rule](https://www.law.cornell.edu/wex/brady_rule)
- [Cornell LII — Ineffective Assistance of Counsel](https://www.law.cornell.edu/wex/ineffective_assistance_of_counsel)
- [Cornell LII — Daubert Standard](https://www.law.cornell.edu/wex/daubert_standard)
- [Cornell LII — Federal Rule of Evidence 404](https://www.law.cornell.edu/rules/fre/rule_404)
- [Cornell LII — Corroborating Evidence](https://www.law.cornell.edu/wex/corroborating_evidence)
- [NIH/StatPearls — Chain of Custody](https://www.ncbi.nlm.nih.gov/books/NBK551677/)
- [NIJ — Impact of False or Misleading Forensic Evidence](https://nij.ojp.gov/topics/articles/impact-false-or-misleading-forensic-evidence-wrongful-convictions)
- [National Registry of Exonerations](https://www.law.umich.edu/special/exoneration/)

### Research Sources
- [PMC — Why Eyewitnesses Fail](https://pmc.ncbi.nlm.nih.gov/articles/PMC5544328/)
- [PMC — False Confessions: An Integrative Review](https://pmc.ncbi.nlm.nih.gov/articles/PMC11961347/)
- [Duke Judicature — Judging Eyewitness Evidence](https://judicature.duke.edu/articles/judging-eyewitness-evidence/)
- [SAGE — Tunnel Vision and Confirmation Bias Among Police Investigators](https://journals.sagepub.com/doi/full/10.1177/21582440221095022)
- [Public Prosecution Service of Canada — Understanding Tunnel Vision](https://www.ppsc-sppc.gc.ca/eng/pub/is-ip/ch2.html)
- [APA PsycNet — Anchoring Effect in Legal Decision-Making: A Meta-Analysis](https://psycnet.apa.org/fulltext/2021-26899-001.html)
- [NACDL — Why Do Brady Violations Happen: Cognitive Bias and Beyond](https://www.nacdl.org/Article/May2013-WhyDoBradyViolationsHappenCogn)
- [Wiley — Cross-Race Effect and Eyewitness Identification](https://spssi.onlinelibrary.wiley.com/doi/10.1111/j.1751-2409.2012.01044.x)
