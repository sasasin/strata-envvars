# `DS4_FAST_ATTN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1 の HIP 実装で、FP4 packed-KV を使う chunked prefill の sparse attention に WMMA 行列コア kernel `sparse_attn_wmma_kernel` を選ぶかを制御します。通常の scalar packed kernel と計算順序が異なるため、出力の最下位部分は一致しません。decode と verify window ではこの kernel を使いません。

実際に環境から読むのは `src/dsv41/ds4_kernels.cu:2077-2081` の `std::getenv("DS4_FAST_ATTN")` です。値は `fast_attn_enabled()` 内の関数ローカル `static const int` に保存され、プロセスで最初にこの関数が呼ばれた時に一度だけ読みます。呼び出し側は `#if defined(STRATA_USE_HIP)` 内にあるため、CUDA / Metal / その他の非 HIP dispatch ではこの設定による kernel 選択は起きません（同ファイル `:2477-2484`）。

## 値と判定

値は `std::atoi` で整数に変換します。文字列全体の妥当性検査はありません。変換結果が 0 以上なら明示値として扱い、0 は OFF、0 以外は ON。負数はすべて未設定と同じ既定値判定に回ります。

| `DS4_FAST_ATTN` | `atoi` 結果 | 判定 |
|---|---:|---|
| 未設定 | `-1`（実装上の sentinel） | GPU / `DS4_DEFAULTS` による既定値 |
| 空文字 | `0` | 明示 OFF |
| `0`、非数値文字列 | `0` | 明示 OFF |
| `1`、`2`、`1tail`、` 1tail` | それぞれ先頭の整数 | 変換結果が正なら明示 ON |
| `-1`、`-2` | 負数 | 未設定と同じ既定値。明示 OFF にはならない |

したがって `false` は `atoi` が 0 を返すため明示 OFF、`true` も 0 となり明示 OFF です。後続文字が数値変換後に残っても拒否されません。変換処理の根拠は `src/dsv41/ds4_kernels.cu:2077-2081`、明示値と既定値の分岐は `src/dsv41/ds4_experts_rule.hpp:192-195` です。

未設定または負数時は次の規則です。

| backend / GPU | `DS4_DEFAULTS` が 0.2.6 指定 | それ以外 |
|---|---|---|
| HIP gfx1200 / gfx1201 | OFF | ON |
| Windows HIP gfx1151 | OFF | ON |
| その他の HIP GPU | OFF | OFF |
| 非 HIP dispatch | この kernel 選択経路なし | この kernel 選択経路なし |

`DS4_DEFAULTS` は値が厳密に `026`、`0.2.6`、`v0.2.6` のいずれかと完全一致した時だけ 0.2.6 指定になります。大文字小文字、空白、接尾辞は許容しません（`src/dsv41/ds4_experts_rule.hpp:22-27`）。明示された `DS4_FAST_ATTN` の 0 / 正数はこの既定値を上書きします。ほかにこの kernel 選択を変える CLI 引数は見つかりませんでした。

## 有効になる条件

明示 ON または既定 ON でも、実際に WMMA kernel が選ばれるのは、次の条件を満たして分岐まで到達した場合です。

- `STRATA_USE_HIP` が定義されたビルドである。
- `sparse_attn()` の入力 head dimension が 512、KV 形式が `kKvFp4` である。BF16 形式は `src/dsv41/ds4_kernels.cu:2437-2440` で別 kernel に送られて先に return する。
- `AttnRows.gen != 0`、query 数 `T >= 16`、head 数が 16 の倍数である（同ファイル `:2479-2484`）。DeepSeek の通常の生成側は `ar.gen = 1` としてこの関数を呼びます（`src/dsv41/ds4_model.cu:8305-8313`）。
- 先行する decode split-KV または few-query scratch 経路が選択されて return していない（`src/dsv41/ds4_kernels.cu:2442-2475`）。

未設定時に ON となる GPU は、HIP の `cudaGetDeviceProperties()` で得た arch 名の先頭 7 文字が `gfx1200` / `gfx1201`（全 HIP OS）、または Windows で `gfx1151` の場合です。GPU 番号ごとの判定結果は `device_is_gfx12()` / `device_is_gfx1151win()` 内の atomic cache に保存されます。取得失敗や対象範囲外の device 番号は該当 GPU と判定されず、既定 OFF です（`src/dsv41/ds4_kernels.cu:2044-2075`）。明示 ON はこれら以外の HIP GPU でも既定値判定を上書きしますが、上記の入力形状・dispatch 条件は引き続き必要です。

## 実行時の詳細

Strata の `serve.server.child_env()` は親プロセスの環境を複製し、run config の `env` エントリで同名の値を上書きして engine 子プロセスに渡します（`serve/server.py:3747-3763`）。そのため設定ファイルの `env.DS4_FAST_ATTN` は継承環境変数より優先されます。汎用の起動設定から値を渡せますが、engine 側では起動後に初回 dispatch 時点で一度だけ読み、後から環境を変更しても再評価しません。`DS4_DEFAULTS` も helper の static cache に一度だけ保存されます（`src/dsv41/ds4_experts_rule.hpp:25-27`）。GPU 世代の結果は device ごとに cache されます。

Strata の設定 UI にある「DeepSeek speed-ups」は通常 ON で、OFF にすると設定環境へ `DS4_FAST_ATTN=0` と `DS4_DEFAULTS=026` を含む複数の値を書きます。ON に戻すとそれらのスイッチ値を削除します（`apps/host/server/native-settings.mjs:49-53,78-85`）。このため OFF は明示的な `DS4_FAST_ATTN=0` により機能を止め、ON は値を未設定に戻して GPU 世代別の既定動作を使います。

選択された WMMA kernel は 16 heads を 1 block、16 keys を 1 tile として実行します。Strata のコードコメントは、matrix-core の積算順序が scalar kernel と異なり出力の最下位部分が変わること、decode と verify は scalar kernel のままであることを記しています（`src/dsv41/ds4_kernels.cu:2034-2039,2477-2484`）。`docs/DETAILS.md` にはこの環境変数の個別説明は見当たらず、性能・精度について本書ではコードコメントの測定記録を独立に検証した結果としては扱いません。

この設定専用のログ、警告、終了処理はありません。kernel launch の失敗を stderr に出す仕組みは別の `DS4_LAUNCH_CHECK` が設定されている時だけ有効で、文言は `ds4 launch failed at ...` です（`src/dsv41/ds4_launch.h:10-19`）。この変数自体の値が不正でもエラーにはならず、`atoi` による判定結果が適用されます。

## 根拠

- 環境読み取り、数値変換、cache: `src/dsv41/ds4_kernels.cu:2077-2090`
- GPU 世代の判定と per-device cache: `src/dsv41/ds4_kernels.cu:2044-2075`
- 既定値、`DS4_DEFAULTS` の読み取りと優先順位: `src/dsv41/ds4_experts_rule.hpp:22-27,189-195`
- attention の形式別経路と WMMA dispatch 条件: `src/dsv41/ds4_kernels.cu:2425-2484`
- DeepSeek 生成側の `gen` 指定: `src/dsv41/ds4_model.cu:8305-8313`
- config 環境の子プロセスへの転送: `serve/server.py:3747-3763`
- アプリ設定の値と書き換え規則: `apps/host/server/native-settings.mjs:49-53,78-85`
- 起動失敗ログの条件: `src/dsv41/ds4_launch.h:10-19`
