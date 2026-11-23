# `STRATA_UPDATE_PULLED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。調査対象リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はなかった。

## 役割

`terminal/setup.py` の更新処理が `git pull` 後に新しい `setup.py` を起動するとき、起動先で同じ pull を繰り返さないための内部マーカー。これ自体は更新を開始せず、`--update` が処理されるときだけ参照される。値が厳密に `1` なら pull を省略し、そのまま後続の更新処理へ進む（`terminal/setup.py:8214-8215,8302-8308,11312-11314,11389-11392`）。

`STRATA_UPDATE_PULLED` の定義・参照・子プロセスへの設定は `terminal/setup.py` のみで確認できた。通常のモデル起動やエンジン実行の挙動を変える読み取りはない（`terminal/setup.py:8215,8307,8339`）。

## 値と判定

`os.environ.get(PULLED_ENV) == "1"` で文字列全体を比較する。数値変換、前後空白の除去、大文字小文字変換はない。値が未設定、空文字、または `1` 以外ならマーカーによる skip は起きず、`CONTROL` が偽であれば checkout の確認と pull を試みる（`terminal/setup.py:8307`）。

| 条件 | unset | skip になる値 | skip にならない値 |
|---|---|---|---|
| `--update` の処理中かつ `CONTROL` が偽 | pull を試みる | `1` のみ | ``, `0`, `01`, `1 `, `true`, `TRUE`, `false`, 任意のその他の文字列 |
| `--update` の処理中かつ `CONTROL` が真 | `STRATA_UPDATE_PULLED` の値にかかわらず pull を skip | すべて | なし |

`CONTROL` は `STRATA_CONTROL_INSTALL` が厳密に `1` のとき真になるモジュール定数（起動時評価）で、アプリのインストーラーモードを表す（`terminal/setup.py:97-103`）。

## 有効になる条件

- `setup.py` の引数に `--update` があり、`main()` から `update_pull()` が呼ばれること。通常の起動ではこの変数を参照しない（`terminal/setup.py:11312-11314,11389-11392`）。
- `STRATA_UPDATE_PULLED=1` は `CONTROL` が偽のときに限り pull を抑止する。`CONTROL` が真なら、マーカーの値に関係なく pull を省略する（`terminal/setup.py:8307`）。
- 既存の git checkout で pull が行われるのは、マーカーが `1` でなく、`CONTROL` も偽で、`source_checkout()` が checkout を見つけた場合。git がない、detached HEAD、pull 失敗などは別のエラー経路となる（`terminal/setup.py:8218-8225,8309-8332`）。
- OS、CUDA/HIP/SYCL backend、build macro、モデルの状態による値判定の差はない。Windows とそれ以外で異なるのは案内文・再実行コマンド（`.bat` と `.sh`）である（`terminal/setup.py:8320-8327,8338-8339`）。

## 実行時の詳細

`--update` のとき `update_pull()` が環境から値を読み取る。`STRATA_UPDATE_PULLED=1` または `CONTROL` 真なら `None` を返し、呼び出し元は pull 処理を終えて後続へ進む。マーカーが一致しないときは git checkout を調べ、`git pull -q --ff-only` を行う。pull 後の HEAD が変わらなければ「最新」と表示して通常の同じプロセスで続行する。HEAD が変わった場合は、新しい `setup.py` を元の引数で起動し、子プロセスの環境を親の環境から複製したうえで `STRATA_UPDATE_PULLED=1` に上書きする。新しいプロセスが再び `--update` を処理しても pull を繰り返さない。子プロセスの終了コードは `update_pull()` の戻り値として返される（`terminal/setup.py:8302-8308,8329-8339,11389-11392`）。

変数名はモジュール定数に置かれているが、値は `update_pull()` 呼び出し時に `os.environ.get` で読む。読み取った値を別のキャッシュには保存しない。新しい `setup.py` には明示的に `1` を設定して環境を渡す（`terminal/setup.py:8215,8307,8339`）。

## ログと測定値

マーカーが `1` のとき、マーカー判定による専用ログは出さず、pull 前の「Getting the newest Strata (git pull) ...」も表示しない（`terminal/setup.py:8307,8330`）。値が `1` 以外で pull を開始すると同ログが表示される。変更がなければ「Strata is up to date.」、更新された場合は「Got the newest Strata...」を表示する。git pull が失敗した場合は git の出力を表示し、復旧できない旧履歴や checkout 状態などに応じた案内を出して終了コード `1` を返す（`terminal/setup.py:8284-8293,8320-8336`）。測定値は該当しない。

## 根拠

- `terminal/setup.py:8214-8215` — マーカー名の定義。
- `terminal/setup.py:8302-8339` — 値判定、pull の経路、pull 後の子プロセス起動と環境上書き。
- `terminal/setup.py:97-103` — `CONTROL` の設定とアプリインストーラーモード。
- `terminal/setup.py:11312-11314,11389-11392` — `--update` と `update_pull()` の呼び出し。
- `docs/DETAILS.md:197-198` — 更新についての概説。環境変数や自動 pull の詳しい分岐は記載していないため、本書の挙動説明は対象 commit の `setup.py` に基づく。
