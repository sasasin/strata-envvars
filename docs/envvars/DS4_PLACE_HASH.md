# `DS4_PLACE_HASH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek-V4.1 用の `strata-dsv41` がモデル配置の説明を出すとき、各 expert の VRAM slot 配置から作った 64-bit ハッシュを stderr に追加します。配置や実行経路を変更する設定ではなく、配置の比較・診断用表示です。候補一覧にはありますが、Strata ソースで確認できた参照は `src/dsv41/ds4_model.cu` のこの読み取り一箇所です。

## 値と判定

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | ハッシュ行を追加しない |
| 設定あり（空文字を含む） | ハッシュ行を追加する |

`std::getenv("DS4_PLACE_HASH")` の null / 非 null だけを判定します。値の内容、数値、先頭文字、大文字小文字は調べず、無効値や fallback もありません。CLI 引数や他の環境変数との優先順位もありません。`describe()` が呼ばれるたびに環境を読み直し、結果を cache しません（`src/dsv41/ds4_model.cu:5311`）。

## 有効になる条件

- この分岐は CMake の `STRATA_BUILD_DSV41` が有効で構成された `strata-dsv41` の DeepSeek-V4.1 経路にあります。同オプションは既定 OFF です（`CMakeLists.txt:906-920`）。
- `Model::describe()` が呼ばれる必要があります。通常のモデル load 後は `--verbose` の有無にかかわらず呼ばれます。ただし `--vision` 経路では main 側の説明呼び出しが省かれます（`src/dsv41/ds4_main.cpp:1395-1408`）。
- verbose の場合、load 処理中にも `describe()` が呼ばれるため、その時点でも設定されていればハッシュ行が出ます（`src/dsv41/ds4_model.cu:3201`）。

## 実行時の詳細

`describe()` は各 layer `L` の各 expert を順に走査し、expert の slot が非負なら `1 + layer.il * 1000 + e`、負なら `0` を `uint64_t` にしてハッシュへ加えます。初期値は `1469598103934665603` で、各値との XOR 後に `1099511628211` を乗算します。結果を `%016llx` で16桁の小文字16進数に整形し、`ds4: placement hash <hash>` 行として説明文字列へ追加します（`src/dsv41/ds4_model.cu:5311-5318`）。

通常の CLI 実行では main が `m.describe()` の文字列を stderr に出すため、行も stderr に現れます。`--verbose` では load 中の `describe()` の出力にも含まれます（`src/dsv41/ds4_main.cpp:1402-1409`, `src/dsv41/ds4_model.cu:3201`）。環境変数自体による警告、エラー、終了コード変更はありません。モデルの load に失敗した場合は main が `maya-ds4: <error>` を stderr に出して `1` で終了するため、説明表示には到達しません（`src/dsv41/ds4_main.cpp:1402-1408`）。

## 根拠

- 候補名の Strata 全体検索: `src/dsv41/ds4_model.cu:5311` のみ。動的な名前を渡す helper 経由を含む別の参照は見つかりませんでした。
- 読み取り、値判定、ハッシュ計算、出力文字列: `src/dsv41/ds4_model.cu:5278-5318`。
- load 後の verbose 表示: `src/dsv41/ds4_model.cu:3201`。
- main での説明出力と vision-only 条件: `src/dsv41/ds4_main.cpp:1395-1409`。
- `strata-dsv41` の任意ビルド対象: `CMakeLists.txt:906-920`。
