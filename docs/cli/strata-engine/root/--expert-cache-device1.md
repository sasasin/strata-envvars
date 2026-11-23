# `strata`（エンジン）`--expert-cache-device1`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの root parser。生成処理は `strata generate`） |
| オプション | `--expert-cache-device1` |
| 別名 | なし |
| 値 | `N`（整数として `atoi` で変換）または `auto` |

## 役割

主 GPU（CUDA0）の expert cache に加えて、helper GPU の CUDA1 に追加の expert cache を作ります。選ばれた expert blob は CUDA1 の VRAM に保持され、prompt 中に必要な blob をそこから読み出します。CUDA1 上での cache 構築・expert pool からの読み込みに失敗すると起動を中断します。値 `auto` は、CUDA1 に少なくとも 512 MiB の空きを残せる範囲で、順位付き expert をできるだけ多く配置します。

## 使い方

```sh
# CUDA1 に収まるだけ配置する
strata generate --expert-profile profile.json --expert-cache 8192 --expert-cache-device1 auto model.gguf

# CUDA1 に最大 2000 件を配置する（実際に保持する件数は未配置 expert 数にも制限される）
strata generate --expert-profile profile.json --expert-cache 8192 --expert-cache-device1 2000 model.gguf
```

## 値と既定値

- 引数は必須です。値を省くと parser が `--expert-cache-device1 needs a value` を stderr に出し、終了コード 2 で終了します。
- CUDA/HIP の実装では `auto` は内部で上限値として扱われ、空き容量と 512 MiB の headroom を見ながら配置数を決めます。headroom を保って 1 件も配置できない場合は失敗します。SYCL 実装は `auto_size` を使わず、選んだ cache 全体の後段容量検査で判断するため、同じように空き分まで自動で縮むとは限りません。
- 数値は `std::atoi` で変換され、正の値だけが cache 初期化の対象になります。`0`、負数、数値として読めない文字列は 0 以下となり、この helper cache を有効にしません。parser に厳密な数値形式・上限検証はありません。
- 未指定時の値は 0 で、helper cache は無効です。

## 実行時の動作

CUDA1 cache は、主 GPU の cache にある expert と layer split の各 stage が既に保持している expert を除き、expert profile の順位に沿って構成されます。`N` は配置数の上限です。`auto` では各 expert の blob サイズを見積もり、CUDA1 の空き VRAM から 512 MiB を残して収まるところまで選びます。選択した blob を helper GPU に読み込み、最初の slot を検証した後、stderr に追加 expert 数と使用 GiB を出します。実行中の helper cache hit は cached blob を利用し、helper にない blob は fallback source から読みます。helper で計算した結果行は pinned host rows 経由で返されます。

`--expert-cache-device1` を正の値にする場合は `--expert-profile`、正の `--expert-cache`、expert pool（`--no-pool` で無効にしていないこと）が必要です。満たさない場合は理由を stderr に出して終了コード 2 になります。`--peer-device` とは同時に指定できず、併用時も終了コード 2 です。layer split との併用では stage が使わない可視 GPU が helper に割り当てられます。主 GPU が CUDA0 でない構成では、helper は主 GPU を除く可視 ordinal の順に割り当てられます。

`--expert-cache-device2` / `--expert-cache-device3` は追加 helper の上限です。現行実装では helper cache の構築処理自体が `--expert-cache-device1` の正値を入口にするため、device1 が無効なら device2/3 だけでは cache は構築されません。device2/3 も有効にした場合は複数 helper に順位を stripe（既定）または layer 単位で割り当てます。割当方法を変える `--expert-cache-remote-placement` は `stripe` または `layer` のみ受理されます。

## 適用条件と副作用

- オプションは推論エンジンの parser に属し、Terminal CLI の同名 `strata` コマンドとは別スコープです。索引上の配置は [`strata-engine` root の一覧](../../README.md)です。
- 実際に helper cache を作ると CUDA1 の context を初期化し、VRAM cache と pinned host / device 側の作業領域を確保します。必要な追加 VRAM が空き容量を超える場合、明示数値では「slots leave less than 512 MiB free」となり起動に失敗します。`auto` は 512 MiB を残して選ぶため、選べる expert がなければ「no unclaimed expert fits with 512 MiB free」となります。
- CUDA1 が見えない、primary と helper が同じ device になる、cache の割当・blob 読み込み・検証に失敗する場合も初期化は失敗し、通常は stderr と終了コード 1 で報告されます。
- これは CUDA ordinal を使う helper GPU 経路です。ソースには HIP 側の同等 parser / remote expert 実装と SYCL 側実装もあります。SYCL 側は自動縮小の実装が CUDA/HIP と異なります。各 runtime・GPU での可用性や性能はソース調査だけでは確定できません。実機実行はこの調査では行っていません。

## 出力とエラー

- CUDA0 の cache、expert profile、expert pool の不足: `strata generate: remote experts need --expert-profile, a CUDA0 expert cache and the expert pool`（終了コード 2）。
- helper cache の容量不足、device 不可視、CUDA 操作や blob の読み込み・検証失敗: `strata generate: ...` の診断を stderr に出して終了します。cache 初期化失敗は終了コード 1 です。
- 初期化成功時は、たとえば `CUDA1: <件数> additional experts, <GiB> GiB; results return through pinned host rows` を stderr に出します。

## 根拠

- `engine/src/program/generate.cpp:1418-1426` — help 文字列の値形式と、helper cache 関連 option の説明。
- `engine/src/program/generate.cpp:902-905, 3837-3842, 3983-3988` — 既定値、必須引数の失敗、`N` / `auto` の parser 変換。
- `engine/src/program/generate.cpp:4877-4889, 4952-4963` — CUDA ordinal の helper 割当と layer split 時の未使用 GPU 選択。
- `engine/src/program/generate.cpp:5252-5263` — `--peer-device` との排他条件。
- `engine/src/program/generate.cpp:10045-10053, 10061-10129` — device1 を入口とする初期化、前提条件、順位・配置、初期化失敗と成功ログ。
- `engine/src/core/remote_experts.cpp:136-205` — 自動・明示 slot 選択、512 MiB headroom、cache の割当、blob 充填・検証と失敗経路。
- `engine/src/core/remote_experts.cpp:426-445` — helper cache からの読み出しと fallback source。
- `engine/sycl/src/program/generate.cpp:2006-2012, 5648-5657, 5664-5732`、`engine/sycl/src/core/remote_experts.cpp:161-223` — SYCL parser と初期化条件、`auto_size` を用いない slot 選択および後段の容量 headroom 検査。
