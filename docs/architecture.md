# Architecture — insight-mcp

## Vue d'ensemble

```
MCP client (Claude Code / Desktop / API Anthropic)   ← le client GÉNÈRE
        │ stdio / Streamable HTTP (:8020, phase 3)      (synthèse + citations)
        ▼
    insight-mcp (FastMCP)
        │ index local : BM25 (phase 1), hybrid BM25+dense RRF (phase 2)
        ▼
    SQLite data/corpus.db (gitignoré)
        ▲
    scripts/ingest.py — httpx + trafilatura, rate-limité, caché
        ▲
    URLs publiques (corpus configurable ; démo = publications Wavestone)
```

## Décisions

1. **Retrieval-only, pas de LLM côté serveur.** Dans une archi MCP le LLM est déjà
   côté client : le serveur retourne passages + scores + sources, l'agent rédige la
   réponse citée. Conséquences : zéro clé API, zéro coût d'inférence, démo
   reproductible par quiconque clone le repo.
2. **Serveur autonome** : index embarqué plutôt qu'un backend de recherche externe.
   Aucune dépendance privée — le déploiement cloud (phase 3) se réduit à un conteneur.
3. **Corpus jamais commité.** `data/` gitignoré ; le repo ne contient que le code et
   une liste d'URLs publiques. Ingestion polie : robots.txt, User-Agent identifiable,
   ~1 req/s, cache disque.
4. **BM25 d'abord, hybrid ensuite.** rank-bm25 pur Python en phase 1 (deps légères,
   CI rapide) ; fastembed (ONNX, pas de torch) + fusion RRF en phase 2, derrière un
   flag `SEARCH_MODE` — les deux modes restent comparables sur un même corpus.
5. **Transport** : stdio en phase 1 ; Streamable HTTP (port 8020 par défaut,
   configurable via `MCP_PORT`) en phase 3.
6. **Index en mémoire** rechargé au démarrage — OK < 10k chunks ; index persistant
   documenté comme évolution.

## Contrat des tools (phase 1)

| Tool | Entrée | Sortie |
|------|--------|--------|
| `search_publications` | `query, top_k=5` | passages + scores + {titre, URL, date} |
| `get_publication` | `doc_id` | texte complet + métadonnées |
| `list_topics` | — | aperçu corpus (docs, titres, dates) |

Phase 2 : resources `corpus://stats`, `corpus://health` ; prompt « réponds uniquement
à partir des publications retournées, cite titre + URL ».
