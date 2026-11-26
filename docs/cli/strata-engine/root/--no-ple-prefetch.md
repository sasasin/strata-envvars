# `strata --no-ple-prefetch`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンのトップレベル引数） |
| オプション | `--no-ple-prefetch` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

PLE（n-gram）テーブルをメモリマップで読むときの OS 先読みヒントを止める A/B 用フラグです。既定では PLE の読み出し前に必要な行をまとめて先読みする設定が有効です。このフラグを付けると、そのヒントを無効にし、後続の行読み出しにページフォールトを任せます。エンジンの CUDA/HIP 系と SYCL 系の parser の両方に定義されています（`engine/src/program/generate.cpp:927,3977`、`engine/sycl/src/program/generate.cpp:599,1995`）。

## 使い方

```sh
# mmap 読み込みとの A/B 比較用に、PLE の先読みヒントを止めて実行する
strata --pack ./pack --tokens "1,2,3" --ple-gguf ./ple.gguf --ple-io mmap --no-ple-prefetch
```

この例はエンジンの usage が示す `--pack` と `--tokens` の入力形式に、PLE shard と mmap 読み込みを指定しています（`engine/src/program/generate.cpp:1208-1224`）。実際のモデルやトークン列に合わせて入力を置き換えてください。

## 値と既定値

値は不要です。parser は引数文字列との一致だけで `no_ple_prefetch` を `true` にし、値の変換・範囲検証はしません（`engine/src/program/generate.cpp:3977`、`engine/sycl/src/program/generate.cpp:1995`）。未指定時の option 値は `false` です（`engine/src/program/generate.cpp:927`、`engine/sycl/src/program/generate.cpp:599`）。同じフラグを重複して指定しても同じ `true` の設定になります。フラグに余分な値を続けると、その値は別の引数として解析され、未知の引数なら usage を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274`）。

## 実行時の動作

parser 後、CPU pool の構築時にこの設定が真なら `ple_prefetch_enable(false)` を呼びます（`engine/src/program/generate.cpp:9043`、SYCL: `engine/sycl/src/program/generate.cpp:4822`）。先読みスイッチの初期値は `true` です（`engine/src/kernels/ngram.cpp:43-49`）。メモリマップ経路では、Windows の `PrefetchVirtualMemory` 呼び出しと、その他のプラットフォームでの `madvise(..., MADV_WILLNEED)` の双方がこのスイッチを条件にしています。無効時はそれらのヒントを出さず、後続の行読み出しが必要なページを読み込みます（`engine/src/kernels/ngram.cpp:737-762,907-924`）。ヒントの呼び出し自体は値を変えない best-effort の処理として実装されています。

`--ple-io direct` は別経路です。Direct モードでは `prefetch_rows` が reader に読み出しを発行して早期 return するため、このフラグの有効・無効を確認する分岐を通りません（`engine/src/kernels/ngram.cpp:558-581`）。したがって Direct I/O の読み出し動作はこのオプションでは切り替わりません。`--ple-io` の既定値は `direct` です（`engine/src/program/generate.cpp:818`）。効果を比較する場合は、例のように mmap 経路を選ぶ必要があります。

## 適用条件と副作用

- メモリマップされた PLE テーブルの先読みヒントを無効化します。Direct reader の発行・完了制御、テーブル内容、行のデコード方法はこのフラグでは変更しません（`engine/src/kernels/ngram.cpp:558-581,907-924`）。
- 既定の `direct` I/O では先読みスイッチの判定箇所に到達しないため、通常は `--ple-io mmap` などのマップ経路と組み合わせたときに差が出ます（`engine/src/program/generate.cpp:818`、`engine/src/kernels/ngram.cpp:558-581`）。
- 先読みヒントの停止によりページ読み込みのタイミングは変わりますが、ソースはヒントが取得できない場合も実読み出しでページフォールトすると説明しています。性能差は実機測定なしには判断できません（`engine/src/kernels/ngram.cpp:737-762,904-906`）。

## 出力とエラー

このフラグ固有のログ出力や検証エラーは確認できませんでした。未知の引数は `unknown argument: ...` と usage を stderr に出し、終了コード 2 になります（`engine/src/program/generate.cpp:4268-4274`）。

## 根拠

- `engine/src/program/generate.cpp:925-927,1414-1415,3977,9043` — CUDA/HIP 系の option 初期値、help 表示、parser、実行時のスイッチ切り替え。
- `engine/sycl/src/program/generate.cpp:597-599,971-972,1995,4822` — SYCL 系の同じ option 定義と切り替え。
- `engine/src/kernels/ngram.cpp:43-49,558-581,737-762,907-924` — スイッチの初期値、Direct と mmap の分岐、および OS ごとのマップ先読み処理。
- `engine/src/program/generate.cpp:818,1208-1224,4268-4274` — `--ple-io` の既定値、エンジンの入力例・PLE 読み込みモード、未知引数の失敗経路。
