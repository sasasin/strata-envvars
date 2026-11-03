# `DS4_LANE_CAL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek V4.1 の GGUF 実行経路にある PCIe lane の測定値・判定を保存するファイルを指定します。保存値は次回以降の起動で読み直され、CPU lane と PCIe 経由で GPU が処理する lane の分担計画、ならびに前回その GPU では streaming しなかったという判定に使われます。変数自体は streaming を有効化するスイッチではありません。

## 値と判定

| 環境値 | 使用するファイル／動作 |
|---|---|
| 未設定 | `<pack>/lane-times.txt`。pack 内の測定値・判定を読み書きする |
| 空文字 | 空のファイル名となり、過去値を読まず、保存もしない |
| 正確に `none` | 空のファイル名となり、過去値を読まず、保存もしない |
| その他 | 値をそのままファイル名として使う。相対パスはプロセスの作業ディレクトリ基準 |

`none` の比較は大文字小文字を区別する文字列全体の一致です。空白除去やパス正規化はありません。したがって `NONE` や `none ` は通常のファイル名です。数値変換、値域検査、無効値時の fallback はありません。CLI 引数による上書きもありません。値を読み取るのはモデルロード中で、`lane_file()` は static cache せず呼び出されます。lane の確保時に得たパスは `ln_file` に保持され、その実行中の後続保存にも使われます。

## 有効になる条件

- ファイルの測定値を PCIe lane が読むのは、GGUF、`DS4_STREAM` または fallback の `STRATA_DS4_STREAM` が有効、MoE token path、同期 decode でない、対象 GPU/layer に lane 用の空きがある場合です。`DS4_STREAM` が未設定または `atoi` で 0 になる値なら lane allocation は行われません（`src/dsv41/ds4_model.cu:9711-9719,9753-9755`）。
- 対象 layer は MTP でなく、`nm == 1`、MXFP4、`0 < k_exp <= kPicks` などの条件を満たす必要があります。全 expert が VRAM に収まる場合や必要な device/pinned memory を確保できない場合も lane は使われません（`src/dsv41/ds4_model.cu:9721-9725,9763-9775,10429-10431`）。
- CUDA の NVIDIA 単一 discrete GPU 経路では、初期化時にも同ファイルの GPU lane 判定を読みます。`DS4_STREAM_FORCE` が未設定で、レコードが `off` なら one-GPU decode path を初期状態から無効にします。ここでは空文字でも環境変数が設定済みなら `off` 判定を避けます。HIP build ではこの初期判定のコードは `#if !defined(STRATA_USE_HIP)` の内側ですが、後段の lane setup による測定値の読み書きは同じソースにあります（`src/dsv41/ds4_model.cu:6104-6127`）。
- `DS4_STREAM_FORCE` が非空なら lane 判定レコードによる allocation 抑止を避け、個別測定値を読み込まず、測定値・GPU lane 判定も保存しません。空文字の場合はこの後段の cache 制御では空値扱いです（`src/dsv41/ds4_model.cu:6120-6121,9755-9756,9775,10522,10584,10619-10631`）。

## 実行時の詳細

起動時、CUDA の one-GPU 判定は `lane_file()` の値が空でない場合に GPU lane の `off` レコードを確認します。通常の lane setup では、GPU と format/thread/readers の組み合わせから作った完全一致キーのレコードを読みます。レコードは `key<TAB>values` 形式です。値は `sscanf` で最大 11 個の数値項目に読み込まれ、少なくとも最初の 7 項目が読めて `c > 0` と `p > 0` なら候補になります。保存値を無条件に採用せず、3 expert 分の CPU/stream 時間を再測定し、両方が保存時の予測値の約 `1/1.35`〜`1.35` 倍に収まる場合だけ再利用します。そうでなければ「do not hold now ... - timed again」と stderr に出して再測定します（`src/dsv41/ds4_model.cu:10515-10553`, `src/dsv41/ds4_pcie.hpp:18-24`）。

cache miss、空値、不正な値、ファイルを開けない場合は再測定経路に進みます。測定成功時は値を保存し、実行中の decode 測定で lane の判定・cost が変わったときも更新します。GPU の全 class が streaming しない判定になれば `| lane` レコードに `off` を保存し、次回起動の CUDA one-GPU 判定や lane allocation に反映します（`src/dsv41/ds4_model.cu:10137-10147,10251-10263,10581-10589,10616-10633`）。

読み取りでファイルを開けないこと自体はエラー表示されず、cache miss と同様に扱います。書き込みも一時ファイル `<file>.tmp` を作り置換を試みますが、open/write/replace の失敗を呼び出し元へ返さず、明示的な失敗ログもありません（`src/dsv41/ds4_pcie.hpp:97-109,112-128`; 呼び出し側 `src/dsv41/ds4_model.cu:9743-9747`）。lane の測定自体に失敗した場合は stderr に `ds4: PCIe lane: CUDA%d %s: timing failed - the CPU lane alone` を出し、その class は CPU lane のみになります（`src/dsv41/ds4_model.cu:10555-10589`）。lane が使える場合の最終ログには layer/GPU 数、reader 数、測定値を使ったかどうかが出ます（`src/dsv41/ds4_model.cu:10635-10642`）。

## 根拠

- 環境値の読み取りと既定値・`none` 判定: `src/dsv41/ds4_model.cu:6099-6102`
- 起動時の GPU lane `off` 判定と CUDA 条件: `src/dsv41/ds4_model.cu:6104-6127`
- lane allocation 条件とファイルパスの保持: `src/dsv41/ds4_model.cu:9711-9719,9743-9756`
- cache のキー、再利用条件、再測定とログ: `src/dsv41/ds4_model.cu:10515-10589`
- lane 判定の保存・実行中更新: `src/dsv41/ds4_model.cu:10137-10147,10251-10263,10616-10642`
- cache のファイル形式と best-effort 読み書き: `src/dsv41/ds4_pcie.hpp:95-128`
