"""Strict versioned input contract for the nine supported sections."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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
    price: Text
    brand_color: Annotated[str, StringConstraints(pattern=r'^#[0-9a-fA-F]{6}$')]

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

class Spec(Section):
    type: Literal['spec']
    rows: Annotated[list[Annotated[list[Text], Field(min_length=2,max_length=2)]], Field(min_length=1,max_length=10)]

class Question(Model):
    q: Annotated[Text, Field(max_length=200)]
    a: Annotated[Text, Field(max_length=1000)]

class FAQ(Section):
    type: Literal['faq']
    items: Annotated[list[Question], Field(min_length=1,max_length=10)]

class Notice(Section):
    type: Literal['notice']
    body: Body

SectionType = Annotated[Hero | Pain | Solution | Features | HowTo | Review | Spec | FAQ | Notice, Field(discriminator='type')]

class Document(Model):
    schema_version: Literal['1.0']
    product: Product
    sections: Annotated[list[SectionType], Field(min_length=1,max_length=20)]

    @model_validator(mode='after')
    def structure(self):
        if sum(s.type=='hero' for s in self.sections)!=1:
            raise ValueError('sections: exactly one hero required')
        ids=[s.id for s in self.sections]
        if len(set(ids))!=len(ids):
            raise ValueError('sections.id: duplicate id')
        return self
