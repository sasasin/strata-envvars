# `STRATA_ATTN_BATCH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリや GPU driver の環境変数動作は対象外。

## 役割

SYCL backend の prompt prefill において、QSA attention の FP32 decode kernel に一度に渡す query 数の上限を設定します。設定値はその query 数分の attention scratch の確保量にも使われます。`sycl/src/prefill/prefill.cpp` に読み取り箇所があり、CUDA/HIP 側の Strata ソースに同名の読み取りはありません。

実行時に tensor-core prompt attention が成功すれば、設定値はその計算の query 分割には使われません。`STRATA_PROMPT_ATTN_OLD` が設定されている場合、または tensor-core prompt attention が対応できず `false` を返す場合に、FP32 decode kernel の分割数として使われます。

## 値と判定

`std::getenv` で値を取り、設定されていれば `std::atoll` で `long long` に変換します。変換後の値が 1 から 1024 まで（両端を含む）なら採用し、それ以外は 32 に戻します。環境変数の文字列全体が数値かどうかは検査しません。

| 環境変数の状態・値 | 判定結果 |
|---|---:|
| 未設定 | 32 |
| 空文字 | `atoll("")` が 0 となるため 32 |
| `1`～`1024` に変換される値 | 変換後の整数値 |
| 0、負数、1024 より大きい値 | 32 |
| 数字に変換できない文字列 | 32 |
| 数字の後に文字が続く文字列 | 数字部分が 1～1024 ならその値（例: `128junk` → 128） |

`atoll` のため、先頭の空白や符号は通常の整数変換規則で扱われます。オーバーフローする入力の結果はこの実装で保証されていません。

根拠: `sycl/src/prefill/prefill.cpp:707-715`。

## 有効になる条件

- この読み取りは `sycl/src/prefill/prefill.cpp` にあり、同ファイルは SYCL port の `strata_prefill` に組み込まれます（`sycl/CMakeLists.txt:265-277`）。トップレベルでは `STRATA_ENABLE_SYCL`（既定 `OFF`）が有効な場合に `sycl/` を追加します（`CMakeLists.txt:12-20`）。この環境変数の Strata 側の効果は SYCL build に限られます。
- 実際の query 分割への効果は、モデルの prompt に QSA attention layer があり、その層で FP32 decode attention 経路が実行される場合に現れます。tensor-core prompt attention が成功する経路では、全 chunk の `T` query を一度に渡します（`sycl/src/prefill/prefill.cpp:3446-3477`）。
- `STRATA_PROMPT_ATTN_OLD` が設定されていると、値の内容にかかわらず（空文字を含む）tensor-core prompt attention を使わず、FP32 decode attention 側へ進みます。その場合、`STRATA_ATTN_BATCH` は最大 query 数を決めます（同:3450,3470-3476）。変数が未設定でも decode 経路自体は必要に応じて選ばれ、batch の既定値は 32 です。
- `T` が設定値より小さい場合、使用 batch は `T` に制限されます。`attn_batch_for(T)` は `max(1, min(setting, T))` を返します（同:712-715）。
- CLI 引数によるこの値の上書きは確認できません。別環境変数 `STRATA_PROMPT_ATTN_OLD` はどの attention 経路を使うかに関わりますが、`STRATA_ATTN_BATCH` の値判定自体は変更しません。

## 実行時の詳細

`attn_batch_setting()` は `static` cache を使わず、呼ばれるたびに `getenv` と変換を行います。`attn_batch_for(T)` は chunk の確保サイズを数える `bytes_needed_impl` と、実バッファを組み立てる `Prefill::carve` の両方から呼ばれます。`carve` は `m.attn_batch` にその chunk の値を保存し、その値で `m.attn_scratch` を確保します（`sycl/src/prefill/prefill.cpp:1102-1111,1443-1485,2151-2184`）。従って通常の prompt 実行では値は起動時に一度だけ読むのではなく、サイズ見積もりやバッファ構築時に読み直され、構築後の chunk の実行には `m.attn_batch` が使われます。見積もりと構築の間にプロセス内で環境値を変更すると、両者が異なる値を読む可能性があります。

FP32 decode 経路は `t0` を `m.attn_batch` 刻みで進め、最後の batch は残り query 数までに制限して `qsa_decode_attn_batch` を呼びます。設定値を大きくすると scratch の query 次元も大きくなり、同じ scratch は chunk 内の呼び出しで再利用されます（同:1102-1111,1461-1485,3470-3477）。`bytes_needed` 系の計算も同じ値で QSA scratch のサイズを見積もるため、prefill のバッファ予算に反映されます。

この変数専用のログや警告はありません。バッファ構築に失敗した場合は `Prefill::init` が失敗し、上位の生成経路が `strata generate: <error>` を stderr に出して終了コード 1 を返します（`sycl/src/program/generate.cpp:12385-12389`）。借用バッファの再配置で chunk 用 device buffer が足りない場合は `prefill: device buffers for a chunk of ... tokens do not fit (...)` というエラー文字列を作ります（`sycl/src/prefill/prefill.cpp:1541-1582`）。値そのものに対する無効値警告やエラーはなく、範囲外値は既定値へ静かに fallback します。

## 根拠

- 読み取り、変換、範囲制限、chunk による上限: `sycl/src/prefill/prefill.cpp:701-715`。
- scratch サイズ見積もりと実確保: `sycl/src/prefill/prefill.cpp:1102-1111,1443-1485,2151-2184`。
- tensor-core / FP32 decode の選択、`STRATA_PROMPT_ATTN_OLD`、FP32 query 分割: `sycl/src/prefill/prefill.cpp:3446-3477`。
- SYCL target への組み込み条件: `CMakeLists.txt:12-20`, `sycl/CMakeLists.txt:265-277`。
- 上位の init 失敗ログと終了: `sycl/src/program/generate.cpp:12385-12389`。
