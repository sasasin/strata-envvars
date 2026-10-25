# `STRATA_MMVQ_IL_Q3K`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の interleaved small-batch matvec (`native_mmvq_il`) で、Q3_K（ggml type 11）に対して interleaved カーネルの行数テーブルを使うかを制御します。無効にすると、この環境変数が判定されるテーブル経路では Q3_K の行数を 0 とし、通常の `native_mmvq` カーネルに戻します。`STRATA_MMVQ_IL` が無効なら interleaved 経路全体が先に使われないため、この変数単独では有効化しません。

## 値と判定

`il_env_on()` は `std::getenv()` の結果が null か、先頭文字が `'0'` 以外なら有効とします。文字列全体の parse はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効（空文字列の先頭は `\0`） |
| 先頭文字が `0`（例: `0`, `0false`, `00`） | 無効 |
| その他（例: `1`, `true`, `false`, ` 0`） | 有効 |

大文字小文字や後続文字は検査されません。したがって文字列 `false` も有効です。

## 有効になる条件

- 実行経路が CUDA 版 `native_mmvq_il` であること。HIP コンパイル側は `native_mmvq_il_supported()` を常に false とし、`native_mmvq_il()` も通常カーネルへ委譲します。
- 呼び出し元が interleaved 経路を選ぶこと。Verifier では `STRATA_MMVQ_IL` が unset または先頭文字が `0` 以外である必要があります。
- GPU architecture が `il_arch_ok()` を通り、複数列での exact-layout 処理が利用可能であること。sm_80 以上はこの判定で許可されます。sm_70、sm_75、sm_60、sm_61 はそれぞれ別のテーブル設定・スイッチ条件があります。
- Q3_K の該当 shape に選択されたテーブルの行数が 0 でないこと。非ゼロのときだけ `native_mmvq_il_supported()` が true になり、interleaved Q3_K カーネルが呼ばれます。

## 実行時の詳細

判定は `il_q3k_on()` 内の `static const bool` に保存されます。最初の判定後、プロセス内で環境を変更しても再評価されません。通常の decode/verify 経路では `native_mmvq_il_supported()` が shape を確認するときにテーブル判定へ進みます。

2〜4列では、対象 GPU のアーキテクチャと行数クラスに対応する通常テーブルに Q3_K の行があれば、それを使います。`STRATA_MMVQ_IL_Q3K` が無効なら `native_mmvq_il_rows_for()` は Q3_K に対して 0 を返すため、Verifier は `native_mmvq()` を呼びます。5〜8列は `STRATA_MMVQ_IL_WIDE` が有効な場合だけ別テーブルを調べ、その経路でも Q3_K の判定を適用します。0行のセルは元から通常カーネルを選びます。

例外として、`STRATA_MMVQ_IL_ROWS` に該当する type/列数の行があり、その行の判定に先に一致すると、カスタム行数を返してから Q3_K の環境変数を確認する通常テーブル判定を通りません。その上書きで非ゼロ行を指定した場合、`STRATA_MMVQ_IL_Q3K=0` でも interleaved Q3_K が使われ得ます。ncols=1 は通常の1列テーブルを使い、この Q3_K スイッチを確認しません（ただし上記カスタム行数の先行一致は除く）。

この変数自身によるログやエラー出力はありません。無効時にテーブル行数が 0 となった shape は、呼び出し元で通常の `native_mmvq` に送られます。

## 根拠

- `src/kernels/cuda/native_mmvq.cu:3092-3097`: 先頭文字による共通判定、Q3_K 判定の static cache。
- `src/kernels/cuda/native_mmvq.cu:3143-3174`: wide/通常テーブル、環境指定テーブル、1列用テーブルの順序と Q3_K の無効化判定。
- `src/kernels/cuda/native_mmvq.cu:3213-3232`: アーキテクチャ条件と interleaved カーネル対応 type の判定。
- `src/kernels/cuda/native_mmvq.cu:3235-3255,3259-3271`: 非対応 shape の通常カーネル fallback、および HIP 側 stub。
- `src/core/verify.cpp:165,1320-1342,1375-1384,1607-1614,2233-2241`: Verifier 側全体スイッチと interleaved / 通常カーネルの選択。
- `docs/MMVQ_IL_TABLE.md:1-20`, `docs/DETAILS.md:2483-2485`: interleaved matvec の説明、対象列数と bitwise parity の記述。性能測定は特定 GPU と shape の結果であり、ここでは一般化していません。
