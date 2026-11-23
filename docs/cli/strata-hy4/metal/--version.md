# `strata-hy4-metal --version`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal backend、トップ階層） |
| オプション | `--version` |
| 別名 | なし |
| 値 | 取らない |

## 役割

Metal backend の Hy4 実行ファイルが埋め込んだバージョン文字列を表示して終了する。モデル、トークン入力、Metal デバイスや推論カーネルを使わずに実行ファイルの版を確認できる。

## 使い方

```sh
strata-hy4-metal --version
```

## 値と既定値

値を取りません。表示文字列は `strata-hy4 <version>` の形式で、行末に改行が付きます。ソースには `STRATA_HY4_VERSION` がビルド時に未定義の場合の値として `0.1.66` が定義されています（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1484-1485`）。この checkout 内では同マクロを別途定義する箇所は見つからなかったため、ビルド時に外部から上書きする構成の有無までは確認できていません。

## 実行時の動作

引数を左から処理し、`--version` に到達すると標準出力へバージョン行を出して、その場で終了コード `0` を返します。その後の引数処理やモデル有無の確認、Metal context の生成、モデル読み込みには進みません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506,1583-1585,1611-1622`）。したがって `--version` より前にある引数は通常どおり解析され、未知フラグなら失敗しますが、後ろの引数は処理されません。

## 適用条件と副作用

`strata-hy4-metal` の実行時に利用できます。引数処理中に即時終了するため、モデルファイルの読み込みや GPU/Metal 処理は発生しません。引数解析より前に共通初期値と parser 用の状態を用意しますが、版表示に伴うファイル・ネットワークへのアクセスは確認できません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1504,1583-1585`）。

## 出力とエラー

標準出力に `strata-hy4 <version>` を1行出力し、終了コード `0` で返ります（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1583-1585`）。この分岐自体にエラー経路はありません。`--version` より前に未知の引数がある場合は、通常の未知フラグ経路が標準出力・標準エラーへエラーを出して `2` を返します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1484-1485` — バージョンマクロの fallback 定義。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1504-1506` — 引数を左から走査する parser。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1583-1585` — `--version` の認識、出力、即時の正常終了。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1608,1611-1622` — 未知引数の失敗経路と、通常起動時のモデル確認・Metal context 初期化が版表示の後段であること。
