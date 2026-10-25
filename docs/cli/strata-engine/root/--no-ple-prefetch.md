# `--no-ple-prefetch`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--no-ple-prefetch` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

PLE（Per-Layer Embedding）テーブルを読む前に行う OS のページ先読みヒントを無効にします。A/B 比較用のフラグで、PLE の値や推論結果を切り替えるものではありません。ソースコメントは、mapped table の16行をまとめて先読みする経路と、これを無効にして行単位で読む比較を説明しています（`src/program/generate.cpp:580-582,997-998`、`include/strata/kernels/ngram.hpp:228-239`）。

## 使い方

```sh
strata --native /path/to/model.gguf --ple-gguf /path/to/ple.gguf --no-ple-prefetch --tokens 1,2,3
```

モデルや PLE shard のパス、入力 token は手元のファイル・入力に置き換えます。`--native` 時はモデル shard から PLE shard を自動検出する経路もありますが、検出できない場合は起動に失敗します（`src/program/generate.cpp:3247-3261`）。

## 値と既定値

値を取りません。省略時は `Options::no_ple_prefetch` が `false` で、PLE の先読み設定は有効です。指定すると `true` になり、同じフラグを複数回指定しても同じ状態です。parser に値の validation はありません（`src/program/generate.cpp:580-582,2550-2553`）。

## 実行時の動作

引数 parser はこのフラグを `Options` に記録し、初期化後に `ple_prefetch_enable(false)` を呼びます。これはプロセス内の PLE テーブル実装が参照する共有フラグを false にします（`src/program/generate.cpp:2550-2553,6012`、`src/kernels/ngram.cpp:35-41`）。

効果があるのは mapped mode の OS 先読みヒントです。Windows の単一 token 読み出しでは、通常は16行分を1回の `PrefetchVirtualMemory` 呼び出しで要求する処理を省略し、後続の行読み出しに任せます（`src/kernels/ngram.cpp:496-520,639-681`）。バッチ読み出しでは Windows の `PrefetchVirtualMemory` と、非 Windows の `madvise(MADV_WILLNEED)` の両方を止めます（`src/kernels/ngram.cpp:538-617`）。ヒントが無効または OS に実行されなくても、後続の read が必要なページを読みます。先読み API の戻り値も利用していません（同: `601-608,664-681`）。

## 適用条件と副作用

- PLE テーブルを使う実行でのみ意味があります。通常の parser は `--ple-gguf` が必要で、`--no-ple` と `--ple-gguf` は併用不可です。`--no-ple` を指定した実行では PLE 自体が無効なため、このフラグの先読み効果もありません（`src/program/generate.cpp:3290-3299,4033-4036`）。
- `--native` のモデルが `qwen35moe` と判定される場合、通常 parser の前に `strata::qwen35::run` へ全引数を渡します。この別 parser には `--no-ple-prefetch` がありません。通常モードでは未知引数として usage を表示して終了コード 2 になり、`--serve` を先に解析した場合は未対応 option として警告してスキップされます（`src/program/generate.cpp:2393-2408`、`src/qwen35/q36_engine.cu:3742-3795`）。
- `--ple-io direct` は mapped mode ではなく `PleReader` の読み出し経路です。この direct 経路の `prefetch_rows` は reader の ticket を発行し、`g_ple_prefetch` を参照しません。そのため `--no-ple-prefetch` は direct I/O の reader 内部先読みを止めません（`src/kernels/ngram.cpp:425-434,496-505,538-581`）。
- 単一 token の mapped 読み出しでこの OS 先読み呼び出しを持つのは Windows の条件付きコードです。非 Windows では単一 token の `gather` は行を順に読みます。一方、mapped batch 読み出しでは非 Windows も `madvise` を使うため、このフラグが効きます（`src/kernels/ngram.cpp:602-608,639-681`）。
- データ値は変えず、先読み要求だけを変えます。性能差はストレージ、ページキャッシュ、OS に左右されるため、この調査では速度の向上・低下を断定しません。

## 出力とエラー

このフラグ固有の警告や成功メッセージはありません。引数 parser はこの値を拒否する追加検査を行いません。誤記など未認識の引数は `unknown argument: ...` と usage を stderr に出して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。

## 根拠

- parser の既定値、help 表示、受理箇所、反映箇所: `src/program/generate.cpp:580-582,997-998,2550-2553,6012`
- PLE 読み出しでの OS 先読みの有効条件・無効化箇所: `src/kernels/ngram.cpp:35-41,425-448,496-520,538-617,639-681`
- 共有設定の説明と A/B 比較の意図: `include/strata/kernels/ngram.hpp:228-239`
- SYCL 実装にも同名フラグの parser と反映箇所がある: `sycl/src/program/generate.cpp:558-560,898-899,1871,4476`
- 対象はソース checkout です。既存の同一 revision の CLI バイナリや Release artifact は照合していません。性能測定、build、テストは実施していません。
