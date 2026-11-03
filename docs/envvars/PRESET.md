# `PRESET`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数は対象外。

## 役割

`PRESET` は Strata 本体が直接読む変数ではなく、Docker イメージの `docker/entrypoint.sh` が読むシェル環境変数です。コンテナの通常起動時に `strata launch` へ渡す保存済み launch preset の名前を選びます。既定名は `docker` です。Docker entrypoint を通さず `strata` を直接起動する場合、この変数は参照されません（`docker/entrypoint.sh:34,53-56`）。

## 値と判定

| 入力 | entrypoint の扱い |
| --- | --- |
| 未設定 | `docker` に置き換える |
| 空文字 | `docker` に置き換える（シェルの `${PRESET:-docker}`） |
| 空でない文字列 | その文字列をトリム・大文字小文字変換・数値化せず保持し、プリセット一覧の検索と `strata launch` 引数に使う |
| 空白だけ、または CLI 側で有効な名前にならない値 | entrypoint 独自の値検証はない。プリセット照合に失敗すれば新規保存側に進み、launch preset store は名前を slug 化する。空白だけの名前は保存時に `A preset needs a name.` で拒否される |

設定値の比較は厳密な値パーサーではありません。entrypoint は JSON のプリセット一覧に対して `grep` の正規表現で名前を探し（`docker/entrypoint.sh:173-174`）、tuning 済み判定にも表示名を正規表現として渡します（同:228-239）。そのため、値の文字列全体を安全な完全一致として検査する処理や、許可文字の検証はありません。Strata 側の保存ファイル名は `slug()` が小文字化し、許可外の連続文字を `-` に変換し、最大 48 文字に切り詰めます（`strata_cli/launch/settings.py:371-376`）。

## 有効になる条件

- この設定が使われるのは Docker のデフォルト entrypoint が通常起動（引数なし、または `run` / `serve`）として処理するときです。別コマンドを渡すと entrypoint は早期に `exec` し、`PRESET` を使いません（`docker/entrypoint.sh:53-56`）。通常起動でも、preset の照合に到達する前にエンジンとデバイス確認があり、失敗すると終了コード 3 で終わります（同:136-160）。PRESET の値判定自体に backend 別の分岐はありません。
- entrypoint は一覧に名前が見つかると `--preset NAME` を付けます。起動設定も指定されていれば同時に `--save-preset NAME` を付け、今回の設定を同じ名前で保存します。名前が見つからない場合は `--save-preset NAME` を付け、新しい preset として保存する経路にします（`docker/entrypoint.sh:169-175,190-250`）。
- `have` は `MODEL`, `FAMILY`, `MODEL_PATH`/`GGUF_DIR`, `CONTEXT`, `PARALLEL`, `KV`, `VISION`, `GPU`/`GPUS`, `GPU_ROLES`, `STRATA_SET`、または有効な `TUNE` などが指定されたときに立ちます（`docker/entrypoint.sh:190-241`）。既存 preset に設定を足す場合、Strata はまず preset を読み、CLI の指定で上書きします（`strata_cli/launch/cmd.py:212-225`）。
- 既存名で追加設定がない場合は `--preset` だけで保存済み設定を使います。既存名に追加設定がある場合は `--preset` と `--save-preset` の両方が渡り、起動処理後にその名前で保存されます（`docker/entrypoint.sh:243-250`; `strata_cli/launch/cmd.py:993-997`）。
- 一覧にない名前で追加設定がある場合は `--save-preset` で保存を試みます。未登録名で追加設定がなく `TUNE` もない場合、entrypoint は推奨モデルを選ぶ旨の警告を出しますが、実際には `--no-tui` 起動に選択肢がないため CLI が終了コード 2 で失敗します。`have_choices` は `--save-preset` を含まず、非対話かつ `--no-tui` のとき選択がなければ `strata launch` が失敗する実装です（`docker/entrypoint.sh:228-250`; `strata_cli/launch/cmd.py:879-891`）。

## 実行時の詳細

entrypoint は起動時に一度 `PRESET` をシェル変数へ展開し、その後の一覧照合、tuning 済み照合、launch 引数、停止処理、API key の表示・保存に同じ値を使います。プロセス起動後に環境を書き換えて再読する処理はありません（`docker/entrypoint.sh:34,173-175,228-250,253-299`）。

起動成功後の主な引数利用は次の通りです。

- preset が存在すれば `strata launch --preset NAME` で読み込みます。CLI は保存設定を読み、同じ実行のフラグをその上に適用します（`strata_cli/launch/cmd.py:212-225`）。存在しない保存済み preset を `--preset` で読み込もうとした場合、store は `There is no saved preset called 'NAME'.` を返し、CLI は終了コード 2 にします（`strata_cli/launch/store.py:88-103`; `strata_cli/launch/cmd.py:1048-1051`）。
- `TUNE` が有効なとき、一覧の名前で tuning 済みかを確認し、未調整なら `--tune` を追加します。既に調整済みなら `RETUNE=1` がない限り再調整せず、`This preset is already tuned; keeping the tuned settings ...` と表示します（`docker/entrypoint.sh:228-239`）。
- 起動プロセス終了時は `strata launch --stop --preset NAME`、成功後の key 取得は `strata launch --show-key --preset NAME` を呼びます。画面出力にも preset 名を含めます（`docker/entrypoint.sh:253-299`）。
- 起動コマンドが非ゼロ終了すると entrypoint は `strata launch stopped with code N ...` を stderr に出して同じ終了コードで終了します（`docker/entrypoint.sh:285-292`）。

## 根拠

- `docker/entrypoint.sh:24,34,53-56` — Docker 専用設定の説明、未設定・空値の既定値、通常起動を外れる早期実行。
- `docker/entrypoint.sh:136-160,169-175,228-250` — エンジン確認、preset 一覧照合、tuning 済み確認、`--preset` / `--save-preset` の選択。
- `docker/entrypoint.sh:253-299` — 終了処理、起動ログ、key 取得への名前の引き渡し、失敗時の終了。
- `strata_cli/launch/cmd.py:212-225,879-891,993-997,1048-1051` — CLI の保存設定と引数の優先順位、選択不足の終了条件、保存、preset エラーの終了コード。
- `strata_cli/launch/store.py:68-103`; `strata_cli/launch/settings.py:371-376` — 名前の空判定、未登録 preset のエラー、slug 化。
- `docs/DOCKER.md:108-138` — Docker の設定一覧と `/data` に保存される利用者設定についての説明。動作の説明は上記ソース実装に基づく。
