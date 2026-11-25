"""Strict versioned input contract for detail-page sections."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationInfo, field_validator, model_validator

Text = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r'\S')]
Title = Annotated[Text, Field(max_length=80)]
Short = Annotated[Text, Field(max_length=300)]
Body = Annotated[Text, Field(max_length=2000)]
ImagePath = Text

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

class Product(Model):
    name: Text
    category: Text
    # M9: optional. An empty price is left off the page; a written sale status is shown as written.
    price: Text | None = None
    brand_color: Annotated[str, StringConstraints(pattern=r'^#[0-9a-fA-F]{6}$')]

    @field_validator('price', mode='before')
    @classmethod
    def empty_price(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

class Section(Model):
    id: Text

class Hero(Section):
    type: Literal['hero']
    headline: Title
    image: ImagePath
    subcopy: Short | None = None

class Pain(Section):
    type: Literal['pain']
    title: Title
    items: Annotated[list[Short], Field(min_length=1,max_length=10)]

class Solution(Section):
    type: Literal['solution']
    title: Title
    body: Body
    image: ImagePath | None = None

class Feature(Model):
    title: Title
    desc: Short
    image: ImagePath | None = None

class Features(Section):
    type: Literal['features']
    items: Annotated[list[Feature], Field(min_length=1,max_length=10)]

class Step(Model):
    title: Title
    desc: Short

class HowTo(Section):
    type: Literal['how_to']
    steps: Annotated[list[Step], Field(min_length=1,max_length=10)]

class ReviewItem(Model):
    text: Annotated[Text, Field(max_length=1000)]
    rating: Annotated[int, Field(ge=1,le=5)]
    source: Text
    permission_confirmed: bool

    @model_validator(mode='after')
    def permission(self):
        if self.permission_confirmed is not True:
            raise ValueError('permission_confirmed must be true')
        return self

class Review(Section):
    type: Literal['review']
    items: Annotated[list[ReviewItem], Field(min_length=1,max_length=10)]

class Highlight(Model):
    value: Title
    label: Title
    fact_id: Text

class StructureItem(Model):
    name: Title
    desc: Short

class SpecTable(Model):
    columns: list[Title] = Field(min_length=2, max_length=8)
    rows: list[list[Short]] = Field(min_length=1, max_length=30)
    notes: list[Short] = Field(default_factory=list)

    @field_validator('rows')
    @classmethod
    def row_width(cls, rows, info: ValidationInfo):
        columns = info.data.get('columns')
        if columns:
            for index, row in enumerate(rows, 1):
                if len(row) != len(columns):
                    raise ValueError(f'사양표 {index}행의 칸 수가 열 수와 다릅니다.')
        return rows

class Stats(Section):
    type: Literal['stats']
    items: list[Highlight] = Field(min_length=1, max_length=4)

class TargetGroup(Model):
    name: Literal['업종', '용도', '대상']
    items: list[Title] = Field(min_length=1, max_length=12)

class Targets(Section):
    type: Literal['targets']
    items: list[Title] = Field(min_length=1, max_length=36)
    groups: list[TargetGroup] | None = None  # M9: industries / uses, shown apart in design v2

class CaseItem(Model):
    name: Title
    desc: Short

class Cases(Section):
    # M9: separate application examples (not consecutive steps), entered by the seller.
    type: Literal['cases']
    items: list[CaseItem] = Field(min_length=1, max_length=6)

class Structure(Section):
    type: Literal['structure']
    items: list[StructureItem] = Field(min_length=1, max_length=8)
    image: ImagePath | None = None

class ImageSection(Section):
    type: Literal['image']
    image: ImagePath
    staged: Literal[True] | None = None  # M8-B: fully AI-generated mood picture, labelled on the page

class GalleryPhoto(Model):
    image: ImagePath
    alt: Text | None = None
    staged: Literal[True] | None = None

class Gallery(Section):
    type: Literal['gallery']
    items: list[GalleryPhoto] = Field(min_length=1, max_length=10)

class Spec(Section):
    type: Literal['spec']
    rows: list[Annotated[list[Text], Field(min_length=2, max_length=2)]] | None = Field(default=None, min_length=1, max_length=10)
    spec_table: SpecTable | None = None

    @model_validator(mode='after')
    def one_table(self):
        if (self.rows is None) == (self.spec_table is None):
            raise ValueError('spec requires either rows or spec_table')
        return self

class Question(Model):
    q: Annotated[Text, Field(max_length=200)]
    a: Annotated[Text, Field(max_length=1000)]

class FAQ(Section):
    type: Literal['faq']
    items: Annotated[list[Question], Field(min_length=1,max_length=10)]

class Notice(Section):
    type: Literal['notice']
    body: Body

SectionType = Annotated[Hero | Pain | Solution | Features | HowTo | Review | Spec | FAQ | Notice | Stats | Targets | Structure | Gallery | ImageSection | Cases, Field(discriminator='type')]

class Document(Model):
    schema_version: Literal['1.0', '1.1']
    product: Product
    sections: Annotated[list[SectionType], Field(min_length=1,max_length=20)]

    @model_validator(mode='after')
    def structure(self):
        if sum(s.type=='hero' for s in self.sections)!=1:
            raise ValueError('sections: exactly one hero required')
        if self.schema_version == '1.0' and any(
            s.type in ('stats', 'targets', 'structure', 'gallery', 'image')
            or isinstance(s, Spec) and s.spec_table is not None for s in self.sections
        ):
            raise ValueError('new sections require schema_version 1.1')
        ids=[s.id for s in self.sections]
        if len(set(ids))!=len(ids):
            raise ValueError('sections.id: duplicate id')
        return self
