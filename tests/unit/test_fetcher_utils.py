import pytest

from enrichment.fetcher import (
    _extract_taleo,
    _extract_pdf_candidates,
    _extract_echa_row_index,
    _find_embedded_pdf_link,
    _is_echa_row_url,
    _is_taleo_url,
    _is_short_or_placeholder,
    _score_pdf_candidate,
    _select_embedded_pdf_link,
    _satcen_payload_to_text,
    classify_fetch_error,
)


@pytest.mark.unit
def test_classify_fetch_error_403():
    status, reason = classify_fetch_error(RuntimeError("403 Client Error: Forbidden"))
    assert status == "blocked_source"
    assert reason == "http_403"


@pytest.mark.unit
def test_classify_fetch_error_404():
    status, reason = classify_fetch_error(RuntimeError("404 Client Error: Not Found"))
    assert status == "broken_link"
    assert reason == "http_404"


@pytest.mark.unit
def test_classify_fetch_error_429():
    status, reason = classify_fetch_error(RuntimeError("429 Too Many Requests"))
    assert status == "blocked_source"
    assert reason == "http_429"


@pytest.mark.unit
def test_find_embedded_pdf_link_absolute():
    html = '<a href="./docs/vacancy.pdf">Download PDF</a>'
    out = _find_embedded_pdf_link(html, "https://example.org/jobs/123")
    assert out == "https://example.org/jobs/docs/vacancy.pdf"


@pytest.mark.unit
def test_find_embedded_pdf_link_none():
    html = "<html><body><h1>No attachment</h1></body></html>"
    out = _find_embedded_pdf_link(html, "https://example.org/jobs/123")
    assert out == ""


@pytest.mark.unit
def test_is_taleo_url_supports_custom_domains():
    assert _is_taleo_url(
        "https://jobs.fao.org/careersection/fao_external/jobdetail.ftl?job=2600348"
    )


@pytest.mark.unit
def test_extract_taleo_script_payload_fao_style():
    html = """
    <html><body>
      <script>
        var data = "abc !|!!*!<p><strong>Organizational Setting</strong></p><p>FAO mission text</p><p><strong>Minimum Requirements</strong></p><p>Master degree and 5 years experience</p>!|!2600348!|!Partnerships Specialist!|!13/Feb/2026";
      </script>
    </body></html>
    """
    out = _extract_taleo(html)
    assert "Organizational Setting" in out
    assert "Minimum Requirements" in out


@pytest.mark.unit
def test_extract_taleo_prefers_substantive_fragment_over_notice():
    html = """
    <html><body>
      <script>
        var data = "!|!!*!<p>IMPORTANT NOTICE: generic text</p>"
          + "!|!!*!<p><strong>Organizational Setting</strong></p><p>Main role details and long substantive description text for the assignment.</p><p><strong>Minimum Requirements</strong></p><p>Degree and years of relevant experience.</p>!|!2600999!|!";
      </script>
    </body></html>
    """
    out = _extract_taleo(html)
    assert "Organizational Setting" in out
    assert "Minimum Requirements" in out
    assert "IMPORTANT NOTICE" not in out


@pytest.mark.unit
def test_satcen_payload_to_text_collects_section_fields():
    payload = {
        "title": "System Support Officer",
        "reference": "SatCen/2025/038",
        "description": "<p>Main responsibilities text.</p>",
        "qualifications": "<ul><li>Degree in IT</li></ul>",
        "skills": "Linux, scripting",
        "requirements": "<p>EU nationality</p>",
        "conditions": "<p>Temporary contract</p>",
    }
    out = _satcen_payload_to_text(payload)
    assert "System Support Officer" in out
    assert "SatCen/2025/038" in out
    assert "Description" in out
    assert "Qualifications" in out
    assert "Requirements" in out
    assert "Temporary contract" in out


@pytest.mark.unit
def test_is_short_or_placeholder_flags_low_word_count_even_if_long_chars():
    text = ("alpha " * 21).strip()  # >120 chars but only 21 words
    assert _is_short_or_placeholder(text)


@pytest.mark.unit
def test_select_embedded_pdf_link_prefers_vacancy_notice_over_policy_pdf():
    html = """
    <html><body>
      <a href="/system/files/2026-02/01-edps-data-protection-notice.pdf">Download</a>
      <a href="/system/files/2026-02/vn-08-2026-edps-legal-and-policy-officer_en.pdf">
        Vacancy Notice 08-2026 EDPS - Legal and Policy Officer
      </a>
    </body></html>
    """
    out = _select_embedded_pdf_link(
        html,
        "https://www.edps.europa.eu/job",
        title="Vacancy Notice 08-2026 EDPS - Legal and Policy Officer",
        org_abbrev="EDPS",
    )
    assert "vn-08-2026-edps-legal-and-policy-officer" in out


@pytest.mark.unit
def test_select_embedded_pdf_link_rejects_manual_only_candidate_for_prefer_org():
    html = """
    <html><body>
      <a href="https://www.eba.europa.eu/Online-Application-Manual-for-Candidates.pdf">
        Candidates Manual
      </a>
    </body></html>
    """
    out = _select_embedded_pdf_link(
        html,
        "https://www.careers.eba.europa.eu/en/our-vacancies/senior-expert",
        title="Senior Expert Depositor Protection",
        org_abbrev="EBA",
    )
    assert out == ""


@pytest.mark.unit
def test_extract_pdf_candidates_discovers_pdf_like_links():
    html = """
    <html><body>
      <a href="/files/vacancy_notice.pdf">Vacancy notice</a>
      <a href="/files/info.docx">info</a>
    </body></html>
    """
    cands = _extract_pdf_candidates(html, "https://example.org/jobs/1")
    assert len(cands) == 1
    assert cands[0]["url"] == "https://example.org/files/vacancy_notice.pdf"


@pytest.mark.unit
def test_score_pdf_candidate_boosts_title_overlap_and_vacancy_markers():
    c = {
        "url": "https://example.org/files/vacancy_notice_legal_officer.pdf",
        "text": "Vacancy Notice Legal Officer",
        "context": "",
    }
    s = _score_pdf_candidate(c, title="Legal Officer")
    assert s > 100


@pytest.mark.unit
def test_score_pdf_candidate_penalizes_docx_application_form():
    c = {
        "url": "https://example.org/files/application_form.docx",
        "text": "Download application form",
        "context": "",
    }
    s = _score_pdf_candidate(c, title="Call for traineeships")
    assert s < 0


@pytest.mark.unit
def test_extract_pdf_candidates_finds_pdf_urls_in_json_like_script():
    html = r'''
    <script id="__NEXT_DATA__" type="application/json">
      {"content":"<object data=\"https:\/\/www.careers.eba.europa.eu\/assets\/offers\/22_RR_EU_Vacancy_Notice.pdf?276029\"/>"}
    </script>
    '''
    cands = _extract_pdf_candidates(html, "https://www.careers.eba.europa.eu/en/our-vacancies/x")
    urls = [c["url"] for c in cands]
    assert any("vacancy_notice.pdf" in u.lower() for u in urls)


@pytest.mark.unit
def test_echa_row_url_helpers():
    url = (
        "https://jobs.echa.europa.eu/psp/pshrrcr/EMPLOYEE/HRMS/c/"
        "HRS_HRAM.HRS_APP_SCHJOB.GBL?FOCUS=Applicant&languageCd=ENG#row-42"
    )
    assert _is_echa_row_url(url)
    assert _extract_echa_row_index(url) == 42
    assert not _is_echa_row_url("https://jobs.echa.europa.eu/no-row")
