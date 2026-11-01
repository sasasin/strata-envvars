# `STRATA_DEFAULTS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査範囲は Strata 所有ソース。外部ライブラリ・GPU driver の環境変数動作は対象外。

## 役割

Qwen エンジンの複数の「0.2.7 で変わった既定値」を v0.2.6 相当に戻すマスタースイッチです。変数自体が各機能を一括設定するのではなく、共通 helper が環境値を一度判定し、その bool をアーキテクチャ別既定値、生成処理、prefill、batch group などの規則に渡します。判定結果によって既定値が変わるのは対象の機能・条件に限られます。`include/strata/core/defaults_026.hpp:1-13,26-30`。

現行 HEAD で確認できた影響は、gfx12 の decode 既定値、CUDA sm_121 の速度設定、特定 CUDA カーネルの既定、gfx12 native pack の PCIe 分担開始値、PLE 表の自動 RAM 常駐ポリシー、2 NVIDIA GPU の batch group 既定、automatic expert cache の追加予約、CUDA layer-split の layer-major prefill です。個々の設定を明示すれば、多くの機能ではその設定が優先されます。現行コードでは `STRATA_ROUTE_PRIOR` の既定値はスイッチの有無によらず 0 で、このマスタースイッチによる変化はありません。KVA の既定値もこのスイッチでは変わりません。`include/strata/core/defaults_026.hpp:3-13`; `include/strata/core/sm120_series.hpp:59-68`。

## 値と判定

`include/strata/core/defaults_026.hpp:21-29` の `is_026_token()` が `std::getenv("STRATA_DEFAULTS")` の戻り値を、`strcmp` による大文字小文字を区別した文字列全体比較で判定します。数値変換、trim、前方一致はしません。

| 環境値 | 判定 | 結果 |
|---|---|---|
| 未設定 | false | 通常の現行既定値 |
| `026` | true | 該当する機能を v0.2.6 相当にする |
| `0.2.6` | true | 同上 |
| `v0.2.6` | true | 同上 |
| 空文字、`0`、`027`、`026 `、`V0.2.6` など | false | 通常の現行既定値 |

部分一致や数値として等価な文字列は受け付けません。たとえば `v0.2.6 `、`026anything`、`0.2.06` は false です。

## 有効になる条件

- **GPU・ビルド条件**: gfx12 / gfx1151 のアーキテクチャ既定値は HIP の起動経路で適用され、全可視 GPU が同じ統合 GPU 条件を満たす場合の設定もあります。CUDA の NVIDIA 既定値は、全可視 CUDA GPU が同一 compute capability の場合に限り適用されます。sm_121 の表は CUDA でのみ使われます。`src/program/generate.cpp:3383-3400,3445-3459`; `src/core/nv_defaults.cpp:23-79`。
- **gfx12 既定値**: `STRATA_GFX12_DEFAULTS` が先頭文字 `0` なら表全体が空になり、`STRATA_DEFAULTS` より先に除外されます。それ以外で `STRATA_DEFAULTS` が該当値なら既存の prompt 用 5 設定は残りますが、0.2.7 で加わった decode 用 `STRATA_ATTN_LANECELL`、`STRATA_ATTN_MERGE_V2`、`STRATA_TSUM`、`STRATA_EXPDEC` は加わりません。`src/core/arch_defaults.cpp:25-53`。
- **gfx1151 既定値**: `STRATA_GFX1151_DEFAULTS=0` が表を止めます。`STRATA_DEFAULTS` は gfx1151 表全体を止めるものではなく、Windows で通常外される `STRATA_SH_STREAM` を v0.2.6 相当に戻して表へ含めます。`src/core/arch_defaults.cpp:55-90`。
- **明示設定と CLI**: アーキテクチャ/NVIDIA の既定値適用は、各機能環境変数が設定済みなら値の内容にかかわらず上書きしません。個別ルールも明示値を先に解釈するものがあります（例: `STRATA_MMVQ_IL_89` の先頭文字 `1` / `0`、`STRATA_PLE_AUTO_RAM` の `atoi`）。`--ple-io` が明示された場合は PLE 自動 RAM 判定自体に入りません。`--batch-groups` を数値または `auto` で明示すると、二枚 NVIDIA GPU の「既定 serial」への変更は適用されません。`src/core/arch_defaults.cpp:175-180`; `src/core/nv_defaults.cpp:82-92`; `include/strata/core/sm120_series.hpp:87-100`; `include/strata/core/ple_residency.hpp:30-35`; `src/program/generate.cpp:4748-4752`; `include/strata/program/batch_groups.hpp:92-107`。
- **実行条件による不適用**: layer-major prefill の現行既定は CUDA の layer split（2 stage 以上）のみです。`STRATA_DEFAULTS=026` で既定 OFF になります。HIP は既定 OFF で、明示値があっても実行時に辞退する経路があります。`src/prefill/prefill.cpp:7233-7242`; `include/strata/core/sm120_series.hpp:107-119`。

