# 00｜プロジェクト入口・現在地

更新基準：2026-11-03（日本時間）。**この資料はChatGPT以外のAIでも使える、サービス非依存の運用入口です。**

## 1. 何を運営するか

- 公開サイト：[ChatGPT リセット履歴](https://mtk-ctrl.github.io/ChatGPT-Codex-/)
- コードとデータの正本：[mtk-ctrl/ChatGPT-Codex- の main](https://github.com/mtk-ctrl/ChatGPT-Codex-)
- 目的：Codex・ChatGPT Workなどの臨時利用枠リセット、後から使えるリセットチケット、関連する公式発表、サイト独自の予想を、一般読者向けに日本語で表示する。誤情報を増やすことより、原資料に紐づく正確な履歴と見やすさを優先する。
- 動作：GitHub Pagesで静的サイトを配信し、GitHub Actionsでデータ確認・ビルド・公開を行う。別のVercelプロジェクトが非表示のアクセス計測を受信する。
- 原則：**運用の正本はGitHub**。Google Driveの共通ルーターとAddnessは横断管理・進捗の補助であり、このリポジトリを読めば運用を再開できるようにする。特定AIの会話履歴や記憶に依存しない。

## 2. 最初に読む順番

1. [README（リポジトリ入口）](../README.md) → この資料。
2. [AGENTS.md（実行上の約束）](../AGENTS.md)：別のAIでも必ず適用する。
3. [10_ARCHITECTURE.md](10_ARCHITECTURE.md)：コード、データ、配信、自動処理の接続関係。
4. [20_OPERATIONS.md](20_OPERATIONS.md)：新着確認、記事追加、テスト、公開、復旧の具体的手順。
5. [30_HISTORY_AND_DECISIONS.md](30_HISTORY_AND_DECISIONS.md)：これまでの出来事、予想・表示方針の変更理由。
6. [40_ANALYTICS_AND_SECURITY.md](40_ANALYTICS_AND_SECURITY.md)：非表示の訪問者計測、アクセス制御、Google検索データ。
7. [50_AI_HANDOFF.md](50_AI_HANDOFF.md)：別のAIや人間の作業者に渡す引継ぎ文、使用する権限・機能、チェックリスト。
8. 変更前の全記録は [archive](archive/) に保管。古い判断を探すときだけ読む。

## 3. 正本の優先順位

| 情報 | 唯一の現行正本 | 注意 |
|---|---|---|
| 公開内容を作るコード | scripts/site.py、scripts/primary.py、scripts/forecast.py | docs/*.html は生成物。直接編集だけで直さない |
| 原資料に裏付けられた掲載レコード | data/events.json | 投稿件数＝リセット回数ではない |
| 28日企画Day1〜28 | data/shipping-28.json | 太平洋時間の企画日。日本時間の配布時刻と別 |
| 個々の確認・取得状況 | data/source-checks/、data/health.json | 取得不能≠発表なし |
| サイト独自の予想・過去の判定 | data/editorial-forecast.json、data/editorial-forecast-history.json | 公開済み予想は後から改変しない |
| GitHub Pagesの公開成否 | GitHub ActionsのPublishステップ | commitだけでは公開成功を意味しない |
| サイト編集基準 | AGENTS.md とこのhandbook | READMEの過去ログは旧資料として扱う |
| 訪問者の計測値 | 認証付きの保存先から取得した集計 | Search Consoleのクリック数と混ぜない |

ユーザーの最新の明確な指示、確認済み原資料、保存済みの実データを優先する。食い違いがあれば勝手に上書きせず、出典・日時を照合してから変更する。

## 4. 現在地のスナップショット

以下は2026年11月3日現在の**確認時点の数字**。常にリポジトリの現物と最新Actionsで更新してから回答する。

- data/events.json：**74件**（公式・Tibo氏などの出典に紐づく投稿記録。実施回数ではない）。
- data/shipping-28.json：**Day1〜28の28日分**。企画自体は終了しているためDay29を増設しない。
- 独自予想の公開履歴：**6件**（履歴JSONに収録。過去の判定変更の経緯も保持）。
- 直近の配布：**2026/11/1 04時ごろ、11/2 07時**（日本時間）。両日ともチケット配布の運営者確認であり、配布時点で通常の臨時リセットなし。出典区分は owner observation。通常リセットの履歴に加算しない。
- data/health.json：2026/11/03 08:29 JST相当の最終更新時点で**公式ページとXの自動取得に失敗**。自動ジョブのsuccessはデータ取得成功を保証しない。公式投稿の調査は別途行う。
- GitHubの自動更新：2時間ごと、手動起動にも対応。最新実行と公開先を必ず照合する。
- 11月初めの予告とDay27/28は後日の観測で更新済み。古い見通し文書は予想の当時の状態を保存するもので、現時点の最新表示とは限らない。

## 5. 実行時の最重要ルール

- **一次情報だけを実施の出典**とする。OpenAI公式文書、Tibo氏など関係者本人のX。第三者のまとめやSNS転載を本人投稿と偽らない。
- **ユーザーが実際に確認したチケット配布**は「運営者確認」として別に記録できる。公式の実施発表に見せかけない。一般的なOpenAIガイドは当日の配布の証拠ではない。
- Tibo氏・OpenAIが利用枠リセットの実施を予告したら、完了報告を待たずリセット発表として扱う。単に「今後2日間に何か行う」という種類未割当の予告は、個々の日付の実施とは分ける。
- 日本時間の投稿日時／太平洋時間の企画日／実際の反映時刻を混同しない。入力ミスと推定した年月日は監査記録に残す。
- **見せる文章は簡潔に**。検証経緯・保険文言を何度も掲載しない。一般的な注意事項は「このサイトについて」に、詳しい根拠は内部データに残す。
- 勝手に外部アカウントへ投稿・メール送信しない。サイトの修正・公開は依頼があれば実施可能。秘密情報・アクセストークンはGitHubに書かない。
- **成功条件**：保存 → 自動テスト → HTML生成 → Pages Publish成功 → 生成物の読戻し（可能なら公開URLで実表示）。未実施部分は明示する。

## 6. 任意の補助資料

- [Addnessの運用Goal](https://www.addness.com/goals/c4d6a2c0-1a42-4094-92c4-61a426e8c796)：決定・検証・次の一手のメモ。これがなくてもGitHubから運用を再開できる構成とする。
- [Google DriveのAI共通ルーター](https://drive.google.com/file/d/1Kft2Uyld-m4b48Dp4e3P4BzYfBH96waY/view)：ChatGPT・Claudeで共通の横断入口。**Driveに接続できないAIでも、このリポジトリのAGENTS.mdとREADMEだけで作業できるようにする**。
- [旧README](archive/README_before_reorganization_2026-11-03.md)、[旧AGENTS](archive/AGENTS_before_reorganization_2026-11-03.md)：日付別の原文を保存。Gitのコミット履歴も残す。
