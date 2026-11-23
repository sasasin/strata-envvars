# `STRATA_DEFAULTS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen エンジンで 0.2.7 以降に追加された一部の既定動作を、0.2.6 相当へ戻すマスタースイッチ。すべての Strata 設定や全 GPU の動作を一律に戻すものではない。対象になる既定値は各機能の個別判定に渡され、GPU 世代、backend、モデル・実行条件が合う機能だけに作用する。例えば CUDA の世代別既定テーブル、HIP の gfx 世代別テーブル、裸の `--prefill auto` の上限、PLE テーブルの常駐方針、NVIDIA の複数 GPU バッチ群、後段 GPU のメモリ予約などが判定に使う（`engine/include/strata/core/defaults_026.hpp:1-13`, `engine/src/core/nv_defaults.cpp:29-38`, `engine/src/core/arch_defaults.cpp:16-30`, `engine/src/program/generate.cpp:4490-4525,6275-6287,6879-6884,7741-7749`）。

## 値と判定

| 読み取り経路 | unset | 有効になる値 | 設定されていても無効な値 |
|---|---|---|---|
| エンジン共通 `qwen_defaults_026()` | 無効（通常の現行既定値） | 完全一致の `026`、`0.2.6`、`v0.2.6` | 空文字、`0`、`027`、`026 `、` 026`、`TRUE` など、上記以外すべて |
| CUDA QSA の `sm70_default_on()` 内の独立判定 | 無効 | 完全一致の `026` のみ | `0.2.6`、`v0.2.6` を含む上記以外 |
| Terminal の `bare_auto_is_32768()`（設定提案用） | 現プロセスの環境変数に同じ完全一致判定 | `026`、`0.2.6`、`v0.2.6` | それ以外 |

エンジン共通判定は `std::getenv` の結果を `strcmp` で文字列全体比較するため、数値変換・前後空白の除去・大文字小文字の正規化はありません。明示的な空文字は「設定あり」でも無効値です。QSA の CUDA 経路だけは `026` しか認識せず、共通判定と値規則が異なります（`engine/include/strata/core/defaults_026.hpp:21-29`, `engine/src/kernels/cuda/qsa_select.cu:2155-2161`）。

## 有効になる条件

- 共通判定が有効でも、各呼び出し箇所に到達し、対象 backend・GPU・モデル・モードの条件を満たす機能だけが変わります。例として NVIDIA の裸の `--prefill auto` は CUDA build、対象計算能力 8.0 以上または 7.0、可視 GPU 条件などを満たす必要があり、明示的な `--prefill N` / `auto:N` はこの既定値調整の対象外です。適用時は `STRATA_NV_CHUNK` よりマスタースイッチが先に上限を 8192 相当へ戻します（`engine/src/program/generate.cpp:4490-4525`, `engine/include/strata/core/nv_chunk.hpp:21-43`）。
- HIP の AMD 既定テーブルは gfx12 / gfx1151 等のアーキテクチャ分岐を通る場合に限られます。gfx12 では `STRATA_GFX12_DEFAULTS` が先に `0` で無効化するとテーブルは空になり、そうでなければ `STRATA_DEFAULTS` 有効時も従来の prompt 側エントリは残し、新しい decode 側エントリを加えません（`engine/src/core/arch_defaults.cpp:28-64`）。
- PLE の自動常駐方針は直接読み取りモードで、かつ `--ple-io` が明示されていない場合にだけ判定されます。`STRATA_PLE_AUTO_RAM` が設定されていれば `atoi(value) != 0` が優先し、`1` で明示的に再有効化、`0` で無効化できます。未設定ならこのスイッチが有効なとき常駐方針を止めます（ただし RAM 容量等の適合判定も別途必要です）（`engine/src/program/generate.cpp:6275-6295`, `engine/include/strata/core/ple_residency.hpp:32-37`）。
- NVIDIA の世代別既定値では、ユーザーが個別の環境変数を設定している場合、その設定が優先されます。自動設定は未設定変数にだけ書き込みます。CUDA/HIP の世代や個別フラグが対象外なら該当機能への影響はありません（`engine/src/core/nv_defaults.cpp:222-253`; sm_121 等の適用条件は `engine/include/strata/core/sm120_series.hpp:75-81`）。
- `--pcie-frac` など明示 CLI 引数や個別機能変数がある機能では、明示設定がマスター判定に優先するものがあります。一方、全 CLI 引数がこの変数を上書きするわけではありません（`engine/include/strata/core/defaults_026.hpp:10-13,32-38`; PLE の CLI 条件は上記）。
- Terminal の Advanced 設定にある「Qwen: 0.2.6 behaviour」は Terminal 専用の切替項目で、オン時に `STRATA_DEFAULTS=026` を設定します。Terminal 共通で自動的に付与される値ではありません（`terminal/strata_control/speed_switches.py:71-75`）。

