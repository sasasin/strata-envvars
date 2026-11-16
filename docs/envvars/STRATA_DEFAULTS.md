# `STRATA_DEFAULTS`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。調査開始時の状態は `## main...origin/main`（未コミット変更なし）。

## 役割

`STRATA_DEFAULTS` は、Qwen エンジンのコードで `0.2.6` 相当へ戻す対象として明示された複数の**既定値**を選ぶマスタースイッチです。`026`、`0.2.6`、`v0.2.6` のいずれかを指定すると `qwen_defaults_026()` が true になり、接続先の各ルールが旧版相当の既定値を返します。これは機能群を一律に無効化する設定ではなく、環境変数を参照する機能の既定判断にだけ渡されます。対象外の設定は変えず、個別の機能環境変数や明示的な CLI 引数がある場合はそちらを優先するルールがあります（`include/strata/core/defaults_026.hpp:1-13, 21-30`）。

現 HEAD でこの判定に接続されている処理には、GPU アーキテクチャ別設定表（AMD gfx12 および NVIDIA）、gfx12 の追加既定、NVIDIA の prompt chunk 上限、prefill の層単位読み込み、PLE の RAM 常駐判断、PCIe share の既定、分割起動時の後段 cache 予約、batch group の選択、CUDA の GR / prompt-attention / MMVQ カーネル選択が含まれます（`src/core/arch_defaults.cpp:16, 115`; `src/core/nv_defaults.cpp:22, 127`; `src/program/generate.cpp:2729, 2974-2978, 4256, 5194, 5936, 6531, 7383, 8581, 8636, 8679, 8707, 9217, 11706`; `src/prefill/prefill.cpp:8994`; `src/kernels/cuda/fused_gr.cu:496, 2682`; `src/kernels/cuda/qsa_prompt_attn.cu:2563`; `src/kernels/cuda/native_mmvq.cu:3805, 3904`; `src/kernels/cuda/dequant_bf16.cu:301`; `src/kernels/cuda/iq_kernels.cu:6199`; `src/kernels/mmvq_il_parity.cpp:406`; `include/strata/core/gfx12_extra.hpp:51, 67`; `include/strata/core/bw_dense_defaults.hpp:16, 19`）。実際に適用される機能は GPU、backend、モデル・pack、分割や batch の状態、および各機能固有の条件にも依存します。

`setup.py` にも読み取りがありますが、これは `--prefill auto` の推奨文を出すか決める診断用の判定です。エンジン設定を変更しません（`setup.py:8034-8052, 8055-8070`）。`strata_control/speed_switches.py` は Qwen 用・terminal-only の「Qwen: 0.2.6 behaviour」スイッチから `STRATA_DEFAULTS=026` を設定します（`strata_control/speed_switches.py:61-63`）。

## 値と判定

C++ の `is_026_token()` は `std::strcmp` で文字列全体を次の3値と比較します。数値変換、trim、大文字小文字の正規化、前方一致はありません。したがって空白付き、大小文字違い、後続文字付きの値も一致しません（`include/strata/core/defaults_026.hpp:21-24`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| エンジンの共通 C++ 判定 | false（現行の各既定ルールを使う） | `026`、`0.2.6`、`v0.2.6` | 空文字、`0`、`027`、`026 `、`V0.2.6`、`026anything` |
| `setup.py` の推奨表示判定 | `str(None)` が許可値と一致せず、旧版相当とは判定しない | 上記3文字列 | 上記以外。config 側の `env` にキーがあればその値を使い、キーがなければ setup プロセスの環境を参照する |

C++ 判定が true でも、接続先機能の個別条件を満たさなければ効果はありません。たとえば NVIDIA chunk 上限は NVIDIA の bare `--prefill auto` 経路だけで参照され、gfx12 設定は対象 arch/backend の表に限られます（`include/strata/core/nv_chunk.hpp:21-33`; `include/strata/core/arch_defaults.hpp:22-38`）。

## 有効になる条件

- C++ エンジンでは、プロセス内で `qwen_defaults_026()` が最初に呼ばれた時点で環境値が上記3値のいずれかであることが必要です。その結果は関数内 `static const bool` に保存され、同一プロセスで後から環境を書き換えても更新されません（`include/strata/core/defaults_026.hpp:26-30`）。
- 適用は `qwen_defaults_026()` を明示的に使う各コード経路に限られます。関連する GPU/backend/モデル/実行モード条件を満たさない場合、その機能の既定判断自体が行われないか、別の既定経路が使われます。例として bare auto chunk ceiling は `nv_chunk_ceiling()` に渡され、カード世代・単一 GPU / layer-split 条件や `STRATA_NV_CHUNK` とともに判定されます（`src/program/generate.cpp:4253-4256`; `include/strata/core/nv_chunk.hpp:23-36`; `setup.py:8034-8052`）。
- 各機能が読む個別環境変数が明示されていると、その値がマスタースイッチより優先されるルールがあります。共通ヘッダーは `STRATA_GR_V3`、`STRATA_PLE_AUTO_RAM` 等を例示し、CLI の `--pcie-frac` / `--ple-io` も優先すると記しています。個別の優先規則は機能ごとに異なり、すべての環境変数を一括上書きする意味ではありません（`include/strata/core/defaults_026.hpp:10-13`; `src/program/generate.cpp:5194, 5936`; `include/strata/core/sm120_series.hpp:63, 104, 149`）。
- `setup.py` の推奨判定は GPU arch が数字列で、compute capability が 8.0 以上または 7.0、かつ `--gpus` と `--layer-split` が引数にない場合にだけ 32768-token の bare-auto 推奨候補になります。そこで `STRATA_DEFAULTS` が許可値なら候補を false にして tip を抑制します。これは設定の強制やエンジンへの値の転送ではありません（`setup.py:8034-8052, 8068-8070`）。

