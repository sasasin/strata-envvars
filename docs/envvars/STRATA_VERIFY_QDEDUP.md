# `STRATA_VERIFY_QDEDUP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

CUDA と SYCL の verifier において、MoE 入力 `xm` の q8_1 量子化結果を shared expert と通常 expert で共有します。条件を満たす場合、shared expert を呼ぶ前に q8_1 データを作り、そのポインターを shared expert に渡します。shared expert 側で同じ入力を再量子化せずに済み、shared expert の後で通常 expert 用に同じデータを作り直す処理も省きます。

## 値と判定

値は `std::getenv()` で取得し、`std::atoi(v) != 0` で判定します。変数が未設定なら無効です。設定値は数値の全体一致ではなく `atoi` の変換結果で決まります。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、`true`、`abc` | `atoi` が 0 を返すため無効 |
| `0`、`0tail`、`+0` | 変換結果が 0 のため無効 |
| `1`、`2`、`-1`、`1tail` | 変換結果が非 0 のため有効 |

`atoi` は先頭の空白と符号を受け付け、数字列の後ろに続く文字列を検査しません。たとえば ` 1xyz` は有効になります。範囲・書式のエラーを別途検査するコードはありません。

判定結果は `g_qdedup()` 内の関数ローカル `static const bool` に保存されます。最初の呼び出しで一度評価され、その後プロセス内で環境を書き換えても再評価されません。

## 有効になる条件

環境変数の判定が有効でも、実際に再利用するのは `!sh_fork` かつ `strata::kernels::cpu::expert_layout().native` の場合だけです。shared expert が forked stream で実行される場合は専用バッファに量子化するため対象外です。native expert layout でない場合も `qdedup` は false のままです。

`q8_ffn` が false のときは、shared expert の呼び出し前に `quantize_q8_1_rows(xm, ...)` が `nat_xq_` を作成します。true のときはその場所で作成せず、既に MoE 入力の q8_1 データが用意されている経路として扱います。いずれの場合も `qdedup` が true なら `nat_xq_` が shared expert に渡され、native layout の通常 expert 向け q8_1 量子化は shared expert の後では繰り返しません。

## 実行時の詳細

通常 expert と shared expert は同じ verifier の layer/group 処理内で計算されます。CUDA 実装では shared expert 呼び出し時に `nat_xq_` の group 内オフセットを `x_q8_1_ready` 引数として渡します。shared expert はその引数が非 null なら優先して入力の q8_1 として使い、gate/up の行列ベクトル積へ渡します。null の場合は descriptor の q8_1 バッファを使い、それもなければその場で量子化します。SYCL 実装も同じ選択です。

この再利用は `quantize_q8_1_rows` と shared expert の通常量子化が同じバイト列を作る、というコードコメントに基づいています。`docs/DETAILS.md` にこの環境変数の説明や測定値は見つかりませんでした。コード上はログ出力を伴わない最適化です。

## 根拠

- `src/core/verify.cpp:155` — 環境変数を `atoi` で一度判定。
- `src/core/verify.cpp:1544-1561` — 通常 expert と shared expert の q8_1 を共有する条件と事前量子化。
- `src/core/verify.cpp:1567-1582` — q8_1 ポインターを shared expert に渡し、重複する通常 expert 量子化を省略。
- `src/kernels/cuda/shared_expert.cu:214-225,227-240` — 渡された ready buffer を入力として使う処理。
- `sycl/src/core/verify.cpp:74,1360-1377,1383-1398` — SYCL 側の同等実装。
- `sycl/src/kernels/cuda/shared_expert.dp.cpp:313-324,326-352` — SYCL shared expert の同等処理。
