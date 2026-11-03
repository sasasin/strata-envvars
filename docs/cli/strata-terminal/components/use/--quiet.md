# `strata components use --quiet`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ。省略時は無効、指定時は有効。 |

## 役割

成功時の人間向け標準出力を抑制します。`components use` のエンジン選択や切り替えを変更するフラグではなく、CLI 共通層で出力を扱います。索引では `components use` のオプションとして列挙され、`strata_cli.cli.parser()` が `update_cmd.add_parsers()` の返す parser 群に `--quiet` を後付けしています（`strata_cli/cli.py:139-140,508-515`）。

## 使い方

```sh
strata components use newest --quiet
```

この例はインストール済みの最新 engine を選択し、成功時の人間向けメッセージを表示しません。`engine` 引数は版番号、folder 名、または `newest` で、`--quiet` はその後付け option 群の一つです（`strata_cli/update_cmd.py:84-87`）。

## 値と既定値

- `store_true` のフラグで、値は不要です。既定値は `argparse.SUPPRESS` であり、未指定時には属性を作らず、実行時は `getattr(a, "quiet", False)` で無効として扱います（`strata_cli/cli.py:508-515,2253`）。
- 追加の形式・範囲検証はありません。繰り返し指定や値を続けた場合の特別な処理は定義されていません。`--quiet` の後ろに値を置けば通常は未認識引数となり、CLI が usage error を返します（`strata_cli/cli.py:2241-2248`）。

## 実行時の動作

`strata components use` は `update_cmd.run()` に渡され、その中の `_engines_command()` が `engine_library.use_engine()` を呼びます（`strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:272-273,378-394`）。通常の人間向け出力には、選択 engine が既に使用中か、切り替わったか、tuning preset を再確認対象にしたか、更新追従に戻る方法が含まれます（`strata_cli/update_cmd.py:386-393`）。

`main()` は human 出力で `--quiet` が有効な場合、対象外の常時表示コマンドでなければ `_run()` 中の stdout を一時捕捉します。`components use` は対象外一覧に含まれないため、成功時の human stdout は表示されません（`strata_cli/cli.py:2253-2260`）。捕捉上限は 64 KiB で、終了コードが非ゼロなら捕捉内容を stderr に戻します。上限を超えて切り詰めた場合は、その前に `strata: earlier human output omitted in quiet mode` も stderr に出します（`strata_cli/cli.py:2197-2212,2261-2265`）。

切り替え処理自体は抑制されません。対象 engine の検査後、`use_engine()` は更新ロックを取り、serving 中なら idle になるまで待つか busy error にし、該当 family の切り替え処理へ進みます（`strata_cli/update_cmd.py:378-383`、`strata_control/engine_library.py:225-240`）。したがって `--quiet` は engine の選択、preset の扱い、ファイル・状態の変更を無効化しません。

## 適用条件と副作用

- `--quiet` は `update_parsers` 全体への後付けなので、`components use` を含む同リストの parser で有効です（`strata_cli/cli.py:508-515`）。
- `--json` は同じ parser 群に追加され、指定されると `output` が `json` に切り替わります。JSON/JSONL の場合は `main()` の quiet 捕捉を通らず、JSON 応答は quiet によって消えません（`strata_cli/cli.py:512-515,2249-2254`）。`_engines_command()` は machine 出力時に JSON を出します（`strata_cli/update_cmd.py:384-385`）。
- 対話待機の抑止や自動承認はしません。`components use` は serving 状態を確認し、条件によっては `input()` で待機確認を行います（`strata_cli/update_cmd.py:378-380,403-418`）。`--quiet` 有効時は `_run()` 全体の stdout がリダイレクトされるため、その確認 prompt も表示されない可能性があります。これは `input()` と stdout リダイレクトの組み合わせから分かる点で、対話環境で使う場合は注意が必要です。
- `--wait` は `_maybe_wait()` の待機時間設定として別に処理され、`--quiet` はこの値を変えません（`strata_cli/update_cmd.py:47-56,403-418`）。

## 出力とエラー

成功時は人間向け stdout を抑制します。engine が見つからない・複数に一致する場合などの `UpdateError` は `run()` が通常 stderr に出してエラーコードを返します。実行可能性がない engine はコード 5 で拒否され、serving 中に切り替えできない場合は `engine_library` の busy 経路で変更せず失敗します（`strata_control/engine_library.py:198-210,216-240`、`strata_cli/update_cmd.py:237-242,378-383,307-311`）。非ゼロ終了時には quiet が捕捉した stdout も stderr に転送されます（`strata_cli/cli.py:2261-2265`）。

## 根拠

- parser への共通 option 追加と既定値: `strata_cli/cli.py:508-515`
- quiet 時の出力捕捉、対象外コマンド、失敗時の転送: `strata_cli/cli.py:2197-2212,2253-2265`
- `components use` parser と位置引数・関連 option: `strata_cli/update_cmd.py:47-56,84-87`
- command dispatch と engine 切り替え・人間向け出力: `strata_cli/cli.py:2136-2138`、`strata_cli/update_cmd.py:272-273,378-394`
- engine の検索・serving 中の切り替え待ち・失敗経路: `strata_control/engine_library.py:198-240`、`strata_cli/update_cmd.py:403-418`
