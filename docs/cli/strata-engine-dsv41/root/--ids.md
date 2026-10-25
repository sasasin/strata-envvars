# `--ids`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（トップレベル） |
| オプション | `--ids` |
| 別名 | なし |
| 値 | カンマまたは空白区切りの整数 token ID 列。`@PATH` を指定すると PATH から列を読む |

## 役割

DeepSeek-V4.1 エンジンに入力 prompt の token ID 列を渡します。読み込んだ ID はモデルの prompt として順に feed され、[`--n`](--n.md) を併用した場合はその続きの token を生成します。`--ids` は `--serve`、`--score`、`--profile-run`、`--spec-eval` などとは別の通常 prompt 実行経路です。

## 使い方

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids 0,128803,42 --n 16
```

ID 列が長い場合は `@` に続けてファイル名を指定できます。

```sh
strata-dsv41 --pack /path/to/model/maya-ds4 --ids @prompt.ids --n 16
```

## 値と既定値

- `--ids` の値は必須です。値がコマンド末尾にない場合、`--ids needs a value` を標準エラーに出して終了コード 2 で終了します。
- 値は `strtol(..., 10)` で整数を順に読みます。読み取った整数の後はカンマと ASCII 空白を読み飛ばします。空白類は `strtol` の先頭空白処理でも扱われます。明示的な区切り形式・ID の個数範囲は parser で検証されません。
- 数字として読めない文字に達すると、そこで解析を止めます。したがって、余分な文字や不正な後続部分はエラーにならず、前までに読めた ID だけが使われます。負数など整数として読める値は後段のモデル検証に渡されます。
- 先頭文字が `@` の値は、その後ろのパスを開いてファイル全体を読みます。ファイル読み込みの成否は確認されず、開けない場合も空の入力列になります。読み込んだファイル内容も同じ整数列 parser に渡ります。
- `--ids` 自体に既定値はありません。通常実行では `--pack` と、`--serve`・`--ids`・画像エンコード・score/profile/spec のいずれかの実行指定が必要です。`--n` の既定値は 0 で、指定しなければ prompt feed 後の生成ループには入りません。

## 実行時の動作

通常 prompt 経路では、`@PATH` の内容を読んだあと整数列に変換し、[`--images`](--images.md) があれば画像ファイルを読み込んで prompt 内の画像 span として設定します。その後、列を [`--window`](--window.md) の大きさ（未指定時はモデルの feed unit を基に決定）に分けてモデルへ feed します。最後の window では通常 feed 時に最後の token の logits を要求します。`--n > 0` なら、その prompt 状態から token の decode を始め、生成 token ID をカンマ区切りで標準出力へ出します。

`--serve` が指定されると server 経路を先に実行して戻るため `--ids` は通常 prompt として処理されません。また `--profile-run`、`--spec-eval`、`--score` が同時に指定された場合は、それぞれ通常 prompt 経路より先に処理されます。通常 prompt のみで [`--dump-logits`](--dump-logits.md) を併用すると、各 prompt 位置の logits を指定ファイルへ書く経路が有効になります。出力ファイルは prompt 処理前に `wb` で開かれるため、既存ファイルは切り詰められます。open の失敗は検査されず、失敗時は logits 出力なしで続行します。

## 適用条件と副作用

- エンジンは CMake の `STRATA_BUILD_DSV41=ON` で有効になる独立実行ファイルです。この設定は既定で OFF で、gfx906 では target を作成しません。リリース配布の有無はこのソース調査からは確認していません。
- `--pack` のモデルをロードし、GPU/CPU 等の推論資源を使って prompt を処理します。実際の対応条件は build/backend と pack に依存します。
- prompt token が語彙範囲外（負数または vocab 以上）の場合は feed が失敗します。`--max-context` を超える prompt もモデル側で失敗します。
- `--ids @PATH` はファイルを読みますが、読み込み失敗を専用エラーとして報告しません。空列となった場合は prompt feed のループが実行されません。`--n` も指定した場合の空 prompt に対する sampling の挙動は、この入口のコードだけでは保証されません。
- `--images` は `--ids` の各 ID の意味を変更するものではなく、別途読み込む DSI1 画像データを prompt 内の位置に結び付けます。画像ファイル不正・open 失敗時はエラーになります。

## 出力とエラー

- `--ids` の値不足は標準エラーに表示され、終了コード 2 です。
- 必須の `--pack` または実行モードの指定がない場合は usage を標準エラーへ出し、終了コード 2 です。
- モデル load または prompt feed が失敗すると `maya-ds4: <理由>` を標準エラーへ出し、終了コード 1 です。feed 側では token の語彙範囲外を `token <ID> out of range` として報告します。
- prompt feed の正常終了時、prompt の token 数・所要時間等を標準エラーへ表示します。生成を行う場合、生成 ID 列は標準出力へ出ます。

## 根拠

- `CMakeLists.txt:797-811` — `strata-dsv41` target の build 条件と実行ファイル定義。
- `src/dsv41/ds4_main.cpp:71-83` — 整数列 parser の変換・区切り処理。
- `src/dsv41/ds4_main.cpp:85-94` — usage に記載された `--ids` の位置付け。
- `src/dsv41/ds4_main.cpp:1187-1208, 1255-1273` — root parser、値取得、値不足・未知 option のエラー経路。
- `src/dsv41/ds4_main.cpp:1275-1302, 1329-1373, 1385-1397` — 必須条件と実行モードの優先順、`@PATH` 読み込み、prompt feed、画像・logits 関連処理、生成ループ。
- `src/dsv41/ds4_model.cu:7891-7900, 8277-8290, 9056-9068` — prompt feed の context と token 範囲検査、feed 経路。
- `docs/cli/README.md:1353-1372` — `strata-engine-dsv41` のコマンド階層・索引リンク。Release 配布の有無は索引でも未確定とされる。
