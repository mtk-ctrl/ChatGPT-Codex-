# ChatGPT リセット履歴

OpenAI公式と担当者本人の発表をもとに、Codex・ChatGPT Workの臨時リセット、リセットチケット、新機能とサイト独自の予想をまとめる日本語サイト。

- **公開サイト**：https://mtk-ctrl.github.io/ChatGPT-Codex-/
- **コード・データの正本**：このGitHubリポジトリの main
- **運用方針**：初めての読者に分かりやすく、根拠を確認し、無償で継続できる形を目指す
- **引継ぎ可能性**：ChatGPTの会話履歴や特定のAI・接続アプリなしでも、下記の資料から再開できる

## 運用状態（2026-11-03）

**自動収集は停止中。** 本人の指示により、GitHub Actionsのワークフロー「Collect reset records and publish」（`.github/workflows/update.yml`）を2026-11-03に無効化した（`disabled_manually`）。停止前は一次情報（OpenAI公式ページ・X）の取得が失敗し続けており、`data/health.json` の `last_success_at` が空だった。公開中のサイトは停止時点のデータのまま残る。

再開する場合は、本人の指示を受けてからワークフローを有効化する。取得失敗の原因を直さずに再開しない。

## 最初に読む資料

| 何を知りたいか | 現行資料 |
|---|---|
| **全体像と最新の状態** | [00｜プロジェクト入口](handbook/00_START_HERE.md) |
| **実施時に守るルール** | [AGENTS.md](AGENTS.md) |
| ソース・自動更新・公開の構造 | [10｜システム構成](handbook/10_ARCHITECTURE.md) |
| **ニュースを確認してサイトを更新する** | [20｜更新・公開・復旧](handbook/20_OPERATIONS.md) |
| これまでの発表、判断、訂正、予想 | [30｜経緯と判断履歴](handbook/30_HISTORY_AND_DECISIONS.md) |
| 訪問者計測、検索流入、認証 | [40｜計測とセキュリティ](handbook/40_ANALYTICS_AND_SECURITY.md) |
| **別のAI・人間に作業を引き継ぐ** | [50｜AI引継ぎ](handbook/50_AI_HANDOFF.md) |
| 以前の長いREADME等 | [アーカイブ](handbook/archive/README_before_reorganization_2026-11-03.md) |

## 開発・テスト

Python3とNode.jsを利用。標準テストとローカル生成：

~~~sh
python3 -m unittest discover -s tests -v
node --test tests/test_counter.mjs tests/test_stats.mjs
python3 scripts/site.py build
~~~

公開は [.github/workflows/update.yml](.github/workflows/update.yml) のGitHub Actionsで実施。サイトの配信元は docs/。編集は生成元の scripts/ と data/、ブラウザ表示の docs/assets/ を基本とする。

## 最新の記録はどこを見る？

- [原投稿に紐づく履歴](data/events.json)
- [28日間企画Day1～28](data/shipping-28.json)
- [公開済み独自予想の履歴](data/editorial-forecast-history.json)
- [一次情報取得の現在の状態](data/health.json)
- [確認・修正の監査記録](data/source-checks/)
- [GitHub Actionsの実行・公開状況](https://github.com/mtk-ctrl/ChatGPT-Codex-/actions)

2026年11月3日時点で28日間企画はDay28まで終了。以降の新着調査は引き続き必要。現在の件数・状態はGitHub mainのデータを毎回確認する。

## 文書管理の約束

- READMEは**案内・索引専用**。運用上の決定はAGENTS、手順はhandbook、事実はdata/へ保存し、日誌をREADMEに継ぎ足さない。
- 古いREADME、AGENTS、計測READMEは [handbook/archive](handbook/archive/) に原文保管。削除したのではなく、現行手順から分離した。
- 文書の変更をしても、公開サイト自体の更新成功とは限らない。テスト・ビルド・Pages Publishは別に確認する。
