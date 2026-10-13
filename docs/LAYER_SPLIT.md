# `LAYER_SPLIT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Docker コンテナの entrypoint が `LAYER_SPLIT` を `setup.py --layer-split` に渡し、複数 GPU でモデルを分割する境界を指定します。この環境変数を読むのは `docker-entrypoint.sh` です。エンジン本体は環境変数 `LAYER_SPLIT` を読みません。setup の CLI 引数または保存済み設定を通して、エンジンの `--layer-split` になります。

境界値 `K` は各「後続 GPU が担当する最初のレイヤー番号」です。たとえば2 GPUで `18` なら、先の GPU がレイヤー 0–17、後の GPU が18以降を担当します。GPUごとのレイヤー数を並べる指定ではありません。

## 値と判定

| 環境変数の状態 | entrypoint の処理 |
|---|---|
| 未設定 | `${LAYER_SPLIT:-}` により空文字になる。`-n` 判定を通らず `--layer-split` を渡さない |
| 空文字 | 未設定と同じ。CLI 引数を渡さない |
| 空でない値 | 文字列を変換せず、そのまま `--layer-split <値>` として渡す |

したがって shell 側では `auto` や数値の妥当性を判定せず、空白だけの値も空ではないため渡します。数値境界を明示する場合は、後続 GPU ごとに1個、カンマ区切りで指定します（例: `18`、`16,32`）。`auto` は各 GPU の空き VRAM を使ってエンジンが境界を決める指定です。

setup のサーバー設定変換は `null`、空文字、空白だけ、または大文字小文字を問わない `auto` を `auto` として扱います。数値のリストは整数に変換してカンマ区切りに正規化し、空要素・整数にできない要素・GPU 数との要素数不一致（GPU が複数の場合）・2未満から始まらない列・昇順でない列を拒否します。エンジンの CLI 側でも `auto` 以外は数字だけのカンマ区切りとして検査され、最初の境界が2以上、以降が厳密な昇順である必要があります。

## 有効になる条件

- この環境変数の読み取りと転送は Docker の `docker-entrypoint.sh` に限られます。Docker を使わず `setup.py` やエンジンを直接実行する場合、`LAYER_SPLIT` 環境変数自体は参照されません。直接実行では `--layer-split` を指定します。
- 複数 GPU の指定（通常は `GPUS`）と組み合わせて使います。初回セットアップでは、entrypoint が両方を `setup.py --setup` に渡します。通常起動でも両方を渡し、setup は `--gpus` が与えられた場合に GPU リストと `layer_split` をモデル設定へ保存します。
- 既存の複数 GPU 設定に対して `LAYER_SPLIT` だけを渡し `GPUS` を渡さない場合、setup の通常起動経路はこの値を保存済み設定へ反映しません。環境変数を既存モデルの境界変更に使うときは `GPUS` も指定してください。
- エンジンの `--layer-split` は `--serve` を必要とします。数値境界の個数は後続 GPU 数と一致し、対応する別々の GPU が必要です。`auto` で可視 GPU が1つだけなら、stderr に `strata generate: --layer-split auto: one GPU visible, so no split` を出して分割指定を解除します。
- `--peer-device` と layer split は併用できず、エンジンは stderr に `strata generate: --peer-device cannot be combined with --layer-split (use one or the other)` を出して終了コード2で拒否します。

## 実行時の詳細

entrypoint は起動時に `${LAYER_SPLIT:-}` を変数へ代入します。値が空でなければ、モデルを新規セットアップする分岐（`--setup --no-start`）と、セットアップ後または既存設定からサーバーを起動する分岐の両方で `--layer-split` を組み立てます。既存設定を使う起動では、`CONFIG` の選択やモデル設定ファイルの読み込みを通してサーバーを起動します。

通常起動時に `GPUS` も指定している場合、setup は `--gpus` を受けて選択 GPU をモデル設定に保存し、`layer_split` には今回の `--layer-split`、既存値、`auto` の順で値を設定します。サーバーは複数 GPU 構成なら設定の `layer_split` をエンジン引数 `--layer-split` に追加します。エンジンは引数を起動時に一度解析し、`auto` なら空き VRAMから分割位置を探索し、手動値なら指定レイヤー位置を各後続ステージの開始位置として使います。サーバー側は `[strata] layer split across GPUs ... (...)` を出し、エンジンは自動配置時に `strata generate: layer split auto: K=...` などの配置情報を stderr に出します。

`LAYER_SPLIT` 自体の値をプロセス実行中に再読する処理はありません。コンテナの entrypoint 実行時に CLI 引数へ渡されるため、値を変えるにはコンテナを再起動します。`LAYER_SPLIT` をエンジン環境へ子プロセス継承する処理は確認できません。

## 根拠

- `docker-entrypoint.sh:28-30,50-53` — 変数の既定値と、GPUS等とともに任意指定である旨。
- `docker-entrypoint.sh:76-86,96-105` — 初回セットアップおよび通常起動の両方で、空でない値を `--layer-split` に渡す。
- `setup.py:4852-4859,4944-4950,4991-4995,5022-5028` — CLI 引数、GPU リストの解釈、通常起動時の `start()` 呼び出し。
- `setup.py:4354-4357,4380-4386` — `--gpus` で起動する場合、GPU リストと `layer_split` を設定へ保存。境界は引数値、既存値、`auto` の順で選ぶ。
- `serve/server.py:2368-2398,2401-2425` — 設定値の正規化・検査、および複数 GPU 設定からエンジン引数を組み立てる処理。
- `src/program/generate.cpp:2042,2299-2347,2645-2651` — エンジンの引数取り込み、`auto`/数値リストの検査、単一 GPU 時の `auto` 処理、peer-device との併用拒否。
- `docs/INSTALL.md:118-125` — Docker 利用者向けに `GPUS` と `LAYER_SPLIT` を例示。
- `docs/MULTI_GPU.md:41,60-68,99-100` — `auto`、境界値の意味、`--layer-split` と後続 GPU 指定の説明。
