from maestro.config import get_settings
from maestro.services.tavily import TavilyProspectFinder


def test_tavily_result_extracts_public_emails():
    finder = TavilyProspectFinder(get_settings())

    prospects = finder._prospects_from_result(
        "hoa",
        "Cape Cod",
        {
            "title": "Harbor HOA Contact",
            "url": "https://example.org/contact",
            "content": "Board contact: manager@harborhoa.org. No-reply@example.org",
            "raw_content": None,
        },
    )

    assert len(prospects) == 1
    assert prospects[0].email == "manager@harborhoa.org"
    assert prospects[0].source_url == "https://example.org/contact"


def test_tavily_result_uses_fetched_source_text():
    finder = TavilyProspectFinder(get_settings())

    prospects = finder._prospects_from_result(
        "hoa",
        "South Shore",
        {
            "title": "Condo Association",
            "url": "https://condo.example/contact",
            "content": "Official website for the association.",
        },
        source_text="Contact our manager at board@condoassociation.org",
    )

    assert len(prospects) == 1
    assert prospects[0].email == "board@condoassociation.org"
    assert "South Shore" in prospects[0].verification_note
