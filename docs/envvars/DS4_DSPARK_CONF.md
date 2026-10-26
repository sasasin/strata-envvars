# `DS4_DSPARK_CONF`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。Strata 所有ソースを対象とし、外部ライブラリの環境変数は対象外。

## 役割

`src/dsv41/ds4_model.cu` の `Model::Impl` は、この環境変数を読み、`conf_threshold` メンバーに値を格納します。ただし、このメンバーはリポジトリ内で初期化行以外に参照されていません。そのため、現行 HEAD では `DS4_DSPARK_CONF` を設定しても draft confidence の足切り値は変わらず、実行時の挙動への効果は確認できません。

## 値と判定

モデル実装オブジェクトの生成時に `std::getenv("DS4_DSPARK_CONF")` を確認し、設定されていれば `std::atof` で `float` に変換します。未設定時は `0.5f` です。`atof` のため文字列全体の厳密な検証やエラー報告はなく、数値として読める先頭部分が変換され、変換できない文字列や空文字列は通常 `0` になります。変換結果は `conf_threshold` に保存されますが、未設定時・設定時のいずれもこの値は利用されません。

値は `Model::Impl` ごとに生成時に読み込まれます。生成後の環境変更で保存値は更新されませんが、保存値自体が未使用なので実際の推論結果にも影響しません。

## 有効になる条件

この読み取りは DS4.1 CUDA 実装の `src/dsv41/ds4_model.cu` にあります。環境変数の保存処理はモデルに DSpark が読み込まれるかどうかを変更しません。また値が設定されていても、confidence の足切りには適用されません。

現行コードで足切りを指定する経路は別にあります。CLI では `--dspark-conf` が `Options::dspark_conf` を更新し、生成ループがその値を `round()` に渡します。サーバー経路ではリクエストの `dspark_conf` が `0` 以上ならその値を使い、負値ならサーバー側の `conf_min` を `round()` に渡します。`round()` は各 draft の confidence が `conf_min` 以上である間だけ draft を残します。これらの経路は `DS4_DSPARK_CONF` を参照しません。

## 実行時の詳細

`DS4_DSPARK_CONF` の直接参照は `src/dsv41/ds4_model.cu:901` の一箇所です。`conf_threshold` の全参照を検索すると同じ初期化行しかなく、読み取った数値が分岐、GPU 計算、ログ、エラー処理へ渡る経路はありません。

対照的に、実際の confidence 判定は `src/dsv41/ds4_main.cpp:181-183` にあり、`round()` の引数 `conf_min` と draft ごとの `conf` を比較します。CLI の `--dspark-conf` は `src/dsv41/ds4_main.cpp:1229,1409`、サーバーのリクエスト値との選択は同ファイル `:895-900` にあります。従って、この環境変数の設定による専用ログ、警告、終了、データ出力も実装上確認できません。

## 根拠

- `src/dsv41/ds4_model.cu:800-801,901`: `Model::Impl` のメンバー初期化。環境変数を `atof` で変換し、未設定時は `0.5f` を格納。
- `src/dsv41/ds4_model.cu:901`: ソース全体で `conf_threshold` が現れる唯一の箇所。
- `src/dsv41/ds4_main.cpp:181-183`: `round()` が `conf_min` と各 draft confidence を比較する実際の足切り。
- `src/dsv41/ds4_main.cpp:1229,1301,1305,1409`: `--dspark-conf` の設定と、serve / spec-eval / 通常生成経路への値の受け渡し。
- `src/dsv41/ds4_main.cpp:895-900`: サーバーでリクエストの `dspark_conf` とエンジン側 `conf_min` を選択。
- `src/dsv41/ds4_model.hpp:48-51`: DSpark のロード設定と、CLI 用 `dspark_conf` の既定値 `0.5f`。
