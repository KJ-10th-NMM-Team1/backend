from enum import IntEnum


class EnumStatus(IntEnum):
    SHORT = 0
    SLIGHTLY_SHORT = 1
    RETRANSLATE = 2
    SLIGHTLY_LONG = 3
    LONG = 4

    def label(self) -> str:
        return _ENUM_STATUS_LABELS[self]


_ENUM_STATUS_LABELS = {
    EnumStatus.SHORT: "짧게",
    EnumStatus.SLIGHTLY_SHORT: "조금 짧게",
    EnumStatus.RETRANSLATE: "다시 번역",
    EnumStatus.SLIGHTLY_LONG: "조금 길게",
    EnumStatus.LONG: "길게",
}
