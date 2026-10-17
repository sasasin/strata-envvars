# `STRATA_MMQ_DIRECT_LOG`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_MMQ_DIRECT=1` で prompt MMQ が cache slot 内の resident expert を直接読む経路について、prompt 処理後に stage ごとの expert 数を stderr へ出します。直接読み込みの有効・無効や計算方法は切り替えず、診断ログだけを制御します。

## 値と判定

`src/prefill/prefill.cpp` は、`Prefill::run()` が成功経路を通り、かつ `mmq::direct_mode() == 1` のときだけ、この変数を読みます。値は `std::atoi()` で変換し、結果が 0 以外ならログを有効にします。

| 値 | 判定 |
|---|---|
| 未設定、空文字 | `atoi` の結果が 0 となり無効 |
| `1` など数値変換結果が 0 以外 | 有効（負数も有効） |
| `0`、`0tail`、数値に変換できない文字列 | `atoi` の結果が 0 となり無効 |
| 数字の後ろに文字が続く値 | `atoi` が先頭の数値部分を変換し、その値が 0 以外なら有効。例: `2tail` は有効 |

空白と符号は `atoi` の変換規則に従います。文字列全体の妥当性検査や警告はありません。判定結果は関数内の `static const bool` に保存され、最初の該当 prompt で読み取られた後は同じプロセス内で環境値を変更しても再評価されません。

## 有効になる条件

- `STRATA_MMQ_DIRECT` の実効 mode が `1` であることが必要です。mode `0`（未設定を含む）と mode `2` では、このログ判定は実行されません。mode の値判定は `src/prefill/moe_mmq.cu` で `atoi` により行われます。
- mode `1` を実行できるのは CUDA で `STRATA_MMQ_TAB` を含めてビルドした場合です。CMake の同オプションは既定 OFF で、llama.cpp の `mmq.cuh` が Strata 側 scheduler の検証対象と一致しない場合も configure 時に無効化されます。HIP や pointer-table MMQ なしの build では mode `1` は無効です。
- prompt MMQ 自体が使われる条件も必要です。native pack で `STRATA_PREFILL_MMQ` が有効であり、対象 layer の形式・shape が MMQ の対応条件を満たす場合に直接読み込みが計画されます。対応しない layer や streamed / peer-GPU expert は直接読み込み数に含まれず、既存の gather 経路を使います。
- `Prefill::run()` が `run_impl()` と pipeline drain の両方に成功した後にだけ出力します。prompt が失敗した場合はこのログ箇所に到達しません。

## 実行時の詳細

prompt ごとに各 prefill stage を走査し、次の形式で stderr に出します。

```text
strata prefill: layers <開始>..<終了>: <直接読み込み数> of <resident expert 数> resident experts read in place, <streamed expert 数> streamed (STRATA_MMQ_DIRECT, totals)
```

数値は `Prefill::stats_` の stage 累計です。直接読み込み数は `experts_direct`、resident expert の数は `experts_resident`、streamed expert の数は `experts_streamed` から取得します。ラベルの `totals` の通り、chunk ごとのログではなく prompt の `run()` が完了した時点の stage 別集計です。ログ変数はこれらのカウンタを変更しません。

## 根拠

- `src/prefill/prefill.cpp:4813-4844` — `Prefill::run()` の成功・drain 後に mode を確認し、`STRATA_MMQ_DIRECT_LOG` を `atoi != 0` で一度だけ判定して stage 別 stderr ログを出す。
- `include/strata/prefill/prefill.hpp:32-40` — stage 統計の `experts_direct`、`experts_resident`、`experts_streamed`。
- `src/prefill/prefill.cpp:1129-1174,4203-4260` — MMQ plan の直接読み込み条件と、実際に slot を使って直接読み込む expert の計数。
- `src/prefill/moe_mmq.cu:541-554` — `STRATA_MMQ_DIRECT` の parse、未対応 build での無効化。
- `CMakeLists.txt:88-96,1606-1645` — `STRATA_MMQ_TAB` の既定値、CUDA-only 条件、llama.cpp scheduler の検査。
- `docs/DETAILS.md:1928-1940` — `STRATA_MMQ_DIRECT` の設計資料と、このログが prompt ごとに stage の直接読み込み数を出すとの説明。資料中の測定値はこの変数自体の効果ではないため、本書では記載していない。
