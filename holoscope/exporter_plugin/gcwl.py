#!/usr/bin/env python
# -*- coding: utf-8 -*-

import arrow
import boto3
import json
import logging
import os.path
import re
import socket
import textwrap

from ..datamodel import GCalEvent
from ..token_manager import TokenManager

from datetime import datetime
from datetime import timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from icalendar import Calendar
from icalendar import Event

from linebot.exceptions import LineBotApiError
from linebot import LineBotApi
from linebot.models import TextSendMessage

log = logging.getLogger(__name__)
timeout_in_sec = 5
socket.setdefaulttimeout(timeout_in_sec)

CALENDAR_API_SERVICE_NAME = 'calendar'
CALENDAR_API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/calendar']
TZ = "Asia/Tokyo"
ISO861FORMAT = 'YYYY-MM-DDTHH:mm:ss.SSSSSS'
LINEFORMAT = 'YYYY/MM/DD HH:mm:ss'

PAST = 7
FUTURE = 120


def create_title(live_event):
    if live_event.collaborate:
        title = (f'[{", ".join(live_event.collaborate)} コラボ] ' +
                 f'{live_event.channel_title}: {live_event.title}')
    else:
        title = f'{live_event.channel_title}: {live_event.title}'
    return title


def create_event_dateTime(live_event, time_format):
    start_time = live_event.actual_start_time or live_event.scheduled_start_time
    end_time = live_event.actual_end_time or start_time + timedelta(hours=1)

    if time_format == LINEFORMAT:
        start_dateTime = start_time.to(TZ).format(time_format)
        end_dateTime = end_time.to(TZ).format(time_format)
    elif time_format == ISO861FORMAT:
        start_dateTime = start_time.format(time_format) + 'Z'
        end_dateTime = end_time.format(time_format) + 'Z'

    return start_dateTime, end_dateTime


