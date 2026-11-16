# `strata --prefill`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン引数） |
| オプション | `--prefill` |
| 別名 | なし |
| 値 | `CHUNK` はトークン数、または `auto` / `auto:N` |

## 役割

複数トークンのプロンプトを一度に処理する際の最大チャンクサイズを指定します。数値を指定するとそのサイズを基本にし、`auto` はエキスパートキャッシュからプロンプト用バッファを借りられる最大サイズを実行時に選びます。CLI の usage では `--native` が必要とされています。特に native (IQ) pack は、複数トークン入力時に `--native`、`--spec`、正の `--prefill` 値がそろわないと開始できません（`src/program/generate.cpp:1329-1331`, `5415-5421`）。

## 使い方

```sh
# native pack を読み、プロンプトをキャッシュ状況に合わせたチャンクで処理する
strata --pack MODEL.gguf --native SHARD1.gguf --spec 4 --prefill auto --tokens 1,2,3

# チャンクを 4096 トークンに指定する
strata --pack MODEL.gguf --native SHARD1.gguf --spec 4 --prefill 4096 --tokens 1,2,3
```

`--tokens` は例示用のトークン ID リストです。実際に使う pack と native shard に合わせてパスを指定してください。

## 値と既定値

- オプションを省略した場合の内部値は `0` で、プロンプトの batched chunk path を使いません。`0` 以下の値も同じくその path を無効にします（`src/program/generate.cpp:948-949`, `21568`）。
- 数値は `std::atoll` で読み取られ、この分岐内に数値形式や正の範囲を検証する処理はありません。指定値を厳密に拒否する validation は確認できません（`src/program/generate.cpp:3825-3847`）。
- `auto` の通常上限は 8192。`auto:N` と [環境変数 `STRATA_PREFILL_AUTO_MAX`](../../../envvars/STRATA_PREFILL_AUTO_MAX.md) は上限を 8192 / 16384 / 32768 の段階に丸めます。`N` が 16384 未満なら 8192、16384 以上なら 16384、32768 以上なら 32768 です（`src/program/generate.cpp:3827-3833`）。
- `STRATA_PREFILL_AUTO_MAX` は値が `auto` で suffix がない場合にだけ参照されます。`auto:N` はこの環境変数より優先され、数値指定には適用されません（`src/program/generate.cpp:3829-3833`）。
- 引数を複数回指定すると parser のループで各回の値を代入し、後の指定が前の値を置き換えます（`src/program/generate.cpp:3667-3672`, `3825-3847`）。

## 実行時の動作

`--prefill` が正の値で、プロンプトに 1 個を超えるトークンがあると batched prompt path を初期化します（`src/program/generate.cpp:21567-21578`）。数値指定はキャッシュ貸出の fit に応じて調整されることがあり、serve の auto scan では固定指定を元の値から半分ずつ下げて適合サイズを探します（`src/program/generate.cpp:11667-11671`）。直接の generate 経路では、借りられる slot がない場合は指定値のまま自前バッファを初期化し、収まらなければ初期化エラーになります（`src/program/generate.cpp:21633-21644`, `21672-21680`）。

`auto` はキャッシュの空き、必要なバッファ、プロンプト長などから実際のサイズを選びます。リング用バッファを含む適合判定で選択し、プロンプトごとの host memory 条件も評価します（`src/program/generate.cpp:10514-10518`, `10616-10635`, `21574-21603`）。直接の generate 経路で貸出ができないと、実際のプロンプト長に応じた 1024 トークン基準の小さい chunk に切り替わります（`src/program/generate.cpp:21639-21641`）。profile がない、または自前バッファを強制する設定では auto が無効化され、通常は 2048 に戻ります（`src/program/generate.cpp:4694-4698`）。

裸の `auto` には platform 条件があります。Windows HIP build は上限 6144 ですが、`auto:N` や `STRATA_PREFILL_AUTO_MAX` による指定はこの上限の対象外です（`include/strata/platform/host_limits.hpp:19-30`, `src/program/generate.cpp:3834-3846`）。Windows の gfx1151 (Strix Halo) では既定条件により上限解除と 16384 への引き上げが行われ、自前バッファを保持します。対応する環境変数でこの既定動作を抑止できます（`src/program/generate.cpp:4161-4192`）。CUDA の条件を満たす NVIDIA GPU および Linux HIP gfx12 では、裸の `auto` の上限が 32768 まで引き上げられることがあります。layer split や host RAM の余裕などにより再度制限されます（`src/program/generate.cpp:4248-4272`, `4277-4294`, `10519-10568`）。

プロンプト処理中、キャッシュ末尾の slot を借りる場合はそこへ一時的に prompt buffer を配置し、処理後に expert データを戻して decode 用 cache に返します。借りられない場合は自前バッファを確保します（`src/program/generate.cpp:21668-21680`, `21726-21742`）。

## 適用条件と副作用

- usage は `--native` が必要と説明しています。native (IQ) pack では、複数トークン入力時に `--prefill` が正のサイズであることを含む条件を満たさないと、エラーを stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:1329-1331`, `5415-5421`）。
- `auto` の結果は GPU/build、layer split、キャッシュ・RAM 条件で変わります。裸の `auto`、`auto:N`、環境変数指定は同じ上限選択ではありません（`src/program/generate.cpp:3829-3846`, `4248-4294`, `10519-10568`）。
- Windows HIP build で明示数値または `auto:N` が 8192 以上なら、クラッシュ報告に基づく警告が stderr に出ますが、指定サイズは維持されます。裸の `auto` は通常 6144 に制限されます（`include/strata/platform/host_limits.hpp:19-30`, `src/program/generate.cpp:4203-4207`）。
- chunk buffer の GPU memory を確保します。貸出時は prompt path が expert cache の slot を一時利用し、その後データを復元します。ログには自動選択サイズ、貸出または自前確保が出ます（`src/program/generate.cpp:21639-21680`, `21726-21742`）。

## 出力とエラー

- 値を省略した場合は `--prefill needs a value` を stderr に出し、終了コード 2 で終了します（`src/program/generate.cpp:3669-3671`）。
- batched prompt buffer の初期化に失敗した場合、エラー文字列を stderr に出して終了コード 1 で終了します。`prefill.run` の失敗も同様です（`src/program/generate.cpp:21676-21680`, `21722-21724`）。
- Windows HIP の指定 chunk 警告と auto 選択・貸出・自前 buffer の状況は stderr に出力されます（`src/program/generate.cpp:4203-4207`, `21639-21680`）。

## 根拠

- `src/program/generate.cpp:948-965` — option の内部値と既定値。
- `src/program/generate.cpp:1329-1331` — usage 上の値の説明と `--native` 条件。
- `src/program/generate.cpp:3667-3672`, `3825-3847` — 引数取得、値の変換、auto 上限、環境変数、Windows HIP 条件。
- `include/strata/platform/host_limits.hpp:19-30` — Windows HIP bare-auto 上限と警告条件。
- `src/program/generate.cpp:4161-4192`, `4248-4294`, `10514-10568` — platform に応じた auto 上限の変更と host memory による縮小。
- `src/program/generate.cpp:10616-10635`, `11667-11680`, `21568-21648` — 適合する chunk の選択、prompt path への適用、貸出不可時の動作。
- `src/program/generate.cpp:21668-21680`, `21722-21742` — 自前 buffer 初期化、prompt 実行、貸出 slot の復元と失敗経路。
- `src/program/generate.cpp:5415-5421` — native (IQ) pack での必須条件と失敗終了。
