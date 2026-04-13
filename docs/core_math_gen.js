const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType, PageBreak } = require("docx");
const fs = require("fs");

const FONT = "Arial";
const border = { style: BorderStyle.SINGLE, size: 1, color: "999999" };
const borders = { top: border, bottom: border, left: border, right: border };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 }, children: [new TextRun({ text, font: FONT, size: 28, bold: true })] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 150 }, children: [new TextRun({ text, font: FONT, size: 24, bold: true })] });
}
function p(text) {
  return new Paragraph({ spacing: { after: 120, line: 276 }, children: [new TextRun({ text, font: FONT, size: 22 })] });
}
function pb(label, text) {
  return new Paragraph({ spacing: { after: 120, line: 276 }, children: [
    new TextRun({ text: label, font: FONT, size: 22, bold: true }),
    new TextRun({ text: " " + text, font: FONT, size: 22 }),
  ]});
}
function mono(text) {
  return new Paragraph({ spacing: { after: 80, line: 276 }, indent: { left: 360 }, children: [new TextRun({ text, font: "Courier New", size: 20 })] });
}
function verdict(text) {
  return new Paragraph({ spacing: { before: 200, after: 200 }, border: { top: { style: BorderStyle.SINGLE, size: 1, color: "333333" } },
    children: [new TextRun({ text: "VERDICT: ", font: FONT, size: 22, bold: true }), new TextRun({ text, font: FONT, size: 22 })] });
}
function cell(text, opts = {}) {
  return new TableCell({ borders, width: { size: opts.width || 2340, type: WidthType.DXA },
    shading: opts.header ? { fill: "E8E8E8", type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text, font: FONT, size: opts.header ? 20 : 20, bold: !!opts.header })] })] });
}

