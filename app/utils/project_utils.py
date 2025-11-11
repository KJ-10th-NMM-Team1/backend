"""
Project 관련 유틸리티 함수들
"""
from typing import Any, List, Union, Optional


def extract_language_code(target: Union[Any, dict]) -> Optional[str]:
    """
    ProjectTarget 객체나 dict에서 language_code를 안전하게 추출

    Args:
        target: ProjectTarget Pydantic 모델 또는 dict

    Returns:
        language_code 문자열 또는 None
    """
    if hasattr(target, 'language_code'):
        return target.language_code if target.language_code else None
    elif isinstance(target, dict):
        return target.get("language_code")
    return None


def extract_language_codes(targets: List[Union[Any, dict]]) -> List[str]:
    """
    ProjectTarget 리스트에서 모든 language_code를 추출

    Args:
        targets: ProjectTarget 객체들의 리스트

    Returns:
        language_code 문자열 리스트 (빈 값 제외)
    """
    language_codes = []
    for target in targets:
        lang_code = extract_language_code(target)
        if lang_code:
            language_codes.append(lang_code)
    return language_codes