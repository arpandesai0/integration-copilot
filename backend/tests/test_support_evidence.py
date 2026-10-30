"""Do not promote a vendor homepage or connector catalog to public OAuth support."""
import pytest

from app.schemas import GuideDraft
from app.seeds.guides import seed_guide
from app.services.support_evidence import constrain_oauth_claims


def draft(**updates):
    data = seed_guide("slack").model_dump(mode="json")
    data["oauth_evidence"] = {
        "source_id": data["sources"][0]["id"],
        "authorization_url": "https://provider.example/authorize",
        "token_url": "https://provider.example/token",
    }
    return GuideDraft.model_validate({**data, **updates})


RESEARCH = "Authorization endpoint https://provider.example/authorize; token endpoint https://provider.example/token."


@pytest.mark.parametrize("evidence", [
    None,
    {"source_id": "invented", "authorization_url": "https://provider.example/authorize", "token_url": "https://provider.example/token"},
    {"source_id": "slack-apps", "authorization_url": "https://invented.example/authorize", "token_url": "https://invented.example/token"},
])
def test_missing_or_invented_oauth_evidence_cannot_create_setup(evidence):
    result = constrain_oauth_claims(draft(oauth_evidence=evidence), RESEARCH)
    assert result.oauth_support_status == "unknown"
    assert result.steps == []
    assert result.setup_confidence == "unknown"
    assert result.citations == []
    assert all(not source.claims and source.excerpt is None for source in result.sources)
    assert "could not be verified" in result.summary


def test_grounded_endpoint_pair_keeps_supported_guide():
    guide = draft()
    assert constrain_oauth_claims(guide, RESEARCH) is guide


def test_marketing_or_inbound_connector_prose_is_not_endpoint_evidence():
    result = constrain_oauth_claims(draft(), "Official product information. Connect Salesforce using OAuth.")
    assert result.oauth_support_status == "unknown"
    assert result.steps == []


@pytest.mark.parametrize("status", ["unknown", "unsupported"])
def test_no_evidence_is_not_automatically_confirmed_unsupported(status):
    guide = draft(oauth_support_status=status, steps=[], oauth_evidence=None)
    assert constrain_oauth_claims(guide, "No public documentation found.") is guide
    assert guide.oauth_support_status == status



def test_unknown_support_cannot_ship_generic_oauth_steps():
    result = constrain_oauth_claims(draft(oauth_support_status="unknown"), RESEARCH)
    assert result.oauth_support_status == "unknown"
    assert result.steps == []



def test_endpoint_prefix_does_not_count_as_exact_grounded_endpoint():
    result = constrain_oauth_claims(
        draft(),
        "https://provider.example/authorize-fake https://provider.example/token-fake",
    )
    assert result.oauth_support_status == "unknown"
    assert result.steps == []


def test_saml_workflow_keeps_documented_steps_without_oauth_endpoints():
    passage = "Configure SAML in the authentication settings and exchange identity provider metadata."
    guide = draft(authentication_method="saml", oauth_support_status="unknown",
                  oauth_evidence=None,
                  workflow_evidence={"source_id": "slack-oauth", "excerpt": passage})
    result = constrain_oauth_claims(guide, passage)
    assert result.steps
    assert result.authentication_method == "saml"
    assert result.oauth_support_status == "unknown"


def test_iam_role_workflow_keeps_documented_steps_without_oauth_endpoints():
    passage = "Assume the cross-account role with AWS STS and use the returned temporary security credentials."
    guide = draft(authentication_method="iam_role", oauth_support_status="unknown",
                  oauth_evidence=None,
                  workflow_evidence={"source_id": "slack-oauth", "excerpt": passage})
    result = constrain_oauth_claims(guide, passage)
    assert result.steps
    assert result.authentication_method == "iam_role"
    assert result.oauth_support_status == "unknown"


def test_non_oauth_label_cannot_bypass_evidence_gate():
    guide = draft(authentication_method="saml", oauth_support_status="unknown",
                  oauth_evidence=None, workflow_evidence=None)
    assert constrain_oauth_claims(guide, "Marketing homepage only.").steps == []


def test_workflow_passage_may_omit_markdown_emphasis_without_changing_words():
    passage = "Configure SAML in authentication settings and exchange identity provider metadata."
    guide = draft(authentication_method="saml", oauth_support_status="unknown",
                  oauth_evidence=None,
                  workflow_evidence={"source_id": "slack-oauth", "excerpt": passage})
    assert constrain_oauth_claims(guide, passage.replace("SAML", "**SAML**")).steps


def test_documented_endpoint_query_does_not_hide_same_endpoint():
    result = constrain_oauth_claims(
        draft(),
        "Authorize https://provider.example/authorize?scope=read and exchange at https://provider.example/token",
    )
    assert result.steps


def test_workflow_quote_can_omit_acronym_but_not_negation():
    passage = "Google Identity Services supports ID token sign-in for web applications."
    guide = draft(authentication_method="oidc_sdk", oauth_support_status="unknown",
                  oauth_evidence=None,
                  workflow_evidence={"source_id": "slack-oauth", "excerpt": passage})
    assert constrain_oauth_claims(guide, passage.replace("Services", "Services (GIS)")).steps
    assert not constrain_oauth_claims(guide, passage.replace("supports", "does not support")).steps
