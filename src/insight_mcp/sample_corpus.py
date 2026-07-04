"""Bundled demo corpus: original texts written for this project.

Seeded automatically on first start when no corpus database exists, so a fresh
clone works immediately — no network, no ingestion step, no third-party
content. Replace it with a real corpus any time: `python scripts/ingest.py`.
"""

from __future__ import annotations

SAMPLE_DOCS: list[dict[str, str]] = [
    {
        "url": "sample://ai-agents-governance",
        "title": "Governing autonomous AI agents in the enterprise",
        "date": "2026-01-10",
        "text": (
            "Autonomous AI agents plan, call tools, and act on systems with"
            " limited human supervision, which makes governance a first-class"
            " engineering concern rather than a policy afterthought. Three"
            " safeguards matter most in practice. First, scoped permissions:"
            " every tool an agent can call should carry an explicit allow"
            " policy, and destructive actions should require confirmation."
            " Second, full traceability: log every tool call with its inputs,"
            " duration and outcome so incidents can be replayed and audited."
            " Third, bounded autonomy: budgets on iterations, tokens and"
            " spend keep a misbehaving loop from running away. Organizations"
            " that treat agents like junior colleagues — capable but"
            " supervised, with narrow initial responsibilities that grow with"
            " demonstrated reliability — report smoother adoption than those"
            " that either forbid agents outright or deploy them unsupervised."
        ),
    },
    {
        "url": "sample://mcp-protocol-overview",
        "title": "The Model Context Protocol: a standard interface between models and knowledge",
        "date": "2026-02-05",
        "text": (
            "The Model Context Protocol (MCP) standardizes how AI"
            " applications expose capabilities to language models. A server"
            " publishes tools (functions the model may call), resources"
            " (readable context such as files or stats) and prompts (reusable"
            " templates); any compliant client — a desktop assistant, a"
            " coding agent, an API — can consume them without custom"
            " integration code. Two transports cover most deployments: stdio"
            " for a locally spawned process, and Streamable HTTP for a remote"
            " server shared by many clients. An important architectural"
            " consequence is that the language model stays on the client"
            " side: a retrieval server returns passages and sources, and the"
            " client generates the final answer. The server therefore needs"
            " no model API key and incurs no inference cost, which makes it"
            " cheap to operate and easy to reproduce."
        ),
    },
    {
        "url": "sample://hybrid-search-tradeoffs",
        "title": "Lexical, dense, and hybrid retrieval: choosing a search strategy",
        "date": "2026-03-12",
        "text": (
            "Lexical ranking functions such as BM25 score documents by exact"
            " term overlap. They are fast, dependency-free, and excellent for"
            " acronyms, product names and error codes — but they miss"
            " paraphrases: a query about 'reducing cloud costs' will not"
            " match a document that only says 'FinOps savings'. Dense"
            " retrieval embeds queries and documents into vectors so that"
            " semantically similar texts land close together, catching"
            " paraphrases at the price of model loading and per-query"
            " embedding. Hybrid retrieval runs both and merges the rankings,"
            " typically with Reciprocal Rank Fusion: each document earns"
            " 1/(k + rank) from every list that ranks it, so items that both"
            " retrievers like rise to the top. The practical guidance is to"
            " start lexical, measure real queries, and add the dense leg"
            " when paraphrase misses actually show up in the logs."
        ),
    },
    {
        "url": "sample://mcpops-observability",
        "title": "MCPOps: operating MCP servers in production",
        "date": "2026-04-01",
        "text": (
            "Running an MCP server for real users raises the same questions"
            " as any production service: is it up, is it fast, who is calling"
            " it, and what does it cost to run. A minimal operational"
            " baseline has four parts. Structured logs, one JSON line per"
            " tool call with name, duration and status, feed both debugging"
            " and usage analytics. Prometheus metrics — a call counter"
            " labeled by tool and status plus a latency histogram — make"
            " dashboards and alerting trivial. Authentication on the HTTP"
            " transport, even a static bearer token, keeps a public endpoint"
            " from becoming an open proxy, and rate limiting bounds the blast"
            " radius of a misconfigured client. Finally, containerized"
            " deployment with a code-only image and externally mounted data"
            " keeps releases reproducible and content licensing clean."
        ),
    },
    {
        "url": "sample://grounded-generation",
        "title": "Grounded generation: making language models cite their sources",
        "date": "2026-05-20",
        "text": (
            "A language model answering from retrieved passages is only as"
            " trustworthy as its grounding discipline. Effective systems"
            " constrain generation three ways. The retrieval layer returns"
            " passages with their source title, URL and date, so provenance"
            " travels with the text. The prompt instructs the model to answer"
            " only from the returned passages and to cite the source of every"
            " claim, saying explicitly when the corpus does not cover the"
            " question instead of guessing. And the interface surfaces the"
            " citations so a reader can verify any statement in one click."
            " Hallucination is not eliminated by retrieval alone — a model"
            " will happily blend memorized knowledge into a summary — but the"
            " combination of scoped prompts and visible citations turns an"
            " opaque answer into an auditable one."
        ),
    },
]
