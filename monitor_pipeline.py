#!/usr/bin/env python3
"""
파이프라인 진행 상황 실시간 모니터링

사용법:
  python monitor_pipeline.py <project_id>
  python monitor_pipeline.py <project_id> --watch
  python monitor_pipeline.py <project_id> --export report.json
"""

import argparse
import asyncio
import json
import time
from datetime import datetime
from typing import Optional
import httpx


BASE_URL = "http://localhost:8000"


async def get_project_status(project_id: str):
    """프로젝트 전체 상태 조회"""
    async with httpx.AsyncClient() as client:
        # 1. Jobs 조회
        try:
            response = await client.get(f"{BASE_URL}/api/jobs/project/{project_id}")
            response.raise_for_status()
            jobs = response.json()
        except Exception as e:
            jobs = []
            print(f"⚠️  Jobs 조회 실패: {e}")

        # 2. Targets 조회
        try:
            response = await client.get(f"{BASE_URL}/api/projects/{project_id}/targets")
            response.raise_for_status()
            targets = response.json()
        except Exception as e:
            targets = []
            print(f"⚠️  Targets 조회 실패: {e}")

        # 3. Segments 조회
        try:
            response = await client.get(f"{BASE_URL}/api/segments/project/{project_id}")
            response.raise_for_status()
            segments = response.json()
        except Exception as e:
            segments = []
            print(f"⚠️  Segments 조회 실패: {e}")

        # 4. Assets 조회
        try:
            response = await client.get(f"{BASE_URL}/api/assets/project/{project_id}")
            response.raise_for_status()
            assets = response.json()
        except Exception as e:
            assets = []
            print(f"⚠️  Assets 조회 실패: {e}")

        return {
            "project_id": project_id,
            "jobs": jobs,
            "targets": targets,
            "segments": segments,
            "assets": assets,
            "timestamp": datetime.now().isoformat(),
        }


def print_status(status: dict, clear_screen: bool = False):
    """상태 출력"""
    if clear_screen:
        print("\033[2J\033[H")  # Clear screen

    print("=" * 80)
    print(f"📊 Project Status: {status['project_id']}")
    print(f"🕐 Updated: {status['timestamp']}")
    print("=" * 80)

    # Jobs
    print(f"\n📝 Jobs ({len(status['jobs'])})")
    print("-" * 80)
    if status['jobs']:
        for job in status['jobs']:
            job_id = job.get('job_id', 'N/A')
            job_status = job.get('status', 'N/A')
            target_lang = job.get('target_lang', 'N/A')
            created = job.get('created_at', 'N/A')

            status_emoji = {
                'queued': '⏳',
                'in_progress': '🔄',
                'done': '✅',
                'failed': '❌',
            }.get(job_status, '❓')

            print(f"  {status_emoji} [{job_id[:8]}...] {target_lang:5s} | {job_status:12s} | {created}")

            # History 표시
            history = job.get('history', [])
            if history:
                latest = history[-1]
                print(f"     Latest: {latest.get('status')} - {latest.get('message', 'N/A')}")
    else:
        print("  (No jobs)")

    # Targets
    print(f"\n🎯 Targets ({len(status['targets'])})")
    print("-" * 80)
    if status['targets']:
        for target in status['targets']:
            lang = target.get('language_code', 'N/A')
            target_status = target.get('status', 'N/A')
            progress = target.get('progress', 0)

            status_emoji = {
                'pending': '⏳',
                'processing': '🔄',
                'completed': '✅',
                'failed': '❌',
            }.get(target_status, '❓')

            # Progress bar
            bar_length = 20
            filled = int(bar_length * progress / 100)
            bar = '█' * filled + '░' * (bar_length - filled)

            print(f"  {status_emoji} {lang:5s} | {bar} {progress:3d}% | {target_status}")
    else:
        print("  (No targets)")

    # Segments
    print(f"\n📐 Segments ({len(status['segments'])})")
    print("-" * 80)
    if status['segments']:
        # 처음 5개만 표시
        for seg in status['segments'][:5]:
            idx = seg.get('segment_index', 'N/A')
            speaker = seg.get('speaker_tag', 'N/A')
            start = seg.get('start', 0)
            end = seg.get('end', 0)
            text = seg.get('source_text', '')[:50]

            print(f"  [{idx:3}] {speaker:12s} | {start:6.2f}s - {end:6.2f}s | {text}...")

        if len(status['segments']) > 5:
            print(f"  ... and {len(status['segments']) - 5} more segments")
    else:
        print("  (No segments)")

    # Assets
    print(f"\n🎬 Assets ({len(status['assets'])})")
    print("-" * 80)
    if status['assets']:
        for asset in status['assets']:
            lang = asset.get('language_code', 'N/A')
            asset_type = asset.get('asset_type', 'N/A')
            file_path = asset.get('file_path', 'N/A')

            print(f"  📦 {lang:5s} | {asset_type:15s} | {file_path}")
    else:
        print("  (No assets)")

    print("\n" + "=" * 80)


