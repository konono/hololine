# holoscope
hololive schdule export to calendar.

## 概要

hololineはholoviveの所属タレント(ホロメン)の予定をLineで通知してくれるアプリです。

動作環境は以下になります。
  - Python3.9 on Linux/Mac(Windowsは未確認)
    - git
    - pipenv
  - Python3.9 on AWS Lambda
    - git
    - pipenv
    - terraform

### アーキテクチャー

このアプリの構成要素は大まかに以下の3つです。
  - importer: youtubeの動画IDを取得してくる役割を持っています、デフォルトは[holodule](https://schedule.hololive.tv/simple)から取得してきます。
  - exporter: 受け取ったLiveEventオブジェクトを使って予定を作成します、デフォルトはgoogle calendarが指定されています。
  - core:　importer/exporterのプラグイン管理、動画IDを使って動画の詳細情報を取得し、LiveEventオブジェクトを生成する役割を持っています。

### configuration

以下はconfigurationサンプル
```
[general]
loglevel = "INFO"　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 # loglevel - 変更不要
logdir = "log"　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　 # logを出力するディレクトリ - 変更不要
logfile = "holoscope.log"            # logfile名 -  変更不要
importer_plugin = "holodule"　　　　　　　　　　　　　　　　 #　import_pluginの指定(現在はholoduleのみ) - 変更不要
exporter_plugin = "google_calendar"  #　exporter_pluginの指定(現在はgoogle_calendarのみ) - 変更不要

[google_calendar]
calendar_id = "YOUR CALENDAR ID"     # google calendar id(e.x xxx@group.calendar.google.com) - 要変更

[holodule]
holomenbers = ['猫又おかゆ', 'さくらみこ', '桃鈴ねね']       # 予定を取得したいホロメンを正式名称で記述　 - 要変更
holodule_url = 'https://schedule.hololive.tv/simple'  # holoduleのURLを記載　　- 変更不要

[youtube]
api_key = "YOUR YOUTUBE API KEY"　# YoutubeのAPI　KEY - 要変更

# AWS Lambdaで動作させる場合記述
[aws]
access_key_id = 'YOUR AWS ACCESS KEY'　　　　　　　　　　　　# YoutubeのACCESS　KEY - 要変更
secret_access_key = 'YOUR AWS SECRET KEY'　　　　# YoutubeのSECRET　KEY - 要変更
dynamodb_table = 'holoscope'　　　　　　　　　　　　　　　　　　　　　　　　　　　　　　#　　　dynamodbのtable名　　- 変更不要
dynamodb_hash_key_name = 'hashKey'         #　　　dynamodbのhash key　　- 変更不要
```

