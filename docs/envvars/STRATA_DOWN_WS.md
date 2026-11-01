# `STRATA_DOWN_WS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の実験ビルドで、条件に合う grouped expert の down projection を `native_down_ws_kernel` に切り替えます。このカーネルは down weight の行ブロックを shared memory に読み込んでから処理します。通常の down カーネルを選ぶ箇所に入る前に判定され、条件に合わなければ既存の down 実装へ進みます（`src/kernels/cuda/iq_kernels.cu:6444-6453,6484-6491`）。

## 値と判定

`STRATA_DOWN_WS` は `env_on()` で読み、環境変数が設定されていて、かつ先頭文字が NUL でも `0` でもない場合に有効です。文字列全体の parse はしません（`src/kernels/cuda/iq_kernels.cu:3395-3398`）。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0` または `0` で始まる文字列（例: `0abc`） | 無効 |
| `1`、`true`、`false`、空白で始まる文字列など、空でなく `0` 以外で始まる値 | 有効 |

大文字小文字、後続文字、数値としての妥当性は検査されません。CLI 引数や設定ファイルによる同等の選択肢はこの判定箇所にはなく、別の設定値との優先順位もありません。

## 有効になる条件

値判定が有効でも、次の条件をすべて満たす場合だけ切り替わります。

- CUDA の `STRATA_EXPERIMENTAL_SM60` ビルドであること。HIP、Metal、およびこの macro のないビルドには当該カーネルがコンパイルされません（`src/kernels/cuda/iq_kernels.cu:4305-4311`）。
- 現在の CUDA device の compute capability が **6.0** であること。6.1 や 7.x は対象外です（`src/kernels/cuda/iq_kernels.cu:4573-4582`）。
- grouped expert layout の down 型が IQ4_NL（内部型番号 20）または Q2_0（42）で、`n_ff == 640` であること（`src/kernels/cuda/iq_kernels.cu:4570-4572`; 型名は同ファイル `:1185,1246`）。
- `STRATA_OLD_IQ_MMVQ` と `STRATA_NO_SUB16_GU` がどちらも `env_on()` 判定で無効であること。いずれかが有効ならこの切り替えは行いません（`src/kernels/cuda/iq_kernels.cu:3399-3401,4570-4572`）。

CUDA device の取得に失敗するか、device index が 0–63 の範囲外なら無効になります。compute capability の取得結果が 6.0 以外なら無効です。属性取得の戻り値自体は確認せず、初期値 0 の major/minor が使われます（`src/kernels/cuda/iq_kernels.cu:4573-4582`）。

## 実行時の詳細

本番の verify 処理では、native layout の expert を処理する経路から `native_expert_grouped()` が呼ばれます（`src/core/verify.cpp:2221-2236`）。この関数の down 処理で `down_ws_on(L)` が真なら `launch_down_ws()` を呼び、`check("native_expert_grouped/down ws")` の後に通常の down dispatch を飛ばして戻ります（`src/kernels/cuda/iq_kernels.cu:6448-6453`）。その他の型・条件では通常の dispatch に進みます（同 `:6455-6491`）。同じ grouped 関数はベンチや parity 用ツールからも呼ばれます。

値の判定は `down_ws_on()` 内の関数ローカル `static const bool` に保存され、最初にこの関数へ到達したときに一度だけ評価されます。したがって、その後にプロセス内の環境を変更しても反映されません。GPU 世代の判定も device ごとの `static` 配列に cache されます（`src/kernels/cuda/iq_kernels.cu:4570-4582`）。

この環境変数専用の有効化ログや無効値警告はありません。選択された kernel の起動エラーは `check()` が stderr に `<処理名>: <CUDA error string>` を出して終了コード 1 で終了します（`src/kernels/cuda/iq_kernels.cu:38-41,6451`）。切り替え条件を満たさない場合は警告せず fallback します。

コードコメントは staged カーネルの出力が従来 mode 0 と bitwise 一致すると述べています（`src/kernels/cuda/iq_kernels.cu:4293-4304`）。`docs/OLDER_GPUS.md:164-169` は同じ適用条件と、著者測定による一 token window での kernel 時間を記載しています。これは同文書記載の PH402 die / Swift 1.5 IQ3_S 条件の測定値で、単一カードでの end-to-end 測定ではありません。

## 根拠

- 読み取り API、未設定・空文字・値の判定: `src/kernels/cuda/iq_kernels.cu:3395-3398,4570-4572`
- ビルド macro によるコンパイル条件: `src/kernels/cuda/iq_kernels.cu:4305-4311`
- 型・寸法・デバイス判定と cache: `src/kernels/cuda/iq_kernels.cu:4570-4582`
- verify からの grouped 呼び出し: `src/core/verify.cpp:2221-2236`
- kernel の選択と通常 dispatch への fallback: `src/kernels/cuda/iq_kernels.cu:6444-6453,6484-6491`
- ログ・終了経路: `src/kernels/cuda/iq_kernels.cu:38-41,6451`
- 説明資料: `docs/OLDER_GPUS.md:164-169`
