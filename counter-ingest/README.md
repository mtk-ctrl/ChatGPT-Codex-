# アクセス取り込み専用API

Vercel project: `prj_Quq1MsTLnZfceEpy1gwtOIQ5vruy` / `reset-visit-ingest`。

公開するのはPOST `/api/collect`のみ。GitHub Pagesの当サイトのOriginだけを許可し、UUID・パス・長さを検査してから所有者限定のSites保存先へ転送する。集計APIは公開しない。画面にカウンターを表示しない。

`COUNTER_STORE_TOKEN` はVercel production環境の暗号化変数で管理し、GitHub・ブラウザへ出さない。専用Sitesの既存サービスアクセスに使う。Sites保存先は `appgprj_6ae1a7864764819187492690d8a5c8f5`（所有者限定）。

変更後はVercelコネクタでこのディレクトリの全ファイルをproductionへデプロイする。ブラウザ配信側は通常のGitHub Pages公開手順。集計時はSites `get_site` が返す既存のサービス資格情報で `/api/stats?from=YYYY-MM-DD&to=YYYY-MM-DD` を読む。`test=1` は検証データのみ。期間は日本時間。

日別PV・訪問者（ブラウザ単位）・セッション（30分無操作で新規）を分ける。IP・氏名・メール・検索語・URLのクエリ文字列は保存しない。DNT/GPC、手動計測除外、既知のbotには通常イベントを送らない。計測をブロックする環境は数えられない。public APIのOrigin検査はブラウザ誤送信対策であり、偽造アクセスを完全に判別するものではない。

## 管理者用の集計取得（2026-10-29修正）

- 集計をSitesの専用ツールだけに依存させないため、`api/stats.mjs`を**Vercel Authenticationが有効なpreview環境限定**で使用する。productionの公開受信API `/api/collect` は変更しない。
- Vercel project `reset-visit-ingest` の `ssoProtection` は `preview`、`COUNTER_STORE_TOKEN` は暗号化envで `production`と`preview`に設定。原文の秘密値は閲覧・転記しない。
- 管理者が認証されたpreviewの `GET /api/stats?from=YYYY-MM-DD&to=YYYY-MM-DD` を使う。`test=1` は検証分のみ。日付はJSTで最大93日分。返すのはPV・ブラウザ単位の訪問者・30分区切りのセッション・日別/ページ別/流入元別集計のみ。
- このAPIのコードには `VERCEL_ENV==='preview'` の追加ガードがあり、誤ってproductionへ同コードが展開されても404になる。previewの認証状態はVercel設定と外部からのアクセス拒否を検証する。通常のユーザーにはこのURLや共有リンクを掲載しない。
- 接続済みのVercelプラグインでpreviewデプロイを探し、`web_fetch_vercel_url`を用いてプラットフォーム認証下で取得する。結果を返す際は実取得した対象期間・実データと、未取得の範囲を区別する。取得不能を0件と呼ばない。
- `tests/test_stats.mjs`と既存 `tests/test_counter.mjs`をCIで実行し、集計表示の前に認証とデータ応答を検証する。プレビューのURLはAddnessの関連Goalに保管。
