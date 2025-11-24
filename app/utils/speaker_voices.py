"""보이스 메타데이터를 speaker_voices 구조로 변환하는 유틸리티 함수."""

from typing import Any, Dict, List, Optional


def build_speaker_voices_dict(
    speakers_list: Optional[List[Dict[str, Any]]] = None,
    speaker_refs: Optional[Dict[str, Any]] = None,
    voice_replacements: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    스피커 메타데이터를 speaker_voices 딕셔너리 구조로 변환합니다.

    Args:
        speakers_list: 스피커 정보 딕셔너리 리스트 (키: speaker, voice_sample_key, prompt_text, voice_replacement)
        speaker_refs: 스피커를 참조 정보로 매핑하는 딕셔너리 (키: ref_wav_key, prompt_text)
        voice_replacements: 스피커를 교체 정보로 매핑하는 딕셔너리 (키: voice_sample_id, similarity, sample_key)

    Returns:
        {speaker: {default_voice: {...}, replace_voice: {...}}} 형식의 딕셔너리
    """
    speaker_voices_dict: Dict[str, Dict[str, Any]] = {}

    # speakers_list 처리 (우선 형식)
    if speakers_list:
        for speaker_info in speakers_list:
            speaker = speaker_info.get("speaker")
            if not speaker:
                continue

            default_voice = {
                "ref_wav_key": speaker_info.get("voice_sample_key", ""),
                "prompt_text": speaker_info.get("prompt_text", ""),
            }

            speaker_voices_dict[speaker] = {
                "default_voice": default_voice,
            }

            # speaker_info에 voice_replacement가 있으면 replace_voice 추가
            voice_replacement = speaker_info.get("voice_replacement")
            if voice_replacement and isinstance(voice_replacement, dict):
                replace_voice = {
                    "voice_sample_id": voice_replacement.get("voice_sample_id"),
                    "similarity": voice_replacement.get("similarity"),
                    "sample_key": voice_replacement.get("sample_key"),
                }
                speaker_voices_dict[speaker]["replace_voice"] = replace_voice

    # speakers_list가 비어있으면 speaker_refs로 폴백
    if not speaker_voices_dict and speaker_refs:
        for speaker, ref_info in speaker_refs.items():
            if isinstance(ref_info, dict):
                default_voice = {
                    "ref_wav_key": ref_info.get("ref_wav_key", ""),
                    "prompt_text": ref_info.get("prompt_text", ""),
                }
            else:
                default_voice = {
                    "ref_wav_key": str(ref_info),
                    "prompt_text": "",
                }

            speaker_voices_dict[speaker] = {
                "default_voice": default_voice,
            }

    # voice_replacements 딕셔너리가 제공되면 replace_voice 추가
    if voice_replacements:
        for speaker, replacement_info in voice_replacements.items():
            if speaker in speaker_voices_dict and isinstance(replacement_info, dict):
                replace_voice = {
                    "voice_sample_id": replacement_info.get("voice_sample_id"),
                    "similarity": replacement_info.get("similarity"),
                    "sample_key": replacement_info.get("sample_key"),
                }
                speaker_voices_dict[speaker]["replace_voice"] = replace_voice

    return speaker_voices_dict
