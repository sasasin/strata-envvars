# `INK_GGUF_SK_BITS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

GGUF の GGUF_RAW expert を S_K 形式へ変換する経路で、gate/up と down の各 GGML 型をどの S_K codec（S4_K / S6_K / S8_K）に割り当てるかを上書きする。選択結果は変換後の expert body のサイズ・符号化形式に使われる。GGUF_RAW を native kernel で処理する expert は変換されず、この設定もその expert の演算には適用されない。実装は `ink2::transcode::choose_sk_code_for_ggml` にある。`engine/src/inkling2/ink_gguf_transcode.h:84-113`。

## 値と判定

関数が呼ばれるたびに `std::getenv("INK_GGUF_SK_BITS")` で値を取得し、設定されていれば `std::atoi` の結果が 4、6、8 のいずれかと一致した場合にそれぞれ S4_K、S6_K、S8_K を選ぶ。未設定、空文字、数値変換できない文字列、または変換結果が 4/6/8 以外なら、入力 GGML 型別の既定判定へ進む。文字列全体の検証はなく、`atoi` が先頭の数値部分を変換するため、例えば `4junk`, ` 6`, `08tail`, `+4` は上書きとして認識される。`true`, `false`, `0`, `5`, `-4`, 空文字は上書きにならない。大文字小文字は比較対象でない。`engine/src/inkling2/ink_gguf_transcode.h:86-112`。

| 条件 | unset | 上書きになる値の例 | 上書きにならない値の例 |
|---|---|---|---|
| 共通の chooser | GGML 型に応じて既定 codec を選ぶ | `4` / `4tail` → S4_K、`6` / ` 6x` → S6_K、`8` / `08x` → S8_K | 空文字、`true`、`0`、`5`、`9`, `-4` → GGML 型別の既定判定 |

既定判定は GGML 型コード 0/1/8/9/15/30 を S8_K、6/7/13/14 を S6_K、それ以外を S4_K とする。設定値が不正でも警告やエラーにはならず、この既定判定に戻る。CLI 引数からこの変数を上書きする処理は見つからなかった。別の環境変数 `INK_METAL_FORCE_SK_TRANSCODE`、`INK_HIP_FORCE_SK_TRANSCODE`、`INK_SYCL_FORCE_SK_TRANSCODE` は変換経路を選ぶ条件であり、codec 上書き値自体の優先順位を変えない。`engine/src/inkling2/ink_gguf_transcode.h:88-112`、`engine/src/inkling2/metal/ink_metal_common.h:656-682`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:937-962`、`engine/src/inkling2/sycl/ink_sy_common.h:1121-1146`。

## 有効になる条件

- 入力が GGUF 由来で、対象 expert の gate/up または down の codec ID が `GGUF_RAW` である必要がある。既に S_K、SF4、MX8 等で格納された expert は `read_or_transcode_expert` がそのまま読み出すため、この chooser による変更を受けない。`engine/src/inkling2/ink_gguf_transcode.h:373-399, 413-447`。
- Apple Metal の ModelFile loader は `plan_transcoded_expert_directory` で raw expert の変換後サイズを計画する。native Metal kernel に対応する GGML 型の expert は、`INK_METAL_FORCE_SK_TRANSCODE` の先頭文字が `'1'` でない限り native GGUF_RAW として保持され、codec の上書きは実データに適用されない。force 変数は未設定・空文字・先頭文字が `'1'` 以外なら偽、`1`, `10`, `1anything` は真。`engine/src/inkling2/metal/ink_metal_common.h:651-686, 719-745`。
- HIP では GGUF モデルの raw expert について、`INK_HIP_FORCE_SK_TRANSCODE` の `atoi` 結果が 0 でなく、または gate/up と down の両型に native HIP kernel がない場合に S_K 変換用 codec が選ばれる。両型に native kernel があれば、force が偽のとき raw expert のまま扱う。force の未設定・空文字・非数値は偽、`1` や `-1` は真。`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:937-962`。
- SYCL も同様に、GGUF raw expert に対して `INK_SYCL_FORCE_SK_TRANSCODE` の `atoi` 結果が 0 でないか、gate/up と down の両型に native SYCL kernel がないときに S_K codec を選ぶ。両型に native kernel があり force が偽なら raw のまま扱う。`engine/src/inkling2/sycl/ink_sy_common.h:1121-1146`。
- 共通ヘッダーの chooser は Metal、HIP、SYCL 実装から呼ばれる。どの backend が利用可能かはそのビルドと実行構成に依存する。CUDA 専用の読取箇所はこの名前について見つからなかった。`engine/src/inkling2/metal/ink_metal_common.h:659, 730`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:954-962, 2611-2622`、`engine/src/inkling2/sycl/ink_sy_common.h:1138-1146, 1153-1163`。

