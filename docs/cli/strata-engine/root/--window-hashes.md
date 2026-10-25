# `--window-hashes`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--window-hashes` |
| 別名 | なし |
| 値 | 出力ファイルのパス（文字列） |

## 役割

投機的デコードの各 verify window について、window の位置・幅、最終 residual rows のハッシュ、各行の argmax token ID をテキストファイルへ記録します。推論結果そのものの保存や、モデルの重みのハッシュではありません。実装コメントはこの記録をテスト用の経路としています（`src/program/generate.cpp:677-678, 16628-16637`）。

## 使い方

モデルと入力 token ファイルを指定する通常の起動例です。`--spec-follow` には比較対象の continuation token ID 列を置き、出力先には新しいファイルを指定します。

```sh
strata --pack model.gguf --tokens-file prompt.tokens \
  --spec 4 --spec-follow continuation.tokens --adapt-every 0 \
  --window-hashes /tmp/window-hashes.txt
```

`--spec-follow` と `--adapt-every 0` の併用は、同じ continuation と固定した適応設定で build 間を比較する用途として help に案内されています（`src/program/generate.cpp:979-984`）。verify loop が実際に走るには、モデル・入力・実行環境の条件も満たす必要があります。

## 値と既定値

- 値は `next("--window-hashes")` で次の argv 要素からそのまま読み取られます。専用の形式・範囲検査はありません（`src/program/generate.cpp:2418-2420, 2622`）。
- 省略時は空文字列のままで、ファイルを開かず記録もしません（`src/program/generate.cpp:678, 16418`）。別の既定パスはありません。
- 値を省略すると `--window-hashes needs a value` を stderr に出し、parser 内の `exit(2)` で終了します（`src/program/generate.cpp:2418-2420`）。空文字列を明示した場合は空値として保持され、ファイル出力は無効になります。
- 複数回指定した場合の重複拒否はなく、parser は同じフィールドへ順に代入するため最後の値が残ります（`src/program/generate.cpp:2416-2422, 2622`）。

## 実行時の動作

parser はパスを `Options::window_hashes` に格納します。投機的デコードの loop が開始された後に限り、空でないパスを `fopen(path, "w")` で開きます。そのため既存ファイルがあれば切り詰められ、追記ではありません。通常の非投機 decode や、生成上限・停止条件などで verify loop に入らない実行では、この箇所でファイルは開かれません（`src/program/generate.cpp:16091-16102, 16408-16420`）。

各 verify window の検証後、`T * (g.hc * g.n_embd)` 個の float に相当する final residual rows を GPU から host にコピーします。コピーした float の生バイト列を走査し、コード中の初期値 `1469598103934665603` と乗数 `1099511628211` を使って 64-bit 値を計算します。その後、1行に次の順で記録します（`src/program/generate.cpp:16628-16637`）。

1. window の round index `rounds`
2. window の開始位置 `p`
3. 実際に検証した幅 `T`
4. 16桁の16進表記の residual hash
5. `T` 個の argmax token ID

hash は follow token 適用前に計算・出力されます。`--spec-follow` が指定されていれば、その後で `outv` を continuation token に置き換えて続行します（`src/program/generate.cpp:16628-16644`）。help は、同じ演算を行う build で同じファイルを得る用途として説明しています（`src/program/generate.cpp:982-984`）。

## 適用条件と副作用

- この記録処理は `spec_loop_runs(...)` が true の投機的デコード経路内にあります。通常 decode の出力には作用しません（`src/program/generate.cpp:16095-16102, 16416-16420`）。
- `--spec-follow` は同じ continuation で比較するための関連 option です。ファイルが読めない、または token 列として解析できない場合はエラーを stderr に出して終了コード 2 になります（`src/program/generate.cpp:16103-16116`）。
- help は `--adapt-every 0` を併用例として示しています。明示指定は parser で `adapt_every` に保存されますが、適応処理全般をこの option が無効化するわけではありません（`src/program/generate.cpp:2626, 982-984`）。
- 出力先は `"w"` モードで作成または切り詰められます。既存データを残したい場合は別パスを指定してください（`src/program/generate.cpp:16418`）。
- ファイルを開けない場合は `strata generate: cannot write <path>` を stderr に出し、終了コード 1 で失敗します（`src/program/generate.cpp:16418-16421`）。書き込み・close の戻り値はこのコードで確認していません（`src/program/generate.cpp:16635-16637, 16725`）。
- SYCL 実装にも同じ parser、`"w"` の open と同じ列構成の出力があります（`sycl/src/program/generate.cpp:1920, 12638-12641, 12734-12746, 12830`）。この調査では実行バイナリを用いた platform 別の挙動確認はしていません。

## 出力とエラー

通常の parser は値を検証しません。値欠落は終了コード 2、投機 loop での出力ファイル open 失敗は終了コード 1 です。open 失敗が検出されるのは verify 用の初期化処理後であり、その時点までに行われた初期化の副作用はこの option では取り消されません（`src/program/generate.cpp:16121-16141, 16408-16421`）。正常時の各行は専用ファイルに `fprintf` されます。標準出力にはこの option 固有の完了メッセージはありません。

## 根拠

- parser と値欠落時の処理: `src/program/generate.cpp:2418-2420, 2622`
- option の保存先・help の用途説明: `src/program/generate.cpp:677-678, 982-984`
- verify loop と出力ファイル open: `src/program/generate.cpp:16091-16102, 16408-16421`
- hash 算出・1行の形式・follow 処理との順序: `src/program/generate.cpp:16628-16644`
- 正常時の close: `src/program/generate.cpp:16720-16727`
- SYCL 実装: `sycl/src/program/generate.cpp:639, 1920, 12638-12641, 12734-12746, 12830`
