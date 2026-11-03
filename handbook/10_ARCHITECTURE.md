# 10｜システムとデータの全体像

更新日：2026-11-03。外部AIが理解できる運用設計の説明。

## 全体の流れ

1. scripts/primary.py がOpenAI公式情報と関係者本人のX投稿を確認。既存の検証済み履歴は data/events.json で保存。
2. 28日間企画の情報は data/shipping-28.json、出典・取得状況は data/source-checks/ に記録。
3. scripts/site.py が履歴、独自予想、健康状態を読み、docs/ のHTML、RSS、CSV、サイトマップを生成。docs/ のHTMLを直接直すのではなく生成器を直す。
4. GitHub Actions がテスト、取得、HTML生成、GitHub PagesへのPublishを行う。
5. 公開サイト https://mtk-ctrl.github.io/ChatGPT-Codex-/ の閲覧情報は、別プロジェクトのVercel経由で管理者用保存先に集計。アクセス数はサイト上には表示しない。

## 正本とその責務

| ファイル | 役割 |
|---|---|
| AGENTS.md | 現行の編集・検証ルール |
| README.md、handbook/ | 運用入口と専門マニュアル。古い日誌はhandbook/archive/ |
| .github/workflows/update.yml | 自動化と公開の正本 |
| data/events.json | 原資料に紐づく発表履歴。投稿数と実施回数は別 |
| data/shipping-28.json | 2026年の28日企画Day1～28。太平洋時間の日付 |
| data/shipping-notices.json | 企画に関連した追加の公式発信 |
| data/source-checks/ | 出典、確認方法、調査制限、修正理由 |
| data/health.json | 一次情報の自動取得状態 |
| data/official-confirmations.json | OpenAI公式の記事からの日付確認 |
| data/editorial-forecast.json | 最新のサイト独自予想と当時の見通し |
| data/editorial-forecast-history.json | 予想の初回公開時刻、判定と訂正履歴 |
| data/forecast-history.json | 統計による予想の履歴 |
| scripts/primary.py | 信頼する一次資料の判定と自動取得 |
| scripts/forecast.py | 90日間のリセット発表間隔から24・48時間を試算 |
| scripts/site.py | 読み取り、生成、表示データの整合 |
| docs/assets/app.js、style.css、counter.js | ブラウザ操作、表示、非表示アクセス計測 |
| counter-ingest/ | Vercelで独立して運用する収集・認証付き集計API |
| tests/ | PythonとNodeの回帰テスト |

## GitHub Actionsの実際の条件

- 2時間ごと（cron: 17 */2 * * *、UTC）、手動起動、mainへの一部ファイルのpushで実行。
- push対象は README.md、AGENTS.md、handbook/**、scripts/**、tests/**、counter-ingest/**、data/**、docs/assets/** とworkflow本体。**文書変更でも自動実行される**。実際のActions結果を確認する。
- Python unittest と Nodeの計測用テストを実行した後、一次情報取得、HTML生成、生成物コミット、Pagesアップロード、Publishを行う。
- 一次情報への接続失敗は処理を継続し、既存履歴を保持する。したがって **Actions success と情報取得成功は別**。必ず data/health.json の feed、x_status、last_success_at を確認する。
- 公開リポジトリとして無料運用する設計。privateになった場合は更新ジョブを抑制する安全策がある。
- Pages Publish成功を確認して公開と報告。コミットだけで「更新済み」とは言わない。生成物の保存時にmainが前進した場合はfetch/rebaseで最大3回再試行し、強制pushはしない。

## 時刻と真偽の意味

- events.json の reference_at は投稿時刻、official_dateは日付だけの公式告知。実際の枠回復時刻ではない。
- shipping-28.json の date_pt は米国太平洋時間の企画日。observed_at_jst_approx は運営者が見た日本時間の目安。
- イベント一次資料はOpenAI/Tibo氏の本人投稿に限定。運営者のチケット観測は別種別として扱う。**data/events.json に根拠なく入れるとscripts/primary.pyの trusted() が除外する場合がある。**
- リセットの実施予告が明示されれば完了報告を待たず履歴に含める。種類未割当の「今後2日間に関連企画」の予告は実施履歴とは分ける。
- ユーザー独自の予想日とその公開時刻は data/editorial-forecast-history.json で固定。チケットだけで予想的中にしない。

## 更新対象の境界

- 28日企画はDay28で終了している。Day29は生成器のバリデーションで許されない。以後の運営者観測を載せるには新しいデータ系統と表示処理を実装する。
- 公開URLのパスは保持する。変更する場合はリンク、サイトマップ、canonical、Googleの登録状態を確認する。
- Xは自動取得制限がある。最新の health は2026年11月3日朝の更新時点で取得失敗。発表の調査は必要に応じて本人の原投稿を手動で照合する。
- アクセス計測の認証情報はコードにない。Vercelと保存先への正規の所有者権限が別途必要。詳細は [40_ANALYTICS_AND_SECURITY.md](40_ANALYTICS_AND_SECURITY.md) を参照。
