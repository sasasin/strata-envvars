# `--no-coupled-draft`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25）。調査対象 checkout は `main...origin/main` で、未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（ネイティブ `strata` 推論エンジンの root option） |
| オプション | `--no-coupled-draft` |
| 別名 | なし。反対の状態を指定する option は `--coupled-draft` |
| 値 | 値を取らないフラグ |

## 役割

MTP drafter の sampled request に対する coupled draft sampling を無効にし、draft を argmax で提案する状態にします。MTP 自体や speculative decoding を有効にする指定ではありません。help 文字列も「disable coupled draft sampling (propose argmax drafts)」と説明しています（`src/program/generate.cpp:1058-1059`）。

## 使い方

```sh
strata generate --pack ./model-pack --tokens "1,2,3" --mtp ./model-mtp --spec 4 --no-coupled-draft
```

`--no-coupled-draft` は値を受け取りません。例では MTP drafter を使う speculative decoding の実行で coupled sampling を抑止します。`--mtp` が指定されていない場合、parser はこのフラグを受理しますが、MTP draft の処理は行われません（`src/program/generate.cpp:16143-16146,16168-16169`）。

## 値と既定値

parser はこのフラグを見つけると `Options::coupled_draft` を `false` にします。値の変換や追加 validation はありません（`src/program/generate.cpp:535,2550-2554`）。未指定時の初期値は `coupled_draft_env()` の結果です。同 helper は `STRATA_SPEC_COUPLED` と `STRATA_SPEC_PROB` のいずれかが有効なら true を返します。各変数は未設定、空、または文字列 `0` なら false、それ以外の空でない値なら true です。引数処理後の値を共有状態へ設定します（`include/strata/core/coupled_draft.hpp:57-63,65-83`; `src/program/generate.cpp:2892`）。

`--coupled-draft` と `--no-coupled-draft` を両方指定した場合は、引数列を処理する順に同じ状態を書き換えるため、最後に現れた方が CLI 状態を決めます（`src/program/generate.cpp:2552-2553`）。

## 実行時の動作と適用条件

MTP が使われる speculative decoding 経路では、draft sampling の設定が MTP drafter に渡されます（`src/program/generate.cpp:16143-16146,16168-16169`）。coupled setup が有効でないとき、draft head の各行は argmax 経路へ進みます（`src/core/mtp.cpp:1199-1218`）。したがって、このフラグの効果が現れるのは MTP draft が実際に使われる場合です。

このフラグを指定しても、別環境変数 `STRATA_SPEC_PROB` が有効なら probabilistic draft sampling の setup は有効になります。CUDA/HIP 側 helper は `STRATA_SPEC_COUPLED` 状態と `STRATA_SPEC_PROB` の論理和を setup 条件にし、probabilistic sampling を coupled sampling と別分岐で実行します（`include/strata/core/coupled_draft.hpp:65-79`; `src/core/mtp.cpp:553-555,574-577,599-605,1199-1209`）。

## 副作用、出力、失敗経路

このフラグ単独では buffer を確保せず、ログも出しません。coupled または probabilistic setup が有効なときは、MTP bind 中に sampler parameter、penalty ring、scratch などの GPU buffer と mapped host buffer を確保します。draft vocabulary subset がある場合は token map も GPU に確保し、setup 完了時に stderr へ有効化ログを出します（`src/core/mtp.cpp:558-606,746`）。

それらの buffer、token map、同期処理の確保・実行に失敗すると MTP bind が失敗し、`strata generate: <error>` を stderr に出して終了コード 1 となります（`src/core/mtp.cpp:567-597,746`; `src/program/generate.cpp:16143-16146`）。coupled sampler が処理できる幅を超えた場合は setup をエラーにせず、stderr に警告して argmax draft に戻ります（`src/core/mtp.cpp:560-565`）。

## 根拠

- 索引上の tool ID、root scope、リンク: [`docs/cli/README.md`](../../README.md) の `strata-engine` 項目と `--no-coupled-draft`（1224 行）。配置・調査基準: [`001_investigation.md`](../../001_investigation.md)。
- parser の option 宣言と隣接 option、help、環境初期値、状態反映: `src/program/generate.cpp:535,1058-1059,2552-2554,2892`。
- 環境変数の既定値と probabilistic mode との合成: `include/strata/core/coupled_draft.hpp:57-83`。
- MTP の bind/setup、allocation・fallback・stderr ログ: `src/core/mtp.cpp:553-606,609-614,746`。
- coupled/probabilistic/argmax の draft 分岐: `src/core/mtp.cpp:1199-1218`。実行側から MTP bind と sampler 設定を行う箇所: `src/program/generate.cpp:16143-16146,16168-16169`。

調査範囲は指定 revision の索引対象である CMake 生成 native engine の `src/program/generate.cpp` parser と CUDA/HIP MTP 実装です。別の `sycl/src/program/generate.cpp` / `sycl/include/strata/core/coupled_draft.hpp` にも同名フラグがありますが、SYCL 実装の runtime 差はこのページの対象に含めていません。ビルド生成バイナリ、GPU 実行、Release artifact の挙動は確認していません。
