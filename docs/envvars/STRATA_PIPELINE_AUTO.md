# `STRATA_PIPELINE_AUTO`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--pipeline-windows` を指定しなかった場合の自動判定を止めるための環境変数です。値が `atoi()` で 0 になると、自動判定の結果を無効にします。値を 1 にしても、それだけでパイプラインを有効にはしません。自動有効化には AMD HIP の gfx12、`--serve`、層分割、MTP drafter など複数の条件が必要です。

自動判定で有効になる `--pipeline-windows 2` は、層分割した各 GPU が別々の verify window を並行処理する機能です。decode 中は先段が次の window を投機的に処理し、後段が現在の window を検証します。明示的な `--pipeline-windows 1` または `2` はこの環境変数による自動判定を通りません（`src/program/generate.cpp:665-670,3507-3522`）。

## 値と判定

環境変数は自動判定ブロックで `std::getenv()` により読み、設定されていれば `std::atoi(ae) == 0` かを調べます。文字列全体の検証や真偽語の比較はしません。

| 値 | 自動判定への影響 |
|---|---|
| unset | この変数による抑止なし。ほかの条件で自動有効化され得る |
| 空文字 | `atoi("") == 0` となり、自動有効化を抑止 |
| 数値として 0 になる文字列（例: `0`, `false`, `abc`, `0xyz`） | 抑止 |
| 数値として 0 以外になる文字列（例: `1`, `2`, `-1`, `1xyz`, ` 2x`） | 抑止しない。ただし、それだけで有効化はしない |

`atoi()` は整数の先頭部分を読み、後ろの非数値文字を検査しません。そのため `1xyz` は非ゼロ、`0xyz` は 0 です。`false` も真偽文字列としては解釈されず、数値変換結果 0 により抑止になります。根拠: `src/program/generate.cpp:3507-3514`。

## 有効になる条件

この変数の値が自動判定を抑止しない場合も、次の条件を満たさなければ自動で有効になりません。

- `--pipeline-windows` が未指定である（内部値 `-1`）。
- `--serve` が指定されている。
- 複数 GPU の layer split であり、同じ GPU に重なる stage 分割ではない。
- stage 数が最小数以上。通常の既定値は 3。MTP drafter が先段 GPU に置ける条件を満たし、HIP gfx12 の既定配置も有効な場合は 2。関連変数 `STRATA_PIPELINE_AUTO_MIN_STAGES` が設定されている場合は `max(2, atoi(value))` が閾値になる（`src/program/generate.cpp:3510-3514`）。
- HIP ビルドであり、現在の GPU が gfx12 WMMA 対応（gfx1200/gfx1201 系）である。CUDA ビルドは自動判定を明示的に無効にする。
- MTP drafter（`--mtp`）があり、`--spec >= 2`。
- `--batch` を使わず、`--peer-device` が未指定で、helper cache がなく、`--adapt-async` が無効。

`--pipeline-windows N` を明示した場合はこの自動条件判定を使わず、正の値について別の適用条件を検査します。手動指定時も `--serve`、layer split、MTP などを満たさない場合、stderr に `strata generate: --pipeline-windows N is off: ...` と理由を出し、設定を 0 にします。したがって `STRATA_PIPELINE_AUTO=1` は CUDA 上で手動指定された値を無効化するものではなく、未指定時の HIP 自動化だけに関係します（`src/program/generate.cpp:3514-3542`）。

## 実行時の詳細

`--pipeline-windows` の初期値は `-1` で、引数指定時は 0〜2 に制限されます。初期値のままなら環境変数を読み、条件に応じて `o.pipeline_windows` を 2 または 0 に決定します。自動有効化された場合、stderr に `strata generate: --pipeline-windows 2 is on by default for a layer split of N stages (--pipeline-windows 0 or STRATA_PIPELINE_AUTO=0 turns it off)` を出します。自動条件を満たさず無効になる場合は、この自動判定からの理由ログは出ません（`src/program/generate.cpp:2133,3507-3525`）。

環境変数の読み取りは関数内 static local の初期化時に一度だけ行われます。したがって、同一プロセスで最初の自動判定後に環境値を変更しても、この読み取り値は再評価されません。CLI で `--pipeline-windows 0` を指定すれば明示的に無効、`1` または `2` を指定すれば環境変数による自動判定を経ない明示設定になります。

## 文書との照合

`docs/MULTI_GPU.md:248-255` は AMD gfx12 の `--serve` + draft layer + 2段以上の層分割で既定有効、`STRATA_PIPELINE_AUTO=0` で無効と説明しています。ソースでも gfx12 HIP 上の自動化を実装しています。ただし実際には stage 数の閾値、batch/peer/helper cache/adapt-async の除外など追加条件があり、2段の既定有効化は drafter を先段へ置ける場合に限られます。NVIDIA の自動判定はソース上常に無効です。ドキュメントの測定値は当該機能の背景として同ページに記載されていますが、この環境変数単独の性能測定ではありません。

## 根拠

- `src/program/generate.cpp:665-670` — `--pipeline-windows` の初期値と機能の説明。
- `src/program/generate.cpp:2133` — CLI 指定時の 0〜2 制限。
- `src/program/generate.cpp:3500-3525` — MTP 先段配置可否、環境変数の読み取りと `atoi` 判定、自動有効化条件、ログ。
- `src/program/generate.cpp:1630-1638` — HIP で gfx12 WMMA 対応 GPU を確認し、CUDA では真を返す共通判定（自動 pipeline 判定側では CUDA を別途無効化）。
- `src/program/generate.cpp:3527-3542` — 明示指定時の適用条件と無効化ログ。
- `docs/MULTI_GPU.md:248-255` — 利用者向けの既定動作と無効化方法。
