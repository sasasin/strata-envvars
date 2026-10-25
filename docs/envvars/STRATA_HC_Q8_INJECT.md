# `STRATA_HC_Q8_INJECT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_HC_Q8=1` で有効になる hyper-connection の Q8_0 verify read に、GGUF 内で F32 として保存された `_inject.weight` 行の Q8_0 コピーも渡します。未設定または無効なら、inject 行は既存の BF16 重みを使います。この変数単独では Q8 read を有効にしません。

## 値と判定

| 値 | 判定 |
|---|---|
| unset、空文字、先頭文字が `1` 以外 | OFF |
| 先頭文字が `1` | ON（例: `1`, `10`, `1anything`） |

文字列全体や数値としての妥当性は検査せず、先頭文字だけを大文字小文字区別ありで比較します。値を読む箇所は関数内 static の bool なので、`NativeDense::load()` の該当ループが初めて実行された時点で一度だけ評価され、その後のプロセス内の環境変更は反映されません。なおこの読み取りは `STRATA_HC_Q8` が有効で、GGUF shard を走査する分岐に入った場合にだけ行われます（`src/core/native_dense.cpp:323-328`）。

## 有効になる条件

- `NativeDense::load()` が実行されること。エンジンでは `--native-dense-gguf` を指定する経路でロードされます（`src/program/generate.cpp:1878,3028-3031`）。
- `STRATA_HC_Q8` が先頭文字 `1` で有効になっていること。こちらが無効なら inject 変数の判定・処理まで到達しません（`src/core/native_dense.cpp:40-43,323-328`）。
- shard に `hc_q8_name()` が認める F32・2次元テンソルがあること。F32 からの変換対象は `blk.*.hc_attn_inject.weight` と `blk.*.hc_ffn_inject.weight` に該当する名前です。`output_hc_down/up.weight` は関数が名前として許可しますが、`_inject.weight` ではないためこの変数による F32 変換対象ではありません（`src/core/native_dense.cpp:45-51,328-330`）。
- 対応する weight table entry があり、まだ `hc_q8` コピーが登録されていないこと。行幅 `ne0` は32の倍数で、GGUF shape は weight table の次元と一致する必要があります。違えば load は `native dense (STRATA_HC_Q8): incompatible matrix <name>` で失敗します（`src/core/native_dense.cpp:330-345`）。

既に GGUF に Q8_0（tensor type 8）で格納された hyper-connection projection は、この変数が OFF でも `STRATA_HC_Q8` の処理対象です。この変数が追加する対象は F32 の inject tensor です。

## 実行時の詳細

有効時は各32要素ブロックについて最大絶対値を127で割った scale を作り、scale を half にして、各値を scale で割って `lround` した int8 にします。34 byte/ブロックの Q8_0 データを CUDA device memory に割り当ててコピーし、該当 weight の `hc_q8` として登録します。割り当て・転送に失敗すると load は `native dense (STRATA_HC_Q8) upload <name>` のエラーで失敗します（`src/core/native_dense.cpp:53-87,336-347`）。

Verifier は hyper-connection の fused read 引数にこのポインタを渡します（`src/core/verify.cpp:1053-1072`）。down/up の Q8 コピーが両方そろっていれば CUDA 側は Q8 read kernel を起動し、inject の Q8 コピーがある場合はその行も Q8_0 から読みます。ポインタがない場合は pack の BF16 inject 重みを使います（`src/kernels/cuda/fused_gr.cu:1377-1383,1855-1863`）。つまり有効化により注入 projection の重み表現が変わり、演算結果に影響し得ます。

ソースには有効時の Q8_0 hyper-connection 重み総量を stderr に出す処理がありますが、ログは `STRATA_HC_Q8=1` の表示であり、inject 変換だけの件数・容量は別途出しません（`src/core/native_dense.cpp:377-381`）。`docs/STRIX_HALO.md` は `STRATA_HC_Q8` を既定で有効にしない、丸めが変わる実験設定に列挙していますが、`STRATA_HC_Q8_INJECT` 単独の測定値や品質評価は記載していません（`docs/STRIX_HALO.md:100-115`）。

## 根拠

- 環境変数判定と型・名前フィルター: `src/core/native_dense.cpp:323-334`
- F32 からの Q8_0 変換、device copy、登録: `src/core/native_dense.cpp:53-87,336-347`
- verify 引数への伝達と CUDA read 経路: `src/core/verify.cpp:1053-1072`, `src/kernels/cuda/fused_gr.cu:1377-1383,1855-1863`
- 関連設定の資料上の位置づけ: `docs/STRIX_HALO.md:100-115`
