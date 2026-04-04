#!/usr/bin/env python3
"""
SSE Multi-Document CLI - Process and inspect multiple documents with provenance.

Phase 5: Multi-document support with doc_id tracking.

Commands:
  sse-multi run <file1> <file2> ...  - Run SSE on multiple documents
  sse-multi show --doc <doc_id>      - Show claims from specific document
  sse-multi show --contradiction N   - Display contradiction with provenance
  sse-multi search "keyword"         - Search across all documents
  sse-multi validate-offsets         - Verify all offsets across all documents
  sse-multi export --json <file>     - Export full multi-doc index
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sse.multi_doc import MultiDocSSE


def main():
    parser = argparse.ArgumentParser(
        description="SSE Multi-Document CLI - Process multiple documents with provenance",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # sse-multi run
    run_parser = subparsers.add_parser("run", help="Process multiple documents")
    run_parser.add_argument("files", nargs="+", help="Input text files")
    run_parser.add_argument("--max-chars", type=int, default=500, help="Max chunk size")
    run_parser.add_argument("--overlap", type=int, default=100, help="Chunk overlap")
    run_parser.add_argument("--embed-model", default="all-MiniLM-L6-v2", help="Embedding model")
    
    # sse-multi show
    show_parser = subparsers.add_parser("show", help="Show specific document or contradiction")
    show_parser.add_argument("--doc", help="Document ID to display")
    show_parser.add_argument("--contradiction", type=int, help="Contradiction index")
    show_parser.add_argument("--cache", default=".sse_multi_cache.json", help="Cache file")
    
    # sse-multi search
    search_parser = subparsers.add_parser("search", help="Search across all documents")
    search_parser.add_argument("keyword", help="Keyword to search for")
    search_parser.add_argument("--cache", default=".sse_multi_cache.json", help="Cache file")
    
    # sse-multi validate-offsets
    validate_parser = subparsers.add_parser("validate-offsets", help="Verify all offsets")
    validate_parser.add_argument("--cache", default=".sse_multi_cache.json", help="Cache file")
    
    # sse-multi export
    export_parser = subparsers.add_parser("export", help="Export to JSON")
    export_parser.add_argument("--json", required=True, help="Output JSON file")
    export_parser.add_argument("--cache", default=".sse_multi_cache.json", help="Cache file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    # Handle 'run' command
    if args.command == "run":
        print("SSE Multi-Document Pipeline")
        print("=" * 60)
        
        # Create pipeline
        pipeline = MultiDocSSE(embedding_model=args.embed_model)
        
        # Load documents
        for filepath in args.files:
            if not os.path.exists(filepath):
                print(f"Error: File not found: {filepath}")
                return
            doc_id = pipeline.add_document_from_file(filepath)
            print(f"Added: {Path(filepath).name} → {doc_id}")
        
        # Process
        print(f"\nProcessing {len(pipeline.registry)} documents...")
        pipeline.process_documents(
            max_chars=args.max_chars,
            overlap=args.overlap
        )
        
        # Export index
        index = pipeline.export_index()
        
        # Display summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("-" * 60)
        print(f"Documents:      {index['stats']['document_count']}")
        print(f"Chunks:         {index['stats']['chunk_count']}")
        print(f"Claims:         {index['stats']['claim_count']}")
        print(f"Contradictions: {index['stats']['contradiction_count']}")
        print(f"Clusters:       {index['stats']['cluster_count']}")
        
        # Per-document breakdown
        print("\nDOCUMENTS")
        print("-" * 60)
        for doc in index['documents']:
            doc_id = doc['doc_id']
            claims = pipeline.get_claims_by_document(doc_id)
            contradictions = pipeline.get_contradictions_by_document(doc_id)
            print(f"{doc['filename']:40s} {len(claims):3d} claims, {len(contradictions):3d} contradictions")
        
        # Cache for subsequent commands
        cache_data = {
            "index": index,
            "documents": {
                doc_id: meta for doc_id, meta in pipeline.registry.documents.items()
            },
            "embed_model": args.embed_model
        }
        with open(".sse_multi_cache.json", "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)
        print(f"\nOK Cached results to .sse_multi_cache.json")
        
    # Handle commands using cached data
    else:
        if not os.path.exists(args.cache):
            print(f"Error: No cached data. Run 'sse-multi run <files>' first.")
            return
            
        with open(args.cache, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        index = cache_data["index"]
        documents = cache_data["documents"]
        
        if args.command == "show":
            if args.doc:
                # Show all claims from specific document
                doc = next((d for d in index['documents'] if d['doc_id'] == args.doc), None)
                if not doc:
                    print(f"Error: Document not found: {args.doc}")
                    return
                    
                print(f"\nDocument: {doc['filename']} ({doc['doc_id']})")
                print("-" * 60)
                doc_claims = [c for c in index['claims'] if c['doc_id'] == args.doc]
                for claim in doc_claims:
                    print(f"\n[{claim['claim_id']}] {claim['claim_text']}")
                    for quote in claim['supporting_quotes']:
                        print(f"  Quote: \"{quote['quote_text'][:60]}...\" [{quote['start_char']}:{quote['end_char']}]")
                        
            elif args.contradiction is not None:
                # Show contradiction with provenance
                if args.contradiction >= len(index['contradictions']):
                    print(f"Error: Contradiction {args.contradiction} not found")
                    return
                    
                cont = index['contradictions'][args.contradiction]
                pair = cont['pair']
                
                claim_a = next(c for c in index['claims'] if c['claim_id'] == pair['claim_id_a'])
                claim_b = next(c for c in index['claims'] if c['claim_id'] == pair['claim_id_b'])
                
                doc_a = next(d for d in index['documents'] if d['doc_id'] == claim_a['doc_id'])
                doc_b = next(d for d in index['documents'] if d['doc_id'] == claim_b['doc_id'])
                
                print(f"\nCONTRADICTION {args.contradiction}")
                print("=" * 60)
                print(f"Label: {cont['label']}")
                print()
                print(f"[{claim_a['claim_id']}] {claim_a['claim_text']}")
                print(f"  Source: {doc_a['filename']} ({claim_a['doc_id']})")
                for quote in claim_a['supporting_quotes']:
                    print(f"  → \"{quote['quote_text']}\" [{quote['start_char']}:{quote['end_char']}]")
                print()
                print(f"[{claim_b['claim_id']}] {claim_b['claim_text']}")
                print(f"  Source: {doc_b['filename']} ({claim_b['doc_id']})")
                for quote in claim_b['supporting_quotes']:
                    print(f"  → \"{quote['quote_text']}\" [{quote['start_char']}:{quote['end_char']}]")
                    
            else:
                print("Error: Specify --doc or --contradiction")
                
        elif args.command == "search":
            # Search across all documents
            keyword = args.keyword.lower()
            matches = [c for c in index['claims'] if keyword in c['claim_text'].lower()]
            
            print(f"\nSearch: \"{args.keyword}\"")
            print(f"Found: {len(matches)} claims")
            print("-" * 60)
            
            for claim in matches:
                doc = next(d for d in index['documents'] if d['doc_id'] == claim['doc_id'])
                print(f"\n[{claim['claim_id']}] {claim['claim_text']}")
                print(f"  Source: {doc['filename']} ({claim['doc_id']})")
                for quote in claim['supporting_quotes']:
                    print(f"  Offset: [{quote['start_char']}:{quote['end_char']}]")
                    
        elif args.command == "validate-offsets":
            # Validate offsets across all documents
            print("\nOFFSET VALIDATION")
            print("=" * 60)
            
            failures = 0
            total = 0
            
            for claim in index['claims']:
                doc_id = claim['doc_id']
                doc_text = documents[doc_id]['text']
                
                for quote in claim['supporting_quotes']:
                    total += 1
                    start = quote['start_char']
                    end = quote['end_char']
                    reconstructed = doc_text[start:end]
                    quote_text = quote.get('quote_text') or quote.get('text')
                    
                    if reconstructed != quote_text:
                        failures += 1
                        doc_filename = next(d['filename'] for d in index['documents'] if d['doc_id'] == doc_id)
                        print(f"FAIL [{claim['claim_id']}] from {doc_filename}")
                        print(f"  Expected: \"{quote_text[:60]}...\"")
                        print(f"  Got:      \"{reconstructed[:60]}...\"")
                        print()
                        
            if failures == 0:
                print(f"OK All {total} offsets reconstruct correctly across {len(index['documents'])} documents")
            else:
                print(f"FAIL {failures}/{total} offset failures")
                
        elif args.command == "export":
            # Export index to JSON
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            print(f"OK Exported to {args.json}")
            print(f"  Documents:      {len(index['documents'])}")
            print(f"  Claims:         {len(index['claims'])}")
            print(f"  Contradictions: {len(index['contradictions'])}")


if __name__ == "__main__":
    main()
