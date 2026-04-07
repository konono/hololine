#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
holodule importer の _get_programs() のユニットテスト。
実際のHTMLをフィクスチャとして使用し、外部通信なしでテストする。
"""

import importlib
from unittest.mock import MagicMock, patch

import pytest

IMPORTER_PLUGIN_DIR = "holoscope.importer_plugin"

# 実データから取得したHTMLフィクスチャ
# ソロ配信（コラボなし）
SOLO_ENTRY_HTML = '''
<div class="col-6 col-sm-4 col-md-3" style="padding-left:5px;padding-right: 5px;">
 <a class="thumbnail" href="https://www.youtube.com/watch?v=k3rGI1jg9J4" target="_blank">
  <div class="container" style="padding:1px;">
   <div class="row" style="width:100%;margin:0;">
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters">
      <div class="col text-right name" style="line-height:30px;margin-right:5px;">
       Shiori
      </div>
     </div>
    </div>
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters justify-content-between" style="height: 60px;overflow: hidden;">
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;">
       <img src="https://yt3.ggpht.com/shiori_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
     </div>
    </div>
   </div>
  </div>
 </a>
</div>
'''

# コラボ配信（2人）
COLLAB_2_ENTRY_HTML = '''
<div class="col-6 col-sm-4 col-md-3" style="padding-left:5px;padding-right: 5px;">
 <a class="thumbnail" href="https://www.youtube.com/watch?v=_Z_xaf4CRvk" target="_blank">
  <div class="container" style="padding:1px;">
   <div class="row" style="width:100%;margin:0;">
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters">
      <div class="col text-right name" style="line-height:30px;margin-right:5px;">
       Elizabeth Sub
      </div>
     </div>
    </div>
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters justify-content-between" style="height: 60px;overflow: hidden;">
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;">
       <img src="https://yt3.ggpht.com/elizabeth_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;padding:-20px;">
       <img src="https://yt3.ggpht.com/collab_member_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
     </div>
    </div>
   </div>
  </div>
 </a>
</div>
'''

# コラボ配信（4人）
COLLAB_4_ENTRY_HTML = '''
<div class="col-6 col-sm-4 col-md-3" style="padding-left:5px;padding-right: 5px;">
 <a class="thumbnail" href="https://www.youtube.com/watch?v=lpg8GCKfB4o" target="_blank">
  <div class="container" style="padding:1px;">
   <div class="row" style="width:100%;margin:0;">
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters">
      <div class="col text-right name" style="line-height:30px;margin-right:5px;">
       Octavio
      </div>
     </div>
    </div>
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters justify-content-between" style="height: 60px;overflow: hidden;">
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;">
       <img src="https://yt3.ggpht.com/octavio_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;padding:-20px;">
       <img src="https://yt3.ggpht.com/collab1_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;padding:-20px;">
       <img src="https://yt3.ggpht.com/collab2_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;padding:-20px;">
       <img src="https://yt3.ggpht.com/collab3_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
     </div>
    </div>
   </div>
  </div>
 </a>
</div>
'''

# アクター名エイリアスのテスト用
ALIAS_AKIROZE_HTML = '''
<div class="col-6 col-sm-4 col-md-3" style="padding-left:5px;padding-right: 5px;">
 <a class="thumbnail" href="https://www.youtube.com/watch?v=DUmiZdZAr0o" target="_blank">
  <div class="container" style="padding:1px;">
   <div class="row" style="width:100%;margin:0;">
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters">
      <div class="col text-right name" style="line-height:30px;margin-right:5px;">
       アキロゼ
      </div>
     </div>
    </div>
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters justify-content-between" style="height: 60px;overflow: hidden;">
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;">
       <img src="https://yt3.ggpht.com/akiroze_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
     </div>
    </div>
   </div>
  </div>
 </a>
</div>
'''

ALIAS_LAPLUS_HTML = '''
<div class="col-6 col-sm-4 col-md-3" style="padding-left:5px;padding-right: 5px;">
 <a class="thumbnail" href="https://www.youtube.com/watch?v=abc123" target="_blank">
  <div class="container" style="padding:1px;">
   <div class="row" style="width:100%;margin:0;">
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters">
      <div class="col text-right name" style="line-height:30px;margin-right:5px;">
       ラプラス
      </div>
     </div>
    </div>
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters justify-content-between" style="height: 60px;overflow: hidden;">
      <div class="col col-sm col-md col-lg col-xl" style="width:60px;text-align: center;">
       <img src="https://yt3.ggpht.com/laplus_avatar=s88" style="border-radius: 50%;width: 60px;"/>
      </div>
     </div>
    </div>
   </div>
  </div>
 </a>
</div>
'''

# YouTube以外のリンク（スキップされるべき）
NON_YOUTUBE_ENTRY_HTML = '''
<div class="col-6 col-sm-4 col-md-3" style="padding-left:5px;padding-right: 5px;">
 <a class="thumbnail" href="https://www.twitch.tv/somechannel" target="_blank">
  <div class="container" style="padding:1px;">
   <div class="row" style="width:100%;margin:0;">
    <div class="col-12 col-sm-12 col-md-12" style="padding:0;">
     <div class="row no-gutters">
      <div class="col text-right name" style="line-height:30px;margin-right:5px;">
       SomeMember
      </div>
     </div>
    </div>
   </div>
  </div>
 </a>
</div>
'''


def _build_holodule_page(*entry_htmls):
    """テスト用のholoduleページHTMLを組み立てる"""
    entries = '\n'.join(entry_htmls)
    return f'''
    <html><body>
    <div class="container">
     <div class="row">
      {entries}
     </div>
    </div>
    </body></html>
    '''


def _create_importer(html_content):
    """モック化したrequestsでImporterを生成し、_get_programs()を呼び出す"""
    from holoscope.datamodel import HoloduleConfiguration

    class MinimalConfig:
        def __init__(self):
            self.holodule = HoloduleConfiguration(
                holomenbers=[],
                holodule_url='https://schedule.hololive.tv/',
            )

    importer_module = importlib.import_module(
        f'{IMPORTER_PLUGIN_DIR}.holodule', package='Importer')
    importer = object.__new__(importer_module.Importer)
    importer.cnf = MinimalConfig()

    mock_response = MagicMock()
    mock_response.text = html_content

    with patch('holoscope.importer_plugin.holodule.requests.get',
               return_value=mock_response):
        return importer._get_programs()


class TestGetPrograms:
    """_get_programs() のテスト"""

    def test_solo_entry(self):
        """ソロ配信のパースが正しく行われること"""
        html = _build_holodule_page(SOLO_ENTRY_HTML)
        programs = _create_importer(html)

        assert len(programs) == 1
        program = programs[0]
        assert program['actor'] == 'Shiori'
        assert program['video_id'] == 'k3rGI1jg9J4'
        assert program['img'] == 'https://yt3.ggpht.com/shiori_avatar=s88'
        assert program['collaborators'] == []
        assert program['collaborate'] == []

    def test_collab_2_members(self):
        """2人コラボ配信のパースが正しく行われること"""
        html = _build_holodule_page(COLLAB_2_ENTRY_HTML)
        programs = _create_importer(html)

        assert len(programs) == 1
        program = programs[0]
        assert program['actor'] == 'ElizabethSub'
        assert program['video_id'] == '_Z_xaf4CRvk'
        assert program['img'] == 'https://yt3.ggpht.com/elizabeth_avatar=s88'
        assert len(program['collaborators']) == 1
        assert program['collaborators'][0] == 'https://yt3.ggpht.com/collab_member_avatar=s88'
        assert program['collaborate'] == []

    def test_collab_4_members(self):
        """4人コラボ配信のパースが正しく行われること"""
        html = _build_holodule_page(COLLAB_4_ENTRY_HTML)
        programs = _create_importer(html)

        assert len(programs) == 1
        program = programs[0]
        assert program['actor'] == 'Octavio'
        assert program['video_id'] == 'lpg8GCKfB4o'
        assert program['img'] == 'https://yt3.ggpht.com/octavio_avatar=s88'
        assert len(program['collaborators']) == 3
        assert program['collaborate'] == []

    def test_non_youtube_link_skipped(self):
        """YouTube以外のリンクはスキップされること"""
        html = _build_holodule_page(NON_YOUTUBE_ENTRY_HTML)
        programs = _create_importer(html)

        assert len(programs) == 0

    def test_actor_alias_akiroze(self):
        """アキロゼ → アキ・ローゼンタール に変換されること"""
        html = _build_holodule_page(ALIAS_AKIROZE_HTML)
        programs = _create_importer(html)

        assert len(programs) == 1
        assert programs[0]['actor'] == 'アキ・ローゼンタール'

    def test_actor_alias_laplus(self):
        """ラプラス → ラプラス・ダークネス に変換されること"""
        html = _build_holodule_page(ALIAS_LAPLUS_HTML)
        programs = _create_importer(html)

        assert len(programs) == 1
        assert programs[0]['actor'] == 'ラプラス・ダークネス'

    def test_multiple_entries(self):
        """複数エントリが正しくパースされること"""
        html = _build_holodule_page(
            SOLO_ENTRY_HTML, COLLAB_2_ENTRY_HTML, COLLAB_4_ENTRY_HTML)
        programs = _create_importer(html)

        assert len(programs) == 3
        actors = [p['actor'] for p in programs]
        assert 'Shiori' in actors
        assert 'ElizabethSub' in actors
        assert 'Octavio' in actors

    def test_mixed_youtube_and_non_youtube(self):
        """YouTubeと非YouTubeが混在している場合、YouTubeのみ取得されること"""
        html = _build_holodule_page(
            SOLO_ENTRY_HTML, NON_YOUTUBE_ENTRY_HTML, COLLAB_2_ENTRY_HTML)
        programs = _create_importer(html)

        assert len(programs) == 2

    def test_empty_page(self):
        """配信予定がない場合は空リストが返ること"""
        html = _build_holodule_page()
        programs = _create_importer(html)

        assert programs == []

    def test_program_has_required_keys(self):
        """各programが必要なキーを全て持っていること"""
        html = _build_holodule_page(SOLO_ENTRY_HTML)
        programs = _create_importer(html)

        required_keys = {'actor', 'collaborators', 'video_id', 'img', 'collaborate'}
        assert required_keys == set(programs[0].keys())
