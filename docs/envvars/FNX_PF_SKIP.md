# `FNX_PF_SKIP`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この変数は Flash-Next の prefill を制御しません。`strata-split` の Flash-Next Engine は、27B 用設定である `FNX_PF_SKIP` が設定されていたら、誤設定として起動を拒否します。値を読み取って動作を切り替える機能ではありません。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | この検査では拒否しない |
| 設定あり（空文字を含む） | Engine 構築時に例外を送出 |

文字列の変換、数値判定、許容値の範囲はありません。`std::getenv(k)` の非 null 判定だけなので、`FNX_PF_SKIP=0` や空文字でも拒否されます。CLI 引数による上書きや別の環境変数との優先順位はありません。

## 有効になる条件

検査は `STRATA_BUILD_SPLIT` によって作られる `strata-split-*` Engine のコンストラクタで行われます。このターゲットは Linux CUDA または HIP 向けで、`FNX_27B=0` としてビルドされます。`strata-split` は既定ではビルドされません。対象ターゲットの構成と条件は `src/split/CMakeLists.txt:1-5,20-30,64-79,92-114` にあります。

`FNX_PF_SKIP` を設定したまま Engine 構築まで進むと拒否されます。`sfnx` は `--serve` で動くサーバープロセスで、モデルと MTP の構築後、Engine を作る箇所でこの検査に到達します。サーバー用 CLI 引数でこの検査を無効化する経路はありません（`src/split/tools/sfnx.cpp:72-104,1055-1062`）。

## 実行時の詳細

`Engine::Engine` は `FNX_PF_SKIP` を含む27B向け設定名の配列を走査し、各名前を `std::getenv` に渡します。値が存在すれば、設定名を含む `std::runtime_error` を送出します。従って未設定なら通常どおり続行し、設定済みならこの Engine で設定を使った prefill skip は実行されません。検査は Engine 構築時に一度行われ、リクエストごとの再読込や cache はありません（`src/split/src/engine.cu:31-36`）。

`sfnx` の起動経路はこの例外を `fail()` に渡し、stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します。`_Exit(1)` で即時終了します（`src/split/tools/sfnx.cpp:58-63,1027-1035,1055-1062`）。この場合、たとえば `FNX_PF_SKIP=0` なら理由は `FNX_PF_SKIP is the 27B's: Flash-Next has nothing it sets` です。

## 根拠

- `src/split/src/engine.cu:31-36` — Engine コンストラクタでの全名走査、設定有無の判定、例外文。
- `src/split/tools/sfnx.cpp:1055-1062` — モデルと MTP の後に Engine を構築し、例外を `fail()` に渡す。
- `src/split/tools/sfnx.cpp:58-63,1027-1035` — stdout/stderr への通知と終了コード 1。
- `src/split/CMakeLists.txt:1-5,20-30,64-79,92-114` — 対象バイナリのビルド条件と `FNX_27B=0`。
