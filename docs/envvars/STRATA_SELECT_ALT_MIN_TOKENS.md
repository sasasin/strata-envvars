# `STRATA_SELECT_ALT_MIN_TOKENS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

HIP 版の QSA block scorer で、warp scorer の代わりに FP32 tiled SIMT scorer または gfx12 WMMA scorer を選べる最小の読み取り長を指定します。値は token 数として扱われ、selector が使う block 数に `R=4` を掛けた値と比較されます。この変数だけでは代替 scorer を有効にしません。`STRATA_SELECT_SIMT` または `STRATA_SELECT_WMMA` によって scorer が選ばれている必要があります。selector は prefill の QSA 選択で呼ばれます（`src/prefill/prefill.cpp:4270-4285,7497-7510`）。

## 値と判定

HIP ビルドの `qsa_block_scores_tc()` が初めて閾値を評価するとき、環境から読み取った文字列を `std::atoll()` で変換し、結果を関数内 `static const` に保存します。

| 環境値 | `alt_min_env` | 判定時の扱い |
|---|---:|---|
| 未設定 | -1 | 原則として閾値なし。ただし `STRATA_SELECT_SIMT` が未設定で、community tuning が有効な gfx103x の既定 `2` が選ばれた場合は 28,672 token の既定を使う |
| 空文字 | -1 | 未設定と同じ |
| 数値が 0 以上 | その数値 | `reach_all * 4` がその数値未満なら代替 scorer を使わず、呼び出し元が warp scorer に戻る |
| 負数 | 負数 | `alt_min_env >= 0` を満たさないため、未設定時と同じ fallback を使う |
| 数字で始まらない非空文字列 | 0 | 変換結果が 0 なので長さ制限なし |

`atoll` による変換のため文字列全体の妥当性確認はありません。数値の後ろに続く文字は変換結果に影響せず、先頭の空白や符号も変換関数の規則に従います。値の境界チェックやエラー報告はありません。たとえば `28672tokens` は 28,672、`junk` は 0、`-1` は sentinel として fallback になります。根拠: `src/kernels/cuda/qsa_select.cu:2231-2238`。

## 有効になる条件

- この環境変数を直接読むのは `#if defined(__HIPCC__)` 側の実装です。CUDA 側の `#else` にはこの読み取りも閾値判定もなく、この変数は CUDA ビルドの QSA selector に影響しません（`src/kernels/cuda/qsa_select.cu:2208-2238,2271-2273`）。
- `STRATA_SELECT_SIMT` が先頭文字 `1` または `2` の場合、または `STRATA_SELECT_WMMA` が空でなく先頭文字が `0` 以外の場合に、閾値判定へ進みます。その他の `STRATA_SELECT_SIMT` 値は SIMT scorer を選びません。WMMA scorer はさらに gfx12 デバイスが必要です（`src/kernels/cuda/qsa_select.cu:2208-2226,2235-2260`）。community tuning が有効な gfx103x では、`STRATA_SELECT_SIMT` を明示していない場合に mode 2 が選ばれ、その既定経路に限り本変数が未設定なら 28,672 token の fallback になります。明示した `STRATA_SELECT_SIMT=2` はこの暗黙の閾値を使いません（`include/strata/core/amd_community.hpp:75-81`, `src/kernels/cuda/qsa_select.cu:2221-2238`）。
- 通常の HIP `strata` 起動では、デバイス情報取得に成功すると `apply_arch_defaults()` が呼ばれます。RDNA4 の gfx12 で `STRATA_GFX12_DEFAULTS` の先頭文字が `0` でなく、`STRATA_DEFAULTS=026` 系の既定セットが有効でなければ、未設定の `STRATA_SELECT_WMMA` と本変数にそれぞれ `1` と `28672` を設定します。gfx12 以外、この既定抑止条件に当たる場合、または HIP エンジンの当該起動経路を通らない場合、この自動設定はありません（`src/program/generate.cpp:3702-3719`, `src/core/gfx12_extra.hpp:48-60`, `include/strata/core/defaults_026.hpp:21-30`, `src/core/arch_defaults.cpp:244-255`）。
- 既定注入は `getenv(...) != nullptr` なら値を上書きしません。したがって利用者が空文字を含む値を明示した場合も注入されず、selector の読み取り結果に従います。CLI の専用引数はなく、環境値が設定されていなければ gfx12 の既定注入値、そうでなければ環境値が使われます（`src/core/arch_defaults.cpp:247-250`）。
- 本変数のみを設定しても scorer は有効化されません。また、明示した `STRATA_SELECT_WMMA=0` は WMMA を選ばず、明示した `STRATA_SELECT_SIMT` が有効でなければ閾値は使用されません。gfx12 の `STRATA_GFX12_DEFAULTS=0` は自動注入を止めますが、利用者が別途設定した selector 変数を消去する処理ではありません（`include/strata/core/gfx12_extra.hpp:48-57`, `src/core/arch_defaults.cpp:247-255`）。

