from insight_mcp.ingest import chunk_text, extract_article

ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Generative AI in banking — Insights</title></head>
<body>
  <nav><a href="/">Home</a> <a href="/insights">Insights</a></nav>
  <article>
    <h1>Generative AI in banking</h1>
    <p>Banks are moving generative AI from proof of concept to production.
    Customer service assistants now resolve a growing share of requests
    without human escalation, and compliance teams use language models to
    screen transactions faster than before.</p>
    <p>The main challenges remain data governance, model risk management,
    and the integration of AI systems with decades-old core banking
    platforms. Institutions that invested early in data quality report
    smoother deployments and better returns.</p>
    <p>Regulators are watching closely: the coming wave of AI regulation
    will require documented model inventories, human oversight for high
    risk use cases, and clear audit trails for automated decisions.</p>
  </article>
  <footer>Copyright 2026</footer>
</body>
</html>
"""


def test_extract_article_returns_title_and_text():
    article = extract_article(ARTICLE_HTML, "https://example.com/genai-banking")
    assert article is not None
    assert "banking" in article["title"].lower()
    assert "data governance" in article["text"]
    assert "Copyright" not in article["text"]


def test_extract_article_rejects_empty_page():
    assert extract_article("<html><body></body></html>", "https://example.com/x") is None


def test_chunk_text_windows_and_overlap():
    words = " ".join(f"w{i}" for i in range(100))
    chunks = chunk_text(words, size=40, overlap=10)
    assert len(chunks) == 3
    assert chunks[0].split()[0] == "w0"
    # each next window starts size-overlap words later
    assert chunks[1].split()[0] == "w30"
    assert chunks[2].split()[-1] == "w99"
    # overlap: the first words of chunk 2 repeat the tail of chunk 1
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]


def test_chunk_text_short_input_single_chunk():
    assert chunk_text("a b c", size=40, overlap=10) == ["a b c"]


def test_chunk_text_empty():
    assert chunk_text("   ") == []
