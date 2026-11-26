# `STRATA_HC_REQ8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate` の単一 GPU 経路で、各層の hyper-connection `down` / `up` 投影重みを通常の BF16 ではなく、int8 コードと 32 要素ごとの FP32 scale に変換して読み込みます。起動ログは重み形式を示し、生成結果は丸めのため変わり得ます。複数 GPU の layer split ではこの形式を使わず、BF16 のままにします。読み取りと選択は `engine/src/program/generate.cpp:5984-5992`、変換は `engine/src/core/weights.cpp:518-599` です。

## 値と判定

`generate` の重みロード直前に `getenv` で設定有無を調べ、設定されていれば `atoi` の結果が 0 以外かで判定します。未設定・空文字は無効です。`atoi` は先頭の空白と符号を許し、10 進数の先頭部分だけを読みます。したがって `1`、`-1`、`+2`、` 1tail` は有効、`0`、`0tail`、`true`、`false`、空文字、数字で始まらない文字列は無効です。完全一致や末尾の検査はありません。`atoi` の範囲外入力の結果はこのコードで規定されません。根拠: `engine/src/program/generate.cpp:5987`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `multi_gpu == false` | BF16 を使用 | `atoi(value) != 0`（例: `1`, `-1`, ` 2x`） | `atoi(value) == 0`（例: 空, `0`, `0x`, `true`, `x1`） |
| `multi_gpu == true` | BF16 を使用 | 値の判定自体は上と同じだが、BF16 のまま | BF16 のまま |

## 有効になる条件

- `multi_gpu` が false であること。通常の単一 GPU 実行では変換対象になります。layer split が複数 GPU を使う場合は `STRATA_HC_REQ8` が有効値でも警告を出して BF16 を使います。`--split-skip-if-fits` が split を取り消して単一 GPU に戻した場合は変換対象になります（`engine/src/program/generate.cpp:4786-4856, 6446-6491, 5987-5992`）。
- int8 重みを使う実行経路では fused hyper-connection read が必要です。これは `--gr-native-mmvf` が有効で、`--no-fused-gr` がなく、GPU stage / layer dump / half dump / stage timing を使わず、カーネルがモデル形状をサポートする場合に限られます。`--native` の初期化は `--gr-native-mmvf` を有効にします（`engine/src/program/generate.cpp:5160-5164, 6112-6113`; カーネル条件は `engine/src/core/layer.cpp:1500-1502`）。条件を満たさないまま decode 側が unfused read に入ると、`block_layer_pre` は `STRATA_HC_REQ8 needs the fused hyper-connection read` を返して失敗します（`engine/src/core/layer.cpp:1563-1568, 1583-1591`）。
- プロンプト GEMM 側は int8 コードを必要なとき BF16 scratch へ展開して読みます。scratch 確保に失敗すると `prefill: the STRATA_HC_REQ8 scratch` をエラーとして返します（`engine/src/prefill/prefill.cpp:3975-3998`）。
- 変換対象テンソルは各層の `hc_attn_` / `hc_ffn_` の `down` / `up` 重みです。BF16 形式、`ne0` が 32 の倍数、元データが要素ごと 2 byte または 4 byte である必要があります。条件不一致、追加領域の `cudaMalloc`、ファイル open/read、GPU 転送の失敗はエラーになります（`engine/src/core/weights.cpp:518-540, 543-599`）。

## 実行時の詳細

値は `generate` の重みアリーナ確保・読み込みの直前に一度評価され、関数内 static やリクエストごとの再評価ではありません。CLI 引数による値の上書きはありません。multi-GPU 判定は `--layer-split` と split 選択の処理で先に決まり、環境変数はそれを上書きしません（`engine/src/program/generate.cpp:4783-4856, 5984-5992`）。

有効時は `WeightTable::hc_q8_names` が対象重みを通常アリーナの読み込み対象から外し、`load_hc_q8` が元の BF16 値を 32 要素ずつ量子化します。各 group の scale は `amax / 127`、コードは `nearbyint(x / scale)`（ゼロ group は scale 0、コード 0）です。int8 codes と FP32 scales を別々に GPU へ転送し、重み参照へ登録します（`engine/src/core/weights.cpp:518-523, 525-599`）。

計算経路では fused read が scales と int8 重みを渡して使います（`engine/src/core/layer.cpp:1557-1568, 1580-1591`; `engine/src/kernels/cuda/fused_gr.cu:1780-1782, 1900-1910`）。プロンプト GEMM 経路はストリーム上の scratch に BF16 展開してから使います（`engine/src/prefill/prefill.cpp:3980-3998`）。

## ログと測定値

- layer split と複数 GPU が有効で値が非ゼロの場合: `strata generate: WARNING: STRATA_HC_REQ8 does not support a layer split yet - the BF16 projections are used`（`engine/src/program/generate.cpp:5988-5990`）。
- 単一 GPU で変換に成功した場合: `strata generate: STRATA_HC_REQ8: hyper-connection projections as int8 + fp32/32 scales, %llu MiB`（`engine/src/program/generate.cpp:6049-6053`）。
- 形式・割当・I/O・転送の失敗は `STRATA_HC_REQ8: ...` を含むエラーを stderr に出し、`generate` は終了コード 1 で戻ります（`engine/src/core/weights.cpp:535-590`; `engine/src/program/generate.cpp:5993-5996, 6044-6053`）。
- `docs/DETAILS.md:1304` はこの設定の回答差を「Rounding level」と記載しています。同資料 `docs/DETAILS.md:1710` は 0.1.45、RTX 3060 / RTX A4000、IQ3_XXS、5 pairs、30K prompt 後の decode 条件で `STRATA_HC_REQ8` を順に -0.2% / +2.2% と記録しています。これは資料記載値であり、今回の調査で再測定したものではありません。

## 根拠

- 読み取り、split 時の無効化、通常ロード後の変換とログ: `engine/src/program/generate.cpp:5984-6057`。
- 対象テンソルの選択、値変換、スケールと失敗条件: `engine/src/core/weights.cpp:518-599`。
- fused read 条件と非対応経路のエラー: `engine/src/core/layer.cpp:1500-1502, 1557-1591`。
- fused kernel の int8 重み経路: `engine/src/kernels/cuda/fused_gr.cu:1780-1795, 1900-1910`。
- プロンプト GEMM の BF16 展開・scratch: `engine/src/prefill/prefill.cpp:3975-3998`。
- 設計資料と測定記録: `docs/DETAILS.md:1304, 1710`。
