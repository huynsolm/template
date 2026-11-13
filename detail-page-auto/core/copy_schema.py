"""AI produces copy only, never seller-owned product/review/price fields."""
from typing import Annotated
from pydantic import Field
from .schema import Model, Text, Title, Short, Body

class Grounded(Model):
    fact_ids: list[Text]

class HeroCopy(Grounded):
    headline: Title
    subcopy: Short

class CopyText(Grounded):
    text: Short

class PainCopy(Grounded):
    title: Title
    items: Annotated[list[CopyText], Field(min_length=1,max_length=10)]

class SolutionCopy(Grounded):
    title: Title
    body: Body

class FeatureCopy(Grounded):
    title: Title
    desc: Short

class QuestionCopy(Grounded):
    q: Annotated[Text, Field(max_length=200)]
    a: Annotated[Text, Field(max_length=1000)]

class CopyDraft(Model):
    hero: HeroCopy
    pain: PainCopy
    solution: SolutionCopy
    features: Annotated[list[FeatureCopy], Field(min_length=1,max_length=10)]
    how_to: Annotated[list[FeatureCopy], Field(min_length=1,max_length=10)]
    faq: Annotated[list[QuestionCopy], Field(min_length=1,max_length=10)]
