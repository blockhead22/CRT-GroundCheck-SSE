/**
 * SearchResults.jsx - Search Results Panel Component
 * 
 * Renders EvidencePacket as a UI-friendly search results panel.
 * Shows:
 * - Claim list with relevance score
 * - Topology indicators (contradiction count, cluster membership)
 * - Contradiction graph visualization
 * 
 * Explicitly topology-based (never uses truth/credibility language)
 */

import React, { useState } from 'react';
import './SearchResults.css';

/**
 * SearchResultItem - Single search result claim
 * 
 * Props:
 *   - claim: {claim_id, text, source, relevance, contradiction_count, cluster_id, highlighted}
 */
const SearchResultItem = ({ claim, onViewTopology }) => {
  return (
    <div className={`search-result-item ${claim.highlighted ? 'highlighted-topology' : ''}`}>
      <div className="claim-header">
        <span className="claim-id">[{claim.claim_id}]</span>
        <span className="claim-text">{claim.text}</span>
      </div>
      
      <div className="claim-metadata">
        <div className="relevance">
          <span className="label">Relevance:</span>
          <span className="value">{(claim.relevance * 100).toFixed(0)}%</span>
        </div>
        
        <div className="topology-indicator">
          <span className="label">Topology Indicators:</span>
          <div className="indicators">
            {claim.contradiction_count > 0 && (
              <span className="contradiction-count" title="Number of contradictions involving this claim">
                🔀 {claim.contradiction_count} contradiction{claim.contradiction_count !== 1 ? 's' : ''}
              </span>
            )}
            {claim.cluster_id && (
              <span className="cluster-membership" title="Part of cluster (grouping by structure)">
                🔗 Cluster {claim.cluster_id}
              </span>
            )}
          </div>
        </div>
      </div>
      
      <div className="claim-source">
        <span className="label">Source:</span>
        <span className="source-text">{claim.source}</span>
      </div>
      
      {claim.highlighted && (
        <div className="topology-highlight-badge">
          📍 Topology-highlighted (high structural complexity)
        </div>
      )}
      
      <button className="view-topology-btn" onClick={() => onViewTopology(claim.claim_id)}>
        View Topology
      </button>
    </div>
  );
};

/**
 * ContradictionGraph - Visualization of contradiction graph
 * 
 * Shows nodes (claims) and edges (contradictions) as a simple interactive graph.
 * 
 * Props:
 *   - graph: {nodes, edges, statistics}
 */