## 実行時の詳細

### 読み取り・cache

環境からの直接読み取りは `include/strata/core/defaults_026.hpp:27-29` の一箇所です。`qwen_defaults_026()` の関数内 `static const bool` に保存され、プロセス内の最初の呼び出し時に一度だけ環境を読みます。その後の環境変更は反映されません。GPU ごとの初期既定値適用は、engine の switch 読み取り前に行われます（`src/program/generate.cpp:3383-3400,3445-3459`）。

### 対象機能と処理

| 経路 | `STRATA_DEFAULTS` が該当値のとき | 条件・個別指定・結果 |
|---|---|---|
| gfx12 decode 既定 (`src/core/arch_defaults.cpp:25-53`) | 上記4つの decode 用環境値を Strata が既定設定しない | gfx12 HIP で `STRATA_GFX12_DEFAULTS` が無効化していない場合。明示値がある変数は `apply_arch_defaults()` が保持する。既定値ログは設定したものがある場合のみ出る。ログ形式は `strata: gfx12 (RDNA4): ... exact speed switches on by default ...`。`src/core/arch_defaults.cpp:175-189`。 |
| gfx1151 Windows shared-expert stream (`src/core/arch_defaults.cpp:55-90`) | `STRATA_SH_STREAM=1` を既定値表へ戻す | HIP gfx1151 のアーキテクチャ表適用時。利用者が同変数を設定済みなら既定値で上書きしない。 |
| NVIDIA sm_121 (`src/core/nv_defaults.cpp:53-79`) | `STRATA_PF_FUSED`、`STRATA_PREFILL_NVFP4`、`STRATA_HC_UPMIX`、`STRATA_SPEC_COST` の既定値表を空にする | CUDA、全可視デバイスが同一 capability 12.1 の場合。`STRATA_SM121_PERF` が先頭文字 `0` でも表は空。スイッチ値を設定する処理がないため、この経路では既定スイッチの一覧ログも出ない。 |
| CUDA カーネル既定 (`include/strata/core/sm120_series.hpp:45-48,70-105`; `src/kernels/cuda/native_mmvq.cu:3779,3878`; `src/kernels/cuda/dequant_bf16.cu:299-301`; `src/kernels/cuda/fused_gr.cu:488,2376`) | `STRATA_GR_V3`、`STRATA_PROMPT_ATTN_IMMA`、`STRATA_MMVQ_IL_89`、`STRATA_GR_UP_WIDE` の未設定時既定を OFF。sm_80 の wide dequant と MMVQ-IL も未設定時 OFF | GPU capability / CUDA 条件を各規則が満たす場合。sm_80 系は個別変数が先頭文字 `1` / `0` ならそちらを採用。Ada の MMVQ-IL も先頭文字 `1` / `0` が優先。 |
| gfx12 native pack PCIe 分担 (`src/program/generate.cpp:4226-4233`; `include/strata/core/defaults_026.hpp:32-39`) | 自動 `--pcie-frac` の開始値を gfx12 の 0.15 から 0.55 に戻す | `--pcie-frac` が未指定（`o.pcie_frac < 0`）、native pack、gfx12既定が有効で、`STRATA_PCIE_FRAC_DEFAULT=old` による旧値指定などがない場合。`--pcie-frac` 明示値はこの計算を通らない。 |
| PLE 表の自動 RAM 常駐 (`src/program/generate.cpp:4748-4763`; `include/strata/core/ple_residency.hpp:30-35`) | `STRATA_PLE_AUTO_RAM` 未設定ならポリシーを許可しないため、Direct 読み込みのまま | `--ple-io` 未指定で、環境値が未設定のとき。明示された `STRATA_PLE_AUTO_RAM` は `atoi(value) != 0` で判定し、空文字や数値に変換できない文字列は 0 扱い。許可されても表サイズ・expert arena・8 GiB headroom が RAM に収まり、表を開けた場合だけ mmap+lock に切り替わる。成功時は `--ple-io ram chosen by the residency policy` を stderr に出す。open 失敗時は `resident PLE table failed (...); keeping direct reads` と出して Direct に戻し、Direct 再オープンにも失敗すれば `strata generate: <error>` の後に status 1 で終了する。`src/program/generate.cpp:4761-4783`。 |
| 2 NVIDIA GPU の batch group (`src/program/generate.cpp:6028-6045`; `include/strata/program/batch_groups.hpp:73-107`) | `STRATA_BATCH_GROUPS_NV_SERIAL` が未設定または空のとき serial 1 group を選ぶ | CUDA で後段 stage が1つ、batch が複数、`--batch-groups` を明示せず、`--batch-mtp` / `--adapt-async` が serial 選択を優先しない場合。個別変数が空でない場合は先頭文字が `0` なら false、それ以外は true。CLI で group 数または `auto` を指定した場合は明示指定が優先される。serial の説明文字列は `serial windows (STRATA_BATCH_GROUPS_NV_SERIAL=1 or STRATA_DEFAULTS=026 asked for them on two NVIDIA cards; --batch-groups auto pipelines)`。`include/strata/program/batch_groups.hpp:118-120`。 |
| `--expert-cache auto` の late allocation (`src/program/generate.cpp:6948-6954`; `include/strata/core/auto_cache.hpp:30-44`) | 未価格だった後続 GPU 割当分 256 MiB を cache サイズ計算から引かない（v0.2.6 の sizing） | `--expert-cache auto` 経路。通常は 256 MiB を引いた slot 数を採用し、引いた後に最小 slot 数を満たせなければ plain 計算へ戻る。`STRATA_DEFAULTS=026` では常に plain 計算。起動時に `expert cache auto: ... -> N slots` を stderr に出し、256 MiB を予約した場合だけ `(+256 MiB for what is allocated after the cache)` と表示する。 |
| CUDA layer-split prefill (`src/prefill/prefill.cpp:7233-7271`; `include/strata/core/sm120_series.hpp:107-119`) | 未設定時の layer-major walk を OFF | 明示 `STRATA_PREFILL_LAYER_MAJOR` は先頭が空でない場合 `atoi()!=0` で決まり、空または未設定なら既定規則へ進む。明示値がない状態で layer-major が有効な場合は stderr に `layer-major prefill is on for this layer split ... STRATA_DEFAULTS=026 turns it off` を出す。準備不能・prompt 条件不成立時は `layer-major off for this prompt: ...` と出して通常 `run_impl()` に進む。 |

