# `STRATA_EXPERIMENTAL_GFX1103`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata Terminal のセットアップで AMD gfx1103（Radeon 780M / 760M / 740M、Phoenix / Hawk Point）を AMD HIP の対応 GPU として扱うかを制御する。名前に「EXPERIMENTAL」とあるが、この checkout では未設定時も有効で、値がちょうど `"0"` のときだけ無効になる。エンジン実行時に読む環境変数ではなく、`terminal/setup.py` の対応アーキテクチャ判定と、`terminal/strata_control/setup_config.py` の run config 作成に使われる。`setup.py` は有効時に Linux の gfx1103 用 config へ setup 管理の環境設定も書き込む。エンジンや GPU driver がこの変数自体を読む実装は確認できない。`terminal/setup.py:4412-4422`、`terminal/strata_control/setup_config.py:452-458`

## 値と判定

値は `os.environ.get("STRATA_EXPERIMENTAL_GFX1103", "1") != "0"` で文字列比較される。数値・真偽値への変換や trim、大文字小文字の正規化はない。`"0"` との完全一致だけが無効である。`setup.py` のモジュール読込時に定数へ保存され、同じプロセス内で後から環境を変えても再評価されない。`terminal/setup.py:4414`

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全 platform / setup の共通判定 | 既定文字列 `"1"` を使うため有効 | 空文字、`1`、`true` / `TRUE`、`false`、`00`、`0anything`、` 0` | 完全一致の `0` |

空文字も「設定ありで無効」にはならず、有効扱いである。CLI 引数による値の上書き、数値境界、fallback はない。`--backend hip` は HIP 経路を選ぶ引数だが、このフラグを個別に上書きしない。`terminal/setup.py:4414, 11595-11629`

## 有効になる条件

- `GFX1103_OPT_IN` が真なら `AMD_ARCHS` に `gfx1103` が追加され、`amd_problem()` が gfx1103 を「未対応」として弾かなくなる。実際の GPU 選択には AMD GPU の検出と、AMD HIP 経路（例: `--backend hip`）が別途必要。`--gpu` / `--gpus` は検出済みの対応 GPU を選ぶもので、gfx1103 を無効設定から再び対応化するものではない。`terminal/setup.py:4421-4422, 4950-4955, 11617-11629`
- GPU の arch は Linux では KFD の情報などから、Windows では HIP runtime または Windows の display adapter 情報から判定される。gfx1103 と一致する判定は完全な arch 名または `gfx1103:` で始まる arch 名であり、別の gfx 世代への前方一致ではない。無効時も検出名自体は `AMD_IGPU_PCI` / Windows 名対応表に残るが、`AMD_ARCHS` 外として利用不可になる。`terminal/setup.py:4533-4537, 4542-4546, 4950-4955, 5030-5035`
- Linux で選択した GPU が gfx1103 の場合、有効設定のときだけ config 生成時に `STRATA_NO_ARENA_THP=1` と `GFX1103_SWITCHES` が `env` に書かれる。Windows ではこの追加処理に `not WIN` の条件があるため、gfx1103 を許可してもこれらの値は setup が追加しない。ここで記すのは Strata が config に書く事実であり、各設定値のエンジン内効果ではない。`terminal/strata_control/setup_config.py:452-458`
- config 再作成時、`STRATA_NO_ARENA_THP` と `GFX1103_SWITCHES` のキーは `SETUP_ENV` に含まれ、setup 管理項目として古い値が引き継がれない。有効時に新しい config が生成する値があればそれが使われ、無効時はこの分岐からは再生成されない。`terminal/setup.py:7460-7463, 7480-7495`
- この変数による判定に特定の model / server mode / build macro 条件はない。AMD GPU を選んだ後、既存 engine / build toolchain など別の条件が失敗すれば利用はできない。Windows で有効にしても、gfx1103 用 ready-made engine をこの変数が提供するわけではない。`terminal/setup.py:4950-4955, 5010-5017, 11617-11645`

## 実行時の詳細

`setup.py` のモジュール初期化時に環境値を読み、`GFX1103_OPT_IN` として保持する。`AMD_ARCHS` の構築、UMA APU 判定 `is_uma_apu()`、および `strata_control.setup_config` が参照する同定数に使われるため、実行中に環境変数だけを変更しても現在のプロセスには反映されない。別のセットアッププロセスを起動し直すと、そのプロセスが起動時の環境から再判定する。`terminal/setup.py:4414, 4421-4422, 4574-4580`、`terminal/strata_control/setup_config.py:158-161`

有効時に gfx1103 が選択されると、setup は gfx1103 を使える GPU として扱い、Linux では run config の `env` に `STRATA_NO_ARENA_THP=1` と次の 17 キーを書き込む。無効時には gfx1103 は対応 GPU リストから外れ、gfx1103 の Linux 専用 env 設定分岐にも入らない。`terminal/strata_control/setup_config.py:433-458`、キー定義は `terminal/setup.py:4430-4437`。

この変数自身を子 engine や server に転送するコードは確認できない。setup が run config に書くのは上記の別名の env 設定であり、この変数は起動後の model request ごとには評価されない。`terminal/strata_control/setup_config.py:452-458`、`terminal/setup.py:4414`

## ログと測定値

gfx1103 を無効にして AMD GPU 経路へ進み、その gfx1103 GPU しか利用可能な GPU がない場合、GPU 一覧では `amd_problem()` の返す `not supported - Strata's AMD backend runs on ... only, this is gfx1103 (an integrated Radeon, not Strix Halo)` が表示され、セットアップは `no AMD GPU Strata can use` で停止する。`fail()` は `[X]` を付けて表示し exit code 1 で終了する。別の対応 AMD GPU があればセットアップ全体は続行できる。`terminal/setup.py:4950-4955, 1049-1056, 11597-11618`

有効時に gfx1103 が選択されたことを示す専用の警告・ログ文言はこの分岐にはない。Strata の測定値はこの文書では扱わない。セットアップの値判定と、それによる対応 GPU / config の変更を説明するための測定条件は該当しない。

## 根拠

- `terminal/setup.py:4412-4422` — 値の既定値・比較、gfx1103 の AMD 対応リストへの追加。
- `terminal/setup.py:4533-4537, 4542-4546, 4574-4580` — GPU arch 判定と UMA APU 条件。
- `terminal/setup.py:4950-4955, 11617-11629` — 非対応時の判定と GPU 選択。
- `terminal/strata_control/setup_config.py:158-161, 433-458` — setup 定数の取り込みと Linux gfx1103 用 config 生成。
- `terminal/setup.py:7460-7463, 7480-7495` — setup が管理する env キーと再実行時の引継ぎ規則。
- `terminal/setup.py:1049-1056` — セットアップのエラー表示と終了コード。
