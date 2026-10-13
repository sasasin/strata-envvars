# `GPU_MAX_HW_QUEUES`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。

## 役割

調査対象の Strata ソースでは、この変数は HIP 版 verifier のトレース開始ログに現在の環境値を表示するためだけに読み取られる。Strata は値を解釈してキュー数を設定したり、処理を分岐したりしない。GPU ランタイムがこの変数をどう扱うかは、Strata のコードからは確認できず、本書の説明対象外。

## 値と判定

| 環境値 | Strata の表示 |
| --- | --- |
| 未設定 | `-` |
| 設定済み（空文字を含む） | 値をそのまま表示。空文字は空欄になる |

数値変換、真偽値判定、範囲検査、既定キュー数への fallback はない。`std::getenv` が返す文字列をそのまま `fprintf` に渡す。

## 有効になる条件

表示ブロックは `STRATA_VERIFY_TRACE` が有効で、verifier の trace buffer がまだ割り当てられていない場合に実行される。`STRATA_VERIFY_TRACE` 自体は共通 `env_on` 関数で判定され、未設定または空文字、先頭文字が `0` の値では無効、それ以外では有効となる。

`GPU_MAX_HW_QUEUES` の表示は `STRATA_USE_HIP` のコンパイル条件内にある。HIP 以外のビルドでは同じ trace 開始ログに `strata verify trace (#649): on` だけが出て、この変数は読み取られない。CUDA/HIP 共通の verifier 初期化コードにログ位置はあるが、GPU_MAX_HW_QUEUES を参照する部分は HIP 条件付き。

## 実行時の詳細

プロセス起動時に `g_trace` が初期化される。HIP の verifier が arena を準備した後、trace が有効で `trace_h_ == nullptr` の場合に stderr へ次の形式で出力する（HIP 側 `verify.cpp` の両実装で同じ形式）。

```text
strata verify trace (#649): on; coherent words <explicit|default>, doorbell <stored|incremented>, HIP_HOST_COHERENT=<値|-> HSA_ENABLE_SDMA=<値|-> GPU_MAX_HW_QUEUES=<値|->
```

`GPU_MAX_HW_QUEUES` はこのログ行を作る時点で `getenv` により取得される。設定値の変更、他プロセスへの転送、子プロセスへの上書きは Strata のこの読み取り箇所では行わない。trace が無効なら、この変数を表示する処理も走らない。

## 根拠

- `src/core/verify.cpp:169-180` — HIP 向けトレース機能の説明、`env_on` 判定、`g_trace` の初期化。
- `src/core/verify.cpp:694-709` — trace buffer 準備時の条件と HIP/non-HIP のログ分岐。HIP 条件内で `GPU_MAX_HW_QUEUES` を `getenv` し、未設定なら `-`、設定済みなら値を直接出力する。
- `sycl/src/core/verify.cpp:89-100,620-634` — SYCL 側にも同じトレース判定と HIP 条件付き表示がある。

`docs/` 以下にこの変数の Strata 側の読み取りや動作を補足する説明は見つからなかった。コード上で確認できたのは診断ログへの表示のみである。
