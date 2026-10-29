"""Deterministic compatibility projection; never invent claim-level provenance."""
from copy import deepcopy


def project_citations(data):
    result = deepcopy(data)
    sources = {s['id']: s for s in result.get('sources', [])}
    result.setdefault('citations', [])
    for step in result.get('steps', []):
        if step.get('citations'):
            continue
        ids = [sid for sid in step.get('source_ids', []) if sid in sources]
        citations = []
        # An exact claim match is stronger than broad step provenance.
        for field in ('description', 'instructions', 'warnings'):
            values = [step.get(field, '')] if field == 'description' else step.get(field, [])
            for index, value in enumerate(values):
                matched = [sid for sid in ids if value.strip() and value.strip() in
                           [claim.strip() for claim in sources[sid].get('claims', [])]]
                if matched:
                    citations.append({'field': field, 'index': None if field == 'description' else index,
                                      'source_ids': matched, 'scope': 'claim'})
        if len(ids) == 1:
            mapped = {(c['field'], c['index']) for c in citations}
            for index in range(len(step.get('instructions', []))):
                if ('instructions', index) not in mapped:
                    citations.append({'field': 'instructions', 'index': index,
                                      'source_ids': ids, 'scope': 'step'})
        elif ids and not any(c['field'] == 'description' for c in citations):
            citations.append({'field': 'description', 'index': None,
                              'source_ids': ids, 'scope': 'step'})
        step['citations'] = citations
    return result
