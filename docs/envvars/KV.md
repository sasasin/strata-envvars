# `KV`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。対象は Strata 所有ソース。外部ライブラリ・driver の環境変数動作は含めない。

## 役割

Docker コンテナの標準起動で、会話用 KV cache の形式を選びます。`docker/entrypoint.sh` は空でない `KV` を `strata launch --kv <値>` に変換します。Docker entrypoint の標準起動経路だけで参照され、`docker run <image> strata ...` や `docker run <image> sh` のように別コマンドを指定した場合は、環境設定の組み立てより前にそのコマンドへ `exec` するため、この読み取りは行われません（`docker/entrypoint.sh:1-7,53-56,169-195`）。

## 値と判定

| `KV` の状態 | entrypoint の処理 | 結果 |
|---|---|---|
| 未設定 | `${KV:-}` が空になり、条件不成立 | `--kv` を追加しない。変数独自の既定値はない |
| 空文字 | 未設定と同じ | `--kv` を追加しない |
| 非空文字列 | 値をそのまま `--kv` の引数に追加 | `strata launch` が形式を検証する |

根拠: `docker/entrypoint.sh:190-196`。

`strata launch` は値を前後空白除去後に小文字化し、`int8`, `q4_0`, `k8v4`, `fp16` だけを受理します。従って大文字・前後空白は正規化されますが、`q4`、空白だけの値、その他の文字列は受理されません（`strata_cli/launch/cmd.py:37-45,95`; `strata_cli/launch/settings.py:62`）。entrypoint 自体では値の検査や変換はしません。

## 有効になる条件

- `KV` を読むのは Docker entrypoint が `run`（既定 CMD を含む）または `serve` の標準サーバー起動を行う経路です。別コマンドを指定すると line 54-56 の分岐で直ちに `exec` し、`KV` は Strata の環境設定として処理されません（`docker/entrypoint.sh:5-7,53-56`）。
- 標準起動では、まず `PRESET`（既定 `docker`）の保存設定があれば読み込み、その後 CLI オプションを重ねます。非空の `KV` が生成する `--kv` は保存 preset の形式を上書きします。`KV` が未設定または空なら `--kv` が無いため、保存 preset の値があればそのままです（`docker/entrypoint.sh:34,169-195,243-250`; `strata_cli/launch/cmd.py:212-218,239-242`）。
- 非空の `KV` は `have` も設定するため、既存 preset があれば起動時にその名前で保存されます。preset がまだ無くても `PRESET` 名で保存されます。従って指定した形式は後続起動にも残ります。空・未設定では `KV` を理由に preset を更新しません（`docker/entrypoint.sh:190-195,243-250`; `strata_cli/launch/cmd.py:307-309,993-997`; `strata_cli/launch/store.py:75-85`）。
- Docker の `--kv` は `strata launch` の設定・セットアップへ渡され、セットアップ引数にも非空の設定値が入ります（`strata_cli/launch/runner.py:936-950`）。セットアップ側の選択肢も同じ 4 種です（`setup.py:9584-9586`）。engine は `--kv` を解析して KV 形式を選び、値が不正なら `strata generate: --kv must be fp16, int8, q4_0 or k8v4` を stderr に出して終了コード 2 を返します（`src/program/generate.cpp:3357,4114-4127`）。
- engine 側の形式は FP16、INT8、回転 Q4_0、または K8V4（INT8 K + 回転 Q4_0 V）です。これらの形式選択は `KV` から渡された `--kv` が有効な場合の効果であり、KV streaming の有効化とは別です（`include/strata/core/layer.hpp:309-320`; `src/program/generate.cpp:4119-4127`）。

## 実行時の詳細

シェル起動中に一度だけ `${KV:-}` を展開し、非空なら引数リストへ値を追加します。entrypoint 内に `KV` の再読み込みやキャッシュ更新処理はありません（`docker/entrypoint.sh:26,190-195`）。起動した `strata launch` は preset を読み込んでから `--kv` を上書きし、選択された形式をセットアップに渡します。Docker の `launch` に渡す値は `--kv` CLI 引数なので、Strata が `KV` 環境変数を engine 内で直接読む実装ではありません（`strata_cli/launch/cmd.py:212-218,239-242`; `strata_cli/launch/runner.py:936-950`）。

無効な非空値は launch の引数検証で拒否され、起動は失敗します。entrypoint は launch の非ゼロ終了を受けると phase を `failed` にして、stderr に `strata launch stopped with code <終了コード> (the lines above say why). ...` を出して同じコードで終了します（`strata_cli/launch/cmd.py:37-45,95`; `docker/entrypoint.sh:285-292`）。entrypoint には `KV` 固有の警告・fallback はありません。

## 根拠

- Docker の値読み取り、空判定、`--kv` への転送: `docker/entrypoint.sh:1-7,53-56,169-195`。
- preset と CLI 引数の重ね合わせ、形式値の正規化・許可リスト: `strata_cli/launch/cmd.py:37-45,95,212-218,239-242`; `strata_cli/launch/settings.py:62`。
- 選択値のセットアップ引数への受け渡し、保存 preset の更新: `strata_cli/launch/runner.py:936-950`; `strata_cli/launch/cmd.py:307-309,993-997`; `strata_cli/launch/store.py:75-85`。
- engine の `--kv` 判定と形式設定、失敗文言: `src/program/generate.cpp:3357,4114-4127`; 形式の説明: `include/strata/core/layer.hpp:309-320`。
- setup 側の値域: `setup.py:9584-9586`。
