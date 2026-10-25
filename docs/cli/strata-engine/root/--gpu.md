# `--gpu`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata` |
| オプション | `--gpu LIST` |
| 別名 | なし |
| 値 | GPU 番号のカンマ区切り。help は `nvidia-smi` / PCI 番号と説明 |

## 役割

エンジンが見える GPU を起動時に選びます。値は環境変数として CUDA/HIP runtime に渡され、未指定なら呼び出し元環境で可視な GPU 全てが対象です。これは Python 製 Terminal CLI の `strata launch --gpu` や setup の `--gpu` とは別の parser・スコープです（索引: [`strata-engine`](../../README.md)、`docs/cli/README.md:1128-1134`）。

## 使い方

```sh
strata --gpu 0,1 --pack ./pack --tokens "1,2,3"
```

エンジンの help は `--pack` と `--tokens` を基本引数として示し、`--gpu LIST` を「可視 GPU のうち指定したもの」と記載します（`src/program/generate.cpp:806-815`）。

## 値と既定値

- `LIST` はカンマ区切りの GPU 番号です。help の番号体系は `nvidia-smi` / PCI 順です（`src/program/generate.cpp:813-815`）。
- オプションを省略した場合、`CUDA_VISIBLE_DEVICES` / `HIP_VISIBLE_DEVICES` をこのオプションで変更せず、呼び出し元の可視 GPU 全てを使う既定動作です（`src/program/generate.cpp:2370-2380`、help の既定値は `src/program/generate.cpp:813-815`）。
- parser は値を文字列として受け取り、番号の形式・範囲・重複を Strata 側では検証しません。値を取り忘れた場合は `--gpu needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2417-2424`）。値の不正形式や範囲外を runtime がどう扱うかは、CUDA/HIP runtime と build に依存し、このソースだけから一律の診断・終了コードは確認できません。
- 複数回指定したとき、起動時の環境設定走査は最初の `--gpu` で停止します。一方 parser は各指定の値を消費します。そのため後続指定は選択を上書きしません（`src/program/generate.cpp:2373-2391`、`src/program/generate.cpp:2416-2425`）。

## 実行時の動作

CUDA の最初の呼び出しより前に引数列を走査し、CUDA build では `CUDA_VISIBLE_DEVICES`、HIP build では `HIP_VISIBLE_DEVICES` に値を設定します。同時に `CUDA_DEVICE_ORDER=PCI_BUS_ID` も設定します。呼び出し元の選択環境変数が空でなく、指定値と異なる場合は `--gpu <値> overrides <環境変数>=<旧値> from the environment` という警告を stderr に出します（`src/program/generate.cpp:2370-2391`）。

その後の通常 parser は `--gpu` と値を読み飛ばします。GPU の選択自体は、CUDA/HIP runtime が初期化時に読む可視性環境変数を通じて適用されます（`src/program/generate.cpp:2416-2425`）。Qwen3.6-35B-MoE の family switch でも、この環境設定後に同じ引数列を専用実装へ渡し、専用 parser は `--gpu` の値を消費します（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3742-3754`）。

## 適用条件と副作用

- この処理はエンジンプロセス内の環境変数を書き換え、runtime が列挙する GPU を絞ります。外側の親プロセスの環境は変更しません（環境設定処理は `src/program/generate.cpp:2370-2391`）。
- NVIDIA では `CUDA_VISIBLE_DEVICES`、HIP build では `HIP_VISIBLE_DEVICES` が選択に使われます。HIP runtime は `CUDA_VISIBLE_DEVICES` を無視するため、AMD build では `HIP_VISIBLE_DEVICES` を設定します（`src/program/generate.cpp:2377-2389`）。
- 値を空文字にした場合や、runtime が認識しない番号を含めた場合の列挙結果は、調査対象ソースでは定義されていません。GPU の種類、driver/runtime、build variant をまたぐ挙動は実機で検証していません。
- 絞り込んだ可視番号は後続の engine 内での device ordinal に関係します。たとえば `STRATA_PRIMARY_DEVICE` は可視 device の番号として解釈され、layer split では可視 device 数や番号に基づく検査が行われます（`src/program/generate.cpp:2959-2968`、`src/program/generate.cpp:2981-3027`）。これらのオプションと併用する場合、GPU を絞った後の番号・台数に合わせる必要があります。

## 出力とエラー

- `--gpu` の指定が呼び出し元の非空な選択環境変数と異なれば、上記の上書き警告を stderr に出します（`src/program/generate.cpp:2375-2383`）。
- 値なしは stderr にエラーを出して終了コード 2 です（`src/program/generate.cpp:2417-2420`）。
- 選択後に GPU が一台もない、または番号が有効範囲外となるケースでは、共通 device 初期化関数は CUDA/HIP device 不在や ordinal 範囲外のエラーを投げます（`src/core/device.cu:256-273`）。最終表示・終了コードは呼び出し経路と backend により異なるため、`--gpu` 固有の一律な失敗メッセージとしては断定しません。

## 根拠

- parser より前の環境設定、警告、OS 別設定: `src/program/generate.cpp:2370-2391`
- option parser の受理と値欠落処理: `src/program/generate.cpp:2416-2425`
- CLI help の値形式と既定値: `src/program/generate.cpp:806-815`
- 可視 device の番号を使う primary / layer split 処理: `src/program/generate.cpp:2959-3027`
- device 不在・ordinal 範囲外の共通エラー: `src/core/device.cu:256-273`
- Qwen3.6 専用経路での値消費: `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_engine.cu:3735-3754`

調査制約: 同一 revision の既存 CLI help は実行していません。ソース内 help 文と parser を照合しました。Release artifact、各 CUDA/HIP runtime での不正な GPU 番号や空値の実際の挙動は確認していません。
