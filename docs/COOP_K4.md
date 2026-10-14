# `COOP_K4`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。Strata 所有のソースを対象とし、外部ライブラリの動作は対象外。

## 役割

Metal エンジンが、行列演算の右入力 cooperative tensor の要素配置を K 方向に4個ずつ扱う kernel 経路（ソース内の「K4」「M5 layout」）を使うか選びます。値は単独で環境全体の Metal 機能を切り替えるものではなく、decode window と一部の prompt kernel の選択に使われます。

## 値と判定

`Window::coop_k4()` は `std::getenv("COOP_K4")` を読み、値が設定されていれば `std::atoi(e) != 0` を返します。文字列全体の比較ではなく、`atoi` が先頭から解釈できる整数が 0 かどうかで判定します。

| 環境値 | 判定 |
|---|---|
| 未設定 | 下記の cooperative tensor 配置プローブの結果を使う |
| 空文字、`0`、`00`、数値に変換できない文字列（例: `true`） | 無効（false） |
| `1`、`-1`、先頭の整数が非0の文字列（例: `1tail`） | 有効（true） |
| `0tail` | 無効（false） |

`atoi` の数値変換規則に従い、先頭の空白や符号を許し、整数として読める部分の後ろは判定に使いません。整数型の範囲を超える入力の結果はこの文書では保証しません。

変数が未設定なら、`mm_bench.metal` の `coop_layout_16_64_32` kernel を実行し、出力を調べます。32 lane の各出力について、capacity 内の4要素ごとに K index が連続し、N index が同一かを確認します。すべて条件を満たした場合だけ K4 を選びます。プローブ失敗時は古い配置（K4 無効）です。環境変数が設定されているとこのプローブを行わず、`atoi` の判定で結果を上書きします。

## 有効になる条件

- この直接読み取りは `metal/src/engine/prompt_chain.inc` の Metal `Window` 実装にあります。CUDA/HIP/SYCL 実装でこの名前を読むコードは確認できません。
- 値が有効でも、Metal kernel が K4 としてコンパイル・dispatch される経路でなければ効果はありません。通常の `prompt_run_rows()` では、`STRATA_METAL_PROMPT=window` でなく、streaming でなく、prompt 長が `STRATA_METAL_PROMPT_MIN`（既定32行）以上の場合に `Window::prompt()` の prompt chain が選ばれます。それ以外では decode-window prompt 経路になります（`metal/src/engine/window.cpp:2555-2585`）。
- 環境値の明示設定はプローブ結果の代わりになるため、実機の配置に対する互換性確認をコード内で行いません。非対応レイアウトを強制した場合の正確性・性能はソースだけから保証できません。
- `Window::m5_layout()` は最初の呼び出し時に結果を `m5_layout_` に保存し、その後は再判定しません。prompt-chain の `pc_setup()` も初回の buffer setup 時に `b.k4` を保存します。通常の起動時設定を前提にしてください。

## 実行時の詳細

**decode window:** `window.cpp` の decode MoE dispatch は `m5_layout()` の結果を使います。K4 が無効なら M4 向けの tile 形状（特に Q5_1 / Q8_0 down projection の tile 幅と分割）を選びます。K4 有効時は M5 向け設定を使います。根拠は `metal/src/engine/window.cpp:376-377,805-812,1788-1795` です。

**prompt chain:** `pc_setup()` は初回に `b.k4` を保存し、expert GEMM の `mm_gu3` / `mm_down3` と K4 用 QSA attention kernel を選択します。K4 が無効なら `mm_gu2` / `mm_down2` と旧 QSA attention 経路を使います。K4 有効時は function constant 7 に `true` を渡し、tile grid と `meta` の分割値もK4向けにします。該当 dispatch は `metal/src/engine/prompt_chain.inc:49-60,92-99,238-260,299-323`、kernel 内の分岐は `metal/kernels/moe_mm.metal:403-408,808-849,864-910` と `metal/kernels/qsa_prompt.metal:11-16,52-80,250-280` です。初期化時には `COOP_K4` または旧 kernel 経路を示す stderr の `strata metal: prompt kernels ...` ログも出ます（同ファイル `:98-100`）。`Window::prompt()` 自体は `STRATA_METAL_PROMPT_CHUNK`（既定2048、64行単位に丸め）で処理 chunk を決めます（`prompt_chain.inc:394-406`）。

**別の streaming prompt GEMM 経路:** `window.cpp:2040` は外部の `::coop_k4(*cx_)` を呼んで `p.k4` を設定します。その関数定義は Strata 所有ソース内で確認できず、この呼び出しが `COOP_K4` を読むか、どのように判定するかは本調査の対象範囲から確定できません。そのため、この経路の環境変数による挙動は断定しません。なお `STRATA_METAL_PROMPT_EXPERTS` と `STRATA_METAL_PROMPT_QSA` が明示設定されると、それぞれ expert/QSA の方式選択を別途上書きします（`window.cpp:2041-2044`）。

## 根拠

- `metal/src/engine/prompt_chain.inc:26-47` — 環境変数の読み取り、`atoi` 判定、未設定時の配置プローブ。
- `metal/src/engine/window.cpp:354,376-377,805-812,1788-1795` — decode window からの参照、結果のキャッシュ、decode tile 選択。
- `metal/src/engine/prompt_chain.inc:49-60,92-100,238-260,299-323` — prompt chain の値保持、ログ、QSA/expert GEMM の dispatch。
- `metal/kernels/moe_mm.metal:403-408,808-849,864-910`; `metal/kernels/qsa_prompt.metal:11-16,52-80,250-280` — function constant と K4/旧配置の kernel 内処理。
- `docs/DETAILS.md` と Metal 関連の文書には `COOP_K4` の利用者向け説明や、この変数の測定値を確認できませんでした。したがって性能差や出力同一性は記載していません。
