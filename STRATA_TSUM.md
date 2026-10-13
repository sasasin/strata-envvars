# `STRATA_TSUM`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

対応する GPU カーネルの warp 内 reduction を、複数の値をまとめて処理する transposed butterfly に切り替えます。ソースでは通常の reduction と同じ値になる設計とされています。環境変数は、その方式を使う分岐を選ぶもので、すべての演算やモデルで使われる設定ではありません。

CUDA/HIP 共通ソースでは native MMVQ、BF16 multi-row GEMV、fused grouped Q8 expert、および一部の grouped expert カーネルに分岐があります。SYCL の移植ソースでは native MMVQ と BF16 multi-row GEMV に読み取りがあります。`docs/STRIX_HALO.md` も grouped decode experts の説明と並べて「single-butterfly warp sums」と記載しています（`docs/STRIX_HALO.md:96`）。

## 値と判定

カーネル側の全読み取りは `getenv()` の戻り値が存在し、先頭文字が `'1'` かを判定します。文字列全体の parse はしません。

| 値 | カーネル側の判定 |
|---|---|
| 未設定 | 無効。ただし下記の gfx1151 既定値適用時を除く |
| 空文字 | 無効（値は存在するが先頭文字は `\0`） |
| `1`、`10`、`1abc` | 有効（先頭が `1`） |
| `0`、`true`、空白始まりの値など | 無効（先頭が `1` ではない） |

gfx1151 用の既定値処理は、環境変数が**未設定**のときだけ `STRATA_TSUM=1` を設定します。ユーザーが空文字や `0` など何らかの値を設定していれば、その値を保ちます。したがって、gfx1151 では未設定が有効扱いになりますが、明示した空文字は無効です。

## 有効になる条件

- 既定値の自動設定は HIP ビルドに限られます。`generate` 起動時に GPU 0 の arch 名を取得できた場合、gfx1151 用の switch 表を適用します。CUDA ビルドはこの処理を呼ばず、gfx12 用の表にも `STRATA_TSUM` は含まれません。
- gfx1151 の既定値群は `STRATA_GFX1151_DEFAULTS` の先頭文字が `0` の場合に適用されません。表の値を設定する際も、既に存在する環境変数は値にかかわらず上書きしません。
- 各カーネル側では値を関数内 `static` に保存します。最初の該当呼び出し後にプロセス環境を変更しても、その読み取り箇所の判定は変わりません。既定値設定はエンジン処理が switch を初回読み取りする前に行われます。
- 各経路には別途の条件があります。たとえば BF16 multi-row GEMV は `STRATA_MMVF_ROWS` が有効で、`n_out >= 64` のときに rows カーネルへ進みます。MMVQ の通常の multi-column 経路は exact layout を使うときに対象で、`STRATA_NO_MMVQ_ROWS2` が有効な場合は入力サイズに応じて1行または2行の構成になります。Q8/Q6 packed 経路は、それぞれの packed 機能が選択され、shape と registry 条件を満たす必要があります。
- grouped expert の `STRATA_EXPERT_V2` 経路は gate/up type 21、down type 20、`n_embd=2560`、`n_ff=640` の場合にのみ TSUM 判定を使います。`STRATA_EXPERT_V2K` 経路は gate/up type 12 または13、down type 7 または8、同じ埋め込み・FFN サイズの場合に TSUM 判定を使います。その他の grouped expert 形式ではこの2つの分岐に入りません。
- SYCL の移植ソースは native MMVQ / BF16 multi-row GEMV でこの変数を読みますが、SYCL の grouped expert ソースには `STRATA_TSUM` の読み取りがありません。CUDA/HIP の grouped expert / fused GR と同じ適用範囲とは確認できません。

## 実行時の詳細

native MMVQ では、multi-column kernel の template 引数 `TS` を切り替えます。TS 有効時は各 warp の部分和を shared memory から集約した後、transposed butterfly で列ごとの和をまとめます。Q8 packed、Q6 packed、Q8 pair の対応経路も同じ判定 helper を使います。無効時は従来の `warp_sum` 経路です。

BF16 multi-row GEMV では `launch_rows` が `TS` template 引数の kernel を選びます。fused GR の Q8 経路は down/up kernel の両方を TS 版に切り替えます。grouped expert の2分岐も、TS が有効なら TS 対応の launch template を選び、無効なら従来版を選びます。これらは起動カーネルの選択を変えるための判定で、変数自体を出力する専用ログは見つかりませんでした。

## 根拠

- 既定値表と「gfx1151 のみ」「既存設定優先」「設定ログ」: `src/core/arch_defaults.cpp:12-35,45-58,61-80`。gfx1151 用の表に `STRATA_TSUM=1` があり、gfx12 表は別の5変数のみです。
- HIP の起動時適用位置: `src/program/generate.cpp:2152-2158`、`sycl/src/program/generate.cpp:1970-1976`。どちらも device properties 取得成功時に `apply_arch_defaults()` を呼び、直前に switch は初回使用時に読む旨が記されています。
- native MMVQ の読み取りと multi-column 分岐: `src/kernels/cuda/native_mmvq.cu:1156-1160,1261-1290`。packed 経路: `src/kernels/cuda/native_mmvq.cu:1771-1780,1907-1915`。Q8 pair: `src/kernels/cuda/native_mmvq.cu:2406-2415`。SYCL native MMVQ の読み取り: `sycl/src/kernels/cuda/native_mmvq.dp.cpp:1355-1359`。
- BF16 rows 経路と別スイッチ・shape 条件: `src/kernels/cuda/native_bf16.cu:231-251,269-319`。SYCL の読み取り箇所: `sycl/src/kernels/cuda/native_bf16.dp.cpp:322`。
- fused GR の TS 版 kernel 選択: `src/kernels/cuda/fused_gr.cu:1560-1571,1786-1808,1857`。
- grouped expert の両条件付き分岐: `src/kernels/cuda/iq_kernels.cu:3451-3490`。同ファイルの周辺実装が native grouped expert の呼び出し元: `src/core/remote_experts.cpp:318`、`src/core/peer_experts.cpp:240`、`src/core/verify.cpp:1582`。
- 文書上の役割の記載: `docs/STRIX_HALO.md:96`。`docs/DETAILS.md` には `STRATA_TSUM` の詳細な説明を確認できませんでした。