## 実行時の詳細

エンジン側は `std::getenv("STRATA_DEFAULTS")` を `qwen_defaults_026()` の初回評価時に一度だけ読み、厳密な一致結果を cache します。エンジン起動後の変更はそのプロセスでは反映されません。コマンドラインに `STRATA_DEFAULTS` 専用引数はなく、各機能の明示フラグや個別環境値は接続先の解決関数が扱います（`include/strata/core/defaults_026.hpp:21-30`; `include/strata/core/defaults_026.hpp:10-13`）。

この値が true の場合に旧版相当へ切り替わる具体例は、bare NVIDIA prefill auto の ceiling を 32768 から旧来の 8192 相当へ戻す処理、gfx12 および NVIDIA アーキテクチャ既定表の選択、layer-major prefill の既定解決、PLE 自動 RAM 許可の解決、PCIe share の開始値、split/cache の late allocation 量、batch group の既定解決です（`include/strata/core/nv_chunk.hpp:23-29`; `src/core/arch_defaults.cpp:16, 115`; `src/core/nv_defaults.cpp:22, 127`; `src/prefill/prefill.cpp:8994`; `src/program/generate.cpp:5194, 5936, 6531, 7383, 8581, 8636, 8679, 8707, 9217`; `include/strata/program/batch_groups.hpp:73-80`）。CUDA の fused GR、prompt attention、MMVQ / BF16 dequant、gfx12 decode 既定も同じ bool を使って既定経路を選びます（`src/kernels/cuda/fused_gr.cu:496, 2682`; `src/kernels/cuda/qsa_prompt_attn.cu:2563`; `src/kernels/cuda/native_mmvq.cu:3805, 3904`; `src/kernels/cuda/dequant_bf16.cu:301`; `src/kernels/mmvq_il_parity.cpp:406`; `include/strata/core/gfx12_extra.hpp:40-67`）。

`setup.py` 側では呼び出しごとに config の `env` mapping を複製して確認し、`STRATA_DEFAULTS` がなければ現在の Python プロセス環境を参照します。許可値なら「`--prefill auto` から `--prefill auto:32768` への tip」を出さないだけです（`setup.py:8034-8052, 8068-8070`）。

## ログと測定値

`STRATA_DEFAULTS` 自体の値が無効な場合に警告・エラーを出す処理は確認できません。直接読み取り helper は boolean を返すだけです（`include/strata/core/defaults_026.hpp:21-30`）。また、値に応じた専用ログ文言は確認できません。切り替わるのは接続先の機能処理であり、そこでの挙動・出力は個別機能の条件に従います。

`setup.py` の推奨文は、条件を満たしていて `STRATA_DEFAULTS` が旧版相当でない場合にのみ `tip: with ... --prefill auto:32768 ...` を表示し得ます。旧版相当ならこの tip を抑制します（`setup.py:8068-8070`）。

## 根拠

- 値の完全一致、初回読み取りと cache: `include/strata/core/defaults_026.hpp:21-30`
- 対象既定の説明と個別設定・CLI 優先の原則: `include/strata/core/defaults_026.hpp:1-13`
- エンジン側の全 helper 呼び出し箇所: `src/core/arch_defaults.cpp:16, 115`; `src/core/nv_defaults.cpp:22, 127`; `src/program/generate.cpp:2729, 2974-2978, 4256, 5194, 5936, 6531, 7383, 8581, 8636, 8679, 8707, 9217, 11706`; `src/prefill/prefill.cpp:8994`; `src/kernels/cuda/fused_gr.cu:496, 2682`; `src/kernels/cuda/qsa_prompt_attn.cu:2563`; `src/kernels/cuda/native_mmvq.cu:3805, 3904`; `src/kernels/cuda/dequant_bf16.cu:301`; `src/kernels/cuda/iq_kernels.cu:6199`; `src/kernels/mmvq_il_parity.cpp:406`; `include/strata/core/gfx12_extra.hpp:51, 67`; `include/strata/core/bw_dense_defaults.hpp:16, 19`
- bare-auto の診断用判定: `setup.py:8034-8052, 8055-8070`
- terminal-only の Qwen スイッチ登録: `strata_control/speed_switches.py:61-63`
