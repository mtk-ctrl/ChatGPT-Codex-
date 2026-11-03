# 20｜更新・公開・復旧マニュアル

更新日：2026-11-03。特定AIのプラグインを前提としない。GitHubとPython/Nodeがあれば作業の大半を再開できる。

## 1. 作業開始前

1. GitHub mainを取得し、README.md → AGENTS.md → handbook/00_START_HERE.md → 本書を読む。
2. 直近のGitHub ActionsとPublish結果、data/health.json、data/events.json、data/shipping-28.json、data/editorial-forecast-history.json を確認。
3. 依頼された日時を日本時間で確定する。企画Dayは太平洋時間なので混同しない。ユーザーの入力を補正した場合は、何をどう補正したか記録する。
4. 新情報を「公式が明言した臨時リセット」「公式チケット」「運営者自身のチケット確認」「新機能」「独自予想」「発表の調査だけ」のいずれかに分類。
5. 対象のレコードがすでに存在しないか、ID・日時・原投稿URLで重複を確認する。

## 2. 情報の取得・証拠

- OpenAI公式サイト、Tibo氏（Xの @thsottiaux）、その他OpenAI公式アカウントから直接確認する。Web検索は原投稿へたどり着くための手段であり、第三者のまとめを一次資料と同一視しない。
- Xがアクセス拒否した場合は、実際に確認できた本文の範囲と失敗を data/source-checks/YYYY-MM-DD.json に残す。過去の確認済み投稿は勝手に削除しない。
- 原投稿URLが不明なのに想像で作らない。一般的なOpenAIヘルプページは機能の使い方の説明であり、特定日の配布・リセットの裏付けとは限らない。
- Tibo氏が「today is a reset」等と実施を予告したものは、その時点でリセット発表として扱う。後続の「完了」を待たせない。
- 投稿1件とリセット1回は別。完了・補足の複数投稿を個別記録にしても、「実施が複数回」とは数えない。

## 3. 新しいレコードの登録

**公式の臨時リセット**

- data/events.json の既存の同種レコードに従い、id、kind=global、state、reference_at、time_basis、evidence、original_url、note等を登録。
- scripts/primary.py の trusted() が許可する一次資料のみ。新しいサイト・アカウント・投稿形式を追加する場合は trustの条件・テストを設計し直す。自動refreshで消されないことを確認。
- 投稿日時と利用枠の反映日時を別に考える。日付だけの公式告知には時刻を作らない。
- data/source-checks/ に照合方法と日時の意味を書く。

**28日間企画（終了済み）**

- data/shipping-28.json がDay1〜28の原本。既存Dayを訂正するときだけ変更。
- Day27（太平洋時間10/31）は日本時間11/1 04時ごろ、Day28（太平洋時間11/1）は日本時間11/2 07時のリセットチケット配布で登録済み。いずれも運営者の観測として保存。
- 原稿は「いつ・何があったか」を短く。出典の限界、タイムスタンプの取得方法等の技術経緯は data/source-checks/ に記録。HTMLに毎回「未照合」「未確定」等を繰り返さない。
- **Day29は追加不可**。企画後の新しい運営者観測を記録・表示するときは、新たなデータ構造と生成器・テストを一緒に追加する。既存Dayを無理に流用しない。

**運営者が報告したチケット配布**

- 公式告知と異なる観測情報として扱う。運営者が配布時刻を確認した場合は日本時間・大まかさ・臨時リセットの有無・観測出典を区別して記録。
- 公式のリセット件数や、リセット予想の当たりには加算しない。2026/11/1、11/2は上記のDay27/28と data/source-checks/2026-11-01.json、2026-11-02.json が前例。
- 未来の報告日時・自動で付与された対象範囲等を推測で追加しない。

**独自予想**

- ユーザーが指定・承認した日付だけを正式な編集上の予想とする。AIの推測を勝手に正式公開しない。
- data/editorial-forecast.json の日付と理由、作成時刻を保存し、初回公開後にPages Publishの根拠を添えて published_at と publication_run_id を確定。
- data/editorial-forecast-history.json に当初予想の日時と理由を保存。外れも残し、後の結果から予想日時をさかのぼって変えない。
- 例外：10/25の公開予想重複はユーザーの個別指示で修正済み。自動復元しない。詳細は [30_HISTORY_AND_DECISIONS.md](30_HISTORY_AND_DECISIONS.md)。

