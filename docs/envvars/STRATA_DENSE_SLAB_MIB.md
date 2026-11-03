# `STRATA_DENSE_SLAB_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

SYCL backend の native dense 投影行列をまとめる device-memory block のサイズを MiB 単位で指定します。`--native-dense-gguf` によって `NativeDense::load()` が実行される場合に関係し、それ以外の通常の重み読み込み経路にはこの設定の適用箇所はありません。値が 0 の場合は行列ごとの個別 allocation にします。未設定時は Intel GPU の `i915` driver で 256 MiB、それ以外で 0 です。

## 値と判定

| 状態 | 判定結果 |
|---|---|
| 未設定 | `strata::intel_gpu_driver() == "i915"` なら 256 MiB、それ以外なら 0 |
| 設定あり、`std::atol(e) > 0` | 変換結果を MiB 数として `size_t` に変換し、`<< 20` して byte 数にする |
| 設定あり、変換結果が 0 以下 | 0。個別 allocation にする |

`atol` を使うため、入力全体の厳密な数値検証や末尾文字の検査はありません。先頭の空白と符号は `atol` の変換規則に従い、数字に続く文字列は変換後に無視されます。数字を変換できない文字列と空文字は 0、負値も 0 扱いになります。正の値に対する上限 clamp はありません。`long` の範囲を超えた入力はこのコードでエラー処理されず、変換結果に依存します。

## 有効になる条件

- SYCL backend の `sycl/src/core/native_dense.cpp` に実装された設定です。CUDA/HIP 側にこの変数の読み取りはありません。
- `strata generate --native-dense-gguf PATH`（複数 shard では繰り返し指定）を使うか、`--native` preset が dense shard を設定し、native dense projection の読み込みに進む必要があります。最終的に `native_dense_gguf` が空なら通常経路の `NativeDense::load()` は呼ばれません。
- スラブサイズが 0、または 256-byte 単位に切り上げた行列サイズがスラブの半分以上なら、その行列は個別 allocation になります。したがって正の値を設定しても、すべての行列がスラブに入るとは限りません。
- CLI 引数による上書きや、別の環境変数との優先順位はありません。環境値が設定されていれば、driver に基づく既定値の選択より優先します。

## 実行時の詳細

設定値は `dense_slab_bytes()` 内の関数ローカル `static const size_t` として一度だけ評価されます。評価は `dense_alloc()` が最初に呼ばれた時点です。プロセス起動後に環境を変更しても、そのプロセスでは再評価されません。

スラブ対象の行列では、mutex 保護下で既存 block の空き領域を first-fit で使い、空きがなければ指定サイズの device block を確保します。確保に失敗すると `dense_alloc()` は null を返し、ここから個別 allocation へ fallback しません。`NativeDense::load()` は upload の status が失敗した場合に `native dense upload <tensor名>: <DPCT error string>` をエラー文字列にし、通常の generate 経路では stderr に `strata generate: native dense projections: ...` と出して終了コード 1 で戻ります。SYCL exception は別の catch 経路で例外内容を stderr に出し `exit(1)` します。

この設定専用の有効化ログや allocation 成功ログは見つかりません。ソースコメントには i915 上での既定有効化の意図と A750 の 4K-token prompt 測定値（112.6 → 185.6 tok/s）が記載されていますが、測定条件の詳細は当該コメントに示されていないため、一般的な性能値としては扱えません。

## 根拠

- `sycl/src/core/native_dense.cpp:95-113` — スラブの目的、変数の読み取り、`atol`、static cache、driver 別既定値。
- `sycl/src/core/native_dense.cpp:121-132` — 256-byte 丸め、個別 allocation 条件、スラブ利用と block allocation 失敗時の戻り値。
- `sycl/src/core/native_dense.cpp:222-232,322-349` — `NativeDense::load()` の入口、native 行列 upload と失敗処理。
- `sycl/src/program/generate.cpp:818-819,1888-1892,3085-3092` — `--native-dense-gguf` の CLI 表示・解析と通常 generate 経路でのロード・エラー出力。
- `sycl/src/program/generate.cpp:2505-2523` — `--native` preset が dense shard 群を `native_dense_gguf` に設定する経路。
- `sycl/src/program/generate.cpp:3550-3553,3557-3560` — layer-split 経路のロード失敗出力と SYCL exception の終了経路。
