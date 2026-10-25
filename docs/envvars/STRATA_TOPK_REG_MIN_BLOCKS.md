# `STRATA_TOPK_REG_MIN_BLOCKS`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP 版 QSA の block top-k で、prompt 選択時に register kernel を使う最小の active block 数を決めます。閾値未満なら参照 radix kernel に切り替えます。主に Strix Halo（gfx1151）では起動時に `4096` が既定値として設定され、それ以外の HIP GPU では QSA 実装内の既定値 `7168` が使われます。

## 値と判定

QSA top-k 関数の初回実行時に `std::getenv` の値を `std::atoll` で変換し、関数内 `static const` に保存します。数値全体の厳密な検証や範囲制限はありません。`atoll` が読む先頭の整数部分が閾値となり、数字に変換できない場合は `0` です。末尾の非数字以降は閾値に含まれません。

| 状態 | 判定値 |
|---|---:|
| 未設定（かつ arch default が適用されない） | `7168` |
| 未設定、gfx1151 で arch defaults が適用 | `4096` |
| 明示設定 `4096`, `4096tail` | `4096` |
| 空文字、非数値、`0` | `0` |
| 明示設定 `-1` | `-1` |

空文字や非数値は変数としては設定済みなので gfx1151 の `4096` 注入を妨げ、その後 `atoll` により `0` になります。`STRATA_GFX1151_DEFAULTS=0` を先頭文字判定で設定すると gfx1151 の arch-default 表自体が無効になり、対象変数の明示設定がなければ内部既定値 `7168` が使われます。

## 有効になる条件

- 対象の読み取りと分岐は HIP 用の `__HIPCC__` 経路だけです。CUDA ではこの変数を読みません。
- 閾値比較は `active_blocks > 0` のときだけ有効です。active count がない呼び出しでは閾値は選択に影響しません。
- `STRATA_TOPK_OLD` が設定されている場合は、閾値に関係なく参照 radix kernel を使います。
- HIP では QSA cluster kernel の早期 return はありません。active block 数が閾値未満なら参照 radix kernel、それ以外は geometry 条件と `reach` に応じて register kernel または wide kernel を選びます。
- arch defaults は HIP ビルドで GPU 0 のプロパティ取得に成功した場合に適用されます。gfx1151 では、利用者がこの変数を設定済みなら値を保持します（空文字も設定済み）。gfx12 の arch-default 表にはこの変数は含まれません。

## 実行時の詳細

通常の prefill selection は batch 内の最終 query の `n_bid + 1` を `active_blocks` として `qsa_block_topk` に渡します。HIP 側ではこれを `reach` とし、`reach < STRATA_TOPK_REG_MIN_BLOCKS` なら `qsa_block_topk_ref` に戻ります。`reach` が閾値以上なら、register kernel の処理可能範囲と `STRATA_TOPK_STREAM` などの別条件を使って後続 kernel を選びます。この変数自体は選択 cell の値を変える計算ではなく、kernel dispatch の閾値です。

`static const` の値は最初に関数が評価された時点で固定され、同一プロセス内での後の環境変更は反映されません。gfx1151 の arch default はそれより前、引数処理後の起動時に GPU 0 を調べて設定されます。対象変数専用のログはありませんが、arch default が注入された場合は起動時の一覧ログに `TOPK_REG_MIN_BLOCKS` が含まれます。

## 文書との照合

`docs/STRIX_HALO.md` は gfx1151 で `4096` を使い、register kernel の開始点を context 16K 相当（通常の閾値 7168 は約 28K 相当）に下げる説明をしています。同文書は対象の測定値と同一 cell 選択を記していますが、この調査では測定や parity test を再実行していません。

## 根拠

- `src/kernels/cuda/qsa_select.cu:2495-2510,2521-2555,2561-2584` — HIP/CUDA 分岐、変換、既定値、閾値分岐、後続 kernel dispatch。
- `include/strata/kernels/qsa_select.hpp:62-70` — `active_blocks` の契約。値が正なら query の block 上限として渡される。
- `src/prefill/prefill.cpp:3147-3162` — prompt で batch の active block 数を算出して渡す箇所。
- `src/program/generate.cpp:2641-2648` — HIP 起動時に GPU 0 を確認して arch defaults を適用。
- `src/core/arch_defaults.cpp:12-34,43-47,62-80` — gfx1151 で `4096` を既定設定し、既存環境値を保持する処理。gfx12 表には対象変数がない。
- `docs/STRIX_HALO.md:83-96` — gfx1151 の設定と記載された動作・測定の照合。