## 実行時の詳細

関数内キャッシュはなく、chooser が実行されるたびに環境を読み直す。したがって、少なくともコード上は関数呼び出し時点の値で判定する。ただし通常のプロセス内で環境を変更するコードや、子プロセスへ値を転送・上書きするコードは対象名について見つからなかった。

Metal の ModelFile ロードでは、まず `plan_transcoded_expert_directory` が GGUF adapter の各層の型から codec と body サイズを計画し、その後 `read_or_transcode_expert` が GGUF_RAW body を読み、header 内の実際の型でもう一度 chooser を呼んで変換する。force が無効で native Metal kernel 対応の expert は raw body を直接読む。`engine/src/inkling2/ink_gguf_transcode.h:373-399, 428-447`、`engine/src/inkling2/metal/ink_metal_common.h:651-745`。

HIP/SYCL はロード初期化中に各 raw expert の配置 codec と body サイズを決め、native 対応の raw expert は別のフラグで保持する。実際の読み込みはそのフラグを見て raw body の直接読取か `read_or_transcode_expert` を選ぶ。対象変数は GGUF の gate/up と down それぞれに個別適用される。`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:941-962, 2611-2622`、`engine/src/inkling2/sycl/ink_sy_common.h:1125-1163`。

## ログと測定値

この変数の値を理由付きで出力する専用ログや、無効値に対する警告は見つからなかった。Metal のロード成功時には一般的な `[ink_metal] loaded ... (native_gguf=...)` 行が stderr に出て native GGUF expert 数を示すが、codec override の値や個別に変換された数は示さない。HIP/SYCL では native raw kernel を利用した数がある場合に、それぞれ `[ink-hip] native lossless GGUF_RAW GPU kernels active for %zu/%zu experts (zero S_K transcode)`、`[ink_sycl] native lossless GGUF_RAW SG16+XMX kernels active for %zu/%zu experts (zero S_K transcode)` が出る。`engine/src/inkling2/metal/ink_metal_common.h:754-761`、`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:964-967`、`engine/src/inkling2/sycl/ink_sy_common.h:1148-1151`。

変換時に入力 header、次元、バッファ長、dequant 等が不正なら変換関数は `false` とエラー文字列を返し、Metal/HIP/SYCL のロード処理も失敗を返す。これらは形式・データの失敗経路であり、環境変数専用のエラーではない。`engine/src/inkling2/ink_gguf_transcode.h:261-298, 317-368, 428-447`。`docs/DETAILS.md` にこの変数固有の挙動や測定値の記載は確認できなかった。

## 根拠

- 読取と値判定、GGML 型別 fallback: `engine/src/inkling2/ink_gguf_transcode.h:84-113`
- 変換計画と raw expert 判定・変換: `engine/src/inkling2/ink_gguf_transcode.h:373-399, 404-447`
- Metal の native 条件、計画、読込: `engine/src/inkling2/metal/ink_metal_common.h:651-745`
- HIP の force/native 判定と chooser 利用: `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:937-967, 2611-2622`
- SYCL の force/native 判定と chooser 利用: `engine/src/inkling2/sycl/ink_sy_common.h:1121-1163`
- `INK_GGUF_SK_BITS` の全参照検索では本番コードの `std::getenv` は上記 chooser のみ。その他の一致はコメントと test code。