async def watch_project(project_id: str, interval: int = 2):
    """프로젝트 상태 실시간 모니터링"""
    print(f"🔍 Watching project {project_id}... (Press Ctrl+C to stop)")
    print(f"⏱️  Refresh interval: {interval}s\n")

    try:
        while True:
            status = await get_project_status(project_id)
            print_status(status, clear_screen=True)
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n👋 Stopped monitoring")


async def export_status(project_id: str, output_file: str):
    """상태를 JSON 파일로 내보내기"""
    status = await get_project_status(project_id)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

    print(f"✅ Status exported to {output_file}")


async def compare_snapshots(project_id: str, file1: str, file2: str):
    """두 스냅샷 비교"""
    with open(file1, 'r') as f:
        snap1 = json.load(f)

    with open(file2, 'r') as f:
        snap2 = json.load(f)

    print("=" * 80)
    print(f"📊 Comparing snapshots for project {project_id}")
    print(f"  Snapshot 1: {snap1['timestamp']}")
    print(f"  Snapshot 2: {snap2['timestamp']}")
    print("=" * 80)

    # Jobs 비교
    jobs1 = {j['job_id']: j for j in snap1.get('jobs', [])}
    jobs2 = {j['job_id']: j for j in snap2.get('jobs', [])}

    print("\n📝 Jobs Changes:")
    for job_id in set(jobs1.keys()) | set(jobs2.keys()):
        j1 = jobs1.get(job_id)
        j2 = jobs2.get(job_id)

        if not j1:
            print(f"  ➕ New job: {job_id}")
        elif not j2:
            print(f"  ➖ Removed job: {job_id}")
        elif j1['status'] != j2['status']:
            print(f"  🔄 {job_id}: {j1['status']} → {j2['status']}")

    # Targets 비교
    targets1 = {t['language_code']: t for t in snap1.get('targets', [])}
    targets2 = {t['language_code']: t for t in snap2.get('targets', [])}

    print("\n🎯 Targets Changes:")
    for lang in set(targets1.keys()) | set(targets2.keys()):
        t1 = targets1.get(lang)
        t2 = targets2.get(lang)

        if not t1:
            print(f"  ➕ New target: {lang}")
        elif not t2:
            print(f"  ➖ Removed target: {lang}")
        else:
            if t1['progress'] != t2['progress']:
                print(f"  📈 {lang}: {t1['progress']}% → {t2['progress']}%")
            if t1['status'] != t2['status']:
                print(f"  🔄 {lang}: {t1['status']} → {t2['status']}")

    # Segments/Assets 개수 비교
    print(f"\n📐 Segments: {len(snap1.get('segments', []))} → {len(snap2.get('segments', []))}")
    print(f"🎬 Assets: {len(snap1.get('assets', []))} → {len(snap2.get('assets', []))}")


async def main():
    parser = argparse.ArgumentParser(description="파이프라인 진행 상황 모니터링")
    parser.add_argument("project_id", help="Project ID")
    parser.add_argument("--watch", "-w", action="store_true", help="실시간 모니터링 (자동 갱신)")
    parser.add_argument("--interval", "-i", type=int, default=2, help="갱신 간격 (초, 기본값: 2)")
    parser.add_argument("--export", "-e", help="상태를 JSON 파일로 내보내기")
    parser.add_argument("--compare", "-c", nargs=2, metavar=("FILE1", "FILE2"),
                       help="두 스냅샷 파일 비교")

    args = parser.parse_args()

    if args.compare:
        await compare_snapshots(args.project_id, args.compare[0], args.compare[1])
    elif args.watch:
        await watch_project(args.project_id, args.interval)
    elif args.export:
        await export_status(args.project_id, args.export)
    else:
        # 단일 조회
        status = await get_project_status(args.project_id)
        print_status(status)


if __name__ == "__main__":
    asyncio.run(main())
