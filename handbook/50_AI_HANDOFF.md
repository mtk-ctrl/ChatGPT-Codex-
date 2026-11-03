# 50｜他のAI・担当者への引継ぎ

更新日：2026-11-03。ChatGPTのメモリ・Addness・専用プラグインがなくても、GitHubから作業を再開するための資料。

## 引継ぎの入口

**正本**：https://github.com/mtk-ctrl/ChatGPT-Codex-

次の順番で読む。

1. README.md、AGENTS.md、handbook/00_START_HERE.md（目的と優先ルール）。
2. handbook/10_ARCHITECTURE.md（コードとデータの対応）。
3. handbook/20_OPERATIONS.md（調査・編集・テスト・公開の具体的な手順）。
4. handbook/30_HISTORY_AND_DECISIONS.md（予想とリセットの歴史的判断）。
5. handbook/40_ANALYTICS_AND_SECURITY.md（訪問数・Google検索・Vercel認証）。

現物の記録は data/ とGit履歴。旧READMEの長い日誌は handbook/archive/ に保持。**最新の事実はその時点で読み直す。**

## 新しいAIに渡す文章

~~~text
GitHubリポジトリ https://github.com/mtk-ctrl/ChatGPT-Codex- の運用を引き継いでください。

最初にREADME.md、AGENTS.md、handbook/00_START_HERE.md、20_OPERATIONS.mdを読み、必要に応じて他のhandbook資料を確認してください。

目的は、OpenAIとTibo氏などの本人発表を一次資料として、Codex・Workの臨時リセット、リセットチケット、新機能を正確で読みやすい日本語で公開することです。運営者の実機確認とOpenAI公式の発表は出典を区別してください。

変更後はPython/Nodeテスト、HTML生成、GitHub ActionsのPublish成功と生成HTMLの読戻しまで確認してください。出典取得が失敗したら新着ゼロと報告しないでください。日本時間と28日企画の太平洋時間を分け、公開済み予想の時刻・結果を書き換えないでください。

読者には日付と出来事を簡潔に示し、内部の検証経緯を毎回繰り返しません。出典の詳しい経緯はdata/source-checksに保存します。GitHubを正本とし、AddnessとGoogle Driveへのアクセスは必須にしません。認証情報を公開したり、有料サービスへ勝手に変更したりしないでください。

作業前にmainの最新内容・最新Actions・data/health.jsonを確認し、指示された作業を実行してください。
~~~

## 手動で始める方法

~~~sh
git clone https://github.com/mtk-ctrl/ChatGPT-Codex-.git
cd ChatGPT-Codex-
git status --short
git log -5 --oneline
python3 -m unittest discover -s tests -v
node --test tests/test_counter.mjs tests/test_stats.mjs
python3 scripts/site.py build
~~~

作業後はGitHubに保存し、GitHub Actionsで確認する。コード・データのpushは自動起動対象だが、handbookやREADMEの編集だけではジョブが起動しない。

~~~sh
gh workflow run update.yml --repo mtk-ctrl/ChatGPT-Codex- --ref main
gh run list --repo mtk-ctrl/ChatGPT-Codex- --limit 5
~~~

上のコマンドは権限を持つGitHub CLIが使える環境向け。AIにGitHubの書き込み権限がなければ、手順を記録して「保存済み」とは報告しない。

## 必要な作業機能の代替方法

| 仕事 | 利用可能な手段 |
|---|---|
| GitHub閲覧・編集 | git CLI、GitHub API、公式Web、任意のAIのGitHub接続 |
| 本人投稿の確認 | Webブラウザ・検索からOpenAI公式や本人Xへアクセス |
| テスト | Python3、Node.js、GitHub Actions |
| 公開 | GitHub ActionsのPages Publish |
| 訪問者・PV | Vercelの管理者認証付きプレビュー集計（別権限が必要） |
| Google検索の流入 | Search Consoleの管理画面またはAPI（別権限が必要） |
| 過去の判断 | handbook/30_HISTORY_AND_DECISIONS.md、監査JSON、Git履歴 |

Addnessの [関連Goal](https://www.addness.com/goals/c4d6a2c0-1a42-4094-92c4-61a426e8c796) は補助。権限のないAIにもGitHubの資料だけで再開できるようにする。

## 引継ぎ完了チェック

- [ ] mainのREADMEとAGENTS、handbookを読んだ。
- [ ] JSONの件数・確認日時を最新mainで確かめた。
- [ ] Day27/Day28のチケット配布と、臨時リセットを混同していない。
- [ ] 10/25の予想重複整理、10/31の訂正理由を理解した。
- [ ] Python・Nodeのテスト、HTML生成を行った。
- [ ] Pages Publishと生成物を照合した。
- [ ] 公開URLの直接表示まで確認したかどうかを区別した。
- [ ] 秘密情報をコードに追加していない。
- [ ] 変更理由と残課題をGitHubに記録した。

## 既知の未解決課題

1. XとOpenAI公式ページへの自動直接アクセスが失敗しやすい。新着の有無を断定する前に人手または他の合法的な方法で原資料を確認。
2. 28日企画はDay28で終了。以後の新しい運営者観測については新しいデータ構造と表示処理が必要。Day29を仮設しない。
3. CIのテストはスマートフォンでの実表示を全面保証しない。可能ならブラウザE2E確認を追加。
4. 既存アクセス計測の秘密情報はVercelにあり、GitHubだけでは取得できない。移行時には所有者が正規の権限を付与する。
5. 旧READMEの情報には後から訂正された記録もある。現行AGENTS・JSON・このhandbookを優先する。
