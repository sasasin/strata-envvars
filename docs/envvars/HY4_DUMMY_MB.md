# `HY4_DUMMY_MB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`HY4_DUMMY_MB` は HY4 の speculative decode にある `--spec-nodraft` 用テスト分岐で、指定量の HIP device memory を確保し、各反復で device-to-device copy と stream 同期を行う値です。コピー元とコピー先は同じ確保領域の前半・後半です。値が 0 なら、この追加確保・コピー・同期は行いません。通常の DFly2 draft 分岐では参照されません（`engine/src/hy4flash/run/hy4_spec.hip.h:286-310`）。

このコードは `strata-hy4` の CUDA または HIP 実装に含まれます。HY4 の Metal / SYCL 実装は別のソース構成で、この読み取り箇所を含みません（`engine/CMakeLists.txt:846-852,884-891`）。

## 値と判定

`getenv("HY4_DUMMY_MB")` が null でなければ `atoi` の結果を `size_t` に変換してから 20 bit 左シフトし、バイト数として使います。`atoi` は文字列全体の厳密な数値検証ではなく、10 進整数の先頭部分を変換します。したがって空文字や数値で始まらない値は 0 となり、`1abc` は 1、先頭空白や符号は `atoi` の変換規則に従います。正の値に上限確認や clamp はありません。負数も拒否されず、`size_t` への変換後にシフトされるため、意図した負の MiB 数として扱われることはありません。`atoi` の変換範囲外入力に対するエラー処理もありません（`engine/src/hy4flash/run/hy4_spec.hip.h:303-308`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `cfg.nodraft` の分岐に到達 | `dummy_bytes = 0` | `1` は 1 MiB、`2` は 2 MiB | 空文字、`0`、`false`、`abc`、`0anything` は `atoi` が 0 を返すため追加処理なし |
| 同上 | — | `  +3tail` は `atoi` が先頭の整数を 3 と読むため 3 MiB | `-1` は拒否されず、`size_t` 変換とシフト後の値が 0 でない場合は追加処理へ進む |

値を読み取る CLI 引数の上書き経路はありません。`--spec-nodraft` は分岐を選ぶ別の CLI 設定であり、環境変数の値を変更しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:425-428`）。

## 有効になる条件

- `Spec::run` のループが `cfg.nodraft` 分岐に到達する必要があります。この設定は CLI の `--spec-nodraft` がセットします（`engine/src/hy4flash/run/hy4_main.hip.cpp:428`; `engine/src/hy4flash/run/hy4_spec.hip.h:264-310`）。
- デコード経路が speculative decode を実行する必要があります。通常 CLI では `--draft dfly2` と `--gen` が必要で、サーバーでは DFly2 が有効化され、生成可能な上限が正である必要があります（`engine/src/hy4flash/run/hy4_main.hip.cpp:700-712,992-1000`; `engine/src/hy4flash/run/hy4_serve.hip.h:319-341,540-550`）。サーバーで `--spec-nodraft` を渡した場合も `SpecCfg` に保持されます（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-570`）。
- HY4 実行ファイルは CUDA または HIP 構成である必要があります。Metal / SYCL の実装にはこの `Spec` コードがありません（`engine/CMakeLists.txt:846-852,884-891`）。
- `HY4_DUMMY_MB` が未設定、空、または `atoi` の結果が 0 なら、nodraft 自体は動きますが追加の device memory 処理はありません。非 0 でも、`--spec-nodraft` を使わない経路には作用しません（`engine/src/hy4flash/run/hy4_spec.hip.h:288-310`）。

## 実行時の詳細

環境値は `Spec::run` 内のブロック内 `static` 初期化で評価され、初めて `cfg.nodraft` 分岐に達した時点でプロセスにつき一度だけ保存されます。後から環境を書き換えても同じプロセス内では再読込されません。関数内の別の `static` ポインタ `dummy` は null から始まり、最初の非 0 値で `2 * dummy_bytes` の領域を確保します（`engine/src/hy4flash/run/hy4_spec.hip.h:303-306`）。

以降の nodraft 反復では、確保領域の先頭 `dummy_bytes` を後半領域へ `hipMemcpyAsync` で device-to-device コピーし、`r.st` を `hipStreamSynchronize` で同期します。環境値は生成 token の値や `TreeSpec` の固定 junk token を直接決めず、分岐内の追加メモリー操作を決めます（固定 token の構成は `engine/src/hy4flash/run/hy4_spec.hip.h:288-309`）。値が 0 の場合や nodraft 分岐外ではこれらの API は呼ばれません。

## ログと測定値

この値を読み取ったことやコピーを行ったことを示す専用ログはありません。`hipMalloc`、`hipMemcpyAsync` または `hipStreamSynchronize` が失敗すると、`HCK` が stderr に `HIP error %d (%s) at %s:%d\n` を出し、プロセスを終了コード 3 で終了します（`engine/src/hy4flash/run/hy4_spec.hip.h:305-308`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34`）。

## 根拠

- `engine/src/hy4flash/run/hy4_spec.hip.h:286-310` — nodraft 分岐、static 値の読み取り、領域確保、コピー、同期。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:425-428,700-712,992-1008` — CLI による nodraft 設定と通常の speculative decode 経路。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341,540-556` — サーバーでの DFly2 有効化と spec decode 呼び出し。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — HIP 呼び出し失敗時のログと終了。
- `engine/CMakeLists.txt:846-852,884-891` — CMake の HY4 ターゲットおよび CUDA / HIP 条件。
