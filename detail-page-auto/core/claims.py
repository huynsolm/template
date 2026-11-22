"""Evidence-bound numeric/comparative expression checklists for explicit approval."""
import hashlib
import json
import re

DEFAULT_CLAIM_TERMS = ('대비','보다','최고','최초','유일','반영구','화재 위험 없음','위험 없음','화재 없음')
NUMERIC_PERCENT = r'\d+(?:[.,]\d+)?\s*[%％]'
NO_RISK = r'(?:위험|화재|부작용|사고)\s*(?:위험)?\s*(?:이|가)?\s*없(?:음|다|습니다)'


def claim_items(job, terms=None, *, document=None, original_copy=None, review_items=None, seller=None):
    from .editor import _copy_units, evidence_units, provenance_path
    from .workflow import read_json
    from .schema import Document
    document = document if document is not None else Document.model_validate(read_json(job/'draft.json'))
    manifest = read_json(job/'manifest.json')
    terms = terms if terms is not None else manifest.get('claim_terms', [*DEFAULT_CLAIM_TERMS, *manifest.get('review_terms',[])])
    pattern = re.compile('|'.join([NUMERIC_PERCENT, NO_RISK, *(re.escape(term) for term in terms if term)]))
    facts = seller.model_dump(exclude_none=True)['facts'] if seller is not None else read_json(provenance_path(job,'facts.json'))['facts']
    fact_map = {fact['id']:fact for fact in facts}
    units = {unit['key']:unit for unit in evidence_units(job,document.model_dump(exclude_none=True),original_copy=original_copy)}
    reviews = review_items if review_items is not None else (read_json(job/'review.json') if (job/'review.json').is_file() else [])
    texts = [(section.id,path,text,units[section.id+':'+path]['fact_ids'])
             for section,path,text in _copy_units(document)]
    for section in document.sections:
        if section.type == 'stats':
            texts.extend((section.id,f'items.{i}',f'{item.value} {item.label}',[item.fact_id])
                         for i,item in enumerate(section.items))
        elif section.type == 'structure':
            texts.extend((section.id,f'items.{i}',f'{item.name} {item.desc}',[])
                         for i,item in enumerate(section.items))
        elif section.type == 'targets':
            texts.extend((section.id,f'items.{i}',text,[]) for i,text in enumerate(section.items))
        elif section.type == 'spec':
            rows = section.spec_table.rows if section.spec_table else section.rows
            texts.extend((section.id,f'rows.{i}',' '.join(row),
                          [row[0]] if not section.spec_table and row[0] in fact_map else [])
                         for i,row in enumerate(rows))
            if section.spec_table:
                texts.append((section.id,'columns',' '.join(section.spec_table.columns),[]))
                texts.extend((section.id,f'notes.{i}',text,[]) for i,text in enumerate(section.spec_table.notes))
        elif section.type == 'notice':
            texts.append((section.id,'body',section.body,[]))
        elif section.type == 'review':
            texts.extend((section.id,f'items.{i}',item.text,[]) for i,item in enumerate(section.items))
    result = []
    for section_id, path, text, ids in texts:
        expressions = list(dict.fromkeys(match.group() for match in pattern.finditer(text)))
        if not expressions:
            continue
        connected = [fact_map[fact_id] for fact_id in ids if fact_id in fact_map]
        item = {'section_id':section_id, 'field_path':path, 'text':text,
                'expressions':expressions,'facts':connected,
                'has_evidence':bool(connected) and all(fact.get('evidence') for fact in connected),
                'review_reasons':list(dict.fromkeys(row['reason'] for row in reviews
                    if row['section_id']==section_id and row.get('field_path') in (path,path.removesuffix('.text'))))}
        for expression in expressions:
            expression_item = {**item, 'expressions':[expression]}
            expression_item['id'] = hashlib.sha256(json.dumps(expression_item,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            result.append(expression_item)
    return result


def confirmed_claims(items, confirmations=None):
    # A direct accept command is an explicit approval of all currently listed items.
    selected = {item['id'] for item in items} if confirmations is None else set(confirmations)
    required = {item['id'] for item in items}
    if selected != required:
        raise ValueError('수치·비교 표현을 모두 확인한 뒤 승인하세요.')
    return [{**item,'confirmed':True} for item in items]
