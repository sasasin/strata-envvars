# `STRATA_KVA_MIN_PROMPT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

KVA（approximate late-layer prompt read）が対象にする、1 回の prefill read の最小長を token 数で指定します。既定値は 4096 です。値は KVA が有効なときにのみ `n < min_prompt` 判定へ使われ、短い read は通常の完全計算経路になります。KVA 自体は別の環境変数 `STRATA_KVA` で opt-in する機能です。`STRATA_KVA_MIN_PROMPT` 単独では KVA を有効にしません。

## 値と判定

`kva_env_i64()` は未設定または空文字列なら渡された既定値を返し、それ以外は `std::atoll` の結果を `int64_t` にします。文字列全体の厳密な数値検証やエラー処理はありません。`atoll` の通常の変換規則により、先頭空白と符号を含む整数の先頭部分を変換し、後続の非数値文字は変換結果に含めません。数字として読めない文字列は 0 になります。

| 値 | `min_prompt` | 長さ判定への影響 |
|---|---:|---|
| 未設定 | 4096 | `n < 4096` の read は KVA を使わない |
| 空文字列 | 4096 | 未設定と同じ |
| 整数文字列 | `atoll` の結果 | `n < min_prompt` なら KVA を使わない |
| 数字で始まらない文字列 | 0 | この下限判定では通常の非負 `n` を拒否しない |
| 0 または負数 | 0 または負数 | この下限判定では通常の非負 `n` を拒否しない |

この設定に clamp はありません。したがって非常に大きな値は通常の長さを下限未満にし、負数はこの下限条件を実質的に通します。ただし、いずれの場合も suffix を残す条件など別の適用条件は残ります。数値範囲を超える文字列について、実装は `atoll` のエラーを検査していません。

CLI 引数や設定ファイルによる上書きは見つかりません。優先関係は環境変数、または未設定・空の場合の既定値 4096 です。

## 有効になる条件

この値が実際の分岐に影響するには、まず `STRATA_KVA` が空でない値に設定され、その先頭文字が `0` 以外である必要があります。`STRATA_KVA` が未設定・空・`0` で始まる値なら KVA は無効で、この最小長設定も適用されません。

さらに KVA は CUDA/HIP の state-only late-layer path を持つビルドでのみ有効です（Metal は `STRATA_GPU_METAL` 定義時に無効）。単一 GPU で、`--batch` の slot がなく、`--peer-device` を使わず、全 trunk の read であり、継続 read（`pos0 != 0`）でも画像 prompt でも DFlash2 tap 付きでもない必要があります。`STRATA_KVA_CAPTURE` が有効な capture mode では exact path になり、この最小長判定より先に KVA が decline します。通常の対象形状は 48 layers / 512 experts で、異なる形状では `STRATA_KVA_ANY_MODEL` の有効化がない限り exact path になります。さらに prompt 長 `n` は `min_prompt` 以上、かつ完全計算 suffix と 64 token の合計より大きくなければなりません。suffix の既定値は 2048 で、`STRATA_KVA_SUFFIX` が正の値ならその値です。

サーバーの各 prefill 部分もそれぞれの `n` と `pos0` で判定されるため、環境変数は会話全体の累積長ではなく、その read の長さに対する下限です。後続 turn の continuation は `pos0 != 0` なので KVA 対象外です。

## 実行時の詳細

設定は `kva_config_from_env()` で読み込まれ、通常の生成経路では `kva_config()` の関数内 `static const KvaConfig` に保持されます。最初のアクセス後にプロセス環境を変更しても再読込されません。`STRATA_KVA_MIN_PROMPT` 自体は通常の CLI 起動時、KVA 設定を参照する時点で一度読み込まれます。

prefill は `KvaConfig::decline()` で `n < min_prompt` を判定します。下限未満なら理由は `the prompt is shorter than STRATA_KVA_MIN_PROMPT` です。この理由は routine decline とされ、`STRATA_KVA=1` でも短い prompt ごとの「KVA configured but NOT applied」ログは抑制されます。KVA が適用された場合の prefill ログには split、suffix、近似した position 数が出ます。KVA が有効でも、モデル形状、GPU/CLI条件、continuation など他の条件に合わなければこの閾値だけでは適用されません。

## 根拠

- 値の既定値、型、env helper の変換と空値の処理: `include/strata/prefill/kva.hpp:87,137-141,157-160`。
- 実際の prompt 長判定、順序、および短い read を routine decline とする処理: `include/strata/prefill/kva.hpp:104-129`。
- `STRATA_KVA` の opt-in 判定、Metal backend guard、設定全体の static cache: `include/strata/prefill/kva.hpp:43-49,150-160,191-195`。
- 生成起動時の CUDA/HIP backend 条件、layer split / batch / peer device によるプロセス単位の block: `src/program/generate.cpp:6257-6279`。
- 1 回の prefill read に対する判定とモデル形状条件: `src/prefill/prefill.cpp:2947-2966`。
- suffix を残した近似 frontier と chunk 判定: `src/prefill/prefill.cpp:2964-2966,3118-3122`。
- decline 時のログ抑制および KVA 適用・非適用ログ: `src/prefill/prefill.cpp:5820-5856`。
- Strata の KVA 説明および変数表（4096 の既定値と条件）: `docs/KVA.md:43-58,106-115`。
