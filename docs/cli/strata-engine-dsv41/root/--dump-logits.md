# `--dump-logits`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（usage 表示名: `maya-ds4`） |
| オプション | `--dump-logits` |
| 別名 | なし |
| 値 | 出力先のファイルパス（1引数） |

## 役割

通常の token-ID 入力による推論で、モデルが計算した logits をバイナリファイルへ書き出します。DeepSeek-V4.1 エンジンの任意 build target 向けオプションです。CMake の `STRATA_BUILD_DSV41` は既定で `OFF` であり、対象構成で有効化したとき `strata-dsv41` executable が追加されます（`CMakeLists.txt:797-811`）。

## 使い方

未使用の出力先を指定します。`--pack` にはモデルの `maya-ds4` pack、`--ids` には入力 token ID 列を渡します。

```sh
strata-dsv41 --pack /models/example/maya-ds4 --ids 1,128803 --dump-logits ./logits.f32
```

`--ids` が必要な通常推論では、空でない token 列を与えます。`--n N` を加えると prompt 後の生成も実行します。usage は `--ids ... [--n N] [--dump-logits FILE]` と示しています（`src/dsv41/ds4_main.cpp:85-94`）。

## 値と既定値

- 値は `--dump-logits` の次の argv 一つをそのままパスとして受け取ります。値の形式、拡張子、存在確認などの事前 validation はありません。値を省略すると parser の `val()` が `--dump-logits needs a value` を stderr に出して終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1202-1208,1258`）。
- 未指定時の内部値は空文字列で、dump は無効です（`src/dsv41/ds4_main.cpp:1187-1191,1356`）。空文字列を明示した場合も同じ扱いになります。
- 複数回指定すると変数への代入が繰り返され、最後の値が使用されます（`src/dsv41/ds4_main.cpp:1258`）。

## 実行時の動作

指定パスを `fopen(path, "wb")` で開きます。したがって同名ファイルが既にあれば内容を切り詰めます。出力は `float` 要素を要素サイズ4バイトでそのまま書く raw binary で、ヘッダーや token ID は付加されません（`src/dsv41/ds4_main.cpp:1356-1357,1367,1416`）。

通常推論の prompt 処理では、ファイルを開けた場合に各 feed chunk について logits を要求し、`m.logits()` が成功したとき得られる float 配列全体を出力します。既定の window はこのとき16 tokenです。`--window` を指定した場合はその値（parser では最低1）を使います。モデル側は `logits_rows > 16` の feed では各行分を `chunk_logits` に集め、それ以外では最後の feed window の要求行を保持します（`src/dsv41/ds4_main.cpp:1257,1356-1368`; `src/dsv41/ds4_model.cu:7889-7891,7930-7932,8985-8994`）。

`--n` が正数なら生成を行い、生成ループ後に `m.logits()` が成功したとき、その時点の logits 配列も同じファイルに追記します（`src/dsv41/ds4_main.cpp:1385-1416`）。ただし、ここで取得するのは生成ループ全体の後に一度だけ読まれる現在の buffer です。ソースからは speculative decode 中のすべての生成位置を順番に記録する保証や、出力ファイル内の各行と token の対応を示すメタデータは確認できません。

## 適用条件と副作用

- `--dump-logits` 自体は通常推論モードを選択しません。`--serve` は model load 後に server 関数へ戻り、`--profile-run`、`--spec-eval`、`--score` は dump 用の通常推論処理より先にそれぞれの処理へ戻ります。また、画像 encode 専用経路も dump 用ファイルを開く前に戻ります。通常の token-ID 入力経路でのみここに記した出力処理へ進みます（`src/dsv41/ds4_main.cpp:1282-1303,1322-1327,1356`）。
- ファイルを開けなかった場合、`df` は null のままです。エラーは表示されず dump なしとして処理が続き、window 未指定時は dump 用の16ではなくモデルの feed unit に基づく値になります（`src/dsv41/ds4_main.cpp:1356-1358`）。
- ファイルへの書き込み結果 (`fwrite`) と `fclose` の結果は検査されません。途中の feed / generation error は stderr に `maya-ds4: ...` を出して終了コード `1` を返しますが、その経路では明示的な `fclose(df)` に到達しません（`src/dsv41/ds4_main.cpp:1360-1368,1397-1405,1505-1507`）。
- 入力 token ID がモデル vocabulary の範囲外なら model feed が失敗し、エラーを stderr に出して終了コード `1` になります（`src/dsv41/ds4_model.cu:7891-7900`; `src/dsv41/ds4_main.cpp:1360-1365`）。

## 根拠

- parser、値不足時の終了、usage: `src/dsv41/ds4_main.cpp:85-94,1200-1208,1255-1269`
- dump ファイルの open、prompt logits の書き込み、生成後の buffer 書き込み、close: `src/dsv41/ds4_main.cpp:1356-1368,1385-1416,1505-1507`
- logits の格納行数・取得方法: `src/dsv41/ds4_model.cu:7889-7891,7930-7932,8985-8994`
- target が任意 build であること: `CMakeLists.txt:797-811`

調査範囲は上記 commit のソースです。Release artifact の配布状況と、実機での出力内容・性能は確認していません。
