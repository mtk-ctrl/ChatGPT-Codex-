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

最新の掲載は2026年10月20日にTibo氏がXへ投稿した利用枠リセット報告。原投稿：https://x.com/thsottiaux/status/2112432076767289678

GitHub Freeの公開リポジトリとGitHub Pagesを利用し、GitHub Actionsで2時間おきに更新を試みる。X公開ページがアクセスを拒否することがあり、取得できない場合は `data/health.json` に失敗状況を明示する。新着を取得できなかったことは、新しいリセットがなかったことを意味しない。

予測は当サイトの計算による試算であり、OpenAIの予定発表でも的中保証でもない。取得に失敗してデータの鮮度を確認できない場合は予測を表示しない。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/site.py refresh
python3 scripts/site.py build
```

## 表記

利用者が期限内に自分で適用する「banked reset」は、閲覧者に伝わりやすいよう公開サイトでは「リセットチケット」と呼び、カレンダーの短い表示では「チケット」とする。OpenAIの日本語公式案内では「保存済みリセット」と表記される。運用データ上の種類コード `banked` は変えない。
