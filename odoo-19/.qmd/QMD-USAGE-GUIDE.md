# QMD Usage Guide — odoo19-vault

## Quick Reference

### Mode Comparison

| Mode | Command | Speed | Use Case |
|------|---------|-------|----------|
| **BM25 (fast)** | `qmd search COLLECTION "query"` | ~200ms | Keyword literal match |
| **Vector (recommended)** | `qmd vsearch COLLECTION "query" --limit N` | ~1s | Semantic search, best for AI |
| **Hybrid+LLM (slow)** | `qmd query COLLECTION "query" --limit N` | ~30s | Complex synthesis, research |

### When to Use Each Mode

**Use `qmd search` (BM25)** when:
- Exact filename or class name known
- Code snippet search (`def _update_available_quantity`)
- Very fast iteration needed

**Use `qmd vsearch` (Vector — RECOMMENDED)** when:
- AI-assisted research and documentation
- Finding related concepts (synonyms, related topics)
- General knowledge questions about Odoo

**Use `qmd query` (Hybrid+LLM)** when:
- Need synthesized answer from multiple sources
- Complex multi-part questions
- When vsearch results are insufficient

## Performance Notes

### Cold Start
- First query after server idle: 15-30 seconds
- Model loading to GPU (Apple M4 Metal)
- Subsequent queries: 0.5-2 seconds

### Optimization: Context Snippets
Vault has per-directory context snippets for better recall:
```
qmd context list odoo19-vault
```

Context improves search by adding domain knowledge to the embedding space.

## Cross-Vault Results

QMD may return results from other collections (e.g., odoo-minimal-wiki).
This is intentional — related documentation across vaults can be useful.

To focus on odoo19-vault only, check result URLs for `qmd://odoo19-vault/`.

## Reranker Tuning

QMD-full (hybrid mode) uses LLM reranking but is 20-30x slower than vsearch
with marginal improvement in result quality. For 90% of use cases, vsearch
is sufficient. Reserve QMD-full for:
- Complex research questions
- When result quality is unsatisfactory with vsearch
- Multi-document synthesis tasks

## Benchmark Results (5 Cases, Warm)

```
Grep     : ~100ms avg | 2 total results (exact match)
QMD-vec  : ~950ms avg | 18 total results (semantic)
QMD-full : ~970ms avg | 17 total results (semantic + LLM)
```

**Recommendation**: Use QMD-vector for daily AI research. Grep for debugging.
