# `--kv-resident`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--kv-resident N` |
| 別名 | なし |
| 値 | KV の resident 上限を表す cell 数。parser は `std::atoll` で読み取る |

## 役割

QSA 層ごとに VRAM に置く KV cell 数を指定し、それを超える KV を pinned RAM 側に保持して必要時にストリームする設定です。`0`（既定値）ではストリーミングせず、KV 全体を VRAM に置きます。VRAM 上の KV を減らした分は expert cache などに使える余地になりますが、実際に何へ割り当てられるかは他の設定や空き VRAM によります（`src/program/generate.cpp:487`, `src/program/generate.cpp:833-835`, `src/core/layer.cpp:738-755`）。

## 使い方

```sh
strata --native MODEL.gguf --kv-resident 32768
```

`MODEL.gguf` を読む通常のエンジン経路で、各 QSA 層あたり 32,768 cell を基準に KV streaming を有効にします。モデルの最大 context は別途 `--max-context` で決まります（`src/program/generate.cpp:2480-2481`, `src/program/generate.cpp:833-835`）。

## 値と既定値

- 未指定時の値は `0` です。`0` は全 KV を VRAM に置く指定で、負数は標準エラーへ `strata generate: --kv-resident must be >= 0` を出して終了コード `2` になります（`src/program/generate.cpp:487`, `src/program/generate.cpp:3200-3204`）。
- parser は値の欠落を `--kv-resident needs a value` と標準エラーに出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。値の変換は `std::atoll` で行い、数値形式を厳密に検証する処理はありません。したがって、整数でない入力を厳密な validation error として扱う実装ではありません（`src/program/generate.cpp:2481`, `src/program/generate.cpp:3200-3204`）。
- 同じオプションを複数回指定すると parser の走査順に値を代入するため、最後の指定値が残ります（`src/program/generate.cpp:2416-2420`, `src/program/generate.cpp:2481`）。
- `N > 0` の場合でも実効 resident は最低 20,480 cell です。さらに QSA の page 単位に切り上げます。実効 resident page 数が `--max-context` に必要な page 数以上なら streaming mode にならず、全 KV が VRAM に残ります（`src/core/layer.cpp:738-755`, `src/core/layer.cpp:769-771`）。

## 実行時の動作

parser が設定した値は `qsa_set_kv_resident` に渡され、QSA state の KV plan が各層の VRAM slot 数と streaming mode を選びます。streaming 時は最大 context 分の KV を pinned RAM にも確保し、デバイスから参照可能な host copy を用意します。KV append は選択中の形式（標準、Q4、INT8、K8V4）に応じてその host copy にも書き込みます（`src/program/generate.cpp:3200-3204`, `src/core/layer.cpp:738-755`, `src/core/layer.cpp:903-920`, `src/core/layer.cpp:1207-1227`）。

指定値は会話 session の構成 fingerprint に含まれるため、会話の構成識別にも反映されます（`src/program/generate.cpp:9440-9443`, `src/core/conversation_file.cpp:880-885`）。

## 適用条件と副作用

- 対象は索引にある `strata-engine` の通常 `strata` エンジン引数 parser です。Qwen3.6 専用 parser は別 scope です。`--native` が Qwen3.6-35B-A3B を選んだ場合は通常 parser より前に専用実装へ振り分けられるため、本書ではその専用経路の挙動を説明しません（索引 [`docs/cli/README.md:1128-1134`](../../README.md#strata-engine)、`src/program/generate.cpp:2393-2407`）。
- `--kv k8v4` も streaming に対応します。KV の保存形式は `--kv` が選び、本オプションは VRAM と pinned RAM への配置を制御します（`src/program/generate.cpp:827-835`, `src/core/layer.cpp:757-765`, `src/core/layer.cpp:1207-1219`）。
- `--kv-grow` が要求されても、`--kv-resident` が正値なら KV-grow は有効条件を満たさず、標準エラーに「`--kv-grow is off`」と警告されます。KV-grow は全 KV を VRAM に置く条件を必要とするためです（`src/program/generate.cpp:5198-5210`）。
- `--batch` の slot session が VRAM に収まらない場合、エンジンは `--max-context` の縮小または KV streaming を候補として警告します。ただし本オプションを指定すれば必ず batch が有効になるという保証ではありません（`src/program/generate.cpp:5418-5427`）。
- pinned RAM の確保またはデバイス mapping が失敗すると、該当 layer の初期化は失敗し、通常の初期 session では `session_init failed` を標準エラーに出して終了コード `1` になります。確保失敗時には `lower the context, or run without --kv-resident` という案内も標準エラーに出ます（`src/core/layer.cpp:907-917`, `src/program/generate.cpp:5215-5221`）。

## 関連オプション

- [`--kv`](--kv.md): KV の保存形式を選択します。
- [`--max-context`](--max-context.md): KV state の最大 context を設定します。
- [`--kv-grow`](--kv-grow.md): 条件付きの elastic KV allocation を要求します。本オプションの正値とは同時に有効化されません。

## 根拠

索引上の配置は `strata-engine` の `strata`（エンジン引数）です（[`docs/cli/README.md:1128-1134`](../../README.md#strata-engine)、オプションの掲載は [`docs/cli/README.md:1192-1195`](../../README.md#strata-engine)）。値の既定値、parser、負数 validation は `src/program/generate.cpp:487`, `src/program/generate.cpp:2416-2420`, `src/program/generate.cpp:2480-2483`, `src/program/generate.cpp:3200-3204` で確認しました。実効 page 数、pinned host copy、KV append、失敗経路は `src/core/layer.cpp:738-755`, `src/core/layer.cpp:903-920`, `src/core/layer.cpp:1207-1227` と `src/program/generate.cpp:5215-5221` で確認しました。

この調査ではソース checkout と索引を参照し、ビルド済み CLI の `--help` および Release artifact は確認していません。GPU/OS/backend ごとの pin 上限や確保可否は実行環境に依存するため、ここではコード上の失敗経路までを記載しています。
