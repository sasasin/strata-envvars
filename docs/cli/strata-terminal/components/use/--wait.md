# `strata components use --wait`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components use` |
| オプション | `--wait` |
| 別名 | なし |
| 値 | 秒数。`argparse` の `float` として解釈 |

## 役割

Engine が serving 中のとき、停止するまで待ってから engine を切り替える上限時間を指定します。切替先の engine を導入するオプションではありません。切替先は `engine` 位置引数で指定し、すでにインストール済みで、この PC で実行可能である必要があります（`strata_cli/update_cmd.py:84-87`、`strata_control/engine_library.py:225-239`）。

## 使い方

```sh
strata components use 0.1.54 --wait 60
```

上の例は、指定した engine へ切り替える際、稼働中の engine が停止するまで最大 60 秒待ちます。

## 値と既定値

- 値は `float` 秒です。parser に既定値の指定はなく、省略時は `None` です（`strata_cli/update_cmd.py:47-56`）。
- 正数を明示すると、その秒数を上限に待機します。待機中は 3 秒間隔で serving 状態を確認し、上限に達しても serving 中なら `Busy` として切替を拒否します（`strata_control/updater.py:311-322`、`strata_control/engine_library.py:232-236`）。
- `0` または負数は待機しません。serving 中なら即時に拒否されます。`strata_cli/update_cmd.py:255` は値を `a.wait or 0.0` として context に渡し、`strata_control/updater.py:317` が `wait <= 0` を拒否条件にします。
- `float` への変換に失敗する値は `argparse` に拒否されます。正数・非負などの範囲 validation はありません。したがって `inf` や `nan` も parser 上は排除されず、待機期限判定で有限の期限として機能しない場合があります（`strata_cli/update_cmd.py:51-52`、`strata_control/updater.py:314-321`）。
- オプションを複数回指定した場合の専用処理はありません。`argparse` の通常の単一値引数として扱われます。

## 実行時の動作

`strata_cli/update_cmd.py:51-52` の `_common()` が `--wait SECONDS` を `type=float, default=None` で登録し、`use` parser にも `_common(use)` で追加します（同:84-87）。実行時に値は `updater.Context.wait` に渡されます（同:254-256）。

`use` の処理は、まずインストール済み engine 一覧から位置引数と `--family` に一致する項目を解決し、その後 `_maybe_wait()` を呼びます（`strata_cli/update_cmd.py:378-383`）。明示した `--wait` が truthy なら対話確認は行わず、指定秒数で `use_engine()` の待機処理に進みます。engine 切替処理は update lock を取得して serving 状態を再確認するため、事前確認と切替の間に状態が変化しても、serving 中のまま切替を実行しません（`strata_control/engine_library.py:232-239`）。

`--wait` を省略するか `0` を指定した場合、`_maybe_wait()` は serving がなければそのまま進みます。通常の terminal 対話で別の serving instance がある場合は「停止を待つか」を尋ね、`y` / `yes` なら待機上限を 6 時間にします。既定回答は No です。`launch-` で始まる profile の instance が serving 中なら質問せず、また JSON/JSONL 出力または非 TTY 入力でも質問しません（`strata_cli/update_cmd.py:403-418`）。

待機対象は `updater.serving_now()` が検出する managed instance または共有 activity lease を保持する Strata server です（`strata_cli/update_cmd.py:358-362`、`strata_control/updater.py:286-308`）。停止を検出すると、指定 engine が切替可能か確認し、Qwen 系または DeepSeek 系の選択状態を更新します。`--wait` 自体は engine のダウンロードや削除を行いません（`strata_cli/update_cmd.py:381-394`、`strata_control/engine_library.py:225-239`）。

## 適用条件と副作用

- `--wait` は `strata components use` 以外にも `_common()` を使う関連 parser で受理されますが、この文書の対象は `use` の挙動です（`strata_cli/update_cmd.py:47-56,80-95`）。
- serving が停止しない場合、または `--wait 0` / 負数のまま serving 中の場合、engine は切り替わらず exit code 7 になります（`strata_control/updater.py:311-322`、`strata_control/engine_library.py:216-222,232-236`）。
- 待機後の切替はインストール済み engine の選択状態に作用します。切替自体の保存先や family ごとの状態更新は `strata_control/engine_library.py:242-289` に実装されています。待機中に engine が停止するようプロセスへ命令する処理は、このオプションの経路にはありません。

## 出力とエラー

- 人向け出力では、成功時に切替先や以前の engine、保存済み tuning preset の扱いを表示します（`strata_cli/update_cmd.py:386-393`）。
- JSON/JSONL 出力では `_maybe_wait()` の対話確認を行わず、エラーは `{schema_version, ok: false, error: {code, message}}` の JSON として出力されます。通常の人向け出力では `strata: ...` を stderr に出します（`strata_cli/update_cmd.py:235-242,307-311`）。
- 待機上限超過時の exit code は 7 です。未導入の engine や曖昧な指定は exit code 2、実行できない engine は exit code 5 で失敗します（`strata_control/engine_library.py:198-211,216-222`、`strata_cli/update_cmd.py:379-383`）。

## 根拠

- parser・値型・既定値・共通適用: `strata_cli/update_cmd.py:47-56,84-87`
- 値の context への受け渡し、`use` 分岐、エラー出力: `strata_cli/update_cmd.py:233-256,307-319,378-394,403-418`
- 待機確認と上限超過: `strata_control/updater.py:286-322`
- 切替時の再確認と Busy の扱い: `strata_control/engine_library.py:216-239`
- 切替先解決時の未導入・曖昧指定エラー: `strata_control/engine_library.py:198-211`
