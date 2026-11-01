# `DS4_ATTN_PROBE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal 版 DeepSeek-V4.1 の疎 attention にある、計算時間の切り分け用 probe を選びます。probe は attention の一部の演算を省略するため、出力値は意図的に正しくありません。通常の推論品質を保つ設定ではありません。

Strata がこの環境変数を読む箇所は `metal/src/engine/ds4_finish.cpp` の `sparse_attn()` 内だけです。値を関数定数 25 として選択した Metal pipeline に渡し、診断用の計算を切り替えます。

## 値と判定

値は `std::atoi()` で整数化され、結果が 0 か非 0 かで pipeline の作り方が分かれます。文字列全体の妥当性検査やエラー通知はありません。

| 環境値 | Strata の処理 |
|---|---|
| 未設定 | 通常の `pipeline()` を使う。probe 定数は渡さない。 |
| 空文字 | `atoi()` が 0 を返すため、未設定時と同じ。 |
| `0`、`00`、数値として 0 になる文字列 | 通常の `pipeline()` を使う。 |
| `1` | 定数 25 に 1 を設定。`ds4_sparse_attn_mx` では P·V の累積を省略する。 |
| `2` | 定数 25 に 2 を設定。同カーネルでは QK 行列積を省略する。 |
| その他の非ゼロ整数 | その整数を定数 25 に渡し、キャッシュを通さず pipeline を作る。`ds4_sparse_attn_mx` の実装が明示的に分岐する値は 1〜6 で、3 は softmax、4 はスコア集約、5 は次 pass 用の staging store、6 は QK・スコア集約・P·V を省略する。その他の値はこれらの分岐には一致しない。 |

`atoi()` のため、先頭の空白や符号を含む整数表記は変換され、数字の後ろに文字があっても数字部分が使われます（例: `1junk` は 1）。数字に変換できない文字列は 0 になり、probe pipeline を選びません。範囲外整数について Strata 独自の検査・扱いはありません。

根拠: `metal/src/engine/ds4_finish.cpp:1244-1253`, `metal/src/engine/msl/ds4_init.metal:1987-1990,2036-2082`。

## 有効になる条件

- 実装は macOS 専用の Metal engine に含まれます。`metal/CMakeLists.txt` は Apple 以外で構成を停止し、DeepSeek engine の実行ファイル `strata_ds4` に `ds4_finish.cpp` を含めます（`metal/CMakeLists.txt:16-18,135-142,165-171`）。CUDA/HIP/SYCL の同名変数読み取りは見つかりませんでした。
- 呼び出し元の DeepSeek sparse attention から Metal host 実装へ進んだ場合に評価されます。`d != 512`、未対応の `ckv_fmt`、null の行情報などではこの環境変数の読み取り前に通常の検査・return があり、Metal host が `false` を返せば呼び出し元には CUDA 形式の fallback があります（`metal/src/engine/ds4_finish.cpp:1151-1160`, `src/dsv41/ds4_kernels.cu:2432-2439`）。
- probe の分岐は `ckv_fmt == 2 && G == 8 && DS4_ATTN_MX != 0` の場合に選ばれる `ds4_sparse_attn_mx` で実際に定義されています。`ckv_fmt` が 2 でない場合、head 数から決まる `G` が 8 でない場合、または別環境変数 `DS4_ATTN_MX` が 0 の場合は別の関数名になります（`metal/src/engine/ds4_finish.cpp:1219-1241`）。
- `DS4_ATTN2Q` が設定され、行の条件も合えば関数名は `ds4_sparse_attn_mx2` になります。probe 定数と省略分岐が定義されているのは `ds4_sparse_attn_mx` で、`mx2` にはこの定義がありません。Strata host は `DS4_ATTN_PROBE` が非ゼロなら選択中の関数名に定数 25 を渡すため、`mx2` など別関数が選ばれる場合に probe として機能する保証はソースにありません（`metal/src/engine/ds4_finish.cpp:1225-1252`, `metal/src/engine/msl/ds4_init.metal:1987-1992,2110-2115`）。
- CLI 引数、設定ファイル、他の環境変数による `DS4_ATTN_PROBE` の上書きはありません。`DS4_ATTN_MX` と `DS4_ATTN2Q` は使用カーネルを変える条件であり、probe 値そのものは上書きしません。

## 実行時の詳細

`sparse_attn()` の呼び出しごとに `getenv()` で値を読み、static 変数には保存しません。したがって Strata 内に値の読み取り cache はなく、プロセス環境が呼び出し間で変更された場合は次の呼び出しで再評価されます。非ゼロ時には `pipeline_uncached()` を選び、ゼロまたは未設定時には通常の `pipeline()` を使います。後者は `Context` 内の pipeline cache を使います（`metal/src/engine/ds4_finish.cpp:1246-1252`, `metal/src/mtl_rt.mm:450-470`）。

probe 1〜6 の計算省略は `ds4_sparse_attn_mx` の Metal shader 内で行われます。値 1 は各 pass の出力累積 `O = ... + P·V` を飛ばし、値 2 は QK 積を飛ばします。値 3〜6 も一部の中間処理を飛ばす診断分岐です。したがって probe 有効時の attention 出力および後続の推論結果は通常計算の結果として解釈できません（`metal/src/engine/msl/ds4_init.metal:2039-2056,2058-2082`）。

この変数を処理する Strata 側の専用ログはありません。選択 pipeline の生成に失敗すると Metal runtime が `mtl: no function ...` または `mtl: pipeline ...` を stderr に出して終了コード 3 で終了します。host 側には pipeline の C++ 例外を捕捉して `dsv41 metal: sparse_attn pipeline %s unavailable` を出し `false` を返す経路もありますが、runtime の上記失敗経路は `exit(3)` なので例外捕捉を通りません（`metal/src/engine/ds4_finish.cpp:1242-1256`, `metal/src/mtl_rt.mm:494-509`）。

## 根拠

- 環境変数の読み取り、整数変換、function constant の設定: `metal/src/engine/ds4_finish.cpp:1242-1256`
- カーネル選択条件: `metal/src/engine/ds4_finish.cpp:1219-1241`
- probe 定数と shader の省略分岐: `metal/src/engine/msl/ds4_init.metal:1987-1992,2034-2108`
- 通常 pipeline の cache と uncached 生成、生成失敗時のログ・終了: `metal/src/mtl_rt.mm:450-509`
- Metal engine の対象 OS と DeepSeek 実行ファイル: `metal/CMakeLists.txt:16-18,135-171`
