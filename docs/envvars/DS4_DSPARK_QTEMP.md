# `DS4_DSPARK_QTEMP`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DSpark speculative decoder が draft token を確率サンプリングする場合に使う温度倍率です。リクエスト温度そのものではなく、drafter の分布を作る温度を `request temperature × DS4_DSPARK_QTEMP` にします。draft の検証側はリクエスト本来の温度を使い、draft の提案分布も保持して補正するため、この変数は検証対象モデルの sampling temperature を変更しません。

## 値と判定

`Model::Impl` のメンバー初期化時に `getenv()` で一度読み、設定されていれば `atof()` で `float` に変換します。unset の既定値は `1.0` です。文字列全体の妥当性検査、範囲制限、エラー出力はありません。

draft sampling 時は倍率が `> 0.0f` の場合だけその値を使い、それ以外は `1.0f` に置き換えます。したがって、空文字、数値に変換できない文字列、0、負数は倍率 1 と同じです。`atof()` が読む数値接頭辞の後ろに文字があっても、コードは追加検査しません。正の値には上限 clamp がありません。

| 環境変数の状態 | 読み取った倍率 | sampling 時に使う倍率 |
|---|---:|---:|
| unset | `1.0` | `1.0` |
| 空文字または数値として読めない値 | `0.0` | `1.0` |
| 正の数（例: `0.5`, `2`, `0.5tail`） | 変換された値 | その値 |
| 0 または負数 | 変換された値 | `1.0` |

## 有効になる条件

- ビルド時に `STRATA_BUILD_DSV41=ON` として `strata-dsv41` を作る必要があります。この CMake オプションは既定で OFF です。通常の `strata` 実行ファイルにはこの経路が含まれません。
- モデルに DSpark drafter がロードされ、通常の speculative decode 経路から `draft()` が呼ばれる必要があります。
- sampling draft になるには、別変数 `DS4_DSPARK_SAMPLE` が設定され、`atoi(value) != 0` で、かつ当該リクエスト温度が `> 0` である必要があります。この条件を満たさない場合は drafter の argmax を使うため、`DS4_DSPARK_QTEMP` は draft token に影響しません。
- sampling 時も `top_p`、`top_k`、`min_p` はリクエスト値のまま drafter の sampler に渡されます。この変数が変えるのは温度だけです。検証器には元のリクエスト温度が渡され、draft 分布に対する補正を行います。

## 実行時の詳細

`q_temp_scale` はモデル実装オブジェクトのメンバー初期化時に設定されます。`Model` の生成時に `Impl` が作られるため、同じモデルインスタンスを使っている間にプロセス環境を書き換えても倍率は再読込されません。リクエストごとの設定や CLI 引数による上書きは、この変数の読み取り箇所にはありません。

sampling draft が選ばれると、drafter の `SamplerParams.temperature` に倍率適用後の温度を設定し、各 draft 位置で `sample_draft()` を呼びます。`SpecList` にその draft 分布を保存します。検証では target model の logits と元のリクエスト sampling 条件、および保存済み draft 分布を使い、受理または棄却を決めます。実装上、この変数専用のログや警告はありません。

## 根拠

- `CMakeLists.txt:797-810` — DeepSeek-V4.1 engine は既定 OFF の `STRATA_BUILD_DSV41` で別 executable `strata-dsv41` としてビルドされる。
- `src/dsv41/ds4_model.cu:907-919` — `DS4_DSPARK_SAMPLE` と `DS4_DSPARK_QTEMP` の初期化。倍率の既定値と変換方法。
- `src/dsv41/ds4_model.cu:6715-6733` — request temperature が正で sampling hook が有効な場合の状態設定。
- `src/dsv41/ds4_model.cu:6830-6847` — drafter sampling 時の温度倍率適用と sampler 呼び出し。
- `src/dsv41/ds4_model.cu:6902-6967` — target 側の元温度による speculative verification と draft 分布による補正。
- `src/dsv41/ds4_model.cu:9352-9354` — `Model` 生成時に `Impl` を構築する。
