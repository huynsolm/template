"""Seller-owned facts; no generated commercial data."""
from typing import Annotated, Literal
from pathlib import Path
from pydantic import Field, ValidationInfo, field_validator, model_validator
from .schema import Model, Product, ReviewItem, Text, Body, Document, Highlight, SpecTable, StructureItem, Title
from .collect import collect_images
from .images import Processing

class PendingClaim(Model):
    text: Text = Field(max_length=500)
    evidence: Text | None = None


class Fact(Model):
    id: Text
    text: Annotated[Text, Field(max_length=500)]
    kind: Literal['spec','feature','usage','claim','other']
    evidence: Text | None = None

    @model_validator(mode='after')
    def claim_evidence(self):
        if self.kind=='claim' and not self.evidence:
            raise ValueError('claim requires evidence')
        return self

class ImageRef(Model):
    path: Text
    role: Literal['hero','feature','solution','other','detail','lifestyle','diagram']
    alt: Text | None = None
    processing: Processing = Field(default_factory=Processing)
    derived_path: Text | None = None
    document_confirmed: bool = False

    @property
    def effective_path(self) -> str:
        return self.derived_path or self.path

class Reference(Model):
    id: Text
    label: Annotated[Text, Field(max_length=200)]
    kind: Literal['competitor','customer_voice','other']
    text: Annotated[Text, Field(max_length=5000)]
    source_note: Annotated[str, Field(max_length=500)] = ''

class ProductFacts(Model):
    schema_version: Literal['1.0']
    product: Product
    facts: list[Fact]
    images: list[ImageRef] = Field(max_length=20)
    reviews: Annotated[list[ReviewItem], Field(max_length=10)] = Field(default_factory=list)
    notice: Body | None = None
    references: list[Reference] = Field(default_factory=list)
    reference_names: list[Annotated[Text, Field(max_length=100)]] = Field(default_factory=list)

    pending_claims: list[PendingClaim] = Field(default_factory=list)
    uncertain: list[Text] = Field(default_factory=list)
    price_candidate: str | None = None
    spec_from_import: bool = False
    spec_verified: bool = False

    highlights: list[Highlight] = Field(default_factory=list, max_length=4)
    targets: list[Title] = Field(default_factory=list, max_length=12)
    structure: list[StructureItem] = Field(default_factory=list, max_length=8)
    spec_table: SpecTable | None = None

    @field_validator('images')
    @classmethod
    def distinct_photos(cls, images):
        if len({image.path for image in images}) > 10:
            raise ValueError('서로 다른 사진 파일은 최대 10개까지 입력할 수 있습니다.')
        return images

    @field_validator('highlights')
    @classmethod
    def highlight_evidence(cls, values, info: ValidationInfo):
        ids = {fact.id for fact in info.data.get('facts', [])}
        for index, value in enumerate(values, 1):
            if value.fact_id not in ids:
                raise ValueError(f'{index}행: 존재하지 않는 사실 ID {value.fact_id}')
        return values

    @model_validator(mode='after')
    def ids(self):
        ids=[fact.id for fact in self.facts]
        if len(ids)!=len(set(ids)):
            raise ValueError('facts.id: duplicate id')
        reference_ids=[reference.id for reference in self.references]
        if len(reference_ids)!=len(set(reference_ids)):
            raise ValueError('references.id: duplicate id')
        collision=set(ids)&set(reference_ids)
        if collision:
            raise ValueError('reference ids must not match fact ids: '+', '.join(sorted(collision)))
        if len(self.reference_names)!=len(set(self.reference_names)):
            raise ValueError('reference_names: duplicate name')
        return self

    def validate_images(self, image_dir: Path):
        if not self.images:
            raise ValueError('images: at least one image required')
        sections=[{'id':'hero-1','type':'hero','headline':'검증','image':self.images[0].path}]
        # Use M1 validation for every supplied image, including unused role images.
        sections += [{'id':f'solution-{i}','type':'solution','title':'검증','body':'검증','image':image.path} for i,image in enumerate(self.images[1:],1)]
        document=Document.model_validate({'schema_version':'1.0','product':self.product.model_dump(),'sections':sections})
        return collect_images(document,image_dir)

