# `STRATA_DBG_FORCE_SLOW_LAYER`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA と SYCL の prompt MoE 経路にある fused-layout バッファの安全確認を、意図的に layer 0 で通すための診断用フックです。値が有効でも遅い expert 経路を実行する設定ではありません。fused 経路を layer 0 で使うはずの条件でも安全確認を失敗させ、エラーを返します。

## 値と判定

値の数値変換や文字列全体の比較はしません。環境変数の先頭文字が `1` かだけを判定します。

| 環境変数の値 | `force_slow` |
|---|---|
| 未設定 | `false` |
| 空文字 | `false`（先頭文字が `\0`） |
| 先頭文字が `1` | `true`（例: `1`, `10`, `1anything`） |
| それ以外 | `false`（例: `0`, `true`, ` 1`） |

判定結果は `Prefill::run_impl()` 内の関数ローカル `static const bool` に保存されます。そのプロセスの各 backend 実装で、MoE 分岐がこの文に初めて到達した時に読み取られ、以降の実行中に環境を変更しても再評価されません。

## 有効になる条件

環境変数を参照するのは CUDA 実装 `src/prefill/prefill.cpp` と SYCL 実装 `sycl/src/prefill/prefill.cpp` です。条件分岐において `force_slow` が結果を変えるには、次のすべてが必要です。

- `Prefill::run_impl()` が MoE 層の処理に進む。
- 現在の層番号 `l` が `0`。
- `m.fused_bufs` が真である。
- chunk の token 数 `T` が `stream_all_min()` 以上である。
- fused 経路の条件 `fused_l` が真であり、`STRATA_DBG_FORCE_SLOW_LAYER` の先頭文字が `1` である。

`fused_l` が偽なら同じ安全確認は設定値に関係なくエラーを返します。`m.fused_bufs` が偽、または `T < stream_all_min()` なら、このフックによるエラーは発生しません。CUDA/SYCL 共通のコードはありますが、実際にどの backend がビルドされ実行されるかはビルド構成によります。

## 実行時の詳細

fused-layout の `GU`, `H`, `Xq` バッファは `stream_all_min() - 1` token 相当の MMQ 用行数で確保されます。そのため、同じ大きな chunk で fused ではない expert 経路を通すと、これらの容量を超えて書き込み、違法アクセスや kernel 停止を招き得ます。各 backend は `(!fused_l || (force_slow && l == 0)) && m.fused_bufs && T >= stream_all_min()` を検出すると、expert 計算を続けず `err` に次の文字列を設定して `false` を返します。

```text
prefill: the fused layout's MoE buffers are too small for layer <layer>'s expert path at a chunk of <T> tokens
```

実際の文字列では層番号と chunk サイズが補間され、`<layer>` の直後に空白はなく、`'s` が続きます。`Prefill::run()` は `run_impl()` の `false` を呼び出し元へ返します。この箇所自体に `stderr` 出力はありません。フックが有効でも、layer 0 以外や小さい chunk の実行を遅い経路に切り替える動作はありません。

## 根拠

- `src/prefill/prefill.cpp:1016-1029`: fused-layout が `stream_all_min() - 1` token 分の行数を保持する説明とサイズ計算。
- `src/prefill/prefill.cpp:2040-2044`: 読み取り箇所を含む関数 `Prefill::run_impl()` の範囲。
- `src/prefill/prefill.cpp:2945-2974`: fused 経路の条件、安全確認、環境変数判定、エラー文字列と早期 return。
- `src/prefill/prefill.cpp:4181-4192`: `Prefill::run()` が `run_impl()` の失敗を返す処理。
- `sycl/src/prefill/prefill.cpp:889-904`: SYCL fused-layout のサイズ説明と計算。
- `sycl/src/prefill/prefill.cpp:3218-3246`: SYCL 側の同じ条件、判定、エラー処理。
- `docs/DETAILS.md:22-27`, `docs/STRIX_HALO.md:108-125`: fused prompt expert の説明はあるものの、この診断環境変数の具体的な説明は見つかりませんでした。
