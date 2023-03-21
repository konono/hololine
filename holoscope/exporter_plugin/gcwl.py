#!/usr/bin/env python
# -*- coding: utf-8 -*-

import arrow
import boto3
import datetime
import json
import logging
import os.path
import re
import socket
import textwrap

from ..datamodel import GCalEvent
from ..datamodel import LiveEvent
from ..token_manager import TokenManager

from linebot import LineBotApi
from linebot.models import TextSendMessage

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from icalendar import Calendar
from icalendar import Event

log = logging.getLogger(__name__)
timeout_in_sec = 5
socket.setdefaulttimeout(timeout_in_sec)

CALENDAR_API_SERVICE_NAME = 'calendar'
CALENDAR_API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/calendar']
TZ = "Asia/Tokyo"
ISO861FORMAT = 'YYYY-MM-DDTHH:mm:ss.SSSSSS'

PAST = 7
FUTURE = 120


class Exporter(object):
    def __init__(self, config) -> None:
        token_manager = TokenManager(config, token_type='google_calendar')
        self.calendar = build(
            CALENDAR_API_SERVICE_NAME,
            CALENDAR_API_VERSION,
            credentials=token_manager._get_token()
        )
        self.calendar_id = config.google_calendar.calendar_id
        self.holomenbers = config.holodule.holomenbers
        self.events = self._get_events()
        self.linebot = LineBotApi(config.line.line_channel_access_token)
        if config.aws.access_key_id and config.aws.secret_access_key:
            self.s3 = boto3.client('s3',
                                   aws_access_key_id=config.aws.access_key_id,
                                   aws_secret_access_key=config.aws.secret_access_key)
            self.s3_bucket = config.aws.s3_bucket

    def _create_ics(self, title_str, live_event) -> str:
        if live_event.actual_start_time:
            start_dateTime = live_event.actual_start_time.to(TZ).format('YYYYMMDD HH:mm:ss')
            end_dateTime = live_event.actual_start_time.shift(hours=+1)\
                .to(TZ).format('YYYYMMDD HH:mm:ss')
            if live_event.actual_end_time:
                end_dateTime = live_event.actual_end_time.to(TZ).format('YYYYMMDD HH:mm:ss')
        else:
            start_dateTime = live_event.scheduled_start_time.to(TZ).format('YYYYMMDD HH:mm:ss')
            end_dateTime = live_event.scheduled_start_time.shift(hours=+1)\
                .to(TZ).format('YYYYMMDD HH:mm:ss')
        cal = Calendar()
        cal.creator = 'Hololine'
        cal.add('prodid', '-//Okayun Calendar//product//ja//')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'REQUEST')

        # イベント作成
        event = Event()
        event.add('summary', f'{title_str}')
        event.add('dtstart', datetime.datetime.strptime(start_dateTime, '%Y%m%d %H:%M:%S'))
        event.add('dtend', datetime.datetime.strptime(end_dateTime, '%Y%m%d %H:%M:%S'))
        event.add('description', textwrap.dedent(f'''タイトル: {title_str}
        チャンネル: {live_event.channel_title}
        配信URL: https://www.youtube.com/watch?v={live_event.id}
        '''))

        cal.add_component(event)

        # icsファイル作成
        path = f'/tmp/{live_event.id}.ics'
        f = open(path, 'wb')
        f.write(cal.to_ical())
        f.close()
        return path

    def _ics_upload(self, path) -> str:
        file_name = os.path.basename(path)
        self.s3.upload_file(path, self.s3_bucket, file_name)
        return file_name

    def _create_presigned_url(self, bucket_key) -> str:
        presigned_url = self.s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': self.s3_bucket, 'Key': bucket_key},
            ExpiresIn=86400,
            HttpMethod='GET')
        return presigned_url

    def _get_events(self, past: int = PAST, future: int = FUTURE) -> list:
        # 指定されたカレンダーからeventを取得
        events = []
        now = arrow.utcnow()
        past = now.shift(days=-past).format(ISO861FORMAT) + 'Z'
        future = now.shift(days=future).format(ISO861FORMAT) + 'Z'
        try:
            # Call the Calendar API
            responses = self.calendar.events().list(calendarId=self.calendar_id,
                                                    timeMin=(past),
                                                    timeMax=(future),
                                                    maxResults=250, singleEvents=True,
                                                    orderBy='startTime').execute()
            responses = responses.get('items', [])
            if not responses:
                log.error('Upcomming events was not found.')
                return events
            log.debug('CALENDAR EVENT JSON DUMP')
            log.debug(json.dumps(responses))
            for resp in responses:
                events.append(GCalEvent(resp))
                if(events[-1].scheduled_start_time.to(TZ) > arrow.utcnow().to(TZ)):
                    log.info(f'Schedule found {events[-1].title}.')
            return events
        except HttpError as error:
            log.error(f'An error occurred: {error}.')

    def create_event(self, live_events: list) -> None:
        for live_event in live_events:
            log.info(f'[{live_event.id}]: scheduled_start_time is ' +
                     f'{live_event.scheduled_start_time.to(TZ)}')
            log.info(f'[{live_event.id}]: utcnow is {arrow.utcnow().to(TZ)}')
            log.info(f'[{live_event.id}]: difference is ' +
                     f'{(live_event.scheduled_start_time.to(TZ) - arrow.utcnow().to(TZ)).seconds}')

            if live_event.collaborate:
                title_str = (f'[{", ".join(live_event.collaborate)} コラボ] ' +
                             f'{live_event.channel_title}: {live_event.title}')
            else:
                title_str = f'{live_event.channel_title}: {live_event.title}'
            if live_event.actual_start_time:
                start_dateTime = live_event.actual_start_time.format(ISO861FORMAT) + 'Z'
                start_dateTimeJST = live_event.actual_start_time.to(TZ).format('YYYY/MM/DD HH:mm:ss')
                end_dateTime = live_event.actual_start_time.shift(hours=+1).format(ISO861FORMAT) + 'Z'
                end_dateTimeJST = live_event.actual_start_time.shift(hours=+1)\
                    .to(TZ).format('YYYY/MM/DD HH:mm:ss') + '(仮)'
                if live_event.actual_end_time:
                    end_dateTime = live_event.actual_end_time.format(ISO861FORMAT) + 'Z'
                    end_dateTimeJST = live_event.actual_end_time.to(TZ).format('YYYY/MM/DD HH:mm:ss')
            else:
                start_dateTime = live_event.scheduled_start_time.format(ISO861FORMAT) + 'Z'
                start_dateTimeJST = live_event.scheduled_start_time.to(TZ).format('YYYY/MM/DD HH:mm:ss')
                end_dateTime = live_event.scheduled_start_time.shift(hours=+1).format(ISO861FORMAT) + 'Z'
                end_dateTimeJST = live_event.scheduled_start_time.shift(hours=+1)\
                    .to(TZ).format('YYYY/MM/DD HH:mm:ss') + '(仮)'
            LINE_MESSAGE_TEMPLATE = f'タイトル: {title_str}\n'\
                                    f'チャンネル: {live_event.channel_title}\n'\
                                    f'開始時刻: {start_dateTimeJST}\n'\
                                    f'終了時刻: {end_dateTimeJST}\n'\
                                    f'配信URL: https://www.youtube.com/watch?v={live_event.id}'
            body = {
                # 予定のタイトル
                'summary': f'{title_str}',
                'description':
                textwrap.dedent(f'''チャンネル: {live_event.channel_title}
                 タイトル: {live_event.title}

                 配信URL: https://www.youtube.com/watch?v={live_event.id}
                '''),
                # 予定の開始時刻
                'start': {
                    'dateTime': start_dateTime,
                    'timeZone': 'Japan'
                },
                # 予定の終了時刻
                'end': {
                    'dateTime': end_dateTime,
                    'timeZone': 'Japan'
                },
                'extendedProperties': {
                    'private': {
                        "video_id": live_event.id,
                        "title": live_event.title,
                        "channel_id": live_event.channel_id,
                        "actor": live_event.actor,
                        "scheduled_start_time": live_event.scheduled_start_time.format(ISO861FORMAT),
                    }
                },
            }
            if live_event.collaborate:
                body["extendedProperties"]["private"]["collaborate"] = ",".join(live_event.collaborate)

            # ここではlive_eventとcalendarのイベントに違いがあるかを探している、相違があった場合はupdate_eventに進む
            if (event := [event for event in self.events if live_event.id == event.video_id]):
                event = event[0]
                if title_str != event.title:
                    line_first_line = "【通知】タイトルが変更になりました\n"
                    self._update_event(event.id, live_event)
                    log.info(f'[{live_event.id}]: Update the scheduled {live_event.title}.')
                    path = self._create_ics(title_str, live_event)
                    bucket_key = self._ics_upload(path)
                    presigned_url = self._create_presigned_url(bucket_key)
                    last_line = f'\nカレンダーに登録: {presigned_url}'
                    line_message_text = line_first_line + LINE_MESSAGE_TEMPLATE + last_line
                    self.linebot.broadcast(TextSendMessage(text=line_message_text))
                    log.info(f'[{live_event.id}]: Push message to channel {line_message_text}')
                    continue
                if live_event.actual_start_time:
                    if live_event.actual_start_time.to(TZ) != event.start_dateTime:
                        self._update_event(event.id, live_event)
                        log.info(f'[{live_event.id}]: Update the scheduled {live_event.title}.')
                        # すでにactual_end_timeがgoogle calendarの中にあった場合はLineで通知しない
                        if not event.actual_start_time:
                            line_first_line = "【通知】配信が開始されました\n"
                            line_message_text = line_first_line + LINE_MESSAGE_TEMPLATE
                            self.linebot.broadcast(TextSendMessage(text=line_message_text))
                        log.info(f'[{live_event.id}]: Push message to channel {line_message_text}')
                        continue
                elif live_event.scheduled_start_time.to(TZ) != event.start_dateTime:
                    line_first_line = "【通知】時刻が変更されました\n"
                    self._update_event(event.id, live_event)
                    log.info(f'[{live_event.id}]: Update the scheduled {live_event.title}.')
                    path = self._create_ics(title_str, live_event)
                    bucket_key = self._ics_upload(path)
                    presigned_url = self._create_presigned_url(bucket_key)
                    last_line = f'\nカレンダーに登録: {presigned_url}'
                    line_message_text = line_first_line + LINE_MESSAGE_TEMPLATE + last_line
                    self.linebot.broadcast(TextSendMessage(text=line_message_text))
                    log.info(f'[{live_event.id}]: Push message to channel {line_message_text}')
                    continue
                elif live_event.scheduled_start_time.to(TZ) > arrow.utcnow().to(TZ):
                    if (live_event.scheduled_start_time.to(TZ) - arrow.utcnow().to(TZ))\
                            .seconds <= 900:
                        line_first_line = "【通知】配信がもうすぐ開始します！\n"
                        line_message_text = line_first_line + LINE_MESSAGE_TEMPLATE
                        self.linebot.broadcast(TextSendMessage(text=line_message_text))
                        log.info(f'[{live_event.id}]: Push message to channel {line_message_text}')
                if live_event.actual_end_time:
                    if live_event.actual_end_time.to(TZ) != event.end_dateTime:
                        self._update_event(event.id, live_event)
                        log.info(f'[{live_event.id}]: Update the scheduled {live_event.title}.')
                        # すでにactual_end_timeがgoogle calendarの中にあった場合はLineで通知しない
                        if not event.actual_end_time:
                            line_first_line = "【通知】配信が終了しました\n"
                            line_message_text = line_first_line + LINE_MESSAGE_TEMPLATE
                            self.linebot.broadcast(TextSendMessage(text=line_message_text))
                            log.info(f'[{live_event.id}]: Push message to channel {line_message_text}')
                            continue
                log.info(f'[{live_event.id}]: {live_event.title} is already scheduled.')
                continue
            else:
                if live_event.scheduled_start_time > arrow.utcnow().shift(days=FUTURE):
                    log.info(f'[{live_event.id}]: {title_str} was not scheduled, ' +
                             f'because it is {FUTURE} days away.')
                    continue
                line_first_line = "【通知】新しい予定が追加されました\n"
                event = self.calendar.events().insert(calendarId=self.calendar_id,
                                                      body=body).execute()
                log.info(f'[{live_event.id}]: Create {title_str} has been scheduled.')
                path = self._create_ics(title_str, live_event)
                bucket_key = self._ics_upload(path)
                presigned_url = self._create_presigned_url(bucket_key)
                log.info(f'[{live_event.id}]: Create presigned_url: {presigned_url}')
                last_line = f'\nカレンダーに登録: {presigned_url}'
                line_message_text = line_first_line + LINE_MESSAGE_TEMPLATE + last_line
                self.linebot.broadcast(TextSendMessage(text=line_message_text))
                log.info(f'[{live_event.id}]: Push message to channel {line_message_text}')

    def _update_event(self, event_id: str, live_event: LiveEvent):
        if live_event.collaborate:
            title_str = (f'[{", ".join(live_event.collaborate)} コラボ] ' +
                         f'{live_event.channel_title}: {live_event.title}')
        else:
            title_str = f'{live_event.channel_title}: {live_event.title}'
        if live_event.actual_start_time:
            start_dateTime = live_event.actual_start_time.format(ISO861FORMAT) + 'Z'
            end_dateTime = live_event.actual_start_time.shift(hours=+1).format(ISO861FORMAT) + 'Z'
            actual_start_time = live_event.actual_start_time
            if live_event.actual_end_time:
                end_dateTime = live_event.actual_end_time.format(ISO861FORMAT) + 'Z'
                actual_end_time = live_event.actual_end_time
        else:
            start_dateTime = live_event.scheduled_start_time.format(ISO861FORMAT) + 'Z'
            end_dateTime = live_event.scheduled_start_time.shift(hours=+1).format(ISO861FORMAT) + 'Z'
        body = {
            # 予定のタイトル
            'summary': f'{title_str}',
            'description':
            textwrap.dedent(f'''チャンネル: {live_event.channel_title}
             タイトル: {live_event.title}

              配信URL: https://www.youtube.com/watch?v={live_event.id}
            '''),
            # 予定の開始時刻
            'start': {
                'dateTime': start_dateTime,
                'timeZone': 'Japan'
            },
            # 予定の終了時刻
            'end': {
                'dateTime': end_dateTime,
                'timeZone': 'Japan'
            },
            'extendedProperties': {
                'private': {
                    "video_id": live_event.id,
                    "title": live_event.title,
                    "channel_id": live_event.channel_id,
                    "actor": live_event.actor,
                    "scheduled_start_time": live_event.scheduled_start_time.format(ISO861FORMAT)
                }
            },
        }
        if live_event.collaborate:
            body["extendedProperties"]["private"]["collaborate"] = ",".join(live_event.collaborate)
        if actual_start_time:
            body["extendedProperties"]["private"]["actual_start_time"] = actual_start_time\
                .format(ISO861FORMAT)
        if actual_end_time:
            body["extendedProperties"]["private"]["actual_end_time"] = actual_end_time.format(ISO861FORMAT)
        self.calendar.events().update(calendarId=self.calendar_id,
                                      eventId=event_id,
                                      body=body).execute()

    def delete_deplicate_event(self, live_events: list):
        pattern = re.compile(r'^\[\D*\sコラボ\]')
        for i in self.holomenbers:
            for live_event in live_events:
                if not live_event.collaborate and live_event.actor == i:
                    for e in self.events:
                        match = pattern.match(e.title)
                        if match:
                            collabo_title = match.group()
                        else:
                            continue
                        if i not in collabo_title:
                            continue
                        if e.scheduled_start_time:
                            sst = live_event.scheduled_start_time
                            if e.scheduled_start_time == sst:
                                self.calendar.events().delete(calendarId=self.calendar_id,
                                                              eventId=e.id).execute()
                                log.info(f'[{e.id}] was deleted because deplicate {e.title}.')