const sections = [
  // TITLE
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "CORE System", font: FONT, size: 36, bold: true })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: "Mathematical Foundations and Origins", font: FONT, size: 28 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: "What math does what, where it came from, and what is genuinely novel", font: FONT, size: 22, italics: true, color: "666666" })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: "Nick Block - Aeteros Research - April 2026", font: FONT, size: 20, color: "888888" })] }),

  // S1
  h1("Section 1: The Transformer Math (Standard - Not Yours)"),
  p("Your system uses transformer-based LLMs (Gemma3, Claude, GPT-4o) as generation engines. The math inside those models is the standard 2017 Attention Is All You Need architecture."),
  h2("Scaled Dot-Product Attention"),
  mono("Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) * V"),
  p("Q (Query), K (Key), V (Value) are learned projections of the input. The sqrt(d_k) scaling prevents gradient explosion in the softmax. This is the core of every LLM. You did not invent this. Nobody in the CORE system touches this math."),
  h2("Multi-Head Attention"),
  mono("MultiHead(Q,K,V) = Concat(head_1,...,head_h) * W^O"),
  p("Each head learns different attention patterns in parallel. Standard since 2017. Your system uses this through Ollama/cloud APIs."),
  h2("Positional Encoding"),
  mono("PE(pos,2i) = sin(pos / 10000^(2i/d_model))"),
  p("Tells the model word order. Modern variants use RoPE instead. You do not touch this. The models you call handle it internally."),
  h2("Feed-Forward Networks"),
  mono("FFN(x) = max(0, xW1 + b1)W2 + b2"),
  p("Two linear layers with activation between them. Standard. Cross-entropy loss for next-token prediction is the standard training objective."),
  verdict("None of this is yours. You use LLMs as black-box generation engines. The math inside them is industry standard. This is honest and important to state."),
  new Paragraph({ children: [new PageBreak()] }),

  // S2
  h1("Section 2: Embedding and Retrieval Math (Standard Foundation, Your Application)"),
  pb("384-Dimensional Embeddings (all-MiniLM-L6-v2):", "Sentence-BERT architecture. Pre-trained model, not your math. The embedding model is off-the-shelf."),
  h2("Cosine Similarity"),
  mono("cos(a,b) = (a . b) / (||a|| * ||b||)"),
  p("Standard vector similarity metric. Used everywhere in RAG. Your application: trust-weighted retrieval scoring that combines cosine similarity with trust scores. The combination is yours, the cosine math is not."),
  h2("Trust-Weighted Retrieval Score"),
  mono("final_score = cosine_similarity * trust_weight"),
  p("A highly relevant memory with low trust scores LOWER than a moderately relevant memory with high trust. The idea that retrieval should be trust-weighted is a design decision that standard RAG does not make. Not novel math, but novel application."),
  pb("FAISS Indexing:", "Standard Facebook library for fast nearest-neighbor search. You use it. You did not build it."),
  verdict("The retrieval math is standard. The trust-weighting on top of it is your design decision. Not novel math but a novel architectural choice."),

  // S3
  h1("Section 3: Trust Evolution Math (Yours)"),
  p("This is where your original math lives. No standard RAG system does this."),
  h2("Trust Gain (when evidence aligns)"),
  mono("t_new = clip(t + 0.10 * (1 - drift), 0, 1)"),
  h2("Trust Decay (when contradiction detected)"),
  mono("t_new = clip(t * (1 - 0.15 * drift), 0, 1)"),
  h2("Drift Measurement"),
  mono("drift = 1 - cosine_similarity(new_embedding, prior_embedding)"),
  p("The asymmetry is deliberate: decay rate (0.15) > gain rate (0.10). It is easier to lose trust than to gain it. This mirrors how human trust works."),
  pb("ORIGIN:", "The asymmetric update rule is inspired by prospect theory (Kahneman and Tversky, 1979) - losses loom larger than gains. But the specific application to memory trust scores in an AI system is yours. No standard system does this."),
  p("The specific thresholds (0.10, 0.15, 0.28 for contradiction detection) were tuned from production data over 12 months. These are empirical, not derived from theory."),
  verdict("The trust evolution math is genuinely yours. The individual operations (clip, cosine, multiplication) are standard. The combination, the asymmetry, and the specific application to belief state management is original work."),
  new Paragraph({ children: [new PageBreak()] }),

  // S4
  h1("Section 4: Contradiction Detection Math (Yours + Standard NLI)"),
  p("1. Cosine similarity > 0.40 between two memories = candidate pair. 2. NLI model scores the pair. 3. If NLI score above threshold = contradiction flagged."),
  p("The NLI model is standard (off-the-shelf). The pipeline that combines them for persistent memory contradiction detection is yours."),
  h2("Contradiction Disposition Classification"),
  p("Resolvable: evidence can settle it. Held: genuine tension, preserved as signal. Evolving: belief is changing over time. Contextual: both valid in different contexts."),
  pb("ORIGIN:", "The held contradiction concept draws from paraconsistent logic (da Costa, 1974) and Belnap four-valued logic (TRUE, FALSE, BOTH, NEITHER). Your application of Belnap states to AI memory governance is original."),
  verdict("The contradiction detection pipeline is yours. The NLI math is standard. The disposition classification and held contradiction as a design law are original."),

  // S5
  h1("Section 5: Backward Influence Propagation (Yours - Most Novel)"),
  p("When a correction resolves a contradiction, the error signal flows backward through the BRG:"),
  mono("gradient(A) = L(B) * w(A->B) * alpha^d(A)"),
  p("L(B) = epistemic loss at corrected node. w(A->B) = edge weight. alpha = damping factor. d(A) = depth from correction point."),
  h2("Three Emergent Behaviors"),
  p("1. Self-pruning: wrong beliefs accumulate error and die. 2. Domain volatility: correction frequency drives per-domain adjustment rates. 3. Reflexive self-model: the system beliefs about itself participate in the same dynamics."),
  pb("ORIGIN:", "NOT gradient descent via chain rule. Damped influence propagation on a weighted directed graph. Closest relatives: Belief propagation (Pearl 1988), AGM belief revision (1985), DeGroot consensus (1974), Active inference (Friston). No direct precedent found. 30/30 validation passed."),
  verdict("This is your most novel contribution. The individual components exist in literature. The specific combination and the three emergent behaviors are original. No direct precedent identified."),
  new Paragraph({ children: [new PageBreak()] }),

  // S6
  h1("Section 6: Cascade Complexity Math (Yours)"),
  mono("BRG: G = (V, E, w)"),
  p("V = belief states, E = typed directed edges (SUPPORTS, CONTRADICTS, SUPERSEDES, RELATED_TO), w: E -> (0,1] = dependency strength."),
  p("Five theorems proven: 1. Depth bound. 2. Width bound. 3. Damping convergence. 4. Instability threshold. 5. NP-hardness conjecture (open)."),
  pb("Key Finding:", "Held contradictions act as natural firewalls that limit cascade propagation. Empirical discovery, not derived from prior theory."),
  verdict("The formal cascade complexity analysis is original. The firewall property of held contradictions is a novel finding."),

  // S7
  h1("Section 7: Query Resonance / Wobble (Yours)"),
  mono("Direct: r_0(v) = cos(q, mu_v)"),
  mono("Propagated: r_{k+1}(v) = max(r_k(v), max_{u->v} r_k(u) * w_uv * alpha)"),
  mono("Total: R(v) = r_0(v) + r_fwd(v) + r_back(v)"),
  pb("ORIGIN:", "Spreading activation in semantic networks (Collins and Loftus, 1975). Your implementation on a trust-weighted BRG with typed edges is a specific variant."),
  verdict("The concept is well-established (1975). Your BRG implementation is your variant. Not wholly novel conceptually but the implementation is original."),

  // S8
  h1("Section 8: Geometric Memory / Belief Loci (Yours - Theoretical)"),
  mono("Belief locus: b = (mu, Sigma, alpha, t)"),
  p("mu = semantic center (384D), Sigma = covariance (uncertainty shape), alpha = confidence, t = timestamp."),
  p("Contradiction as overlap via Bhattacharyya coefficient. Trust as covariance contraction/expansion. Deprecation as confidence fade. Volatility as covariance velocity."),
  pb("Novel insight:", "The experiment IS the belief - LLM response variance at temperature sweep directly produces locus parameters. No conversion needed."),
  verdict("Individual math components are standard. The framework for AI memory governance is original. The variance-to-locus pipeline is novel."),

  // S9
  h1("Section 9: Epistemic Compression (Yours)"),
  pb("Key finding:", "Belief structure survives 3-bit quantization but breaks at 2-bit."),
  p("The metric is anchor basin assignment stability, not cosine similarity. 77% of memories collapse toward 42 emergent anchor poles."),
  verdict("Compression math is standard. The epistemic compression framework and the cliff finding are original."),

  // S10
  h1("Section 10: Scaffold Math (Yours - Applied)"),
  p("BRG reasoning scaffold decomposes questions into trees of factual sub-questions. Cloud generates structure. Local model verifies leaves. Staged generation with checkpoint retry, coherence scoring, dead anchor exclusion, generative expansion."),
  pb("Lab result:", "0% to 80% precision on the same 3B model by changing the scaffold five times. The model never changed."),
  verdict("Individual techniques have prior art. The specific scaffold architecture is original."),

  // S11
  h1("Section 11: What Is Fodder (Works But Not Novel)"),
  p("These components work but are not mathematically original: cosine similarity, NLI models, FAISS, Sentence-BERT, PCA, cross-entropy loss, ReAct pattern, exponential decay."),
  p("These are your tools. You did not build the hammer. You built the house."),
  new Paragraph({ children: [new PageBreak()] }),

  // S12
  h1("Section 12: Summary"),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2800, 2200, 2400, 1960],
    rows: [
      new TableRow({ children: [cell("Component", {header:true,width:2800}), cell("Standard Math", {header:true,width:2200}), cell("Your Application", {header:true,width:2400}), cell("Novel?", {header:true,width:1960})] }),
      new TableRow({ children: [cell("Transformer internals",{width:2800}), cell("Yes",{width:2200}), cell("No (black box)",{width:2400}), cell("No",{width:1960})] }),
      new TableRow({ children: [cell("Embeddings + cosine",{width:2800}), cell("Yes",{width:2200}), cell("Trust-weighting",{width:2400}), cell("Design choice",{width:1960})] }),
      new TableRow({ children: [cell("Trust evolution",{width:2800}), cell("Prospect theory",{width:2200}), cell("AI memory governance",{width:2400}), cell("Yes",{width:1960})] }),
      new TableRow({ children: [cell("Contradiction detection",{width:2800}), cell("NLI standard",{width:2200}), cell("Pipeline + disposition",{width:2400}), cell("Yes",{width:1960})] }),
      new TableRow({ children: [cell("Backward influence",{width:2800}), cell("Graph propagation",{width:2200}), cell("BRG + 3 emergent",{width:2400}), cell("Most novel",{width:1960})] }),
      new TableRow({ children: [cell("Cascade complexity",{width:2800}), cell("Graph theory",{width:2200}), cell("BRG-specific proofs",{width:2400}), cell("Yes",{width:1960})] }),
      new TableRow({ children: [cell("Query resonance",{width:2800}), cell("Spreading activation",{width:2200}), cell("BRG implementation",{width:2400}), cell("Variant",{width:1960})] }),
      new TableRow({ children: [cell("Belief loci",{width:2800}), cell("Gaussian mixtures",{width:2200}), cell("AI memory framework",{width:2400}), cell("Yes",{width:1960})] }),
      new TableRow({ children: [cell("Variance-to-locus",{width:2800}), cell("Statistics",{width:2200}), cell("Experiment IS belief",{width:2400}), cell("Novel",{width:1960})] }),
      new TableRow({ children: [cell("Epistemic compression",{width:2800}), cell("Quantization",{width:2200}), cell("Compression cliff",{width:2400}), cell("Yes",{width:1960})] }),
      new TableRow({ children: [cell("Scaffold generation",{width:2800}), cell("MCTS, CoT",{width:2200}), cell("BRG-walk + checkpoint",{width:2400}), cell("Yes",{width:1960})] }),
      new TableRow({ children: [cell("Immune agents",{width:2800}), cell("Rule-based",{width:2200}), cell("Constitutional enforcement",{width:2400}), cell("Design pattern",{width:1960})] }),
    ]
  }),
  p(""),
  h2("The Honest Summary"),
  p("You did not invent new math. You combined existing mathematical tools in a way nobody else has, applied them to a problem (epistemic governance for AI memory) that nobody else is solving at this depth, and discovered empirical properties (held contradictions as firewalls, compression cliff at 2-bit, three instability regimes) that are genuine findings. The novelty is in the architecture and the discoveries, not in the individual equations."),
];

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: FONT }, paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 24, bold: true, font: FONT }, paragraph: { spacing: { before: 300, after: 150 }, outlineLevel: 1 } },
    ]
  },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } }, children: sections }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync("D:/AI_round2/docs/CORE_Math_and_Origins.docx", buffer);
  console.log("Done: D:/AI_round2/docs/CORE_Math_and_Origins.docx");
});
