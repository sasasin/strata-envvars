# `--no-kv-grow`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、root scope） |
| オプション | `--no-kv-grow` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

QSA の K/V プールをコンテキストの使用量に応じて拡張する elastic K/V を無効にします。CUDA/HIP 系と SYCL 系の両 parser がこのフラグを受理します。

## 使い方

```sh
strata --no-kv-grow --model model.gguf --tokens-file prompt.txt
```

## 値と既定値

値は不要です。`Options::kv_grow` の初期値は `false` なので、他の指定がなければ elastic K/V は要求されません（`engine/src/program/generate.cpp:826`、`engine/sycl/src/program/generate.cpp:510`）。parser は `--no-kv-grow` を受けると同じ値を `false` に設定します（`engine/src/program/generate.cpp:3908-3909`、`engine/sycl/src/program/generate.cpp:1947-1948`）。

同じコマンドラインで `--kv-grow` と併用した場合は、parser が順に引数を処理するため後に現れた方が `kv_grow` の値になります。フラグ自体に値検証はありません。値を取らないので、続けて書かれた余分な引数は別引数として解析され、未知の引数なら stderr に `unknown argument: ...` と usage を出して終了コード 2 になります（`engine/src/program/generate.cpp:3842-3849, 3908-3909, 4268-4273`）。

ただし、実行時の `STRATA_KV_GROW` が空でない場合は環境変数がコマンドライン設定に優先します。先頭文字が `0` なら無効、それ以外なら有効として扱われるため、`STRATA_KV_GROW=1` の環境では `--no-kv-grow` を指定しても有効要求になります。未設定または空文字の場合に限り、コマンドラインの値が使われます（`engine/src/program/generate.cpp:7718-7726`、`engine/sycl/src/program/generate.cpp:4285-4293`）。

## 実行時の動作

elastic K/V は、単一 GPU、非ストリーミング（`--kv-resident` が 0 以下）、expert profile の指定、CPU 側 expert 配置の無効、expert cache が有効、remote expert cache がない、VMM が利用可能、`--batch` が 0、`--vram-elastic` が無効、`--peer-device` が未指定という条件でのみ有効になります。条件を満たさない場合は elastic K/V を無効にします（`engine/src/program/generate.cpp:7718-7729`、`engine/sycl/src/program/generate.cpp:4285-4296`）。

`--no-kv-grow` が有効に働き、かつ K/V streaming も使わない場合、QSA の K/V プールは elastic 用の別 VMM range ではなく通常の session state 側に含まれます。通常の K/V 配列のサイズ計上と初期化は `engine/src/core/layer.cpp:788-804, 807-864` および `engine/sycl/src/core/layer.cpp:758-775, 777-835` にあります。従って、K/V の割当方式は起動時に決まり、このフラグは elastic K/V の初期化より前に評価されます。

環境変数による上書きがなく、他条件を満たして `--kv-grow` が要求された場合でも、適用条件を満たさなければ stderr に `strata generate: --kv-grow is off (...)` と警告を出して無効化します。条件を満たす場合は初期化時に elastic K/V と expert cache の VMM を有効化します（`engine/src/program/generate.cpp:7727-7732`、`engine/sycl/src/program/generate.cpp:4294-4299`）。無効時に特有の警告やエラーはありません。

## 適用条件と副作用

`STRATA_KV_GROW=1` などの環境変数が明示されると、このフラグ単独では無効化を保証できません。逆に `STRATA_KV_GROW=0` は `--kv-grow` の要求を無効にします。さらに、長い context の事前メモリ計画には `o.kv_grow` を直接参照する分岐があり、`STRATA_KV_GROW` による上書き後の実効値とは別の判定になります（`engine/src/program/generate.cpp:4240-4242, 7718-7726`）。

起動時の session state 割当に失敗すると `strata generate: session state allocation failed` を stderr に出し、終了コード 1 で終了します（`engine/src/program/generate.cpp:7734-7736`）。この失敗経路はフラグ固有の validation ではなく、割当処理の結果です。VMM の確保や GPU backend 固有の詳細な失敗挙動は、ここでは CLI フラグの影響として一般化しません。

## 根拠

- `engine/src/program/generate.cpp:826, 3908-3909` — CUDA/HIP 系 `Options` の既定値と parser 定義。
- `engine/sycl/src/program/generate.cpp:510, 1947-1948` — SYCL 系の既定値と parser 定義。
- `engine/src/program/generate.cpp:7718-7736`、`engine/sycl/src/program/generate.cpp:4285-4305` — 環境変数の優先、適用条件、警告、elastic 設定、session state 割当。
- `engine/src/core/layer.cpp:788-804, 807-864`、`engine/sycl/src/core/layer.cpp:758-775, 777-835` — elastic 無効時の通常 K/V 配列計上と、elastic 有効時の VMM pool 初期化。
- `engine/src/program/generate.cpp:4240-4242` — `o.kv_grow` を使う長い context のメモリ計画分岐。