アプリ内 Terminal の Advanced 表にも「Qwen: 0.2.6 behaviour」というトラブルシューティング項目があり、ON 時に `STRATA_DEFAULTS=026` を設定します（`strata_control/speed_switches.py:56-59`）。これはエンジンの追加 CLI 引数ではありません。リリースノートも本変数を Qwen 向けの切り戻しスイッチとして説明しています（`docs/release-notes-0.2.7.md:26,33`）。

## ログ・終了・失敗経路

`STRATA_DEFAULTS` 自体の値が不正でも警告・エラー・終了は発生せず、単に false として扱われます。共通判定からのログ出力はありません。上記の各機能が適用された場合のログはその機能側で出ます。sm_121 表では既定値自体を設定しないため、その表の既定値一覧ログは出ません。`STRATA_DEFAULTS` の判定だけが原因で終了する経路は確認できません。PLE 表の open failure は値のエラーではなく、条件を満たした自動常駐処理の失敗であり、上記の fallback / 終了条件になります。

## 根拠

- 値の完全一致判定とプロセス内一度の読み取り: `include/strata/core/defaults_026.hpp:21-30`。
- 対象処理への helper 伝播: `src/core/arch_defaults.cpp:13-15`; `src/core/nv_defaults.cpp:19-23`; `src/program/generate.cpp:4233,4751-4753,6041-6045,6951-6954`; `src/prefill/prefill.cpp:7238-7242`; `src/kernels/cuda/native_mmvq.cu:3779,3878`; `src/kernels/cuda/dequant_bf16.cu:299-301`; `src/kernels/cuda/fused_gr.cu:488,2376`。
- 起動時の GPU 条件と個別値保持: `src/program/generate.cpp:3383-3400,3445-3459`; `src/core/arch_defaults.cpp:175-189`; `src/core/nv_defaults.cpp:82-105`。
- 関連説明: `docs/release-notes-0.2.7.md:20-23,26,33`; `docs/DGX_SPARK_LINUX.md:117`; `include/strata/core/defaults_026.hpp:3-13`。
