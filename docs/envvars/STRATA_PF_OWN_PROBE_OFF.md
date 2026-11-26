# `STRATA_PF_OWN_PROBE_OFF`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

HIP ビルドで、統合 GPU 上の大きな prefill chunk と、cache slot を借りずに確保した prompt path buffer が同居できるかを確認する起動時 probe を無効にする。通常は prompt path の初期化後、64 MiB の確保・stream 作成・fill・同期を試す。probe が失敗すると、prefill を始める前に理由を stderr に出してプロセスを終了する。この変数が設定されていれば probe を省略し、その失敗による終了を避ける代わりに、この probe による事前確認は行わない。生成 token や chunk の選択自体をこの変数が変更する処理はない。

実装は `engine/src/program/generate.cpp` の `uma_refuse_chunk_if_full` と `uma_launch_probe`。通常生成と serve の prompt path 初期化後に呼ばれる（同ファイル 24118-24124、13101-13142）。

## 値と判定

`std::getenv(...) != nullptr` という設定有無だけで判定する。値の文字列は parse・比較しないため、空文字列を含め、何らかの値が設定されていれば probe をスキップする。未設定なら、以下の他条件を満たした場合に probe が実行される。数値や真偽値としての境界・無効値判定はない（`engine/src/program/generate.cpp:2204`）。

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| HIP build、統合 GPU、chunk > 16384、cache slot を借りない | probe を実行 | `1`、`0`、`false`、空文字列（いずれも設定済みなので probe を抑止） | 該当なし。文字列内容の判定なし |
| HIP 以外 | probe 関数は何もしない | 同上 | 該当なし |
| chunk <= 16384、cache slot を借りる、または discrete GPU | この変数に関係なく probe を実行しない | 同上 | 該当なし |

## 有効になる条件

- probe 本体は `STRATA_USE_HIP` が定義された build に限られる。非 HIP build では関数は引数を使わず return する（`engine/src/program/generate.cpp:2199-2204`）。
- HIP build でも、prompt chunk が 16384 以下、prompt path が cache slot を借りている、または `spill_discrete_gpu()` が true の場合は probe を呼ばない（`engine/src/program/generate.cpp:2204`）。`spill_discrete_gpu()` は統合 GPU を除く discrete GPU を true とする（`engine/src/program/generate.cpp:326-338`; `engine/include/strata/core/spill_gate.hpp:2-14`）。
- 上記を通過し、かつ変数が未設定の場合に限って probe する。コメントでは統合 GPU のうち Strix Halo を挙げており、対象条件を満たす他の統合 GPU にもコード上は適用される（`engine/src/program/generate.cpp:2194-2204`）。
- 通常生成では prompt が複数 token で prefill chunk が正のときの prompt path を初期化した後、prompt の prefill 実行前に判定する。serve では prompt path の初期化を終えた後に判定する（`engine/src/program/generate.cpp:23989-23990, 24118-24125, 13101-13142`）。
- CLI 引数や別環境変数がこの環境変数の判定値を上書きする処理はない。chunk と借用状態は CLI や他設定等を反映した後の実値として判定に渡される。

## 実行時の詳細

環境変数は `uma_refuse_chunk_if_full` の呼び出しごとに直接 `std::getenv` され、関数内や static には cache されない（`engine/src/program/generate.cpp:2199-2204`）。通常生成は prompt path の `init` 成功後、prefill の実行前に一度確認する。serve も初期 prompt path の `init` 後に確認する。

probe は先に CUDA/HIP の last error を消費し、64 MiB を `cudaMalloc` する。続いて non-blocking stream を作り、64 MiB をゼロ埋めして stream を同期し、最後の error 状態も確認する。stream があれば破棄し、確保した領域を解放する。allocation、stream 作成、launch/sync/error 確認のいずれかが失敗した場合は、chunk を小さくして再試行せず、stderr に理由を含む行を出し、flush 後に `_Exit(2)` でプロセスを終了する（`engine/src/program/generate.cpp:2175-2191, 2205-2215`）。

## ログと測定値

probe 成功時は、さらに `STRATA_TRACE` が設定されている場合に限り、stderr に `strata trace: the launch probe passed with a %lld-token chunk` を出す（`engine/src/program/generate.cpp:2206-2208`）。失敗時は次の形式で stderr に出力し、flush して終了コード 2 でプロセスを終了する。`%s` には probe が設定した理由が入る（同 2181-2186, 2210-2214）。

```text
strata generate: a %lld-token prompt chunk does not fit beside the %.1f GiB expert cache on this GPU (%s): use --prefill auto:%lld, or a smaller --expert-cache
```

理由文字列は `a 64 MiB allocation failed`、`a stream could not be created`、または `a launch failed`（memset・同期・error 確認を含む失敗）である。probe 成功時も失敗時も、この環境変数自体の値を表示するログはない。対象コード・関連資料に、この probe の性能測定値は見つからなかった。

## 根拠

- `engine/src/program/generate.cpp:2175-2191` — probe の確保、stream、fill/sync、cleanup と失敗理由。
- `engine/src/program/generate.cpp:2194-2215` — 実行条件、環境変数の設定有無判定、成功時 trace、失敗時終了。
- `engine/src/program/generate.cpp:23989-24125` — 通常生成での prompt path 初期化と probe 呼び出し。
- `engine/src/program/generate.cpp:13101-13142` — serve での prompt path 初期化後の呼び出し。
- `engine/src/program/generate.cpp:326-338`、`engine/include/strata/core/spill_gate.hpp:2-14` — discrete / integrated GPU の spill 判定。
