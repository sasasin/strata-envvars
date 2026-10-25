# `strata tune plan`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata tune plan` |
| 主な実装 | `strata_cli/cli.py`、`strata_control/tuning.py` |

## 役割

バックエンドと engine が扱える探索次元、その候補値、探索対象外となる次元と理由を表示する計画コマンドです。後続の測定を実行したり、現在の profile を変更したりはしません。`--time` は計画に上限値として記録・表示されますが、このコマンド自体は時間計測をしません。

このコマンドは engine の `--help` を実行して対応フラグを読み取ります。照会できた場合は、backend 用の各次元が engine に受理されるフラグだけを使うか確認します。engine を実行できない場合は静的な backend 表を使い、その状態を計画に記録します。

## 基本的な使い方

```sh
strata tune plan --engine /path/to/strata --backend cuda --model my-model

# 探索範囲を狭め、機械処理向け JSON で表示
strata tune plan --engine /path/to/strata --backend cuda --model my-model \
  --objective prefill --trials 8 --repeats 5 --hold expert_cache --output json
```

`--engine` は engine バイナリへのパスのほか、インストール済みコンポーネントを指す `component:strata-engine` 形式を使えます。この参照形式では `--backend` に応じた engine を解決します。`--backend` は `metal`、`cuda`、`hip`、`sycl`、`cpu` のいずれか、`--objective` は `generation`、`prefill`、`latency` のいずれかです。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 人向け表示 | `strata tune plan --engine PATH --backend cpu --model MODEL` | engine、backend、objective、反復数、探索上限、探索次元、除外理由を標準出力に表示します。 |
| JSON 表示 | 上記に `--output json` を追加 | 計画全体を `{"ok":true,"plan":...}` 形式の JSON として標準出力に出します。 |

## 計画作成時の動作

- engine の `--help` を最大20秒で起動し、標準出力と標準エラーの両方から `--...` フラグを集めます。エンジンパッケージに `engine-component.json` がある場合、同梱ライブラリの場所を環境変数のライブラリパスへ加えて起動します。
- 起動できない、またはフラグ一覧を得られない場合、フラグ一覧は未知として扱われ、backend の静的なルールで探索次元を判定します。取得できた場合は、その engine が受理するフラグを含まない次元を除外理由付きで記録します。
- `--hold DIMENSION` は繰り返し指定できます。指定された次元は探索から外れます。backend に存在しない次元名も parser では拒否せず、「固定指定、またはこの backend の次元ではない」として除外一覧に入ります。
- `--trials` は整数を受け取り、計画では負数を0に丸めます。`--repeats` も整数を受け取り、1未満は1に丸めます。`--time` は浮動小数値を受け取り、その値をそのまま計画に格納します。これらの数値オプションには parser 上の正の範囲制約はありません。
- CLI は `model_path` を渡さず、`--model` の文字列だけを計画に記録します。そのため、この経路で作る比較用 identity ではモデルファイルのパス・digest・サイズは不明になります。
- 成功した計画は毎回新しい ID と作成時刻を含みます。`--output json` はそれを含む全計画を出力します。人向け表示では探索次元が空の場合にその旨を表示し、最後に結果の適用は別工程で profile を書き換えないことを示します。

## 注意点

- 計画表示でも engine の `--help` 子プロセスは起動します。指定した engine は実行可能で、対象環境で `--help` を安全に照会できるものを使ってください。照会失敗は通常、CLI エラーではなく静的表への fallback として記録されます。
- backend と engine の実態が一致しないと、探索次元が全て除外され、backend が engine package と一致するか確認するよう促す計画になります。
- `--time` は sweep 時に新しい trial を開始する期限として説明される値ですが、`plan` では表示用の計画値です。負値やゼロを含む範囲の制約は CLI 側で検証されません。
- CLI の `--model` は計画上のモデル名です。このコマンドはモデルファイルのパスを受け取らず、ファイル内容も確認しません。

## 出力とエラー

- 不正な選択値や数値型は `argparse` の parser で拒否されます。`--engine`、`--backend`、`--model` は必須です。
- `component:strata-engine` の参照先が見つからない場合はエラーコード5になります。通常の `ValueError` 系は既定でコード2、ファイル操作の `OSError` はコード6として処理されます。人向けエラーは標準エラーへ、`--output json` のエラーは `ok:false` を含む JSON へ出力されます。
- engine の `--help` を起動できない場合は `_tune` の処理を失敗させず、エンジンフラグ未知として計画を続けます。

## 関連文書

- [`strata tune` の概要](../README.md)
- [CLI 索引と `tune plan` のオプション一覧](../../../README.md#strata-tune-plan-tuneplan)

## 根拠

- Strata `strata_cli/cli.py:23` — backend の受理値。
- Strata `strata_cli/cli.py:395-412` — `tune plan` の登録、必須引数、選択値、既定値。
- Strata `strata_cli/cli.py:1621-1629` — engine path と component 参照の解決。
- Strata `strata_cli/cli.py:1632-1639,1715-1739` — plan の役割、生成呼び出し、人向け・JSON 出力。
- Strata `strata_control/tuning.py:151-174` — backend と engine のフラグに基づく探索次元の選別。
- Strata `strata_control/tuning.py:189-224` — engine 起動方法、環境、`--help` の読み取りと失敗時の扱い。
- Strata `strata_control/tuning.py:723-768` — hold の処理、trial/repeat の補正、計画・identity 作成。
- Strata `strata_control/tune_history.py:48-81,99-118` — file identity と未知のモデル情報を含む comparison key の生成。
- Strata `strata_cli/cli.py:527-541,2166-2188` — エラー時の出力先と終了コードの伝播、成功時の JSON 形式。
