# `--kv-dtype`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（トップレベル） |
| オプション | `--kv-dtype` |
| 別名 | `--kv` |
| 値 | `auto`、`fp8` / `fp8_e4m3`、`fp16` / `f16`、`k8v8` / `i8` / `q8`、`k8v4` |

## 役割

K/V（キー・バリュー）キャッシュの保存形式を指定します。キャッシュは通常の生成、`--serve`、`--bench` などで backend の初期化・slot 確保に渡され、選んだ形式に応じた格納領域や読み書き経路が使われます。既定値の `auto` は FP16 を基準にしつつ、CUDA/HIP では並列数・GPU メモリなどに応じて FP8 を選ぶことがあります。parser は `--info` や `--export-tokenizer` といった別モードでも共通にオプションを読みますが、それらの処理は backend を初期化しないため、この値は使いません（`engine/src/inkling2/ink_main.cpp:380-426`, `544-569`）。

## 使い方

```sh
# 自動選択（既定）でモデルを起動
strata-inkling --native model.strata

# 明示的に FP16 キャッシュを使って起動
strata-inkling --native model.strata --kv-dtype fp16

# サーバーモードで FP8 を指定
strata-inkling --serve --native model.strata --kv fp8
```

## 値と既定値

- オプションを省略した場合の `BackendOpts` は `kv_dtype=FP16`、`kv_dtype_auto=true` です。つまり既定は固定 FP16 ではなく、自動選択が有効な状態です（`engine/src/inkling2/ink_backend.h:32-34`）。
- `fp8` と `fp8_e4m3` は FP8 E4M3、`fp16` と `f16` は FP16、`k8v8` / `i8` / `q8` は K8V8、`k8v4` は K8V4 を選び、自動選択フラグを解除します（`engine/src/inkling2/ink_main.cpp:415-421`）。値の比較は大文字小文字を区別します。
- `auto` は自動選択フラグを有効にします。parser はこのとき既存の dtype 値を初期値に保ちます。複数回指定した場合は左から順に処理され、最後の指定が最終状態を決めます。ただし `auto` の後の明示値は自動選択を解除し、明示値の後の `auto` は自動選択を再度有効にします（同:415-421）。
- 値なし、または列挙外の値は拒否されます。値は別引数で渡す形式で、`--kv-dtype=fp16` のような等号形式は parser にありません（同:380-383, 415-425）。

## 実行時の動作

- 明示値は backend の設定に反映されます。CPU backend は選択値を保持し、slot の K/V 領域をその dtype で初期化します（`engine/src/inkling2/ink_cpu_backend.cpp:153-159, 310-319`）。CUDA backend は FP8/K8V8/K8V4/FP16 を CUDA 側の形式に写像し、runner の初期化に渡します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:162-168, 240`）。
- `auto` の選択条件は backend ごとに異なります。
  - CUDA は並列 slot 数が16以上なら FP8 を選びます。また `--kv-offload off` の場合、GPU 総メモリが13 GiB以下、または compute capability 8.9以上・contextが16,384超・総メモリ40 GiB未満の条件でも FP8 を選びます。それ以外は初期値 FP16 です（`engine/src/inkling2/cuda/ink_cuda_backend.cu:146-168`）。
  - HIP は並列数16以上かつ実効総メモリ36 GiB以下、または UMA でない GPU の実効総メモリ13 GiB以下で FP8 を選びます。さらにモデル読込後、FP16 の KV 必要量・ShortConv 必要量・予約余裕の合計に空き VRAM が足りない場合も FP8 に切り替え、stderr に選択理由を出します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:693-701, 1352-1359`）。
  - 共通 parser は並列数16以上なら backend 初期化前にも dtype を FP8 にします（`engine/src/inkling2/ink_main.cpp:535-538`）。
- K8V8 と K8V4 は CPU/CUDA でサポートされていますが、HIP backend は初期化時に拒否します。エラー文は `--kv k8v4/k8v8 is not supported ...` で、FP8 または FP16 を使うよう案内します（`engine/src/inkling2/ink_batch.h:33-36`, `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:566-569`）。
- `--kv-offload` は CUDA の自動選択条件に関係し、特に `off` は FP8 を選ぶ条件を追加します。`--kv-dtype` を明示すると dtype の自動選択は止まります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:148-160`）。

## 適用条件と副作用

この指定は backend を初期化してキャッシュを使う経路に適用されます。トップレベル parser の値は `--selfcheck`、`--bench`、`--serve`、直接生成、KLD 評価などの設定へ渡りますが、モデル情報表示や tokenizer 書き出しのように backend を呼ばない mode では効果がありません（`engine/src/inkling2/ink_main.cpp:544-579`）。HIP では K8V8/K8V4 が利用できず、明示時は初期化に失敗します。CUDA/HIP で `auto` から FP8 に切り替わる条件は異なり、特に HIP ではモデル読込後の空き容量にも依存します。

## 出力とエラー

- 値が欠落すると `missing value after --kv-dtype` を stderr に出して終了コード 2 で終了します（`engine/src/inkling2/ink_main.cpp:380-383`）。
- 不明な値では `unknown --kv value '<値>' (expected: auto, fp8, fp16, k8v8, k8v4)` を stderr に出し、終了コード 2 で終了します（同:422-425）。
- backend 初期化失敗は通常 mode で `init: <理由>`、serve mode でプロトコル出力 `ERR init: <理由>` を出し、終了コード 1 になります。HIP の K8V8/K8V4 拒否はこの経路です（同:564-569）。
- serve は backend の実際の選択 dtype を `INFO ... kv_dtype=<fp8|fp16|k8v8|k8v4>` に含めます（`engine/src/inkling2/ink_serve.h:471-485`）。HIP のメモリ不足による自動 FP8 切替時は追加で stderr に通知します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:1354-1359`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:380-383, 415-425` — parser の値・別名・失敗処理。
- `engine/src/inkling2/ink_backend.h:32-34` — 既定の dtype と自動選択フラグ。
- `engine/src/inkling2/ink_main.cpp:535-538, 544-579` — 共通の高並列時選択、処理 mode への適用。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:146-168, 240` — CUDA backend の自動選択と型の写像・runner 初期化。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:566-569, 693-701, 1352-1359` — HIP の非対応値、選択条件、メモリ容量による自動切替。
- `engine/src/inkling2/ink_cpu_backend.cpp:153-159, 310-319` — CPU backend の設定保持と slot の K/V 初期化。
- `engine/src/inkling2/ink_batch.h:23-36` — dtype 名と整数量子化形式の定義。
- `engine/src/inkling2/ink_serve.h:471-485` — serve の INFO 出力。
