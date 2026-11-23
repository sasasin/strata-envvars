# `FNX_SH_FUSE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`FNX_SH_FUSE` は、`strata-split` の FFN 処理で共有 expert の gate/up・down 計算を routed expert のカーネル起動へ組み込む対象型を広げる設定である。既定値では Q4_K に加えて対応する非 Q4_K 型でも組み込み、`0` では非 Q4_K 型を別ストリームの処理へ戻す。Q4_K は `0` でも組み込み対象のまま。ルーティング条件そのものを変更する分岐ではなく、共有 expert の実行経路を選ぶ（`engine/src/split/src/engine.cu:937-975`）。

このコードは `STRATA_BUILD_SPLIT` が有効なときだけ追加される Linux 向け CUDA/HIP の任意ビルド `strata-split` に属する。通常の Strata エンジンにはこの読み取り箇所はない（`engine/CMakeLists.txt:839-844`、`engine/src/split/CMakeLists.txt:116-152`）。

## 値と判定

読み取りは `fnx::env_int` を通じて行われる。未設定なら呼び出し側の既定値 `1`。設定時は符号付き 10 進整数全体を `strtoll` で解析し、先頭から末尾まで整数であることと `long long` の範囲内であることを要求する。符号は許可される。空文字、前後の空白、整数に続く文字、整数範囲外は無効で、`FNX_SH_FUSE: '<値>' is not a whole number` の例外になる。値を boolean にする段階では `!= 0` を使うため、整数として有効な非ゼロ値は正負を問わず有効。clamp はない（`engine/src/split/src/env.hpp:15-21,33-40`、`engine/src/split/src/engine.cu:940`）。

| `FNX_SH_FUSE` | 値の判定 | 非 Q4_K 対応型 | Q4_K |
|---|---|---|---|
| 未設定 | 既定値 `1` | 型・量子化等の他条件を満たせば融合 | 他条件を満たせば融合 |
| 整数 `0`（例: `0`, `-0`） | 無効 | 別ストリーム経路 | 他条件を満たせば融合 |
| 整数の非ゼロ値（例: `1`, `-1`, `01`, `+2`） | 有効 | 型・量子化等の他条件を満たせば融合 | 他条件を満たせば融合 |
| 空文字、`true`、`false`、`0anything`、空白付き数値 | 整数全体として不正 | 例外 | 例外 |

## 有効になる条件

- `strata-split` がビルドされ、そのエンジンの FFN 処理が実行されること。ビルド設定 `STRATA_BUILD_SPLIT` は既定で OFF（`engine/CMakeLists.txt:839-844`）。
- `FNX_SH_FUSE` が未設定または整数として有効であること。設定値は CLI 引数による上書きの分岐を持たない（`engine/src/split/src/engine.cu:940`）。
- 非 Q4_K 型で融合する場合、expert の型が Q5_K、Q5_1、Q4_0、Q8_0、IQ4_NL、IQ4_XS、IQ3_S、IQ3_XXS、IQ2_S のいずれかであること。Q4_K は環境変数の値にかかわらず型条件を通る（`engine/src/split/src/engine.cu:941`）。
- いずれの型でも、共有 expert の gate/up と down の Q8S データが存在し（`L.sh_gu.s.q` と `L.sh_down.s.q`）、FF 幅 `ffs` が 32 の倍数かつ `SH_MAXF` 以下であること。満たさない場合は `sh_in` が偽となり別ストリーム経路になる（`engine/src/split/src/engine.cu:935,941-949`）。

## 実行時の詳細

値は `Engine::ffn_half` 内の関数ローカル `static const bool` によって初期化される。したがってプロセス内で最初にこの関数へ到達した際に一度読み、以後の呼び出しやカード、同じプロセス内の別 `Engine` でも保存値を使う。初期化後に環境を変更しても再読込しない。`ffn_half` は通常の enqueue 経路と MTP enqueue 経路の双方から呼ばれる（`engine/src/split/src/engine.cu:940,1037-1039,1121-1123,1206-1208,1341-1345,1405-1409`）。

`sh_in` が真なら `router_route` に共有 expert の gate/up 重みを渡し、共有 expert の down 重み等を引数にして `moe_gate_up` を一度呼ぶ。この関数は Q4_K と表の対応型を処理し、それ以外の型を渡された場合は例外を投げる。`sh_in` が偽なら共有 expert の gate/up、SwiGLU、down を第 2 ストリームで実行し、routed expert の処理後にイベントを待つ（`engine/src/split/src/engine.cu:942-975`、`engine/src/split/src/kernels.cu:2202-2229`）。

## ログと測定値

未設定・有効値時にこの設定自体のログ出力はない。無効な文字列は `env_int` が `std::runtime_error` を投げる。`fnx_run` では stderr に `fnx_run: <例外内容>` を出し終了コード 1、`sfnx` では `ERR <例外内容>` を stdout、`sfnx: failed: <例外内容>` を stderr に出して終了コード 1 となる（`engine/src/split/tools/fnx_run.cpp:1365-1373`、`engine/src/split/tools/sfnx.cpp:1094-1103,1131-1135,1160-1167`）。Strata の資料にこの変数による測定値の記載は確認できない。

## 根拠

- `engine/src/split/src/env.hpp:15-21,33-40` — 整数全体の構文、基数、範囲確認、未設定時の既定値、無効値の例外。
- `engine/src/split/src/engine.cu:934-975` — 読み取り、型・量子化・幅の条件、融合／別ストリームの実行。
- `engine/src/split/src/kernels.cu:2202-2229` — 融合経路の処理と対応型、それ以外の例外。
- `engine/CMakeLists.txt:839-844`、`engine/src/split/CMakeLists.txt:116-152` — split engine の opt-in ビルドと CUDA/HIP ターゲット。
- `engine/src/split/tools/fnx_run.cpp:1365-1373`、`engine/src/split/tools/sfnx.cpp:1094-1103,1131-1135,1160-1167` — 例外時の観測出力と終了。
