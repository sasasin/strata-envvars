# `--force`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時 `False`、指定時 `True`。 |

## 役割

このコマンドでは `--force` は共通 parser option として受理されますが、engine 切替の動作には使われません。名前から「検査を無視して切り替える」などの効果を期待して付けても、その効果はありません。共通定義の説明文が示す再試行用途は update 経路向けです。

## 使い方

```sh
strata components use newest --force
```

この例では `newest` の engine を選ぶ動作は通常どおり行われます。`--force` は切替条件を変更しません。実際に切り替える engine は事前に `strata components engines` で確認してください。

## 値と既定値

`strata_cli/update_cmd.py:53` で `action="store_true"`、既定値の指定なしで定義されています。値を続けて渡す形式ではなく、追加の値検証もありません。`strata_cli/update_cmd.py:84-87` で同じ `_common()` が `use` parser に適用されます。

## 実行時の動作

parser がセットした値は `strata_cli/update_cmd.py:254-256` で `updater.Context(force=...)` に渡されます。ただし `use` は `strata_cli/update_cmd.py:378-383` から `find_entry()`、適用条件確認、`engine_library.use_engine()` を呼び、`force` を参照しません。`engine_library.use_engine()` も context の `force` を使わず、engine の family・folder の検査、実行中モデルとの競合確認、Qwen / DeepSeek の切替処理を行います（`strata_control/engine_library.py:225-239`）。

`force` を参照する updater の経路は別用途です。たとえば update の候補選定では、以前テスト起動に失敗した候補を通常は `failed-before` として抑止し、`ctx.force` が真なら候補を再試行できるようにします（`strata_control/updater.py:634-642,1098-1109`）。これは `strata update` などの更新経路であり、`components use` の切替経路には適用されません。

## 適用条件と副作用

`--force` 自体による追加の副作用はありません。指定の有無にかかわらず、対象 engine がこの PC で実行可能かを調べ、適合しなければ exit code 5 で拒否します（`strata_cli/update_cmd.py:378-383`）。切替要求は更新 lock の下で処理され、engine が serving 中なら待機するか exit code 7 で拒否されます（`strata_control/engine_library.py:232-239`）。DeepSeek engine の切替では選択した executable の test start に失敗すると exit code 5 になります（同 `:265-289`）。`--force` はこれらの検査を無効化しません。

切替が成功した場合の実際の副作用は、以後起動するモデルが選択 engine を使うようにすることです。ダウンロードや削除はしません（`strata_cli/update_cmd.py:84-85`、`strata_control/engine_library.py:225-227`）。これは `--force` 固有の効果ではありません。

## 出力とエラー

`--force` を付けたこと自体を示す出力や警告はありません。切替成功時は通常の human 出力、または `--output json` / `jsonl` に応じた結果を返します（`strata_cli/update_cmd.py:383-393`、`strata_cli/update_cmd.py:47-56`）。engine 名が見つからない・複数候補に一致する場合は `strata_control/engine_library.py:198-210` により exit code 2、実行不可または DeepSeek test start 失敗は exit code 5、モデル稼働中で切替できない場合は exit code 7 です（同 `:216-222,265-279`）。これらの結果は `--force` でも変わりません。

## 根拠

- `strata_cli/update_cmd.py:47-56,84-87` — `--force` の共通 parser 定義、`components use` への適用。
- `strata_cli/update_cmd.py:254-256,378-394` — Context への格納後、切替分岐では `force` を消費しないこと、通常の出力。
- `strata_control/engine_library.py:198-210,216-239,246-289` — engine 解決、切替条件と副作用、失敗経路。
- `strata_control/updater.py:634-642,1098-1109` — `force` が更新候補の再試行に使われる経路。