## 実行時の詳細

`qsa_block_scores_tc()` は形状・行数などの初期条件を満たした呼び出しで閾値を初めて読み、その整数値をプロセス内で cache します。起動後に環境を変更しても、この関数での閾値は再読込されません。通常の gfx12 既定注入は selector 呼び出しより前に行われます（`src/kernels/cuda/qsa_select.cu:2204-2238`, `src/program/generate.cpp:3702-3719`）。

比較対象は `active_blocks` が正かつ `max_blocks` 未満なら `active_blocks`、それ以外なら `max_blocks` とした `reach_all` です。`reach_all * R < min_tok` なら関数は `false` を返し、prefill 呼び出し元は `qsa_block_scores()` の warp scorer を実行します。閾値以上なら選ばれた SIMT または WMMA scorer を実行します。したがって境界値と等しい長さでは閾値による fallback は起きません（`src/kernels/cuda/qsa_select.cu:2235-2269`, `src/prefill/prefill.cpp:4276-4284,7501-7510`）。

gfx12 の既定注入で WMMA scorer を設定した場合、Strata は stderr に `strata: gfx12 (RDNA4): the matrix-core QSA block scorer is on once a prompt is past 28,672 tokens ...` の起動メッセージを出します。この文言は測定値も含む実装ログです。既定注入がなく、または既存設定があっても、このログが常に出るわけではありません。閾値の無効値に対する専用警告・終了経路はありません（`src/core/arch_defaults.cpp:244-255`）。

## 資料との照合

`docs/AMD_HIP.md:305` の速度スイッチ表は gfx12 の `STRATA_SELECT_WMMA` を「Off」としています。一方、現行ソースでは上記の gfx12 既定条件を満たす通常 HIP エンジン起動時に `STRATA_SELECT_WMMA=1` と本変数の `28672` を自動設定します。表の説明はこの既定注入条件を反映していません。実際の動作は調査対象 commit のソースを根拠にしています。

## 根拠

- `src/kernels/cuda/qsa_select.cu:2204-2238,2240-2269,2271-2273` — HIP 側の閾値読込、SIMT/WMMA 条件、長さ判定、代替 scorer の dispatch。CUDA 側には本変数の処理がない。
- `src/core/gfx12_extra.hpp:48-60` — gfx12 用に `STRATA_SELECT_WMMA=1` と `STRATA_SELECT_ALT_MIN_TOKENS=28672` を返す条件。
- `src/core/arch_defaults.cpp:244-255` — 既存値を保つ注入と gfx12 scorer の stderr メッセージ。
- `src/program/generate.cpp:3702-3719` — 通常 HIP 起動時のデバイス判定後に既定値を適用する箇所。
- `include/strata/core/defaults_026.hpp:21-30` — `STRATA_DEFAULTS` の許容 token と起動後 cache。
- `include/strata/core/amd_community.hpp:75-81` — gfx103x に限る community SIMT mode 2 の既定条件。
- `src/prefill/prefill.cpp:4270-4285,7497-7510` — QSA selector 呼び出しと `false` 時の warp scorer fallback。
- `docs/AMD_HIP.md:295-305` — `STRATA_SELECT_WMMA` の説明との照合。
