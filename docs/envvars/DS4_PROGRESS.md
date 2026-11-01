# `DS4_PROGRESS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal ビルドの `strata-dsv41` が通常の単発 decode を実行するとき、生成 token 数が 200 の倍数に達するたび、累積 token 数と直近区間の生成速度を stderr に出します。生成や sampling の選択は変えず、進捗診断ログだけを追加します。

## 値と判定

値の parse はなく、環境変数が設定されているかだけを判定します。

| ビルド・値 | 判定 |
|---|---|
| `STRATA_METAL` 定義あり、unset | 無効 |
| `STRATA_METAL` 定義あり、任意の値（空文字を含む） | 設定ありとして有効 |
| `STRATA_METAL` 未定義（CUDA/HIP を含む） | helper が定数 `false` を返すため無効。環境変数を読みません |

したがって `DS4_PROGRESS=0` や空文字も、Metal ビルドでは有効です。数値変換、無効値扱い、既定で有効になる fallback はありません。CLI 引数や他の環境変数との値の優先順位もありません。`--n` は出力上限として間接的に関係し、200 token に届かなければログは出ません。

## 有効になる条件

- `ds4_dbg` が環境を参照する `STRATA_METAL` 定義ありのビルドであること。`ds4_launch.h` はこれを Mac/Metal の診断と説明し、それ以外のビルドでは同 helper を `constexpr false` にしています。
- `strata-dsv41` の `--serve` ではなく、通常の単発生成ループに入り、200 token 以上を生成すること。`--serve` は単発ループより前に別の `serve()` 経路へ return します。
- ループは `n > 0` のときだけ始まり、EOS token で早期終了することがあります。`DS4_NO_EOS` が設定されていれば（空文字も含む）EOS での終了を抑えますが、`--n` の上限は残ります。

リポジトリの CMake では `strata-dsv41` は `STRATA_BUILD_DSV41`（既定 OFF）の別 target です。確認した target 定義には `STRATA_METAL` の設定がありません。その CMake target では `ds4_dbg` の定数 false 経路となり、この変数は効きません。別の Metal ビルドについては、ここでは macro の定義元までは確認していません。

## 実行時の詳細

各生成 token を `out` に追加し、token を stdout に出した後、`out.size() % 200 == 0` かつ `ds4_dbg("DS4_PROGRESS")` が真なら、stderr に次の形式で出力します。

```text
progress <累積token数> tokens: <速度> tok/s over the last <区間token数>
```

速度は `(今回の out.size() - 前回値) / 経過秒` です。静的な時刻・token 数はログ計算用に保持しますが、環境変数の判定結果はキャッシュしません。Metal では生成ループ内で `getenv` を都度呼びます。値による生成内容、終了コード、失敗経路への変更はなく、この分岐自体に警告やエラー出力もありません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — Metal 時のみ `std::getenv(name) != nullptr`、それ以外は `constexpr false`。
- `src/dsv41/ds4_main.cpp:388-395,1003-1023,1408-1415` — `--serve` は独自ループを使い、単発生成処理より先に分岐する。
- `src/dsv41/ds4_main.cpp:1505-1525` — `n > 0` の生成ループ、token 出力、200 token ごとの進捗ログ、`DS4_NO_EOS` による EOS 判定。
- `src/dsv41/ds4_main.cpp:1555-1569` — 単発 decode の最後の統計ログ。進捗ログとは別の出力。
- `CMakeLists.txt:906-920,932-939` — `STRATA_BUILD_DSV41` は既定 OFF の別 executable target。ここにある target 定義には `STRATA_METAL` の追加定義がない。

`docs/DETAILS.md` と調査した設計資料には `DS4_PROGRESS` の個別説明は見つかりませんでした。
