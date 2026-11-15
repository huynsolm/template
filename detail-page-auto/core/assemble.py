"""Deterministic seller-owned assembly and advisory evidence checks."""
import re
from .schema import Document

DEFAULT_TERMS=('����','ȿ��','ȿ��','ġ��','����','��ġ','����','�ְ�','�ֻ�','����','���')


def assemble(facts, copy, locked=None, terms=DEFAULT_TERMS):
    fact_map={f.id:f for f in facts.facts}
    review=[]
    def check(unit, section_id, path):
        ids=unit.fact_ids
        missing=[i for i in ids if i not in fact_map]
        def flag(reason): review.append({'section_id':section_id,'field_path':path,'reason':reason,'fact_ids':ids})
        if missing: flag('�������� �ʴ� fact_ids: '+', '.join(missing))
        if not ids: flag('�ٰ� fact_ids�� ��� ����')
        text=' '.join(v for k,v in unit.model_dump().items() if isinstance(v,str))
        if (re.search(r'\d|[%��]',text) or any(term in text for term in terms)) and not any(fact_map[i].kind in ('claim','spec') for i in ids if i in fact_map):
            flag('��ġ��������ȿ�� ǥ���� claim/spec �ٰ� Ȯ�� �ʿ�')
    sections=[]
    def add(kind, **values):
        sid=f'{kind}-1'
        sections.append({'id':sid,'type':kind,**values})
        return sid
    hero=next((i for i in facts.images if i.role=='hero'),facts.images[0] if facts.images else None)
    if hero is None: raise ValueError('images: hero or first image required')
    add('hero',headline=copy.hero.headline,subcopy=copy.hero.subcopy,image=hero.effective_path)
    check(copy.hero,'hero-1','hero')
    add('pain',title=copy.pain.title,items=[i.text for i in copy.pain.items])
    check(copy.pain,'pain-1','pain.title')
    for n,i in enumerate(copy.pain.items): check(i,'pain-1',f'pain.items.{n}.text')
    solution={'title':copy.solution.title,'body':copy.solution.body}
    solution_image=next((i for i in facts.images if i.role=='solution'),None)
    if solution_image: solution['image']=solution_image.effective_path
    add('solution',**solution); check(copy.solution,'solution-1','solution')
    feature_images=iter(i.effective_path for i in facts.images if i.role=='feature')
    features=[]
    for n,i in enumerate(copy.features):
        item={'title':i.title,'desc':i.desc}; image=next(feature_images,None)
        if image: item['image']=image
        features.append(item); check(i,'features-1',f'features.{n}')
    add('features',items=features)
    add('how_to',steps=[{'title':i.title,'desc':i.desc} for i in copy.how_to])
    for n,i in enumerate(copy.how_to): check(i,'how_to-1',f'how_to.{n}')
    if facts.reviews: add('review',items=[i.model_dump() for i in facts.reviews])
    rows=[[f.id,f.text] for f in facts.facts if f.kind=='spec']
    if rows: add('spec',rows=rows)
    add('faq',items=[{'q':i.q,'a':i.a} for i in copy.faq])
    for n,i in enumerate(copy.faq): check(i,'faq-1',f'faq.{n}')
    if facts.notice: add('notice',body=facts.notice)
    if locked:
        for index,section in enumerate(sections):
            if section['id'] in locked: sections[index]=locked[section['id']]
        current={s['id'] for s in sections}
        sections.extend(section for sid,section in locked.items() if sid not in current)
        review=[item for item in review if item['section_id'] not in locked]
    document=Document.model_validate({'schema_version':'1.0','product':facts.product.model_dump(),'sections':sections})
    from .similarity import reference_reviews
    review+=reference_reviews(facts,document)
    return document,review


