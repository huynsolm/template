"""Seller-owned facts; no generated commercial data."""
import re
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

# M8-B image origin. None (the default, omitted from JSON) is a real photo.
AI_SOURCES = ('ai_edited', 'ai_generated')
AI_GENERATED_ROLES = ('lifestyle',)  # fully generated images: mood/scene pictures only
# A tool name only: letters, digits, spaces and a little punctuation; no domains, no token-like runs.
TOOL_NAME = re.compile(r'[0-9A-Za-z가-힣 ()+\-_.]{1,40}')
DOMAIN_LIKE = re.compile(r'[0-9A-Za-z-]\.[A-Za-z]{2,}')
TOKEN_LIKE = re.compile(r'(AIza|sk-|ghp_|gho_|github_pat_|xox[abp]-|glpat-|ya29\.)|[0-9A-Za-z_\-]{20,}')


def tool_name_ok(name: str) -> bool:
    return bool(TOOL_NAME.fullmatch(name)) and not DOMAIN_LIKE.search(name) and not TOKEN_LIKE.search(name)


def same_name(path: str) -> str:
    """Compare image names as the file system would (``./a.png`` and ``x/../a.png`` are ``a.png``)."""
    import posixpath
    return posixpath.normpath(path.replace('\\', '/'))


class ImageRef(Model):
    path: Text
    role: Literal['hero','feature','solution','other','detail','lifestyle','diagram']
    alt: Text | None = None
    processing: Processing = Field(default_factory=Processing)
    derived_path: Text | None = None
    document_confirmed: bool = False
    source: Literal['ai_edited','ai_generated'] | None = None
    based_on: Text | None = None
    generator: Annotated[Text, Field(max_length=40)] | None = None
    edit_request: Annotated[Text, Field(max_length=300)] | None = None

    @property
    def effective_path(self) -> str:
        return self.derived_path or self.path

    @property
    def origin(self) -> str:
        return self.source or 'photo'

    @model_validator(mode='after')
    def provenance(self):
        if self.source is None:
            if self.based_on or self.generator or self.edit_request:
                raise ValueError('실제 사진에는 원본·생성 도구·요청 내용을 적지 않습니다.')
            return self
        if not self.generator:
            raise ValueError('AI로 만든 이미지는 사용한 도구 이름(예: ChatGPT, Gemini)을 적어 주세요.')
        if not tool_name_ok(self.generator):
            raise ValueError('생성 도구에는 이름만 적어 주세요(주소·계정 정보 불가).')
        if self.source == 'ai_edited' and not self.based_on:
            raise ValueError('AI로 배경을 바꾼 사진은 원본 사진을 선택해야 합니다.')
        if self.source == 'ai_generated':
            if self.based_on:
                raise ValueError('AI 생성 이미지에는 원본 사진을 지정하지 않습니다.')
            if self.role not in AI_GENERATED_ROLES:
                raise ValueError('AI 생성 이미지는 사용 장면(분위기) 역할에만 쓸 수 있습니다.')
        return self

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
        photos={same_name(image.path) for image in self.images if image.source is None}
        for index,image in enumerate(self.images,1):
            if image.based_on is not None and (same_name(image.based_on)==same_name(image.path) or same_name(image.based_on) not in photos):
                raise ValueError(f'사진 {index}: 원본은 같은 작업의 실제 사진이어야 합니다.')
            if image.source is not None and same_name(image.path) in photos:
                raise ValueError(f'사진 {index}: 같은 파일을 실제 사진과 AI 이미지로 함께 쓸 수 없습니다.')
        if self.images and all(image.source=='ai_generated' for image in self.images):
            raise ValueError('대표 사진으로 쓸 실제 사진(또는 배경만 바꾼 사진)이 한 장 이상 필요합니다. AI 생성 이미지는 사용 장면에만 쓰입니다.')
        return self

    def validate_images(self, image_dir: Path):
        if not self.images:
            raise ValueError('images: at least one image required')
        sections=[{'id':'hero-1','type':'hero','headline':'검증','image':self.images[0].path}]
        # Use M1 validation for every supplied image, including unused role images.
        sections += [{'id':f'solution-{i}','type':'solution','title':'검증','body':'검증','image':image.path} for i,image in enumerate(self.images[1:],1)]
        document=Document.model_validate({'schema_version':'1.0','product':self.product.model_dump(),'sections':sections})
        return collect_images(document,image_dir)

