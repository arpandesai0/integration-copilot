import pytest
from pydantic import ValidationError
from app.schemas import Guide
from app.seeds.guides import seed_guide
from app.services.claim_citations import project_citations


def test_reviewed_seed_bindings():
    for slug in ('github', 'slack', 'google-drive'):
        guide = seed_guide(slug)
        assert guide.citations
        assert all(step.citations for step in guide.steps)
    github = seed_guide('github')
    register = next(s for s in github.steps if s.id == 'register-app')
    assert register.citations[0].source_ids == ['github-app-register']
    assert register.citations[1].source_ids == ['github-register']


@pytest.mark.parametrize('citation', [
    {'field': 'instructions', 'index': 99, 'source_ids': ['github-types']},
    {'field': 'instructions', 'source_ids': ['github-types']},
    {'field': 'description', 'index': 0, 'source_ids': ['github-types']},
    {'field': 'description', 'source_ids': ['github-org']},
    {'field': 'description', 'source_ids': ['unknown']},
])
def test_reject_invalid_step_citations(citation):
    data = seed_guide('github').model_dump(mode='json')
    data['steps'][0]['citations'] = [citation]
    with pytest.raises(ValidationError):
        Guide.model_validate(data)


@pytest.mark.parametrize('citation', [
    {'field': 'summary', 'index': 0, 'source_ids': ['github-types']},
    {'field': 'prerequisites', 'index': 99, 'source_ids': ['github-types']},
    {'field': 'summary', 'source_ids': ['unknown']},
])
def test_reject_invalid_guide_citations(citation):
    data = seed_guide('github').model_dump(mode='json')
    data['citations'] = [citation]
    with pytest.raises(ValidationError):
        Guide.model_validate(data)


def test_legacy_projection_preserves_provenance_without_guessing():
    data = seed_guide('github').model_dump(mode='json')
    for step in data['steps']:
        step['citations'] = []
    projected = project_citations(data)
    single = projected['steps'][0]['citations']
    assert all(c['scope'] == 'step' for c in single)
    ambiguous = projected['steps'][1]['citations']
    assert ambiguous == [{'field': 'description', 'index': None,
                          'source_ids': ['github-register', 'github-app-register'], 'scope': 'step'}]
    assert data['steps'][0]['citations'] == []
    data['sources'][0]['claims'] = [data['steps'][0]['instructions'][0]]
    exact = project_citations(data)['steps'][0]['citations'][0]
    assert exact['scope'] == 'claim' and exact['source_ids'] == ['github-types']
