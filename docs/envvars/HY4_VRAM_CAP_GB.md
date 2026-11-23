# `HY4_VRAM_CAP_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata-hy4` の非サーバー実行で、メモリ計画に使う GPU メモリ量を指定 GiB 相当に見せるテスト用フックです。設定値をバイトに換算し、現在の空きメモリ `fr` より小さい場合は差分サイズの HIP 割り当てを保持して空きを減らし、ローカルの `fr` と `tot` をともに指定量へ置き換えます。その値は `plan_memory` に渡され、チャンク自動選択などの容量判断に使われます。実カードの総 VRAM を変更する設定ではありません。`engine/src/hy4flash/run/hy4_main.hip.cpp:617-630,648`、`engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-438,492-501`。

## 値と判定

実装は `getenv("HY4_VRAM_CAP_GB")` の非 null 判定で設定有無を見てから、同じ環境変数を `atof` に渡し、結果に `1073741824.0` を掛けます。文字列全体の妥当性・範囲・変換エラーは検証しません。`atof` の数値プレフィックスが使われ、後続文字は無視されます。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効・特別な値 |
|---|---|---|---|
| `strata-hy4` の非サーバー経路 | 実測した `fr` / `tot` のまま。追加割り当て・上書き・上限ログなし | 変換値が現在の `fr` より小さいときだけ、差分を `hipMalloc` し、ローカルの `fr` / `tot` を指定量にする。例: 空きが 8 GiB より多い状態で `8`、`7.6`、` 7.6junk` | 値が現在の空き以上なら何もしない。空文字・`true`・`abc`・`0anything` は `atof` 結果が 0 となり、`fr > 0` なら 0 バイト相当の上限を目指す。`8GB` は 8 として扱う。`nan` は比較が成立せず何もしない。負値は範囲検証されず `size_t` へ変換されるため、結果は規定可能な安全な上限として扱えない |

`atof` による変換後、正の値も GiB からバイトへ換算した後 `size_t` に切り詰められます。`cap < fr` の比較だけが割り当て条件です。境界値 `cap == fr` では何もしません。変換不能文字列を拒否したり、0 や負値を clamp したりする処理はありません。`engine/src/hy4flash/run/hy4_main.hip.cpp:622-630`。

## 有効になる条件

- `strata-hy4` がビルドされて実行される必要があります。統合 CMake では `STRATA_BUILD_HY4=ON` かつ CUDA または HIP が必要で、既定は OFF です（`engine/CMakeLists.txt:846-852,884-908`）。
- `--serve` なしの通常実行でのみ、この読み取り箇所に到達します。`--serve` は先に `hy4_serve_main` を呼んで戻り、そちらは通常の `hipMemGetInfo` の値で計画するため、この変数を適用しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:543-611,617-630`; `engine/src/hy4flash/run/hy4_serve.hip.h:262-292`）。
- `--info` など GPU 実行前に戻る引数経路にも適用されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:507,617`）。
- `cap` がその時点の空き `fr` 以上なら無視されます。別の CLI 値との優先順位はなく、`--chunk` が正数なら `plan_memory` の自動チャンク選択はスキップされますが、変数によるメモリ値の置換自体は行われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:622-630,648`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:492-510`）。
- `plan_memory` は `HY4_KV_HOST` が設定済みなら計算した host-KV mask をその値で上書きし、`HY4_RESERVE_GB` が設定済みなら予約量を新規計算・設定しません。これらの明示設定は後段の計画項目を変えますが、`HY4_VRAM_CAP_GB` の割り当てと `fr` / `tot` の置換を取り消しません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:518-535,545-563`）。

## 実行時の詳細

引数解析後、サーバーモード分岐の外で GPU 情報と `gpu_mem_avail` の `fr` / `tot` を得てから読みます。値は関数ローカルで使われ、`static` キャッシュはありません。環境変数を再読する契機はなく、この実行中にプロセス環境を変更しても既に行った割り当てや計画値には反映されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-630`）。

`cap < fr` の場合、`hipMalloc` の返したポインタは保持され、ここで解放されません。続いて `fr = cap`、`tot = cap` として `plan_memory(..., tot, ..., fr, ...)` に渡すため、自動チャンク・KV配置・予約計算などの判断が指定値に基づきます。明示的な `--chunk` は自動チャンク選択だけを抑止します（`engine/src/hy4flash/run/hy4_main.hip.cpp:622-630,648`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:434-438,492-501,511-563`）。

HIP 割り当てが失敗すると `HCK` が stderr に `HIP error %d (%s) at %s:%d` を出し、終了コード 3 で終了します。上限割り当て後にモデル読み込みが失敗する場合は通常の `load_gpu_model` 失敗経路で終了コード 1 です（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`; `engine/src/hy4flash/run/hy4_main.hip.cpp:626,658-660`）。

## ログと測定値

- 初期の `[gpu] ... free ... / ... GiB` は上限処理前の計測値です（`engine/src/hy4flash/run/hy4_main.hip.cpp:617-621`）。
- `cap < fr` で割り当てが成功すると `[gpu] VRAM capped to %.1f GiB (test)` を stderr に出します。`cap >= fr` や unset の場合、この上限ログは出ません（`engine/src/hy4flash/run/hy4_main.hip.cpp:624-630`）。
- 後続の `[plan]` は計画に使った空き・総量を出します（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:564-565`）。この変数に関する測定値は Strata の文書に見つかりませんでした。
- `hipMalloc` 失敗時は前節の `HIP error ...` と終了コード 3 が観測されます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:617-630` — 初期 GPU メモリの取得、環境変数判定、変換、ballast 割り当て、値の置換とログ。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:543-611,648,658-660` — サーバー分岐、メモリ計画への値渡し、モデル読み込み失敗。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34,434-438,492-510,518-565` — HIP エラー時の終了、容量判断、自動チャンクと後続メモリ計画・ログ。
- `engine/src/hy4flash/run/hy4_serve.hip.h:262-292` — サーバー側の独立したメモリ取得と計画。
- `engine/CMakeLists.txt:846-852,884-908` — 対象バイナリのビルド条件と CUDA/HIP ソース選択。
