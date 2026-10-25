# `--context`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--context` |
| 別名 | なし |
| 値 | `SIZE`。token 数、または `k` / `m` 接尾辞付きのサイズ |

## 役割

モデルが一度に扱う文脈長（token 数）を指定します。より長い文脈は VRAM や RAM を多く必要とします。これは `strata launch` の起動設定用です。同じ名前の `strata connect --context` は接続先アプリへ通知する文脈長の設定であり、別の parser・文書スコープです（索引の `strata connect` 節を参照）。

## 使い方

```sh
strata launch --model iq3_xxs --context 128k --no-tui
```

この例では `128k` を 131072 token として解釈し、モデルの準備・起動に使います。起動前に計画だけを表示する場合は `--plan` を組み合わせられます。

## 値と既定値

- 値は空白を除いた後、`<数値>`、`<数値>k`、`<数値>m` の形式で読み取ります。大文字小文字は区別せず、数値部分には小数を指定できます。`k` は 1024 token、`m` は 1024×1024 token として換算し、最も近い整数に丸めます。前後の空白、数値中の空白・`_`・`,` は取り除かれます。例: `128k`、`128K`、`64 K`、`131072`。
- 換算後が 1024 token 未満なら拒否されます。数値以外の書式も拒否されます。launch parser 自体には上限値の検査がありません。
- `--context` を省略し、preset にも値がなければ、モデルとコンピューターに応じて `catalog.max_context(...)` が選びます。CLI オプションとして固定の数値既定値はありません。
- 同じオプションを複数回指定した場合、`argparse` の通常の単一値 action により最後の値が残ります。

## 実行時の動作

1. parser が値を token 数へ変換します。変換エラーは `argparse.ArgumentTypeError` にされ、通常の usage とエラー表示で終了します。
2. `strata launch --preset NAME` の場合は保存済み設定を読み、その上に明示した `--context` を適用します。したがって、明示値は preset の context を上書きします。どちらにも値がない場合、モデルが選ばれていると `catalog.max_context` の推奨値が入ります。
3. 値は setup.py の `--context <token数>` に転送されます。macOS の特定の経路では渡す引数を絞り込む処理がありますが、`--context` は維持されます。既に準備済みモデルの context が一致し、必要ファイルも揃っている場合は再セットアップを省略します。
4. setup.py は選んだ context を `--max-context` として生成する run config に記録します。256K（262144 token）を超えると、未指定時は RoPE の `yarn` 拡張を選び、最終 context / 262144 を基準に factor を決めます。launch は setup.py を `--yes` 付きで起動するため、この経路で対話質問は行いません。

## 適用条件と副作用

- モデルの学習長 262144 token を超える値は拒否されず、experimental な RoPE 拡張を伴う設定として扱われます。`strata launch` の `check_context` は 262144 超で警告を加え、回答の信頼性が下がる可能性を伝えます。
- ハードウェアの推奨 context より大きい場合、launch は警告を加えますが、通常は利用者が指定した値を保持します。setup.py も RAM 推定を超える値を保持して警告する旨の処理があります。小さいカード向け Unsloth 専用の調整処理など、モデル固有の例外は setup.py 側にあります。
- context の変更は、準備済み run config との一致判定にも使われます。一致しなければモデル準備処理を再実行し、モデル・設定・環境に応じてファイルの確認や取得などが行われます。起動時には生成された設定でエンジンを実行します。
- `--kv` を省略した場合、context が 8K を超えると setup.py は既定の `int8` KV cache を選び、8K 以下では `fp16` を使います。これは context とメモリ使用の相互作用です。
- 256K 超の拡張はモデル学習長を超える実験的な設定です。大きい context はメモリ不足や応答品質への影響を招く可能性があります。CLI はメモリ適合性を一律に拒否するのではなく、警告を示して起動を続ける設計です。

## 出力とエラー

- 形式不正または 1024 token 未満の値は parser 段階でエラーになります。`strata launch` の不明引数も `strata: ...` を stderr に出し終了コード 2 で返します。
- context の大きさ・学習長超過・RAM 推定超過は警告です。人向け出力では `[!]` 付きで表示され、JSON 出力では launch 結果の `notices` または計画の `warnings` に含まれます。
- setup.py や後続の起動が失敗した場合、launch は `LaunchError` をエラー文へ変換して返します。setup.py の出力は診断用ログへ保存される場合があります。context の parser だけで engine のメモリ確保成功を保証するものではありません。

## 根拠

- `strata_cli/launch/cmd.py:48-52,94` — launch の parser、`_context` 型変換。
- `strata_cli/launch/settings.py:47-57` — suffix・数値形式・換算・最小値の検証。
- `strata_cli/launch/cmd.py:197-225,302-340` — preset 読み込み後の明示値上書き、未指定時の model/hardware 推奨値、context 警告。
- `strata_cli/launch/runner.py:223-238,925-949` — 既存 config との context 比較、再利用条件、setup.py 起動。
- `strata_cli/launch/runner.py:727-775` — `--context` を setup.py に転送し、macOS 引数フィルターで保持する処理。
- `strata_cli/launch/runner.py:1235-1244` — launch 用 run config の生成。
- `setup.py:559-566,7286-7310,8428-8435,9050-9096,9418-9425` — setup の context 群、parser、既定値、学習長超過時の RoPE 設定、engine 引数への反映。
- `setup.py:9070-9077,9540-9564` — RAM 推定警告と Unsloth の小容量 GPU 向け例外処理。
- `strata_cli/cli.py:2223-2231` — launch/connect の不明引数エラー表示と終了コード。
- `strata_cli/launch/cmd.py:630-641,721-725,784-787` — launch の失敗出力と validation / runner error の処理。
- `docs/cli/README.md:925-985` — `strata launch` と `strata connect` の別々の `--context` 文書リンク。

## 調査範囲

checkout のソースと索引を確認しました。CLI help、実機の backend・モデル別実行結果、Release 配布物は照合していません。そのため、個別環境でのメモリ適合性や起動成功は断定していません。