## 実行時の詳細

`qwen_defaults_026()` は関数内 `static const bool` に `std::getenv` の判定結果を保存します。最初に呼ばれた時点の値がプロセス内で再利用され、以降の環境変更では更新されません（`engine/include/strata/core/defaults_026.hpp:26-30`）。これは実行時の再設定 API ではなく、子プロセスへの転送処理もこの関数にはありません。

有効時は複数の独立した機能判定が現行既定を抑制または旧値へ戻します。ソース上で確認できる例は、CUDA bare-auto prefill の 32768 上限を抑えること、gfx12 の decode 既定群を追加しないこと、PLE 自動常駐を既定では行わないこと、2 枚の NVIDIA カードで batch groups を serial 側にすること、後段 GPU の予約メモリや Windows WDDM の遅延割当を外すことです（`engine/include/strata/core/nv_chunk.hpp:21-38`, `engine/src/core/arch_defaults.cpp:28-62`, `engine/include/strata/core/ple_residency.hpp:32-37`, `engine/src/program/generate.cpp:7741-7749,6879-6884,9151-9154`）。効果はそれぞれの機能が実行されるときに限られ、生成結果や全設定が必ず 0.2.6 と同一になるというコード上の保証ではありません。

CUDA QSA は別の `static` 判定を持ちます。`scores_thread_on()` の環境変数 `STRATA_SCORES_THREAD` が未設定のときにデバイスごとの既定判定へ進み、Volta では `sm70_default_on()` が呼ばれます。そこでは `STRATA_DEFAULTS` を独自に一度読み、文字列 `026` だけを除外条件として使用します。そのため `0.2.6` / `v0.2.6` は共通ヘルパーでは有効でも、この QSA の Volta 既定には反映されない実装差があります。`STRATA_SCORES_THREAD` が明示されると同関数は先にその `atoi` 判定を返します（`engine/src/kernels/cuda/qsa_select.cu:2155-2176`）。

Terminal の `bare_auto_is_32768()` はエンジン設定ではなく、設定内容に対するベンチマーク提案の判定です。引数 `env` に `STRATA_DEFAULTS` キーがあればその値を使い、キーがなければプロセス環境を参照し、前記3文字列の場合に 32768 の提案条件から外れます。単独 GPU の arch 条件を満たし、`--gpus` / `--layer-split` がない場合だけの提案ロジックで、エンジン引数や設定値を変更しません（`terminal/setup.py:8884-8902,8905-8908`）。

## ログと測定値

変数自体の値を報告する専用ログは確認できません。機能側のログは通常どおり出ることがあります。例えば NVIDIA bare-auto の上限を引き上げたときは `strata generate: NVIDIA: --prefill auto may take chunks up to ...`、引き上げない特定条件では `strata generate: NVIDIA (... GiB): --prefill auto stays at 8192 ...` が stderr に出ます（`engine/src/program/generate.cpp:4514-4525`）。CUDA の世代別既定値を自動設定した場合は `apply_nv_defaults()` が設定されたスイッチ名を stderr に出しますが、マスター変数の判定結果そのものを出力する行ではありません（`engine/src/core/nv_defaults.cpp:222-253`）。

`docs/release-notes-0.2.7.md:28-35` は、このスイッチを Qwen の 0.2.7 既定を戻す用途として挙げ、個別変数・CLI フラグが引き続き優先する旨を記載しています。現行ソースではこの説明と整合する複数の判定を確認しましたが、同資料の一覧は全呼び出し箇所の網羅リストではありません。`docs/SETTINGS.md:365` は NVIDIA / AMD 向け設定として索引化しています。測定値はこの変数単独の効果としては記載しません。

## 根拠

- 共通の値判定とキャッシュ: `engine/include/strata/core/defaults_026.hpp:21-30`
- 独立して環境を読む CUDA QSA 判定: `engine/src/kernels/cuda/qsa_select.cu:2152-2176`
- 代表的な backend / 機能別の適用箇所: `engine/src/core/nv_defaults.cpp:29-38,222-253`; `engine/src/core/arch_defaults.cpp:16-64`; `engine/include/strata/core/ple_residency.hpp:32-37`; `engine/include/strata/core/nv_chunk.hpp:21-43`; `engine/src/program/generate.cpp:4490-4525,6275-6295,6879-6884,7741-7749,9151-9154`
- Terminal の設定 UI と提案判定: `terminal/strata_control/speed_switches.py:71-75`; `terminal/setup.py:8884-8902`
- 設計資料との照合: `docs/SETTINGS.md:365`; `docs/release-notes-0.2.7.md:28-35`
