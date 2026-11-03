# `DS4_VISION_REF_GEMM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 の Metal 版 vision tower で、通常の GEMM の代わりに参照 GEMM カーネル `vis_gemm_ref` を選びます。設定すると Metal 4 tensor-op（MPP）経路も選択対象から外れます。実装コメント上はテスト用の切替です。Metal 以外の backend でこの名前を読む Strata の箇所は見つかりませんでした。

## 値と判定

文字列の数値変換や全体比較はしません。未設定かどうかだけで参照 GEMM を選び、設定されている場合は先頭 1 文字が `'2'` かどうかで参照カーネルの加算順を決めます。

| 値 | 選ばれる GEMM | 加算順 |
|---|---|---|
| 未設定 | 通常の `vis_gemm`（MPP が別条件を満たせば MPP GEMM） | 通常カーネルの実装による |
| 空文字を含む、設定済みで先頭が `'2'` 以外 | `vis_gemm_ref` | 各出力につき `k` を順にたどる FP32 FMA の逐次累積 |
| 先頭が `'2'`（例: `2`, `2foo`） | `vis_gemm_ref` | 64 要素ごとに FP32 FMA 累積を分け、各 chunk の和を加算 |

したがって `0`、`1`、`true`、先頭が空白の ` 2` も参照 GEMM を有効にしますが、いずれも先頭が `'2'` ではないため逐次累積になります。大文字小文字、後続文字、数値としての妥当性は検査されません。環境変数の値自体をエラーとして拒否する分岐はありません。

根拠: `metal/src/engine/ds4_vision_metal.cpp:235-238`、`metal/src/engine/msl/ds4_vision.metal:284-313`。

## 有効になる条件

- 対象コードは Apple 専用 Metal ビルドに含まれます。`metal/CMakeLists.txt` は非 Apple で構成を停止し、Metal engine のソースを `strata_metal_kernels` に含めて `strata_ds4` にリンクします（`metal/CMakeLists.txt:16-18,110-127,165-171`）。
- `strata-dsv41` のモデルに vision tower があり、画像を encode する経路に入ったときに効きます。モデルに tower がない、または無効なら `encode_image()` は失敗して vision encode に進みません（`src/dsv41/ds4_model.cu:7756-7764`）。Metal の encode 呼び出しは `STRATA_GPU_METAL` 経路です（`src/dsv41/ds4_vision.cu:551-572`）。
- `encode()` の最初の呼び出し時にこの変数が設定済みなら、`choose_mpp()` が MPP の選択を抑止し、`use_mpp` は false になります。その後の GEMM はすべて参照カーネルへ分岐します。通常 GEMM を選ぶ設定値はありません。
- `DS4_VISION_NO_MPP` も値ではなく設定有無で同じ MPP 抑止条件になります。両方が設定されても結果は同じです。`DS4_VISION_FORCE_MPP_FAIL` は MPP 検査用ですが、この変数または `DS4_VISION_NO_MPP` が設定されている場合は先行分岐により評価されません（`metal/src/engine/ds4_vision_metal.cpp:189-206`）。
- 未設定時は通常 GEMM が選ばれます。ただし、Metal 4 対応、MPP kernel のコンパイル成功、参照 kernel との自己テスト成功という条件を満たせば、対応する GEMM 呼び出しでは MPP が使われます。MPP 自己テスト失敗などでは plain kernel に戻ります（`metal/src/engine/ds4_vision_metal.cpp:189-212,261-276`）。

## 実行時の詳細

2 つの読み取りはいずれも `encode()` 内の関数ローカル `static` 初期化です。MPP の選択結果 `mc` と環境変数ポインター `ref_env` は各プロセスで初回の vision encode 時に一度決まり、以後同プロセスで環境を変更しても再評価されません。画像処理を一度も行わない実行では、これらの判定は行われません（`metal/src/engine/ds4_vision_metal.cpp:217-238`）。

参照モードでは出力要素ごとに 1 thread を使い、`in` 全体を走査します。先頭が `'2'` 以外なら単一の FMA 累積、先頭が `'2'` なら最大 64 要素単位で部分和を作って加算します。どちらも BF16 入力を float に変換して累積し、alpha を乗じた後、出力フラグに応じて FP32 または BF16 に書きます。dispatch は出力幅を 32 ごと、行を 1 ごとに区切り、threadgroup サイズ 32 です（`metal/src/engine/ds4_vision_metal.cpp:261-276`、`metal/src/engine/msl/ds4_vision.metal:286-313`）。

初回選択時には `stderr` に `ds4: vision tower GEMM: plain kernel (asked for by DS4_VISION_NO_MPP / DS4_VISION_REF_GEMM)` が出ます。この文言は参照 GEMM を明示しません。逐次累積と 64 要素 chunk のどちらが選ばれたかを示す専用ログも、この実装にはありません（`metal/src/engine/ds4_vision_metal.cpp:208-212`）。

参照 pipeline は `encode()` で取得されます。取得に失敗すると `Runner::pipe()` が `vision: no pipeline vis_gemm_ref` を `err` に設定し、`encode()` は `false` を返します。vision model 側の `encode_image()` はその失敗をそのまま返します（`metal/src/engine/ds4_vision_metal.cpp:53-60,231-252`、`src/dsv41/ds4_model.cu:7756-7764`）。通常 kernel library 自体のコンパイル失敗では `vision: compiling ds4_vision.metal failed` が返ります（`metal/src/engine/ds4_vision_metal.cpp:219-223`）。

`docs/DETAILS.md` などの設計・利用者向け資料には、この変数の値や測定結果の説明は見つかりませんでした。コードから確認できる範囲を超えた性能・出力差の測定値は記載していません。

## 根拠

- 読み取り箇所は `metal/src/engine/ds4_vision_metal.cpp:192`（MPP 抑止）と `:235-238`（参照 GEMM 選択）の 2 箇所です。候補名の全リポジトリ参照を検索し、動的な env helper 経由の別読み取りは見つかりませんでした。
- MPP 抑止・理由ログ: `metal/src/engine/ds4_vision_metal.cpp:189-212`。
- GEMM 選択・dispatch: `metal/src/engine/ds4_vision_metal.cpp:217-276`。
- 参照 kernel の累積・出力形式: `metal/src/engine/msl/ds4_vision.metal:284-313`。
- Metal build 条件と vision 呼び出し: `metal/CMakeLists.txt:16-18,110-127,165-171`、`src/dsv41/ds4_vision.cu:551-572`。
