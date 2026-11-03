# `REINSTALL`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

現在の Docker イメージでは旧イメージ由来の設定として検出し、値が空でなければ「無視される」と stderr に警告します。再インストールやモデル設定の再適用を指示する動作は、この commit の Strata 所有コードでは確認できません。Strata のエンジンや CLI が `REINSTALL` を読む箇所も見つかりませんでした。

## 値と判定

`docker/entrypoint.sh` は旧設定名の一覧を順に走査し、`eval` で各名前の環境値を `v` に取り出してから、シェルの `-n` で空でないかを判定します。

| 値 | 判定と結果 |
|---|---|
| 未設定 | `v` は空になり、警告しない |
| 空文字 | `${VAR:-}` の既定展開で空になり、未設定と同じく警告しない |
| 空でない値 | 内容にかかわらず警告する。例: `1`、`0`、`false`、空白文字 |

数値や真偽値への変換、文字列比較、値域検証はありません。値が空でないときも失敗・終了にはならず、その設定は無視されます。根拠: `docker/entrypoint.sh:80-83`。

## 有効になる条件

- Docker イメージの既定 `CMD` は `run` で、`ENTRYPOINT` は `/opt/strata/entrypoint.sh` です。したがって通常のコンテナ起動ではこのスクリプトが動きます（`docker/Dockerfile:133-134`）。
- スクリプトは `run` または `serve` 以外の引数で起動した場合、旧変数の確認より前にコマンドを `exec` します。その経路では `REINSTALL` の警告は出ません（`docker/entrypoint.sh:53-56`）。`run` / `serve` の経路では、データディレクトリ作成後の一般警告処理で確認します（同 `:58-82`）。
- OS、GPU backend、モデル状態、他の環境変数による `REINSTALL` の判定差はありません。CLI 引数へ変換したり、設定値を上書きしたりする処理もありません。

## 実行時の詳細

確認は entrypoint の起動中に一度行われます。値が空でない場合の出力は stderr の `[!] REINSTALL is from the older image and is ignored here. See docs/DOCKER.md ("From the older image").` です。これは `warn` 関数が `[!] ` を付けて stderr に出力するためです（`docker/entrypoint.sh:37-39,80-83`）。警告処理そのものは終了コードを変えず、後続の起動処理を続けます（同 `:80-85`）。

Docker の利用者向け説明も、`REINSTALL` を旧イメージの設定名として「ignored with a warning」と記載しています（`docs/DOCKER.md:265-275`）。索引の候補名に対応する実装上の読み取りは上記 entrypoint の動的参照です。その他の完全一致参照は Docker 説明文と benchmark の記録であり、実装根拠にはしていません。

## 根拠

- `docker/entrypoint.sh:80-83` — `HOST`, `LOW_RAM`, `REINSTALL` などの候補名を動的に環境から読み、空でない値に警告する。
- `docker/entrypoint.sh:37-39` — `warn` は `[!] ` を付けて stderr に出す。
- `docker/entrypoint.sh:53-56,58-82` — 任意コマンドへの早期 `exec` と、サーバー起動経路での警告位置。
- `docker/Dockerfile:133-134` — entrypoint と既定 `run` コマンド。
- `docs/DOCKER.md:265-275` — 旧イメージ設定一覧での説明。
