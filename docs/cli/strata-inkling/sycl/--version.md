# `--version`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

SYCL 版 Inkling エンジンのバージョン文字列を表示して終了する。モデルの指定やロードをせずに、実行ファイルの識別に使える。

## 使い方

```sh
strata-inkling-sycl --version
```

## 値と既定値

値は不要で、既定値もない。parser は `--version` に別名を割り当てていない。

## 実行時の動作

引数走査中に `--version` を見つけると、その場で `strata-inkling 0.1.67` を出力して終了コード `0` で戻る。引数にこのオプションが含まれていれば、モデルなど別の引数を先に指定していても後続処理には進まず、これより後ろの引数も処理しない。

コマンド入口では引数走査より先に `ensure_l0_v1_default()` を呼び、未設定の場合は `UR_LOADER_USE_LEVEL_ZERO_V2=0` をプロセス環境に設定する。明示済みの値は上書きしない。`--version` の分岐はこの後にあるが、モデル読込や SYCL デバイス初期化には進まない。

## 適用条件と副作用

この文書の対象は `strata-inkling-sycl` の parser であり、CUDA/HIP 版や Metal 版の同名オプションとは別スコープである。SYCL サブターゲットは `STRATA_ENABLE_SYCL` が有効で SYCL の CMake 設定が存在するときに追加される。

観測できる副作用は、上記の環境変数が未設定の場合に現在のプロセス内で既定値を設定することと、標準出力への一行出力である。ファイルやネットワークへの処理はこの分岐にない。

## 出力とエラー

成功時の標準出力は次の一行で、末尾に改行が付く。

```text
strata-inkling 0.1.67
```

この分岐自体に値検証や失敗経路はなく、終了コードは `0`。モデル未指定時の usage 出力と終了コード `1` は、`--version` による早期終了が起きない場合の後続処理である。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-115` — `main` の冒頭で環境変数の既定化を行い、parser が値なしの `--version` を処理してバージョン文字列を出力し `0` を返す。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-183` — 早期終了しない場合のモデル必須チェックと、その後にモデルをロードする経路。
- `engine/src/inkling2/sycl/ink_sy_common.h:57-63,74-80` — 環境変数設定の実装と、`UR_LOADER_USE_LEVEL_ZERO_V2` が未設定の場合だけ `0` にする処理。
- `engine/src/inkling2/CMakeLists.txt:246-247` — SYCL サブターゲットを追加する条件。
- `docs/cli/README.md:1579-1599` — `strata-inkling-sycl` の tool ID・SYCL parser 所在・scope と、`sycl/--version` の索引リンク。
