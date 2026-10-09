"""Verified-quote contract (M3.3). A quote is valid only with LOCAL source provenance; see navigator.quotes."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QuoteProvenance(_Strict):
    method: Literal["local_source_match"]  # the only accepted way to verify a quote
    source_file: NonEmptyStr  # project-relative path to a LOCAL full source text
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    translator: NonEmptyStr
    edition: NonEmptyStr


class VerifiedQuote(_Strict):
    card_id: Annotated[str, Field(pattern=r"^C\d{4}$")]
    text: NonEmptyStr
    reference: NonEmptyStr  # exact reference of the quoted lines (not the card range)
    provenance: QuoteProvenance
