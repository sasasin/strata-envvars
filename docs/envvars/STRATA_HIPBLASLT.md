# `STRATA_HIPBLASLT`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Inkling2 の HIP backend が使う動的 hipBLASLt Tensile runner の有効・無効を切り替える。runner が使えると、対応する BF16/FP16 GEMM を hipBLASLt に渡し、使わない場合や個別 GEMM が失敗した場合は HIP backend 内の通常 GEMM 経路を使う。値は `HipBlasLtRunner::init()` が GPU 世代ごとの既定値を上書きする用途で読み取る（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-65`）。

## 値と判定

対応する AMD GPU 世代では、環境変数が未設定なら RDNA4 のみ有効、RDNA3/3.5 は無効。設定されている場合は `std::atoi(env) != 0` の結果でこの既定値を上書きする。文字列全体の厳密な数値検証はなく、`atoi` が先頭の整数部分を変換する。したがって空文字・先頭が数値でない文字列は `0`、`1tail` は `1`、`0anything` は `0`、`-1` は非ゼロとなる。先頭空白と符号は `atoi` の変換規則に従い、大文字小文字は数値判定には関係しない。整数として表現できない範囲の入力はコードで検査されない（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:61-65`）。

| GPU 世代（HIP backend） | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| RDNA4（`gfx120*`） | 有効 | `atoi` の結果が非ゼロ（例: `1`, `-1`, `1tail`） | `atoi` の結果がゼロ（例: `0`, 空文字, `true`, `0anything`） |
| RDNA3 / RDNA3.5（`gfx110*` / `gfx115*`） | 無効 | `atoi` の結果が非ゼロ | `atoi` の結果がゼロ |
| RDNA2（`gfx103*`）または Unknown | 無効 | 該当なし。値を読む前に runner 初期化を拒否 | 常に無効 |

世代の分類は `gfx120` を RDNA4、`gfx115` を RDNA3.5、`gfx110` を RDNA3、`gfx103` を RDNA2 とする（`engine/include/strata/hip_uma_guard.hpp:29-35,49-55`）。

## 有効になる条件

- Inkling2 の HIP backend が選ばれる必要がある。この backend は `INKLING_ENABLE_HIP` で宣言・選択され、CPU 強制時や CUDA / Metal / SYCL backend ではこの読み取り経路を通らない（`engine/src/inkling2/ink_backend.h:131-167`）。
- `--serve` と直接生成で別の env 判定はなく、どちらも共通の backend 初期化を通る（`engine/src/inkling2/ink_main.cpp:564-577`）。
- GPU 世代が RDNA3、RDNA3.5、RDNA4 のいずれかであること。RDNA2 と Unknown は環境変数の判定より前に `false` を返すため、非ゼロ値でも有効化できない（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-65`）。
- 非ゼロ値で有効化しても、Windows では `libhipblaslt.dll` または `hipblaslt.dll`、それ以外では `libhipblaslt.so.1` または `libhipblaslt.so` のロードが必要。必要なシンボルや hipBLASLt の handle / preference 作成に失敗すれば runner は無効のまま戻る（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:67-109`）。
- ほかの環境変数や CLI 引数によるこのスイッチの上書きは、この環境変数の読み取り箇所にはない。読み取り箇所は `HipBlasLtRunner::init()` の `getenv` 一箇所（`engine/src/inkling2/hip/ink_hip_blaslt.hpp:62-64`）。

## 実行時の詳細

`HipBackend::init()` は GPU 情報を得た後、runner の `init()` を呼び、その直後に `warmup()` を呼ぶ。変数はこの runner 初期化時に読み取られ、関数内 static やリクエスト単位の再読込はない。したがって、backend 初期化後にプロセス環境を変えても、backend を再初期化しない限り反映されない。無効時やロード・初期化失敗時は runner が `false` を返し、呼び出し元は戻り値を無視して backend の初期化を続ける。`warmup()` は runner が ready でなければ何もしない（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:703-705`; `engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-65,67-123,128-132`）。

runner が ready でもすべての行列積が必ず hipBLASLt になるわけではない。例として BF16 経路では `M >= blaslt_min_m_`、`N >= 64`、`K >= 64`、scratch 容量が条件を満たし、hipBLASLt GEMM が成功した場合にその結果を使う。それ以外は続く HIP WMMA または通常 GEMM 経路を実行する（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2582-2609`）。

## ログと測定値

環境変数の値や runner 初期化の失敗を直接説明する専用ログは確認できない。Inkling2 の selfcheck 成功行は backend の `device_info()` を出力し、その文字列に `blasLt=1`（ready）または `blasLt=0`（not ready）が含まれる。文言は `[selfcheck] PASS backend=... (...)`（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:517-538`; `engine/src/inkling2/ink_main.cpp:122-127`）。Strata 資料にこの変数固有の測定値はない。

## 根拠

- 値の読み取り、GPU 世代既定値、未対応世代の拒否、動的ライブラリのロードと初期化: `engine/src/inkling2/hip/ink_hip_blaslt.hpp:53-123`
- AMD GPU 世代分類: `engine/include/strata/hip_uma_guard.hpp:29-55`
- HIP backend のビルド時選択: `engine/src/inkling2/ink_backend.h:131-167`; HIP 実装のコンパイル: `engine/src/inkling2/hip/CMakeLists.txt:74-116`
- backend 初期化時の runner 初期化と warmup: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:703-705`
- server / 直接生成が共有する backend 初期化: `engine/src/inkling2/ink_main.cpp:564-577`
- runner の利用条件と失敗後の別 GEMM 経路: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2582-2609`
- selfcheck での状態表示: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:517-538`; `engine/src/inkling2/ink_main.cpp:122-127`
