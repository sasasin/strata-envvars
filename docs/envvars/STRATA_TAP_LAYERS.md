# `STRATA_TAP_LAYERS`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

`STRATA_TAP_FILE` に verifier の中間層出力を記録するとき、記録対象にする層番号を指定します。層番号は 0 始まりで、最終層を除きます。この変数だけでは記録を有効にしません。`STRATA_TAP_FILE` が未設定または空文字なら研究用ファイル出力は無効で、この変数も読み取られません。

DFlash2 drafter の通常経路は `Verifier::set_taps()` で対象層を渡します。その場合、`STRATA_TAP_FILE` が設定されていなければ、その API から渡された層が使われ、`STRATA_TAP_LAYERS` は参照されません。ファイル出力と DFlash2 を同時に有効にした場合は、ファイル出力側の環境変数リストが層を決めます。

## 値と判定

値はカンマ区切りとして分割され、各要素を C の `atoi()` で整数化します。文字列全体の厳密な数値検証はありません。

| `STRATA_TAP_FILE` | `STRATA_TAP_LAYERS` | 結果 |
|---|---|---|
| 未設定または空文字 | 任意 | ファイル出力は無効。この変数は読まれない |
| 空でない | 未設定または空文字 | `5,15,25,35,45` を使用 |
| 空でない | 空でない | カンマで分割し、各要素を `atoi()` で変換して範囲内の層だけ採用 |

採用条件は `0 <= layer < n_layers - 1` です。範囲外の値は捨てられます。`atoi()` のため、先頭空白や符号は受け付け、数値以降の文字列は無視します。数値に変換できない要素は `0` になるので、モデルに 2 層以上あれば `x` や空の要素も層 0 として採用されます。例えば `5abc, 15,-1,999` は、層数が十分あるモデルでは 5 と 15 が採用され、-1 と範囲外の 999 は捨てられます。連続するカンマの間にある空要素も `atoi("") == 0` として扱われます。

要素の順序と重複は除去されません。ヘッダーには採用した各層が入力順で書かれますが、層からバッファ位置への対応表は後の同じ層で上書きされます。そのため重複層は記録スロットを余分に確保し、先行する重複スロットは使われません。

## 有効になる条件

- verifier が全層を担当している必要があります（`lb_ == 0 && le_ == g.n_layers`）。layer split の途中段では tap の初期化を行いません。
- `STRATA_TAP_FILE` に空でないパスを設定する必要があります。ファイルを開けない場合、`verify: cannot write STRATA_TAP_FILE <path>` で初期化に失敗します。
- 採用層が 0 個の場合はバッファ初期化失敗として扱われ、`verify: the DFlash2 tap buffers could not be allocated` で初期化に失敗します。
- 既定層がモデルの層数を超える場合、その層は範囲外として捨てられます。結果的に対象層が残らなければ初期化に失敗します。
- tap は verifier の窓処理に属します。通常の DFlash2 利用時は、ビルドが DFlash2 を含み `--draft dflash2` が選ばれたとき、`generate` が drafter の層を `set_taps()` に渡します。これは `STRATA_TAP_LAYERS` の設定とは別経路です。

## 実行時の詳細

`Verifier::init()` が `STRATA_TAP_FILE` を読み、値が空でなければ `STRATA_TAP_LAYERS` を一度読みます。対象層リストはその verifier インスタンスの初期化時に確定します。実行中の環境変更では変わらず、新しい verifier を初期化すればその時点の環境が使われます。

初期化時に対象層のバッファを確保し、ファイルを `wb` で開きます。ファイル先頭には int32 のヘッダー（magic `STAP`、version `1`、埋め込み次元数、対象層数）と、対象層番号の配列を書きます。各 verifier window の各行について、対象層の完了出力（residual に FFN の書き込みを反映し、hyper-connection stream の平均を取った値）を GPU 上で集めます。window 完了後、各行の位置と入力 token に続けて対象層の float 値をファイルへ書き、flush します。batch recording 中は tap のコピーとファイル記録を行いません。

初期化成功時には stderr に `strata: STRATA_TAP_FILE <path>: <n> taps of <N> floats per row` が出ます。各層のデータ定義とファイル形式は `docs/STRATA_TAP_FILE.md` も参照してください。

## 根拠

- `src/core/verify.cpp:785-820`: `STRATA_TAP_FILE` と `STRATA_TAP_LAYERS` の読取条件、既定値、分割、`atoi()`、範囲フィルター、重複保持、確保失敗、ファイルヘッダーと初期化ログ。
- `src/core/verify.cpp:2203-2216,2345-2346,3198-3200`: 対象層の完了出力の取得、window 後の mapped copy、ファイル記録の呼び出し。
- `src/core/verify.cpp:664-674`: 行ごとの位置・token・tap 出力と flush。
- `include/strata/core/verify.hpp:326-331,566-578`: API からの層指定と tap バッファの役割。
- `src/program/generate.cpp:16136-16139,16148-16165`: DFlash2 経路が `set_taps()` を呼び、tap が使えなければ MTP に戻る処理。
- `CMakeLists.txt:333-340`: DFlash2 は CUDA/HIP の GPU runtime build に含まれ、Metal/SYCL build には含まれない旨。
- `docs/DETAILS.md` にこの環境変数の独立した説明や測定値は見つからなかった。性能・正確性に関する測定値は記載していない。
