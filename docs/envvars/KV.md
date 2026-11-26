# `KV`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

`KV` は Strata の Docker entrypoint 専用の入力です。既定のサーバー起動経路で、値が空でなければ `strata launch` に `--kv <値>` を追加し、選んだモデルの会話メモリー形式として起動設定へ渡します。Strata のエンジンが環境変数 `KV` を直接読む実装は見つかりませんでした。コンテナから `strata` 以外のコマンドを直接実行する経路、および `docker run IMAGE strata ...` で任意の Strata コマンドを実行する経路では、この Docker 設定変換を通りません（`tools/docker/entrypoint.sh:68-71, 184-218`）。

## 値と判定

entrypoint は `${KV:-}` の空文字置換と `[ -n ... ]` で判定します。未設定と空文字は同じ扱いで、`--kv` を追加しません。空でない値は trim や大文字小文字変換をせず、一つの引数として `--kv` の後ろに渡します。したがって、通常の値 `int8` は渡されますが、`1` や `int8xyz` も entrypoint 自体では拒否されず、後段の `strata launch` が検査します。空白だけの値も entrypoint では「設定あり」となりますが、launch 側では trim 後に空になり不正値です（`tools/docker/entrypoint.sh:218`; `terminal/strata_cli/launch/cmd.py:35-43, 92`）。

| 条件 | unset / 空文字 | 受理される値 | 無効値・後段の扱い |
| --- | --- | --- | --- |
| Docker の通常サーバー起動 | CLI に値を渡さない。既存 preset の設定があればそれが使われ、選択もなければ launch のモデル・context 既定に従う | launch parser が前後空白を除去し小文字化した後、`int8`, `q4_0`, `k8v4`, `fp16`, `fp8`, `k8v8` のいずれかとなる値 | `strata launch` の引数エラー。Docker entrypoint は起動時の非ゼロ終了を `strata launch stopped with code ...` として stderr に出し、コンテナを終了する（`tools/docker/entrypoint.sh:268-276, 303-316`; `terminal/strata_cli/launch/settings.py:38-45`; `terminal/strata_cli/launch/cmd.py:35-43, 92`） |

## 有効になる条件

- コンテナの既定起動経路を使う必要があります。任意のコマンド実行では `entrypoint.sh` は `exec` で抜け、`KV` を CLI 引数に変換しません（`tools/docker/entrypoint.sh:68-71`）。
- `KV` が空でない場合でも、対象モデル・エンジンがその形式を使うとは限りません。標準モデル向けの launch では未指定時の KV は context が 8K 超なら `int8`、それ以外なら `fp16` とされます（`terminal/strata_cli/launch/settings.py:122-135`; `terminal/strata_cli/launch/runner.py:345-347`）。
- Qwen3.6 系（`qwen35moe`）は専用の `fp32` / `fp16` / `fp8` / `fp4` を扱います。Docker の `KV` と launch parser は `fp32` / `fp4` を有効値として受け付けないため、それらを `KV` 経由で指定できません。Qwen3.6 に Flash-Next 用形式（例 `int8`）を渡すと setup は警告し、既定の `fp32` を維持します（`terminal/strata_cli/launch/runner.py:339-344`; `terminal/setup.py:9911-9913`）。
- Tencent Hy4-Flash はこの `--kv` 設定の対象外で、Flash-Next 用設定として警告されます（`terminal/setup.py:10328-10329`）。
- Inkling-2-Mini は backend により許可形式が異なります。CUDA は `fp16`, `fp8`, `k8v8`, `k8v4`、HIP / Metal / SYCL は `fp16`, `fp8` です。後者で `k8v4` または `k8v8` を指定すると `fp8` に置き換えて警告し、`int8` / `q4_0` は不適合形式として警告してエンジン既定値を使います（`terminal/strata_cli/launch/settings.py:38-45, 48-74`; `terminal/strata_cli/launch/runner.py:329-337, 773-785, 2219-2223`）。

## 実行時の詳細

`entrypoint.sh` は起動時に環境を展開し、`KV` が空でなければ他の設定と同じ `strata launch --no-tui ...` コマンド列へ `--kv` と値を追加します。`KV` 専用の cache や再読込経路はありません。以後の処理は launch の CLI 設定として行われ、entrypoint 自体は実行中の環境変更を監視しません（`tools/docker/entrypoint.sh:184-218, 268-307`）。

この設定が指定されると entrypoint は `have` を立て、preset が既にあれば `--save-preset <PRESET>` を付け、なければ同じ preset 名で保存します。そのため明示した値は選択中モデルの起動設定に保存されます。`KV` を未設定または空にした場合は今回の起動から `--kv` の指定を省き、既存 preset の値が残っていればそれを使います（`tools/docker/entrypoint.sh:213-218, 268-276`; `terminal/strata_cli/launch/cmd.py:248-249`; `terminal/strata_cli/launch/runner.py:305-308, 345-347`）。

通常の launch setup は Qwen / Gyro 系へ `--kv` を渡し、Inkling では backend 対応値に直して渡します。Qwen3.6 は専用形式のみを転送し、Hy4-Flash はこの設定を使いません（`terminal/strata_cli/launch/runner.py:1351-1374`; `terminal/setup.py:9911-9913, 10328-10329, 10891-10897`）。エンジンの generate CLI は `--kv` を受け取り、`q4` を `q4_0` に別名変換した後、`fp16`, `int8`, `q4_0`, `k8v4` 以外をエラーコード 2 で拒否します。許容値は各エンジン経路で異なるため、この generate 側の規則を Inkling や Qwen3.6 に一律適用するものではありません（`engine/src/program/generate.cpp:3906, 5014-5027`）。

## ログと測定値

Docker entrypoint は `KV` の値だけを理由にしたログを出しません。launch parser が値を拒否した場合は argparse のエラーとなり、entrypoint は `strata launch stopped with code <終了コード> (the lines above say why). ...` を stderr に出して終了します（`tools/docker/entrypoint.sh:314-316`; `terminal/strata_cli/launch/cmd.py:35-43`）。Inkling の形式不適合・backend 置換では launch が次の警告を出します。

- `--kv <形式> is not a memory format of Inkling-2-Mini (it takes <形式一覧>), so the engine's own default is used.`
- `Inkling-2-Mini on <backend> does not support --kv <形式> (it takes <形式一覧>); using --kv fp8 instead.`

根拠: `terminal/strata_cli/launch/settings.py:61-74`; `terminal/strata_cli/launch/runner.py:2219-2223`。この調査では build・実行・測定は行っていません。

## 根拠

- `tools/docker/entrypoint.sh:68-71, 184-218, 268-276, 303-316` — Docker 起動経路、値判定、`--kv` 付加、preset 保存、失敗時終了。
- `terminal/strata_cli/launch/settings.py:38-74, 122-135` — launch が受理する形式、Inkling 対応形式と警告、未指定時設定。
- `terminal/strata_cli/launch/cmd.py:35-43, 92, 248-249` — 値の正規化・検証と `LaunchSettings` への反映。
- `terminal/strata_cli/launch/runner.py:305-354, 773-785, 1351-1374, 2219-2223` — モデル設定への反映と Inkling backend 対応。
- `terminal/setup.py:9911-9913, 10328-10329, 10891-10897, 11460-11462` — Qwen3.6 / Hy4 / Inkling の設定差と setup の受理値。
- `engine/src/program/generate.cpp:3906, 5014-5027` — generate CLI の `--kv` 処理、値検証、K/V 形式の選択。
