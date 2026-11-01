# `--profile-readonly`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 engine） |
| オプション | `--profile-readonly` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

expert profile を expert 配置の初期値として読み込みますが、実行中に集計した routing counts を profile ファイルへ書き戻さないようにします。オプションを付けない場合は、通常の実行経路が終了時などに profile を保存します。このフラグは読み取りも止めるものではありません。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --serve --profile-readonly
```

`--serve` を使わない実行でも指定できます。CLI は `--pack` と `--serve` または各処理モードの引数を要求します。

## 値と既定値

値・引数は不要です。parser はフラグを見つけると `profile_readonly` を `true` にします。既定値は `false` で、同じフラグを複数回指定しても同じ真偽値を設定するだけです。値を続けて指定する構文はありません。

profile のパスは `--expert-profile FILE` で指定できます。未指定なら `<pack>/expert-profile.bin` が使われます。`--expert-profile none` の場合は profile を無効化し、読み込み・保存とも行いません。readonly は保存抑止なので、`none` と併用しても追加の効果はありません。`--pack-info` はモデル読み込み前に pack 情報を出して終了するため、このモードでは profile を読み書きせず、readonly も作用しません。

## 実行時の動作

モデル読み込み時、指定された profile をバイナリ読み込みで開き、読み込んだ expert counts を配置順の決定と初期 heat に使います。ファイルを開けない場合はゼロ初期値のまま続行します。profile データの要素数が現行形式または旧形式の期待要素数に一致したときだけ採用され、それ以外の長さはエラーにせず無視します（形式一致の詳細検証はこの箇所では行いません）。

通常は `save_profile()` が profile が有効で readonly でない場合に限って `<profile>.tmp` へ書き、書き込み成功後に置換します。`--profile-readonly` が有効ならこの関数は直ちに戻るため、その保存呼び出しから元 profile や `.tmp` を変更しません。serve の各リクエスト後と終了時、`--profile-run` の10 segmentごとおよび終了時、通常生成の終了時に保存関数が呼ばれますが、いずれも同じ抑止条件が適用されます。

## 適用条件と副作用

このオプションは DeepSeek-V4.1 用の独立 engine CLI の parser に属します。索引上、この executable は `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` でない build で生成されます。macOS Metal build も同じ入口ソースを利用します。

readonly は profile への書き戻しだけを抑えます。モデル pack や他の出力を読み取り専用にするフラグではなく、profile が存在しない・読めない場合のエラー化もしません。profile の書き込みを止めるため、後続実行に反映される新しい routing counts も作成されません。

## 出力とエラー

このフラグ自体に専用の出力や validation error はありません。未知のオプションは `unknown option ...` と usage を stderr に出し、終了コード 2 になります。モデル読み込み失敗は `maya-ds4: ...` を stderr に出して終了コード 1 ですが、profile が開けない場合は profile 読み込み箇所でエラーを設定せず、通常処理を続けます。

## 根拠

- `src/dsv41/ds4_main.cpp:101-109` — usage にある形式と値を取らないこと。
- `src/dsv41/ds4_main.cpp:1307-1315,1323-1325` — parser の値取得規則とフラグ設定。
- `src/dsv41/ds4_main.cpp:1383-1406,1410-1415` — unknown option、pack/profile の既定・`none` 処理、モデル読み込みとモード分岐。
- `src/dsv41/ds4_model.hpp:33-36` — profile の役割と readonly の既定値・意図。
- `src/dsv41/ds4_model.cu:2934-2943` — profile の読み込み、受理する要素数、開けない場合の扱い。
- `src/dsv41/ds4_model.cu:4687-4725` — profile counts による expert の配置順と初期 heat。
- `src/dsv41/ds4_model.cu:10642-10652` — readonly 時の保存早期 return と、通常時の一時ファイル・置換処理（open/write/replace に失敗してもこの関数は診断を出さず、失敗した一時ファイルは削除）。
- `src/dsv41/ds4_main.cpp:1023,1050-1052,1192-1221,1634-1635` — serve、profile-run、通常生成の保存呼び出し。
- `docs/cli/README.md:1375-1407` — `strata-engine-dsv41` scope と対象オプションの索引上の位置づけ。build 条件と配布記載も同節を参照。
