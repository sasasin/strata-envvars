# `MSYS_NO_PATHCONV`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata の Metal 用同期・チェック用 Bash スクリプト 3 件が、後続コマンドの環境へ `MSYS_NO_PATHCONV=1` を設定する。Strata のアプリ本体がこの名前を読み取って動作を変える実装は見つからず、既存値に応じた分岐もない。対象スクリプトは `sync_vis.sh`、`check_mac.sh`、`sync_mac.sh`（`engine/src/hy4flash/metal/sync_vis.sh:2-4`、`engine/src/hy4flash/metal/check_mac.sh:2-4`、`engine/src/hy4flash/metal/sync_mac.sh:2-4`）。

## 値と判定

3 スクリプトはいずれも `export MSYS_NO_PATHCONV=1` を無条件に実行する。Strata は呼び出し元の値を読み取らず、文字列変換・妥当性検査もしない。したがって、呼び出し元で未設定、空文字、`0`、`true` などのどの値であっても、各スクリプト内では `1` に上書きされる。`1` 以外を指定して無効化する分岐はない（`engine/src/hy4flash/metal/sync_vis.sh:4`、`engine/src/hy4flash/metal/check_mac.sh:3`、`engine/src/hy4flash/metal/sync_mac.sh:4`）。

| 実行経路 | 未設定または呼び出し元の設定 | スクリプトが設定する値 | Strata による値判定 |
|---|---|---|---|
| `sync_vis.sh` | いずれも `1` に上書き | `1` | なし |
| `check_mac.sh` | いずれも `1` に上書き | `1` | なし |
| `sync_mac.sh` | いずれも `1` に上書き | `1` | なし |

## 有効になる条件

- Metal のソース同期またはコンパイルチェックのために、上記いずれかのスクリプトを実行したときに設定される。各スクリプトの冒頭コメントは owner PC 上で動かす用途を示し、処理はローカルの `tar` / `scp` / `ssh` コマンドを起動する（`engine/src/hy4flash/metal/sync_vis.sh:2-11`、`engine/src/hy4flash/metal/check_mac.sh:2-6`、`engine/src/hy4flash/metal/sync_mac.sh:2-11`）。
- 対象名の参照はこの 3 件だけで、アプリの CLI、サーバーモード、GPU backend、build macro、モデル状態による有効化条件はない。
- これらのスクリプトを通らない実行経路では、Strata がこの変数を設定する根拠はない。

## 実行時の詳細

スクリプト実行時に、最初の外部コマンドより前に値を設定する。`sync_vis.sh` と `sync_mac.sh` は続けて `tar`、`scp`、`ssh` などを呼び、`check_mac.sh` は `scp` と `ssh` を呼ぶため、エクスポートされた値はそれらのローカル子プロセスの環境に渡される（`engine/src/hy4flash/metal/sync_vis.sh:4-11`、`engine/src/hy4flash/metal/check_mac.sh:3-6`、`engine/src/hy4flash/metal/sync_mac.sh:4-11`）。値をキャッシュする処理や、実行中に再読込する処理はない。スクリプト内で固定値を一度設定するため、起動後に親環境を変えてもその実行中の設定は変わらない。

Strata のソースから確認できるのはローカル子プロセスへの環境設定までであり、リモート側への転送や、`scp` / `ssh` 等がこの変数をどう扱うかは説明対象に含めない。

## 根拠

- `engine/src/hy4flash/metal/sync_vis.sh:2-11` — owner PC 用の同期スクリプト。値を設定してから `tar`、`scp`、`ssh` を実行する。
- `engine/src/hy4flash/metal/check_mac.sh:2-6` — owner PC 用の Metal compile check スクリプト。値を設定してから `scp`、`ssh` を実行する。
- `engine/src/hy4flash/metal/sync_mac.sh:2-11` — owner PC 用の同期スクリプト。値を設定してから `tar`、`scp`、`ssh` を実行する。
