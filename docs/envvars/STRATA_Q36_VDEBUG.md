# `STRATA_Q36_VDEBUG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 エンジンの検証実行で、新旧 Q8_1 量子化画像に不一致があったとき、最初の不一致ブロックの詳細を追加で stderr に出す診断スイッチです。量子化結果やカーネル選択は変えません。`verify_q8` が照合した後、実行時にこの変数が設定されていて、今回の照合で不一致が増え、同じ照合名の不一致が 2 回以下の場合だけ診断処理へ進みます（`engine/src/qwen35/q36_engine.cu:2461-2495`）。

## 値と判定

`std::getenv("STRATA_Q36_VDEBUG")` の null 判定だけで、値の変換・文字列比較・数値検査はありません。値が設定されていること（空文字も含む）が条件です（`engine/src/qwen35/q36_engine.cu:2468`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `verify_q8` が呼ばれたとき | この追加診断は無効 | `1`、`0`、`true`、`false`、空文字、`0anything` など、環境に存在する任意の値 | なし。環境に存在しない場合のみ無効 |

大文字小文字、前後の空白、数値としての妥当性は調べません。CLI 引数や別の設定値でこの判定を上書きする処理もありません。なお、この変数だけでは検証を開始しません。検証の有効条件は次節のとおりです。

## 有効になる条件

- `STRATA_Q36_VERIFY` が `Engine` 構築時に設定され、`verify_k` が有効である必要があります。こちらも `getenv != nullptr` の判定で、未設定なら照合処理自体が無効です（`engine/src/qwen35/q36_engine.cu:2405-2408`）。
- Qwen3.6（GGUF architecture `qwen35moe`）のエンジン経路である必要があります。`strata` はモデルヘッダーの family 判定でこの経路へ切り替え、単独の `strata-q36` も同じエンジンを使います（`engine/src/program/generate.cpp:3804-3818`、`engine/cmake/strata_gpu_engine.cmake:565-584`）。
- Qwen3.6 エンジンのビルド対象が必要です。CMake は gfx906 を除外し、CUDA/HIP エンジン構成で `strata_qwen35` を追加します（`engine/cmake/strata_gpu_engine.cmake:565-584`）。
- 対象となる `verify_q8` 呼び出しで、新旧 Q8_1 画像にバイト不一致が必要です。現在の呼び出しは `add_rms q8` と `moe_out q8` で、前者は `fast_k` かつ `T <= 8` の経路、後者は小型 MoE 出力経路の検証時です（`engine/src/qwen35/q36_engine.cu:2505-2523`、`2667-2691`）。不一致がなければ `STRATA_Q36_VDEBUG` が設定されていても追加ログは出ません。
- 同じ `what` 名について、不一致回数が 2 以下である必要があります。`verify_cmp` が不一致ごとに `v_by[what]` を増やし、通常の VERIFY 不一致行は最大 3 回、VDEBUG 詳細行は最大 2 回に抑えます（`engine/src/qwen35/q36_engine.cu:2411-2424`、`2466-2493`）。

## 実行時の詳細

`STRATA_Q36_VDEBUG` は起動時にキャッシュされません。`verify_q8` が不一致を検出した後に毎回 `getenv` で確認します。一方、検証自体を制御する `verify_k` は `Engine` のメンバー初期化時に `STRATA_Q36_VERIFY` を一度読み、その後その値を使います（`engine/src/qwen35/q36_engine.cu:2405-2408`、`2461-2468`）。通常の CLI 解析に `STRATA_Q36_VDEBUG` 用の引数はありません（`engine/src/qwen35/q36_engine.cu:5339-5418`）。

検証時、`verify_q8` は `hsrc` を native Q8_1 量子化して `vq` に置き、カーネル側で作成済みの `xq` と `verify_cmp` で比較します。不一致かつ VDEBUG 条件を満たす場合、両画像と元の `hsrc` をホストへコピーし、36 バイト単位で最初に違うブロックを探して、そのブロックの scale bits、量子化 bytes の一致状況、CPU 側 butterfly sum と half bits を stderr に出します（`engine/src/qwen35/q36_engine.cu:2461-2494`）。この処理は原因調査用で、比較対象の画像を修正したり、推論出力を差し替えたりしません。

## ログと測定値

不一致時には、まず `verify_cmp` が次の形式で stderr に不一致を記録します（各 `what` で最初の 3 件まで）。

```text
strata-q36 VERIFY MISMATCH <what><tag>: first at <i> of <n>: new <value> old <value> (bits <new-bits> <old-bits>)
```

追加診断が有効な場合は、最初に異なるブロックについて次の形式を出します（各 `what` で最大 2 件）。

```text
VDEBUG block <blk>: ds new <bits> old <bits>, qs bytes <equal|DIFFER>, cpu butterfly sum <value> (half <bits>)
```

どちらも `std::fprintf(stderr, ...)` による出力です（`engine/src/qwen35/q36_engine.cu:2417-2424`、`2484-2493`）。終了や fallback を起こす処理ではありません。検証全体の比較数と不一致数は `STRATA_Q36_VERIFY` が有効な場合、`Engine` の破棄時に stderr へ出ます（`engine/src/qwen35/q36_engine.cu:5528-5534`）。この変数に関する測定値はありません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:2405-2424` — `STRATA_Q36_VERIFY` の保存、照合カウンター、不一致ログ。
- `engine/src/qwen35/q36_engine.cu:2461-2495` — Q8_1 の比較、`STRATA_Q36_VDEBUG` 判定、ホスト側詳細計算とログ。
- `engine/src/qwen35/q36_engine.cu:2505-2523`, `2667-2691` — 詳細照合を呼ぶ実行経路。
- `engine/src/program/generate.cpp:3804-3818` — `strata` から Qwen3.6 エンジンへの切り替え。
- `engine/cmake/strata_gpu_engine.cmake:565-584` — Qwen3.6 エンジンのビルド条件。
- 関連資料 `docs/QWEN36.md:117-119` は `STRATA_Q36_VERIFY` による旧カーネルとの照合を説明しています。`STRATA_Q36_VDEBUG` の詳細動作は上記ソースに基づきます。
