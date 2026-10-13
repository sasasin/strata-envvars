# `STRATA_GDN_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

検証（verify）経路で複数 token を一括処理する GDN（gated-delta-net）の状態更新を、各 head の状態列を4つの32列ブロックに分けて処理する CUDA/HIP カーネルへ切り替えます。通常の1ブロック/head の recurrence と split kernel のどちらも `gdn_step_norm_multi()` から選ばれます。SYCL の変換済み実装にも同じ環境変数判定があります。

通常の token-by-token GDN カーネル全般を切り替える設定ではありません。呼び出し元で `gdn_step_norm_multi()` が使われる verify の GDN layer に適用されます。

## 値と判定

値全体の parse は行わず、初回判定時の環境値の先頭文字が `'1'` かだけを比較します。

| 環境値 | split 判定 |
|---|---|
| 未設定（通常時） | 無効 |
| 空文字 | 無効 |
| 先頭文字が `1`（例: `1`, `10`, `1foo`） | 有効 |
| 先頭文字が `1` 以外（例: `0`, `true`, ` 1`） | 無効 |

比較は先頭1文字だけです（英字の大文字小文字は判定対象になりません）。数値としての検証、空白の除去、文字列全体の比較はありません。判定値は関数内の `static const bool` に保存されるため、最初の `gdn_step_norm_multi()` 呼び出し後に同一プロセス内で環境値を変更しても反映されません。

HIP ビルドでは起動時に GPU 0 の architecture defaults を適用します。GPU が gfx1151 で、`STRATA_GFX1151_DEFAULTS` が未設定または先頭文字が `0` 以外の場合、`STRATA_GDN_SPLIT` が未設定なら `"1"` を設定します。ユーザーが `STRATA_GDN_SPLIT` を空文字を含め何らかの値で設定していれば、その値を保持します。gfx1151 以外（gfx12 を含む）ではこの architecture default はありません。CUDA ビルドではこの自動設定処理自体が HIP 用 compile guard 内にあるため、unset は無効のままです。

## 有効になる条件

環境値が有効でも、`gdn_step_norm_multi()` が呼ばれ、さらに次のいずれかを満たす場合だけ split 経路になります。

- commit のみの呼び出し: `t_out_begin >= n_tok`。出力を作らず、`gdn_state_replay_kernel` で状態を更新します。
- 出力対象 token が2個以上: `n_tok - t_out_begin >= 2`。split recurrence と、その後の `gdn_out_norm_kernel` を実行します。

commit-only ではなく出力対象が1 token の場合は、この変数が有効でも従来の `gdn_step_norm_multi_kernel` に進みます。これにより1行出力は split しない実装です。`n_tok` の入力範囲は1から `kVerifyMaxT` で、範囲外などの不正引数は環境変数による分岐の前に stderr へ `gdn_step_norm_multi: invalid arguments` を出して終了します。

## 実行時の詳細

verify の forward 側では、GDN layer ごとに `gdn_step_norm_multi()` を呼び、提案 token 群の recurrence と出力を処理します。commit 側でも同関数が呼ばれます。split 出力経路では状態更新を `gdn_step_split_kernel`、出力の正規化を `gdn_out_norm_kernel` に分け、QFUSE 用の `xq` が渡された場合は正規化カーネル側で q8_1 出力も作ります。commit-only 経路は `gdn_state_replay_kernel` を使います。split launch の後は `check("gdn_step_norm_multi (split)")` で backend のエラーを確認します。

gfx1151 向けの起動時自動設定は `src/program/generate.cpp` の `STRATA_USE_HIP` guard 内で、エンジンが各スイッチを初回読み取りする前に `apply_arch_defaults()` を呼びます。自動設定が1つ以上行われると、stderr に設定されたスイッチ名を含む `strata: gfx1151 (Strix Halo): ... exact speed switches on by default ...` の行が出ます。変数単独のログはありません。CUDA/HIP および SYCL の各 kernel 分岐自体には、split専用の情報ログはありません（backend エラーチェックはあります）。

## 資料との照合

`docs/STRIX_HALO.md` は `STRATA_GDN_SPLIT` を gfx1151 で既定有効となる正確性維持型の速度スイッチとして列挙しています。ヘッダーと実装では、ユーザー値を優先し、gfx1151 以外と CUDA の自動 default は対象外とする条件を確認できます。カーネル実装コメントは gfx1151 harness の `h_v=48` で commit 1回あたり8–19%、2行以上の window で3–13%の短縮、1行では利得なしと記載しています。これはソースコメントにある harness 条件での記録であり、一般的な速度保証としては扱えません。同コメントおよび docs は出力が bitwise equal と記載しています。

## 根拠

- `src/kernels/cuda/verify_kernels.cu:327-335,993-1047` — split kernel の構造、環境変数の parse、適用条件、既存経路への fallback、launch error check。
- `sycl/src/kernels/cuda/verify_kernels.dp.cpp:497-505,1831-2050` — SYCL 実装の同じ判定と分岐。
- `src/core/arch_defaults.cpp:12-59,61-80` — gfx1151 architecture default、既存のユーザー値を保持する処理と起動ログ。
- `src/program/generate.cpp:2152-2158` — HIP 起動時に GPU 0 の default を初回読み取り前に適用。
- `src/core/verify.cpp:1162-1180,1988-2006,2638-2658` — verify forward、commit、複数 slot の GDN 呼び出し。
- `include/strata/core/arch_defaults.hpp:1-10`, `docs/STRIX_HALO.md:83-98` — gfx1151 default の範囲と資料上の説明。
