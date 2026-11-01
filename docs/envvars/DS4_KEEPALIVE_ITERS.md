# `DS4_KEEPALIVE_ITERS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DS4 Metal runtime の GPU keep-alive spin kernel 1 回の dispatch で、各 GPU thread が線形合同式の更新を何回行うかを指定します。これ自体は keep-alive を有効にしません。有効化の条件は別環境変数 `DS4_KEEPALIVE` です。

## 値と判定

worker thread が spin kernel と pipeline を作成した後、`DS4_KEEPALIVE_ITERS` を一度読みます。値が未設定なら `20000`、設定されていれば `std::atoi` の結果を `uint32_t` にキャストします。空文字や数値に変換できない先頭文字列は `atoi` が 0 を返すため、kernel のループ回数は 0 になります。

`atoi` は先頭の空白と符号を受け付け、数字列の後ろにある非数字は変換を止めるだけです（例: `12junk` は 12）。従って負数も拒否されず、`uint32_t` への変換で 2 の 32 乗を法とする値になります（例: `-1` は `UINT32_MAX`）。`atoi` の `int` 範囲を超える文字列の結果は規格上定義されないため、動作を保証できません。範囲検査、clamp、エラー処理はありません。

## 有効になる条件

- `metal/src/mtl_rt.mm` の keep-alive 実装が `STRATA_DS4_RUNTIME` ビルド macro の内側にあります。`metal/CMakeLists.txt` はこの macro を DS4 runtime object に定義し、その object を `strata_ds4` にリンクします。
- `Context::start_keepalive()` が呼ばれ、`DS4_KEEPALIVE` が設定されている必要があります。ここでは値の内容や空文字かどうかでなく、`getenv()` が null かどうかだけを判定します。未設定なら `DS4_KEEPALIVE_ITERS` の値は読み取られず、keep-alive thread も開始しません。
- 同じ Context の keep-alive が既に開始済みなら、atomic flag により追加の thread は開始しません。

この箇所には CLI 引数、設定ファイル、別の反復数環境変数による上書きはありません。文書化コメントにある `DS4_NO_KEEPALIVE` は実際の分岐条件ではなく、実装は `DS4_KEEPALIVE` の有無を見ています。

## 実行時の詳細

`ensure()` が Context を初期化するとき `start_keepalive()` を呼びます。`DS4_KEEPALIVE` が有効なら detached thread を作り、その中で Metal の spin kernel と pipeline を準備した後に反復数を取得します。従って値はプロセス起動時ではなくこの worker の初期化時に読み込まれ、以後の環境変更で再評価されません。

thread は最後の dispatch 時刻から 50 ms を超えていれば 2 ms sleep し、そうでなければ別 command queue で 256 thread の compute dispatch を投入して完了を待ちます。各 thread は指定回数だけ `x = x * 1664525u + 1013904223u` を反復します。値 0 でも thread と dispatch の仕組み自体は残り、kernel 内の反復 loop だけが 0 回になります。kernel library または pipeline の作成に失敗すると、その worker はエラーログを出さずに戻ります。反復数の不正値について Strata 独自の警告、終了、fallback はありません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:62-85`: `ensure()` が Context を生成し、keep-alive を開始。
- `metal/src/mtl_rt.mm:364-412`: macro guard、`DS4_KEEPALIVE` の有無判定、worker 起動、kernel の反復処理、既定値 20000 と環境値の変換、dispatch と失敗時の無言 return。
- `metal/src/mtl_rt.mm:927-931`: 各 dispatch の時刻を記録し、keep-alive の無活動判定に使う。
- `metal/CMakeLists.txt:151-165`: `STRATA_DS4_RUNTIME` を DS4 runtime object に定義し、`strata_ds4` にリンク。

候補一覧 `000_envvers.md` に名前がありますが、Strata ソース内の実参照は `metal/src/mtl_rt.mm:392` のみです。全リポジトリの候補名検索では、他の読み取り箇所や動的 helper への転送は見つかりませんでした。