const ContradictionGraph = ({ graph }) => {
  if (!graph || !graph.nodes || graph.nodes.length === 0) {
    return (
      <div className="contradiction-graph-empty">
        <p>No contradictions found in this set of claims.</p>
      </div>
    );
  }

  return (
    <div className="contradiction-graph">
      <div className="graph-header">
        <h3>Contradiction Topology Graph</h3>
        <div className="graph-stats">
          <span className="stat">
            {graph.statistics.total_nodes} claims (nodes)
          </span>
          <span className="stat">
            {graph.statistics.total_edges} contradictions (edges)
          </span>
        </div>
      </div>
      
      <div className="graph-legend">
        <div className="legend-item">
          <span className="legend-symbol node">●</span>
          <span className="legend-text">Claim (node)</span>
        </div>
        <div className="legend-item">
          <span className="legend-symbol edge">─</span>
          <span className="legend-text">Contradiction (edge)</span>
        </div>
      </div>
      
      <div className="graph-container">
        <svg className="graph-svg" viewBox="0 0 800 400">
          {/* Edges (contradictions) */}
          {graph.edges && graph.edges.map((edge, idx) => {
            const source = graph.nodes.find(n => n.id === edge.source);
            const target = graph.nodes.find(n => n.id === edge.target);
            
            if (!source || !target) return null;
            
            const x1 = (source.id.charCodeAt(0) % 30) * 25 + 50;
            const y1 = (source.id.charCodeAt(1) % 15) * 25 + 50;
            const x2 = (target.id.charCodeAt(0) % 30) * 25 + 50;
            const y2 = (target.id.charCodeAt(1) % 15) * 25 + 50;
            
            return (
              <line
                key={`edge-${idx}`}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                className={`graph-edge edge-${edge.type}`}
                strokeWidth="2"
                title={`${edge.source} ${edge.type} ${edge.target} (strength: ${edge.strength.toFixed(2)})`}
              />
            );
          })}
          
          {/* Nodes (claims) */}
          {graph.nodes && graph.nodes.map((node) => {
            const cx = (node.id.charCodeAt(0) % 30) * 25 + 50;
            const cy = (node.id.charCodeAt(1) % 15) * 25 + 50;
            
            return (
              <g key={`node-${node.id}`}>
                <circle
                  cx={cx}
                  cy={cy}
                  r="12"
                  className={`graph-node ${node.highlighted ? 'highlighted' : ''}`}
                  title={node.label.substring(0, 50) + '...'}
                />
                <text
                  x={cx}
                  y={cy}
                  className="node-label"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {node.id.substring(0, 3)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      
      <div className="graph-explanation">
        <p>
          <strong>Graph Explanation:</strong> This graph shows the structural topology of 
          contradictions. Node size and highlighting are based purely on structural properties 
          (contradiction count + cluster membership), never on truth or credibility judgments.
        </p>
      </div>
    </div>
  );
};

/**
 * SearchResults - Main search results panel
 * 
 * Props:
 *   - results: {results, contradictions, clusters, statistics}
 *   - graph: {nodes, edges, statistics}
 *   - loading: boolean
 *   - error: string or null
 */
const SearchResults = ({ results, graph, loading, error }) => {
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'graph'
  const [selectedClaimId, setSelectedClaimId] = useState(null);

  if (loading) {
    return <div className="search-results-loading">Loading search results...</div>;
  }

  if (error) {
    return (
      <div className="search-results-error">
        <h3>Error</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="search-results-empty">
        <p>No search results available.</p>
      </div>
    );
  }

  return (
    <div className="search-results-panel">
      <div className="search-results-header">
        <h2>Search Results</h2>
        
        <div className="view-mode-toggle">
          <button
            className={`toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
            onClick={() => setViewMode('list')}
          >
            📋 List View
          </button>
          <button
            className={`toggle-btn ${viewMode === 'graph' ? 'active' : ''}`}
            onClick={() => setViewMode('graph')}
          >
            📊 Topology Graph
          </button>
        </div>
        
        <div className="results-statistics">
          <span className="stat">
            <strong>{results.statistics.total_claims}</strong> claims
          </span>
          <span className="stat">
            <strong>{results.statistics.total_contradictions}</strong> contradictions
          </span>
          <span className="stat">
            <strong>{results.statistics.total_clusters}</strong> clusters
          </span>
        </div>
      </div>
      
      {viewMode === 'list' && (
        <div className="search-results-list">
          <div className="list-explanation">
            <p>
              <strong>Topology-Based Display:</strong> Results are sorted by relevance, then 
              by structural complexity (contradiction count + cluster membership). 
              No truth judgments or credibility ranking.
            </p>
          </div>
          
          {results.results && results.results.length > 0 ? (
            results.results.map((claim) => (
              <SearchResultItem
                key={claim.claim_id}
                claim={claim}
                onViewTopology={(claimId) => setSelectedClaimId(claimId)}
              />
            ))
          ) : (
            <div className="no-results">No claims found.</div>
          )}
        </div>
      )}
      
      {viewMode === 'graph' && (
        <ContradictionGraph graph={graph} />
      )}
      
      {/* Contradictions List */}
      {results.contradictions && results.contradictions.length > 0 && (
        <div className="contradictions-section">
          <h3>All Contradictions ({results.contradictions.length})</h3>
          <div className="contradictions-list">
            {results.contradictions.map((contradiction, idx) => (
              <div key={idx} className="contradiction-item">
                <span className="contradiction-claim claim-1">
                  [{contradiction.claim_1}]
                </span>
                <span className="contradiction-type">
                  {contradiction.type}
                </span>
                <span className="contradiction-claim claim-2">
                  [{contradiction.claim_2}]
                </span>
                <span className="contradiction-strength">
                  (strength: {contradiction.strength.toFixed(2)})
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchResults;
