"""Seller-owned facts; no generated commercial data."""
from typing import Annotated, Literal
from pathlib import Path
from pydantic import Field, model_validator
from .schema import Model, Product, ReviewItem, Text, Body, Document
from .collect import collect_images
from .images import Processing

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
    role: Literal['hero','feature','solution','other']
    alt: Text | None = None
    processing: Processing = Field(default_factory=Processing)
    derived_path: Text | None = None

    @property
    def effective_path(self) -> str:
        return self.derived_path or self.path

class ProductFacts(Model):
    schema_version: Literal['1.0']
    product: Product
    facts: list[Fact]
    images: list[ImageRef]
    reviews: Annotated[list[ReviewItem], Field(max_length=10)] = Field(default_factory=list)
    notice: Body | None = None

    @model_validator(mode='after')
    def ids(self):
        ids=[fact.id for fact in self.facts]
        if len(ids)!=len(set(ids)):
            raise ValueError('facts.id: duplicate id')
        return self

    def validate_images(self, image_dir: Path):
        if not self.images:
            raise ValueError('images: at least one image required')
        sections=[{'id':'hero-1','type':'hero','headline':'검증','image':self.images[0].path}]
        # Use M1 validation for every supplied image, including unused role images.
        sections += [{'id':f'solution-{i}','type':'solution','title':'검증','body':'검증','image':image.path} for i,image in enumerate(self.images[1:],1)]
        document=Document.model_validate({'schema_version':'1.0','product':self.product.model_dump(),'sections':sections})
        return collect_images(document,image_dir)