class GoogleCalendar:
    def __init__(self, config):
        self.calendar_id = config.google_calendar.calendar_id
        token_manager = TokenManager(config, token_type='google_calendar')
        self.calendar_service = build(
            CALENDAR_API_SERVICE_NAME,
            CALENDAR_API_VERSION,
            credentials=token_manager._get_token())

    def _create_event_data(self, live_event):
        title = create_title(live_event)
        start_dateTime, end_dateTime = create_event_dateTime(live_event, ISO861FORMAT)
        # 予定のタイトル
        summary = f'{title}'
        description = textwrap.dedent(f'''
        チャンネル: {live_event.channel_title}
        タイトル: {live_event.title}

        配信URL: https://www.youtube.com/watch?v={live_event.id}
        '''[1:-1])
        # 予定の開始時刻
        start_time = {
            'dateTime': start_dateTime,
            'timeZone': TZ
        }
        end_time = {
                'dateTime': end_dateTime,
                'timeZone': TZ
            }
        extended_property = {
            "private": {
                "video_id": live_event.id,
                "title": live_event.title,
                "channel_id": live_event.channel_id,
                "actor": live_event.actor,
                "scheduled_start_time": live_event.scheduled_start_time.format(ISO861FORMAT),
            }
        }
        if live_event.collaborate:
            extended_property["private"]["collaborate"] = ",".join(live_event.collaborate)
        if live_event.actual_start_time:
            extended_property["private"]["actual_start_time"] = live_event.actual_start_time.\
                    format(ISO861FORMAT)
        if live_event.actual_end_time:
            extended_property["private"]["actual_end_time"] = live_event.actual_end_time.\
                    format(ISO861FORMAT)
        body = {
                'summary': summary,
                'description': description,
                'start': start_time,
                'end': end_time,
                'extendedProperties': extended_property
            }
        return body

    def create_event(self, live_event):
        body = self._create_event_data(live_event)
        try:
            created_event = self.calendar_service.events().insert(
                    calendarId=self.calendar_id, body=body).execute()
            log.info(f'[{live_event.id}]: Event created {created_event.get("htmlLink")}')
        except HttpError as error:
            log.info(f'An error occurred: {error}')
            created_event = None
        return created_event

    def update_event(self, event_id, live_event):
        body = self._create_event_data(live_event)
        try:
            updated_event = self.calendar_service.events().update(
                    calendarId=self.calendar_id, eventId=event_id, body=body).execute()
            log.info(f'[{live_event.id}]: Event updated {live_event.title}')
            log.info(f'[{live_event.id}]: Event updated url is {updated_event.get("htmlLink")}')
        except HttpError as error:
            log.info(f'An error occurred: {error}')
            updated_event = None
        return updated_event

    def get_events(self, past: int = PAST, future: int = FUTURE) -> list:
        # 指定されたカレンダーからeventを取得
        events = []
        now = arrow.utcnow()
        past = now.shift(days=-past).format(ISO861FORMAT) + 'Z'
        future = now.shift(days=future).format(ISO861FORMAT) + 'Z'
        try:
            # Call the Calendar API
            responses = self.calendar_service.events().list(calendarId=self.calendar_id,
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


class LineMessageSender:
    def __init__(self, config):
        self.linebot = LineBotApi(config.line.line_channel_access_token)

    def create_message_data(self, event, live_event):
        title = create_title(live_event)
        start_dateTime, end_dateTime = create_event_dateTime(live_event, LINEFORMAT)
        line_message = f'タイトル: {title}\n'\
                       f'チャンネル: {live_event.channel_title}\n'\
                       f'開始時刻: {start_dateTime}\n'\
                       f'終了時刻: {end_dateTime}\n'\
                       f'配信URL: https://www.youtube.com/watch?v={live_event.id}'
        return line_message

    def broadcast_message(self, line_message):
        try:
            self.linebot.broadcast(TextSendMessage(text=line_message))
        except LineBotApiError as e:
            log.error(f'LineBotApiError: {e}.')


class S3Operator:
    def __init__(self, config):
        self.s3 = boto3.client('s3',
                               aws_access_key_id=config.aws.access_key_id,
                               aws_secret_access_key=config.aws.secret_access_key)
        self.s3_bucket = config.aws.s3_bucket

    def _create_ics(self, live_event) -> str:
        title = create_title(live_event)
        start_dateTime, end_dateTime = create_event_dateTime(live_event, LINEFORMAT)
        cal = Calendar()
        cal.creator = 'Hololine'
        cal.add('prodid', '-//Okayun Calendar//product//ja//')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'REQUEST')

        # イベント作成
        event = Event()
        event.add('summary', f'{title}')
        event.add('dtstart', datetime.strptime(start_dateTime, '%Y/%m/%d %H:%M:%S'))
        event.add('dtend', datetime.strptime(end_dateTime, '%Y/%m/%d %H:%M:%S'))
        event.add('description', textwrap.dedent(f'''
        タイトル: {title}
        チャンネル: {live_event.channel_title}
        配信URL: https://www.youtube.com/watch?v={live_event.id}
        '''[1:-1]))
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

    def create_presigned_url(self, live_event) -> str:
        path = self._create_ics(live_event)
        bucket_key = self._ics_upload(path)
        presigned_url = self.s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': self.s3_bucket, 'Key': bucket_key},
            ExpiresIn=86400,
            HttpMethod='GET')
        return presigned_url


