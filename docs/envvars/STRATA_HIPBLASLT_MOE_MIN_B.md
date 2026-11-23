# `STRATA_HIPBLASLT_MOE_MIN_B`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HIP 版 `strata-inkling` の MoE において、全 expert が GPU 常駐する層で使う hipBLASLt の unpack-once 経路（Fast Path A2）を選ぶ最小 batch `B` を設定する。バックエンド初期化時の既定閾値は `999999` で、通常の batch では A2 を実質無効にする。値を `16` 以上にするとその値が閾値になり、条件を満たす batch で expert 重みを FP16 に unpack して hipBLASLt GEMM を使う候補になる。変数自体が hipBLASLt を有効化するわけではない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:703-728,3805-3810,3903-3904`）。

## 値と判定

`HipBackend::init()` が `std::getenv` で値の有無を調べ、設定されていれば `std::atoi` の結果を使う。`atoi` は数値全体の厳密な検証をせず、数値として読める先頭部分を変換する。変換結果が `16` 以上なら閾値に採用し、それ未満なら既定値 `999999` のまま。空文字や数字で始まらない文字列は通常 `atoi` が `0` を返すため採用されない。先頭空白や符号は `atoi` の変換規則に従い、末尾の文字列は値判定されない。変換前後に独自の形式検査はない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:714-718`）。

| 条件 | unset | 有効になる値 | 無効・採用されない値 |
|---|---|---|---|
| HIP Inkling2 backend の初期化 | `999999`（実質無効） | 変換結果が `16`〜`999998`。例: `16`, `64`, `16tail` | 空文字、非数値、`0`, `15`, `-1` は閾値に採用されず既定値。`999999` 以上は閾値に代入されても scratch buffer 確保条件を満たさず A2 は使えない |

数値として解釈できる値に対する追加の上限 clamp はありません。ただし `999999` 以上では確保条件 `blaslt_moe_min_b_ < 999999` が偽になり、A2 に必要なバッファが確保されません。`atoi` が `int` の表現範囲外の入力に対して返す結果はこのコードで検査されていません（同 `:714-728`）。

## 有効になる条件

- HIP backend を使う `strata-inkling` であること。この変数の読み取りは `engine/src/inkling2/hip/ink_hip_backend.hip.cpp` にあります。HIP plugin のビルド定義と `strata-inkling` へのリンクは `engine/src/inkling2/hip/CMakeLists.txt:74-82,96-116`。
- `STRATA_HIPBLASLT_MOE_MIN_B` の変換結果が `16` 以上かつ `999999` 未満であること。これにより `blaslt_.ready()` が真のときだけ重み用 FP16 バッファを確保します。確保結果のポインタも実行時分岐で確認されます（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:714-728,3903-3904`）。
- hipBLASLt runner が ready であること。runner は RDNA2 と世代不明では初期化を拒否します。その他では既定で RDNA4 のみ有効で、`STRATA_HIPBLASLT` が設定されると `atoi` の非ゼロ判定で有効・無効を上書きします。ライブラリや必要シンボルなどの初期化に失敗した場合も ready になりません（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-74,84-105,122`; 呼び出し元 `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:703-705`）。
- 対象層の expert がすべて GPU 常駐で、実行 batch `B` が設定閾値以上であり、CUDA graph 実行中でないこと（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3903-3904`）。
- `ep2_active_ && layer_all_ep2_[ip]` の経路では先に EP-2GPU 処理を行い、この A2 分岐を通りません。また `B <= 4` の all-GPU 経路はその前の direct MoE 分岐を使います（同 `:3811-3818,3875-3904`）。GPU 常駐条件などを満たさない経路では A2 の閾値は使われず、別の MoE 経路へ進みます（同 `:3903-3947`）。

## 実行時の詳細

値は各 `HipBackend::init()` の実行中、hipBLASLt runner の初期化・warmup の後に一度読み、`blaslt_moe_min_b_` メンバーへ保存する。各 MoE 層の実行で環境を読み直す処理はなく、batch `B` と保存済み閾値を比較する。backend を再初期化すればその初期化時点の環境値で再設定される（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:554-565,703-718,5425-5429`）。

A2 に入ると router の expert ID から bucket を作り、入力行を FP16 に集め、bucket offset を host にコピーして stream を同期する。expert ごとに必要な重みを unpack-once して、行数を scratch 上限で分割しながら `run_single_expert_blaslt()` を呼ぶ。最後に expert 出力を token ごとに集約する（同 `:3903-3945,2624-2704`）。この閾値を CLI 引数が直接上書きする処理はありません。CLI やサーバーの batch が実際の `B` を決める場合、その値との比較を通じて間接的に経路選択へ影響します。

## ログと測定値

この環境変数を読んだことや閾値を採用したことを示すログはありません。A2 内の bucket offset コピーまたは stream 同期が失敗すると `false` を返します。bucket 範囲または scratch 容量の異常時は `err` に `[ink-hip] Fast Path A2 MoE bucket out of bounds (beg=..., m_e=..., pairs=...)` を設定して `false` を返します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3917-3930`）。個々の hipBLASLt GEMM が成功しない場合、重み形式に応じた Strata の別の kernel 経路へ fallback します（同 `:2659-2670,2692-2702`）。

`docs/SETTINGS.md:104` はこの名前を AMD 向け `number` として列挙しています。性能コメントは実装ソースにありますが、ここではその測定条件を裏付ける資料を確認できなかったため、性能値は記載しません。

## 根拠

- 読み取り、`atoi` 判定、既定値、FP16 scratch buffer 確保: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:703-728`
- A2 の選択条件、bucket 処理と集約: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:3805-3810,3875-3904,3913-3945`
- expert unpack-once、GEMM と kernel fallback: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2624-2704`
- hipBLASLt runner の GPU 世代・環境変数・初期化条件: `engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-74,84-126`
- HIP plugin のコンパイルと実行ファイルへのリンク: `engine/src/inkling2/hip/CMakeLists.txt:74-82,96-116`
- 設定一覧の記載: `docs/SETTINGS.md:104`
