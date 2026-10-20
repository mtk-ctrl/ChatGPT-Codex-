# ChatGPT・Codex リセットログ

ChatGPT Work・Codexの臨時の利用枠リセットを、日本時間と根拠の確認状況で記録する非公式の無料サイト。

## 費用と公開条件

- GitHub Freeの**公開リポジトリ**とGitHub Pagesを利用する。URLはGitHub提供のものを使う。
- サーバー、独自ドメイン、有料AI API、有料X API、外部データベースは使わない。
- 定期処理は標準Linuxランナー1ジョブ。非公開リポジトリではジョブを実行しないガードがある。
- 有料プランへの変更や支払い方法の追加は行わない。無料サービスの条件変更があれば構成を見直す。

## 初回の公開設定

ソースをmainに反映した後、GitHubの管理画面で次を設定する。

1. Settings → General → Danger Zone → Change repository visibility → Public。
2. Settings → Pages → Build and deployment → Source → **GitHub Actions**。
3. 次の定期処理を待つ。すぐに公開する場合は、Actions → **Collect reset records and publish** → Run workflow。

ワークフロー成功後の公開URLはPagesの設定画面と、Actionsのdeployment結果で確認する。設定が完了するまで、公開済みとは報告しない。

## 自動運用

`.github/workflows/update.yml` がUTCの偶数時17分（日本時間の奇数時17分）に起動する設定。GitHub側の都合で遅れることがある。

1. テストを実行。
2. Codex Resetの公開データを取得し、正規化・重複排除。
3. 根拠区分を保持し、公式本文の取得状況を別に記録。
4. 取得状況 `data/health.json` を毎回保存し、HTMLを再生成して公開。履歴の追加がなくても公開を再試行するため、初回設定や一時的な配信失敗から次回の処理で復旧できる。
5. 取得失敗時は前回の履歴を保持し、状態を保存した上でジョブを失敗にする。通常のGitHub通知対象になる。

正常確認の記録を保存するため、履歴の追加が長くない場合もリポジトリに意味のある更新が残る。GitHubの権限変更・スケジュール停止・上流側の仕様変更などによる永久無停止を保証するものではない。サイトは最終成功から24時間を超えた場合に更新確認の表示を出す。

`health.json` は公開されたraw.githubusercontent.comから閲覧時に読み込み、履歴の更新と取得状態の更新を分ける。初回の定期取得が成功するまでは、サイトに初期データであることを明示する。

## 根拠と日時の方針

- 取得元の `confirmed: true` は、当サイトの公式確認を意味しない。
- `data/official-confirmations.json` に、人が公式本文を直接確認した根拠と確認範囲を記録する。
- 公式に日付だけ確認できても、参考時刻を公式確認済みにしない。
- 上流データは第三者記録。参考時刻はUTCからJSTへ換算するが、実施時刻を推定して補完しない。
- 一斉リセットと保存型リセットの付与を分ける。同じ付与の予告・配信確認を二重計上しない。
- 新しい情報源を増やすときも、認証不要・再利用条件・取得頻度を確認する。
- 上流の英文投稿全文を転載しない。公開データは日時・種類・対象・出典URLなどの事実項目に限定する。

出典：Codex Reset（https://codex-reset.com/ja/timeline/、掲載元の表示はCC BY 4.0）。公式確認はOpenAI公式ヘルプを用いる。ライセンス表示と元の出典はサイトに常時掲載する。

## ローカル確認（Python標準ライブラリのみ）

```sh
python3 -m unittest discover -s tests -v
python3 scripts/site.py refresh
python3 scripts/site.py build
```

既存の `data/events.json` があれば、ネットワークなしでbuildできる。取得に失敗した場合、refreshは終了コード2を返す。生成先は `docs/`。

## Google検索への準備

本文は静的HTMLで配信し、JavaScriptなしでも全履歴を読める。固有のtitle、説明、canonical、サイトマップ、RSS、CSVを生成する。

公開後にGoogle Search ConsoleのURLプレフィックスでサイトを登録し、所有者確認ファイルまたはメタタグを設定して `sitemap.xml` を送信する。所有者確認にはオーナーのGoogle認証が必要になる。検索登録・検索上位表示を保証するものではない。

## ファイル

- `scripts/site.py`：取得・正規化・生成
- `data/events.json`：保存する履歴
- `data/health.json`：取得状態と最終成功
- `data/official-confirmations.json`：直接確認した根拠
- `data/quoted-confirmations.json`：担当者発言の転載を確認した根拠
- `data/editorial.json`：確認した日本語の補足
- `docs/`：公開サイト
- `tests/`：日時・根拠区分・取得失敗・入力検証のテスト

サイトと実行履歴の修正は、このリポジトリで管理する。
