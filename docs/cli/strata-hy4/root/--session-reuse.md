# `strata-hy4 --session-reuse`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root。主に `--serve` と併用） |
| オプション | `--session-reuse` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。0 は無効、0 以外は有効 |

## 役割

`--serve` で起動した CUDA/HIP の Hy4-Flash サーバーで、リクエスト間に GPU 上の KV 状態を保持し、後続 prompt が前回処理済み token 列をそのまま含んで延長する場合に、その続きから処理します。サーバーを起動したまま同じ会話の続きのリクエストを送る利用を想定した設定です。オフライン実行ではこの設定は ServeOpts に渡されず、効果がありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-565,611-613`）。

## 使い方

```sh
# サーバーモードを起動し、会話間の KV 再利用を有効にする
strata-hy4 --serve --model Model.strata --session-reuse 1
```

## 値と既定値

- 引数は必須です。値を省略すると `ERR --session-reuse needs a value` を標準出力に出し、終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383,444`）。
- 既定値は無効（`false`）です（`engine/src/hy4flash/run/hy4_main.hip.cpp:351-353`）。
- 値は `atoi` で整数変換され、0 なら無効、0 以外なら有効です。厳密な数値形式や範囲の検証はありません。オプションを複数回指定した場合は、引数走査中の代入により最後の値が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,444`）。

## 実行時の動作

parser は値を boolean に変換し、`--serve` 経路で `ServeOpts.session_reuse` に渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:444,544-565`）。サーバーはこの設定、または `--conversation-cache-dir` で会話キャッシュの初期化に成功した状態のどちらかで再利用を有効にします（`engine/src/hy4flash/run/hy4_serve.hip.h:365-370`）。関連オプションは [`--conversation-cache-dir`](--conversation-cache-dir.md) を参照してください。

会話キャッシュを使わない場合、直前の処理済み token 列と次の request の prompt が処理済み部分まで完全一致し、prompt に未処理部分が続く場合に限って、残りの prompt から再開します。再開位置があると stdout のプロトコルに `RESUME n` が出ます（`engine/src/hy4flash/run/hy4_serve.hip.h:453-468,493-497`）。異なる prompt や短い prompt への共通 prefix から巻き戻して再利用する経路はなく、先頭から処理します（同:453-468）。生成された token も直前の token 列へ追加され、次のリクエストとの照合対象になります（同:575-593）。

再利用されるのはサーバープロセス内の GPU KV 状態です。完了後も再利用が有効なら処理済み位置を保持し、無効時または画像付きリクエスト時は位置をリセットします。画像付きリクエストは再利用判定から除外されます（`engine/src/hy4flash/run/hy4_serve.hip.h:389-417,453-468,601-605`）。このオプション単独によるファイル出力は確認できません。

## 適用条件と副作用

- 対象は `engine/src/hy4flash/run/hy4_main.hip.cpp` の CUDA/HIP parser です。索引上の Metal (`metal/`) と SYCL (`sycl/`) は別スコープであり、この文書では扱いません（`docs/cli/README.md:1277-1280,1358-1361`）。
- `--serve` がなければ `session_reuse` はサーバー設定へ渡らず、オフライン実行に影響しません（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-565,611-613`）。
- 再利用される KV 状態はサーバーの GPU メモリを占有し続けます。複数会話を保存する SSD キャッシュは `--conversation-cache-dir` との併用時の別機能です（`engine/src/hy4flash/run/hy4_serve.hip.h:365-367`）。

## 出力とエラー

起動時に標準出力へ `INFO ... session_reuse=0|1` と `READY ...` が出ます。この表示値は当オプション単独ではなく、会話キャッシュが有効な場合も 1 です（`engine/src/hy4flash/run/hy4_serve.hip.h:365-371`）。再開したリクエストでは `RESUME n` が出力されます（同:493-497）。引数不足時の標準出力と終了コードは「値と既定値」を参照してください。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:351-353,375-384,444` — 既定値、引数の取得と変換、parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-565,611-613` — serve 経路への受け渡しと、オフライン経路との境界。
- `engine/src/hy4flash/run/hy4_serve.hip.h:365-371,453-497,575-605` — 再利用の有効条件、prompt 照合・再開、出力、画像 request と完了時の状態処理。
- `docs/cli/README.md:1277-1280,1331-1333` — 対象コマンド階層と索引上の掲載。
