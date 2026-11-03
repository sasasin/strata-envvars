# `QA_MASK_PAGES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL 版 `qsa_prompt_attn_parity` が使う合成 page table に無効ページを作り、QSA prompt attention の parity 比較へ欠損ページを含めるための QA 用入力です。通常の `strata` 実行時設定としては参照されていません。リポジトリ全体の完全一致検索で環境から値を読む箇所は `sycl/src/kernels/qsa_prompt_attn_parity.cpp:124` のみです。

この parity 実行ファイルは `STRATA_SYCL_PARITY` が有効なときのテスト群に登録されています（既定値は ON）。通常のエンジンとは別の実行ファイルです（`sycl/CMakeLists.txt:288-291,413-418`）。

## 値と判定

変数の設定有無だけを確認します。数値変換や CLI 引数との優先順位はありません。

| 値 | page table への処理 |
|---|---|
| 未設定 | 変更しない |
| 完全一致で `all` | 全 page table entry を `-1` にする |
| 上記以外の設定値 | entry の位置 `i` が `i % 7 == 0` のものを `-1` にする |

文字列全体を `strcmp(mask, "all")` で比較するため、大文字小文字や前後の文字は一致しません。たとえば `ALL`、`all `、`1`、空文字はすべて「設定済みだが `all` ではない」扱いで、7 件ごとの位置を無効化します。ページ数を `pages` とすると対象位置は 0, 7, 14, … であり、個数は `ceil(pages / 7)` です。

## 有効になる条件

- `sycl/src/kernels/qsa_prompt_attn_parity.cpp` から作られた `qsa_prompt_attn_parity` を実行すること。SYCL CMake の parity 群は `STRATA_SYCL_PARITY` が真のときに構成され、同プログラムは CTest にも登録されています（`sycl/CMakeLists.txt:288-291,413-418`）。
- 各 `run()` 呼び出しで、合成 table を作成・shuffle した後に環境変数を評価します。設定値を別の通常 CLI 引数が上書きする処理はありません（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:121-128,455-494`）。

候補一覧の同名項目は、Strata 全体で共通のランタイム機能を意味しません。CUDA parity 用の `src/kernels/qsa_prompt_attn_parity.cpp` は別ファイルであり、この名前を読みません。SYCL parity ソース以外に完全一致の環境読み取りはありません。

## 実行時の詳細

`run()` はコンテキスト長と QSA 形状から page 数を求め、連番の合成 page table を shuffle します。その後 `std::getenv("QA_MASK_PAGES")` を呼び、上記規則で entry を `-1` にします。処理した table は device へ転送され、旧 batched attention、prompt batched attention、および per-cell 経路の比較に渡されます（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:85-88,121-128,249-287`）。環境変数の値自体は保存・cache されず、プロセス内で `run()` が呼ばれるたびに読みます。起動後に値を変更した場合の動作は、この実行ファイル内で環境を変更する処理がないため確認対象外です。

同ファイルの FP64 参照計算では、page table entry が負なら score を `-INFINITY` とし、そのページの value 寄与を飛ばします（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:311-346`）。これは parity ハーネス側の参照計算です。GPU kernel 内部の無効ページ処理をこの環境変数の説明として一般化しません。

変数専用の警告・エラー出力はありません。parity 比較の結果は `PASS` / `FAIL` 行と `FAILURES: n` に現れ、最後に失敗数が終了コードとして返ります（`sycl/src/kernels/qsa_prompt_attn_parity.cpp:401-435,451,482-494`）。

## 根拠

- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:121-128` — table の初期化、shuffle、環境変数の読み取り、値判定と `-1` 設定。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:249-287` — table 転送と比較対象の呼び出し。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:311-346` — parity ハーネス内の FP64 参照で無効ページを扱う箇所。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:401-435,451,482-494` — 比較結果の表示と終了コード。
- `sycl/CMakeLists.txt:288-291,413-418` — SYCL parity 群とテスト登録。
- `src/kernels/qsa_prompt_attn_parity.cpp:1-11`、`CMakeLists.txt:541-547` — CUDA parity は別ソースを使い、この変数を参照しないこと。
