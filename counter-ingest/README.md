# アクセス取り込み専用API

Vercel project: `prj_Quq1MsTLnZfceEpy1gwtOIQ5vruy` / `reset-visit-ingest`。

公開するのはPOST `/api/collect`のみ。GitHub Pagesの当サイトのOriginだけを許可し、UUID・パス・長さを検査してから所有者限定のSites保存先へ転送する。集計APIは公開しない。画面にカウンターを表示しない。

`COUNTER_STORE_TOKEN` はVercel production環境の暗号化変数で管理し、GitHub・ブラウザへ出さない。専用Sitesの既存サービスアクセスに使う。Sites保存先は `appgprj_6ae1a7864764819187492690d8a5c8f5`（所有者限定）。

変更後はVercelコネクタでこのディレクトリの全ファイルをproductionへデプロイする。ブラウザ配信側は通常のGitHub Pages公開手順。集計時はSites `get_site` が返す既存のサービス資格情報で `/api/stats?from=YYYY-MM-DD&to=YYYY-MM-DD` を読む。`test=1` は検証データのみ。期間は日本時間。

日別PV・訪問者（ブラウザ単位）・セッション（30分無操作で新規）を分ける。IP・氏名・メール・検索語・URLのクエリ文字列は保存しない。DNT/GPC、手動計測除外、既知のbotには通常イベントを送らない。計測をブロックする環境は数えられない。public APIのOrigin検査はブラウザ誤送信対策であり、偽造アクセスを完全に判別するものではない。