## 4. テストとローカル生成

GitHubのリポジトリをcloneし、Python3とNode.jsを使用する。追加の有料サービスは前提としない。

~~~sh
git clone https://github.com/mtk-ctrl/ChatGPT-Codex-.git
cd ChatGPT-Codex-
python3 -m unittest discover -s tests -v
node --test tests/test_counter.mjs tests/test_stats.mjs
python3 scripts/site.py build
~~~

- docs/index.html、docs/ship28.html、docs/assets/app.jsで、カレンダーの初期表示・月切替・日付タップ・出典リンク・予想◯✕が一致するか確認。
- docs/内のHTMLは生成物。変更すべき本文は scripts/site.py または元のJSON、表示ロジックは docs/assets/app.js を編集。
- ビルドが失敗したら直近で編集したJSONのDay数、日付の連続性、出典許可、テスト期待値を確認。
- refreshはネット接続の制限で失敗し得る。取得不能を0件と報告しない。
- Python/Nodeの成功は見た目の保証ではない。スマートフォンの文字の重なり、クリック後の表示も可能な手段で確認する。

## 5. GitHub Pages公開

1. 認証されたGitHubアカウントで許可された変更をmainへ保存。
2. コード・データに加え、**README・AGENTS・handbookの変更もActionsの自動起動対象**（2026/11/3以降）。実際の起動を確認。起動しなければ手動実行する。
3. リポジトリのActions → 「Collect reset records and publish」→ Run workflow（main）。CLIが使えれば以下も可。

~~~sh
gh workflow run update.yml --repo mtk-ctrl/ChatGPT-Codex- --ref main
gh run list --repo mtk-ctrl/ChatGPT-Codex- --limit 5
~~~

4. 当該runの Run data and publishing checks、Build readable HTML、Upload the static website、Publish が成功したことを確認。
5. GitHub mainの生成docs/index.html、docs/ship28.htmlの該当文面を再取得。できる環境なら公開サイトをブラウザ・スマホでも確認。
6. 完了報告には **コミット・run・公開URL**、実際に検証できた範囲だけを示す。Web表示を確認できなければ確認できたと偽らない。
7. データ取得失敗でもPages更新は成功し得る。data/health.jsonも必ず照合。

## 6. 不具合を発見したとき

| 症状 | 先に見る場所 | 対応 |
|---|---|---|
| 新しいリセットが載らない | data/health.json、X本人投稿 | 取得制限か本当の未更新かを分離。一次情報を確かめ手動記録 |
| GitHub Actions failure | 該当runの失敗ステップのログ | コード、JSON、テスト期待値を直し再テスト |
| 保存時のgit pushが拒否される | 同時編集でmainが前進したか | fetch・rebaseで最大3回再試行。rebase競合時は強制pushせず差分を確認し解決 |
| GitHubには変更済みだが公開が古い | Pages Publish結果、docsの生成HTML | ビルド・Publishを再検証。ブラウザキャッシュとソース未更新を区別 |
| カレンダーと日付タップの内容が違う | scripts/site.py、docs/assets/app.js | 静的HTMLとJSの両方を同一データで更新 |
| 予想履歴が変わった | editorial-forecast-history.json、Actionsの自動コミット | Git差分・初回Publish証跡・ユーザー判断と照合。恣意的に消さない |
| 訪問者数を取得できない | Vercel preview、認証、stats API、保存先 | 認証と期間を確認。Search Consoleクリックを訪問者数と呼ばない |

## 7. 変更の後に残すもの

- コード・データはGitHubへ、訂正理由は data/source-checks/ または [履歴・判断](30_HISTORY_AND_DECISIONS.md) へ。
- 再発する設計上の失敗と恒久策はAGENTSまたは本書へ。**日付別の日誌をREADMEに延々と追記しない**。
- Addnessは使える場合のみGoalに差分を記録。利用できなくてもGitHubの説明だけで再開できるよう更新する。
