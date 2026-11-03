# アクセス計測API（Vercel）

このフォルダはGitHub Pagesとは**別デプロイ**。本体サイトは [README](../README.md)、計測の詳しい運用・権限・移管方法は [handbook/40_ANALYTICS_AND_SECURITY.md](../handbook/40_ANALYTICS_AND_SECURITY.md) を参照。

## 構成

- Vercelプロジェクト：reset-visit-ingest（ID：prj_Quq1MsTLnZfceEpy1gwtOIQ5vruy）
- 公開受信：POST /api/collect（api/collect.mjs）
- **管理者集計：GET /api/stats（api/stats.mjs）**。Vercel Authentication付きpreview環境のみ有効。productionでのstatsは404。
- 受信データの保存先：所有者限定の既存Sitesストレージ。GitHubにはDB・トークンを保管しない。
- 認証用の COUNTER_STORE_TOKEN：Vercel暗号化環境変数。production・previewに設定。秘密値をREADMEやチャットにコピーしない。
- ブラウザ送信元：GitHub Pagesの docs/assets/counter.js。氏名・メール・IP・検索語は送らない。
- 集計のテスト：tests/test_counter.mjs、tests/test_stats.mjs（リポジトリrootから実行）。

## 実施時の確認

1. 公開収集APIのデプロイと、既存サイトからのブラウザ送信の成否を確認。
2. 管理者集計はVercelで認証されたpreviewデプロイの /api/stats?from=YYYY-MM-DD&to=YYYY-MM-DD を使う（日本時間の日付）。一般にプレビューURLや管理者用リンクを配布しない。
3. pageviews（PV）、visitors（ブラウザ単位）、sessions（30分区切り）を分けて集計。test=1 は検証用だけ。Vercel/APIから値を取得できないときは「未取得」であり0と記載しない。
4. 変更後はNodeテスト、Vercelのデプロイ状態、productionのstats拒否、認証済みpreviewのstats成功を確認。
5. 既存のAPIを一般公開の統計閲覧APIに変更しない。外部AIへの引継ぎにはVercel側の正式な権限付与が必要。

変更前の全文：[旧counter-ingest README](../handbook/archive/counter-ingest_README_before_reorganization_2026-11-03.md)。
