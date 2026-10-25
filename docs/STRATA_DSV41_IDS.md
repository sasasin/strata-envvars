# `STRATA_DSV41_IDS`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

この変数は通常の Strata エンジンやセットアップの設定ではなく、DeepSeek-V4.1 の prompt-skip 比較テスト `tools/dsv41/test_prompt_skip.py` が入力する golden IDs ファイルのパスです。テストが実行されると、その文字列を `strata-dsv41 --score <値>` に渡し、prompt skip を無効にした実行と有効にした実行の結果を比較します。

リポジトリ内の完全一致検索では、環境変数として読む実装はこのテストファイルだけです。エンジン本体にはこの名前を読む処理はなく、エンジンはテストから CLI 引数 `--score` で受け取ったパスを使います。

## 値と判定

| 値 | テストの扱い |
|---|---|
| 未設定 | `os.environ.get()` が `None` を返し、比較テストを skip |
| 空文字 | 空文字列は偽として扱われ、比較テストを skip |
| 空でない文字列 | 文字列の形式や内容を検証せず truthy として扱い、比較テストを実行。値を IDs ファイルのパスとして `--score` に渡す |

数値変換、空白除去、大小文字変換、パス解決はありません。たとえば文字列 `0` も空でないためテストを実行します。値の読み取りは Python モジュールの import 時に一度行われ、その値で unittest の skip 条件がクラス定義時に決まります。import 後の環境変更はこのテストの `IDS` 値に反映されません。

## 有効になる条件

比較テストは `STRATA_DSV41_BIN`、`STRATA_DSV41_PACK`、`STRATA_DSV41_IDS` の3つがすべて空でない場合にだけ実行されます。環境変数の存在だけでは GPU、pack、IDs ファイルの妥当性を確認しません。テストファイルの説明では GPU、DeepSeek-V4.1 pack、golden IDs file が必要とされています。

このテストは `STRATA_BUILD_DSV41=ON` かつ `STRATA_HIP_GFX906` ではない構成で作られる専用 `strata-dsv41` を使います。CMake の同オプションは既定で OFF です。通常の `strata` エンジンで `STRATA_DSV41_IDS` が動作を変える経路は確認できません。

## 実行時の詳細

テストは同じバイナリを `STRATA_DS4_PROMPT_SKIP=0` と `=1` でそれぞれ起動します。両方の起動で `IDS` を `--score` 引数に渡し、親環境を複製した子プロセス環境には `DS4_SCORE_PREFIX=4200` と `DS4_CHUNK=1024` も設定します。各実行の score 出力を一時ディレクトリに保存し、比較結果について 500 超の positions、KL `< 0.002`、top-1 一致率 `>= 0.99` を unittest で検査します。

エンジンは `--score` の値を score IDs ファイルのパスとして扱います。ファイルを開けなければ stderr に `<path>: cannot open` を含む `strata-dsv41: ...` を出して終了コード 1 を返します。ファイルを開けても有効な segment がなければ `no segments (expected quant_quality.py's ids file)` を出して同じく 1 を返します。テスト側の `subprocess.run(..., check=True)` はその非ゼロ終了を例外として扱います。これらは `--score` の動作であり、エンジンが `STRATA_DSV41_IDS` 環境変数を直接読むことを意味しません。

## 根拠

- `tools/dsv41/test_prompt_skip.py:1-11` — テスト用途、必要とする入力、golden IDs を使う比較の説明。
- `tools/dsv41/test_prompt_skip.py:23-25,38-52` — import 時の環境読み取り、3変数の truthy 判定、`IDS` を `--score` に渡す処理と比較条件。
- `src/dsv41/ds4_main.cpp:972-1003,1006-1011` — `--score` から渡されたファイルを開き、segment がない場合にエラーを返す処理。
- `src/dsv41/ds4_main.cpp:1259-1260,1282,1301` — CLI の `--score` 引数を score 処理に結び付ける箇所。
- `CMakeLists.txt:797-811` — DSV41 の専用 executable と、既定 OFF の build option。

