# `FNX_PF_GDN_CHUNK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split` の prompt 処理で、GDN（recurrent layer）の recurrence に使う CUDA/HIP kernel 経路を選びます。既定および `1` は 32 行単位の sub-chunk 経路、`0` は行を順に処理する recurrence 経路です。これは Strata の通常の `strata` 実行エンジン全体に適用される設定ではありません。`strata-split` は `STRATA_BUILD_SPLIT=ON` のときだけ追加される別 executable です（`CMakeLists.txt:2945-2949`、`src/split/CMakeLists.txt:1-7`）。

## 値と判定

| 値 | 判定 |
| --- | --- |
| 未設定 | sub-chunk 経路を選ぶ（既定 ON） |
| `1` | sub-chunk 経路を選ぶ |
| `0` | 行ごとの recurrence 経路を選ぶ |
| 空文字、`01`、`true`、` 1`、`1 ` など | 無効値として例外 |

数値変換はせず、`strcmp` で文字列全体を `"0"` または `"1"` と比較します。空白除去、大文字小文字変換、部分一致はありません。無効値では `FNX_PF_GDN_CHUNK: 0 or 1, not '<値>'` という `std::runtime_error` を投げます。CLI 引数、設定ファイル、別環境変数による上書きや優先順位は、この変数の読み取り経路にはありません。

根拠: `src/split/src/kernels.cu:1986-1990`。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で split engine がビルドされること。CMake は Linux の CUDA または HIP ビルドに限って split engine のソースを追加し、HIP 時は同じ kernel ソースを HIP としてコンパイルします（`CMakeLists.txt:2945-2949`、`src/split/CMakeLists.txt:20-30,64-89`）。
- split engine の prompt 処理が recurrent layer に到達すること。呼び出し元は `!is_attn(l)` の分岐で `gdn_prompt()` を呼びます（`src/split/src/prefill.cu:1197-1205`）。attention layer では呼ばれません。

環境変数の値は `gdn_prompt()` の関数内 static 値として初回呼び出し時に読み取られます。有効値を読んだ後にプロセスの環境を変更しても選択は再評価されません。`FNX_PF_GDN_CHECK` は別の診断用分岐で、sub-chunk 経路が選ばれた場合に限って有効です。この変数を設定しても `FNX_PF_GDN_CHUNK` の選択自体は変わりません（`src/split/src/kernels.cu:2000-2009`）。

## 実行時の詳細

`gdn_prompt()` は先に convolution と history の kernel を enqueue し、その後に `FNX_PF_GDN_CHUNK` を判定します。sub-chunk 経路では必要な dynamic shared memory を設定し、`k_gdn_ch_prep` と `k_gdn_ch_rec` を起動してから `k_gdn_pf_norm_own` で出力を正規化します。もう一方の経路では `k_gdn_pf_rec` と `k_gdn_pf_norm` を使います（`src/split/src/kernels.cu:1982-1999,2017-2037`）。sub-chunk 用の一時領域は `prefill.cu` で確保され、`gdn_prompt()` に渡されます（`src/split/src/prefill.cu:332-334,677-684,1200-1205`）。sub-chunk の定数 `GCH` は 32 です（`src/split/src/gdn_prompt.cuh:166-177`）。

無効値の例外は `srv.run()` から上位へ伝播します。`sfnx` の失敗処理はプロトコル出力に `ERR <内容>`、stderr に `sfnx: failed: <内容>` を出し、終了コード 1 でプロセスを終了します（`src/split/tools/sfnx.cpp:1027-1035,1086-1092`）。この変数専用の警告ログや fallback はありません。なお値の判定より前に convolution/history kernel が enqueue 済みですが、無効値では recurrence 経路の選択・起動には進みません（`src/split/src/kernels.cu:1982-1990`）。

## 根拠

- `CMakeLists.txt:2945-2949`、`src/split/CMakeLists.txt:1-7,20-30,64-89` — split engine のビルド条件と CUDA/HIP ソース。
- `src/split/src/prefill.cu:1197-1205` — recurrent layer からの呼び出し。
- `src/split/src/kernels.cu:1979-2039` — 値の検査、既定値、cache、2 つの kernel 経路。
- `src/split/src/gdn_prompt.cuh:155-177` — sub-chunk recurrence と行幅の実装注釈・定数。
- `src/split/tools/sfnx.cpp:1027-1035,1086-1092` — 実行中例外のプロトコル出力、stderr、終了経路。

`docs/DETAILS.md` と `docs/SPLIT_ENGINE.md` にはこの環境変数の個別説明は見つかりませんでした。性能値や両経路の数値的一致は、この文書では主張していません。
