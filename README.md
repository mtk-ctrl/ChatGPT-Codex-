# ChatGPT リセット履歴（非公式）

公開先: https://mtk-ctrl.github.io/ChatGPT-Codex-/

## 情報源は一次資料だけ

- OpenAI公式サイト（openai.com／help.openai.com）と、OpenAI関係者本人のX原投稿のみを対象にする。
- 現在の自動収集対象：OpenAI公式ヘルプ、Xの @thsottiaux と @OpenAI。外部の履歴サイト、転載記事、外部のAPIを収集しない。
- 第三者サイト由来の旧63件をそのまま流用せず、OpenAI公式記事で確認した3件と、Xの原投稿を検索結果の本文抜粋で照合できた53件を再登録した（合計56件）。未確認の記録は復元しない。
- XはOpenAI関係者本人の原投稿について、本人アカウント・Xの原投稿URL・検索エンジンに登録されたそのX原投稿の本文抜粋を照合できた場合に登録する。これらは「検索表示で確認・全文未確認」として区別する。元投稿URLだけ存在する記録は確定扱いしない。
- 公式に時刻の記載がない日付は「公式記載日・時刻未公表」と表示し、勝手な日本時間変換・時刻の補完は行わない。
- X投稿のSnowflake IDから投稿時刻を計算するが、これはリセットの実施時刻ではない。以前の外部記録の日時は引き継がず、投稿IDから一律に再計算している。

## 確認済みの一次情報

OpenAI公式ヘルプ「Managing usage with GPT-6 Astra in Work and Codex」に明記された2026年9月3日・4日の保存型リセット配布、9月7日の一斉リセット。
一次資料: https://help.openai.com/en/articles/20001516-managing-usage-with-gpt-6-astra-in-work-and-codex

## 自動更新と限界

GitHub Pagesで公開、GitHub Actionsが2時間おきに公式ヘルプとXの公開プロフィールへ直接アクセスを試す。Xはアクセス制限により新着投稿を自動取得できない場合がある。見つからなかったことはリセットがなかったことの証明ではない。収集失敗は data/health.json に記録し、他サイトから補わない。

無料のGitHub FreeとPython標準ライブラリのみ利用する。X有料API・AI有料API・外部DB・独自ドメインは使わない。

独自予測は、十分な数の「時刻付き一次資料」が揃い、かつ収集の鮮度を確認できた場合のみ実行する。Xの新着取得が停止している間は予測を表示しない。2026年9月の日付のみの情報は時刻間隔の計算に使わない。第三者由来の過去の予測記録は初期化した。予測はOpenAI公式の予定ではなく、的中を保証しない。

```sh
python3 -m unittest discover -s tests -v
python3 scripts/site.py refresh
python3 scripts/site.py build
```

以前の第三者データ取り込み用 --input オプションは使用禁止。Gitの過去コミットには履歴が残るため、現在の公開データから削除することと過去Git履歴そのものの消去は別である。
