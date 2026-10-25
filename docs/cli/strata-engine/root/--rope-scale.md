# `strata --rope-scale`

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--rope-scale F` |
| 別名 | なし |
| 値 | 浮動小数点数。0 は未指定、明示値は 1 以上 |

## 役割

`linear` または `yarn` RoPE scaling の倍率を指定します。指定した倍率は、モデルの GGUF に倍率が記録されている場合も上書きします。倍率だけでは scaling type を有効にしません。type が `none` なら倍率などの scaling knob は適用されません。

## 使い方

```sh
strata --native /path/to/supported-model.gguf --rope-scaling yarn --rope-scale 2 --max-context 524288
```

この例は `yarn` を選び、倍率を 2 にして最大 context を 524288 に設定します。`--rope-scale` 自体が `--max-context` を変更することはありません。

## 値と既定値

- parser は `F` を `std::atof` で読み取ります。引数を省略すると、その場で `--rope-scale needs a value` を stderr に出し、終了コード 2 で終了します。
- 値 `0` は「フラグなし」の sentinel です。明示倍率としては `1` 以上が必要で、0 以外の 1 未満は起動時検査で拒否されます。有限でない値も拒否されます。
- 既定倍率は、`--native` で読む GGUF に `rope.scaling.factor` があり、その値が 1 より大きければその値、それ以外は 1 です。正の CLI 値は GGUF の倍率より優先されます。
- `1` は有効な明示値です。倍率を 1 にしても scaling type を `none` にする指定ではありません。

## 実行時の動作

エンジンは起動時に CLI とモデル metadata を合わせて RoPE 設定を解決し、`--rope-scale` が 0 より大きければその値を `RopeScaling::factor` に設定します。倍率が 0 のときは GGUF 値または既定値が使われます。type は別 option `--rope-scaling` が明示されていればそれを使い、なければモデル metadata（取得できる場合）を参照します。

有効な scaling type のとき、倍率から導く角度縮小率は `--rope-freq-scale` が正ならその値、そうでなければ `1 / factor` です。解決した設定は起動時に一度だけ登録され、セッション初期化時の RoPE table と analytic RoPE kernel に使われます。RoPE 適用後の key が cache に保存されるため、実行途中に倍率を切り替える仕組みはありません。

type が `none` の場合、エンジンは倍率・頻度縮小・YaRN knob を初期値に戻して scaling を適用しません。`--rope-scale` が 1 より大きいと stderr に「scaling is active none のため ... have no effect」という note が出ます。倍率 1 はこの note の条件には含まれません。

## 適用条件と副作用

- `src/program/generate.cpp` の通常エンジン経路が対象です。Qwen3.6 family は parser より前に `strata::qwen35::run` へ振り分けられますが、その parser に `--rope-scale` はありません。通常経路では未対応 option として usage を表示し終了コード 2、`--serve` を先に処理した場合は未対応 option として警告し値を読み飛ばします。
- `--rope-scaling` は `none`、`linear`、`yarn` のいずれかです。倍率指定だけでは `none` から `linear` / `yarn` へ切り替わりません。
- `--max-context` が学習済み context 以下でも scaling type が有効なら設定は適用されます。その場合、エンジンは「学習済み範囲内だが scaling は全角度に適用される」という stderr note を出します。
- 有効な scaling は角度と、設定によっては cos/sin の振幅にも作用します。特に YaRN の既定 ext factor は 1、他の type では 0 です。正確な振幅や補正範囲は併用する YaRN option にも依存します。
- この option によるファイル書き込みやネットワーク通信は、確認した parser・設定経路にはありません。主な副作用は起動時の process-wide RoPE 設定と stderr の診断表示です。

## 出力とエラー

- 値なし: `--rope-scale needs a value` を stderr に出して終了コード 2。
- 値が有限でない場合: `a rope scaling knob is not a finite number` を stderr に出して終了コード 2。
- 0 以外で 1 未満の場合: `--rope-scale ... must be >= 1` を stderr に出して終了コード 2。
- 解決後の設定が不正なら `invalid rope scaling configuration: ...` を stderr に出し終了コード 2。scaling が有効なら、起動時に type、factor、freq scale、base、context を stderr に表示します。

## 調査範囲

Strata checkout の `src/program/generate.cpp` と RoPE 設定ヘッダーを確認しました。CMake build、実行バイナリ、GPU、各 backend、Release 配布物での動作確認はしていません。したがって本書は下記 revision のソースに基づき、実行時確認や性能評価を示すものではありません。

## 根拠

- 調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、調査日 `2026-10-25`。調査時の `git status --short --branch` は `## main...origin/main`（未コミット変更なし）。
- `src/program/generate.cpp:450-463` — RoPE 設定 option の初期値と 0 の sentinel。
- `src/program/generate.cpp:2393-2407` — Qwen3.6 family の parser 前 dispatch。
- `src/program/generate.cpp:867-877` — エンジンの help に記載された type、倍率、既定値。
- `src/program/generate.cpp:2418-2421,2444-2453` — 値の取得と `--rope-scale` の parser。
- `src/program/generate.cpp:3315-3339` — scaling type の検査、有限値検査、倍率の下限検査。
- `src/program/generate.cpp:3642-3729` — CLI と GGUF の優先順位、倍率の解決、`none` 時の無効化、resolved config の検査と失敗経路。
- `src/program/generate.cpp:3731-3750` — 起動時登録、適用状況・context 内警告・振幅補正の stderr 表示。
- `include/strata/kernels/rope_scaling.hpp:22-35,61-90,164-190` — table / analytic path、設定の起動時固定、倍率から頻度縮小率への変換、resolved config の validation。
- `include/strata/kernels/qsa.hpp:121-125` — 既定周波数 base と実行時設定の説明。
- `src/qwen35/q36_engine.cu:3735-3795` — Qwen3.6 側 parser、未対応 option の通常時エラーと `--serve` 時の警告・値読み飛ばし。
- 索引 `docs/cli/README.md:1128-1135,1274` — `strata-engine` の parser scope とこの文書の配置先。