class Exporter(object):
    def __init__(self, config) -> None:
        self.holomenbers = config.holodule.holomenbers
        self.google_calendar = GoogleCalendar(config)
        self.events = self.google_calendar.get_events()
        self.line_message_sender = LineMessageSender(config)
        self.s3operator = S3Operator(config)

    def create_event(self, live_events: list) -> None:
        for live_event in live_events:
            log.info(f'[{live_event.id}]: ### Processing ### {live_event.title}.')
            log.info(f'[{live_event.id}]: scheduled_start_time is ' +
                     f'{live_event.scheduled_start_time.to(TZ)}')
            log.info(f'[{live_event.id}]: utcnow is {arrow.utcnow().to(TZ)}')
            log.info(f'[{live_event.id}]: difference is ' +
                     f'{(live_event.scheduled_start_time.to(TZ) - arrow.utcnow().to(TZ)).seconds}')
            # ここではlive_eventとcalendarのイベントに違いがあるかを探している、相違があった場合はupdate_eventに進む
            title = create_title(live_event)
            if (event := [event for event in self.events if live_event.id == event.video_id]):
                message_template = self.line_message_sender.create_message_data(event, live_event)
                event = event[0]
                if title != event.title:
                    self.google_calendar.update_event(event.id, live_event)
                    log.info(f'[{live_event.id}] [UPDATE]: Update the scheduled {live_event.title}.')
                    presigned_url = self.s3operator.create_presigned_url(live_event)
                    log.info(f'[{live_event.id}]: Create presigned_url: {presigned_url}.')
                    first_line = "【通知】タイトルが変更になりました\n"
                    last_line = f'\nカレンダーに登録: {presigned_url}'
                    nortification_message = first_line + message_template + last_line
                    self.line_message_sender.broadcast_message(nortification_message)
                    log.info(f'[{live_event.id}]: Push message to channel.')
                    continue
                if live_event.actual_start_time:
                    if live_event.actual_start_time.to(TZ) != event.start_dateTime:
                        self.google_calendar.update_event(event.id, live_event)
                        log.info(f'[{live_event.id}] [UPDATE]: Update the scheduled {live_event.title}.')
                        # すでにactual_end_timeがgoogle calendarの中にあった場合はLineで通知しない
                        if not event.actual_start_time:
                            first_line = "【通知】配信が開始されました\n"
                            nortification_message = first_line + message_template
                            self.line_message_sender.broadcast_message(nortification_message)
                            log.info(f'[{live_event.id}]: Push message to channel.')
                        continue
                elif live_event.scheduled_start_time.to(TZ) != event.start_dateTime:
                    self.google_calendar.update_event(event.id, live_event)
                    log.info(f'[{live_event.id}] [UPDATE]: Update the scheduled {live_event.title}.')
                    presigned_url = self.s3operator.create_presigned_url(live_event)
                    log.info(f'[{live_event.id}]: Create presigned_url: {presigned_url}.')
                    first_line = "【通知】時刻が変更されました\n"
                    last_line = f'\nカレンダーに登録: {presigned_url}'
                    nortification_message = first_line + message_template + last_line
                    self.line_message_sender.broadcast_message(nortification_message)
                    log.info(f'[{live_event.id}]: Push message to channel.')
                    continue
                elif live_event.scheduled_start_time.to(TZ) > arrow.utcnow().to(TZ):
                    if (live_event.scheduled_start_time.to(TZ) - arrow.utcnow().to(TZ))\
                            .seconds <= 900:
                        first_line = "【通知】配信がもうすぐ開始します！\n"
                        nortification_message = first_line + message_template
                        self.line_message_sender.broadcast_message(nortification_message)
                        log.info(f'[{live_event.id}]: Push message to channel.')
                if live_event.actual_end_time:
                    if live_event.actual_end_time.to(TZ) != event.end_dateTime:
                        self.google_calendar.update_event(event.id, live_event)
                        log.info(f'[{live_event.id}] [UPDATE]: Update the scheduled {live_event.title}.')
                        # すでにactual_end_timeがgoogle calendarの中にあった場合はLineで通知しない
                        if not event.actual_end_time:
                            first_line = "【通知】配信が終了しました\n"
                            nortification_message = first_line + message_template
                            self.line_message_sender.broadcast_message(nortification_message)
                            log.info(f'[{live_event.id}]: Push message to channel.')
                            continue
                log.info(f'[{live_event.id}] [ALREADY_EXIST]: {live_event.title} is already scheduled.')
                continue
            else:
                message_template = self.line_message_sender.create_message_data(event, live_event)
                if live_event.scheduled_start_time > arrow.utcnow().shift(days=FUTURE):
                    log.info(f'[{live_event.id}]: {title} was not scheduled, ' +
                             f'because it is {FUTURE} days away.')
                    continue
                event = self.google_calendar.create_event(live_event)
                log.info(f'[{live_event.id}] [CREATE]: Create {title} has been scheduled.')
                presigned_url = self.s3operator.create_presigned_url(live_event)
                log.info(f'[{live_event.id}]: Create presigned_url: {presigned_url}.')
                first_line = "【通知】新しい予定が追加されました\n"
                last_line = f'\nカレンダーに登録: {presigned_url}'
                nortification_message = first_line + message_template + last_line
                self.line_message_sender.broadcast_message(nortification_message)
                log.info(f'[{live_event.id}]: Push message to channel.')

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
