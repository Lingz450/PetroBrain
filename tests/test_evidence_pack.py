from app.core.evidence import build_evidence_pack


def test_evidence_pack_summarizes_sources_and_calculations_without_raw_tool_inputs():
    pack = build_evidence_pack(
        module="well_control",
        citations=[
            {"title": "Kick SOP", "revision": "Rev 1", "clause": "2.1"},
            {"title": "Search Result", "url": "https://example.com/current"},
        ],
        tool_results=[
            {
                "tool": "build_kill_sheet",
                "input": {"sidpp_psi": 400, "private_note": "do not expose"},
                "result": {
                    "kill_mud_weight_ppg": 10.37,
                    "banner": "verify",
                    "working": ["KMW = OMW + SIDPP / (0.052 x TVD)"],
                },
            },
            {
                "tool": "web_search",
                "input": {"query": "private search query"},
                "result": {"results": [{"title": "Search Result", "url": "https://example.com/current"}]},
            },
        ],
        flags=[],
        offline_mode=False,
        disable_web_search=False,
    )

    rendered = str(pack)
    assert pack["confidence"]["label"] == "High"
    assert pack["sources"][0]["label"] == "Kick SOP - Rev 1 - section 2.1"
    assert pack["calculations"][0]["label"] == "Kill sheet calculation"
    assert pack["calculations"][0]["outputs"][0]["label"] == "Kill Mud Weight ppg"
    assert "private search query" not in rendered
    assert "private_note" not in rendered
    assert "build_kill_sheet" not in rendered
    assert "web_search" not in rendered


def test_evidence_pack_marks_unverified_numbers_as_needs_verification():
    pack = build_evidence_pack(
        module="general",
        citations=[],
        tool_results=[],
        flags=["unverified_numbers"],
        offline_mode=False,
        disable_web_search=True,
    )

    assert pack["confidence"]["label"] == "Needs verification"
    assert any("numbers" in note.lower() for note in pack["not_verified"])
