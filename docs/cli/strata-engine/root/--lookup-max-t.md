# `--lookup-max-t`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--lookup-max-t` |
| 別名 | なし |
| 値 | 整数 `N`。必須。負数は0に補正され、正数は prompt-lookup window の幅として使われる |

## 役割

prompt lookup（過去の文脈にある一致箇所から候補 token を提案する処理）が使う verify window の最大幅を指定します。MTP drafter の幅は別に維持し、lookup 候補だけをより長い window で検証できるようにします。通常の8 token幅を超える窓は最大16 tokenまでで、build が16行窓を持つ場合もこの lookup 用上限は `kVerifyLongT` で制限されます（`src/program/generate.cpp:4140-4158,4170-4172`、`include/strata/kernels/verify_kernels.hpp:25-31`）。

## 使い方

```sh
strata --pack ./model.gguf --serve --mtp ./draft.gguf --spec 6 --suffix-draft 3 --lookup-max-t 12
```

`--suffix-draft` を有効にして serve する例です。`--lookup-max-t` の自動既定値もこの種の実行条件を見ますが、明示値を指定するとその自動判定を通らず、指定値が設定されます（`src/program/generate.cpp:3549-3552,4143-4158`）。

## 値と既定値

- 値は必須です。`Options` の初期値は `-1`（未指定）で、明示値は `std::atoi()` で読み、`std::max(0, ...)` により負数を0にします。整数として読めない文字列も `atoi` の結果が0となります。厳密な数値形式 validation はありません。引数を複数回指定した場合は、後の値が前の値を置き換えます（`src/program/generate.cpp:972-977,3551`）。
- 未指定時は `default_lookup_max_t()` が条件を判定します。既定値12になるのは、ビルドの verify 窓が narrow（`kVerifyMaxT == kVerifyNarrowT`）、Metal ではない、serve、単一GPU、layer split なし、`--batch` が1以下、DFlash2 なし、`--lookup-chain` なし、suffix draft 有効、`--spec >= 2`、かつ `STRATA_LOOKUP_MAX_T` が先頭 `0` ではない場合です。どれか一つでも外れると0です（`src/program/generate.cpp:4143-4154`、`include/strata/core/lookup_default.hpp:9-27`）。
- `STRATA_LOOKUP_MAX_T` は未指定時の自動値を抑止する用途です。値の先頭文字が `0` なら自動値を0にし、それ以外の値は自動で有効化するものではありません。CLI で `--lookup-max-t` を明示すると環境変数判定は行われません（`src/program/generate.cpp:4143-4155`）。詳細は [`STRATA_LOOKUP_MAX_T`](../../../envvars/STRATA_LOOKUP_MAX_T.md) を参照してください。
- `N=0` は lookup の長い窓を無効にします。上限の明示 validation は parser にありませんが、実際に利用できるのは `kVerifyLongT` までです。narrow build では `kVerifyMaxT` が8のため `kVerifyLongT` は16です。wide build では `kVerifyLongT` はその build の `kVerifyMaxT` です（`include/strata/kernels/verify_kernels.hpp:25-31`）。
- 値を省略すると parser の `next()` が `--lookup-max-t needs a value` を stderr に出して終了コード2で終了します（`src/program/generate.cpp:3293-3298,3551`）。

## 実行時の動作

値が正で suffix draft が有効かつ `--spec >= 2` の場合、初期化時に必要なら `--spec` を `N` 以下・`kVerifyLongT` 以下まで広げ、MTP 上限を元の `--spec` に保ちます。したがって MTP が提案する幅を `N` にする指定ではありません（`src/program/generate.cpp:4133-4159`）。suffix draft が無効の場合、この拡張処理は働かず、lookup サイズ候補の設定だけでは suffix lookup を起動しません（`src/program/generate.cpp:4156-4159,20031-20040`）。

正の値では、draft policy の許可サイズに MTP 側のサイズと lookup 側のサイズを設定します。`--lookup-sizes` が未指定なら MTP 上限より1つ・2つ大きい幅と `--spec` が追加候補です。明示されている場合はカンマ区切りを `atoi` で読み、2以上 `--spec` 以下の値だけを追加します。`--lookup-sizes` 自体に不正形式のエラーはなく、不適合な値は候補から外れます（`src/program/generate.cpp:1300-1321`）。

serve では起動時に stderr へ上限・MTP 幅・許可 window サイズを表示します。各サイズは個別の window graph として準備されます。VRAM 不足で graph を作れないサイズは policy から恒久的に除外され、小さい候補へ進みます。VRAM 以外の graph 準備エラーは fallback せず、呼び出し側のエラー経路へ進みます。prompt の分割処理と decode の lookup 候補の双方で、選択サイズに対してこの準備確認を行います（`src/program/generate.cpp:13417-13437,16237-16243,18233-18252`）。

## 適用条件と副作用

- 自動値12の対象は上記条件をすべて満たす serve 実行に限られます。明示値は自動判定を迂回しますが、実際の幅は backend/build、draft 使用条件、layer split のバッファ制約に従います（`src/program/generate.cpp:4143-4158,10857-10863`）。
- layer split では verify hand-off の幅に合わせて `--spec` を narrow 幅へ下げるログを stderr に出し、lookup policy の許可サイズも narrow 幅までに制限します（`src/program/generate.cpp:10857-10863,13417-13422`）。batch は自動値12の条件から除外されています（`src/program/generate.cpp:4146-4150`）。pipeline window の設定は MTP drafter の load 幅にも影響します（`src/program/generate.cpp:6759-6763`）。
- 追加される window サイズごとに graph を準備するため、VRAM を消費します。ソースコメントは各 graph を約20–35 MiB と記していますが、実使用量はモデル・build 等に依存し、ここでは測定していません（`src/program/generate.cpp:972-976,13423-13435`）。
- 値は起動時の設定処理で決まり、要求ごとに再読込する処理は確認できません。このオプション固有のファイル書き込みやネットワーク処理も確認できません。

## 出力とエラー

- serve で値が正なら、設定された上限とサイズ一覧を stderr に出します。graph の VRAM 不足時はサイズを除外した旨と残り候補を stderr に出し、より小さいサイズを試します（`src/program/generate.cpp:13420-13437`）。
- graph 準備時に VRAM 以外のエラーが起きた場合、prompt 経路は失敗を返し、decode 経路は `ERR ...` を stdout に出してその処理を終了します（`src/program/generate.cpp:13426-13437,16240-16243,18237-18252`）。
- 未知の引数は stderr に `unknown argument` と usage を出し、終了コード2です（`src/program/generate.cpp:3683-3688`）。このオプションには専用の値範囲拒否処理はありません。

## 根拠と調査範囲

- parser、初期値、値変換: `src/program/generate.cpp:972-977,3293-3298,3551`。
- 自動既定値と条件: `src/program/generate.cpp:4140-4158`、`include/strata/core/lookup_default.hpp:9-27`。
- 候補サイズと幅上限: `src/program/generate.cpp:1300-1321,4168-4175`、`include/strata/kernels/verify_kernels.hpp:25-31`。
- serve での graph 準備・VRAM fallback・prompt/decode への適用: `src/program/generate.cpp:13417-13437,16237-16243,18233-18252`。
- 索引上の scope は `strata-engine` の `strata` エンジン root 引数です（`docs/cli/README.md:1223-1231,1296-1300`）。
- 同一 revision のソース parser と使用箇所を確認しました。ビルド済み CLI の help 実行、Release artifact の確認、build、GPU 実行、性能測定、テストは行っていません。`src/program/generate.cpp` の parser が共通で受理する点を確認しましたが、全 backend/build での実行結果は検証していません。
