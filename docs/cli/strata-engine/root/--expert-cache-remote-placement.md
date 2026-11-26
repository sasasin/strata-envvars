# `strata --expert-cache-remote-placement`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--expert-cache-remote-placement` |
| 別名 | なし |
| 値 | `stripe` または `layer` |

## 役割

`--expert-cache-device1..3` で設定する helper GPU cache が複数あるとき、expert profile の順位に沿って cache へ割り当てる方法を選びます。`stripe` は割当可能な GPU を巡回し、`layer` は層番号を helper 数で剰余した GPU に割り当てます。主 GPU 上の cache にない expert を複数の helper GPU に分散する構成向けです（`engine/src/program/generate.cpp:10123-10131,10155-10190`）。

## 使い方

```sh
strata --pack ./model.gguf \
  --expert-profile ./expert-profile.csv --expert-cache 128 \
  --expert-cache-device1 auto --expert-cache-device2 auto \
  --expert-cache-remote-placement layer
```

この例では、profile と主 GPU cache を用意したうえで、二つの helper cache を層単位で割り当てます。`--pack`、profile、cache 容量は実際のモデル・実行環境に合わせて指定してください。option の値そのものは `stripe` または `layer` です（parser: `engine/src/program/generate.cpp:3842-3847,3994-3997`）。

## 値と既定値

- 省略時は `stripe` です（`engine/src/program/generate.cpp:903-907`）。
- 値は大文字小文字を区別する文字列で、受理値は `stripe` と `layer` のみです。値を省略すると `--expert-cache-remote-placement needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3847`）。
- 未知の値や空文字列は validation で拒否され、`strata generate: --expert-cache-remote-placement must be stripe or layer` を stderr に出して終了コード 2 になります（`engine/src/program/generate.cpp:5276-5278`）。
- 同じ引数を複数回指定した場合に一意性チェックはなく、parser が読むたびに値を代入するため最後の指定値が残ります（`engine/src/program/generate.cpp:3842-3847,3994-3997`）。

## 実行時の動作

値は parser で文字列として `Options::expert_cache_remote_placement` に保存され、resource validation の後、helper cache に渡す profile 順位リストを作る分岐で参照されます（`engine/src/program/generate.cpp:903-907,3994-3997,5276-5278,10133-10160`）。

- `stripe` では、profile 上の順位順に、容量枠が残っている helper を巡回して割り当てます。既存の主 GPU cache にある expert や範囲外・重複の pair は割当対象から除外されます（`engine/src/program/generate.cpp:10162-10185`）。
- `layer` では、`layer_index % helper_devices` で決めた helper だけをその層の割当先にします。その GPU の指定枠が埋まっている場合、その pair は割当を飛ばし、別 GPU へ振り替えません（`engine/src/program/generate.cpp:10160-10172`）。
- この配置分岐に入るのは `--expert-cache-device2` または `--expert-cache-device3` の cache 枠が正の場合です。helper が device1 一つだけなら、profile はその cache に直接渡されるため、この値による配置差はありません（`engine/src/program/generate.cpp:10126-10127,10155-10160,10189-10190`）。
- helper cache を使う場合、`--expert-cache` の主 GPU cache が正、expert profile が空でないこと、expert pool が有効であることが必要です。満たさない場合は必要条件のエラーを stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:10127-10131`）。`--expert-cache-device2` は device1、device3 は device2 の枠も正でなければ resource validation に失敗します（`engine/src/program/generate.cpp:5267-5274`）。

割当結果は各 `RemoteExperts::open` に渡され、失敗時はエラー文字列を stderr に出して終了コード 1、成功時は GPU ごとの追加 expert 数・容量と「results return through pinned host rows」を stderr に出します（`engine/src/program/generate.cpp:10197-10207`）。配置は起動時に組み立てる cache の割当であり、このオプション自体がファイルを書き換える処理は確認できません。

## 適用条件と副作用

このオプションの文字列検証は helper cache の有無にかかわらず行われますが、値を配置に使うのは複数 helper cache の構成時です。helper cache は追加 GPU 上に構築され、実行時の結果行は pinned host rows 経由で戻ります（`engine/src/program/generate.cpp:5276-5278,10126-10131,10155-10160,10197-10207`）。

`--peer-device` は remote expert cache と併用できず、該当時は終了コード 2 で拒否されます。layer split と併用する場合、split の stage を実行しない GPU が helper cache 用に必要です（`engine/src/program/generate.cpp:5284-5290,4954-4968`）。この配置モードが実際に転送量や速度へ与える量的効果は、ソースから確定できません。

同じ parser・配置分岐は SYCL 側にもあります（`engine/sycl/src/program/generate.cpp:576-579,2012-2015,2690-2692,5695-5725`）。この調査では Strata のソース実装を確認し、実行バイナリや GPU 上での動作確認はしていません。

## 出力とエラー

- 値の欠落: stderr に値が必要と表示し、終了コード 2（`engine/src/program/generate.cpp:3844-3847`）。
- 不正値: stderr に許可値を表示し、終了コード 2（`engine/src/program/generate.cpp:5276-5278`）。
- remote expert cache の必須条件不足: stderr に `remote experts need --expert-profile, a CUDA0 expert cache and the expert pool` を出し、終了コード 2（`engine/src/program/generate.cpp:10127-10131`）。
- cache の初期化失敗: エラー文字列を stderr に出し、終了コード 1（`engine/src/program/generate.cpp:10197-10203`）。
- helper cache が複数ある場合、順位リストを割り当てた後に `remote ranks grouped by layer` または `remote ranks striped` と device 数を stderr に出します（`engine/src/program/generate.cpp:10155-10160,10187-10190`）。

## 根拠

- `docs/cli/README.md:1036-1094` — `strata-engine` の root scope に対象リンクがあること。
- `engine/src/program/generate.cpp:903-907,1416-1425` — 既定値と help 表示。
- `engine/src/program/generate.cpp:3842-3847,3994-3997` — root parser、欠値処理、値の保存。
- `engine/src/program/generate.cpp:5267-5290` — 値の validation と resource / peer-device 制約。
- `engine/src/program/generate.cpp:10123-10207` — helper 構成条件、配置アルゴリズム、cache 初期化と出力。
- `engine/src/program/generate.cpp:4954-4968` — layer split 併用時の helper GPU 条件。
- `engine/sycl/src/program/generate.cpp:2012-2015,2690-2692,5695-5745` — SYCL 側 parser、validation、同配置分岐。
