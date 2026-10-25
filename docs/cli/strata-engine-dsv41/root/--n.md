# `--n`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek-V4.1 用の独立 engine CLI） |
| オプション | `--n` |
| 別名 | なし |
| 値 | 整数として `std::atoi` で変換される値 |

## 役割

`--ids` で与えた prompt の後に生成する token 数の上限を指定します。`--spec-eval` と併用した場合は、各 prompt segment について行う greedy/speculative decode の目標 token 数にも使われます。`--n` を省略した場合は 0 で、通常の `--ids` 実行では decode を行いません。

## 使い方

```sh
strata-dsv41 --pack /models/example/maya-ds4 --ids 0,128803,42 --n 32
```

この例では prompt の token ID 列を処理し、最大 32 token を生成します。エンジンは `--pack` と実行モードを必要とします。`--n` 自体は `--ids` モードで有効です。

## 値と既定値

- 値は必須です。値を省くと parser の `val()` が `--n needs a value` を stderr に出して終了コード 2 で終了します。
- 既定値は `0` です。`std::atoi` で読み込みますが、正数かどうかなどの validation はありません。0、負数、または整数に変換されない文字列は通常の生成経路では decode を開始しません。
- 同じ引数を複数回指定したときは parser が順に代入するため、最後に指定した値が残ります。

## 実行時の動作

- 通常の `--ids` 経路では prompt の feed が完了した後、`n > 0` の場合だけ生成を始めます。生成 token を標準出力へ `ID,` の形式で逐次出力し、最後に改行します。EOS token ID `1` が出ると `DS4_NO_EOS` 環境変数が未設定の場合は上限前でも停止します。`DS4_NO_EOS` が設定されている場合は EOS で止めず、`n` 個まで続けます。
- decode round には残り数 `n - 生成済み数` を渡します。`--dspark` が有効な場合もこの残数が speculative decode の上限になります。温度と seed は `--temperature` と `--seed` が別途制御します。
- `--spec-eval FILE` と併用すると、各 segment の prompt を処理してから greedy の初回 token をサンプルし、その後 `emitted < n` の間 decode round を行います。`n <= 1` では round は行われませんが、評価関数は初回 token を先にサンプルし、ログ上の token 数を 1 として報告します。
- `--serve` は parser が受け取った `n` を serve 関数へ渡さず、各リクエストの `GEN <max_new>` が生成上限になります。`--profile-run` と `--score` も通常生成より先に分岐するため `--n` はその処理量を変えません。画像 encode 専用の `--encode-image` 経路でも使われません。

## 適用条件と副作用

`strata-dsv41` は `STRATA_BUILD_DSV41=ON` で生成される独立実行ファイルで、既定では build されません。通常の `--n` はモデルの読み込みと prompt feed の後に作用するため、0 以下でもそれらの処理は行われます。生成時は標準出力へ token ID を出し、モデルの decode 処理を実行します。`--spec-eval` では各 segment ごとにモデル状態を reset して評価します。

## 出力とエラー

- 通常の decode は標準出力へ token ID をカンマ区切りで出力します。prompt/decode の統計や診断は stderr に出力されます。
- `--n` に対する範囲外エラーは実装されていません。値の validation 失敗による専用エラーもありません。
- prompt feed または decode round が失敗すると stderr にエラーを出し、終了コード 1 で終了します。`--n` の値不足は終了コード 2 です。

## 根拠

- `CMakeLists.txt:797-811` — DSV41 engine は `STRATA_BUILD_DSV41` の opt-in で生成される独立 target。
- `src/dsv41/ds4_main.cpp:85-94` — usage では `--ids` モードの `[--n N]` として記載。
- `src/dsv41/ds4_main.cpp:1187-1207,1255-1257` — 初期値 0、値の必須取得と `std::atoi` による parser。
- `src/dsv41/ds4_main.cpp:1282-1301` — pack/mode の必須確認、serve/profile/spec-eval/score の分岐順。
- `src/dsv41/ds4_main.cpp:1385-1415` — 通常経路の `n > 0` 条件、decode の残数、EOS 停止条件、標準出力。
- `src/dsv41/ds4_main.cpp:1130-1179` — `--spec-eval` での意味、初回サンプル、round 上限と segment ごとのログ。
