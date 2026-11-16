# `STRATA_SYCL_GU16_METADATA_QUARTET`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の gate/up FP16 dequantization で、IQ2_XXS（type 16）の特定形状に限り、従来の bounded kernel の代わりに quartet metadata の読み出し・配布を行う kernel を選ぶ opt-in 変数です。対象形状は `n_ff=640`、`n_embd=2560` です。専用 kernel は subgroup 内で4レーンごとに metadata を読み、`select_from_group` で共有します。その他の形状・量子化 type ではこの変数による分岐はありません。実装は `iq_dequant_gu_f16_bounded` と `launch_dequant_gu_metadata` です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6502-6534,6537-6557`）。

## 値と判定

対象の値を `std::getenv` で取得し、関数内 `static const bool` に一度だけ保存します。値全体の parse はせず、設定値が存在し、先頭文字が `'1'` の場合だけ有効です（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6547-6549`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| bounded gate/up 経路が呼ばれ、形状が対象と一致 | 無効 | `1`, `1anything` | 空文字、`0`, `0anything`, `true`, `True`, ` 1` |
| `STRATA_SYCL_DEQUANT_GU_BOUNDED` が無効 | この変数を読む分岐に到達しない | 該当なし | 該当なし |

空文字は未設定とは異なりますが、どちらもこの判定では無効です。先頭1文字以降は無視され、大文字小文字・数値としての妥当性・空白の trim は行いません。`'1'` 以外の先頭文字は無効です（同:6547）。

## 有効になる条件

- SYCL の gate/up FP16 IQ dequantization 関数 `iq_dequant_gu_f16` を通ること。同関数は `n_embd` が256の倍数、type が IQ、`tail == nullptr` であることを要求します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6644`）。
- `STRATA_SYCL_DEQUANT_GU_BOUNDED` が `env_on` 判定で有効であること。この helper は未設定・空文字・先頭文字 `'0'` を無効、それ以外の非空値を有効とします（同:3689-3692,6643-6644）。
- bounded 関数が受け付ける範囲内であり、かつ `type == 16`、`n_ff == 640`、`n_embd == 2560` であること。これ以外では bounded の通常分岐に進みます（同:6537-6556）。
- `iq_dequant_gu_f16` で上記の先行条件を満たすこと。条件に違反すると `stderr` に `iq_dequant_gu_f16: type %d / %lld\n` を出して `exit(1)` します（同:6640-6643）。

SYCL の prefill では、少なくとも `f16_pairs` の処理経路と native pack の個別 dequant 経路からこの関数を呼ぶコードがあります。`f16_pairs` の明示条件には type 16/22、down type 42、`n_ff=640`、`n_embd=2560` が含まれます（`sycl/src/prefill/prefill.cpp:4686-4698,4704-4717`）。prompt expert の別経路では XMX grouped kernel が選ばれる場合があり、その場合この dequant 呼び出しを通りません（同:4583-4605）。

## 実行時の詳細

`STRATA_SYCL_DEQUANT_GU_BOUNDED` が有効なときに `iq_dequant_gu_f16_bounded` が呼ばれます。まずサイズ・オーバーフロー条件を検査し、失敗時は `false` を返して呼び出し元の別 kernel 経路へ進みます。検査後に初めて対象変数の static 初期化を行います。対象値が有効で形状も一致すると metadata kernel を起動して `true` を返し、それ以外は type 16/22/29 の通常 bounded kernel を選びます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6557,6643-6649`）。

値はプロセス起動時に必ず読むのではなく、対象の有効な bounded 呼び出しで初めて評価され、その後は関数内 static にキャッシュされます。従って、その初回評価後に環境を変更してもこのプロセス内の判定は変わりません。対象専用 kernel は8 subgroupで実行し、各 subgroup では quartet の先頭レーンだけが metadata word を読み、4レーン単位に共有します（同:6502-6534）。

## ログと測定値

この変数の有効・無効を知らせる専用ログはありません。対象分岐は別 kernel を起動して戻り、ソース上に専用の成功・fallback ログはありません（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:6547-6557`）。上記 `iq_dequant_gu_f16` の引数検査に失敗した場合は記載の stderr と終了があります（同:6640-6643）。

`docs/DETAILS.md` を含む関連資料に、この変数の測定値や出力同一性の確認条件は見つかりませんでした。性能向上や数値結果の同一性はここでは断定しません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:3220-3237` — quartet 単位で metadata word を共有する dequant 処理。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6502-6534` — 対象 kernel と gate/up の出力配置。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6537-6557` — 対象環境変数の読み取り、値の分岐、形状制約、bounded fallback。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:6638-6649` — bounded 経路への入口とその前提。
- `sycl/src/prefill/prefill.cpp:4583-4605,4686-4717` — prefill の dequant 呼び出しと XMX 経路。
- `CMakeLists.txt:23-30` — SYCL は CUDA/HIP と分離した実験的 backend として有効化されます。
