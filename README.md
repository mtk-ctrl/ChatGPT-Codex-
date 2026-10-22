# ChatGPT リセット履歴（非公式）

公開先：https://mtk-ctrl.github.io/ChatGPT-Codex-/

## 掲載方針

OpenAI公式サイトとOpenAI関係者本人のX原投稿だけを情報源として、Work・Codexの利用枠に関する臨時リセットを記録する。閲覧できる原投稿はXのURLを添え、原投稿の検索表示だけで確認した記録には「全文未確認」と明記する。

公式記事に日付しかない場合は日付だけを表示し、実施時刻は補完しない。Xの投稿日時は投稿IDから算出し、日本時間で表示する。投稿時刻と実際の反映時刻は異なり得る。実施予告・完了報告・リセットチケット配布を区別する。

## データと確認

- `data/events.json`：掲載履歴（OpenAI公式と関係者のX投稿）
- `data/official-confirmations.json`：公式本文による確認記録
- `data/health.json`：一次情報への取得状況
- `data/forecast-history.json`：独自予測の履歴
- `scripts/site.py`：サイトのHTML・CSV・RSS生成
- `scripts/primary.py`：OpenAI公式とX公開投稿の直接確認
- `scripts/forecast.py`：時刻が分かるリセット報告からの条件付き予測

最新の掲載は2026年10月22日にTibo氏がXへ投稿したDay17リセット予告と反映予定時刻の案内。予告：https://x.com/thsottiaux/status/2113162277688070445 ／反映予定：https://x.com/thsottiaux/status/2113162413008884099 。全員への完了確認は未発表で、ユーザー個別の利用枠回復とは区別する。

GitHub Freeの公開リポジトリとGitHub Pagesを利用し、GitHub Actionsで2時間おきに更新を試みる。X公開ページがアクセスを拒否することがあり、取得できない場合は `data/health.json` に失敗状況を明示する。新着を取得できなかったことは、新しいリセットがなかったことを意味しない。

予測は当サイトの計算による試算であり、OpenAIの予定発表でも的中保証でもない。取得に失敗してデータの鮮度を確認できない場合は予測を表示しない。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/site.py refresh
python3 scripts/site.py build
```

## 表記

利用者が期限内に自分で適用する「banked reset」は、閲覧者に伝わりやすいよう公開サイトでは「リセットチケット」と呼び、カレンダーの短い表示では「チケット」とする。OpenAIの日本語公式案内では「保存済みリセット」と表記される。運用データ上の種類コード `banked` は変えない。

## 公開時の表記基準

- 「臨時リセット」は発表で対象とされたプラン・機能だけを指す。ChatGPT利用者全員を意味しない。
- 投稿1件ごとに履歴を掲載し、予告と実施報告は別記録とする。掲載件数を実施回数として案内しない。
- データ上の`products`は大まかな分類であり個別投稿の対象サービスの証明ではないため、根拠のない対象ラベルは表示しない。
- Xの投稿時刻は日本時間。OpenAI公式の日付だけの記載は日本時間に変換しない。
- RSS・CSVにも予告と実施の違いを残す。

## 2026年10月23日の予想

`data/editorial-forecast.json` はサイト運営者の非公式な予想を保存する。10月11・13・15・18・20日の実施報告が2～3日間隔だったことをもとに23日を予想する。公式発表・自動の確率計算とは別枠で表示する。10月22日にDay17の新たな公式予告が出たため、23日の予想は「次回予想」としての表示を終了した。予想内容と事前の根拠は履歴として保持し、公式の実施確定とは混同しない。

## 2026年10月25日（日）の予想

2026年10月23日07:03（日本時間）、ユーザーは次回を**10月25日（日）**と予想。13・15・18・20・22日という直近の発表間隔（2・3・2・2日）から、22日から3日後を選んだ。日本時間の日曜にもX実施報告があり、週末という理由のみでは除外しない。独自予想でありOpenAIの確定日ではない。表示期限は10月26日00:00 JST。旧23日の予想は `data/editorial-forecast-history.json` に保存。

## 予想の公開日時の保存

- 2026年10月23日（金）予想：**2026年10月20日23:17（JST）** にサイト公開。根拠：GitHub PagesのPublish完了時刻 https://github.com/mtk-ctrl/ChatGPT-Codex-/actions/runs/39437667124 。履歴は `data/editorial-forecast-history.json`。
- 2026年10月25日（日）予想：**2026年10月23日07:07（JST）** にサイト公開。根拠：GitHub PagesのPublish完了時刻 https://github.com/mtk-ctrl/ChatGPT-Codex-/actions/runs/39862593473 。現行設定は `data/editorial-forecast.json`。
- `created_at`（会話・編集で案を決めた日時）と `published_at`（GitHub Pagesで公開が完了した日時）は別。予想を公開したら、成功したPublishステップの完了時刻とrun IDを確認して `published_at` / `publication_run_id` に固定保存する。次回予想への更新時は旧データをアーカイブに加え、元の公開日時を書き換えない。
