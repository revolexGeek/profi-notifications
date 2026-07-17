"""Источник заявки — часть идентичности для дедупа."""

from enum import StrEnum


class Source(StrEnum):
    PROFI = "profi"
