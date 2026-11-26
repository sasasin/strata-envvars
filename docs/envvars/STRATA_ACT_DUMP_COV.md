# `STRATA_ACT_DUMP_COV`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU native expert の活性値 dump に、各ベクトルの二次モーメント行列（`sum x_i x_j`）を追加します。対象変数だけでは dump は始まらず、`STRATA_ACT_DUMP` に空でない出力 prefix と `STRATA_ACT_DUMP_LAYERS` に層指定が必要です。共分散の記録は `native_quant_act` / `native_quant_h` が呼ばれる native expert 経路で行われます。記録対象は gate/up 入力と down 入力で、Hadamard-folded 層では量子化に使う回転後ベクトルを記録します（`engine/src/kernels/cpu/native_expert.cpp:432-436, 514-537`）。

この値は記録・ファイル出力を増やすだけで、活性値の量子化結果や expert の選択を変更する分岐はありません（同 `:488-510, 514-537`）。

## 値と判定

`ActDump` の初期化時に、まず `STRATA_ACT_DUMP` が未設定または空文字ならそこで初期化を終え、この変数は読まれません。空でない prefix がある場合は `getenv(...) != nullptr && atoi(...) != 0` で判定します。したがって文字列全体の妥当性は検証せず、`atoi` が先頭から変換した整数が 0 かどうかで決まります（`engine/src/kernels/cpu/native_expert.cpp:449-454`）。

| 条件 | unset | 共分散を有効にする値 | 共分散を無効にする値 |
|---|---|---|---|
| `STRATA_ACT_DUMP` が未設定または空 | 無効。対象変数は読まれない | なし | なし |
| prefix が空でなく、`STRATA_ACT_DUMP_LAYERS` の解析結果が空でない | 無効 | `1`, `+1`, `-1`, ` 1`, `1x`（`atoi` の結果が非 0） | 空文字、`0`, `0anything`, `true`, `false`, `x1`（`atoi` の結果が 0） |

先頭の空白と符号は `atoi` の変換対象となり、数値以降の文字列は検査されません。負数も 0 以外なら有効です。値の範囲チェックやエラー処理はありません（同 `:453`）。ただし層指定がない場合は `on` が false のままなので記録されず、共分散 dump も発生しません（同 `:454-465, 488-490`）。

## 有効になる条件

- ビルドに `native_expert.cpp` が含まれ、native expert の活性量子化関数が使われることが必要です。通常の engine 構成では `STRATA_NATIVE_EXPERTS` が ON のとき `strata_cpu_native_experts()` がこのソースを追加します（`engine/CMakeLists.txt:725-736`、`engine/cmake/backends/cpu.cmake:303-308, 370`）。OFF の build ではこの実装がありません。
- 実行時には `STRATA_ACT_DUMP` が空でないことと、`STRATA_ACT_DUMP_LAYERS` が少なくとも 1 要素に解析されることが必要です。層指定に一致した活性だけが記録されます（`engine/src/kernels/cpu/native_expert.cpp:450-465, 488-490`）。層指定はカンマ区切りで各要素を `atoi` 変換するため、不正な要素も 0 になります（同 `:454-463`）。
- GPU engine でも CPU に割り当てられた native expert の活性を `native_quant_act` に渡す経路があります。一方、同じ箇所でも `q2` 経路は `act_quant_any` を使うため、この dump 関数を通りません（`engine/src/prefill/prefill.cpp:6281-6297`）。したがって GPU の有無だけでは有効性は決まらず、該当する CPU native expert 経路に入る必要があります。
- `STRATA_ACT_DUMP_COV` だけを設定しても prefix または層指定の条件を満たさなければ機能しません。CLI による優先順位や上書きはこの実装にはありません。

## 実行時の詳細

`act_dump()` の関数内 static ポインターが `ActDump` を最初に一度だけ生成します。初期化時に prefix、共分散設定、層リストを読み、記録が有効なら `atexit` に flush を登録します。そのため環境を最初の `native_quant_act` / `native_quant_h` 呼び出し後に変更しても、このプロセス内の判定には反映されません（`engine/src/kernels/cpu/native_expert.cpp:449-471, 514-537`）。

記録時にはベクトルの各要素の二乗和を累積し、共分散が有効なら全ての組 `(i,j)` の積も `double[n*n]` に累積します。ファイル名は `<prefix>_L<層番号>_gu.bin` または `_dn.bin` で、データは `int64 n`、`int64 count`、`double sum(x²)[n]`、共分散有効時は続けて `double sum(x_i*x_j)[n*n]` です（同 `:473-485, 488-505`）。

共分散有効時は記録 400,000 件ごと、無効時は 2,000 件ごとに flush を試み、終了時にも flush します。ファイルは `.tmp` に書いてから本名へ rename します（同 `:465, 473-486, 506-510`）。出力先を開けない場合はそのファイルの flush を飛ばし、`fwrite` / `rename` の失敗も明示的には処理しません（同 `:477-486`）。

## ログと測定値

この dump 実装による有効化ログ、警告、失敗ログはありません。出力ファイルが作られない場合でも、`fopen` 失敗は無言で継続します（`engine/src/kernels/cpu/native_expert.cpp:473-486`）。コメントは共分散を有効にした際にフル共分散を追加すると説明していますが、ソース上の flush 間隔は共分散有効時 400,000 件です（コメント `:432-436`、実装 `:506-510`）。性能測定値は該当資料で確認できませんでした。

## 根拠

- 読み取りと初期化条件、static cache: `engine/src/kernels/cpu/native_expert.cpp:449-471`
- 活性記録・共分散計算・flush 間隔: 同 `:488-510`
- 呼び出し位置と量子化前の記録: 同 `:514-537`
- native expert ソースの build 条件: `engine/CMakeLists.txt:725-736`、`engine/cmake/backends/cpu.cmake:303-308, 370`
- CPU 割り当て expert と `q2` の分岐: `engine/src/prefill/prefill.cpp:6281-6297`

候補名の全参照も確認しました。実行時の環境読み取りは `native_expert.cpp:453` のみです。`terminal/data/settings-register.json:60-95` は候補情報、`terminal/tools/trellis/build_swap.py:11, 66-74` は説明文と dump ファイル検査であり、この変数を環境から読む実装ではありません。
