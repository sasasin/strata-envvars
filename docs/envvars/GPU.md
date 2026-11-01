# `GPU`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

`GPU` は Strata 全体で共通のエンジン環境変数ではありません。確認できた本番経路は Docker イメージの `docker/entrypoint.sh` で、カード番号を読み `strata launch --gpu` 引数に渡します。Docker entrypoint を通さず `strata` を直接起動する場合、この変数は参照されません。

同梱の比較用スクリプト `tools/dsv41/bytecheck.sh` も `GPU` を読み、子プロセスに `CUDA_VISIBLE_DEVICES` として渡します。このスクリプトは指定した二つの DeepSeek ビルドを実行する検証ツールであり、通常の Strata 起動設定とは別経路です。

## 値と判定

| 読み取り先 | 未設定・空文字 | 設定時の処理 |
|---|---|---|
| Docker `docker/entrypoint.sh` | `GPUS` も未設定または空なら `GPU` は空扱い。`--gpu` を渡さず、カード選択は launch の既定経路に任せる | `GPUS` が未設定・空の場合に限り `GPU` の値を使う。`all` または `ALL` は `--gpu` を渡さない。それ以外は値をそのまま `--gpu <値>` に渡す |
| `tools/dsv41/bytecheck.sh` | `${GPU:-0}` により `CUDA_VISIBLE_DEVICES=0` を渡す | 値を parse・検証せず `CUDA_VISIBLE_DEVICES=<値>` として各ビルドの実行環境へ渡す |

Docker 経路では、`GPU=0` や `GPU=0,1` は launch のカード番号リストになります。launch 側の `_gpus()` は空白をすべて除き、カンマで分割した各要素を Python `int()` に変換し、空要素は捨てます。したがって `0, 1` は `[0, 1]`、`0,,1` も `[0, 1]` になります。整数に変換できない文字列（例 `GPU=All`）は `'<値>' is not a list of graphics card numbers. Use 0 or 0,1.` のエラーになり、`strata launch` は終了コード 2 を返します。番号の有効範囲を `_gpus()` 自体は検査せず、ここで clamp もしません。カンマだけなど空要素しかない値は空リストになります。

Docker entrypoint は大文字小文字を区別して `all` と `ALL` だけを特別扱いします。空値も特別扱いされます。`All` などは特別扱いされず launch に渡ります。比較用スクリプトでは空値は未設定と同じで既定 `0`、その他は文字列のままです。

## 有効になる条件

- Docker の通常起動経路（引数なし、または先頭引数が `run` / `serve`）で読み取られます。別コマンドが渡された場合、entrypoint は初期処理の前に `exec` するため `GPU` は適用しません。
- Docker では空でない `GPUS` が `GPU` より優先されます。`GPUS` が空なら `GPU` に戻ります。`GPU_ROLES` も指定されていると、実カード指定との併用を拒み、stderr に `Set GPU_ROLES or GPU / GPUS, not both.` を出して entrypoint が終了コード 2 で止まります。`GPU` が空または `all` / `ALL` の場合はこの競合になりません。
- `--gpu` は preset から読み込んだ launch 設定より優先され、今回の launch に使うカードを上書きします。指定がなければ、保存済みモデル設定のカード選択があればそれを使い、なければカード選択の既定処理に進みます。明示されたカード選択は launch 用設定に反映されます。
- Docker entrypoint は、保存済みモデル設定の GPU と今回要求された GPU が違う場合、該当する `/data/install/strata-*.json` を削除してモデルファイルから設定を作り直します。GPU 指定が同じ場合は削除しません。`all` / 空値ではこの比較・削除経路に入りません。
- 比較用スクリプトは GPU 実行ファイルを呼ぶ各 run で値を読みます。シェル展開で子プロセスの環境に付与するため、スクリプト内の cache はありません。Docker entrypoint は launch コマンド構築時に一度読み、コマンドに引き渡します。

## 実行時の詳細

Docker entrypoint は `GPUS` / `GPU` の実効値が `all`（または空）以外なら `--gpu` を追加し、launch の preset があれば `--save-preset` を指定します。launch の引数処理は preset を読み込んだ後に `--gpu` を設定へ反映します。CLI のカード指定は launch config の `gpu` フィールドに書かれ、複数カードなら `layer_split` が未指定のとき `auto` になります。Docker のログでは保存済み選択と不一致のとき `The saved run settings use graphics card ...: making them again (model files are kept).` が表示されます。

形式不正の値は launch の `ValueError` 経路から `strata: ...` と stderr に出て終了コード 2 になります。Docker entrypoint は launch の非ゼロ終了を受けると phase を `failed` にし、`strata launch stopped with code <終了コード> ...` を stderr に出してコンテナを終了します。比較用スクリプトは `CUDA_VISIBLE_DEVICES` を付けて各実行ファイルを起動し、終了後に `<build> <check> rc=<終了コード>` を出します。この環境変数の先にある GPU 可視性の解釈・挙動は外部実行ファイル側なので、ここでは Strata の動作として扱いません。

## 根拠

- `docker/entrypoint.sh:53-56,203-224,242-249,273-290`: Docker 通常起動と直接コマンドの分岐、`GPUS` 優先で `GPU` を選ぶ処理、`--gpu` への変換、`GPU_ROLES` との競合、preset 保存、launch 終了時のエラー。
- `strata_cli/launch/cmd.py:112-113,196-203,205-210,250-261,753,913-918`: `--gpu` / `--gpu-roles` 引数、カード番号の変換、preset の後に CLI 値を適用する順序、エラー終了コード。
- `strata_cli/launch/runner.py:329-356,378-399,535-545`: 指定カードの launch config への反映、既存設定・自動選択との関係。
- `strata_cli/launch/runner.py:1438-1454`: 設定作成時にカード選択を適用し launch 用 JSON を書く処理。
- `tools/dsv41/bytecheck.sh:4-11,35-49,51-55`: 比較用スクリプトの用途、`GPU` の既定値と `CUDA_VISIBLE_DEVICES` として子実行へ渡す箇所。
- 補助資料 `docs/DOCKER.md:110-124` も Docker の `GPU` / `GPUS` をカード番号、空または `all` を engine 選択として説明しています。実装上は `GPUS` が `GPU` より優先し、`ALL` も特別扱いされます。
