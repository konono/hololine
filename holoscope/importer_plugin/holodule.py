#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import requests

from bs4 import BeautifulSoup
from urllib.parse import parse_qs, urlparse

from ..datamodel import LiveEvent
from ..thumbnail_cache_manager import ThumbnailCacheManager
from ..utils import YoutubeUtils

log = logging.getLogger(__name__)

ACTOR_NAME_ALIASES = {
    'ラプラス': 'ラプラス・ダークネス',
    'アキロゼ': 'アキ・ローゼンタール',
}


class Importer(object):
    def __init__(self, config, youtube_instance):
        self.cnf = config
        self.youtube = youtube_instance
        self.live_events = self._get_live_events()

    def _deduplicate_live_events(self, events) -> list:
        """推しの主配信とコラボ配信の時間が重複している場合、コラボ側を除外する"""
        favorites = set(self.cnf.holodule.holomenbers)

        # 主配信（コラボなし）を (actor, scheduled_start_time) でインデックス化
        primary_keys = set()
        for e in events:
            if not e.collaborate:
                primary_keys.add((e.actor, e.scheduled_start_time))

        seen_ids = set()
        result = []
        for e in events:
            # コラボイベントが主配信と重複する場合は除外
            if e.collaborate:
                is_duplicate = any(
                    (member, e.scheduled_start_time) in primary_keys
                    for member in e.collaborate if member in favorites
                )
                if is_duplicate:
                    log.info(f'{e.title} was deleted because duplicate event.')
                    continue

            # 同一video IDの重複を排除
            if e.id in seen_ids:
                continue
            seen_ids.add(e.id)
            result.append(e)

        return result

    def _filter_and_annotate_programs(self, all_programs, thumbnail_cache) -> list:
        """推しメンバーに関連するprogramのみをフィルタし、コラボ情報を付与する"""
        favorites = set(self.cnf.holodule.holomenbers)

        # サムネイルURL → メンバー名の逆引き辞書
        thumb_to_member = {}
        for member_name, cache_entry in thumbnail_cache.items():
            url = cache_entry.get('holodule_url')
            if url:
                thumb_to_member[url] = member_name

        results = {}  # video_id をキーにして自動重複排除
        for program in all_programs:
            actor = program['actor']
            video_id = program['video_id']

            # コラボレーターのサムネイルから推しメンバーを検出
            collabs = [
                thumb_to_member[url]
                for url in program.get('collaborators', [])
                if url in thumb_to_member and thumb_to_member[url] in favorites
            ]

            is_favorite_stream = actor in favorites
            has_favorite_collab = len(collabs) > 0

            if is_favorite_stream or has_favorite_collab:
                program_copy = dict(program)
                # 推しの主配信ではcollaborateを空に、コラボ配信では推しメンバー名を格納
                program_copy['collaborate'] = [] if is_favorite_stream else collabs
                results[video_id] = program_copy

        return list(results.values())

    def _build_events_from_responses(self, programs, youtube_utils) -> list:
        """programリストからYouTube APIを呼び出し、LiveEventオブジェクトを生成する"""
        program_by_video_id = {p['video_id']: p for p in programs}
        video_ids = list(program_by_video_id.keys())

        events = []
        # YouTube APIは50件までなのでチャンク分割
        for chunk_start in range(0, len(video_ids), 50):
            chunk = video_ids[chunk_start:chunk_start + 50]
            responses = youtube_utils.get_live_events(chunk)
            log.debug('LIVE EVENT JSON DUMP')
            log.debug(json.dumps(responses))
            for resp in responses:
                if 'scheduledStartTime' not in resp.get('liveStreamingDetails', {}):
                    continue
                program = program_by_video_id.get(resp['id'])
                if program is None:
                    continue
                event = LiveEvent(resp, program['actor'], program['collaborate'])
                events.append(event)
                log.info(f'Live event found [{event.id}] {event.channel_title}:{event.title}.')

        return events

    def _get_live_events(self) -> list:
        youtube_utils = YoutubeUtils(self.youtube)
        all_programs = self._get_programs()

        # サムネイルキャッシュの構築
        thumbnail_hash = {p['actor']: {'holodule_url': p['img']} for p in all_programs}
        thumbnail_cache_manager = ThumbnailCacheManager(self.cnf, self.youtube, thumbnail_hash)
        thumbnail_cache = thumbnail_cache_manager.get_thumbnail_cache()

        # 推しメンバーに関連するprogramをフィルタ
        programs = self._filter_and_annotate_programs(all_programs, thumbnail_cache)
        log.debug(f'Contents filtered by favorite: {programs}')

        # YouTube APIからLiveEvent取得
        events = self._build_events_from_responses(programs, youtube_utils)

        return self._deduplicate_live_events(events)

    def _get_programs(self) -> list:
        programs = []
        r = requests.get(self.cnf.holodule.holodule_url, timeout=(3.0, 7.5))
        soup = BeautifulSoup(r.text, 'html.parser')
        divs = soup.find_all('div', class_="col-6 col-sm-4 col-md-3")
        for div in divs:
            a = div.find('a')
            url = urlparse(a.get("href"))
            if ('youtube.com' not in url.netloc and 'youtu.be' not in url.netloc) or '/watch' != url.path:
                continue
            s = a.find('div', class_="col text-right name").get_text()
            actor = '\n'.join(filter(lambda x: x.strip(),
                                     s.replace(" ", "").split('\n')))
            actor = ACTOR_NAME_ALIASES.get(actor, actor)
            s_img = a.find('div', class_="col col-sm col-md col-lg col-xl").find('img').attrs['src']
            imgs = a.find_all('div', class_="col col-sm col-md col-lg col-xl")
            collaborators = [
                        i.find('img').attrs['src']
                        for i in imgs
                        if i.find('img').attrs['src'] != s_img
                        ]
            video_id = parse_qs(url.query).get('v', [None])[0]
            result = {'actor': actor,
                      'collaborators': collaborators,
                      'video_id': video_id,
                      'img': s_img,
                      'collaborate': []}
            programs.append(result)
            log.debug(f'Get contents from holodule: {result}')
        return programs
